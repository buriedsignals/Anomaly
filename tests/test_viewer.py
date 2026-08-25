from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from anomaly.case import create_case
from anomaly.acquire import register_local_source
from anomaly.review import _hash_json, draft_findings, record_review, accept_findings
from anomaly.detectors.registry import package_implementation_hash

from test_report import (
    DETECTOR_HASH,
    SECOND_DETECTOR_HASH,
    SECRET_CATEGORY,
    SECRET_STATEMENT,
    _signal,
    _write_run,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
VIEWER_PATH = Path("findings") / "viewer.html"
RECEIPT_PATH = Path(".anomaly") / "receipts" / "viewer.json"
HOSTILE_STATEMENT = (
    '<script>alert("xss")</script> Acme volume is 20% above baseline '
    "</script><img src=x onerror=alert(1)>"
)
HOSTILE_PREVIEW_VALUE = '</script><svg onload=alert(1)><iframe src="javascript:x">'


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _viewer_case(tmp_path: Path, *, statement: str, preview_value: Any) -> Path:
    """Drive a real case to Gate B with attacker-controlled redacted text."""
    root = tmp_path / "case"
    create_case(
        root,
        title="Quarterly procurement anomalies",
        question="Which payments need review?",
        case_id="case-008",
        now=NOW,
    )
    source = tmp_path / "payments.csv"
    source.write_text("vendor,amount,baseline\nAcme,12,10\n", encoding="utf-8")
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

    signal = _signal(
        signal_id="signal-ratio",
        claim_id="claim-ratio",
        rank=1,
        category="numeric",
        detector_hash=DETECTOR_HASH,
        statement=statement,
        calculation={"kind": "ratio", "numerator": 2, "denominator": 10, "value": 0.2},
        source_hash=source_hash,
    )
    signal["preview"] = {"vendor": preview_value, "amount": 12}
    _write_run(
        root,
        "run-007",
        "numeric.zscore_outliers",
        DETECTOR_HASH,
        [signal],
        source_hash,
    )

    (root / "evidence" / "signals.jsonl").write_text("", encoding="utf-8")
    used = root / "detectors" / "used"
    used.mkdir(parents=True, exist_ok=True)
    (used / "numeric__zscore_outliers.json").write_text(
        json.dumps({"implementation_hash": DETECTOR_HASH, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-008",
        verdicts={"claim-ratio": {"verdict": "accepted", "notes": "Replayed cleanly."}},
        independent_attestation={
            "isolated": True,
            "attested_by": "reviewer-008",
            "draft_hash": _hash_json(_json(root / "findings" / "draft.json")),
            "statement": "Inspected draft, replay, provenance, and previews.",
        },
        unresolved_questions=["Why does Acme exceed every peer?"],
        alternatives=["A legitimate seasonal promotion."],
    )
    (root / "findings" / "unresolved.md").write_text(
        "# Unresolved\n\n- Confirm the Acme contract terms.\n",
        encoding="utf-8",
    )
    accept_findings(root, ["claim-ratio"])
    return root


def _gate_b_viewer_case(tmp_path: Path) -> Path:
    return _viewer_case(
        tmp_path,
        statement=SECRET_STATEMENT,
        preview_value="Acme",
    )


def _hostile_viewer_case(tmp_path: Path) -> Path:
    return _viewer_case(
        tmp_path,
        statement=HOSTILE_STATEMENT,
        preview_value=HOSTILE_PREVIEW_VALUE,
    )


def test_refuses_without_gate_b_receipt_and_writes_nothing(tmp_path: Path) -> None:
    from anomaly.viewer import ViewerError, generate_viewer

    root = _gate_b_viewer_case(tmp_path)
    (root / ".anomaly" / "receipts" / "gate-b.json").unlink()

    with pytest.raises(ViewerError, match=r"(?i)receipt"):
        generate_viewer(root)
    assert not (root / "findings" / "viewer.html").exists()
    assert not (root / ".anomaly" / "receipts" / "viewer.json").exists()


def test_refuses_on_fresh_case(tmp_path: Path) -> None:
    from anomaly.viewer import ViewerError, generate_viewer

    root = tmp_path / "case"
    create_case(root, title="Empty case", question="?", case_id="case-empty", now=NOW)

    with pytest.raises(ViewerError):
        generate_viewer(root)
    assert not (root / "findings" / "viewer.html").exists()


def test_refuses_when_findings_are_tampered_after_acceptance(tmp_path: Path) -> None:
    from anomaly.viewer import ViewerError, generate_viewer

    root = _gate_b_viewer_case(tmp_path)
    findings_path = root / "findings" / "findings.json"
    payload = _json(findings_path)
    payload["claims"][0]["calculation"]["value"] = 0.9
    findings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ViewerError, match=r"(?i)hash"):
        generate_viewer(root)
    assert not (root / "findings" / "viewer.html").exists()


def test_generates_deterministic_viewer_with_matching_receipt(tmp_path: Path) -> None:
    from anomaly.viewer import generate_viewer

    root = _gate_b_viewer_case(tmp_path)
    gate_b = _json(root / ".anomaly" / "receipts" / "gate-b.json")

    manifest_first = generate_viewer(root)
    html_first = (root / VIEWER_PATH).read_bytes()
    receipt_first = (root / RECEIPT_PATH).read_bytes()

    manifest_second = generate_viewer(root)
    assert (root / VIEWER_PATH).read_bytes() == html_first
    assert (root / RECEIPT_PATH).read_bytes() == receipt_first
    assert manifest_second == manifest_first

    assert manifest_first["kind"] == "viewer"
    assert manifest_first["gate"] == "B"
    assert manifest_first["findings_hash"] == gate_b["findings_hash"]
    assert manifest_first["replay_hash"] == gate_b["replay_hash"]
    assert manifest_first["viewer"] == "findings/viewer.html"
    assert manifest_first["viewer_hash"] == _sha256(html_first)
    assert _json(root / RECEIPT_PATH) == manifest_first


def test_viewer_renders_claims_signals_review_and_unresolved(tmp_path: Path) -> None:
    from anomaly.viewer import generate_viewer

    root = _gate_b_viewer_case(tmp_path)
    generate_viewer(root)

    document = (root / VIEWER_PATH).read_text(encoding="utf-8")
    assert "Anomaly evidence viewer" in document
    assert "Acme volume is 20% above its baseline" in document
    assert "signal-ratio" in document
    assert "numeric.zscore_outliers" in document
    assert "reviewer-008" in document
    assert "Replayed cleanly." in document
    assert "Confirm the Acme contract terms." in document
    assert "A legitimate seasonal promotion." in document

    embedded = re.search(
        r'<script type="application/json" id="viewer-data">(.*?)</script>',
        document,
        re.DOTALL,
    )
    assert embedded is not None
    payload = json.loads(embedded.group(1))
    assert payload["claims"][0]["claim_id"] == "claim-ratio"
    assert payload["claims"][0]["signals"][0]["signal_id"] == "signal-ratio"
    assert payload["claims"][0]["review"]["verdict"] == "accepted"
    assert payload["reviewer"]["isolated"] is True
    assert "Confirm the Acme contract terms." in payload["unresolved_markdown"]


def test_viewer_escapes_hostile_content_and_redacts_secrets(tmp_path: Path) -> None:
    from anomaly.viewer import generate_viewer

    root = _hostile_viewer_case(tmp_path)
    generate_viewer(root)

    raw = (root / VIEWER_PATH).read_bytes()
    document = raw.decode("utf-8")

    # The only script open/close tags are the page's own two literal elements.
    assert len(re.findall(r"<script", document)) == 2
    assert len(re.findall(r"</script>", document)) == 2
    # Hostile markup survives only inside the escaped JSON payload.
    assert "<img" not in document and "<svg" not in document and "<iframe" not in document
    assert "\\u003cscript\\u003e" in document
    assert "\\u003c/script\\u003e\\u003csvg" in document
    # Case redaction still applies on top of escaping.
    assert b"super-secret-token" not in raw
    assert b"sk_live_" not in raw
    assert b"hunter2" not in raw


def test_receipt_records_only_relative_names(tmp_path: Path) -> None:
    from anomaly.viewer import generate_viewer

    root = _gate_b_viewer_case(tmp_path)
    generate_viewer(root)

    receipt_text = (root / RECEIPT_PATH).read_text(encoding="utf-8")
    assert str(root) not in receipt_text
    assert "/Users/" not in receipt_text
    manifest = json.loads(receipt_text)
    assert manifest["viewer"] == "findings/viewer.html"
    assert not Path(manifest["viewer"]).is_absolute()


def test_readme_outputs_block_includes_the_viewer(tmp_path: Path) -> None:
    from anomaly.readme import project_readme

    root = tmp_path / "case"
    create_case(root, title="T", question="?", case_id="case-readme", now=NOW)
    project_readme(root, {"status": "complete"}, "P7")

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "[evidence viewer](findings/viewer.html)" in readme


def test_viewer_module_uses_no_network_or_imaging_surface() -> None:
    source = (Path(__file__).parents[1] / "src" / "anomaly" / "viewer.py").read_text(
        encoding="utf-8"
    )
    forbidden = re.compile(
        r"(?m)^\s*(?:import|from)\s+(?:socket|ssl|urllib|http|ftplib|smtplib|requests|httpx|aiohttp|matplotlib|PIL)\b"
    )
    assert forbidden.search(source) is None
