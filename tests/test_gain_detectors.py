from __future__ import annotations

import csv
import hashlib
import importlib
import json
import os
import re
from pathlib import Path

import pytest


GAIN_MANIFEST = {
    "D1_spending_spikes": {"sql_hash": "0a110bb8b0fc1347", "rows": 200, "columns": ["registrant_id", "registrant_name", "filing_year", "filing_period", "total_income", "prior_mean", "prior_sd", "prior_n", "z_score"], "csv_sha256": "897b9fc3719896351e2e4de3dca04a1fc852fbf358c6ba026ce8c7598c737037"},
    "D2_missing_income_filings": {"sql_hash": "fb87b5e50dca9aa7", "rows": 200, "columns": ["registrant_id", "registrant_name", "quarterly_filings_with_null_income", "distinct_clients", "first_seen", "last_seen"], "csv_sha256": "ed1fea798ea180b4959585b197dc62cf874604e4eb847fa92de3cce3d2ff46b5"},
    "D3_revolving_door_candidates": {"sql_hash": "61b1486a422655b1", "rows": 500, "columns": ["lobbyist_id", "first_name", "last_name", "sample_position", "filings_with_lobbyist", "distinct_positions", "clients_lobbied_for"], "csv_sha256": "4254e0be967611451f5c399f7e1fed6c33426012969b818e1dd7a614f098c255"},
    "D4_foreign_filings": {"sql_hash": "f7c962b62d2393b1", "rows": 500, "columns": ["filing_uuid", "filing_year", "filing_period", "registrant_name", "client_name", "client_country", "client_ppb_country", "foreign_entity_name", "foreign_entity_country", "foreign_entity_ppb", "income", "url"], "csv_sha256": "8dd54b56a623504230c2fed212a03ad3ee285fb96e5d5774199331b142e4a157"},
    "D5_single_client_juggernauts": {"sql_hash": "f9e737b8f3554a90", "rows": 200, "columns": ["registrant_id", "registrant_name", "distinct_clients", "filings", "total_income", "earliest_year", "latest_year", "clients"], "csv_sha256": "047a4f4834295a4ea59edf016d89a228463a0743037297a0000c6e4fef596e9e"},
    "D6_pac_contribution_flow": {"sql_hash": "aac2e9c1e8815f67", "rows": 500, "columns": ["payee_name", "honoree_name", "n_contributions", "total_amount", "distinct_filings", "distinct_contributors"], "csv_sha256": "a4bce45c0a8d1c4bd273e4004159330183b622203cb898be7ff872af7ce2ab01"},
    "D7_issue_concentration_shifts": {"sql_hash": "d7d0657d4e725c32", "rows": 126, "columns": ["general_issue_code", "filing_year", "filing_period", "registrants", "total_income", "prior_income", "prior_registrants", "income_delta_pct", "registrants_delta_pct"], "csv_sha256": "945e47913e86c99ba06efd4dcfbac8fa0bc0b89866fd481b5edc8358945ccb7a"},
    "D8_new_registrant_surge": {"sql_hash": "e51ec9c1d23d4479", "rows": 45, "columns": ["registrant_id", "registrant_name", "filings_in_window", "distinct_clients", "total_income", "clients"], "csv_sha256": "dd80158ef5fe28e2e2da5f18fe5b9dd65b0b1878a60fae11927a3da6757e8550"},
    "D9_shell_pattern_filings": {"sql_hash": "bbbea171aa997a1e", "rows": 15, "columns": ["filing_uuid", "filing_year", "filing_period", "filing_type", "registrant_name", "client_name", "client_desc", "income", "shell_score", "sig_sovereign_client", "sig_established_govt", "sig_esoteric_terms", "sig_self_styled_title", "sig_posted_by_llc_slashes", "sig_global_pbc_naming", "url"], "csv_sha256": "b380e8c81243b767dedf863faf26a3c3f2a95b224f06966633e7538671f65554"},
    "D10_fara_gap_narrowed": {"sql_hash": "ae4ebdb2ecf19559", "rows": 200, "columns": ["filing_uuid", "filing_year", "registrant_name", "client_name", "client_country", "client_ppb_country", "fe_countries", "income", "sig_non_us_client", "sig_non_us_ppb", "sig_foreign_gov_topic", "sig_soe_pattern", "url"], "csv_sha256": "66087f341d23d9de815f3c6b9b191758cdb7f44f12a59b4c6b62f0f8c846ff3b"},
    "D11_revolving_door_committee_match": {"sql_hash": "a7712c723043a717", "rows": 200, "columns": ["lobbyist_id", "first_name", "last_name", "former_committee", "covered_position", "filing_uuid", "filing_year", "filing_period", "registrant_name", "client_name", "general_issue_code", "description", "income", "url"], "csv_sha256": "f09884d2874097a74ea31eb9fc072f6830273623ec28a7d7847c3ab55a155ed7"},
    "D12_committee_say_vs_pay": {"sql_hash": "274c4ef00515cd73", "rows": 161, "columns": ["lobbying_firm", "lobbied_client", "lobbyist", "former_role", "current_committee_members", "attack_press_releases", "committee_members_attacking", "income"], "csv_sha256": "508ee7a65bb3f1f535f8f190cdf4cbd88259b28e289ae8f44eade65c5df19352"},
}

