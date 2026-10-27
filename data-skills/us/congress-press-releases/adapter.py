"""Adapter for us/congress-press/press-releases — members' press releases.

Reads one month of the Congress Press collection (dwillis/congress-press on
GitHub: JSONL files of press releases scraped daily from official House and
Senate websites, with full text and bioguide IDs) and fills the lobbying
contract table ``press_releases``. A month file is about 17 MB; the adapter
streams it and filters by member and text locally.
"""

from __future__ import annotations

import json
import re

import httpx

DATA_URL = "https://raw.githubusercontent.com/dwillis/congress-press/main/data"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MAX_LIMIT = 5000


def _record(release: dict) -> dict:
    member = release.get("member") or {}
    return {
        "bioguide_id": member.get("bioguide_id"),
        "date": release.get("date"),
        "member_name": member.get("name"),
        "text": release.get("text"),
        "title": release.get("title"),
        "url": release.get("url"),
    }


def run(input: dict, ctx) -> dict:
    month = input.get("month")
    match = MONTH.match(month) if isinstance(month, str) else None
    if not match:
        raise ValueError("month is required as YYYY-MM.")
    bioguide = input.get("bioguide_id") or ""
    q = input.get("q") or input.get("query") or ""
    if not isinstance(bioguide, str) or not isinstance(q, str):
        raise ValueError("bioguide_id and q must be strings.")
    limit = input.get("limit", 500)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    bioguide, needle = bioguide.strip().upper(), q.strip().casefold()
    records, scanned = [], 0
    url = f"{DATA_URL}/{match.group(1)}/{month}.jsonl"
    with httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                scanned += 1
                record = _record(json.loads(line))
                if bioguide and record["bioguide_id"] != bioguide:
                    continue
                if needle and needle not in f"{record['title'] or ''} {record['text'] or ''}".casefold():
                    continue
                records.append(record)
                if len(records) >= limit:
                    break
    return {"records": records, "page": {"scanned": scanned, "returned": len(records), "limit": limit}}
