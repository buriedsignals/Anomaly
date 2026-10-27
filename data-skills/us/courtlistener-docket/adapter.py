"""CourtListener RECAP dockets: v4 search, plus court-domain contract rows.

``mode`` search/get reads the v4 search API (type=r). ``operation`` court-cases,
case-parties and case-counsel read the PACER database endpoints (/dockets/,
/parties/, /attorneys/) and emit rows shaped like the court domain contract
(domains/court.yaml); SKILL.md maps each field. The database endpoints need a
CourtListener token, and accounts start at 5 requests a minute and 125 a day,
so every operation reads a bounded number of pages or dockets.
"""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
SOURCE_ID = "us/courtlistener/docket"
MAX_RESULTS = 20  # The search API currently returns at most 20 rows per page.
API = f"{BASE}/api/rest/v4"
MAX_PAGES = 5
MAX_DOCKETS = 10
DOCKET_FIELDS = (
    "id,court_id,case_name,docket_number,date_filed,date_terminated,nature_of_suit,"
    "federal_dn_office_code,assigned_to,assigned_to_str,absolute_url"
)


def _absolute(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"{BASE}{url}"


def _score(record: dict[str, Any]) -> float | None:
    return ((record.get("meta") or {}).get("score") or {}).get("bm25")


def _normalize_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document.get("id"),
        "docket_entry_id": document.get("docket_entry_id"),
        "document_number": document.get("document_number"),
        "entry_number": document.get("entry_number"),
        "attachment_number": document.get("attachment_number"),
        "description": document.get("description"),
        "short_description": document.get("short_description"),
        "document_type": document.get("document_type"),
        "entry_date_filed": document.get("entry_date_filed"),
        "is_available": document.get("is_available"),
        "pacer_doc_id": document.get("pacer_doc_id"),
        "page_count": document.get("page_count"),
        "snippet": document.get("snippet"),
        "source_url": _absolute(document.get("absolute_url")),
    }


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    meta = record.get("meta") or {}
    return {
        "entity": "Docket",
        "name": record.get("caseName"),
        "name_full": record.get("case_name_full"),
        "court": record.get("court"),
        "court_id": record.get("court_id"),
        "date_filed": record.get("dateFiled"),
        "date_terminated": record.get("dateTerminated"),
        "docket_number": record.get("docketNumber"),
        "docket_id": record.get("docket_id"),
        "pacer_case_id": record.get("pacer_case_id"),
        "judge": record.get("assignedTo"),
        "judge_id": record.get("assigned_to_id"),
        "referred_to": record.get("referredTo"),
        "referred_to_id": record.get("referred_to_id"),
        "cause": record.get("cause"),
        "chapter": record.get("chapter"),
        "jury_demand": record.get("juryDemand"),
        "suit_nature": record.get("suitNature"),
        "parties": record.get("party") or [],
        "attorneys": record.get("attorney") or [],
        "firms": record.get("firm") or [],
        # CourtListener documents that type=r embeds no more than three
        # matching filings. This must never be represented as a full docket sheet.
        "documents": [
            _normalize_document(item) for item in record.get("recap_documents") or []
        ],
        "more_documents": bool(meta.get("more_docs")),
        "relevance_score": _score(record),
        "source_url": _absolute(record.get("docket_absolute_url")),
    }


def _headers(ctx) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "BuriedSignals-catalogue/1.0",
    }
    token = ctx.get_key_optional("courtlistener") if hasattr(ctx, "get_key_optional") else None
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def _text(value: Any) -> Any:
    return (value.strip() or None) if isinstance(value, str) else value


def _resource_id(url: Any) -> str | None:
    """CourtListener person or docket id from its API URL (…/people/1124/)."""
    if not isinstance(url, str) or not url.rstrip("/"):
        return None
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.isdigit() else None


def _court_case(docket: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": str(docket.get("id")),
        "court_id": docket.get("court_id"),
        "case_name": _text(docket.get("case_name")),
        "docket_number": _text(docket.get("docket_number")),
        "date_filed": docket.get("date_filed"),
        "date_terminated": docket.get("date_terminated"),
        "nature_of_suit": _text(docket.get("nature_of_suit")),
        "division": _text(docket.get("federal_dn_office_code")),
        "assigned_judge_id": _resource_id(docket.get("assigned_to")),
        "assigned_judge_name": _text(docket.get("assigned_to_str")),
        "url": _absolute(docket.get("absolute_url")),
    }


