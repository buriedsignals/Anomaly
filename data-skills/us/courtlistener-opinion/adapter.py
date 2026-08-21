"""CourtListener case-law opinion search through the public v4 search API."""

from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
SOURCE_ID = "us/courtlistener/opinion"
MAX_RESULTS = 20
ALLOWED_STATUSES = {
    "Published",
    "Unpublished",
    "Errata",
    "Separate",
    "In-chambers",
    "Relating-to",
    "Unknown",
}


def _absolute(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"{BASE}{url}"


def _normalize_opinion(opinion: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": opinion.get("id"),
        "type": opinion.get("type"),
        "author_id": opinion.get("author_id"),
        "snippet": opinion.get("snippet"),
        "per_curiam": opinion.get("per_curiam"),
        "download_url": opinion.get("download_url"),
        "sha1": opinion.get("sha1"),
        "cites": opinion.get("cites") or [],
    }


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity": "OpinionCluster",
        "name": record.get("caseName"),
        "name_full": record.get("caseNameFull") or record.get("case_name_full"),
        "court": record.get("court"),
        "court_id": record.get("court_id"),
        "date_filed": record.get("dateFiled"),
        "date_argued": record.get("dateArgued"),
        "docket_number": record.get("docketNumber"),
        "docket_id": record.get("docket_id"),
        "cluster_id": record.get("cluster_id"),
        "citations": record.get("citation") or [],
        "judge": record.get("judge"),
        "attorney": record.get("attorney"),
        "status": record.get("status"),
        "snippet": record.get("snippet"),
        "opinions": [_normalize_opinion(item) for item in record.get("opinions") or []],
        "cite_count": record.get("citeCount"),
        "relevance_score": (((record.get("meta") or {}).get("score") or {}).get("bm25")),
        "source_url": _absolute(record.get("absolute_url")),
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
    supplied = [key for key in ("q", "cluster_id", "docket_id") if input.get(key) not in (None, "")]
    if len(supplied) != 1:
        raise ValueError("Provide exactly one of q, cluster_id, or docket_id.")
    if supplied[0] == "cluster_id":
        query = f"cluster_id:{int(input['cluster_id'])}"
    elif supplied[0] == "docket_id":
        query = f"docket_id:{int(input['docket_id'])}"
    else:
        query = str(input["q"]).strip()
        if not query:
            raise ValueError("q cannot be blank.")

    limit = int(input.get("limit", 10))
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
    params: dict[str, Any] = {"type": "o", "q": query}
    if input.get("court"):
        params["court"] = input["court"]
    if input.get("order_by"):
        params["order_by"] = input["order_by"]
    if input.get("semantic"):
        if supplied[0] != "q":
            raise ValueError("semantic search can only be used with q.")
        params["semantic"] = "true"
    if input.get("highlight"):
        params["highlight"] = "on"
    for status in input.get("include_statuses") or []:
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported opinion status: {status}.")
        params[f"stat_{status}"] = "on"

    response = httpx.get(ENDPOINT, params=params, headers=_headers(ctx), timeout=30)
    response.raise_for_status()
    data = response.json()
    results = (data.get("results") or [])[:limit]
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(record) for record in results],
        "page": {
            "limit": limit,
            "returned": len(results),
            "count": data.get("count"),
            "next": data.get("next"),
            "previous": data.get("previous"),
        },
    }
