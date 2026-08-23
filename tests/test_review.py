from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from anomaly.acquire import register_local_source
from anomaly.case import create_case
from anomaly.review import (
    ReviewError,
    _hash_json,
    accept_findings,
    draft_findings,
    record_review,
    replay_signals,
    write_report,
)
from anomaly.detectors.registry import package_implementation_hash


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
DETECTOR_HASH = package_implementation_hash(
    Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _attestation(root: Path, reviewer: str) -> dict[str, Any]:
    """Isolated-review attestation bound to the current draft hash."""
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    return {
        "isolated": True,
        "attested_by": reviewer,
        "draft_hash": _hash_json(draft),
        "statement": "Inspected draft, replay, provenance, and previews.",
    }


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _claims(root: Path, filename: str = "findings.json") -> list[dict[str, Any]]:
    payload = _json(root / "findings" / filename)
    return payload["claims"] if isinstance(payload, dict) else payload


def _seed_case(tmp_path: Path, *, categories_same_source: bool = False) -> Path:
    root = tmp_path / "case"
    create_case(
        root,
        title="Quarterly procurement anomalies",
        question="Which payments need review?",
        case_id="case-007",
        now=NOW,
    )

    source = tmp_path / "payments.csv"
    source.write_text(
        "vendor,amount,baseline,api_key\nAcme,12,10,super-secret-token\n"
        "Beta,4,10,super-secret-token\n",
        encoding="utf-8",
    )
    source_record = register_local_source(
        root,
        source,
        source_id="payments",
        now=NOW,
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the locked newsroom drive.",
        included=True,
    )
    source_hash = source_record["content_hash"]

    run = root / "evidence" / "runs" / "run-007"
    run.mkdir(parents=True)
    rows: list[dict[str, Any]] = [
        {
            "signal_id": "signal-accepted",
            "rank": 1,
            "status": "lead",
            "category": "numeric",
            "statement": "Acme is 20% above its baseline.",
            "redacted": True,
            "preview": {"vendor": "Acme", "amount": 12, "baseline": 10},
            "evidence_refs": [{"source_id": "payments", "row": 1}],
            "calculation": {
                "kind": "ratio",
                "numerator": 2,
                "denominator": 10,
                "value": 0.2,
            },
            "source_hash": source_hash,
            "detector_hash": DETECTOR_HASH,
            "run_id": "run-007",
        },
        {
            "signal_id": "signal-rejected",
            "rank": 2,
            "status": "lead",
            "category": "numeric",
            "statement": "Beta is 60% below its baseline.",
            "redacted": True,
            "preview": {"vendor": "Beta", "amount": 4, "baseline": 10},
            "evidence_refs": [{"source_id": "payments", "row": 2}],
            "calculation": {
                "kind": "ratio",
                "numerator": -6,
                "denominator": 10,
                "value": -0.6,
            },
            "source_hash": source_hash,
            "detector_hash": DETECTOR_HASH,
            "run_id": "run-007",
        },
        {
            "signal_id": "signal-unreviewed",
            "rank": 3,
            "status": "lead",
            "category": "missingness",
            "statement": "A third lead remains unresolved.",
            "redacted": True,
            "preview": {"vendor": "Gamma", "missing_fields": ["amount"]},
            "evidence_refs": [{"source_id": "payments", "row": 3}],
            "calculation": {"kind": "count", "value": 1},
            "source_hash": source_hash,
            "detector_hash": DETECTOR_HASH,
            "run_id": "run-007",
        },
    ]
    if categories_same_source:
        rows.extend(
            [
                {
                    "signal_id": "signal-category-a",
                    "claim_id": "claim-category-corroboration",
                    "rank": 4,
                    "status": "lead",
                    "category": "duplicate_rows",
                    "statement": "The same payment appears duplicated.",
                    "redacted": True,
                    "preview": {"vendor": "Acme", "row": 1},
                    "evidence_refs": [{"source_id": "payments", "row": 1}],
                    "calculation": {"kind": "count", "value": 2},
                    "source_hash": source_hash,
                    "detector_hash": DETECTOR_HASH,
                    "run_id": "run-007",
                },
                {
                    "signal_id": "signal-category-b",
                    "claim_id": "claim-category-corroboration",
                    "rank": 5,
                    "status": "lead",
                    "category": "rare_levels",
                    "statement": "The same payment uses a rare vendor level.",
                    "redacted": True,
                    "preview": {"vendor": "Acme", "row": 1},
                    "evidence_refs": [{"source_id": "payments", "row": 1}],
                    "calculation": {"kind": "count", "value": 1},
                    "source_hash": source_hash,
                    "detector_hash": DETECTOR_HASH,
                    "run_id": "run-007",
                },
            ]
        )

    (run / "preview.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (run / "provenance.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-007",
                "detector_id": "numeric.zscore_outliers",
                "detector_version": "1.0.0",
                "detector_hash": DETECTOR_HASH,
                "source_hashes": [source_hash],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "evidence" / "signals.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    (root / "evidence" / "ledger.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "signal_id": row["signal_id"],
                    "source_hash": source_hash,
                    "detector_hash": DETECTOR_HASH,
                    "run_id": "run-007",
                    "evidence_refs": row["evidence_refs"],
                },
                sort_keys=True,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    (root / "detectors" / "used" / "numeric__zscore_outliers.json").write_text(
        json.dumps({"implementation_hash": DETECTOR_HASH, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    return root


def test_draft_findings_uses_ranked_redacted_leads_and_provenance_only(tmp_path: Path) -> None:
    root = _seed_case(tmp_path)

    draft_findings(root)

    payload = _json(root / "findings" / "draft.json")
    claims = payload["claims"]
    assert [claim["claim_id"] for claim in claims] == [
        "claim-accepted",
        "claim-rejected",
        "claim-unreviewed",
    ]
    assert all(claim["status"] == "draft" for claim in claims)
    assert all(claim["signal_ids"] for claim in claims)
    assert all(claim["source_hash"] == _json(root / "data" / "sources.json")[0]["content_hash"] for claim in claims)
    assert "super-secret-token" not in json.dumps(payload)
    assert "api_key" not in json.dumps(payload)


def test_replay_recomputes_calculations_and_rejects_source_or_detector_tampering(
    tmp_path: Path,
) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)

    replay = replay_signals(root)
    assert replay["status"] == "replayed"
    assert replay["claims"][0]["calculation"]["value"] == pytest.approx(0.2)

    source = root / "data" / "raw" / "payments" / "payments.csv"
    source.write_text(source.read_text(encoding="utf-8") + "Evil,999,1,super-secret-token\n", encoding="utf-8")
    with pytest.raises(Exception, match=r"(?i)(hash|tamper|source)"):
        replay_signals(root)

    source.write_text(
        "vendor,amount,baseline,api_key\nAcme,12,10,super-secret-token\nBeta,4,10,super-secret-token\n",
        encoding="utf-8",
    )
    provenance = root / "evidence" / "runs" / "run-007" / "provenance.json"
    payload = _json(provenance)
    payload["detector_hash"] = "sha256:" + ("e" * 64)
    provenance.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    unavailable = replay_signals(root)
    assert unavailable["status"] == "replay-unavailable"
    assert unavailable["replay_possible"] is False


def test_unavailable_reviewer_is_explicit_and_cannot_claim_independent_review(
    tmp_path: Path,
) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)

    record_review(root, reviewer_id=None, verdicts={"claim-accepted": {"verdict": "accepted"}})

    review = _json(root / "findings" / "review.json")
    assert "unavailable" in json.dumps(review).lower()
    # Audit A5: an unavailable review cannot promote anything through Gate B.
    with pytest.raises(ReviewError, match=r"(?i)(attestation|review)"):
        accept_findings(root, ["claim-accepted"])
    assert not (root / "findings" / "findings.json").exists()


def test_legacy_shaped_run_requires_attestation_instead_of_silent_independence(
    tmp_path: Path,
) -> None:
    """Audit A5: a schema-1 run without signals.parquet is attestation-required."""
    root = _seed_case(tmp_path)
    draft_findings(root)

    review = record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )

    assert review["schema_version"] == 2
    assert review["status"] == "unavailable"
    assert review["independent"] is False

    with pytest.raises(ReviewError, match=r"(?i)attestation"):
        accept_findings(root, ["claim-accepted"])
    assert not (root / "findings" / "findings.json").exists()


def test_gate_b_owns_accepted_artifacts_and_receipt_without_mutating_workflow_state(
    tmp_path: Path,
) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)
    draft_before = (root / "findings" / "draft.json").read_bytes()
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={
            "claim-accepted": {"verdict": "accepted", "notes": "replayed"},
            "claim-rejected": {"verdict": "rejected", "notes": "denominator is not justified"},
        },
        independent_attestation=_attestation(root, "reviewer-007"),
    )
    state_before = _json(root / ".anomaly" / "state.json")

    accept_findings(root, ["claim-accepted", "claim-rejected", "claim-unreviewed"])

    assert (root / "findings" / "draft.json").read_bytes() == draft_before
    assert [claim["claim_id"] for claim in _claims(root)] == ["claim-accepted"]
    gate_b = _json(root / ".anomaly" / "receipts" / "gate-b.json")
    assert gate_b["accepted_claim_ids"] == ["claim-accepted"]
    assert _json(root / ".anomaly" / "state.json") == state_before


