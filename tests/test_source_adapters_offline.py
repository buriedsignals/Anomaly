"""Offline fixture tests for source adapters.

A fake ``httpx`` serves fixtures shaped like each provider's documented (and
live-checked) responses, so each adapter runs through the real registry and
result contract without network.
"""

from __future__ import annotations

import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

from anomaly import domains
from anomaly.sources.contract import validate_source_result
from anomaly.sources.registry import discover_sources, load_source_adapter

SOURCE_ROOT = Path(__file__).parents[1] / "data-skills"

PF = "https://partyfacts.herokuapp.com/download"
CORE_CSV = (
    "country,partyfacts_id,technical,name_short,name,name_english,name_other,year_first,"
    "year_last,share,share_year,new,wikipedia,description,comment,created,modified\n"
    "GBR,1001,,Lab,Labour Party,Labour Party,,1900,,40.0,2017,,https://en.wikipedia.org/wiki/Labour_Party_(UK),,,,\n"
    "NZL,1002,,Lab,New Zealand Labour Party,Labour Party,,1916,,50.0,2020,,,,,,\n"
    "GBR,1003,,Con,Conservative Party,Conservative Party,,1834,,43.6,2019,,,,,,\n"
)
EXTERNAL_CSV = (
    "country,dataset_key,dataset_party_id,name_short,name,name_english,year_first,year_last,"
    "share,share_year,description,comment,created,modified,external_id,partyfacts_id\n"
    "GBR,parlgov,1001,Lab,Labour Party,Labour Party,1945,,,,,,,,501,1001\n"
    "GBR,manifesto,51320,Lab,Labour Party,Labour Party,1945,,,,,,,,502,1001\n"
    "GBR,parlgov,773,Con,Conservative Party,Conservative Party,1945,,,,,,,,503,1003\n"
)

DH = "https://datahub.io/core"
GDP_PACKAGE = {
    "name": "gdp",
    "title": "Country, Regional and World GDP",
    "last_updated": "2026-04-08",
    "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/",
                  "title": "Creative Commons Attribution 4.0"}],
    "resources": [
        {"name": "top-economies", "path": "data/top-economies.csv", "format": "csv"},
        {"name": "gdp", "path": "data/gdp.csv",
         "schema": {"fields": [{"name": "Country Name"}, {"name": "Year"}, {"name": "Value"}]}},
    ],
}
GDP_CSV = "Country Name,Year,Value\nAruba,1986,405586592\nAruba,1987,487709497\nAruba,1988,596648045\n"


class _FakeResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status_code = status
        self._body = body
        self.text = body
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self._body)

    def iter_lines(self):
        yield from self._body.splitlines()


def _fake_httpx(routes: dict[str, str], requested: list[str], params: list[dict]) -> types.ModuleType:
    class Client:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, url: str, **kwargs) -> _FakeResponse:
            requested.append(url)
            params.append(kwargs.get("params") or {})
            return _FakeResponse(200, routes[url]) if url in routes else _FakeResponse(404, "")

        @contextmanager
        def stream(self, _method: str, url: str, **_kwargs):
            yield self.get(url)

    module = types.ModuleType("httpx")
    module.Client = Client
    return module


@pytest.fixture
def run_source(monkeypatch: pytest.MonkeyPatch):
    requested: list[str] = []
    params: list[dict] = []
    routes = {
        f"{PF}/core-parties-csv/": CORE_CSV,
        f"{PF}/external-parties-csv/": EXTERNAL_CSV,
        f"{DH}/gdp/_r/-/datapackage.json": json.dumps(GDP_PACKAGE),
        f"{DH}/gdp/_r/-/data/gdp.csv": GDP_CSV,
    }

    def run(source_id: str, payload: dict, extra_routes: dict[str, str] | None = None) -> dict:
        routes.update(extra_routes or {})
        monkeypatch.setitem(sys.modules, "httpx", _fake_httpx(routes, requested, params))
        adapter = load_source_adapter(discover_sources(SOURCE_ROOT), source_id)
        return validate_source_result(adapter.run(payload, None))

    run.requested = requested
    run.params = params
    return run


