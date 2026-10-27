"""Adapter for eu/transparency-register/lobbying — EU Transparency Register and Commission meetings.

Streams two official bulk XML exports listed on data.europa.eu and emits rows of
the lobbying domain contract (domains/lobbying.yaml):

- ``lobbying-registrations``: the daily register export, one row per declared
  client of a consultancy, or one row for an organisation lobbying for itself,
  with the closed financial year's money ranges as spend_low/spend_high.
- ``lobbying-contacts``: meetings of Commissioners, their cabinets and
  Directors-General with registered organisations, one row per organisation
  and Commission participant.

The register export declares XML 1.1 and contains control-character references
that XML 1.0 parsers reject, so each line is cleaned before parsing. The
register-to-contract mapping is documented in SKILL.md.
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET

import httpx

SOURCE_ID = "eu/transparency-register/lobbying"
REGISTER_URL = "https://transparency-register.europa.eu/odplastorganisationxml_en"
MEETINGS_URL = "https://ec.europa.eu/transparency-initiative/meetings/data/meetings/dataxml"
MEETING_FILES = {
    "commission-2024": "meetingscommissionrepresentatives2429",
    "commission-2019": "meetingscommissionrepresentatives1924",
    "commission-2014": "meetingscommissionrepresentatives1419",
    "directors-general": "meetingsdirectorgenerals",
}
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
MAX_LIMIT = 100000
# XML 1.0 forbids most C0 control characters, even as character references.
_CONTROL_REFS = re.compile(r"&#(?:x0*(?:[0-8bBcCeE]|1[0-9a-fA-F])|0*(?:[0-8]|1[124-9]|2[0-9]|3[01]));")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _text(element, path: str) -> str | None:
    value = element.findtext(path) if element is not None else None
    value = html.unescape(value).strip() if value else None
    return value or None


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _range(element) -> tuple[float | None, float | None]:
    """(low, high) of a money element: an exact absoluteCost or a range.

    A range with only a maximum is the register's lowest band ("less than"),
    so its low end is zero.
    """
    if element is None:
        return None, None
    exact = _number(_text(element, "absoluteCost"))
    if exact is not None:
        return exact, exact
    high = _number(_text(element, "range/max"))
    low = _number(_text(element, "range/min"))
    if high is None and low is None:
        return None, None
    return (0.0 if low is None else low), (low if high is None else high)


def _elements(client, url: str, tag: str):
    """Stream one XML export and yield each complete ``tag`` element."""
    parser = ET.XMLPullParser(events=("end",))
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            parser.feed(_CONTROL_REFS.sub(" ", line) + "\n")
            for _event, element in parser.read_events():
                if element.tag.rsplit("}", 1)[-1] == tag:
                    yield element
                    element.clear()


def _registration_rows(rep) -> list[dict]:
    code = _text(rep, "identificationCode")
    year = rep.find("financialData/closedYear")
    start = _text(year, "startDate") or (_text(rep, "registrationDate") or "")[:10] or None
    base = {
        "registration_id": code,
        "register": SOURCE_ID,
        "period_start": start,
        "period_end": _text(year, "endDate"),
        "registrant_id": code,
        "registrant_name": _text(rep, "name/originalName"),
        "issue_area": "|".join(filter(None, (_text(i, "name") for i in rep.findall("interests/interest")))) or None,
        "filing_type": _text(rep, "registrationCategory"),
        "head_office_country": _text(rep, "headOffice/country"),
    }
    clients = year.findall("clients/client") if year is not None else []
    if clients:
        rows = []
        for client in clients:
            low, high = _range(client.find("revenue"))
            rows.append(base | {"client_id": None, "client_name": _text(client, "name"), "client_country": None,
                                "spend_low": low, "spend_high": high})
        return rows
    low, high = _range(year.find("costs") if year is not None else None)
    # An organisation lobbying for itself has no client; its own country is
    # the country of the interest represented.
    return [base | {"client_id": None, "client_name": None, "client_country": base["head_office_country"],
                    "spend_low": low, "spend_high": high}]


def _registrations(client, input: dict, limit: int) -> list[dict]:
    ids = set(_list(input, "ids"))
    needle = (input.get("q") or "").strip().casefold()
    country = (input.get("country") or "").strip().upper()
    category = (input.get("category") or "").strip().casefold()
    records: list[dict] = []
    for rep in _elements(client, REGISTER_URL, "interestRepresentative"):
        code = _text(rep, "identificationCode")
        if ids and code not in ids:
            continue
        if needle and needle not in (_text(rep, "name/originalName") or "").casefold():
            continue
        if country and country != (_text(rep, "headOffice/country") or "").upper():
            continue
        if category and category not in (_text(rep, "registrationCategory") or "").casefold():
            continue
        records.extend(_registration_rows(rep))
        if len(records) >= limit:
            break
    return records[:limit]


def _contacts(client, input: dict, limit: int) -> list[dict]:
    files = _list(input, "meetings") or ["commission-2024", "directors-general"]
    if not set(files) <= set(MEETING_FILES):
        raise ValueError(f"meetings must be among: {', '.join(MEETING_FILES)}.")
    ids = set(_list(input, "ids"))
    needle = (input.get("q") or "").strip().casefold()
    since, until = input.get("since"), input.get("until")
    for bound in (since, until):
        if bound is not None and not (isinstance(bound, str) and _DATE.match(bound)):
            raise ValueError("since and until must be YYYY-MM-DD dates.")
    records: list[dict] = []
    seen: set[tuple] = set()
    for name in files:
        for meeting in _elements(client, f"{MEETINGS_URL}?name={MEETING_FILES[name]}", "meeting"):
            day = _text(meeting, "date")
            if (since and (day or "") < since) or (until and (day or "") > until):
                continue
            dg = _text(meeting, "dgname")
            institution = f"{dg} ({_text(meeting, 'dgacronym')})" if dg else _text(meeting, "cabinet")
            subject = _text(meeting, "subject")
            key = "\x1f".join(str(part) for part in (name, institution, day, _text(meeting, "location"), subject))
            contact_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            for entity in meeting.findall("entities/entity"):
                registrant_id, registrant_name = _text(entity, "id"), _text(entity, "name")
                if ids and registrant_id not in ids:
                    continue
                if needle and needle not in (registrant_name or "").casefold():
                    continue
                for person in meeting.findall("representatives/representative"):
                    row = {
                        "contact_id": contact_id,
                        "registrant_id": registrant_id,
                        "registrant_name": registrant_name,
                        "contact_date": day,
                        "official_name": _text(person, "name"),
                        "official_title": _text(person, "title"),
                        "institution": institution,
                        "subject": subject,
                    }
                    # The exports repeat some meetings and entities verbatim.
                    identity = (contact_id, registrant_id, row["official_name"])
                    if identity in seen:
                        continue
                    seen.add(identity)
                    records.append(row)
                    if len(records) >= limit:
                        return records
    return records


def _list(input: dict, name: str) -> list[str]:
    value = input.get(name) or []
    value = [value] if isinstance(value, str) else value
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a string or a list of strings.")
    return value


OPERATIONS = {"lobbying-registrations": _registrations, "lobbying-contacts": _contacts}


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "lobbying-registrations")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    limit = input.get("limit", 20000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    with httpx.Client(headers={"User-Agent": UA}, timeout=300, follow_redirects=True) as client:
        records = OPERATIONS[operation](client, input, limit)
    return {"records": records, "page": {"returned": len(records), "limit": limit}}
