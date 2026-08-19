# 0009 — Symlink-safe P2 prepare and profile

## Goal

Implement the PRD P2 prepare/profile behavior on `main` with namespace-safe filesystem boundaries. This explicitly supersedes abandoned task 0004; its blocked evidence is preserved at jj bookmark `task-4-blocked`.

## Acceptance criteria

- All task 0004 product criteria remain required: hashed included sources load into a rebuildable DuckDB index; transforms, mappings, ambiguity, profile statistics and coverage, instructions, and replay-unavailable states are deterministic and portable.
- Editorial `source_id` is separate from a stable, secret-free storage identity. Every manifest reference is relative, matches the artifact actually written, and remains resolvable after moving the case.
- Every read/write stays in its declared namespace, not merely somewhere inside the case: `data/raw/`, `data/prepared/`, `instructions/`, and `.anomaly/receipts/` cannot alias each other or root files.
- Reject pre-existing symlinks and symlinked path components for source receipts, raw destinations, prepared artifacts, manifests, profiles, and instruction writes.
- Reject external or in-case symlinked `transforms.json` before reading it.
- Reject absolute, traversal, and out-of-namespace persisted paths before any read or write.
- Credential-shaped values and keys (`sk_live_`, `ghp_`, `github_pat_`) never appear in persisted JSON, Markdown, receipt content, or physical filenames.
- Tests reproduce and prevent all four final task-0004 audit failures:
  1. raw destination symlink overwriting `case.json`;
  2. transforms output symlink overwriting `case.json`;
  3. profile/instruction output symlink overwriting another in-case artifact;
  4. external transforms-manifest symlink controlling profile output.
- The full suite remains green; a fresh review and required audit pass.

## Non-goals

- Detector recommendation or execution (0005–0006).
- Public-source adapters (M3).
- A generic virtual filesystem or sandbox.
- Following or rewriting links found in case content.

## Audit

Required. Filesystem namespace integrity, symlink refusal, path containment, secret redaction, and external-manifest rejection are blocking boundaries.
