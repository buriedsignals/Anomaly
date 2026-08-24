# Context

## Relevant production paths and symbols

- `src/anomaly/workflow.py:22` — single P0-P7 owner registry with each phase's fixed write set.
- `src/anomaly/workflow.py:85` — complete phase required-input names.
- `src/anomaly/workflow.py:94` — pure `resolve_workflow` decision.
- `src/anomaly/workflow.py:132` — fixed-path dynamic owner loading.
- `src/anomaly/workflow.py:158` — public invocation-bound `run_workflow` dispatcher.
- `src/anomaly/workflow_inputs.py:39` — schema-aware workflow input capabilities.
- `src/anomaly/attempts.py:29` — bounded three-attempt staged execution and evidence boundary.
- `src/anomaly/_attempt_workspace.py:13` — portable case-shaped attempt workspace creation.
- `src/anomaly/_attempt_workspace.py:25` — journalled promotion with state sealed last.
- `src/anomaly/_attempt_workspace.py:57` — interrupted-promotion recovery.
- `src/anomaly/owners.py:37` — one resolved-owner consumer operating on the staged case.
- `src/anomaly/owners.py:58` — deterministic handler dispatch.
- `src/anomaly/owners.py:81` — staged multi-source registration.
- `src/anomaly/owners.py:110` — staged replay plus independent-review owner.
- `src/anomaly/owners.py:129` — staged Gate B acceptance/report/chart owner.
- `src/anomaly/state.py:32` — snapshot load and required-identity invalidation entry.
- `src/anomaly/state.py:126` — durable values route through the shared credential sanitizer.
- `src/anomaly/identities.py:8` — artifact identity-to-phase table.
- `src/anomaly/identities.py:22` — required recorded/current identity comparison.
- `src/anomaly/readme.py:24` — marker-bounded README Outputs projection.
- `src/anomaly/case.py:139` — whole-tree-scanned public case inspection.
- `src/anomaly/case.py:147` — whole-tree-scanned public case resume.
- `src/anomaly/case.py:257` — whole-case file/link scan.
- `src/anomaly/acquire.py:31` — public local source registration.
- `src/anomaly/review.py:650` — dataset-derived Markdown escaping through the shared sanitizer.
- `src/anomaly/semantics.py:70` — canonical Unicode identity key.
- `src/anomaly/semantics.py:101` — central assignment/Bearer/provider/userinfo credential sanitizer.

## Plan-owned tests

- `tests/test_workflow.py:57` — P1-P4 clock and gate required-input resolver matrix.
- `tests/test_pipeline_walk.py:180` — six recommendation/Gate A/detector/draft/replay/review identity mutations for P3-P6.
- `tests/test_pipeline_walk.py:209` — missing `now` pauses before P1 attempts.
- `tests/test_pipeline_walk.py:229` — incomplete Gate A pauses before an attempt.
- `tests/test_pipeline_walk.py:248` — incomplete Gate B pauses before an attempt.
- `tests/test_pipeline_walk.py:263` — future Gate A decision turn boundary.
- `tests/test_pipeline_walk.py:291` — future Gate B decision turn boundary.
- `tests/test_pipeline_walk.py:319` — checked-in demo, completion links, authored Outputs block, restart, and dynamic event order.
- `tests/test_pipeline_walk.py:443` — five credential forms across durable three-attempt evidence.
- `tests/test_pipeline_walk.py:518` — failed multi-source P1 batch live-artifact boundary.
- `tests/test_pipeline_walk.py:624` — P3-P6 earliest-suffix invalidation matrix.
- `tests/test_pipeline_walk.py:643` — completed state with missing required identities.
- `tests/test_pipeline_walk.py:682` — canonical Gate A/reviewer separation.
- `tests/test_pipeline_walk.py:726` — canonical reviewer/Gate B separation.
- `tests/test_pipeline_walk.py:748` — Gate B invalidation, README demotion, and recompletion.
- `tests/test_pipeline_walk.py:791` — failed P7 live-artifact and README boundary.
- `tests/test_pipeline_walk.py:872` — link introduced by a dynamic owner.
- `tests/test_case.py:227` — public inspect/resume nested-link cases.
- `tests/test_acquire.py:188` — direct source destination-link case.
- `tests/test_review.py:425` — inert Markdown with a standalone bare URL.
- `tests/fixtures/orchestration_demo.csv` — checked-in public workflow input.

## Commands

- Targeted RED: `uv run --extra test pytest tests/test_workflow.py::test_resolver_reports_incomplete_phase_input_before_attempt tests/test_pipeline_walk.py::test_missing_now_pauses_before_p1_attempts_are_consumed tests/test_pipeline_walk.py::test_incomplete_gate_a_decision_pauses_without_consuming_an_attempt tests/test_pipeline_walk.py::test_incomplete_gate_b_decision_pauses_without_consuming_an_attempt tests/test_pipeline_walk.py::test_gate_a_decision_supplied_before_gate_is_not_carried_across_the_turn tests/test_pipeline_walk.py::test_gate_b_decision_supplied_before_review_is_not_carried_across_the_turn tests/test_pipeline_walk.py::test_public_dispatcher_persists_three_failed_attempts_and_blocks tests/test_pipeline_walk.py::test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence tests/test_pipeline_walk.py::test_failed_multi_source_attempt_does_not_promote_an_earlier_source tests/test_pipeline_walk.py::test_public_dispatcher_retries_recommendation_failure_inside_p3 tests/test_pipeline_walk.py::test_public_dispatcher_replaces_changed_registered_source tests/test_pipeline_walk.py::test_changed_p3_p6_identity_invalidates_only_its_earliest_suffix tests/test_pipeline_walk.py::test_completed_snapshot_without_required_identities_fails_closed_from_p1 tests/test_pipeline_walk.py::test_public_dispatcher_rejects_canonical_gate_a_approver_as_reviewer tests/test_pipeline_walk.py::test_public_dispatcher_rejects_canonical_reviewer_as_gate_b_journalist tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_pipeline_walk.py::test_failed_p7_attempt_does_not_promote_outputs_or_delete_journalist_content tests/test_pipeline_walk.py::test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns tests/test_case.py::test_public_case_reader_rejects_a_nested_symlink tests/test_acquire.py::test_register_local_source_rejects_an_in_case_destination_symlink tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`
- Targeted RED result: `19 failed, 13 passed in 2.34s` (exit 1).
- Targeted GREEN result after implementation: `32 passed in 4.08s` (exit 0).
- Jeff project gate: `uv run --extra test pytest tests/`.

## Mechanical constraints

- Python package root: `src/anomaly`; commands run from the repository root through `uv`.
- Public installed entry: `anomaly.workflow.run_workflow`.
- Installed dynamic instruction paths: `skills/anomaly/SKILL.md` and `agents/anomaly-data-reviewer.md`.
- Case and attempt references persisted in JSON are relative paths.
- Maximum executed attempts per phase: 3.
- Human Gate A and Gate B pauses consume no phase attempt.
- `WorkflowRunner`, `PhaseResult`, `RetryLimitExceeded`, `product_workflow.py`, handler composition, compatibility aliases, state-level `gate`, and `last_completed_phase` are absent from the current production surface.
- Plan-stage file scope: tests, this task's `notes.md`, and this task's `context.md`.
- Task command scope excludes formatter, linter, and full-suite execution.
- Repository mutation uses Jujutsu; no commit is created by this plan stage.
