from __future__ import annotations

import copy
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from p2_helpers import NOW, create_p2_case, read_json, register, write_source

DETECTOR_IDS = (
    "table.missingness_clusters",
    "table.duplicate_rows",
    "numeric.zscore_outliers",
    "numeric.level_shift",
    "categorical.rare_levels",
    "temporal.coverage_gaps",
)


def _detect_api():
    return importlib.import_module("anomaly.detect")


def _recommend_api():
    return importlib.import_module("anomaly.recommend")


def _prepared_case(tmp_path: Path) -> Path:
    from anomaly.prepare import prepare_sources
    from anomaly.profile import profile_prepared

    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / "observations.csv",
            "id,group,amount,observed_at\n"
            "1,A,10,2026-01-01\n"
            "2,A,11,2026-01-02\n"
            "3,B,100,2026-01-03\n"
            "4,B,,2026-01-10\n",
        ),
        "observations",
    )
    prepare_sources(root, now=NOW)
    profile_prepared(root, now=NOW)
    return root


def _metadata(*, blocked: bool = False) -> list[dict[str, Any]]:
    metadata = copy.deepcopy(_detect_api().load_detector_metadata())
    requirements: dict[str, dict[str, Any]] = {
        "table.duplicate_rows": {
            "required_tables": ["*"],
            "required_fields": [],
            "required_types": {},
            "minimum_coverage": {},
        },
        "table.missingness_clusters": {
            "required_tables": ["*"],
            "required_fields": [],
            "required_types": {},
            "minimum_coverage": {},
        },
        "numeric.level_shift": {
            "required_tables": ["*"],
            "required_fields": ["amount"],
            "required_types": {"amount": ["integer", "float"]},
            "minimum_coverage": {"amount": 0.75},
        },
        "numeric.zscore_outliers": {
            "required_tables": ["*"],
            "required_fields": ["amount"],
            "required_types": {"amount": ["integer", "float"]},
            "minimum_coverage": {"amount": 0.75},
        },
        "categorical.rare_levels": {
            "required_tables": ["*"],
            "required_fields": ["group"],
            "required_types": {"group": ["text"]},
            "minimum_coverage": {"group": 0.75},
        },
        "temporal.coverage_gaps": {
            "required_tables": ["*"],
            "required_fields": ["observed_at"],
            "required_types": {"observed_at": ["datetime"]},
            "minimum_coverage": {"observed_at": 0.75},
        },
    }
    if blocked:
        requirements["numeric.zscore_outliers"]["required_fields"] = ["not_in_profile"]
    for item in metadata:
        item.update(requirements[item["id"]])
        item.update(
            {
                "relevance": 0.8,
                "utility": 0.7,
                "cost": 0.2,
                "false_positive_risk": 0.1,
            }
        )
    return metadata


def _patch_metadata(monkeypatch: pytest.MonkeyPatch, metadata: list[dict[str, Any]]) -> None:
    detect = _detect_api()
    monkeypatch.setattr(detect, "load_detector_metadata", lambda: copy.deepcopy(metadata))


def _plan(root: Path) -> dict[str, Any]:
    return read_json(root / "detectors" / "plan.json")


def test_recommend_filters_by_profile_compatible_tables_fields_types_and_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata(blocked=True))

    result = _recommend_api().recommend_detectors(root, now=NOW)
    plan = _plan(root)

    assert result == plan
    assert set(plan) == {"recommended", "approved", "parameters", "reasons", "blocked"}
    assert "numeric.zscore_outliers" not in plan["recommended"]
    blocked = {item["id"]: item["reason"] for item in plan["blocked"]}
    assert "numeric.zscore_outliers" in blocked
    assert any(token in blocked["numeric.zscore_outliers"].lower() for token in ("field", "profile", "compatible"))
    assert "numeric.level_shift" in plan["recommended"]
    assert "categorical.rare_levels" in plan["recommended"]
    assert "temporal.coverage_gaps" in plan["recommended"]


def test_recommend_scores_all_required_dimensions_and_is_deterministically_ranked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    metadata = _metadata()
    _patch_metadata(monkeypatch, metadata)
    api = _recommend_api()

    first = api.recommend_detectors(root, now=NOW, max_detectors=10)
    monkeypatch.setattr(_detect_api(), "load_detector_metadata", lambda: list(reversed(metadata)))
    second = api.recommend_detectors(root, now=NOW, max_detectors=10)

    assert first == second
    for detector_id in first["recommended"]:
        scores = first["reasons"][detector_id]["scores"]
        assert set(scores) == {
            "relevance",
            "data_fit",
            "utility",
            "cost",
            "false_positive_risk",
        }
        assert all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in scores.values())
        assert first["parameters"][detector_id]
        assert first["reasons"][detector_id]["selection"]


