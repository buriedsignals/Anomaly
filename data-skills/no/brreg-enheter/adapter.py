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


# --- Companies domain contract (domains/companies.yaml) -----------------------
# A company_id is "no:" plus the organisation number. The open API publishes
# roles but no ownership, so Brreg fills companies and company_officers only.


def _organisation_number(input: dict) -> str:
    number = input.get("organisasjonsnummer")
    if not isinstance(number, str) or not number.isdigit() or len(number) != 9:
        raise ValueError("organisasjonsnummer must contain exactly 9 digits")
    return number


def _status(item: dict) -> str:
    if item.get("konkurs"):
        return "bankrupt"
    if item.get("underAvvikling") or item.get("underTvangsavviklingEllerTvangsopplosning"):
        return "in_liquidation"
    return "active"


def _company_row(item: dict) -> dict:
    address = item.get("forretningsadresse") or {}
    lines = list(address.get("adresse") or [])
    locality = " ".join(part for part in (address.get("postnummer"), address.get("poststed")) if part)
    return {
        "company_id": f"no:{item.get('organisasjonsnummer')}",
        "jurisdiction": "NO",
        "name": item.get("navn"),
        "status": _status(item),
        "incorporation_date": item.get("stiftelsesdato") or item.get("registreringsdatoEnhetsregisteret"),
        # Deleted entities leave the open API, so no dissolution date is published.
        "dissolution_date": None,
        "registered_address": ", ".join(lines + ([locality] if locality else [])) or None,
        "previous_name_count": len(item.get("historiskeNavn") or []),
        "source_url": ((item.get("_links") or {}).get("self") or {}).get("href"),
    }


def _officer_rows(data: dict, company_id: str) -> list[dict]:
    rows = []
    for group in data.get("rollegrupper") or []:
        for role in group.get("roller") or []:
            # A deregistered role has no end date in the open API; current roles only.
            if role.get("avregistrert"):
                continue
            person, entity = role.get("person") or {}, role.get("enhet") or {}
            if entity.get("organisasjonsnummer"):
                officer_id, name = f"no:{entity['organisasjonsnummer']}", " ".join(entity.get("navn") or [])
            else:
                names = person.get("navn") or {}
                name = " ".join(part for part in (names.get("fornavn"), names.get("mellomnavn"), names.get("etternavn")) if part)
                # Birth dates are public; national identity numbers are not.
                officer_id = f"no:person:{name.upper()}|{person.get('fodselsdato') or ''}"
            rows.append({
                "company_id": company_id,
                "officer_id": officer_id,
                "name": name,
                "company_name": None,
                "role": (role.get("type") or {}).get("kode"),
                "appointed_on": None,
                "resigned_on": None,
            })
    return rows


def _contract(operation: str, input: dict) -> dict:
    if operation == "company-officers":
        number = _organisation_number(input)
        response = httpx.get(f"{ENDPOINT}/{number}/roller", headers={"Accept": "application/json"}, timeout=20)
        response.raise_for_status()
        records = _officer_rows(response.json(), f"no:{number}")
        return {"source_id": "no/brreg/enheter", "records": records, "page": {"returned": len(records)}}
    if input.get("organisasjonsnummer"):
        endpoint, params = f"{ENDPOINT}/{_organisation_number(input)}", {}
    else:
        params = {"size": max(1, min(int(input.get("size", 100)), 100)), "page": max(0, int(input.get("page", 0)))}
        if isinstance(input.get("navn"), str) and input["navn"].strip():
            params["navn"] = input["navn"].strip()
        postnummer = input.get("postnummer")
        if isinstance(postnummer, str) and postnummer.isdigit() and len(postnummer) == 4:
            params["forretningsadresse.postnummer"] = postnummer
        if len(params) == 2:
            raise ValueError("companies needs organisasjonsnummer, navn or a four-digit postnummer")
        endpoint = ENDPOINT
    response = httpx.get(endpoint, params=params, headers={"Accept": "application/json"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = [data] if not params else (data.get("_embedded") or {}).get("enheter") or []
    page = data.get("page") or {}
    return {
        "source_id": "no/brreg/enheter",
        "records": [_company_row(item) for item in items],
        "page": {"returned": len(items), "total_elements": page.get("totalElements"), "total_pages": page.get("totalPages")},
    }


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    if operation in {"companies", "company-officers"}:
        return _contract(operation, input)
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
