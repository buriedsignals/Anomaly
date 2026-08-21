---
name: courtlistener-financial-disclosures
description: >-
  Use this skill to retrieve CourtListener financial-disclosure reports for one
  known federal judicial person ID and inspect extracted investments, gifts,
  debts, agreements, positions, reimbursements, income, redactions, and source
  PDFs. Apply it to conflict-of-interest research; preserve value ranges and
  inferred flags, and verify every material finding in the original filing.
compatibility: Requires the Navigator CLI, Python 3.11+, and network access to www.courtlistener.com; a CourtListener token is optional but recommended for deployed clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/financial-disclosures
---

# Query judicial financial disclosures

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current Navigator release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/financial-disclosures:list-financial-disclosures` — Return bounded disclosure reports and selected nested extracted rows for an exact CourtListener person ID.
<!-- END GENERATED OPERATION STATUS -->
## Retrieve one person's reports

Resolve the subject to a CourtListener person ID first, then query:

```bash
navigator query us/courtlistener/financial-disclosures \
  --operation list-financial-disclosures \
  --input '{"person_id":2738,"limit":10}'
```

The provider endpoint does not accept a `year` filter. Filter the returned
bounded reports locally only after preserving that limitation; do not send an
invented provider parameter.

## Extraction discipline

- Open `pdf_url` before publishing a finding. Extraction can be incomplete.
- Keep `gross_value_code`, `transaction_value_code`, and their ranges. Never
  turn a band into an exact amount.
- Treat `has_inferred_values=true` as an extraction inference, not a filing fact.
- Inspect every `redacted` marker and avoid reconstructing protected details.
- Separate a reported interest from evidence that it affected a case.
- Absence from CourtListener coverage is not proof of no report or no conflict.

Read [the API reference](references/api-reference.md) for endpoint scope, nested
fields, redactions, inferred values, and provider limits. Read
[the query guide](references/query-guide.md) for conflict research and reporting.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved official documentation and OPTIONS evidence.
- `references/query-guide.md` — identity resolution, extraction review, and corroboration.
- `scripts/verify.py` and `assets/verification-cases.json` — live disclosure check.
- `evals/evals.json` — range, inference, redaction, and absence cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