def test_partyfacts_search_filters_core_parties_by_name_and_country(run_source) -> None:
    result = run_source("global/partyfacts/parties",
                        {"operation": "search-parties", "q": "LABOUR", "country": "gbr"})

    assert result["status"] == "ok"
    assert [(r["partyfacts_id"], r["country"]) for r in result["records"]] == [(1001, "GBR")]
    record = result["records"][0]
    assert record["entity"] == "PoliticalParty"
    assert record["year_first"] == 1900 and record["year_last"] is None
    assert record["source_url"] == "https://partyfacts.herokuapp.com/data/partycodes/1001/"


def test_partyfacts_get_party_and_external_links_use_the_right_tables(run_source) -> None:
    party = run_source("global/partyfacts/parties", {"operation": "get-party", "partyfacts_id": 1003})
    links = run_source("global/partyfacts/parties",
                       {"operation": "list-external-links", "partyfacts_id": "1001"})

    assert [r["name"] for r in party["records"]] == ["Conservative Party"]
    assert [(r["dataset_key"], r["dataset_party_id"]) for r in links["records"]] == [
        ("parlgov", "1001"), ("manifesto", "51320"),
    ]
    assert run_source.requested == [f"{PF}/core-parties-csv/", f"{PF}/external-parties-csv/"]


def test_partyfacts_search_without_name_or_country_is_an_invalid_request(run_source) -> None:
    result = run_source("global/partyfacts/parties", {"operation": "search-parties"})

    assert result["status"] == "error"
    assert result["error"]["code"] == "invalid-source-request"
    assert run_source.requested == []


def test_datahub_package_carries_the_dataset_licence_and_resource_urls(run_source) -> None:
    result = run_source("global/datahub/core-datasets", {"operation": "get-package", "dataset": "gdp"})

    record = result["records"][0]
    assert record["license"] == "CC-BY-4.0"
    assert record["licenses"][0]["path"] == "https://creativecommons.org/licenses/by/4.0/"
    assert {r["name"]: r["url"] for r in record["resources"]} == {
        "top-economies": f"{DH}/gdp/_r/-/data/top-economies.csv",
        "gdp": f"{DH}/gdp/_r/-/data/gdp.csv",
    }
    assert record["resources"][1]["fields"] == ["Country Name", "Year", "Value"]


def test_datahub_fetch_resource_returns_bounded_rows_with_licence(run_source) -> None:
    result = run_source("global/datahub/core-datasets",
                        {"operation": "fetch-resource", "dataset": "gdp", "resource": "gdp",
                         "offset": 1, "limit": 1})

    assert [r["row_number"] for r in result["records"]] == [2]
    row = result["records"][0]
    assert row["values"] == {"Country Name": "Aruba", "Year": "1987", "Value": "487709497"}
    assert row["license"] == "CC-BY-4.0"


@pytest.mark.parametrize(
    ("payload", "package"),
    [
        ({"dataset": "gdp"}, None),  # two CSV resources and no resource named
        ({"dataset": "gdp", "resource": "gdp"}, {"path": "../other/data.csv"}),
        ({"dataset": "gdp", "resource": "gdp"}, {"path": "https://evil.test/data.csv"}),
        ({"dataset": "country-list"}, None),  # no datapackage.json (yml-only packages 404)
    ],
)
def test_datahub_refuses_ambiguous_unsafe_or_missing_packages(run_source, payload, package) -> None:
    routes = None
    if package is not None:
        unsafe = {**GDP_PACKAGE, "resources": [{"name": "gdp", "format": "csv", **package}]}
        routes = {f"{DH}/gdp/_r/-/datapackage.json": json.dumps(unsafe)}

    result = run_source("global/datahub/core-datasets",
                        {"operation": "fetch-resource", **payload}, routes)

    assert result["status"] == "error"
    assert result["error"]["code"] == "invalid-source-request"
    assert all(url.endswith("datapackage.json") for url in run_source.requested)


