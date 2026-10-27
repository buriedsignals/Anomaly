"""OpenFEC entity search and campaign finance contract rows (BYO api.data.gov key).

Modes ``candidate`` and ``committee`` search registrations. Modes ``donations``
(Schedule A itemized receipts) and ``recipients`` (committee registrations)
emit rows shaped like the campaign_finance domain contract
(domains/campaign_finance.yaml), so they can be written to a file for
anomaly.oneshot without a column map.
"""

from __future__ import annotations

from typing import Any

import httpx

API_URL = "https://api.open.fec.gov/v1"
SOURCE_ID = "us/fec/campaign-finance"
MAX_PAGES = 20
DONATION_FILTERS = ("committee_id", "contributor_name", "contributor_employer", "contributor_zip",
                    "contributor_state", "two_year_transaction_period", "min_date", "max_date", "min_amount")

_CANDIDATE_ENUMS = {
    "office": {"H", "S", "P"},
    "candidate_status": {"C", "F", "N", "P"},
    "incumbent_challenge": {"I", "C", "O"},
}
_COMMITTEE_ENUMS = {
    "committee_type": set("CDEHINOPQSUVWXYZ"),
    "designation": {"A", "J", "P", "U", "B", "D"},
    "filing_frequency": {"A", "M", "N", "Q", "T", "W", "-A", "-T"},
}


