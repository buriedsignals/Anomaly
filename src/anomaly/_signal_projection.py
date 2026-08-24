from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import stat
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb

from anomaly.detectors import is_valid_snapshot_reference
from anomaly.semantics import (
    UnsafeCasePathError,
    sanitize_public_value,
    validate_portable_component,
)

class SignalSearchError(RuntimeError):
    """The signal projection or query contract is invalid."""


class StaleSignalProjectionError(SignalSearchError):
    """The derived projection no longer matches its canonical inputs."""


class _PrivateProjection:
    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        temporary_directory: tempfile.TemporaryDirectory[str],
    ) -> None:
        self._connection = connection
        self._temporary_directory = temporary_directory

    def execute(
        self, query: str, parameters: list[str]
    ) -> duckdb.DuckDBPyConnection:
        return self._connection.execute(query, parameters)

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            self._temporary_directory.cleanup()


class _PinnedInput:
    def __init__(self, root: Path, relative: str, descriptor: int) -> None:
        self._root = root
        self._relative = relative
        self._descriptor = descriptor

    def read_bytes(self) -> bytes:
        descriptor = self._descriptor
        self._descriptor = -1
        try:
            before = os.fstat(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read()
            after = os.fstat(descriptor)
            if (
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or not _input_still_pinned(
                    self._root, self._relative, descriptor
                )
            ):
                raise SignalSearchError(
                    f"unsafe projection input changed after validation: {self._relative}"
                )
            return raw
        finally:
            os.close(descriptor)

    def __del__(self) -> None:
        if self._descriptor >= 0:
            os.close(self._descriptor)


_SCHEMA_VERSION = 1
_SIGNAL_PATH = "evidence/signals.jsonl"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TABLE_ID = re.compile(r"tbl_[0-9a-f]{64}\Z")
_DETECTOR_ID = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\Z")
_DETECTOR_SNAPSHOT = re.compile(
    r"[A-Za-z0-9_]+(?:__[A-Za-z0-9_]+)+(?:__[0-9a-f]{64})?\.json\Z"
)
_PUBLIC_SIGNAL_FIELDS = (
    "signal_id",
    "rank",
    "status",
    "category",
    "severity",
    "confidence",
    "statement",
    "warnings",
    "redacted",
    "preview",
    "evidence_refs",
    "calculation",
    "source_hash",
    "detector_hash",
    "run_id",
    "detector_id",
    "table_id",
)
_METADATA_FIELDS = (
    "title",
    "description",
    "group",
    "signal_category",
    "severity",
    "assumptions",
    "false_positives",
)


def build_projection(root: Path) -> dict[str, Any]:
    base = _case_root(root)
    rows, inputs = _read_projection_inputs(base)
    identity = _input_identity(inputs)
    search_root = _prepare_search_root(base)
    search_descriptor = _pin_search_root(base, search_root)
    stage_name = f".build-{secrets.token_hex(16)}"
    stage_descriptor = -1
    try:
        _validate_owned_artifact(search_descriptor, "signals.duckdb")
        _validate_owned_artifact(search_descriptor, "signals-manifest.json")
        os.mkdir(stage_name, mode=0o700, dir_fd=search_descriptor)
        stage_descriptor = os.open(
            stage_name, _directory_open_flags(), dir_fd=search_descriptor
        )
        projection_bytes = _build_private_projection(rows)
        _write_owned_bytes(stage_descriptor, "signals.duckdb", projection_bytes)
        projection_hash = _sha256(projection_bytes)
        manifest = {
            "schema_version": _SCHEMA_VERSION,
            "projection_identity": identity,
            "projection_hash": projection_hash,
            "inputs": inputs,
            "signal_count": len(rows),
        }
        _write_owned_bytes(
            stage_descriptor,
            "signals-manifest.json",
            (_json(manifest, indent=2) + "\n").encode("utf-8"),
        )
        if not _directory_still_pinned(search_root, search_descriptor):
            raise SignalSearchError("unsafe derived search boundary changed")
        os.replace(
            "signals.duckdb",
            "signals.duckdb",
            src_dir_fd=stage_descriptor,
            dst_dir_fd=search_descriptor,
        )
        os.replace(
            "signals-manifest.json",
            "signals-manifest.json",
            src_dir_fd=stage_descriptor,
            dst_dir_fd=search_descriptor,
        )
        return manifest
    except (OSError, UnicodeError, duckdb.Error, ValueError) as error:
        if isinstance(error, SignalSearchError):
            raise
        raise SignalSearchError("could not build signal search projection") from error
    finally:
        if stage_descriptor >= 0:
            _remove_owned_file(stage_descriptor, "signals.duckdb")
            _remove_owned_file(stage_descriptor, "signals-manifest.json")
            os.close(stage_descriptor)
            try:
                os.rmdir(stage_name, dir_fd=search_descriptor)
            except OSError:
                pass
        os.close(search_descriptor)


def verified_projection(root: Path) -> tuple[_PrivateProjection, dict[str, Any]]:
    base = _case_root(root)
    search_root = _existing_search_root(base)
    search_descriptor = _pin_search_root(base, search_root)
    projection: _PrivateProjection | None = None
    try:
        manifest = _decode_json(
            _read_owned_bytes(search_descriptor, "signals-manifest.json"),
            "signal search manifest",
        )
        if not isinstance(manifest, dict) or set(manifest) != {
            "schema_version",
            "projection_identity",
            "projection_hash",
            "inputs",
            "signal_count",
        }:
            raise SignalSearchError("invalid signal search manifest")
        if manifest["schema_version"] != _SCHEMA_VERSION:
            raise SignalSearchError("unsupported signal search projection")
        inputs = manifest["inputs"]
        if not isinstance(inputs, dict) or not inputs or not all(
            isinstance(path, str)
            and _is_projection_input(path)
            and isinstance(digest, str)
            and _SHA256.fullmatch(digest)
            for path, digest in inputs.items()
        ):
            raise SignalSearchError("invalid signal search input manifest")
        if list(inputs) != sorted(inputs) or _SIGNAL_PATH not in inputs:
            raise SignalSearchError("invalid signal search input ordering")
        if manifest["projection_identity"] != _input_identity(inputs):
            raise SignalSearchError("invalid signal search projection identity")
        for relative, expected_hash in inputs.items():
            current_hash = _sha256(_safe_input_file(base, relative).read_bytes())
            if current_hash != expected_hash:
                raise StaleSignalProjectionError(
                    f"stale signal search projection input: {relative}"
                )
        projection_bytes = _read_owned_bytes(
            search_descriptor, "signals.duckdb"
        )
        if _sha256(projection_bytes) != manifest["projection_hash"]:
            raise SignalSearchError("signal search projection is corrupt")
        if not isinstance(manifest["signal_count"], int) or manifest["signal_count"] < 0:
            raise SignalSearchError("invalid signal count in search manifest")
        projection = _open_private_projection(projection_bytes)
        return projection, manifest
    except (OSError, duckdb.Error, SignalSearchError) as error:
        if projection is not None:
            projection.close()
        if isinstance(error, SignalSearchError):
            raise
        raise SignalSearchError("could not verify signal search projection") from error
    finally:
        os.close(search_descriptor)


def read_rows(
    projection: _PrivateProjection,
    filter_columns: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    where = " AND ".join(f"{column} = ?" for column, _ in filter_columns)
    sql = "SELECT payload_json, search_fields_json FROM signals"
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY signal_id, run_id"
    try:
        return projection.execute(
            sql, [value for _, value in filter_columns]
        ).fetchall()
    except duckdb.Error as error:
        raise SignalSearchError("could not read signal search projection") from error


def _read_projection_inputs(
    root: Path,
) -> tuple[list[tuple[Any, ...]], dict[str, str]]:
    signal_bytes = _safe_input_file(root, _SIGNAL_PATH).read_bytes()
    signals = _read_json_lines(signal_bytes)
    inputs: dict[str, str] = {_SIGNAL_PATH: _sha256(signal_bytes)}
    seen: set[tuple[str, str]] = set()
    rows: list[tuple[Any, ...]] = []
    cache: dict[str, Any] = {}
    for raw in signals:
        signal = _validate_signal(raw, seen)
        run_relative = f"evidence/runs/{signal['run_id']}/provenance.json"
        provenance = _cached_json(root, run_relative, cache, inputs)
        detector_relative = _snapshot_relative(provenance, signal)
        snapshot = _cached_json(root, detector_relative, cache, inputs)
        rows.append(_projection_row(signal, provenance, snapshot, detector_relative))
    return rows, dict(sorted(inputs.items()))

def _snapshot_relative(provenance: Any, signal: dict[str, Any]) -> str:
    if not isinstance(provenance, dict) or provenance.get("schema_version") != 2:
        raise SignalSearchError("signal requires schema-v2 run provenance")
    relative = provenance.get("detector_snapshot")
    snapshot_hash = provenance.get("detector_snapshot_hash")
    if (
        not isinstance(relative, str)
        or not _is_projection_input(relative)
        or not isinstance(snapshot_hash, str)
        or _SHA256.fullmatch(snapshot_hash) is None
    ):
        raise SignalSearchError("invalid detector snapshot provenance")
    if not is_valid_snapshot_reference(
        signal["detector_id"],
        relative,
        snapshot_hash,
        allow_legacy=True,
    ):
        raise SignalSearchError("run refers to an unsafe detector snapshot")
    return relative


def _projection_row(
    signal: dict[str, Any],
    provenance: Any,
    snapshot: Any,
    detector_relative: str,
) -> tuple[Any, ...]:
    if (
        not isinstance(provenance, dict)
        or provenance.get("schema_version") != 2
        or any(
            provenance.get(field) != signal[field]
            for field in ("run_id", "detector_id", "detector_hash")
        )
    ):
        raise SignalSearchError("signal does not match its schema-v2 run provenance")
    if provenance.get("detector_snapshot") != detector_relative:
        raise SignalSearchError("run refers to an unsafe detector snapshot")
    snapshot_hash = provenance.get("detector_snapshot_hash")
    if (
        not isinstance(snapshot_hash, str)
        or _SHA256.fullmatch(snapshot_hash) is None
        or snapshot_hash != _sha256(_json(snapshot).encode("utf-8"))
    ):
        raise SignalSearchError("detector snapshot hash does not match provenance")
    table_id = signal["table_id"]
    if table_id not in provenance.get("table_ids", []):
        raise SignalSearchError("signal table is absent from run provenance")
    table_sources = provenance.get("table_sources")
    source = table_sources.get(table_id) if isinstance(table_sources, dict) else None
    if not isinstance(source, dict) or source.get("source_hash") != signal["source_hash"]:
        raise SignalSearchError("signal source does not match run provenance")
    source_id = _portable(source.get("source_id"), "source identity")
    _validate_evidence_refs(signal["evidence_refs"], table_sources)
    executed_at = _executed_at(provenance.get("executed_at"))
    metadata = _validated_metadata(snapshot, signal)
    if metadata["signal_category"] != signal["category"]:
        raise SignalSearchError("signal category does not match detector metadata")
    public_signal = sanitize_public_value(
        {field: signal[field] for field in _PUBLIC_SIGNAL_FIELDS if field in signal}
    )
    public_metadata = sanitize_public_value(
        {field: metadata[field] for field in _METADATA_FIELDS}
    )
    payload = {
        **public_signal,
        "signal_ref": {
            "path": _SIGNAL_PATH,
            "signal_id": signal["signal_id"],
            "run_id": signal["run_id"],
        },
        "source_id": source_id,
        "date": executed_at.date().isoformat(),
        "review_state": "unreviewed",
        "detector": public_metadata,
    }
    fields = _search_fields(public_signal, public_metadata)
    return (
        signal["signal_id"],
        signal["detector_id"],
        public_metadata["group"],
        signal["category"],
        signal["severity"],
        source_id,
        table_id,
        signal["run_id"],
        executed_at.date().isoformat(),
        "unreviewed",
        _json(payload),
        _json(fields),
    )


def _validate_signal(
    raw: Any, seen: set[tuple[str, str]]
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SignalSearchError("signal JSONL rows must be objects")
    required = {
        "signal_id",
        "status",
        "category",
        "severity",
        "statement",
        "redacted",
        "preview",
        "evidence_refs",
        "source_hash",
        "detector_hash",
        "run_id",
        "detector_id",
        "table_id",
    }
    if not required.issubset(raw):
        raise SignalSearchError("signal is missing required public fields")
    signal_id = _text(raw["signal_id"], "signal identity")
    run_id = _portable(raw["run_id"], "run identity")
    identity = (signal_id, run_id)
    if identity in seen:
        raise SignalSearchError(
            f"duplicate signal run identity: {signal_id}/{run_id}"
        )
    seen.add(identity)
    if not isinstance(raw["detector_id"], str) or not _DETECTOR_ID.fullmatch(raw["detector_id"]):
        raise SignalSearchError("invalid detector identity")
    if not isinstance(raw["table_id"], str) or not _TABLE_ID.fullmatch(raw["table_id"]):
        raise SignalSearchError("invalid table identity")
    for field in ("source_hash", "detector_hash"):
        if not isinstance(raw[field], str) or not _SHA256.fullmatch(raw[field]):
            raise SignalSearchError(f"invalid signal {field}")
    if raw["status"] != "lead" or raw["redacted"] is not True:
        raise SignalSearchError("search projection accepts only redacted leads")
    for field in ("category", "severity", "statement"):
        _text(raw[field], f"signal {field}")
    if not isinstance(raw["preview"], (dict, list)):
        raise SignalSearchError("invalid redacted preview")
    if not isinstance(raw["evidence_refs"], list) or not raw["evidence_refs"]:
        raise SignalSearchError("signal requires canonical evidence references")
    warnings = raw.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise SignalSearchError("invalid signal warnings")
    confidence = raw.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
    ):
        raise SignalSearchError("invalid signal confidence")
    _json(sanitize_public_value(raw))
    return raw


def _validate_evidence_refs(refs: list[Any], table_sources: dict[str, Any]) -> None:
    for ref in refs:
        if not isinstance(ref, dict):
            raise SignalSearchError("invalid canonical evidence reference")
        table_id = ref.get("table_id")
        source_id = ref.get("source_id")
        binding = table_sources.get(table_id) if isinstance(table_id, str) else None
        if not isinstance(binding, dict) or binding.get("source_id") != source_id:
            raise SignalSearchError("evidence reference does not match run provenance")
        _portable(source_id, "evidence source identity")


def _validated_metadata(snapshot: Any, signal: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("implementation_hash") != signal["detector_hash"]:
        raise SignalSearchError("detector snapshot does not match signal")
    metadata = snapshot.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("id") != signal["detector_id"]:
        raise SignalSearchError("detector metadata identity mismatch")
    for field in ("title", "description", "group", "signal_category", "severity"):
        _text(metadata.get(field), f"detector metadata {field}")
    for field in ("assumptions", "false_positives"):
        value = metadata.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SignalSearchError(f"invalid detector metadata {field}")
    return metadata


def _search_fields(
    signal: dict[str, Any], metadata: dict[str, Any]
) -> list[dict[str, str]]:
    fields = [{"field": "statement", "text": signal["statement"]}]
    fields.append({"field": "warnings", "text": " ".join(signal.get("warnings", []))})
    for field in ("title", "description", "assumptions", "false_positives"):
        value = metadata[field]
        text = " ".join(value) if isinstance(value, list) else value
        fields.append({"field": f"detector.{field}", "text": text})
    fields.extend(_flatten_preview(signal["preview"], "preview"))
    return fields


def _flatten_preview(value: Any, path: str) -> list[dict[str, str]]:
    if isinstance(value, dict):
        output: list[dict[str, str]] = []
        for key in sorted(value):
            output.extend(_flatten_preview(value[key], f"{path}.{key}"))
        return output
    if isinstance(value, list):
        return [{"field": path, "text": " ".join(_leaf_text(item) for item in value)}]
    return [{"field": path, "text": _leaf_text(value)}]


def _leaf_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_private_projection(rows: list[tuple[Any, ...]]) -> bytes:
    with tempfile.TemporaryDirectory(
        prefix="anomaly-signal-projection-"
    ) as temporary_directory:
        os.chmod(temporary_directory, 0o700)
        path = Path(temporary_directory) / "signals.duckdb"
        _write_projection(path, rows)
        return path.read_bytes()


def _write_projection(path: Path, rows: list[tuple[Any, ...]]) -> None:
    with duckdb.connect(str(path)) as connection:
        os.chmod(path, 0o600)
        connection.execute("PRAGMA enable_external_access=false")
        connection.execute(
            "CREATE TABLE signals ("
            "signal_id VARCHAR NOT NULL, detector_id VARCHAR NOT NULL, "
            "detector_group VARCHAR NOT NULL, category VARCHAR NOT NULL, "
            "severity VARCHAR NOT NULL, source_id VARCHAR NOT NULL, "
            "table_id VARCHAR NOT NULL, run_id VARCHAR NOT NULL, "
            "run_date VARCHAR NOT NULL, review_state VARCHAR NOT NULL, "
            "payload_json VARCHAR NOT NULL, search_fields_json VARCHAR NOT NULL, "
            "PRIMARY KEY (signal_id, run_id))"
        )
        if rows:
            connection.executemany(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        connection.execute("CHECKPOINT")


def _open_private_projection(raw: bytes) -> _PrivateProjection:
    temporary_directory = tempfile.TemporaryDirectory(
        prefix="anomaly-signal-projection-"
    )
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        os.chmod(temporary_directory.name, 0o700)
        path = Path(temporary_directory.name) / "signals.duckdb"
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
        connection = duckdb.connect(str(path), read_only=True)
        connection.execute("PRAGMA enable_external_access=false")
        os.unlink(path)
        return _PrivateProjection(connection, temporary_directory)
    except (OSError, duckdb.Error):
        if connection is not None:
            connection.close()
        temporary_directory.cleanup()
        raise


def _cached_json(
    root: Path,
    relative: str,
    cache: dict[str, Any],
    inputs: dict[str, str],
) -> Any:
    if relative not in cache:
        path = _safe_input_file(root, relative)
        raw = path.read_bytes()
        inputs[relative] = _sha256(raw)
        cache[relative] = _decode_json(raw, relative)
    return cache[relative]


def _read_json_lines(raw: bytes) -> list[Any]:
    try:
        text = raw.decode("utf-8")
        lines = text.splitlines()
        if any(not line.strip() for line in lines):
            raise SignalSearchError("invalid signal JSONL")
        return [json.loads(line) for line in lines]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SignalSearchError("invalid signal JSONL") from error


def _decode_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SignalSearchError(f"invalid JSON in {label}") from error


def _case_root(root: Path) -> Path:
    try:
        base = Path(root).resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as error:
        raise SignalSearchError("invalid case root") from error
    if not base.is_dir():
        raise SignalSearchError("invalid case root")
    return base


def _safe_input_file(root: Path, relative: str) -> _PinnedInput:
    pure = PurePosixPath(relative)
    if (
        not _is_projection_input(relative)
        or pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise SignalSearchError("unsafe projection input path")
    return _PinnedInput(root, relative, _open_input_descriptor(root, pure.parts))


def _open_input_descriptor(root: Path, parts: tuple[str, ...]) -> int:
    try:
        directory = os.open(root, _directory_open_flags())
    except OSError as error:
        raise SignalSearchError("unsafe case root") from error
    try:
        for part in parts[:-1]:
            child = os.open(part, _directory_open_flags(), dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], _file_open_flags(), dir_fd=directory)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise SignalSearchError("unsafe projection input is not a file")
        return descriptor
    except OSError as error:
        raise SignalSearchError("missing or unsafe projection input") from error
    finally:
        os.close(directory)


def _input_still_pinned(root: Path, relative: str, descriptor: int) -> bool:
    try:
        current = _open_input_descriptor(root, PurePosixPath(relative).parts)
    except SignalSearchError:
        return False
    try:
        return _same_object(os.fstat(descriptor), os.fstat(current))
    finally:
        os.close(current)


def _prepare_search_root(root: Path) -> Path:
    anomaly_root = root / ".anomaly"
    if anomaly_root.is_symlink() or (anomaly_root.exists() and not anomaly_root.is_dir()):
        raise SignalSearchError("unsafe derived search boundary")
    anomaly_root.mkdir(mode=0o700, exist_ok=True)
    search_root = anomaly_root / "search"
    if search_root.is_symlink() or (search_root.exists() and not search_root.is_dir()):
        raise SignalSearchError("unsafe derived search boundary")
    search_root.mkdir(mode=0o700, exist_ok=True)
    return search_root


def _existing_search_root(root: Path) -> Path:
    search_root = root / ".anomaly" / "search"
    if not search_root.is_dir() or search_root.is_symlink():
        raise SignalSearchError("signal search projection is missing or unsafe")
    return search_root


def _pin_search_root(root: Path, search_root: Path) -> int:
    descriptor = os.open(root, _directory_open_flags())
    try:
        for part in (".anomaly", "search"):
            child = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if not _directory_still_pinned(search_root, descriptor):
            raise SignalSearchError("unsafe derived search boundary changed")
        return descriptor
    except (OSError, SignalSearchError) as error:
        os.close(descriptor)
        if isinstance(error, SignalSearchError):
            raise
        raise SignalSearchError("unsafe derived search boundary") from error


def _directory_still_pinned(path: Path, descriptor: int) -> bool:
    try:
        current = os.open(path, _directory_open_flags())
    except OSError:
        return False
    try:
        return _same_object(os.fstat(descriptor), os.fstat(current))
    finally:
        os.close(current)


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _file_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def _validate_owned_artifact(directory: int, name: str) -> None:
    try:
        details = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(details.st_mode):
        raise SignalSearchError("unsafe derived search artifact")


def _read_owned_bytes(directory: int, name: str) -> bytes:
    try:
        descriptor = os.open(name, _file_open_flags(), dir_fd=directory)
    except OSError as error:
        raise SignalSearchError("missing or unsafe derived search artifact") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SignalSearchError("unsafe derived search artifact")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read()
        after = os.fstat(descriptor)
        if (
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise SignalSearchError("derived search artifact changed during read")
        return raw
    finally:
        os.close(descriptor)


def _write_owned_bytes(directory: int, name: str, raw: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(name, flags, 0o600, dir_fd=directory)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _remove_owned_file(directory: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory)
    except FileNotFoundError:
        pass


def _is_projection_input(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    if relative == _SIGNAL_PATH:
        return True
    if (
        len(parts) == 4
        and parts[:2] == ("evidence", "runs")
        and parts[3] == "provenance.json"
    ):
        try:
            validate_portable_component(parts[2])
        except UnsafeCasePathError:
            return False
        return True
    return (
        len(parts) == 3
        and parts[:2] == ("detectors", "used")
        and _DETECTOR_SNAPSHOT.fullmatch(parts[2]) is not None
    )


def _input_identity(inputs: dict[str, str]) -> str:
    return _sha256(_json(inputs).encode("utf-8"))


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _json(value: Any, *, indent: int | None = None) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
            separators=None if indent is not None else (",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise SignalSearchError("projection input is not valid public JSON") from error


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SignalSearchError(f"invalid {label}")
    return value


def _portable(value: Any, label: str) -> str:
    try:
        return validate_portable_component(value)
    except UnsafeCasePathError as error:
        raise SignalSearchError(f"invalid {label}") from error


def _executed_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise SignalSearchError("invalid run execution date")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SignalSearchError("invalid run execution date") from error
    if "T" not in value:
        raise SignalSearchError("invalid run execution date")
    return parsed
