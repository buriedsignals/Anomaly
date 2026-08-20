from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as parquet

import anomaly.decode as public_decoder
from anomaly.case import resume_case
from anomaly.semantics import (
    UnsafeCasePathError,
    redact_credentials,
    validate_case_documents,
)

_TABLE_ID = re.compile(r"tbl_[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)\Z")
_IDENTIFIER_NAMES = {"id", "identifier", "key", "pk", "uuid", "imo"}
_TEMPORAL_NAMES = {
    "date",
    "datetime",
    "time",
    "timestamp",
    "observed_at",
    "created_at",
    "updated_at",
    "seen_at",
    "last_seen",
}
_LATITUDE_NAMES = {"lat", "latitude"}
_LONGITUDE_NAMES = {"lon", "lng", "longitude"}


def prepare_sources(root: Path, *, now: datetime) -> dict[str, Any]:
    """Build one hash-bound prepared generation for every registered source."""
    root = Path(root)
    resume_case(root)
    sources, _ = validate_case_documents(root)
    prepared_dir = _owned_directory(root, "data/prepared")
    index_path = _owned_path(root, "data/index.duckdb", "data")

    failures = _source_failures(root, sources)
    if not sources:
        return _commit_unavailable(
            prepared_dir,
            index_path,
            now,
            reason="no-included-sources",
            sources=[],
        )
    if failures:
        return _commit_unavailable(
            prepared_dir,
            index_path,
            now,
            reason="required-sources-unavailable",
            sources=failures,
        )

    decoded: list[tuple[dict[str, Any], list[dict[str, Any]], str]] = []
    decode_failures: list[dict[str, str]] = []
    for source in sources:
        raw_path = _source_path(root, source["path"])
        source_reference = source["path"]
        reason: str | None = None
        rows: list[dict[str, Any]] | None = None
        try:
            observation = _source_observation(raw_path)
            snapshot = _verified_snapshot(raw_path, source["content_hash"])
        except SourceMutationError:
            reason = "source-hash-mismatch"
        except OSError:
            reason = "source-missing"
        else:
            decode_failed = False
            try:
                with public_decoder.verified_source_snapshot(raw_path, snapshot):
                    rows = public_decoder.decode_records(raw_path, source["format"])
            except Exception:
                decode_failed = True
            try:
                changed = _source_observation(raw_path) != observation
            except OSError:
                reason = "source-missing"
            else:
                if changed:
                    reason = "source-hash-mismatch"
                elif decode_failed:
                    reason = "source-decode-failed"
                else:
                    assert rows is not None
                    decoded.append((source, rows, source_reference))
                    continue
        assert reason is not None
        decode_failures.append(
            {
                "source_id": redact_credentials(source["source_id"]),
                "reason": reason,
            }
        )
    if decode_failures:
        return _commit_unavailable(
            prepared_dir,
            index_path,
            now,
            reason="required-sources-unavailable",
            sources=decode_failures,
        )
    planned: list[
        tuple[
            dict[str, Any],
            list[dict[str, Any]],
            list[dict[str, str]],
            list[dict[str, Any]],
            pa.Table,
            str,
        ]
    ] = []
    normalization_failures: list[dict[str, str]] = []
    for source, rows, source_reference in decoded:
        try:
            normalized, fields, ambiguities = _normalize(rows)
            if not fields:
                raise ValueError("zero-column records cannot be represented losslessly")
            arrow_table = _arrow_table(normalized, fields)
            planned.append(
                (source, normalized, fields, ambiguities, arrow_table, source_reference)
            )
        except (ValueError, TypeError, OverflowError, pa.ArrowException):
            normalization_failures.append(
                {
                    "source_id": redact_credentials(source["source_id"]),
                    "reason": "source-decode-failed",
                }
            )
    if normalization_failures:
        return _commit_unavailable(
            prepared_dir,
            index_path,
            now,
            reason="required-sources-unavailable",
            sources=normalization_failures,
        )

    staging = Path(tempfile.mkdtemp(prefix=".p2-", dir=root / "data"))
    staging_prepared = staging / "prepared"
    staging_prepared.mkdir()
    staging_index = staging / "index.duckdb"
    tables: list[dict[str, Any]] = []
    arrow_tables: list[tuple[str, pa.Table]] = []
    structural_occurrences: dict[bytes, int] = {}
    try:
        for source, normalized, fields, ambiguities, arrow_table, source_reference in planned:
            structural_key = _structural_source_key(source)
            occurrence = structural_occurrences.get(structural_key, 0)
            structural_occurrences[structural_key] = occurrence + 1
            table_id = _table_id(source, occurrence)
            output = staging_prepared / f"{table_id}.parquet"
            parquet.write_table(arrow_table, output, compression="zstd")
            prepared_reference = f"data/prepared/{table_id}.parquet"
            tables.append(
                {
                    "source_id": redact_credentials(source["source_id"]),
                    "table_id": table_id,
                    "source": {
                        "path": source_reference,
                        "sha256": source["content_hash"],
                    },
                    "prepared": {
                        "path": prepared_reference,
                        "sha256": _sha256(output),
                        "format": "parquet",
                    },
                    "row_count": len(normalized),
                    "fields": fields,
                    "ambiguities": ambiguities,
                }
            )
            arrow_tables.append((table_id, arrow_table))
        _write_index(staging_index, arrow_tables)
        manifest = {
            "schema_version": 1,
            "prepared_at": now.isoformat(),
            "replay": {"available": True, "reason": None, "sources": []},
            "tables": tables,
        }
        _write_json(staging_prepared / "transforms.json", manifest)
        late_failures = [
            {
                "source_id": table["source_id"],
                "reason": "source-hash-mismatch",
            }
            for table in tables
            if _sha256(_source_path(root, table["source"]["path"]))
            != table["source"]["sha256"]
        ]
        if late_failures:
            return _commit_unavailable(
                prepared_dir,
                index_path,
                now,
                reason="required-sources-unavailable",
                sources=late_failures,
            )
        _commit_generation(prepared_dir, index_path, staging_prepared, staging_index)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
