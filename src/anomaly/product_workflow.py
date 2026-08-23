from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from anomaly.acquire import register_local_source
from anomaly.case import _scan_case_tree, resume_case
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
from anomaly.semantics import UnsafeCasePathError, canonical_key
from anomaly.workflow import PHASES, PhaseHandler, WorkflowError, WorkflowRunner, _completed_phase, _next_phase

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


def run_product_workflow(
    root: Path,
    *,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the installed product composition through the durable runner."""
    supplied = _public_inputs(inputs)
    case_root = Path(root)
    _scan_case_tree(case_root)
    case_root = _safe_case_root(case_root)
    resume_case(case_root)
    runner = WorkflowRunner(case_root, handlers=_PRODUCT_HANDLERS)
    while True:
        state = runner.load_state()
        if state.get("status") in {"unavailable", "blocked"} or _completed_phase(state) == "P7":
            return state
        phase = _next_phase(state)
        awaiting_input = _awaiting_input(runner.root, phase, supplied)
        if awaiting_input is not None:
            return runner.pause(awaiting_input, phase=phase)
        runner.continue_after_pause()
        result = runner.run_phase(phase, context=supplied)
        if result.status != "completed":
            return runner.load_state()


def _resume(root: Path, _attempt: Path, _inputs: Mapping[str, Any]) -> Any:
    return resume_case(root)


def _register_sources(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "sources" not in inputs:
        return _registered_sources(root)
    requests = _source_requests(inputs["sources"])
    request_keys = [canonical_key(request["source_id"]) for request in requests]
    if len(request_keys) != len(set(request_keys)):
        raise ValueError("source IDs must be unique after canonicalization")
    existing_keys = {
        canonical_key(record["source_id"])
        for record in _registered_sources(root, required=False)
    }
    registered: list[dict[str, Any]] = []
    for request, request_key in zip(requests, request_keys, strict=True):
        registered.append(
            register_local_source(
                root,
                request["path"],
                source_id=request["source_id"],
                now=_input_time(inputs),
                license=request["license"],
                sensitivity=request["sensitivity"],
                redistribution=request["redistribution"],
                reacquisition=request["reacquisition"],
                included=request["included"],
                reason=request.get("reason"),
                replace_existing=request_key in existing_keys,
            )
        )
    return registered


def _prepare_and_profile(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
    now = _input_time(inputs)
    return {
        "prepared": prepare_sources(root, now=now),
        "profile": profile_prepared(root, now=now),
    }


def _recommend(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
    return recommend_detectors(root, now=_input_time(inputs))


def _approve_and_detect(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
    gate = _mapping_input(inputs, "gate_a", {"approved_ids", "approved_by"})
    approval = approve_detector_plan(
        root,
        gate["approved_ids"],
        approved_by=gate["approved_by"],
        now=_input_time(inputs),
    )
    return {
        "approval": approval,
        "runs": execute_detectors(root, approval["approved"], now=_input_time(inputs)),
    }


def _draft(root: Path, _attempt: Path, _inputs: Mapping[str, Any]) -> dict[str, Any]:
    return draft_findings(root)


def _replay_and_review(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
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
    gate_a_approver = _artifact_identity_field(root, ".anomaly/receipts/gate-a.json", "approved_by")
    if _same_identity(reviewer_id, gate_a_approver):
        raise WorkflowError("independent reviewer must differ from the Gate A journalist")
    replay = replay_signals(root)
    if replay.get("status") != "replayed":
        raise WorkflowError(str(replay.get("reason") or "replay is unavailable"))
    review = record_review(root, **review_input)
    if review.get("status") != "recorded" or review.get("independent") is not True:
        raise WorkflowError("independent review is unavailable")
    return {"replay": replay, "review": review}


def _accept_and_report(root: Path, _attempt: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
    gate = _mapping_input(inputs, "gate_b", {"accepted_claim_ids", "journalist_id"})
    journalist_id = _required_identity(gate.get("journalist_id"), "journalist_id")
    reviewer_id = _artifact_identity_field(root, "findings/review.json", "reviewer_id")
    if _same_identity(journalist_id, reviewer_id):
        raise WorkflowError("Gate B journalist must differ from the independent reviewer")
    findings = accept_findings(root, gate["accepted_claim_ids"], journalist_id=journalist_id)
    report = write_report(root)
    charts = generate_charts(root)
    return {"findings": findings, "report": report, "charts": charts}


_PRODUCT_HANDLERS: dict[str, PhaseHandler] = {
    "P0": _resume,
    "P1": _register_sources,
    "P2": _prepare_and_profile,
    "P3": _recommend,
    "P4": _approve_and_detect,
    "P5": _draft,
    "P6": _replay_and_review,
    "P7": _accept_and_report,
}
assert tuple(_PRODUCT_HANDLERS) == PHASES


def _safe_case_root(root: Path) -> Path:
    case_root = Path(root).resolve()
    durable_root = case_root / ".anomaly"
    if durable_root.is_symlink() or durable_root.resolve() != durable_root:
        raise UnsafeCasePathError(f"unsafe case path: {durable_root}")
    return case_root


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
    if phase == "P1" and "sources" not in inputs and not _registered_sources(root, required=False):
        return "sources"
    if phase == "P4" and "gate_a" not in inputs:
        return "gate_a"
    if phase == "P6" and "review" not in inputs:
        return "review"
    if phase == "P7" and "gate_b" not in inputs:
        return "gate_b"
    return None


def _input_time(inputs: Mapping[str, Any]) -> datetime:
    value = inputs.get("now")
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be an explicit timezone-aware datetime")
    return value


def _source_requests(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("sources must be a non-empty list")
    required = _SOURCE_INPUTS - {"reason"}
    requests: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("each source input must be a mapping")
        request = dict(item)
        if set(request) - _SOURCE_INPUTS or not required.issubset(request):
            raise ValueError("source input has missing or unknown fields")
        requests.append(request)
    return requests


def _mapping_input(inputs: Mapping[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    value = inputs.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} input must be a mapping")
    result = dict(value)
    if set(result) - allowed:
        raise ValueError(f"{name} input has unknown fields")
    return result


def _registered_sources(root: Path, *, required: bool = True) -> list[dict[str, Any]]:
    value = _read_case_json(root, "data/sources.json")
    valid = isinstance(value, list) and all(isinstance(item, dict) for item in value)
    if not valid or (required and not value):
        raise WorkflowError("at least one registered source is required")
    return value


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
