"""Installed-path orchestration conformance over one deterministic demo case."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from anomaly.acquire import register_local_source
from anomaly.case import create_case
from anomaly.detect import execute_detectors
from anomaly.prepare import prepare_sources
from anomaly.profile import profile_prepared
from anomaly.recommend import approve_detector_plan, recommend_detectors
from anomaly.report import generate_charts
from anomaly.review import (
    _hash_json,
    accept_findings,
    draft_findings,
    record_review,
    replay_signals,
    write_report,
)
from anomaly.workflow import PHASES, WorkflowRunner, run_workflow

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
DEMO_CSV = Path(__file__).parent / "fixtures" / "orchestration_demo.csv"


def _review_input(root: Path) -> dict[str, Any]:
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    claim_ids = [claim["claim_id"] for claim in draft["claims"]]
    assert claim_ids
    reviewer = "reviewer-007"
    return {
        "reviewer_id": reviewer,
        "verdicts": {
            claim_ids[0]: {
                "verdict": "accepted",
                "notes": "replay and wording hold",
            }
        },
        "independent_attestation": {
            "isolated": True,
            "attested_by": reviewer,
            "draft_hash": _hash_json(draft),
            "statement": "Inspected draft, replay, provenance, and previews.",
        },
    }


def _review(root: Path) -> dict[str, Any]:
    return record_review(root, **_review_input(root))


def _source_inputs(source: Path = DEMO_CSV) -> dict[str, Any]:
    return {
        "now": NOW,
        "sources": [
            {
                "path": source,
                "source_id": "payments",
                "license": "internal",
                "sensitivity": "restricted",
                "redistribution": "no",
                "reacquisition": "Copy from the locked newsroom drive.",
                "included": True,
            }
        ],
    }


def _phase_handlers(source: Path = DEMO_CSV) -> dict[str, Callable[..., Any]]:
    def register(root: Path) -> dict[str, Any]:
        return register_local_source(
            root,
            source,
            source_id="payments",
            now=NOW,
            license="internal",
            sensitivity="restricted",
            redistribution="no",
            reacquisition="Copy from the locked newsroom drive.",
            included=True,
        )

    def prepare_and_profile(root: Path) -> dict[str, Any]:
        prepare_sources(root, now=NOW)
        return profile_prepared(root, now=NOW)

    def recommend_and_approve(root: Path) -> dict[str, Any]:
        plan = recommend_detectors(root, now=NOW)
        return approve_detector_plan(
            root,
            plan["recommended"],
            approved_by="journalist",
            now=NOW,
        )

    def detect(root: Path) -> list[dict[str, Any]]:
        plan = json.loads((root / "detectors" / "plan.json").read_text(encoding="utf-8"))
        return execute_detectors(root, plan["approved"], now=NOW)

    def replay_and_review(root: Path) -> dict[str, Any]:
        replay = replay_signals(root)
        assert replay["status"] == "replayed", replay.get("reason")
        return _review(root)

    def accept_and_report(root: Path) -> dict[str, Any]:
        draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
        claim_ids = [claim["claim_id"] for claim in draft["claims"]]
        accept_findings(root, claim_ids[:1], journalist_id="journalist")
        write_report(root)
        return generate_charts(root)

    return {
        "P1": register,
        "P2": prepare_and_profile,
        "P3": recommend_and_approve,
        "P4": detect,
        "P5": draft_findings,
        "P6": replay_and_review,
        "P7": accept_and_report,
    }


def _completed_demo_with_test_handlers(parent: Path) -> Path:
    root = parent / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-walk",
        now=NOW,
    )
    state = WorkflowRunner(root, handlers=_phase_handlers()).run()
    assert state["status"] == "complete"
    return root


def _completed_demo(parent: Path) -> Path:
    root = parent / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-walk",
        now=NOW,
    )

    gate_a_pause = run_workflow(root, inputs=_source_inputs())
    assert gate_a_pause["status"] == "paused"
    assert gate_a_pause["awaiting_input"] == "gate_a"
    assert gate_a_pause["last_completed_phase"] == "P2"
    plan = json.loads((root / "detectors" / "plan.json").read_text(encoding="utf-8"))

    review_pause = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "journalist-42",
            },
        },
    )
    assert review_pause["status"] == "paused"
    assert review_pause["awaiting_input"] == "review"
    assert review_pause["last_completed_phase"] == "P5"

    gate_b_pause = run_workflow(root, inputs={"review": _review_input(root)})
    assert gate_b_pause["status"] == "paused"
    assert gate_b_pause["awaiting_input"] == "gate_b"
    assert gate_b_pause["last_completed_phase"] == "P6"
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    accepted_claim_ids = [draft["claims"][0]["claim_id"]]

    state = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": accepted_claim_ids,
                "journalist_id": "journalist-42",
            }
        },
    )
    assert state["status"] == "complete"
    return root


def _rewrite_json(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _mark(path: Path) -> None:
    _rewrite_json(path, lambda payload: payload.__setitem__("conformance_mutation", True))


def _mutate_source(root: Path) -> None:
    sources = json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))
    source = root / sources[0]["path"]
    source.write_text(source.read_text(encoding="utf-8") + "11,V11,100,20\n", encoding="utf-8")


def _mutate_detector(root: Path) -> None:
    snapshot = sorted((root / "detectors" / "used").glob("*.json"))[0]
    _rewrite_json(
        snapshot,
        lambda payload: payload.__setitem__("implementation_hash", "sha256:" + "0" * 64),
    )


def _mutate_parameters(root: Path) -> None:
    def change(payload: dict[str, Any]) -> None:
        payload["parameters"] = {**payload["parameters"], "conformance_mutation": {}}

    _rewrite_json(root / "detectors" / "plan.json", change)


MUTATIONS: tuple[tuple[str, str, Callable[[Path], None]], ...] = (
    ("source", "P1", _mutate_source),
    ("prepared generation", "P2", lambda root: _mark(root / "data" / "prepared" / "transforms.json")),
    ("detector identity", "P4", _mutate_detector),
    ("detector parameters", "P3", _mutate_parameters),
    ("draft", "P5", lambda root: _mark(root / "findings" / "draft.json")),
    ("replay", "P6", lambda root: _mark(root / "evidence" / "replay.json")),
    ("review", "P6", lambda root: _mark(root / "findings" / "review.json")),
    ("Gate A approval", "P3", lambda root: _mark(root / ".anomaly" / "receipts" / "gate-a.json")),
    ("Gate B approval", "P6", lambda root: _mark(root / ".anomaly" / "receipts" / "gate-b.json")),
)


def test_public_dispatcher_fails_closed_without_required_inputs(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Missing inputs",
        question="Can incomplete wiring complete?",
        case_id="case-missing-inputs",
        now=NOW,
    )

    state = run_workflow(root)

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "sources"
    assert state["last_completed_phase"] == "P0"
    assert not (root / "findings" / "report.md").exists()


def test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    first_state = WorkflowRunner(root).load_state()
    assert first_state["last_completed_phase"] == "P7"
    assert (root / "findings" / "report.md").is_file()
    assert (root / ".anomaly" / "receipts" / "charts.json").is_file()

    resumed = run_workflow(root)
    assert resumed == first_state

    api_events = [
        json.loads(line)
        for line in (root / ".anomaly" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if '"source": "api"' in line
    ]
    names = [event["event"] for event in api_events]
    assert names.index("draft_findings") < names.index("replay_signals")
    assert names.index("replay_signals") < names.index("record_review")
    assert names.index("record_review") < names.index("accept_findings")
    assert names.index("replay_signals") < names.index("accept_findings")


def test_successful_mutation_remains_resumable_when_event_store_is_unavailable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Event failure",
        question="Does durable state survive?",
        case_id="case-event-failure",
        now=NOW,
    )
    runner = WorkflowRunner(root)
    runner.run_phase("P0")
    events = root / ".anomaly" / "events.jsonl"
    events.unlink()
    events.mkdir()

    result = runner.run_phase("P1", _phase_handlers()["P1"])
    assert result.status == "completed"
    assert (root / "data" / "sources.json").is_file()

    repeated: list[str] = []
    fresh = WorkflowRunner(root)
    resumed = fresh.run_phase("P1", lambda: repeated.append("P1"))
    assert resumed.status == "completed"
    assert repeated == []
    assert fresh.load_state()["completed"]["P1"]["attempt_path"] == (
        ".anomaly/attempts/P1/attempt-1"
    )


def test_installed_runner_persists_three_failed_attempts_and_blocks(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Retry failure",
        question="Does bounded convergence stop?",
        case_id="case-retry-failure",
        now=NOW,
    )

    inputs = _source_inputs()
    inputs["sources"][0]["source_id"] = "../unsafe"

    state = run_workflow(root, inputs=inputs)

    assert state["status"] in {"blocked", "unavailable"}
    assert state["attempts"]["P1"] == 3
    failures = state["failures"]["P1"]
    assert [failure["attempt"] for failure in failures] == [1, 2, 3]
    assert [failure["attempt_path"] for failure in failures] == [
        f".anomaly/attempts/P1/attempt-{attempt}" for attempt in (1, 2, 3)
    ]
    assert all(not Path(failure["attempt_path"]).is_absolute() for failure in failures)
    assert all((root / failure["attempt_path"]).is_dir() for failure in failures)


@pytest.mark.parametrize(("change", "expected_phase", "mutate"), MUTATIONS)
def test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase(
    tmp_path: Path,
    change: str,
    expected_phase: str,
    mutate: Callable[[Path], None],
) -> None:
    baseline = _completed_demo_with_test_handlers(tmp_path / "baseline")
    root = tmp_path / change.replace(" ", "-")
    shutil.copytree(baseline, root)
    mutate(root)
    rerun: list[str] = []

    def record(phase: str) -> Callable[[], None]:
        def handler() -> None:
            rerun.append(phase)

        return handler

    runner = WorkflowRunner(root, handlers={phase: record(phase) for phase in PHASES})
    state = runner.load_state()
    start = PHASES.index(expected_phase)
    expected_prefix = list(PHASES[:start])
    expected_suffix = list(PHASES[start:])

    assert state["status"] == "active"
    assert state["invalidated_from"] == expected_phase
    assert list(state["completed"]) == expected_prefix
    assert all(phase not in state["completed"] for phase in expected_suffix)

    resumed = runner.run()

    assert rerun == expected_suffix
    assert list(resumed["completed"]) == list(PHASES)
    assert resumed["status"] == "complete"
