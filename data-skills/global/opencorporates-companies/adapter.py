"""Read-only OpenCorporates company search and exact company lookup."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

API_URL = "https://api.opencorporates.com/v0.4"
SOURCE_ID = "global/opencorporates/companies"


def _string(input: dict[str, Any], field: str, *, maximum: int = 500) -> str:
    value = input.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters.")
    return value


def _integer(
    input: dict[str, Any], field: str, default: int, minimum: int, maximum: int
) -> int:
    value = input.get(field, default)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return parsed


def _normalize(company: dict[str, Any]) -> dict[str, Any]:
    source = company.get("source") if isinstance(company.get("source"), dict) else {}
    return {
        "entity": "Company",
        "name": company.get("name"),
        "jurisdiction": company.get("jurisdiction_code"),
        "company_number": company.get("company_number"),
        "company_type": company.get("company_type"),
        "status": company.get("current_status"),
        "inactive": company.get("inactive"),
        "incorporation_date": company.get("incorporation_date"),
        "dissolution_date": company.get("dissolution_date"),
        "registered_address": company.get("registered_address_in_full"),
        "previous_names": company.get("previous_names") or [],
        "created_at": company.get("created_at"),
        "updated_at": company.get("updated_at"),
        "source_retrieved_at": source.get("retrieved_at") or company.get("retrieved_at"),
        "source_publisher": source.get("publisher"),
        "source_registry_url": source.get("url") or company.get("registry_url"),
        "source_terms": source.get("terms"),
        "registry_url": company.get("registry_url"),
        "source_url": company.get("opencorporates_url"),
    }


def _mode(input: dict[str, Any]) -> str:
    mode = input.get("mode")
    if mode is not None:
        if mode not in {"search", "entity"}:
            raise ValueError("mode must be search or entity.")
        return str(mode)
    if input.get("company_number") and input.get("jurisdiction_code"):
        return "entity"
    if input.get("q") or input.get("query"):
        return "search"
    raise ValueError(
        "OpenCorporates needs q for search or jurisdiction_code plus company_number for exact lookup."
    )


def _search(
    input: dict[str, Any], token: str, client: httpx.Client
) -> dict[str, Any]:
    query = input.get("q") or input.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("q is required.")
    params: dict[str, Any] = {
        "q": query.strip(),
        "per_page": _integer(input, "per_page", 10, 1, 100),
        "page": _integer(input, "page", 1, 1, 100),
        "api_token": token,
    }
    if input.get("jurisdiction_code") is not None:
        params["jurisdiction_code"] = _string(input, "jurisdiction_code", maximum=100)
    if "inactive" in input:
        if not isinstance(input["inactive"], bool):
            raise ValueError("inactive must be a boolean.")
        params["inactive"] = str(input["inactive"]).lower()
    response = client.get(f"{API_URL}/companies/search", params=params)
    response.raise_for_status()
    results = response.json().get("results", {})
    companies = results.get("companies", [])
    return {
        "source_id": SOURCE_ID,
        "mode": "search",
        "records": [
            _normalize(item.get("company", {}))
            for item in companies
            if isinstance(item, dict)
        ],
        "page": {
            "page": results.get("page"),
            "per_page": results.get("per_page"),
            "total_count": results.get("total_count"),
            "total_pages": results.get("total_pages"),
        },
    }


def _entity(
    input: dict[str, Any], token: str, client: httpx.Client
) -> dict[str, Any]:
    jurisdiction = quote(_string(input, "jurisdiction_code", maximum=100), safe="")
    number = quote(_string(input, "company_number", maximum=200), safe="")
    response = client.get(
        f"{API_URL}/companies/{jurisdiction}/{number}",
        params={"api_token": token},
    )
    response.raise_for_status()
    company = response.json().get("results", {}).get("company", {})
    return {
        "source_id": SOURCE_ID,
        "mode": "entity",
        "records": [_normalize(company)],
        "page": {},
    }


def run(input: dict[str, Any], ctx) -> dict[str, Any]:
    token = ctx.get_key("opencorporates")
    mode = _mode(input)
    with httpx.Client(timeout=30) as client:
        if mode == "search":
            return _search(input, token, client)
        return _entity(input, token, client)
