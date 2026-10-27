"""Adapter for global/partyfacts/parties — Party Facts party crosswalk (public).

Party Facts links political-party identifiers across political-science datasets
(ParlGov, Manifesto Project, and others). It publishes two CSV tables with no
API key: core parties (one row per Party Facts party) and external parties (one
row per party in a linked dataset, carrying the partyfacts_id it maps to).
Three ops: search core parties, get one core party, list its external links.
"""

from __future__ import annotations

import csv

import httpx

DOWNLOAD_URL = "https://partyfacts.herokuapp.com/download"
CORE_CSV = f"{DOWNLOAD_URL}/core-parties-csv/"
EXTERNAL_CSV = f"{DOWNLOAD_URL}/external-parties-csv/"
SOURCE_ID = "global/partyfacts/parties"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
NAME_FIELDS = ("name", "name_short", "name_english", "name_other")


def _party_url(partyfacts_id) -> str | None:
    return f"https://partyfacts.herokuapp.com/data/partycodes/{partyfacts_id}/" if partyfacts_id else None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _core(row: dict) -> dict:
    pid = _int(row.get("partyfacts_id"))
    return {
        "entity": "PoliticalParty",
        "partyfacts_id": pid,
        "name": row.get("name") or None,
        "name_short": row.get("name_short") or None,
        "name_english": row.get("name_english") or None,
        "name_other": row.get("name_other") or None,
        "country": row.get("country") or None,
        "year_first": _int(row.get("year_first")),
        "year_last": _int(row.get("year_last")),
        "share": row.get("share") or None,
        "share_year": _int(row.get("share_year")),
        "technical": _int(row.get("technical")),
        "wikipedia": row.get("wikipedia") or None,
        "source_url": _party_url(pid),
    }


def _external(row: dict) -> dict:
    pid = _int(row.get("partyfacts_id"))
    return {
        "entity": "ExternalPartyLink",
        "partyfacts_id": pid,
        "dataset_key": row.get("dataset_key") or None,
        "dataset_party_id": row.get("dataset_party_id") or None,
        "external_id": _int(row.get("external_id")),
        "name": row.get("name") or None,
        "name_short": row.get("name_short") or None,
        "name_english": row.get("name_english") or None,
        "country": row.get("country") or None,
        "year_first": _int(row.get("year_first")),
        "year_last": _int(row.get("year_last")),
        "source_url": _party_url(pid),
    }


def _rows(client, url: str):
    """Stream one Party Facts CSV table as dict rows (header names per the codebook)."""
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        yield from csv.DictReader(resp.iter_lines())


def _limit(input: dict, default: int, maximum: int) -> int:
    limit = int(input.get("limit", default))
    if not 1 <= limit <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}.")
    return limit


def _partyfacts_id(input: dict) -> int:
    pid = _int(input.get("partyfacts_id"))
    if pid is None or pid < 1:
        raise ValueError("partyfacts_id must be a positive integer.")
    return pid


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    if operation not in {"search-parties", "get-party", "list-external-links"}:
        raise ValueError("a released Party Facts operation is required")
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as client:
        if operation == "search-parties":
            q = input.get("q") or input.get("query") or ""
            country = input.get("country") or ""
            if not isinstance(q, str) or not isinstance(country, str):
                raise ValueError("q and country must be strings.")
            q, country = q.strip().casefold(), country.strip().upper()
            if not q and not country:
                raise ValueError("q (party name) or country (ISO 3166-1 alpha-3) is required.")
            limit = _limit(input, 20, 100)
            matched = []
            for row in _rows(client, CORE_CSV):
                if country and (row.get("country") or "").upper() != country:
                    continue
                if q and not any(q in (row.get(field) or "").casefold() for field in NAME_FIELDS):
                    continue
                matched.append(_core(row))
            records = matched[:limit]
            return {"source_id": SOURCE_ID, "records": records,
                    "page": {"returned": len(records), "matched": len(matched), "limit": limit}}
        pid = _partyfacts_id(input)
        if operation == "get-party":
            records = [_core(row) for row in _rows(client, CORE_CSV) if _int(row.get("partyfacts_id")) == pid]
            return {"source_id": SOURCE_ID, "records": records[:1], "page": {"returned": len(records[:1])}}
        limit = _limit(input, 100, 500)
        matched = [_external(row) for row in _rows(client, EXTERNAL_CSV) if _int(row.get("partyfacts_id")) == pid]
        records = matched[:limit]
        return {"source_id": SOURCE_ID, "records": records,
                "page": {"returned": len(records), "matched": len(matched), "limit": limit}}
