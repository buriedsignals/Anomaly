"""Versioned, generated catalogue of released detectors for external tools.

``python -m anomaly.catalogue`` prints the catalogue as JSON, ``--write``
regenerates the checked-in ``detectors/catalogue.json`` and ``--check`` exits
non-zero when that file is stale. The schema is documented in
``docs/catalogue.md``; any breaking change to it bumps ``SCHEMA_VERSION``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from anomaly.detectors import registry

SCHEMA_VERSION = 1
CATALOGUE_PATH = registry._ROOT / "catalogue.json"
_PARAMETER_TYPES = {"integer", "number", "string"}
_BOUND_KEYS = {
    "integer": {"type", "minimum", "maximum"},
    "number": {"type", "minimum", "maximum"},
    "string": {"type", "max_length"},
}
_PUBLISHED_FIELDS = (
    "title", "description", "group", "family", "data_type", "signal_category", "severity",
    "required_tables", "expected_output", "assumptions", "false_positives",
    "sensitive_output", "resource_limits", "attribution", "source_repository",
)

# Shape of each JSONL record emitted by ``anomaly.oneshot``.
SIGNAL_SCHEMA: dict[str, Any] = {
    "status": "always 'lead'; detector output is never a finding",
    "signal_id": "string; stable over detector, input hash and candidate",
    "detector_id": "string",
    "detector_version": "string",
    "detector_hash": "string; sha256:<hex> implementation hash",
    "candidate_id": "string",
    "category": "string; the detector's signal_category",
    "severity": "string",
    "summary": "string; the detector title",
    "values": "object; the detector row, redacted per sensitive_output",
    "provenance": {
        "input_hash": "string; sha256:<hex> of the supplied table file, or for domain detectors of the sorted JSON of input_hashes",
        "input_format": "csv | jsonl | parquet, or 'tables' for domain detectors",
        "field_map": "object; core detectors only: required field -> supplied column",
        "column_map": "object; domain detectors only: contract table -> {contract column -> file column}",
        "input_hashes": "object; domain detectors only: contract table -> sha256:<hex> of its file",
        "parameters": "object; effective parameter values",
        "limits": "object; effective execution limits",
        "run_id": "string",
        "executed_at": "string; ISO 8601 UTC",
        "approval": "always 'caller-recorded'; the caller owns the approval record",
    },
}


class CatalogueError(registry.RegistryError):
    """The released detector metadata cannot be published as a catalogue."""


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parameters(detector_id: str, metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    defaults = metadata["parameters"]
    bounds = metadata.get("parameter_bounds")
    if not isinstance(bounds, dict) or set(bounds) != set(defaults):
        raise CatalogueError(f"every parameter needs exactly one bound: {detector_id}")
    result: dict[str, dict[str, Any]] = {}
    for name, default in defaults.items():
        bound = bounds[name]
        kind = bound.get("type") if isinstance(bound, dict) else None
        if kind not in _PARAMETER_TYPES or set(bound) != _BOUND_KEYS[kind]:
            raise CatalogueError(f"invalid bound for {detector_id}.{name}")
        if kind == "string":
            if not isinstance(default, str) or len(default) > bound["max_length"]:
                raise CatalogueError(f"default outside bound: {detector_id}.{name}")
        else:
            if not (_is_number(bound["minimum"]) and _is_number(bound["maximum"])):
                raise CatalogueError(f"invalid bound for {detector_id}.{name}")
            if kind == "integer" and not (isinstance(default, int) and not isinstance(default, bool)):
                raise CatalogueError(f"default outside bound: {detector_id}.{name}")
            if not _is_number(default) or not bound["minimum"] <= default <= bound["maximum"]:
                raise CatalogueError(f"default outside bound: {detector_id}.{name}")
        result[name] = {"default": default, **bound}
    return result


def _required_fields(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    declared = metadata.get("required_types")
    declared = declared if isinstance(declared, dict) else {}
    # Not every package declares field types; publish null rather than guess.
    return [
        {"name": name, "types": declared.get(name)}
        for name in metadata["required_fields"]
    ]


def _entry(metadata: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": metadata["id"],
        "version": metadata["version"],
        "implementation_hash": metadata["implementation_hash"],
        "required_fields": _required_fields(metadata),
        "parameters": _parameters(metadata["id"], metadata),
    }
    entry.update({field: metadata[field] for field in _PUBLISHED_FIELDS if field in metadata})
    entry.setdefault("family", "core")
    return entry


def released_detectors(root: Path | None = None) -> list[dict[str, Any]]:
    """Validate and return the full metadata of every released package."""
    root = Path(root) if root is not None else registry._ROOT
    released: dict[str, dict[str, Any]] = {}
    for meta_path in sorted(root.rglob("meta.yaml"), key=lambda path: path.as_posix()):
        if "_template" in meta_path.relative_to(root).parts:
            continue
        metadata = registry.validate_detector_package(meta_path.parent, allowed_root=root)
        if metadata.get("release") != "released":
            continue
        if metadata["id"] in released:
            raise CatalogueError("duplicate detector id")
        released[metadata["id"]] = metadata
    return [released[detector_id] for detector_id in sorted(released)]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_catalogue(root: Path | None = None) -> dict[str, Any]:
    """Generate the full released catalogue from detector ``meta.yaml`` files."""
    body = {
        "schema_version": SCHEMA_VERSION,
        "detectors": [_entry(metadata) for metadata in released_detectors(root)],
        "signal_schema": SIGNAL_SCHEMA,
    }
    return {**body, "catalogue_hash": "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()}


def render(catalogue: dict[str, Any]) -> str:
    return json.dumps(catalogue, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anomaly.catalogue", description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate the checked-in catalogue")
    mode.add_argument("--check", action="store_true", help="fail when the checked-in catalogue is stale")
    args = parser.parse_args(argv)
    text = render(build_catalogue())
    if args.write:
        CATALOGUE_PATH.write_text(text, encoding="utf-8")
        return 0
    if args.check:
        current = CATALOGUE_PATH.read_text(encoding="utf-8") if CATALOGUE_PATH.is_file() else ""
        if current != text:
            print(f"stale: run python -m anomaly.catalogue --write ({CATALOGUE_PATH})", file=sys.stderr)
            return 1
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
