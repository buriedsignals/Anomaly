from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from anomaly.case import CaseNotFoundError, UnsafeCasePathError, resume_case

_FORMATS = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".parquet": "parquet",
    ".xml": "xml",
}
_URI_PREFIXES = ("http://", "https://", "file://")
_CREDENTIAL = re.compile(r"sk_live_[A-Za-z0-9]+")


class UnsupportedLocalSourceError(Exception):
    pass


def register_local_source(
    root: Path,
    source: Path | str,
    *,
    source_id: str,
    now: datetime,
    license: str,
    sensitivity: str,
    redistribution: str,
    reacquisition: str,
    included: bool,
    reason: str | None = None,
) -> dict[str, Any]:
    resume_case(Path(root))
    source_path = _local_file(source)
    format_name = _format_of(source_path)
    if not included and not (isinstance(reason, str) and reason.strip()):
        raise ValueError("reason is required when a source is not included")
    _reject_unsafe_id(source_id)
    relative = _posix("data/raw", source_id, source_path.name)
    dest = _under_root(root, relative)
    receipt_rel = _posix(".anomaly/receipts", f"{source_id}.json")
    _under_root(root, receipt_rel)
    payload = source_path.read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    record: dict[str, Any] = {
        "source_id": source_id,
        "path": relative,
        "content_hash": digest,
        "format": format_name,
        "acquired_at": now.isoformat(),
        "license": license,
        "sensitivity": sensitivity,
        "redistribution": redistribution,
        "reacquisition": reacquisition,
        "included": included,
    }
    if not included:
        record["reason"] = reason
    persisted = _redact(record)
    if included:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        _write_json(root, receipt_rel, persisted)
    sources = _read_json(root, "data/sources.json")
    if not isinstance(sources, list):
        raise CaseNotFoundError(str(root))
    _write_json(root, "data/sources.json", [*sources, persisted])
    return persisted


def _local_file(source: Path | str) -> Path:
    text = source if isinstance(source, str) else source.as_posix()
    lowered = text.lstrip().lower()
    if any(lowered.startswith(prefix) for prefix in _URI_PREFIXES):
        raise UnsafeCasePathError(text)
    path = Path(source)
    if path.is_symlink():
        raise UnsafeCasePathError(str(path))
    return path


def _format_of(source: Path) -> str:
    format_name = _FORMATS.get(source.suffix.lower())
    if format_name is None:
        raise UnsupportedLocalSourceError(source.suffix)
    return format_name


def _posix(*parts: str) -> str:
    return "/".join(parts)


def _under_root(root: Path, relative: str) -> Path:
    base = Path(root).resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise UnsafeCasePathError(relative)
    return candidate


def _reject_unsafe_id(source_id: str) -> None:
    path = Path(source_id)
    if path.is_absolute() or ".." in path.parts:
        raise UnsafeCasePathError(source_id)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _CREDENTIAL.sub("[redacted]", value)
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _read_json(root: Path, relative: str) -> Any:
    return json.loads(_under_root(root, relative).read_text(encoding="utf-8"))


def _write_json(root: Path, relative: str, payload: object) -> None:
    path = _under_root(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
