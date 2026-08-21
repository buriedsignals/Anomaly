"""Safe deterministic discovery and request-time adapter loading."""

from __future__ import annotations

import hashlib
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

_SOURCE_ID = re.compile(r"^[a-z0-9]+(?:/[a-z0-9][a-z0-9-]*){2,}$")


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    package: Path
    metadata: dict[str, str]


def _metadata(meta_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(id|title|endpoint|operation|license):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip(" '\"")
        if "data_license:" in line and not values.get("license"):
            values["license"] = line.split("data_license:", 1)[1].strip(" '\"")
        if line.startswith("  - id:") and "operation" not in values:
            values["operation"] = line.split(":", 1)[1].strip(" '\"")
    required = {"id", "title", "endpoint", "license"}
    if not required <= values.keys():
        raise ValueError(f"malformed source metadata: {meta_path}")
    values.setdefault("operation", "query")
    return values


def _safe_package(root: Path, meta_path: Path) -> SourceEntry:
    package = meta_path.parent
    if package.is_symlink() or any(part == ".." for part in package.relative_to(root).parts):
        raise ValueError(f"unsafe source package: {package}")
    metadata = _metadata(meta_path)
    source_id = metadata["id"]
    if not _SOURCE_ID.fullmatch(source_id):
        raise ValueError(f"unsafe source id: {source_id}")
    if not (package / "SKILL.md").is_file() or not (package / "adapter.py").is_file():
        raise ValueError(f"incomplete source package: {package}")
    return SourceEntry(source_id, package, metadata)


def discover_sources(root: Path) -> list[SourceEntry]:
    """Return valid source packages in stable source-id order."""
    root = Path(root).resolve()
    entries = [_safe_package(root, path) for path in root.rglob("meta.yaml")]
    return sorted(entries, key=lambda entry: entry.source_id)


def load_source_adapter(entries: list[SourceEntry], source_id: str) -> ModuleType:
    """Import one adapter after discovery, never while walking the catalogue."""
    entry = next((item for item in entries if item.source_id == source_id), None)
    if entry is None:
        raise KeyError(f"unknown source id: {source_id}")
    module_name = "anomaly_source_" + hashlib.sha256(source_id.encode()).hexdigest()
    spec = importlib.util.spec_from_file_location(module_name, entry.package / "adapter.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter: {source_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
