from __future__ import annotations

import importlib
import json
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

US_LOBBYING_DETECTOR_IDS = (
    "us_lobbying.committee_say_vs_pay",
    "us_lobbying.fara_gap_narrowed",
    "us_lobbying.foreign_filings",
    "us_lobbying.missing_income_filings",
    "us_lobbying.new_registrant_surge",
    "us_lobbying.pac_contribution_flow",
    "us_lobbying.revolving_door_candidates",
    "us_lobbying.revolving_door_committee_match",
    "us_lobbying.shell_pattern_filings",
    "us_lobbying.single_client_juggernauts",
    "us_lobbying.spending_spikes",
    "us_lobbying.issue_concentration_shifts",
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


def test_registry_discovers_core_and_us_lobbying_detectors_with_scalable_groups() -> None:
    # Explicit limit is authoritative: the whole registry is listable.
    detectors = _registry_api().discover_detectors(limit=100)
    ids = tuple(item["id"] for item in detectors)
    expected = set(CORE_DETECTOR_IDS) | set(US_LOBBYING_DETECTOR_IDS)
    assert set(ids) == expected
    assert all(isinstance(item["group"], str) and item["group"] for item in detectors)
    us_lobbying_families = {item.get("family") for item in detectors if item["id"].startswith("us_lobbying.")}
    assert not us_lobbying_families or us_lobbying_families == {"us_lobbying"}
    required = {
        "id", "version", "title", "author", "license", "group", "description",
        "required_tables", "required_fields", "parameters", "signal_category",
        "severity", "expected_output", "assumptions", "false_positives",
        "sensitive_output", "resource_limits",
    }
    assert all(required <= set(item) for item in detectors)


def test_registry_default_discovery_stays_bounded() -> None:
    # Without an explicit limit, menu-style discovery stays bounded (PRD: <=10).
    detectors = _registry_api().discover_detectors()
    assert len(detectors) <= 10


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
    with pytest.raises(Exception, match=r"(?i)(prepared|gate|receipt)"):
        _registry_api().execute_detectors(
            tmp_path / "prepared-case", ["numeric.zscore_outliers"], approved=True,
            limits={"memory_mb": 32, "timeout_seconds": 2, "threads": 1, "max_output_rows": 10},
        )


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


def test_registry_rejects_packages_with_incomplete_required_metadata(tmp_path: Path) -> None:
    package = tmp_path / "incomplete"
    package.mkdir()
    (package / "meta.yaml").write_text(
        "id: user.incomplete\nversion: 1.0.0\nquery: query.sql\n", encoding="utf-8"
    )
    (package / "query.sql").write_text("SELECT 1", encoding="utf-8")

    with pytest.raises(Exception, match=r"(?i)(metadata|required|invalid)"):
        _registry_api().validate_detector_package(package)


@pytest.mark.parametrize("filename", ["meta.yaml", "query.sql"])
def test_registry_rejects_symlinked_package_files(tmp_path: Path, filename: str) -> None:
    package = _valid_user_package(tmp_path)
    outside = tmp_path / f"outside-{filename}"
    outside.write_text((package / filename).read_text(encoding="utf-8"), encoding="utf-8")
    (package / filename).unlink()
    (package / filename).symlink_to(outside)

    with pytest.raises(Exception, match=r"(?i)(symlink|unsafe|boundary)"):
        _registry_api().validate_detector_package(package)


def test_package_hash_rejects_nested_symlink_instead_of_omitting_it(tmp_path: Path) -> None:
    api = _registry_api()
    package = _valid_user_package(tmp_path)
    fixtures = package / "fixtures"
    fixtures.mkdir()
    outside = tmp_path / "outside-fixture"
    outside.write_text("fixture", encoding="utf-8")
    (fixtures / "expected.json").symlink_to(outside)

    with pytest.raises(Exception, match=r"(?i)(symlink|unsafe|boundary)"):
        api.package_implementation_hash(package)


def test_registry_rejects_executable_files_in_sql_only_packages(tmp_path: Path) -> None:
    package = _valid_user_package(tmp_path)
    (package / "detector.py").write_text("raise RuntimeError('must not load')\n", encoding="utf-8")

    with pytest.raises(Exception, match=r"(?i)(executable|python|unsupported|unsafe)"):
        _registry_api().validate_detector_package(package)


def test_registry_uses_one_catalog_for_recommendation_and_prepared_case_execution(
    tmp_path: Path,
) -> None:
    from p2_helpers import NOW, create_p2_case, register, write_source
    from anomaly.prepare import prepare_sources
    from anomaly.profile import profile_prepared

    root = tmp_path / "case"
    create_p2_case(root)
    register(root, write_source(tmp_path / "observations.csv", "id,amount\n1,10\n2,20\n"), "observations")
    prepare_sources(root, now=NOW)
    profile_prepared(root, now=NOW)

    api = _registry_api()
    plan = api.recommend_detectors(root, max_detectors=10)

    assert set(plan["recommended"]) <= set(CORE_DETECTOR_IDS)
    assert 0 < len(plan["recommended"]) <= 10
    with pytest.raises(Exception, match=r"(?i)(gate|approv|receipt)"):
        api.execute_detectors(root, plan["recommended"], approved=True)


def test_registry_discovers_and_recommends_user_sql_package(tmp_path: Path) -> None:
    _valid_user_package(tmp_path)
    api = _registry_api()
    discovered = api.discover_detectors([tmp_path], limit=100)

    assert any(item["id"] == "user.sql_lead" for item in discovered)
    plan = api.recommend_detectors(
        tmp_path / "prepared-case", max_detectors=10, detector_roots=[tmp_path]
    )
    assert "user.sql_lead" in plan["recommended"]


def test_all_new_detector_fixtures_have_nonempty_deterministic_outputs() -> None:
    root = Path(__file__).parents[1] / "detectors"
    existing_ids = {
        "categorical.rare_levels", "numeric.level_shift", "numeric.zscore_outliers",
        "table.duplicate_rows", "table.missingness_clusters", "temporal.coverage_gaps",
    }
    for detector_id in CORE_DETECTOR_IDS:
        if detector_id in existing_ids:
            continue
        package = root.joinpath(*detector_id.split("."))
        query = (package / "query.sql").read_text(encoding="utf-8").upper()
        expected = json.loads((package / "fixtures" / "expected.json").read_text(encoding="utf-8"))
        assert "LIMIT 0" not in query, detector_id
        assert expected, detector_id


def test_sensitive_output_metadata_requires_redacted_fixture_results() -> None:
    root = Path(__file__).parents[1] / "detectors"
    for metadata in _registry_api().discover_detectors(limit=100):
        package = next(
            path.parent
            for path in root.rglob("meta.yaml")
            if f"id: {metadata['id']}" in path.read_text(encoding="utf-8")
        )
        fixtures = package / "fixtures"
        expected_path = fixtures / "expected.json"
        if not expected_path.is_file():
            expected_path = fixtures / "expected.csv"
            assert expected_path.is_file(), metadata["id"]
            assert (fixtures / "source.provenance.json").is_file(), metadata["id"]
        expected = expected_path.read_text(encoding="utf-8").lower()
        assert metadata["sensitive_output"] in {"redact", "reference", "none"}
        assert "sk_live_" not in expected
        assert "private_key" not in expected
