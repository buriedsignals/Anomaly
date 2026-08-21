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
_GAIN_ATTRIBUTION = "Built during the GAIN 2026 Challenge; source repository: https://github.com/buriedsignals/gain-2026"


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


def normalize_detector_result(
    result: dict[str, Any],
    *,
    detector_id: str,
    source_detector_id: str,
    source_sql_hash: str,
    source_hash: str,
    detector_hash: str,
    table_id: str,
) -> dict[str, Any]:
    """Wrap one detector row as a local lead with source-bound lineage."""
    if not isinstance(result, dict) or not detector_id or not source_detector_id:
        raise RegistryError("detector result and provenance identifiers are required")
    if not detector_hash.startswith("sha256:") or not source_hash.startswith("sha256:"):
        raise RegistryError("detector and source hashes must be sha256 values")
    family = detector_id.split(".", 1)[0]
    return {
        **result,
        "status": "lead",
        "detector_id": detector_id,
        "table_id": table_id,
        "source_hash": source_hash,
        "provenance": {
            "source_family": family,
            "source_detector_id": source_detector_id,
            "source_sql_hash": source_sql_hash,
            "source_hash": source_hash,
            "detector_hash": detector_hash,
            "table_id": table_id,
        },
    }


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
    if normalized.get("family") == "gain":
        normalized["description"] = f"{normalized['description']} {_GAIN_ATTRIBUTION}"
        normalized["attribution"] = _GAIN_ATTRIBUTION
        normalized["source_repository"] = "https://github.com/buriedsignals/gain-2026"
        normalized["group"] = "gain"
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
    def menu_key(item: dict[str, Any]) -> tuple[int, int, str]:
        family = str(item.get("family", "core"))
        source_id = str(item.get("source_detector_id", ""))
        numeric_source_id = int(source_id[1:]) if family == "gain" and source_id[1:].isdigit() else 0
        return (1 if family == "gain" else 0, numeric_source_id, item["id"])

    return sorted(result, key=menu_key)


def _menu_selection(
    metadata: list[dict[str, Any]],
    *,
    limit: int,
    group: str | None,
    family: str | None,
    signal_category: str | None,
) -> list[dict[str, Any]]:
    selected = [
        item for item in metadata
        if (group is None or item.get("group") == group)
        and (family is None or item.get("family", "core") == family)
        and (signal_category is None or item.get("signal_category") == signal_category)
    ]
    return selected[:limit]


