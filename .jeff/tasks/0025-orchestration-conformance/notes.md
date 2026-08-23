# Notes

## Plan decision

- Complexity: `complex`.
- Audit required: `false`. The selected work changes orchestration ownership and documentation only; it does not change detector execution, path containment, DuckDB isolation, credentials, acquisition networking, or another trust boundary. If implementation crosses one of those boundaries, audit becomes required.
- Selected authority: wire the existing `anomaly.workflow.WorkflowRunner`/`run_workflow` path into the installed skill rather than add receipt-derived state or another runtime layer. `state.json` is the resumable phase/attempt/fingerprint authority; validated receipts bind artifacts and approvals; `events.jsonl` is best-effort observational history; `.anomaly/attempts/` retains relative per-attempt evidence.
- Canonical order: P5 drafts claims, then P6 replays calculations and obtains the independent review, then Gate B promotion occurs. This preserves PRD phase numbering, replay-before-promotion, and reviewer separation with fewer changes than renumbering phases.
- Refactor opportunity: harmonize Gate A/Gate B and decorated API transition writes under `WorkflowRunner`, deleting duplicate direct phase/state ownership from `approve_detector_plan`, `accept_findings`, and phase-event callers once every installed call is routed through `run_workflow`.
- Decomposition: keep this as one independently shippable task. Durable authority, retries, invalidation, P5/P6 alignment, and the demo are coupled by the same end-to-end proof; no shared conformance package or second task is warranted.

## Ordered slices

1. Make the existing runner the installed dispatcher authority: route the documented phase handlers through `anomaly.workflow.run_workflow`, make event appends non-authoritative/best-effort, persist structured failure records with relative attempt paths, and remove competing phase/state writes.
2. Persist and reconcile validated artifact/receipt identities at phase completion so a fresh `WorkflowRunner` invalidates from P1 source, P2 prepared generation, P3 parameters/Gate A, P4 detector identity, P5 draft, or P6 replay/review/Gate B.
3. Harmonize `PRD.md`, `skills/anomaly/SKILL.md`, decorators, and tests on P5 draft → P6 replay/review → Gate B; retain independent reviewer and human approval rules.
4. Use `tests/fixtures/orchestration_demo.csv` through the installed runner for create-to-charts, prove a second session performs no completed work, and prove every mutation seam deterministically.

## Acceptance-criterion dispositions

1. **One documented entry and non-conflicting stores — `revise`.** Consumer behavior: invoking the installed Anomaly skill routes all phase work through `anomaly.workflow.run_workflow`; a reopened case reports the same phase and status from `state.json`. Seam: `test_skill_local_invocation_wires_the_durable_runner_and_returns_a_portable_case` plus the demo's fresh-runner equality assertion. Receipts remain artifact/approval validators, events remain observational, and attempt directories remain audit evidence.
2. **Mutation survives event failure — `write`.** Consumer behavior: a successfully registered source is complete and is not repeated after `events.jsonl` becomes unavailable. Seam: `test_successful_mutation_remains_resumable_when_event_store_is_unavailable`.
3. **Exactly three durable attempts — `write`.** Consumer behavior: the installed runner returns `blocked` or `unavailable` after attempt 3 and exposes three structured, portable failure/attempt records. Seam: `test_installed_runner_persists_three_failed_attempts_and_blocks`.
4. **Earliest downstream invalidation — `write`.** Consumer behavior: a fresh session marks the case active and removes completion beginning at P1/P2/P3/P4/P5/P6 according to the changed source, prepared generation, parameters/approval, detector identity, draft, or replay/review/approval artifact. Seam: the parameterized `test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase`.
5. **One P5/P6 order — `revise`.** Consumer behavior: installed instructions and emitted API events show draft before replay, while accept remains after replay and independent review. Seams: `test_skill_local_invocation_wires_the_durable_runner_and_returns_a_portable_case`, `test_case_walk_appends_phase_events_for_every_mainline_call`, and the demo event-order assertions. `PRD.md` is reused because it already defines P5 draft then P6 replay/review.
6. **Checked-in complete demo and deterministic resume — `revise`.** Consumer behavior: the checked-in CSV completes create through charts and a new runner performs no completed handler again. Seam: `test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work`.
7. **Existing deterministic contracts and portable paths — `reuse`.** Consumer behavior: the product-owned APIs and detector execution remain unchanged, while attempt paths asserted by the new test remain relative. Seam: the targeted demo uses the existing real modules and checked-in built-in detector path; no new detector/source/report contract test is owed.

## Decisive RED

- Command: `uv run pytest tests/test_pipeline_walk.py tests/test_skill.py tests/test_events.py -q`
- Result: `12 failed, 14 passed in 1.17s` (command exit 1).
- Missing-contract evidence: event-store failure raises `IsADirectoryError` before the successful phase can commit; failure history contains strings rather than structured attempt/path records; all nine source/artifact/approval mutations reopen as `complete` rather than invalidating; the installed skill does not name `anomaly.workflow.run_workflow`.

## Existing ledger condition

Task 20 is pre-existing invalid ledger state: it is recorded `done` with a non-green gate, and its journal records the absent external GAIN fixture baseline. It was not edited, repaired, or pruned. `cook validate` therefore remains independently red outside task 25.
