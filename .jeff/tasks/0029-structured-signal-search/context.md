# Task 29 context

## Relevant paths and symbols

- `.jeff/tasks/0029-structured-signal-search/task.md:3` — locked goal, seven acceptance criteria, non-goals, and audit requirement.
- `.jeff/tasks/0029-structured-signal-search/review-correctness-valid.json:49` — cycle-0 correctness findings.
- `.jeff/tasks/0029-structured-signal-search/review-standards-valid.json:49` — cycle-0 standards and boundary findings.
- `.jeff/tasks/0029-structured-signal-search/audit-valid.json:52` — cycle-0 verified-read/rebuild and path-swap findings.
- `.jeff/tasks/0029-structured-signal-search/refute-01-valid.json:1` — refuted credential-shaped source finding.
- `.jeff/tasks/0029-structured-signal-search/refute-02-valid.json:1` through `refute-17-valid.json:1` — source-bound outcomes for the surviving cycle-0 findings.
- `src/anomaly/detect.py:609` — canonical detector execution entry point with an injected `now` value.
- `src/anomaly/detect.py:679` — canonical lead assembly and stable `signal_id` derivation.
- `src/anomaly/detect.py:717` — sanitized snapshot construction, canonical hash derivation, content-addressed immutable write, and schema-v2 provenance binding.
- `src/anomaly/review.py:699` — strict redacted-lead validation.
- `src/anomaly/review.py:714` — schema-v2 provenance detector-snapshot content-addressed path/hash validation through the shared pure reference predicate.
- `src/anomaly/review.py:1030` — public replay allowlisting through `semantics.sanitize_public_value`.
- `src/anomaly/semantics.py:107` — recursive credential text redaction.
- `src/anomaly/semantics.py:116` — recursive sensitive-key removal and credential redaction for public values.
- `src/anomaly/detectors/registry.py:16` — required detector metadata fields.
- `src/anomaly/detectors/__init__.py:12` — shared pure detector snapshot path/hash/reference predicate used by strict replay and signal projection.
- `src/anomaly/search.py:44` — public projection builder.
- `src/anomaly/search.py:49` — public structured search entry point and verified-connection lifetime.
- `src/anomaly/search.py:108` — filter-key and filter-value validation.
- `src/anomaly/search.py:143` — retrieval ranking with composite signal/run ordering.
- `src/anomaly/search.py:169` — complete matched-field calculation.
- `src/anomaly/search.py:187` — composite keyset continuation comparison.
- `src/anomaly/_signal_projection.py:104` — private staged derived projection construction and manifest replacement through a pinned search directory.
- `src/anomaly/_signal_projection.py:168` — input and projection verification plus a read connection opened against the verified database object.
- `src/anomaly/_signal_projection.py:234` — DuckDB row read boundary using the verified connection.
- `src/anomaly/_signal_projection.py:251` — signal, provenance, and provenance-selected detector snapshot input collection.
- `src/anomaly/_signal_projection.py:269` — required schema-v2 snapshot path/hash discrimination through the shared pure reference predicate.
- `src/anomaly/_signal_projection.py:291` — signal/provenance/snapshot binding and exact public run-aware row construction.
- `src/anomaly/_signal_projection.py:363` — composite signal/run identity and public field validation.
- `src/anomaly/_signal_projection.py:449` — statement, warning, detector metadata, and preview search-field construction.
- `src/anomaly/_signal_projection.py:544` — no-follow pinned canonical-input reads.
- `src/anomaly/_signal_projection.py:588` — pinned derived-directory containment helpers.
- `tests/test_signal_search.py:53` — isolated structured-search fixture with schema-v2 snapshot path/hash bindings and canonical sentinels.
- `tests/test_signal_search.py:237` — isolated canonical acquisition/prepare/profile/recommend/approve fixture.
- `tests/test_signal_search.py:283` — exact public result shape, full detector metadata shape, manifest inputs, and canonical digest assertions.
- `tests/test_signal_search.py:369` — independently discriminating nine-filter matrix.
- `tests/test_signal_search.py:411` — all public lexical fields, full `matched_on`, literal query, and retrieval-score matrix.
- `tests/test_signal_search.py:434` — repeatable keyset pages and editorially independent scores.
- `tests/test_signal_search.py:464` — stale rejection plus explicit rebuild for signals, provenance, and detector metadata.
- `tests/test_signal_search.py:517` — required schema-v2 snapshot path/hash cases.
- `tests/test_signal_search.py:538` — unknown and mixed-type malformed filter-key cases.
- `tests/test_signal_search.py:549` — two canonical detector executions against an isolated copied package with changed metadata content.
- `tests/test_signal_search.py:593` — repeated canonical `signal_id` rows, run-aware references, and bounded cursor walk.
- `tests/test_signal_search.py:654` — Event-scheduled verified-read/rebuild interleaving.
- `tests/test_signal_search.py:700` — post-validation canonical-input symlink swap.
- `tests/test_signal_search.py:735` — post-validation derived-directory symlink swap.
- `tests/test_signal_search.py:765` — pre-existing derived-directory symlink rejection.

## Commands

- Targeted RED: `.venv/bin/python -m pytest tests/test_signal_search.py -q` — `10 failed, 21 passed in 0.84s`.
- Targeted GREEN: `.venv/bin/python -m pytest tests/test_signal_search.py -q` — `31 passed in 0.87s`.
- Full suite configured by pytest: `.venv/bin/python -m pytest` (not run by plan station).

## Mechanical constraints

- The production API named by the target contract is `anomaly.search`, with `build_signal_projection`, `search_signals`, `SignalSearchError`, and `StaleSignalProjectionError`.
- Derived projection artifacts are `.anomaly/search/signals.duckdb` and `.anomaly/search/signals-manifest.json` relative to a case root.
- Canonical `data/index.duckdb`, `evidence/signals.jsonl`, `evidence/runs/**`, detector snapshots, and detector-run outputs are read-only projection inputs.
- Canonical `signal_id` identifies detector/table/candidate evidence; the target result-row identity is `(signal_id, run_id)`.
- The target `signal_ref` contains `path`, `signal_id`, and `run_id`; keyset tie-breaking is `query_score` descending, then `signal_id` and `run_id` ascending.
- Schema-v2 run provenance contains `detector_snapshot` and `detector_snapshot_hash`; the target snapshot path is beneath `detectors/used` and its filename ends with the canonical snapshot SHA-256 digest.
- Targeted concurrency uses `threading.Event` scheduling and injected `NOW` values; the target tests contain no sleeps, network access, unseeded randomness, shared case paths, filesystem timestamp assertions, or real wall-clock reads.
- Embeddings, triage writes, browser UI, automatic projection rebuild, canonical-evidence mutation, and `data/index.duckdb` mutation are outside task scope.
