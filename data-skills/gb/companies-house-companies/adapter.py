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


# --- Companies domain contract (domains/companies.yaml) -----------------------
# These operations return rows whose columns are the contract's, so they run
# through anomaly.oneshot unmapped. A company_id is "gb:" plus the company number.

PAGE_SIZE = 100
UK_PLACES = ("united kingdom", "england", "wales", "scotland", "northern ireland", "great britain", "uk")


def _company_number(input: dict) -> str:
    number = input.get("company_number")
    if not isinstance(number, str) or not number.strip():
        raise ValueError("company_number is required")
    number = number.strip().upper()
    if len(number) > 8 or not number.isalnum():
        raise ValueError("company_number must contain at most 8 letters or digits")
    return number


def _limit(input: dict, default: int, maximum: int) -> int:
    return max(1, min(int(input.get("limit", default)), maximum))


def _street_address(address: dict | None) -> str | None:
    # Care-of names and the country vary between filings of one address, so the
    # contract address leaves them out (shared_registered_address keys on it).
    if not address:
        return None
    parts = [address.get(key) for key in ("po_box", "premises", "address_line_1", "address_line_2",
                                           "locality", "region", "postal_code")]
    return ", ".join(str(part) for part in parts if part) or None


def _pages(path: str, auth: tuple, limit: int, params: dict | None = None) -> list[dict]:
    """Follow start_index pagination until limit items or the reported total."""
    items: list[dict] = []
    while len(items) < limit:
        page = {**(params or {}), "items_per_page": min(PAGE_SIZE, limit - len(items)), "start_index": len(items)}
        response = httpx.get(f"{API_URL}{path}", params=page, auth=auth, timeout=20)
        response.raise_for_status()
        data = response.json()
        batch = data.get("items") or []
        items.extend(batch)
        total = data.get("total_results", data.get("hits"))
        if not batch or (isinstance(total, int) and len(items) >= total):
            break
    return items[:limit]


def _company_row(item: dict) -> dict:
    number = item.get("company_number")
    previous = item.get("previous_company_names")
    return {
        "company_id": f"gb:{number}",
        "jurisdiction": "GB",
        "name": item.get("company_name") or item.get("title"),
        "status": item.get("company_status"),
        "incorporation_date": item.get("date_of_creation"),
        "dissolution_date": item.get("date_of_cessation"),
        "registered_address": _street_address(item.get("registered_office_address")),
        # Only the full profile lists earlier names; search results leave it empty.
        "previous_name_count": len(previous) if isinstance(previous, list) else None,
        "source_url": f"https://find-and-update.company-information.service.gov.uk/company/{number}",
    }


def _officer_id(item: dict) -> str | None:
    link = ((item.get("links") or {}).get("officer") or {}).get("appointments") or ""
    parts = link.strip("/").split("/")
    return parts[1] if len(parts) == 3 and parts[0] == "officers" else None


def _officer_row(item: dict, company_id: str, company_name: str | None, officer_id: str | None) -> dict:
    return {
        "company_id": company_id,
        "officer_id": officer_id,
        "name": item.get("name"),
        "company_name": company_name,
        "role": item.get("officer_role"),
        "appointed_on": item.get("appointed_on"),
        "resigned_on": item.get("resigned_on"),
    }


def _controller_row(item: dict, company_id: str) -> dict:
    kind = item.get("kind") or ""
    name = item.get("name") or item.get("description") or kind
    identification = item.get("identification") or {}
    if kind.startswith("super-secure"):
        # A protected PSC: Companies House withholds the person, so it is a statement.
        return {"company_id": company_id, "controller_id": f"gb:statement:{kind}", "controller_name": name,
                "controller_kind": "statement", "controller_country": None, "controller_company_id": None,
                "control_type": kind, "notified_on": item.get("notified_on"), "ceased_on": item.get("ceased_on")}
    if kind.startswith("individual"):
        birth = item.get("date_of_birth") or {}
        month = f"|{birth['year']}-{int(birth['month']):02d}" if birth.get("year") and birth.get("month") else ""
        controller_id = f"gb:psc:{name.upper()}{month}"
        country, controller_company_id, controller_kind = item.get("country_of_residence"), None, "individual"
    else:
        # PSCs carry no register-wide id; a UK corporate PSC with a registration
        # number resolves to its own company_id, the link circular_control follows.
        controller_id = f"gb:psc:{name.upper()}"
        country = identification.get("country_registered")
        registered = " ".join(str(identification.get(key) or "") for key in ("country_registered", "place_registered")).lower()
        number = str(identification.get("registration_number") or "").strip().upper().replace(" ", "")
        uk = any(place in registered for place in UK_PLACES) or "companies house" in registered
        controller_company_id = f"gb:{number.zfill(8) if number.isdigit() else number}" if uk and number else None
        controller_kind = "legal_entity"
    return {
        "company_id": company_id,
        "controller_id": controller_id,
        "controller_name": name,
        "controller_kind": controller_kind,
        "controller_country": country,
        "controller_company_id": controller_company_id,
        "control_type": "|".join(item.get("natures_of_control") or []) or None,
        "notified_on": item.get("notified_on"),
        "ceased_on": item.get("ceased_on"),
    }


def _contract(operation: str, input: dict, auth: tuple) -> list[dict]:
    if operation == "companies":
        if input.get("company_number"):
            response = httpx.get(f"{API_URL}/company/{_company_number(input)}", auth=auth, timeout=20)
            response.raise_for_status()
            return [_company_row(response.json())]
        location = input.get("location")
        if not isinstance(location, str) or not location.strip():
            raise ValueError("companies needs location (advanced search) or company_number")
        params = {"location": location.strip()}
        for key in ("incorporated_from", "incorporated_to", "company_status"):
            if input.get(key):
                params[key] = str(input[key])
        # Advanced search pages with size/start_index, up to 5,000 per request.
        limit = _limit(input, 500, 5000)
        response = httpx.get(f"{API_URL}/advanced-search/companies", params={**params, "size": limit, "start_index": 0},
                             auth=auth, timeout=30)
        response.raise_for_status()
        return [_company_row(item) for item in (response.json().get("items") or [])[:limit]]
    if operation == "company-officers":
        number = _company_number(input)
        items = _pages(f"/company/{number}/officers", auth, _limit(input, 100, 1000))
        return [_officer_row(item, f"gb:{number}", None, _officer_id(item)) for item in items]
    if operation == "officer-appointments":
        officer_id = input.get("officer_id")
        if not isinstance(officer_id, str) or not officer_id.strip() or "/" in officer_id:
            raise ValueError("officer_id is required (from company-officers)")
        items = _pages(f"/officers/{officer_id.strip()}/appointments", auth, _limit(input, 500, 5000))
        return [
            _officer_row(item, f"gb:{(item.get('appointed_to') or {}).get('company_number')}",
                         (item.get("appointed_to") or {}).get("company_name"), officer_id.strip())
            for item in items
        ]
    number = _company_number(input)
    items = _pages(f"/company/{number}/persons-with-significant-control", auth, _limit(input, 100, 1000))
    return [_controller_row(item, f"gb:{number}") for item in items]


CONTRACT_OPERATIONS = ("companies", "company-officers", "officer-appointments", "company-controllers")


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    auth = (ctx.get_key("companies-house"), "")
    if operation in CONTRACT_OPERATIONS:
        records = _contract(operation, input, auth)
        return {"source_id": "gb/companies-house/companies", "records": records, "page": {"returned": len(records)}}
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
