# 0007 — Replay, review, findings, and report

## Goal

Turn detector leads into reviewed claims and a report without promoting any unreviewed signal.

## Acceptance criteria

- `findings/draft.json` is derived from ranked, redacted signal previews and provenance-wrapped read-only queries. Signals remain leads.
- Deterministic replay checks every cited calculation against recorded source and detector hashes.
- `findings/review.json` records independent review verdicts. Review cannot edit the draft.
- If an isolated reviewer is unavailable, the case says so and cannot claim independent review.
- Only Gate-B-accepted claims enter `findings/findings.json`.
- `findings/unresolved.md` preserves missing evidence, open questions, and next steps.
- `findings/report.md` is generated only from accepted findings.
- `README.md` is refreshed with status and relative links.
- Different signal categories are not treated as independent corroboration.

## Non-goals

- Authoring `skills/anomaly/` or installing the reviewer into an agent runtime (0008).
- Publishing, vault ingest, or OpenKnowledge writes.

## Audit

Redaction of review inputs, hash-bound replay, and refusal to persist secrets in reports.
