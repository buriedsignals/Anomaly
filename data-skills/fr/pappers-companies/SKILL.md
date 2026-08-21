---
name: pappers-companies
description: >-
  Use this skill to search French company candidates and retrieve a company by
  exact SIREN through Pappers API v2 with a member-provided key. Apply it to
  French legal-entity resolution using lean, credit-aware calls; do not request
  unwrapped officers or beneficial owners, expose the key, or interpret blank
  partial-diffusion fields as proof of absence or misconduct.
compatibility: Requires Python 3.11+, a Pappers API key, and network access to api.pappers.fr.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: fr/pappers/companies
---

# Query Pappers company records

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `fr/pappers/companies:search-companies` — Search Pappers company records by denomination text using page-number mode within the provider's first-400-result ceiling.
- `fr/pappers/companies:get-company` — Retrieve the Pappers company profile for one exact nine-digit SIREN without paid enriched fields.
<!-- END GENERATED OPERATION STATUS -->
## Authentication and credits

Provide the key through the execution context. The adapter sends it in
the recommended `api-key` header and never exposes it to the agent. The checked
pricing page assigns 0.1 credit per search result and one credit per company
profile; supplementary fields can cost more. This adapter requests only the
free `lien_pappers` supplement on detail.

## Workflow

1. Assess the full request and inspect the exact operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show fr/pappers/companies:search-companies
   ```

2. Search a small page, compare candidates, then retrieve the chosen SIREN:

   ```bash
   catalogue query fr/pappers/companies --operation search-companies \
     --input '{"q":"Danone","par_page":3,"page":1}'
   catalogue query fr/pappers/companies --operation get-company \
     --input '{"siren":"552032534"}'
   ```

3. Preserve SIREN, legal name, legal form, NAF code, status, dates, address,
   employee-band code, provider link, and observation date.

## Boundaries and cautions

- SIREN is nine digits for the legal unit; SIRET is fourteen digits for an
  establishment and is not a released input.
- Page-number search is capped at the first 400 provider results. Cursor search
  is documented upstream but not released.
- Some companies elect partial INSEE diffusion; documented fields can be null.
- Pappers integrates multiple public sources and updates daily, but the result
  is still provider data rather than independent confirmation.
- Officer, beneficial-owner, document, account, graph, and monitoring endpoints
  are not released. Some beneficial-owner access requires authorization.

Read [the API reference](references/api-reference.md) and
[the query guide](references/query-guide.md) before interpreting coverage,
employee bands, or negative results.

## Bundled resources

- `references/api-reference.md` — official API/price evidence, mappings,
  pagination, credits, diffusion, and errors.
- `references/query-guide.md` — SIREN resolution and evidence limits.
- `scripts/verify.py` with `assets/verification-cases.json` — credentialed checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py  # consumes a small number of Pappers credits
```
