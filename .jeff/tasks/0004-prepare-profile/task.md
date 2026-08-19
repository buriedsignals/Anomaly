# 0004 — Prepare and profile

## Goal

Load registered local sources into DuckDB, persist prepared tables, and write a complete dataset profile before any detector is recommended.

## Acceptance criteria

- Supported files load into DuckDB from recorded source hashes.
- Raw inputs are preserved; transformations are documented under `data/prepared/`.
- Field types and semantic roles are inferred; ambiguous mappings are surfaced rather than silently guessed.
- The profile includes row counts, missingness, cardinality, ranges, distributions, duplicates, and temporal or geographic coverage when those fields exist.
- `instructions/methodology.md`, `instructions/context.md`, and `instructions/data-dictionary.md` are updated from the profile.
- `data/index.duckdb` can be rebuilt from recorded sources and preparation steps when all included dependencies are present.
- Missing required data makes replay unavailable rather than approximated.

## Non-goals

- Detector recommendation or execution.
- Entity resolution beyond documenting join keys and ambiguous mappings.

## Audit

Read-only source hashes, no network, no secrets in profile artifacts.
