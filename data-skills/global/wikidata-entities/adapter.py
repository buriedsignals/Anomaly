"""Adapter for global/wikidata/entities — Wikidata entity search (public).

Wikidata is the structured-data backbone behind Wikipedia: people, companies,
places, and the identifiers that link them across databases. This is entity
search — resolve a name to a Q-id, label, and description. No key (Wikidata asks
for a descriptive User-Agent, set below).
"""

from __future__ import annotations

import httpx

ENDPOINT = "https://www.wikidata.org/w/api.php"
SOURCE_ID = "global/wikidata/entities"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
ENTITY_TYPES = {"entity-schema", "form", "item", "lexeme", "property", "sense"}


def _normalize(r: dict) -> dict:
    qid = r.get("id")
    concept = r.get("concepturi")
    return {
        "entity": "WikidataEntity",
        "name": r.get("label"),
        "id": qid,
        "description": r.get("description"),
        "match": (r.get("match") or {}).get("text"),
        "match_type": (r.get("match") or {}).get("type"),
        "match_language": (r.get("match") or {}).get("language"),
        "source_url": (
            concept.replace("http://", "https://", 1)
            if isinstance(concept, str)
            else (f"https://www.wikidata.org/wiki/{qid}" if qid else None)
        ),
    }


def run(input: dict, ctx) -> dict:
    q = input.get("q") or input.get("query") or input.get("search")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q is required (name or term to resolve to a Wikidata entity).")
    q = q.strip()
    language = input.get("language", "en")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("language must be a non-empty MediaWiki language code.")
    language = language.strip()
    entity_type = input.get("type", "item")
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"type must be one of: {', '.join(sorted(ENTITY_TYPES))}.")
    limit = int(input.get("limit", 10))
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50.")
    offset = input.get("continue")
    if offset is not None:
        offset = int(offset)
        if offset < 0:
            raise ValueError("continue must be zero or greater.")
    params = {
        "action": "wbsearchentities",
        "search": q,
        "language": language,
        "uselang": language,
        "type": entity_type,
        "limit": limit,
        "format": "json",
    }
    if offset is not None:
        params["continue"] = offset
    if input.get("strictlanguage") is not None:
        strict = input["strictlanguage"]
        if not isinstance(strict, bool):
            raise ValueError("strictlanguage must be a boolean.")
        params["strictlanguage"] = 1 if strict else 0
    resp = httpx.get(ENDPOINT, params=params, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("search", [])
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(r) for r in results],
        "page": {
            "returned": len(results),
            "limit": limit,
            "continue": offset,
            "next_continue": data.get("search-continue"),
        },
    }
