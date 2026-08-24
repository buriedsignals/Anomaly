from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from anomaly.identities import IDENTITY_PHASES, changed_identities
from anomaly.readme import project_readme
from anomaly.semantics import redact_credentials

PHASES: tuple[str, ...] = tuple(f"P{index}" for index in range(8))
MAX_ATTEMPTS = 3


class WorkflowError(RuntimeError):
    """Anomaly could not safely advance its durable workflow."""


def completed_phase(snapshot: Mapping[str, Any]) -> str | None:
    completed = snapshot.get("completed")
    if not isinstance(completed, Mapping):
        return None
    last: str | None = None
    for phase in PHASES:
        if phase not in completed:
            break
        last = phase
    return last


def load_snapshot(root: Path) -> dict[str, Any]:
    root = Path(root)
    _ensure_durable_tree(root)
    state = _read_state(root)
    identities = state.get("identities")
    change = changed_identities(
        root,
        identities if isinstance(identities, Mapping) else {},
        through_phase=completed_phase(state),
    )
    if change is not None:
        start, changed = change
        state = _invalidate_state(
            root,
            state,
            start,
            changed,
            reason="authoritative artifact identity changed",
        )
    completed = completed_phase(state)
    if completed == "P7":
        project_readme(root, state, completed)
    return state


def pause_at(root: Path, snapshot: Mapping[str, Any], phase: str, missing: str) -> dict[str, Any]:
    if phase not in PHASES or not missing:
        raise ValueError("a known phase and missing input are required")
    if (
        snapshot.get("status") == "paused"
        and snapshot.get("phase") == phase
        and snapshot.get("awaiting_input") == missing
    ):
        return dict(snapshot)
    state = dict(snapshot)
    state.update({"phase": phase, "status": "paused", "awaiting_input": missing})
    write_state(root, state)
    append_event(root, "workflow_paused", phase=phase, awaiting_input=missing)
    return state


def append_event(
    root: Path,
    event: str,
    *,
    phase: str | None = None,
    attempt: int | None = None,
    **fields: Any,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"event": event, "at": datetime.now(timezone.utc).isoformat()}
    if phase is not None:
        payload["phase"] = phase
    if attempt is not None:
        payload["attempt"] = attempt
    payload.update(safe_json(fields))
    try:
        with (root / ".anomaly" / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError:
        return None
    return payload


def write_state(root: Path, state: Mapping[str, Any]) -> None:
    canonical = dict(state)
    canonical.pop("last_completed_phase", None)
    canonical.pop("gate", None)
    path = root / ".anomaly" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, canonical)


def write_json_atomic(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {_safe_text(key): safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(value)


def safe_error(value: Any) -> str:
    return _safe_text(value)[:2000]


def _safe_text(value: Any) -> str:
    return str(redact_credentials(str(value)))


def _invalidate_state(
    root: Path,
    state: dict[str, Any],
    start: str,
    changed: Sequence[str],
    *,
    reason: str,
) -> dict[str, Any]:
    previous = completed_phase(state)
    start_index = PHASES.index(start)
    invalidated_phases = PHASES[start_index:]
    completed = dict(state.get("completed", {}))
    for phase in invalidated_phases:
        completed.pop(phase, None)
    remaining = completed_phase({"completed": completed})
    safe_reason = safe_error(reason)
    state.update(
        {
            "phase": remaining or "P0",
            "status": "active",
            "invalidated_from": start,
            "completed": completed,
            "invalidations": [
                *state.get("invalidations", []),
                {"from": start, "changed": list(changed), "reason": safe_reason},
            ],
        }
    )
    for key in ("attempts", "failures"):
        values = dict(state.get(key, {}))
        for phase in invalidated_phases:
            values.pop(phase, None)
        state[key] = values
    identities = dict(state.get("identities", {}))
    for name, phase in IDENTITY_PHASES.items():
        if PHASES.index(phase) >= start_index:
            identities.pop(name, None)
    state["identities"] = identities
    for key in ("awaiting_input", "blocked", "blocked_reason"):
        state.pop(key, None)
    write_state(root, state)
    if previous == "P7":
        project_readme(root, state, remaining)
    append_event(
        root,
        "invalidation",
        phase=start,
        changed=list(changed),
        reason=safe_reason,
        previous_completed=previous,
    )
    return state


def _ensure_durable_tree(root: Path) -> None:
    durable = root / ".anomaly"
    (durable / "receipts").mkdir(parents=True, exist_ok=True)
    (durable / "attempts").mkdir(parents=True, exist_ok=True)
    if not (durable / "state.json").is_file():
        write_state(root, {"phase": "P0", "status": "active", "attempts": {}, "completed": {}})
    events_path = durable / "events.jsonl"
    if not events_path.exists():
        try:
            events_path.touch()
        except OSError:
            pass


def _read_state(root: Path) -> dict[str, Any]:
    try:
        state = json.loads((root / ".anomaly" / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError("invalid workflow state") from error
    if not isinstance(state, dict):
        raise WorkflowError("workflow state must be a record")
    return state
