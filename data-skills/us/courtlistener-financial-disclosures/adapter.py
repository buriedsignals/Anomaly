"""CourtListener federal judicial financial-disclosure records."""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/financial-disclosures/"
SOURCE_ID = "us/courtlistener/financial-disclosures"
MAX_RESULTS = 20

VALUE_MAP = {
    "J": "$1–$15,000",
    "K": "$15,001–$50,000",
    "L": "$50,001–$100,000",
    "M": "$100,001–$250,000",
    "N": "$250,001–$500,000",
    "O": "$500,001–$1,000,000",
    "P1": "$1,000,001–$5,000,000",
    "P2": "$5,000,001–$25,000,000",
    "P3": "$25,000,001–$50,000,000",
    "P4": "$50,000,001 or more",
    "-1": "failed extraction",
}


def _range(code: str | None) -> str | None:
    if not code:
        return None
    return VALUE_MAP.get(code, code)


def _investment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "description": item.get("description"),
        "income_type": item.get("income_during_reporting_period_type"),
        "income_code": item.get("income_during_reporting_period_code"),
        "gross_value_code": item.get("gross_value_code"),
        "gross_value_range": _range(item.get("gross_value_code")),
        "transaction_type": item.get("transaction_during_reporting_period"),
        "transaction_date": item.get("transaction_date"),
        "transaction_value_code": item.get("transaction_value_code"),
        "transaction_value_range": _range(item.get("transaction_value_code")),
        "transaction_partner": item.get("transaction_partner"),
        "has_inferred_values": item.get("has_inferred_values"),
        "redacted": item.get("redacted"),
    }


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    person_uri = record.get("person") or ""
    person_id = person_uri.rstrip("/").split("/")[-1] if person_uri else None
    return {
        "entity": "FinancialDisclosure",
        "id": record.get("id"),
        "person_id": int(person_id) if person_id and person_id.isdigit() else person_id,
        "year": record.get("year"),
        "report_type": record.get("report_type"),
        "is_amended": record.get("is_amended"),
        "page_count": record.get("page_count"),
        "has_been_extracted": record.get("has_been_extracted"),
        "investments": [_investment(item) for item in record.get("investments") or []],
        "agreements": record.get("agreements") or [],
        "positions": record.get("positions") or [],
        "debts": record.get("debts") or [],
        "gifts": record.get("gifts") or [],
        "non_investment_incomes": record.get("non_investment_incomes") or [],
        "reimbursements": record.get("reimbursements") or [],
        "spouse_incomes": record.get("spouse_incomes") or [],
        "pdf_url": record.get("filepath"),
        "thumbnail_url": record.get("thumbnail"),
        "sha1": record.get("sha1"),
        "source_url": record.get("filepath"),
    }


def _headers(ctx) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "BuriedSignals-Navigator/1.0",
    }
    token = ctx.get_key_optional("courtlistener")
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def run(input: dict, ctx) -> dict:
    person_id = input.get("person_id")
    if person_id is None:
        raise ValueError("person_id is required.")
    limit = int(input.get("limit", 10))
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
    fields = (
        "id,person,year,report_type,is_amended,page_count,has_been_extracted,"
        "filepath,thumbnail,sha1,investments,agreements,positions,debts,gifts,"
        "non_investment_incomes,reimbursements,spouse_incomes"
    )
    response = httpx.get(
        ENDPOINT,
        params={"person": str(int(person_id)), "fields": fields},
        headers=_headers(ctx),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    results = (data.get("results") or [])[:limit]
    count = data.get("count")
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(record) for record in results],
        "page": {
            "limit": limit,
            "returned": len(results),
            # Database endpoints return an on-demand count URL unless count=on.
            "count": count if isinstance(count, int) else None,
            "count_url": count if isinstance(count, str) else None,
            "next": data.get("next"),
            "previous": data.get("previous"),
        },
    }
