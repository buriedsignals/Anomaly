"""Adapter for us/lda/lobbying-disclosures — US Lobbying Disclosure Act filings.

Reads the LDA.gov REST API (LD-1/LD-2 filings and LD-203 contribution reports)
and emits rows shaped like the lobbying domain contract (domains/lobbying.yaml):
each operation fills one contract table (the generic lobbying_registrations and
lobbyists, or a US extension table) and every record carries that table's
columns, so rows can be written straight to a CSV for anomaly.oneshot. The
LDA-to-contract column mapping is documented in SKILL.md.
An API key is optional; anonymous requests are throttled to 15 per minute.
"""

from __future__ import annotations

import time

import httpx

API_URL = "https://lda.gov/api/v1"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
MAX_PAGES = 40
MAX_RETRY_AFTER = 60

SOURCE_ID = "us/lda/lobbying-disclosures"
# Reporting periods as (first day, last day) within the filing year.
PERIODS = {
    "first_quarter": ("01-01", "03-31"), "second_quarter": ("04-01", "06-30"),
    "third_quarter": ("07-01", "09-30"), "fourth_quarter": ("10-01", "12-31"),
    "mid_year": ("01-01", "06-30"), "year_end": ("07-01", "12-31"),
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


def _period(f: dict) -> tuple[str | None, str | None]:
    year = f.get("filing_year")
    if not year:
        return None, None
    start, end = PERIODS.get(f.get("filing_period"), ("01-01", "12-31"))
    return f"{year}-{start}", f"{year}-{end}"


def _registration(f: dict) -> dict:
    registrant, client = f.get("registrant") or {}, f.get("client") or {}
    # A registrant filing for itself has no separate client (contract rule).
    own = bool(client.get("client_self_select"))
    # Outside firms report income from the client; self-filers report expenses.
    spend = _number(f.get("income"))
    spend = _number(f.get("expenses")) if spend is None else spend
    codes = dict.fromkeys(a.get("general_issue_code") for a in f.get("lobbying_activities") or [])
    period_start, period_end = _period(f)
    return {
        "registration_id": f.get("filing_uuid"),
        "register": SOURCE_ID,
        "period_start": period_start,
        "period_end": period_end,
        "registrant_id": registrant.get("id"),
        "registrant_name": registrant.get("name"),
        "client_id": None if own else client.get("id"),
        "client_name": None if own else client.get("name"),
        "client_country": _text(client.get("country")),
        "spend_low": spend,
        "spend_high": spend,
        "issue_area": "|".join(code for code in codes if code) or None,
        "filing_type": f.get("filing_type"),
        "url": f.get("filing_document_url"),
        "client_description": _text(client.get("general_description")),
        "client_ppb_country": _text(client.get("ppb_country")),
        "posted_by_name": f.get("posted_by_name"),
    }


def _foreign_entities(f: dict) -> list[dict]:
    return [{
        "registration_id": f.get("filing_uuid"),
        "foreign_entity_name": entity.get("name"),
        "country": _text(entity.get("country")),
        "ppb_country": _text(entity.get("ppb_country")),
    } for entity in f.get("foreign_entities") or []]


def _activities(f: dict) -> list[dict]:
    return [{
        "registration_id": f.get("filing_uuid"),
        "general_issue_code": activity.get("general_issue_code"),
        "description": _text(activity.get("description")),
        "activity_index": index,
    } for index, activity in enumerate(f.get("lobbying_activities") or [])]


def _lobbyists(f: dict) -> list[dict]:
    """One row per lobbyist and disclosed covered position on a filing, across its activities."""
    rows, seen = [], set()
    for activity in f.get("lobbying_activities") or []:
        for entry in activity.get("lobbyists") or []:
            person = entry.get("lobbyist") or {}
            position = _text(entry.get("covered_position"))
            key = (person.get("id"), position)
            if key in seen:
                continue
            seen.add(key)
            name = " ".join(part for part in (person.get("first_name"), person.get("last_name")) if part)
            rows.append({
                "registration_id": f.get("filing_uuid"),
                "lobbyist_id": person.get("id"),
                "name": name or None,
                "former_public_office": position,
                # LDA covered positions are free text with no institution or end date.
                "former_office_institution": None,
                "former_office_end": None,
            })
    return rows


def _contributions(report: dict) -> list[dict]:
    return [{
        "registration_id": report.get("filing_uuid"),
        "payee_name": _text(item.get("payee_name")),
        "honoree_name": _text(item.get("honoree_name")),
        "amount": _number(item.get("amount")),
        "contributor_name": _text(item.get("contributor_name")),
        "date": item.get("date"),
        "contribution_type": item.get("contribution_type"),
    } for item in report.get("contribution_items") or []]


OPERATIONS = {
    "lobbying-registrations": ("filings", FILING_FILTERS, lambda f: [_registration(f)]),
    "lobbyists": ("filings", FILING_FILTERS, _lobbyists),
    "lobbying-foreign-entities": ("filings", FILING_FILTERS, _foreign_entities),
    "lobbying-activities": ("filings", FILING_FILTERS, _activities),
    "political-contributions": ("contributions", CONTRIBUTION_FILTERS, _contributions),
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
    operation = input.get("operation", "lobbying-registrations")
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
