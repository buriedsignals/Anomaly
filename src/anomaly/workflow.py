from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from anomaly.semantics import redact_credentials

PHASES: tuple[str, ...] = tuple(f"P{index}" for index in range(8))
MAX_ATTEMPTS = 3
_SECRET = re.compile(r"(?:sk_live_|ghp_|github_pat_)[A-Za-z0-9_]+")
_IDENTITY_PHASES: dict[str, str] = {
    "source": "P1",
    "prepared": "P2",
    "recommendation": "P3",
    "gate_a": "P4",
    "detector": "P4",
    "draft": "P5",
    "replay": "P6",
    "review": "P6",
    "gate_b": "P7",
}
_NON_SOURCE_RECEIPTS = {"charts.json", "gate-a.json", "gate-b.json", "replay.json"}


class WorkflowError(RuntimeError):
    """The durable phase runner could not execute a workflow."""


class RetryLimitExceeded(WorkflowError):
    """A phase failed three times and was made unavailable."""


@dataclass(frozen=True)
class PhaseResult:
    phase: str
    status: str
    attempt: int
    output: Any = None
    error: str | None = None


PhaseHandler = Callable[..., Any]


class WorkflowRunner:
    """Run Anomaly's linear phases with durable, restart-safe bookkeeping.

    Handlers are deliberately small and injectable.  A handler may accept no
    arguments, ``attempt_dir``, ``attempt_dir, context``, or
    ``root, attempt_dir, context``.  Its output is retained as JSON in the
    attempt directory; handlers remain responsible for validating and
    promoting their domain artifacts.
    """

    def __init__(
        self,
        root: Path,
        phases: Mapping[str, PhaseHandler] | Sequence[PhaseHandler] | None = None,
        *,
        handlers: Mapping[str, PhaseHandler] | Sequence[PhaseHandler] | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        phase_handlers: Mapping[str, PhaseHandler] | Sequence[PhaseHandler] | None = None,
        fingerprints: Mapping[str, Any] | None = None,
        input_fingerprint: Any = None,
        profile_fingerprint: Any = None,
        detector_fingerprint: Any = None,
        parameter_fingerprint: Any = None,
        required_journalist_id: str | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        if max_attempts != MAX_ATTEMPTS:
            raise ValueError("Anomaly permits exactly three attempts per phase")
        self.max_attempts = MAX_ATTEMPTS
        self._handlers = (
            phase_handlers
            if phase_handlers is not None
            else (handlers if handlers is not None else phases)
        )
        self._fingerprints = dict(fingerprints or {})
        for name, value in (
            ("input", input_fingerprint),
            ("profile", profile_fingerprint),
            ("detector", detector_fingerprint),
            ("parameters", parameter_fingerprint),
        ):
            if value is not None:
                self._fingerprints[name] = value
        if required_journalist_id is not None:
            if not isinstance(required_journalist_id, str) or not required_journalist_id.strip():
                raise ValueError("required journalist identity must be non-empty")
            self._required_journalist_id = required_journalist_id.strip()
        else:
            self._required_journalist_id = None
        self._ensure_durable_tree()
        if self._required_journalist_id is not None:
            state = self.load_state()
            if state.get("required_journalist_id") != self._required_journalist_id:
                state["required_journalist_id"] = self._required_journalist_id
                self._write_state(state)
        if self._fingerprints:
            self._check_fingerprints()
    # -- durable storage -------------------------------------------------

    @property
    def state_path(self) -> Path:
        return self.root / ".anomaly" / "state.json"

    @property
    def events_path(self) -> Path:
        return self.root / ".anomaly" / "events.jsonl"

    def _ensure_durable_tree(self) -> None:
        anomaly = self.root / ".anomaly"
        (anomaly / "receipts").mkdir(parents=True, exist_ok=True)
        (anomaly / "attempts").mkdir(parents=True, exist_ok=True)
        if not self.state_path.is_file():
            self._write_state(
                {
                    "phase": "P0",
                    "last_completed_phase": None,
                    "status": "active",
                    "attempts": {},
                    "fingerprints": {},
                }
            )
        if not self.events_path.exists():
            try:
                self.events_path.touch()
            except OSError:
                pass

    def load_state(self) -> dict[str, Any]:
        state = self._read_state()
        changed = [
            name
            for name, digest in state.get("identities", {}).items()
            if name in _IDENTITY_PHASES
            and digest != _artifact_identity(self.root, name)
        ]
        if not changed:
            return state
        start = min((_IDENTITY_PHASES[name] for name in changed), key=PHASES.index)
        return self._invalidate_state(
            state,
            start,
            changed,
            reason="authoritative artifact identity changed",
        )

    def _read_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise WorkflowError("invalid workflow state") from error
        if not isinstance(value, dict):
            raise WorkflowError("workflow state must be a record")
        return value

    read_state = load_state

    def _write_state(self, state: Mapping[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def events(self) -> list[dict[str, Any]]:
        if not self.events_path.is_file():
            return []
        result: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    read_events = events

    def append_event(
        self,
        event: str,
        *,
        phase: str | None = None,
        attempt: int | None = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "event": event,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if phase is not None:
            payload["phase"] = phase
        if attempt is not None:
            payload["attempt"] = attempt
        payload.update(_safe_json(fields))
        try:
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, sort_keys=True) + "\n")
        except OSError:
            return None
        return payload

    def pause(self, awaiting_input: str, *, phase: str) -> dict[str, Any]:
        if phase not in PHASES:
            raise ValueError(f"unknown phase: {phase}")
        if not isinstance(awaiting_input, str) or not awaiting_input:
            raise ValueError("awaiting input is required")
        state = self.load_state()
        if (
            state.get("status") == "paused"
            and state.get("awaiting_input") == awaiting_input
            and state.get("phase") == phase
        ):
            return state
        state["phase"] = phase
        state["status"] = "paused"
        state["awaiting_input"] = awaiting_input
        self._write_state(state)
        self.append_event("workflow_paused", phase=phase, awaiting_input=awaiting_input)
        return state

    def continue_after_pause(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("status") != "paused" and "awaiting_input" not in state:
            return state
        awaiting_input = state.pop("awaiting_input", None)
        state["status"] = "active"
        self._write_state(state)
        self.append_event(
            "workflow_resumed",
            phase=state.get("phase"),
            supplied_input=awaiting_input,
        )
        return state

    # -- invalidation ----------------------------------------------------

    def invalidate(
        self,
        changed: str | Sequence[str],
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        fields = [changed] if isinstance(changed, str) else list(changed)
        if not fields or any(not isinstance(item, str) or not item for item in fields):
            raise ValueError("changed fields are required")
        start = min((_invalidation_phase(item) for item in fields), key=PHASES.index)
        return self._invalidate_state(self.load_state(), start, fields, reason=reason)

    def _invalidate_state(
        self,
        state: dict[str, Any],
        start: str,
        changed: Sequence[str],
        *,
        reason: str | None,
    ) -> dict[str, Any]:
        previous = _completed_phase(state)
        start_index = PHASES.index(start)
        completed = dict(state.get("completed", {}))
        for phase in PHASES[start_index:]:
            completed.pop(phase, None)
        last_completed = _completed_phase({"completed": completed})
        state["phase"] = last_completed or "P0"
        state["last_completed_phase"] = last_completed
        state["status"] = "active"
        state["invalidated_from"] = start
        state["invalidations"] = [
            *state.get("invalidations", []),
            {
                "from": start,
                "changed": list(changed),
                "reason": _safe_error(reason) if reason else None,
            },
        ]
        state["completed"] = completed
        for key in ("attempts", "failures"):
            values = dict(state.get(key, {}))
            for phase in PHASES[start_index:]:
                values.pop(phase, None)
            state[key] = values
        identities = dict(state.get("identities", {}))
        for name, phase in _IDENTITY_PHASES.items():
            if PHASES.index(phase) >= start_index:
                identities.pop(name, None)
        state["identities"] = identities
        for key in ("awaiting_input", "blocked", "blocked_reason"):
            state.pop(key, None)
        if start_index <= PHASES.index("P4"):
            state.pop("gate", None)
        elif start_index <= PHASES.index("P7") and state.get("gate") == "B":
            state["gate"] = "A"
        self._write_state(state)
        self.append_event(
            "invalidation",
            phase=start,
            changed=list(changed),
            reason=_safe_error(reason) if reason else None,
            previous_last_completed=previous,
        )
        return state

    invalidate_downstream = invalidate
    record_invalidation = invalidate

    def _check_fingerprints(self) -> None:
        if not self._fingerprints:
            return
        state = self.load_state()
        previous = state.get("fingerprints")
        if not isinstance(previous, dict):
            previous = {}
        changed = [name for name, value in self._fingerprints.items() if name in previous and previous[name] != value]
        if changed:
            self.invalidate(changed, reason="workflow dependency changed")
            state = self.load_state()
        state["fingerprints"] = _safe_json(self._fingerprints)
        self._write_state(state)

    # -- phase execution -------------------------------------------------

    def run(self, context: Any = None) -> dict[str, Any]:
        self._validate_composition()

        self._check_fingerprints()
        state = self.load_state()
        if state.get("status") in {"unavailable", "blocked"}:
            return state
        start_index = PHASES.index(_next_phase(state))
        for phase in PHASES[start_index:]:
            result = self.run_phase(phase, context=context)
            if result.status != "completed":
                return self.load_state()
        return self.load_state()

    resume = run

    def _validate_composition(self) -> None:
        handlers = self._handlers
        if isinstance(handlers, Mapping):
            valid = set(handlers) == set(PHASES) and all(
                callable(handlers[phase]) for phase in PHASES
            )
        elif isinstance(handlers, Sequence):
            valid = len(handlers) == len(PHASES) and all(
                callable(handler) for handler in handlers
            )
        else:
            valid = False
        if not valid:
            raise WorkflowError(
                "workflow composition must define callable P0-P7 handlers"
            )


    def run_phase(self, phase: str, handler: PhaseHandler | None = None, *, context: Any = None) -> PhaseResult:
        if phase not in PHASES:
            raise ValueError(f"unknown phase: {phase}")
        state = self.load_state()
        completed = _completed_phase(state)
        if completed in PHASES and PHASES.index(completed) >= PHASES.index(phase):
            return PhaseResult(phase, "completed", int(state.get("attempts", {}).get(phase, 0) or 0))
        attempts = dict(state.get("attempts", {}))
        attempt = int(attempts.get(phase, 0) or 0)
        callback = handler or self._handler_for(phase)
        while attempt < self.max_attempts:
            attempt += 1
            attempts[phase] = attempt
            state["attempts"] = attempts
            state["phase"] = phase
            state["status"] = "active"
            self._write_state(state)
            attempt_dir = self.root / ".anomaly" / "attempts" / phase / f"attempt-{attempt}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            attempt_path = _relative(self.root, attempt_dir)
            self.append_event(
                "phase_started",
                phase=phase,
                attempt=attempt,
                attempt_path=attempt_path,
            )
            try:
                output = _call_handler(callback, self.root, attempt_dir, context)
                _write_output(attempt_dir, output)
            except Exception as error:  # phase failures are durable, not swallowed
                message = _safe_error(str(error))
                failure = {
                    "attempt": attempt,
                    "attempt_path": attempt_path,
                    "error": message,
                }
                (attempt_dir / "failure.json").write_text(
                    json.dumps(failure, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.append_event(
                    "phase_failed",
                    phase=phase,
                    attempt=attempt,
                    attempt_path=attempt_path,
                    error=message,
                )
                state = self.load_state()
                state.setdefault("failures", {}).setdefault(phase, []).append(failure)
                state["attempts"] = attempts
                if attempt < self.max_attempts:
                    self._write_state(state)
                    self.append_event(
                        "phase_retry",
                        phase=phase,
                        attempt=attempt,
                        next_attempt=attempt + 1,
                    )
                    continue
                state["phase"] = phase
                state["status"] = "unavailable"
                state["blocked"] = True
                state["blocked_reason"] = message
                self._write_state(state)
                self.append_event(
                    "phase_unavailable",
                    phase=phase,
                    attempt=attempt,
                    attempt_path=attempt_path,
                    error=message,
                )
                return PhaseResult(phase, "unavailable", attempt, error=message)
            state = self.load_state()
            state["phase"] = phase
            state["last_completed_phase"] = phase
            state.setdefault("completed", {})[phase] = {
                "attempt": attempt,
                "attempt_path": attempt_path,
            }
            state["attempts"] = attempts
            state["status"] = "complete" if phase == "P7" else "active"
            if phase == "P4":
                state["gate"] = "A"
            elif phase == "P7":
                state["gate"] = "B"
            if state.get("invalidated_from") == phase:
                state.pop("invalidated_from", None)
            _capture_identities(self.root, state, phase)
            self._write_state(state)
            self.append_event(
                "phase_completed",
                phase=phase,
                attempt=attempt,
                attempt_path=attempt_path,
            )
            return PhaseResult(phase, "completed", attempt, output)
        return PhaseResult(phase, "unavailable", attempt, error="retry limit reached")

    execute_phase = run_phase

    def _handler_for(self, phase: str) -> PhaseHandler:
        if isinstance(self._handlers, Mapping):
            callback = self._handlers.get(phase)
        elif isinstance(self._handlers, Sequence):
            index = PHASES.index(phase)
            callback = self._handlers[index] if index < len(self._handlers) else None
        elif self._handlers is None and phase == "P0":
            return self._initialize_durable_execution
        else:
            callback = None
        if not callable(callback):
            raise WorkflowError(f"callable handler is required for {phase}")
        return callback

    def _initialize_durable_execution(self) -> dict[str, str]:
        self._read_state()
        return {"status": "initialized"}


def run_workflow(
    root: Path,
    *,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the installed P0-P7 composition, pausing for explicit human input."""
    from anomaly.product_workflow import run_product_workflow

    return run_product_workflow(root, inputs=inputs)


def _completed_phase(state: Mapping[str, Any]) -> str | None:
    value = state.get("last_completed_phase")
    if value in PHASES:
        return value
    completed = state.get("completed")
    if isinstance(completed, Mapping):
        valid = [phase for phase in PHASES if phase in completed]
        if valid:
            return valid[-1]
    return None


def _next_phase(state: Mapping[str, Any]) -> str:
    completed = _completed_phase(state)
    if completed is None:
        return "P0"
    index = PHASES.index(completed)
    if (
        state.get("status") == "active"
        and state.get("phase") == completed
        and not isinstance(state.get("completed"), Mapping)
    ):
        return completed
    if (
        state.get("status") == "active"
        and state.get("phase") == completed
        and completed not in state.get("completed", {})
    ):
        return completed
    return PHASES[index + 1] if index < len(PHASES) - 1 else "P7"



def load_state(root: Path) -> dict[str, Any]:
    return WorkflowRunner(root).load_state()


def read_events(root: Path) -> list[dict[str, Any]]:
    return WorkflowRunner(root).events()


def append_event(
    root: Path,
    event: str,
    *,
    phase: str | None = None,
    attempt: int | None = None,
    **fields: Any,
) -> dict[str, Any] | None:
    return WorkflowRunner(root).append_event(event, phase=phase, attempt=attempt, **fields)


def invalidate(root: Path, changed: str | Sequence[str], *, reason: str | None = None) -> dict[str, Any]:
    return WorkflowRunner(root).invalidate(changed, reason=reason)


def _invalidation_phase(field: str) -> str:
    value = field.casefold()
    if any(token in value for token in ("input", "source", "raw", "acquisition")):
        return "P1"
    if any(token in value for token in ("profile", "mapping", "prepare", "schema")):
        return "P2"
    if any(token in value for token in ("detector", "version", "parameter", "plan")):
        return "P3"
    return "P1"


def _capture_identities(root: Path, state: dict[str, Any], through_phase: str) -> None:
    identities = dict(state.get("identities", {}))
    through_index = PHASES.index(through_phase)
    for name, phase in _IDENTITY_PHASES.items():
        if PHASES.index(phase) > through_index:
            continue
        digest = _artifact_identity(root, name)
        if digest is not None:
            identities[name] = digest
    state["identities"] = identities


def _artifact_identity(root: Path, name: str) -> str | None:
    if name == "recommendation":
        return _recommendation_identity(root)
    files = _identity_files(root, name)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        relative = _relative(root, path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path.is_symlink() or not path.is_file():
            digest.update(b"unavailable")
        else:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _recommendation_identity(root: Path) -> str | None:
    try:
        plan = json.loads((root / "detectors" / "plan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(plan, dict):
        return None
    payload = {
        key: plan.get(key)
        for key in ("recommended", "parameters", "reasons", "blocked")
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _identity_files(root: Path, name: str) -> list[Path]:
    candidates: list[Path]
    if name == "source":
        candidates = [root / "data" / "sources.json", root / "data" / "raw"]
        receipts = root / ".anomaly" / "receipts"
        if receipts.is_dir():
            candidates.extend(
                path
                for path in receipts.iterdir()
                if path.name not in _NON_SOURCE_RECEIPTS
            )
    else:
        relative = {
            "prepared": ("data/prepared", "data/index.duckdb"),
            "gate_a": ("detectors/plan.json", ".anomaly/receipts/gate-a.json"),
            "detector": ("detectors/used",),
            "draft": ("findings/draft.json",),
            "replay": ("evidence/replay.json", ".anomaly/receipts/replay.json"),
            "review": ("findings/review.json",),
            "gate_b": (".anomaly/receipts/gate-b.json",),
        }[name]
        candidates = [root / path for path in relative]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir() and not candidate.is_symlink():
            files.extend(path for path in candidate.rglob("*") if path.is_file() or path.is_symlink())
        elif candidate.exists() or candidate.is_symlink():
            files.append(candidate)
    return sorted(set(files), key=lambda path: _relative(root, path))


def _call_handler(handler: PhaseHandler, root: Path, attempt_dir: Path, context: Any) -> Any:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return handler(attempt_dir, context)
    parameters = list(signature.parameters.values())
    if any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters):
        return handler(root=root, attempt_dir=attempt_dir, context=context)
    positional = [item for item in parameters if item.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    required = len([item for item in positional if item.default is inspect.Parameter.empty])
    count = len(positional)
    if count == 0:
        return handler()
    if count >= 3 or required >= 3:
        return handler(root, attempt_dir, context)
    if count == 2:
        first = positional[0].name.casefold()
        return handler(root, context) if first in {"root", "case_root"} else handler(attempt_dir, context)
    first = positional[0].name.casefold()
    return handler(root) if first in {"root", "case_root"} else handler(attempt_dir)


def _write_output(attempt_dir: Path, output: Any) -> None:
    payload = {"status": "completed"} if output is None else _safe_json(output)
    (attempt_dir / "result.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _safe_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_error(value: Any) -> str:
    return _SECRET.sub("[redacted]", str(redact_credentials(value)))[:2000]


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
