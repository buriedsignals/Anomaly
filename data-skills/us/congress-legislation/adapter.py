"""Adapter for us/congress/legislation — Congress.gov bills & members (BYO key).

Official Library of Congress API (api.congress.gov v3). Two ops in one adapter:
bill search (default) and member lookup (mode=members). Replaces the retired
ProPublica Congress API for basic legislative tracking.

Upstream quirk this adapter owns: the v3 API has NO server-side full-text
search (a `query` param is silently ignored). `q` is therefore a client-side
title filter applied over the most-recently-updated bills (fetch window 250).
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

import httpx

API_URL = "https://api.congress.gov/v3"
SOURCE_ID = "us/congress/legislation"

_PAGE_MAX = 250  # upstream hard cap per request
_MEMBER_SCAN_PAGES = 4
_BIOGUIDE_RE = re.compile(r"^[A-Z][0-9]{6}$")

# congress.gov web-URL slugs per bill type (stable, documented set).
_BILL_TYPE_SLUGS = {
    "HR": "house-bill",
    "S": "senate-bill",
    "HRES": "house-resolution",
    "SRES": "senate-resolution",
    "HJRES": "house-joint-resolution",
    "SJRES": "senate-joint-resolution",
    "HCONRES": "house-concurrent-resolution",
    "SCONRES": "senate-concurrent-resolution",
}


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _bill_url(b: dict[str, Any]) -> str | None:
    """Human congress.gov page; fall back to the record's API url."""
    slug = _BILL_TYPE_SLUGS.get((b.get("type") or "").upper())
    congress, number = b.get("congress"), b.get("number")
    if slug and congress and number:
        return f"https://www.congress.gov/bill/{_ordinal(int(congress))}-congress/{slug}/{number}"
    return b.get("url")


def _normalize_bill(b: dict[str, Any]) -> dict[str, Any]:
    latest = b.get("latestAction") or {}
    bill_type, number = b.get("type"), b.get("number")
    return {
        "entity": "Bill",
        "name": b.get("title"),
        "bill": f"{bill_type} {number}" if bill_type and number else None,
        "bill_type": bill_type,
        "bill_number": number,
        "congress": b.get("congress"),
        "chamber": b.get("originChamber"),
        "latest_action_date": latest.get("actionDate"),
        "latest_action": latest.get("text"),
        "updated": b.get("updateDate"),
        "updated_including_text": b.get("updateDateIncludingText"),
        "source_url": _bill_url(b),
    }


def _normalize_member(m: dict[str, Any]) -> dict[str, Any]:
    """One seam for both member shapes: the list endpoint (partyName at top,
    terms = {"item": [...]}) and the detail endpoint (partyHistory list,
    terms = [...])."""
    terms = m.get("terms")
    term_items = terms.get("item") if isinstance(terms, dict) else (terms or [])
    term_items = [item for item in term_items if isinstance(item, dict)]
    last_term = term_items[-1] if term_items else {}
    party = m.get("partyName")
    party_history = m.get("partyHistory") or []
    if not party and party_history:
        party = party_history[-1].get("partyName")
    bioguide = m.get("bioguideId")
    return {
        "entity": "Member",
        "name": m.get("invertedOrderName") or m.get("name"),
        "bioguide_id": bioguide,
        "party": party,
        "state": m.get("state"),
        "district": m.get("district"),
        "chamber": last_term.get("chamber"),
        "current_member": m.get("currentMember"),
        "birth_year": m.get("birthYear"),
        "death_year": m.get("deathYear"),
        "official_website": m.get("officialWebsiteUrl"),
        "terms": [
            {
                "chamber": term.get("chamber"),
                "congress": term.get("congress"),
                "start_year": term.get("startYear"),
                "end_year": term.get("endYear"),
                "state_code": term.get("stateCode"),
                "state_name": term.get("stateName"),
                "district": term.get("district"),
                "member_type": term.get("memberType"),
            }
            for term in term_items
        ],
        "updated": m.get("updateDate"),
        "source_url": (
            f"https://bioguide.congress.gov/search/bio/{bioguide}" if bioguide else None
        ),
    }


def _member_state_code(member: dict[str, Any]) -> str:
    state = str(member.get("state") or "").upper()
    if len(state) == 2:
        return state
    terms = member.get("terms")
    items = terms.get("item") if isinstance(terms, dict) else (terms or [])
    if items and isinstance(items[-1], dict):
        return str(items[-1].get("stateCode") or "").upper()
    return ""


def _mode(input: dict) -> str:
    mode = input.get("mode")
    if mode:
        if mode not in ("bills", "members"):
            raise ValueError(f"Unknown mode `{mode}` — use bills or members.")
        return mode
    if any(input.get(k) for k in ("bioguide_id", "state", "name")):
        return "members"
    return "bills"


