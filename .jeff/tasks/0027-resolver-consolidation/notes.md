# Notes

Task 27 remains a consolidation task. The first recovery cycle repairs the surviving consumer contracts in the current resolver/owner/attempt shape; it does not restore `WorkflowRunner`, `product_workflow`, injected handler maps, compatibility aliases, or synthetic all-P0-P7 compositions.

## Plan decision

- **Complexity:** `complex`.
- **Audit required:** `true`.
- **Approach:** retain `run_workflow` as the only public dispatcher, `resolve_workflow` as the pure decision, the single fixed owner registry, `consume_owner` as the one-owner boundary, and `run_attempts` as the durable execution utility. Repair input capability derivation, human-turn binding, attempt staging/promotion, containment, identities, redaction, and README projection at those owners instead of adding a runner.
- **AC3 reconciliation:** extend the existing fixed phase registry with each owner's bounded writable artifact set. `run_attempts` creates a case-shaped workspace under the numbered attempt directory, runs the selected owner against that workspace, scans and validates the staged result, records a durable promotion journal plus rollback copies, promotes only the declared artifacts, and seals state last. An interrupted promotion is recovered from that journal before fresh resolution. The owner registry remains the single phase metadata source; there is no second loop, handler composition API, result class, or all-P0-P7 test harness.
- **Turn binding:** schema validation produces the resolver's set of complete input capabilities. `now` is required for P1-P4, Gate A/B capabilities exist only for complete decision mappings, and a human decision is eligible only when its gate was the entry phase of the current invocation. A future decision is not persisted or carried after an intervening phase; the dispatcher returns the gate pause with no gate attempt consumed.
- **Containment:** put the whole-tree scan at `inspect_case` and `resume_case`, which already own public case reads and are upstream of direct writers; scan staged work after a dynamic owner returns and before any promotion, state write, or event append. `UnsafeCasePathError` escapes attempt retry/evidence writes when the durable namespace cannot be trusted.
- **Identity and redaction:** require every identity whose phase is marked complete, treat a missing digest or missing artifact as a change from its owning phase, use `canonical_key` for all cross-role comparisons, and move the broader assignment/Bearer/provider/userinfo redactor to one shared sanitizer used by state, attempts, events, and review.
- **README:** remove and replace only the bounded `anomaly:outputs` marker block. Never delete an unmarked block by content equality. P7 artifacts and README completion are promoted together only after the full P7 attempt validates; failure projects the last sealed phase while preserving all journalist content.

## Ordered slices

1. **Input and turn boundary:** make P1-P4 `now` requirements complete, derive capabilities only from schema-valid source/Gate A/Gate B values, bind Gate A/B decisions to an invocation that starts at that gate, and keep human pauses attempt-free.
2. **Atomic attempts without a runner:** add phase write sets to the existing owner registry; execute deterministic and dynamic owners in numbered attempt workspaces; validate, journal, promote or roll back the declared artifacts; recover an interrupted promotion before resolution; keep exactly-three retry evidence.
3. **Containment, identity, and secrets:** scan every public resume/inspect/direct-writer entry and immediately after dynamic work; rethrow unsafe-path failures without writing through the compromised tree; require complete artifact identities; compare role identities canonically; reuse one broad credential sanitizer everywhere durable errors can land.
4. **README and P7 lifecycle:** stop global legacy Outputs replacement, preserve exact journalist-authored matching Markdown on completed restart/invalidation/failure/recompletion, and keep incomplete P7 outputs out of the live case.
5. **Proof and deletion preservation:** retain the six P3-P6 identity invalidation cases, source replacement, retry/event-resume, dynamic-owner/order/demo and bare-URL proof; do not restore deleted orchestration, aliases, duplicate projections, or synthetic phase compositions.

## Surviving blocker union

Duplicate review, standards, audit, and refute statements are combined only where they identify the same reachable defect.

