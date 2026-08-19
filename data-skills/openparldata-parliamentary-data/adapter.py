"""Adapter for OpenParlData.ch parliamentary records.

The upstream API exposes many harmonized tables behind one consistent REST
shape.  This adapter keeps one source-level router: choose a primary resource,
then list/search it, fetch one record, or traverse an allow-listed relation.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

API_URL = "https://api.openparldata.ch/v1"
SOURCE_ID = "ch/openparldata/parliamentary-data"

RESOURCES = {
    "access_badges",
    "affairs",
    "agendas",
    "bodies",
    "contributors",
    "docs",
    "events",
    "external_links",
    "groups",
    "identities",
    "interests",
    "meetings",
    "memberships",
    "news",
    "person_images",
    "persons",
    "speeches",
    "texts",
    "votes",
    "votings",
}

RELATIONS = {
    "affairs": {
        "agendas", "bodies", "contributors", "docs", "events",
        "external_links", "meetings", "speeches", "texts", "votings",
    },
    "docs": {"affair", "agenda", "bodies", "meeting", "news"},
    "groups": {"bodies", "contributors", "meetings", "memberships"},
    "interests": {"bodies", "person"},
    "meetings": {
        "agendas", "bodies", "child_meetings", "docs", "group",
        "parent_meeting", "speeches",
    },
    "memberships": {"bodies", "group", "person"},
    "persons": {
        "access_badges", "affairs", "bodies", "contributors",
        "external_links", "identities", "interests", "memberships",
        "person_images", "speeches", "votes",
    },
    "speeches": {"affair", "agenda", "bodies", "meeting", "person"},
    "votes": {"bodies", "person", "person_image", "voting"},
    "votings": {"affairs", "bodies", "meeting", "votes"},
}

_FILTER_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_RESERVED_FILTERS = {"format", "output_format", "offset", "limit"}

_SINGULAR_RELATION_RESOURCES = {
    "affair": "affairs",
    "agenda": "agendas",
    "group": "groups",
    "meeting": "meetings",
    "person": "persons",
    "person_image": "person_images",
    "voting": "votings",
}


def _language_value(raw: dict[str, Any], base: str, language: str) -> Any:
    value = raw.get(base)
    if isinstance(value, dict):
        return value.get(language) or value.get("de") or next(iter(value.values()), None)
    for suffix in (language, "de", "fr", "it", "en"):
        value = raw.get(f"{base}_{suffix}")
        if value not in (None, ""):
            return value
    return value


def _source_url(raw: dict[str, Any], resource: str) -> str | None:
    if raw.get("url_api"):
        return raw["url_api"]
    record_id = raw.get("id")
    return f"{API_URL}/{resource}/{record_id}" if record_id is not None else None


def _normalize(raw: dict[str, Any], resource: str, language: str, include_raw: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "resource": resource,
        "id": raw.get("id"),
        "body_key": raw.get("body_key"),
        "source_url": _source_url(raw, resource),
    }

    if resource == "persons":
        record |= {
            "name": raw.get("fullname") or " ".join(
                p for p in (raw.get("firstname"), raw.get("lastname")) if p
            ) or None,
            "first_name": raw.get("firstname"),
            "last_name": raw.get("lastname"),
            "party": _language_value(raw, "party_harmonized", language)
            or _language_value(raw, "party", language),
            "role": _language_value(raw, "function_latest", language),
            "electoral_district": _language_value(raw, "electoral_district", language),
            "active": raw.get("active"),
            "email": raw.get("email"),
            "birth_date": raw.get("birthday"),
            "wikidata_id": raw.get("wikidata_id"),
        }
    elif resource == "affairs":
        record |= {
            "number": raw.get("number"),
            "title": _language_value(raw, "title_long", language)
            or _language_value(raw, "title", language),
            "type": _language_value(raw, "type_harmonized", language)
            or _language_value(raw, "type_name", language),
            "status": _language_value(raw, "state_name_harmonized", language)
            or _language_value(raw, "state_name", language),
            "begin_date": raw.get("begin_date"),
            "end_date": raw.get("end_date"),
            "active": raw.get("active"),
            "external_url": _language_value(raw, "url_external", language),
        }
    elif resource == "interests":
        record |= {
            "name": _language_value(raw, "name", language),
            "person_id": raw.get("person_id"),
            "role": _language_value(raw, "role_name", language),
            "type": _language_value(raw, "type", language),
            "begin_date": raw.get("begin_date"),
            "end_date": raw.get("end_date"),
            "place": raw.get("place"),
            "payment_type": _language_value(raw, "type_payment", language),
            "declaration_url": raw.get("declaration_doc_url"),
        }
    elif resource == "votings":
        record |= {
            "title": _language_value(raw, "title", language)
            or _language_value(raw, "affair_title", language),
            "affair_id": raw.get("affair_id"),
            "meeting_id": raw.get("meeting_id"),
            "date": raw.get("date"),
            "decision": raw.get("decision"),
            "yes": raw.get("results_yes"),
            "no": raw.get("results_no"),
            "abstention": raw.get("results_abstention"),
            "absent": raw.get("results_absent"),
            "meaning_of_yes": _language_value(raw, "meaning_of_yes", language),
            "meaning_of_no": _language_value(raw, "meaning_of_no", language),
            "external_url": _language_value(raw, "url_external", language),
        }
    elif resource == "votes":
        record |= {
            "person_id": raw.get("person_id"),
            "person_name": raw.get("person_fullname"),
            "voting_id": raw.get("voting_id"),
            "vote": raw.get("vote"),
            "party": _language_value(raw, "person_party", language),
            "parliamentary_group": _language_value(
                raw, "person_parliamentary_group_name", language
            ),
        }
    else:
        record |= {
            "name": _language_value(raw, "name", language)
            or raw.get("fullname")
            or raw.get("person_fullname"),
            "title": _language_value(raw, "title", language),
            "date": raw.get("date") or raw.get("begin_date"),
            "end_date": raw.get("end_date"),
            "person_id": raw.get("person_id"),
            "affair_id": raw.get("affair_id"),
            "meeting_id": raw.get("meeting_id"),
            "status": raw.get("status") or _language_value(raw, "state_name", language),
        }

    if include_raw:
        record["raw"] = raw
    return record


def _resource(input: dict) -> str:
    resource = input.get("resource")
    if not resource:
        if input.get("person_id") or input.get("name"):
            resource = "persons"
        elif input.get("affair_id"):
            resource = "affairs"
        elif input.get("q") or input.get("search"):
            resource = "affairs"
        else:
            raise ValueError(
                "OpenParlData needs `resource`, `name`/`person_id`, "
                "`affair_id`, or `q` (defaults to affairs)."
            )
    if resource not in RESOURCES:
        raise ValueError(f"Unsupported OpenParlData resource `{resource}`.")
    return resource


def _filters(input: dict) -> dict[str, Any]:
    filters = input.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("`filters` must be an object of upstream query parameters.")
    params: dict[str, Any] = {}
    for key, value in filters.items():
        if not _FILTER_RE.match(key) or key in _RESERVED_FILTERS:
            raise ValueError(f"Unsafe or reserved OpenParlData filter `{key}`.")
        params[key] = ",".join(str(v) for v in value) if isinstance(value, list) else value
    return params


def _relation_resource(relation: str) -> str:
    return _SINGULAR_RELATION_RESOURCES.get(relation, relation)


def _request(input: dict, client: httpx.Client) -> dict:
    resource = _resource(input)
    record_id = input.get("id") or input.get("person_id") or input.get("affair_id")
    relation = input.get("relation")
    if relation:
        if record_id is None:
            raise ValueError("A relation query needs `id` (or person_id/affair_id).")
        if relation not in RELATIONS.get(resource, set()):
            raise ValueError(f"Unsupported relation `{relation}` for `{resource}`.")

    limit = max(1, min(int(input.get("limit", 10)), 100))
    offset = max(0, int(input.get("offset", 0)))
    language = input.get("language") or "en"
    params = _filters(input)
    params |= {
        "limit": limit,
        "offset": offset,
        "lang": language,
        "lang_fallback": input.get("language_fallback") or "de",
        "lang_format": "flat",
    }
    query = input.get("q") or input.get("search") or input.get("name")
    if query:
        params["search"] = query
        params["search_mode"] = input.get("search_mode") or "partial"
    for source_key, upstream_key in (
        ("search_scope", "search_scope"),
        ("search_language", "search_language"),
        ("sort_by", "sort_by"),
        ("expand", "expand"),
        ("fields", "fields"),
    ):
        if input.get(source_key) is not None:
            params[upstream_key] = input[source_key]

    if record_id is None:
        path = f"/{resource}/"
        mode = "search" if query else "list"
    elif relation:
        path = f"/{resource}/{record_id}/{relation}"
        mode = "relation"
    else:
        path = f"/{resource}/{record_id}"
        mode = "detail"

    response = client.get(f"{API_URL}{path}", params=params)
    response.raise_for_status()
    payload = response.json()
    raw_records = payload.get("data", payload)
    if isinstance(raw_records, dict):
        raw_records = [raw_records]
    meta = payload.get("meta") or {}
    result_resource = _relation_resource(relation) if relation else resource
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "resource": resource,
        "relation": relation,
        "records": [
            _normalize(raw, result_resource, language, bool(input.get("include_raw")))
            for raw in (raw_records or [])
        ],
        "page": {
            "offset": meta.get("offset", offset),
            "limit": meta.get("limit", limit),
            "total": meta.get("total_records"),
            "has_more": meta.get("has_more"),
            "next": meta.get("next_page"),
        },
        "attribution": "Source: OpenParlData.ch (CC BY 4.0)",
    }


def run(input: dict, ctx) -> dict:
    del ctx  # public API; retained for the standard adapter contract
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        return _request(input, client)
