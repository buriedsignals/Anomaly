"""End-to-end documented-path walk over a real detector run (audit issue A1).

SKILL.md step 7 executes real built-in detectors whose provenance must replay
against the live registry identity; every later step through charts depends on
that working. These tests drive the documented local-API sequence unseeded.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anomaly.acquire import register_local_source
from anomaly.case import create_case
from anomaly.detect import execute_detectors
from anomaly.detectors.registry import package_implementation_hash
from anomaly.prepare import prepare_sources
from anomaly.profile import profile_prepared
from anomaly.recommend import approve_detector_plan, recommend_detectors
from anomaly.report import generate_charts
from anomaly.review import (
    _hash_json,
    accept_findings,
    draft_findings,
    record_review,
    replay_signals,
    write_report,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _source(tmp_path: Path) -> Path:
    rows = ["id,vendor,amount,baseline"]
    for index, amount in enumerate((25, 14, 30, 8, 9, 39, 11, 28, 8), start=1):
        rows.append(f"{index},V{index},{amount},20")
    rows.append("10,V10,819,20")
    source = tmp_path / "payments.csv"
    source.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return source


def _walk(tmp_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Drive create through execute_detectors exactly as SKILL.md documents."""
    root = tmp_path / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-walk",
        now=NOW,
    )
    register_local_source(
        root,
        _source(tmp_path),
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
    approve_detector_plan(root, plan["recommended"], approved_by="journalist", now=NOW)
    results = execute_detectors(root, plan["recommended"], now=NOW)
    return root, results


def _attestation(root: Path, reviewer: str) -> dict[str, Any]:
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    return {
        "isolated": True,
        "attested_by": reviewer,
        "draft_hash": _hash_json(draft),
        "statement": "Inspected draft, replay, provenance, and previews.",
    }


def test_documented_walk_replays_real_run_through_charts(tmp_path: Path) -> None:
    root, results = _walk(tmp_path)

    # Run provenance must carry the canonical registry implementation hash.
    runs_root = root / "evidence" / "runs"
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
        package = Path(__file__).parents[1] / "detectors" / Path(*provenance["detector_id"].split("."))
        assert provenance["detector_hash"] == package_implementation_hash(package)

    replay = replay_signals(root)
    assert replay["status"] == "replayed", replay.get("reason")
    assert any(run["signal_count"] for run in replay["runs"])
    assert replay["claims"], "expected at least one replayed lead"

    draft_findings(root)
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    claim_ids = [claim["claim_id"] for claim in draft["claims"]]
    assert claim_ids

    record_review(
        root,
        "reviewer-007",
        {claim_ids[0]: {"verdict": "accepted", "notes": "replay and wording hold"}},
        independent_attestation=_attestation(root, "reviewer-007"),
    )
    findings = accept_findings(root, claim_ids[:1])
    assert findings["status"] == "accepted"
    write_report(root)

    manifest = generate_charts(root)
    assert manifest["kind"] == "charts"
    receipt = json.loads((root / ".anomaly" / "receipts" / "charts.json").read_text(encoding="utf-8"))
    assert receipt["gate"] == "B"
