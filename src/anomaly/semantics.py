from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping


class UnsafeCasePathError(Exception):
    pass


FORMAT_BY_EXTENSION = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".parquet": "parquet",
    ".xml": "xml",
}

_SOURCE_FIELDS: dict[str, type] = {
    "source_id": str,
    "path": str,
    "content_hash": str,
    "format": str,
    "acquired_at": str,
    "license": str,
    "sensitivity": str,
    "redistribution": str,
    "reacquisition": str,
    "included": bool,
}
_NON_SOURCE_RECEIPT_KINDS = frozenset(
    {"detector", "replay", "review", "user-approval", "charts", "viewer"}
)
_CASE_STRING_FIELDS = (
    "case_id",
    "title",
    "created_at",
    "updated_at",
    "status",
    "workflow_version",
)
_FORBIDDEN_COMPONENT_CHARS = frozenset('<>:"/\\|?*')
_WINDOWS_DEVICE = re.compile(
    r"(?:con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?\Z",
    re.IGNORECASE,
)
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ISO_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:\d{2})?\Z"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b((?:[a-z0-9]+[_-])*(?:api[_-]?key|access[_-]?key|"
    r"access[_-]?token|auth(?:entication)?|authorization|credential|password|"
    r"passwd|secret(?:[_-]access)?[_-]?key|secret|token|private[_-]?key)"
    r"(?:[_-][a-z0-9]+)*)\s*[:=]\s*(?:Bearer\s+)?[^,;\s]+"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_TOKEN_PREFIX = re.compile(
    r"\b(?:sk_live_|ghp_|github_pat_|xox[baprs]-|AKIA)[A-Za-z0-9_./+=-]{8,}"
)
_URL_USERINFO = re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^@\s/]+@")
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|auth(?:entication)?|authorization|"
    r"credential|password|passwd|secret|token|private[_-]?key)",
    re.IGNORECASE,
)


def canonical_key(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).casefold())


