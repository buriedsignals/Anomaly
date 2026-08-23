from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from anomaly import detect
from anomaly.detectors.registry import package_implementation_hash
from anomaly.events import phase_event
from anomaly.semantics import UnsafeCasePathError, redact_credentials, validate_case_documents


class ReviewError(RuntimeError):
    """A replay, review, or promotion contract was not satisfied."""

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TABLE_ID = re.compile(r"tbl_[0-9a-f]{64}\Z")
_DETECTOR_ID = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\Z")
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|auth(?:entication)?|authorization|credential|password|passwd|secret|token|private[_-]?key)",
    re.I,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|authorization|password|secret|token|private[_-]?key)\s*[:=]\s*(?:Bearer\s+)?[^,;\s]+"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_TOKEN_PREFIX = re.compile(r"\b(?:sk_live_|ghp_|github_pat_|xox[baprs]-|AKIA)[A-Za-z0-9_./+=-]{8,}")

# The fields below are the public, redacted signal contract.  In particular, a
# preview is retained only as a redacted, useful reading and never as a source
# record or arbitrary case-controlled object.
_SIGNAL_FIELDS = {
    "signal_id",
    "claim_id",
    "rank",
    "status",
    "category",
    "severity",
    "statement",
    "redacted",
    "preview",
    "evidence_refs",
    "calculation",
    "source_hash",
    "detector_hash",
    "run_id",
    "detector_id",
    "table_id",
}


@phase_event("P6", "replay_signals")
def replay_signals(root: Path) -> dict[str, Any]:
    """Revalidate source/provenance bindings and recompute signal calculations."""
    root = _root(root)
    basis_status = _replay_basis_status(root)
    if basis_status is not None:
        return basis_status
    sources = _source_records(root)
    source_hashes = {record["source_id"]: record["content_hash"] for record in sources if record["included"]}
    included = [record for record in sources if record["included"]]
    if any(not _owned(root, record["path"]).is_file() for record in included):
        return {"schema_version": 1, "status": "unavailable", "reason": "required source data is missing", "replay_possible": False, "runs": [], "claims": []}
    _verify_source_bytes(root, sources)
    runs_root = _owned(root, "evidence/runs")
    if not included or not runs_root.is_dir() or not any(path.is_dir() for path in runs_root.iterdir()):
        result = {"schema_version": 1, "status": "unavailable", "reason": "required source data or detector runs are missing", "replay_possible": False, "runs": [], "claims": []}
        return result

    replayed: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    if not runs_root.is_dir() or runs_root.is_symlink():
        raise ReviewError("evidence runs are missing")
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if run_dir.is_symlink():
            raise UnsafeCasePathError(str(run_dir))
        preview_path = run_dir / "preview.json"
        provenance_path = run_dir / "provenance.json"
        output_path = run_dir / "signals.parquet"
        if any(path.is_symlink() for path in (preview_path, provenance_path, output_path)):
            raise UnsafeCasePathError(str(run_dir))
        if not preview_path.is_file() or not provenance_path.is_file():
            raise ReviewError(f"incomplete replay inputs for {run_dir.name}")
        preview = _read_json(preview_path)
        provenance = _read_json(provenance_path)
        if not isinstance(preview, list) or not isinstance(provenance, dict):
            raise ReviewError(f"invalid replay inputs for {run_dir.name}")
        try:
            strict = _verify_provenance(run_dir.name, provenance, source_hashes, root)
        except ReviewError as error:
            if _is_detector_dependency_failure(error):
                return _unavailable_replay(str(error), status="replay-unavailable")
            raise
        if strict:
            _verify_prepared_generation(root, provenance)
            if not output_path.is_file():
                raise ReviewError(f"run output is missing: {run_dir.name}")
            _verify_run_hashes(preview_path, output_path, provenance)
        run_signals: list[dict[str, Any]] = []
        for raw in preview:
            if not isinstance(raw, dict):
                raise ReviewError("signal preview must contain records")
            signal = _safe_signal(raw)
            _verify_signal_binding(signal, provenance, source_hashes, strict=strict)
            if strict and not _valid_lead_preview(raw):
                raise ReviewError("signal preview is not a redacted lead")
            if "calculation" in signal:
                signal["calculation"] = _recompute_calculation(signal["calculation"], strict=strict)
            run_signals.append(signal)
            replayed.append(signal)
        runs.append(
            {
                "run_id": run_dir.name,
                "detector_id": provenance.get("detector_id"),
                "detector_hash": provenance.get("detector_hash"),
                "source_hashes": list(provenance.get("source_hashes", [])),
                "table_ids": list(provenance.get("table_ids", [])),
                "signal_count": len(run_signals),
            }
        )
    payload = {"schema_version": 1, "status": "replayed", "runs": runs, "claims": replayed}
    _write_json(root, "evidence/replay.json", payload)
    _write_json(
        root,
        ".anomaly/receipts/replay.json",
        {
            "kind": "replay",
            "status": "replayed",
            "source_hashes": sorted(set(source_hashes.values())),
            "runs": runs,
            "replayed_at": _now(),
            "replay_hash": _hash_json(payload),
        },
    )
    return payload


def _unavailable_replay(reason: str, *, status: str = "unavailable") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": status,
        "reason": reason,
        "replay_possible": False,
        "runs": [],
        "claims": [],
    }


def _is_detector_dependency_failure(error: ReviewError) -> bool:
    message = str(error).casefold()
    return any(
        marker in message
        for marker in (
            "detector provenance snapshot is missing",
            "incomplete detector provenance",
            "detector dependency is unavailable",
        )
    )


