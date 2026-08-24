# Remove automatic crash rollback and finalize resolver consolidation

## Goal
Honor the operator's scope decision: Anomaly does not guarantee automatic recovery from a machine or process crash during artifact promotion. Remove the case-local rollback journal and backup trust machinery while preserving normal deterministic attempts, validation, retries, gates, containment, identity invalidation and report behavior.

## Acceptance criteria

- Normal owner errors and validation failures still leave live case artifacts unchanged and persist bounded redacted attempt evidence.
- The automatic case-local promotion journal, rollback backups, provenance inference and restart rollback state machine are deleted rather than replaced.
- If startup detects evidence of an interrupted promotion, it preserves every live file, records `repair required`, and stops without deleting or overwriting case content.
- The blocked result identifies the phase/attempt and the retained attempt workspace so the journalist can inspect it before an explicit later repair action.
- Resolver, Gate A/Gate B turn boundaries, source replacement, identity invalidation, dynamic reviewer separation, README preservation, inert Markdown and all ordinary restart/resume behavior remain green.
- Public fork, attempt and event writers retain whole-case no-symlink containment.
- Stale tests/docs claiming automatic machine-crash rollback are removed or rewritten to the fail-closed manual-repair contract.
- WorkflowRunner, product loop, aliases, duplicate projections and Spotlight-specific machinery remain absent.

## Non-goals

- No machine/power-crash rollback guarantee.
- No external signing key or authenticated recovery journal.
- No native-Windows redesign, service, database, framework or new phase.

## Audit

Required for path containment, attempt workspace preservation and the fail-closed repair boundary.