# --- Lobbying contract sources -------------------------------------------------
# Each lobbying source promises rows whose columns already equal the contract
# columns of the table its operation fills (domains/lobbying.yaml), so they can
# be written to CSV and passed to anomaly.oneshot without a column map.

LDA = "https://lda.gov/api/v1"
LDA_LOBBYIST = {"lobbyist": {"id": 68995, "first_name": "ZACHARY", "last_name": "RUDISILL"},
                "covered_position": "House Ways and Means Comm, Tax Counsel"}
LDA_FILING = {
    "filing_uuid": "2c5d1bb9-bd38-41e8-a76e-cfd256d2f26d", "filing_type": "Q4", "filing_year": 2025,
    "filing_period": "fourth_quarter", "income": "30000.00", "posted_by_name": "Jane Filer",
    "filing_document_url": "https://lda.gov/filings/public/filing/2c5d1bb9-bd38-41e8-a76e-cfd256d2f26d/print/",
    "registrant": {"id": 682, "name": "AKIN GUMP STRAUSS HAUER & FELD"},
    "client": {"id": 63876, "client_id": "1234", "name": "REPUBLIC OF EXAMPLE", "country": "XX",
               "ppb_country": "XX", "general_description": "Foreign government"},
    "lobbying_activities": [
        {"general_issue_code": "TAX", "description": "Tax treaties", "lobbyists": [LDA_LOBBYIST]},
        {"general_issue_code": "FOR", "description": "Embassy matters",
         "lobbyists": [LDA_LOBBYIST, {"lobbyist": {"id": 7, "first_name": "ANA", "last_name": "LEE"},
                                      "covered_position": ""}]},
    ],
    "foreign_entities": [{"name": "Example Holdings", "country": "XX", "ppb_country": "YY"}],
}
LDA_REPORT = {"filing_uuid": "5e0c0d1e-0000-4000-8000-000000000203", "contribution_items": [
    {"contribution_type": "feca", "contributor_name": "AKIN GUMP PAC", "payee_name": "Friends of Smith",
     "honoree_name": "Rep. Smith", "amount": "2500.00", "date": "2025-05-01"}]}


def _contract_columns(table: str) -> set[str]:
    return set(domains.load_domain("lobbying")["tables"][table]["columns"])


@pytest.mark.parametrize(("operation", "table", "expected"), [
    ("lobbying-registrations", "lobbying_registrations",
     [{"period_start": "2025-10-01", "period_end": "2025-12-31", "filing_type": "Q4", "spend_low": 30000.0,
       "spend_high": 30000.0, "registrant_id": 682, "client_id": 63876, "client_country": "XX",
       "issue_area": "TAX|FOR", "url": LDA_FILING["filing_document_url"]}]),
    ("lobbying-foreign-entities", "lobbying_foreign_entities",
     [{"foreign_entity_name": "Example Holdings", "country": "XX", "ppb_country": "YY"}]),
    ("lobbying-activities", "lobbying_activities",
     [{"general_issue_code": "TAX", "activity_index": 0}, {"general_issue_code": "FOR", "activity_index": 1}]),
    # The same lobbyist on two activities is one row; an empty position is null.
    ("lobbyists", "lobbyists",
     [{"lobbyist_id": 68995, "name": "ZACHARY RUDISILL", "former_public_office": LDA_LOBBYIST["covered_position"]},
      {"lobbyist_id": 7, "name": "ANA LEE", "former_public_office": None}]),
])
def test_lda_filing_operations_emit_contract_rows(run_source, operation, table, expected) -> None:
    page = json.dumps({"count": 1, "next": None, "results": [LDA_FILING]})
    result = run_source("us/lda/lobbying-disclosures",
                        {"operation": operation, "registrant_id": 682, "filing_year": 2025},
                        {f"{LDA}/filings/": page})

    assert result["status"] == "ok"
    assert all(_contract_columns(table) <= set(row) for row in result["records"])
    assert all(row["registration_id"] == LDA_FILING["filing_uuid"] for row in result["records"])
    assert [{key: row[key] for key in want} for row, want in zip(result["records"], expected)] == expected
    assert len(result["records"]) == len(expected)
    assert run_source.params[0] == {"registrant_id": 682, "filing_year": 2025, "page_size": 25}


