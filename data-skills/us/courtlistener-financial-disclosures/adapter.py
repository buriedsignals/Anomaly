"""CourtListener federal judicial financial-disclosure records.

The default operation returns each report with its nested rows. The
``judge-interests`` operation flattens them into rows of the court domain
contract's judge_interests table (domains/court.yaml); SKILL.md maps each field.
"""

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


# Numeric bounds of the disclosure value codes; P4 has no upper bound.
VALUE_BOUNDS = {
    "J": (1, 15000), "K": (15001, 50000), "L": (50001, 100000), "M": (100001, 250000),
    "N": (250001, 500000), "O": (500001, 1000000), "P1": (1000001, 5000000),
    "P2": (5000001, 25000000), "P3": (25000001, 50000000), "P4": (50000001, None),
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


def _text(value: Any) -> Any:
    return (value.strip() or None) if isinstance(value, str) else value


def _amount(value: Any) -> tuple[float | None, float | None]:
    """A stated dollar amount such as "$1,199.00" as (low, high); else (None, None)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), float(value)
    text = (value or "").replace("$", "").replace(",", "").strip() if isinstance(value, str) else ""
    try:
        number = float(text)
    except ValueError:
        return None, None
    return number, number


def _coded(code: Any) -> tuple[float | None, float | None]:
    low, high = VALUE_BOUNDS.get(code, (None, None))
    return (float(low) if low is not None else None, float(high) if high is not None else None)


def _join(*parts: Any) -> str | None:
    return "; ".join(str(part).strip() for part in parts if isinstance(part, str) and part.strip()) or None


# interest_type -> (nested array, counterparty, description, value bounds)
INTEREST_ROWS = {
    "investment": ("investments", lambda i: i.get("description"), lambda i: None,
                   lambda i: _coded(i.get("gross_value_code"))),
    "gift": ("gifts", lambda i: i.get("source"), lambda i: i.get("description"),
             lambda i: _amount(i.get("value"))),
    "reimbursement": ("reimbursements", lambda i: i.get("source"),
                      lambda i: _join(i.get("date_raw"), i.get("location"), i.get("purpose"),
                                      i.get("items_paid_or_provided")),
                      lambda i: (None, None)),
    "position": ("positions", lambda i: i.get("organization_name"), lambda i: i.get("position"),
                 lambda i: (None, None)),
    "agreement": ("agreements", lambda i: i.get("parties_and_terms"), lambda i: i.get("date_raw"),
                  lambda i: (None, None)),
    "income": ("non_investment_incomes", lambda i: i.get("source_type"), lambda i: i.get("date_raw"),
               lambda i: _amount(i.get("income_amount"))),
    "spouse_income": ("spouse_incomes", lambda i: i.get("source_type"), lambda i: i.get("date_raw"),
                      lambda i: (None, None)),
    "debt": ("debts", lambda i: i.get("creditor_name"), lambda i: i.get("description"),
             lambda i: _coded(i.get("value_code"))),
}


def _judge_interests(record: dict[str, Any]) -> list[dict[str, Any]]:
    person_uri = record.get("person") or ""
    tail = person_uri.rstrip("/").rsplit("/", 1)[-1] if isinstance(person_uri, str) else ""
    rows = []
    for interest_type, (array, counterparty, description, value) in INTEREST_ROWS.items():
        for item in record.get(array) or []:
            name = _text(counterparty(item))
            if not name:
                continue
            low, high = value(item)
            rows.append({
                "judge_id": tail if tail.isdigit() else None,
                "judge_name": None,
                "report_year": record.get("year"),
                "interest_type": interest_type,
                "counterparty": name,
                "description": _text(description(item)),
                "value_low": low,
                "value_high": high,
                "url": record.get("filepath"),
                "redacted": item.get("redacted"),
            })
    return rows


def _headers(ctx) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "BuriedSignals-catalogue/1.0",
    }
    token = ctx.get_key_optional("courtlistener") if hasattr(ctx, "get_key_optional") else None
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "list-financial-disclosures")
    if operation not in {"list-financial-disclosures", "judge-interests"}:
        raise ValueError("operation must be list-financial-disclosures or judge-interests.")
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
        "records": [
            row for record in results for row in _judge_interests(record)
        ] if operation == "judge-interests" else [_normalize(record) for record in results],
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
