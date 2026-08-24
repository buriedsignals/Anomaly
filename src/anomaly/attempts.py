from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from anomaly._attempt_workspace import (
    create_workspace,
    discard_workspace,
    promote_workspace,
)
from anomaly.case import _scan_case_tree
from anomaly.identities import IDENTITY_PHASES, capture_identities
from anomaly.readme import project_readme
from anomaly.semantics import UnsafeCasePathError
from anomaly.state import (
    MAX_ATTEMPTS,
    PHASES,
    WorkflowError,
    append_event,
    completed_phase,
    load_snapshot,
    safe_error,
    safe_json,
    write_json_atomic,
    write_state,
)


def run_attempts(
    root: Path,
    phase: str,
    execute: Callable[[Path], Any],
    *,
    writes: Sequence[str],
) -> dict[str, Any]:
    """Execute one resolved owner in a durable, bounded attempt workspace."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase}")
    state = load_snapshot(root)
    completed = completed_phase(state)
    if completed is not None and PHASES.index(completed) >= PHASES.index(phase):
        return state
    attempts = dict(state.get("attempts", {}))
    attempt = int(attempts.get(phase, 0) or 0)
    while attempt < MAX_ATTEMPTS:
        attempt += 1
        attempts[phase] = attempt
        state.update({"phase": phase, "status": "active", "attempts": attempts})
        state.pop("awaiting_input", None)
        write_state(root, state)
        attempt_dir = root / ".anomaly" / "attempts" / phase / f"attempt-{attempt}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (attempt_dir / "result.json").unlink(missing_ok=True)
        attempt_path = _relative(root, attempt_dir)
        append_event(
            root,
            "phase_started",
            phase=phase,
            attempt=attempt,
            attempt_path=attempt_path,
        )
        workspace: Path | None = None
        try:
            workspace = create_workspace(root, attempt_dir)
            output = execute(workspace)
        except Exception as error:
            state = _finish_failure(
                root, phase, attempt, attempt_path, error, attempts, workspace
            )
            if attempt < MAX_ATTEMPTS:
                continue
            return state

        try:
            _scan_case_tree(workspace)
        except UnsafeCasePathError:
            discard_workspace(workspace)
            raise

        try:
            _write_output(attempt_dir, output)
            state = _success_state(
                root, workspace, phase, attempt, attempt_path, attempts
            )
            if phase == "P7":
                project_readme(workspace, state, phase)
            promote_workspace(root, workspace, attempt_dir, writes, state)
        except Exception as error:
            state = _finish_failure(
                root, phase, attempt, attempt_path, error, attempts, workspace
            )
            if attempt < MAX_ATTEMPTS:
                continue
            return state
        append_event(
            root,
            "phase_completed",
            phase=phase,
            attempt=attempt,
            attempt_path=attempt_path,
        )
        return state
    return state


def _success_state(
    root: Path,
    workspace: Path,
    phase: str,
    attempt: int,
    attempt_path: str,
    attempts: Mapping[str, int],
) -> dict[str, Any]:
    state = load_snapshot(root)
    state.update({"phase": phase, "status": "complete" if phase == "P7" else "active"})
    for key in ("awaiting_input", "blocked", "blocked_reason"):
        state.pop(key, None)
    completed = dict(state.get("completed", {}))
    completed[phase] = {"attempt": attempt, "attempt_path": attempt_path}
    state.update({"completed": completed, "attempts": dict(attempts)})
    if state.get("invalidated_from") == phase:
        state.pop("invalidated_from", None)
    capture_identities(workspace, state, phase)
    identities = state.get("identities", {})
    missing = [
        name
        for name, identity_phase in IDENTITY_PHASES.items()
        if PHASES.index(identity_phase) <= PHASES.index(phase)
        and name not in identities
    ]
    if missing:
        raise WorkflowError(
            "phase artifacts are missing required identities: " + ", ".join(missing)
        )
    return state


def _finish_failure(
    root: Path,
    phase: str,
    attempt: int,
    attempt_path: str,
    error: Exception,
    attempts: Mapping[str, int],
    workspace: Path | None,
) -> dict[str, Any]:
    if workspace is not None:
        discard_workspace(workspace)
    (root / attempt_path / "result.json").unlink(missing_ok=True)
    state = _record_failure(root, phase, attempt, attempt_path, error, attempts)
    if attempt < MAX_ATTEMPTS:
        append_event(
            root,
            "phase_retry",
            phase=phase,
            attempt=attempt,
            next_attempt=attempt + 1,
        )
    elif phase == "P7":
        project_readme(root, state, completed_phase(state))
    return state


def _record_failure(
    root: Path,
    phase: str,
    attempt: int,
    attempt_path: str,
    error: Exception,
    attempts: Mapping[str, int],
) -> dict[str, Any]:
    message = safe_error(error)
    failure = {"attempt": attempt, "attempt_path": attempt_path, "error": message}
    write_json_atomic(root / attempt_path / "failure.json", failure)
    append_event(
        root,
        "phase_failed",
        phase=phase,
        attempt=attempt,
        attempt_path=attempt_path,
        error=message,
    )
    state = load_snapshot(root)
    failures = dict(state.get("failures", {}))
    failures[phase] = [*failures.get(phase, []), failure]
    state.update({"attempts": dict(attempts), "failures": failures})
    if attempt == MAX_ATTEMPTS:
        state.update(
            {
                "phase": phase,
                "status": "unavailable",
                "blocked": True,
                "blocked_reason": message,
            }
        )
    write_state(root, state)
    if attempt == MAX_ATTEMPTS:
        append_event(
            root,
            "phase_unavailable",
            phase=phase,
            attempt=attempt,
            attempt_path=attempt_path,
            error=message,
        )
    return state


def _write_output(attempt_dir: Path, output: Any) -> None:
    payload = {"status": "completed"} if output is None else safe_json(output)
    write_json_atomic(attempt_dir / "result.json", payload)


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
