from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from anomaly.attempts import run_attempts
from anomaly._attempt_workspace import recover_interrupted_promotion
from anomaly.case import resume_case
from anomaly.owners import consume_owner
from anomaly.state import (
    MAX_ATTEMPTS,
    PHASES,
    WorkflowError,
    completed_phase,
    load_snapshot,
    pause_at,
)
from anomaly.workflow_inputs import input_capabilities, normalize_inputs, registered_sources

Owner = dict[str, str]
OwnerInvoker = Callable[..., Any]
_OWNER_REGISTRY: Mapping[str, tuple[str, str, tuple[str, ...]]] = {
    "P0": ("handler", "resume-case", ()),
    "P1": (
        "handler",
        "register-sources",
        ("data/sources.json", "data/raw", ".anomaly/receipts", ".anomaly/events.jsonl"),
    ),
    "P2": (
        "handler",
        "prepare-and-profile",
        ("data/prepared", "data/index.duckdb", "instructions", ".anomaly/events.jsonl"),
    ),
    "P3": (
        "handler",
        "recommend-detectors",
        ("detectors/plan.json", ".anomaly/events.jsonl"),
    ),
    "P4": (
        "handler",
        "approve-and-detect",
        (
            "detectors/plan.json",
            "detectors/used",
            "evidence/runs",
            "evidence/signals.jsonl",
            ".anomaly/receipts/gate-a.json",
            ".anomaly/events.jsonl",
        ),
    ),
    "P5": (
        "skill",
        "anomaly",
        ("findings/draft.json", ".anomaly/events.jsonl"),
    ),
    "P6": (
        "persona",
        "anomaly-data-reviewer",
        (
            "evidence/replay.json",
            "findings/review.json",
            ".anomaly/receipts/replay.json",
            ".anomaly/events.jsonl",
        ),
    ),
    "P7": (
        "handler",
        "accept-and-report",
        (
            "findings/findings.json",
            "findings/report.md",
            "findings/unresolved.md",
            "findings/charts",
            ".anomaly/receipts/gate-b.json",
            ".anomaly/receipts/charts.json",
            ".anomaly/events.jsonl",
            "README.md",
        ),
    ),
}
_OWNER_INSTRUCTIONS = {
    ("skill", "anomaly"): "skills/anomaly/SKILL.md",
    ("persona", "anomaly-data-reviewer"): "agents/anomaly-data-reviewer.md",
}
_REQUIRED_INPUTS: Mapping[str, tuple[str, ...]] = {
    "P1": ("sources", "now"),
    "P2": ("now",),
    "P3": ("now",),
    "P4": ("gate_a", "now"),
    "P7": ("gate_b",),
}


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
    kind, owner_id, _writes = _OWNER_REGISTRY[phase]
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
    resume_case(case_root)
    case_root = case_root.resolve()
    recover_interrupted_promotion(case_root)
    reason = (
        None
        if invoke is None
        else lambda resolution, owner_root: invoke_resolved_owner(
            resolution,
            case_root=owner_root,
            invoke=invoke,
        )
    )
    entry_phase: str | None = None
    while True:
        snapshot = load_snapshot(case_root)
        capabilities = set(input_capabilities(supplied))
        if "sources" not in supplied and registered_sources(case_root, required=False):
            capabilities.add("sources")
        resolution = resolve_workflow(snapshot, supplied=frozenset(capabilities))
        if entry_phase is None:
            entry_phase = resolution["phase"]
        if entry_phase != "P4":
            capabilities.discard("gate_a")
        if entry_phase != "P7":
            capabilities.discard("gate_b")
        resolution = resolve_workflow(snapshot, supplied=frozenset(capabilities))
        if resolution["status"] in {"complete", "unavailable"}:
            return snapshot
        if resolution["status"] == "paused":
            return pause_at(case_root, snapshot, resolution["phase"], resolution["missing"])
        phase = resolution["phase"]
        state = run_attempts(
            case_root,
            phase,
            lambda workspace: consume_owner(
                resolution,
                workspace,
                supplied,
                reason,
            ),
            writes=_OWNER_REGISTRY[phase][2],
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
    return next(
        (required for required in _REQUIRED_INPUTS.get(phase, ()) if required not in supplied),
        None,
    )
