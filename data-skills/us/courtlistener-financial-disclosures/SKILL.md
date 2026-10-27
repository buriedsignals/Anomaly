---
name: courtlistener-financial-disclosures
description: >-
  Use this skill to retrieve CourtListener financial-disclosure reports for one
  known federal judicial person ID and inspect extracted investments, gifts,
  debts, agreements, positions, reimbursements, income, redactions, and source
  PDFs. Apply it to conflict-of-interest research; preserve value ranges and
  inferred flags, and verify every material finding in the original filing.
compatibility: Requires Python 3.11+ and network access to www.courtlistener.com; a CourtListener token is optional but recommended for clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/financial-disclosures
---

# Query judicial financial disclosures

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/financial-disclosures:list-financial-disclosures` — Return bounded disclosure reports and selected nested extracted rows for an exact CourtListener person ID.
- `us/courtlistener/financial-disclosures:judge-interests` — Flatten one person's reports into one row per investment, gift, reimbursement, position, agreement, income, spouse income or debt line.
<!-- END GENERATED OPERATION STATUS -->
## Court domain rows

`judge-interests` flattens the same reports into the court domain contract's
`judge_interests` table (`domains/court.yaml`). Nested field names follow
CourtListener's `cl/disclosures/models.py`. The endpoint returned HTTP 401
without a token on 2026-10-27.

| Disclosure field | judge_interests column |
|---|---|
| person id at the end of `person` | `judge_id` (joins `court_cases.assigned_judge_id`) |
| `year` | `report_year` |
| `filepath` | `url` |
| `investments[]`: `description`; `gross_value_code` J..P4 | `interest_type` investment, `counterparty`; `value_low`/`value_high` from the code's band (P4 has no upper bound; -1 and unknown codes stay empty) |
| `gifts[]`: `source`, `description`, `value` ("$1,199.00") | gift, `counterparty`, `description`, `value_low` = `value_high` |
| `reimbursements[]`: `source`; `date_raw`, `location`, `purpose`, `items_paid_or_provided` | reimbursement, `counterparty`; `description` (joined with "; ") |
| `positions[]`: `organization_name`, `position` | position, `counterparty`, `description` |
| `agreements[]`: `parties_and_terms`, `date_raw` | agreement, `counterparty`, `description` |
| `non_investment_incomes[]`: `source_type`, `income_amount` | income, `counterparty`, value bounds when the amount parses |
| `spouse_incomes[]`: `source_type` | spouse_income, `counterparty` |
| `debts[]`: `creditor_name`, `description`, `value_code` | debt, `counterparty`, `description`, value bounds |
| row `redacted` | extra column `redacted` (not in the contract; check the PDF) |

`judge_name` is left empty: the report links the person only by id. Lines
without a counterparty are dropped.

## Retrieve one person's reports

Resolve the subject to a CourtListener person ID first, then query:

```bash
catalogue query us/courtlistener/financial-disclosures \
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
