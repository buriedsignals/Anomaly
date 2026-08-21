"""Adapter for global/gdelt/news — GDELT DOC 2.0 article search (public, no key).

GDELT indexes worldwide news in ~100 languages. This is the DOC 2.0 article-list
mode: full-text query → recent matching articles with domain/language/country.

The adapter makes one request and, only when GDELT returns its explicit
one-request-per-five-seconds 429 response, waits once and retries once.
"""

from __future__ import annotations

import re
import time
from datetime import datetime

import httpx

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
SOURCE_ID = "global/gdelt/news"
SORT_VALUES = {"DateDesc", "DateAsc", "ToneDesc", "ToneAsc", "HybridRel"}
DATETIME_RE = re.compile(r"^[0-9]{14}$")
TIMESPAN_RE = re.compile(r"^(?P<count>[0-9]+)(?P<unit>min|h|hours|d|days|w|weeks|m|months)$")


def _normalize(a: dict) -> dict:
    return {
        "entity": "Article",
        "name": a.get("title"),
        "url": a.get("url"),
        "domain": a.get("domain"),
        "language": a.get("language"),
        "source_country": a.get("sourcecountry"),
        "seen_date": a.get("seendate"),
        "social_image": a.get("socialimage"),
        "source_url": a.get("url"),
    }


def run(input: dict, ctx) -> dict:
    query = input.get("query") or input.get("q")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required (GDELT full-text query — a name, phrase, or boolean).")
    query = query.strip()
    maxrecords = int(input.get("maxrecords", input.get("size", 25)))
    if not 1 <= maxrecords <= 250:
        raise ValueError("maxrecords must be between 1 and 250.")
    sort = input.get("sort", "DateDesc")
    if sort not in SORT_VALUES:
        raise ValueError(f"sort must be one of: {', '.join(sorted(SORT_VALUES))}.")
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": maxrecords,
        "sort": sort,
    }
    # The provider accepts either boundary independently. A precise range and
    # a relative timespan are alternative scopes, never silently combined.
    start = input.get("startdatetime")
    end = input.get("enddatetime")
    if (start is not None or end is not None) and input.get("timespan") is not None:
        raise ValueError("Use startdatetime/enddatetime or timespan, not both.")
    for field, value in (("startdatetime", start), ("enddatetime", end)):
        if value is not None:
            if not isinstance(value, str) or not DATETIME_RE.fullmatch(value):
                raise ValueError(f"{field} must use YYYYMMDDHHMMSS.")
            params[field] = value
    if start and end:
        if datetime.strptime(start, "%Y%m%d%H%M%S") > datetime.strptime(end, "%Y%m%d%H%M%S"):
            raise ValueError("startdatetime must not be after enddatetime.")
    if start is None and end is None:
        timespan = input.get("timespan", "1w")
        if not isinstance(timespan, str):
            raise ValueError("timespan must be a provider duration such as 15min, 1d, or 1w.")
        match = TIMESPAN_RE.fullmatch(timespan.strip())
        if not match:
            raise ValueError("timespan must be a provider duration such as 15min, 1d, or 1w.")
        if match.group("unit") == "min" and int(match.group("count")) < 15:
            raise ValueError("GDELT timespan has a 15-minute minimum.")
        params["timespan"] = timespan.strip()

    request_kwargs = {
        "params": params,
        "headers": {"User-Agent": "buriedsignals-navigator/1.0"},
        "timeout": 30,
    }
    resp = httpx.get(ENDPOINT, **request_kwargs)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
        try:
            delay = float(retry_after) if retry_after is not None else 5.5
        except ValueError:
            delay = 5.5
        # The live provider message specifies one request per five seconds.
        # Avoid an unbounded sleep if a proxy supplies an unexpectedly large
        # Retry-After; the caller can schedule a later attempt instead.
        if 0 <= delay <= 30:
            time.sleep(max(delay, 5.5))
            resp = httpx.get(ENDPOINT, **request_kwargs)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:
        # GDELT returns a plain-text error (not JSON) for a malformed/too-broad
        # query — surface it as a clean upstream error, not a JSON parse crash.
        raise httpx.HTTPError(
            f"GDELT did not return JSON (query too broad or malformed?): {resp.text[:200]}"
        ) from exc
    articles = data.get("articles", [])
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(a) for a in articles],
        "page": {
            "maxrecords": params["maxrecords"],
            "returned": len(articles),
            "sort": params["sort"],
            "timespan": params.get("timespan"),
            "startdatetime": params.get("startdatetime"),
            "enddatetime": params.get("enddatetime"),
        },
    }
