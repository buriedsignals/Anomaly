"""Adapter for us/congress-legislators/roster — current Congress and committees.

Reads the public-domain unitedstates/congress-legislators JSON files and fills
two lobbying contract tables: ``legislators`` (current members) and
``committee_assignments`` (current committee and subcommittee seats), joined
on bioguide_id.
"""

from __future__ import annotations

import httpx

BASE_URL = "https://unitedstates.github.io/congress-legislators"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
CHAMBERS = {"sen": "senate", "rep": "house"}


def _get(client, name: str):
    response = client.get(f"{BASE_URL}/{name}")
    response.raise_for_status()
    return response.json()


def _legislator(member: dict) -> dict:
    name, term = member.get("name") or {}, (member.get("terms") or [{}])[-1]
    return {
        "bioguide_id": (member.get("id") or {}).get("bioguide"),
        "name": name.get("official_full") or " ".join(p for p in (name.get("first"), name.get("last")) if p),
        "party": term.get("party"),
        "state": term.get("state"),
        "chamber": CHAMBERS.get(term.get("type"), term.get("type")),
    }


def _committee_names(committees: list[dict]) -> dict[str, str]:
    """Map membership-file IDs to names; subcommittee IDs are parent + sub thomas_id."""
    names = {}
    for committee in committees:
        parent_id, parent = committee.get("thomas_id"), committee.get("name")
        names[parent_id] = parent
        for sub in committee.get("subcommittees") or []:
            names[f"{parent_id}{sub.get('thomas_id')}"] = f"{parent}: {sub.get('name')}"
    return names


def _filter(value, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    return value.strip()


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "legislators")
    if operation not in {"legislators", "committee-assignments"}:
        raise ValueError("operation must be legislators or committee-assignments.")
    bioguide = _filter(input.get("bioguide_id"), "bioguide_id").upper()
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as client:
        if operation == "legislators":
            state = _filter(input.get("state"), "state").upper()
            records = [
                record for record in map(_legislator, _get(client, "legislators-current.json"))
                if (not bioguide or record["bioguide_id"] == bioguide)
                and (not state or record["state"] == state)
            ]
            return {"records": records, "page": {"returned": len(records)}}
        committee = _filter(input.get("committee"), "committee").casefold()
        names = _committee_names(_get(client, "committees-current.json"))
        records = []
        for committee_id, members in _get(client, "committee-membership-current.json").items():
            committee_name = names.get(committee_id, committee_id)
            if committee and committee not in committee_name.casefold():
                continue
            for member in members:
                if bioguide and member.get("bioguide") != bioguide:
                    continue
                records.append({
                    "bioguide_id": member.get("bioguide"),
                    "committee_name": committee_name,
                    "role": member.get("title") or "Member",
                    "committee_id": committee_id,
                    "party_side": member.get("party"),
                    "rank": member.get("rank"),
                })
    return {"records": records, "page": {"returned": len(records)}}