SOURCE_REPOSITORY = "https://github.com/buriedsignals/gain-2026"
# Durable default: one clone serves every future run. Override with
# GAIN_FIXTURE_ROOT when a different checkout should be replayed.
SOURCE_ANOMALIES = Path(
    os.environ.get(
        "GAIN_FIXTURE_ROOT",
        str(Path.home() / ".cache" / "buriedsignals" / "gain-2026" / "case-trace" / "data-detective" / "anomalies"),
    )
)


# These tests replay the real GAIN-2026 case artifacts, which live outside the
# repository (sensitive source data, never committed). Acquire once:
#   git clone --depth 1 https://github.com/buriedsignals/gain-2026 \
#     ~/.cache/buriedsignals/gain-2026
# When the fixture root is absent, skip instead of failing: the suite stays
# green on machines without the case and runs in full wherever it exists.
pytestmark = [
    pytest.mark.skipif(
        not SOURCE_ANOMALIES.is_dir(),
        reason=f"GAIN-2026 fixture root not present: {SOURCE_ANOMALIES}",
    )
]

def _api():
    return importlib.import_module("anomaly.detectors.registry")


@pytest.fixture(autouse=True)
def _use_explicit_full_catalog_for_gain_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _api()
    discover = api.discover_detectors

    def discover_all(roots=None, **kwargs):
        kwargs.setdefault("limit", 100)
        return discover(roots, **kwargs)

    monkeypatch.setattr(api, "discover_detectors", discover_all)


def _all_detectors() -> list[dict[str, object]]:
    root = Path(__file__).parents[1] / "detectors"
    detectors = [
        _api().validate_detector_package(path.parent)
        for path in sorted(root.rglob("meta.yaml"))
        if "_template" not in path.parts
    ]
    return sorted(
        detectors,
        key=lambda item: (
            int(str(item["source_detector_id"])[1:])
            if str(item.get("source_detector_id", "")).startswith("D")
            and str(item["source_detector_id"])[1:].isdigit()
            else 10**9,
            item["id"],
        ),
    )


def _gain_packages() -> list[Path]:
    return sorted((Path(__file__).parents[1] / "detectors" / "us_lobbying").glob("*"))


