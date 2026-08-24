# Consolidate Anomaly on resolver plus durable attempt mechanics

## Goal

Preserve Anomaly's deterministic data pipeline, durable attempts, invalidation, Gate A/Gate B receipts and independent review while expressing orchestration through the shared method: pure resolver → one phase owner → deterministic handler or dynamically loaded reasoning skill/persona → sealed result or human gate → fresh resolution. Reduce the accumulated runner/product/test surface.

## Acceptance criteria

- A pure Anomaly resolver returns phase, status, owner, missing input/human decision, attempts, invalidated-from and resume detail without executing a phase.
- One compact phase-to-owner registry selects deterministic handlers for code-first phases and dynamically loaded skills/personas for interpretation and independent review.
- Durable attempt staging, retries, failure evidence and atomic promotion remain separate execution utilities rather than a second orchestration API.
- Gate A/Gate B turn boundaries, identity separation, source replacement, earliest invalidation, event-failure resume, case portability and exact P5→P6→Gate B→P7 order remain green.
- README projection preserves journalist-authored content, successful completion/relative links are positively tested, and invalidation demotes completion truthfully.
- Dataset-derived Markdown is inert, including bare URL autolinks.
- Whole-case no-symlink validation protects every public resume/read/write path.
- Unused aliases, direct report completion, duplicate P0–P7 test compositions, stale expectations and duplicate state projections are removed.
- One demo CSV proves the shared six-step method, dynamic reasoning/reviewer loading and both human gates.

## Non-goals

- No shared runner, service, database, new phase, source adapter, detector or report feature.
- Deterministic phases remain deterministic code; do not turn them into LLM skills.

## Simplicity objective

Use task 25 checkpoints as evidence and deletion inventory. Prefer a smaller resolver/registry and focused attempt utilities over preserving accumulated structure. Material additions must replace more competing code or protect demonstrated user data. Final handoff reports plain-language transformation and line counts for product code, tests, docs/evidence and Jeff state.

## Audit

Required for case containment, source mutation, detector execution and report serialization boundaries.
