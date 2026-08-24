# Expose agent signal search and triage operations

## Goal

Expose bounded signal search, inspection, and triage through the installed Anomaly agent workflow.

## Acceptance criteria

- Search signals using structured filters and lexical queries.
- Open one signal with detector rationale, warnings, preview, calculation, provenance, and source references.
- Shortlist, dismiss, mark needs-context, add notes or tags, and list unresolved review work.
- Require explicit journalist identity for writes and return credential-redacted bounded results.
- Update the installed anomaly skill contract without adding another agent persona.

## Non-goals

- Semantic retrieval.
- Automatic claim promotion.
- Dedicated browser UI.

## Audit

Required: agent write authorization, result redaction, prompt-injection boundaries, and bounded read/query behavior.
