from __future__ import annotations

import re
from pathlib import Path

import pytest

from anomaly.sources.contract import validate_source_result
from anomaly.sources.registry import discover_sources, load_source_adapter


SOURCE_ROOT = Path(__file__).parents[1] / "data-skills"

EXPECTED_SOURCE_IDS = frozenset(
    {
        "ch/openparldata/parliamentary-data",
        "ch/zefix/companies",
        "eu/europarl/open-data",
        "eu/eurostat/data",
        "eu/ted/notices",
        "fr/pappers/companies",
        "gb/companies-house/companies",
        "gb/find-a-tender/notices",
        "global/bluesky/posts",
        "global/gdelt/news",
        "global/gleif/lei-records",
        "global/occrp-aleph/entities",
        "global/opencorporates/companies",
        "global/opensanctions",
        "global/thinkpol/reddit-evidence",
        "global/wikidata/entities",
        "no/brreg/enheter",
        "us/congress/legislation",
        "us/courtlistener/docket",
        "us/courtlistener/financial-disclosures",
        "us/courtlistener/judge",
        "us/courtlistener/opinion",
        "us/courtlistener/search",
        "us/epa/envirofacts",
        "us/federal-register/documents",
        "us/fec/campaign-finance",
        "us/sec-edgar/filings",
        "us/usaspending/awards",
    }
)


def _source_id(meta_path: Path) -> str:
    match = re.search(r"^id:\s*(.+?)\s*$", meta_path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    return match.group(1).strip("'\"")


def test_migration_has_exact_navigator_inventory_and_complete_packages() -> None:
    meta_paths = sorted(SOURCE_ROOT.rglob("meta.yaml"))
    actual_ids = {_source_id(path) for path in meta_paths}

    assert actual_ids == EXPECTED_SOURCE_IDS
    assert "global/thinkpol/reddit-evidence" in actual_ids
    assert "ch/openparldata/parliamentary-data" in actual_ids
    assert "global/arbiter/case-studies" not in actual_ids
    for meta_path in meta_paths:
        assert meta_path.with_name("SKILL.md").is_file()
        assert meta_path.with_name("adapter.py").is_file()


def test_thinkpol_uses_catalogue_contract_without_hosted_surfaces() -> None:
    thinkpol = SOURCE_ROOT / "global" / "thinkpol-reddit-evidence"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (thinkpol / "SKILL.md", thinkpol / "meta.yaml")
    ).lower()

    assert "global/thinkpol/reddit-evidence" in text
    for forbidden in ("hosted", "membership", "metering", "navigator cli", "mcp"):
        assert forbidden not in text


def test_source_result_contract_covers_success_and_unavailable_states() -> None:
    base = {
        "source_id": "global/example/source",
        "operation": "search",
        "license": "CC BY 4.0",
        "endpoint": "https://example.org/api",
        "source_hash": "sha256:" + "a" * 64,
        "provenance": {"endpoint": "https://example.org/api", "request": {"q": "Ada"}},
    }

    success = validate_source_result(
        base
        | {
            "status": "ok",
            "records": [{"id": "1", "name": "Ada"}],
            "normalized": True,
            "error": None,
        }
    )
    unavailable = validate_source_result(
        base
        | {
            "status": "unavailable",
            "records": [],
            "normalized": True,
            "error": {"code": "upstream-unavailable", "message": "not reachable"},
        }
    )

    assert success["status"] == "ok"
    assert success["records"] == [{"id": "1", "name": "Ada"}]
    assert unavailable["status"] == "unavailable"
    assert unavailable["error"]["code"] == "upstream-unavailable"

    with pytest.raises(ValueError):
        validate_source_result(base | {"status": "ok", "records": []})


def test_registry_is_deterministic_safe_and_loads_adapter_only_on_request(
    tmp_path: Path,
) -> None:
    package = tmp_path / "global" / "example-source"
    package.mkdir(parents=True)
    marker = tmp_path / "imported"
    (package / "meta.yaml").write_text(
        "id: global/example/source\n"
        "title: Example\n"
        "license: CC BY 4.0\n"
        "endpoint: https://example.org/api\n"
        "operation: search\n",
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text(
        "---\nname: example-source\ndescription: Example source\n---\n\nQuery it.\n",
        encoding="utf-8",
    )
    (package / "adapter.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('loaded')\n"
        "def run(input, ctx):\n"
        "    return {'status': 'ok', 'records': [], 'normalized': True}\n",
        encoding="utf-8",
    )

    first = discover_sources(tmp_path)
    second = discover_sources(tmp_path)

    assert [entry.source_id for entry in first] == ["global/example/source"]
    assert first == second
    assert not marker.exists()
    adapter = load_source_adapter(first, "global/example/source")
    assert marker.read_text(encoding="utf-8") == "loaded"
    assert adapter.run({}, {}) == {"status": "ok", "records": [], "normalized": True}


def test_registry_rejects_malformed_or_unsafe_packages(tmp_path: Path) -> None:
    package = tmp_path / "global" / "unsafe-source"
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text("id: ../escape\n", encoding="utf-8")

    with pytest.raises(ValueError):
        discover_sources(tmp_path)


def test_prd_m3_language_describes_catalogue_only_migration() -> None:
    prd = (Path(__file__).parents[1] / "PRD.md").read_text(encoding="utf-8")
    m3_line = next(line for line in prd.splitlines() if "| M3 |" in line)

    assert "28 non-Arbiter Navigator source packages" in m3_line
    assert "catalogue" in m3_line.lower()
    assert all(term not in m3_line.lower() for term in ("cli", "service", "mcp", "deployment"))
