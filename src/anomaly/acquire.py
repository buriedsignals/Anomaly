from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from anomaly.case import resume_case
from anomaly.semantics import (
    FORMAT_BY_EXTENSION,
    UnsafeCasePathError,
    canonical_key,
    redact_credentials,
    validate_case_documents,
    validate_portable_component,
    validate_source_record,
)

_URI_PREFIXES = ("http://", "https://", "file://")


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
    root = Path(root).resolve()
    resume_case(root)
    sources, reserved_receipt_keys = validate_case_documents(root)
    validate_portable_component(source_id)
    requested_key = canonical_key(source_id)
    if requested_key in reserved_receipt_keys or any(
        canonical_key(item["source_id"]) == requested_key for item in sources
    ):
        raise UnsafeCasePathError("duplicate canonical source identity")
    source_path = _local_file(source)
    format_name = _format_of(source_path)
    if included is False and not (isinstance(reason, str) and reason.strip()):
        raise ValueError("reason is required when a source is not included")
    relative = _posix("data/raw", source_id, source_path.name)
    dest = _under_root(root, relative)
    receipt_rel = _posix(".anomaly/receipts", f"{source_id}.json")
    _under_root(root, receipt_rel)
    payload = source_path.read_bytes() if source_path.is_file() else None
    if payload is None:
        if included:
            raise FileNotFoundError(source_path)
        # The bytes were not available at registration time.  Keep a stable
        # non-content hash so the manifest remains schema-valid without
        # claiming that a payload was observed.
        unavailable_key = f"anomaly-unavailable-v1\0{source_id}\0{source_path.name}"
        digest = "sha256:" + hashlib.sha256(unavailable_key.encode("utf-8")).hexdigest()
    else:
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    record: dict[str, Any] = {
        "source_id": source_id,
        "path": relative,
        "content_hash": digest,
        "format": format_name,
        "acquired_at": now.isoformat(),
        "license": redact_credentials(license),
        "sensitivity": redact_credentials(sensitivity),
        "redistribution": redact_credentials(redistribution),
        "reacquisition": redact_credentials(reacquisition),
        "included": included,
    }
    if included is False:
        record["reason"] = redact_credentials(reason)
        if payload is None:
            record["availability"] = "unavailable"
    persisted = record
    validate_source_record(persisted)
    if included:
        assert payload is not None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        _write_json(root, receipt_rel, persisted)
    _write_json(root, "data/sources.json", [*sources, persisted])
    return persisted


def _local_file(source: Path | str) -> Path:
    text = source if isinstance(source, str) else source.as_posix()
    lowered = text.lstrip().lower()
    if any(lowered.startswith(prefix) for prefix in _URI_PREFIXES):
        raise UnsafeCasePathError(text)
    path = Path(source)
    validate_portable_component(path.name)
    if path.is_symlink():
        raise UnsafeCasePathError(str(path))
    return path


def _format_of(source: Path) -> str:
    format_name = FORMAT_BY_EXTENSION.get(source.suffix.lower())
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



def _write_json(root: Path, relative: str, payload: object) -> None:
    path = _under_root(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
