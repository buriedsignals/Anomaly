"""USAspending Advanced Award Search adapter.

``search-awards`` returns award-level search records. ``procurement-processes``
and ``procurement-awards`` run the same contract search, then read each award's
detail to emit rows of the procurement
domain contract (domains/procurement.yaml), ready to write to CSV for
anomaly.oneshot. Each record costs one extra API request.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

API_URL = "https://api.usaspending.gov/api/v2"
ENDPOINT = f"{API_URL}/search/spending_by_award/"
HEADERS = {"Accept": "application/json", "User-Agent": "BuriedSignals-catalogue/1.0"}
OPERATIONS = ("search-awards", "procurement-processes", "procurement-awards")
# FPDS extent_competed codes (USAspending data dictionary) mapped to the OCDS
# procurementMethod codelist: open = any supplier may bid, selective = only
# qualified or eligible suppliers, limited = buyer picks whom to ask,
# direct = no competition.
METHODS = {
    "A": "open",        # full and open competition
    "D": "selective",   # full and open after exclusion of sources (set-asides)
    "CDO": "selective", # competitive delivery order among IDV holders
    "F": "limited",     # competed under simplified acquisition procedures
    "B": "direct",      # not available for competition
    "C": "direct",      # not competed
    "E": "direct",      # follow-on to a competed action
    "G": "direct",      # not competed under simplified acquisition procedures
    "NDO": "direct",    # non-competitive delivery order
}
SOURCE_ID = "us/usaspending/awards"
TYPE_CODES = {
    "contracts": ["A", "B", "C", "D"],
    "grants": ["02", "03", "04", "05"],
    "loans": ["07", "08"],
    "idvs": ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"],
    "direct_payments": ["06", "10"],
    "other_assistance": ["09", "11", "-1"],
    # Backward-compatible umbrella for all non-grant, non-loan assistance.
    "other": ["06", "09", "10", "11", "-1"],
}
BASE_FIELDS = [
    "Award ID",
    "Recipient Name",
    "Recipient UEI",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Funding Agency",
    "Funding Sub Agency",
    "Description",
    "Last Modified Date",
    "Base Obligation Date",
    "generated_internal_id",
]
TYPE_FIELDS = {
    "contracts": ["Start Date", "End Date", "Award Amount", "Total Outlays", "Contract Award Type", "NAICS", "PSC"],
    "idvs": ["Start Date", "Award Amount", "Total Outlays", "Contract Award Type", "Last Date to Order", "NAICS", "PSC"],
    "loans": ["Issued Date", "Loan Value", "Subsidy Cost", "SAI Number", "CFDA Number", "Assistance Listings"],
    "grants": ["Start Date", "End Date", "Award Amount", "Total Outlays", "Award Type", "SAI Number", "CFDA Number", "Assistance Listings"],
    "direct_payments": ["Start Date", "End Date", "Award Amount", "Total Outlays", "Award Type", "SAI Number", "CFDA Number", "Assistance Listings"],
    "other_assistance": ["Start Date", "End Date", "Award Amount", "Total Outlays", "Award Type", "SAI Number", "CFDA Number", "Assistance Listings"],
    "other": ["Start Date", "End Date", "Award Amount", "Total Outlays", "Award Type", "SAI Number", "CFDA Number", "Assistance Listings"],
}


def _date(value: str, field: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD.") from exc


def _window(input: dict) -> tuple[str, str, int | None]:
    start, end = input.get("start_date"), input.get("end_date")
    if bool(start) != bool(end):
        raise ValueError("start_date and end_date must be provided together.")
    if start and end:
        parsed_start, parsed_end = _date(start, "start_date"), _date(end, "end_date")
        if parsed_start > parsed_end:
            raise ValueError("start_date must be on or before end_date.")
        return parsed_start, parsed_end, None
    fiscal_year = input.get("fiscal_year")
    if fiscal_year is None:
        today = date.today()
        fiscal_year = today.year + 1 if today.month >= 10 else today.year
    fiscal_year = int(fiscal_year)
    if not 1950 <= fiscal_year <= 2200:
        raise ValueError("fiscal_year must be between 1950 and 2200.")
    return f"{fiscal_year - 1}-10-01", f"{fiscal_year}-09-30", fiscal_year


def _fields(award_type: str) -> list[str]:
    return BASE_FIELDS + TYPE_FIELDS[award_type]


def _sort_field(award_type: str, requested: str) -> str:
    if requested == "recipient":
        return "Recipient Name"
    if requested == "date":
        return "Issued Date" if award_type == "loans" else "Start Date"
    return "Loan Value" if award_type == "loans" else "Award Amount"


def _normalize(item: dict[str, Any], award_group: str) -> dict[str, Any]:
    recipient = item.get("Recipient Name") or ""
    description = item.get("Description") or ""
    generated_id = item.get("generated_internal_id") or ""
    amount = item.get("Award Amount")
    if amount is None:
        amount = item.get("Loan Value")
    start_date = item.get("Start Date") or item.get("Issued Date") or item.get("Base Obligation Date")
    return {
        "entity": "FederalAward",
        "name": f"{recipient} — {description}".strip(" —"),
        "award_id": item.get("Award ID"),
        "award_group": award_group,
        "award_type": item.get("Contract Award Type") or item.get("Award Type"),
        "recipient": recipient or None,
        "recipient_uei": item.get("Recipient UEI"),
        "amount": amount,
        "total_outlays": item.get("Total Outlays"),
        "subsidy_cost": item.get("Subsidy Cost"),
        "description": description or None,
        "awarding_agency": item.get("Awarding Agency"),
        "awarding_subagency": item.get("Awarding Sub Agency"),
        "funding_agency": item.get("Funding Agency"),
        "funding_subagency": item.get("Funding Sub Agency"),
        "start_or_issued_date": start_date,
        "end_date": item.get("End Date"),
        "base_obligation_date": item.get("Base Obligation Date"),
        "last_modified_date": item.get("Last Modified Date"),
        "cfda_number": item.get("CFDA Number"),
        "assistance_listings": item.get("Assistance Listings"),
        "naics": item.get("NAICS"),
        "psc": item.get("PSC"),
        "internal_id": item.get("internal_id"),
        "generated_internal_id": generated_id or None,
        "source_url": f"https://www.usaspending.gov/award/{generated_id}" if generated_id else None,
    }


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _detail(client: httpx.Client, generated_id: str) -> dict[str, Any]:
    response = client.get(f"{API_URL}/awards/{generated_id}/")
    response.raise_for_status()
    return response.json()


def _process_row(item: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    contract = detail.get("latest_transaction_contract_data") or {}
    subtier = (detail.get("awarding_agency") or {}).get("subtier_agency") or {}
    extent = contract.get("extent_competed")
    return {
        "process_id": item.get("generated_internal_id"),
        "buyer_id": subtier.get("code"),
        "buyer_name": subtier.get("name") or item.get("Awarding Sub Agency"),
        "country": "US",
        "category_code": contract.get("naics"),
        "procurement_method": METHODS.get(extent),
        "tender_value": None,
        "currency": "USD",
        "tender_published_date": None,
        "tender_deadline": None,
        "number_of_tenderers": _integer(contract.get("number_of_offers_received")),
        "extent_competed": extent,
        "psc": contract.get("product_or_service_code"),
        "solicitation_procedures": contract.get("solicitation_procedures"),
        "piid": detail.get("piid"),
    }


def _award_row(item: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    # The API exposes only current award values, not the value at award, so
    # final_value stays empty; see SKILL.md for the bulk-download mapping.
    recipient = detail.get("recipient") or {}
    return {
        "award_id": item.get("generated_internal_id"),
        "process_id": item.get("generated_internal_id"),
        "supplier_id": recipient.get("recipient_uei") or item.get("Recipient UEI"),
        "supplier_name": recipient.get("recipient_name") or item.get("Recipient Name"),
        "award_value": detail.get("total_obligation"),
        "currency": "USD",
        "award_date": detail.get("date_signed") or item.get("Base Obligation Date"),
        "final_value": None,
        "base_exercised_options": detail.get("base_exercised_options"),
        "base_and_all_options": detail.get("base_and_all_options"),
        "piid": detail.get("piid"),
    }


def _contract_rows(operation: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for item in results:
            generated_id = item.get("generated_internal_id")
            if not generated_id:
                continue
            detail = _detail(client, generated_id)
            if operation == "procurement-processes":
                rows.append(_process_row(item, detail))
            else:
                rows.append(_award_row(item, detail))
    return rows


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "search-awards")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    award_type = str(input.get("award_type") or "contracts").lower()
    if operation != "search-awards" and award_type != "contracts":
        raise ValueError("procurement operations read contracts only.")
    if award_type not in TYPE_CODES:
        raise ValueError(f"award_type must be one of: {', '.join(TYPE_CODES)}.")
    start, end, fiscal_year = _window(input)
    limit = int(input.get("limit", 10))
    page = int(input.get("page", 1))
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")
    if page < 1:
        raise ValueError("page must be at least 1.")

    filters: dict[str, Any] = {
        "time_period": [{"start_date": start, "end_date": end}],
        "award_type_codes": TYPE_CODES[award_type],
    }
    if input.get("keyword"):
        filters["keywords"] = [input["keyword"]]
    if input.get("recipient"):
        filters["recipient_search_text"] = [input["recipient"]]
    if input.get("award_id"):
        award_id = str(input["award_id"]).strip().strip('"')
        if not award_id:
            raise ValueError("award_id cannot be blank.")
        filters["award_ids"] = [f'"{award_id}"']

    order = input.get("order", "desc")
    if order not in {"asc", "desc"}:
        raise ValueError("order must be asc or desc.")
    sort = input.get("sort", "amount")
    if sort not in {"amount", "recipient", "date"}:
        raise ValueError("sort must be amount, recipient, or date.")
    payload = {
        "filters": filters,
        "fields": _fields(award_type),
        "page": page,
        "limit": limit,
        "sort": _sort_field(award_type, sort),
        "order": order,
        "subawards": False,
    }
    response = httpx.post(ENDPOINT, json=payload, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    metadata = data.get("page_metadata") or {}
    results = data.get("results") or []
    records = (
        [_normalize(item, award_type) for item in results] if operation == "search-awards"
        else _contract_rows(operation, results)
    )
    return {
        "source_id": SOURCE_ID,
        "records": records,
        "page": {
            "limit": limit,
            "page": metadata.get("page", page),
            "has_next": metadata.get("hasNext"),
            "returned": len(results),
            "sort": payload["sort"],
            "order": order,
        },
        "query_window": {"start_date": start, "end_date": end, "fiscal_year": fiscal_year},
        "messages": data.get("messages") or [],
    }
