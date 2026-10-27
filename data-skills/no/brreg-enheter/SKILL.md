---
name: brreg-enheter
description: >-
  Use this skill to search Norway's Brønnøysund Register Centre main entities
  by name or retrieve one by an exact nine-digit organisation number. Apply it
  to Norwegian legal-entity resolution and current register observations; do
  not confuse main entities with sub-entities or infer historical status from
  the current record.
compatibility: Requires Python 3.11+ and network access to data.brreg.no.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: no/brreg/enheter
---

# Query Norway's main-entity register

Use only released operations and treat `meta.yaml` as the executable contract.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `no/brreg/enheter:search-companies` — Search Norwegian main entities by provider name semantics with explicit page and page size.
- `no/brreg/enheter:get-company` — Retrieve one Norwegian main entity by its exact nine-digit organisation number.
- `no/brreg/enheter:companies` — Main entities by number, name or business postal code as companies-contract rows.
- `no/brreg/enheter:company-officers` — An entity's current roles as company_officers rows.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete question and inspect the operation contract:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show no/brreg/enheter:search-companies
   ```

2. Search with a small page, retain all plausible candidates, then retrieve the
   chosen organisation number:

   ```bash
   catalogue query no/brreg/enheter --operation search-companies \
     --input '{"navn":"Equinor","size":5,"page":0}'
   catalogue query no/brreg/enheter --operation get-company \
     --input '{"organisasjonsnummer":"923609016"}'
   ```

3. Preserve the organisation number, provider URL, page metadata, and
   observation date. See [the query guide](references/query-guide.md) before
   interpreting employee, bankruptcy, address, or industry fields.

## Source boundary

Released scope covers the provider's `enheter` main-entity search and detail
routes, plus the open roles route. Sub-entities (`underenheter`), group structure, change feeds,
nonprofit information, organisation forms, and bulk downloads are documented
provider capabilities but are not released operations here.

## Fill the companies contract

`companies` (one `organisasjonsnummer`, or `navn` and/or a four-digit
`postnummer`, up to 100 per page) and `company-officers` (one
`organisasjonsnummer`, via `/enheter/{orgnr}/roller`) return rows of
`domains/companies.yaml`. The open API publishes no ownership, so Brreg fills
no `company_controllers`; run `prolific_officer` with a header-only
controllers file. Parameters follow the API documentation
(https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html, read
2026-10-27).

| If the source publishes | map it to column |
|---|---|
| `organisasjonsnummer` | `company_id` = `no:` + number; `jurisdiction` = `NO` |
| `navn` | `name` |
| `konkurs`; `underAvvikling` or `underTvangsavviklingEllerTvangsopplosning` | `status` = `bankrupt`; `in_liquidation`; else `active` |
| `stiftelsesdato`, else `registreringsdatoEnhetsregisteret` | `incorporation_date` |
| (deleted entities leave the open API) | `dissolution_date` stays empty |
| `forretningsadresse.adresse[]`, `postnummer`, `poststed` | `registered_address` |
| `historiskeNavn[]` | `previous_name_count` |
| role `enhet.organisasjonsnummer` (corporate role) | `officer_id` = `no:` + number |
| role `person.navn` + `person.fodselsdato` | `officer_id` = `no:person:` + upper-case name + `\|` + birth date |
| role `type.kode` (DAGL, LEDE, MEDL, REVI, REGN, ...) | `role` |
| role `avregistrert: true` | dropped: the open API gives no end date |
| (not published) | `appointed_on`, `resigned_on`, `company_name` stay empty |

A postal code covers an area, not one building, so search by `postnummer` to
collect candidates and let `shared_registered_address` group them by the full
street address. Auditors (REVI) and accountants (REGN) hold many roles by
trade; `prolific_officer` excludes them by default.

## Interpretation cautions

- Name search returns candidates, not an identity decision.
- Organisation numbers contain exactly nine digits; preserve leading zeros.
- `konkurs`, employee count, address, and registration fields are mutable.
- A missing main entity can still be present as a sub-entity or outside this
  register's scope; absence is not proof of non-existence.
- Provider fields are Norwegian; normalization does not change their meaning.

## Bundled resources

- [API reference](references/api-reference.md) — official endpoints, fields,
  page behavior, licence, and released coverage.
- [Query guide](references/query-guide.md) — entity resolution and no-result recovery.
- `scripts/verify.py` and `assets/verification-cases.json` — bounded live checks.
- `evals/evals.json` — forward agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
