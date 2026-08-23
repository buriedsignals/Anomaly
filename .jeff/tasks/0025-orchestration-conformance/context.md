# Context

## Relevant paths and symbols

- `.jeff/tasks/0025-orchestration-conformance/task.md:7` — locked acceptance criteria.
- `.jeff/tasks/0025-orchestration-conformance/review-correctness.json:14` — first blocking review findings.
- `.jeff/tasks/0025-orchestration-conformance/review-maintainability.json:14` — second blocking review findings.
- `.jeff/tasks/0025-orchestration-conformance/refute-*.json:1` — nine source-bound refute records with `survives` verdicts.
- `src/anomaly/workflow.py:14` — canonical `PHASES` tuple P0–P7.
- `src/anomaly/workflow.py:50` — `WorkflowRunner`, durable state/events/attempt execution owner.
- `src/anomaly/workflow.py:137` — `WorkflowRunner.load_state`, identity reconciliation entry.
- `src/anomaly/workflow.py:189` — best-effort `WorkflowRunner.append_event`.
- `src/anomaly/workflow.py:227` — downstream completion/attempt/failure/identity deletion in `_invalidate_state`.
- `src/anomaly/workflow.py:295` — linear `WorkflowRunner.run`.
- `src/anomaly/workflow.py:309` — retry and completion bookkeeping in `WorkflowRunner.run_phase`.
- `src/anomaly/workflow.py:405` — `_handler_for`, optional injected-handler lookup.
- `src/anomaly/workflow.py:416` — public `run_workflow`.
- `src/anomaly/recommend.py:334` — `approve_detector_plan`, plan and Gate A receipt API.
- `src/anomaly/recommend.py:380` — current Gate A state read/write block.
- `src/anomaly/review.py:369` — `accept_findings`, findings and Gate B receipt API.
- `src/anomaly/review.py:475` — current Gate B state write block.
- `src/anomaly/review.py:598` — `write_report`, report and README API.
- `src/anomaly/review.py:661` — current report state write block.
- `src/anomaly/events.py:24` — best-effort API event append.
- `src/anomaly/events.py:51` — API phase-event decorator.
- `PRD.md:205` — `.anomaly/` storage roles and restart wording.
- `PRD.md:218` — canonical P5 draft → P6 replay/review → Gate B order.
- `skills/anomaly/SKILL.md:39` — installed state/receipt/event/attempt role wording.
- `skills/anomaly/SKILL.md:64` — installed dispatch table.
- `tests/test_pipeline_walk.py:34` — explicit independent-review input builder.
- `tests/test_pipeline_walk.py:60` — explicit source registration input builder.
- `tests/test_pipeline_walk.py:145` — staged public-dispatch demo helper.
- `tests/test_pipeline_walk.py:226` — nine-entry mutation matrix.
- `tests/test_pipeline_walk.py:239` — public no-input fail-closed contract.
- `tests/test_pipeline_walk.py:257` — checked-in CSV public pause/resume and fresh-session contract.
- `tests/test_pipeline_walk.py:281` — event-store failure/resume contract.
- `tests/test_pipeline_walk.py:312` — installed public retry contract.
- `tests/test_pipeline_walk.py:341` — full downstream deletion and exact-suffix rerun contract.
- `tests/test_recommend.py:230` — Gate A artifact/receipt-only state contract.
- `tests/test_review.py:304` — Gate B artifact/receipt-only state contract.
- `tests/test_review.py:393` — report artifact contract with unchanged workflow state.
- `tests/fixtures/orchestration_demo.csv:1` — deterministic ten-row demo input.

## Targeted commands

- Recovery RED: `uv run pytest tests/test_pipeline_walk.py tests/test_recommend.py::test_approval_records_gate_a_artifacts_without_mutating_workflow_state tests/test_review.py::test_gate_b_owns_accepted_artifacts_and_receipt_without_mutating_workflow_state tests/test_review.py::test_report_preserves_unresolved_work_and_contains_only_accepted_findings tests/test_skill.py -q`
- Recovery RED result: `6 failed, 18 passed in 1.66s`; exit 1.
- Focused pipeline file: `uv run pytest tests/test_pipeline_walk.py -q`

## Mechanical constraints

- Python requirement: `>=3.11`; focused runner: pytest via `uv`.
- Public proof input keys are `sources`, `gate_a`, `review`, and `gate_b`; test timestamps and identities are supplied explicitly.
- Durable pause proof fields are `status: paused` and `awaiting_input`.
- Maximum attempts per failed phase is 3.
- Persisted case references and attempt paths are relative to the case root.
- Gate A and Gate B remain explicit journalist inputs.
- Independent review input includes reviewer ID, verdicts, and draft-hash attestation.
- Replay and independent review precede Gate B; P5 draft precedes P6.
- Plan-stage edits are limited to tests and task notes/context; production source and canonical documentation are unchanged in this stage.
- No detector, source-adapter, report-feature, case-format, shared-package, service, database, scheduler, event-framework, network, or `ORCHESTRATION-SPINE.md` runtime dependency changes are in scope.
- Task 20 ledger files are outside task 25's edit scope.

## Implementation verification

- `src/anomaly/workflow.py` now owns the validated public P0–P7 handler
  composition and persists `paused` / `awaiting_input` state before source,
  Gate A, independent-review, and Gate B inputs without creating a phase
  attempt.
- `src/anomaly/recommend.py` Gate A approval now commits only the plan and
  Gate A receipt; `src/anomaly/review.py` Gate B acceptance and report writing
  no longer update `.anomaly/state.json`.
- `PRD.md` and `skills/anomaly/SKILL.md` now name state plus validated artifact
  identities as resume authority, receipts as binding evidence, and events as
  best-effort observational history.
- Recovery GREEN: `uv run pytest tests/test_pipeline_walk.py tests/test_recommend.py::test_approval_records_gate_a_artifacts_without_mutating_workflow_state tests/test_review.py::test_gate_b_owns_accepted_artifacts_and_receipt_without_mutating_workflow_state tests/test_review.py::test_report_preserves_unresolved_work_and_contains_only_accepted_findings tests/test_skill.py -q` — `24 passed in 1.74s`.
- Directly affected runner units: `uv run pytest tests/test_workflow.py -q` —
  `5 passed in 0.07s`.
