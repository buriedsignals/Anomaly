from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from anomaly.acquire import register_local_source
from anomaly.case import create_case
from anomaly.detectors.registry import package_implementation_hash
from anomaly.review import (
    _hash_json,
    accept_findings,
    draft_findings,
    record_review,
    replay_signals,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
DETECTOR_HASH = package_implementation_hash(
    Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"
)
SECRET_STATEMENT = (
    "Acme volume is 20% above its baseline (api_key=super-secret-token, "
    "fallback sk_live_aaaabbbbcccc)."
)
SECRET_CATEGORY = "duplicate password=hunter2"
DETECTOR_HASH = package_implementation_hash(
    Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"
)
SECOND_DETECTOR_HASH = package_implementation_hash(
    Path(__file__).parents[1] / "detectors" / "table" / "duplicate_rows"
)


CHART_NAMES = {
    "claims-by-category.svg",
    "claim-values-by-rank.svg",
    "signals-per-detector.svg",
}

def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _signal(
    *,
    signal_id: str,
    claim_id: str,
    rank: int,
    category: str,
    statement: str,
    detector_hash: str,
    calculation: dict[str, Any],
    source_hash: str,
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "claim_id": claim_id,
        "rank": rank,
        "status": "lead",
        "category": category,
        "statement": statement,
        "redacted": True,
        "preview": {"vendor": "Acme", "amount": 12, "baseline": 10},
        "evidence_refs": [{"source_id": "payments", "row": rank}],
        "calculation": calculation,
        "source_hash": source_hash,
        "detector_hash": detector_hash,
        "run_id": "",
    }


def _write_run(
    root: Path,
    run_id: str,
    detector_id: str,
    detector_hash: str,
    rows: list[dict[str, Any]],
    source_hash: str,
) -> None:
    run_dir = root / "evidence" / "runs" / run_id
    run_dir.mkdir(parents=True)
    for row in rows:
        row["run_id"] = run_id
    (run_dir / "preview.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": run_id,
                "detector_id": detector_id,
                "detector_version": "1.0.0",
                "detector_hash": detector_hash,
                "source_hashes": [source_hash],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _gate_b_case(tmp_path: Path) -> Path:
    """Drive a real case to Gate B so charts have legitimate hash-bound inputs."""
    root = tmp_path / "case"
    create_case(
        root,
        title="Quarterly procurement anomalies",
        question="Which payments need review?",
        case_id="case-008",
        now=NOW,
    )
    source = tmp_path / "payments.csv"
    source.write_text("vendor,amount,baseline\nAcme,12,10\nBeta,4,10\n", encoding="utf-8")
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

    _write_run(
        root,
        "run-007",
        "numeric.zscore_outliers",
        DETECTOR_HASH,
        [
            _signal(
                signal_id="signal-ratio",
                claim_id="claim-ratio",
                rank=1,
                category="numeric",
                detector_hash=DETECTOR_HASH,
                statement=SECRET_STATEMENT,
                calculation={"kind": "ratio", "numerator": 2, "denominator": 10, "value": 0.2},
                source_hash=source_hash,
            ),
            _signal(
                signal_id="signal-count",
                detector_hash=DETECTOR_HASH,
                statement="The same payment appears duplicated.",
                claim_id="claim-count",
                rank=2,
                category=SECRET_CATEGORY,
                calculation={"kind": "count", "value": 2},
                source_hash=source_hash,
            ),
        ],
        source_hash,
    )
    _write_run(
        root,
        "run-008",
        "table.duplicate_rows",
        SECOND_DETECTOR_HASH,
        [
            _signal(
                signal_id="signal-count-b",
                claim_id="claim-count",
                rank=3,
                category=SECRET_CATEGORY,
                detector_hash=SECOND_DETECTOR_HASH,
                statement="A related payment is missing an amount.",
                calculation={"kind": "count", "value": 1},
                source_hash=source_hash,
            )
        ],
        source_hash,
    )

    (root / "evidence" / "signals.jsonl").write_text("", encoding="utf-8")
    used = root / "detectors" / "used"
    used.mkdir(parents=True, exist_ok=True)
    for name, digest in (
        ("numeric__zscore_outliers.json", DETECTOR_HASH),
        ("table__duplicate_rows.json", SECOND_DETECTOR_HASH),
    ):
        (used / name).write_text(
            json.dumps({"implementation_hash": digest, "version": "1.0.0"}) + "\n",
            encoding="utf-8",
        )

    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-008",
        verdicts={
            "claim-ratio": {"verdict": "accepted"},
            "claim-count": {"verdict": "accepted"},
        },
        independent_attestation={
            "isolated": True,
            "attested_by": "reviewer-008",
            "draft_hash": _hash_json(
                _json(root / "findings" / "draft.json")
            ),
            "statement": "Inspected draft, replay, provenance, and previews.",
        },
    )
    accept_findings(root, ["claim-ratio", "claim-count"])
    return root


def _chart_files(root: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted((root / "findings" / "charts").iterdir())
        if path.is_file()
    }


def test_refuses_without_gate_b_receipt_and_writes_nothing(tmp_path: Path) -> None:
    from anomaly.report import ChartError, generate_charts

    root = _gate_b_case(tmp_path)
    (root / ".anomaly" / "receipts" / "gate-b.json").unlink()

    with pytest.raises(ChartError, match=r"(?i)receipt"):
        generate_charts(root)
    assert not (root / "findings" / "charts").exists()


def test_refuses_when_gate_b_receipt_is_absent_on_fresh_case(tmp_path: Path) -> None:
    from anomaly.report import ChartError, generate_charts

    root = tmp_path / "case"
    create_case(root, title="Empty case", question="?", case_id="case-empty", now=NOW)

    with pytest.raises(ChartError):
        generate_charts(root)
    assert not (root / "findings" / "charts").exists()


def test_refuses_when_findings_are_tampered_after_acceptance(tmp_path: Path) -> None:
    from anomaly.report import ChartError, generate_charts

    root = _gate_b_case(tmp_path)
    findings_path = root / "findings" / "findings.json"
    payload = _json(findings_path)
    payload["claims"][0]["calculation"]["value"] = 0.9
    findings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ChartError, match=r"(?i)hash"):
        generate_charts(root)
    assert not (root / "findings" / "charts").exists()


