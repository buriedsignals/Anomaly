"""Adapter for gb/find-a-tender/notices — UK Find a Tender Service (OCDS).

FTS publishes UK public procurement above-threshold notices as an OCDS 1.1
release feed. The feed is paginated by date, NOT keyword-searchable — so this
adapter pulls a recent window and, if `q` is given, filters it client-side.
Public, no key.

``procurement-processes`` and ``procurement-awards`` turn the same release page
into rows of the procurement domain contract (domains/procurement.yaml): one
process row per lot (``ocid/lot``, or ``ocid`` without lots) and one award row
per supplier on an award (``ocid/award id``).
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
OPERATIONS = ("search-notices", "procurement-processes", "procurement-awards")


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


def _day(value: object) -> str | None:
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _amount(value: dict | None) -> tuple[float | None, str | None]:
    """Net amount when published, else the gross amount (Procurement Act notices)."""
    value = value or {}
    amount = value.get("amount") if value.get("amount") is not None else value.get("amountGross")
    return amount, value.get("currency")


def _lot_ids(tender: dict) -> list[str]:
    return [str(lot["id"]) for lot in tender.get("lots") or [] if lot.get("id") is not None]


def _process_id(release: dict, lot: object) -> str:
    """``ocid/lot`` when the tender has that lot, else the process ``ocid``."""
    ocid = release.get("ocid")
    return f"{ocid}/{lot}" if lot is not None and str(lot) in _lot_ids(release.get("tender") or {}) else ocid


def _cpv(release: dict) -> str | None:
    tender = release.get("tender") or {}
    if (tender.get("classification") or {}).get("id"):
        return tender["classification"]["id"]
    for item in [*(tender.get("items") or []),
                 *(i for a in release.get("awards") or [] for i in a.get("items") or [])]:
        for c in [item.get("classification") or {}, *(item.get("additionalClassifications") or [])]:
            if c.get("scheme") == "CPV" and c.get("id"):
                return c["id"]
    return None


def _bids(release: dict, lot: str | None) -> int | None:
    """Bids for one lot (bids/statistics, measure ``bids``), else tender/numberOfTenderers."""
    single = len(_lot_ids(release.get("tender") or {})) <= 1
    for stat in (release.get("bids") or {}).get("statistics") or []:
        related = stat.get("relatedLot")
        if stat.get("measure") == "bids" and (str(related) == lot if related is not None else single):
            return stat.get("value")
    return (release.get("tender") or {}).get("numberOfTenderers")


def _process_rows(r: dict) -> list[dict]:
    tender, buyer = r.get("tender") or {}, r.get("buyer") or {}
    if not any(tender.get(key) for key in ("procurementMethod", "lots", "tenderPeriod")):
        return []  # contract-stage releases (changes, terminations) describe no process
    period = tender.get("tenderPeriod") or {}
    # A first tender notice opens the submission period on its release date.
    published = period.get("startDate") or (r.get("date") if "tender" in (r.get("tag") or []) else None)
    lots = tender.get("lots") or [None]
    rows = []
    for lot in lots:
        lot_id = str(lot["id"]) if lot and lot.get("id") is not None else None
        value, currency = _amount((lot or {}).get("value") or tender.get("value"))
        rows.append({
            "process_id": _process_id(r, lot_id),
            "buyer_id": buyer.get("id"),
            "buyer_name": buyer.get("name"),
            "country": "GB",
            "category_code": _cpv(r),
            "procurement_method": tender.get("procurementMethod"),
            "tender_value": value,
            "currency": currency,
            "tender_published_date": _day(published),
            "tender_deadline": _day(period.get("endDate")),
            "number_of_tenderers": _bids(r, lot_id),
            "procurement_method_details": tender.get("procurementMethodDetails"),
            "release_id": r.get("id"),
            "tags": " ".join(r.get("tag") or []),
        })
    return rows


def _award_rows(r: dict) -> list[dict]:
    """One row per supplier on each award; a contract change notice adds the new value as final_value."""
    contracts = r.get("contracts") or []
    rows = []
    for award in r.get("awards") or []:
        signed = [c for c in contracts if str(c.get("awardID")) == str(award.get("id"))]
        value, currency = _amount(award.get("value"))
        if value is None and signed:
            amounts = [_amount(c.get("value")) for c in signed]
            known = [a for a, _ in amounts if a is not None]
            value, currency = (sum(known) if known else None), next((c for _, c in amounts if c), None)
        dates = [award.get("date"), *(c.get("dateSigned") for c in signed), r.get("date")]
        lots = award.get("relatedLots") or [None]
        for supplier in award.get("suppliers") or [{}]:
            rows.append({
                "award_id": f"{r.get('ocid')}/{award.get('id')}",
                "process_id": _process_id(r, lots[0]),
                "supplier_id": supplier.get("id"),
                "supplier_name": supplier.get("name"),
                "award_value": value,
                "currency": currency,
                "award_date": _day(next((d for d in dates if d), None)),
                "final_value": None,
                "release_id": r.get("id"),
            })
    if "contractAmendment" in (r.get("tag") or []):
        for contract in contracts:
            value, currency = _amount(contract.get("value"))
            rows.append({
                "award_id": f"{r.get('ocid')}/{contract.get('awardID')}", "process_id": None,
                "supplier_id": None, "supplier_name": None, "award_value": None, "currency": currency,
                "award_date": None, "final_value": value, "release_id": r.get("id"),
            })
    return rows


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
    operation = input.get("operation", "search-notices")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
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
        headers={"User-Agent": "BuriedSignals-catalogue/1.0"},
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
    rows = {"search-notices": lambda r: [_normalize(r)], "procurement-processes": _process_rows,
            "procurement-awards": _award_rows}[operation]
    return {
        "source_id": SOURCE_ID,
        "records": [row for r in releases for row in rows(r)],
        "page": {
            "returned": len(releases),
            "filtered_by": q or None,
            "stage": stage,
            "next_cursor": _next_cursor((payload.get("links") or {}).get("next")),
            "next_url": (payload.get("links") or {}).get("next"),
            "published_date": payload.get("publishedDate"),
        },
    }