def _limit(input: dict) -> int:
    value = input.get("limit", 10)
    if isinstance(value, bool):
        raise ValueError("limit must be an integer from 1 to 250.")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer from 1 to 250.") from exc
    if not 1 <= value <= _PAGE_MAX:
        raise ValueError("limit must be an integer from 1 to 250.")
    return value


def _congress(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("congress must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("congress must be a positive integer.") from exc
    if number < 1:
        raise ValueError("congress must be a positive integer.")
    return number


def _current_congress(today: date | None = None) -> int:
    """Congress numbers advance every odd-numbered year on January 3."""
    today = today or date.today()
    number = ((today.year - 1789) // 2) + 1
    if today.year % 2 == 1 and (today.month, today.day) < (1, 3):
        number -= 1
    return number


def _scan_congress_members(
    client: httpx.Client, congress: int, *, current_only: bool
) -> tuple[list[dict[str, Any]], int | None]:
    members: list[dict[str, Any]] = []
    total: int | None = None
    for page in range(_MEMBER_SCAN_PAGES):
        resp = client.get(
            f"{API_URL}/member/congress/{congress}",
            params={
                "currentMember": "true" if current_only else "false",
                "limit": _PAGE_MAX,
                "offset": page * _PAGE_MAX,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("members", [])
        members.extend(batch)
        total = (data.get("pagination") or {}).get("count")
        if len(batch) < _PAGE_MAX:
            break
    return members, total


def _bills(input: dict, client: httpx.Client) -> dict:
    q = input.get("q") or input.get("query")
    limit = _limit(input)
    path = (
        f"/bill/{_congress(input['congress'])}"
        if input.get("congress") is not None
        else "/bill"
    )
    params = {
        "sort": "updateDate desc",
        # No server-side search upstream: when filtering client-side, widen the
        # fetch window to the max page so `q` scans 250 bills, not `limit`.
        "limit": _PAGE_MAX if q else limit,
    }
    resp = client.get(f"{API_URL}{path}", params=params)
    resp.raise_for_status()
    data = resp.json()
    bills = data.get("bills", [])
    if q:
        needle = q.lower()
        bills = [b for b in bills if needle in (b.get("title") or "").lower()]
    return {
        "source_id": SOURCE_ID,
        "mode": "bills",
        "records": [_normalize_bill(b) for b in bills[:limit]],
        "page": {
            "limit": limit,
            "total": (data.get("pagination") or {}).get("count"),
            "filtered_client_side": bool(q),
        },
    }


def _members(input: dict, client: httpx.Client) -> dict:
    limit = _limit(input)
    if input.get("bioguide_id"):
        bioguide = str(input["bioguide_id"]).upper()
        if not _BIOGUIDE_RE.fullmatch(bioguide):
            raise ValueError("bioguide_id must be one letter followed by six digits.")
        resp = client.get(f"{API_URL}/member/{bioguide}", params={})
        resp.raise_for_status()
        member = resp.json().get("member") or {}
        return {
            "source_id": SOURCE_ID,
            "mode": "members",
            "records": [_normalize_member(member)],
            "page": {},
        }

    name = str(input.get("name") or "").strip().lower()
    state = str(input.get("state") or "").strip().upper()
    if state and (len(state) != 2 or not state.isalpha()):
        raise ValueError("state must be a two-letter US state or territory code.")
    members: list[dict] = []
    total = None
    queried_congress: int | None = None
    if state and not input.get("congress"):
        resp = client.get(
            f"{API_URL}/member/{state}",
            params={"currentMember": "true", "limit": _PAGE_MAX},
        )
        resp.raise_for_status()
        data = resp.json()
        members = data.get("members", [])
        total = (data.get("pagination") or {}).get("count")
    else:
        # The unscoped /member list does not support filters. Scope name and
        # historical searches to a Congress, then filter the bounded result.
        queried_congress = (
            _congress(input["congress"])
            if input.get("congress") is not None
            else _current_congress()
        )
        current = queried_congress == _current_congress()
        members, total = _scan_congress_members(
            client, queried_congress, current_only=current
        )
    if name:
        members = [m for m in members if name in (m.get("name") or "").lower()]
    if state and input.get("congress"):
        members = [m for m in members if _member_state_code(m) == state]
    return {
        "source_id": SOURCE_ID,
        "mode": "members",
        "records": [_normalize_member(m) for m in members[:limit]],
        "page": {
            "limit": limit,
            "total": total,
            "filtered_client_side": bool(name),
            "congress": queried_congress,
        },
    }


def run(input: dict, ctx) -> dict:
    if input.get("mode") == "members" and not any(
        input.get(k) for k in ("bioguide_id", "state", "name", "congress")
    ):
        raise ValueError(
            "members mode needs `bioguide_id`, `state`, `name`, or `congress`."
        )
    mode = _mode(input)
    params = {"format": "json", "api_key": ctx.get_key("congress")}
    with httpx.Client(params=params, timeout=30) as client:
        return _bills(input, client) if mode == "bills" else _members(input, client)
