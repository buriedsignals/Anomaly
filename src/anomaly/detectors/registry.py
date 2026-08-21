from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anomaly import detect, recommend

_ROOT = Path(__file__).resolve().parents[3] / "detectors"
_REQUIRED = {
    "id", "version", "title", "author", "license", "group", "description",
    "required_tables", "required_fields", "parameters", "signal_category",
    "severity", "expected_output", "assumptions", "false_positives",
    "sensitive_output", "resource_limits",
}
_ID = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_ORDER = (
    "categorical.rare_levels", "cross_dataset.location_conflicts",
    "credential.private_key_patterns", "credential.secret_patterns",
    "domain.contractor_concentration", "domain.procurement_bid_clusters",
    "network.cross_commit_overlap", "network.shared_infrastructure",
    "numeric.level_shift", "numeric.zscore_outliers",
    "relational.conflicting_profiles", "relational.shared_identifiers",
    "table.duplicate_rows", "table.missingness_clusters",
    "temporal.backdated_records", "temporal.coverage_gaps",
    "temporal.timezone_activity_shifts", "text.path_hostname_leakage",
    "text.portfolio_cloning", "text.secret_patterns",
)
_FORBIDDEN = re.compile(
    r"\b(?:CREATE|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|ATTACH|DETACH|COPY|"
    r"INSTALL|LOAD|EXPORT|IMPORT|CALL|PRAGMA|SET|RESET)\b", re.IGNORECASE
)
_EXTERNAL = re.compile(
    r"\b(?:read_[a-z0-9_]+|query(?:_table)?|glob|http_[a-z0-9_]+|"
    r"(?:parquet|delta|iceberg|sqlite|postgres|mysql|arrow)_scan)\s*\(",
    re.IGNORECASE,
)


class RegistryError(detect.DetectorError):
    """A detector package or execution request is invalid."""


def _yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        value = detect._parse_restricted_yaml(text)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise RegistryError("invalid detector metadata") from error
    if not isinstance(value, dict):
        raise RegistryError("invalid detector metadata")
    return dict(value)


def _package_root(package: Path, allowed_root: Path | None) -> Path:
    package = Path(package)
    if not package.is_dir() or package.is_symlink():
        raise RegistryError("detector package boundary is unsafe")
    resolved = package.resolve()
    if allowed_root is not None:
        root = Path(allowed_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise RegistryError("detector package escapes its allowed boundary") from error
    current = package
    while current != current.parent:
        if current.is_symlink():
            raise RegistryError("detector package contains a symlink")
        current = current.parent
    return resolved


def _validate_query(package: Path, metadata: dict[str, Any]) -> None:
    query_name = metadata.get("query")
    if query_name != "query.sql" or not (package / query_name).is_file():
        raise RegistryError("detector must provide query.sql")
    query = (package / query_name).read_text(encoding="utf-8")
    stripped = query.strip().rstrip(";").strip()
    if ";" in stripped or not re.match(r"(?is)^(SELECT|WITH)\b", stripped):
        raise RegistryError("only one read-only SELECT statement is allowed")
    if _FORBIDDEN.search(stripped) or _EXTERNAL.search(stripped):
        raise RegistryError("unsafe external or mutating SQL rejected")
    if re.search(r"(?is)\b(?:FROM|JOIN)\s*(?:'|`|/|[A-Za-z]:[\\/])", stripped):
        raise RegistryError("external file relation rejected")


def validate_detector_package(package: Path, *, allowed_root: Path | None = None) -> dict[str, Any]:
    """Validate a SQL detector package without importing or executing it."""
    package = _package_root(Path(package), allowed_root)
    metadata = _yaml(package / "meta.yaml")
    if not isinstance(metadata.get("id"), str) or not _ID.fullmatch(metadata["id"]):
        raise RegistryError("invalid detector id")
    if not isinstance(metadata.get("version"), str) or not metadata["version"]:
        raise RegistryError("invalid detector version")
    if not isinstance(metadata.get("parameters", {}), dict):
        raise RegistryError("invalid detector parameters")
    _validate_query(package, metadata)
    normalized = {key: metadata.get(key, []) for key in _REQUIRED}
    normalized.update(metadata)
    normalized["package"] = str(package)
    normalized["implementation_hash"] = _hash_package(package)
    return normalized


def _hash_package(package: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_file() and not path.is_symlink():
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def discover_detectors(roots: list[Path] | tuple[Path, ...] | None = None) -> list[dict[str, Any]]:
    """Discover local package metadata in stable ID order."""
    roots = tuple(Path(root) for root in roots) if roots is not None else (_ROOT,)
    packages: list[Path] = []
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            raise RegistryError("detector root boundary is unsafe")
        packages.extend(
            path.parent
            for path in root.rglob("meta.yaml")
            if path.is_file() and "_template" not in path.parts
        )
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for package in sorted(packages, key=lambda path: path.as_posix()):
        metadata = validate_detector_package(package, allowed_root=package.parents[1])
        detector_id = metadata["id"]
        if detector_id in seen:
            raise RegistryError("duplicate detector id")
        seen.add(detector_id)
        result.append(metadata)
    order = {detector_id: index for index, detector_id in enumerate(_ORDER)}
    return sorted(result, key=lambda item: (order.get(item["id"], len(order)), item["id"]))


def recommend_detectors(root: Path, *, max_detectors: int = 10) -> dict[str, Any]:
    """Return a deterministic, bounded plan without executing detector SQL."""
    if not isinstance(max_detectors, int) or isinstance(max_detectors, bool) or max_detectors < 1:
        raise RegistryError("max_detectors must be positive")
    limit = min(max_detectors, 10)
    root = Path(root)
    try:
        return recommend.recommend_detectors(root, now=datetime.now(timezone.utc), max_detectors=limit)
    except (FileNotFoundError, RegistryError, recommend.RecommendationError):
        metadata = discover_detectors()
        selected = [item["id"] for item in metadata[:limit]]
        return {"recommended": selected, "approved": [], "parameters": {}, "reasons": {}, "blocked": []}


def execute_detectors(
    root: Path,
    detector_ids: list[str] | tuple[str, ...],
    *,
    approved: bool = False,
    limits: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute only explicitly approved local detectors, capped at ten."""
    if not approved:
        raise RegistryError("explicit approval is required before execution")
    requested = tuple(detector_ids)
    if not requested or len(requested) > 10 or len(set(requested)) != len(requested):
        raise RegistryError("at most 10 unique detectors may be executed")
    catalog = {item["id"]: item for item in discover_detectors()}
    unknown = [item for item in requested if item not in catalog]
    if unknown:
        raise RegistryError("unknown detector")
    root = Path(root)
    if root.is_dir() and (root / "data" / "index.duckdb").is_file():
        return detect.execute_detectors(root, requested, now=datetime.now(timezone.utc), limits=limits)
    source_hash = "sha256:" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()
    return [
        {
            "status": "lead",
            "signal_id": "signal-" + hashlib.sha256(detector_id.encode()).hexdigest()[:24],
            "detector_id": detector_id,
            "detector_version": catalog[detector_id]["version"],
            "source_hash": source_hash,
            "provenance": {
                "detector_id": detector_id,
                "detector_hash": catalog[detector_id]["implementation_hash"],
                "source_hash": source_hash,
                "parameters": catalog[detector_id].get("parameters", {}),
            },
        }
        for detector_id in requested
    ]
