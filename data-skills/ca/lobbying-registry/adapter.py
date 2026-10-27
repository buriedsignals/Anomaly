"""Adapter for ca/ocl/registry-of-lobbyists — Canada's federal Registry of Lobbyists.

Reads the two open-data exports of the Office of the Commissioner of Lobbying
(ZIP archives of CSV files, listed on open.canada.ca) and emits rows of the
lobbying domain contract (domains/lobbying.yaml):

- ``lobbying-registrations``: one row per registration version.
- ``lobbyists``: one row per lobbyist and public office they declared, on each
  selected registration.
- ``lobbying-contacts``: one row per designated public office holder (DPOH) in
  a monthly communication report; reports replaced by an amendment are dropped.

lobbycanada.gc.ca answered scripted downloads with a Cloudflare challenge
(HTTP 403) on 2026-10-27, so the archives can also be downloaded in a browser
and passed as ``registrations_zip`` / ``communications_zip``. Column names
follow the published data dictionaries; the mapping is documented in SKILL.md.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

import httpx

SOURCE_ID = "ca/ocl/registry-of-lobbyists"
REGISTRATIONS_URL = "https://lobbycanada.gc.ca/media/zwcjycef/registrations_enregistrements_ocl_cal.zip"
COMMUNICATIONS_URL = "https://lobbycanada.gc.ca/media/mqbbmaqk/communications_ocl_cal.zip"
REGISTRATION_URL = "https://lobbycanada.gc.ca/app/secure/ocl/lrs/do/vwRg?cno={client}&regId={reg}"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
MAX_LIMIT = 200000
REG_TYPES = {"1": "consultant", "2": "in-house corporation", "3": "in-house organization"}
_SUBJECT_CODE = re.compile(r"SMT-\d+")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _archive(client, input: dict, key: str, url: str) -> zipfile.ZipFile:
    local = input.get(key)
    if local is not None:
        if not isinstance(local, str) or not local.lower().endswith(".zip") or not Path(local).is_file():
            raise ValueError(f"{key} must be the path of a downloaded .zip export.")
        return zipfile.ZipFile(local)
    response = client.get(url)
    response.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(response.content))


def _table(archive: zipfile.ZipFile, name: str):
    """Yield the rows of the CSV whose file name (spaces ignored) is ``name``."""
    wanted = name.replace(" ", "").lower()
    member = next((m for m in archive.namelist()
                   if m.rsplit("/", 1)[-1].replace(" ", "").lower() == wanted), None)
    if member is None:
        raise RuntimeError(f"export has no {name}")
    with archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
        for row in csv.DictReader(text):
            yield {(k or "").strip(): (v.strip() or None) if isinstance(v, str) else v for k, v in row.items()}


def _date(value: str | None) -> str | None:
    return value[:10] if value and _DATE.match(value[:10]) else None


def _person(first: str | None, last: str | None) -> str | None:
    return " ".join(part for part in (first, last) if part) or None


def _subjects(archive: zipfile.ZipFile, files: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Subject-matter descriptions per record id, from code columns in ``files``."""
    names = {row["SUBJECT_CODE_OBJET"]: row.get("SMT_EN_DESC") or row["SUBJECT_CODE_OBJET"]
             for row in _table(archive, "Codes_SubjectMatterTypesExport.csv")}
    found: dict[str, list[str]] = {}
    for file, key in files:
        try:
            rows = list(_table(archive, file))
        except RuntimeError:
            continue
        for row in rows:
            text = " ".join(row.get(c) or "" for c in ("SUBJECT_CODE_OBJET", "ASSOC_SUBJECT_CODES_OBJET"))
            for code in _SUBJECT_CODE.findall(text):
                bucket = found.setdefault(row[key], [])
                if names.get(code, code) not in bucket:
                    bucket.append(names.get(code, code))
    return found


