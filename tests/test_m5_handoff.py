from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from anomaly.case import UnsafeCasePathError, create_case, fork_case
from anomaly.detectors.registry import validate_detector_package
from anomaly.review import replay_signals


NOW = "2026-08-22T12:00:00+00:00"


def _user_package(root: Path, detector_id: str = "user.amount_lead") -> Path:
    package = root / detector_id.replace(".", "-")
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        f"id: {detector_id}\n"
        "version: 2.1.0\n"
        "title: User amount lead\n"
        "author: journalist\n"
        "license: CC0-1.0\n"
        "group: numeric\n"
        "description: A user supplied lead detector.\n"
        "required_tables:\n  - observations\n"
        "required_fields:\n  - amount\n"
        "parameters:\n  threshold: 10\n"
        "signal_category: anomaly\n"
        "severity: medium\n"
        "expected_output:\n  - candidate_id\n"
        "assumptions:\n  - Amounts are comparable.\n"
        "false_positives:\n  - Legitimate high values.\n"
        "sensitive_output: redact\n"
        "resource_limits:\n  timeout_seconds: 5\n"
        "query: query.sql\n",
        encoding="utf-8",
    )
    (package / "query.sql").write_text(
        "SELECT id AS candidate_id, amount FROM {{table_id}} WHERE amount > ?",
        encoding="utf-8",
    )
    return package


def _create_case(root: Path, case_id: str = "parent-001") -> None:
    create_case(
        root,
        title="Registry handoff",
        question="Which records need review?",
        case_id=case_id,
        now=datetime.fromisoformat(NOW),
    )


def test_registry_search_filters_metadata_before_validating_irrelevant_packages(
    tmp_path: Path,
) -> None:
    selected = tmp_path / "selected"
    _user_package(selected, "numeric.selected")
    irrelevant = tmp_path / "irrelevant"
    irrelevant.mkdir()
    (irrelevant / "meta.yaml").write_text("not: a detector\n", encoding="utf-8")

    from anomaly.detectors.registry import discover_detectors

    results = discover_detectors([tmp_path], group="numeric", limit=10)

    assert [item["id"] for item in results] == ["numeric.selected"]


def test_user_detector_metadata_preserves_origin_version_hash_and_signal_contract(
    tmp_path: Path,
) -> None:
    metadata = validate_detector_package(_user_package(tmp_path))

    assert metadata["origin"] == "user"
    assert metadata["version"] == "2.1.0"
    assert metadata["implementation_hash"].startswith("sha256:")
    assert metadata["signal_contract"] == "lead"


def test_fork_records_parent_content_hash_and_resets_to_selected_phase(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    _create_case(parent)

    fork_case(parent, child, case_id="child-001", reset_phase="P3")

    parent_hash = "sha256:" + hashlib.sha256(
        (parent / "case.json").read_bytes()
    ).hexdigest()
    child_record = json.loads((child / "case.json").read_text(encoding="utf-8"))
    child_state = json.loads((child / ".anomaly/state.json").read_text(encoding="utf-8"))

    assert child_record["derived_from"] == {
        "case_id": "parent-001",
        "case_hash": parent_hash,
    }
    assert child_state["phase"] == "P3"
    assert child_state["status"] == "active"
    assert json.loads((parent / "case.json").read_text(encoding="utf-8"))["case_id"] == "parent-001"


def test_fork_rejects_executable_detector_artifact_before_copy(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    _create_case(parent)
    executable = parent / "detectors" / "used" / "detector.py"
    executable.write_text("print('must never run')\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | 0o111)

    with pytest.raises(UnsafeCasePathError, match=r"(?i)(executable|code|unsafe)"):
        fork_case(parent, child, case_id="child-001", now=datetime.fromisoformat(NOW))

    assert not child.exists()


def test_replay_without_required_inputs_returns_explicit_unavailable_status(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create_case(root)

    result = replay_signals(root)

    assert result["status"] == "unavailable"
    assert result["reason"]
    assert result["replay_possible"] is False


def test_gate_b_requires_new_run_review_after_methodology_changes(tmp_path: Path) -> None:
    from test_review import _seed_case
    from anomaly.review import accept_findings, draft_findings, record_review

    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )
    (root / "instructions" / "methodology.md").write_text(
        "Changed semantic mapping requires re-exploration.\n", encoding="utf-8"
    )

    with pytest.raises(Exception, match=r"(?i)(rerun|review|methodolog|invalidat)"):
        accept_findings(root, ["claim-accepted"])
