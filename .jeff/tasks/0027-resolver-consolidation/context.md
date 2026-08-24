# Context

## Locked task and gated lineage

- `.jeff/tasks/0027-resolver-consolidation/task.md:7` — AC1-AC9 and the no-runner non-goal.
- `.jeff/tasks/0027-resolver-consolidation/task.json:8` — current stage `plan`; line 9 locks category `code`.
- `.jeff/tasks/0027-resolver-consolidation/task.json:42` — prior clean full gate at `8500ab972190cc5d83fc37344fede3a24816dfe2` with `uv run --extra test pytest tests/`.
- `.jeff/tasks/0027-resolver-consolidation/review-recovered-correctness.json:61` — cycle-1 correctness findings.
- `.jeff/tasks/0027-resolver-consolidation/review-recovered-standards.json:61` — cycle-1 standards findings.
- `.jeff/tasks/0027-resolver-consolidation/audit-recovered.json:56` — cycle-1 security findings.
- `.jeff/tasks/0027-resolver-consolidation/refute-post-1.json` through `refute-post-10.json` — ten sustained cycle-1 refutes.

## Relevant production and installed-content paths

- `src/anomaly/workflow.py:22` — sole P0-P7 owner registry and bounded phase write tuples.
- `src/anomaly/workflow.py:85` — per-phase required input names.
- `src/anomaly/workflow.py:94` — pure `resolve_workflow` decision.
- `src/anomaly/workflow.py:132` — installed dynamic owner loading.
- `src/anomaly/workflow.py:158` — public `run_workflow` dispatcher and recovery entry.
- `src/anomaly/workflow_inputs.py:25` — public input normalization.
- `src/anomaly/workflow_inputs.py:39` — capability derivation.
- `src/anomaly/workflow_inputs.py:83` — source request normalization.
- `src/anomaly/workflow_inputs.py:116` — gate mapping completeness predicate.
- `src/anomaly/attempts.py:29` — bounded `run_attempts` utility.
- `src/anomaly/attempts.py:43` — durable attempt counter and attempt loop.
- `src/anomaly/attempts.py:138` — failure cleanup/evidence path.
- `src/anomaly/attempts.py:164` — failure state/event recording.
- `src/anomaly/_attempt_workspace.py:25` — journalled workspace promotion.
- `src/anomaly/_attempt_workspace.py:57` — public-entry interrupted-promotion recovery.
- `src/anomaly/_attempt_workspace.py:82` — entry-by-entry promotion application.
- `src/anomaly/_attempt_workspace.py:109` — promotion rollback.
- `src/anomaly/_attempt_workspace.py:166` — persisted promotion journal parsing.
- `src/anomaly/owners.py:37` — one resolved-owner consumer.
- `src/anomaly/identities.py:8` — artifact identity-to-phase mapping.
- `src/anomaly/identities.py:22` — recorded/current identity comparison.
- `src/anomaly/identities.py:42` — identity capture through a sealed phase.
- `src/anomaly/identities.py:85` — identity artifact path mapping.
- `src/anomaly/state.py:12` — `MAX_ATTEMPTS = 3`.
- `src/anomaly/state.py:32` — snapshot identity invalidation and README projection entry.
- `src/anomaly/state.py:104` — atomic JSON persistence.
- `src/anomaly/state.py:122` — durable error sanitizer entry.
- `src/anomaly/case.py:102` — public `create_case` writer.
- `src/anomaly/case.py:139` — whole-tree-scanned `inspect_case` reader.
- `src/anomaly/case.py:147` — whole-tree-scanned `resume_case` reader.
- `src/anomaly/case.py:257` — unresolved-path ancestor and descendant scan.
- `src/anomaly/readme.py:7` — marker-owned output links.
- `src/anomaly/readme.py:24` — README state projection.
- `src/anomaly/semantics.py:58` — shared assignment credential pattern.
- `src/anomaly/semantics.py:101` — shared recursive credential sanitizer.
- `skills/anomaly/SKILL.md:39` — current state/event/attempt authority text.
- `skills/anomaly/SKILL.md:46` — current durable-runner wording.
- `skills/anomaly/SKILL.md:207` — current abstract Verbs section.
- `skills/anomaly/SKILL.md:232` — current last-completed-event resume wording.
- `skills/anomaly/SKILL.md:247` — current `MAX_ATTEMPTS` owner wording.