def _integer(value: Any, field: str, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if number < minimum or (maximum is not None and number > maximum):
        upper = f" to {maximum}" if maximum is not None else " or greater"
        raise ValueError(f"{field} must be {minimum}{upper}.")
    return number


def _code(input: dict[str, Any], field: str, allowed: set[str]) -> str | None:
    value = input.get(field)
    if value in (None, ""):
        return None
    value = str(value).upper()
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return value


def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = candidate.get("candidate_id")
    committees = candidate.get("principal_committees") or []
    return {
        "entity": "Candidate",
        "name": candidate.get("name"),
        "candidate_id": candidate_id,
        "party": candidate.get("party_full"),
        "party_code": candidate.get("party"),
        "office": candidate.get("office_full"),
        "office_code": candidate.get("office"),
        "state": candidate.get("state"),
        "district": candidate.get("district"),
        "incumbent_challenge": candidate.get("incumbent_challenge_full"),
        "incumbent_challenge_code": candidate.get("incumbent_challenge"),
        "candidate_status": candidate.get("candidate_status"),
        "candidate_inactive": candidate.get("candidate_inactive"),
        "active_through": candidate.get("active_through"),
        "cycles": candidate.get("cycles") or [],
        "election_years": candidate.get("election_years") or [],
        "has_raised_funds": candidate.get("has_raised_funds"),
        "first_file_date": candidate.get("first_file_date"),
        "last_file_date": candidate.get("last_file_date"),
        "last_form2_date": candidate.get("last_f2_date"),
        "principal_committee_ids": [
            item.get("committee_id")
            for item in committees
            if isinstance(item, dict) and item.get("committee_id")
        ],
        "source_url": (
            f"https://www.fec.gov/data/candidate/{candidate_id}/"
            if candidate_id
            else None
        ),
    }


def _normalize_committee(committee: dict[str, Any]) -> dict[str, Any]:
    committee_id = committee.get("committee_id")
    return {
        "entity": "Committee",
        "name": committee.get("name"),
        "committee_id": committee_id,
        "committee_type": committee.get("committee_type_full"),
        "committee_type_code": committee.get("committee_type"),
        "designation": committee.get("designation_full"),
        "designation_code": committee.get("designation"),
        "organization_type": committee.get("organization_type_full"),
        "organization_type_code": committee.get("organization_type"),
        "filing_frequency": committee.get("filing_frequency"),
        "treasurer": committee.get("treasurer_name"),
        "state": committee.get("state"),
        "party": committee.get("party_full"),
        "party_code": committee.get("party"),
        "cycles": committee.get("cycles") or [],
        "candidate_ids": committee.get("candidate_ids") or [],
        "sponsor_candidate_ids": committee.get("sponsor_candidate_ids") or [],
        "affiliated_committee_name": committee.get("affiliated_committee_name"),
        "first_file_date": committee.get("first_file_date"),
        "last_file_date": committee.get("last_file_date"),
        "first_form1_date": committee.get("first_f1_date"),
        "last_form1_date": committee.get("last_f1_date"),
        "source_url": (
            f"https://www.fec.gov/data/committee/{committee_id}/"
            if committee_id
            else None
        ),
    }


def _base_params(input: dict[str, Any], ctx) -> dict[str, Any]:
    query = input.get("q") or input.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("q is required and must be a non-empty candidate or committee name.")
    return {
        "q": query.strip(),
        "api_key": ctx.get_key("openfec"),
        "per_page": _integer(input.get("per_page", 10), "per_page", minimum=1, maximum=100),
        "page": _integer(input.get("page", 1), "page", minimum=1),
    }


def _candidate_params(input: dict[str, Any], ctx) -> dict[str, Any]:
    params = _base_params(input, ctx)
    for field in ("office", "candidate_status", "incumbent_challenge"):
        value = _code(input, field, _CANDIDATE_ENUMS[field])
        if value:
            params[field] = value
    for field in ("state", "party", "sort"):
        if input.get(field) not in (None, ""):
            params[field] = str(input[field])
    for field in ("cycle", "election_year"):
        if input.get(field) is not None:
            params[field] = _integer(input[field], field, minimum=1976, maximum=2200)
    if input.get("is_active_candidate") is not None:
        if not isinstance(input["is_active_candidate"], bool):
            raise ValueError("is_active_candidate must be true or false.")
        params["is_active_candidate"] = input["is_active_candidate"]
    return params


def _committee_params(input: dict[str, Any], ctx) -> dict[str, Any]:
    params = _base_params(input, ctx)
    for field in ("committee_type", "designation", "filing_frequency"):
        value = _code(input, field, _COMMITTEE_ENUMS[field])
        if value:
            params[field] = value
    for field in ("state", "party", "sort"):
        if input.get(field) not in (None, ""):
            params[field] = str(input[field])
    if input.get("treasurer") not in (None, ""):
        params["treasurer_name"] = str(input["treasurer"])
    for field in ("cycle", "year"):
        if input.get(field) is not None:
            params[field] = _integer(input[field], field, minimum=1976, maximum=2200)
    return params


def _date(value: Any) -> str | None:
    return value[:10] if isinstance(value, str) and value else None


def _donation(item: dict[str, Any]) -> dict[str, Any]:
    committee = item.get("committee") or {}
    return {
        "donation_id": item.get("sub_id"),
        "recipient_id": item.get("committee_id"),
        "recipient_name": item.get("committee_name") or committee.get("name"),
        "recipient_type": committee.get("committee_type_full") or item.get("recipient_committee_type"),
        "donor_name": item.get("contributor_name"),
        "donor_type": item.get("entity_type_desc") or item.get("entity_type"),
        "donor_company_number": None,
        "donor_employer": item.get("contributor_employer"),
        "donor_postcode": item.get("contributor_zip"),
        "amount": item.get("contribution_receipt_amount"),
        "currency": "USD",
        "donation_date": _date(item.get("contribution_receipt_date")),
        "election_type": item.get("election_type"),
        "memo_text": item.get("memo_text"),
        "url": item.get("pdf_url"),
    }


def _recipient(committee: dict[str, Any]) -> dict[str, Any]:
    return {
        "recipient_id": committee.get("committee_id"),
        "name": committee.get("name"),
        # first_f1_date is the first Statement of Organization (Form 1).
        "registered_date": _date(committee.get("first_f1_date") or committee.get("first_file_date")),
        "committee_type": committee.get("committee_type_full"),
    }


def _committee_ids(input: dict[str, Any], most: int) -> list[str]:
    ids = input.get("committee_id")
    if ids in (None, "", []):
        return []
    ids = [ids] if isinstance(ids, str) else ids
    if not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids) or len(ids) > most:
        raise ValueError(f"committee_id must be one id or a list of at most {most}.")
    return ids


