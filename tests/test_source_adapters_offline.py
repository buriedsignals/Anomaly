"""Offline fixture tests for the Party Facts and DataHub Core adapters.

A fake ``httpx`` serves codebook- and datapackage-shaped fixtures, so each
adapter runs through the real registry and result contract without network.
"""

from __future__ import annotations

import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

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

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self._body)

    def iter_lines(self):
        yield from self._body.splitlines()


def _fake_httpx(routes: dict[str, str], requested: list[str]) -> types.ModuleType:
    class Client:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, url: str, **_kwargs) -> _FakeResponse:
            requested.append(url)
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
    routes = {
        f"{PF}/core-parties-csv/": CORE_CSV,
        f"{PF}/external-parties-csv/": EXTERNAL_CSV,
        f"{DH}/gdp/_r/-/datapackage.json": json.dumps(GDP_PACKAGE),
        f"{DH}/gdp/_r/-/data/gdp.csv": GDP_CSV,
    }

    def run(source_id: str, payload: dict, extra_routes: dict[str, str] | None = None) -> dict:
        routes.update(extra_routes or {})
        monkeypatch.setitem(sys.modules, "httpx", _fake_httpx(routes, requested))
        adapter = load_source_adapter(discover_sources(SOURCE_ROOT), source_id)
        return validate_source_result(adapter.run(payload, None))

    run.requested = requested
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
