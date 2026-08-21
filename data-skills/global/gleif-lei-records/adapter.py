"""Adapter for global/gleif/lei-records — GLEIF LEI record search."""

from __future__ import annotations

import httpx

ENDPOINT = "https://api.gleif.org/api/v1/lei-records"
SEARCH_FIELDS = {
    "fulltext": "filter[fulltext]",
    "legal_name": "filter[entity.legalName]",
    "lei": "filter[lei]",
}


def _compose_address(address: dict | None) -> str:
    if not address:
        return ""
    parts = list(address.get("addressLines") or [])
    city = address.get("city")
    postal = address.get("postalCode")
    region = address.get("region")
    country = address.get("country")
    locality = " ".join(part for part in (postal, city) if part)
    if locality:
        parts.append(locality)
    if region:
        parts.append(region)
    if country:
        parts.append(country)
    return ", ".join(part for part in parts if part)


def _normalize(item: dict) -> dict:
    attrs = item.get("attributes") or {}
    entity = attrs.get("entity") or {}
    registration = attrs.get("registration") or {}
    legal_name = entity.get("legalName") or {}
    legal_form = entity.get("legalForm") or {}
    links = item.get("links") or {}
    return {
        "entity": "LegalEntity",
        "name": legal_name.get("name"),
        "jurisdiction": entity.get("jurisdiction"),
        "lei": attrs.get("lei"),
        "registered_as": entity.get("registeredAs"),
        "category": entity.get("category"),
        "legal_form": legal_form.get("id") or legal_form.get("other"),
        "status": entity.get("status"),
        "registration_status": registration.get("status"),
        "next_renewal_date": registration.get("nextRenewalDate"),
        "corroboration_level": registration.get("corroborationLevel"),
        "address": _compose_address(entity.get("legalAddress")),
        "source_url": links.get("self"),
    }


def run(input: dict, ctx) -> dict:
    q = input.get("q") or input.get("query") or input.get("name")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q is required")
    q = q.strip()
    search_field = input.get("search_field", "fulltext")
    if search_field not in SEARCH_FIELDS:
        raise ValueError("search_field must be one of: fulltext, legal_name, lei")
    if search_field == "lei" and (len(q) != 20 or not q.isalnum()):
        raise ValueError("an LEI search requires exactly 20 alphanumeric characters")
    limit = max(1, min(int(input.get("limit", 10)), 100))
    page = max(1, int(input.get("page", 1)))
    params = {
        SEARCH_FIELDS[search_field]: q.upper() if search_field == "lei" else q,
        "page[size]": limit,
        "page[number]": page,
    }
    if input.get("jurisdiction"):
        jurisdiction = input["jurisdiction"]
        if not isinstance(jurisdiction, str) or len(jurisdiction.strip()) != 2:
            raise ValueError("jurisdiction must be a two-letter ISO country code")
        params["filter[entity.jurisdiction]"] = jurisdiction.strip().upper()

    response = httpx.get(
        ENDPOINT,
        params=params,
        headers={
            "Accept": "application/vnd.api+json",
            "User-Agent": "BuriedSignals-catalogue/1.0",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    pagination = (data.get("meta") or {}).get("pagination") or {}
    return {
        "source_id": "global/gleif/lei-records",
        "records": [_normalize(item) for item in data.get("data", [])],
        "page": {
            "size": pagination.get("perPage", limit),
            "total_elements": pagination.get("total"),
            "current_page": pagination.get("currentPage"),
            "total_pages": pagination.get("lastPage"),
            "returned": len(data.get("data", [])),
        },
    }
