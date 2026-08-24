from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
except ImportError:  # PyYAML is optional; use the restricted parser below.
    _yaml = None

import duckdb
import pyarrow as pa
import pyarrow.parquet as parquet

from anomaly.events import phase_event
from anomaly.semantics import UnsafeCasePathError, redact_credentials, validate_case_documents

_BUILTIN_IDS = (
    "categorical.rare_levels",
    "numeric.level_shift",
    "numeric.zscore_outliers",
    "table.duplicate_rows",
    "table.missingness_clusters",
    "temporal.coverage_gaps",
)
_TABLE_ID = re.compile(r"tbl_[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*\Z")
_FORBIDDEN_WORDS = re.compile(
    r"\b(?:CREATE|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|ATTACH|DETACH|COPY|INSTALL|LOAD|EXPORT|IMPORT|CALL|PRAGMA|SET|RESET)\b",
    re.IGNORECASE,
)
_EXTERNAL_READERS = re.compile(
    r"\b(?:query|query_table|json_execute_serialized_sql|sqlite_query|read_[A-Za-z0-9_]+|"
    r"(?:parquet|delta|iceberg|sqlite|postgres|mysql|arrow)_scan|glob|http_get|load_extension)\s*\(",
    re.IGNORECASE,
)
_IMPLICIT_FILE_RELATION = re.compile(
    r"""(?is)\b(?:FROM|JOIN)\s*(?:E?'[^']*'|\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$|`[^`]*`|"(?:[^"]*(?:[/\\]|\.csv\b|\.tsv\b|\.json\b|\.ndjson\b|\.parquet\b|\.duckdb\b|\.db\b)[^"]*)")"""
)
_SENSITIVE_OUTPUT_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|authorization|credential|password|passwd|secret|token|private[_-]?key)",
    re.IGNORECASE,
)


class DetectorError(RuntimeError):
    """A detector request or execution crossed a trusted boundary."""
def _detector_root() -> Path:
    return Path(__file__).resolve().parents[2] / "detectors"

def package_implementation_hash(package: Path) -> str:
    """Return the canonical registry hash over every file in a detector package.

    This is the same identity ``anomaly.detectors.registry`` publishes and
    ``anomaly.review._current_detector_identity`` verifies; run provenance must
    stamp it so strict replay of a real run can match the live package.
    """
    package = Path(package)
    if package.is_symlink() or not package.is_dir():
        raise DetectorError("detector package boundary is unsafe")
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise DetectorError("detector package contains a symlink")
        if path.is_file():
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _strip_yaml_comment(value: str) -> str:
    quoted = False
    quote = ""
    for index, char in enumerate(value):
        if char in "'\"" and (index == 0 or value[index - 1] != "\\"):
            if quoted and char == quote:
                quoted = False
            elif not quoted:
                quoted, quote = True, char
        elif char == "#" and not quoted and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _parse_scalar(value: str) -> Any:
    value = _strip_yaml_comment(value.strip())
    if not value:
        return None
    if value[0] in "'\"" and value[-1:] == value[0]:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    folded = value.casefold()
    if folded in {"null", "~"}:
        return None
    if folded == "true":
        return True
    if folded == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_scalar(part) for part in _split_yaml_items(inner)]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        result: dict[str, Any] = {}
        if inner:
            for item in _split_yaml_items(inner):
                key, separator, val = item.partition(":")
                if not separator:
                    raise ValueError("invalid inline YAML mapping")
                result[str(_parse_scalar(key.strip()))] = _parse_scalar(val)
        return result
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+|\d+[eE][-+]?\d+)(?:[eE][-+]?\d+)?", value):
            return float(value)
    except ValueError:
        pass
    return value


