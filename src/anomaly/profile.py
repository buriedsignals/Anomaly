from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as parquet

from anomaly.case import resume_case
from anomaly.events import phase_event
from anomaly.semantics import UnsafeCasePathError, redact_credentials

_START = "<!-- anomaly:p2:start -->"
_END = "<!-- anomaly:p2:end -->"
_TABLE_ID = re.compile(r"tbl_[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INSTRUCTIONS = ("methodology.md", "context.md", "data-dictionary.md")

_AMBIGUITY = {
    "field": "location",
    "candidates": ["geographic", "text"],
    "reason": "multiple semantic roles match",
}
_DUCKDB_TYPES = {
    "integer": "BIGINT",
    "float": "DOUBLE",
    "datetime": "TIMESTAMP WITH TIME ZONE",
    "text": "VARCHAR",
}


class PreparedDataError(ValueError):
    """The prepared manifest, Parquet generation, and DuckDB index disagree."""


@phase_event("P2", "profile_prepared")
def profile_prepared(root: Path, *, now: datetime) -> dict[str, Any]:
    """Validate and completely profile the current prepared generation."""
    root = Path(root)
    resume_case(root)
    try:
        manifest, prepared_tables = _preflight(root)
        profile = {
            "schema_version": 1,
            "profiled_at": now.isoformat(),
            "tables": [
                _profile_table(declared, table)
                for declared, table in zip(manifest["tables"], prepared_tables, strict=True)
            ],
        }
        profile = redact_credentials(profile)
        replacements = _instruction_replacements(root, manifest, profile)
        _commit_outputs(root, profile, replacements)
        return profile
    except PreparedDataError:
        raise
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        duckdb.Error,
        pa.ArrowException,
        UnsafeCasePathError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
    ) as error:
        raise PreparedDataError(str(error)) from error


def _preflight(root: Path) -> tuple[dict[str, Any], list[pa.Table]]:
    manifest_path = _owned_path(root, "data/prepared/transforms.json", "data/prepared")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreparedDataError("invalid transform manifest") from error
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "prepared_at",
        "replay",
        "tables",
    }:
        raise PreparedDataError("invalid transform manifest schema")
    if manifest["schema_version"] != 1 or isinstance(manifest["schema_version"], bool):
        raise PreparedDataError("unsupported transform manifest")
    prepared_at = manifest["prepared_at"]
    if not isinstance(prepared_at, str):
        raise PreparedDataError("invalid preparation timestamp")
    try:
        datetime.fromisoformat(prepared_at)
    except ValueError as error:
        raise PreparedDataError("invalid preparation timestamp") from error
    if not isinstance(manifest["tables"], list):
        raise PreparedDataError("invalid transform tables")
    replay = manifest["replay"]
    if (
        not isinstance(replay, dict)
        or set(replay) != {"available", "reason", "sources"}
        or replay["available"] is not True
        or replay["reason"] is not None
        or replay["sources"] != []
    ):
        raise PreparedDataError("prepared replay is unavailable")

    declarations: list[dict[str, Any]] = []
    prepared_tables: list[pa.Table] = []
    seen: set[str] = set()
    for value in manifest["tables"]:
        declaration, table = _validate_prepared_table(root, value)
        if declaration["table_id"] in seen:
            raise PreparedDataError("duplicate prepared table")
        seen.add(declaration["table_id"])
        declarations.append(declaration)
        prepared_tables.append(table)
    if not declarations:
        raise PreparedDataError("prepared replay has no tables")

    index_path = _owned_path(root, "data/index.duckdb", "data")
    if not index_path.is_file() or index_path.is_symlink():
        raise PreparedDataError("missing DuckDB index")
    with duckdb.connect(str(index_path), read_only=True) as connection:
        loaded = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        if loaded != seen:
            raise PreparedDataError("DuckDB table set does not match manifest")
        for declaration, table in zip(declarations, prepared_tables, strict=True):
            table_id = declaration["table_id"]
            columns = [
                row
                for row in connection.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = 'main' AND table_name = ? "
                    "ORDER BY ordinal_position",
                    [table_id],
                ).fetchall()
            ]
            expected_columns = [
                (field["name"], _DUCKDB_TYPES[field["type"]])
                for field in declaration["fields"]
            ]
            if columns != expected_columns:
                raise PreparedDataError("DuckDB table shape does not match manifest")
            count = connection.execute(f'SELECT count(*) FROM "{table_id}"').fetchone()[0]
            if count != declaration["row_count"]:
                raise PreparedDataError("DuckDB row count does not match manifest")
            actual_rows = connection.execute(f'SELECT * FROM "{table_id}"').fetchall()
            expected_rows = [
                tuple(row[field["name"]] for field in declaration["fields"])
                for row in table.to_pylist()
            ]
            if actual_rows != expected_rows:
                raise PreparedDataError("DuckDB content does not match prepared Parquet")
    return manifest, prepared_tables


