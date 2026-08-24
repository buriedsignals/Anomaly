"""Installed-path orchestration conformance over one deterministic demo case."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

import anomaly.workflow as workflow
from anomaly.attempts import run_attempts
from anomaly.case import create_case
from anomaly.review import _hash_json, draft_findings
from anomaly.state import load_snapshot
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


P3_P6_MUTATIONS: tuple[tuple[str, str, Callable[[Path], None]], ...] = (
    ("recommendation", "P3", _mutate_parameters),
    ("Gate A approval", "P4", lambda root: _mark(root / ".anomaly" / "receipts" / "gate-a.json")),
    ("detector identity", "P4", _mutate_detector),
    ("draft", "P5", lambda root: _mark(root / "findings" / "draft.json")),
    ("replay", "P6", lambda root: _mark(root / "evidence" / "replay.json")),
    ("review", "P6", lambda root: _mark(root / "findings" / "review.json")),
)

P7_OUTPUT_MUTATIONS: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("accepted findings", lambda root: _mark(root / "findings" / "findings.json")),
    (
        "report",
        lambda root: (root / "findings" / "report.md").write_text(
            "changed report\n", encoding="utf-8"
        ),
    ),
    (
        "unresolved work",
        lambda root: (root / "findings" / "unresolved.md").write_text(
            "changed unresolved work\n", encoding="utf-8"
        ),
    ),
    ("charts directory", lambda root: shutil.rmtree(root / "findings" / "charts")),
    (
        "charts receipt",
        lambda root: _mark(root / ".anomaly" / "receipts" / "charts.json"),
    ),
)


def _write_interrupted_promotion_marker(
    root: Path,
    *,
    phase: str = "P1",
    **legacy_fields: object,
) -> Path:
    attempt_path = f".anomaly/attempts/{phase}/attempt-1"
    payload = {
        "phase": phase,
        "attempt": 1,
        "attempt_path": attempt_path,
        **legacy_fields,
    }
    marker = root / ".anomaly" / "promotion.json"
    marker.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return marker


def _prepare_interrupted_promotion(root: Path) -> tuple[Path, Path]:
    paused = run_workflow(root)
    assert tuple(paused["completed"]) == ("P0",)

    def mark_interrupted_attempt(state: dict[str, Any]) -> None:
        attempts = dict(state.get("attempts", {}))
        attempts["P1"] = 1
        state.update({"phase": "P1", "status": "active", "attempts": attempts})

    _rewrite_json(root / ".anomaly" / "state.json", mark_interrupted_attempt)
    attempt_dir = root / ".anomaly" / "attempts" / "P1" / "attempt-1"
    workspace = attempt_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "partial.txt").write_text("retain for repair\n", encoding="utf-8")
    return attempt_dir, workspace


def _assert_manual_repair(
    state: dict[str, Any],
    *,
    phase: str = "P1",
    attempt: int = 1,
) -> None:
    workspace = f".anomaly/attempts/{phase}/attempt-{attempt}/workspace"
    reason = state["blocked_reason"]
    assert state["status"] == "blocked"
    assert state["blocked"] is True
    assert state["phase"] == phase
    assert state["attempts"][phase] == attempt
    assert "repair required" in reason.casefold()
    assert phase in reason
    assert f"attempt {attempt}" in reason
    assert workspace in reason


def _assert_no_automatic_rollback_material(root: Path) -> None:
    assert not (root / ".anomaly" / "promotion.json").exists()
    assert list(root.rglob("promotion-backup")) == []




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

def test_missing_now_pauses_before_p1_attempts_are_consumed(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Missing phase clock",
        question="Can a phase run without its explicit clock?",
        case_id="case-missing-now",
        now=NOW,
    )
    inputs = _source_inputs()
    inputs.pop("now")

    state = run_workflow(root, inputs=inputs)

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "now"
    assert tuple(state["completed"]) == ("P0",)
    assert state["attempts"].get("P1") is None

@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_id", ""),
        ("source_id", "../outside"),
        ("path", ""),
        ("path", 7),
        ("license", None),
        ("sensitivity", None),
        ("redistribution", None),
        ("reacquisition", None),
        ("included", "yes"),
        ("included", False),
        ("reason", 7),
    ),
    ids=(
        "blank-source-id",
        "unsafe-source-id",
        "blank-path",
        "non-path",
        "license-type",
        "sensitivity-type",
        "redistribution-type",
        "reacquisition-type",
        "included-type",
        "excluded-without-reason",
        "reason-type",
    ),
)
def test_value_invalid_source_input_pauses_before_an_attempt(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Source input boundary",
        question="Does malformed source input consume an attempt?",
        case_id="case-source-input",
        now=NOW,
    )
    inputs = _source_inputs()
    inputs["sources"][0][field] = value

    state = run_workflow(root, inputs=inputs)

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "sources"
    assert state["attempts"].get("P1") is None


def test_incomplete_gate_a_decision_pauses_without_consuming_an_attempt(
    tmp_path: Path,
) -> None:
    root, _plan = _case_at_gate_a(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {"approved_by": "journalist-42"},
        },
    )

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert tuple(state["completed"])[-1] == "P3"
    assert state["attempts"].get("P4") is None


def test_incomplete_gate_b_decision_pauses_without_consuming_an_attempt(
    tmp_path: Path,
) -> None:
    root = _case_at_gate_b(tmp_path)

    state = run_workflow(
        root,
        inputs={"gate_b": {"journalist_id": "journalist-42"}},
    )

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_b"
    assert tuple(state["completed"])[-1] == "P6"
    assert state["attempts"].get("P7") is None

@pytest.mark.parametrize(
    "approved_ids",
    (
        [],
        [1],
        ["   "],
        ["duplicate", "duplicate"],
        ["unsafe/id"],
        [f"detector-{index}" for index in range(11)],
    ),
    ids=("empty", "non-string", "whitespace", "duplicate", "unsafe", "over-limit"),
)
def test_value_invalid_gate_a_input_pauses_before_an_attempt(
    tmp_path: Path,
    approved_ids: list[object],
) -> None:
    root, _plan = _case_at_gate_a(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": approved_ids,
                "approved_by": "journalist-42",
            },
        },
    )

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert state["attempts"].get("P4") is None


@pytest.mark.parametrize(
    "accepted_claim_ids",
    ([None], ["   "], ["duplicate", "duplicate"]),
    ids=("non-string", "whitespace", "duplicate"),
)
def test_value_invalid_gate_b_input_pauses_before_an_attempt(
    tmp_path: Path,
    accepted_claim_ids: list[object],
) -> None:
    root = _case_at_gate_b(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": accepted_claim_ids,
                "journalist_id": "journalist-42",
            }
        },
    )

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_b"
    assert state["attempts"].get("P7") is None

def test_gate_a_decision_supplied_before_gate_is_not_carried_across_the_turn(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Gate A turn",
        question="Can Gate A be decided before its plan exists?",
        case_id="case-future-gate-a",
        now=NOW,
    )
    inputs = {
        **_source_inputs(),
        "gate_a": {
            "approved_ids": [],
            "approved_by": "journalist-42",
        },
    }

    state = run_workflow(root, inputs=inputs)

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_a"
    assert tuple(state["completed"])[-1] == "P3"
    assert state["attempts"].get("P4") is None
    assert not (root / ".anomaly" / "receipts" / "gate-a.json").exists()


def test_gate_b_decision_supplied_before_review_is_not_carried_across_the_turn(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "journalist-42",
            },
            "gate_b": {
                "accepted_claim_ids": [],
                "journalist_id": "journalist-42",
            },
        },
        invoke=_reasoning_invoker(),
    )

    assert state["status"] == "paused"
    assert state["awaiting_input"] == "gate_b"
    assert tuple(state["completed"])[-1] == "P6"
    assert state["attempts"].get("P7") is None
    assert not (root / ".anomaly" / "receipts" / "gate-b.json").exists()


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
    journalist_outputs = (
        "## Journalist appendix\n\n"
        "This section is newsroom-authored.\n\n"
        "## Outputs\n\n"
        "- [accepted findings](findings/findings.json)\n"
        "- [report](findings/report.md)\n"
        "- [unresolved work](findings/unresolved.md)\n\n"
        "## End journalist appendix\n\n"
        "Keep this text too.\n"
    )
    readme_path = root / "README.md"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8").rstrip() + "\n\n" + journalist_outputs,
        encoding="utf-8",
    )


    resumed = run_workflow(root)
    assert resumed == first_state
    resumed_readme = readme_path.read_text(encoding="utf-8")
    assert journalist_outputs in resumed_readme
    assert resumed_readme.count("## Outputs") == 2

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
    _assert_no_automatic_rollback_material(root)


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


def test_public_dispatcher_persists_three_failed_attempts_and_blocks(
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

    inputs = _source_inputs(tmp_path / "missing.csv")

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


def test_startup_with_an_interrupted_promotion_marker_blocks_for_manual_repair(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Interrupted promotion",
        question="Does startup preserve the case for manual repair?",
        case_id="case-interrupted-promotion",
        now=NOW,
    )
    _attempt_dir, workspace = _prepare_interrupted_promotion(root)
    marker = _write_interrupted_promotion_marker(root)
    protected_paths = (
        root / "README.md",
        root / "data" / "sources.json",
        root / ".anomaly" / "events.jsonl",
    )
    protected = {path: path.read_bytes() for path in protected_paths}
    marker_before = marker.read_bytes()

    blocked = run_workflow(root)

    _assert_manual_repair(blocked)
    assert {path: path.read_bytes() for path in protected_paths} == protected
    assert marker.read_bytes() == marker_before
    assert (workspace / "partial.txt").read_text(encoding="utf-8") == "retain for repair\n"
    assert list(root.rglob("promotion-backup")) == []


@pytest.mark.parametrize(
    "claimed_original",
    (True, False),
    ids=("backup-cannot-authorize-overwrite", "journal-cannot-authorize-deletion"),
)
def test_legacy_journal_fields_and_backups_cannot_authorize_live_mutation(
    tmp_path: Path,
    claimed_original: bool,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Untrusted promotion metadata",
        question="Can legacy recovery material mutate live evidence?",
        case_id=f"case-untrusted-promotion-{claimed_original}",
        now=NOW,
    )
    attempt_dir, workspace = _prepare_interrupted_promotion(root)
    write_paths = (
        "data/sources.json",
        "data/raw",
        ".anomaly/receipts",
        ".anomaly/events.jsonl",
    )
    entries = [
        {
            "path": relative,
            "original": (root / relative).exists(),
            "status": "pending",
        }
        for relative in write_paths
    ]
    entries[0].update({"original": claimed_original, "status": "applied"})
    backup = attempt_dir / "promotion-backup" / "data" / "sources.json"
    if claimed_original:
        backup.parent.mkdir(parents=True)
        backup.write_text('{"attacker": "replacement"}\n', encoding="utf-8")
    marker = _write_interrupted_promotion_marker(
        root,
        schema_version=1,
        status="prepared",
        entries=entries,
    )
    protected_paths = (
        root / "README.md",
        root / "data" / "sources.json",
        root / ".anomaly" / "events.jsonl",
    )
    protected = {path: path.read_bytes() for path in protected_paths}
    marker_before = marker.read_bytes()

    blocked = run_workflow(root)

    _assert_manual_repair(blocked)
    assert {path: path.read_bytes() for path in protected_paths} == protected
    assert marker.read_bytes() == marker_before
    assert (workspace / "partial.txt").read_text(encoding="utf-8") == "retain for repair\n"
    if claimed_original:
        assert backup.read_text(encoding="utf-8") == '{"attacker": "replacement"}\n'
    else:
        assert not backup.exists()


def test_run_attempts_rejects_a_symlinked_case_before_any_durable_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Attempt containment",
        question="Can a direct attempt write through a case symlink?",
        case_id="case-attempt-containment",
        now=NOW,
    )
    run_workflow(root)
    external = tmp_path / "external-anomaly"
    (root / ".anomaly").replace(external)
    (root / ".anomaly").symlink_to(external, target_is_directory=True)
    state_before = (external / "state.json").read_bytes()
    events_before = (external / "events.jsonl").read_bytes()
    executed: list[Path] = []

    with pytest.raises(UnsafeCasePathError):
        run_attempts(
            root,
            "P1",
            lambda workspace: executed.append(workspace),
            writes=(),
        )

    assert executed == []
    assert (external / "state.json").read_bytes() == state_before
    assert (external / "events.jsonl").read_bytes() == events_before



def test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)
    secrets = (
        "abcdefghijklmnop",
        "hunter2",
        "AKIATESTONLY12345678",
        "xoxb-TESTONLY12345678",
        "swordfish",
        "awsSecretValue1234567890abcd",
        "openaiSecretValue1234567890abcd",
    )
    message = (
        f"Authorization: Bearer {secrets[0]} password={secrets[1]} "
        f"aws={secrets[2]} slack={secrets[3]} "
        f"url=https://alice:{secrets[4]}@example.invalid/private "
        f"AWS_SECRET_ACCESS_KEY={secrets[5]} OPENAI_API_KEY={secrets[6]}"
    )

    def fail_reasoning(*, case_root: Path, **_kwargs: Any) -> dict[str, Any]:
        (case_root / "findings" / "draft.json").write_text(
            '{"partial": true}\n',
            encoding="utf-8",
        )
        raise RuntimeError(message)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "journalist-42",
            },
        },
        invoke=fail_reasoning,
    )

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P5"
    assert state["attempts"]["P5"] == 3
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    leaked = [secret for secret in secrets if secret in persisted]
    assert leaked == []
    assert "[redacted]" in persisted
    failures = state["failures"]["P5"]
    assert [failure["attempt"] for failure in failures] == [1, 2, 3]
    assert all((root / failure["attempt_path"] / "failure.json").is_file() for failure in failures)
    assert not (root / "findings" / "draft.json").exists()
    _assert_no_automatic_rollback_material(root)


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

def test_failed_multi_source_attempt_does_not_promote_an_earlier_source(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_case(
        root,
        title="Atomic source batch",
        question="Can one invalid source partially register its batch?",
        case_id="case-atomic-sources",
        now=NOW,
    )
    unsupported = tmp_path / "unsupported.txt"
    unsupported.write_text("not tabular\n", encoding="utf-8")
    inputs = _source_inputs()
    inputs["sources"].append(
        {
            **inputs["sources"][0],
            "path": unsupported,
            "source_id": "unsupported",
        }
    )

    state = run_workflow(root, inputs=inputs)

    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P1"
    assert state["attempts"]["P1"] == 3
    assert json.loads((root / "data" / "sources.json").read_text(encoding="utf-8")) == []
    assert list((root / "data" / "raw").iterdir()) == []
    assert all(
        (root / ".anomaly" / "attempts" / "P1" / f"attempt-{attempt}" / "failure.json").is_file()
        for attempt in (1, 2, 3)
    )
    failures = state["failures"]["P1"]
    assert [failure["attempt"] for failure in failures] == [1, 2, 3]
    assert [failure["attempt_path"] for failure in failures] == [
        f".anomaly/attempts/P1/attempt-{attempt}" for attempt in (1, 2, 3)
    ]
    _assert_no_automatic_rollback_material(root)


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

@pytest.mark.parametrize(("change", "expected_phase", "mutate"), P3_P6_MUTATIONS)
def test_changed_p3_p6_identity_invalidates_only_its_earliest_suffix(
    tmp_path: Path,
    change: str,
    expected_phase: str,
    mutate: Callable[[Path], None],
) -> None:
    root = _completed_demo(tmp_path)
    mutate(root)

    snapshot = load_snapshot(root)

    start = PHASES.index(expected_phase)
    assert snapshot["status"] == "active", change
    assert snapshot["invalidated_from"] == expected_phase
    assert list(snapshot["completed"]) == list(PHASES[:start])
    resolution = workflow.resolve_workflow(snapshot, supplied=frozenset())
    assert resolution["phase"] == expected_phase


def test_completed_snapshot_without_required_identities_fails_closed_from_p1(
    tmp_path: Path,
) -> None:
    root = _completed_demo(tmp_path)
    state_path = root / ".anomaly" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.pop("identities")
    state_path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    snapshot = load_snapshot(root)

    assert snapshot["status"] == "active"
    assert snapshot["invalidated_from"] == "P1"
    assert list(snapshot["completed"]) == ["P0"]
    assert workflow.resolve_workflow(snapshot, supplied=frozenset())["status"] != "complete"


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

def test_public_dispatcher_rejects_canonical_gate_a_approver_as_reviewer(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)

    state = run_workflow(
        root,
        inputs={
            "now": NOW,
            "gate_a": {
                "approved_ids": plan["recommended"],
                "approved_by": "Réviewer",
            },
        },
        invoke=_reasoning_invoker("Re\u0301viewer"),
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

def test_public_dispatcher_rejects_canonical_reviewer_as_gate_b_journalist(
    tmp_path: Path,
) -> None:
    root = _case_at_gate_b(tmp_path, reviewer_id="Re\u0301viewer")
    draft = json.loads((root / "findings" / "draft.json").read_text(encoding="utf-8"))

    state = run_workflow(
        root,
        inputs={
            "gate_b": {
                "accepted_claim_ids": [draft["claims"][0]["claim_id"]],
                "journalist_id": "Réviewer",
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


@pytest.mark.parametrize(("output", "mutate"), P7_OUTPUT_MUTATIONS)
def test_changed_or_missing_p7_output_demotes_completion_and_readme(
    tmp_path: Path,
    output: str,
    mutate: Callable[[Path], None],
) -> None:
    root = _completed_demo(tmp_path)
    mutate(root)

    paused = run_workflow(root)

    assert paused["status"] == "paused", output
    assert paused["awaiting_input"] == "gate_b", output
    assert list(paused["completed"]) == list(PHASES[:7]), output
    assert paused["invalidated_from"] == "P7", output
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Status: active" in readme, output
    assert "Last completed phase: P6" in readme, output
    assert "<!-- anomaly:outputs:start -->" not in readme, output


def test_failed_p7_attempt_does_not_promote_outputs_or_delete_journalist_content(
    tmp_path: Path,
) -> None:
    root = _case_at_gate_b(tmp_path)
    readme_path = root / "README.md"
    journalist_notes = "## Journalist notes\nKeep this newsroom context through failure.\n"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8").rstrip() + "\n\n" + journalist_notes,
        encoding="utf-8",
    )
    charts_path = root / "findings" / "charts"
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

    readme = readme_path.read_text(encoding="utf-8")
    assert state["status"] in {"blocked", "unavailable"}
    assert state["phase"] == "P7"
    assert state["attempts"]["P7"] == 3
    assert "P7" not in state["completed"]
    assert not (root / ".anomaly" / "receipts" / "gate-b.json").exists()
    assert not (root / "findings" / "findings.json").exists()
    assert not (root / "findings" / "report.md").exists()
    assert "Status: complete" not in readme
    assert "Last completed phase: P7" not in readme
    assert journalist_notes in readme


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

def test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns(
    tmp_path: Path,
) -> None:
    root, plan = _case_at_gate_a(tmp_path)
    external = tmp_path / "outside-events.jsonl"
    external.write_text("sentinel\n", encoding="utf-8")

    def introduce_link(
        *,
        owner: dict[str, str],
        instructions: str,
        case_root: Path,
    ) -> dict[str, Any]:
        assert owner == {"kind": "skill", "id": "anomaly"}
        assert "name: anomaly" in instructions
        draft = draft_findings(case_root)
        events = case_root / ".anomaly" / "events.jsonl"
        events.unlink()
        events.symlink_to(external)
        return draft

    with pytest.raises(UnsafeCasePathError, match=r"(?i)(symlink|case path)"):
        run_workflow(
            root,
            inputs={
                "now": NOW,
                "gate_a": {
                    "approved_ids": plan["recommended"],
                    "approved_by": "journalist-42",
                },
            },
            invoke=introduce_link,
        )

    assert external.read_text(encoding="utf-8") == "sentinel\n"
    assert not (root / "findings" / "draft.json").exists()


