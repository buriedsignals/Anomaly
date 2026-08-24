from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from anomaly.state import PHASES, MAX_ATTEMPTS, WorkflowError, write_json_atomic, write_state

_PROMOTION = ".anomaly/promotion.json"


def create_workspace(root: Path, attempt_dir: Path) -> Path:
    workspace = attempt_dir / "workspace"
    discard_workspace(workspace)
    durable = root / ".anomaly"

    def ignore(directory: str, names: list[str]) -> set[str]:
        return {"attempts"} if Path(directory) == durable and "attempts" in names else set()

    shutil.copytree(root, workspace, ignore=ignore)
    return workspace


def promote_workspace(
    root: Path,
    workspace: Path,
    attempt_dir: Path,
    writes: Sequence[str],
    state: Mapping[str, Any],
) -> None:
    phase = attempt_dir.parent.name
    attempt = int(attempt_dir.name.removeprefix("attempt-"))
    attempt_path = attempt_dir.relative_to(root).as_posix()
    marker = {"phase": phase, "attempt": attempt, "attempt_path": attempt_path}
    marker_path = root / _PROMOTION
    write_json_atomic(marker_path, marker)
    _apply(root, workspace, _validated_writes(writes))
    write_state(root, state)
    discard_workspace(workspace)
    marker_path.unlink()


def recover_interrupted_promotion(root: Path) -> dict[str, Any] | None:
    marker_path = root / _PROMOTION
    if not marker_path.exists():
        return None
    marker = _read_marker(marker_path)
    state = _read_state(root)
    phase = marker["phase"]
    attempt = marker["attempt"]
    attempt_path = marker["attempt_path"]
    attempts = dict(state.get("attempts", {}))
    attempts[phase] = attempt
    state.update(
        {
            "phase": phase,
            "status": "blocked",
            "attempts": attempts,
            "blocked": True,
            "blocked_reason": (
                f"Repair required after interrupted promotion in {phase}, attempt {attempt}; "
                f"inspect retained workspace {attempt_path}/workspace."
            ),
        }
    )
    write_state(root, state)
    return state


def discard_workspace(workspace: Path) -> None:
    try:
        if workspace.is_symlink() or workspace.is_file():
            workspace.unlink(missing_ok=True)
        elif workspace.is_dir():
            shutil.rmtree(workspace)
    except FileNotFoundError:
        pass


def _apply(root: Path, workspace: Path, writes: Sequence[str]) -> None:
    for relative in writes:
        live = _artifact(root, relative)
        staged = _artifact(workspace, relative)
        if not staged.exists():
            discard_workspace(live)
            continue
        live.parent.mkdir(parents=True, exist_ok=True)
        if live.is_symlink() or live.is_dir() or (live.exists() and staged.is_dir()):
            discard_workspace(live)
        staged.replace(live)


def _read_marker(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError("invalid interrupted-promotion marker") from error
    if not isinstance(value, dict):
        raise WorkflowError("invalid interrupted-promotion marker")
    phase = value.get("phase")
    attempt = value.get("attempt")
    if (
        not isinstance(phase, str)
        or phase not in PHASES
        or type(attempt) is not int
        or not 1 <= attempt <= MAX_ATTEMPTS
    ):
        raise WorkflowError("invalid interrupted-promotion attempt")
    attempt_path = f".anomaly/attempts/{phase}/attempt-{attempt}"
    if value.get("attempt_path") != attempt_path:
        raise WorkflowError("invalid interrupted-promotion path")
    return {"phase": phase, "attempt": attempt, "attempt_path": attempt_path}


def _read_state(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / ".anomaly" / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError("invalid workflow state during interrupted promotion") from error
    if not isinstance(value, dict):
        raise WorkflowError("invalid workflow state during interrupted promotion")
    return value


def _validated_writes(writes: Sequence[Any]) -> tuple[str, ...]:
    if isinstance(writes, (str, bytes)):
        raise WorkflowError("phase write set must be a sequence of relative paths")
    result: list[str] = []
    for value in writes:
        if not isinstance(value, str):
            raise WorkflowError("phase write paths must be strings")
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
            raise WorkflowError(f"unsafe phase write path: {value}")
        result.append(path.as_posix())
    if len(result) != len(set(result)):
        raise WorkflowError("phase write paths must be unique")
    return tuple(result)


def _artifact(root: Path, relative: str) -> Path:
    return root.joinpath(*PurePosixPath(relative).parts)