def _validate_prepared_table(root: Path, value: object) -> tuple[dict[str, Any], pa.Table]:
    if not isinstance(value, dict) or set(value) != {
        "source_id",
        "table_id",
        "source",
        "prepared",
        "row_count",
        "fields",
        "ambiguities",
    }:
        raise PreparedDataError("invalid prepared table declaration")
    source_id = value["source_id"]
    if not isinstance(source_id, str) or not source_id:
        raise PreparedDataError("invalid editorial source identity")
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
        raise PreparedDataError("invalid source reference")
    source_reference = source["path"]
    source_hash = source["sha256"]
    if (
        not isinstance(source_reference, str)
        or not source_reference
        or not isinstance(source_hash, str)
        or _SHA256.fullmatch(source_hash) is None
    ):
        raise PreparedDataError("invalid source reference members")
    source_path = _owned_path(root, source_reference, "data/raw")
    if (
        not source_path.is_file()
        or source_path.is_symlink()
        or _sha256(source_path) != source_hash
    ):
        raise PreparedDataError("source reference is missing or hash-mismatched")
    table_id = value["table_id"]
    if not isinstance(table_id, str) or _TABLE_ID.fullmatch(table_id) is None:
        raise PreparedDataError("invalid table identity")
    if not isinstance(value["row_count"], int) or isinstance(value["row_count"], bool) or value["row_count"] < 0:
        raise PreparedDataError("invalid prepared row count")
    prepared = value["prepared"]
    if not isinstance(prepared, dict) or set(prepared) != {"path", "sha256", "format"}:
        raise PreparedDataError("invalid prepared reference")
    expected_reference = f"data/prepared/{table_id}.parquet"
    if prepared.get("path") != expected_reference or prepared.get("format") != "parquet":
        raise PreparedDataError("prepared reference does not match table identity")
    if not isinstance(prepared.get("sha256"), str) or _SHA256.fullmatch(prepared["sha256"]) is None:
        raise PreparedDataError("invalid prepared hash")
    path = _owned_path(root, expected_reference, "data/prepared")
    if not path.is_file() or path.is_symlink() or _sha256(path) != prepared["sha256"]:
        raise PreparedDataError("prepared Parquet is missing or hash-mismatched")

    fields = value["fields"]
    if not isinstance(fields, list) or not fields:
        raise PreparedDataError("invalid field mappings")
    names: list[str] = []
    allowed_types = {"integer", "float", "datetime", "text"}
    role_types = {
        "identifier": allowed_types,
        "measure": {"integer", "float"},
        "temporal": {"datetime"},
        "latitude": {"integer", "float"},
        "longitude": {"integer", "float"},
        "label": allowed_types,
    }
    for field in fields:
        if not isinstance(field, dict) or set(field) != {"name", "type", "semantic_role"}:
            raise PreparedDataError("invalid field mapping")
        if not isinstance(field["name"], str) or not field["name"] or field["name"] in names:
            raise PreparedDataError("invalid mapped field name")
        field_type = field["type"]
        role = field["semantic_role"]
        if (
            field_type not in allowed_types
            or not isinstance(role, str)
            or role not in role_types
            or field_type not in role_types[role]
        ):
            raise PreparedDataError("invalid mapped field type or role")
        names.append(field["name"])

    ambiguities = value["ambiguities"]
    if not isinstance(ambiguities, list):
        raise PreparedDataError("invalid ambiguities")
    for ambiguity in ambiguities:
        if (
            not isinstance(ambiguity, dict)
            or set(ambiguity) != {"field", "candidates", "reason"}
            or ambiguity != _AMBIGUITY
            or ambiguity["field"] not in names
        ):
            raise PreparedDataError("invalid ambiguity")
    try:
        table = parquet.read_table(path)
    except (OSError, pa.ArrowException) as error:
        raise PreparedDataError("prepared Parquet cannot be decoded") from error
    if table.schema.names != names or table.num_rows != value["row_count"]:
        raise PreparedDataError("prepared Parquet shape does not match manifest")
    expected_types = {
        "integer": pa.int64(),
        "float": pa.float64(),
        "datetime": pa.timestamp("us", tz="UTC"),
        "text": pa.string(),
    }
    if any(table.schema.field(field["name"]).type != expected_types[field["type"]] for field in fields):
        raise PreparedDataError("prepared Parquet types do not match manifest")
    return value, table