def _source_failures(root: Path, sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for source in sources:
        reason: str | None = None
        if redact_credentials(source["path"]) != source["path"]:
            reason = "source-path-unsafe"
        elif not source["included"]:
            reason = "source-excluded"
        else:
            raw_path = _source_path(root, source["path"])
            if not raw_path.is_file() or raw_path.is_symlink():
                reason = "source-missing"
            else:
                try:
                    digest = _sha256(raw_path)
                except OSError:
                    reason = "source-missing"
                else:
                    if digest != source["content_hash"]:
                        reason = "source-hash-mismatch"
        if reason is not None:
            failures.append(
                {
                    "source_id": redact_credentials(source["source_id"]),
                    "reason": reason,
                }
            )
    return failures

def _source_observation(path: Path) -> tuple[int, int, int, int, int, int]:
    stat = path.stat()
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        stat.st_mode,
    )

def _verified_snapshot(path: Path, expected_hash: str) -> bytes:
    payload = path.read_bytes()
    if _sha256_bytes(payload) != expected_hash:
        raise SourceMutationError(str(path))
    return payload







def _normalize(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    original_fields: list[str] = []
    for row in rows:
        for name in row:
            if name not in original_fields:
                original_fields.append(name)

    names = _safe_field_names(original_fields)
    columns: dict[str, list[Any]] = {names[name]: [] for name in original_fields}
    for row in rows:
        for original in original_fields:
            columns[names[original]].append(_safe_value(row.get(original)))

    fields: list[dict[str, str]] = []
    ambiguities: list[dict[str, Any]] = []
    converted: dict[str, list[Any]] = {}
    for original in original_fields:
        name = names[original]
        inferred = _infer_type(columns[name])
        role, ambiguity = _semantic_role(name, inferred)
        fields.append({"name": name, "type": inferred, "semantic_role": role})
        if ambiguity is not None:
            ambiguities.append(ambiguity)
        converted[name] = [_convert(value, inferred) for value in columns[name]]

    normalized = [
        {field["name"]: converted[field["name"]][row_number] for field in fields}
        for row_number in range(len(rows))
    ]
    return normalized, fields, ambiguities


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
            candidate = candidate + "_" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        result[original] = candidate
        used.add(candidate)
    return result


def _safe_value(value: Any) -> Any:
    value = _redact_nested(value)
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, (bool, int, float, date, datetime)):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _redact_nested(value: Any) -> Any:
    if isinstance(value, str):
        return redact_credentials(value)
    if isinstance(value, dict):
        original_names = [str(name) for name in value]
        safe_names = _safe_field_names(original_names)
        return {
            safe_names[str(name)]: _redact_nested(item)
            for name, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_nested(item) for item in value]
    return value


def _infer_type(values: list[Any]) -> str:
    present = [value for value in values if value is not None]
    if not present:
        return "text"
    if all(_as_integer(value) is not None for value in present):
        return "integer"
    if all(_as_float(value) is not None for value in present):
        return "float"
    if all(_as_datetime(value) is not None for value in present):
        return "datetime"
    return "text"


def _semantic_role(name: str, inferred: str) -> tuple[str, dict[str, Any] | None]:
    normalized = name.strip().casefold()
    if normalized == "location":
        return "label", {
            "field": name,
            "candidates": ["geographic", "text"],
            "reason": "multiple semantic roles match",
        }
    if normalized in _LATITUDE_NAMES:
        return ("latitude" if inferred in {"integer", "float"} else "label"), None
    if normalized in _LONGITUDE_NAMES:
        return ("longitude" if inferred in {"integer", "float"} else "label"), None
    if normalized in _IDENTIFIER_NAMES or normalized.endswith("_id"):
        return "identifier", None
    if normalized in _TEMPORAL_NAMES or normalized.endswith("_at"):
        return ("temporal" if inferred == "datetime" else "label"), None
    if inferred in {"integer", "float"}:
        return "measure", None
    if inferred == "datetime":
        return "temporal", None
    return "label", None