def test_lda_self_filer_has_no_client_and_reports_expenses_as_spend(run_source) -> None:
    # Generic detectors treat an empty client as "lobbies for itself"; in-house
    # LDA filers report expenses instead of income.
    own = {**LDA_FILING, "income": None, "expenses": "120000.00",
           "client": {**LDA_FILING["client"], "client_self_select": True}}
    page = json.dumps({"count": 1, "next": None, "results": [own]})

    (row,) = run_source("us/lda/lobbying-disclosures",
                        {"operation": "lobbying-registrations", "registrant_id": 682},
                        {f"{LDA}/filings/": page})["records"]

    assert (row["client_id"], row["client_name"], row["client_country"]) == (None, None, "XX")
    assert (row["spend_low"], row["spend_high"]) == (120000.0, 120000.0)


def test_lda_contributions_read_ld203_items_and_follow_pages_up_to_the_limit(run_source) -> None:
    second = f"{LDA}/contributions/?page=2&registrant_id=682"
    pages = {f"{LDA}/contributions/": json.dumps({"count": 3, "next": second, "results": [LDA_REPORT]}),
             second: json.dumps({"count": 3, "next": f"{LDA}/contributions/?page=3", "results": [LDA_REPORT]})}

    result = run_source("us/lda/lobbying-disclosures",
                        {"operation": "political-contributions", "registrant_id": 682, "pages": 2}, pages)

    assert run_source.requested == [f"{LDA}/contributions/", second]
    assert len(result["records"]) == 2
    row = result["records"][0]
    assert _contract_columns("political_contributions") <= set(row)
    assert (row["payee_name"], row["honoree_name"], row["amount"]) == ("Friends of Smith", "Rep. Smith", 2500.0)


def test_lda_refuses_an_unfiltered_query_before_any_request(run_source) -> None:
    result = run_source("us/lda/lobbying-disclosures", {"operation": "lobbying-registrations", "pages": 5})

    assert result["error"]["code"] == "invalid-source-request"
    assert run_source.requested == []


def test_fara_lists_active_and_terminated_registrants_as_contract_rows(run_source) -> None:
    fara = "https://efile.fara.gov/api/v1/Registrants/json"
    active = {"REGISTRANTS_ACTIVE": {"ROW": [
        {"Registration_Number": 7784, "Name": "Gulf Hill & Knowlton WLL", "Registration_Date": "10/22/2026"},
        {"Registration_Number": 7785, "Name": "Kiel, Margot", "Registration_Date": "10/24/2026"}]}}
    # A single row arrives as an object, not a one-item list.
    terminated = {"REGISTRANTS_TERMINATED": {"ROW": {
        "Registration_Number": 7777, "Name": "Korea Foundation USA", "Termination_Date": "10/08/2026"}}}

    everyone = run_source("us/fara/registrants", {"operation": "foreign-agent-registrants"},
                          {f"{fara}/Active": json.dumps(active), f"{fara}/Terminated": json.dumps(terminated)})
    knowlton = run_source("us/fara/registrants", {"operation": "foreign-agent-registrants", "q": "KNOWLTON"})

    assert [(r["registrant_name"], r["status"]) for r in everyone["records"]] == [
        ("Gulf Hill & Knowlton WLL", "active"), ("Kiel, Margot", "active"), ("Korea Foundation USA", "terminated")]
    assert all(_contract_columns("foreign_agent_registrants") <= set(r) for r in everyone["records"])
    assert [r["registration_number"] for r in knowlton["records"]] == [7784]


