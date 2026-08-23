# Unify Anomaly durable execution and demo conformance

## Goal

Make Anomaly's installed mainline sequence use one authoritative durable execution protocol, align its documented phase order with actual behavior, and prove create-to-report behavior with one deterministic demo dataset. Choose the smaller of wiring the existing runner into the product path or deleting it in favor of receipt-derived state; do not retain two competing authorities.

## Acceptance criteria

- One documented API/dispatcher entry path owns phase transitions, attempts, invalidation, blocked status, and fresh-session resume. `state.json`, receipts, events, and attempts have explicit non-conflicting roles.
- A successful artifact mutation cannot become invisible to resume because best-effort event logging failed. Either the authoritative transition is committed with the artifact or state is re-derived from validated receipts/artifacts.
- The actual installed path enforces exactly three attempts per phase, persists failures and attempt paths, and returns explicit `blocked` or `unavailable` after exhaustion.
- Changed source, prepared generation, detector identity, parameters, draft, replay, review, or approval invalidates downstream progress at the earliest correct phase.
- P5/P6 ordering has one canonical definition shared by `PRD.md`, `skills/anomaly/SKILL.md`, implementation, and tests. Preserve replay-before-promotion and independent reviewer separation regardless of the selected order.
- One small checked-in demo CSV runs create → register → prepare/profile → recommend/approve → detect → replay/draft/review/accept → report/charts, then restart and mutation cases prove deterministic resume and invalidation.
- Existing deterministic modules, case format, detector contracts, and portable relative paths remain intact.

## Non-goals

- No new service, database, queue, scheduler, agent framework, shared orchestration package, or network dependency.
- No new pipeline phases, detector behavior, source adapters, report features, or case-file format beyond the minimum durable transition data required.
- No broad rewrite of deterministic modules that already pass their contracts.
- Do not make `ORCHESTRATION-SPINE.md` a runtime dependency.

## Audit

Not required unless the plan changes detector execution, path containment, DuckDB isolation, credential handling, acquisition networking, or another existing trust boundary.