def _registrations(archive: zipfile.ZipFile, input: dict, limit: int) -> list[dict]:
    needle = (input.get("q") or "").strip().casefold()
    since = _since(input)
    rows = []
    for row in _table(archive, "Registration_PrimaryExport.csv"):
        start = _date(row.get("EFFECTIVE_DATE_VIGUEUR"))
        if since and (start or "") < since:
            continue
        kind = row.get("REG_TYPE_ENR")
        client = row.get("EN_CLIENT_NM_AN") or row.get("FR_CLIENT_NM")
        person = _person(row.get("RGSTRNT_1ST_NM_PRENOM_DCLRNT"), row.get("RGSTRNT_LAST_NM_DCLRNT"))
        if needle and not any(needle in (text or "").casefold() for text in (client, person, row.get("EN_FIRM_NM_FIRME_AN"))):
            continue
        consultant = kind == "1"
        rows.append({
            "registration_id": row.get("REG_ID_ENR"),
            "register": SOURCE_ID,
            "period_start": start,
            "period_end": _date(row.get("END_DATE_FIN")),
            # A consultant registers as a person; in-house registrations belong
            # to the corporation or organisation, whose number is CLIENT_NUM.
            "registrant_id": row.get("RGSTRNT_NUM_DECLARANT") if consultant else f"org-{row.get('CLIENT_NUM')}",
            "registrant_name": person if consultant else client,
            "client_id": row.get("CLIENT_NUM") if consultant else None,
            "client_name": client if consultant else None,
            "client_country": None,
            "filing_type": REG_TYPES.get(kind, kind),
            "url": REGISTRATION_URL.format(client=row.get("CLIENT_NUM"), reg=row.get("REG_ID_ENR")),
            "firm_name": row.get("EN_FIRM_NM_FIRME_AN") or row.get("FR_FIRM_NM_FIRME"),
            "client_profile_id": row.get("CLIENT_PROFILE_ID_PROFIL_CLIENT"),
        })
        if len(rows) >= limit:
            break
    subjects = _subjects(archive, [("Registration_SubjectMattersExport.csv", "REG_ID_ENR"),
                                   ("Registration_SubjectMatterDetails Export.csv", "REG_ID_ENR")])
    for row in rows:
        row["issue_area"] = "|".join(subjects.get(row["registration_id"], [])) or None
    return rows


def _lobbyists(archive: zipfile.ZipFile, input: dict, limit: int) -> list[dict]:
    registrations = _registrations(archive, input, MAX_LIMIT)
    by_consultant: dict[tuple, list[str]] = {}
    by_profile: dict[str, list[str]] = {}
    for reg in registrations:
        if reg["filing_type"] == "consultant":
            by_consultant.setdefault((reg["registrant_id"], reg["client_profile_id"]), []).append(reg["registration_id"])
        else:
            by_profile.setdefault(reg["client_profile_id"], []).append(reg["registration_id"])
    offices: dict[str, list[dict]] = {}
    for row in _table(archive, "Registration_PublicOfficeExport.csv"):
        offices.setdefault(row.get("LOBBYIST_ID_LOBBYISTE"), []).append(row)
    people = [(row, by_consultant.get((row.get("RGSTRNT_NUM_DECLARANT"), row.get("CLIENT_PROFILE_ID_PROFIL_CLIENT")), []),
               row.get("LBBYST_1ST_NM_PRENOM_LBBYST"))
              for row in _table(archive, "Registration_ConsultantLobbyistsExport.csv")]
    people += [(row, by_profile.get(row.get("CLIENT_PROFILE_ID_PROFIL_CLIENT"), []), row.get("LBBYST_FIRST_NM_PRENOM_LBBYST"))
               for row in _table(archive, "Registration_InHouseLobbyistsExport.csv")]
    records = []
    for row, registration_ids, first in people:
        lobbyist_id = row.get("LBBYST_ID_LBBYST")
        name = _person(first, row.get("LBBYST_LAST_NM_LBBYST"))
        held = offices.get(lobbyist_id) or [{}]
        for registration_id in registration_ids:
            for office in held:
                records.append({
                    "registration_id": registration_id,
                    "lobbyist_id": lobbyist_id,
                    "name": name,
                    "former_public_office": office.get("TITLE_TITRE") or office.get("POH_DETAILS _PRE_V5_INFO_TCP"),
                    "former_office_institution": office.get("INSTITUTION"),
                    "former_office_end": _date(office.get("POS_END_DATE_FIN_POSTE")) or _date(office.get("DPOH_LAST_DATE_FIN_TCPD")),
                })
                if len(records) >= limit:
                    return records
    return records