def _case_parties(docket_id: int, party: dict[str, Any]) -> list[dict[str, Any]]:
    # filter_nested_results=True limits party_types to this docket.
    roles = dict.fromkeys(
        _text(kind.get("name")) for kind in party.get("party_types") or []
        if kind.get("docket_id") in (None, docket_id)
    )
    base = {"case_id": str(docket_id), "party_name": _text(party.get("name"))}
    return [base | {"party_role": role} for role in roles if role] or [base | {"party_role": None}]


def _case_counsel(docket_id: int, attorney: dict[str, Any]) -> list[dict[str, Any]]:
    # The attorneys endpoint publishes no firm field.
    return [{"case_id": str(docket_id), "counsel_name": _text(attorney.get("name")), "firm_name": None}]


def _bounded_int(input: dict, name: str, default: int, maximum: int) -> int:
    value = input.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum}.")
    return value


def _iso_date(value: Any, name: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"{name} must be YYYY-MM-DD.")
    return value


def _pages(client, url: str, params: dict | None, pages: int) -> tuple[list[dict], int, str | None]:
    results, fetched = [], 0
    while url and fetched < pages:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        fetched += 1
        results.extend(data.get("results") or [])
        url, params = data.get("next"), None
    return results, fetched, url


def _court_cases(input: dict, client) -> dict:
    court = input.get("court")
    if not isinstance(court, str) or not court.strip():
        raise ValueError("court is required for court-cases.")
    params: dict[str, Any] = {"court": court.strip(), "fields": DOCKET_FIELDS, "order_by": "id"}
    for name, filter_name in (("filed_after", "date_filed__gte"), ("filed_before", "date_filed__lte")):
        value = _iso_date(input.get(name), name)
        if value:
            params[filter_name] = value
    pages = _bounded_int(input, "pages", 1, MAX_PAGES)
    dockets, fetched, next_url = _pages(client, f"{API}/dockets/", params, pages)
    records = [_court_case(docket) for docket in dockets]
    return {"records": records, "page": {"pages_fetched": fetched, "next": next_url, "returned": len(records)}}


def _per_docket(input: dict, client, endpoint: str, rows) -> dict:
    ids = input.get("docket_ids")
    if (not isinstance(ids, list) or not 1 <= len(ids) <= MAX_DOCKETS
            or not all(isinstance(i, int) and not isinstance(i, bool) and i > 0 for i in ids)):
        raise ValueError(f"docket_ids must list 1 to {MAX_DOCKETS} CourtListener docket ids.")
    records, fetched, truncated = [], 0, []
    for docket_id in ids:
        params = {"docket": docket_id, "filter_nested_results": "True"}
        items, pages, next_url = _pages(client, f"{API}/{endpoint}/", params, 1)
        fetched += pages
        if next_url:
            truncated.append(docket_id)
        for item in items:
            records.extend(rows(docket_id, item))
    return {"records": records, "page": {"pages_fetched": fetched, "truncated_dockets": truncated,
                                         "returned": len(records)}}


OPERATIONS = {
    "court-cases": _court_cases,
    "case-parties": lambda input, client: _per_docket(input, client, "parties", _case_parties),
    "case-counsel": lambda input, client: _per_docket(input, client, "attorneys", _case_counsel),
}


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    if operation is not None:
        if operation not in OPERATIONS:
            raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
        with httpx.Client(headers=_headers(ctx), timeout=30) as client:
            return OPERATIONS[operation](input, client)
    mode = input.get("mode", "search")
    if mode not in {"search", "get"}:
        raise ValueError("mode must be search or get.")
    if mode == "get" or input.get("docket_id") is not None:
        if input.get("docket_id") is None:
            raise ValueError("docket_id is required for get-docket.")
        query = f"docket_id:{int(input['docket_id'])}"
    else:
        query = (input.get("q") or "").strip()
        if not query:
            raise ValueError("q is required for search-dockets.")

    limit = int(input.get("limit", 10))
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
    params: dict[str, Any] = {"type": "r", "q": query}
    if input.get("court"):
        params["court"] = input["court"]
    if input.get("order_by"):
        params["order_by"] = input["order_by"]
    if input.get("highlight"):
        params["highlight"] = "on"

    response = httpx.get(ENDPOINT, params=params, headers=_headers(ctx), timeout=30)
    response.raise_for_status()
    data = response.json()
    results = (data.get("results") or [])[:limit]
    count = data.get("count")
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "records": [_normalize(record) for record in results],
        "page": {
            "limit": limit,
            "returned": len(results),
            "count": count,
            "count_is_approximate": bool(isinstance(count, int) and count > 2000),
            "next": data.get("next"),
            "previous": data.get("previous"),
        },
    }
