# Integrate semantic review into P4 and P5

## Goal

Build, validate, and reuse approved semantic projections at the correct workflow boundaries.

## Acceptance criteria

- Build source embeddings after Gate A without modifying data/index.duckdb.
- Add approved redacted signal content after P4.
- Offer searchable review before P5 and identify lexical, semantic, or hybrid matches.
- Keep semantic-index absence or failure non-blocking unless the journalist explicitly made it required.
- Invalidate projections and affected downstream state when sources, prepared data, plans, models, prompts, or chunkers change.
- Validate manifests and hashes before reuse on resume.

## Non-goals

- A browser review application.
- Changing final finding authority.

## Audit

Required: phase ownership, projection lifecycle, fallback semantics, invalidation completeness, and resume safety.