def _safe_field_names(original_fields: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    for original in original_fields:
        redacted = redact_credentials(original)
        candidate = redacted
        if redacted != original:
            candidate = "redacted_" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        if not candidate:
            candidate = "field_" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        if candidate in used:
            candidate += "_" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        result[original] = candidate
        used.add(candidate)
    return result

def _profile_table(declared: dict[str, Any], table: pa.Table) -> dict[str, Any]:
    rows = table.to_pylist()
    field_mappings = declared["fields"]
    safe_names = _safe_field_names([field["name"] for field in field_mappings])
    field_metrics: dict[str, dict[str, Any]] = {}
    for mapping in field_mappings:
        name = mapping["name"]
        values = [row.get(name) for row in rows]
        present = [value for value in values if value is not None]
        counts = Counter(_distribution_key(value) for value in present)
        exemplars = {_distribution_key(value): _json_value(value) for value in present}
        ordered = sorted(counts, key=lambda key: (-counts[key], _sort_key(exemplars[key])))
        value_range: dict[str, Any] | None = None
        if present and mapping["type"] in {"integer", "float", "datetime"}:
            value_range = {
                "min": _json_value(min(present)),
                "max": _json_value(max(present)),
            }
        field_metrics[safe_names[name]] = {
            "missing_count": len(rows) - len(present),
            "missing_fraction": (len(rows) - len(present)) / len(rows) if rows else 0.0,
            "cardinality": len(counts),
            "range": value_range,
            "distribution": [
                {"value": exemplars[key], "count": counts[key]} for key in ordered
            ],
        }

    duplicate_rows = sum(
        count - 1
        for count in Counter(_row_key(row, field_mappings) for row in rows).values()
    )
    return {
        "table_id": declared["table_id"],
        "row_count": len(rows),
        "duplicate_rows": duplicate_rows,
        "fields": field_metrics,
        "temporal_coverage": _temporal_coverage(rows, field_mappings, safe_names),
        "geographic_coverage": _geographic_coverage(rows, field_mappings, safe_names),
    }

def _temporal_coverage(
    rows: list[dict[str, Any]],
    fields: list[dict[str, str]],
    safe_names: dict[str, str],
) -> dict[str, Any] | None:
    mapping = next((field for field in fields if field["semantic_role"] == "temporal"), None)
    if mapping is None:
        return None
    name = mapping["name"]
    values = [row[name] for row in rows if row.get(name) is not None]
    if not values:
        return None
    return {
        "field": safe_names[name],
        "start": _utc_iso(min(values)),
        "end": _utc_iso(max(values)),
    }


def _geographic_coverage(
    rows: list[dict[str, Any]],
    fields: list[dict[str, str]],
    safe_names: dict[str, str],
) -> dict[str, Any] | None:
    latitude = next((field["name"] for field in fields if field["semantic_role"] == "latitude"), None)
    longitude = next((field["name"] for field in fields if field["semantic_role"] == "longitude"), None)
    if latitude is None or longitude is None:
        return None
    complete = [
        (float(row[latitude]), float(row[longitude]))
        for row in rows
        if row.get(latitude) is not None and row.get(longitude) is not None
    ]
    if not complete:
        return None
    latitudes = [item[0] for item in complete]
    longitudes = [item[1] for item in complete]
    return {
        "latitude_field": safe_names[latitude],
        "longitude_field": safe_names[longitude],
        "row_count": len(complete),
        "bounds": {
            "min_latitude": min(latitudes),
            "max_latitude": max(latitudes),
            "min_longitude": min(longitudes),
            "max_longitude": max(longitudes),
        },
    }
def _instruction_replacements(
    root: Path, manifest: dict[str, Any], profile: dict[str, Any]
) -> dict[Path, bytes]:
    table_lines = [
        f"- `{table['table_id']}`: {table['row_count']} rows, hash-verified Parquet."
        for table in manifest["tables"]
    ]
    context_lines = [
        f"- `{table['table_id']}`: {table['row_count']} rows; {table['duplicate_rows']} duplicate rows."
        for table in profile["tables"]
    ]
    dictionary_lines: list[str] = []
    for table in manifest["tables"]:
        dictionary_lines.append(f"- `{table['table_id']}`")
        safe_names = _safe_field_names([field["name"] for field in table["fields"]])
        dictionary_lines.extend(
            f"  - {_markdown_code(safe_names[field['name']])}: "
            f"{field['type']}; {field['semantic_role']}"
            for field in table["fields"]
        )
    bodies = {
        "methodology.md": "\n".join([_START, "## Prepared data", *table_lines, _END]),
        "context.md": "\n".join([_START, "## Prepared data profile", *context_lines, _END]),
        "data-dictionary.md": "\n".join([_START, "## Prepared tables", *dictionary_lines, _END]),
    }
    replacements: dict[Path, bytes] = {}
    for name in _INSTRUCTIONS:
        path = _owned_path(root, f"instructions/{name}", "instructions")
        block = redact_credentials(bodies[name]).encode("utf-8")
        replacements[path] = _replace_owned_block(path.read_bytes(), block)
    return replacements


def _markdown_code(value: str) -> str:
    escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "&#96;")
        .replace("\r", "&#13;")
        .replace("\n", "&#10;")
    )
    return f"<code>{escaped}</code>"


