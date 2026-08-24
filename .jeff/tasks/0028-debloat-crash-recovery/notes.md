# Notes

## Plan decision

- **Category:** `code`.
- **Complexity:** `complex`.
- **Audit required:** `true`.
- **Approach:** retain the current pure resolver, fixed owner registry, bounded attempt evidence, workspace isolation, and public containment chokepoints. Replace automatic promotion rollback with a minimal interrupted-promotion marker whose only startup effect is to preserve the case and persist a manual-repair block. Delete journal entry interpretation, case-local provenance inference, backup creation/consumption, rollback, attempt rewind, and their synthetic crash fixtures instead of building another recovery protocol.
- **Refactor opportunity:** delete `_rollback`, `_rewind_attempt`, promotion journal schema/progress/artifact validation, `promotion-backup` handling, and the obsolete hard-exit/rollback fixtures; harmonize the retained marker with the existing relative `attempt_path`, attempt workspace, `blocked`, and `blocked_reason` conventions rather than adding a second recovery state model.
- **Escalation:** `null`; the operator explicitly placed machine/process crash rollback outside scope, so no unresolved recovery-guarantee fork remains.

## Task 27 council lineage carried forward

- A case-local `original=false` journal assertion could authorize deletion of a registry-bound live file.
- A case-local `original=true` assertion plus an attacker-controlled backup could authorize overwrite of a registry-bound live file.
- Producer-reachable interruptions for newly created artifacts and the sealed-state/pre-cleanup window could permanently wedge restart.
- Earlier recovery fixtures encoded producer-unreachable journal orderings and did not discriminate those destructive trust cases.
- The bounded task 28 contract removes the destructive authorization problem: startup treats the marker as interruption evidence only, leaves marker/workspace/live content in place, and requires explicit later repair.

## Ordered slices

1. **Ordinary attempt preservation:** keep case-shaped workspaces and the existing three-attempt failure path; prove owner and validation failures promote no partial live artifacts, retain redacted relative failure evidence, and leave no durable rollback journal or backup material.
2. **Fail-closed promotion boundary:** reduce promotion metadata to phase/attempt/relative attempt path, remove automatic backups/rollback/rewind and every journal entry authority, and make startup persist `blocked` plus `repair required` while retaining the marker, attempt workspace, any legacy backup, and all live content.
3. **Deletion and conformance:** delete stale hard-exit/rollback tests and recovery prose, revise the installed skill's public manual-repair contract, and rerun the existing canonical demo and public case/attempt/event containment seams without broadening production scope.

## Acceptance-criterion dispositions

