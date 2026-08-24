from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import anomaly.workflow as workflow



def test_resolver_is_pure_and_reports_durable_resume_detail() -> None:
    snapshot = {
        "phase": "P2",
        "status": "active",
        "completed": {"P0": {}, "P1": {}, "P2": {}},
        "attempts": {"P3": 2},
        "invalidated_from": "P3",
    }
    original = copy.deepcopy(snapshot)
    resolve = getattr(workflow, "resolve_workflow", None)

    assert callable(resolve), "workflow must expose the pure durable resolver"
    resolution = resolve(snapshot, supplied=frozenset({"now"}))

    assert snapshot == original
    assert resolution == {
        "phase": "P3",
        "status": "ready",
        "owner": {"kind": "handler", "id": "recommend-detectors"},
        "missing": None,
        "attempts": 2,
        "invalidated_from": "P3",
        "resume": "Resume P3 after P2; attempt 3 of 3.",
    }

@pytest.mark.parametrize(
    ("completed", "supplied", "expected_phase", "expected_missing"),
    [
        ({"P0": {}}, frozenset({"sources"}), "P1", "now"),
        ({"P0": {}, "P1": {}}, frozenset(), "P2", "now"),
        ({"P0": {}, "P1": {}, "P2": {}}, frozenset(), "P3", "now"),
        (
            {"P0": {}, "P1": {}, "P2": {}, "P3": {}},
            frozenset({"now"}),
            "P4",
            "gate_a",
        ),
        (
            {"P0": {}, "P1": {}, "P2": {}, "P3": {}, "P4": {}, "P5": {}, "P6": {}},
            frozenset(),
            "P7",
            "gate_b",
        ),
    ],
)
def test_resolver_reports_incomplete_phase_input_before_attempt(
    completed: dict[str, Any],
    supplied: frozenset[str],
    expected_phase: str,
    expected_missing: str,
) -> None:
    snapshot = {
        "phase": tuple(completed)[-1],
        "status": "active",
        "completed": completed,
        "attempts": {},
    }
    original = copy.deepcopy(snapshot)

    resolution = workflow.resolve_workflow(snapshot, supplied=supplied)

    assert snapshot == original
    assert resolution["phase"] == expected_phase
    assert resolution["status"] == "paused"
    assert resolution["owner"] is None
    assert resolution["missing"] == expected_missing
    assert resolution["attempts"] == 0


@pytest.mark.parametrize(
    ("completed", "expected_owner", "marker"),
    [
        (
            {"P0": {}, "P1": {}, "P2": {}, "P3": {}, "P4": {}},
            {"kind": "skill", "id": "anomaly"},
            "name: anomaly",
        ),
        (
            {"P0": {}, "P1": {}, "P2": {}, "P3": {}, "P4": {}, "P5": {}},
            {"kind": "persona", "id": "anomaly-data-reviewer"},
            "name: anomaly-data-reviewer",
        ),
    ],
)
def test_resolved_reasoning_owner_is_loaded_and_invoked_once(
    tmp_path: Path,
    completed: dict[str, Any],
    expected_owner: dict[str, str],
    marker: str,
) -> None:
    resolve = getattr(workflow, "resolve_workflow", None)
    invoke_owner = getattr(workflow, "invoke_resolved_owner", None)
    assert callable(resolve), "workflow must expose the pure durable resolver"
    assert callable(invoke_owner), "workflow must expose one owner invocation boundary"
    resolution = resolve(
        {"phase": tuple(completed)[-1], "status": "active", "completed": completed},
        supplied=frozenset(),
    )
    observed: list[tuple[dict[str, str], Path]] = []

    def invoke(*, owner: dict[str, str], instructions: str, case_root: Path) -> dict[str, str]:
        assert marker in instructions
        observed.append((owner, case_root))
        return {"selected": owner["id"]}

    result = invoke_owner(resolution, case_root=tmp_path, invoke=invoke)

    assert resolution["owner"] == expected_owner
    assert observed == [(expected_owner, tmp_path)]
    assert result == {"selected": expected_owner["id"]}
