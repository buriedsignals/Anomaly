# Notes

## Stale event-contract repair

- Recovery kind: `test-contract-repair`.
- Complexity: `simple`.
- Audit required: `true`; retain the causal recovery's already-required audit. This test-only repair does not add audit scope.
- Refactor opportunity: `null`; production already owns the canonical replay/review sequence, and no behavior-preserving production cleanup is owed.
- Ordered slice: revise only the direct mainline event expectation so completed P6 review is followed by P7 acceptance without a second P6 replay, preserving every other phase-event assertion.

### Acceptance-criterion dispositions

1. **One documented entry and non-conflicting stores — `reuse`.** Consumer behavior remains the public `run_workflow` authority with runner-owned phase state. Deterministic seams remain `test_public_dispatcher_fails_closed_without_required_inputs` and `test_workflow_runner_rejects_incomplete_or_noncallable_composition`.
2. **Mutation survives event failure — `reuse`.** A successful durable mutation remains resumable when best-effort event storage is unavailable. Deterministic seam: `test_successful_mutation_remains_resumable_when_event_store_is_unavailable`.
3. **Exactly three installed-path attempts — `reuse`.** P1 and P3 failures retain exactly three durable attempts and terminate blocked/unavailable. Deterministic seams: `test_installed_runner_persists_three_failed_attempts_and_blocks` and `test_public_dispatcher_retries_recommendation_failure_inside_p3`.
4. **Earliest downstream invalidation — `reuse`.** Existing source, prepared, gate, and artifact mutations retain their earliest affected suffix. Deterministic seams: `test_public_dispatcher_rebuilds_stale_plan_after_prepared_change`, `test_public_dispatcher_replaces_changed_registered_source`, `test_public_dispatcher_invalidates_changed_gate_b_from_p7`, and `test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase`.
5. **Canonical P5/P6 order and independent review — `revise`.** The direct API event stream contains P5 draft, one P6 replay, P6 independent review, then P7 acceptance; `accept_findings` after completed review emits no redundant P6 replay. Deterministic seam: `test_case_walk_appends_phase_events_for_every_mainline_call`, with all other phase-event assertions retained.
6. **Checked-in demo, resume, and mutation — `reuse`.** The checked-in CSV continues through the public dispatcher and resumes without repeated completed work. Deterministic seam: `test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work`.
7. **Existing deterministic contracts and portable paths — `reuse`.** Existing modules, case shape, detector contracts, and relative attempt paths remain unchanged. Deterministic seams: `test_installed_runner_persists_three_failed_attempts_and_blocks` and the recorded full-suite gate.

### RED/GREEN disposition

- Decisive recorded RED: `uv run --extra test pytest tests/` returned `1 failed, 721 passed`; the sole failure was `tests/test_events.py::test_case_walk_appends_phase_events_for_every_mainline_call`, whose expected stream still contained a second `("P6", "replay_signals")` before P7 acceptance.
- Targeted GREEN after revising only that expectation: `uv run --extra test pytest tests/test_events.py::test_case_walk_appends_phase_events_for_every_mainline_call -q` returned `1 passed in 0.12s`.
- Revised test file: `tests/test_events.py`.

## Recovery decision

- Complexity: `complex`.
- Audit required: `true`. This recovery changes the caller-controlled `.anomaly` containment boundary and retains public cross-gate identity validation. Audit scope is containment before durable writes, gate separation, source-replacement ownership, portable attempt paths, and credential-redacted failures.
- Selected recovery: `causal-subgraph-reconstruction`, confined to the dispatcher, durable runner, phase-artifact invalidation/recovery, and P7 completion projection.
- Public authority: `anomaly.workflow.run_workflow(root, *, inputs=None)` remains the only documented product entry. `WorkflowRunner` remains the durable state/attempt executor but must reject an absent, partial, or non-callable composition when asked to run a workflow; explicit single-phase handlers remain a focused unit-test seam.
- Phase boundaries: runner-owned P3 recommendation completes before the Gate A pause; Gate A is consumed at P4. P6 replay/review completes before the Gate B pause; Gate B is consumed at P7. Gate A and Gate B identity changes therefore invalidate from P4 and P7 respectively.
- Refactor opportunity: extract the production P0–P7 composition plus input/gate policy from the 922-line `src/anomaly/workflow.py` into one focused `src/anomaly/product_workflow.py` module, leaving the durable runner and state primitives in `workflow.py`; delete `_ensure_recommendation`, no-op handler fallback, and the weightless `Workflow`/`DurableWorkflow` aliases. The public `anomaly.workflow.run_workflow` path remains unchanged.
- The eight blockers are one coupled recovery. Splitting would temporarily leave either recommendation outside retry ownership, a fail-open runner, stale artifact reuse, or premature finalization, so there is no independently shippable decomposition.

