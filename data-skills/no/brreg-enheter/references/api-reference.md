# Brønnøysund Register Centre API reference

## Evidence checked

Primary provider material was fetched with Firecrawl and checked against the
live API on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Register of Business Enterprises API documentation, English, version 2.0 | https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html | Paths, filters, paging, response models, bulk data, and access boundaries |
| Norwegian Licence for Open Government Data 2.0 | https://data.norge.no/nlod/en/2.0 | Reuse, attribution, and licence conditions |

## Provider scope and released coverage

| Provider capability | Provider route or area | Navigator status |
|---|---|---|
| Search main entities | `GET /enhetsregisteret/api/enheter` | `search-companies` released |
| Get one main entity | `GET /enhetsregisteret/api/enheter/{organisasjonsnummer}` | `get-company` released |
| Search/detail sub-entities | `underenheter` routes | Not wrapped |
| Organisation forms | `organisasjonsformer` | Not wrapped |
| Roles and group structure | Documented role/group routes | Not wrapped; some provider access is restricted |
| Updates and bulk data | Update endpoints and JSON/CSV/XLSX downloads | Not wrapped |

## `search-companies`

`GET https://data.brreg.no/enhetsregisteret/api/enheter`

| Navigator field | Provider parameter | Semantics |
|---|---|---|
| `navn` | `navn` | Required name query for released search. Treat results as candidates. |
| `size` | `size` | Page size bounded by Navigator to 1–100. |
| `page` | `page` | Zero-based page number; defaults to 0. |

The HAL-style response returns entities under `_embedded.enheter`, links under
`_links`, and `size`, `totalElements`, `totalPages`, and `number` under `page`.
Navigator preserves the essential page values and record count.

## `get-company`

`GET https://data.brreg.no/enhetsregisteret/api/enheter/{organisasjonsnummer}`

The identifier must contain exactly nine digits. A successful response is one
entity object, normalized into a one-record result. A 404 must not be disguised
as an empty name search.

## Response mapping

| Normalized field | Provider field | Interpretation |
|---|---|---|
| `name` | `navn` | Registered name. |
| `company_number` | `organisasjonsnummer` | Nine-digit organisation number. |
| `legal_form` | `organisasjonsform.beskrivelse` | Provider description of organisation form. |
| `incorporation_date` | `registreringsdatoEnhetsregisteret` | Registration date in this register, not necessarily founding date. |
| `employees` | `antallAnsatte` | Mutable provider observation and sometimes absent. |
| `industry_code` | `naeringskode1.kode` | Primary industry classification code. |
| `industry_description` | `naeringskode1.beskrivelse` | Provider classification label. |
| `address` | `forretningsadresse` | Flattened business address. |
| `bankrupt` | `konkurs` | Current provider boolean at observation time. |
| `website` | `hjemmeside` | Provider-supplied value; not necessarily verified or normalized as a URL. |
| `source_url` | `_links.self.href` | Exact API record link. |

## Authentication, quota, and licence

- Released endpoints require no API key.
- The checked public documentation does not establish an exact request quota
  for these calls; honor 429 responses and keep verification bounded.
- Data is offered under NLOD 2.0. Preserve provider attribution and the licence
  terms in redistributed material.

## Errors and no-result behavior

- Empty search page: valid bounded negative result; inspect page metadata.
- Invalid organisation number: rejected before the request.
- Detail 404: re-resolve the identifier; do not retry unchanged.
- Provider 4xx: fix the declared input instead of broadening silently.
- 429, timeout, DNS, or 5xx: transient upstream failure; retry with bounded backoff.

## Known gaps and drift risks

- Main entities and sub-entities are separate datasets.
- Historic names can appear in provider data, but released output does not
  normalize the full history.
- Employee, address, industry, website, bankruptcy, liquidation, and register
  flags change over time.
- Some fields are nullable or absent for particular legal forms.
- Provider page totals can change between requests during pagination.