def test_recommend_diversifies_detector_groups_and_honors_maximum_ten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata())

    plan = _recommend_api().recommend_detectors(root, now=NOW, max_detectors=3)
    metadata = {item["id"]: item for item in _metadata()}
    groups = {metadata[detector_id]["group"] for detector_id in plan["recommended"]}

    assert len(plan["recommended"]) <= 3
    assert len(plan["recommended"]) == len(groups)
    assert len(groups) == 3
    assert len(plan["recommended"]) <= 10


def test_recommend_never_executes_sql_or_writes_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata())
    detect = _detect_api()

    def fail_execution(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("recommendation must not execute detectors")

    monkeypatch.setattr(detect, "execute_detectors", fail_execution)
    monkeypatch.setattr(detect, "validate_read_only_sql", fail_execution)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != "plan.json"
    }

    _recommend_api().recommend_detectors(root, now=NOW)

    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != "plan.json"
    }
    assert after == before
    assert not (root / "findings" / "findings.json").exists()
    assert not (root / "evidence" / "signals.jsonl").exists()


def test_approval_rejects_unknown_or_blocked_ids_without_mutating_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata(blocked=True))
    api = _recommend_api()
    api.recommend_detectors(root, now=NOW)
    before = _plan(root)

    with pytest.raises(Exception, match=r"(?i)(unknown|not recommended|blocked|approved)"):
        api.approve_detector_plan(root, ["does.not.exist"], approved_by="journalist", now=NOW)
    with pytest.raises(Exception, match=r"(?i)(unknown|not recommended|blocked|approved)"):
        api.approve_detector_plan(root, ["numeric.zscore_outliers"], approved_by="journalist", now=NOW)

    assert _plan(root) == before


def test_approval_records_gate_a_and_approved_subset_with_identity_and_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata(blocked=True))
    api = _recommend_api()
    api.recommend_detectors(root, now=NOW)

    approved_ids = ["numeric.level_shift", "categorical.rare_levels"]
    result = api.approve_detector_plan(root, approved_ids, approved_by="editor-1", now=NOW)
    plan = _plan(root)

    assert result == plan
    assert plan["approved"] == approved_ids
    receipt = read_json(root / ".anomaly" / "receipts" / "gate-a.json")
    assert receipt["approved"] == approved_ids
    assert receipt["approved_by"] == "editor-1"
    assert receipt["approved_at"] == NOW.isoformat()
    state = read_json(root / ".anomaly" / "state.json")
    assert state["phase"] == "P4"
    assert state["gate"] == "A"


def test_execution_is_refused_until_gate_a_approval(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    execute_detectors = _detect_api().execute_detectors

    with pytest.raises(Exception, match=r"(?i)(gate|approv|plan)"):
        execute_detectors(root, ["table.duplicate_rows"], now=NOW)


def test_approval_rejects_duplicate_ids_and_more_than_ten_detectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata())
    api = _recommend_api()
    api.recommend_detectors(root, now=NOW)

    with pytest.raises(Exception, match=r"(?i)(duplicate|maximum|10|detector)"):
        api.approve_detector_plan(root, ["numeric.level_shift", "numeric.level_shift"], approved_by="editor", now=NOW)
    with pytest.raises(Exception, match=r"(?i)(maximum|10|detector)"):
        api.approve_detector_plan(root, list(DETECTOR_IDS) * 2, approved_by="editor", now=NOW)


def test_plan_output_is_json_and_contains_only_portable_case_relative_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_case(tmp_path)
    _patch_metadata(monkeypatch, _metadata())

    _recommend_api().recommend_detectors(root, now=datetime(2026, 8, 21, tzinfo=timezone.utc))
    raw = (root / "detectors" / "plan.json").read_text(encoding="utf-8")
    plan = json.loads(raw)

    assert raw.endswith("\n")
    assert all("/" not in detector_id and "\\" not in detector_id for detector_id in plan["recommended"])
    assert all("/" not in detector_id and "\\" not in detector_id for detector_id in plan["approved"])
