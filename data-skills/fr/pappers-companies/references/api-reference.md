# Pappers API v2 reference

## Evidence checked

Primary Pappers material was fetched with Firecrawl on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Pappers API documentation, version 2.20.0 when checked | https://www.pappers.fr/api/documentation | Authentication, endpoints, filters, response fields, partial diffusion, errors |
| Pappers API product and pricing page | https://www.pappers.fr/api | Credit packs, per-operation consumption, free account, source integration and update claims |

The production endpoints were also called without credentials and returned the
documented 401. No Pappers key is configured in this workspace, so successful
live response verification remains pending; fixtures use documented fields.

## Provider scope and released coverage

Pappers documents company and association profiles; company, officer,
beneficial-owner, document, and publication searches; autocomplete; annual
accounts; corporate graphs; document downloads; monitoring; webhooks; and
credit-usage lookup.

| Endpoint | Operation | Release status |
|---|---|---|
| `GET https://api.pappers.fr/v2/recherche` | `search-companies` | Released |
| `GET https://api.pappers.fr/v2/entreprise` | `get-company` | Released |
| All other documented endpoints | None | Not wrapped |

## Authentication and credits

The documentation permits the `api-key` header or discouraged `api_token`
query parameter. catalogue uses only the header so secrets do not enter URLs or
logs. The checked pricing page states:

- company profile: one credit;
- company/officer/beneficiary/document search: 0.1 credit per result;
- autocomplete: free up to its published IP/day condition, then per-result;
- many supplementary fields consume additional credits.

Released detail requests ask only for `champs_supplementaires=lien_pappers`,
which the documentation lists as free. Do not add enriched fields ad hoc.

## `search-companies`

| catalogue field | Provider parameter | Semantics |
|---|---|---|
| `q` | `q` | Company denomination or natural-person name text. |
| `page` | `page` | One-based page; defaults to 1. |
| `par_page` | `par_page` | Provider page size; catalogue caps at 100. |

The provider says all search filters are optional, but catalogue requires `q`
to avoid costly broad search. Pappers page-number pagination is limited to the
first 400 results. Provider cursor fields (`curseur`, `par_curseur`, and
`curseurSuivant`) cover deeper traversal but are not released.

Responses contain `resultats`, `total`, and `page`. Provider 404 means no
matching companies; it is not a successful empty array and should be reported
as a bounded no-result condition.

## `get-company`

`siren` must contain nine digits. Pappers also accepts SIRET upstream, but the
released operation intentionally resolves legal units only by SIREN. The API
documents some companies unknown to INSEE and an opt-in
`autoriser_absence_insee`; catalogue does not enable it because resulting legal
category and registered-office fields can be null and need a separate contract.

## Response mapping

| Normalized field | Pappers field | Interpretation |
|---|---|---|
| `name` | `nom_entreprise`, `denomination`, or `nom_complet` | Provider display identity. |
| `siren` | `siren` | Nine-digit legal-unit identifier. |
| `legal_form` | `forme_juridique` | Provider legal-form label. |
| `naf_code`, `naf_label` | `code_naf`, `libelle_code_naf` | Activity classification; not proof of every activity. |
| `incorporation_date` | `date_creation` | Provider creation date. |
| `cessation_date` | `date_cessation` | Nullable provider cessation date. |
| `status` | `statut_consolide`, otherwise `entreprise_cessee` | Consolidated provider status preferred; boolean fallback normalized. |
| `registered_address` | `siege` fields | Flattened registered office; can be null under diffusion rules. |
| `employees_range` | `effectif`, otherwise `tranche_effectif` | Human band if returned, otherwise band code. |
| `employee_band_code` | `tranche_effectif` | SIRENE employee-band code. |
| `source_url` | `lien_pappers`, otherwise constructed | Pappers company page. |

## Partial diffusion and errors

Pappers warns that companies in partial INSEE diffusion can have nullable name,
person, and address fields; rare companies may not be known by INSEE. Therefore
a blank field is not proof the underlying fact is absent or deliberately
concealed.

- 401: invalid API key; fix configuration, do not retry.
- 404: no company/detail under the requested scope; recheck identity.
- 503 or network failure: transient; retry with bounded delay.
- Exhausted credits: the product page states API calls stop; inspect account
  usage rather than looping.

## Known gaps and drift risks

- Pappers integrates INSEE, INPI, BODACC, RNA, and other sources; update timing
  and disagreements can vary by field.
- Search ranking and precision defaults can change; catalogue does not expose
  the provider's precision filter.
- Page-number search is incomplete past 400 results.
- Employee bands, status, NAF, address, and name are time-sensitive.
- Commercial reuse depends on Pappers terms and each underlying dataset;
  redistribution is conservatively disabled in the contract.
