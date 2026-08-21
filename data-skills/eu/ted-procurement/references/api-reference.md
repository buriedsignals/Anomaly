# TED Search API v3 reference

## Evidence checked

Primary TED material was fetched with Firecrawl and the machine-readable API
contract was checked against the live service on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| TED API v3 overview | https://docs.ted.europa.eu/api/latest/index.html | API families, anonymous published-notice access, key boundary, v3 context |
| Search API documentation | https://docs.ted.europa.eu/api/latest/search.html | Published-notice purpose, expert queries, XML download, no authentication |
| Live Swagger UI | https://api.ted.europa.eu/swagger-ui/index.html#/Search/search | Interactive primary contract |
| OpenAPI YAML | https://api.ted.europa.eu/api-v3.yaml | Exact request fields, pagination modes, limits, scopes, and error schemas |
| TED CPV reference | https://ted.europa.eu/en/simap/cpv | Hierarchical procurement vocabulary |
| TED country codelist | https://docs.ted.europa.eu/eforms/latest/reference/code-lists/country.html | Three-character country values and extensions |

## Provider scope and authentication boundary

TED API covers published-notice search/retrieval as well as authenticated
validation, publication, management, and rendering workflows for notice
submitters. Anonymous access applies to services manipulating already published
notices. Unpublished notice APIs require an API key and are not Navigator scope.

The released operation calls:

```text
POST https://api.ted.europa.eu/v3/notices/search
```

## Request mapping

| Navigator input | TED body | Semantics |
|---|---|---|
| `query` | `query` | Non-empty TED expert query; takes precedence over shortcuts. |
| `cpv` | builds `classification-cpv={8 digits}` | Optional ninth check digit is validated then removed for the query. |
| `country` | builds `buyer-country={alpha-3}` | Supported alpha-2 shortcuts are mapped; alpha-3 passes through. |
| `limit` | `limit` | Navigator 1–100; provider permits up to 250 notices per page and 10,000 returned fields per page. |
| `page` | `page` | One-based page in `PAGE_NUMBER` mode. |
| `scope` | `scope` | `LATEST`, `ACTIVE`, or `ALL`; defaults to `ALL`. |
| `only_latest_versions` | `onlyLatestVersions` | Boolean version filter. |

The adapter requests five fields: `publication-number`, `notice-title`,
`buyer-name`, `buyer-country`, and `publication-date`.

## Pagination

The current OpenAPI documents:

- `PAGE_NUMBER`: choose a page but retrieve no more than 15,000 notices for one
  query;
- `ITERATION`: follow an opaque `iterationNextToken`, with no equivalent
  retrievable-notice ceiling but no random page selection.

Navigator releases only page-number mode. Do not emulate iteration by guessing
tokens or deep page values.

## Response mapping

| Normalized field | TED field | Interpretation |
|---|---|---|
| `publication_number` | `publication-number` | Notice publication identifier and link pivot. |
| `name` | `notice-title` | English value when available, otherwise first multilingual value. |
| `buyer` | `buyer-name` | Same multilingual fallback. |
| `buyer_country` | `buyer-country` | Returned provider value, normally alpha-3. |
| `publication_date` | `publication-date` | First ten characters of provider date. |
| `source_url` | constructed notice page | Human-readable TED notice. |

The response reports `totalNoticeCount`; Navigator preserves it with requested
page and limit. A total is a count for the exact expert query and scope, not a
count of contracts executed.

## Errors and no-result behavior

The OpenAPI enumerates 400 errors for syntax, unknown fields, unsupported field
operations, unsupported values, and invalid/expired iteration tokens. Correct
the query instead of retrying unchanged. Empty `notices` is a bounded negative
search. Honor 429 and retry transient 5xx/timeouts with bounded backoff.

## Reuse and attribution

TED describes published-notice search and XML download as available for reuse
and analysis. Preserve European Union/Publications Office/TED attribution,
notice identifiers, and source links. Full notices can include supplier or
attachment material requiring its own rights assessment.

## Known gaps and drift risks

- Expert-query vocabulary is large and versioned; an accepted field can change.
- CPV and NUTS are hierarchical and require scope-aware interpretation.
- Notices can be changed, corrected, cancelled, or superseded.
- Search output does not establish award winner, lot value, currency, or execution.
- Multilingual fallback can return a non-requested language.
- Page totals and active/latest scopes are time-sensitive.
