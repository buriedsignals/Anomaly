"""Adapter for no/brreg/enheter — Norwegian Enhetsregisteret."""

from __future__ import annotations

import httpx

ENDPOINT = "https://data.brreg.no/enhetsregisteret/api/enheter"


def _compose_address(addr: dict | None) -> str:
    if not addr:
        return ""
    lines = list(addr.get("adresse") or [])
    parts = [", ".join(lines)] if lines else []
    pn, ps = addr.get("postnummer"), addr.get("poststed")
    if pn or ps:
        parts.append(f"{pn or ''} {ps or ''}".strip())
    if addr.get("land"):
        parts.append(addr["land"])
    return ", ".join(p for p in parts if p)


def _normalize(item: dict) -> dict:
    nace = item.get("naeringskode1") or {}
    org_form = item.get("organisasjonsform") or {}
    self_link = ((item.get("_links") or {}).get("self") or {}).get("href", "")
    return {
        "entity": "Company",
        "name": item.get("navn"),
        "jurisdiction": "no",
        "company_number": item.get("organisasjonsnummer"),
        "legal_form": org_form.get("beskrivelse"),
        "incorporation_date": item.get("registreringsdatoEnhetsregisteret"),
        "employees": item.get("antallAnsatte"),
        "industry_code": nace.get("kode"),
        "industry_description": nace.get("beskrivelse"),
        "address": _compose_address(item.get("forretningsadresse")),
        "bankrupt": item.get("konkurs"),
        "website": item.get("hjemmeside"),
        "source_url": self_link,
    }


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    if operation == "get-company":
        organisation_number = input.get("organisasjonsnummer")
        if not isinstance(organisation_number, str) or not organisation_number.isdigit() or len(organisation_number) != 9:
            raise ValueError("organisasjonsnummer must contain exactly 9 digits")
        endpoint = f"{ENDPOINT}/{organisation_number}"
        params: dict = {}
    elif operation == "search-companies":
        name = input.get("navn")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("navn is required")
        endpoint = ENDPOINT
        params = {
            "navn": name.strip(),
            "size": max(1, min(int(input.get("size", 10)), 100)),
            "page": max(0, int(input.get("page", 0))),
        }
    else:
        raise ValueError("a released BRREG operation is required")
    response = httpx.get(
        endpoint,
        params=params,
        headers={"Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    items = (
        [data]
        if operation == "get-company"
        else (data.get("_embedded") or {}).get("enheter") or []
    )
    return {
        "source_id": "no/brreg/enheter",
        "records": [_normalize(item) for item in items],
        "page": {
            "size": int(params.get("size", len(items))),
            "total_elements": (data.get("page") or {}).get("totalElements"),
            "current_page": (data.get("page") or {}).get("number"),
            "total_pages": (data.get("page") or {}).get("totalPages"),
            "returned": len(items),
        },
    }
