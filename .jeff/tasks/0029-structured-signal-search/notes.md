# Task 29 recovery plan

Category: `code`

Complexity: `complex`

Audit required: `true` (unchanged floor)

## Shortest correct approach

Keep the existing public `anomaly.search` API and installed DuckDB dependency. Repair the canonical producer and the derived projection as one coherent contract rather than adding a second indexing path or a compatibility facade.

1. Preserve canonical `signal_id` as the detector/table/candidate evidence identity. Treat a JSONL occurrence as the composite `(signal_id, run_id)`: the projection key is that pair, the public `signal_ref` is exactly `{"path": "evidence/signals.jsonl", "signal_id": ..., "run_id": ...}`, and pagination sorts by descending retrieval score followed by ascending `signal_id` and `run_id`. Reject only a repeated composite pair, not a legitimate signal identity produced by a later run.
2. Make the canonical detector producer persist immutable content-addressed snapshot files beneath `detectors/used`. A snapshot filename ends with its canonical SHA-256 digest; changed detector content therefore uses a different path and cannot overwrite an earlier run's bytes. Schema-v2 provenance must contain both the safe snapshot path and canonical JSON hash. Projection construction resolves that exact provenance path, validates the hash and implementation identity, and includes every referenced snapshot in the manifest input map.
3. Retain the existing public allowlist and shared sanitizer. Return the exact allowlisted signal/detector shape, with sensitive keys absent and credential-bearing public text already redacted. Apply all nine filters independently; validate key types before unknown-key handling. Report every deterministic matching field and set `query_score` from retrieval matches only, never editorial attributes.
4. Keep rebuild explicit. A verified search holds one verified database snapshot/connection through row retrieval or fails closed if a rebuild wins; it never combines rows from projection B with projection A's manifest identity. Replace pathname precheck/reopen flows with pinned/no-follow input handles and a pinned private derived directory using unpredictable staging names, so input and output symlink swaps cannot cross containment.

No new dependency, search abstraction, automatic rebuild, triage state, UI, embedding path, or canonical-evidence write is introduced.

## Ordered slices

1. **Canonical run history and row identity.** Persist content-addressed detector snapshots from `detect.py`, bind required path/hash fields in provenance, resolve them from projection construction, and use `(signal_id, run_id)` for rows, references, cursors, and duplicate validation.
2. **Public query contract.** Preserve the exact redacted result shape; independently apply detector/group/category/severity/source/table/run/date/review-state filters; validate malformed keys; emit all detector metadata search fields, complete ordered `matched_on`, and retrieval-only scores.
3. **Rebuild and containment integrity.** Preserve explicit stale rejection/rebuild, pin the verified projection throughout a read, and pin/no-follow canonical inputs plus the derived output directory across check/use boundaries.

The slices are not independently shippable: projection/query behavior consumes the canonical run history, and the security boundaries protect that same public operation.

## Refactor opportunity

Harmonize schema-v2 detector snapshot path/hash validation currently duplicated between strict replay and signal projection into one shared pure validator after the corrected behavior is established. This is behavior-preserving deduplication: replay and search keep their existing public outputs and errors while one owner enforces the same required path, canonical hash, detector identity, and safe-containment rules.

## Acceptance-criterion dispositions

