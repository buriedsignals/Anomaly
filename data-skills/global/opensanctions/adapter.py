"""Read-only OpenSanctions screening, search, and entity retrieval."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

API_URL = "https://api.opensanctions.org"
SOURCE_ID = "global/opensanctions"
DATASET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
CHANGED_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?$")
ALGORITHMS = {"best", "logic-v2", "ofac", "name-based", "name-qualified", "logic-v1", "regression-v1"}


def _string(input: dict[str, Any], field: str, *, maximum: int = 500) -> str:
    value = input.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters.")
    return value


def _integer(
    input: dict[str, Any], field: str, default: int, minimum: int, maximum: int
) -> int:
    value = input.get(field, default)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return parsed


def _strings(input: dict[str, Any], field: str, *, maximum: int = 100) -> list[str]:
    value = input.get(field)
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError(f"{field} must be a string or list of strings.")
    normalized = [item.strip() for item in values if item.strip()]
    if len(normalized) > maximum:
        raise ValueError(f"{field} must contain at most {maximum} values.")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} must not contain duplicates.")
    return normalized


def _dataset(input: dict[str, Any]) -> str:
    value = str(input.get("dataset") or "default").strip()
    if not DATASET_RE.fullmatch(value):
        raise ValueError("dataset must be an OpenSanctions dataset or collection slug.")
    return value


def _result_url(entity_id: Any) -> str | None:
    if not entity_id:
        return None
    return f"https://www.opensanctions.org/entities/{quote(str(entity_id), safe='')}"


def _summarize_entity(
    entity: dict[str, Any], *, include_properties: bool = False
) -> dict[str, Any]:
    properties = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_id = entity.get("id")
    record: dict[str, Any] = {
        "entity": entity.get("schema"),
        "id": entity_id,
        "caption": entity.get("caption"),
        "topics": entity.get("topics") or properties.get("topics") or [],
        "datasets": entity.get("datasets") or [],
        "countries": entity.get("countries") or properties.get("country") or [],
        "target": entity.get("target"),
        "first_seen": entity.get("first_seen"),
        "last_seen": entity.get("last_seen"),
        "last_change": entity.get("last_change"),
        "source_url": _result_url(entity_id),
    }
    if include_properties:
        record["properties"] = properties
        record["referents"] = entity.get("referents") or []
    return record


def _mode(input: dict[str, Any]) -> str:
    mode = input.get("mode")
    if mode is not None:
        if mode not in {"match", "search", "entity"}:
            raise ValueError("mode must be match, search, or entity.")
        return str(mode)
    if input.get("entity_id") or input.get("id"):
        return "entity"
    if input.get("q") or input.get("query"):
        return "search"
    if input.get("name") or input.get("properties"):
        return "match"
    raise ValueError(
        "OpenSanctions needs name/properties for match, q for search, or entity_id for entity retrieval."
    )


def _common_filters(input: dict[str, Any], params: dict[str, Any]) -> None:
    for field in ("include_dataset", "exclude_dataset", "exclude_schema", "topics"):
        values = _strings(input, field)
        if values:
            params[field] = values
    if input.get("changed_since") is not None:
        changed_since = _string(input, "changed_since", maximum=19)
        if not CHANGED_SINCE_RE.fullmatch(changed_since):
            raise ValueError("changed_since must be YYYY-MM-DD or a supported partial ISO timestamp.")
        params["changed_since"] = changed_since


def _total(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value")
    return value


def _search(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    query = input.get("q") or input.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("q is required.")
    dataset = _dataset(input)
    params: dict[str, Any] = {
        "q": query.strip(),
        "limit": _integer(input, "limit", 10, 1, 50),
        "offset": _integer(input, "offset", 0, 0, 9499),
    }
    if input.get("schema") is not None:
        params["schema"] = _string(input, "schema", maximum=100)
    for field in ("countries", "topics", "datasets", "sort"):
        values = _strings(input, field)
        if values:
            params[field] = values
    property_filters = _strings(input, "property_filters")
    if property_filters:
        if any(":" not in value for value in property_filters):
            raise ValueError("property_filters entries must use field:value syntax.")
        params["filter"] = property_filters
    for field in ("simple", "fuzzy"):
        if field in input:
            if not isinstance(input[field], bool):
                raise ValueError(f"{field} must be a boolean.")
            params[field] = input[field]
    if input.get("filter_op") is not None:
        value = _string(input, "filter_op", maximum=3).upper()
        if value not in {"AND", "OR"}:
            raise ValueError("filter_op must be AND or OR.")
        params["filter_op"] = value
    for field in ("include_dataset", "exclude_dataset", "exclude_schema"):
        values = _strings(input, field)
        if values:
            params[field] = values
    if input.get("changed_since") is not None:
        changed_since = _string(input, "changed_since", maximum=19)
        if not CHANGED_SINCE_RE.fullmatch(changed_since):
            raise ValueError("changed_since must be YYYY-MM-DD or a supported partial ISO timestamp.")
        params["changed_since"] = changed_since
    response = client.get(f"{API_URL}/search/{dataset}", params=params)
    response.raise_for_status()
    data = response.json()
    return {
        "source_id": SOURCE_ID,
        "mode": "search",
        "records": [
            _summarize_entity(entity)
            for entity in data.get("results", [])
            if isinstance(entity, dict)
        ],
        "page": {
            "dataset": dataset,
            "limit": data.get("limit", params["limit"]),
            "offset": data.get("offset", params["offset"]),
            "total": _total(data.get("total")),
        },
        "facets": data.get("facets"),
    }


def _properties(input: dict[str, Any]) -> dict[str, list[str]]:
    raw = input.get("properties")
    if raw is None:
        name = _string(input, "name", maximum=500)
        return {"name": [name]}
    if not isinstance(raw, dict) or not raw:
        raise ValueError("properties must be a non-empty object.")
    normalized: dict[str, list[str]] = {}
    for key, values in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("properties keys must be non-empty strings.")
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError("properties values must be non-empty strings or arrays of strings.")
        normalized[key.strip()] = [value.strip() for value in values]
    return normalized


def _match(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    dataset = _dataset(input)
    schema = str(input.get("schema") or "Person").strip()
    if not schema:
        raise ValueError("schema must be a non-empty FollowTheMoney schema name.")
    params: dict[str, Any] = {"limit": _integer(input, "limit", 5, 1, 50)}
    _common_filters(input, params)
    if input.get("algorithm") is not None:
        algorithm = _string(input, "algorithm", maximum=50)
        if algorithm not in ALGORITHMS:
            raise ValueError(f"algorithm must be one of: {', '.join(sorted(ALGORITHMS))}.")
        params["algorithm"] = algorithm
    if input.get("threshold") is not None:
        threshold = input["threshold"]
        if isinstance(threshold, bool):
            raise ValueError("threshold must be a number between 0 and 1.")
        try:
            threshold = float(threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError("threshold must be a number between 0 and 1.") from exc
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be a number between 0 and 1.")
        params["threshold"] = threshold
    excluded = _strings(input, "exclude_entity_ids", maximum=50)
    if excluded:
        params["exclude_entity_ids"] = excluded
    request = {"queries": {"query": {"schema": schema, "properties": _properties(input)}}}
    response = client.post(f"{API_URL}/match/{dataset}", params=params, json=request)
    response.raise_for_status()
    data = response.json()
    results = ((data.get("responses") or {}).get("query") or {}).get("results") or []
    return {
        "source_id": SOURCE_ID,
        "mode": "match",
        "records": [
            {
                **_summarize_entity(result.get("entity") or {}),
                "score": result.get("score"),
                "match": result.get("match"),
            }
            for result in results
            if isinstance(result, dict)
        ],
        "page": {"dataset": dataset, "limit": params["limit"]},
        "verification_note": "OpenSanctions candidates require human review and independent grounding.",
    }


def _entity(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    entity_id = input.get("entity_id") or input.get("id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError("entity_id is required.")
    if len(entity_id.strip()) > 500:
        raise ValueError("entity_id must be at most 500 characters.")
    nested = input.get("nested", True)
    if not isinstance(nested, bool):
        raise ValueError("nested must be a boolean.")
    response = client.get(
        f"{API_URL}/entities/{quote(entity_id.strip(), safe='')}",
        params={"nested": str(nested).lower()},
    )
    response.raise_for_status()
    entity = response.json()
    return {
        "source_id": SOURCE_ID,
        "mode": "entity",
        "records": [_summarize_entity(entity, include_properties=True)],
        "page": {},
    }


def run(input: dict[str, Any], ctx) -> dict[str, Any]:
    mode = _mode(input)
    headers = {"Authorization": f"ApiKey {ctx.get_key('opensanctions')}"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        if mode == "search":
            return _search(input, client)
        if mode == "match":
            return _match(input, client)
        return _entity(input, client)
