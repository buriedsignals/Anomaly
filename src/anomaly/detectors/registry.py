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
    attribution = normalized.get("attribution")
    repository = normalized.get("source_repository")
    if isinstance(attribution, str) and attribution and isinstance(repository, str) and repository:
        if attribution not in str(normalized.get("description", "")):
            normalized["description"] = f"{normalized['description']} {attribution}; source repository: {repository}"
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
    return sorted(result, key=lambda item: (item.get("menu_order", 0), item["id"]))


def _table_matches(table: dict[str, Any], requirement: Any) -> bool:
    return requirement == "*" or (
        isinstance(requirement, str)
        and requirement in {table.get("table_id"), table.get("source_id"), table.get("name")}
    )


def _compatible_tables(root: Path, metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    has_profile = True
    try:
        profile = recommend._read_json(root, "data/prepared/profile.json")
        profile_tables = profile.get("tables") if isinstance(profile, dict) else None
    except recommend.RecommendationError:
        has_profile = False
        profile_tables = [
            {"table_id": table["table_id"], "source_id": table["source_id"]}
            for table in detect._prepared_tables(root)
        ]
    if not isinstance(profile_tables, list) or not profile_tables:
        return [], "profile has no prepared tables"
    requirements = metadata.get("required_tables", [])
    if isinstance(requirements, str):
        requirements = [requirements]
    if not isinstance(requirements, list):
        requirements = []
    if "*" in requirements:
        matched = [table for table in profile_tables if isinstance(table, dict)]
    else:
        matched = [
            table for table in profile_tables
            if isinstance(table, dict)
            and any(_table_matches(table, requirement) for requirement in requirements)
        ]
        if any(
            not any(
                isinstance(table, dict) and _table_matches(table, requirement)
                for table in profile_tables
            )
            for requirement in requirements
        ):
            return [], "incompatible with profile (required table)"
    fields = metadata.get("required_fields", [])
    if isinstance(fields, str):
        fields = [fields]
    if not isinstance(fields, list):
        fields = []
    if has_profile and any(
        not isinstance(table.get("fields"), dict)
        or any(field not in table["fields"] for field in fields if isinstance(field, str))
        for table in matched
    ):
        return [], "incompatible with profile (required field)"
    return matched, None


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
    filtered = _menu_selection(metadata, limit=len(metadata), group=group, family=family, signal_category=signal_category)
    case_ready = detector_roots is None and root.is_dir() and (root / "data" / "index.duckdb").is_file()
    eligible: list[dict[str, Any]] = []
    reasons: dict[str, dict[str, Any]] = {}
    blocked: list[dict[str, str]] = []
    for item in filtered:
        tables: list[dict[str, Any]] = []
        if case_ready:
            try:
                tables, reason = _compatible_tables(root, item)
            except (RegistryError, recommend.RecommendationError):
                reason = "incompatible with prepared profile"
            if reason is not None:
                blocked.append({"id": item["id"], "reason": reason})
                continue
        eligible.append(item)
        reasons[item["id"]] = {"table_ids": [table["table_id"] for table in tables]}
    selected: list[dict[str, Any]] = []
    dimensions: set[str] = set()
    for item in eligible:
        dimension = str(item.get("data_type", item.get("signal_category", "")))
        if dimension not in dimensions:
            selected.append(item)
            dimensions.add(dimension)
        if len(selected) >= limit:
            break
    for item in eligible:
        if len(selected) >= limit:
            break
        if item not in selected:
            selected.append(item)
    selected = selected[:limit]
    selected_ids = [item["id"] for item in selected]
    return {
        "recommended": selected_ids,
        "approved": [],
        "parameters": {item["id"]: item.get("parameters", {}) for item in selected},
        "reasons": {item_id: reasons[item_id] for item_id in selected_ids},
        "blocked": sorted(blocked, key=lambda item: item["id"]),
    }


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
    if not root.is_dir():
        raise RegistryError("prepared case with index is required")
    try:
        try:
            index = detect._owned_path(root, "data/index.duckdb", "data")
        except detect.UnsafeCasePathError as error:
            raise RegistryError("prepared case with index is required") from error
        if not index.is_file() or index.is_symlink():
            raise RegistryError("prepared case with index is required")
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
            detector_tables = [tables[item] for item in selected_table_ids]
            if any(table["source_hash"] not in source_hashes.values() for table in detector_tables):
                raise RegistryError("prepared source is not registered")
            declared_memory = metadata.get("resource_limits", {}).get("memory_mb")
            if isinstance(declared_memory, int) and not isinstance(declared_memory, bool) and declared_memory > 0:
                if "memory_mb" in (limits or {}) and execution_limits["memory_mb"] > declared_memory:
                    raise RegistryError(f"requested memory exceeds detector bound: {detector_id}")
                detector_limits = {**execution_limits, "memory_mb": min(execution_limits["memory_mb"], declared_memory)}
            else:
                detector_limits = execution_limits
            query = (Path(metadata["package"]) / "query.sql").read_text(encoding="utf-8")
            source_tables = {item["source_id"]: detect._identifier(item["table_id"]) for item in detector_tables}
            for source_id, prepared_id in source_tables.items():
                query = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(source_id)}(?![A-Za-z0-9_])", prepared_id, query)
            query = query.replace("{{table_id}}", detect._identifier(detector_tables[0]["table_id"]))
            detect.validate_read_only_sql(query)
            with duckdb.connect(str(index), read_only=True) as connection:
                connection.execute("PRAGMA enable_external_access=false")
                connection.execute("SET threads = ?", [detector_limits["threads"]])
                connection.execute(f"PRAGMA memory_limit='{detector_limits['memory_mb']}MB'")
                rows = detect._run_query(
                    connection, query, list(metadata.get("parameters", {}).values()),
                    detector_limits["timeout_seconds"], detector_limits["max_output_rows"],
                )
            for row in rows:
                candidate = str(row.get("candidate_id") or next(iter(row.values()), "candidate"))
                executed_at = datetime.now(timezone.utc).isoformat()
                evidence_refs = [
                    {
                        "source_id": table["source_id"],
                        "table_id": table["table_id"],
                        "candidate_id": row.get("candidate_id", candidate),
                    }
                    for table in detector_tables
                ]
                payload = normalize_detector_result(
                    _redact_output(
                        detect.redact_credentials(detect._json_safe(row)),
                        str(metadata.get("sensitive_output")),
                    ),
                    detector_id=detector_id,
                    source_detector_id=str(metadata.get("source_detector_id", detector_id)),
                    source_sql_hash=str(metadata.get("source_sql_hash", "")),
                    source_hash=detector_tables[0]["source_hash"],
                    detector_hash=metadata["implementation_hash"],
                    table_id=detector_tables[0]["table_id"],
                )
                payload.update(
                    {
                        "candidate_id": candidate,
                        "detector_version": metadata["version"],
                        "detector_hash": metadata["implementation_hash"],
                        "category": metadata["signal_category"],
                        "severity": metadata["severity"],
                        "observed_at": row.get("observed_at", executed_at),
                        "summary": metadata["title"],
                        "evidence_refs": evidence_refs,
                        "warnings": [],
                    }
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
                            "limits": detector_limits,
                        },
                        "table_ids": [table["table_id"] for table in detector_tables],
                        "source_hashes": [table["source_hash"] for table in detector_tables],
                        "table_sources": {
                            table["table_id"]: {
                                "source_id": table["source_id"],
                                "source_hash": table["source_hash"],
                            }
                            for table in detector_tables
                        },
                    }
                )
                payload["run_id"] = run_id
                payload["executed_at"] = executed_at
                payload["limits"] = detector_limits
                payload["signal_id"] = "signal-" + hashlib.sha256(
                    f"{detector_id}:{','.join(selected_table_ids)}:{candidate}".encode()
                ).hexdigest()[:24]
                results.append(payload)
        return results
    except detect.DetectorError as error:
        raise RegistryError(str(error)) from error
