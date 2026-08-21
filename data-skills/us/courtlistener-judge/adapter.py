"""CourtListener judge/person search and exact retrieval."""

from __future__ import annotations

from typing import Any

import httpx

PEOPLE_ENDPOINT = "https://www.courtlistener.com/api/rest/v4/people/"
SEARCH_ENDPOINT = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
SOURCE_ID = "us/courtlistener/judge"
MAX_RESULTS = 20

RACE_MAP = {
    "w": "White",
    "b": "Black / African American",
    "h": "Hispanic / Latino",
    "a": "Asian",
    "i": "American Indian / Alaska Native",
    "p": "Native Hawaiian / Pacific Islander",
}
GENDER_MAP = {"m": "Male", "f": "Female", "o": "Other"}


def _absolute(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"{BASE}{url}"


def _detail(record: dict[str, Any]) -> dict[str, Any]:
    person_id = record.get("id")
    slug = record.get("slug")
    educations = []
    for item in record.get("educations") or []:
        school = item.get("school") or {}
        educations.append(
            {
                "school": school.get("name"),
                "school_id": school.get("id"),
                "degree_level": item.get("degree_level"),
                "degree_detail": item.get("degree_detail"),
                "degree_year": item.get("degree_year"),
            }
        )
    return {
        "entity": "JudicialPerson",
        "id": person_id,
        "name": " ".join(
            str(value)
            for value in (
                record.get("name_first"),
                record.get("name_middle"),
                record.get("name_last"),
                record.get("name_suffix"),
            )
            if value
        ),
        "name_first": record.get("name_first"),
        "name_middle": record.get("name_middle"),
        "name_last": record.get("name_last"),
        "name_suffix": record.get("name_suffix"),
        "slug": slug,
        "date_dob": record.get("date_dob"),
        "date_dob_granularity": record.get("date_granularity_dob"),
        "dob_city": record.get("dob_city"),
        "dob_state": record.get("dob_state"),
        "dob_country": record.get("dob_country"),
        "date_dod": record.get("date_dod"),
        "date_dod_granularity": record.get("date_granularity_dod"),
        "gender": GENDER_MAP.get(record.get("gender"), record.get("gender")),
        "race": [RACE_MAP.get(code, code) for code in record.get("race") or []],
        "religion": record.get("religion"),
        "political_affiliations": record.get("political_affiliations") or [],
        "aba_ratings": record.get("aba_ratings") or [],
        "educations": educations,
        "position_urls": record.get("positions") or [],
        "positions_count": len(record.get("positions") or []),
        "has_photo": record.get("has_photo"),
        "fjc_id": record.get("fjc_id"),
        "is_alias_of": record.get("is_alias_of"),
        "source_url": f"{BASE}/person/{person_id}/{slug}/" if person_id and slug else None,
    }


def _search_result(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity": "JudicialPerson",
        "id": record.get("id"),
        "name": record.get("name"),
        "date_dob": record.get("dob"),
        "date_dob_granularity": record.get("date_granularity_dob"),
        "date_dod": record.get("dod"),
        "date_dod_granularity": record.get("date_granularity_dod"),
        "dob_city": record.get("dob_city"),
        "dob_state": record.get("dob_state"),
        "gender": record.get("gender"),
        "race": record.get("races") or [],
        "religion": record.get("religion"),
        "political_affiliations": record.get("political_affiliation") or [],
        "aba_ratings": record.get("aba_rating") or [],
        "educations": record.get("school") or [],
        "positions": record.get("positions") or [],
        "positions_count": len(record.get("positions") or []),
        "fjc_id": record.get("fjc_id"),
        "relevance_score": (((record.get("meta") or {}).get("score") or {}).get("bm25")),
        "source_url": _absolute(record.get("absolute_url")),
    }


def _headers(ctx) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "BuriedSignals-catalogue/1.0",
    }
    token = ctx.get_key_optional("courtlistener")
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def run(input: dict, ctx) -> dict:
    mode = input.get("mode", "search")
    limit = int(input.get("limit", 10))
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
    headers = _headers(ctx)

    if mode == "get":
        if input.get("person_id") is None:
            raise ValueError("person_id is required for get-judge.")
        response = httpx.get(
            f"{PEOPLE_ENDPOINT}{int(input['person_id'])}/", headers=headers, timeout=30
        )
        response.raise_for_status()
        return {
            "source_id": SOURCE_ID,
            "mode": mode,
            "records": [_detail(response.json())],
            "page": {"limit": 1, "returned": 1},
        }

    if mode != "search":
        raise ValueError("mode must be search or get.")
    q = (input.get("q") or "").strip()
    if q:
        params: dict[str, Any] = {"type": "p", "q": q}
        response = httpx.get(SEARCH_ENDPOINT, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = (data.get("results") or [])[:limit]
        return {
            "source_id": SOURCE_ID,
            "mode": mode,
            "records": [_search_result(record) for record in results],
            "page": {
                "limit": limit,
                "returned": len(results),
                "count": data.get("count"),
                "next": data.get("next"),
                "previous": data.get("previous"),
            },
        }

    params = {}
    if input.get("name_first"):
        params["name_first"] = input["name_first"]
    if input.get("name_last"):
        params["name_last"] = input["name_last"]
    if not params:
        raise ValueError("Provide q, name_first, or name_last.")
    response = httpx.get(PEOPLE_ENDPOINT, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    results = (data.get("results") or [])[:limit]
    count = data.get("count")
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "records": [_detail(record) for record in results],
        "page": {
            "limit": limit,
            "returned": len(results),
            "count": count if isinstance(count, int) else None,
            "count_url": count if isinstance(count, str) else None,
            "next": data.get("next"),
            "previous": data.get("previous"),
        },
    }
