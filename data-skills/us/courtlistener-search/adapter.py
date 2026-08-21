"""Typed CourtListener v4 legal-search adapter."""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
SOURCE_ID = "us/courtlistener/search"
SEARCH_TYPES = {"o", "r", "rd", "d", "p", "oa"}
MAX_RESULTS = 20


def _absolute(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"{BASE}{url}"


def _common(record: dict[str, Any], record_type: str) -> dict[str, Any]:
    meta = record.get("meta") or {}
    return {
        "record_type": record_type,
        "provider_id": record.get("id") or record.get("cluster_id") or record.get("docket_id"),
        "relevance_score": ((meta.get("score") or {}).get("bm25")),
        "source_url": _absolute(record.get("absolute_url") or record.get("docket_absolute_url")),
    }


def _normalize(record: dict[str, Any], record_type: str) -> dict[str, Any]:
    common = _common(record, record_type)
    if record_type == "o":
        return common | {
            "entity": "OpinionCluster",
            "name": record.get("caseName"),
            "court": record.get("court"),
            "court_id": record.get("court_id"),
            "date": record.get("dateFiled"),
            "docket_number": record.get("docketNumber"),
            "docket_id": record.get("docket_id"),
            "cluster_id": record.get("cluster_id"),
            "citations": record.get("citation") or [],
            "judge": record.get("judge"),
            "status": record.get("status"),
            "snippet": record.get("snippet"),
        }
    if record_type in {"r", "d"}:
        return common | {
            "entity": "Docket",
            "name": record.get("caseName"),
            "court": record.get("court"),
            "court_id": record.get("court_id"),
            "date": record.get("dateFiled"),
            "docket_number": record.get("docketNumber"),
            "docket_id": record.get("docket_id"),
            "judge": record.get("assignedTo"),
            "parties": record.get("party") or [],
            "documents": record.get("recap_documents") or [],
            "more_documents": bool((record.get("meta") or {}).get("more_docs")),
        }
    if record_type == "rd":
        return common | {
            "entity": "RECAPDocument",
            "name": record.get("short_description") or record.get("description"),
            "date": record.get("entry_date_filed"),
            "docket_id": record.get("docket_id"),
            "document_id": record.get("id"),
            "docket_entry_id": record.get("docket_entry_id"),
            "document_number": record.get("document_number"),
            "description": record.get("description"),
            "is_available": record.get("is_available"),
            "snippet": record.get("snippet"),
        }
    if record_type == "p":
        return common | {
            "entity": "JudicialPerson",
            "name": record.get("name"),
            "date": record.get("dob"),
            "person_id": record.get("id"),
            "gender": record.get("gender"),
            "races": record.get("races") or [],
            "positions": record.get("positions") or [],
        }
    return common | {
        "entity": "OralArgument",
        "name": record.get("caseName"),
        "court": record.get("court"),
        "court_id": record.get("court_id"),
        "date": record.get("dateArgued"),
        "docket_number": record.get("docketNumber"),
        "docket_id": record.get("docket_id"),
        "audio_id": record.get("id"),
        "download_url": record.get("download_url"),
        "duration_seconds": record.get("duration"),
        "snippet": record.get("snippet"),
        "judge": record.get("judge"),
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
    q = (input.get("q") or input.get("query") or "").strip()
    if not q:
        raise ValueError("q is required.")
    record_type = input.get("type", "o")
    if record_type not in SEARCH_TYPES:
        raise ValueError("type must be one of o, r, rd, d, p, or oa.")
    if input.get("semantic") and record_type != "o":
        raise ValueError("semantic search is available only for type=o case law.")
    limit = int(input.get("limit", 10))
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
    params: dict[str, Any] = {"q": q, "type": record_type}
    if input.get("court"):
        params["court"] = input["court"]
    if input.get("order_by"):
        params["order_by"] = input["order_by"]
    if input.get("semantic"):
        params["semantic"] = "true"
    if input.get("highlight"):
        params["highlight"] = "on"
    response = httpx.get(ENDPOINT, params=params, headers=_headers(ctx), timeout=30)
    response.raise_for_status()
    data = response.json()
    results = (data.get("results") or [])[:limit]
    count = data.get("count")
    return {
        "source_id": SOURCE_ID,
        "record_type": record_type,
        "records": [_normalize(record, record_type) for record in results],
        "page": {
            "limit": limit,
            "returned": len(results),
            "count": count,
            "count_is_approximate": bool(
                record_type in {"r", "d"} and isinstance(count, int) and count > 2000
            ),
            "next": data.get("next"),
            "previous": data.get("previous"),
        },
    }
