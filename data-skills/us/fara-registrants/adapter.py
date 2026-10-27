"""Adapter for us/fara/registrants — FARA registrants from the DOJ FARA.gov API.

Fills the lobbying contract table ``foreign_agent_registrants``. The API has no
key and returns every active or terminated registrant in one JSON document
(encoded as ISO-8859-1); the adapter filters names locally.
"""

from __future__ import annotations

import json

import httpx

API_URL = "https://efile.fara.gov/api/v1/Registrants/json"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
STATUSES = {"active": "Active", "terminated": "Terminated"}
MAX_LIMIT = 20000


def _rows(document: dict, status: str) -> list[dict]:
    """Rows under REGISTRANTS_<STATUS>.ROW; a single row arrives as an object."""
    rows = (document.get(f"REGISTRANTS_{status.upper()}") or {}).get("ROW") or []
    return [rows] if isinstance(rows, dict) else rows


def _record(row: dict, status: str) -> dict:
    number = row.get("Registration_Number")
    return {
        "registrant_name": (row.get("Name") or "").strip() or None,
        "registration_number": number,
        "status": status,
        "registration_date": row.get("Registration_Date"),
        "termination_date": row.get("Termination_Date"),
        # Documented RegDocs endpoint: the registrant's filed documents.
        "documents_url": f"https://efile.fara.gov/api/v1/RegDocs/json/{number}" if number else None,
    }


def run(input: dict, ctx) -> dict:
    status = input.get("status", "all")
    if status not in {"all", *STATUSES}:
        raise ValueError("status must be all, active or terminated.")
    q = input.get("q") or input.get("query") or ""
    if not isinstance(q, str):
        raise ValueError("q must be a string.")
    limit = input.get("limit", MAX_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    needle = q.strip().casefold()
    records = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=True) as client:
        for wanted in STATUSES if status == "all" else [status]:
            response = client.get(f"{API_URL}/{STATUSES[wanted]}")
            response.raise_for_status()
            # .text honours the ISO-8859-1 charset the API declares.
            for row in _rows(json.loads(response.text), STATUSES[wanted]):
                record = _record(row, wanted)
                if not needle or needle in (record["registrant_name"] or "").casefold():
                    records.append(record)
    return {"records": records[:limit], "page": {"matched": len(records), "returned": len(records[:limit])}}
