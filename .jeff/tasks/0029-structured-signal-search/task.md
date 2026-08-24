# Build deterministic structured signal search

## Goal

Make detector signals searchable through deterministic filters and lexical matching without changing canonical evidence.

## Acceptance criteria

- Build a rebuildable projection from the public redacted signal contract, run provenance, and detector metadata.
- Never modify data/index.duckdb, evidence/signals.jsonl, or detector-run artifacts.
- Filter by detector, group or category, severity, source, table, run, date, and review state when supplied.
- Lexically search statements, warnings, detector metadata, and redacted preview text.
- Return stable keyset pagination, matched_on details, and canonical signal and evidence references.
- Bind the projection to input hashes and reject or rebuild stale projections.
- Keep query scores separate from severity, confidence, and editorial status.

## Non-goals

- Embeddings or semantic ranking.
- Journalist triage writes.
- Browser UI or workflow pauses.

## Audit

Required: derived-index containment, stale-index handling, redaction, query construction, and canonical-evidence immutability.
