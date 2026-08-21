"""Bounded SEC EDGAR full-text search through the live EFTS web backend.

The SEC documents the Full-Text Search user interface and query semantics, but
does not list efts.sec.gov/LATEST/search-index among its supported public JSON
APIs. Treat this adapter as a monitored UI-backend integration, not a stable
versioned API contract.
"""

from __future__ import annotations

from datetime import date
import os
from typing import Any

import httpx

ENDPOINT = "https://efts.sec.gov/LATEST/search-index"
SOURCE_ID = "us/sec-edgar/filings"
DEFAULT_UA = "Buried Signals catalogue@buriedsignals.com"


def _integer(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer from {minimum} to {maximum}.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be an integer from {minimum} to {maximum}."
        ) from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be an integer from {minimum} to {maximum}.")
    return number


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date in YYYY-MM-DD form.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date in YYYY-MM-DD form.") from exc
    return parsed.isoformat()


def _cik(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.lstrip("0") or "0"


def _normalize(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit.get("_source") or {}
    hit_id = str(hit.get("_id") or "")
    accession = source.get("adsh") or (
        hit_id.split(":", 1)[0] if ":" in hit_id else hit_id
    )
    filename = hit_id.split(":", 1)[1] if ":" in hit_id else None
    ciks = [value for value in (_cik(item) for item in source.get("ciks") or []) if value]
    filers = source.get("display_names") or []
    source_url = None
    if ciks and accession and filename:
        source_url = (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{ciks[0]}/{str(accession).replace('-', '')}/{filename}"
        )
    return {
        "entity": "FilingDocument",
        "name": filers[0] if filers else None,
        "form": source.get("form"),
        "root_forms": source.get("root_forms") or [],
        "filer": filers[0] if filers else None,
        "filers": filers,
        "cik": ciks[0] if ciks else None,
        "ciks": ciks,
        "accession": accession,
        "filed_date": source.get("file_date"),
        "period": source.get("period_ending"),
        "location": (source.get("biz_locations") or [None])[0],
        "locations": source.get("biz_locations") or [],
        "business_states": source.get("biz_states") or [],
        "incorporation_states": source.get("inc_states") or [],
        "sic_codes": source.get("sics") or [],
        "file_numbers": source.get("file_num") or [],
        "film_numbers": source.get("film_num") or [],
        "items": source.get("items") or [],
        "sequence": source.get("sequence"),
        "document_filename": filename,
        "file_type": source.get("file_type"),
        "file_description": source.get("file_description"),
        "relevance_score": hit.get("_score"),
        "source_url": source_url,
    }


def run(input: dict, ctx) -> dict:
    query = input.get("q") or input.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("q is required and must be a non-empty full-text query.")

    start = input.get("startdt")
    end = input.get("enddt")
    if (start is None) != (end is None):
        raise ValueError("startdt and enddt must be supplied together.")
    if start is not None:
        start = _date(start, "startdt")
        end = _date(end, "enddt")
        if start > end:
            raise ValueError("startdt must be on or before enddt.")

    limit = _integer(input.get("limit", 10), "limit", minimum=1, maximum=100)
    offset = _integer(input.get("offset", 0), "offset", minimum=0, maximum=9900)
    params: dict[str, Any] = {"q": query.strip(), "from": offset}
    forms = input.get("forms")
    if forms not in (None, ""):
        if not isinstance(forms, str):
            raise ValueError("forms must be a comma-separated string.")
        normalized_forms = ",".join(
            part.strip() for part in forms.split(",") if part.strip()
        )
        if not normalized_forms:
            raise ValueError("forms must include at least one form type.")
        params["forms"] = normalized_forms
    if start is not None:
        params["startdt"] = start
        params["enddt"] = end

    user_agent = os.getenv("catalogue_SEC_UA", DEFAULT_UA).strip()
    if not user_agent:
        raise ValueError("catalogue_SEC_UA must identify the requester and contact.")
    response = httpx.get(
        ENDPOINT,
        params=params,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    hits_object = data.get("hits") or {}
    upstream_hits = hits_object.get("hits") or []
    hits = upstream_hits[:limit]
    total_object = hits_object.get("total")
    if isinstance(total_object, dict):
        total = total_object.get("value")
        total_relation = total_object.get("relation")
    else:
        total = total_object
        total_relation = None
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(hit) for hit in hits],
        "page": {
            "offset": offset,
            "limit": limit,
            "returned": len(hits),
            "upstream_returned": len(upstream_hits),
            "total": total,
            "total_relation": total_relation,
        },
        "query": {
            "q": query.strip(),
            "forms": params.get("forms"),
            "startdt": start,
            "enddt": end,
        },
    }
