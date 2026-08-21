# Companies House Public Data API reference

## Evidence checked

Primary Companies House material was fetched with Firecrawl on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Search companies endpoint | https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/search/search-companies | Search path, parameters, auth, response and 401 |
| Company profile endpoint | https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/company-profile/company-profile | Detail path, company-number input, auth, 200/401/404 |
| CompanySearch resource | https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companysearch?v=latest | Search response fields and status/type vocabularies |
| Rate-limiting guide | https://developer-specs.company-information.service.gov.uk/guides/rateLimiting | 600 requests per five minutes and 429 behavior |
| Get started | https://developer.company-information.service.gov.uk/get-started | Application/API-key setup and REST API context |
| Open Government Licence v3.0 | https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ | Crown data reuse and attribution |

The production search and profile endpoints returned documented 401 responses
without a key. No key is configured, so successful live cases are pending;
official-shape fixtures exercise both normalizers.

## Provider scope and released coverage

Companies House documents search, advanced/alphabetic/dissolved search, company
profiles, addresses, officers, filing history, charges, insolvency, registers,
UK establishments, disqualifications, and PSC resources.

| Endpoint | Operation | Status |
|---|---|---|
| `GET /search/companies` | `search-companies` | Released |
| `GET /company/{companyNumber}` | `get-company` | Released |
| Other documented endpoints | None | Not wrapped |

## Authentication and rate limit

Released calls use a Live REST API key as HTTP Basic username with an empty
password. Sandbox keys and production keys are separate. The official limit is
600 requests in a five-minute application window. Exceeding it returns 429 for
the rest of that window. Official search docs reserve 401 for unauthorized.

## `search-companies`

| Navigator field | Provider parameter | Semantics |
|---|---|---|
| `q` | `q` | Required search term. |
| `items_per_page` | same | Navigator bounds 1–100. |
| `start_index` | same | Zero-based first-result index. |

Companies House also documents `restrictions`, including active/company-name-
availability modes, but Navigator does not expose it. Search response includes
`items`, `items_per_page`, `start_index`, and `total_results`.

## `get-company`

The provider path uses exact `company_number`. Navigator accepts 1–8
alphanumeric characters, uppercases letters, and preserves leading zeros. Do
not parse the identifier as an integer. A 404 is a missing resource, not an
empty search page.

## Response mapping

| Normalized field | Search/profile field | Interpretation |
|---|---|---|
| `name` | `title` / `company_name` | Registered display name. |
| `company_number` | same | Stable register identifier in the response. |
| `status` | `company_status` | Provider status vocabulary. |
| `company_type` | `company_type` / `type` | Provider company-type code. |
| `incorporation_date` | `date_of_creation` | Provider creation date. |
| `cessation_date` | `date_of_cessation` | Nullable cessation date. |
| `registered_address` | `address_snippet` / `registered_office_address` | Search string or flattened profile address. |
| `source_url` | constructed from company number | Official Find and update company page. |

Current documented status values include active, dissolved, liquidation,
receivership, administration, voluntary-arrangement, converted-closed,
insolvency-proceedings, registered, and removed. Preserve unknown future values.

## Errors and no-result behavior

- 401: unauthorized key; correct configuration.
- 404 on detail: re-resolve company number; do not retry unchanged.
- 429: official quota exhaustion; wait until the five-minute window resets.
- 5xx/network: transient upstream failure; bounded retry.
- Empty search: bounded result for the exact term/page, not proof no UK entity exists.

## Known gaps and drift risks

- Filed information can be late, corrected, contested, or fraudulent.
- `active` is register status, not proof of trading, solvency, ownership, or a
  particular historical state.
- Search address is a snippet and can differ from current profile address.
- Officers and PSC data have privacy/suppression considerations and are not
  inferable from company profiles.
- Company type and status vocabularies can expand.
