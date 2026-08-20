from __future__ import annotations

from pathlib import Path

import pytest

from anomaly.workflow import MAX_ATTEMPTS, PHASES, RetryLimitExceeded, WorkflowRunner


def test_workflow_records_linear_events_attempts_and_resume(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(attempt_dir: Path) -> dict[str, str]:
        calls.append(attempt_dir.parent.name)
        return {"phase": attempt_dir.parent.name}

    runner = WorkflowRunner(tmp_path, handlers={phase: handler for phase in PHASES})
    state = runner.run()

    assert state["status"] == "complete"
    assert state["last_completed_phase"] == "P7"
    assert calls == list(PHASES)
    events = runner.events()
    assert [event["event"] for event in events].count("phase_started") == 8
    assert [event["event"] for event in events].count("phase_completed") == 8
    for phase in PHASES:
        assert (tmp_path / ".anomaly" / "attempts" / phase / "attempt-1" / "result.json").is_file()


def test_workflow_retries_three_times_then_marks_unavailable(tmp_path: Path) -> None:
    attempts: list[int] = []

    def fail(_attempt_dir: Path) -> None:
        attempts.append(1)
        raise RuntimeError("secret sk_live_TESTONLY must be redacted")

    runner = WorkflowRunner(tmp_path, handlers={"P0": fail})
    result = runner.run_phase("P0")

    assert result.status == "unavailable"
    assert len(attempts) == MAX_ATTEMPTS
    state = runner.load_state()
    assert state["status"] == "unavailable"
    assert "[redacted]" in state["blocked_reason"]
    assert len([event for event in runner.events() if event["event"] == "phase_retry"]) == 2


def test_workflow_resumes_from_next_uncompleted_phase(tmp_path: Path) -> None:
    first_calls: list[str] = []

    def first_handler(attempt_dir: Path) -> None:
        first_calls.append(attempt_dir.parent.name)

    runner = WorkflowRunner(tmp_path, handlers={phase: first_handler for phase in PHASES})
    runner.run_phase("P0")
    runner.run_phase("P1")

    second_calls: list[str] = []

    def second_handler(attempt_dir: Path) -> None:
        second_calls.append(attempt_dir.parent.name)

    resumed = WorkflowRunner(
        tmp_path,
        handlers={phase: second_handler for phase in PHASES},
    ).run()

    assert resumed["status"] == "complete"
    assert first_calls == ["P0", "P1"]
    assert second_calls == list(PHASES[2:])


def test_workflow_fingerprint_change_invalidates_downstream(tmp_path: Path) -> None:
    handlers = {phase: (lambda: None) for phase in PHASES}
    runner = WorkflowRunner(tmp_path, handlers=handlers, input_fingerprint="A")
    runner.run_phase("P0")
    runner.run_phase("P1")
    assert runner.load_state()["last_completed_phase"] == "P1"

    changed = WorkflowRunner(tmp_path, handlers=handlers, input_fingerprint="B")
    state = changed.load_state()

    assert state["phase"] == "P0"
    assert state["last_completed_phase"] == "P0"
    assert state["invalidated_from"] == "P1"
    assert any(event["event"] == "invalidation" for event in changed.events())


def test_workflow_rejects_non_three_attempt_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly three"):
        WorkflowRunner(tmp_path, max_attempts=4)
