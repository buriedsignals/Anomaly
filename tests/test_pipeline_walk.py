"""Installed-path orchestration conformance over one deterministic demo case."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

import anomaly.workflow as workflow
from anomaly.case import create_case
from anomaly.review import _hash_json, draft_findings
from anomaly.semantics import UnsafeCasePathError
from anomaly.workflow import PHASES, run_workflow

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
DEMO_CSV = Path(__file__).parent / "fixtures" / "orchestration_demo.csv"


def _review_input(
    root: Path,
    reviewer_id: str = "reviewer-007",
) -> dict[str, Any]:
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    claim_ids = [claim["claim_id"] for claim in draft["claims"]]
    assert claim_ids
    reviewer = reviewer_id
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


def _reasoning_invoker(
    reviewer_id: str = "reviewer-007",
    observed: list[dict[str, str]] | None = None,
) -> Callable[..., dict[str, Any]]:
    def invoke(
        *,
        owner: dict[str, str],
        instructions: str,
        case_root: Path,
    ) -> dict[str, Any]:
        if observed is not None:
            observed.append(owner)
        if owner == {"kind": "skill", "id": "anomaly"}:
            assert "name: anomaly" in instructions
            return draft_findings(case_root)
        if owner == {"kind": "persona", "id": "anomaly-data-reviewer"}:
            assert "name: anomaly-data-reviewer" in instructions
            return _review_input(case_root, reviewer_id)
        raise AssertionError(f"unexpected reasoning owner: {owner}")

    return invoke




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




def _case_at_gate_a(parent: Path) -> tuple[Path, dict[str, Any]]:
    root = parent / "case"
    create_case(
        root,
        title="Payments review",
        question="Which payments need review?",
        case_id="case-walk",
        now=NOW,
    )
    state = run_workflow(root, inputs=_source_inputs())
    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    plan = json.loads((root / "detectors" / "plan.json").read_text(encoding="utf-8"))
    return root, plan




def _case_at_gate_b(
    parent: Path,
    *,
    approved_by: str = "journalist-42",
    reviewer_id: str = "reviewer-007",
    observed: list[dict[str, str]] | None = None,
) -> Path:
    root, plan = _case_at_gate_a(parent)
    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": approved_by,
            },
        },
        invoke=_reasoning_invoker(reviewer_id, observed),
    )
    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_b"
    assert tuple(state["completed"])[-1] == "P6"
    return root


def _completed_demo(
    parent: Path,
    observed: list[dict[str, str]] | None = None,
) -> Path:
    root = _case_at_gate_b(parent, observed=observed)
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
    assert tuple(state["completed"]) == ("P0",)
    assert not (root / "findings" / "report.md").exists()


def test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work(
    tmp_path: Path,
) -> None:
    observed: list[dict[str, str]] = []
    root = _completed_demo(tmp_path, observed)
    first_state = json.loads(
        (root / ".anomaly" / "state.json").read_text(encoding="utf-8")
    )
    first_resolution = workflow.resolve_workflow(first_state, supplied=frozenset())
    assert first_resolution["phase"] == "P7"
    assert first_resolution["status"] == "complete"
    assert first_resolution["owner"] is None
    assert observed == [
        {"kind": "skill", "id": "anomaly"},
        {"kind": "persona", "id": "anomaly-data-reviewer"},
    ]
    assert (root / "findings" / "report.md").is_file()
    assert (root / ".anomaly" / "receipts" / "charts.json").is_file()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Status: complete" in readme
    assert "Last completed phase: P7" in readme
    for relative in (
        "findings/findings.json",
        "findings/report.md",
        "findings/unresolved.md",
    ):
        assert f"]({relative})" in readme
        target = Path(relative)
        assert not target.is_absolute()
        resolved = (root / target).resolve()
        assert resolved.is_relative_to(root.resolve())
        assert resolved.is_file()

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
    events = root / ".anomaly" / "events.jsonl"
    events.unlink()
    events.mkdir()

    state = run_workflow(root, inputs=_source_inputs())

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert (root / "data" / "sources.json").is_file()
    attempt_path = state["completed"]["P1"]["attempt_path"]
    assert attempt_path == ".anomaly/attempts/P1/attempt-1"

    resumed = run_workflow(root)

    assert resumed["status"] == "paused"
    assert resumed["awaiting_input"] == "gate_a"
    assert resumed["completed"]["P1"]["attempt_path"] == attempt_path


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


def test_public_dispatcher_rejects_duplicate_source_batch_before_registration(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Duplicate source batch",
        question="Can canonical source IDs collide?",
        case_id="case-duplicate-sources",
        now=NOW,
    )
    duplicate = tmp_path / "duplicate.csv"
    shutil.copyfile(DEMO_CSV, duplicate)
    inputs = _source_inputs()
    inputs["sources"].append(
        {
            **inputs["sources"][0],
            "path": duplicate,
            "source_id": "PAYMENTS",
        }
    )

    state = run_workflow(root, inputs=inputs)

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P1"
    assert state["attempts"]["P1"] == 3
    assert json.loads((root / "data" / "sources.json").read_text(encoding="utf-8")) == []
    assert list((root / "data" / "raw").iterdir()) == []


def test_public_dispatcher_retries_recommendation_failure_inside_p3(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)
    plan_path = root / "detectors" / "plan.json"
    plan_path.unlink()
    plan_path.mkdir()

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "journalist-42",
            },
        },
    )

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P3"
    assert state["attempts"]["P3"] == 3
    failures = state["failures"]["P3"]
    assert [failure["attempt"] for failure in failures] == [1, 2, 3]
    assert all((root / failure["attempt_path"]).is_dir() for failure in failures)


def test_public_dispatcher_rebuilds_stale_plan_after_prepared_change(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    completed_plan = json.loads(
        (root / "detectors" / "plan.json").read_text(encoding="utf-8")
    )
    assert completed_plan["approved"]
    _mark(root / "data" / "prepared" / "transforms.json")

    state = run_workflow(root, inputs={"now": NOW})

    rebuilt_plan = json.loads(
        (root / "detectors" / "plan.json").read_text(encoding="utf-8")
    )
    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert tuple(state["completed"])[-1] == "P3"
    assert rebuilt_plan["recommended"]
    assert rebuilt_plan["approved"] == []


def test_public_dispatcher_replaces_changed_registered_source(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    sources_path = root / "data" / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    registered_source = root / sources[0]["path"]
    registered_source.write_text(
        registered_source.read_text(encoding="utf-8") + "11,V11,100,20\n",
        encoding="utf-8",
    )

    state = run_workflow(root, inputs=_source_inputs())

    replaced_sources = json.loads(sources_path.read_text(encoding="utf-8"))
    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert tuple(state["completed"])[-1] == "P3"
    assert len(replaced_sources) == 1
    assert registered_source.read_bytes() == DEMO_CSV.read_bytes()


def test_public_dispatcher_rejects_gate_a_approver_as_reviewer(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "reviewer-007",
            },
        },
        invoke=_reasoning_invoker("reviewer-007"),
    )

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P6"
    assert "must differ" in state["blocked_reason"]
    assert not (root / "findings" / "review.json").exists()


def test_public_dispatcher_rejects_reviewer_as_gate_b_journalist(
    tmp_path: Path,
) -> None:
    root = _case_at_gate_b(tmp_path, reviewer_id="reviewer-007")
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))

    state = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": [draft["claims"][0]["claim_id"]],
                "journalist_id": "reviewer-007",
            }
        },
    )

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P7"
    assert "must differ" in state["blocked_reason"]
    assert not (root / ".anomaly" / "receipts" / "gate-b.json").exists()


def test_public_dispatcher_invalidates_changed_gate_b_from_p7(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    review_path = root / "findings" / "review.json"
    replay_path = root / "evidence" / "replay.json"
    preserved = (review_path.read_bytes(), replay_path.read_bytes())
    readme_path = root / "README.md"
    journalist_notes = "## Journalist notes\nKeep this newsroom context.\n"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8").rstrip()
        + "\n\n"
        + journalist_notes,
        encoding="utf-8",
    )
    _mark(root / ".anomaly" / "receipts" / "gate-b.json")

    paused = run_workflow(root)

    assert paused["status"] == "paused"
    assert paused["awaiting_input"] == "gate_b"
    assert list(paused["completed"]) == list(PHASES[:7])
    assert (review_path.read_bytes(), replay_path.read_bytes()) == preserved
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Status: active" in readme
    assert "Last completed phase: P6" in readme
    assert journalist_notes in readme

    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))
    resumed = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": [draft["claims"][0]["claim_id"]],
                "journalist_id": "journalist-42",
            }
        },
    )
    assert resumed["status"] == "complete"
    assert (review_path.read_bytes(), replay_path.read_bytes()) == preserved
    assert journalist_notes in readme_path.read_text(encoding="utf-8")


def test_readme_does_not_claim_completion_when_chart_generation_fails(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    _mark(root / ".anomaly" / "receipts" / "gate-b.json")
    paused = run_workflow(root)
    assert paused["status"] == "paused"
    charts_path = root / "findings" / "charts"
    shutil.rmtree(charts_path)
    charts_path.write_text("not a directory\n", encoding="utf-8")
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))

    state = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": [draft["claims"][0]["claim_id"]],
                "journalist_id": "journalist-42",
            }
        },
    )

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P7"
    assert state["attempts"]["P7"] == 3
    assert "Status: complete" not in readme
    assert "Last completed phase: P7" not in readme


def test_public_dispatcher_rejects_nested_case_symlink_before_durable_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Containment",
        question="Can a case-controlled link be read?",
        case_id="case-nested-containment",
        now=NOW,
    )
    external = tmp_path / "external-sources.json"
    external.write_text('[{"source_id": "external"}]\n', encoding="utf-8")
    sources_path = root / "data" / "sources.json"
    sources_path.unlink()
    sources_path.symlink_to(external)

    with pytest.raises(UnsafeCasePathError, match=r"(?i)(symlink|case path)"):
        run_workflow(root)

    assert list((root / ".anomaly" / "attempts").iterdir()) == []


def test_public_dispatcher_rejects_anomaly_symlink_before_durable_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Containment",
        question="Can durable writes escape?",
        case_id="case-containment",
        now=NOW,
    )
    shutil.rmtree(root / ".anomaly")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".anomaly").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeCasePathError, match=r"(?i)(symlink|case path)"):
        run_workflow(root)

    assert list(outside.iterdir()) == []


