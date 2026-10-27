"""Adapter for us/lda/lobbying-disclosures — US Lobbying Disclosure Act filings.

Reads the LDA.gov REST API (LD-1/LD-2 filings and LD-203 contribution reports)
and emits rows shaped like the lobbying domain contract (domains/lobbying.yaml):
each operation fills one contract table and every record carries exactly that
table's columns, so rows can be written straight to a CSV for anomaly.oneshot.
An API key is optional; anonymous requests are throttled to 15 per minute.
"""

from __future__ import annotations

import time

import httpx

API_URL = "https://lda.gov/api/v1"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
MAX_PAGES = 40
MAX_RETRY_AFTER = 60

# Quarter codes sort in calendar order, which the detectors' window functions
# rely on; the API's own values ("first_quarter", "fourth_quarter", ...) do not.
PERIODS = {
    "first_quarter": "Q1", "second_quarter": "Q2", "third_quarter": "Q3", "fourth_quarter": "Q4",
    "mid_year": "H1", "year_end": "H2",
}
FILING_FILTERS = ("registrant_name", "registrant_id", "client_name", "client_id",
                  "filing_year", "filing_period", "filing_type", "filing_uuid")
CONTRIBUTION_FILTERS = ("registrant_name", "registrant_id", "filing_year", "filing_period",
                        "filing_uuid", "lobbyist_name", "contribution_payee", "contribution_honoree")


def _number(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text(value):
    return (value.strip() or None) if isinstance(value, str) else value


def _filing(f: dict) -> dict:
    registrant, client = f.get("registrant") or {}, f.get("client") or {}
    return {
        "filing_uuid": f.get("filing_uuid"),
        "filing_year": f.get("filing_year"),
        "filing_period": PERIODS.get(f.get("filing_period"), f.get("filing_period")),
        "filing_type": f.get("filing_type"),
        "registrant_id": registrant.get("id"),
        "registrant_name": registrant.get("name"),
        "client_id": client.get("id"),
        "client_name": client.get("name"),
        "client_country": _text(client.get("country")),
        "client_ppb_country": _text(client.get("ppb_country")),
        "client_general_description": _text(client.get("general_description")),
        "income": _number(f.get("income")),
        "url": f.get("filing_document_url"),
        "posted_by_name": f.get("posted_by_name"),
    }


def _foreign_entities(f: dict) -> list[dict]:
    return [{
        "filing_uuid": f.get("filing_uuid"),
        "foreign_entity_name": entity.get("name"),
        "country": _text(entity.get("country")),
        "ppb_country": _text(entity.get("ppb_country")),
    } for entity in f.get("foreign_entities") or []]


def _activities(f: dict) -> list[dict]:
    return [{
        "filing_uuid": f.get("filing_uuid"),
        "general_issue_code": activity.get("general_issue_code"),
        "description": _text(activity.get("description")),
        "activity_index": index,
    } for index, activity in enumerate(f.get("lobbying_activities") or [])]


def _lobbyists(f: dict) -> list[dict]:
    """One row per lobbyist and disclosed position on a filing, across its activities."""
    rows, seen = [], set()
    for activity in f.get("lobbying_activities") or []:
        for entry in activity.get("lobbyists") or []:
            person = entry.get("lobbyist") or {}
            position = _text(entry.get("covered_position"))
            key = (person.get("id"), position)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "filing_uuid": f.get("filing_uuid"),
                "lobbyist_id": person.get("id"),
                "first_name": person.get("first_name"),
                "last_name": person.get("last_name"),
                "covered_position": position,
            })
    return rows


def _contributions(report: dict) -> list[dict]:
    return [{
        "filing_uuid": report.get("filing_uuid"),
        "payee_name": _text(item.get("payee_name")),
        "honoree_name": _text(item.get("honoree_name")),
        "amount": _number(item.get("amount")),
        "contributor_name": _text(item.get("contributor_name")),
        "date": item.get("date"),
        "contribution_type": item.get("contribution_type"),
    } for item in report.get("contribution_items") or []]


OPERATIONS = {
    "lobbying-filings": ("filings", FILING_FILTERS, lambda f: [_filing(f)]),
    "lobbying-foreign-entities": ("filings", FILING_FILTERS, _foreign_entities),
    "lobbying-activities": ("filings", FILING_FILTERS, _activities),
    "lobbying-activity-lobbyists": ("filings", FILING_FILTERS, _lobbyists),
    "lobbying-contributions": ("contributions", CONTRIBUTION_FILTERS, _contributions),
}


def _params(input: dict, allowed: tuple[str, ...]) -> dict:
    params = {}
    for name in allowed:
        value = input.get(name)
        if value in (None, ""):
            continue
        if name in {"filing_year", "registrant_id", "client_id"}:
            if isinstance(value, bool) or not str(value).isdigit():
                raise ValueError(f"{name} must be a positive integer.")
            value = int(value)
        elif not isinstance(value, str):
            raise ValueError(f"{name} must be a string.")
        params[name] = value
    if not params:
        raise ValueError(f"name at least one filter: {', '.join(allowed)}.")
    return params


def _get(client, url: str, params: dict | None) -> dict:
    """GET one page, waiting once on a 429 when the API asks for a short pause."""
    response = client.get(url, params=params)
    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", MAX_RETRY_AFTER + 1))
        if wait > MAX_RETRY_AFTER:
            response.raise_for_status()
        time.sleep(wait)
        response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _headers(ctx) -> dict:
    headers = {"Accept": "application/json", "User-Agent": UA}
    key = ctx.get_key_optional("lda") if ctx is not None and hasattr(ctx, "get_key_optional") else None
    if key:
        headers["Authorization"] = f"Token {key}"
    return headers


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "lobbying-filings")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    endpoint, allowed, rows = OPERATIONS[operation]
    params = _params(input, allowed) | {"page_size": 25}
    pages = input.get("pages", 1)
    if isinstance(pages, bool) or not isinstance(pages, int) or not 1 <= pages <= MAX_PAGES:
        raise ValueError(f"pages must be an integer from 1 to {MAX_PAGES}.")
    if input.get("page") is not None:
        params["page"] = int(input["page"])
    records, fetched = [], 0
    url, query = f"{API_URL}/{endpoint}/", params
    with httpx.Client(headers=_headers(ctx), timeout=60, follow_redirects=True) as client:
        while url and fetched < pages:
            data = _get(client, url, query)
            fetched += 1
            for item in data.get("results") or []:
                records.extend(rows(item))
            url, query = data.get("next"), None
    return {"records": records, "page": {"pages_fetched": fetched, "count": data.get("count"),
                                         "next": url, "returned": len(records)}}
