from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from anomaly.acquire import register_local_source
from anomaly.case import resume_case
from anomaly.detect import execute_detectors
from anomaly.prepare import prepare_sources
from anomaly.profile import profile_prepared
from anomaly.recommend import approve_detector_plan, recommend_detectors
from anomaly.report import generate_charts
from anomaly.review import (
    accept_findings,
    draft_findings,
    record_review,
    replay_signals,
    write_report,
)
from anomaly.semantics import redact_credentials

PHASES: tuple[str, ...] = tuple(f"P{index}" for index in range(8))
MAX_ATTEMPTS = 3
_SECRET = re.compile(r"(?:sk_live_|ghp_|github_pat_)[A-Za-z0-9_]+")
_IDENTITY_PHASES: dict[str, str] = {
    "source": "P1",
    "prepared": "P2",
    "gate_a": "P3",
    "detector": "P4",
    "draft": "P5",
    "replay": "P6",
    "review": "P6",
    "gate_b": "P6",
}
_NON_SOURCE_RECEIPTS = {"charts.json", "gate-a.json", "gate-b.json", "replay.json"}
_PUBLIC_INPUTS = frozenset({"now", "sources", "gate_a", "review", "gate_b"})
_SOURCE_INPUTS = frozenset(
    {
        "path",
        "source_id",
        "license",
        "sensitivity",
        "redistribution",
        "reacquisition",
        "included",
        "reason",
    }
)


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
        if start_index <= PHASES.index("P3"):
            state.pop("gate", None)
        elif start_index <= PHASES.index("P6") and state.get("gate") == "B":
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
            if phase == "P3":
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
        if self._handlers is None:
            return lambda: None
        if isinstance(self._handlers, Mapping):
            callback = self._handlers.get(phase)
        else:
            index = PHASES.index(phase)
            callback = self._handlers[index] if index < len(self._handlers) else None
        return callback if callable(callback) else (lambda: None)