def test_roster_fills_legislators_and_named_committee_assignments(run_source) -> None:
    base = "https://unitedstates.github.io/congress-legislators"
    routes = {
        f"{base}/legislators-current.json": json.dumps([
            {"id": {"bioguide": "C000127"}, "name": {"first": "Maria", "last": "Cantwell", "official_full": "Maria Cantwell"},
             "terms": [{"type": "rep", "state": "WA", "party": "Democrat"},
                       {"type": "sen", "state": "WA", "party": "Democrat"}]}]),
        f"{base}/committees-current.json": json.dumps([
            {"thomas_id": "SSFI", "name": "Senate Committee on Finance",
             "subcommittees": [{"thomas_id": "13", "name": "Taxation and IRS Oversight"}]}]),
        f"{base}/committee-membership-current.json": json.dumps({
            "SSFI": [{"name": "Mike Crapo", "party": "majority", "rank": 1, "title": "Chairman", "bioguide": "C000880"}],
            "SSFI13": [{"name": "Maria Cantwell", "party": "minority", "rank": 1, "bioguide": "C000127"}]}),
    }

    members = run_source("us/congress-legislators/roster", {"operation": "legislators"}, routes)
    seats = run_source("us/congress-legislators/roster", {"operation": "committee-assignments", "committee": "taxation"})

    assert members["records"] == [{"bioguide_id": "C000127", "name": "Maria Cantwell", "party": "Democrat",
                                   "state": "WA", "chamber": "senate"}]
    assert _contract_columns("committee_assignments") <= set(seats["records"][0])
    assert [(r["bioguide_id"], r["committee_name"], r["role"]) for r in seats["records"]] == [
        ("C000127", "Senate Committee on Finance: Taxation and IRS Oversight", "Member")]


def test_press_releases_stream_one_month_and_filter_member_and_text(run_source) -> None:
    month = "https://raw.githubusercontent.com/dwillis/congress-press/main/data/2026/2026-09.jsonl"
    lines = [
        {"url": "https://a.house.gov/1", "title": "On private equity", "date": "2026-09-01", "text": "Apollo and others",
         "member": {"bioguide_id": "H001085", "name": "Chrissy Houlahan"}},
        {"url": "https://a.house.gov/2", "title": "Farm bill", "date": "2026-09-02", "text": None,
         "member": {"bioguide_id": "H001085", "name": "Chrissy Houlahan"}},
        {"url": "https://b.senate.gov/3", "title": "Hearing", "date": "2026-09-03", "text": "PRIVATE EQUITY abuses",
         "member": {"bioguide_id": "W000817", "name": "Elizabeth Warren"}},
    ]
    routes = {month: "\n".join(json.dumps(line) for line in lines) + "\n"}

    text = run_source("us/congress-press/press-releases",
                      {"operation": "press-releases", "month": "2026-09", "q": "private equity"}, routes)
    member = run_source("us/congress-press/press-releases",
                        {"operation": "press-releases", "month": "2026-09", "bioguide_id": "h001085"})

    assert _contract_columns("press_releases") <= set(text["records"][0])
    assert [r["url"] for r in text["records"]] == ["https://a.house.gov/1", "https://b.senate.gov/3"]
    assert [r["title"] for r in member["records"]] == ["On private equity", "Farm bill"]


def test_press_releases_require_a_month_before_any_request(run_source) -> None:
    result = run_source("us/congress-press/press-releases", {"operation": "press-releases", "month": "2026-13"})

    assert result["error"]["code"] == "invalid-source-request"
    assert run_source.requested == []


