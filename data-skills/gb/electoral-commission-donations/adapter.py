"""Adapter for gb/electoral-commission/donations — UK political donations.

Reads the CSV exports behind the Electoral Commission's register search
(search.electoralcommission.org.uk) and emits rows shaped like the
campaign_finance domain contract (domains/campaign_finance.yaml): the
``donations`` operation fills ``donations`` and ``registrations`` fills
``recipients``, so rows can be written to a file for anomaly.oneshot without a
column map. The export ignores paging and returns every matching row, so a
search term or date range is required and ``max_rows`` bounds the result.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

import httpx

API_URL = "https://search.electoralcommission.org.uk/api/csv"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
ENTITY_TYPES = {"pp", "ppm", "tp", "perpar", "rd"}
MAX_ROWS = 50000
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso(value: str | None) -> str | None:
    """dd/mm/yyyy as published -> yyyy-mm-dd."""
    value = (value or "").strip()
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat() if value else None


def _money(value: str | None) -> float | None:
    cleaned = (value or "").replace("£", "").replace(",", "").strip()
    return float(cleaned) if cleaned else None


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _donation(row: dict) -> dict:
    return {
        "donation_id": _text(row.get("ECRef")),
        "recipient_id": _text(row.get("RegulatedEntityId")),
        "recipient_name": _text(row.get("RegulatedEntityName")),
        "recipient_type": _text(row.get("RegulatedEntityType")),
        "donor_name": _text(row.get("DonorName")),
        "donor_type": _text(row.get("DonorStatus")),
        "donor_company_number": _text(row.get("CompanyRegistrationNumber")),
        "donor_employer": None,
        "donor_postcode": _text(row.get("Postcode")),
        "amount": _money(row.get("Value")),
        "currency": "GBP",
        # Received is when the money arrived; accepted is the regulatory date.
        "donation_date": _iso(row.get("ReceivedDate")) or _iso(row.get("AcceptedDate")),
        "accepted_date": _iso(row.get("AcceptedDate")),
        "donor_id": _text(row.get("DonorId")),
        "accounting_unit": _text(row.get("AccountingUnitName")),
        "donation_type": _text(row.get("DonationType")),
        "is_aggregation": _text(row.get("IsAggregation")) == "True",
        "reporting_period": _text(row.get("ReportingPeriodName")),
    }


def _registration(row: dict) -> dict:
    # ECRef is the entity number with a type prefix (PP7931, TP10257); the
    # digits equal RegulatedEntityId in the donations export.
    return {
        "recipient_id": re.sub(r"^[A-Z]+", "", _text(row.get("ECRef")) or "") or None,
        "name": _text(row.get("RegulatedEntityName")),
        "registered_date": _iso(row.get("ApprovedDate")),
        "entity_type": _text(row.get("RegulatedEntityTypeName")),
        "registration_status": _text(row.get("RegistrationStatusName")),
        "company_number": _text(row.get("CompanyRegistrationNumber")),
    }


def _entity_types(input: dict) -> list[str]:
    value = input.get("entity_types", ["pp"])
    value = [value] if isinstance(value, str) else value
    if not isinstance(value, list) or not value or not set(value) <= ENTITY_TYPES:
        raise ValueError(f"entity_types must be a list drawn from: {', '.join(sorted(ENTITY_TYPES))}.")
    return value


def _donation_params(input: dict) -> list[tuple[str, str]]:
    query = input.get("query") or ""
    start, end = input.get("from"), input.get("to")
    if not isinstance(query, str) or not all(v is None or (isinstance(v, str) and _DATE.match(v)) for v in (start, end)):
        raise ValueError("query must be text and from/to must be YYYY-MM-DD.")
    if not query.strip() and not (start and end):
        raise ValueError("name a query or both from and to; the export returns every matching row.")
    params = [("query", query.strip()), ("sort", "AcceptedDate"), ("order", "desc")]
    params += [("et", kind) for kind in _entity_types(input)]
    if start and end:
        params += [("date", "Accepted"), ("from", start), ("to", end)]
    params += [("register", "gb"), ("register", "ni"), ("register", "none"),
               ("isIrishSourceYes", "true"), ("isIrishSourceNo", "true"),
               ("prePoll", "false"), ("postPoll", "true"), ("includeOutsideSection75", "true")]
    return params


def _registration_params(input: dict) -> list[tuple[str, str]]:
    # The registers are small (parties and campaigners), so no filter is required.
    query = input.get("query") or ""
    if not isinstance(query, str):
        raise ValueError("query must be text.")
    params = [("query", query.strip()), ("sort", "RegulatedEntityName"), ("order", "asc")]
    params += [("et", kind) for kind in _entity_types(input)]
    return params + [("register", "gb"), ("register", "ni"), ("register", "none")]


OPERATIONS = {
    "donations": ("Donations", _donation_params, _donation),
    "registrations": ("Registrations", _registration_params, _registration),
}


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "donations")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    kind, params, row = OPERATIONS[operation]
    max_rows = input.get("max_rows", 10000)
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError(f"max_rows must be an integer from 1 to {MAX_ROWS}.")
    with httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=True) as client:
        response = client.get(f"{API_URL}/{kind}", params=params(input))
        response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))
    records = [row(item) for item in rows[:max_rows]]
    return {"records": records, "page": {"matched": len(rows), "returned": len(records),
                                         "truncated": len(rows) > max_rows}}
