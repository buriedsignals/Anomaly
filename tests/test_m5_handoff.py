from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from anomaly.acquire import register_local_source
from anomaly.case import UnsafeCasePathError, create_case, fork_case
from anomaly.detectors.registry import discover_detectors, execute_detectors, validate_detector_package
from anomaly.review import accept_findings, draft_findings, record_review, replay_signals


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


def test_registry_discovery_without_limit_is_bounded_to_safe_maximum(tmp_path: Path) -> None:
    for index in range(12):
        _user_package(tmp_path, f"numeric.detector_{index:02d}")

    results = discover_detectors([tmp_path])

    assert len(results) <= 10
    assert [item["id"] for item in results] == sorted(item["id"] for item in results)


def test_registry_discovery_with_default_roots_is_bounded_to_safe_maximum() -> None:
    results = discover_detectors()

    assert len(results) <= 10


def test_registry_and_live_review_use_the_same_implementation_hash_for_unchanged_package() -> None:
    from anomaly.review import _current_detector_identity

    package = Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"

    registry_metadata = validate_detector_package(package)
    live_identity = _current_detector_identity("numeric.zscore_outliers")

    assert live_identity is not None
    assert registry_metadata["implementation_hash"] == live_identity["implementation_hash"]


def test_default_execution_resolves_explicit_namespaced_gain_detector_without_uncapping_discovery(
    tmp_path: Path,
) -> None:
    from approved_case import approved_case

    root = approved_case(
        tmp_path,
        source_payloads= {
            "senate_filings": (
                "id,registrant_id,registrant_name,filing_year,filing_period,income,filing_type\n" +
                "1,1,Example,2025,Q1,100,Q1\n"
            )
        }
    )
    discovered = discover_detectors()

    assert len(discovered) <= 10
    results = execute_detectors(
        root,
        ["us_lobbying.spending_spikes"],
        approved=True,
        limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
    )

    assert isinstance(results, list)


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


def test_replay_with_missing_detector_dependency_returns_replay_unavailable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create_case(root)
    source_file = tmp_path / "observations.csv"
    source_file.write_text("id,amount\n1,10\n", encoding="utf-8")
    source_record = register_local_source(
        root,
        source_file,
        source_id="observations",
        now=datetime.fromisoformat(NOW),
        license="internal",
        sensitivity="restricted",
        redistribution="no",
        reacquisition="Copy from the newsroom drive.",
        included=True,
    )
    digest = source_record["content_hash"]
    run = root / "evidence" / "runs" / "run-missing-detector"
    run.mkdir(parents=True)
    (run / "preview.json").write_text("[]", encoding="utf-8")
    (run / "provenance.json").write_text(
        json.dumps(
            {
                "run_id": run.name,
                "detector_id": "missing.detector",
                "detector_hash": "sha256:" + ("b" * 64),
                "source_hashes": [digest],
            }
        ),
        encoding="utf-8",
    )

    result = replay_signals(root)

    assert result["status"] == "replay-unavailable"
    assert result["replay_possible"] is False
    assert "detector" in result["reason"].lower()


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


def test_gate_b_rejects_replay_after_source_mutation(tmp_path: Path) -> None:
    from test_review import _seed_case

    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )
    replay_signals(root)
    source = root / "data" / "raw" / "payments" / "payments.csv"
    source.write_text(
        source.read_text(encoding="utf-8") + "Gamma,99,1,super-secret-token\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception, match=r"(?i)(source|stale|replay|hash)"):
        accept_findings(root, ["claim-accepted"])
    assert not (root / "findings" / "findings.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", "2"),
        ("title", "Changed detector metadata"),
        ("implementation_hash", "sha256:" + ("e" * 64)),
    ],
)
def test_detector_identity_changes_invalidate_replay_review_and_gate_b_without_query_change(
    tmp_path: Path, field: str, value: str
) -> None:
    from test_review import _seed_case

    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )
    query = Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers" / "query.sql"
    query_before = query.read_bytes()
    snapshot = root / "detectors" / "used" / "numeric__zscore_outliers.json"
    metadata = json.loads(snapshot.read_text(encoding="utf-8"))
    metadata[field] = value
    snapshot.write_text(json.dumps(metadata) + "\n", encoding="utf-8")

    assert query.read_bytes() == query_before
    replay = replay_signals(root)
    assert replay["status"] == "replay-unavailable"
    assert replay["replay_possible"] is False
    with pytest.raises(Exception, match=r"(?i)(rerun|review|detector|invalidat)"):
        accept_findings(root, ["claim-accepted"])


@pytest.mark.parametrize(
    ("metadata_field", "metadata_value"),
    [
        ("version", "9.9.9"),
        ("title", "Changed live detector metadata"),
    ],
)
def test_live_detector_package_metadata_change_invalidates_replay_and_review_without_query_change(
    tmp_path: Path, metadata_field: str, metadata_value: str
) -> None:
    from test_review import _seed_case

    root = _seed_case(tmp_path)
    draft_findings(root)
    record_review(
        root,
        reviewer_id="reviewer-007",
        verdicts={"claim-accepted": {"verdict": "accepted"}},
    )

    package = Path(__file__).parents[1] / "detectors" / "numeric" / "zscore_outliers"
    metadata_path = package / "meta.yaml"
    query_path = package / "query.sql"
    metadata_before = metadata_path.read_text(encoding="utf-8")
    query_before = query_path.read_bytes()
    lines = metadata_before.splitlines(keepends=True)
    prefix = f"{metadata_field}:"
    changed = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{prefix} {metadata_value}{newline}"
            changed = True
            break
    assert changed, metadata_field

    try:
        metadata_path.write_text("".join(lines), encoding="utf-8")
        assert query_path.read_bytes() == query_before

        replay = replay_signals(root)
        assert replay["status"] == "replay-unavailable"
        assert replay["replay_possible"] is False
        with pytest.raises(Exception, match=r"(?i)(rerun|review|detector|invalidat)"):
            accept_findings(root, ["claim-accepted"])
    finally:
        metadata_path.write_text(metadata_before, encoding="utf-8")