def _split_yaml_items(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote = ""
    for index, char in enumerate(value):
        if char in "'\"" and (index == 0 or value[index - 1] != "\\"):
            if quote == char:
                quote = ""
            elif not quote:
                quote = char
        elif not quote:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == "," and depth == 0:
                items.append(value[start:index].strip())
                start = index + 1
    items.append(value[start:].strip())
    return items


def _parse_restricted_yaml(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise ValueError("tabs are not supported in metadata indentation")
        content = _strip_yaml_comment(raw_line).strip()
        if not content:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, content))

    def parse_block(position: int, indent: int) -> tuple[Any, int]:
        if position >= len(lines) or lines[position][0] < indent:
            return {}, position
        sequence = lines[position][1].startswith("- ")
        result: Any = [] if sequence else {}
        while position < len(lines) and lines[position][0] == indent:
            content = lines[position][1]
            is_item = content.startswith("- ")
            if is_item != sequence:
                raise ValueError("mixed YAML sequence and mapping")
            if sequence:
                item = content[2:].strip()
                position += 1
                if not item:
                    if position < len(lines) and lines[position][0] > indent:
                        value, position = parse_block(position, lines[position][0])
                    else:
                        value = None
                elif ":" in item and not item.startswith(("[", "{", "'", '"')):
                    key, _, raw_value = item.partition(":")
                    key = key.strip()
                    if not _IDENTIFIER.fullmatch(key):
                        raise ValueError("invalid YAML mapping key")
                    value_map: dict[str, Any] = {}
                    if raw_value.strip():
                        value_map[key] = _parse_scalar(raw_value)
                    elif position < len(lines) and lines[position][0] > indent:
                        value_map[key], position = parse_block(position, lines[position][0])
                    else:
                        value_map[key] = None
                    if position < len(lines) and lines[position][0] > indent:
                        nested, position = parse_block(position, lines[position][0])
                        if not isinstance(nested, dict):
                            raise ValueError("invalid YAML sequence mapping")
                        value_map.update(nested)
                    value = value_map
                else:
                    value = _parse_scalar(item)
                result.append(value)
            else:
                key, separator, raw_value = content.partition(":")
                key = key.strip()
                if not separator or not _IDENTIFIER.fullmatch(key):
                    raise ValueError("invalid YAML mapping")
                position += 1
                if raw_value.strip():
                    value = _parse_scalar(raw_value)
                elif position < len(lines) and lines[position][0] > indent:
                    value, position = parse_block(position, lines[position][0])
                else:
                    value = {}
                result[key] = value
        return result, position

    if not lines:
        return {}
    parsed, position = parse_block(0, lines[0][0])
    if position != len(lines):
        raise ValueError("invalid YAML indentation")
    return parsed


def _read_metadata(detector_id: str) -> dict[str, Any]:
    package = _detector_root().joinpath(*detector_id.split("."))
    path = package / "meta.yaml"
    if not path.is_file() or path.is_symlink():
        raise DetectorError(f"missing built-in metadata: {detector_id}")
    try:
        text = path.read_text(encoding="utf-8")
        values = _yaml.safe_load(text) if _yaml is not None else _parse_restricted_yaml(text)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise DetectorError(f"invalid detector metadata: {detector_id}") from error
    if not isinstance(values, dict):
        raise DetectorError(f"invalid detector metadata: {detector_id}")
    values = dict(values)
    parameters = values.get("parameters", {})
    if not isinstance(parameters, dict):
        raise DetectorError(f"invalid detector parameters: {detector_id}")
    values["parameters"] = parameters
    if values.get("id") != detector_id or values.get("query") != "query.sql":
        raise DetectorError(f"invalid built-in metadata: {detector_id}")
    if not isinstance(values.get("version"), str) or not values["version"]:
        raise DetectorError(f"invalid built-in metadata: {detector_id}")
    return values


def load_detector_metadata() -> list[dict[str, Any]]:
    """Load only the immutable, package-owned detector catalog."""
    metadata = [_read_metadata(detector_id) for detector_id in _BUILTIN_IDS]
    return sorted(metadata, key=lambda item: item["id"])


