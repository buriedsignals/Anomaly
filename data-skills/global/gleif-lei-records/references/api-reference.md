# GLEIF API reference

## Evidence checked

Primary GLEIF material was fetched with Firecrawl and checked against the live
API on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| GLEIF API overview | https://www.gleif.org/en/lei-data/gleif-api | Provider scope, search capabilities, Level 1 and Level 2 data, quota |
| GLEIF API documentation | https://api.gleif.org/docs | JSON:API routes, filters, pagination, relationships, and mappings |
| LEI Data Terms of Use | https://www.gleif.org/en/lei-data/gleif-lei-data-terms-of-use | Reuse terms and attribution context |

## Provider scope and released coverage

GLEIF documents legal-entity identity records (Level 1), direct and ultimate
parent relationships (Level 2), reporting exceptions, fuzzy completion,
field-specific filters, and identifier mappings including BIC and ISIN.

Navigator releases one bounded `lei-records` operation with three filter modes.
Relationship traversal, fuzzy completion, and identifier mapping are not
released and must not be approximated from name results.

## Released request

`GET https://api.gleif.org/api/v1/lei-records`

| `search_field` | Upstream parameter | Purpose |
|---|---|---|
| `fulltext` | `filter[fulltext]` | Broad discovery across provider-indexed text. |
| `legal_name` | `filter[entity.legalName]` | Field-specific legal-name filter. Do not call it independently verified identity. |
| `lei` | `filter[lei]` | Exact 20-character LEI filter; input is uppercased. |

Additional released fields:

| Navigator field | Upstream parameter | Semantics |
|---|---|---|
| `jurisdiction` | `filter[entity.jurisdiction]` | Two-letter legal-jurisdiction code. This is not the legal-address country filter. |
| `limit` | `page[size]` | Bounded by Navigator to 1–100. |
| `page` | `page[number]` | One-based page number. |

Live checks confirmed that `entity.jurisdiction=NO` and
`entity.legalAddress.country=NO` produce different totals. The adapter uses the
former because its input is explicitly legal jurisdiction.

## Pagination

The JSON:API response reports `currentPage`, `perPage`, `from`, `to`, `total`,
and `lastPage` under `meta.pagination`. Navigator exposes current page, page
size, total records, total pages, and returned record count. Totals can change
as the live LEI data pool updates.

## Response mapping

| Normalized field | GLEIF field | Interpretation |
|---|---|---|
| `lei` | `attributes.lei` | Global Legal Entity Identifier. |
| `name` | `entity.legalName.name` | Provider legal name. |
| `jurisdiction` | `entity.jurisdiction` | Legal jurisdiction. |
| `registered_as` | `entity.registeredAs` | Identifier at the validation authority, when supplied. |
| `category` | `entity.category` | GLEIF entity category. |
| `legal_form` | `entity.legalForm.id` or `.other` | ELF code or provider text. |
| `status` | `entity.status` | Entity status layer. |
| `registration_status` | `registration.status` | LEI registration status layer. |
| `next_renewal_date` | `registration.nextRenewalDate` | LEI record renewal date, not entity expiry. |
| `corroboration_level` | `registration.corroborationLevel` | GLEIF validation metadata. |
| `address` | `entity.legalAddress` | Flattened provider legal address. |
| `source_url` | record `links.self` | Exact GLEIF API record. |

## Authentication, quota, and terms

- Public released calls require no key.
- GLEIF publishes a limit of 60 requests per minute per user. Keep automated
  verification bounded and honor 429 responses.
- GLEIF makes LEI data openly available under its LEI Data Terms of Use.
  Preserve provenance and recheck the terms for downstream redistribution.

## Status interpretation

Entity and registration state are independent. In particular, an LEI record
can be `LAPSED` because renewal was not maintained while the entity remains
`ACTIVE`. Never convert a registration state into a dissolution claim.

## Errors and no-result behavior

- Malformed LEIs and invalid jurisdiction values are rejected locally.
- A successful empty `data` array is a bounded negative search, not proof that
  the entity does not exist.
- Provider 4xx means fix filters rather than retry unchanged.
- Honor 429 and retry with bounded delay.
- Preserve timeout, DNS, and 5xx errors as upstream failures.

## Known gaps and drift risks

- Only entities participating in the LEI system are represented.
- Legal names, addresses, entity status, and validation metadata can change.
- A national identifier can be absent or formatted differently from the local
  register.
- Provider fuzzy-completion results carry separate limitations and are not
  interchangeable with released full-text search.
- Ownership relationships require Level 2 records and reporting-exception
  handling; they cannot be inferred from common addresses or names.