def _write_registry_package(
    root: Path,
    detector_id: str,
    *,
    family: str,
    group: str,
    source_detector_id: str | None = None,
) -> Path:
    package = root / detector_id.replace(".", "-")
    package.mkdir()
    source_line = f"source_detector_id: {source_detector_id}\n" if source_detector_id else ""
    metadata = (
        f"id: {detector_id}\n"
        "version: 1.0.0\n"
        "title: Synthetic registry package\n"
        "author: test\n"
        "license: CC0-1.0\n"
        f"group: {group}\n"
        f"family: {family}\n"
        f"{source_line}"
        "description: A metadata-driven registry fixture.\n"
        "required_tables: [observations]\n"
        "required_fields: [id]\n"
        "parameters: {}\n"
        "signal_category: anomaly\n"
        "severity: low\n"
        "expected_output: [candidate_id]\n"
        "assumptions: [Synthetic prepared observations.]\n"
        "false_positives: [Synthetic fixture only.]\n"
        "sensitive_output: none\n"
        "resource_limits: {timeout_seconds: 5}\n"
        "query: query.sql\n"
    )
    (package / "meta.yaml").write_text(metadata, encoding="utf-8")
    (package / "query.sql").write_text(
        "SELECT id AS candidate_id FROM {{table_id}}",
        encoding="utf-8",
    )
    return package


def _approved_gain_case(
    tmp_path: Path,
    source_ids: tuple[str, ...] = ("senate_filings",),
    detector_ids: tuple[str, ...] = ("us_lobbying.spending_spikes",),
    source_payloads: dict[str, str] | None = None,
) -> Path:
    from anomaly.prepare import prepare_sources
    from anomaly.recommend import approve_detector_plan
    from p2_helpers import NOW, create_p2_case, register, write_source

    root = tmp_path / "case"
    create_p2_case(root)
    for index, source_id in enumerate(source_ids):
        payload = (source_payloads or {}).get(
            source_id,
            "id,registrant_id,registrant_name,filing_year,filing_period,income,filing_type\n"
            "1,1,Example,2025,Q1,100,Q1\n",
        )
        source = write_source(
            tmp_path / f"{source_id}-{index}.csv",
            payload,
        )
        register(root, source, source_id)
    prepare_sources(root, now=NOW)
    api = _api()
    plan = api.recommend_detectors(root, max_detectors=10)
    plan["recommended"] = list(detector_ids)
    plan["parameters"] = {detector_id: next(item["parameters"] for item in _all_detectors() if item["id"] == detector_id) for detector_id in detector_ids}
    table_ids = [
        table["table_id"]
        for table in json.loads(
            (root / "data" / "prepared" / "transforms.json").read_text()
        )["tables"]
    ]
    plan["reasons"] = {
        detector_id: {"table_ids": table_ids} for detector_id in detector_ids
    }
    (root / "detectors" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    approve_detector_plan(root, list(detector_ids), approved_by="test-journalist", now=NOW)
    return root


def test_gain_catalogue_is_a_separate_twelve_detector_family() -> None:
    gain = [item for item in _all_detectors() if item.get("family") == "us_lobbying"]

    assert [item["source_detector_id"] for item in gain] == [f"D{i}" for i in range(1, 13)]
    assert len(gain) == 12
    assert all(item["id"].startswith("us_lobbying.") for item in gain)


def test_gain_metadata_records_source_and_local_hashes() -> None:
    gain = [item for item in _all_detectors() if item.get("family") == "us_lobbying"]

    for item in gain:
        expected = GAIN_MANIFEST[item["source_name"]]
        assert item["source_sql_hash"] == expected["sql_hash"]
        assert item["implementation_hash"].startswith("sha256:")
        assert item["implementation_hash"] != "sha256:" + expected["sql_hash"]
        assert item["source_provenance_hash"].startswith("sha256:")


def test_gain_metadata_exposes_challenge_attribution_and_source_repository() -> None:
    gain = [item for item in _all_detectors() if item.get("family") == "us_lobbying"]

    assert all("GAIN 2026 Challenge" in item["description"] for item in gain)
    assert {item["source_repository"] for item in gain} == {SOURCE_REPOSITORY}

    for package in _gain_packages():
        metadata_text = (package / "meta.yaml").read_text(encoding="utf-8")
        assert "attribution:" in metadata_text
        assert "source_repository:" in metadata_text


def test_registry_preserves_package_groups_and_orders_by_metadata_id(tmp_path: Path) -> None:
    _write_registry_package(
        tmp_path, "us_lobbying.zeta", family="us_lobbying", group="relational", source_detector_id="D1"
    )
    _write_registry_package(
        tmp_path, "us_lobbying.alpha", family="us_lobbying", group="temporal", source_detector_id="D2"
    )

    discovered = _api().discover_detectors([tmp_path])

    assert [item["id"] for item in discovered] == ["us_lobbying.alpha", "us_lobbying.zeta"]
    assert {item["id"]: item["group"] for item in discovered} == {
        "us_lobbying.alpha": "temporal",
        "us_lobbying.zeta": "relational",
    }


def test_gain_packages_declare_memory_bounds() -> None:
    for package in _gain_packages():
        metadata = _api().validate_detector_package(package)
        assert isinstance(metadata["resource_limits"].get("memory_mb"), int)
        assert metadata["resource_limits"]["memory_mb"] > 0


@pytest.mark.parametrize("source_name, expected", GAIN_MANIFEST.items())
def test_gain_fixture_reproduces_source_rows_and_order(source_name: str, expected: dict[str, object]) -> None:
    package = next(path for path in _gain_packages() if path.name == source_name)
    fixture = package / "fixtures" / "expected.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == expected["columns"]
    assert len(rows) - 1 == expected["rows"]
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected["csv_sha256"]

    source_fixture = SOURCE_ANOMALIES / f"{source_name}.csv"
    with source_fixture.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle)) == rows


