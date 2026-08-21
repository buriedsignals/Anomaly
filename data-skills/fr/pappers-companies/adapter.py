"""Adapter for fr/pappers/companies — Pappers French company search.

BYO-key: Pappers authenticates via an `api-key` header (free tier available).
Two ops: name search (/v2/recherche) and company detail by SIREN (/v2/entreprise).
The key is fetched via ctx.get_key and never enters agent context.
"""

from __future__ import annotations

import httpx

API_URL = "https://api.pappers.fr/v2"
SOURCE_ID = "fr/pappers/companies"


def _compose_address(siege: dict) -> str:
    parts = [
        siege.get("adresse_ligne_1"),
        " ".join(p for p in (siege.get("code_postal"), siege.get("ville")) if p) or None,
    ]
    return ", ".join(p for p in parts if p)


def _normalize(e: dict) -> dict:
    siren = e.get("siren")
    siege = e.get("siege") or {}
    ceased = e.get("entreprise_cessee")
    status = e.get("statut_consolide")
    if status is None and isinstance(ceased, bool):
        status = "ceased" if ceased else "active"
    return {
        "entity": "Company",
        "name": e.get("nom_entreprise") or e.get("denomination") or e.get("nom_complet"),
        "jurisdiction": "fr",
        "siren": siren,
        "legal_form": e.get("forme_juridique"),
        "naf_code": e.get("code_naf"),
        "naf_label": e.get("libelle_code_naf"),
        "incorporation_date": e.get("date_creation"),
        "cessation_date": e.get("date_cessation"),
        "status": status,
        "registered_address": _compose_address(siege),
        "employees_range": e.get("effectif") or e.get("tranche_effectif"),
        "employee_band_code": e.get("tranche_effectif"),
        "source_url": e.get("lien_pappers")
        or (f"https://www.pappers.fr/entreprise/{siren}" if siren else None),
    }


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    headers = {
        "api-key": ctx.get_key("pappers"),
        "User-Agent": "BuriedSignals-Navigator/1.0",
    }
    with httpx.Client(headers=headers, timeout=30) as client:
        if operation == "get-company":
            siren = input.get("siren")
            if not isinstance(siren, str) or not siren.isdigit() or len(siren) != 9:
                raise ValueError("siren must contain exactly 9 digits")
            resp = client.get(
                f"{API_URL}/entreprise",
                params={"siren": siren, "champs_supplementaires": "lien_pappers"},
            )
            resp.raise_for_status()
            return {
                "source_id": SOURCE_ID,
                "mode": "entreprise",
                "records": [_normalize(resp.json())],
                "page": {},
            }
        if operation != "search-companies":
            raise ValueError("a released Pappers operation is required")
        q = input.get("q") or input.get("query")
        if not isinstance(q, str) or not q.strip():
            raise ValueError("q must be a non-empty company-name query")
        params = {
            "q": q.strip(),
            "par_page": max(1, min(int(input.get("par_page", input.get("limit", 10))), 100)),
            "page": max(1, int(input.get("page", 1))),
        }
        resp = client.get(f"{API_URL}/recherche", params=params)
        resp.raise_for_status()
        data = resp.json()
        return {
            "source_id": SOURCE_ID,
            "mode": "recherche",
            "records": [_normalize(e) for e in data.get("resultats", [])],
            "page": {
                "par_page": params["par_page"],
                "page": data.get("page"),
                "total": data.get("total"),
                "pagination_ceiling": 400,
            },
        }