def _scan_sql(sql: str) -> tuple[str, list[str]]:
    if not isinstance(sql, str) or not sql.strip():
        raise DetectorError("rejected empty SQL")
    # Scan quoted strings/identifiers so semicolons cannot hide in an injected
    # quoted identifier. SQL comments are not part of the detector language.
    chars: list[str] = []
    quoted_identifiers: list[str] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        if char in "'\"`":
            quote = char
            index += 1
            value: list[str] = []
            closed = False
            while index < len(sql):
                current = sql[index]
                if current == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote:
                        value.append(quote)
                        index += 2
                        continue
                    closed = True
                    index += 1
                    break
                if current == ";" and quote in '"`':
                    raise DetectorError("rejected identifier injection")
                value.append(current)
                index += 1
            if not closed:
                raise DetectorError("rejected unterminated SQL quote")
            if quote in '"`':
                quoted_identifiers.append("".join(value))
            chars.append(" ")
            continue
        if char == ";":
            if sql[index + 1 :].strip():
                raise DetectorError("rejected multiple statements")
            chars.append(char)
            index += 1
            continue
        if char == "-" and index + 1 < len(sql) and sql[index + 1] == "-":
            raise DetectorError("rejected SQL comments")
        if char == "/" and index + 1 < len(sql) and sql[index + 1] == "*":
            raise DetectorError("rejected SQL comments")
        chars.append(char)
        index += 1
    return "".join(chars), quoted_identifiers


def validate_read_only_sql(sql: str) -> None:
    """Reject every statement outside the parameterized SELECT-only dialect."""
    normalized, quoted_identifiers = _scan_sql(sql)
    if _FORBIDDEN_WORDS.search(normalized):
        raise DetectorError("unsafe or mutating SQL rejected")
    # DuckDB treats quoted string literals in FROM/JOIN as file relations.
    # Keep double-quoted column/table identifiers, but reject every implicit
    # path-like relation and all single-quoted relations.
    if _IMPLICIT_FILE_RELATION.search(sql):
        raise DetectorError("external access SQL rejected")
    if _EXTERNAL_READERS.search(sql):
        raise DetectorError("external access SQL rejected")
    if any(";" in identifier or "\x00" in identifier for identifier in quoted_identifiers):
        raise DetectorError("rejected identifier injection")
    statement = normalized.strip()
    if not re.match(r"(?is)^(?:SELECT|WITH)\b", statement):
        raise DetectorError("only read-only SELECT statements are allowed")
    if "\x00" in statement:
        raise DetectorError("rejected NUL in SQL")
    # A detector query may use quoted table/column names, but never arbitrary
    # executable identifier interpolation. The only dynamic table marker is
    # substituted and validated by the trusted executor before this call.


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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DetectorError(f"invalid detector input: {path.name}") from error


def _validate_limits(limits: dict[str, Any] | None) -> dict[str, int]:
    supplied = dict(limits or {})
    defaults = {
        "memory_mb": 256,
        "timeout_seconds": 30,
        "threads": 1,
        "max_output_rows": 1000,
    }
    unknown = set(supplied) - set(defaults)
    if unknown:
        raise DetectorError(f"unknown execution limits: {sorted(unknown)}")
    result: dict[str, int] = {}
    for key, default in defaults.items():
        value = supplied.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DetectorError(f"invalid execution limit: {key}")
        result[key] = value
    return result


def _table_id(value: Any) -> str:
    if not isinstance(value, str) or _TABLE_ID.fullmatch(value) is None:
        raise DetectorError("invalid prepared table id")
    return value


def _prepared_tables(root: Path) -> list[dict[str, Any]]:
    manifest_path = _owned_path(root, "data/prepared/transforms.json", "data/prepared")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise DetectorError("invalid prepared transform manifest")
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not tables:
        raise DetectorError("prepared data has no tables")
    result: list[dict[str, Any]] = []
    for table in tables:
        if not isinstance(table, dict):
            raise DetectorError("invalid prepared table declaration")
        table_id = _table_id(table.get("table_id"))
        source_id = table.get("source_id")
        source = table.get("source")
        if not isinstance(source_id, str) or not source_id.strip() or not isinstance(source, dict):
            raise DetectorError("invalid prepared source declaration")
        source_hash = source.get("sha256")
        if not isinstance(source_hash, str) or _SHA256.fullmatch(source_hash) is None:
            raise DetectorError("invalid prepared source hash")
        prepared = table.get("prepared")
        if not isinstance(prepared, dict) or prepared.get("format") != "parquet":
            raise DetectorError("invalid prepared table artifact")
        prepared_path = _owned_path(root, prepared.get("path"), "data/prepared")
        if not prepared_path.is_file() or prepared_path.is_symlink():
            raise DetectorError("missing prepared table artifact")
        digest = prepared.get("sha256")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise DetectorError("invalid prepared table hash")
        actual = "sha256:" + hashlib.sha256(prepared_path.read_bytes()).hexdigest()
        if actual != digest:
            raise DetectorError("prepared table hash mismatch")
        result.append(
            {
                "table_id": table_id,
                "source_id": source_id,
                "source_hash": source_hash,
                "prepared_path": prepared["path"],
                "prepared_hash": digest,
                "path": prepared_path,
            }
        )
    return result