def _pages(input: dict[str, Any]) -> int:
    return _integer(input.get("pages", 1), "pages", minimum=1, maximum=MAX_PAGES)


def _donations(input: dict[str, Any], ctx) -> dict:
    """Read Schedule A with keyset pagination, as the OpenFEC docs require."""
    params: dict[str, Any] = {}
    for field in DONATION_FILTERS:
        value = input.get(field)
        if value in (None, ""):
            continue
        if field == "committee_id":
            # Schedule A refuses more than 10 committee ids (HTTP 422).
            value = _committee_ids(input, 10)
        elif field == "two_year_transaction_period":
            value = _integer(value, field, minimum=1976, maximum=2200)
        elif field == "min_amount":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("min_amount must be a non-negative number.")
        elif not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        params[field] = value
    if not {"committee_id", "contributor_name", "contributor_employer", "contributor_zip"} & set(params):
        raise ValueError("name a committee_id, contributor_name, contributor_employer or contributor_zip.")
    is_individual = input.get("is_individual", True)
    if not isinstance(is_individual, bool):
        raise ValueError("is_individual must be true or false.")
    params |= {
        "api_key": ctx.get_key("openfec"),
        "per_page": _integer(input.get("per_page", 100), "per_page", minimum=1, maximum=100),
        "sort": "contribution_receipt_date",
        "is_individual": is_individual,
    }
    pages, records, fetched, last = _pages(input), [], 0, {}
    with httpx.Client(timeout=60) as client:
        while fetched < pages:
            response = client.get(f"{API_URL}/schedules/schedule_a/", params=params | last)
            response.raise_for_status()
            data = response.json()
            fetched += 1
            results = data.get("results") or []
            records.extend(_donation(item) for item in results)
            last = (data.get("pagination") or {}).get("last_indexes") or {}
            if not results or not last:
                break
    return {"source_id": SOURCE_ID, "mode": "donations", "records": records,
            "page": {"pages_fetched": fetched, "next": last or None, "returned": len(records)}}


def _recipients(input: dict[str, Any], ctx) -> dict:
    params: dict[str, Any] = {}
    ids = _committee_ids(input, 100)
    if ids:
        params["committee_id"] = ids
    for field in ("min_first_f1_date", "max_first_f1_date"):
        if input.get(field) not in (None, ""):
            params[field] = str(input[field])
    if not params:
        raise ValueError("name committee_id or a min_first_f1_date/max_first_f1_date range.")
    value = _code(input, "committee_type", _COMMITTEE_ENUMS["committee_type"])
    if value:
        params["committee_type"] = value
    params |= {"api_key": ctx.get_key("openfec"), "per_page": 100,
               "page": _integer(input.get("page", 1), "page", minimum=1)}
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{API_URL}/committees/", params=params)
        response.raise_for_status()
        data = response.json()
    return {"source_id": SOURCE_ID, "mode": "recipients",
            "records": [_recipient(record) for record in data.get("results", [])],
            "page": {"count": (data.get("pagination") or {}).get("count"), "page": params["page"]}}


def run(input: dict, ctx) -> dict:
    mode = input.get("mode", "candidate")
    if mode == "donations":
        return _donations(input, ctx)
    if mode == "recipients":
        return _recipients(input, ctx)
    if mode not in ("candidate", "committee"):
        raise ValueError(f"Unknown mode `{mode}` — use candidate, committee, donations or recipients.")
    if mode == "candidate":
        params = _candidate_params(input, ctx)
        path = "/candidates/search/"
        normalize = _normalize_candidate
    else:
        params = _committee_params(input, ctx)
        path = "/committees/"
        normalize = _normalize_committee
    response = httpx.get(f"{API_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    pagination = data.get("pagination") or {}
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "records": [normalize(record) for record in data.get("results", [])],
        "page": {
            "per_page": pagination.get("per_page", params["per_page"]),
            "page": pagination.get("page", params["page"]),
            "count": pagination.get("count"),
            "pages": pagination.get("pages"),
            "is_count_exact": pagination.get("is_count_exact"),
        },
    }
