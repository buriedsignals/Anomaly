from __future__ import annotations

import json
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from anomaly import detect
from anomaly.semantics import UnsafeCasePathError

_MAX_DETECTORS = 10
_PLAN_KEYS = {"recommended", "approved", "parameters", "reasons", "blocked"}


class RecommendationError(detect.DetectorError):
    """A detector recommendation or Gate A approval is invalid."""


def _case_path(root: Path, relative: str) -> Path:
    root = Path(root).resolve()
    candidate = root / relative
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise UnsafeCasePathError(f"unsafe case path: {relative}") from error
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise UnsafeCasePathError(f"unsafe case path: {relative}")
    return candidate


def _read_json(root: Path, relative: str) -> Any:
    path = _case_path(root, relative)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RecommendationError(f"invalid or missing {relative}") from error


def _write_json(root: Path, relative: str, payload: Any) -> None:
    path = _case_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_bundle(root: Path, writes: dict[str, Any]) -> None:
    """Commit related case JSON files together, restoring prior bytes on failure."""
    previous: dict[str, bytes | None] = {}
    paths: dict[str, Path] = {}
    for relative in writes:
        path = _case_path(root, relative)
        paths[relative] = path
        try:
            previous[relative] = path.read_bytes()
        except FileNotFoundError:
            previous[relative] = None
    try:
        for relative, payload in writes.items():
            _write_json(root, relative, payload)
    except Exception:
        for relative, path in paths.items():
            old = previous[relative]
            try:
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(old)
            except OSError:
                pass
        raise


