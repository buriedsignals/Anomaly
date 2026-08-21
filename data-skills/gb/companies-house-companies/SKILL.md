---
name: companies-house-companies
description: >-
  Use this skill to search UK Companies House company summaries and retrieve a
  basic profile by exact company number with a member-provided API key. Apply it
  to company identity and current register checks; preserve leading zeros and
  do not infer directors, beneficial ownership, continuous trading, or
  historical status from the released fields.
compatibility: Requires the catalogue CLI, Python 3.11+, a Companies House Live REST API key, and network access to api.company-information.service.gov.uk.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: gb/companies-house/companies
---

# Query Companies House companies

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `gb/companies-house/companies:search-companies` — Search official Companies House company summaries by term with offset pagination.
- `gb/companies-house/companies:get-company` — Retrieve official basic company information by exact Companies House company number.
<!-- END GENERATED OPERATION STATUS -->
## Authentication and quota

Create a Live REST API key and run `catalogue keys set companies-house`.
catalogue sends the key as the HTTP Basic username with an empty password and
keeps it out of prompts. Companies House publishes a limit of 600 requests per
five minutes; exceeding it returns 429. A 401 means unauthorised, not quota.

## Workflow

1. Assess the full request and inspect the operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show gb/companies-house/companies:search-companies
   ```

2. Search candidates with a small page, then retrieve the exact number:

   ```bash
   catalogue query gb/companies-house/companies --operation search-companies \
     --input '{"q":"BP","items_per_page":5,"start_index":0}'
   catalogue query gb/companies-house/companies --operation get-company \
     --input '{"company_number":"00102498"}'
   ```

3. Preserve company number exactly, status, type, dates, registered address,
   official profile URL, page metadata, and observation date.

## Boundaries and cautions

- Search rank and name are candidate evidence; resolve with the company number.
- Leading zeros and letter prefixes are meaningful.
- Basic profile status does not prove current commercial activity or status on
  a historical date.
- Officers, filings, charges, insolvency, registers, disqualifications, and PSC
  endpoints are documented provider scope but not released here.
- Register data is filed information and can be corrected or updated.

Read [the API reference](references/api-reference.md) and
[the query guide](references/query-guide.md) for response vocabulary,
pagination, no-result recovery, and follow-up verification.

## Bundled resources

- `references/api-reference.md` — official endpoint, profile, quota, auth,
  licensing, response mapping, and errors.
- `references/query-guide.md` — identity resolution and historical cautions.
- `scripts/verify.py` with `assets/verification-cases.json` — credentialed checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
