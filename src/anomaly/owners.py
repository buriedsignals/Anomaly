from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from anomaly.acquire import register_local_source
from anomaly.detect import execute_detectors
from anomaly.prepare import prepare_sources
from anomaly.profile import profile_prepared
from anomaly.recommend import approve_detector_plan, recommend_detectors
from anomaly.report import generate_charts
from anomaly.review import accept_findings, record_review, replay_signals, write_report
from anomaly.semantics import canonical_key
from anomaly.state import WorkflowError
from anomaly.workflow_inputs import (
    gate_a_input,
    gate_b_input,
    input_time,
    read_case_json,
    registered_sources,
    source_requests,
)

ReasoningCall = Callable[[Mapping[str, Any], Path], Any]
_REVIEW_FIELDS = {
    "reviewer_id",
    "verdicts",
    "independent_attestation",
    "attestation",
    "unavailable_inputs",
    "replay_gaps",
    "unresolved_questions",
    "alternatives",
    "reviewer_context",
}


def consume_owner(
    resolution: Mapping[str, Any],
    root: Path,
    inputs: Mapping[str, Any],
    reason: ReasoningCall | None,
) -> Any:
    owner = resolution["owner"]
    if owner["kind"] == "handler":
        return _run_handler(owner["id"], root, inputs)
    if reason is None:
        raise WorkflowError("reasoning owner invocation is unavailable")
    if resolution["phase"] == "P5":
        draft = reason(resolution, root)
        if not isinstance(draft, Mapping) or draft.get("status") != "draft":
            raise WorkflowError("anomaly reasoning owner returned an invalid draft")
        if not (root / "findings" / "draft.json").is_file():
            raise WorkflowError("anomaly reasoning owner did not seal the draft")
        return dict(draft)
    return _replay_and_review(resolution, root, reason)


def _run_handler(owner_id: str, root: Path, inputs: Mapping[str, Any]) -> Any:
    if owner_id == "resume-case":
        from anomaly.case import resume_case

        resume_case(root)
        return {"status": "resumed"}
    if owner_id == "register-sources":
        return _register_sources(root, inputs)
    if owner_id == "prepare-and-profile":
        now = input_time(inputs)
        return {"prepared": prepare_sources(root, now=now), "profile": profile_prepared(root, now=now)}
    if owner_id == "recommend-detectors":
        return recommend_detectors(root, now=input_time(inputs))
    if owner_id == "approve-and-detect":
        gate = gate_a_input(inputs.get("gate_a"))
        now = input_time(inputs)
        approval = approve_detector_plan(root, gate["approved_ids"], approved_by=gate["approved_by"], now=now)
        return {"approval": approval, "runs": execute_detectors(root, approval["approved"], now=now)}
    if owner_id == "accept-and-report":
        return _accept_and_report(root, inputs)
    raise WorkflowError(f"unknown deterministic owner: {owner_id}")


def _register_sources(root: Path, inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "sources" not in inputs:
        return registered_sources(root)
    requests = source_requests(inputs["sources"])
    request_keys = [canonical_key(request["source_id"]) for request in requests]
    if len(request_keys) != len(set(request_keys)):
        raise ValueError("source IDs must be unique after canonicalization")
    existing_keys = {canonical_key(record["source_id"]) for record in registered_sources(root, required=False)}
    now = input_time(inputs)
    registered: list[dict[str, Any]] = []
    for request, request_key in zip(requests, request_keys, strict=True):
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
                replace_existing=request_key in existing_keys,
            )
        )
    return registered


def _replay_and_review(
    resolution: Mapping[str, Any],
    root: Path,
    reason: ReasoningCall,
) -> dict[str, Any]:
    replay = replay_signals(root)
    if replay.get("status") != "replayed":
        raise WorkflowError(str(replay.get("reason") or "replay is unavailable"))
    review_input = _review_owner_result(reason(resolution, root))
    reviewer_id = _required_identity(review_input.get("reviewer_id"), "reviewer_id")
    gate_a_approver = _artifact_identity_field(root, ".anomaly/receipts/gate-a.json", "approved_by")
    if canonical_key(reviewer_id) == canonical_key(gate_a_approver):
        raise WorkflowError("independent reviewer must differ from the Gate A journalist")
    review = record_review(root, **review_input)
    if review.get("status") != "recorded" or review.get("independent") is not True:
        raise WorkflowError("independent review is unavailable")
    return {"replay": replay, "review": review}


def _accept_and_report(root: Path, inputs: Mapping[str, Any]) -> dict[str, Any]:
    gate = gate_b_input(inputs.get("gate_b"))
    journalist_id = _required_identity(gate.get("journalist_id"), "journalist_id")
    reviewer_id = _artifact_identity_field(root, "findings/review.json", "reviewer_id")
    if canonical_key(journalist_id) == canonical_key(reviewer_id):
        raise WorkflowError("Gate B journalist must differ from the independent reviewer")
    findings = accept_findings(root, gate["accepted_claim_ids"], journalist_id=journalist_id)
    return {"findings": findings, "report": write_report(root), "charts": generate_charts(root)}


def _review_owner_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowError("independent reviewer returned no structured review")
    result = dict(value)
    if set(result) - _REVIEW_FIELDS:
        raise WorkflowError("independent reviewer returned unknown fields")
    if "attestation" in result:
        if "independent_attestation" in result:
            raise WorkflowError("independent reviewer returned duplicate attestations")
        result["independent_attestation"] = result.pop("attestation")
    if not isinstance(result.get("verdicts"), Mapping):
        raise WorkflowError("independent reviewer returned invalid verdicts")
    return result


def _artifact_identity_field(root: Path, relative: str, field: str) -> str:
    value = read_case_json(root, relative)
    if not isinstance(value, dict):
        raise WorkflowError(f"invalid workflow artifact: {relative}")
    return _required_identity(value.get(field), field)


def _required_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty identity")
    return value.strip()
