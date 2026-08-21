"""Read-only OCCRP Aleph entity search, detail, and graph expansion."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

API_URL = "https://aleph.occrp.org/api/2"
UI_URL = "https://aleph.occrp.org/entities"
SOURCE_ID = "global/occrp-aleph/entities"
MODES = {"search", "entity", "expand"}


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


def _list(input: dict[str, Any], field: str) -> list[str]:
    value = input.get(field)
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError(f"{field} must be a string or list of strings.")
    normalized = [item.strip() for item in values if item.strip()]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} must not contain duplicates.")
    return normalized


def _first(props: dict[str, Any], key: str) -> Any:
    value = props.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _normalize(entity: dict[str, Any]) -> dict[str, Any]:
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_id = entity.get("id")
    collection = entity.get("collection") if isinstance(entity.get("collection"), dict) else {}
    countries = props.get("country") or props.get("nationality") or props.get("jurisdiction") or []
    if not isinstance(countries, list):
        countries = [countries]
    encoded_id = quote(str(entity_id), safe="") if entity_id else None
    return {
        "entity": entity.get("schema"),
        "id": entity_id,
        "name": entity.get("caption") or _first(props, "name"),
        "collection": collection.get("label"),
        "collection_id": collection.get("id") or collection.get("collection_id") or entity.get("collection_id"),
        "countries": countries,
        "source_url": f"{UI_URL}/{encoded_id}" if encoded_id else None,
    }


def _mode(input: dict[str, Any]) -> str:
    mode = input.get("mode")
    if mode is not None:
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError("mode must be search, entity, or expand.")
        return mode
    if input.get("entity_id") or input.get("id"):
        return "expand" if input.get("expand") else "entity"
    if input.get("q") or input.get("query"):
        return "search"
    raise ValueError("Aleph needs q for search or entity_id for entity/expand.")


def _entity_id(input: dict[str, Any]) -> str:
    value = input.get("entity_id") or input.get("id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("entity_id is required.")
    value = value.strip()
    if len(value) > 500:
        raise ValueError("entity_id must be at most 500 characters.")
    return quote(value, safe="")


def _search(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    query = input.get("q") or input.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("q is required.")
    params: dict[str, Any] = {
        "q": query.strip(),
        "limit": _integer(input, "limit", 10, 1, 50),
        "offset": _integer(input, "offset", 0, 0, 10_000),
    }
    if input.get("schema") is not None:
        params["filter:schemata"] = _string(input, "schema", maximum=100)
    if input.get("collection_id") is not None:
        params["filter:collection_id"] = _string(input, "collection_id", maximum=200)
    response = client.get(f"{API_URL}/entities", params=params)
    response.raise_for_status()
    data = response.json()
    return {
        "source_id": SOURCE_ID,
        "mode": "search",
        "records": [_normalize(entity) for entity in data.get("results", []) if isinstance(entity, dict)],
        "page": {
            "total": data.get("total"),
            "total_type": data.get("total_type"),
            "limit": data.get("limit", params["limit"]),
            "offset": data.get("offset", params["offset"]),
        },
    }


def _entity(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    response = client.get(f"{API_URL}/entities/{_entity_id(input)}")
    response.raise_for_status()
    data = response.json()
    return {
        "source_id": SOURCE_ID,
        "mode": "entity",
        "records": [_normalize(data)],
        "page": {},
    }


def _expand(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": _integer(input, "limit", 10, 1, 50)}
    properties = _list(input, "properties")
    if properties:
        params["filter:property"] = properties
    response = client.get(f"{API_URL}/entities/{_entity_id(input)}/expand", params=params)
    response.raise_for_status()
    data = response.json()
    records: list[dict[str, Any]] = []
    for relation in data.get("results", []):
        if not isinstance(relation, dict):
            continue
        for entity in relation.get("entities", []):
            if isinstance(entity, dict):
                records.append(
                    {
                        **_normalize(entity),
                        "relation": relation.get("property"),
                        "relation_count": relation.get("count"),
                    }
                )
    return {
        "source_id": SOURCE_ID,
        "mode": "expand",
        "records": records,
        "page": {"total": data.get("total"), "limit": params["limit"]},
    }


def run(input: dict[str, Any], ctx) -> dict[str, Any]:
    # Aleph's source tests distinguish session `Token` credentials from API
    # keys. User API keys use the `ApiKey` authorization method.
    headers = {"Authorization": f"ApiKey {ctx.get_key('occrp-aleph')}"}
    mode = _mode(input)
    with httpx.Client(headers=headers, timeout=30) as client:
        if mode == "search":
            return _search(input, client)
        if mode == "expand":
            return _expand(input, client)
        return _entity(input, client)
