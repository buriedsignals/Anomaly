"""Adapter for gb/find-a-tender/notices — UK Find a Tender Service (OCDS).

FTS publishes UK public procurement above-threshold notices as an OCDS 1.1
release feed. The feed is paginated by date, NOT keyword-searchable — so this
adapter pulls a recent window and, if `q` is given, filters it client-side.
Public, no key.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx

ENDPOINT = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
SOURCE_ID = "gb/find-a-tender/notices"
_CURSOR_RE = re.compile(r"^[A-Za-z0-9=]{1,300}$")
_STAGES = {"planning", "tender", "award"}


def _doc_url(release: dict) -> str | None:
    for section in ("tender", "planning"):
        for doc in ((release.get(section) or {}).get("documents") or []):
            if doc.get("url"):
                return doc["url"]
    return None


def _normalize(r: dict) -> dict:
    tender = r.get("tender") or {}
    buyer = r.get("buyer") or {}
    value = tender.get("value") or {}
    return {
        "entity": "TenderNotice",
        "name": tender.get("title"),
        "jurisdiction": "gb",
        "ocid": r.get("ocid"),
        "release_id": r.get("id"),
        "buyer": buyer.get("name"),
        "description": tender.get("description"),
        "value_amount": value.get("amount"),
        "value_currency": value.get("currency"),
        "status": tender.get("status"),
        "date": r.get("date"),
        "tags": r.get("tag"),
        "source_url": (f"{ENDPOINT}/{r['id']}" if r.get("id") else _doc_url(r)),
    }


def _datetime(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must use YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DDTHH:MM:SS") from exc
    return value


def _next_cursor(next_url: object) -> str | None:
    if not isinstance(next_url, str):
        return None
    values = parse_qs(urlparse(next_url).query).get("cursor") or []
    return values[0] if values else None


def run(input: dict, ctx) -> dict:
    q = input.get("q") or input.get("query")
    if q is not None and (not isinstance(q, str) or not q.strip()):
        raise ValueError("q must be a non-empty string when supplied")
    if isinstance(q, str):
        q = q.strip()
    limit = max(1, min(int(input.get("limit", 10)), 100))
    # Fetch a wider slice to filter down when a term is given.
    params = {"limit": min(100, limit * 5) if q else limit}
    updated_from = _datetime(input.get("updatedFrom"), "updatedFrom")
    updated_to = _datetime(input.get("updatedTo"), "updatedTo")
    if updated_from and updated_to and updated_from > updated_to:
        raise ValueError("updatedFrom must not be after updatedTo")
    if updated_from:
        params["updatedFrom"] = updated_from
    if updated_to:
        params["updatedTo"] = updated_to
    stage = input.get("stage")
    if stage is not None:
        if stage not in _STAGES:
            raise ValueError("stage must be one of: planning, tender, award")
        params["stages"] = stage
    cursor = input.get("cursor")
    if cursor is not None:
        if not isinstance(cursor, str) or not _CURSOR_RE.fullmatch(cursor):
            raise ValueError("cursor is not a valid Find a Tender cursor")
        params["cursor"] = cursor
    resp = httpx.get(
        ENDPOINT,
        params=params,
        headers={"User-Agent": "BuriedSignals-Navigator/1.0"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    releases = payload.get("releases", [])

    if q:
        needle = q.lower()
        releases = [
            r
            for r in releases
            if needle in json.dumps(r.get("tender") or {}, ensure_ascii=False).lower()
            or needle in ((r.get("buyer") or {}).get("name") or "").lower()
        ]
    releases = releases[:limit]
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(r) for r in releases],
        "page": {
            "returned": len(releases),
            "filtered_by": q or None,
            "stage": stage,
            "next_cursor": _next_cursor((payload.get("links") or {}).get("next")),
            "next_url": (payload.get("links") or {}).get("next"),
            "published_date": payload.get("publishedDate"),
        },
    }