def test_gain_d1_executes_against_a_valid_prepared_schema_and_returns_detector_rows(
    tmp_path: Path,
) -> None:
    root = _approved_gain_case(
        tmp_path,
        source_payloads={
            "senate_filings": (
                "id,registrant_id,registrant_name,filing_year,filing_period,income,filing_type\n"
                "1,r-1,Example,2024,Q1,100000,Q1\n"
                "2,r-1,Example,2024,Q2,110000,Q2\n"
                "3,r-1,Example,2024,Q3,90000,Q3\n"
                "4,r-1,Example,2024,Q4,105000,Q4\n"
                "5,r-1,Example,2025,Q1,300000,Q1\n"
            )
        },
    )
    results = _api().execute_detectors(
        root,
        ["us_lobbying.spending_spikes"],
        approved=True,
        limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
    )

    assert results
    assert all(result["status"] == "lead" for result in results)
    assert all(result["detector_id"] == "us_lobbying.spending_spikes" for result in results)
    assert results[0]["registrant_id"] == "r-1"
    assert results[0]["prior_n"] >= 3
    assert results[0]["z_score"] >= 2
    required_signal_fields = {
        "signal_id", "detector_id", "detector_version", "detector_hash",
        "candidate_id", "category", "severity", "observed_at", "summary",
        "evidence_refs", "warnings", "status",
    }
    assert required_signal_fields <= results[0].keys()
    assert results[0]["category"] == "lobbying"
    assert results[0]["status"] == "lead"


def test_gain_d3_executes_against_valid_joined_schemas_and_returns_detector_rows(
    tmp_path: Path,
) -> None:
    root = _approved_gain_case(
        tmp_path,
        source_ids=("senate_filings", "senate_activity_lobbyists"),
        detector_ids=("us_lobbying.revolving_door_candidates",),
        source_payloads={
            "senate_filings": (
                "id,filing_uuid,client_name\n"
                "1,f-1,Example Client\n"
                "2,f-2,Another Client\n"
            ),
            "senate_activity_lobbyists": (
                "id,lobbyist_id,first_name,last_name,covered_position,filing_uuid\n"
                "1,l-1,Ada,Lovelace,Senior Legislative Director,f-1\n"
                "2,l-1,Ada,Lovelace,Senior Legislative Director,f-2\n"
            ),
        },
    )
    results = _api().execute_detectors(
        root,
        ["us_lobbying.revolving_door_candidates"],
        approved=True,
        limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
    )

    assert results
    assert results[0]["detector_id"] == "us_lobbying.revolving_door_candidates"
    assert results[0]["lobbyist_id"] == "l-1"
    assert results[0]["filings_with_lobbyist"] == 2
    assert results[0]["clients_lobbied_for"] == "Example Client | Another Client"

    transforms = json.loads(
        (root / "data" / "prepared" / "transforms.json").read_text(encoding="utf-8")
    )
    table_ids = {table["table_id"] for table in transforms["tables"]}
    source_hashes = {table["source"]["sha256"] for table in transforms["tables"]}
    provenance = results[0]["provenance"]
    assert set(provenance["table_ids"]) == table_ids
    assert set(provenance["source_hashes"]) == source_hashes
    assert set(provenance["table_sources"]) == table_ids
    assert {entry["source_hash"] for entry in provenance["table_sources"].values()} == source_hashes


