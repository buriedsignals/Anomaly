# Add Gate A semantic indexing consent

## Goal

Suggest semantic indexing only after profiling identifies eligible text or code fields and bind case-specific consent at Gate A.

## Acceptance criteria

- Derive eligible fields and estimate chunks, index size, and build time without embedding content.
- Show selected tables and fields, exclusions, text or code mode, model revision, dimensions, locality, and estimates at Gate A.
- Do not suggest indexing when no eligible fields exist or handling rules prohibit it.
- Never select credential outputs, secrets, personal identifiers, or explicitly excluded fields.
- Bind the approved plan and prepared-data hashes in the Gate A receipt.
- Preserve structured and lexical search without repeated prompts when semantic indexing is declined.

## Non-goals

- Building embeddings.
- Changing the number or authority of workflow gates.

## Audit

Required: sensitive-field eligibility, consent fidelity, handling-policy enforcement, and hash-bound plan invalidation.
