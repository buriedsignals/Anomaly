"""Adapter for OpenParlData.ch parliamentary records.

The upstream API exposes many harmonized tables behind one consistent REST
shape.  This adapter keeps one source-level router: choose a primary resource,
then list/search it, fetch one record, or traverse an allow-listed relation.
"""

from __future__ import annotations

import json
import re
import zlib
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


# --- Parliamentary contract rows ------------------------------------------------
# These operations read the bulk NDJSON exports, because the API stops at offset
# 100,000 and votes carry no date. Each returns rows of one table of
# domains/parliamentary.yaml for one parliament (body_key).

EXPORTS_URL = "https://files.openparldata.ch/exports"
CONTRACT_OPERATIONS = {"parl-members", "parl-affiliations", "parl-votings", "parl-member-votes", "parl-interests"}
# Upstream also publishes absent_excused (counted as absent, like the European
# Parliament's "did not vote") and abstention_president (kept as is, so the
# chair is neither absent nor a voter).
VOTE_POSITIONS = {"yes": "for", "no": "against", "abstention": "abstain", "absent": "absent", "absent_excused": "absent"}
PAYMENT = {"paid": "paid", "honorary": "unpaid"}
DEFAULT_MAX_ROWS = 50_000
MAX_ROWS = 500_000
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BODY_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")


def _ndjson(client: httpx.Client, table: str, body_key: str):
    """Stream one gzipped export and yield the rows of one body.

    Lines without the quoted body key are skipped before parsing, which keeps a
    full pass over the 287 MB votes export affordable."""
    marker = json.dumps(body_key).encode()
    inflater = zlib.decompressobj(31)
    pending = b""
    with client.stream("GET", f"{EXPORTS_URL}/{table}.ndjson.gz") as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            pending += inflater.decompress(chunk)
            *lines, pending = pending.split(b"\n")
            for line in lines:
                if marker in line:
                    row = json.loads(line)
                    if row.get("body_key") == body_key:
                        yield row
    pending += inflater.flush()
    if pending.strip() and marker in pending:
        row = json.loads(pending)
        if row.get("body_key") == body_key:
            yield row


def _flat(row: dict[str, Any], base: str, language: str) -> Any:
    for suffix in (language, "de", "fr", "it", "rm", "en"):
        value = row.get(f"{base}_{suffix}")
        if value not in (None, ""):
            return value.strip() if isinstance(value, str) else value
    return None


def _contract_input(input: dict) -> tuple[str, str | None, str | None, int, str]:
    body_key = str(input.get("body_key") or "CHE")
    if not _BODY_RE.match(body_key):
        raise ValueError("`body_key` must be an OpenParlData body key such as CHE.")
    start, end = input.get("from"), input.get("to")
    for value in (start, end):
        if value is not None and not (isinstance(value, str) and _DATE_RE.match(value)):
            raise ValueError("`from` and `to` must be YYYY-MM-DD dates.")
    max_rows = int(DEFAULT_MAX_ROWS if input.get("max_rows") is None else input["max_rows"])
    if not 1 <= max_rows <= MAX_ROWS:
        raise ValueError(f"`max_rows` must be between 1 and {MAX_ROWS}.")
    return body_key, start, end, max_rows, input.get("language") or "de"


def _chambers(client: httpx.Client, body_key: str, language: str) -> dict[Any, str]:
    return {row["id"]: _flat(row, "name", language) for row in _ndjson(client, "groups", body_key)}


def _votings(client: httpx.Client, body_key: str, start: str | None, end: str | None, language: str) -> dict[Any, dict]:
    """Votings of the body inside the date window, as parl_votings rows by id."""
    chambers = _chambers(client, body_key, language)
    rows: dict[Any, dict] = {}
    for raw in _ndjson(client, "votings", body_key):
        day = str(raw.get("date") or "")[:10] or None
        if day is None or (start and day < start) or (end and day > end):
            continue
        rows[raw["id"]] = {
            "voting_id": raw["id"],
            "parliament": body_key,
            "chamber": chambers.get(raw.get("group_id")),
            "vote_date": day,
            "title": _flat(raw, "title", language) or _flat(raw, "affair_title", language),
            "dossier_id": raw.get("affair_id"),
            "url": _flat(raw, "url_external", language) or f"{API_URL}/votings/{raw['id']}",
        }
    return rows


