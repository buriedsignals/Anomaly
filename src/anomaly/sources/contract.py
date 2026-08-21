"""The result envelope shared by every catalogue source adapter."""

from __future__ import annotations

import re
from typing import Any

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATUSES = {"ok", "unavailable", "error"}


def validate_source_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a source result without changing its payload."""
    if not isinstance(result, dict):
        raise ValueError("source result must be an object")
    required = {
        "source_id", "operation", "license", "endpoint", "source_hash",
        "provenance", "status", "records", "normalized", "error",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValueError(f"source result is missing: {', '.join(missing)}")
    if not isinstance(result["source_id"], str) or not result["source_id"]:
        raise ValueError("source_id must be a non-empty string")
    if not isinstance(result["operation"], str) or not result["operation"]:
        raise ValueError("operation must be a non-empty string")
    if not isinstance(result["license"], str) or not result["license"]:
        raise ValueError("license must be a non-empty string")
    if not isinstance(result["endpoint"], str) or not result["endpoint"]:
        raise ValueError("endpoint must be a non-empty string")
    if not isinstance(result["source_hash"], str) or not _HASH.fullmatch(result["source_hash"]):
        raise ValueError("source_hash must be a sha256 digest")
    if not isinstance(result["provenance"], dict):
        raise ValueError("provenance must be an object")
    if result["status"] not in _STATUSES:
        raise ValueError("status must be ok, unavailable, or error")
    if not isinstance(result["records"], list):
        raise ValueError("records must be an array")
    if result["status"] == "ok" and not result["records"]:
        raise ValueError("ok results must contain normalized records")
    if not isinstance(result["normalized"], bool):
        raise ValueError("normalized must be boolean")
    if result["status"] == "ok" and not result["normalized"]:
        raise ValueError("ok results must be normalized")
    if result["status"] == "ok" and result["error"] is not None:
        raise ValueError("ok results cannot contain an error")
    if result["status"] != "ok":
        if not isinstance(result["error"], dict):
            raise ValueError("unavailable and error results need an error object")
        if not isinstance(result["error"].get("code"), str) or not result["error"]["code"]:
            raise ValueError("source errors need a code")
        if not isinstance(result["error"].get("message"), str) or not result["error"]["message"]:
            raise ValueError("source errors need a message")
    return result
