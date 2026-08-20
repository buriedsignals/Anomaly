# 0012 — P2 preparation and profile integration

## Goal

Integrate the safe case boundary from 0010 and record decoder from 0011 into the PRD P2 phase: hash-verified prepared data, rebuildable DuckDB, deterministic semantic mappings and complete profiling.

## Acceptance criteria

- Included registered sources are hash-verified and decoded only through 0011.
- Preparation is all-or-nothing for required sources: any missing, mismatched, excluded, invalid, or lossy input yields no partial prepared tables or DuckDB index.
- Editorial source identity is separate from stable secret-free structural identity; DuckDB/table/path identities cannot collide after redaction.
- Transforms record exact relative source/prepared paths and hashes; every reference resolves after moving the complete case.
- DuckDB is queryable and deterministically rebuildable for all five supported formats.
- Types and semantic roles are deterministic; ambiguous mappings are surfaced.
- Profile includes complete row counts, missingness, cardinality, ranges, distributions, duplicate counts, and applicable temporal/geographic coverage from persisted mappings.
- Every manifest-declared loaded table must exist and decode to the expected prepared shape before profile or instruction writes.
- Methodology, context, and data dictionary update atomically; handling remains unchanged.
- Credentials never appear in generated values, keys, filenames, DuckDB, JSON, Markdown, or return payloads.
- Empty/unavailable cases remain explicitly unreplayable.
- Full suite and moved-case rebuild/profile pass.

## Non-goals

- Reimplementing case-tree validation or decoders.
- Detector execution or recommendation.
- Entity resolution.

## Audit

Required: manifest trust boundary, path portability, atomic multi-output writes, secret redaction, DuckDB read/write confinement, and no network.