1. **Rebuildable projection from public redacted signals, run provenance, and detector metadata — `revise`.** Consumer behavior: repeated canonical runs remain buildable; each row binds immutable run-specific metadata; returned items have the exact public sanitized signal and complete detector metadata shape. Deterministic seams: `test_canonical_repeated_runs_keep_immutable_run_bound_detector_metadata`, `test_projection_pages_repeated_signal_identity_by_run_aware_reference`, `test_projection_requires_run_bound_detector_snapshot_fields`, and `test_projection_returns_exact_public_redacted_shape_without_mutating_evidence`.
2. **Never modify canonical index, signal JSONL, or detector-run artifacts — `revise`.** Consumer behavior: build/query leave canonical bytes unchanged and reject pre-existing or post-validation link swaps without outside reads/writes. Deterministic seams: canonical digest assertions plus `test_projection_refuses_an_input_symlink_swapped_after_validation`, `test_projection_refuses_a_search_directory_swapped_after_validation`, and the pre-existing symlink case.
3. **Filter by detector, group/category, severity, source, table, run, date, and review state — `revise`.** Consumer behavior: each supplied facet independently constrains results; unknown and non-string/mixed keys consistently raise `SignalSearchError`. Deterministic seams: the nine-case `test_each_structured_filter_independently_constrains_results` matrix and `test_malformed_filter_keys_use_the_public_search_error`.
4. **Lexically search statements, warnings, detector metadata, and redacted preview text — `revise`.** Consumer behavior: statement, warnings, title, description, assumptions, false positives, and preview leaves are each searchable through literal case-folded terms; private fields and injection-shaped literals do not match. Deterministic seam: the seven-case `test_lexical_search_reports_every_public_field_and_retrieval_score` matrix.
5. **Stable keyset pagination, matched-on details, and canonical signal/evidence references — `revise`.** Consumer behavior: every genuine field match is reported in deterministic field order; repeated canonical signal IDs remain distinct by run-aware reference; cursor pages are repeatable and complete without duplicates. Deterministic seams: the overlapping `Acme` lexical case, `test_projection_pages_repeated_signal_identity_by_run_aware_reference`, and `test_search_uses_repeatable_keyset_pages_and_retrieval_only_scores`.
6. **Bind input hashes and reject or rebuild stale projections — `revise`.** Consumer behavior: all three input families make reads stale, explicit build replaces stale derived artifacts and exposes the changed canonical content, required snapshot bindings reject malformed provenance, and a read racing rebuild returns its verified snapshot or `StaleSignalProjectionError`. Deterministic seams: `test_query_rejects_then_explicitly_rebuilds_each_bound_input_family`, `test_projection_requires_run_bound_detector_snapshot_fields`, and the Event-scheduled `test_verified_search_never_returns_rows_from_a_concurrent_rebuild`.
7. **Keep query scores separate from severity, confidence, and editorial status — `revise`.** Consumer behavior: empty queries score every row zero; equal lexical evidence scores equally despite different severity/confidence; overlapping public fields raise retrieval score and appear in `matched_on`. Deterministic seams: `test_search_uses_repeatable_keyset_pages_and_retrieval_only_scores` and the lexical matrix.

## Surviving blocker consolidation

Duplicated review/review2 findings are represented once in the contract above without dropping behavior:

- repeated-run identity and ambiguous references → composite row/reference and pagination seam;
- mutable detector-global snapshots plus optional path/hash → canonical content-addressed producer and required-binding seams;
- non-discriminating filter conjunction → nine independent filter cases;
- incomplete public redaction assertion → exact returned object equality;
- incomplete detector metadata search → title/description/assumptions/false-positive cases;
- truncated `matched_on` and collapsed score → overlapping-field exact list and score;
- missing explicit rebuild → stale/rebuild matrix over signals, provenance, and detector metadata;
- editorial-coupled score possibility → zero/equal retrieval-score assertions over differing editorial values;
- malformed mixed filter keys → exact public error-family assertion;
- verified read/rebuild race → Event-scheduled verification/rebuild/read interleaving with no sleeps;
- pathname and derived-directory symlink swaps → deterministic post-validation input and output swaps.

The credential-shaped-source finding remains **non-blocking and refuted**. Disposition: `skip`. The accepted acquisition-only value cannot reach prepared tables or canonical signals because preparation rejects the credential-bearing registered path; no search behavior or test is owed for that unreachable pair.

## Non-goal dispositions

- Embeddings or semantic ranking — `skip`.
- Journalist triage writes — `skip`.
- Browser UI or workflow pauses — `skip`.
- Production implementation by plan station — `skip`; only the test contract and task records changed.

## Targeted RED

- Test file: `tests/test_signal_search.py`
- Command: `.venv/bin/python -m pytest tests/test_signal_search.py -q`
- Decisive result: `10 failed, 21 passed in 0.84s`.
- Attribution: the failures reach the intended production seams: missing run-aware `signal_ref`; truncated overlapping `matched_on`; optional snapshot path/hash; raw `TypeError` for mixed malformed keys; mutable detector-global snapshot path; duplicate `signal_id` rejection across runs; projection A verification followed by projection B rows; and accepted post-validation input/output symlink swaps. The 21 passing cases prove fixture setup, all independent filters, all detector metadata lexical branches, explicit rebuild behavior, retrieval-only score baselines, pre-existing symlink rejection, collection, and imports are sound.

## Recovered checkpoint gate failure

- Gate command: `uv run --extra test pytest tests/`
- Result: `27 failed, 775 passed`.
- Targeted search tests remained green: `31 passed`.
- The failures cluster in `tests/test_pipeline_walk.py`: detector execution makes P5 unavailable, so Gate B and downstream workflow assertions cannot be reached; one containment recheck no longer raises.
- Route: implementation. Preserve the revised search contract and repair the canonical detector snapshot/workflow compatibility. Tests remain unchanged.
- Original targeted RED full output: `artifact://186`.
