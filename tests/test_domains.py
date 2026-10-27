from __future__ import annotations

from pathlib import Path

import duckdb

from anomaly import catalogue, domains


def _contract_detectors() -> list[dict]:
    return [item for item in catalogue.released_detectors() if item["required_tables"] != ["*"]]


def test_every_multi_table_detector_names_a_domain_whose_contract_has_its_tables() -> None:
    detectors = _contract_detectors()
    assert detectors
    for item in detectors:
        contract = domains.load_domain(item["data_type"])
        assert set(item["required_tables"]) <= set(contract["tables"]), item["id"]


def test_contract_columns_are_enough_for_every_detector_query() -> None:
    # Each query must run against empty tables holding only the contract's
    # columns, so a source that fills the contract can serve every detector.
    for item in _contract_detectors():
        contract = domains.load_domain(item["data_type"])
        with duckdb.connect(":memory:") as connection:
            for table in item["required_tables"]:
                columns = contract["tables"][table]["columns"]
                definition = ", ".join(
                    f'"{column}" {domains.column_type(meaning)}' for column, meaning in columns.items()
                )
                connection.execute(f'CREATE TABLE "{table}" ({definition})')
            query = (Path(item["package"]) / "query.sql").read_text(encoding="utf-8")
            parameters = [item["parameters"][name] for name in item["parameters"]]
            connection.execute(query, parameters).fetchall()