def _replay_basis_status(root: Path) -> dict[str, Any] | None:
    review_path = _owned(root, "findings/review.json")
    if not review_path.is_file() or review_path.is_symlink():
        return None
    review = _read_json(review_path)
    expected = review.get("review_basis_hash") if isinstance(review, dict) else None
    if isinstance(expected, str) and expected != _review_basis_hash(root):
        return _unavailable_replay(
            "detector metadata, version, implementation hash, or review inputs changed; rerun detector and review",
            status="replay-unavailable",
        )
    return None


@phase_event("P5", "draft_findings")
def draft_findings(root: Path) -> dict[str, Any]:
    """Create an immutable, redacted draft from ranked signal previews."""
    root = _root(root)
    draft_path = _owned(root, "findings/draft.json")
    if draft_path.exists():
        existing = _read_json(draft_path)
        if not isinstance(existing, dict) or not isinstance(existing.get("claims"), list):
            raise ReviewError("invalid findings draft")
        return existing

    signals = _draft_signals(root)
    grouped: dict[str, dict[str, Any]] = {}
    for signal, provenance in signals:
        claim_id = signal.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            signal_id = signal.get("signal_id")
            if not isinstance(signal_id, str) or not signal_id.strip():
                raise ReviewError("signal is missing signal_id")
            claim_id = signal_id.replace("signal-", "claim-", 1)
        rank = _rank(signal.get("rank"))
        claim = grouped.setdefault(
            claim_id,
            {
                "claim_id": claim_id,
                "status": "draft",
                "rank": rank,
                "statement": _text(signal.get("statement", "")),
                "category": signal.get("category"),
                "categories": [],
                "signal_ids": [],
                "source_hash": signal.get("source_hash") or _first(provenance.get("source_hashes")),
                "detector_hash": signal.get("detector_hash") or provenance.get("detector_hash"),
                "run_ids": [],
                "evidence_refs": [],
                "preview": signal.get("preview", {}),
                "calculation": signal.get("calculation"),
                "provenance": [],
            },
        )
        claim["rank"] = min(claim["rank"], rank)
        _append_unique(claim["signal_ids"], signal.get("signal_id"))
        _append_unique(claim["run_ids"], signal.get("run_id") or provenance.get("run_id"))
        _append_unique(claim["categories"], signal.get("category"))
        for reference in signal.get("evidence_refs", []):
            if reference not in claim["evidence_refs"]:
                claim["evidence_refs"].append(reference)
        provenance_view = {
            "run_id": provenance.get("run_id"),
            "detector_id": provenance.get("detector_id"),
            "detector_hash": provenance.get("detector_hash"),
            "detector_snapshot": provenance.get("detector_snapshot"),
            "query_hash": provenance.get("query_hash"),
            "source_hashes": provenance.get("source_hashes", []),
            "table_ids": provenance.get("table_ids", []),
            "read_only": provenance.get("read_only"),
            "external_access": provenance.get("external_access"),
        }
        if provenance_view not in claim["provenance"]:
            claim["provenance"].append(provenance_view)

    claims = sorted(grouped.values(), key=lambda item: (item["rank"], item["claim_id"]))
    payload = {"schema_version": 1, "status": "draft", "claims": _sanitize(claims)}
    _write_json(root, "findings/draft.json", payload)
    return payload