def recommend_detectors(
    root: Path,
    *,
    max_detectors: int = 10,
    detector_roots: list[Path] | tuple[Path, ...] | None = None,
    group: str | None = None,
    family: str | None = None,
    signal_category: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic, bounded plan without executing detector SQL."""
    if not isinstance(max_detectors, int) or isinstance(max_detectors, bool) or max_detectors < 1:
        raise RegistryError("max_detectors must be positive")
    limit = min(max_detectors, 10)
    if signal_category is not None and category is not None and signal_category != category:
        raise RegistryError("category and signal_category must agree")
    signal_category = signal_category or category
    root = Path(root)
    metadata = discover_detectors(detector_roots) if detector_roots is not None else discover_detectors()
    filtered = _menu_selection(
        metadata,
        limit=limit,
        group=group,
        family=family,
        signal_category=signal_category,
    )
    if group is not None or family is not None or signal_category is not None:
        return {
            "recommended": [item["id"] for item in filtered],
            "approved": [],
            "parameters": {item["id"]: item.get("parameters", {}) for item in filtered},
            "reasons": {item["id"]: {"table_ids": []} for item in filtered},
            "blocked": [],
        }
    if detector_roots is not None:
        selected = [item["id"] for item in metadata[:limit]]
        return {
            "recommended": selected,
            "approved": [],
            "parameters": {item["id"]: item.get("parameters", {}) for item in metadata[:limit]},
            "reasons": {item["id"]: {"table_ids": []} for item in metadata[:limit]},
            "blocked": [],
        }
    if not root.is_dir() or not (root / "data" / "index.duckdb").is_file():
        selected = [item["id"] for item in metadata[:limit]]
        return {"recommended": selected, "approved": [], "parameters": {}, "reasons": {}, "blocked": []}
    try:
        plan = recommend.recommend_detectors(root, now=datetime.now(timezone.utc), max_detectors=limit)
    except recommend.RecommendationError as error:
        table_ids = [table["table_id"] for table in detect._prepared_tables(root)]
        source_ids = {table["source_id"] for table in detect._prepared_tables(root)}
        eligible = [
            item for item in metadata
            if item.get("family") != "gain" or any(source_id.startswith("senate_") for source_id in source_ids)
        ]
        selected: list[dict[str, Any]] = []
        groups: set[str] = set()
        for item in eligible:
            if item.get("group") not in groups:
                selected.append(item)
                groups.add(str(item.get("group")))
            if len(selected) >= limit:
                break
        for item in eligible:
            if len(selected) >= limit:
                break
            if item not in selected:
                selected.append(item)
        gain_items = [item for item in eligible if item.get("family") == "gain"]
        if gain_items and not any(item.get("family") == "gain" for item in selected):
            selected[-1] = gain_items[0]
        plan = {
            "recommended": [item["id"] for item in selected],
            "approved": [],
            "parameters": {item["id"]: item.get("parameters", {}) for item in selected},
            "reasons": {item["id"]: {"table_ids": table_ids} for item in selected},
            "blocked": [],
        }
    try:
        source_ids = {table["source_id"] for table in detect._prepared_tables(root)}
    except detect.DetectorError:
        source_ids = set()
    if not any(source_id.startswith("senate_") for source_id in source_ids):
        allowed = {item["id"] for item in metadata if item.get("family") != "gain"}
        recommended = [item for item in plan["recommended"] if item in allowed]
        for item in sorted(allowed - set(recommended)):
            if len(recommended) >= limit:
                break
            recommended.append(item)
        plan["recommended"] = recommended[:limit]
        plan["parameters"] = {item: plan["parameters"][item] for item in plan["parameters"] if item in plan["recommended"]}
        plan["reasons"] = {item: plan["reasons"][item] for item in plan["reasons"] if item in plan["recommended"]}
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
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        for detector_id in requested:
            metadata = catalog[detector_id]
            scope = scopes[detector_id]
            selected_table_ids = tuple(scope) if "*" not in scope else tuple(tables)
            if not selected_table_ids:
                raise RegistryError("approved table scope is empty")
            table = tables[selected_table_ids[0]]
            if any(tables[item]["source_hash"] not in source_hashes.values() for item in selected_table_ids):
                raise RegistryError("prepared source is not registered")
            query = (Path(metadata["package"]) / "query.sql").read_text(encoding="utf-8")
            source_tables = {item["source_id"]: detect._identifier(item["table_id"]) for item in tables.values()}
            for source_id, prepared_id in source_tables.items():
                query = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(source_id)}(?![A-Za-z0-9_])", prepared_id, query)
            query = query.replace("{{table_id}}", detect._identifier(table["table_id"]))
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
                payload = normalize_detector_result(
                    _redact_output(
                        detect.redact_credentials(detect._json_safe(row)),
                        str(metadata.get("sensitive_output")),
                    ),
                    detector_id=detector_id,
                    source_detector_id=str(metadata.get("source_detector_id", detector_id)),
                    source_sql_hash=str(metadata.get("source_sql_hash", "")),
                    source_hash=table["source_hash"],
                    detector_hash=metadata["implementation_hash"],
                    table_id=table["table_id"],
                )
                payload["provenance"]["parameters"] = metadata.get("parameters", {})
                payload["provenance"].update(
                    {
                        "detector_version": metadata["version"],
                        "source_provenance_hash": metadata.get("source_provenance_hash"),
                        "source_csv_hash": metadata.get("source_csv_hash"),
                        "package_hash": metadata["implementation_hash"],
                        "run": {
                            "run_id": run_id,
                            "executed_at": datetime.now(timezone.utc).isoformat(),
                            "limits": execution_limits,
                        },
                    }
                )
                payload["run_id"] = run_id
                payload["executed_at"] = datetime.now(timezone.utc).isoformat()
                payload["limits"] = execution_limits
                payload["signal_id"] = "signal-" + hashlib.sha256(
                    f"{detector_id}:{table['table_id']}:{candidate}".encode()
                ).hexdigest()[:24]
                results.append(payload)
        return results
    except detect.DetectorError as error:
        raise RegistryError(str(error)) from error
