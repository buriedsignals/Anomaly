---
name: usaspending-awards
description: >-
  Use this skill to search USAspending prime federal contracts, grants, loans,
  IDVs, direct payments, or other assistance by recipient, keyword, award ID,
  and time window. Apply it to award-level procurement and assistance research;
  keep award amount distinct from transactions, obligations, outlays, payments,
  and subawards, and resolve recipients with UEI and award identifiers.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to api.usaspending.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/usaspending/awards
---

# Query USAspending federal awards

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/usaspending/awards:search-awards` — Search one award-type group over an explicit date range or federal fiscal year with bounded, type-compatible fields and pagination.
<!-- END GENERATED OPERATION STATUS -->
## Define type and time explicitly

```bash
catalogue query us/usaspending/awards --operation search-awards \
  --input '{"recipient":"Boeing","award_type":"contracts","fiscal_year":2025,"limit":10}'
```

A federal fiscal year runs October 1 through September 30. Supplying explicit
dates requires both `start_date` and `end_date`. If neither is present, the
adapter uses the current federal fiscal year and returns that window in
`query_window`.

Use `recipient` to search recipient name, UEI, and DUNS. Use `keyword` for the
broader award keyword filter. `award_id` is quoted upstream for exact matching.

## Interpret amounts and records

- `amount` is Award Amount, except loans where it is Loan Value.
- `total_outlays` and `subsidy_cost` are separate fields when valid for the type.
- This operation returns prime awards, not transactions or subawards.
- A recipient-name match is not entity resolution; verify UEI, generated award
  ID, agency, dates, and the linked award profile.
- Corrections and modifications can change award-level values over time.

Read [the API reference](references/api-reference.md) for filters, type codes,
type-specific fields, pagination, and amount semantics. Read
[the query guide](references/query-guide.md) for reproducible award research.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved Treasury API contract and endpoint index.
- `references/query-guide.md` — time/type selection, recipient resolution, and reporting.
- `scripts/verify.py` and `assets/verification-cases.json` — live contract and grant checks.
- `evals/evals.json` — amount, recipient, time-window, and subaward cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
