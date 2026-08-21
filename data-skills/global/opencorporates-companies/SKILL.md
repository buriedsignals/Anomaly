---
name: opencorporates-companies
description: >-
  Use this skill to search OpenCorporates company records across jurisdictions
  or retrieve one exact company by jurisdiction and registry number, preserving
  status, inactive mapping, source publisher, source retrieval time, registry
  links, and OpenCorporates attribution. Apply it to corporate entity
  resolution; do not infer ownership, current activity, solvency, or official
  legal status beyond the returned and corroborated registry fields.
compatibility: Requires the catalogue CLI, Python 3.11+, an OpenCorporates API token, and network access to api.opencorporates.com.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/opencorporates/companies
---

# Query OpenCorporates companies

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/opencorporates/companies:search-companies` — Search company records with bounded pagination and optional jurisdiction and inactive-state filters.
- `global/opencorporates/companies:get-company` — Retrieve an exact company record using its OpenCorporates jurisdiction code and registry number.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Inspect the operation contract and jurisdiction semantics:

   ```bash
   catalogue data show global/opencorporates/companies:search-companies
   ```

2. Search with a small page and compare jurisdiction, number, status, address,
   and provenance rather than selecting the first name match:

   ```bash
   catalogue query global/opencorporates/companies --operation search-companies \
     --input '{"q":"Barclays","jurisdiction_code":"gb","per_page":10,"page":1}'
   ```

3. When jurisdiction and company number are known, use exact lookup and
   preserve leading zeroes:

   ```bash
   catalogue query global/opencorporates/companies --operation get-company \
     --input '{"jurisdiction_code":"gb","company_number":"00102498"}'
   ```

Read [the API reference](references/api-reference.md) for current pagination,
status, provenance, token, and licence semantics and
[the query guide](references/query-guide.md) for entity resolution and registry
corroboration.

## Status and provenance discipline

- `current_status` and OpenCorporates' boolean `inactive` mapping are distinct.
  Missing `inactive: true` does not prove activity because not every register
  supplies status.
- Preserve `source_retrieved_at`, `updated_at`, publisher, registry URL, source
  terms, and OpenCorporates URL. Aggregated records can lag the official register.
- Search results do not return ownership or complete officer networks through
  this skill.
- A missing record can reflect spelling, jurisdiction, number format, provider
  coverage, pagination, or source lag; it is not proof the company never existed.

## Authentication and reuse

Store the token with `catalogue keys set opencorporates`; never place it in
prompts or command arguments. Usage depends on the account and can be inspected
through the provider's `/account_status` route. Follow OpenCorporates ODbL
attribution/share-alike requirements and any underlying source terms preserved
on the record.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved official API contract,
  pagination, provenance, status, authentication, and reuse requirements.
- `references/query-guide.md` — search, exact lookup, disambiguation, and
  official-register verification.
- `scripts/verify.py` with `assets/verification-cases.json` — credential-aware
  search and exact-lookup checks.
- `evals/evals.json` — status, identity, provenance, and licence cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