def test_charts_receipt_is_a_known_non_source_kind(tmp_path: Path) -> None:
    """Audit A2: a charts receipt must never lock later validating calls out."""
    from anomaly.acquire import register_local_source
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    generate_charts(root)

    extra = tmp_path / "followup.csv"
    extra.write_text("vendor,amount\nDelta,7\n", encoding="utf-8")
    record = register_local_source(
        root,
        extra,
        source_id="followup",
        now=NOW,
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the locked newsroom drive.",
        included=False,
        reason="Data cannot travel with the case.",
    )

    assert record["source_id"] == "followup"


def test_generates_deterministic_charts_with_matching_receipt(tmp_path: Path) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    gate_b = _json(root / ".anomaly" / "receipts" / "gate-b.json")

    manifest_first = generate_charts(root)
    snapshot = _chart_files(root)
    receipt_first = (root / ".anomaly" / "receipts" / "charts.json").read_bytes()

    manifest_second = generate_charts(root)
    assert _chart_files(root) == snapshot
    assert (root / ".anomaly" / "receipts" / "charts.json").read_bytes() == receipt_first
    assert manifest_second == manifest_first

    assert set(snapshot) == CHART_NAMES
    for name, payload in snapshot.items():
        ET.fromstring(payload)  # every chart is well-formed XML
        assert payload.startswith(b"<?xml") or payload.lstrip().startswith(b"<svg")

    assert manifest_first["kind"] == "charts"
    assert manifest_first["gate"] == "B"
    assert manifest_first["findings_hash"] == gate_b["findings_hash"]
    assert manifest_first["replay_hash"] == gate_b["replay_hash"]
    assert set(manifest_first["charts"]) == CHART_NAMES
    for name, digest in manifest_first["charts"].items():
        assert digest == _sha256(snapshot[name])
    assert _json(root / ".anomaly" / "receipts" / "charts.json") == manifest_first


def test_chart_text_is_redacted_before_it_lands(tmp_path: Path) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    generate_charts(root)

    blobs = b"".join(_chart_files(root).values())
    assert b"super-secret-token" not in blobs
    assert b"sk_live_" not in blobs
    assert b"hunter2" not in blobs


def test_value_chart_draws_only_comparable_calculations_and_records_skips(
    tmp_path: Path,
) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    manifest = generate_charts(root)

    values_svg = (root / "findings" / "charts" / "claim-values-by-rank.svg").read_text(
        encoding="utf-8"
    )
    assert "claim-ratio" in values_svg
    assert "claim-count" not in values_svg
    skipped = {item["claim_id"]: item["reason"] for item in manifest["notes"]["skipped_claims"]}
    assert set(skipped) == {"claim-count"}
    assert isinstance(skipped["claim-count"], str) and skipped["claim-count"].strip()


def test_category_and_detector_charts_use_sorted_keys(tmp_path: Path) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    generate_charts(root)

    categories_svg = (root / "findings" / "charts" / "claims-by-category.svg").read_text(
        encoding="utf-8"
    )
    assert "numeric" in categories_svg
    assert "password=" in categories_svg and "hunter2" not in categories_svg
    # "duplicate ..." sorts before "numeric ..."
    assert categories_svg.index("duplicate") < categories_svg.index("numeric")

    detectors_svg = (root / "findings" / "charts" / "signals-per-detector.svg").read_text(
        encoding="utf-8"
    )
    assert "table.duplicate_rows" in detectors_svg
    assert "numeric.zscore_outliers" in detectors_svg
    assert detectors_svg.index("numeric.zscore_outliers") < detectors_svg.index(
        "table.duplicate_rows"
    )


def test_regeneration_replaces_prior_charts(tmp_path: Path) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    generate_charts(root)
    stale = root / "findings" / "charts" / "stale-chart.svg"
    stale.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")

    generate_charts(root)

    assert not stale.exists()
    assert set(_chart_files(root)) == CHART_NAMES


def test_receipt_records_only_relative_names(tmp_path: Path) -> None:
    from anomaly.report import generate_charts

    root = _gate_b_case(tmp_path)
    generate_charts(root)

    receipt_text = (root / ".anomaly" / "receipts" / "charts.json").read_text(encoding="utf-8")
    assert str(root) not in receipt_text
    assert "/Users/" not in receipt_text
    manifest = json.loads(receipt_text)
    assert all("/" not in name and "\\" not in name for name in manifest["charts"])
    for relative in (manifest.get("findings_identity"), manifest.get("replay_identity")):
        if isinstance(relative, str):
            assert not Path(relative).is_absolute()


def test_report_module_uses_no_network_or_imaging_surface() -> None:
    source = (Path(__file__).parents[1] / "src" / "anomaly" / "report.py").read_text(
        encoding="utf-8"
    )
    forbidden = re.compile(
        r"(?m)^\s*(?:import|from)\s+(?:socket|ssl|urllib|http|ftplib|smtplib|requests|httpx|aiohttp|matplotlib|PIL)\b"
    )
    assert forbidden.search(source) is None
