from __future__ import annotations

import importlib
from pathlib import Path

import pytest


CORE_DETECTOR_IDS = (
    "categorical.rare_levels",
    "cross_dataset.location_conflicts",
    "credential.private_key_patterns",
    "credential.secret_patterns",
    "domain.contractor_concentration",
    "domain.procurement_bid_clusters",
    "network.cross_commit_overlap",
    "network.shared_infrastructure",
    "numeric.level_shift",
    "numeric.zscore_outliers",
    "relational.conflicting_profiles",
    "relational.shared_identifiers",
    "table.duplicate_rows",
    "table.missingness_clusters",
    "temporal.backdated_records",
    "temporal.coverage_gaps",
    "temporal.timezone_activity_shifts",
    "text.path_hostname_leakage",
    "text.portfolio_cloning",
    "text.secret_patterns",
)


def _registry_api():
    return importlib.import_module("anomaly.detectors.registry")


def _template_path() -> Path:
    return Path(__file__).parents[1] / "detectors" / "_template"


def _valid_user_package(root: Path) -> Path:
    package = root / "user-sql-lead"
    package.mkdir()
    (package / "meta.yaml").write_text(
        "id: user.sql_lead\n"
        "version: 1.0.0\n"
        "title: User SQL lead\n"
        "author: journalist\n"
        "license: CC0-1.0\n"
        "group: domain\n"
        "description: Finds a documented lead in prepared case data.\n"
        "required_tables:\n  - observations\n"
        "required_fields:\n  - amount\n"
        "parameters:\n  threshold: 10\n"
        "signal_category: anomaly\n"
        "severity: medium\n"
        "expected_output:\n  - candidate_id\n"
        "assumptions:\n  - Amount is comparable within the selected table.\n"
        "false_positives:\n  - Legitimate high-value observations.\n"
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


def test_registry_discovers_exactly_twenty_core_detectors_with_complete_metadata() -> None:
    detectors = _registry_api().discover_detectors()

    assert tuple(item["id"] for item in detectors) == CORE_DETECTOR_IDS
    assert len(detectors) == 20
    required = {
        "id", "version", "title", "author", "license", "group", "description",
        "required_tables", "required_fields", "parameters", "signal_category",
        "severity", "expected_output", "assumptions", "false_positives",
        "sensitive_output", "resource_limits",
    }
    assert all(required <= set(item) for item in detectors)


def test_registry_discovery_is_deterministic_and_rejects_duplicate_or_escape_packages(tmp_path: Path) -> None:
    api = _registry_api()
    assert api.discover_detectors() == api.discover_detectors()

    duplicate = tmp_path / "duplicate"
    duplicate.mkdir()
    (duplicate / "meta.yaml").write_text(
        "id: table.duplicate_rows\nversion: 1.0.0\nquery: query.sql\n", encoding="utf-8"
    )
    (duplicate / "query.sql").write_text("SELECT 1", encoding="utf-8")
    with pytest.raises(Exception, match=r"(?i)(duplicate|unsafe|invalid)"):
        api.discover_detectors([Path(__file__).parents[1] / "detectors", duplicate])

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "meta.yaml").write_text("id: unsafe.escape\n", encoding="utf-8")
    with pytest.raises(Exception, match=r"(?i)(symlink|escape|unsafe|boundary)"):
        api.validate_detector_package(outside, allowed_root=tmp_path / "detectors")


def test_user_sql_template_is_validated_without_executing_case_supplied_code(tmp_path: Path) -> None:
    package = _valid_user_package(tmp_path)
    metadata = _registry_api().validate_detector_package(package)

    assert metadata["id"] == "user.sql_lead"
    assert metadata["query"] == "query.sql"
    assert metadata["resource_limits"]["timeout_seconds"] == 5
    assert not list(package.rglob("*.py"))


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE observations SET amount = 0",
        "SELECT * FROM read_csv_auto(?)",
        "SELECT * FROM '/tmp/outside.parquet'",
        "SELECT 1; DROP TABLE observations",
    ],
)
def test_user_sql_template_rejects_mutation_external_access_and_multiple_statements(
    tmp_path: Path, query: str
) -> None:
    package = _valid_user_package(tmp_path)
    (package / "query.sql").write_text(query, encoding="utf-8")

    with pytest.raises(Exception, match=r"(?i)(read.only|external|unsafe|multiple|rejected)"):
        _registry_api().validate_detector_package(package)


def test_recommendation_is_capped_at_ten_and_execution_requires_explicit_approval(tmp_path: Path) -> None:
    api = _registry_api()
    result = api.recommend_detectors(tmp_path / "prepared-case", max_detectors=100)

    assert len(result["recommended"]) <= 10
    with pytest.raises(Exception, match=r"(?i)(approv|gate|plan)"):
        api.execute_detectors(tmp_path / "prepared-case", result["recommended"])


def test_execution_is_read_only_bounded_and_returns_provenance_bearing_leads(tmp_path: Path) -> None:
    result = _registry_api().execute_detectors(
        tmp_path / "prepared-case",
        ["table.duplicate_rows"],
        approved=True,
        limits={"memory_mb": 32, "timeout_seconds": 2, "threads": 1, "max_output_rows": 10},
    )

    assert result
    assert all(item["status"] == "lead" for item in result)
    assert all(item["provenance"]["detector_id"] for item in result)
    assert all(item["provenance"]["source_hash"] for item in result)
    assert all(item["provenance"]["parameters"] is not None for item in result)


def test_registry_and_detector_outputs_have_no_hosted_or_service_surface() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path(__file__).parents[1] / "src" / "anomaly").rglob("*.py")
    ).lower()
    forbidden = ("hosted", "membership", "metering", "navigator cli", "mcp", "web ui", "deployment")
    assert not any(term in source for term in forbidden)


def test_user_template_is_documented_and_has_no_runtime_or_network_dependency() -> None:
    template = _template_path()
    assert (template / "meta.yaml").is_file()
    assert (template / "query.sql").is_file()
    assert not (template / "detector.py").exists()
    text = (template / "query.sql").read_text(encoding="utf-8").upper()
    assert "SELECT" in text
    assert not any(token in text for token in ("ATTACH", "COPY", "INSTALL", "LOAD", "HTTP"))
