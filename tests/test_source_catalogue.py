from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import types
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


class _OfflineContext:
    def get_key(self, _name: str) -> str:
        return "offline-test-key"

    def get_key_optional(self, _name: str) -> str | None:
        return None


class _OfflineError(Exception):
    pass


class _OfflineClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def __enter__(self) -> "_OfflineClient":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def _request(self, *_args, **_kwargs):
        raise _OfflineError("network disabled by source catalogue test")

    get = _request
    post = _request


def _offline_request(*_args, **_kwargs):
    raise _OfflineError("network disabled by source catalogue test")


def _offline_httpx() -> types.ModuleType:
    module = types.ModuleType("httpx")
    module.Client = _OfflineClient
    module.HTTPError = _OfflineError
    module.get = _offline_request
    module.post = _offline_request
    return module


def _offline_input(source_id: str) -> dict:
    if source_id == "no/brreg/enheter":
        return {"operation": "search-companies", "navn": "test"}
    if source_id == "fr/pappers/companies":
        return {"operation": "search-companies", "q": "test"}
    if source_id == "gb/companies-house/companies":
        return {"operation": "search-companies", "q": "test"}
    if source_id == "us/epa/envirofacts":
        return {"mode": "tri", "id": "TEST"}
    if source_id == "us/usaspending/awards":
        return {"keyword": "test"}
    if source_id == "us/courtlistener/financial-disclosures":
        return {"person_id": 1}
    if source_id == "eu/eurostat/data":
        return {"mode": "datasets", "q": "test"}
    if source_id == "us/congress/legislation":
        return {"q": "test"}
    return {"q": "test"}


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


def test_shared_result_contract_validates_each_real_adapter_output_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "httpx", _offline_httpx())
    entries = discover_sources(SOURCE_ROOT)
    assert len(entries) == 28
    for entry in entries:
        adapter = load_source_adapter(entries, entry.source_id)
        assert callable(getattr(adapter, "run", None))
        result = adapter.run(_offline_input(entry.source_id), _OfflineContext())
        result = validate_source_result(result)
        assert result["source_id"] == entry.source_id
        assert result["operation"] == entry.metadata["operation"]
        assert result["license"] == entry.metadata["license"]
        assert result["endpoint"] == entry.metadata["endpoint"]
        expected_hash = "sha256:" + hashlib.sha256(
            (entry.package / "adapter.py").read_bytes()
        ).hexdigest()
        assert result["source_hash"] == expected_hash
        assert result["provenance"]["source"] == str(entry.package / "adapter.py")
        assert result["provenance"]["adapter"] == entry.source_id
        assert result["status"] in {"ok", "unavailable", "error"}
        if result["status"] != "ok":
            assert result["error"]["code"]
            assert result["error"]["message"]


def test_catalogue_contains_no_forbidden_hosted_or_navigator_surfaces() -> None:
    forbidden = (
        r"navigator\s+(?:query|data\s+show|cli|service)",
        r"catalogue\s+(?:cli|keys\s+set)",
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


def test_thinkpol_catalogue_has_no_key_quota_or_profile_surfaces() -> None:
    thinkpol_root = SOURCE_ROOT / "global" / "thinkpol-reddit-evidence"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in thinkpol_root.rglob("*")
        if path.is_file()
    ).lower()
    forbidden = (
        r"\bapi[_ -]?key\b",
        r"\bctx\.get_key\b",
        r"\bquota\b",
        r"\b(?:analyze[_ -]?profile|profile[_ -]?analysis)\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, text) is None, pattern


def test_registry_loads_real_adapters_only_after_request() -> None:
    source_ids = {entry.source_id for entry in discover_sources(SOURCE_ROOT)}
    module_names = {
        "anomaly_source_" + hashlib.sha256(source_id.encode()).hexdigest(): source_id
        for source_id in source_ids
    }
    for module_name in module_names:
        sys.modules.pop(module_name, None)

    first = discover_sources(SOURCE_ROOT)
    second = discover_sources(SOURCE_ROOT)
    assert first == second
    assert [entry.source_id for entry in first] == sorted(entry.source_id for entry in first)
    assert not (set(module_names) & sys.modules.keys())

    requested_id = "global/opensanctions"
    unrequested_id = next(source_id for source_id in source_ids if source_id != requested_id)
    adapter = load_source_adapter(first, requested_id)
    assert adapter.__name__.startswith("anomaly_source_")
    assert callable(adapter.run)
    assert adapter.__name__ not in sys.modules
    assert "anomaly_source_" + hashlib.sha256(unrequested_id.encode()).hexdigest() not in sys.modules


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


def test_registry_rejects_adapter_without_callable_run(tmp_path: Path) -> None:
    package = tmp_path / "global" / "malformed"
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        "id: global/malformed/source\ntitle: Malformed\nlicense: CC0\n"
        "endpoint: https://example.test\noperation: search\n",
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text("# Source\n", encoding="utf-8")
    (package / "adapter.py").write_text(
        "def run(input, ctx):\n    return {}\n\nrun = 1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="callable run"):
        discover_sources(tmp_path)


def test_registry_rejects_adapter_rebound_with_augassign(tmp_path: Path) -> None:
    package = tmp_path / "global" / "augassign"
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        "id: global/augassign/source\ntitle: AugAssign\nlicense: CC0\n"
        "endpoint: https://example.test\noperation: search\n",
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text("# Source\n", encoding="utf-8")
    (package / "adapter.py").write_text(
        "def run(input, ctx):\n    return {}\n\nrun += 1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="callable run"):
        discover_sources(tmp_path)


def test_adapter_error_envelope_does_not_expose_raw_exception_text(tmp_path: Path) -> None:
    package = tmp_path / "global" / "error-envelope"
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        "id: global/error-envelope/source\ntitle: Error envelope\nlicense: CC0\n"
        "endpoint: https://example.test\noperation: search\n",
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text("# Source\n", encoding="utf-8")
    secret_url = "https://api.example.test/search?token=super-secret-token"
    (package / "adapter.py").write_text(
        "def run(input, ctx):\n"
        f"    raise RuntimeError({secret_url!r})\n",
        encoding="utf-8",
    )

    entries = discover_sources(tmp_path)
    adapter = load_source_adapter(entries, "global/error-envelope/source")
    result = adapter.run({"q": "test"}, _OfflineContext())

    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "upstream-unavailable"
    assert result["error"]["message"]
    assert secret_url not in result["error"]["message"]
    assert "super-secret-token" not in result["error"]["message"]


def test_prd_and_backlog_m3_language_describes_catalogue_only_migration() -> None:
    prd = (ANOMALY_ROOT / "PRD.md").read_text(encoding="utf-8")
    m3_line = next(line for line in prd.splitlines() if "| M3 |" in line)

    assert "28 non-Arbiter Navigator source packages" in m3_line
    assert "catalogue" in m3_line.lower()
    assert all(term not in m3_line.lower() for term in ("cli", "service", "mcp", "deployment"))
