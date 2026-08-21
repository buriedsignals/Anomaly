"""Adapter for gb/companies-house/companies — UK Companies House search.

BYO-key source: the key is fetched via ctx.get_key and sent as the HTTP Basic
username with an empty password. It never enters the agent's context.
"""

from __future__ import annotations

import httpx

API_URL = "https://api.company-information.service.gov.uk"
SEARCH_ENDPOINT = f"{API_URL}/search/companies"


def _compose_address(address: dict | None) -> str:
    if not address:
        return ""
    parts = [
        address.get("care_of"),
        address.get("po_box"),
        address.get("premises"),
        address.get("address_line_1"),
        address.get("address_line_2"),
        address.get("locality"),
        address.get("region"),
        address.get("postal_code"),
        address.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part)


def _normalize(item: dict) -> dict:
    company_number = item.get("company_number")
    address = item.get("address_snippet") or _compose_address(
        item.get("registered_office_address") or item.get("address")
    )
    return {
        "entity": "Company",
        "name": item.get("title") or item.get("company_name"),
        "jurisdiction": "gb",
        "company_number": company_number,
        "status": item.get("company_status"),
        "company_type": item.get("company_type") or item.get("type"),
        "incorporation_date": item.get("date_of_creation"),
        "cessation_date": item.get("date_of_cessation"),
        "registered_address": address,
        "source_url": (
            f"https://find-and-update.company-information.service.gov.uk/company/{company_number}"
            if company_number
            else None
        ),
    }


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    auth = (ctx.get_key("companies-house"), "")
    if operation == "get-company":
        company_number = input.get("company_number")
        if not isinstance(company_number, str) or not company_number.strip():
            raise ValueError("company_number is required")
        company_number = company_number.strip().upper()
        if len(company_number) > 8 or not company_number.isalnum():
            raise ValueError("company_number must contain at most 8 letters or digits")
        response = httpx.get(
            f"{API_URL}/company/{company_number}", auth=auth, timeout=20
        )
        response.raise_for_status()
        return {
            "source_id": "gb/companies-house/companies",
            "records": [_normalize(response.json())],
            "page": {"returned": 1},
        }
    if operation != "search-companies":
        raise ValueError("a released Companies House operation is required")
    q = input.get("q")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q is required")
    items_per_page = max(1, min(int(input.get("items_per_page", 20)), 100))
    start_index = max(0, int(input.get("start_index", 0)))
    response = httpx.get(
        SEARCH_ENDPOINT,
        params={
            "q": q.strip(),
            "items_per_page": items_per_page,
            "start_index": start_index,
        },
        auth=auth,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "source_id": "gb/companies-house/companies",
        "records": [_normalize(item) for item in data.get("items", [])],
        "page": {
            "start_index": data.get("start_index", start_index),
            "items_per_page": data.get("items_per_page", items_per_page),
            "total_results": data.get("total_results"),
            "returned": len(data.get("items", [])),
        },
    }