1. **Future Gate A/B decisions cross turns — repair / `tests/test_pipeline_walk.py`.** A decision supplied before P3 or P6 completes must not become actionable later in the same call. Deterministic seams: `test_gate_a_decision_supplied_before_gate_is_not_carried_across_the_turn` and `test_gate_b_decision_supplied_before_review_is_not_carried_across_the_turn`.
2. **Missing-input resolution is incomplete and schema-blind — repair / `tests/test_workflow.py`, `tests/test_pipeline_walk.py`.** Missing P1-P4 clocks and incomplete Gate A/B mappings pause with truthful `awaiting_input` and consume no phase attempt. Seams: `test_resolver_reports_incomplete_phase_input_before_attempt`, `test_missing_now_pauses_before_p1_attempts_are_consumed`, and both `test_incomplete_gate_*_decision_pauses_without_consuming_an_attempt` cases.
3. **Owners mutate live state before an attempt succeeds — repair / `tests/test_pipeline_walk.py`.** A failed multi-source P1 batch leaves no earlier source live; a failed P7 leaves no Gate B receipt/findings/report live; an unsafe dynamic attempt leaves no draft live. Seams: `test_failed_multi_source_attempt_does_not_promote_an_earlier_source`, `test_failed_p7_attempt_does_not_promote_outputs_or_delete_journalist_content`, and the between-owner containment test.
4. **README global replacement deletes authored content — repair / `tests/test_pipeline_walk.py`.** An unmarked journalist block exactly equal to the historical Outputs block survives completed restart; marker-owned output links still resolve. Seam: revised checked-in demo test.
5. **Public case readers/direct writers omit whole-case scanning — repair / `tests/test_case.py`, `tests/test_acquire.py`.** `inspect_case`, `resume_case`, and direct registration reject any nested link before reading or overwriting case artifacts. Seams: `test_public_case_reader_rejects_a_nested_symlink` and `test_register_local_source_rejects_an_in_case_destination_symlink`.
6. **The dispatcher does not rescan after dynamic ownership — repair / `tests/test_pipeline_walk.py`.** A callback-created event-store link raises before external mutation or live draft promotion. Seam: `test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns`.
7. **Casefold-only role checks admit canonical-equivalent identities — repair / `tests/test_pipeline_walk.py`.** NFC-equivalent Gate A/reviewer and reviewer/Gate B spellings are the same identity and are rejected. Seams: both `test_public_dispatcher_rejects_canonical_*` tests.
8. **Missing authoritative identities are trusted — repair / `tests/test_pipeline_walk.py`.** A sequential P7 state without its required identity map is invalidated from P1 and cannot resolve complete. Seam: `test_completed_snapshot_without_required_identities_fails_closed_from_p1`.
9. **Durable attempt errors leak common credentials and lost proof — repair / `tests/test_pipeline_walk.py`.** Bearer, assignment, AWS, Slack, and URL-userinfo secrets are absent from failure JSON, events, state failures, and blocked reason across three attempts. Seam: `test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence`; the existing P1/P3 retry tests retain three-attempt and relative-path proof.
10. **P3-P6 invalidation coverage was deleted — test repair / `tests/test_pipeline_walk.py`.** Recommendation/P3, Gate A/P4, detector/P4, draft/P5, replay/P6, and review/P6 changes each clear only their earliest suffix. Seam: `test_changed_p3_p6_identity_invalidates_only_its_earliest_suffix`; no fake rerun or injected handlers return.
11. **README completed/failure lifecycle proof is incomplete — test repair / `tests/test_pipeline_walk.py`.** Completed restart preserves the exact authored legacy-shaped block; invalidation and recompletion preserve notes; failed P7 preserves notes and never claims P7. Seams: revised demo, Gate B invalidation, and failed-P7 tests.
12. **Bare URL proof used only embedded URLs — test repair / `tests/test_review.py`.** A standalone dataset URL remains readable as escaped text but cannot autolink. Seam: revised inert-Markdown test.

## Acceptance-criterion dispositions

1. **AC1 pure resolver — `revise`.** Observable behavior: the decision stays pure and immutable while complete P1-P4 clock and gate capabilities yield `paused`, singular `missing`, zero consumed attempts, and truthful resume fields. Deterministic outcome: resolver parameter cases plus public missing-now/incomplete-gate cases.
2. **AC2 owner registry/dynamic loading — `reuse`.** Observable behavior: fixed P5 skill/P6 persona loading and one selected invocation remain unchanged. Deterministic outcome: existing `test_resolved_reasoning_owner_is_loaded_and_invoked_once` and checked-in demo.
3. **AC3 durable staging/retries/failure evidence — `revise`.** Observable behavior: failed owners cannot partially promote live artifacts; three attempts and relative evidence remain durable; every error field is redacted; event failure does not undo sealed success. Deterministic outcome: new P1/P7/dynamic failure tests plus existing P1/P3 retry and event-store-resume tests.
4. **AC4 gates, identities, invalidation, source replacement, order — `revise`.** Observable behavior: both gates require a fresh turn; canonical identities stay independent; all P3-P6 identity classes invalidate their earliest suffix; source replacement and exact P5→P6→Gate B→P7 ordering remain. Deterministic outcome: new gate/canonical/matrix tests plus existing source replacement and demo event order.
5. **AC5 README projection — `revise`.** Observable behavior: only marker-owned output content changes; authored content survives completed restart, invalidation, failed recomputation, and recompletion; successful P7 links are relative and resolving. Deterministic outcome: revised demo, Gate B invalidation, and failed-P7 tests.
6. **AC6 inert Markdown — `revise`.** Observable behavior: dataset HTML, headings, Markdown links, and standalone HTTP(S) URLs cannot become active markup while visible URL text remains. Deterministic outcome: revised report serialization test. Production escaping is reused.
7. **AC7 whole-case no-symlink — `write`.** Observable behavior: public inspect/resume/direct registration and between-owner continuation reject nested links before any protected read/write. Deterministic outcome: new case, acquisition, and dynamic-owner containment tests.
8. **AC8 obsolete surfaces removed — `delete`.** Observable behavior: none; the deleted runner/product loop/aliases/duplicate projections and synthetic tests stay absent. Deterministic outcome: all focused public behavior is expressed without restoring those surfaces; no symbol-absence test is added.
9. **AC9 one demo CSV — `revise`.** Observable behavior: the existing checked-in CSV still crosses deterministic owners, dynamic skill/persona, both human gates, completion, relative outputs, restart, and exact event order while preserving authored README content. Deterministic outcome: revised canonical demo test; no second demo is added.

