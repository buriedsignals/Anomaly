# Context

## Task and lineage

- `.jeff/tasks/0028-debloat-crash-recovery/task.md:3` — task 28 goal; lines 6–15 contain the acceptance criteria.
- `.jeff/tasks/0028-debloat-crash-recovery/task.json:9` — locked category `code`; line 12 records complexity `complex`; lines 32–37 record required audit state.
- `.jeff/tasks/0027-resolver-consolidation/council-final.json:75` — task 27 recovery trust-model council question and evidence.
- `.jeff/tasks/0027-resolver-consolidation/audit-council.json:62` — case-local backup overwrite finding; line 72 records the newly-created-artifact interruption finding.
- `.jeff/tasks/0027-resolver-consolidation/review-council-correctness.json:68` — sealed-state/pre-cleanup interruption finding.
- `.jeff/tasks/0027-resolver-consolidation/refute-terminal-1.json` through `refute-terminal-5.json` — terminal finding dispositions and evidence.

## Production and installed-content paths

- `src/anomaly/_attempt_workspace.py:10` — `.anomaly/promotion.json` path.
- `src/anomaly/_attempt_workspace.py:25` — workspace promotion entry; lines 33–46 create the current journal entry records.
- `src/anomaly/_attempt_workspace.py:57` — startup promotion recovery entry.
- `src/anomaly/_attempt_workspace.py:85` — current ordered apply and backup creation.
- `src/anomaly/_attempt_workspace.py:112` — current rollback and backup consumption.
- `src/anomaly/_attempt_workspace.py:146` — current attempt rewind.
- `src/anomaly/_attempt_workspace.py:181` — current promotion journal parser.
- `src/anomaly/_attempt_workspace.py:267` — current live/backup recovery-artifact validation.
- `src/anomaly/attempts.py:29` — bounded public attempt utility and case-shaped workspace execution.
- `src/anomaly/attempts.py:210` — workspace cleanup plus failure transition.
- `src/anomaly/attempts.py:236` — relative attempt failure evidence and blocked/unavailable state recording.
- `src/anomaly/workflow.py:22` — sole phase-to-owner registry and fixed phase write tuples.
- `src/anomaly/workflow.py:94` — pure workflow resolver.
- `src/anomaly/workflow.py:161` — public startup/dispatch loop; lines 170–175 invoke resume and promotion recovery.
- `src/anomaly/state.py:13` — three-attempt bound.
- `src/anomaly/state.py:16` — public workflow error type.
- `skills/anomaly/SKILL.md:25` — installed operating contract; lines 45–66 describe attempts, retries, and restart.

## Plan-owned and reused test seams

- `tests/test_pipeline_walk.py:637` — minimal interrupted-promotion marker/manual-repair contract.
- `tests/test_pipeline_walk.py:672` — legacy journal fields and backup bytes are inert and retained.
- `tests/test_pipeline_walk.py:763` — failing P5 owner writes only inside attempt workspaces and retains three redacted failures.
- `tests/test_pipeline_walk.py:850` — invalid multi-source P1 batch retains three failures without live promotion.
- `tests/test_pipeline_walk.py:512` — checked-in public demo, both gates, dynamic owners, relative README links, order, and resume.
- `tests/test_pipeline_walk.py:730` — direct attempt pre-write no-symlink containment.
- `tests/test_pipeline_walk.py:1187` — nested case symlink containment at dispatcher entry.
- `tests/test_pipeline_walk.py:1210` — `.anomaly` symlink containment at dispatcher entry.
- `tests/test_pipeline_walk.py:1231` — containment recheck after a reasoning owner returns.
- `tests/test_case.py:227` — public inspect/resume nested-symlink rejection.
- `tests/test_case.py:244` — create-time root/nested symlink rejection.
- `tests/test_case.py:429` — fork destination-ancestor symlink rejection.
- `tests/test_events.py:304` — direct event-store symlink rejection.
- `tests/test_skill.py:70` — installed bounded-attempt/manual-repair/portable-path contract.
- `tests/fixtures/orchestration_demo.csv` — checked-in canonical public demo input.

## Commands

- Focused RED: `uv run --extra test pytest -q tests/test_pipeline_walk.py::test_startup_with_an_interrupted_promotion_marker_blocks_for_manual_repair tests/test_pipeline_walk.py::test_legacy_journal_fields_and_backups_cannot_authorize_live_mutation tests/test_pipeline_walk.py::test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence tests/test_pipeline_walk.py::test_failed_multi_source_attempt_does_not_promote_an_earlier_source tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_run_attempts_rejects_a_symlinked_case_before_any_durable_write tests/test_pipeline_walk.py::test_public_dispatcher_rejects_nested_case_symlink_before_durable_write tests/test_pipeline_walk.py::test_public_dispatcher_rejects_anomaly_symlink_before_durable_write tests/test_pipeline_walk.py::test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns tests/test_case.py::test_public_case_reader_rejects_a_nested_symlink tests/test_case.py::test_create_case_rejects_a_symlink_before_writing tests/test_case.py::test_fork_rejects_a_symlinked_destination_ancestor_without_external_copy tests/test_events.py::test_direct_log_event_rejects_a_symlinked_store_without_external_append tests/test_skill.py::test_skill_contracts_bounded_attempts_manual_repair_and_portable_paths`
- Focused RED result: `4 failed, 13 passed in 0.97s` (exit 1).
- Project gate command: `uv run --extra test pytest tests/`.

## Mechanical constraints

- Python package root: `src/anomaly`; repository commands run from the anomaly root through `uv`.
- Persisted case, attempt, and workspace paths are relative.
- Maximum attempts per phase: 3.
- `.anomaly/state.json` is resume authority; `.anomaly/events.jsonl` is observational.
- Plan-stage mutations are limited to tests and task 28 `notes.md`/`context.md`.
- Repository mutation uses Jujutsu; no commit or full-suite command runs at plan stage.
