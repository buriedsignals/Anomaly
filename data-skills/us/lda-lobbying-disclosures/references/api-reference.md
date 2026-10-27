# LDA.gov REST API reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27.

| Evidence | URL | Supports |
|---|---|---|
| API landing page | https://lda.gov/api/ | Key registration, LD-1/LD-2 and LD-203 scope |
| API documentation v1 | https://lda.gov/api/redoc/v1/ | Endpoints, filters, fields, pagination, throttling, lda.senate.gov sunset |
| API terms of service | https://lda.gov/api/tos/ | Anonymous vs key access, citation requirement |
| Live filings page (via Firecrawl) | https://lda.gov/api/v1/filings/?registrant_name=Akin%20Gump&filing_year=2025&page_size=2&format=json | Real response shape: `count`, `next`, nested `registrant`, `client`, `lobbying_activities`, `foreign_entities` |

Not verified: direct requests from this host got HTTP 403 "Access Denied"
(also from senate.gov and congress.gov), so the adapter's own HTTP calls were
not exercised live; its mapping was run on the Firecrawl-fetched page.

## Host and access

- Base: `https://lda.gov/api/v1/`. The old `lda.senate.gov` API was
  deprecated 2026-01-09 and sunset 2026-07-31.
- Anonymous: 15 requests/minute per IP. Registered key: 120/minute, sent as
  `Authorization: Token <key>`. HTTP 429 carries `Retry-After`.
- Pages hold at most 25 results (`page_size`); paging past page 1 of
  `filings` or `contributions` needs at least one filter.

## Endpoints and mapping

`GET /filings/` filters used: `registrant_name`, `registrant_id`,
`client_name`, `client_id`, `filing_year`, `filing_period`
(`first_quarter`..`fourth_quarter`, `mid_year`, `year_end`), `filing_type`,
`filing_uuid`.

The field-to-column mapping onto the lobbying contract is in `SKILL.md`
("Column mapping").

`GET /contributions/` (LD-203) filters used: `registrant_name`,
`registrant_id`, `filing_year`, `filing_period` (`mid_year`, `year_end`),
`filing_uuid`, `lobbyist_name`, `contribution_payee`, `contribution_honoree`.
Each `contribution_items[]` entry becomes one `political_contributions` row
(`payee_name`, `honoree_name`, `amount`, `contributor_name`, plus `date` and
`contribution_type`).

## Terms

Cite the date the data were retrieved and state that the Senate Office of
Public Records cannot vouch for the data or analyses derived from them after
retrieval. Do not use the Senate seal.