## Test ownership

- `tests/test_workflow.py` — pure complete missing-input resolver matrix.
- `tests/test_pipeline_walk.py` — gate-turn/schema pauses, P1/P7 atomicity, durable redaction, P3-P6 invalidation, required identities, canonical roles, README lifecycle, source replacement, retries, dynamic containment, and demo/order.
- `tests/test_case.py` — public inspect/resume whole-tree containment.
- `tests/test_acquire.py` — direct source-writer destination-link containment.
- `tests/test_review.py` — standalone bare-URL inertness.

## Focused RED

- Command: `uv run --extra test pytest tests/test_workflow.py::test_resolver_reports_incomplete_phase_input_before_attempt tests/test_pipeline_walk.py::test_missing_now_pauses_before_p1_attempts_are_consumed tests/test_pipeline_walk.py::test_incomplete_gate_a_decision_pauses_without_consuming_an_attempt tests/test_pipeline_walk.py::test_incomplete_gate_b_decision_pauses_without_consuming_an_attempt tests/test_pipeline_walk.py::test_gate_a_decision_supplied_before_gate_is_not_carried_across_the_turn tests/test_pipeline_walk.py::test_gate_b_decision_supplied_before_review_is_not_carried_across_the_turn tests/test_pipeline_walk.py::test_public_dispatcher_persists_three_failed_attempts_and_blocks tests/test_pipeline_walk.py::test_failed_reasoning_attempts_redact_credentials_from_all_durable_evidence tests/test_pipeline_walk.py::test_failed_multi_source_attempt_does_not_promote_an_earlier_source tests/test_pipeline_walk.py::test_public_dispatcher_retries_recommendation_failure_inside_p3 tests/test_pipeline_walk.py::test_public_dispatcher_replaces_changed_registered_source tests/test_pipeline_walk.py::test_changed_p3_p6_identity_invalidates_only_its_earliest_suffix tests/test_pipeline_walk.py::test_completed_snapshot_without_required_identities_fails_closed_from_p1 tests/test_pipeline_walk.py::test_public_dispatcher_rejects_canonical_gate_a_approver_as_reviewer tests/test_pipeline_walk.py::test_public_dispatcher_rejects_canonical_reviewer_as_gate_b_journalist tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_pipeline_walk.py::test_failed_p7_attempt_does_not_promote_outputs_or_delete_journalist_content tests/test_pipeline_walk.py::test_dispatcher_rechecks_containment_after_a_reasoning_owner_returns tests/test_case.py::test_public_case_reader_rejects_a_nested_symlink tests/test_acquire.py::test_register_local_source_rejects_an_in_case_destination_symlink tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`
- Exact result: `19 failed, 13 passed in 2.34s` (exit 1).
- Failures are decisive for the uncovered contracts: P1-P3 resolve ready without `now`; public missing/incomplete inputs consume attempts; future gates cross turns; five credential forms persist; P1 and P7 partially promote; missing identities remain complete; canonical-equivalent roles pass; completed restart deletes the authored legacy-shaped Outputs block; dynamic and public containment scans do not fire. The 13 passes retain retries, source replacement, all six P3-P6 change boundaries, Gate B invalidation/recompletion, dynamic order, and standalone bare-URL escaping.

## Refactor opportunity