@phase_event("P6", "record_review")
def record_review(
    root: Path,
    reviewer_id: str | None,
    verdicts: dict[str, Any],
    *,
    independent_attestation: dict[str, Any] | None = None,
    unavailable_inputs: list[Any] | tuple[Any, ...] | None = None,
    replay_gaps: list[Any] | tuple[Any, ...] | None = None,
    unresolved_questions: list[Any] | tuple[Any, ...] | None = None,
    alternatives: list[Any] | tuple[Any, ...] | None = None,
    reviewer_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record an independent review without changing the immutable draft.

    Reviewer context is persisted even when review/replay is unavailable so a
    later journalist can distinguish a missing dependency from an empty
    review.  Values are sanitized before they enter the case.
    """
    root = _root(root)
    draft = _read_json(_owned(root, "findings/draft.json"))
    if not isinstance(draft, dict) or not isinstance(draft.get("claims"), list):
        raise ReviewError("findings draft is required")
    if not isinstance(verdicts, dict):
        raise ReviewError("verdicts must be a mapping")
    claim_ids = {claim.get("claim_id") for claim in draft["claims"] if isinstance(claim, dict)}
    normalized: dict[str, dict[str, Any]] = {}
    for claim_id, value in verdicts.items():
        if claim_id not in claim_ids:
            raise ReviewError(f"unknown claim: {claim_id}")
        if not isinstance(value, dict):
            raise ReviewError("each verdict must be a record")
        verdict = value.get("verdict")
        if verdict not in {"accepted", "rejected", "unresolved"}:
            raise ReviewError("verdict must be accepted, rejected, or unresolved")
        entry = {"verdict": verdict}
        if "notes" in value:
            entry["notes"] = _text(value["notes"])
        if "signal_ids" in value:
            ids = value["signal_ids"]
            if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
                raise ReviewError("signal_ids must be a list of strings")
            draft_claim = next(claim for claim in draft["claims"] if claim.get("claim_id") == claim_id)
            if set(ids) != set(draft_claim.get("signal_ids", [])):
                raise ReviewError("review signal_ids do not match the draft")
            entry["signal_ids"] = list(ids)
        normalized[claim_id] = entry

    reviewer = reviewer_id.strip() if isinstance(reviewer_id, str) and reviewer_id.strip() else None
    if reviewer_context is not None and not isinstance(reviewer_context, dict):
        raise ReviewError("reviewer_context must be a mapping")
    context = reviewer_context or {}
    context_fields = {
        "unavailable_inputs": _review_context_field(
            unavailable_inputs if unavailable_inputs is not None else context.get("unavailable_inputs")
        ),
        "replay_gaps": _review_context_field(
            replay_gaps if replay_gaps is not None else context.get("replay_gaps")
        ),
        "unresolved_questions": _review_context_field(
            unresolved_questions
            if unresolved_questions is not None
            else context.get("unresolved_questions")
        ),
        "alternatives": _review_context_field(
            alternatives if alternatives is not None else context.get("alternatives")
        ),
    }
    draft_hash = _hash_json(draft)
    strict = _strict_case(root)
    attestation: dict[str, Any] | None = None
    if isinstance(independent_attestation, dict):
        attestation = _sanitize(dict(independent_attestation))
    independent = bool(reviewer)
    if strict:
        independent = bool(
            reviewer
            and isinstance(attestation, dict)
            and attestation.get("isolated") is True
            and attestation.get("attested_by") == reviewer
            and attestation.get("draft_hash") == draft_hash
            and isinstance(attestation.get("statement"), str)
            and bool(attestation["statement"].strip())
        )
    payload = {
        "schema_version": 2 if strict else 1,
        "status": "recorded" if independent else "unavailable",
        "reviewer_id": reviewer,
        "independent": independent,
        "availability": "available" if reviewer else "unavailable",
        "draft_hash": draft_hash,
        "review_basis_hash": _review_basis_hash(root),
        "verdicts": _sanitize(normalized),
        **context_fields,
        "recorded_at": _now(),
    }
    if attestation is not None:
        payload["independent_attestation"] = attestation
    _write_json(root, "findings/review.json", payload)
    return payload


def _strict_case(root: Path) -> bool:
    runs_root = _owned(root, "evidence/runs")
    if not runs_root.is_dir() or runs_root.is_symlink():
        return False
    for run_dir in runs_root.iterdir():
        if run_dir.is_symlink() or not run_dir.is_dir():
            continue
        if (run_dir / "signals.parquet").is_file() and not (run_dir / "signals.parquet").is_symlink():
            return True
        provenance_path = run_dir / "provenance.json"
        if provenance_path.is_file() and not provenance_path.is_symlink():
            payload = _read_json(provenance_path)
            # Any recorded provenance makes the case attestation-required:
            # a legacy-shaped run (schema_version 1, no signals.parquet) must
            # never bypass the isolated-review attestation and silently count
            # as independent.
            if isinstance(payload, dict):
                return True
    return False


@phase_event("P7", "accept_findings")
def accept_findings(
    root: Path,
    accepted_claim_ids: list[str] | tuple[str, ...],
    *,
    journalist_id: str | None = None,
    required_journalist_id: str | None = None,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Promote only independently accepted claims through Gate B.

    Existing legacy cases may omit a journalist identity.  New callers can
    bind Gate B to an expected identity with ``required_journalist_id`` (or a
    case state carrying that field); the supplied ``journalist_id`` or
    ``approved_by`` must then match it.
    """
    root = _root(root)
    draft = _read_json(_owned(root, "findings/draft.json"))
    review = _read_json(_owned(root, "findings/review.json"))
    if not isinstance(draft, dict) or not isinstance(review, dict):
        raise ReviewError("draft and review are required")
    state = _read_json(_owned(root, ".anomaly/state.json"))
    if not isinstance(state, dict):
        raise ReviewError("invalid case state")
    configured_identity = (
        required_journalist_id
        if required_journalist_id is not None
        else state.get("required_journalist_id")
    )
    if configured_identity is not None and (
        not isinstance(configured_identity, str) or not configured_identity.strip()
    ):
        raise ReviewError("required journalist identity must be non-empty")
    identity = approved_by if approved_by is not None else journalist_id
    if identity is not None and (not isinstance(identity, str) or not identity.strip()):
        raise ReviewError("journalist approval identity must be non-empty")
    if configured_identity is not None and identity != configured_identity:
        raise ReviewError("required journalist approval is missing or does not match")
    strict = _strict_case(root)
    replay = _require_replay(root, strict)
    unavailable = review.get("status") != "recorded" or review.get("availability") != "available"
    if review.get("draft_hash") != _hash_json(draft):
        raise ReviewError("draft changed after review")
    review_basis_hash = review.get("review_basis_hash")
    if not isinstance(review_basis_hash, str) or review_basis_hash != _review_basis_hash(root):
        if not isinstance(review_basis_hash, str):
            raise ReviewError("review basis hash is required; review is unavailable")
        raise ReviewError("review is invalidated; rerun review after methodology or case inputs changed")
    if strict:
        attestation = review.get("independent_attestation")
        reviewer = review.get("reviewer_id")
        if (
            not isinstance(reviewer, str)
            or not reviewer.strip()
            or review.get("independent") is not True
            or not isinstance(attestation, dict)
            or attestation.get("isolated") is not True
            or attestation.get("attested_by") != reviewer
            or attestation.get("draft_hash") != _hash_json(draft)
            or not isinstance(attestation.get("statement"), str)
            or not attestation["statement"].strip()
        ):
            raise ReviewError("independent isolated review attestation is required")
    if not isinstance(accepted_claim_ids, (list, tuple)):
        raise ReviewError("accepted claim ids must be a list")
    requested = list(accepted_claim_ids)
    if len(set(requested)) != len(requested) or any(not isinstance(item, str) for item in requested):
        raise ReviewError("duplicate or invalid claim id")
    claims = [claim for claim in draft.get("claims", []) if isinstance(claim, dict)]
    by_id = {claim.get("claim_id"): claim for claim in claims}
    verdicts = review.get("verdicts")
    if not isinstance(verdicts, dict):
        raise ReviewError("invalid review")
    if unavailable:
        verdicts = {}
    promoted: list[dict[str, Any]] = []
    for claim_id in requested:
        claim = by_id.get(claim_id)
        verdict = verdicts.get(claim_id, {}).get("verdict") if isinstance(verdicts.get(claim_id), dict) else None
        if claim is None or verdict != "accepted":
            continue
        if _is_same_source_category_claim(claim):
            continue
        promoted.append({**claim, "status": "accepted"})
    promoted.sort(key=lambda item: (item.get("rank", 10**9), item.get("claim_id", "")))
    findings = {"schema_version": 1, "status": "accepted", "claims": _sanitize(promoted)}
    _write_json(root, "findings/findings.json", findings)
    receipt = {
        "kind": "review",
        "gate": "B",
        "draft_identity": "findings/draft.json",
        "draft_hash": _hash_json(draft),
        "review_identity": "findings/review.json",
        "review_hash": _hash_json(review),
        "replay_identity": "evidence/replay.json",
        "replay_hash": _hash_json(replay),
        "replay_status": replay.get("status"),
        "findings_hash": _hash_json(findings),
        "accepted_claim_ids": [claim["claim_id"] for claim in promoted],
        "accepted_by": identity or review.get("reviewer_id"),
        "journalist_id": identity,
        "required_journalist_id": configured_identity,
        "accepted_at": _now(),
    }
    _write_json(root, ".anomaly/receipts/gate-b.json", receipt)
    return findings


def _require_replay(root: Path, strict: bool) -> dict[str, Any]:
    replay_path = _owned(root, "evidence/replay.json")
    receipt_path = _owned(root, ".anomaly/receipts/replay.json")
    if not replay_path.is_file() or not receipt_path.is_file():
        # Strict cases (any recorded run provenance) replay here too: a
        # missing artifact is regenerated or refused with its reason, so a
        # legacy-shaped run can never skip the attestation gate by skipping
        # the explicit replay call.
        replay = replay_signals(root)
        if replay.get("status") != "replayed":
            raise ReviewError(
                replay.get("reason", "replay is unavailable; rerun detectors and review")
            )
    else:
        replay = _read_json(replay_path)
    receipt = _read_json(receipt_path)
    sources = _source_records(root)
    _verify_source_bytes(root, sources)
    current_source_hashes = sorted(
        {record["content_hash"] for record in sources if record["included"]}
    )
    replay_hash = receipt.get("replay_hash") if isinstance(receipt, dict) else None
    valid_hash = isinstance(replay_hash, str) and replay_hash == _hash_json(replay)
    receipt_source_hashes = receipt.get("source_hashes") if isinstance(receipt, dict) else None
    valid_source_hashes = (
        isinstance(receipt_source_hashes, list)
        and sorted(receipt_source_hashes) == current_source_hashes
        and all(
            isinstance(item, str) and _SHA256.fullmatch(item)
            for item in receipt_source_hashes
        )
    )
    if (
        not isinstance(replay, dict)
        or replay.get("status") != "replayed"
        or not isinstance(receipt, dict)
        or receipt.get("kind") != "replay"
        or receipt.get("status") != "replayed"
        or not valid_hash
        or not valid_source_hashes
    ):
        raise ReviewError("invalid, stale, or tampered replay artifact")
    return replay


def _review_basis_hash(root: Path) -> str:
    paths = (
        "instructions/methodology.md",
        "instructions/context.md",
        "instructions/data-dictionary.md",
        "instructions/handling.md",
        "data/sources.json",
        "detectors/plan.json",
    )
    digest = hashlib.sha256()
    for relative in paths:
        path = _owned(root, relative)
        digest.update(relative.encode())
        digest.update(path.read_bytes() if path.is_file() else b"<missing>")
    snapshots = _owned(root, "detectors/used")
    if snapshots.is_dir() and not snapshots.is_symlink():
        for path in sorted(snapshots.glob("*.json")):
            if path.is_symlink():
                continue
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
            detector_id = path.stem.replace("__", ".")
            digest.update(detector_id.encode())
            digest.update(_live_detector_fingerprint(detector_id))
    return "sha256:" + digest.hexdigest()


def _verify_prepared_generation(root: Path, provenance: dict[str, Any]) -> None:
    manifest_path = _owned(root, "data/prepared/transforms.json")
    index_path = _owned(root, "data/index.duckdb")
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or not index_path.is_file()
        or index_path.is_symlink()
        or provenance.get("prepared_manifest_hash") != _sha256_bytes(manifest_path.read_bytes())
        or provenance.get("index_hash") != _sha256_bytes(index_path.read_bytes())
    ):
        raise ReviewError("prepared data or index changed after detector run")
    manifest = _read_json(manifest_path)
    tables = manifest.get("tables") if isinstance(manifest, dict) else None
    expected = provenance.get("prepared_tables")
    table_sources = provenance.get("table_sources")
    if not isinstance(tables, list) or not isinstance(expected, dict) or not isinstance(table_sources, dict):
        raise ReviewError("prepared generation provenance is incomplete")
    current: dict[str, dict[str, Any]] = {}
    for table in tables:
        if not isinstance(table, dict) or not isinstance(table.get("table_id"), str):
            raise ReviewError("invalid prepared generation")
        table_id = table["table_id"]
        prepared = table.get("prepared")
        source = table.get("source")
        declared = expected.get(table_id)
        source_declared = table_sources.get(table_id)
        if not isinstance(prepared, dict) or not isinstance(source, dict):
            raise ReviewError("invalid prepared table provenance")
        if (
            not isinstance(declared, dict)
            or not isinstance(source_declared, dict)
            or prepared.get("sha256") != declared.get("hash")
            or source.get("sha256") != source_declared.get("source_hash")
        ):
            raise ReviewError("prepared table provenance mismatch")
        path = _owned(root, prepared.get("path"))
        if not path.is_file() or path.is_symlink() or _sha256_bytes(path.read_bytes()) != prepared.get("sha256"):
            raise ReviewError("prepared table artifact changed")
        current[table_id] = table
    if set(current) != set(expected) or set(current) != set(provenance.get("table_ids", [])):
        raise ReviewError("prepared table set changed")


