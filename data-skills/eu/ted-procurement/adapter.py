"""Adapter for eu/ted/notices — TED (EU public procurement) notice search.

TED is the EU's Tenders Electronic Daily. The Search API (v3, POST, no key)
takes an expert-syntax query and returns notices; most text fields are
multilingual dicts (language code -> list), so we prefer English and fall back.

Country filter: the API uses ISO 3166-1 alpha-3 codes (DEU, FRA, …). The
adapter accepts alpha-2 (DE, FR, …) and converts internally via a mapping
of EU/EEA/CH countries.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
SOURCE_ID = "eu/ted/notices"
FIELDS = [
    "publication-number",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "publication-date",
]

# ISO 3166-1 alpha-2 → alpha-3 for EU/EEA/CH countries
_A2_TO_A3 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP",
    "CZ": "CZE", "DK": "DNK", "EE": "EST", "FI": "FIN", "FR": "FRA",
    "DE": "DEU", "GR": "GRC", "HU": "HUN", "IE": "IRL", "IT": "ITA",
    "LV": "LVA", "LT": "LTU", "LU": "LUX", "MT": "MLT", "NL": "NLD",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK", "SI": "SVN",
    "ES": "ESP", "SE": "SWE", "IS": "ISL", "LI": "LIE", "NO": "NOR",
    "CH": "CHE", "GB": "GBR", "AL": "ALB", "ME": "MNE", "MK": "MKD",
    "RS": "SRB", "TR": "TUR", "UA": "UKR", "BA": "BIH", "XK": "XKX",
}
_CPV_RE = re.compile(r"^(\d{8})(?:-\d)?$")
_COUNTRY_RE = re.compile(r"^[A-Z]{3}$")
_SCOPES = {"LATEST", "ACTIVE", "ALL"}


def _pick(value: Any, prefer: str = "eng") -> Any:
    """Flatten a TED value: multilingual dict {lang: [str]}, list, or scalar."""
    if isinstance(value, dict):
        chosen = value.get(prefer) or next((v for v in value.values() if v), None)
        return _pick(chosen)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _normalize(n: dict) -> dict:
    pub = n.get("publication-number")
    pub_date = _pick(n.get("publication-date"))
    return {
        "entity": "TenderNotice",
        "name": _pick(n.get("notice-title")),
        "publication_number": pub,
        "buyer": _pick(n.get("buyer-name")),
        "buyer_country": _pick(n.get("buyer-country")),
        "publication_date": (pub_date or "")[:10] or None,
        "source_url": f"https://ted.europa.eu/en/notice/{pub}" if pub else None,
    }


def _build_query(input: dict) -> str:
    if input.get("query") is not None:
        query = input["query"]
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty TED expert query")
        return query.strip()
    parts = []
    if input.get("cpv"):
        cpv = str(input["cpv"]).strip()
        match = _CPV_RE.fullmatch(cpv)
        if not match:
            raise ValueError("cpv must be eight digits, optionally followed by - and its check digit")
        parts.append(f"classification-cpv={match.group(1)}")
    if input.get("country"):
        code = str(input["country"]).strip().upper()
        if len(code) == 2:
            code = _A2_TO_A3.get(code, "")
        if not _COUNTRY_RE.fullmatch(code):
            raise ValueError("country must be a supported alpha-2 or alpha-3 country code")
        parts.append(f"buyer-country={code}")
    if not parts:
        raise ValueError(
            "Provide `query` (TED expert syntax) or `cpv` / `country` shortcuts."
        )
    return " AND ".join(parts)


def run(input: dict, ctx) -> dict:
    scope = input.get("scope", "ALL")
    if scope not in _SCOPES:
        raise ValueError("scope must be one of: LATEST, ACTIVE, ALL")
    body = {
        "query": _build_query(input),
        "fields": FIELDS,
        "limit": max(1, min(int(input.get("limit", 10)), 100)),
        "page": max(1, int(input.get("page", 1))),
        "scope": scope,
        "onlyLatestVersions": bool(input.get("only_latest_versions", False)),
    }
    resp = httpx.post(
        ENDPOINT,
        json=body,
        headers={"User-Agent": "BuriedSignals-Navigator/1.0", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    notices = data.get("notices", [])
    return {
        "source_id": SOURCE_ID,
        "records": [_normalize(n) for n in notices],
        "page": {
            "limit": body["limit"],
            "page": body["page"],
            "total": data.get("totalNoticeCount"),
        },
    }
