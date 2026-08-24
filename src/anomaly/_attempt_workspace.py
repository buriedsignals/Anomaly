from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from anomaly.state import WorkflowError, write_json_atomic, write_state

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
    relative_attempt = attempt_dir.relative_to(root).as_posix()
    entries = [
        {"path": relative, "original": _artifact(root, relative).exists(), "status": "pending"}
        for relative in _validated_writes(writes)
    ]
    journal: dict[str, Any] = {
        "schema_version": 1,
        "phase": attempt_dir.parent.name,
        "attempt": int(attempt_dir.name.removeprefix("attempt-")),
        "attempt_path": relative_attempt,
        "status": "prepared",
        "entries": entries,
    }
    journal_path = root / _PROMOTION
    write_json_atomic(journal_path, journal)
    try:
        _apply(root, workspace, attempt_dir, journal, journal_path)
        write_state(root, state)
    except Exception:
        _rollback(root, attempt_dir, journal, journal_path)
        _finish(attempt_dir, journal_path)
        raise
    _finish(attempt_dir, journal_path)


def recover_interrupted_promotion(root: Path) -> None:
    journal_path = root / _PROMOTION
    if not journal_path.exists():
        return
    journal = _read_journal(journal_path)
    attempt_dir = _attempt_dir(root, journal)
    if _is_sealed(root, journal):
        _finish(attempt_dir, journal_path)
        return
    if journal.get("status") != "rolled_back":
        _rollback(root, attempt_dir, journal, journal_path)
    _rewind_attempt(root, journal)
    _finish(attempt_dir, journal_path)


def discard_workspace(workspace: Path) -> None:
    try:
        if workspace.is_symlink() or workspace.is_file():
            workspace.unlink(missing_ok=True)
        elif workspace.is_dir():
            shutil.rmtree(workspace)
    except FileNotFoundError:
        pass


def _apply(
    root: Path,
    workspace: Path,
    attempt_dir: Path,
    journal: dict[str, Any],
    journal_path: Path,
) -> None:
    backup_root = attempt_dir / "promotion-backup"
    for entry in journal["entries"]:
        entry["status"] = "applying"
        write_json_atomic(journal_path, journal)
        relative = entry["path"]
        live = _artifact(root, relative)
        staged = _artifact(workspace, relative)
        backup = _artifact(backup_root, relative)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if entry["original"]:
            live.replace(backup)
        if staged.exists():
            live.parent.mkdir(parents=True, exist_ok=True)
            staged.replace(live)
        entry["status"] = "applied"
        write_json_atomic(journal_path, journal)
    journal["status"] = "promoted"
    write_json_atomic(journal_path, journal)


def _rollback(
    root: Path,
    attempt_dir: Path,
    journal: dict[str, Any],
    journal_path: Path,
) -> None:
    backup_root = attempt_dir / "promotion-backup"
    for entry in reversed(journal["entries"]):
        if entry.get("status") == "pending":
            continue
        live = _artifact(root, entry["path"])
        backup = _artifact(backup_root, entry["path"])
        if backup.exists():
            discard_workspace(live)
            live.parent.mkdir(parents=True, exist_ok=True)
            backup.replace(live)
        elif not entry["original"]:
            discard_workspace(live)
    journal["status"] = "rolled_back"
    write_json_atomic(journal_path, journal)


def _rewind_attempt(root: Path, journal: Mapping[str, Any]) -> None:
    state_path = root / ".anomaly" / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError("invalid workflow state during promotion recovery") from error
    if not isinstance(state, dict):
        raise WorkflowError("invalid workflow state during promotion recovery")
    attempts = dict(state.get("attempts", {}))
    phase = journal["phase"]
    previous = max(0, int(journal["attempt"]) - 1)
    if previous:
        attempts[phase] = previous
    else:
        attempts.pop(phase, None)
    state.update({"phase": phase, "status": "active", "attempts": attempts})
    write_state(root, state)


def _finish(attempt_dir: Path, journal_path: Path) -> None:
    discard_workspace(attempt_dir / "workspace")
    discard_workspace(attempt_dir / "promotion-backup")
    journal_path.unlink(missing_ok=True)


def _is_sealed(root: Path, journal: Mapping[str, Any]) -> bool:
    try:
        state = json.loads((root / ".anomaly" / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    completed = state.get("completed") if isinstance(state, dict) else None
    record = completed.get(journal["phase"]) if isinstance(completed, dict) else None
    return isinstance(record, dict) and record.get("attempt_path") == journal["attempt_path"]


def _read_journal(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError("invalid promotion journal") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise WorkflowError("invalid promotion journal")
    entries = value.get("entries")
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise WorkflowError("invalid promotion journal entries")
    _validated_writes([entry.get("path") for entry in entries])
    _attempt_dir(path.parents[1], value)
    return value


def _attempt_dir(root: Path, journal: Mapping[str, Any]) -> Path:
    phase = journal.get("phase")
    attempt = journal.get("attempt")
    expected = f".anomaly/attempts/{phase}/attempt-{attempt}"
    if phase not in {f"P{index}" for index in range(8)} or not isinstance(attempt, int):
        raise WorkflowError("invalid promotion journal attempt")
    if journal.get("attempt_path") != expected:
        raise WorkflowError("invalid promotion journal path")
    return root / expected


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