@phase_event("P7", "write_report")
def write_report(
    root: Path,
    *,
    complete_readme: bool = True,
) -> dict[str, Any]:
    """Write a redacted report and relative case links from Gate-B findings."""
    root = _root(root)
    findings = _read_json(_owned(root, "findings/findings.json"))
    receipt = _read_json(_owned(root, ".anomaly/receipts/gate-b.json"))
    review_path = _owned(root, "findings/review.json")
    replay_path = _owned(root, "evidence/replay.json")
    if (
        not isinstance(findings, dict)
        or findings.get("status") != "accepted"
        or not isinstance(receipt, dict)
        or receipt.get("kind") != "review"
        or receipt.get("gate") != "B"
        or receipt.get("findings_hash") != _hash_json(findings)
        or receipt.get("accepted_claim_ids")
        != [
            claim.get("claim_id")
            for claim in findings.get("claims", [])
            if isinstance(claim, dict)
        ]
        or not review_path.is_file()
        or receipt.get("review_hash") != _hash_json(_read_json(review_path))
        or not replay_path.is_file()
        or receipt.get("replay_hash") != _hash_json(_read_json(replay_path))
        or receipt.get("replay_status") != "replayed"
    ):
        raise ReviewError("hash-bound Gate B receipt is required")
    claims = findings.get("claims")
    if not isinstance(claims, list):
        raise ReviewError("invalid accepted findings")
    unresolved_path = _owned(root, "findings/unresolved.md")
    if not unresolved_path.exists():
        _write_text(root, "findings/unresolved.md", "")
    lines = ["# Findings report", "", "## Accepted findings", ""]
    if claims:
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_id = _redact_text(_text(claim.get("claim_id", "claim")))
            statement = (
                _redact_text(_text(claim.get("statement", "")).strip())
                or "(statement unavailable)"
            )
            lines.extend([f"### {claim_id}", "", statement, ""])
    else:
        lines.extend(["No claims were accepted at Gate B.", ""])
    lines.extend(
        ["## Unresolved work", "", "See [unresolved work](unresolved.md).", ""]
    )
    _write_text(
        root,
        "findings/report.md",
        _redact_text("\n".join(lines)),
    )
    unresolved = unresolved_path.read_text(encoding="utf-8")
    _write_text(root, "findings/unresolved.md", _redact_text(unresolved))
    if complete_readme:
        complete_report_readme(root)
    return {
        "status": "complete",
        "report": "findings/report.md",
        "findings": "findings/findings.json",
    }


