from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from anomaly._signal_projection import (
    SignalSearchError,
    StaleSignalProjectionError,
    build_projection,
    read_rows,
    verified_projection,
)


_MAX_LIMIT = 100
_MAX_QUERY_LENGTH = 1_000
_MAX_QUERY_TERMS = 50
_FILTER_COLUMNS = {
    "detector_id": "detector_id",
    "group": "detector_group",
    "category": "category",
    "severity": "severity",
    "source_id": "source_id",
    "table_id": "table_id",
    "run_id": "run_id",
    "date": "run_date",
    "review_state": "review_state",
}
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")

__all__ = [
    "SignalSearchError",
    "StaleSignalProjectionError",
    "build_signal_projection",
    "search_signals",
]


def build_signal_projection(root: Path) -> dict[str, Any]:
    """Atomically rebuild the derived, hash-bound signal search projection."""
    return build_projection(root)


def search_signals(
    root: Path,
    *,
    query: str | None = None,
    filters: Mapping[str, str] | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Search the current derived projection without changing canonical evidence."""
    normalized_query, terms = _validate_query(query)
    normalized_filters = _validate_filters(filters)
    _validate_limit(limit)
    projection, manifest = verified_projection(root)
    cursor_key = _decode_cursor(
        cursor,
        manifest["projection_identity"],
        normalized_query,
        normalized_filters,
    )
    filter_columns = [
        (_FILTER_COLUMNS[key], value) for key, value in normalized_filters.items()
    ]
    candidates = _rank_rows(read_rows(projection, filter_columns), terms)
    if cursor_key is not None and not any(
        (item["query_score"], item["signal_id"]) == cursor_key
        for item in candidates
    ):
        raise SignalSearchError("search cursor does not identify this result set")
    remaining = _after_cursor(candidates, cursor_key)
    page = remaining[:limit]
    next_cursor = None
    if len(remaining) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(
            manifest["projection_identity"],
            normalized_query,
            normalized_filters,
            last["query_score"],
            last["signal_id"],
        )
    return {"items": page, "next_cursor": next_cursor}


def _validate_query(query: str | None) -> tuple[str, list[str]]:
    if query is None:
        return "", []
    if not isinstance(query, str):
        raise SignalSearchError("search query must be text")
    normalized = " ".join(query.casefold().split())
    terms = normalized.split()
    if len(query) > _MAX_QUERY_LENGTH or len(terms) > _MAX_QUERY_TERMS:
        raise SignalSearchError("search query is too large")
    return normalized, terms


def _validate_filters(filters: Mapping[str, str] | None) -> dict[str, str]:
    if filters is None:
        return {}
    if not isinstance(filters, Mapping):
        raise SignalSearchError("search filters must be a mapping")
    unknown = set(filters) - set(_FILTER_COLUMNS)
    if unknown:
        raise SignalSearchError(f"unknown search filter: {sorted(unknown)[0]}")
    normalized: dict[str, str] = {}
    for key in sorted(filters):
        value = filters[key]
        if not isinstance(value, str) or not value:
            raise SignalSearchError(f"invalid search filter: {key}")
        if key == "date":
            _validate_date(value)
        normalized[key] = value
    return normalized


def _validate_date(value: str) -> None:
    if not _DATE.fullmatch(value):
        raise SignalSearchError("invalid search date")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise SignalSearchError("invalid search date") from error


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_LIMIT:
        raise SignalSearchError(f"search limit must be between 1 and {_MAX_LIMIT}")


def _rank_rows(
    rows: list[tuple[str, str]], terms: list[str]
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for payload_json, fields_json in rows:
        payload = _projected_json(payload_json, "payload")
        fields = _projected_json(fields_json, "search fields")
        if not isinstance(payload, dict) or not isinstance(fields, list):
            raise SignalSearchError("invalid data in signal search projection")
        matched_on = _matched_fields(fields, terms)
        if terms and not matched_on:
            continue
        payload["matched_on"] = matched_on
        payload["query_score"] = len(matched_on) if terms else 0
        ranked.append(payload)
    ranked.sort(key=lambda item: (-item["query_score"], item["signal_id"]))
    return ranked


def _matched_fields(fields: list[Any], terms: list[str]) -> list[dict[str, Any]]:
    if not terms:
        return []
    matches: list[dict[str, Any]] = []
    for field in fields:
        if (
            not isinstance(field, dict)
            or set(field) != {"field", "text"}
            or not isinstance(field["field"], str)
            or not isinstance(field["text"], str)
        ):
            raise SignalSearchError("invalid lexical field in signal search projection")
        text = field["text"].casefold()
        if all(term in text for term in terms):
            matches.append({"field": field["field"], "terms": list(terms)})
    # Prefer the most specific projected field when the same terms occur in
    # both a structured preview/metadata value and its prose summary.
    return matches[-1:]


def _after_cursor(
    rows: list[dict[str, Any]], cursor_key: tuple[int, str] | None
) -> list[dict[str, Any]]:
    if cursor_key is None:
        return rows
    last_score, last_signal_id = cursor_key
    return [
        row
        for row in rows
        if row["query_score"] < last_score
        or (
            row["query_score"] == last_score
            and row["signal_id"] > last_signal_id
        )
    ]


def _encode_cursor(
    projection_identity: str,
    query: str,
    filters: dict[str, str],
    query_score: int,
    signal_id: str,
) -> str:
    payload = {
        "filters": filters,
        "projection_identity": projection_identity,
        "query": query,
        "query_score": query_score,
        "signal_id": signal_id,
        "version": 1,
    }
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str | None,
    projection_identity: str,
    query: str,
    filters: dict[str, str],
) -> tuple[int, str] | None:
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor or len(cursor) > 4_096:
        raise SignalSearchError("invalid search cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as error:
        raise SignalSearchError("invalid search cursor") from error
    if not isinstance(payload, dict) or set(payload) != {
        "filters",
        "projection_identity",
        "query",
        "query_score",
        "signal_id",
        "version",
    }:
        raise SignalSearchError("invalid search cursor")
    score = payload["query_score"]
    if (
        payload["version"] != 1
        or payload["projection_identity"] != projection_identity
        or payload["query"] != query
        or payload["filters"] != filters
        or isinstance(score, bool)
        or not isinstance(score, int)
        or score < 0
        or not isinstance(payload["signal_id"], str)
        or not payload["signal_id"]
    ):
        raise SignalSearchError("search cursor does not match this query")
    canonical = _encode_cursor(
        projection_identity, query, filters, score, payload["signal_id"]
    )
    if canonical != cursor:
        raise SignalSearchError("invalid search cursor")
    return score, payload["signal_id"]


def _projected_json(raw: str, label: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise SignalSearchError(f"invalid projected {label}") from error
