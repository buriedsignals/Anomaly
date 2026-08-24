# Task 29 plan

Category: `code`

Complexity: `complex`

Audit required: `true`

## Shortest correct approach

Use the installed DuckDB dependency for one derived relational projection; do not add a search or tokenization dependency. Keep the public boundary in a focused `anomaly.search` module:

- `build_signal_projection(root)` validates and reads `evidence/signals.jsonl`, the referenced `evidence/runs/<run_id>/provenance.json` files, and the referenced `detectors/used/*.json` snapshots. It writes only `.anomaly/search/signals.duckdb` and `.anomaly/search/signals-manifest.json`.
- `search_signals(root, *, query=None, filters=None, limit=20, cursor=None)` verifies the manifest's exact input hashes, opens the projection read-only with external access disabled, applies parameter-bound filters and lexical terms, and returns bounded result dictionaries.
- `SignalSearchError` covers malformed/unsafe projection inputs and query contracts. `StaleSignalProjectionError` is the explicit no-write outcome when any bound input changes. Rebuilding is an explicit call to `build_signal_projection`; a read never silently rebuilds.

The projection manifest has no clock value. It records a schema version, deterministic relative input paths with SHA-256 byte hashes, the projection identity, and signal count. Build stages its two owned artifacts inside a validated non-symlink `.anomaly/search` boundary and replaces only those exact derived files. Query recomputes the same ordered input-hash map before opening DuckDB.

The searchable signal view is an allowlisted, recursively sanitized view. It retains stable signal identity, statement, warnings, redacted preview leaves, severity, confidence, lead status, evidence references, detector/run/table/source identities, and the metadata needed by the filters. It excludes arbitrary detector-result fields such as `private_context`. Run date comes from provenance `executed_at`; source identity comes from canonical evidence references checked against provenance table-source bindings; detector group/category metadata comes from the run-bound detector snapshot. Current immutable `lead` signals project as `review_state="unreviewed"`; this task neither invents nor writes the later triage ledger.

Lexical matching casefolds and whitespace-tokenizes the query, requires every token to occur in one indexed public field, and searches statement, warning text, detector title/description/assumptions/false-positive metadata, and flattened redacted preview text. `matched_on` is an ordered list of `{"field": <public field path>, "terms": [<casefolded tokens>]}` dictionaries. `query_score` is a retrieval-only numeric value. Results keep `severity`, `confidence`, `status`, and `review_state` as separate fields. Query order is descending `query_score`, then ascending `signal_id`; an empty query gives every row score zero. The opaque cursor binds the projection input identity, normalized query, filters, and last `(query_score, signal_id)` key.

Supported exact filters are `detector_id`, `group`, `category`, `severity`, `source_id`, `table_id`, `run_id`, ISO calendar `date`, and `review_state`. Unknown filter keys, invalid dates, invalid cursors, nonpositive or over-bound limits, malformed inputs, duplicate signal identities, broken run/metadata bindings, and unsafe paths raise `SignalSearchError`. SQL text and values remain fixed/parameterized; query-like literal input cannot broaden the result set.

## Ordered slices

1. Extract the existing key-aware public-value sanitizer from `review.py` into `semantics.py`, preserving review output byte-for-byte, then use it for the search allowlist.
2. Add the contained, atomic, clock-free DuckDB projection builder and deterministic hash manifest over signals, run provenance, and detector snapshots.
3. Add validated structured filters, deterministic lexical matching, canonical references, separate retrieval scores, stable keyset pagination, and explicit stale-projection rejection.

These slices are one externally shippable feature: the query contract has no usable behavior without its projection and the projection has no consumer without the query.

## Refactor opportunity

Extract `review._sanitize`'s sensitive-key removal plus credential redaction into one shared `semantics.sanitize_public_value` helper and reuse it unchanged from review and search. This is behavior-preserving for replay/draft/report consumers and prevents a second redaction implementation from drifting; keep the existing review field allowlist and serialized outputs unchanged.

## Acceptance-criterion dispositions

1. **Rebuildable projection from public redacted signals, run provenance, and detector metadata — `write`.** Consumer-observable behavior: `build_signal_projection` creates a bounded derived DuckDB and deterministic manifest under `.anomaly/search`, and a subsequent query joins each signal to its run-bound metadata without exposing non-public fields. Deterministic seam: `test_projection_filters_every_structured_facet_without_mutating_evidence` checks all three input families, projection paths, count, and allowlisted result shape; lexical coverage also proves metadata attachment.
2. **Never modify `data/index.duckdb`, `evidence/signals.jsonl`, or detector-run artifacts — `write`.** Consumer-observable behavior: build and query leave byte hashes of the canonical index, signal JSONL, provenance, Parquet outputs, and detector snapshots unchanged, and refuse a symlinked derived-index boundary without writing through it. Deterministic seams: the canonical digest assertions in `test_projection_filters_every_structured_facet_without_mutating_evidence` and `test_projection_refuses_a_symlinked_derived_index_boundary`.
3. **Filter supplied detector, group/category, severity, source, table, run, date, and review state — `write`.** Consumer-observable behavior: all supplied filters are conjunctive exact filters and return only the matching stable signal; a current lead has explicit `unreviewed` review state without a triage write. Deterministic seam: the single all-facets query in `test_projection_filters_every_structured_facet_without_mutating_evidence`.
4. **Lexically search statements, warnings, detector metadata, and redacted preview text — `write`.** Consumer-observable behavior: case-insensitive token queries return only records with all terms in a public field, disclose the field/terms in `matched_on`, exclude arbitrary detector fields, and treat injection-shaped text literally. Deterministic seam: the four-field parameter matrix and negative literals in `test_lexical_search_reports_the_public_redacted_fields_that_matched`.
5. **Stable keyset pagination, matched-on details, and canonical signal/evidence references — `write`.** Consumer-observable behavior: repeated first pages are identical, continuation returns no duplicate, the terminal cursor is null, and every item carries a canonical JSONL signal reference plus unchanged evidence references. Deterministic seams: `test_search_uses_repeatable_keyset_pages_with_no_duplicates`, the canonical-reference assertions in the all-facets test, and the lexical `matched_on` matrix.
6. **Bind input hashes and reject or rebuild stale projections — `write`.** Consumer-observable behavior: changing signal JSONL, run provenance, or detector metadata makes reads fail with `StaleSignalProjectionError` and does not rewrite the projection; an explicit build is the rebuild path. Deterministic seam: the three-input parameter matrix in `test_query_rejects_a_projection_when_any_bound_input_changes`.
7. **Keep query scores separate from severity, confidence, and editorial status — `write`.** Consumer-observable behavior: each result exposes numeric `query_score` independently alongside unchanged `severity`, `confidence`, lead `status`, and `review_state`. Deterministic seam: the field assertions in `test_projection_filters_every_structured_facet_without_mutating_evidence`.

## Non-goal dispositions

- Embeddings or semantic ranking — `skip`; no dependency, field, score, or test is introduced.
- Journalist triage writes — `skip`; this read-only task projects current leads as unreviewed and does not define ledger storage.
- Browser UI or workflow pauses — `skip`; the contract is a deterministic Python API only.

## Targeted RED

- Test file: `tests/test_signal_search.py`
- Command: `.venv/bin/python -m pytest tests/test_signal_search.py -q`
- Result: `10 failed in 0.12s`.
- Decisive failure: every collected case completed isolated fixture setup and then failed at the dynamic production boundary with `ModuleNotFoundError: No module named 'anomaly.search'`. There were no syntax, fixture, pytest collection, import-environment, network, or unrelated-suite failures.
- Full output: `artifact://89`