def complete_report_readme(root: Path) -> None:
    """Project P7 completion only after all final outputs have succeeded."""
    root = _root(root)
    for relative in ("findings/findings.json", "findings/report.md"):
        path = _owned(root, relative)
        if not path.is_file() or path.is_symlink():
            raise ReviewError(f"final report output is missing: {relative}")
    readme_path = _owned(root, "README.md")
    readme = (
        readme_path.read_text(encoding="utf-8")
        if readme_path.is_file()
        else "# Case\n"
    )
    readme = re.sub(r"(?m)^Status: .*?$", "Status: complete", readme)
    if "Status: complete" not in readme:
        readme = readme.rstrip() + "\n\nStatus: complete\n"
    readme = re.sub(
        r"(?m)^Last completed phase: .*?$",
        "Last completed phase: P7",
        readme,
    )
    if "Last completed phase: P7" not in readme:
        readme = readme.rstrip() + "\nLast completed phase: P7\n"
    links = (
        "\n## Outputs\n\n"
        "- [accepted findings](findings/findings.json)\n"
        "- [report](findings/report.md)\n"
        "- [unresolved work](findings/unresolved.md)\n"
    )
    readme = re.sub(r"\n## Outputs\n.*\Z", "\n", readme, flags=re.S)
    _write_text(root, "README.md", _redact_text(readme.rstrip() + "\n" + links))


