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


# --- Companies domain contract (domains/companies.yaml) -----------------------
# A company_id is "lei:" plus the LEI. GLEIF Level 2 data names the direct and
# ultimate accounting-consolidation parents; an entity without a reported parent
# answers 404 on the parent route (it files a reporting exception instead).

API_ROOT = "https://api.gleif.org/api/v1/lei-records"
HEADERS = {"Accept": "application/vnd.api+json", "User-Agent": "BuriedSignals-catalogue/1.0"}
CONTRACT_LIMIT = 50


def _country(entity: dict) -> str | None:
    # jurisdiction can be a subdivision such as US-DE; the contract wants ISO alpha-2.
    jurisdiction = entity.get("jurisdiction") or (entity.get("legalAddress") or {}).get("country")
    return jurisdiction.split("-")[0].upper() if jurisdiction else None


def _street_address(address: dict | None) -> str | None:
    if not address:
        return None
    parts = list(address.get("addressLines") or []) + [address.get("postalCode"), address.get("city")]
    return ", ".join(str(part) for part in parts if part) or None


def _company_row(item: dict) -> dict:
    attrs = item.get("attributes") or {}
    entity = attrs.get("entity") or {}
    expiration = entity.get("expiration") or {}
    dissolved = expiration.get("reason") == "DISSOLVED" and expiration.get("date")
    created = entity.get("creationDate")
    return {
        "company_id": f"lei:{attrs.get('lei')}",
        "jurisdiction": _country(entity),
        "name": (entity.get("legalName") or {}).get("name"),
        "status": entity.get("status"),
        "incorporation_date": created[:10] if created else None,
        "dissolution_date": dissolved[:10] if dissolved else None,
        "registered_address": _street_address(entity.get("legalAddress")),
        "previous_name_count": None,
        "source_url": (item.get("links") or {}).get("self"),
    }


def _parent_rows(client: httpx.Client, lei: str) -> list[dict]:
    rows: list[dict] = []
    for level in ("direct-parent", "ultimate-parent"):
        response = client.get(f"{API_ROOT}/{lei}/{level}")
        if response.status_code == 404:
            continue
        response.raise_for_status()
        parent = (response.json() or {}).get("data") or {}
        attrs = parent.get("attributes") or {}
        parent_lei = attrs.get("lei")
        if not parent_lei or any(row["controller_id"] == f"lei:{parent_lei}" for row in rows):
            continue
        entity = attrs.get("entity") or {}
        rows.append({
            "company_id": f"lei:{lei}",
            "controller_id": f"lei:{parent_lei}",
            "controller_name": (entity.get("legalName") or {}).get("name"),
            "controller_kind": "legal_entity",
            "controller_country": _country(entity),
            "controller_company_id": f"lei:{parent_lei}",
            "control_type": level,
            "notified_on": None,
            "ceased_on": None,
        })
    return rows


def _contract(operation: str, input: dict) -> dict:
    lei = input.get("lei")
    with httpx.Client(headers=HEADERS, timeout=20) as client:
        if isinstance(lei, str) and lei.strip():
            lei = lei.strip().upper()
            if len(lei) != 20 or not lei.isalnum():
                raise ValueError("lei must be exactly 20 alphanumeric characters")
            response = client.get(f"{API_ROOT}/{lei}")
            response.raise_for_status()
            items = [response.json().get("data") or {}]
        else:
            # Reuse the search inputs, capped because parents cost two requests per record.
            data, _ = _search({**input, "limit": min(int(input.get("limit", 10)), CONTRACT_LIMIT)})
            items = data.get("data", [])
        if operation == "companies":
            records = [_company_row(item) for item in items]
        else:
            records = [row for item in items for row in _parent_rows(client, (item.get("attributes") or {}).get("lei"))]
    return {"source_id": "global/gleif/lei-records", "records": records, "page": {"returned": len(records)}}


def _search(input: dict) -> tuple[dict, int]:
    """Run the record search; return the JSON:API body and the page size used."""
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
    return response.json(), limit


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "search-lei-records")
    if operation in {"companies", "company-controllers"}:
        return _contract(operation, input)
    data, limit = _search(input)
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
