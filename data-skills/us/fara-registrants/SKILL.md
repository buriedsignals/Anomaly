---
name: fara-registrants
description: >-
  Use this skill to list US Foreign Agents Registration Act registrants
  (active and terminated) from the DOJ FARA.gov API as
  foreign_agent_registrants rows of Anomaly's lobbying contract, for example
  to check LDA filers with foreign ties against FARA registration.
compatibility: Requires Python 3.11+ and network access to efile.fara.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/fara/registrants
---

# List FARA registrants as lobbying contract rows

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/fara/registrants:foreign-agent-registrants` — Active and/or terminated FARA registrants, optionally filtered by name substring.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

```python
from pathlib import Path
from anomaly.sources.registry import discover_sources, load_source_adapter

entries = discover_sources(Path("data-skills"))
fara = load_source_adapter(entries, "us/fara/registrants")
result = fara.run({"operation": "foreign-agent-registrants", "status": "all"}, None)
```

Write `records` to `foreign_agent_registrants.csv` and pass it to
`python -m anomaly.oneshot --tables foreign_agent_registrants=...`. The
`lobbying.fara_gap_narrowed` detector needs the full list (active and
terminated), not a name-filtered subset, because it looks for LDA filers that
are absent from it.

## Source boundary

- Each call downloads the whole active and/or terminated list (no key;
  5 requests per 10 seconds) and filters names locally.
- `registration_number`, `status`, dates, and `documents_url` (the RegDocs
  endpoint listing the registrant's filed PDFs) follow the contract column.
- Names are free text. A name mismatch with LDA is a lead to check by hand,
  not evidence of a missing registration.

Read [the API reference](references/api-reference.md) for endpoints and limits.

## Bundled resources

- `references/api-reference.md` — endpoints, encoding, limits.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — interpretation cases.
