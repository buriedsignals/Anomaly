# Notes

Operator-approved replacement for task 25. Task 25 terminal evidence is preserved in Jujutsu checkpoints and `prunedTaskIds`. This task consolidates the validated behaviour into a smaller resolver/registry/attempt shape; it is not permission to add another workflow layer.

## Plan decision

- **Complexity:** `complex`. The cutover changes durable resolution, dynamic owner dispatch, state projection, and three audited trust boundaries while preserving a portable case format.
- **Audit required:** `true`. Audit the fixed-path skill/persona loader, whole-case containment before resume/read/write, source replacement and detector execution, credential-redacted attempt evidence, and Markdown/report/README serialization.
- **Approach:** replace the `WorkflowRunner` plus `product_workflow` double loop with one pure `resolve_workflow(snapshot, supplied)` decision and one compact P0-P7 owner registry. A resolution has exactly `phase`, `status`, singular `owner` (`{"kind": "handler|skill|persona", "id": ...}` or `null` at a human stop/terminal), `missing`, numeric attempts consumed, `invalidated_from`, and truthful `resume`. It reads no files, clocks, or globals and mutates neither input nor case.
- The executor consumes one resolution only. Handler owners call existing deterministic domain code. P5 loads the installed `anomaly` skill; P6 runs deterministic replay, then loads the fixed installed `anomaly-data-reviewer` persona, validates its return, and seals review. Gate A and Gate B return a missing human-decision descriptor, end the turn without consuming an attempt, and never invoke an owner. Every seal or pause is followed by a fresh snapshot and fresh resolution.
- Move attempt-directory staging, exactly-three retry accounting, redacted failure/result evidence, event append, and atomic state promotion into small function utilities in `src/anomaly/attempts.py`, separate from resolution. They execute an already-resolved owner but make no phase/owner/gate policy decisions.
- Keep `anomaly.workflow.run_workflow` as the sole public installed entry. Use the fixed repository-owned registry to load skill/persona text; never resolve executable instructions from a case path. No dependency, shared framework, handler-map API, database, service, or new phase is warranted.
- **Refactor opportunity:** delete the behaviorless injected-runner/product-composition surface and harmonize durable state to one projection: remove `WorkflowRunner`, `PhaseResult`, `RetryLimitExceeded`, handler signature introspection and composition validation, module-level state/event/invalidation aliases, the entire competing `product_workflow.py` loop/handler map, and the duplicate `last_completed_phase`/`gate` state projections. Derive completion and gate position from the canonical completed-phase map plus sealed receipts.

## Ordered slices

1. Introduce the pure resolver contract and the one fixed owner registry; encode source input and Gate A/Gate B stops as `missing`, preserve attempts/invalidation/resume detail, and prove the input snapshot is unchanged.
2. Add one owner-consumption boundary: deterministic handlers stay code; P5/P6 load the trusted installed skill/persona dynamically, validate returns, replay before review, seal once, then resolve fresh.
3. Extract the durable attempt functions into `src/anomaly/attempts.py` and migrate the public dispatcher to resolver → owner → seal/pause → fresh resolver. Preserve exactly three attempts, atomic promotion, failure evidence, event-failure resume, earliest invalidation, identity separation, case portability, containment, and P5→P6→Gate B→P7.
4. Fix the two preserved task-25 defects at their owning serializers: bound generated README Outputs replacement so later journalist content survives completion/invalidation, and neutralize bare HTTP(S) autolinks in dataset-derived Markdown. Keep successful completion and relative-link assertions at the public P7 demo seam.
5. Delete the old orchestration surfaces, synthetic full-P0-P7 test compositions, stale report-completion plumbing/expectations, and duplicate projections; update PRD/installed-skill wording to the single resolver method and run only the task-targeted tests before the orchestrator's gate.

## Deletion inventory

### Production

- Delete `src/anomaly/product_workflow.py` after moving only its input validation and compound deterministic handlers behind the single registry; remove `run_product_workflow`, `_PRODUCT_HANDLERS`, its while-loop, and its duplicate awaiting/next/completed policy.
- Delete `WorkflowRunner`, `PhaseResult`, `RetryLimitExceeded`, `_validate_composition`, `_handler_for`, `_call_handler`, injected `phases`/`handlers`/`phase_handlers`, and arbitrary handler-signature support from `src/anomaly/workflow.py`.
- Delete unused module aliases `load_state`, `read_events`, `append_event`, and `invalidate`; callers use the public dispatcher or focused durable functions.
- Stop writing `last_completed_phase` and state-level `gate`; remove their fallback/repair branches and derive both from canonical completed phases plus Gate A/B receipts. Normalize them away on the next atomic state write rather than maintaining dual projections.
- Do not restore report-owned README completion. Bound the one runner-owned generated Outputs block, preserving unrelated trailing sections.