def _prepared_manifest_hash(root: Path) -> str:
    path = _owned_path(root, "data/prepared/transforms.json", "data/prepared")
    return _sha256_bytes(path.read_bytes())


def _included_source_hashes(root: Path) -> dict[str, str]:
    try:
        records, _ = validate_case_documents(root)
    except Exception as error:
        raise DetectorError(f"invalid source registry: {error}") from error
    hashes = {
        record["source_id"]: record["content_hash"]
        for record in records
        if record.get("included") is True
    }
    if not hashes:
        raise DetectorError("detector execution requires included sources")
    return hashes


def _identifier(value: str) -> str:
    if _TABLE_ID.fullmatch(value) is None:
        raise DetectorError("invalid prepared identifier")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _redacted_preview(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redacted_preview(item)
            for key, item in value.items()
            if isinstance(key, str) and not _SENSITIVE_OUTPUT_KEY.search(key)
        }
    if isinstance(value, list):
        return [_redacted_preview(item) for item in value]
    return value


def _run_query(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any],
    timeout_seconds: int,
    max_output_rows: int,
) -> list[dict[str, Any]]:
    timer = threading.Timer(timeout_seconds, connection.interrupt)
    timer.daemon = True
    timer.start()
    try:
        cursor = connection.execute(query, parameters)
        columns = [item[0] for item in cursor.description or []]
        rows = cursor.fetchmany(max_output_rows)
        return [dict(zip(columns, row, strict=True)) for row in rows]
    except Exception as error:
        if "interrupt" in str(error).casefold() or "cancel" in str(error).casefold():
            raise DetectorError("detector query timed out") from error
        raise DetectorError(f"detector query rejected: {error}") from error
    finally:
        timer.cancel()


