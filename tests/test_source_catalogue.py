from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from anomaly.sources.contract import validate_source_result
from anomaly.sources.registry import discover_sources, load_source_adapter


ANOMALY_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = ANOMALY_ROOT / "data-skills"
NAVIGATOR_ROOT = ANOMALY_ROOT.parent / "navigator" / "osint-navigator" / "data" / "skills"
ARBITER_ID = "global/arbiter/case-studies"
SOURCE_ID_PATTERN = re.compile(r"^id:\s*(.+?)\s*$", re.MULTILINE)


def _source_id(meta_path: Path) -> str:
    match = SOURCE_ID_PATTERN.search(meta_path.read_text(encoding="utf-8"))
    assert match is not None, meta_path
    return match.group(1).strip("'\"")


def _ids(root: Path) -> list[str]:
    return sorted(
        _source_id(path)
        for path in root.rglob("meta.yaml")
        if "_template" not in path.relative_to(root).parts
    )


def _load_adapter(path: Path):
    module_name = "test_catalogue_" + path.parent.name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_result(source_id: str, status: str) -> dict:
    result = {
        "source_id": source_id,
        "operation": "catalogue-contract-test",
        "license": "test licence",
        "endpoint": "https://example.test/source",
        "source_hash": "sha256:" + "a" * 64,
        "provenance": {"endpoint": "https://example.test/source", "request": {}},
        "status": status,
        "records": [{"id": "1"}] if status == "ok" else [],
        "normalized": True,
        "error": None,
    }
    if status != "ok":
        result["error"] = {"code": f"{status}-source", "message": "fixture state"}
    return result


def test_navigator_inventory_has_29_packages_and_exactly_28_one_to_one_migrations() -> None:
    navigator_ids = _ids(NAVIGATOR_ROOT)
    anomaly_meta = sorted(SOURCE_ROOT.rglob("meta.yaml"))
    anomaly_ids = [_source_id(path) for path in anomaly_meta]

    assert len(navigator_ids) == 29
    assert navigator_ids.count(ARBITER_ID) == 1
    expected_ids = set(navigator_ids) - {ARBITER_ID}
    assert len(expected_ids) == 28
    assert len(anomaly_ids) == 28
    assert set(anomaly_ids) == expected_ids
    assert anomaly_ids.count("global/opensanctions") == 1
    assert anomaly_ids.count("global/thinkpol/reddit-evidence") == 1
    for meta_path in anomaly_meta:
        assert meta_path.with_name("SKILL.md").is_file()
        assert meta_path.with_name("adapter.py").is_file()


@pytest.mark.parametrize("status", ["ok", "unavailable", "error"])
def test_shared_result_contract_enforces_each_real_adapter_state(status: str) -> None:
    entries = discover_sources(SOURCE_ROOT)
    assert len(entries) == 28
    for entry in entries:
        adapter = load_source_adapter(entries, entry.source_id)
        assert callable(getattr(adapter, "run", None))
        result = validate_source_result(_base_result(entry.source_id, status))
        assert result["source_id"] == entry.source_id
        assert result["status"] == status


def test_catalogue_contains_no_forbidden_hosted_or_navigator_surfaces() -> None:
    forbidden = (
        r"navigator\s+(?:query|data\s+show|cli|service)",
        r"hosted\s+(?:key|credential|runtime|execution|access)",
        r"requires[_ -]hosted[_ -]access",
        r"membership[_ -]?(?:required|tier|plan|metering)",
        r"\bmetering\b",
        r"\bmcp\b",
        r"\bweb\s+ui\b",
        r"\bdeployment\b",
    )
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file()
    ).lower()
    for pattern in forbidden:
        assert re.search(pattern, text) is None, pattern


def test_registry_loads_real_adapters_only_after_request() -> None:
    first = discover_sources(SOURCE_ROOT)
    second = discover_sources(SOURCE_ROOT)
    assert first == second
    assert [entry.source_id for entry in first] == sorted(entry.source_id for entry in first)
    adapter = load_source_adapter(first, "global/opensanctions")
    assert adapter.__name__.startswith("anomaly_source_")
    assert callable(adapter.run)


def test_registry_rejects_symlink_escape_before_loading(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "meta.yaml").write_text(
        "id: global/escaped/source\ntitle: Escaped\nlicense: CC0\nendpoint: https://example.test\n",
        encoding="utf-8",
    )
    root = tmp_path / "catalogue"
    root.mkdir()
    (root / "global").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="unsafe"):
        discover_sources(root)


def test_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    for package_name in ("first", "second"):
        package = tmp_path / "global" / package_name
        package.mkdir(parents=True)
        (package / "meta.yaml").write_text(
            "id: global/duplicate/source\ntitle: Duplicate\nlicense: CC0\n"
            "endpoint: https://example.test\noperation: search\n",
            encoding="utf-8",
        )
        (package / "SKILL.md").write_text("# Source\n", encoding="utf-8")
        (package / "adapter.py").write_text("def run(input, ctx):\n    return {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        discover_sources(tmp_path)


def test_prd_m3_language_describes_catalogue_only_migration() -> None:
    prd = (ANOMALY_ROOT / "PRD.md").read_text(encoding="utf-8")
    m3_line = next(line for line in prd.splitlines() if "| M3 |" in line)

    assert "28 non-Arbiter Navigator source packages" in m3_line
    assert "catalogue" in m3_line.lower()
    assert all(term not in m3_line.lower() for term in ("cli", "service", "mcp", "deployment"))
