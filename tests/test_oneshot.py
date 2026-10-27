from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from anomaly import catalogue, oneshot
from anomaly.detectors import registry

DETECTORS = Path(__file__).parents[1] / "detectors"


def _entries() -> dict[str, dict]:
    return {entry["id"]: entry for entry in catalogue.build_catalogue()["detectors"]}


def _request(entry: dict, **overrides) -> dict:
    request = {
        "id": entry["id"],
        "version": entry["version"],
        "fields": {field["name"]: field["name"] for field in entry["required_fields"]},
    }
    return {**request, **overrides}


def _package(detector_id: str) -> Path:
    return next(
        path.parent for path in DETECTORS.rglob("meta.yaml")
        if f"id: {detector_id}\n" in path.read_text(encoding="utf-8")
    )


def _single_table_ids() -> list[str]:
    return [
        detector_id for detector_id, entry in _entries().items()
        if entry["required_tables"] == ["*"]
    ]


@pytest.mark.parametrize("detector_id", _single_table_ids())
def test_released_detector_fixture_runs_through_one_shot_path(detector_id: str) -> None:
    entry = _entries()[detector_id]
    fixtures = _package(detector_id) / "fixtures"
    expected = json.loads((fixtures / "expected.json").read_text(encoding="utf-8"))
    expected = expected if isinstance(expected, list) else [expected]
    table = fixtures / "input.csv"

    signals = oneshot.run_detectors(table, [_request(entry)], approved=True)

    candidates = {signal["candidate_id"] for signal in signals}
    assert {item["candidate_id"] for item in expected} <= candidates
    for signal in signals:
        assert signal["status"] == "lead"
        assert signal["detector_hash"] == entry["implementation_hash"]
        assert signal["provenance"]["input_hash"] == (
            "sha256:" + hashlib.sha256(table.read_bytes()).hexdigest()
        )
        assert signal["provenance"]["parameters"] == {
            name: bound["default"] for name, bound in entry["parameters"].items()
        }


def test_one_shot_maps_columns_and_loads_only_mapped_ones(tmp_path: Path) -> None:
    table = tmp_path / "records.jsonl"
    rows = [
        {"record": index, "when": f"2026-01-0{index}", "value": value, "api_token": "sk_live_secret"}
        for index, value in enumerate([10, 11, 10, 50, 51], start=1)
    ]
    table.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    entry = _entries()["numeric.level_shift"]
    request = _request(entry, fields={"id": "record", "observed_at": "when", "amount": "value"})

    signals = oneshot.run_detectors(table, [request], approved=True)

    assert [signal["candidate_id"] for signal in signals] == ["row-4", "row-5"]
    assert "sk_live_secret" not in json.dumps(signals)
    assert signals[0]["provenance"]["input_format"] == "jsonl"


def test_caller_parameters_within_bounds_change_the_result() -> None:
    entry = _entries()["table.missingness_clusters"]
    table = _package(entry["id"]) / "fixtures" / "input.csv"

    signals = oneshot.run_detectors(
        table, [_request(entry, parameters={"min_missing_fraction": 0.9})], approved=True
    )

    assert signals == []


def _refusal_cases() -> list[tuple[str, dict, dict]]:
    entries = _entries()
    zscore = entries["numeric.zscore_outliers"]
    lobbying = next(entry for entry in entries.values() if entry["required_tables"] != ["*"])
    return [
        ("hash-mismatch", {"requests": [_request(zscore, implementation_hash="sha256:" + "0" * 64)]}, {"match": "implementation hash mismatch"}),
        ("version-mismatch", {"requests": [_request(zscore, version="9.9.9")]}, {"match": "version mismatch"}),
        ("no-catalogue-identity", {"requests": [{"id": zscore["id"], "fields": _request(zscore)["fields"]}]}, {"match": "name a catalogue version"}),
        ("unmapped-field", {"requests": [_request(zscore, fields={"id": "id"})]}, {"match": "unmapped required fields"}),
        ("out-of-bounds", {"requests": [_request(zscore, parameters={"z_threshold": 1000.0})]}, {"match": "out of bounds"}),
        ("wrong-type", {"requests": [_request(zscore, parameters={"z_threshold": "3"})]}, {"match": "out of bounds"}),
        ("unknown-parameter", {"requests": [_request(zscore, parameters={"limit": 1})]}, {"match": "unknown parameters"}),
        ("draft-detector", {"requests": [{"id": "credential.secret_patterns", "version": "1.1.0", "fields": {"id": "id"}}]}, {"match": "not in the released catalogue"}),
        ("named-tables", {"requests": [_request(lobbying)]}, {"match": "needs named tables"}),
        ("too-many", {"requests": [_request(zscore)] * 11}, {"match": "between 1 and 10"}),
        ("duplicate", {"requests": [_request(zscore)] * 2}, {"match": "once per call"}),
        ("unapproved", {"requests": [_request(zscore)]}, {"approved": False, "match": "approval is required"}),
    ]