def validate_portable_component(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise UnsafeCasePathError(str(value))
    if unicodedata.normalize("NFC", value) != value:
        raise UnsafeCasePathError(value)
    if value in {".", ".."} or value.endswith((".", " ")):
        raise UnsafeCasePathError(value)
    if _DRIVE_PREFIX.match(value) or _WINDOWS_DEVICE.fullmatch(value):
        raise UnsafeCasePathError(value)
    if any(character in _FORBIDDEN_COMPONENT_CHARS for character in value):
        raise UnsafeCasePathError(value)
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise UnsafeCasePathError(value)
    return value


def reject_unsafe_recursive_paths(value: object) -> None:
    if isinstance(value, str):
        _reject_unsafe_path_value(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            reject_unsafe_recursive_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_unsafe_recursive_paths(item)


def redact_credentials(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {key: redact_credentials(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_credentials(item) for item in value]
    return value

def sanitize_public_value(value: Any) -> Any:
    """Recursively remove sensitive keys and redact credentials from strings."""
    return _sanitize_public_value(value)


def _sanitize_public_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return None
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for name, item in value.items():
            if not isinstance(name, str) or _SENSITIVE_KEY.search(name):
                continue
            output[name] = _sanitize_public_value(item, name)
        return output
    if isinstance(value, list):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, str):
        return str(redact_credentials(value))
    return value


def _redact_text(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        value,
    )
    value = _BEARER.sub("Bearer [redacted]", value)
    value = _TOKEN_PREFIX.sub("[redacted]", value)
    return _URL_USERINFO.sub(r"\1[redacted]@", value)


def validate_case_record(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UnsafeCasePathError("case.json must be a record")
    known_fields = {*_CASE_STRING_FIELDS, "derived_from"}
    for field, value in payload.items():
        if field not in known_fields:
            reject_unsafe_recursive_paths(value)
    for field in _CASE_STRING_FIELDS:
        if not isinstance(payload.get(field), str):
            raise UnsafeCasePathError(f"invalid case field: {field}")
    if "derived_from" not in payload:
        raise UnsafeCasePathError("missing case field: derived_from")
    derived_from = payload["derived_from"]
    if derived_from is not None and not isinstance(derived_from, (str, dict)):
        raise UnsafeCasePathError("invalid case field: derived_from")
    validate_portable_component(payload["case_id"])
    if isinstance(derived_from, str):
        validate_portable_component(derived_from)
        if canonical_key(payload["case_id"]) == canonical_key(derived_from):
            raise UnsafeCasePathError("case lineage identities must be distinct")
    elif isinstance(derived_from, dict):
        if set(derived_from) != {"case_id", "case_hash"} or not isinstance(derived_from["case_id"], str) or not isinstance(derived_from["case_hash"], str) or not _SHA256.fullmatch(derived_from["case_hash"]):
            raise UnsafeCasePathError("invalid case lineage")
        validate_portable_component(derived_from["case_id"])
        if canonical_key(payload["case_id"]) == canonical_key(derived_from["case_id"]):
            raise UnsafeCasePathError("case lineage identities must be distinct")
    _validate_timestamp(payload["created_at"], "created_at")
    _validate_timestamp(payload["updated_at"], "updated_at")
    return payload


def validate_source_record(record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise UnsafeCasePathError("source must be a record")
    reject_unsafe_recursive_paths(record)
    for field, expected in _SOURCE_FIELDS.items():
        if not isinstance(record.get(field), expected):
            raise UnsafeCasePathError(f"invalid source field: {field}")

    source_id = validate_portable_component(record["source_id"])
    path = record["path"]
    parts = path.split("/")
    if len(parts) != 4 or parts[:2] != ["data", "raw"] or parts[2] != source_id:
        raise UnsafeCasePathError(path)
    basename = validate_portable_component(parts[3])
    expected_format = FORMAT_BY_EXTENSION.get(PurePosixPath(basename).suffix.lower())
    if expected_format is None or record["format"] != expected_format:
        raise UnsafeCasePathError("source format does not match its path")
    if _SHA256.fullmatch(record["content_hash"]) is None:
        raise UnsafeCasePathError("invalid source content_hash")
    _validate_timestamp(record["acquired_at"], "acquired_at")
    if not record["included"]:
        reason = record.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise UnsafeCasePathError("excluded source requires a reason")
    elif "reason" in record and not isinstance(record["reason"], str):
        raise UnsafeCasePathError("invalid source reason")
    return record


def validate_sources(payload: object) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(payload, list):
        raise UnsafeCasePathError("data/sources.json must be a list")
    records: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    for item in payload:
        record = validate_source_record(item)
        key = canonical_key(record["source_id"])
        if key in by_key:
            raise UnsafeCasePathError("duplicate canonical source identity")
        records.append(record)
        by_key[key] = record
    return records, by_key


def validate_case_documents(
    root: Path,
) -> tuple[list[dict[str, Any]], frozenset[str]]:
    root = Path(root)
    sources_payload = _read_json(root / "data" / "sources.json")
    records, by_key = validate_sources(sources_payload)
    receipts_dir = root / ".anomaly" / "receipts"
    seen_source_keys: set[str] = set()
    reserved_receipt_keys: set[str] = set()
    if not receipts_dir.is_dir():
        raise UnsafeCasePathError("missing receipts directory")

    receipt_paths = sorted(
        path for path in receipts_dir.rglob("*") if path.is_file()
    )
    for receipt_path in receipt_paths:
        if receipt_path.suffix.lower() != ".json":
            raise UnsafeCasePathError(f"unrecognized receipt artifact: {receipt_path}")
        payload = _read_json(receipt_path)
        if not isinstance(payload, dict):
            raise UnsafeCasePathError("receipt must be a record")

        receipt_stem = validate_portable_component(receipt_path.stem)
        key = canonical_key(receipt_stem)
        reject_unsafe_recursive_paths(payload)
        if payload.get("kind") in _NON_SOURCE_RECEIPT_KINDS:
            reserved_receipt_keys.add(key)
            continue

        manifest = by_key.get(key)
        if manifest is None:
            raise UnsafeCasePathError("unrecognized receipt kind")
        if key in seen_source_keys:
            raise UnsafeCasePathError("duplicate canonical receipt identity")
        seen_source_keys.add(key)
        receipt = validate_source_record(payload)
        for field in sorted(manifest.keys() & receipt.keys()):
            if not _json_equal(manifest[field], receipt[field]):
                raise UnsafeCasePathError(f"receipt mismatch: {field}")

    for record in records:
        if (
            record["included"]
            and canonical_key(record["source_id"]) not in seen_source_keys
        ):
            raise UnsafeCasePathError("included source is missing its receipt")
    return records, frozenset(reserved_receipt_keys)


def _validate_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or _ISO_DATETIME.fullmatch(value) is None:
        raise UnsafeCasePathError(f"invalid timestamp: {field}")
    parsed_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(parsed_value)
    except ValueError as error:
        raise UnsafeCasePathError(f"invalid timestamp: {field}") from error


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if type(left) in (int, float) or type(right) in (int, float):
        return type(left) in (int, float) and type(right) in (int, float) and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    return type(left) is type(right) and left == right


def _reject_unsafe_path_value(value: str) -> None:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    segments = value.replace("\\", "/").split("/")
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or value.startswith(("/", "\\"))
        or ".." in segments
    ):
        raise UnsafeCasePathError(value)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UnsafeCasePathError(str(path)) from error
