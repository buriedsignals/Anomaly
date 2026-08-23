# Notes

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