@pytest.mark.parametrize(("case", "call", "options"), _refusal_cases(), ids=lambda value: value if isinstance(value, str) else "")
def test_one_shot_refuses_requests_outside_catalogue_or_bounds(case: str, call: dict, options: dict) -> None:
    table = _package("numeric.zscore_outliers") / "fixtures" / "input.csv"
    with pytest.raises(oneshot.OneShotError, match=options["match"]):
        oneshot.run_detectors(table, call["requests"], approved=options.get("approved", True))


def test_one_shot_refuses_installed_package_that_drifted_from_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = catalogue.build_catalogue()
    entry = next(item for item in published["detectors"] if item["id"] == "numeric.zscore_outliers")
    entry["implementation_hash"] = "sha256:" + "f" * 64
    stale = tmp_path / "catalogue.json"
    stale.write_text(json.dumps(published), encoding="utf-8")
    monkeypatch.setattr(catalogue, "CATALOGUE_PATH", stale)
    table = _package(entry["id"]) / "fixtures" / "input.csv"

    with pytest.raises(oneshot.OneShotError, match="differs from its catalogue entry"):
        oneshot.run_detectors(table, [_request(entry, implementation_hash=entry["implementation_hash"])], approved=True)


def test_sensitive_output_redact_policy_applies_to_one_shot_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "detectors"
    package = root / "user" / "token_echo"
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        "id: user.token_echo\nversion: 1.0.0\nrelease: released\ntitle: Token echo\n"
        "author: test\nlicense: CC0-1.0\ngroup: domain\ndescription: Echoes a token column.\n"
        "required_tables: ['*']\nrequired_fields: [id, secret_value]\n"
        "parameters: {}\nparameter_bounds: {}\nsignal_category: anomaly\nseverity: low\n"
        "expected_output: [candidate_id]\nassumptions: [none]\nfalse_positives: [none]\n"
        "sensitive_output: redact\nresource_limits: {timeout_seconds: 5}\nquery: query.sql\n",
        encoding="utf-8",
    )
    (package / "query.sql").write_text(
        'SELECT CAST(id AS VARCHAR) AS candidate_id, secret_value AS access_token FROM "{{table_id}}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "_ROOT", root)
    published = root / "catalogue.json"
    published.write_text(catalogue.render(catalogue.build_catalogue(root)), encoding="utf-8")
    monkeypatch.setattr(catalogue, "CATALOGUE_PATH", published)
    table = tmp_path / "records.csv"
    table.write_text("id,secret_value\n1,plain-looking-value\n", encoding="utf-8")

    signals = oneshot.run_detectors(
        table,
        [{"id": "user.token_echo", "version": "1.0.0", "fields": {"id": "id", "secret_value": "secret_value"}}],
        approved=True,
    )

    assert signals[0]["values"]["access_token"] == "[redacted]"


def _contract_csv(path: Path, table: str, rows: list[dict], rename: dict[str, str] | None = None) -> Path:
    from anomaly import domains

    columns = list(domains.load_domain("lobbying")["tables"][table]["columns"])
    rename = rename or {}
    header = [rename.get(column, column) for column in columns]
    lines = [",".join(header)] + [",".join(str(row.get(column, "")) for column in columns) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _filing(uuid: str, registrant: str, income: int, **extra) -> dict:
    return {"filing_uuid": uuid, "filing_year": 2025, "filing_period": "Q1", "filing_type": "Q1",
            "registrant_id": registrant, "registrant_name": registrant.upper(), "client_id": f"c-{uuid}",
            "client_name": f"Client {uuid}", "income": income, **extra}


def test_domain_detector_runs_on_contract_tables_with_a_column_map(tmp_path: Path) -> None:
    entry = _entries()["lobbying.foreign_filings"]
    filings = _contract_csv(tmp_path / "filings.csv", "lobbying_filings",
                            [_filing("f1", "r1", 5000), _filing("f2", "r2", 9000)])
    entities = _contract_csv(tmp_path / "entities.csv", "lobbying_foreign_entities",
                             [{"filing_uuid": "f2", "foreign_entity_name": "Acme SA", "country": "FR", "ppb_country": "FR"}],
                             rename={"foreign_entity_name": "entity"})
    request = {"id": entry["id"], "version": entry["version"],
               "columns": {"lobbying_foreign_entities": {"foreign_entity_name": "entity"}}}

    signals = oneshot.run_detectors(
        {"lobbying_filings": filings, "lobbying_foreign_entities": entities}, [request], approved=True
    )

    assert [signal["values"]["filing_uuid"] for signal in signals] == ["f2"]
    assert set(signals[0]["provenance"]["input_hashes"]) == {"lobbying_filings", "lobbying_foreign_entities"}


def test_domain_detector_binds_parameters_in_query_order(tmp_path: Path) -> None:
    # The catalogue lists parameters alphabetically (limit, min_total_income);
    # binding in that order would compare income against the limit (200).
    entry = _entries()["lobbying.single_client_juggernauts"]
    filings = _contract_csv(tmp_path / "filings.csv", "lobbying_filings", [_filing("f1", "small", 1000)])
    request = {"id": entry["id"], "version": entry["version"]}

    assert oneshot.run_detectors({"lobbying_filings": filings}, [request], approved=True) == []


def test_domain_detector_loads_an_absent_optional_column_as_null(tmp_path: Path) -> None:
    # client_general_description is optional in the lobbying contract, so a
    # register that does not publish it can still run the detector.
    entry = _entries()["lobbying.single_client_juggernauts"]
    filings = _contract_csv(tmp_path / "filings.csv", "lobbying_filings", [_filing("f1", "solo", 900000)])
    lines = filings.read_text(encoding="utf-8").splitlines()
    drop = lines[0].split(",").index("client_general_description")
    filings.write_text("\n".join(",".join(v for i, v in enumerate(line.split(",")) if i != drop) for line in lines) + "\n", encoding="utf-8")
    request = {"id": entry["id"], "version": entry["version"]}

    signals = oneshot.run_detectors({"lobbying_filings": filings}, [request], approved=True)

    assert [signal["values"]["registrant_id"] for signal in signals] == ["solo"]


@pytest.mark.parametrize(("tables", "columns", "match"), [
    ({}, None, "missing tables"),
    ({"lobbying_filings": "short"}, None, "lacks contract columns"),
    ({"lobbying_filings": "full"}, {"lobbying_filings": {"not_a_column": "x"}}, "must map contract columns"),
    ({"lobbying_filings": "full"}, {"legislators": {"name": "x"}}, "only name the detector's tables"),
    ({"lobbying_filings": "full"}, {"lobbying_filings": {"income": ""}}, "must map contract columns"),
])
def test_domain_detector_refuses_incomplete_or_invalid_tables(tmp_path: Path, tables: dict, columns, match: str) -> None:
    entry = _entries()["lobbying.single_client_juggernauts"]
    full = _contract_csv(tmp_path / "full.csv", "lobbying_filings", [_filing("f1", "r1", 1)])
    short = tmp_path / "short.csv"
    short.write_text("filing_uuid,income\nf1,1\n", encoding="utf-8")
    files = {name: {"full": full, "short": short}[kind] for name, kind in tables.items()}
    files = files or {"legislators": full}
    request = {"id": entry["id"], "version": entry["version"], **({"columns": columns} if columns else {})}

    with pytest.raises(oneshot.OneShotError, match=match):
        oneshot.run_detectors(files, [request], approved=True)


def test_core_detector_refuses_named_tables(tmp_path: Path) -> None:
    entry = _entries()["numeric.zscore_outliers"]
    table = _package(entry["id"]) / "fixtures" / "input.csv"

    with pytest.raises(oneshot.OneShotError, match="one table, not named tables"):
        oneshot.run_detectors({"anything": table}, [_request(entry)], approved=True)


def test_every_released_detector_query_passes_the_runner_sql_check() -> None:
    # The runner validates SQL more strictly than the registry (it rejects
    # comments), so a released query must pass the runner's own check.
    from anomaly import detect

    for item in catalogue.released_detectors():
        query = (Path(item["package"]) / "query.sql").read_text(encoding="utf-8")
        detect.validate_read_only_sql(query.replace("{{table_id}}", detect._identifier("tbl_" + "0" * 64)))