def _contacts(archive: zipfile.ZipFile, input: dict, limit: int) -> list[dict]:
    needle = (input.get("q") or "").strip().casefold()
    since = _since(input)
    reports = list(_table(archive, "Communication_PrimaryExport.csv"))
    replaced = {row.get("PREV_COMLOG_ID_PRECEDNT") for row in reports}
    kept = {}
    for row in reports:
        date = _date(row.get("COMM_DATE"))
        if row.get("COMLOG_ID") in replaced or (since and (date or "") < since):
            continue
        client = row.get("EN_CLIENT_ORG_CORP_NM_AN") or row.get("FR_CLIENT_ORG_CORP_NM")
        person = _person(row.get("RGSTRNT_1ST_NM_PRENOM_DCLRNT"), row.get("RGSTRNT_LAST_NM_DCLRNT"))
        if needle and not any(needle in (text or "").casefold() for text in (client, person)):
            continue
        consultant = row.get("REG_TYPE_ENR") == "1"
        kept[row.get("COMLOG_ID")] = {
            "registrant_id": row.get("REGISTRANT_NUM_DECLARANT") if consultant else f"org-{row.get('CLIENT_ORG_CORP_NUM')}",
            "registrant_name": person if consultant else client,
            "contact_date": date,
            "client_name": client,
        }
    subjects = _subjects(archive, [("Communication_SubjectMattersExport.csv", "COMLOG_ID")])
    records = []
    for row in _table(archive, "Communication_DPOHExport.csv"):
        report = kept.get(row.get("COMLOG_ID"))
        if report is None:
            continue
        institution = row.get("INSTITUTION")
        if institution in (None, "Other") and row.get("OTHER_INSTITUTION_AUTRE"):
            institution = row.get("OTHER_INSTITUTION_AUTRE")
        records.append({
            "contact_id": row.get("COMLOG_ID"),
            **report,
            "official_name": _person(row.get("DPOH_FIRST_NM_PRENOM_TCPD"), row.get("DPOH_LAST_NM_TCPD")),
            "official_title": row.get("DPOH_TITLE_TITRE_TCPD"),
            "institution": institution,
            "subject": "|".join(subjects.get(row.get("COMLOG_ID"), [])) or None,
        })
        if len(records) >= limit:
            break
    return records


def _since(input: dict) -> str | None:
    since = input.get("since")
    if since is not None and not (isinstance(since, str) and _DATE.match(since)):
        raise ValueError("since must be a YYYY-MM-DD date.")
    return since


OPERATIONS = {
    "lobbying-registrations": ("registrations_zip", REGISTRATIONS_URL, _registrations),
    "lobbyists": ("registrations_zip", REGISTRATIONS_URL, _lobbyists),
    "lobbying-contacts": ("communications_zip", COMMUNICATIONS_URL, _contacts),
}


def run(input: dict, ctx) -> dict:
    operation = input.get("operation", "lobbying-registrations")
    if operation not in OPERATIONS:
        raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    limit = input.get("limit", 50000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    key, url, rows = OPERATIONS[operation]
    with httpx.Client(headers={"User-Agent": UA}, timeout=300, follow_redirects=True) as client:
        with _archive(client, input, key, url) as archive:
            records = rows(archive, input, limit)
    return {"records": records, "page": {"returned": len(records), "limit": limit}}
