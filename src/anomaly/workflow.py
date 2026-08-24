from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from anomaly.attempts import run_attempts
from anomaly.case import _scan_case_tree, resume_case
from anomaly.owners import consume_owner
from anomaly.state import (
    MAX_ATTEMPTS,
    PHASES,
    WorkflowError,
    completed_phase,
    load_snapshot,
    pause_at,
)
from anomaly.workflow_inputs import normalize_inputs, registered_sources

Owner = dict[str, str]
OwnerInvoker = Callable[..., Any]
_OWNER_REGISTRY: Mapping[str, tuple[str, str]] = {
    "P0": ("handler", "resume-case"),
    "P1": ("handler", "register-sources"),
    "P2": ("handler", "prepare-and-profile"),
    "P3": ("handler", "recommend-detectors"),
    "P4": ("handler", "approve-and-detect"),
    "P5": ("skill", "anomaly"),
    "P6": ("persona", "anomaly-data-reviewer"),
    "P7": ("handler", "accept-and-report"),
}
_OWNER_INSTRUCTIONS = {
    ("skill", "anomaly"): "skills/anomaly/SKILL.md",
    ("persona", "anomaly-data-reviewer"): "agents/anomaly-data-reviewer.md",
}
_REQUIRED_INPUTS = {"P1": "sources", "P4": "gate_a", "P7": "gate_b"}


def resolve_workflow(
    snapshot: Mapping[str, Any],
    *,
    supplied: frozenset[str],
) -> dict[str, Any]:
    """Purely select the next Anomaly phase and its single owner."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("workflow snapshot must be a mapping")
    if not isinstance(supplied, frozenset) or any(not isinstance(name, str) for name in supplied):
        raise ValueError("supplied inputs must be a frozenset of names")
    last = completed_phase(snapshot)
    if last == "P7":
        return _resolution(snapshot, "P7", "complete", None, None, "Workflow complete through P7.")
    phase = PHASES[0] if last is None else PHASES[PHASES.index(last) + 1]
    attempts = _attempt_count(snapshot, phase)
    if snapshot.get("status") in {"blocked", "unavailable"}:
        resume = f"{phase} unavailable after {attempts} of {MAX_ATTEMPTS} attempts."
        return _resolution(snapshot, phase, "unavailable", None, None, resume)
    missing = _missing_input(phase, supplied)
    if missing is not None:
        previous = f" after {last}" if last else ""
        return _resolution(
            snapshot,
            phase,
            "paused",
            None,
            missing,
            f"Await {missing} for {phase}{previous}; no attempt consumed.",
        )
    kind, owner_id = _OWNER_REGISTRY[phase]
    owner = {"kind": kind, "id": owner_id}
    if last is None:
        resume = f"Start P0; attempt {attempts + 1} of {MAX_ATTEMPTS}."
    else:
        resume = f"Resume {phase} after {last}; attempt {attempts + 1} of {MAX_ATTEMPTS}."
    return _resolution(snapshot, phase, "ready", owner, None, resume)


def invoke_resolved_owner(
    resolution: Mapping[str, Any],
    *,
    case_root: Path,
    invoke: OwnerInvoker,
) -> Any:
    """Load and invoke the fixed reasoning owner selected by the resolver."""
    if resolution.get("status") != "ready":
        raise WorkflowError("only a ready resolution has an invokable owner")
    owner = resolution.get("owner")
    if not isinstance(owner, Mapping):
        raise WorkflowError("ready resolution is missing its owner")
    relative = _OWNER_INSTRUCTIONS.get((owner.get("kind"), owner.get("id")))
    if relative is None:
        raise WorkflowError("resolved owner is not a reasoning owner")
    if not callable(invoke):
        raise ValueError("reasoning owner invoker must be callable")
    path = Path(__file__).resolve().parents[2] / relative
    try:
        instructions = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise WorkflowError(f"installed owner instructions are unavailable: {relative}") from error
    selected = {"kind": str(owner["kind"]), "id": str(owner["id"])}
    return invoke(owner=selected, instructions=instructions, case_root=Path(case_root))


def run_workflow(
    root: Path,
    *,
    inputs: Mapping[str, Any] | None = None,
    invoke: OwnerInvoker | None = None,
) -> dict[str, Any]:
    """Resolve, execute, seal, and freshly resolve the installed P0-P7 flow."""
    supplied = normalize_inputs(inputs)
    case_root = Path(root)
    _scan_case_tree(case_root)
    case_root = case_root.resolve()
    resume_case(case_root)
    reason = (
        None
        if invoke is None
        else lambda resolution: invoke_resolved_owner(resolution, case_root=case_root, invoke=invoke)
    )
    while True:
        snapshot = load_snapshot(case_root)
        has_sources = bool(registered_sources(case_root, required=False))
        available = frozenset({*supplied, *({"sources"} if has_sources else set())})
        resolution = resolve_workflow(snapshot, supplied=available)
        if resolution["status"] in {"complete", "unavailable"}:
            return snapshot
        if resolution["status"] == "paused":
            return pause_at(case_root, snapshot, resolution["phase"], resolution["missing"])
        state = run_attempts(
            case_root,
            resolution["phase"],
            lambda attempt_dir: consume_owner(
                resolution,
                case_root,
                attempt_dir,
                supplied,
                reason,
            ),
        )
        if state.get("status") in {"blocked", "unavailable"}:
            return state


def _resolution(
    snapshot: Mapping[str, Any],
    phase: str,
    status: str,
    owner: Owner | None,
    missing: str | None,
    resume: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "owner": owner,
        "missing": missing,
        "attempts": _attempt_count(snapshot, phase),
        "invalidated_from": snapshot.get("invalidated_from"),
        "resume": resume,
    }


def _attempt_count(snapshot: Mapping[str, Any], phase: str) -> int:
    attempts = snapshot.get("attempts")
    return int(attempts.get(phase, 0) or 0) if isinstance(attempts, Mapping) else 0


def _missing_input(phase: str, supplied: frozenset[str]) -> str | None:
    required = _REQUIRED_INPUTS.get(phase)
    return required if required is not None and required not in supplied else None