def _number(value: Any, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(0.0, min(1.0, number))


def _requirements(meta: dict[str, Any]) -> tuple[list[Any], list[str], dict[str, Any], dict[str, Any]]:
    tables = meta.get("required_tables", [])
    if isinstance(tables, str):
        tables = [tables]
    if not isinstance(tables, list):
        tables = []
    fields = meta.get("required_fields", [])
    if isinstance(fields, str):
        fields = [fields]
    if not isinstance(fields, list):
        fields = []
    fields = [field for field in fields if isinstance(field, str)]
    types = meta.get("required_types", {})
    if not isinstance(types, dict):
        types = {}
    coverage = meta.get("minimum_coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    return tables, fields, types, coverage


def _table_name_matches(table: dict[str, Any], requirement: Any) -> bool:
    if requirement == "*":
        return True
    if not isinstance(requirement, str):
        return False
    return requirement in {
        table.get("table_id"),
        table.get("source_id"),
        table.get("name"),
    }


def _field_types(root: Path) -> dict[str, dict[str, str]]:
    manifest = _read_json(root, "data/prepared/transforms.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tables"), list):
        raise RecommendationError("invalid prepared transforms manifest")
    result: dict[str, dict[str, str]] = {}
    for table in manifest["tables"]:
        if not isinstance(table, dict) or not isinstance(table.get("table_id"), str):
            continue
        fields = table.get("fields", [])
        if not isinstance(fields, list):
            continue
        result[table["table_id"]] = {
            field["name"]: field["type"]
            for field in fields
            if isinstance(field, dict)
            and isinstance(field.get("name"), str)
            and isinstance(field.get("type"), str)
        }
    return result


def _field_metric(table: dict[str, Any], field: str) -> dict[str, Any] | None:
    fields = table.get("fields", {})
    if not isinstance(fields, dict):
        return None
    metric = fields.get(field)
    return metric if isinstance(metric, dict) else None


def _coverage(metric: dict[str, Any]) -> float:
    if "coverage" in metric:
        return _number(metric["coverage"], 0.0)
    return 1.0 - _number(metric.get("missing_fraction"), 0.0)


def _compatible_tables(
    root: Path, profile: dict[str, Any], meta: dict[str, Any]
) -> tuple[list[dict[str, Any]], str | None, float]:
    tables, required_fields, required_types, minimum_coverage = _requirements(meta)
    profile_tables = profile.get("tables") if isinstance(profile, dict) else None
    if not isinstance(profile_tables, list) or not profile_tables:
        return [], "profile has no prepared tables", 0.0
    field_types = _field_types(root)
    compatible: list[dict[str, Any]] = []
    fit_scores: list[float] = []
    for table in profile_tables:
        if not isinstance(table, dict) or not isinstance(table.get("table_id"), str):
            continue
        if tables and not any(_table_name_matches(table, requirement) for requirement in tables):
            continue
        types = dict(field_types.get(table["table_id"], {}))
        # A profile may carry types itself in hand-authored or migrated cases.
        profile_fields = table.get("fields", {})
        if isinstance(profile_fields, dict):
            for name, metric in profile_fields.items():
                if isinstance(metric, dict) and isinstance(metric.get("type"), str):
                    types.setdefault(name, metric["type"])
        if any(_field_metric(table, field) is None for field in required_fields):
            continue
        if any(
            field not in types
            or (
                (accepted_values := (accepted if isinstance(accepted, list) else [accepted]))
                and types[field] not in accepted_values
            )
            for field, accepted in required_types.items()
        ):
            continue
        coverages = [_coverage(_field_metric(table, field) or {}) for field in required_fields]
        insufficient = False
        for field, minimum in minimum_coverage.items():
            metric = _field_metric(table, field)
            if metric is None:
                insufficient = True
                break
            available = _coverage(metric)
            if available + 1e-12 < _number(minimum, 0.0):
                insufficient = True
                break
            if field not in required_fields:
                coverages.append(available)
        if insufficient:
            continue
        compatible.append(table)
        fit_scores.append(sum(coverages) / len(coverages) if coverages else 1.0)
    if compatible:
        return compatible, None, max(fit_scores)
    requirements = []
    if required_fields:
        requirements.append("required field")
    if required_types:
        requirements.append("required type")
    if minimum_coverage:
        requirements.append("coverage")
    if tables:
        requirements.append("required table")
    detail = ", ".join(requirements) or "profile"
    return [], f"incompatible with profile ({detail})", 0.0


def _selection_reason(meta: dict[str, Any], tables: list[dict[str, Any]]) -> str:
    table_text = " across prepared tables" if len(tables) > 1 else " on a prepared table"
    return (
        f"Selected for {meta.get('title', meta['id'])}{table_text}; "
        "the deterministic score balances relevance, data fit, expected utility, cost, and known false-positive risk."
    )


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    scores = item["scores"]
    total = (
        scores["relevance"]
        + scores["data_fit"]
        + scores["utility"]
        - scores["cost"]
        - scores["false_positive_risk"]
    )
    return (-total, -scores["relevance"], -scores["data_fit"], -scores["utility"], scores["cost"], scores["false_positive_risk"], item["id"])


def recommend_detectors(root: Path, *, now: datetime, max_detectors: int = _MAX_DETECTORS) -> dict[str, Any]:
    """Recommend compatible built-in detectors without executing any detector code or SQL."""
    root = Path(root)
    if not root.is_dir():
        raise RecommendationError("case root is not a directory")
    if isinstance(max_detectors, bool) or not isinstance(max_detectors, int) or max_detectors < 1:
        raise RecommendationError("max_detectors must be a positive integer")
    limit = min(max_detectors, _MAX_DETECTORS)
    profile = _read_json(root, "data/prepared/profile.json")
    metadata = detect.load_detector_metadata()
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for meta in sorted(metadata, key=lambda item: str(item.get("id", ""))):
        detector_id = meta.get("id")
        if not isinstance(detector_id, str) or not detector_id or any(char in detector_id for char in "/\\"):
            continue
        compatible, blocked_reason, data_fit = _compatible_tables(root, profile, meta)
        if blocked_reason is not None:
            blocked.append({"id": detector_id, "reason": blocked_reason})
            continue
        scores = {
            "relevance": _number(meta.get("relevance")),
            "data_fit": _number(data_fit),
            "utility": _number(meta.get("utility")),
            "cost": _number(meta.get("cost")),
            "false_positive_risk": _number(meta.get("false_positive_risk")),
        }
        candidates.append(
            {
                "id": detector_id,
                "group": str(meta.get("group") or detector_id.split(".", 1)[0]),
                "parameters": meta.get("parameters") if isinstance(meta.get("parameters"), dict) else {},
                "scores": scores,
                "tables": compatible,
                "meta": meta,
            }
        )
    candidates.sort(key=_rank_key)
    selected: list[dict[str, Any]] = []
    groups: set[str] = set()
    for candidate in candidates:
        if len(selected) >= limit:
            break
        if candidate["group"] not in groups:
            selected.append(candidate)
            groups.add(candidate["group"])
    if len(selected) < limit:
        selected_ids = {candidate["id"] for candidate in selected}
        selected.extend(candidate for candidate in candidates if candidate["id"] not in selected_ids)
        selected = selected[:limit]
    recommended = [candidate["id"] for candidate in selected]
    parameters = {candidate["id"]: candidate["parameters"] for candidate in selected}
    reasons = {
        candidate["id"]: {
            "scores": candidate["scores"],
            "table_ids": sorted(
                table["table_id"]
                for table in candidate["tables"]
                if isinstance(table, dict) and isinstance(table.get("table_id"), str)
            ),
            "selection": _selection_reason(candidate["meta"], candidate["tables"]),
            "assumptions": ["prepared profile and detector metadata are current"],
            "known_failure_modes": ["results can include false positives and require journalist review"],
        }
        for candidate in selected
    }
    plan = {
        "recommended": recommended,
        "approved": [],
        "parameters": parameters,
        "reasons": reasons,
        "blocked": sorted(blocked, key=lambda item: item["id"]),
    }
    _write_json(root, "detectors/plan.json", plan)
    return plan


def approve_detector_plan(
    root: Path, approved_ids: list[str] | tuple[str, ...], *, approved_by: str, now: datetime
) -> dict[str, Any]:
    """Record Gate A approval for a subset of the current recommendation."""
    root = Path(root)
    plan = _read_json(root, "detectors/plan.json")

    if not isinstance(plan, dict) or set(plan) != _PLAN_KEYS:
        raise RecommendationError("invalid detector plan")
    if not isinstance(approved_ids, (list, tuple)):
        raise RecommendationError("approved detector ids must be a list")
    approved = list(approved_ids)
    if len(approved) > _MAX_DETECTORS:
        raise RecommendationError("maximum of 10 detectors may be approved")
    if any(not isinstance(item, str) or "/" in item or "\\" in item for item in approved):
        raise RecommendationError("unknown detector id")
    if len(set(approved)) != len(approved):
        raise RecommendationError("duplicate detector ids are not allowed")
    recommended = plan.get("recommended")
    if not isinstance(recommended, list):
        raise RecommendationError("invalid detector plan")
    allowed = set(recommended)
    for detector_id in approved:
        if detector_id not in allowed:
            raise RecommendationError(f"detector is unknown, blocked, or not recommended: {detector_id}")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise RecommendationError("approved_by is required")
    plan = dict(plan)
    plan["approved"] = approved
    plan_hash = _canonical_hash(plan)
    receipt = {
        "kind": "user-approval",
        "gate": "A",
        "plan_identity": "detectors/plan.json",
        "plan_id": "detectors/plan.json",
        "plan_hash": plan_hash,
        "recommended": list(recommended),
        "approved": approved,
        "approved_by": approved_by,
        "approved_at": now.isoformat(),
    }
    state = _read_json(root, ".anomaly/state.json")
    if not isinstance(state, dict):
        raise RecommendationError("invalid case state")
    state = dict(state)
    state["phase"] = "P4"
    state["gate"] = "A"
    _write_bundle(
        root,
        {
            "detectors/plan.json": plan,
            ".anomaly/receipts/gate-a.json": receipt,
            ".anomaly/state.json": state,
        },
    )
    return plan