def _draft_signals(root: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    signals: list[tuple[dict[str, Any], dict[str, Any]]] = []
    runs_root = _owned(root, "evidence/runs")
    if not runs_root.is_dir() or runs_root.is_symlink():
        raise ReviewError("evidence runs are missing")
    sources = _source_records(root)
    source_hashes = {record["source_id"]: record["content_hash"] for record in sources if record["included"]}
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if run_dir.is_symlink():
            raise UnsafeCasePathError(str(run_dir))
        preview_path, provenance_path = run_dir / "preview.json", run_dir / "provenance.json"
        output_path = run_dir / "signals.parquet"
        if any(path.is_symlink() for path in (preview_path, provenance_path, output_path)):
            raise UnsafeCasePathError(str(run_dir))
        if not preview_path.is_file() or not provenance_path.is_file():
            raise ReviewError(f"incomplete draft inputs for {run_dir.name}")
        preview, provenance = _read_json(preview_path), _read_json(provenance_path)
        if not isinstance(preview, list) or not isinstance(provenance, dict):
            raise ReviewError(f"invalid draft inputs for {run_dir.name}")
        strict = _verify_provenance(run_dir.name, provenance, source_hashes, root)
        if strict:
            if not output_path.is_file():
                raise ReviewError(f"run output is missing: {run_dir.name}")
            _verify_run_hashes(preview_path, output_path, provenance)
        for raw in preview:
            if not isinstance(raw, dict):
                raise ReviewError("signal preview must contain records")
            signal = _safe_signal(raw)
            _verify_signal_binding(signal, provenance, source_hashes, strict=strict)
            if strict and not _valid_lead_preview(raw):
                raise ReviewError("signal preview is not a redacted lead")
            signals.append((signal, provenance))
    signals.sort(key=lambda item: (_rank(item[0].get("rank")), str(item[0].get("signal_id", ""))))
    return signals


def _valid_lead_preview(raw: dict[str, Any]) -> bool:
    return (
        raw.get("status") == "lead"
        and raw.get("redacted") is True
        and isinstance(raw.get("signal_id"), str)
        and bool(raw["signal_id"].strip())
        and isinstance(raw.get("preview"), dict)
        and isinstance(raw.get("evidence_refs"), list)
        and isinstance(raw.get("statement"), str)
        and bool(raw["statement"].strip())
        and isinstance(raw.get("category"), str)
        and isinstance(raw.get("rank"), int)
        and not isinstance(raw.get("rank"), bool)
    )

def _verify_provenance(
    run_id: str,
    provenance: dict[str, Any],
    source_hashes: dict[str, str],
    root: Path,
) -> bool:
    if provenance.get("run_id", run_id) != run_id:
        raise ReviewError("provenance run id mismatch")
    detector_hash = provenance.get("detector_hash")
    if not isinstance(detector_hash, str) or _SHA256.fullmatch(detector_hash) is None:
        raise ReviewError("invalid detector provenance hash")
    source_list = provenance.get("source_hashes", [])
    if not isinstance(source_list, list) or any(
        not isinstance(item, str) or _SHA256.fullmatch(item) is None for item in source_list
    ):
        raise ReviewError("invalid source provenance hashes")
    strict = provenance.get("schema_version") == 2 or _owned(
        root, f"evidence/runs/{run_id}/signals.parquet"
    ).is_file()
    if strict:
        if (
            not source_list
            or any(item not in source_hashes.values() for item in source_list)
            or provenance.get("read_only") is not True
            or provenance.get("external_access") is not False
        ):
            raise ReviewError("incomplete source or execution provenance")
        detector_id = provenance.get("detector_id")
        table_ids = provenance.get("table_ids")
        query_hash = provenance.get("query_hash")
        snapshot = provenance.get("detector_snapshot")
        snapshot_hash = provenance.get("detector_snapshot_hash")
        if (
            not isinstance(detector_id, str)
            or _DETECTOR_ID.fullmatch(detector_id) is None
            or not detector_id.strip()
            or not isinstance(table_ids, list)
            or not table_ids
            or any(not isinstance(item, str) or _TABLE_ID.fullmatch(item) is None for item in table_ids)
            or len(set(table_ids)) != len(table_ids)
            or not isinstance(query_hash, str)
            or _SHA256.fullmatch(query_hash) is None
            or not isinstance(snapshot, str)
            or not isinstance(snapshot_hash, str)
            or _SHA256.fullmatch(snapshot_hash) is None
        ):
            raise ReviewError("incomplete detector provenance")
        table_sources = provenance.get("table_sources")
        if (
            not isinstance(table_sources, dict)
            or set(table_sources) != set(table_ids)
            or set(source_list) != {
                item.get("source_hash") for item in table_sources.values() if isinstance(item, dict)
            }
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("source_id"), str)
                or item.get("source_id") not in source_hashes
                or item.get("source_hash") != source_hashes[item["source_id"]]
                for item in table_sources.values()
            )
            or snapshot != f"detectors/used/{detector_id.replace('.', '__')}.json"
        ):
            raise ReviewError("incomplete table source provenance")
        snapshot_path = _owned(root, snapshot)
        if not snapshot_path.is_file() or snapshot_path.is_symlink():
            raise ReviewError("detector provenance snapshot is missing")
        snapshot_payload = _read_json(snapshot_path)
        if (
            not isinstance(snapshot_payload, dict)
            or snapshot_payload.get("implementation_hash") != detector_hash
            or _hash_json(snapshot_payload) != snapshot_hash
        ):
            raise ReviewError("detector snapshot does not match provenance")
        query_path = _detector_query_path(detector_id)
        current = _current_detector_identity(detector_id)
        if current is None:
            raise ReviewError("detector dependency is unavailable")
        if current["query_hash"] != query_hash:
            raise ReviewError("detector query hash does not match provenance")
        if current["implementation_hash"] != detector_hash:
            raise ReviewError(
                "detector implementation identity does not match provenance"
            )
    elif source_list and any(item not in source_hashes.values() for item in source_list):
        raise ReviewError("source provenance hash is not registered")
    # Legacy provenance remains readable, but never weakens the live detector
    # identity gate. Without a complete identity, replay is unavailable.
    detector_id = provenance.get("detector_id")
    if not isinstance(detector_id, str) or _DETECTOR_ID.fullmatch(detector_id) is None:
        raise ReviewError("detector identity is unavailable")
    snapshot = _owned(root, f"detectors/used/{detector_id.replace('.', '__')}.json")
    if not snapshot.is_file() or snapshot.is_symlink():
        raise ReviewError("detector provenance snapshot is missing")
    snapshot_payload = _read_json(snapshot)
    if (
        not isinstance(snapshot_payload, dict)
        or snapshot_payload.get("implementation_hash") != detector_hash
        or not isinstance(snapshot_payload.get("version"), str)
        or provenance.get("detector_version", snapshot_payload.get("version"))
        != snapshot_payload.get("version")
    ):
        raise ReviewError("incomplete detector provenance")
    current = _current_detector_identity(detector_id)
    if current is None:
        raise ReviewError("detector dependency is unavailable")
    if current["implementation_hash"] != detector_hash or current["version"] != snapshot_payload["version"]:
        raise ReviewError("detector identity does not match live implementation")
    return strict


