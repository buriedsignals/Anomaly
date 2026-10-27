"""Run released detectors on tables the caller supplies, without an Anomaly case.

A core detector runs on one table whose columns the caller maps to the
detector's required fields. A domain detector reads named tables: the caller
supplies one file per table in the domain contract (``domains/<data_type>.yaml``)
and may map contract columns to differently named file columns. The caller
names each detector by its catalogue entry and records its own approval.
Anomaly's case workflow and Gates A and B are not involved: every output is a
lead, never a finding.

    python -m anomaly.oneshot --table records.csv --request request.json --approved
    python -m anomaly.oneshot --tables lobbying_filings=filings.csv \
        --tables lobbying_foreign_entities=entities.csv --request request.json --approved

``request.json`` holds one request object or a list of at most ten:
``{"id": ..., "version" | "implementation_hash": ..., "fields": {...},
"columns": {table: {contract_column: file_column}}, "parameters": {...}}``.
Signals are written to stdout as JSONL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from anomaly import catalogue, detect, domains
from anomaly.detectors import registry

MAX_DETECTORS = 10
_READERS = {
    ".csv": ("csv", "read_csv_auto"),
    ".jsonl": ("jsonl", "read_json_auto"),
    ".ndjson": ("jsonl", "read_json_auto"),
    ".parquet": ("parquet", "read_parquet"),
}
_REQUEST_KEYS = {"id", "version", "implementation_hash", "fields", "columns", "parameters"}


class OneShotError(registry.RegistryError):
    """A one-shot request is outside the published catalogue or its bounds."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _catalogue_entries() -> dict[str, dict[str, Any]]:
    if not catalogue.CATALOGUE_PATH.is_file():
        raise OneShotError("published detector catalogue is missing")
    published = json.loads(catalogue.CATALOGUE_PATH.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in published["detectors"]}


def _check_parameters(
    detector_id: str, entry: dict[str, Any], supplied: Any, order: list[str],
) -> dict[str, Any]:
    """Bound-check parameters and return them in the query's placeholder order.

    The catalogue lists parameters alphabetically; ``order`` is the package's
    declared order, which is the order of the SQL's ``?`` placeholders.
    """
    supplied = {} if supplied is None else supplied
    if not isinstance(supplied, dict):
        raise OneShotError(f"parameters must be an object: {detector_id}")
    unknown = set(supplied) - set(entry["parameters"])
    if unknown:
        raise OneShotError(f"unknown parameters for {detector_id}: {sorted(unknown)}")
    effective: dict[str, Any] = {}
    for name in order:
        bound = entry["parameters"][name]
        value = supplied.get(name, bound["default"])
        kind = bound["type"]
        if kind == "string":
            valid = isinstance(value, str) and len(value) <= bound["max_length"]
        else:
            valid = (
                catalogue._is_number(value)
                and (kind == "number" or isinstance(value, int))
                and bound["minimum"] <= value <= bound["maximum"]
            )
        if not valid:
            raise OneShotError(f"parameter out of bounds: {detector_id}.{name}")
        effective[name] = value
    return effective