@pytest.mark.parametrize("replay_hash", [None, "sha256:" + ("f" * 64)])
def test_legacy_gate_b_rejects_replay_without_valid_hash(tmp_path: Path, replay_hash: str | None) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )
    replay_signals(root)
    receipt_path = root / ".anomaly" / "receipts" / "replay.json"
    receipt = _json(receipt_path)
    if replay_hash is None:
        del receipt["replay_hash"]
    else:
        receipt["replay_hash"] = replay_hash
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")

    with pytest.raises(ReviewError, match=r"(?i)(replay|hash|tamper)"):
        accept_findings(root, ["claim-accepted"])
    assert not (root / "findings" / "findings.json").exists()


def test_legacy_gate_b_rejects_review_without_basis_hash(tmp_path: Path) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )
    review_path = root / "findings" / "review.json"
    review = _json(review_path)
    del review["review_basis_hash"]
    review_path.write_text(json.dumps(review) + "\n", encoding="utf-8")

    with pytest.raises(ReviewError, match=r"(?i)(basis|unavailable|review)"):
        accept_findings(root, ["claim-accepted"])
    assert not (root / "findings" / "findings.json").exists()


def test_same_evidence_in_different_categories_is_not_corroboration(tmp_path: Path) -> None:
    root = _seed_case(tmp_path, categories_same_source=True)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={
            "claim-category-corroboration": {
                "verdict": "accepted",
                "signal_ids": ["signal-category-a", "signal-category-b"],
            }
        },
        independent_attestation=_attestation(root, "reviewer-007"),
    )

    accept_findings(root, ["claim-category-corroboration"])

    assert not any(
        claim["claim_id"] == "claim-category-corroboration" for claim in _claims(root)
    )