## Ordered slices

1. Enforce the trust and execution boundary before mutation: reject a symlinked/non-contained `.anomaly` before runner construction or durable-tree creation, and make `WorkflowRunner.run()` validate an exact callable P0–P7 composition instead of substituting no-ops.
2. Move product composition/input policy into one focused module. Run recommendation as the P3 handler under the existing three-attempt durable boundary, commit P3, then pause for Gate A; apply Gate A before P4. Keep replay/review in P6, then pause for Gate B before P7. Preserve explicit caller identities and reject equal cross-gate identities.
3. Bind artifacts to their producing/consuming phases: an invalidated P3 always recomputes and overwrites the plan rather than accepting file presence; Gate A/Gate B map to P4/P7; a supplied source with an existing canonical ID performs one validated atomic replacement of its raw payload and manifest record instead of append/duplicate rejection.
4. Make P7 fail closed: produce accepted findings, report body, and charts before projecting README completion from committed P7 state. A chart failure exhausts P7 attempts without writing `Status: complete` or `Last completed phase: P7`. Align PRD/SKILL wording only after behavior is green.

## Blocker proof dispositions

1. **P3 recommendation retry — `write`.** Consumer behavior: a recommendation write failure through `run_workflow` produces exactly three P3 failure attempts and returns unavailable/blocked instead of raising outside the runner. Seam: `test_public_dispatcher_retries_recommendation_failure_inside_p3`.
2. **Stale plan generation — `write`.** Consumer behavior: prepared-generation drift reruns P2 then P3, resets prior approval, and pauses at Gate A with P3 complete. Seam: `test_public_dispatcher_rebuilds_stale_plan_after_prepared_change`.
3. **Cross-gate rejection — `write`.** Consumer behavior: Gate A approver cannot be the independent reviewer, and the reviewer cannot be the Gate B journalist, through caller-supplied public inputs. Seams: `test_public_dispatcher_rejects_gate_a_approver_as_reviewer` and `test_public_dispatcher_rejects_reviewer_as_gate_b_journalist`.
4. **Fail-closed injected runner — `write`.** Consumer behavior: absent, partial, or non-callable phase composition cannot durably complete. Seam: `test_workflow_runner_rejects_incomplete_or_noncallable_composition`.
5. **Executable source replacement — `write`.** Consumer behavior: after registered raw-source drift, supplying the same canonical source ID replaces its payload/record, preserves one registration, recomputes through P3, and pauses at Gate A. Seam: `test_public_dispatcher_replaces_changed_registered_source`.
6. **Gate B at P7 — `revise` plus `write`.** Consumer behavior: changed Gate B invalidates only P7, preserves replay/review bytes, pauses for Gate B, then recompletes. Seams: revised `MUTATIONS` Gate B row plus `test_public_dispatcher_invalidates_changed_gate_b_from_p7`. The Gate A row is likewise corrected to its P4 consumer boundary.
7. **README after whole P7 — `write`.** Consumer behavior: deterministic chart obstruction yields three failed P7 attempts and no README completion claim. Seam: `test_readme_does_not_claim_completion_when_chart_generation_fails`.
8. **Pre-write `.anomaly` containment — `write`.** Consumer behavior: a symlinked `.anomaly` is rejected as an unsafe case path and the target directory remains byte-empty. Seam: `test_public_dispatcher_rejects_anomaly_symlink_before_durable_write`.

## Acceptance-criterion dispositions

1. **One documented entry and non-conflicting stores — `revise`.** Consumer behavior: the documented dispatcher builds the exact product composition; the runner cannot manufacture completion from missing handlers; state owns phase/attempt/status while artifacts and receipts retain their existing roles. Deterministic seams: public demo, missing-input test, and fail-closed runner test.
2. **Mutation survives event failure — `reuse`.** Consumer behavior: committed source plus phase state resumes when best-effort event storage is unavailable. Seam: existing `test_successful_mutation_remains_resumable_when_event_store_is_unavailable`.
3. **Exactly three installed-path attempts — `revise`.** Consumer behavior: both P1 registration and P3 recommendation failures persist three relative attempt paths and end unavailable/blocked. Seams: existing P1 retry test and new P3 retry test.
4. **Earliest downstream invalidation — `revise`.** Consumer behavior: prepared drift rebuilds P3; source drift has an executable replacement; Gate A and Gate B invalidate from P4/P7; existing artifact mutations still delete the exact state suffix. Seams: stale-plan, source-replacement, public Gate B, and revised mutation matrix tests.
5. **Canonical order and independent review — `revise`.** Consumer behavior: P3 precedes Gate A/P4; draft precedes replay/review; Gate B follows independent review and precedes P7; equal cross-gate identities are rejected. Seams: public demo event order and two new identity tests.
6. **Checked-in demo, resume, and mutation — `revise`.** Consumer behavior: the checked-in CSV completes through the public dispatcher, resumes without repeated work, and public mutation cases recover or fail closed deterministically. Seams: existing demo plus stale-plan, source-replacement, Gate B, and chart-failure tests.
7. **Existing deterministic contracts and portable paths — `reuse`.** Consumer behavior: deterministic domain modules, case format, detector contracts, and relative attempt paths remain intact. Seams: existing full suite, checked-in demo, retry path assertions, and containment test.