def _convert(value: Any, inferred: str) -> Any:
    if value is None:
        return None
    if inferred == "integer":
        return _as_integer(value)
    if inferred == "float":
        return _as_float(value)
    if inferred == "datetime":
        return _as_datetime(value)
    return str(value)


def _as_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    if isinstance(value, str) and _INTEGER.fullmatch(value):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(value), time.min)
            except ValueError:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _arrow_table(rows: list[dict[str, Any]], fields: list[dict[str, str]]) -> pa.Table:
    arrow_types = {
        "integer": pa.int64(),
        "float": pa.float64(),
        "datetime": pa.timestamp("us", tz="UTC"),
        "text": pa.string(),
    }
    schema = pa.schema([pa.field(field["name"], arrow_types[field["type"]]) for field in fields])
    columns = [
        pa.array([row[field["name"]] for row in rows], type=arrow_types[field["type"]])
        for field in fields
    ]
    return pa.Table.from_arrays(columns, schema=schema)


def _structural_source_key(source: dict[str, Any]) -> bytes:
    return json.dumps(
        {
            "content_hash": source["content_hash"],
            "format": source["format"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _table_id(source: dict[str, Any], occurrence: int = 0) -> str:
    structural = json.dumps(
        {
            "source": _structural_source_key(source).decode("utf-8"),
            "occurrence": occurrence,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    result = "tbl_" + hashlib.sha256(structural).hexdigest()
    assert _TABLE_ID.fullmatch(result)
    return result


def _write_index(path: Path, tables: list[tuple[str, pa.Table]]) -> None:
    connection = duckdb.connect(str(path))
    try:
        for number, (table_id, table) in enumerate(tables):
            view = f"prepared_{number}"
            connection.register(view, table)
            connection.execute(f'CREATE TABLE "{table_id}" AS SELECT * FROM "{view}"')
            connection.unregister(view)
        connection.execute("CHECKPOINT")
    finally:
        connection.close()




def _commit_generation(
    prepared_dir: Path,
    index_path: Path,
    staging_prepared: Path,
    staging_index: Path | None,
) -> None:
    prepared_dir.mkdir(parents=True, exist_ok=True)
    rollback = Path(tempfile.mkdtemp(prefix=".p2-rollback-", dir=prepared_dir.parent))
    rollback_prepared = rollback / "prepared"
    rollback_prepared.mkdir()
    rollback_index = rollback / "index.duckdb"
    try:
        for path in prepared_dir.iterdir():
            if path.is_symlink():
                raise UnsafeCasePathError(str(path))
            if path.is_file():
                shutil.copy2(path, rollback_prepared / path.name)
        had_index = index_path.is_file()
        if had_index:
            shutil.copy2(index_path, rollback_index)

        wanted = {path.name for path in staging_prepared.iterdir() if path.is_file()}
        try:
            for path in prepared_dir.iterdir():
                if path.is_file() and path.name not in wanted:
                    path.unlink()
            for path in sorted(staging_prepared.iterdir(), key=lambda item: item.name):
                if path.is_file():
                    os.replace(path, prepared_dir / path.name)
            if staging_index is None:
                if index_path.exists():
                    index_path.unlink()
            else:
                os.replace(staging_index, index_path)
        except BaseException:
            _restore_generation(
                prepared_dir,
                index_path,
                rollback_prepared,
                rollback_index if had_index else None,
            )
            raise
    finally:
        shutil.rmtree(rollback, ignore_errors=True)


def _restore_generation(
    prepared_dir: Path,
    index_path: Path,
    rollback_prepared: Path,
    rollback_index: Path | None,
) -> None:
    for path in prepared_dir.iterdir():
        if path.is_file() or path.is_symlink():
            path.unlink()
    for path in rollback_prepared.iterdir():
        shutil.copy2(path, prepared_dir / path.name)
    if rollback_index is None:
        if index_path.exists() or index_path.is_symlink():
            index_path.unlink()
    else:
        shutil.copy2(rollback_index, index_path)


def _commit_unavailable(
    prepared_dir: Path,
    index_path: Path,
    now: datetime,
    *,
    reason: str,
    sources: list[dict[str, str]],
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "prepared_at": now.isoformat(),
        "replay": {"available": False, "reason": reason, "sources": sources},
        "tables": [],
    }
    staging = Path(tempfile.mkdtemp(prefix=".p2-unavailable-", dir=prepared_dir.parent))
    staging_prepared = staging / "prepared"
    staging_prepared.mkdir()
    try:
        _write_json(staging_prepared / "transforms.json", manifest)
        _commit_generation(prepared_dir, index_path, staging_prepared, None)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return manifest


class SourceMutationError(RuntimeError):
    """A source changed while its verified snapshot was captured."""



def _source_path(root: Path, reference: str) -> Path:
    path = _owned_path(root, reference, "data/raw")
    if tuple(Path(reference).parts[:2]) != ("data", "raw"):
        raise UnsafeCasePathError(reference)
    return path


def _owned_directory(root: Path, reference: str) -> Path:
    path = _owned_path(root, reference, reference)
    path.mkdir(parents=True, exist_ok=True)
    return path


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

def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
