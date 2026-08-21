"""Adapter for the European Parliament Open Data API v2.

One source-level router covers two useful domains: MEPs/roles and parliamentary
work.  Resource names are deliberately allow-listed because the upstream API's
filters and response shapes vary by endpoint.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

API_URL = "https://data.europarl.europa.eu/api/v2"
PORTAL_URL = "https://data.europarl.europa.eu"
SOURCE_ID = "eu/europarl/open-data"


class EuroparlResponseError(httpx.HTTPError):
    """The API returned HTTP success with an embedded provider error."""

RESOURCE_PATHS = {
    "meps": "meps",
    "meps_current": "meps/show-current",
    "meps_incoming": "meps/show-incoming",
    "meps_outgoing": "meps/show-outgoing",
    "meps_declarations": "meps-declarations",
    "corporate_bodies": "corporate-bodies",
    "meetings": "meetings",
    "events": "events",
    "speeches": "speeches",
    "procedures": "procedures",
    "documents": "documents",
    "plenary_documents": "plenary-documents",
    "parliamentary_questions": "parliamentary-questions",
    "plenary_session_documents": "plenary-session-documents",
    "plenary_session_items": "plenary-session-documents-items",
    "adopted_texts": "adopted-texts",
    "committee_documents": "committee-documents",
    "external_documents": "external-documents",
    "vote_results": "meetings/{id}/vote-results",
}

TEXT_SEARCH_RESOURCES = {
    "speeches",
    "adopted_texts",
    "plenary_session_items",
    "meps_declarations",
}

_FILTER_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")
_RESERVED_FILTERS = {"format", "offset", "limit"}

_EU_COUNTRY_3_TO_2 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY",
    "CZE": "CZ", "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR",
    "DEU": "DE", "GRC": "EL", "HUN": "HU", "IRL": "IE", "ITA": "IT",
    "LVA": "LV", "LTU": "LT", "LUX": "LU", "MLT": "MT", "NLD": "NL",
    "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI",
    "ESP": "ES", "SWE": "SE", "GBR": "UK",
}


def _pick(value: Any, language: str) -> Any:
    if not isinstance(value, dict):
        return value
    return value.get(language) or value.get("en") or next(iter(value.values()), None)


def _identifier(raw: dict[str, Any]) -> str | None:
    value = (
        raw.get("identifier")
        or raw.get("process_id")
        or raw.get("activity_id")
        or raw.get("id")
    )
    if value is None:
        return None
    value = str(value)
    return value.rsplit("/", 1)[-1]


def _semantic_url(raw: dict[str, Any]) -> str | None:
    value = raw.get("id")
    if not value:
        return None
    value = str(value)
    return value if value.startswith("http") else f"{PORTAL_URL}/{value}"


def _document_details(raw: dict[str, Any], language: str) -> tuple[Any, list[dict[str, Any]]]:
    expressions = raw.get("is_realized_by") or []
    if isinstance(expressions, dict):
        expressions = [expressions]
    preferred = next(
        (item for item in expressions if str(item.get("id", "")).endswith(f"/{language}")),
        expressions[0] if expressions else {},
    )
    title = _pick(preferred.get("title"), language) or _pick(raw.get("title"), language)
    manifestations = preferred.get("is_embodied_by") or []
    if isinstance(manifestations, dict):
        manifestations = [manifestations]
    files = []
    for item in manifestations[:8]:
        path = item.get("is_exemplified_by")
        if not path:
            continue
        files.append(
            {
                "media_type": item.get("media_type"),
                "url": path if str(path).startswith("http") else f"{PORTAL_URL}/{path}",
            }
        )
    return title, files


def _current_memberships(raw: dict[str, Any]) -> list[dict[str, Any]]:
    memberships = raw.get("hasMembership") or []
    if isinstance(memberships, dict):
        memberships = [memberships]
    current = []
    for membership in memberships:
        period = membership.get("memberDuring") or {}
        if period.get("endDate"):
            continue
        current.append(
            {
                "organization": membership.get("organization"),
                "role": membership.get("role"),
                "classification": membership.get("membershipClassification"),
                "start_date": period.get("startDate"),
            }
        )
    return current


def _normalize(raw: dict[str, Any], resource: str, language: str, include_raw: bool) -> dict[str, Any]:
    record_id = _identifier(raw)
    record: dict[str, Any] = {
        "resource": resource,
        "id": record_id,
        "entity": raw.get("type"),
        "source_url": _semantic_url(raw),
    }

    if resource in {"meps", "meps_current", "meps_incoming", "meps_outgoing"}:
        memberships = _current_memberships(raw)
        mandate = next(
            (m for m in memberships if m["role"] == "def/ep-roles/MEMBER_PARLIAMENT"),
            {},
        )
        if not mandate:
            mandate = next((m for m in memberships if m["organization"] == "org/ep-10"), {})
        raw_memberships = raw.get("hasMembership") or []
        if isinstance(raw_memberships, dict):
            raw_memberships = [raw_memberships]
        represented = next(
            (
                item.get("represents", [None])[0]
                for item in raw_memberships
                if not (item.get("memberDuring") or {}).get("endDate")
                and item.get("represents")
            ),
            None,
        )
        group = next(
            (
                m["organization"]
                for m in memberships
                if m["classification"] == "def/ep-entities/EU_POLITICAL_GROUP"
            ),
            None,
        )
        represented_code = str(represented).rsplit("/", 1)[-1] if represented else None
        record |= {
            "name": raw.get("label"),
            "first_name": raw.get("givenName"),
            "last_name": raw.get("familyName"),
            "country": raw.get("api:country-of-representation")
            or _EU_COUNTRY_3_TO_2.get(represented_code, represented_code),
            "political_group": raw.get("api:political-group") or group,
            "mandate_start": mandate.get("start_date"),
            "birth_date": raw.get("bday"),
            "gender": str(raw.get("hasGender", "")).rsplit("/", 1)[-1] or None,
            "email": str(raw.get("hasEmail", "")).removeprefix("mailto:") or None,
            "homepage": raw.get("homepage"),
            "image_url": raw.get("img"),
            "current_memberships": memberships,
        }
    elif resource == "speeches":
        participation = raw.get("had_participation") or {}
        record |= {
            "title": _pick(raw.get("activity_label"), language),
            "date": raw.get("activity_date"),
            "start_date": raw.get("activity_start_date"),
            "end_date": raw.get("activity_end_date"),
            "activity_type": raw.get("had_activity_type"),
            "person_ids": participation.get("had_participant_person") or [],
        }
    elif resource == "procedures":
        record |= {
            "procedure_id": raw.get("process_id") or record_id,
            "title": _pick(raw.get("label"), language),
            "procedure_type": raw.get("process_type"),
        }
    elif resource == "vote_results":
        record |= {
            "title": _pick(raw.get("activity_label"), language)
            or _pick(raw.get("label"), language),
            "date": raw.get("activity_date") or raw.get("date"),
            "decision": raw.get("decision") or raw.get("vote_result"),
            "yes": raw.get("number_of_votes_favor"),
            "no": raw.get("number_of_votes_against"),
            "abstention": raw.get("number_of_votes_abstention"),
        }
    else:
        title, files = _document_details(raw, language)
        record |= {
            "title": title or _pick(raw.get("label"), language)
            or _pick(raw.get("activity_label"), language),
            "date": raw.get("document_date") or raw.get("activity_date") or raw.get("date"),
            "parliamentary_term": raw.get("parliamentary_term"),
            "files": files,
        }

    if include_raw:
        record["raw"] = raw
    return record


def _resource(input: dict) -> str:
    resource = input.get("resource")
    if not resource:
        if input.get("mep_id") or input.get("name") or input.get("country") or input.get("political_group"):
            resource = "meps" if input.get("mep_id") else "meps_current"
        elif input.get("sitting_id"):
            resource = "vote_results"
        elif input.get("q") or input.get("text"):
            resource = "speeches"
        else:
            raise ValueError(
                "Europarl needs `resource`, MEP inputs (`name`, `mep_id`, "
                "`country`, `political_group`), `sitting_id`, or `q` (speeches)."
            )
    if resource not in RESOURCE_PATHS:
        raise ValueError(f"Unsupported European Parliament resource `{resource}`.")
    return resource


def _filters(input: dict) -> dict[str, Any]:
    filters = input.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("`filters` must be an object of upstream query parameters.")
    params: dict[str, Any] = {}
    for key, value in filters.items():
        if not _FILTER_RE.match(key) or key in _RESERVED_FILTERS:
            raise ValueError(f"Unsafe or reserved European Parliament filter `{key}`.")
        params[key] = ",".join(str(v) for v in value) if isinstance(value, list) else value
    return params


def _params(input: dict, resource: str, *, limit: int, offset: int) -> dict[str, Any]:
    params = _filters(input)
    params |= {"format": "application/ld+json", "limit": limit, "offset": offset}
    aliases = {
        "country": "country-of-representation",
        "political_group": "political-group",
        "parliamentary_term": "parliamentary-term",
        "mandate_date": "mandate-date",
        "process_type": "process-type",
        "person_id": "person-id",
        "activity_type": "activity-type",
        "sitting_date_start": "sitting-date",
        "sitting_date_end": "sitting-date-end",
        "work_type": "work-type",
        "search_language": "search-language",
        "sort_by": "sort-by",
    }
    for local, upstream in aliases.items():
        if input.get(local) is not None:
            params[upstream] = input[local]
    for key in ("gender", "year", "title", "language"):
        if input.get(key) is not None:
            params[key] = input[key]
    query = input.get("q") or input.get("text")
    if query:
        if resource not in TEXT_SEARCH_RESOURCES:
            raise ValueError(
                f"`{resource}` has no upstream full-text parameter. Use its "
                "documented filters, or choose speeches/adopted_texts/"
                "plenary_session_items/meps_declarations."
            )
        params["text"] = query
        params.setdefault("search-language", input.get("language") or "en")
    return params


def _get(client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = client.get(url, params=params)
    if response.status_code == 204:
        return {"data": []}
    response.raise_for_status()
    payload = response.json()
    if payload.get("error") and not payload.get("data"):
        raise EuroparlResponseError(
            f"European Parliament API embedded an error: {payload['error']}"
        )
    return payload


def _name_search(input: dict, client: httpx.Client, resource: str) -> dict:
    """The API has no MEP-name filter; fetch the filtered current roster once
    and apply a transparent case-insensitive substring match locally."""
    requested_limit = max(1, min(int(input.get("limit", 10)), 50))
    requested_offset = max(0, int(input.get("offset", 0)))
    params = _params(input, resource, limit=1000, offset=0)
    payload = _get(client, f"{API_URL}/{RESOURCE_PATHS[resource]}", params)
    records = payload.get("data") or []
    needle = str(input["name"]).casefold()
    matches = [r for r in records if needle in str(r.get("label", "")).casefold()]
    page_records = matches[requested_offset : requested_offset + requested_limit]
    language = input.get("language") or "en"
    return {
        "source_id": SOURCE_ID,
        "mode": "search",
        "resource": resource,
        "records": [
            _normalize(r, resource, language, bool(input.get("include_raw")))
            for r in page_records
        ],
        "page": {
            "offset": requested_offset,
            "limit": requested_limit,
            "total": len(matches),
            "local_name_filter": True,
        },
        "attribution": "European Parliament Open Data (CC BY 4.0)",
    }


def _request(input: dict, client: httpx.Client) -> dict:
    resource = _resource(input)
    if input.get("name"):
        if resource not in {"meps", "meps_current"}:
            raise ValueError("`name` is only supported for MEP queries.")
        return _name_search(input, client, "meps_current")

    record_id = input.get("id") or input.get("mep_id") or input.get("sitting_id")
    limit = max(1, min(int(input.get("limit", 10)), 50))
    offset = max(0, int(input.get("offset", 0)))
    params = _params(input, resource, limit=limit, offset=offset)
    path = RESOURCE_PATHS[resource]
    if "{id}" in path:
        if record_id is None:
            raise ValueError(f"`{resource}` needs `sitting_id` or `id`.")
        path = path.format(id=record_id)
        mode = "relation"
    elif record_id is not None:
        if resource in {"meps_current", "meps_incoming", "meps_outgoing"}:
            raise ValueError(f"`{resource}` does not have an item-detail endpoint.")
        path = f"{path}/{record_id}"
        mode = "detail"
    else:
        mode = "search" if input.get("q") or input.get("text") else "list"

    payload = _get(client, f"{API_URL}/{path}", params)
    raw_records = payload.get("data") or []
    if isinstance(raw_records, dict):
        raw_records = [raw_records]
    language = input.get("language") or "en"
    meta = payload.get("meta") or {}
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "resource": resource,
        "records": [
            _normalize(r, resource, language, bool(input.get("include_raw")))
            for r in raw_records
        ],
        "page": {"offset": offset, "limit": limit, "total": meta.get("total")},
        "attribution": "European Parliament Open Data (CC BY 4.0)",
    }


def run(input: dict, ctx) -> dict:
    del ctx  # public API; retained for the standard adapter contract
    headers = {"User-Agent": "BuriedSignals-DataNavigator-0.1"}
    with httpx.Client(headers=headers, timeout=45, follow_redirects=True) as client:
        return _request(input, client)
