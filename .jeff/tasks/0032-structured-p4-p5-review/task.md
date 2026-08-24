# Add optional structured signal review before drafting

## Goal

Offer optional journalist signal review after P4 and bind its decisions into P5 draft behavior.

## Acceptance criteria

- After P4, summarize signal counts by detector, category, and severity and offer Review signals or Continue to drafting.
- Treat the review pause as non-failing and not as a third approval gate.
- Record the exact triage snapshot hash consumed by P5.
- Exclude dismissed signals, rank shortlisted signals first, and retain deterministic order for unreviewed signals.
- Keep needs-context signals visible and prevent silent promotion to accepted findings.
- Prove deterministic resume and invalidation behavior.

## Non-goals

- Semantic indexing.
- Changes to Gate A or Gate B authority.

## Audit

Required: workflow-state ownership, pause/retry accounting, triage-to-draft binding, and downstream invalidation.
