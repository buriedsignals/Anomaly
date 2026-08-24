# Context

## Task and judgment inputs

- `.jeff/tasks/0028-debloat-crash-recovery/task.md:3` — task goal; lines 6–15 contain the eight acceptance criteria.
- `.jeff/tasks/0028-debloat-crash-recovery/task.json:8` — current stage `plan`; line 9 locks category `code`; line 12 records complexity `complex`.
- `.jeff/tasks/0028-debloat-crash-recovery/review-correctness.json:56` — retained-workspace cleanup-order finding; line 61 kicks to plan.
- `.jeff/tasks/0028-debloat-crash-recovery/review-standards.json:55` — cleanup-order and ordinary interrupted-attempt test findings.
- `.jeff/tasks/0028-debloat-crash-recovery/audit-return.json:56` — cleanup-order boundary finding; line 64 names CWE-664.
- `.jeff/tasks/0028-debloat-crash-recovery/refute-1.json` through `refute-4.json` — all three cleanup-order sources and the interrupted-attempt test source survive refutation.

## Production paths and symbols

- `src/anomaly/_attempt_workspace.py:10` — `.anomaly/promotion.json` relative path.
- `src/anomaly/_attempt_workspace.py:25` — `promote_workspace`; lines 37–41 write the marker, apply live writes, write completed state, unlink the marker, and only then discard the workspace so an unlink failure retains the inspectable workspace.
- `src/anomaly/_attempt_workspace.py:44` — `recover_interrupted_promotion`; lines 45–68 turn a surviving marker into blocked durable state naming the retained workspace.
- `src/anomaly/_attempt_workspace.py:71` — `discard_workspace`; lines 72–78 remove a file, symlink, or directory.
- `src/anomaly/attempts.py:29` — public `run_attempts`; lines 44–57 invoke ordinary interrupted-attempt reconciliation before the bounded loop.
- `src/anomaly/attempts.py:58` — three-attempt loop; lines 60–64 durably count each attempt before execution.
- `src/anomaly/attempts.py:117` — successful attempt promotion call.
- `src/anomaly/attempts.py:129` — `_reconcile_interrupted_attempt`; lines 136–175 reuse matching failure evidence or synthesize `interrupted before completion`.
- `src/anomaly/attempts.py:210` — `_finish_failure`; lines 219–233 remove the attempt workspace, persist failure evidence, and emit a finite retry event.
- `src/anomaly/attempts.py:236` — `_record_failure`; lines 244–278 redact and persist relative failure/event/state evidence and mark attempt 3 unavailable.
- `src/anomaly/workflow.py:22` — fixed phase-to-owner/write registry.
- `src/anomaly/workflow.py:161` — public `run_workflow`; lines 170–174 handle startup marker recovery and lines 203–213 invoke public attempts.
- `src/anomaly/state.py:13` — maximum attempt count is 3.

## Target tests

- `tests/test_pipeline_walk.py:639` — successful public P1 promotion interrupted immediately after real workspace cleanup; durable completed state, promoted source registry, missing workspace, and marker/workspace invariant are observed.
- `tests/test_pipeline_walk.py:680` — producer-reachable durable attempt count without failure evidence; public restart reconciliation, two remaining executions, credential redaction, three failure files, and absent rollback material are observed.
- `tests/test_pipeline_walk.py:747` — pre-existing interrupted-promotion marker blocks public startup while preserving live files and workspace.
- `tests/test_pipeline_walk.py:782` — legacy journal fields and backup bytes do not authorize live mutation.

## Commands

- Focused GREEN: `uv run --extra test pytest -q tests/test_pipeline_walk.py::test_successful_promotion_cleanup_never_leaves_a_marker_without_its_workspace tests/test_pipeline_walk.py::test_restart_reconciles_a_counted_attempt_without_failure_evidence`
- Focused GREEN result: `2 passed in 0.10s` (exit 0).
- Project gate: `uv run --extra test pytest tests/`.

## Mechanical constraints

- Python package root: `src/anomaly`; commands run from the anomaly root through `uv`.
- Persisted case, attempt, and workspace paths are relative.
- `.anomaly/state.json` is resume authority; `.anomaly/events.jsonl` is observational.
- Tests use isolated `tmp_path`, fixed `NOW`, checked-in fixtures, and injected failpoints; no network, sleep, random value, or filesystem-time assertion is used.
- Plan-stage mutations are limited to tests and task 28 `notes.md`/`context.md`.
- Repository mutation uses Jujutsu; no commit or full-suite command runs at plan stage.