def _json_bytes(payload: Any) -> bytes:
    public = redact_credentials(_json_safe(payload))
    return (
        json.dumps(public, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(_json_bytes(payload))


def _write_immutable_json(path: Path, payload: Any) -> None:
    raw = _json_bytes(payload)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise DetectorError("detector snapshot identity collision")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _canonical_plan_hash(plan: dict[str, Any]) -> str:
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_gate_a(root: Path, requested: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Require an intact, hash-bound Gate A receipt before detector execution."""
    try:
        plan = json.loads(
            _owned_path(root, "detectors/plan.json", "detectors").read_text(encoding="utf-8")
        )
        receipt = json.loads(
            _owned_path(root, ".anomaly/receipts/gate-a.json", ".anomaly/receipts").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError, UnsafeCasePathError) as error:
        raise DetectorError("Gate A approval required: detector plan or receipt is missing") from error
    if not isinstance(plan, dict) or not isinstance(receipt, dict):
        raise DetectorError("Gate A approval required: invalid plan or receipt")
    approved = plan.get("approved")
    recommended = plan.get("recommended")
    if (
        set(plan) != {"recommended", "approved", "parameters", "reasons", "blocked"}
        or not isinstance(recommended, list)
        or not isinstance(approved, list)
        or any(not isinstance(item, str) for item in recommended + approved)
        or len(approved) > 10
        or len(set(approved)) != len(approved)
        or receipt.get("kind") != "user-approval"
        or receipt.get("gate") != "A"
        or receipt.get("plan_identity") != "detectors/plan.json"
        or receipt.get("plan_id") != "detectors/plan.json"
        or receipt.get("plan_hash") != _canonical_plan_hash(plan)
        or receipt.get("recommended") != recommended
        or receipt.get("approved") != approved
        or not isinstance(receipt.get("approved_by"), str)
        or not receipt["approved_by"].strip()
        or not isinstance(receipt.get("approved_at"), str)
    ):
        raise DetectorError("Gate A approval required before detector execution")
    if len(set(requested)) != len(requested):
        raise DetectorError("duplicate detector ids are not allowed")
    not_approved = [detector_id for detector_id in requested if detector_id not in approved]
    if not_approved:
        raise DetectorError(f"detector is not approved at Gate A: {not_approved[0]}")
    reasons = plan.get("reasons")
    if not isinstance(reasons, dict):
        raise DetectorError("Gate A approval required: invalid detector scopes")
    scopes: dict[str, tuple[str, ...]] = {}
    for detector_id in requested:
        reason = reasons.get(detector_id)
        table_ids = reason.get("table_ids") if isinstance(reason, dict) else None
        if (
            not isinstance(table_ids, list)
            or not table_ids
            or any(not isinstance(table_id, str) or _TABLE_ID.fullmatch(table_id) is None for table_id in table_ids)
            or len(set(table_ids)) != len(table_ids)
        ):
            raise DetectorError(f"Gate A approval required: invalid table scope for {detector_id}")
        scopes[detector_id] = tuple(table_ids)
    return scopes


@phase_event("P4", "execute_detectors")
def execute_detectors(
    root: Path,
    detector_ids: tuple[str, ...] | list[str],
    *,
    now: datetime,
    limits: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute trusted built-ins against the prepared read-only index."""
    root = Path(root)
    if not root.is_dir():
        raise DetectorError("case root is not a directory")
    metadata = {item["id"]: item for item in load_detector_metadata()}
    requested = tuple(detector_ids)
    if not requested:
        raise DetectorError("no detectors requested")
    unknown = [item for item in requested if item not in metadata]
    if unknown:
        raise DetectorError(f"unknown detector: {unknown[0]}")
    scopes = _require_gate_a(root, requested)
    execution_limits = _validate_limits(limits)
    source_hashes = _included_source_hashes(root)
    tables = _prepared_tables(root)
    tables_by_id = {table["table_id"]: table for table in tables}
    for detector_id, table_ids in scopes.items():
        if any(table_id not in tables_by_id for table_id in table_ids):
            raise DetectorError(f"approved table scope is not prepared for {detector_id}")
        for table_id in table_ids:
            table = tables_by_id[table_id]
            if table["source_hash"] not in source_hashes.values():
                raise DetectorError(f"prepared source is not registered for {detector_id}")
    index = _owned_path(root, "data/index.duckdb", "data")
    if not index.is_file() or index.is_symlink():
        raise DetectorError("missing DuckDB index")
    index_before = hashlib.sha256(index.read_bytes()).digest()
    index_hash = "sha256:" + index_before.hex()
    runs_root = _owned_path(root, "evidence/runs", "evidence/runs")
    runs_root.mkdir(parents=True, exist_ok=True)
    signals_path = _owned_path(root, "evidence/signals.jsonl", "evidence")
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    used_root = _owned_path(root, "detectors/used", "detectors/used")
    used_root.mkdir(parents=True, exist_ok=True)
    for path in used_root.rglob("*.py"):
        if path.is_file() and not path.is_symlink():
            path.unlink()

    results: list[dict[str, Any]] = []
    for detector_id in requested:
        meta = metadata[detector_id]
        detector_tables = [tables_by_id[table_id] for table_id in scopes[detector_id]]
        package = _detector_root().joinpath(*detector_id.split("."))
        query_path = package / str(meta["query"])
        query_bytes = query_path.read_bytes()
        query_template = query_bytes.decode("utf-8")
        rows: list[dict[str, Any]] = []
        with duckdb.connect(str(index), read_only=True) as connection:
            connection.execute("PRAGMA enable_external_access=false")
            connection.execute(f"PRAGMA memory_limit='{execution_limits['memory_mb']}MB'")
            connection.execute(f"PRAGMA threads={execution_limits['threads']}")
            for table in detector_tables:
                query = query_template.replace("{{table_id}}", _identifier(table["table_id"]))
                validate_read_only_sql(query)
                parameters = list(meta.get("parameters", {}).values())
                for result in _run_query(
                    connection,
                    query,
                    parameters,
                    execution_limits["timeout_seconds"],
                    execution_limits["max_output_rows"],
                ):
                    candidate_id = str(result.get("candidate_id", "candidate"))
                    signal = {
                        **result,
                        "detector_id": detector_id,
                        "table_id": table["table_id"],
                        "source_hash": table["source_hash"],
                        "evidence_refs": [
                            {
                                "source_id": table["source_id"],
                                "table_id": table["table_id"],
                                "candidate_id": result.get("candidate_id"),
                            }
                        ],
                        "status": "lead",
                        "redacted": True,
                        "preview": _redacted_preview(_json_safe(result)),
                        "statement": f"{result.get('category', 'detector')} lead for {candidate_id}",
                        "rank": len(rows) + 1,
                        "severity": result.get("severity", "medium"),
                    }
                    candidate_id = str(signal.get("candidate_id", "candidate"))
                    signal_key = f"{detector_id}:{table['table_id']}:{candidate_id}"
                    signal["signal_id"] = "signal-" + hashlib.sha256(signal_key.encode("utf-8")).hexdigest()[:24]
                    rows.append(redact_credentials(_json_safe(signal)))
        implementation_hash = package_implementation_hash(package)
        stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{stamp}-{detector_id.replace('.', '_')}-{implementation_hash[7:19]}"
        run_dir = runs_root / run_id
        run_dir.mkdir()
        for row in rows:
            row["run_id"] = run_dir.name
            row["detector_hash"] = implementation_hash
        output_path = run_dir / "signals.parquet"
        if rows:
            parquet.write_table(pa.Table.from_pylist(rows), output_path, compression="zstd")
        else:
            parquet.write_table(pa.table({"status": pa.array([], type=pa.string())}), output_path, compression="zstd")
        _write_json(run_dir / "preview.json", rows)
        snapshot = redact_credentials(
            _json_safe(
                {
                    "schema_version": 1,
                    "metadata": meta,
                    "implementation_hash": implementation_hash,
                    "parameters": meta.get("parameters", {}),
                    "version": meta["version"],
                }
            )
        )
        snapshot_hash = _canonical_plan_hash(snapshot)
        snapshot_name = (
            f"{detector_id.replace('.', '__')}__"
            f"{snapshot_hash.removeprefix('sha256:')}.json"
        )
        snapshot_path = used_root / snapshot_name
        _write_immutable_json(snapshot_path, snapshot)
        provenance = {
            "schema_version": 2,
            "run_id": run_dir.name,
            "detector_version": meta["version"],
            "detector_id": detector_id,
            "detector_snapshot": f"detectors/used/{snapshot_name}",
            "detector_snapshot_hash": snapshot_hash,
            "table_ids": [table["table_id"] for table in detector_tables],
            "prepared_manifest_hash": _prepared_manifest_hash(root),
            "prepared_tables": {
                table["table_id"]: {
                    "path": table["prepared_path"],
                    "hash": table["prepared_hash"],
                }
                for table in detector_tables
            },
            "index_hash": index_hash,
            "table_sources": {
                table["table_id"]: {
                    "source_id": table["source_id"],
                    "source_hash": table["source_hash"],
                }
                for table in detector_tables
            },
            "source_hashes": sorted({table["source_hash"] for table in detector_tables}),
            "detector_hash": implementation_hash,
            "query_hash": _sha256_bytes(query_bytes),
            "preview_hash": _sha256_bytes((run_dir / "preview.json").read_bytes()),
            "output_hash": _sha256_bytes(output_path.read_bytes()),
            "executed_at": now.isoformat(),
            "limits": execution_limits,
            "read_only": True,
            "external_access": False,
        }
        _write_json(run_dir / "provenance.json", provenance)
        with signals_path.open("a", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(redact_credentials(_json_safe(row)), sort_keys=True) + "\n")
        results.extend(rows)
    if hashlib.sha256(index.read_bytes()).digest() != index_before:
        raise DetectorError("detector execution mutated DuckDB index")
    return results
