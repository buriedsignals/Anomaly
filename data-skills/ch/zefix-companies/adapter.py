"""Adapter for the live legacy public Zefix company-name endpoint.

The current published ZefixPublicREST specification describes a different,
Basic-authenticated API.  Keep this endpoint distinction visible in the skill
reference instead of implying that the legacy route is currently documented.
"""

from __future__ import annotations

import httpx

ENDPOINT = "https://www.zefix.ch/ZefixREST/api/v1/firm/search.json"
SOURCE_ID = "ch/zefix/companies"
STATUS = {
    "EXISTIEREND": "active",
    "GELOESCHT": "deleted",
    "IN_LIQUIDATION": "in_liquidation",
    "IN_AUFLOESUNG": "in_dissolution",
}


def _normalize(f: dict) -> dict:
    ehraid = f.get("ehraid")
    return {
        "entity": "Company",
        "name": f.get("name"),
        "jurisdiction": "ch",
        "uid": f.get("uidFormatted") or f.get("uid"),
        "chid": f.get("chidFormatted") or f.get("chid"),
        "legal_seat": f.get("legalSeat"),
        "status": STATUS.get(f.get("status"), f.get("status")),
        "shab_date": f.get("shabDate"),
        "registry_url": f.get("cantonalExcerptWeb"),
        "source_url": f"https://www.zefix.ch/en/search/entity/list/firm/{ehraid}" if ehraid else None,
    }


def run(input: dict, ctx) -> dict:
    q = input.get("name") or input.get("q") or input.get("query")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("name is required (company name to search).")
    language = input.get("language", "en")
    if language not in {"de", "en", "fr", "it"}:
        raise ValueError("language must be one of: de, en, fr, it")
    body = {"name": q.strip(), "languageKey": language}
    resp = httpx.post(
        ENDPOINT,
        json=body,
        headers={"User-Agent": "BuriedSignals-catalogue/1.0", "Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code == 404:
        try:
            error_code = resp.json().get("error", {}).get("code")
        except (AttributeError, ValueError):
            error_code = None
        if error_code == "API.ZFR.SEARCH.NORESULT":
            payload = {"list": [], "hasMoreResults": False}
        else:
            resp.raise_for_status()
    else:
        resp.raise_for_status()
        payload = resp.json()
    firms = payload.get("list") or []
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(f) for f in firms],
        "page": {
            "returned": len(firms),
            "has_more_results": payload.get("hasMoreResults"),
            "offset": payload.get("offset"),
            "max_entries": payload.get("maxEntries"),
        },
    }