def _resolve(request: Any, entries: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (live metadata, catalogue entry) only when both name the same package."""
    if not isinstance(request, dict) or set(request) - _REQUEST_KEYS:
        raise OneShotError("invalid detector request")
    detector_id = request.get("id")
    entry = entries.get(detector_id)
    if entry is None:
        raise OneShotError(f"detector is not in the released catalogue: {detector_id}")
    if "version" not in request and "implementation_hash" not in request:
        raise OneShotError(f"name a catalogue version or implementation_hash: {detector_id}")
    if request.get("version", entry["version"]) != entry["version"]:
        raise OneShotError(f"catalogue version mismatch: {detector_id}")
    if request.get("implementation_hash", entry["implementation_hash"]) != entry["implementation_hash"]:
        raise OneShotError(f"catalogue implementation hash mismatch: {detector_id}")
    live = next(
        (item for item in catalogue.released_detectors() if item["id"] == detector_id), None
    )
    # A stale catalogue must not vouch for a package that has since changed.
    if live is None or live["implementation_hash"] != entry["implementation_hash"]:
        raise OneShotError(f"installed detector differs from its catalogue entry: {detector_id}")
    return live, entry


def _limits(metadata: dict[str, Any], limits: dict[str, Any] | None) -> dict[str, int]:
    effective = detect._validate_limits(limits)
    declared = metadata.get("resource_limits")
    declared = declared if isinstance(declared, dict) else {}
    # A detector's declared limits are ceilings the caller can only tighten.
    for key, ceiling in declared.items():
        if key in effective and isinstance(ceiling, int) and not isinstance(ceiling, bool) and ceiling > 0:
            effective[key] = min(effective[key], ceiling)
    return effective


def _signal(
    row: dict[str, Any], metadata: dict[str, Any], provenance: dict[str, Any], input_hash: str,
) -> dict[str, Any]:
    values = registry._redact_output(
        detect.redact_credentials(detect._json_safe(row)), str(metadata["sensitive_output"])
    )
    candidate = str(row.get("candidate_id") or next(iter(row.values()), "candidate"))
    key = f"{metadata['id']}:{input_hash}:{candidate}"
    return {
        "status": "lead",
        "signal_id": "signal-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
        "detector_id": metadata["id"],
        "detector_version": metadata["version"],
        "detector_hash": metadata["implementation_hash"],
        "candidate_id": candidate,
        "category": metadata["signal_category"],
        "severity": metadata["severity"],
        "summary": metadata["title"],
        "values": values,
        "provenance": provenance,
    }


def _table_file(table: Path) -> tuple[str, str, str]:
    """Return (input format, DuckDB reader, sha256 hash) for a safe table file."""
    table = Path(table)
    reader = _READERS.get(table.suffix.lower())
    if reader is None:
        raise OneShotError("table must be a .csv, .jsonl, .ndjson or .parquet file")
    if table.is_symlink() or not table.is_file():
        raise OneShotError("table file is missing or unsafe")
    return reader[0], reader[1], "sha256:" + hashlib.sha256(table.read_bytes()).hexdigest()


def _file_columns(connection: duckdb.DuckDBPyConnection, read_function: str, table: Path, input_format: str) -> set[str]:
    try:
        rows = connection.execute(f"DESCRIBE SELECT * FROM {read_function}(?)", [str(table)]).fetchall()
    except duckdb.Error as error:
        raise OneShotError(f"table could not be read as {input_format}") from error
    return {row[0] for row in rows}


def _column_maps(detector_id: str, request: dict[str, Any], contract: dict[str, Any], required: list[str]) -> dict[str, dict[str, str]]:
    """Validate ``columns``: only this detector's tables, only contract columns, string targets."""
    maps = request.get("columns") or {}
    if not isinstance(maps, dict) or set(maps) - set(required):
        raise OneShotError(f"columns may only name the detector's tables: {detector_id}")
    for table, mapping in maps.items():
        known = contract["tables"][table]["columns"]
        if not isinstance(mapping, dict) or not all(
            column in known and isinstance(source, str) and source for column, source in mapping.items()
        ):
            raise OneShotError(f"columns for {table} must map contract columns to file columns: {detector_id}")
    return maps


def _load_single(connection, table: Path, request: dict[str, Any], entry: dict[str, Any], table_name: str) -> dict[str, str]:
    detector_id = entry["id"]
    field_map = request.get("fields") or {}
    if not isinstance(field_map, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in field_map.items()
    ):
        raise OneShotError(f"fields must map required field names to columns: {detector_id}")
    required = [field["name"] for field in entry["required_fields"]]
    unmapped = [name for name in required if name not in field_map]
    if unmapped:
        raise OneShotError(f"unmapped required fields for {detector_id}: {unmapped}")
    input_format, read_function, _ = _table_file(table)
    columns = _file_columns(connection, read_function, table, input_format)
    missing = sorted({column for column in field_map.values() if column not in columns})
    if missing:
        raise OneShotError(f"mapped columns are not in the table: {missing}")
    # Load only the mapped columns, renamed to the detector's field names.
    projection = ", ".join(f"{_quote(field_map[name])} AS {_quote(name)}" for name in required)
    connection.execute(f"CREATE TABLE {table_name} AS SELECT {projection} FROM {read_function}(?)", [str(table)])
    return {name: field_map[name] for name in required}


def _load_contract(connection, tables: dict[str, Path], request: dict[str, Any], metadata: dict[str, Any]) -> dict[str, dict[str, str]]:
    detector_id = metadata["id"]
    required = list(metadata["required_tables"])
    try:
        contract = domains.load_domain(str(metadata.get("data_type")))
    except domains.DomainError as error:
        raise OneShotError(f"no domain contract for {detector_id}") from error
    absent = [name for name in required if name not in tables]
    if absent:
        raise OneShotError(f"missing tables for {detector_id}: {absent}")
    maps = _column_maps(detector_id, request, contract, required)
    loaded: dict[str, dict[str, str]] = {}
    for name in required:
        table = tables[name]
        input_format, read_function, _ = _table_file(table)
        contract_columns = contract["tables"][name]["columns"]
        mapping = {column: maps.get(name, {}).get(column, column) for column in contract_columns}
        missing = sorted({source for source in mapping.values()} - _file_columns(connection, read_function, table, input_format))
        if missing:
            raise OneShotError(f"{name} lacks contract columns: {missing}")
        # Load only contract columns, cast to the contract's types.
        projection = ", ".join(
            f"CAST({_quote(mapping[column])} AS {domains.column_type(meaning)}) AS {_quote(column)}"
            for column, meaning in contract_columns.items()
        )
        try:
            connection.execute(f"CREATE TABLE {_quote(name)} AS SELECT {projection} FROM {read_function}(?)", [str(table)])
        except duckdb.Error as error:
            raise OneShotError(f"{name} does not match the {metadata['data_type']} contract types") from error
        loaded[name] = mapping
    return loaded


def run_detectors(
    table: Path | dict[str, Path],
    requests: list[dict[str, Any]],
    *,
    approved: bool = False,
    limits: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run up to ten catalogued detectors in a sealed in-memory DuckDB.

    ``table`` is one file for core detectors (``required_tables == ["*"]``) or
    ``{contract_table: file}`` for domain detectors.
    """
    if approved is not True:
        raise OneShotError("explicit caller approval is required before execution")
    if not isinstance(requests, list) or not 1 <= len(requests) <= MAX_DETECTORS:
        raise OneShotError(f"between 1 and {MAX_DETECTORS} detectors may run per call")
    named = isinstance(table, dict)
    if named:
        tables = {str(name): Path(path) for name, path in table.items()}
        input_hashes = {name: _table_file(path)[2] for name, path in sorted(tables.items())}
        input_format = "tables"
    else:
        single = Path(table)
        input_format, _, single_hash = _table_file(single)
        input_hashes = {"*": single_hash}
    input_hash = single_hash if not named else "sha256:" + hashlib.sha256(
        json.dumps(input_hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()

    entries = _catalogue_entries()
    resolved = [_resolve(request, entries) for request in requests]
    ids = [metadata["id"] for metadata, _ in resolved]
    if len(set(ids)) != len(ids):
        raise OneShotError("each detector may appear once per call")
    for metadata, _ in resolved:
        if (metadata.get("required_tables") == ["*"]) == named:
            kind = "one table, not named tables" if named else "named tables; supply {table: file}"
            raise OneShotError(f"detector needs {kind}: {metadata['id']}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    results: list[dict[str, Any]] = []
    for request, (metadata, entry) in zip(requests, resolved, strict=True):
        detector_id = metadata["id"]
        parameters = _check_parameters(detector_id, entry, request.get("parameters"), list(metadata["parameters"]))
        detector_limits = _limits(metadata, limits)
        query = (Path(metadata["package"]) / "query.sql").read_text(encoding="utf-8")
        table_name = "tbl_" + input_hash.removeprefix("sha256:")
        query = query.replace("{{table_id}}", detect._identifier(table_name))
        detect.validate_read_only_sql(query)
        with duckdb.connect(":memory:") as connection:
            connection.execute("SET threads = ?", [detector_limits["threads"]])
            connection.execute("SET memory_limit = ?", [f"{detector_limits['memory_mb']}MB"])
            if named:
                mapping: Any = _load_contract(connection, tables, request, metadata)
            else:
                mapping = _load_single(connection, single, request, entry, table_name)
            # Seal the connection before any detector SQL runs.
            connection.execute("SET enable_external_access = false")
            rows = detect._run_query(
                connection, query, list(parameters.values()),
                detector_limits["timeout_seconds"], detector_limits["max_output_rows"],
            )
        provenance = {
            "input_hash": input_hash,
            "input_format": input_format,
            "field_map" if not named else "column_map": mapping,
            "parameters": parameters,
            "limits": detector_limits,
            "run_id": run_id,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "approval": "caller-recorded",
        }
        if named:
            provenance["input_hashes"] = {name: input_hashes[name] for name in metadata["required_tables"]}
        results.extend(_signal(row, metadata, provenance, input_hash) for row in rows)
    return results


def _named_table(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("use --tables NAME=PATH")
    return name, Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anomaly.oneshot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--table", type=Path, help="CSV, JSONL or Parquet file for core detectors")
    source.add_argument("--tables", type=_named_table, action="append",
                        help="NAME=PATH for each contract table a domain detector reads (repeatable)")
    parser.add_argument("--request", required=True, type=Path, help="JSON request object or list")
    parser.add_argument("--approved", action="store_true", help="caller has recorded its own approval")
    args = parser.parse_args(argv)
    try:
        requests = json.loads(args.request.read_text(encoding="utf-8"))
        requests = requests if isinstance(requests, list) else [requests]
        table = dict(args.tables) if args.tables else args.table
        signals = run_detectors(table, requests, approved=args.approved)
    except (OSError, json.JSONDecodeError, registry.RegistryError) as error:
        print(f"anomaly.oneshot: {error}", file=sys.stderr)
        return 2
    for signal in signals:
        sys.stdout.write(json.dumps(signal, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
