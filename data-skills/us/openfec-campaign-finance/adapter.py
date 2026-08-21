"""OpenFEC candidate and committee entity search (BYO api.data.gov key)."""

from __future__ import annotations

from typing import Any

import httpx

API_URL = "https://api.open.fec.gov/v1"
SOURCE_ID = "us/fec/campaign-finance"

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


def run(input: dict, ctx) -> dict:
    mode = input.get("mode", "candidate")
    if mode not in ("candidate", "committee"):
        raise ValueError(f"Unknown mode `{mode}` — use candidate or committee.")
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