### Tests

- Delete the six synthetic `WorkflowRunner`/handler-map compositions in `tests/test_workflow.py`; retain only focused resolver/owner and durable-attempt behavior seams.
- Delete the fake all-P0-P7 rerun from `test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase`; assert the pure resolver's earliest suffix, then rely on the public mutation/demo tests for actual execution.
- Remove manual public `inputs={"review": ...}` composition from `tests/test_pipeline_walk.py`; the injected deterministic runtime returns the dynamically loaded reviewer result through the single `invoke` boundary.
- Keep the existing public P1/P3 retry, source replacement, gate identity, Gate B demotion, event-failure resume, containment, and portability tests; do not duplicate each historical bug under the new internal names.
- Keep direct `write_report` non-completion and accepted-content assertions; do not restore stale direct-completion expectations.

## Acceptance-criterion dispositions

1. **Pure resolver — `write`.** Consumer behavior: the same durable snapshot and supplied-input set always yield the same complete decision without mutation or execution. Deterministic seam: `test_resolver_is_pure_and_reports_durable_resume_detail`.
2. **One registry and dynamic owners — `write`.** Consumer behavior: the resolved P5 skill and P6 reviewer persona are loaded from their fixed installed paths and exactly the selected owner is invoked once; deterministic phases remain handler owners. Seam: `test_resolved_reasoning_owner_is_loaded_and_invoked_once`.
3. **Separate durable attempts — `reuse`/`delete`.** Consumer behavior: an owner gets three staged attempts, redacted relative failure evidence, atomic success promotion, and resumability when event append fails. Reuse the installed P1/P3 retry and event-failure tests; delete handler-map composition tests rather than restating utility structure.
4. **Gates, invalidation, containment, identity, and order — `reuse`.** Consumer behavior remains Gate A/P4, P5 interpretation, P6 replay/reviewer, Gate B/P7, earliest suffix invalidation, independent identities, source replacement, event resume, portable paths, and whole-case no-symlink rejection. Reuse the focused public tests in `test_pipeline_walk.py`, `test_events.py`, and `test_case.py`.
5. **README lifecycle and links — `revise`.** Consumer behavior: public P7 completion projects complete/P7 and three resolving relative links; later journalist-authored README sections survive completed restart, Gate B invalidation, failure, and recompletion. Seams: revised public demo and Gate B invalidation tests.
6. **Inert dataset Markdown — `revise`.** Consumer behavior: report claim prose cannot create raw HTML, headings, inline links, or bare HTTP(S) autolinks. Seam: revised `test_write_report_serializes_dataset_text_as_inert_markdown`.
7. **Whole-case no-symlink boundary — `reuse`.** Consumer behavior: every public resume/read/write path scans the case before mutation. Reuse nested-case and `.anomaly` symlink tests; the audit checks all public call sites.
8. **Remove obsolete surfaces — `delete`.** The aliases, direct completion path, duplicate test compositions, stale expectations, and duplicate state projections have no independent consumer contract; deletion is proved by the surviving behavior suite, not symbol-absence tests.
9. **One demo CSV — `revise`.** Consumer behavior: the checked-in CSV traverses resolver → deterministic owners → dynamically loaded interpreter/reviewer → both human gates → complete P7, then resumes without repeating sealed phases. Revise the existing canonical demo rather than add a second demo.

## Focused RED

- Command: `uv run --extra test pytest tests/test_workflow.py::test_resolver_is_pure_and_reports_durable_resume_detail tests/test_workflow.py::test_resolved_reasoning_owner_is_loaded_and_invoked_once tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`
- Corrected decisive result after deleting the obsolete runner-bound tests: `5 failed, 1 passed in 0.47s` (exit 1). Three cases fail because the pure resolver/owner invocation boundary does not exist; the public demo and completed-case invalidation fail because `run_workflow` has no `invoke` boundary. The same focused contract retains the trailing README, positive completion/relative-link, and bare-URL assertions for the serializer defects.
- Changed test files: `tests/test_workflow.py`, `tests/test_pipeline_walk.py`, `tests/test_review.py`.

## Estimated line effect

- Production: approximately `+250/-550`, net **-300** lines (new pure resolver/registry and attempt functions replace the 1,008-line runner/product pair and unused APIs).
- Tests: approximately `+90/-120`, net **-30** lines (focused resolver/dynamic-owner and positive serializer assertions replace synthetic handler-map/full-pipeline compositions).
- Product docs: approximately `+12/-24`, net **-12** lines (PRD and installed skill describe the six-step method and delete the old runner/handler-map prose).
- Jeff notes/context: approximately `+145/-0`, net **+145** planning lines. These are planning estimates; final handoff must report measured added/deleted/net counts for production, tests, docs/evidence, and Jeff state.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No bundled Python-specific skill is present.
