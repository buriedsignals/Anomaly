# OpenCorporates company API reference

## Evidence checked

Official material was fetched with Firecrawl on 2026-08-12 and compared with
the adapter's recorded search and exact-company response shapes.

| Evidence | URL | Supports |
|---|---|---|
| REST API reference, version 0.4.8 | https://api.opencorporates.com/documentation/API-Reference | Company search/detail, authentication, pagination, filters, provenance, response fields, account status |
| OpenCorporates licence | https://opencorporates.com/legal/licence | Open-data attribution and share-alike terms |
| Terms of use | https://opencorporates.com/terms-of-use-2/ | Current service and use conditions |

## Authentication and base

- Base: `https://api.opencorporates.com/v0.4`
- Credential: `api_token=<token>` query parameter
- Every API call requires an API key; limits depend on account type and plan.
- `GET /account_status` reports daily/monthly usage. The documentation states
  daily usage refreshes at midnight UTC and monthly usage at the month boundary.

catalogue retrieves the token from its key store and never places it in agent
context. HTTPS is mandatory in this skill because a query-parameter key would
otherwise be exposed in transit.

## Search companies

`GET /companies/search`

Released inputs:

| catalogue | Provider | Meaning |
|---|---|---|
| `q` | `q` | Required company-name query |
| `jurisdiction_code` | same | Optional provider jurisdiction filter |
| `inactive` | same | true restricts to inactive; false excludes inactive; omitted does not filter |
| `per_page` | same | 1–100; provider default 30, catalogue default 10 |
| `page` | same | 1–100; the provider caps pages at 100 |

Search returns pagination metadata including page, per-page count, total count,
and total pages. A single page is not complete enumeration. The API offers many
additional filters, but this skill does not silently accept them until they are
modeled and tested.

## Exact company lookup

`GET /companies/{jurisdiction_code}/{company_number}`

Both identifiers are required. Company numbers are strings and can include
meaningful leading zeroes. catalogue quotes path components and preserves the
returned identifiers unchanged.

## Status semantics

The provider returns both:

- `current_status`: source-derived status text when available;
- `inactive`: OpenCorporates' boolean mapping from multiple inactive statuses
  such as dissolved, removed, or liquidated.

The official documentation warns that not all sources make status available;
therefore a record not marked inactive cannot automatically be called active.
catalogue exposes these fields separately instead of overwriting
`current_status` with the word "inactive."

## Provenance and freshness

OpenCorporates emphasizes source provenance. Detailed records can include:

- company and source retrieval/update timestamps;
- original publisher and source URL;
- source-specific terms;
- official registry URL;
- OpenCorporates attribution URL.

catalogue normalizes these as `updated_at`, `source_retrieved_at`,
`source_publisher`, `source_registry_url`, `source_terms`, `registry_url`, and
`source_url`. A null `source_terms` field does not mean no underlying rights
apply. Check the official register for time-sensitive or consequential claims.

## Licence and attribution

The API reference identifies OpenCorporates database rights under the Open
Database Licence and explains that returned OpenCorporates URLs support
attribution. ODbL requires attribution and can impose share-alike conditions on
adapted databases. Underlying registry data can carry its own terms, recorded
where known in the source object.

This skill declares caching and redistribution as permitted at the source
metadata level, but that is not a blanket legal conclusion for every downstream
use. Preserve attribution and evaluate the database-versus-individual-record
use, underlying terms, and applicable jurisdiction.
