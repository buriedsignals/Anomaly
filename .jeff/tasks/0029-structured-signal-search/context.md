# Task 29 context

## Relevant paths and symbols

- `.jeff/tasks/0029-structured-signal-search/task.md:3` — locked goal and acceptance criteria for structured signal search.
- `src/anomaly/detect.py:583` — canonical workflow detector execution entry point.
- `src/anomaly/detect.py:654` — persisted lead assembly, including detector, table, source, preview, statement, rank, severity, and stable signal identity.
- `src/anomaly/detect.py:677` — run identity, detector hash, Parquet/preview output, provenance, and `evidence/signals.jsonl` persistence.
- `src/anomaly/review.py:29` — current public redacted replay signal field allowlist.
- `src/anomaly/review.py:52` — replay reads run preview and provenance artifacts and emits `evidence/replay.json`.
- `src/anomaly/review.py:697` — strict redacted-lead shape validation.
- `src/anomaly/review.py:1029` — public signal allowlisting now delegates recursive sanitization to `semantics.sanitize_public_value`.
- `src/anomaly/detectors/registry.py:16` — required detector metadata fields, including group, signal category, severity, assumptions, and false positives.
- `src/anomaly/detectors/registry.py:490` — normalized registry lead fields, including category, severity, observed time, summary, warnings, and provenance.
- `src/anomaly/semantics.py:107` — shared recursive credential redactor.
- `src/anomaly/semantics.py:116` — shared key-aware public-value sanitizer used by review and search.
- `src/anomaly/acquire.py:91` — source registry fields, including source identity, content hash, and acquisition timestamp.
- `src/anomaly/search.py:44` — public projection builder and read-only search API, including validated filters, lexical matching, and cursor handling.
- `src/anomaly/_signal_projection.py:62` — contained hash-bound projection construction, input validation, manifest verification, and parameter-bound DuckDB reads.
- `tests/test_detect.py:30` — local dynamic-import test convention.
- `tests/test_review.py:55` — canonical signal/run/source fixture convention.
- `tests/test_signal_search.py:29` — isolated structured-search fixture with signals, run provenance, detector snapshots, run outputs, and a read-only canonical DuckDB sentinel.
- `tests/test_signal_search.py:213` — structured filters, canonical references, score separation, projection containment, and canonical immutability contract.
- `tests/test_signal_search.py:269` — lexical fields, matched-on detail, non-public field exclusion, and injection-shaped literal contract.
- `tests/test_signal_search.py:292` — stable keyset pagination contract.
- `tests/test_signal_search.py:331` — signal, provenance, and detector-metadata stale-input contract.
- `tests/test_signal_search.py:354` — derived search-directory symlink containment contract.

## Commands

- Targeted RED: `.venv/bin/python -m pytest tests/test_signal_search.py -q`
- Targeted GREEN: `.venv/bin/python -m pytest tests/test_signal_search.py -q` — `10 passed in 0.25s`.
- Full suite configured by pytest: `.venv/bin/python -m pytest` (not run by plan station).

## Mechanical constraints

- The production API named by the targeted contract is `anomaly.search`, with `build_signal_projection`, `search_signals`, `SignalSearchError`, and `StaleSignalProjectionError`.
- Derived projection artifacts are `.anomaly/search/signals.duckdb` and `.anomaly/search/signals-manifest.json` relative to a case root.
- Canonical `data/index.duckdb`, `evidence/signals.jsonl`, `evidence/runs/**`, and detector-run artifacts are read-only inputs for this task.
- Projection inputs covered by the target contract are the public redacted signal JSONL, each referenced run provenance JSON, and each referenced detector snapshot JSON.
- The target contract uses no network, wall clock, sleeps, unseeded randomness, shared mutable paths, or filesystem timestamps.
- Embeddings, triage writes, browser UI, canonical-evidence mutation, and `data/index.duckdb` mutation are outside task scope.