def _replace_owned_block(current: bytes, block: bytes) -> bytes:
    start = _START.encode("ascii")
    end = _END.encode("ascii")
    starts = current.count(start)
    ends = current.count(end)
    if starts != ends or starts > 1:
        raise PreparedDataError("invalid owned instruction block")
    if starts == 1:
        before, remainder = current.split(start, 1)
        _, after = remainder.split(end, 1)
        return before + block + after
    separator = b"" if not current or current.endswith((b"\n", b"\r")) else b"\n"
    return current + separator + block + b"\n"


def _commit_outputs(root: Path, profile: dict[str, Any], replacements: dict[Path, bytes]) -> None:
    profile_path = _owned_path(root, "data/prepared/profile.json", "data/prepared")
    targets: dict[Path, bytes] = {
        profile_path: (json.dumps(profile, indent=2) + "\n").encode("utf-8"),
        **replacements,
    }
    originals = {path: path.read_bytes() if path.exists() else None for path in targets}
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, payload in targets.items():
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            temporary_path.write_bytes(payload)
            temporary[path] = temporary_path
        for path, temporary_path in temporary.items():
            os.replace(temporary_path, path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)


def _owned_path(root: Path, reference: str, namespace: str) -> Path:
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise UnsafeCasePathError(reference)
    base = Path(root).resolve()
    namespace_path = base / namespace
    candidate_path = base / relative
    _reject_alias(base, namespace_path)
    _reject_alias(base, candidate_path)
    expected = namespace_path.resolve()
    resolved = candidate_path.resolve()
    if resolved != expected and expected not in resolved.parents:
        raise UnsafeCasePathError(reference)
    return candidate_path


def _reject_alias(base: Path, path: Path) -> None:
    try:
        parts = path.relative_to(base).parts
    except ValueError as error:
        raise UnsafeCasePathError(str(path)) from error
    current = base
    for part in parts:
        current /= part
        if current.is_symlink():
            raise UnsafeCasePathError(str(path))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _distribution_key(value: Any) -> str:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row_key(row: dict[str, Any], fields: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(_distribution_key(row.get(field["name"])) for field in fields)


def _sort_key(value: Any) -> tuple[str, str]:
    return type(value).__name__, json.dumps(value, sort_keys=True, ensure_ascii=False)