## Test files

- `tests/test_pipeline_walk.py` — revised Gate A/Gate B consumer-phase matrix and added public P3 retry, stale plan, source replacement, cross-gate identity, Gate B resume, README/chart failure, and `.anomaly` symlink contracts.
- `tests/test_workflow.py` — added fail-closed composition contract.
- `tests/fixtures/orchestration_demo.csv` — reused unchanged.

## Decisive RED

- Command: `uv run pytest tests/test_pipeline_walk.py tests/test_workflow.py -q`
- Result: `11 failed, 18 passed in 2.65s` (exit 1).
- Missing behavior represented by failures: P3 recommendation raises before retry accounting; stale P3 plan remains approved after P2 drift; same-ID source input becomes unavailable; Gate A/Gate B still map to P3/P6; chart failure leaves README complete/P7; `.anomaly` symlink writes escape before a `ValueError`; incomplete runner compositions complete rather than raising.
- The two new public cross-gate identity rejection tests pass against the current guards and now own those consumer-visible contracts.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No matching Python-specific bundled skill is present in the supplied skill inventory.

## Existing ledger condition

- Task 20 remains pre-existing invalid ledger state and is outside task 25's edit scope.

## Terminal council causal-subgraph recovery

- Recovery kind: `causal-subgraph-reconstruction`.
- Complexity: `complex`; the recovery spans durable lifecycle projection, pre-write validation, filesystem containment, and output serialization. The existing dual-review floor remains.
- Audit required: `true`; this cannot lower the previously required audit and directly changes the case-tree and untrusted-text boundaries.
- Approach: keep `state.json` authoritative and make runner transitions project both README completion and demotion; prevalidate all canonical source IDs before the P1 registration loop; invoke the existing case-tree scanner before the public dispatcher reads or writes the case; serialize untrusted claim text as collapsed, escaped Markdown using the standard library; delete the competing completion option/helper and unused compatibility/test aliases. No framework, dependency, phase, or case-format change is warranted.
- Refactor opportunity: delete `WorkflowRunner.read_state`, `read_events`, `invalidate_downstream`, `record_invalidation`, `resume`, and `execute_phase`; delete the `write_report(..., complete_readme=...)` branch and report-owned completion helper after moving projection ownership to the runner; retain the valid report-body assertions but delete their stale direct-completion expectations; and keep the removed `_phase_handlers`/`_completed_demo_with_test_handlers` duplicate test composition removed in favor of the public completed-demo baseline plus one focused P1 handler.

### Ordered slices

1. Make the durable runner the sole README lifecycle owner: after successful P7 transition project complete/P7 plus output links; after any P7 invalidation or failed retry project the state-derived active phase and remove stale completion/output claims. `write_report` writes only `findings/report.md`.
2. Guard mutations and reads at existing boundaries: validate canonical uniqueness across the complete supplied source batch before the first registration/replacement, and call the existing whole-tree scanner before public resume/runner construction.
3. Make accepted claim statements Markdown-inert at report serialization by collapsing line breaks and escaping HTML/Markdown syntax with standard-library primitives; leave fixed report structure and trusted relative output links unchanged.
4. Delete obsolete completion plumbing, unused runner aliases, stale direct-completion expectations, and duplicate test composition; run the targeted suite without weakening the six RED contracts.

### Terminal blocker proof dispositions

