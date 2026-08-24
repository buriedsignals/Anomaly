from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from anomaly.semantics import UnsafeCasePathError, validate_portable_component
from anomaly.state import WorkflowError

_PUBLIC_INPUTS = frozenset({"now", "sources", "gate_a", "gate_b"})
_SOURCE_INPUTS = frozenset(
    {
        "path",
        "source_id",
        "license",
        "sensitivity",
        "redistribution",
        "reacquisition",
        "included",
        "reason",
    }
)


def normalize_inputs(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("workflow inputs must be a mapping")
    supplied = dict(value)
    if any(not isinstance(key, str) for key in supplied):
        raise ValueError("workflow input names must be strings")
    unknown = sorted(set(supplied) - _PUBLIC_INPUTS)
    if unknown:
        raise ValueError(f"unknown workflow inputs: {', '.join(unknown)}")
    return supplied


def input_capabilities(inputs: Mapping[str, Any]) -> frozenset[str]:
    """Return only complete, phase-consumable input names."""
    capabilities: set[str] = set()
    if _is_input_time(inputs.get("now")):
        capabilities.add("now")
    if "sources" in inputs:
        try:
            source_requests(inputs["sources"])
        except ValueError:
            pass
        else:
            capabilities.add("sources")
    try:
        gate_a_input(inputs.get("gate_a"))
    except ValueError:
        pass
    else:
        capabilities.add("gate_a")
    try:
        gate_b_input(inputs.get("gate_b"))
    except ValueError:
        pass
    else:
        capabilities.add("gate_b")
    return frozenset(capabilities)


def registered_sources(root: Path, *, required: bool = True) -> list[dict[str, Any]]:
    value = read_case_json(root, "data/sources.json")
    valid = isinstance(value, list) and all(isinstance(item, dict) for item in value)
    if not valid or (required and not value):
        raise WorkflowError("at least one registered source is required")
    return value


def input_time(inputs: Mapping[str, Any]) -> datetime:
    value = inputs.get("now")
    if not _is_input_time(value):
        raise ValueError("now must be an explicit timezone-aware datetime")
    return value


def source_requests(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("sources must be a non-empty list")
    required = _SOURCE_INPUTS - {"reason"}
    requests: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("each source input must be a mapping")
        request = dict(item)
        if set(request) - _SOURCE_INPUTS or not required.issubset(request):
            raise ValueError("source input has missing or unknown fields")
        _validate_source_request(request)
        requests.append(request)
    return requests


def gate_a_input(value: Any) -> dict[str, Any]:
    return _gate_input(
        value,
        sequence="approved_ids",
        identity="approved_by",
        allow_empty=False,
        maximum=10,
        reject_separators=True,
    )


def gate_b_input(value: Any) -> dict[str, Any]:
    return _gate_input(
        value,
        sequence="accepted_claim_ids",
        identity="journalist_id",
        allow_empty=True,
    )


def _is_input_time(value: Any) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _validate_source_request(request: Mapping[str, Any]) -> None:
    try:
        validate_portable_component(request["source_id"])
    except UnsafeCasePathError as error:
        raise ValueError("source_id must be a portable component") from error
    path = request["path"]
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("source path must be a non-empty string or Path")
    for field in ("license", "sensitivity", "redistribution", "reacquisition"):
        if not isinstance(request[field], str):
            raise ValueError(f"{field} must be a string")
    if type(request["included"]) is not bool:
        raise ValueError("included must be a boolean")
    reason = request.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("reason must be a string")
    if request["included"] is False and (
        not isinstance(reason, str) or not reason.strip()
    ):
        raise ValueError("excluded sources require a reason")


def _gate_input(
    value: Any,
    *,
    sequence: str,
    identity: str,
    allow_empty: bool,
    maximum: int | None = None,
    reject_separators: bool = False,
) -> dict[str, Any]:
    required = {sequence, identity}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("gate input has missing or unknown fields")
    selected = value[sequence]
    if not isinstance(selected, (list, tuple)):
        raise ValueError(f"{sequence} must be a list")
    if not allow_empty and not selected:
        raise ValueError(f"{sequence} must not be empty")
    if maximum is not None and len(selected) > maximum:
        raise ValueError(f"{sequence} exceeds its limit")
    if any(
        not isinstance(item, str)
        or not item.strip()
        or (reject_separators and ("/" in item or "\\" in item))
        for item in selected
    ):
        raise ValueError(f"{sequence} contains an invalid ID")
    if len(selected) != len(set(selected)):
        raise ValueError(f"{sequence} contains duplicate IDs")
    actor = value[identity]
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError(f"{identity} must be a non-empty identity")
    return dict(value)


def read_case_json(root: Path, relative: str) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError(f"invalid or missing workflow artifact: {relative}") from error