def test_write_report_preserves_accepted_work_without_completing_case(
    tmp_path: Path,
) -> None:
    root = _seed_case(tmp_path)
    unresolved = (
        "## Missing evidence\n- Vendor ownership records.\n\n"
        "## Open questions\n- Is the baseline comparable?\n\n"
        "## Next steps\n- Request the signed ledger.\n"
    )
    (root / "findings" / "unresolved.md").write_text(unresolved, encoding="utf-8")
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
        independent_attestation=_attestation(root, "reviewer-007"),
    )
    accept_findings(root, ["claim-accepted"])
    state_before_report = _json(root / ".anomaly" / "state.json")
    write_report(root)
    assert _json(root / ".anomaly" / "state.json") == state_before_report

    report = (root / "findings" / "report.md").read_text(encoding="utf-8")
    assert "Acme is 20% above its baseline." in report
    assert "Beta is 60% below its baseline." not in report
    assert "A third lead remains unresolved." not in report
    assert (root / "findings" / "unresolved.md").read_text(encoding="utf-8") == unresolved
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Status: active" in readme
    assert "Last completed phase: P0" in readme


def test_write_report_serializes_dataset_text_as_inert_markdown(
    tmp_path: Path,
) -> None:
    root = _seed_case(tmp_path)
    preview_path = root / "evidence" / "runs" / "run-007" / "preview.json"
    preview = _json(preview_path)
    preview[0]["statement"] = (
        "Acme [click](https://example.invalid/pixel)\n"
        "<img src=https://example.invalid/pixel>\n"
        "## Forged heading"
    )
    preview_path.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
        independent_attestation=_attestation(root, "reviewer-007"),
    )
    accept_findings(root, ["claim-accepted"])

    write_report(root)

    report = (root / "findings" / "report.md").read_text(encoding="utf-8")
    assert "Acme" in report
    assert "[click](https://example.invalid/pixel)" not in report
    assert "<img src=https://example.invalid/pixel>" not in report
    assert "\n## Forged heading" not in report


def test_credentials_never_persist_in_review_findings_or_report(tmp_path: Path) -> None:
    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
        independent_attestation=_attestation(root, "reviewer-007"),
    )
    accept_findings(root, ["claim-accepted"])
    write_report(root)

    generated = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "findings" / "draft.json",
            root / "findings" / "review.json",
            root / "findings" / "findings.json",
            root / "findings" / "report.md",
            root / "README.md",
        )
    )
    assert "super-secret-token" not in generated
    assert "api_key" not in generated