def test_gain_execution_errors_raise_without_synthetic_leads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _approved_gain_case(
        tmp_path,
        source_payloads={"senate_filings": "id,name\n1,Incomplete\n"},
    )

    def fail_query(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise _api().detect.DetectorError("detector query rejected")

    monkeypatch.setattr(_api().detect, "_run_query", fail_query)

    with pytest.raises(_api().RegistryError, match="detector query"):
        _api().execute_detectors(
            root,
            ["us_lobbying.spending_spikes"],
            approved=True,
            limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
        )


def test_gain_parameters_are_bound_to_query_placeholders_with_explicit_semantics() -> None:
    for package in _gain_packages():
        metadata = _api().validate_detector_package(package)
        query = (package / "query.sql").read_text(encoding="utf-8")
        assert query.count("?") == len(metadata["parameters"]), metadata["id"]


def test_gain_multi_table_scope_executes_once_without_duplicate_leads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _approved_gain_case(
        tmp_path,
        ("senate_filings", "senate_activity_lobbyists"),
        ("us_lobbying.revolving_door_committee_match",),
    )
    calls: list[tuple[str, ...]] = []

    def run_once(*args: object, **kwargs: object) -> list[dict[str, object]]:
        calls.append(tuple(str(arg) for arg in args[1:3]))
        return [{"candidate_id": "one", "value": 1}]

    monkeypatch.setattr(_api().detect, "_run_query", run_once)
    monkeypatch.setattr(_api().detect, "validate_read_only_sql", lambda query: None)
    results = _api().execute_detectors(
        root,
        ["us_lobbying.revolving_door_committee_match"],
        approved=True,
        limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
    )

    assert len(calls) == 1
    assert len(results) == 1
    assert len({result["signal_id"] for result in results}) == len(results)


def test_gain_execution_rejects_memory_limits_above_package_bound(tmp_path: Path) -> None:
    root = _approved_gain_case(
        tmp_path,
        source_payloads={
            "senate_filings": (
                "id,registrant_id,registrant_name,filing_year,filing_period,income,filing_type\n"
                "1,r-1,Example,2024,Q1,100000,Q1\n"
                "2,r-1,Example,2024,Q2,110000,Q2\n"
                "3,r-1,Example,2024,Q3,90000,Q3\n"
                "4,r-1,Example,2024,Q4,105000,Q4\n"
                "5,r-1,Example,2025,Q1,300000,Q1\n"
            )
        },
    )
    metadata = next(item for item in _all_detectors() if item["id"] == "us_lobbying.spending_spikes")
    declared = metadata["resource_limits"]["memory_mb"]

    with pytest.raises(_api().RegistryError, match=r"(?i)memory"):
        _api().execute_detectors(
            root,
            ["us_lobbying.spending_spikes"],
            approved=True,
            limits={"memory_mb": declared + 1, "timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
        )


def test_gain_recommendation_is_category_and_data_type_aware_and_capped_at_ten(tmp_path: Path) -> None:
    root = _approved_gain_case(tmp_path)
    plan = _api().recommend_detectors(root, max_detectors=10)
    gain_menu = _api().recommend_detectors(root, max_detectors=10, family="us_lobbying")

    assert len(plan["recommended"]) <= 10
    assert any(detector_id.startswith("us_lobbying.") for detector_id in plan["recommended"])
    assert all(plan["reasons"][detector_id]["table_ids"] for detector_id in plan["recommended"])
    assert gain_menu["recommended"]
    assert all(detector_id.startswith("us_lobbying.") for detector_id in gain_menu["recommended"])
    assert {item["group"] for item in _all_detectors() if item.get("family") == "us_lobbying"} == {"domain"}


def test_gain_recommendation_excludes_multi_table_detector_from_sparse_case(tmp_path: Path) -> None:
    root = _approved_gain_case(tmp_path)

    plan = _api().recommend_detectors(root, max_detectors=10, family="us_lobbying")

    assert "us_lobbying.revolving_door_candidates" not in plan["recommended"]


def test_gain_execution_leads_include_complete_lineage_and_run_metadata(tmp_path: Path) -> None:
    root = _approved_gain_case(tmp_path, detector_ids=("us_lobbying.spending_spikes",))
    results = _api().execute_detectors(
        root,
        ["us_lobbying.spending_spikes"],
        approved=True,
        limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
    )

    assert results == []


_SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def test_gain_scope_remains_local_sql_only_without_forbidden_surfaces() -> None:
    roots = [Path(__file__).parents[1] / "src" / "anomaly", Path(__file__).parents[1] / "detectors" / "us_lobbying"]
    # The SVG namespace is mandated by the SVG specification for every SVG
    # document and is not a network surface: allowlist exactly that literal
    # instead of banning it from the charts module.
    text = (
        "\n".join(
            path.read_text(encoding="utf-8")
            for root in roots
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".yaml", ".sql", ".md", ".json", ".csv"}
        )
        .lower()
        .replace(_SVG_NAMESPACE.lower(), "")
    )
    forbidden = ("api_key", "hosted runtime", "membership", "metering", "navigator cli", "web ui", "deployment", "mcp", "agent persona", "http://", "https://")
    assert not any(re.search(rf"\b{re.escape(term)}\b", text) for term in forbidden if term not in {"https://"})


def test_gain_results_are_normalized_leads_with_source_provenance() -> None:
    result = _api().normalize_detector_result(
        {"filing_uuid": "f-1", "income": 10},
        detector_id="us_lobbying.d1_spending_spikes",
        source_detector_id="D1",
        source_sql_hash="0a110bb8b0fc1347",
        source_hash="sha256:source",
        detector_hash="sha256:local",
        table_id="senate_filings",
    )

    assert result["status"] == "lead"
    assert result["detector_id"] == "us_lobbying.d1_spending_spikes"
    assert result["provenance"] == {
        "source_family": "us_lobbying", "source_detector_id": "D1",
        "source_hash": "sha256:source", "source_sql_hash": "0a110bb8b0fc1347",
        "detector_hash": "sha256:local", "table_id": "senate_filings",
    }


def test_gain_execution_is_bounded_local_and_requires_approval(tmp_path: Path) -> None:
    with pytest.raises(Exception, match=r"(?i)(approv|gate|prepared)"):
        _api().execute_detectors(
            tmp_path / "case", ["us_lobbying.d1_spending_spikes"], approved=False,
            limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
        )


def test_gain_scope_has_no_hosted_orchestration_surface() -> None:
    roots = [Path(__file__).parents[1] / "src" / "anomaly", Path(__file__).parents[1] / "detectors" / "us_lobbying"]
    text_suffixes = {".py", ".yaml", ".sql", ".md", ".json", ".csv"}
    text = "\n".join(path.read_text(encoding="utf-8") for root in roots for path in root.rglob("*") if path.is_file() and path.suffix in text_suffixes).lower()
    forbidden = ("api_key", "hosted runtime", "membership", "metering", "navigator cli", "web ui", "deployment", "mcp", "agent persona")
    assert not any(re.search(rf"\b{re.escape(term)}\b", text) for term in forbidden)
