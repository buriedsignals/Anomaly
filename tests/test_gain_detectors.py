from __future__ import annotations

import csv
import hashlib
import importlib
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


def _api():
    return importlib.import_module("anomaly.detectors.registry")


def _gain_packages() -> list[Path]:
    return sorted((Path(__file__).parents[1] / "detectors" / "gain").glob("*"))


def test_gain_catalogue_is_a_separate_twelve_detector_family() -> None:
    gain = [item for item in _api().discover_detectors() if item.get("family") == "gain"]

    assert [item["source_detector_id"] for item in gain] == [f"D{i}" for i in range(1, 13)]
    assert len(gain) == 12
    assert all(item["id"].startswith("gain.") for item in gain)


def test_gain_metadata_records_source_and_local_hashes() -> None:
    gain = [item for item in _api().discover_detectors() if item.get("family") == "gain"]

    for item in gain:
        expected = GAIN_MANIFEST[item["source_name"]]
        assert item["source_sql_hash"] == expected["sql_hash"]
        assert item["implementation_hash"].startswith("sha256:")
        assert item["implementation_hash"] != "sha256:" + expected["sql_hash"]
        assert item["source_provenance_hash"].startswith("sha256:")


@pytest.mark.parametrize("source_name, expected", GAIN_MANIFEST.items())
def test_gain_fixture_reproduces_source_rows_and_order(source_name: str, expected: dict[str, object]) -> None:
    package = next(path for path in _gain_packages() if path.name == source_name)
    fixture = package / "fixtures" / "expected.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == expected["columns"]
    assert len(rows) - 1 == expected["rows"]
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected["csv_sha256"]


def test_gain_results_are_normalized_leads_with_source_provenance() -> None:
    result = _api().normalize_detector_result(
        {"filing_uuid": "f-1", "income": 10},
        detector_id="gain.d1_spending_spikes",
        source_detector_id="D1",
        source_sql_hash="0a110bb8b0fc1347",
        source_hash="sha256:source",
        detector_hash="sha256:local",
        table_id="senate_filings",
    )

    assert result["status"] == "lead"
    assert result["detector_id"] == "gain.d1_spending_spikes"
    assert result["provenance"] == {
        "source_family": "gain", "source_detector_id": "D1",
        "source_sql_hash": "0a110bb8b0fc1347", "source_hash": "sha256:source",
        "detector_hash": "sha256:local", "table_id": "senate_filings",
    }


def test_gain_execution_is_bounded_local_and_requires_approval(tmp_path: Path) -> None:
    with pytest.raises(Exception, match=r"(?i)(approv|gate|prepared)"):
        _api().execute_detectors(
            tmp_path / "case", ["gain.d1_spending_spikes"], approved=False,
            limits={"timeout_seconds": 2, "threads": 1, "max_output_rows": 20},
        )


def test_gain_scope_has_no_hosted_orchestration_surface() -> None:
    roots = [Path(__file__).parents[1] / "src" / "anomaly", Path(__file__).parents[1] / "detectors" / "gain"]
    text_suffixes = {".py", ".yaml", ".sql", ".md", ".json", ".csv"}
    text = "\n".join(path.read_text(encoding="utf-8") for root in roots for path in root.rglob("*") if path.is_file() and path.suffix in text_suffixes).lower()
    forbidden = ("api_key", "hosted runtime", "membership", "metering", "navigator cli", "web ui", "deployment", "mcp", "agent persona")
    assert not any(term in text for term in forbidden)
