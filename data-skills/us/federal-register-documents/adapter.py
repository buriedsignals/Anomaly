"""Adapter for us/federal-register/documents — Federal Register search (public).

The daily journal of the US government: rules, proposed rules, notices, and
presidential documents. Full-text search, no key.
"""

from __future__ import annotations

import httpx

ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
SOURCE_ID = "us/federal-register/documents"
DOCUMENT_TYPES = {"RULE", "PRORULE", "NOTICE", "PRESDOCU"}
ORDERS = {"relevance", "newest", "oldest", "executive_order_number"}


def _normalize(d: dict) -> dict:
    return {
        "entity": "Document",
        "name": d.get("title"),
        "document_number": d.get("document_number"),
        "type": d.get("type"),
        "agencies": [a.get("name") for a in (d.get("agencies") or []) if a.get("name")],
        "publication_date": d.get("publication_date"),
        "effective_on": d.get("effective_on"),
        "abstract": d.get("abstract"),
        "source_url": d.get("html_url"),
        "official_pdf_url": d.get("pdf_url"),
    }


def run(input: dict, ctx) -> dict:
    q = input.get("q") or input.get("query") or input.get("term")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q is required (full-text term).")
    document_type = input.get("type")
    if document_type is not None and document_type not in DOCUMENT_TYPES:
        raise ValueError("type must be one of: RULE, PRORULE, NOTICE, PRESDOCU")
    order = input.get("order", "newest")
    if order not in ORDERS:
        raise ValueError(
            "order must be one of: relevance, newest, oldest, executive_order_number"
        )
    per_page = max(1, min(int(input.get("per_page", 10)), 100))
    page = max(1, int(input.get("page", 1)))
    params = {
        "conditions[term]": q.strip(),
        "per_page": per_page,
        "page": page,
        "order": order,
    }
    if document_type:
        params["conditions[type][]"] = document_type
    if input.get("agency"):
        params["conditions[agencies][]"] = input["agency"]
    resp = httpx.get(
        ENDPOINT,
        params=params,
        headers={"User-Agent": "BuriedSignals-catalogue/1.0"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(d) for d in results],
        "page": {
            "count": data.get("count"),
            "returned": len(results),
            "current_page": page,
            "total_pages": data.get("total_pages"),
            "next_page_url": data.get("next_page_url"),
        },
    }