1. **F1 README invalidation — `revise`.** Consumer behavior: mutating Gate B on a completed case immediately demotes README to active/P6 while paused, and a subsequent exhausted P7 chart retry never restores or retains complete/P7. Deterministic seams: `test_public_dispatcher_invalidates_changed_gate_b_from_p7` and `test_readme_does_not_claim_completion_when_chart_generation_fails`.
2. **F2 duplicate batch — `write`.** Consumer behavior: case-insensitive duplicate source IDs exhaust the existing three P1 attempts without registering, replacing, or copying either source. Deterministic seam: `test_public_dispatcher_rejects_duplicate_source_batch_before_registration`.
3. **F3 direct report completion — `revise` plus `delete`.** Consumer behavior: direct `write_report` preserves accepted-only report content and unresolved work but leaves README active/P0; only runner-owned successful P7 completion may claim complete/P7. Deterministic seam: `test_write_report_preserves_accepted_work_without_completing_case`, with the old direct-completion assertions deleted; the checked-in public demo reuses the successful P7/charts seam.
4. **F4 whole-tree symlink boundary — `write`.** Consumer behavior: a nested case-controlled `data/sources.json` symlink raises `UnsafeCasePathError` before creation of durable attempt evidence. Deterministic seam: `test_public_dispatcher_rejects_nested_case_symlink_before_durable_write`; the existing `.anomaly` symlink test remains complementary.
5. **F5 Markdown inertness — `write`.** Consumer behavior: dataset text containing an inline link, raw HTML, and a newline heading remains recognizable as claim prose but none of those constructs remains active in `findings/report.md`. Deterministic seam: `test_write_report_serializes_dataset_text_as_inert_markdown`.
6. **Unused aliases and duplicate composition — `delete`/`skip`.** These have no consumer-observable contract, so no symbol-absence/change-detector test is owed. Existing runner and public-dispatch behavior tests remain the proof after deletion.

### Locked acceptance-criterion dispositions

1. **One documented authority and non-conflicting stores — `revise`.** Consumer behavior: runner state alone decides completion/demotion; report helpers cannot independently project P7. Seams: direct report non-completion, public successful demo, and completed Gate B invalidation.
2. **Successful mutation survives event failure — `reuse`.** Consumer behavior and seam remain `test_successful_mutation_remains_resumable_when_event_store_is_unavailable`.
3. **Exactly three installed-path attempts — `revise`.** Consumer behavior: duplicate-batch rejection remains inside P1's three-attempt durable boundary and produces no source mutation. Seam: duplicate-batch test plus existing P1/P3 retry tests.
4. **Earliest downstream invalidation — `revise`.** Consumer behavior: P7 identity drift removes durable P7 and its README projection while preserving P6 review/replay. Seam: revised Gate B invalidation and retry-failure tests.
5. **Canonical P5/P6 order and independent review — `reuse`.** Existing event ordering and independent-identity tests remain unchanged.
6. **Checked-in demo, resume, and mutation — `revise`.** Consumer behavior: the public completed-demo baseline now owns invalidation tests; completed-case Gate B mutation proves paused, failed-retry, and successful-resume projections. Seams: checked-in demo plus the two F1 tests.
7. **Existing deterministic contracts and portable paths — `revise`.** Consumer behavior: the public boundary rejects any case-tree symlink before writes, report text is inert, and relative attempts/case artifacts remain unchanged. Seams: nested and `.anomaly` symlink tests, Markdown test, and existing relative-attempt assertions.

### RED and preservation evidence

- Targeted RED command: `uv run --extra test pytest tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_pipeline_walk.py::test_readme_does_not_claim_completion_when_chart_generation_fails tests/test_pipeline_walk.py::test_public_dispatcher_rejects_duplicate_source_batch_before_registration tests/test_pipeline_walk.py::test_public_dispatcher_rejects_nested_case_symlink_before_durable_write tests/test_review.py::test_write_report_preserves_accepted_work_without_completing_case tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`.
- Decisive result: `6 failed in 0.52s` (exit 1). F1 paused and failed-retry paths retained complete/P7 README; F2 completed to a pause after partial/replacement mutation; F4 reached a later escaping-path `ValueError` instead of the upfront symlink error; F3 direct report writing completed README; F5 retained the raw link, HTML, and newline heading.
- Targeted preservation command: `uv run --extra test pytest tests/test_pipeline_walk.py::test_successful_mutation_remains_resumable_when_event_store_is_unavailable tests/test_pipeline_walk.py::test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase -q`.
- Preservation result: `10 passed in 1.62s`.
- Changed test files: `tests/test_pipeline_walk.py`, `tests/test_review.py`.

### Estimated line effect

- Current test-contract diff: approximately `+112/-92`, net `+20`; the gross deletions include the duplicate P0–P7 test composition and stale completion expectations.
- Expected production recovery: approximately `+50/-40`, net `+10`; this counts moving/generalizing the README projector, four small guards, and deleting obsolete options/aliases.
- Estimated final non-Jeff product/test diff: approximately `+162/-132`, net `+30`; documentation is expected to remain unchanged because its existing authority/order wording already matches the locked contract. These are planning estimates, not a release gate.

### F4 test-contract correction

- `create_case` already guarantees an empty `.anomaly/attempts/` directory (`tests/test_case.py:97-98`). The F4 postcondition therefore asserts that directory remains empty after upfront rejection; it does not require deleting the directory.
- The corrected seam preserves the original pre-implementation RED cause. After implementation began in the shared checkout, the six targeted tests returned `6 passed in 0.45s`.
