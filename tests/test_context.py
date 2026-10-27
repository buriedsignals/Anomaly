from __future__ import annotations

import json
from pathlib import Path

from anomaly import catalogue, context, domains


def test_every_source_has_a_domain_a_skill_and_only_contract_tables() -> None:
    root = context.SOURCES_ROOT
    for source in context.sources():
        assert source["domain"], source["id"]
        assert (root.parent / source["skill"]).is_file(), source["id"]
        if source["provides"]:
            contract = domains.load_domain(source["domain"])
            assert set(source["provides"]) <= set(contract["tables"]), source["id"]


def test_lookup_joins_sources_and_detectors_through_their_domain() -> None:
    result = context.build()
    published = json.loads(catalogue.CATALOGUE_PATH.read_text(encoding="utf-8"))["detectors"]
    by_domain = {item["domain"]: item for item in result["domains"]}

    lobbying = by_domain["lobbying"]
    assert {item["id"] for item in lobbying["detectors"]} == {
        entry["id"] for entry in published if entry.get("data_type") == "lobbying"
    }
    assert set(lobbying["contract"]) == set(domains.load_domain("lobbying")["tables"])
    assert "us/lobbydata/directory" in {item["id"] for item in lobbying["sources"]}
    assert {item["id"] for item in result["any_table"]} == {
        entry["id"] for entry in published if not entry.get("data_type")
    }
    assert sum(len(item["sources"]) for item in result["domains"]) == len(context.sources())


def test_source_metadata_reads_folded_text_inline_auth_and_provides(tmp_path: Path) -> None:
    package = tmp_path / "data-skills" / "xx" / "example"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    (package / "meta.yaml").write_text(
        "id: xx/example/filings\n"
        "title: Example filings\n"
        "description: >-\n"
        "  First line of a long description\n"
        "  issues: that continues here.\n"
        "category: lobbying\n"
        "status: queryable\n"
        "auth: {type: api_key, key_name: example}\n"
        "license:\n"
        "  data_license: CC-BY-4.0\n"
        "provides:\n"
        "  lobbying_filings: {}\n"
        "operations:\n"
        "  - access: {auth: source, cost: free, side_effects: none}\n",
        encoding="utf-8",
    )

    (source,) = context.sources(tmp_path / "data-skills")

    assert source["description"] == "First line of a long description issues: that continues here."
    assert source["auth"] == "api_key"
    assert source["license"] == "CC-BY-4.0"
    assert source["provides"] == ["lobbying_filings"]
    assert source["cost"] == ["free"]
    assert source["skill"] == "data-skills/xx/example/SKILL.md"