EU_REGISTER = """<?xml version='1.1' encoding='UTF-8'?>
<ListOfIRPublicDetail xmlns="http://intragate.ec.europa.eu/transparencyregister/odp">
  <resultList xmlns="">
    <interestRepresentative>
      <identificationCode>111-01</identificationCode>
      <registrationDate>2019-08-28T09:51:42.605+00:00</registrationDate>
      <name><originalName>Kreab &amp; Co</originalName></name>
      <registrationCategory>Professional consultancies</registrationCategory>
      <headOffice><country>BELGIUM</country></headOffice>
      <interests><interest><name>Energy</name></interest><interest><name>Trade</name></interest></interests>
      <financialData><closedYear>
        <startDate>2024-01-01</startDate><endDate>2024-12-01</endDate>
        <clients>
          <client><name>Acme Oil</name><revenue><range><min>100000</min><max>199999</max></range></revenue></client>
          <client><name>Beta Gas</name><revenue><range><max>10000</max></range></revenue></client>
        </clients>
      </closedYear></financialData>
    </interestRepresentative>
    <interestRepresentative>
      <identificationCode>222-02</identificationCode>
      <name><originalName>Gamma Corp guide&#x2;v3</originalName></name>
      <registrationCategory>Companies &amp; groups</registrationCategory>
      <headOffice><country>UNITED STATES</country></headOffice>
      <financialData><closedYear>
        <startDate>2025-01-01</startDate><endDate>2025-12-01</endDate>
        <costs><range><min>300000</min><max>399999</max></range></costs>
      </closedYear></financialData>
    </interestRepresentative>
  </resultList>
</ListOfIRPublicDetail>
"""
EU_MEETINGS = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meetings>
<meeting><dgname>Maritime Affairs and Fisheries</dgname><dgacronym>MARE</dgacronym><date>2026-10-23</date>
<location>Brussels</location><subject>Fish farming</subject>
<entities><entity><name>Seas At Risk</name><id>333-03</id></entity><entity><name>Seas At Risk</name><id>333-03</id></entity>
<entity><name>Aktaia</name><id>444-04</id></entity></entities>
<representatives><representative><name>Delilah Al Khudhairy</name><title>Director</title></representative>
<representative><name>Dan J&amp;#248;rgensen</name><title>Director-General</title></representative></representatives></meeting>
<meeting><dgname>Maritime Affairs and Fisheries</dgname><dgacronym>MARE</dgacronym><date>2024-01-05</date>
<location>Brussels</location><subject>Old meeting</subject>
<entities><entity><name>Seas At Risk</name><id>333-03</id></entity></entities>
<representatives><representative><name>Ana Old</name><title>Director</title></representative></representatives></meeting>
</meetings>
"""
EU_REGISTER_URL = "https://transparency-register.europa.eu/odplastorganisationxml_en"
EU_DG_URL = "https://ec.europa.eu/transparency-initiative/meetings/data/meetings/dataxml?name=meetingsdirectorgenerals"


def test_eu_register_emits_one_row_per_client_or_one_own_row_with_money_bands(run_source) -> None:
    # The export declares XML 1.1 and carries control-character references
    # (here &#x2;) that a plain XML 1.0 parser rejects.
    result = run_source("eu/transparency-register/lobbying", {"operation": "lobbying-registrations"},
                        {EU_REGISTER_URL: EU_REGISTER})

    rows = result["records"]
    columns = domains.load_domain("lobbying")["tables"]["lobbying_registrations"]["columns"]
    assert all({c for c, meaning in columns.items() if not domains.is_optional(meaning)} <= set(row) for row in rows)
    assert [(r["registrant_id"], r["client_name"], r["client_country"], r["spend_low"], r["spend_high"]) for r in rows] == [
        ("111-01", "Acme Oil", None, 100000.0, 199999.0),
        ("111-01", "Beta Gas", None, 0.0, 10000.0),
        ("222-02", None, "UNITED STATES", 300000.0, 399999.0),
    ]
    assert (rows[0]["period_start"], rows[0]["issue_area"], rows[0]["registrant_name"]) == ("2024-01-01", "Energy|Trade", "Kreab & Co")


def test_eu_meetings_emit_one_contact_row_per_organisation_and_official(run_source) -> None:
    result = run_source("eu/transparency-register/lobbying",
                        {"operation": "lobbying-contacts", "meetings": ["directors-general"], "since": "2025-01-01"},
                        {EU_DG_URL: EU_MEETINGS})

    # The repeated entity collapses, the 2024 meeting is before `since`, and the
    # double-escaped name is unescaped.
    rows = result["records"]
    assert [(r["registrant_id"], r["official_name"], r["institution"]) for r in rows] == [
        ("333-03", "Delilah Al Khudhairy", "Maritime Affairs and Fisheries (MARE)"),
        ("333-03", "Dan J\u00f8rgensen", "Maritime Affairs and Fisheries (MARE)"),
        ("444-04", "Delilah Al Khudhairy", "Maritime Affairs and Fisheries (MARE)"),
        ("444-04", "Dan J\u00f8rgensen", "Maritime Affairs and Fisheries (MARE)"),
    ]
    # Every row comes from the same meeting, so they share its id.
    assert len({r["contact_id"] for r in rows}) == 1
    assert all(_contract_columns("lobbying_contacts") <= set(row) for row in rows)


def _ca_zip(path: Path, files: dict[str, str]) -> str:
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(f"export/{name}", "﻿" + text)
    return str(path)


CA_CODES = "SUBJECT_CODE_OBJET,SMT_EN_DESC,SMT_FR_DESC\nSMT-1,Health,Santé\nSMT-2,Agriculture,Agriculture\n"


def test_canada_registrations_and_lobbyists_follow_the_registry_dictionary(run_source, tmp_path: Path) -> None:
    # Columns as published in the registrations data dictionary (2026-10-27).
    archive = _ca_zip(tmp_path / "registrations.zip", {
        "Registration_PrimaryExport.csv":
            "REG_ID_ENR,REG_TYPE_ENR,EN_FIRM_NM_FIRME_AN,RGSTRNT_NUM_DECLARANT,RGSTRNT_LAST_NM_DCLRNT,"
            "RGSTRNT_1ST_NM_PRENOM_DCLRNT,CLIENT_PROFILE_ID_PROFIL_CLIENT,CLIENT_NUM,EN_CLIENT_NM_AN,"
            "EFFECTIVE_DATE_VIGUEUR,END_DATE_FIN\n"
            "969844,1,Bjornson Ltd,895656,Bjornson,Tyler,77,346306,JBS Food Canada Inc.,2025-06-11,2026-03-16\n"
            "500,2,,111,Boss,Ann,88,999,Acme Corp,2024-01-10,\n",
        "Registration_SubjectMattersExport.csv": "REG_ID_ENR,SUBJECT_CODE_OBJET,CUSTOM_SUBJ_OBJET_PERSO\n500,SMT-1,\n",
        "Registration_SubjectMatterDetails Export.csv":
            "REG_ID_ENR,DESCRIPTION,ASSOC_CAT_CODES,ASSOC_SUBJECT_CODES_OBJET\n969844,Meat exports,,\"SMT-2, SMT-1\"\n",
        "Codes_SubjectMatterTypesExport.csv": CA_CODES,
        "Registration_ConsultantLobbyistsExport.csv":
            "RGSTRNT_NUM_DECLARANT,CLIENT_PROFILE_ID_PROFIL_CLIENT,LBBYST_ID_LBBYST,LBBYST_LAST_NM_LBBYST,LBBYST_1ST_NM_PRENOM_LBBYST\n"
            "895656,77,5,Bjornson,Tyler\n",
        "Registration_InHouseLobbyistsExport.csv":
            "CLIENT_PROFILE_ID_PROFIL_CLIENT,LBBYST_ID_LBBYST,LBBYST_POSITION_POSTE_LBBYST,LBBYST_LAST_NM_LBBYST,LBBYST_FIRST_NM_PRENOM_LBBYST\n"
            "88,6,VP,Lee,Ana\n",
        "Registration_PublicOfficeExport.csv":
            "LOBBYIST_ID_LOBBYISTE,DPOH_IND_TCPD,TITLE_TITRE,BRANCH_DIRECTION,INSTITUTION,POS_START_DATE_DEBUT_POSTE,POS_END_DATE_FIN_POSTE\n"
            "6,1,Policy Advisor,,Health Canada (HC),2019-01-01,2023-06-30\n",
    })

    regs = run_source("ca/ocl/registry-of-lobbyists", {"operation": "lobbying-registrations", "registrations_zip": archive})
    people = run_source("ca/ocl/registry-of-lobbyists", {"operation": "lobbyists", "registrations_zip": archive})

    assert [(r["registration_id"], r["registrant_id"], r["registrant_name"], r["client_name"], r["issue_area"], r["period_start"])
            for r in regs["records"]] == [
        ("969844", "895656", "Tyler Bjornson", "JBS Food Canada Inc.", "Agriculture|Health", "2025-06-11"),
        ("500", "org-999", "Acme Corp", None, "Health", "2024-01-10"),
    ]
    assert [(r["registration_id"], r["name"], r["former_office_institution"], r["former_office_end"])
            for r in people["records"]] == [
        ("969844", "Tyler Bjornson", None, None),
        ("500", "Ana Lee", "Health Canada (HC)", "2023-06-30"),
    ]
    assert run_source.requested == []


def test_canada_contacts_drop_superseded_reports_and_use_the_registrant_ids(run_source, tmp_path: Path) -> None:
    archive = _ca_zip(tmp_path / "communications.zip", {
        "Communication_PrimaryExport.csv":
            "COMLOG_ID,CLIENT_ORG_CORP_NUM,EN_CLIENT_ORG_CORP_NM_AN,REGISTRANT_NUM_DECLARANT,RGSTRNT_LAST_NM_DCLRNT,"
            "RGSTRNT_1ST_NM_PRENOM_DCLRNT,COMM_DATE,REG_TYPE_ENR,PREV_COMLOG_ID_PRECEDNT\n"
            "657934,346306,JBS Food Canada Inc.,895656,Bjornson,Tyler,2025-10-23,1,\n"
            "657935,346306,JBS Food Canada Inc.,895656,Bjornson,Tyler,2025-10-24,1,657934\n"
            "700,999,Acme Corp,111,Boss,Ann,2025-11-02,2,\n",
        "Communication_DPOHExport.csv":
            "COMLOG_ID,DPOH_LAST_NM_TCPD,DPOH_FIRST_NM_PRENOM_TCPD,DPOH_TITLE_TITRE_TCPD,BRANCH_UNIT_DIRECTION_SERVICE,OTHER_INSTITUTION_AUTRE,INSTITUTION\n"
            "657934,Moran,Chris,Vice President,,,Canadian Food Inspection Agency (CFIA)\n"
            "657935,Moran,Chris,Vice President,,,Canadian Food Inspection Agency (CFIA)\n"
            "700,Doe,Jo,Senator,,Senate Finance Office,Other\n",
        "Communication_SubjectMattersExport.csv": "COMLOG_ID,SUBJECT_CODE_OBJET,CUSTOM_SUBJ_OBJET_PERSO\n657935,SMT-2,\n",
        "Codes_SubjectMatterTypesExport.csv": CA_CODES,
    })

    result = run_source("ca/ocl/registry-of-lobbyists", {"operation": "lobbying-contacts", "communications_zip": archive})

    assert [(r["contact_id"], r["registrant_id"], r["contact_date"], r["official_name"], r["institution"], r["subject"])
            for r in result["records"]] == [
        ("657935", "895656", "2025-10-24", "Chris Moran", "Canadian Food Inspection Agency (CFIA)", "Agriculture"),
        ("700", "org-999", "2025-11-02", "Jo Doe", "Senate Finance Office", None),
    ]
    assert all(_contract_columns("lobbying_contacts") <= set(row) for row in result["records"])