def run_workflow(
    root: Path,
    *,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the installed P0-P7 composition, pausing for explicit human input."""
    supplied = _public_inputs(inputs)
    runner = WorkflowRunner(root, handlers=_production_handlers(supplied))
    while True:
        state = runner.load_state()
        if state.get("status") in {"unavailable", "blocked"}:
            return state
        if _completed_phase(state) == "P7":
            return state
        phase = _next_phase(state)
        if phase == "P3":
            _ensure_recommendation(runner.root, supplied)
        awaiting_input = _awaiting_input(runner.root, phase, supplied)
        if awaiting_input is not None:
            return runner.pause(awaiting_input, phase=phase)
        runner.continue_after_pause()
        result = runner.run_phase(phase, context=supplied)
        if result.status != "completed":
            return runner.load_state()


Workflow = WorkflowRunner
DurableWorkflow = WorkflowRunner


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


def _public_inputs(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("workflow inputs must be a mapping")
    supplied = dict(value)
    if any(not isinstance(key, str) for key in supplied):
        raise ValueError("workflow input names must be strings")
    unknown = sorted(set(supplied) - _PUBLIC_INPUTS)
    if unknown:
        raise ValueError(f"unknown workflow inputs: {', '.join(unknown)}")
    return supplied


def _awaiting_input(root: Path, phase: str, inputs: Mapping[str, Any]) -> str | None:
    if phase == "P1" and "sources" not in inputs and not _has_registered_sources(root):
        return "sources"
    if phase == "P3" and "gate_a" not in inputs:
        return "gate_a"
    if phase == "P6" and "review" not in inputs:
        return "review"
    if phase == "P7" and "gate_b" not in inputs:
        return "gate_b"
    return None


def _production_handlers(inputs: Mapping[str, Any]) -> dict[str, PhaseHandler]:
    def register_sources(root: Path) -> list[dict[str, Any]]:
        if "sources" not in inputs:
            return _registered_sources(root)
        now = _input_time(inputs)
        registered: list[dict[str, Any]] = []
        for request in _source_requests(inputs["sources"]):
            registered.append(
                register_local_source(
                    root,
                    request["path"],
                    source_id=request["source_id"],
                    now=now,
                    license=request["license"],
                    sensitivity=request["sensitivity"],
                    redistribution=request["redistribution"],
                    reacquisition=request["reacquisition"],
                    included=request["included"],
                    reason=request.get("reason"),
                )
            )
        return registered

    def prepare_and_profile(root: Path) -> dict[str, Any]:
        now = _input_time(inputs)
        prepared = prepare_sources(root, now=now)
        profile = profile_prepared(root, now=now)
        return {"prepared": prepared, "profile": profile}

    def approve_gate_a(root: Path) -> dict[str, Any]:
        gate = _mapping_input(inputs, "gate_a", {"approved_ids", "approved_by"})
        return approve_detector_plan(
            root,
            gate["approved_ids"],
            approved_by=gate["approved_by"],
            now=_input_time(inputs),
        )

    def run_detectors(root: Path) -> list[dict[str, Any]]:
        plan = _read_case_json(root, "detectors/plan.json")
        approved = plan.get("approved") if isinstance(plan, dict) else None
        if not isinstance(approved, list) or not approved:
            raise WorkflowError("Gate A must approve at least one detector")
        return execute_detectors(root, approved, now=_input_time(inputs))

    def replay_and_review(root: Path) -> dict[str, Any]:
        review_input = _mapping_input(
            inputs,
            "review",
            {
                "reviewer_id",
                "verdicts",
                "independent_attestation",
                "unavailable_inputs",
                "replay_gaps",
                "unresolved_questions",
                "alternatives",
                "reviewer_context",
            },
        )
        reviewer_id = _required_identity(review_input.get("reviewer_id"), "reviewer_id")
        gate_a_approver = _artifact_identity_field(
            root,
            ".anomaly/receipts/gate-a.json",
            "approved_by",
        )
        if _same_identity(reviewer_id, gate_a_approver):
            raise WorkflowError("independent reviewer must differ from the Gate A journalist")
        replay = replay_signals(root)
        if replay.get("status") != "replayed":
            raise WorkflowError(str(replay.get("reason") or "replay is unavailable"))
        review = record_review(root, **review_input)
        if review.get("status") != "recorded" or review.get("independent") is not True:
            raise WorkflowError("independent review is unavailable")
        return {"replay": replay, "review": review}

    def close_gate_b_and_report(root: Path) -> dict[str, Any]:
        gate = _mapping_input(
            inputs,
            "gate_b",
            {"accepted_claim_ids", "journalist_id"},
        )
        journalist_id = _required_identity(gate.get("journalist_id"), "journalist_id")
        reviewer_id = _artifact_identity_field(
            root,
            "findings/review.json",
            "reviewer_id",
        )
        if _same_identity(journalist_id, reviewer_id):
            raise WorkflowError("Gate B journalist must differ from the independent reviewer")
        findings = accept_findings(
            root,
            gate["accepted_claim_ids"],
            journalist_id=journalist_id,
        )
        report = write_report(root)
        charts = generate_charts(root)
        return {"findings": findings, "report": report, "charts": charts}

    handlers: dict[str, PhaseHandler] = {
        "P0": resume_case,
        "P1": register_sources,
        "P2": prepare_and_profile,
        "P3": approve_gate_a,
        "P4": run_detectors,
        "P5": draft_findings,
        "P6": replay_and_review,
        "P7": close_gate_b_and_report,
    }
    if tuple(handlers) != PHASES or any(
        not callable(handler) for handler in handlers.values()
    ):
        raise WorkflowError(
            "production workflow wiring must define exact P0-P7 handlers"
        )
    return handlers


def _ensure_recommendation(root: Path, inputs: Mapping[str, Any]) -> None:
    path = root / "detectors" / "plan.json"
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        plan = None
    if (
        isinstance(plan, dict)
        and isinstance(plan.get("recommended"), list)
        and plan["recommended"]
    ):
        return
    recommend_detectors(root, now=_input_time(inputs))


def _input_time(inputs: Mapping[str, Any]) -> datetime:
    value = inputs.get("now")
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("now must be an explicit timezone-aware datetime")
    return value


def _source_requests(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("sources must be a non-empty list")
    requests: list[dict[str, Any]] = []
    required = _SOURCE_INPUTS - {"reason"}
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("each source input must be a mapping")
        request = dict(item)
        if set(request) - _SOURCE_INPUTS or not required.issubset(request):
            raise ValueError("source input has missing or unknown fields")
        requests.append(request)
    return requests


def _mapping_input(
    inputs: Mapping[str, Any],
    name: str,
    allowed: set[str],
) -> dict[str, Any]:
    value = inputs.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} input must be a mapping")
    result = dict(value)
    if set(result) - allowed:
        raise ValueError(f"{name} input has unknown fields")
    return result


def _registered_sources(root: Path) -> list[dict[str, Any]]:
    value = _read_case_json(root, "data/sources.json")
    if not isinstance(value, list) or not value or any(not isinstance(item, dict) for item in value):
        raise WorkflowError("at least one registered source is required")
    return value


def _has_registered_sources(root: Path) -> bool:
    try:
        value = json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def _artifact_identity_field(root: Path, relative: str, field: str) -> str:
    value = _read_case_json(root, relative)
    if not isinstance(value, dict):
        raise WorkflowError(f"invalid workflow artifact: {relative}")
    return _required_identity(value.get(field), field)


def _required_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty identity")
    return value.strip()


def _same_identity(left: str, right: str) -> bool:
    return left.casefold() == right.casefold()


def _read_case_json(root: Path, relative: str) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowError(f"invalid or missing workflow artifact: {relative}") from error


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
