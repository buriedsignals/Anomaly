from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

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
    if _is_complete_mapping(
        inputs.get("gate_a"),
        required={"approved_ids", "approved_by"},
        sequence="approved_ids",
        identity="approved_by",
    ):
        capabilities.add("gate_a")
    if _is_complete_mapping(
        inputs.get("gate_b"),
        required={"accepted_claim_ids", "journalist_id"},
        sequence="accepted_claim_ids",
        identity="journalist_id",
    ):
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
        requests.append(request)
    return requests


def mapping_input(inputs: Mapping[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    value = inputs.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} input must be a mapping")
    result = dict(value)
    if set(result) - allowed:
        raise ValueError(f"{name} input has unknown fields")
    return result


def _is_input_time(value: Any) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _is_complete_mapping(
    value: Any,
    *,
    required: set[str],
    sequence: str,
    identity: str,
) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == required
        and isinstance(value.get(sequence), (list, tuple))
        and isinstance(value.get(identity), str)
        and bool(value[identity].strip())
    )


def read_case_json(root: Path, relative: str) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError(f"invalid or missing workflow artifact: {relative}") from error
