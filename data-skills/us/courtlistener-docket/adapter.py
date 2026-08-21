"""CourtListener RECAP docket search through the public v4 search API."""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
SOURCE_ID = "us/courtlistener/docket"
MAX_RESULTS = 20  # The search API currently returns at most 20 rows per page.


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
        "User-Agent": "BuriedSignals-Navigator/1.0",
    }
    token = ctx.get_key_optional("courtlistener")
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def run(input: dict, ctx) -> dict:
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
