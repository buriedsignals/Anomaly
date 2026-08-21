from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

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
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|authorization|credential|password|passwd|secret|token|private[_-]?key)",
    re.IGNORECASE,
)


class RegistryError(detect.DetectorError):
    """A detector package or execution request is invalid."""


def _redact_output(value: Any, policy: str) -> Any:
    if policy != "redact":
        return value
    if isinstance(value, dict):
        return {
            key: "[redacted]" if isinstance(key, str) and _SENSITIVE_KEY.search(key)
            else _redact_output(item, policy)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_output(item, policy) for item in value]
    return value


def _yaml(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RegistryError("detector package contains an unsafe metadata file")
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
    query_path = package / str(query_name)
    if query_name != "query.sql" or query_path.is_symlink() or not query_path.is_file():
        raise RegistryError("detector must provide query.sql")
    query = query_path.read_text(encoding="utf-8")
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
    for path in Path(package).rglob("*"):
        if path.is_symlink():
            raise RegistryError("detector package contains a symlink")
        if path.is_file() and path.name not in {"meta.yaml", "query.sql"} and "fixtures" not in path.parts:
            raise RegistryError("SQL-only detector package contains unsupported executable files")
    metadata = _yaml(package / "meta.yaml")
    if not isinstance(metadata.get("id"), str) or not _ID.fullmatch(metadata["id"]):
        raise RegistryError("invalid detector id")
    if not isinstance(metadata.get("version"), str) or not metadata["version"]:
        raise RegistryError("invalid detector version")
    if set(metadata) < _REQUIRED | {"query"}:
        raise RegistryError("invalid or incomplete detector metadata")
    if not isinstance(metadata.get("parameters"), dict):
        raise RegistryError("invalid detector parameters")
    if metadata.get("sensitive_output") not in {"redact", "reference", "none"}:
        raise RegistryError("invalid sensitive-output policy")
    _validate_query(package, metadata)
    normalized = dict(metadata)
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


def recommend_detectors(
    root: Path,
    *,
    max_detectors: int = 10,
    detector_roots: list[Path] | tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, bounded plan without executing detector SQL."""
    if not isinstance(max_detectors, int) or isinstance(max_detectors, bool) or max_detectors < 1:
        raise RegistryError("max_detectors must be positive")
    limit = min(max_detectors, 10)
    root = Path(root)
    metadata = discover_detectors(detector_roots)
    selected = [item["id"] for item in metadata[:limit]]
    table_ids: list[str] = []
    if root.is_dir() and (root / "data" / "index.duckdb").is_file():
        try:
            table_ids = [item["table_id"] for item in detect._prepared_tables(root)]
        except detect.DetectorError:
            table_ids = []
    plan = {
        "recommended": selected,
        "approved": [],
        "parameters": {item["id"]: item.get("parameters", {}) for item in metadata[:limit]},
        "reasons": {
            item["id"]: {"table_ids": table_ids}
            for item in metadata[:limit]
        },
        "blocked": [],
    }
    if root.is_dir():
        try:
            recommend._write_json(root, "detectors/plan.json", plan)
        except (OSError, recommend.RecommendationError):
            pass
    return plan


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
    if not root.is_dir() or not (root / "data" / "index.duckdb").is_file():
        raise RegistryError("prepared case with index is required")
    try:
        scopes = detect._require_gate_a(root, requested)
        execution_limits = detect._validate_limits(limits)
        tables = {item["table_id"]: item for item in detect._prepared_tables(root)}
        source_hashes = detect._included_source_hashes(root)
        results: list[dict[str, Any]] = []
        for detector_id in requested:
            metadata = catalog[detector_id]
            for table_id in scopes[detector_id]:
                if table_id == "*":
                    table_ids = tuple(tables)
                else:
                    table_ids = (table_id,)
                for selected_table_id in table_ids:
                    table = tables[selected_table_id]
                    if table["source_hash"] not in source_hashes.values():
                        raise RegistryError("prepared source is not registered")
                    query = (Path(metadata["package"]) / "query.sql").read_text(encoding="utf-8")
                    query = query.replace("{{table_id}}", detect._identifier(selected_table_id))
                    detect.validate_read_only_sql(query)
                    with duckdb.connect(str(root / "data" / "index.duckdb"), read_only=True) as connection:
                        connection.execute("PRAGMA enable_external_access=false")
                        connection.execute("SET threads = ?", [execution_limits["threads"]])
                        rows = detect._run_query(
                            connection, query, list(metadata.get("parameters", {}).values()),
                            execution_limits["timeout_seconds"], execution_limits["max_output_rows"],
                        )
                    for row in rows:
                        candidate = str(row.get("candidate_id", "candidate"))
                        payload = {
                            **_redact_output(
                                detect.redact_credentials(detect._json_safe(row)),
                                str(metadata.get("sensitive_output")),
                            ),
                            "status": "lead", "detector_id": detector_id,
                            "table_id": selected_table_id, "source_hash": table["source_hash"],
                            "signal_id": "signal-" + hashlib.sha256(
                                f"{detector_id}:{selected_table_id}:{candidate}".encode()
                            ).hexdigest()[:24],
                            "provenance": {
                                "detector_id": detector_id,
                                "detector_hash": metadata["implementation_hash"],
                                "source_hash": table["source_hash"],
                                "parameters": metadata.get("parameters", {}),
                            },
                        }
                        results.append(payload)
        return results
    except detect.DetectorError as error:
        raise RegistryError(str(error)) from error