1. **Normal owner/validation failures preserve live artifacts and retry evidence — `revise`.** Consumer-observable behavior: a P5 owner that writes a partial draft in its attempt workspace and fails three times leaves no live draft, while an invalid multi-source P1 batch leaves the live registry/raw directory unchanged; both retain attempts 1–3 and relative `failure.json` evidence with credential redaction. Deterministic seams: `test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence` and `test_failed_multi_source_attempt_does_not_promote_an_earlier_source`.
2. **Automatic journal, backups, provenance inference, and restart rollback are absent — `delete`.** Consumer-observable behavior: successful, owner-failed, and validation-failed calls leave no durable `promotion.json` or `promotion-backup`; pre-existing legacy recovery material is never consumed. Deterministic seams: the canonical demo and the two ordinary-failure tests assert the stable case surface; the legacy-marker test asserts retained backup bytes. Structural deletion itself is review/audit evidence, not a source-text test.
3. **Interrupted-promotion startup preserves live files and blocks for repair — `write`.** Consumer-observable behavior: public `run_workflow` returns a blocked state, preserves README, source registry, event history, marker bytes, and the retained attempt workspace, and creates no backup. Deterministic seam: `test_startup_with_an_interrupted_promotion_marker_blocks_for_manual_repair`.
4. **Blocked result names phase, attempt, and workspace — `write`.** Consumer-observable behavior: the returned durable state has `status == "blocked"`, `blocked is True`, phase `P1`, attempt `1`, and a credential-safe `blocked_reason` containing `repair required` plus `.anomaly/attempts/P1/attempt-1/workspace`. Deterministic seam: the shared `_assert_manual_repair` assertions used by both marker tests.
5. **Resolver, gates, replacement, invalidation, reviewer separation, README, Markdown, and ordinary resume remain green — `reuse`.** Consumer-observable behavior: the existing canonical CSV still completes through both human gates with dynamic P5/P6 owners, relative README links, exact order, and idempotent resume; existing identity/replacement/Markdown suites remain unchanged. Deterministic seams: `test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work` in the focused run and the existing task-27 contract tests outside this plan's RED selection.
6. **Public fork, attempt, event, and dispatcher paths retain whole-case no-symlink containment — `reuse`.** Consumer-observable behavior: public readers/creators/fork, direct attempts, direct event logging, dispatcher entry, and post-reasoning continuation reject symlink traversal before external mutation. Deterministic seams: the selected existing tests in `test_case.py`, `test_pipeline_walk.py`, and `test_events.py`; no new duplicate containment test is authored.
7. **Stale automatic crash-recovery tests/docs are revised — `revise`.** Consumer-observable behavior: installed instructions state that interrupted promotion requires manual repair with live content and workspace preserved, and do not expose automatic rollback/journal/backup promises. Deterministic seam: `test_skill_contracts_bounded_attempts_manual_repair_and_portable_paths`; source-text assertions are limited to this installed public surface because it has no runtime entry. The hard-exit reconciliation, producer-ordered rollback, second-rollback interruption, and exact journal-schema tests are deleted.
8. **Removed orchestration and Spotlight-specific surfaces stay absent — `reuse`.** Consumer-observable behavior: one installed Anomaly skill/reviewer and the resolver/owner/attempt flow remain the public surface; no runner, alias, product loop, duplicate projection, or Spotlight machinery returns. Deterministic seams: existing installed-surface and resolver conformance tests; no new symbol-absence test.

## Test ownership

- `tests/test_pipeline_walk.py` — writes the minimal-marker and inert legacy-journal/manual-repair contracts; revises ordinary failure/canonical stable-surface assertions; deletes automatic hard-exit, rollback, rollback-restart, provenance-recovery, and strict journal-schema fixtures.
- `tests/test_skill.py` — revises the installed public contract assertion to require fail-closed manual repair and remove automatic rollback/journal/backup claims.
- `tests/test_case.py` — reused unchanged for public reader/create/fork containment.
- `tests/test_events.py` — reused unchanged for direct event-writer containment.

## Focused RED

- **Command:** `uv run --extra test pytest -q tests/test_pipeline_walk.py::test_startup_with_an_interrupted_promotion_marker_blocks_for_manual_repair tests/test_pipeline_walk.py::test_legacy_journal_fields_and_backups_cannot_authorize_live_mutation tests/test_pipeline_walk.py::test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence tests/test_pipeline_walk.py::test_failed_multi_source_attempt_does_not_promote_an_earlier_source tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_run_attempts_rejects_a_symlinked_case_before_any_durable_write tests/test_pipeline_walk.py::test_public_dispatcher_rejects_nested_case_symlink_before_durable_write tests/test_pipeline_walk.py::test_public_dispatcher_rejects_anomaly_symlink_before_durable_write tests/test_pipeline_walk.py::test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns tests/test_case.py::test_public_case_reader_rejects_a_nested_symlink tests/test_case.py::test_create_case_rejects_a_symlink_before_writing tests/test_case.py::test_fork_rejects_a_symlinked_destination_ancestor_without_external_copy tests/test_events.py::test_direct_log_event_rejects_a_symlinked_store_without_external_append tests/test_skill.py::test_skill_contracts_bounded_attempts_manual_repair_and_portable_paths`
- **Exact result:** `4 failed, 13 passed in 0.97s` (exit 1).
- **Decisive RED:** the minimal marker still raises `invalid promotion journal`; a legacy `original=true` backup is consumed and overwrites `data/sources.json`; a legacy `original=false` claim raises recovery-artifact validation instead of producing the manual-repair block; and the installed skill has no interrupted-promotion/manual-repair contract.
- **Retained green proof:** both ordinary failure cases, the canonical public demo/resume, all selected dispatcher/attempt/case/event containment paths, and their parameter cases passed.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No bundled Python-specific skill is present.