def _member_votes(client: httpx.Client, votings: dict[Any, dict], body_key: str, max_rows: int, language: str) -> list[dict]:
    rows = []
    for raw in _ndjson(client, "votes", body_key):
        voting = votings.get(raw.get("voting_id"))
        if voting is None:
            continue
        vote = str(raw.get("vote") or "").lower()
        rows.append({
            "voting_id": raw["voting_id"],
            "parliament": body_key,
            "member_id": raw.get("person_id"),
            "position": VOTE_POSITIONS.get(vote, vote or None),
            "group_at_vote": _flat(raw, "person_parliamentary_group_name", language),
            "member_name": raw.get("person_fullname"),
            "vote_date": voting["vote_date"],
        })
        if len(rows) >= max_rows:
            break
    return rows


def _group_spans(votes: list[dict], body_key: str) -> list[dict]:
    """Derive group affiliations from the groups members voted under.

    OpenParlData has no dated faction memberships, so each run of votes under
    one group label becomes a span; the last span of a member stays open."""
    by_member: dict[Any, list[tuple[str, str]]] = {}
    for row in votes:
        if row["member_id"] is not None and row["group_at_vote"]:
            by_member.setdefault(row["member_id"], []).append((row["vote_date"], row["group_at_vote"]))
    spans = []
    for member_id, seen in by_member.items():
        seen.sort()
        runs: list[list[str]] = []
        for day, group in seen:
            if runs and runs[-1][0] == group:
                runs[-1][2] = day
            else:
                runs.append([group, day, day])
        for index, (group, first, last) in enumerate(runs):
            spans.append({
                "member_id": member_id, "parliament": body_key, "affiliation_type": "group",
                "org_id": group, "org_name": group, "start_date": first,
                "end_date": None if index == len(runs) - 1 else last, "term": None,
            })
    return spans


def _members(client: httpx.Client, body_key: str, language: str) -> list[dict]:
    return [{
        "member_id": raw["id"],
        "parliament": body_key,
        "name": raw.get("fullname") or " ".join(p for p in (raw.get("firstname"), raw.get("lastname")) if p) or None,
        "country": _flat(raw, "electoral_district", language),
        "party": _flat(raw, "party", language),
        "active": raw.get("active"),
    } for raw in _ndjson(client, "persons", body_key)]


def _interests(client: httpx.Client, body_key: str, language: str) -> list[dict]:
    return [{
        "interest_id": raw["id"],
        "member_id": raw.get("person_id"),
        "parliament": body_key,
        "organisation": _flat(raw, "name", language),
        "role": _flat(raw, "role_name", language),
        "paid": PAYMENT.get(str(raw.get("type_payment_harmonized") or "").lower()),
        "income_high": None,
        "end_date": raw.get("end_date"),
        "interest_type": _flat(raw, "type", language),
        "start_date": raw.get("begin_date"),
    } for raw in _ndjson(client, "interests", body_key)]


def _contract_rows(input: dict, client: httpx.Client) -> dict:
    operation = input["operation"]
    body_key, start, end, max_rows, language = _contract_input(input)
    if operation == "parl-members":
        records = _members(client, body_key, language)
    elif operation == "parl-interests":
        records = _interests(client, body_key, language)
    else:
        votings = _votings(client, body_key, start, end, language)
        if operation == "parl-votings":
            records = sorted(votings.values(), key=lambda row: (row["vote_date"], row["voting_id"]))[:max_rows]
        else:
            votes = _member_votes(client, votings, body_key, max_rows, language)
            records = votes if operation == "parl-member-votes" else _group_spans(votes, body_key)
    return {
        "source_id": SOURCE_ID,
        "mode": operation,
        "records": records,
        "page": {"max_rows": max_rows, "truncated": len(records) >= max_rows},
        "attribution": "Source: OpenParlData.ch (CC BY 4.0)",
    }


def run(input: dict, ctx) -> dict:
    del ctx  # public API; retained for the standard adapter contract
    if input.get("operation") is not None:
        if input["operation"] not in CONTRACT_OPERATIONS:
            raise ValueError(f"Unsupported OpenParlData operation `{input['operation']}`.")
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            return _contract_rows(input, client)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        return _request(input, client)
