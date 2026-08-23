# Notes

## Recovery plan decision

- Complexity: `complex`.
- Audit required: `true`. The recovery routes caller-supplied journalist and independent-review identities through the installed dispatcher and changes the fail-closed behavior of both editorial approval boundaries. The audit is limited to identity validation, gate bypass, path portability, and credential-safe failure persistence; detector execution and the other existing trust boundaries remain unchanged.
- Selected authority: retain `anomaly.workflow.WorkflowRunner` as the only owner of `.anomaly/state.json` phase, status, attempts, completion, invalidation, pause, and retry fields. Validated domain artifacts and Gate A/Gate B receipts remain owned by their APIs. `.anomaly/events.jsonl` remains best-effort observational history, and `.anomaly/attempts/` remains relative per-attempt evidence.
- Public contract: `anomaly.workflow.run_workflow(root, *, inputs=None)` owns a production-built, complete P0–P7 handler composition. The public dispatcher no longer accepts caller-built phase mappings. It validates the complete production composition before executing and never substitutes a no-op for a missing handler.
- Pause contract: absent sources or human input returns durable `status: paused` with `awaiting_input` set to `sources`, `gate_a`, `review`, or `gate_b`; a pause is neither phase completion nor a failed attempt. A later call supplies only the awaited input and resumes the same authoritative state. Source registration metadata, Gate A approved IDs/identity, independent reviewer/verdict/attestation, and Gate B accepted IDs/journalist identity are explicit caller inputs; no production identity is hard-coded.
- Canonical order: P5 drafts claims, P6 replays and records independent review, Gate B validates journalist acceptance, and P7 writes the report/charts. The checked-in demo retains that exact order.
- Refactor opportunity: delete the public dispatcher's caller-injected/no-op handler fallback and delete direct `.anomaly/state.json` writes from `approve_detector_plan`, `accept_findings`, and `write_report`, harmonizing all phase/status/attempt ownership under `WorkflowRunner`.
- Decomposition: the dispatcher cutover, API ownership deletion, pause/resume inputs, invalidation proof, and documentation alignment are one coupled recovery slice set. Splitting them would temporarily preserve either a fail-open entry or competing state writers, so no independently shippable split is proposed.

## Ordered slices

1. Keep the revised proof contract: Gate A, Gate B, and report APIs must produce their artifacts/receipts while leaving workflow state byte-for-byte unchanged; the public dispatcher must not complete without required inputs.
2. Replace `run_workflow`'s optional caller mapping with a production-owned exact P0–P7 composition over the existing case/acquire/prepare/profile/recommend/detect/review/report APIs. Validate the composition before starting and fail closed if any required handler is absent or non-callable; retain handler injection only on `WorkflowRunner` for isolated runner tests.
3. Add runner-owned durable pause/resume handling and consume explicit `inputs` for sources, Gate A, independent review, and Gate B. Pauses must not consume the three failure attempts; actual phase failures still persist exactly three credential-redacted failure records and relative attempt paths before becoming unavailable/blocked.
4. Remove phase/status writes from `approve_detector_plan`, `accept_findings`, and `write_report`; after each domain call succeeds, let `WorkflowRunner` alone commit completion, identities, phase, status, and attempts. Preserve the APIs' existing artifact validation and receipt ownership.
5. Retain the existing identity invalidation implementation where the strengthened matrix passes it; otherwise repair only the earliest-phase mapping/deletion needed so every downstream `completed` entry is removed and resume executes exactly the expected suffix.
6. Align `PRD.md` and `skills/anomaly/SKILL.md` with state plus validated identities as resume authority, receipts as artifact/approval evidence, and events as observational only. Document the production dispatcher and explicit pauses without a caller-built handler table, preserving P5 → P6 → Gate B.

## Acceptance-criterion dispositions

1. **One documented entry and non-conflicting stores — `revise`.** Consumer behavior: `run_workflow` uses its installed complete composition, pauses on missing input instead of completing, and is the only phase/status/attempt writer; Gate/report APIs leave state unchanged. Deterministic seams: `test_public_dispatcher_fails_closed_without_required_inputs`, `test_approval_records_gate_a_artifacts_without_mutating_workflow_state`, `test_gate_b_owns_accepted_artifacts_and_receipt_without_mutating_workflow_state`, and the report state assertion in `test_report_preserves_unresolved_work_and_contains_only_accepted_findings`.
2. **Mutation survives event failure — `reuse`.** Consumer behavior: a successful artifact plus runner transition remains resumable when event append is unavailable. Deterministic seam: existing `test_successful_mutation_remains_resumable_when_event_store_is_unavailable`.
3. **Exactly three durable attempts on the installed path — `revise`.** Consumer behavior: invalid P1 registration through public `run_workflow` produces exactly three structured relative failure paths and ends unavailable/blocked. Deterministic seam: revised `test_installed_runner_persists_three_failed_attempts_and_blocks`.
4. **Earliest complete downstream invalidation — `revise`.** Consumer behavior: each of the nine source/artifact/approval mutations removes every completion from the expected phase onward, and resume executes exactly that suffix once. Deterministic seam: strengthened parameterized `test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase`.
5. **One P5/P6 order — `revise`.** Consumer behavior: the public demo observes draft before replay, replay before independent review, and review before Gate B acceptance. Deterministic seam: API-event order in `test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work`; canonical PRD/SKILL prose is revised in the implementation slice rather than asserted as source text.
6. **Checked-in complete demo and deterministic resume — `revise`.** Consumer behavior: the checked-in CSV drives the public dispatcher through explicit Gate A, review, and Gate B pauses to report/charts; a fresh no-input call repeats no completed work. Deterministic seam: revised `test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work`.
7. **Existing deterministic contracts and portable paths — `reuse`.** Consumer behavior: existing case, detector, artifact, and receipt APIs retain their formats; structured attempt paths remain relative. Deterministic seams: the checked-in demo plus the relative-path assertions in the installed retry test.

## Test changes

- `tests/test_pipeline_walk.py` — public fail-closed dispatch, staged public pause/resume demo, installed retry behavior, and full downstream deletion/exact-suffix rerun.
- `tests/test_recommend.py` — Gate A artifact/receipt ownership with unchanged workflow state.
- `tests/test_review.py` — Gate B and report artifact ownership with unchanged workflow state.
- `tests/test_skill.py` — deleted the source-text-only handler wiring/order assertion; public behavior now owns that proof.
- `tests/fixtures/orchestration_demo.csv` — reused unchanged.

## Decisive RED

- Command: `uv run pytest tests/test_pipeline_walk.py tests/test_recommend.py::test_approval_records_gate_a_artifacts_without_mutating_workflow_state tests/test_review.py::test_gate_b_owns_accepted_artifacts_and_receipt_without_mutating_workflow_state tests/test_review.py::test_report_preserves_unresolved_work_and_contains_only_accepted_findings tests/test_skill.py -q`
- Result: `6 failed, 18 passed in 1.66s` (exit 1).
- Missing production behavior: no-input `run_workflow` falsely returns `complete`; `run_workflow(..., inputs=...)` is absent; the installed retry contract cannot enter production composition.
- Competing production behavior: Gate A changes P0 to P4/Gate A, Gate B changes P0 to P7/Gate B, and `write_report` changes active to complete. Each failure occurs after its fixture successfully produces the expected plan, receipt, findings, or report artifact.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No matching Python-specific bundled skill is present in the supplied skill inventory.

## Existing ledger condition

Task 20 remains pre-existing invalid ledger state and is outside task 25's edit scope.