Behavior-preserving harmonization is owed: make the existing owner registry the sole owner of both dispatch and bounded write sets, and replace the duplicate narrow state/review credential regexes with one shared sanitizer. Keep `run_attempts` as the only staging/promotion utility and delete any superseded live-root mutation path or sanitizer after migrating every caller. Do not add aliases, a runner class, a second phase registry, or compatibility composition.

## Skill inputs

- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/code-standards/SKILL.md`
- `/Users/tomvaillant/.omp/plugins/node_modules/@johanthoren/jeff/skills/testing/SKILL.md`
- No bundled Python-specific skill is present.

## Full-gate stale-contract recovery plan

- **Accepted lineage:** the clean recovered gate at `709b177a6c73d74a3746c3e9317af974378f27ba` recorded `735/736` green. Its sole failure was `tests/test_workflow.py::test_resolver_is_pure_and_reports_durable_resume_detail`, whose call omitted the accepted P3 `now` capability while still expecting a ready result.
- **Approach:** migrate only that existing pure-resolver call to declare `now`; retain its exact ready owner, attempt-3 resume detail, invalidation detail, and input-snapshot purity assertions. Do not alter production or add another test because `test_resolver_reports_incomplete_phase_input_before_attempt` already proves that absence of `now` pauses.
- **Slice:** test-only stale-fixture repair in `tests/test_workflow.py`, followed by the existing ready/purity test and existing missing-input resolver test.
- **Complexity:** `complex`, inherited from task 27 and its accepted recovery.
- **Audit required:** `true`; this recovery cannot lower the task's existing audit floor.
- **Refactor opportunity:** `null`; a one-capability fixture migration owes no behavior-preserving deduplication, deletion, or harmonization.

### Recovery acceptance-criterion dispositions

1. **AC1 pure resolver — `revise`.** Consumer-observable behavior: a P2-complete snapshot with two durable P3 attempts resolves P3 ready at attempt 3 when `now` is explicitly supplied, without mutating the snapshot; omission of `now` still pauses. Deterministic seams: `test_resolver_is_pure_and_reports_durable_resume_detail` and `test_resolver_reports_incomplete_phase_input_before_attempt`.
2. **AC2 owner registry/dynamic loading — `reuse`.** Consumer-observable behavior: P3 still resolves to the fixed `recommend-detectors` handler and reasoning phases retain dynamic loading. Deterministic seams: the exact owner assertion in the revised resolver test and `test_resolved_reasoning_owner_is_loaded_and_invoked_once`.
3. **AC3 durable attempts — `reuse`.** Consumer-observable behavior: two recorded P3 attempts produce the unchanged `attempt 3 of 3` resume detail; execution and promotion behavior is untouched. Deterministic seam: the exact resolution assertion in the revised resolver test; the existing retry/promotion tests remain unchanged.
4. **AC4 gates, identities, invalidation, replacement, and order — `reuse`.** Consumer-observable behavior: `invalidated_from: P3` remains in the ready result and all public workflow boundaries are untouched. Deterministic seam: the revised exact result plus the existing focused pipeline-walk cases.
5. **AC5 README projection — `reuse`.** Consumer-observable behavior: no projection path changes. Deterministic seam: the existing demo, invalidation, recompletion, and failed-P7 cases remain unchanged.
6. **AC6 inert Markdown — `reuse`.** Consumer-observable behavior: report serialization is untouched. Deterministic seam: the existing standalone bare-URL report case remains unchanged.
7. **AC7 whole-case no-symlink — `reuse`.** Consumer-observable behavior: containment entry points are untouched. Deterministic seam: the existing case, acquisition, and dynamic-owner containment cases remain unchanged.
8. **AC8 obsolete surfaces removed — `reuse`.** Consumer-observable behavior: no production surface is added or restored. Deterministic seam: the test-only diff and existing focused public behavior remain the proof; no symbol-absence test is added.
9. **AC9 one demo CSV — `reuse`.** Consumer-observable behavior: the canonical demo and its six-step path are untouched. Deterministic seam: the existing checked-in demo case remains unchanged.

### Recovery evidence

- **Recorded RED command:** `uv run --extra test pytest tests/`
- **Recorded RED output:** `735 passed, 1 failed`; sole failure `tests/test_workflow.py::test_resolver_is_pure_and_reports_durable_resume_detail` (exit 1).
- **Targeted GREEN command:** `uv run --extra test pytest tests/test_workflow.py::test_resolver_is_pure_and_reports_durable_resume_detail tests/test_workflow.py::test_resolver_reports_incomplete_phase_input_before_attempt`
- **Targeted GREEN output:** `6 passed in 0.06s` (exit 0).