def _detector_query_path(detector_id: str) -> Path:
    return Path(__file__).resolve().parents[2] / "detectors" / Path(*detector_id.split(".")) / "query.sql"


def _detector_package_path(detector_id: str) -> Path:
    return _detector_query_path(detector_id).parent


def _current_detector_identity(detector_id: str) -> dict[str, str] | None:
    package = _detector_package_path(detector_id)
    metadata_path = package / "meta.yaml"
    query_path = package / "query.sql"
    if any(path.is_symlink() or not path.is_file() for path in (metadata_path, query_path)):
        return None
    try:
        metadata = detect._parse_restricted_yaml(metadata_path.read_text(encoding="utf-8"))
        metadata_bytes = metadata_path.read_bytes()
        query_bytes = query_path.read_bytes()
    except (OSError, UnicodeError, ValueError, TypeError, detect.DetectorError):
        return None
    if not isinstance(metadata, dict) or metadata.get("id") != detector_id:
        return None
    version = metadata.get("version")
    if not isinstance(version, str) or not version:
        return None
    return {
        "version": version,
        "query_hash": _sha256_bytes(query_bytes),
        "metadata_hash": _sha256_bytes(metadata_bytes),
        "implementation_hash": package_implementation_hash(package),
    }


def _live_detector_fingerprint(detector_id: str) -> bytes:
    identity = _current_detector_identity(detector_id)
    if identity is None:
        return b"<detector-unavailable>"
    return json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _verify_run_hashes(preview_path: Path, output_path: Path, provenance: dict[str, Any]) -> None:
    if provenance.get("preview_hash") != _sha256_bytes(preview_path.read_bytes()):
        raise ReviewError("preview artifact hash mismatch")
    if provenance.get("output_hash") != _sha256_bytes(output_path.read_bytes()):
        raise ReviewError("run output hash mismatch")

def _verify_signal_binding(
    signal: dict[str, Any],
    provenance: dict[str, Any],
    source_hashes: dict[str, str],
    *,
    strict: bool = False,
) -> None:
    if strict:
        for field in ("run_id", "detector_id", "detector_hash"):
            if field not in signal or signal.get(field) != provenance.get(field):
                raise ReviewError(f"signal {field} binding mismatch")
    elif signal.get("run_id", provenance.get("run_id")) != provenance.get("run_id"):
        raise ReviewError("signal run binding mismatch")
    elif signal.get("detector_hash", provenance.get("detector_hash")) != provenance.get("detector_hash"):
        raise ReviewError("signal detector hash mismatch")
    source_hash = signal.get("source_hash")
    if strict and (not isinstance(source_hash, str) or source_hash not in source_hashes.values()):
        raise ReviewError("signal source hash is required")
    if source_hash is not None and (
        source_hash not in source_hashes.values()
        or source_hash not in provenance.get("source_hashes", [source_hash])
    ):
        raise ReviewError("signal source hash mismatch")
    table_id = signal.get("table_id")
    table_ids = provenance.get("table_ids", [])
    if strict and (not isinstance(table_id, str) or table_id not in table_ids):
        raise ReviewError("signal table binding is required")
    if table_id is not None and table_id not in table_ids:
        raise ReviewError("signal table binding mismatch")
    table_source = provenance.get("table_sources", {}).get(table_id) if isinstance(provenance.get("table_sources"), dict) else None
    if strict and (
        not isinstance(table_source, dict)
        or source_hash != table_source.get("source_hash")
    ):
        raise ReviewError("signal source/table binding mismatch")
    refs = signal.get("evidence_refs", [])
    if strict and (not isinstance(refs, list) or not refs):
        raise ReviewError("signal evidence references are required")
    if refs is not None:
        if not isinstance(refs, list):
            raise ReviewError("evidence_refs must be a list")
        for ref in refs:
            if not isinstance(ref, dict):
                raise ReviewError("evidence reference must be a record")
            source_id = ref.get("source_id")
            ref_table_id = ref.get("table_id")
            if strict and (
                not isinstance(source_id, str)
                or source_id not in source_hashes
                or not isinstance(ref_table_id, str)
                or ref_table_id != table_id
                or not isinstance(table_source, dict)
                or source_id != table_source.get("source_id")
            ):
                raise ReviewError("evidence reference is not bound")
            if source_id is not None and source_id not in source_hashes:
                raise ReviewError("evidence source is not registered")

