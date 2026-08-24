from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from anomaly.acquire import register_local_source
from anomaly.case import create_case
from anomaly.events import log_event
from anomaly.prepare import prepare_sources
from anomaly.profile import profile_prepared
from anomaly.recommend import approve_detector_plan, recommend_detectors

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _events(root: Path) -> list[dict[str, Any]]:
    path = root / ".anomaly" / "events.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _seed_source(tmp_path: Path) -> Path:
    source = tmp_path / "payments.csv"
    source.write_text(
        "id,vendor,amount\n1,Acme,10\n2,Beta,20\n3,Acme,10\n4,Gamma,\n",
        encoding="utf-8",
    )
    return source


def _walk(tmp_path: Path) -> Path:
    """Drive the full happy-path local-API sequence P1 through P7."""
    root = tmp_path / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-events",
        now=NOW,
    )
    register_local_source(
        root,
        _seed_source(tmp_path),
        source_id="payments",
        now=NOW,
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the locked newsroom drive.",
        included=True,
    )
    prepare_sources(root, now=NOW)
    profile_prepared(root, now=NOW)
    plan = recommend_detectors(root, now=NOW)
    approve_detector_plan(
        root, plan["recommended"], approved_by="journalist", now=NOW
    )
    from anomaly.detect import execute_detectors

    execute_detectors(root, plan["recommended"], now=NOW)
    return root


def _seed_reviewable_run(root: Path) -> None:
    """Swap the real P4 runs for a seeded lead so replay stays in its
    non-strict contract, mirroring the seeding pattern used by test_review."""
    import shutil

    from anomaly.detectors.registry import package_implementation_hash

    detector_hash = package_implementation_hash(
        Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"
    )
    source_hash = json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))[
        0
    ]["content_hash"]
    runs_root = root / "evidence" / "runs"
    for run_dir in runs_root.iterdir():
        shutil.rmtree(run_dir)
    run = runs_root / "run-007"
    run.mkdir()
    rows = [
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
            "detector_hash": detector_hash,
            "run_id": "run-007",
        }
    ]
    (run / "preview.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (run / "provenance.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-007",
                "detector_id": "numeric.zscore_outliers",
                "detector_version": "1.0.0",
                "detector_hash": detector_hash,
                "source_hashes": [source_hash],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "evidence" / "signals.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (root / "evidence" / "ledger.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "signal_id": row["signal_id"],
                    "source_hash": source_hash,
                    "detector_hash": detector_hash,
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
        json.dumps({"implementation_hash": detector_hash, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )


def test_case_walk_appends_phase_events_for_every_mainline_call(tmp_path: Path) -> None:
    root = _walk(tmp_path)
    _seed_reviewable_run(root)
    from anomaly.review import (
        _hash_json,
        accept_findings,
        draft_findings,
        record_review,
        replay_signals,
        write_report,
    )
    from anomaly.report import generate_charts

    draft_findings(root)
    replay_signals(root)
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    claim_ids = [claim["claim_id"] for claim in draft["claims"]]
    assert claim_ids, "expected at least one drafted claim"
    record_review(
        root,
        "reviewer-007",
        {claim_ids[0]: {"verdict": "accepted", "notes": "replay and wording hold"}},
        independent_attestation={
            "isolated": True,
            "attested_by": "reviewer-007",
            "draft_hash": _hash_json(draft),
            "statement": "Inspected draft, replay, provenance, and previews.",
        },
    )
    accept_findings(root, claim_ids[:1])
    write_report(root)
    generate_charts(root)

    expected = [
        ("P1", "register_local_source"),
        ("P2", "prepare_sources"),
        ("P2", "profile_prepared"),
        ("P3", "recommend_detectors"),
        ("P3", "approve_detector_plan"),
        ("P4", "execute_detectors"),
        ("P5", "draft_findings"),
        ("P6", "replay_signals"),
        ("P6", "record_review"),
        ("P7", "accept_findings"),
        ("P7", "write_report"),
        ("P7", "generate_charts"),
    ]
    observed = [
        (event["phase"], event["event"])
        for event in _events(root)
        if event.get("source") == "api"
    ]
    assert observed == expected


def test_failed_mainline_call_appends_failure_event_and_still_raises(tmp_path: Path) -> None:
    from anomaly.semantics import UnsafeCasePathError

    root = tmp_path / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-events-failure",
        now=NOW,
    )
    source = _seed_source(tmp_path)
    kwargs: dict[str, Any] = dict(
        source_id="payments",
        now=NOW,
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the locked newsroom drive.",
        included=True,
    )
    register_local_source(root, source, **kwargs)
    baseline = len(_events(root))

    with pytest.raises(UnsafeCasePathError):
        register_local_source(root, source, **kwargs)

    failures = [event for event in _events(root)[baseline:] if event["event"].endswith("_failed")]
    assert any(
        event["phase"] == "P1" and event["event"] == "register_local_source_failed"
        for event in failures
    )


def test_event_store_failure_never_breaks_the_api_call(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-events-broken-store",
        now=NOW,
    )
    # Make the event store unwritable: the JSONL path is now a directory.
    (root / ".anomaly" / "events.jsonl").unlink()
    (root / ".anomaly" / "events.jsonl").mkdir()

    record = register_local_source(
        root,
        _seed_source(tmp_path),
        source_id="payments",
        now=NOW,
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the locked newsroom drive.",
        included=True,
    )

    assert record["source_id"] == "payments"
    assert (root / "data" / "sources.json").is_file()


def test_log_event_redacts_secrets_and_survives_an_unwritable_store(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Redaction check",
        question="Are secrets kept out?",
        case_id="case-redaction",
        now=NOW,
    )

    payload = log_event(root, "P1", "manual_check", detail="token sk_live_ABCDEFGHIJK123 leaked")

    assert payload is not None
    assert payload["event"] == "manual_check"
    assert payload["phase"] == "P1"
    assert "at" in payload
    stored = _events(root)[-1]
    assert "sk_live_" not in json.dumps(stored)
    assert "[redacted]" in stored["detail"]

    (root / ".anomaly" / "events.jsonl").unlink()
    (root / ".anomaly" / "events.jsonl").mkdir()
    assert log_event(root, "P1", "unwritable", detail="ignored") is None


def test_log_event_does_not_invent_state_for_a_missing_case(tmp_path: Path) -> None:
    missing = tmp_path / "not-a-case"

    assert log_event(missing, "P1", "orphan_call") is not None


def test_direct_log_event_rejects_a_symlinked_store_without_external_append(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Event containment",
        question="Can a direct event write escape the case?",
        case_id="case-event-containment",
        now=NOW,
    )
    external = tmp_path / "external-anomaly"
    (root / ".anomaly").replace(external)
    (root / ".anomaly").symlink_to(external, target_is_directory=True)
    events = external / "events.jsonl"
    before = events.read_bytes()

    payload = log_event(root, "P1", "redirected")

    assert payload is None
    assert events.read_bytes() == before