## Plan-owned test seams

- `tests/test_pipeline_walk.py:190` — P1 persisted promotion write-set fixture.
- `tests/test_pipeline_walk.py:196` — P7 authoritative output mutation table.
- `tests/test_pipeline_walk.py:310` — value-invalid source requests pause before P1 attempts.
- `tests/test_pipeline_walk.py:378` — value-invalid Gate A decisions pause before P4 attempts.
- `tests/test_pipeline_walk.py:405` — value-invalid Gate B decisions pause before P7 attempts.
- `tests/test_pipeline_walk.py:578` — valid missing-file source retries retain three-attempt evidence.
- `tests/test_pipeline_walk.py:605` — interrupted attempt recovery, evidence, cleanup, and finite retry limit.
- `tests/test_pipeline_walk.py:644` — valid interrupted-promotion rollback, rewind, cleanup, and fresh retry.
- `tests/test_pipeline_walk.py:695` — untrusted promotion path/status/original rejection without mutation.
- `tests/test_pipeline_walk.py:730` — compound environment assignment redaction across durable evidence.
- `tests/test_pipeline_walk.py:1038` — existing Gate B receipt invalidation and recompletion.
- `tests/test_pipeline_walk.py:1082` — P7 output identity and README demotion table.
- `tests/test_case.py:244` — root/nested create-time symlink rejection before writes.
- `tests/test_skill.py:70` — durable path, bounded retry, and portable-path installed-skill assertions after stale event-resume assertion removal.
- `tests/test_workflow.py:12` — pure ready/resume result and snapshot immutability.
- `tests/test_review.py:425` — inert standalone bare-URL serialization.
- `tests/fixtures/orchestration_demo.csv` — checked-in canonical workflow input.

## Commands

- Focused RED: `uv run --extra test pytest tests/test_pipeline_walk.py::test_value_invalid_source_input_pauses_before_an_attempt tests/test_pipeline_walk.py::test_value_invalid_gate_a_input_pauses_before_an_attempt tests/test_pipeline_walk.py::test_value_invalid_gate_b_input_pauses_before_an_attempt tests/test_pipeline_walk.py::test_public_dispatcher_persists_three_failed_attempts_and_blocks tests/test_pipeline_walk.py::test_interrupted_attempts_recover_with_evidence_and_stop_at_the_limit tests/test_pipeline_walk.py::test_public_restart_rolls_back_an_interrupted_promotion_before_retry tests/test_pipeline_walk.py::test_public_restart_rejects_untrusted_promotion_journal_without_case_mutation tests/test_pipeline_walk.py::test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_pipeline_walk.py::test_changed_or_missing_p7_output_demotes_completion_and_readme tests/test_case.py::test_create_case_rejects_a_symlink_before_writing tests/test_skill.py::test_skill_contracts_durable_state_bounded_retries_and_portable_paths`.
- Focused RED result: `30 failed, 4 passed in 3.71s` (exit 1).
- Jeff project gate command: `uv run --extra test pytest tests/`.

## Mechanical constraints

- Python package root: `src/anomaly`; commands run from the repository root through `uv`.
- Public installed dispatcher: `anomaly.workflow.run_workflow`.
- Dynamic instruction paths: `skills/anomaly/SKILL.md` and `agents/anomaly-data-reviewer.md`.
- Case, attempt, and promotion paths persisted in JSON are relative paths.
- Maximum attempts per phase: 3.
- Human Gate A and Gate B pauses consume no phase attempt.
- `.anomaly/state.json` completion is authoritative; `.anomaly/events.jsonl` is observational.
- `WorkflowRunner`, `PhaseResult`, `RetryLimitExceeded`, `product_workflow.py`, handler composition, compatibility aliases, state-level `gate`, and `last_completed_phase` are absent from production.
- Plan-stage mutations are limited to tests, this task's `notes.md`, and this task's `context.md`.
- No full-suite command, production edit, installed-content edit, product-doc edit, commit, formatter, or linter runs in this plan stage.
- Repository mutation uses Jujutsu.
