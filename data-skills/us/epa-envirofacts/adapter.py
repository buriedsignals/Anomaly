"""EPA Envirofacts DMAP queries for TRI facilities and SDWIS water systems."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

API_BASE = "https://data.epa.gov/dmapservice"
SOURCE_ID = "us/epa/envirofacts"
TABLES = {"tri": "tri.tri_facility", "water": "sdwis.water_system"}
ALIASES = {
    "tri": "tri",
    "tri_facility": "tri",
    "facility": "tri",
    "water": "water",
    "sdwis": "water",
    "water_system": "water",
}


def _segment(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("filter values cannot be blank.")
    return quote(text, safe="")


def _mode(input: dict) -> str:
    raw = input.get("mode")
    if raw:
        mode = ALIASES.get(str(raw).lower())
        if not mode:
            raise ValueError("mode must be tri or water.")
        return mode
    if input.get("pwsid"):
        return "water"
    return "tri"


def _source_url(mode: str, identifier: Any) -> str | None:
    if not identifier:
        return None
    column = "tri_facility_id" if mode == "tri" else "pwsid"
    return f"{API_BASE}/{TABLES[mode]}/{column}/equals/{_segment(identifier)}/1:1/json"


def _normalize(raw: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "tri":
        identifier = raw.get("tri_facility_id")
        return {
            "entity": "TRIFacility",
            "name": raw.get("facility_name"),
            "tri_facility_id": identifier,
            "epa_registry_id": raw.get("epa_registry_id"),
            "street_address": raw.get("street_address"),
            "city": raw.get("city_name"),
            "county": raw.get("county_name"),
            "state": raw.get("state_abbr"),
            "zip": raw.get("zip_code"),
            "parent_company": raw.get("standardized_parent_company")
            or raw.get("parent_co_name"),
            "foreign_parent_company": raw.get("standardized_foreign_parent_company")
            or raw.get("foreign_parent_co_name"),
            "latitude": raw.get("pref_latitude"),
            "longitude": raw.get("pref_longitude"),
            "closed": raw.get("fac_closed_ind") == "1",
            "source_url": _source_url(mode, identifier),
        }
    identifier = raw.get("pwsid")
    return {
        "entity": "WaterSystem",
        "name": raw.get("pws_name"),
        "pwsid": identifier,
        "system_type": raw.get("pws_type_code"),
        "active": raw.get("pws_activity_code") == "A",
        "activity_code": raw.get("pws_activity_code"),
        "deactivation_date": raw.get("pws_deactivation_date"),
        "population_served": raw.get("population_served_count"),
        "service_connections": raw.get("service_connections_count"),
        "primary_source": raw.get("primary_source_code") or raw.get("gw_sw_code"),
        "owner_type": raw.get("owner_type_code"),
        "city": raw.get("city_name"),
        "state": raw.get("state_code"),
        "zip": raw.get("zip_code"),
        "source_url": _source_url(mode, identifier),
    }


def _url(mode: str, input: dict) -> str:
    filters: list[tuple[str, str, Any]] = []
    if mode == "tri":
        identifier = input.get("id") or input.get("tri_facility_id")
        if identifier:
            filters.append(("tri_facility_id", "equals", identifier))
        if input.get("state"):
            filters.append(("state_abbr", "equals", str(input["state"]).upper()))
        if input.get("name"):
            filters.append(("facility_name", "contains", input["name"]))
    else:
        identifier = input.get("id") or input.get("pwsid")
        if identifier:
            filters.append(("pwsid", "equals", identifier))
        if input.get("state"):
            filters.append(("state_code", "equals", str(input["state"]).upper()))
        if input.get("name"):
            filters.append(("pws_name", "contains", input["name"]))
    if input.get("city"):
        filters.append(("city_name", "contains", input["city"]))
    if not filters:
        raise ValueError(
            "Provide at least one filter: state, name, city, or an exact identifier."
        )

    limit = int(input.get("limit", 10))
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")
    path = "/and/".join(
        f"{column}/{operator}/{_segment(value)}" for column, operator, value in filters
    )
    sort_column = "facility_name" if mode == "tri" else "pws_name"
    return (
        f"{API_BASE}/{TABLES[mode]}/{path}/sort/{sort_column}:asc/"
        f"1:{limit}/json"
    )


def run(input: dict, ctx) -> dict:
    mode = _mode(input)
    url = _url(mode, input)
    limit = int(input.get("limit", 10))
    with httpx.Client(
        headers={"Accept": "application/json", "User-Agent": "BuriedSignals-catalogue/1.0"},
        timeout=30,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list):
        raise ValueError(f"Unexpected Envirofacts response shape: {type(rows).__name__}")
    return {
        "source_id": SOURCE_ID,
        "mode": mode,
        "records": [_normalize(row, mode) for row in rows],
        "page": {"limit": limit, "returned": len(rows), "first": 1, "last": limit},
    }
