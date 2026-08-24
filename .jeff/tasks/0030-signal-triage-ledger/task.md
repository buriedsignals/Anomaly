# Add immutable signal triage decisions

## Goal

Let journalists classify detector signals without mutating detector output or promoting findings.

## Acceptance criteria

- Support unreviewed, shortlisted, needs-context, and dismissed states only.
- Bind every event to signal ID, signal hash, state, optional note and tags, journalist identity, and timestamp.
- Keep signals and run artifacts immutable and derive current state deterministically from append-only events.
- Invalidate P5 and every downstream completion when consumed triage changes after drafting.
- Never name or treat a triage state as confirmed, accepted, or promoted.

## Non-goals

- Search ranking or embeddings.
- Changes to final report generation.

## Audit

Required: event integrity, journalist identity, path containment, invalidation authority, and protection against forged signal bindings.