def _recompute_calculation(calculation: Any, *, strict: bool = True) -> Any:
    if not isinstance(calculation, dict):
        if strict:
            raise ReviewError("calculation must be a record")
        return calculation
    result = dict(calculation)
    kind = result.get("kind")
    if not isinstance(kind, str):
        raise ReviewError("calculation kind is required")
    numeric = (int, float)

    def number_from_value(value: Any) -> float | int:
        if isinstance(value, bool) or not isinstance(value, numeric):
            raise ReviewError("invalid calculation operand")
        try:
            if not math.isfinite(float(value)):
                raise ReviewError("non-finite calculation operand")
        except (OverflowError, ValueError) as error:
            raise ReviewError("non-finite calculation operand") from error
        return value

    def number(name: str) -> float | int:
        return number_from_value(result.get(name))

    if kind in {"ratio", "relative_difference", "percentage"}:
        numerator, denominator = number("numerator"), number("denominator")
        if denominator == 0:
            raise ReviewError("calculation denominator is zero")
        expected = numerator / denominator
    elif kind in {"difference", "delta"}:
        expected = number("current") - number("previous")
    elif kind == "zscore":
        stddev = number("stddev")
        if stddev == 0:
            raise ReviewError("calculation standard deviation is zero")
        expected = (number("value_input") - number("mean")) / stddev
    elif kind == "count":
        count = result.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            if strict:
                raise ReviewError("invalid count calculation")
            return result
        expected = count
    elif kind in {"sum", "mean"}:
        values = result.get("values")
        if (
            not isinstance(values, list)
            or not values
            or any(isinstance(item, bool) or not isinstance(item, numeric) for item in values)
        ):
            raise ReviewError("invalid aggregate calculation")
        values = [number_from_value(item) for item in values]
        expected = sum(values) if kind == "sum" else sum(values) / len(values)
    else:
        raise ReviewError(f"unknown calculation kind: {kind}")
    actual = result.get("value")
    if isinstance(actual, bool) or not isinstance(actual, numeric):
        raise ReviewError("calculation value is missing")
    try:
        if not math.isfinite(float(actual)) or not math.isfinite(float(expected)):
            raise ReviewError("calculation value is non-finite")
    except (OverflowError, ValueError) as error:
        raise ReviewError("calculation value is non-finite") from error
    if abs(float(actual) - float(expected)) > 1e-12:
        raise ReviewError("calculation value does not match operands")
    result["value"] = expected
    return result


def _is_same_source_category_claim(claim: dict[str, Any]) -> bool:
    categories = {item for item in claim.get("categories", []) if isinstance(item, str)}
    if len(categories) < 2:
        return False
    source_ids = {ref.get("source_id") for ref in claim.get("evidence_refs", []) if isinstance(ref, dict) and ref.get("source_id")}
    return len(source_ids) <= 1


def _source_records(root: Path) -> list[dict[str, Any]]:
    try:
        sources, _ = validate_case_documents(root)
    except Exception as error:
        raise ReviewError(f"invalid case documents: {error}") from error
    return sources


def _verify_source_bytes(root: Path, sources: list[dict[str, Any]]) -> None:
    for source in sources:
        if not source["included"]:
            continue
        path = _owned(root, source["path"])
        if not path.is_file() or path.is_symlink():
            raise ReviewError(f"source is missing: {source['source_id']}")
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source["content_hash"]:
            raise ReviewError(f"source hash mismatch: {source['source_id']}")


def _safe_signal(raw: dict[str, Any]) -> dict[str, Any]:
    return _sanitize({key: raw[key] for key in _SIGNAL_FIELDS if key in raw})


def _review_context_field(value: Any) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ReviewError("review context fields must be lists")
    return _sanitize(list(value))

def _sanitize(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return None
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for name, item in value.items():
            if not isinstance(name, str) or _SENSITIVE_KEY.search(name):
                continue
            output[name] = _sanitize(item, name)
        return output
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact_text(str(redact_credentials(value)))
    return value


def _redact_text(text: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    value = _BEARER.sub("Bearer [redacted]", value)
    return _TOKEN_PREFIX.sub("[redacted]", value)

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReviewError(f"invalid JSON: {path.name}") from error


def _write_json(root: Path, relative: str, payload: Any) -> None:
    _write_text(root, relative, json.dumps(_sanitize(payload), sort_keys=True, indent=2) + "\n")


def _write_text(root: Path, relative: str, text: str) -> None:
    path = _owned(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _owned(root: Path, relative: str) -> Path:
    base = Path(root).resolve()
    path = (base / relative).resolve()
    if path != base and base not in path.parents:
        raise UnsafeCasePathError(relative)
    if path != base:
        current = base
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise UnsafeCasePathError(relative)
    return path


def _root(root: Path) -> Path:
    value = Path(root).resolve()
    if not value.is_dir():
        raise ReviewError("case root is not a directory")
    return value


def _hash_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rank(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 10**9


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None


def _append_unique(values: list[Any], value: Any) -> None:
    if value is not None and value not in values:
        values.append(value)
