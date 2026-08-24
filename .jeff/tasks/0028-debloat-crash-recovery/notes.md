# Notes

## Recovery plan decision

- **Category:** `code`.
- **Complexity:** `complex`.
- **Audit required:** `true`; the existing audit requirement covers the retained-workspace boundary and cannot be lowered during recovery.
- **Approach:** make the smallest two-part repair. First, clear the durable promotion marker after live artifacts and state are sealed but before ordinary attempt-workspace cleanup, and prove through public `run_workflow` behavior that an interruption immediately after real cleanup cannot leave a repair marker pointing at a deleted workspace. Second, restore the ordinary `run_attempts` restart proof by creating a producer-reachable durably counted attempt with no failure record, then verify restart records a bounded synthetic interrupted failure and consumes only the two remaining retries with credential-safe evidence.
- **Refactor opportunity:** `null`; the two defects require one cleanup-order correction and two focused behavioral tests, with no behavior-preserving deduplication, deletion, or harmonization owed.
- **Escalation:** `null`; the surviving judgments identify one unambiguous ordering invariant and one retained reconciliation contract.

## Ordered slices

1. **Promotion final-cleanup invariant:** exercise a successful P1 promotion through public `run_workflow`, interrupt immediately after the real workspace deletion boundary, and require that the durable marker is absent whenever that workspace is absent. The production correction is limited to clearing `.anomaly/promotion.json` after the completed state is durable and before calling ordinary workspace cleanup.
2. **Ordinary interrupted-attempt reconciliation:** restore a deterministic public `run_attempts` test that interrupts after attempt 1 is durably counted but before any failure evidence exists, then restarts into one synthetic interrupted failure plus attempts 2 and 3, with bounded redacted durable evidence and no promotion-recovery material.

## Acceptance-criterion dispositions

1. **Normal owner/validation failures preserve live artifacts and retry evidence — `reuse`.** Consumer-observable behavior: three ordinary owner or validation failures leave live artifacts unchanged and retain relative credential-safe failure evidence. Deterministic seams: `test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence` and `test_failed_multi_source_attempt_does_not_promote_an_earlier_source`; neither judgment changes this proof.
2. **Automatic promotion rollback machinery remains absent — `reuse`.** Consumer-observable behavior: successful and ordinary failed attempts leave no promotion marker or backup material, while legacy backup bytes cannot authorize overwrite or deletion. Deterministic seams: `_assert_no_automatic_rollback_material` in successful/failure tests and `test_legacy_journal_fields_and_backups_cannot_authorize_live_mutation`; structural absence remains review evidence.
3. **Interrupted-promotion startup preserves live files and blocks for repair — `reuse`.** Consumer-observable behavior: public `run_workflow` seeing a marker preserves live case bytes and the existing workspace, retains the marker, records `repair required`, and stops. Deterministic seam: `test_startup_with_an_interrupted_promotion_marker_blocks_for_manual_repair`.
4. **Blocked results identify an inspectable retained workspace — `write`.** Consumer-observable behavior: after a successful P1 promotion seals its artifacts and state, an interruption immediately after actual workspace cleanup never leaves the combination of a surviving promotion marker and a missing workspace. Deterministic seam: `test_successful_promotion_cleanup_never_leaves_a_marker_without_its_workspace`, which observes durable case files and does not assert collaborator call order.
5. **Resolver and ordinary restart/resume behavior remain green — `revise`.** Consumer-observable behavior: a producer-reachable attempt count of 1 with no matching failure becomes failure 1 with the bounded text `P1 attempt 1 was interrupted before completion`; only attempts 2 and 3 execute, their credential-bearing errors are redacted in all durable JSON/JSONL evidence, and the phase becomes unavailable at the three-attempt limit. Deterministic seam: `test_restart_reconciles_a_counted_attempt_without_failure_evidence`. Existing resolver, gate, replacement, invalidation, reviewer, README, Markdown, canonical-demo, and idempotent-resume tests remain reused.
6. **Public case, fork, attempt, dispatcher, and event paths retain no-symlink containment — `reuse`.** Consumer-observable behavior: each public writer/reader rejects whole-case symlink traversal before external mutation. Deterministic seams remain the existing containment tests in `tests/test_case.py`, `tests/test_pipeline_walk.py`, and `tests/test_events.py`.
7. **Stale automatic crash-rollback claims remain removed — `reuse`.** Consumer-observable behavior: installed instructions expose fail-closed manual repair rather than automatic rollback, while ordinary interrupted-attempt retry remains a separate bounded attempt contract. Deterministic seams: `test_skill_contracts_bounded_attempts_manual_repair_and_portable_paths` plus the restored ordinary reconciliation test; no promotion rollback fixture is restored.
8. **Removed orchestration and Spotlight-specific surfaces stay absent — `reuse`.** Consumer-observable behavior: the installed Anomaly skill/reviewer and resolver-owner-attempt flow remain the only product surface. Deterministic seams remain the installed-surface and resolver conformance tests; no new source-text absence assertion is added.

## Test ownership

- `tests/test_pipeline_walk.py` — adds the successful-promotion cleanup invariant and restores the ordinary counted-attempt reconciliation contract.
- All other task tests are intentionally unchanged and reused.

## Focused RED

- **Command:** `uv run --extra test pytest -q tests/test_pipeline_walk.py::test_successful_promotion_cleanup_never_leaves_a_marker_without_its_workspace tests/test_pipeline_walk.py::test_restart_reconciles_a_counted_attempt_without_failure_evidence`
- **Exact result:** `1 failed, 1 passed in 0.15s` (exit 1).
- **Decisive RED:** after public P1 promotion has durably completed and the injected boundary has performed real workspace cleanup, `.anomaly/promotion.json` still exists while `.anomaly/attempts/P1/attempt-1/workspace` does not. The new invariant assertion fails with `assert (not True or False)`.
- **Preserved green proof:** the restored ordinary reconciliation test passes, showing the current public restart path records attempt 1 as interrupted, runs only attempts 2 and 3, redacts their credential values, persists three relative failure records, stops at the finite limit, and creates no promotion rollback material.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No bundled Python-specific skill is present.
