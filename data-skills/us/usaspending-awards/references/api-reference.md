# USAspending Spending by Award API reference

## Evidence checked

Primary Treasury material was fetched with Firecrawl on 2026-08-12:

| Evidence | URL |
|---|---|
| Endpoint index | https://api.usaspending.gov/docs/endpoints |
| Introductory tutorial | https://api.usaspending.gov/docs/intro-tutorial |
| Source-controlled endpoint contract | https://raw.githubusercontent.com/fedspendingtransparency/usaspending-api/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_award.md |

The source-controlled contract is published from the official USAspending API
repository and defines the request/response fields used here.

## Endpoint

`POST https://api.usaspending.gov/api/v2/search/spending_by_award/`

Required body objects are `filters` and `fields`. Optional controls include
`limit` (default 10), `page`, `sort`, `order` (`asc`/`desc`), and `subawards`.
Navigator fixes `subawards=false`, validates limit 1–100 locally, and exposes
page/sort/order. The response includes results, `page_metadata.hasNext`, and
optional messages.

## Released filters

- `time_period`: one explicit start/end pair derived from dates or federal FY.
- `award_type_codes`: required and mapped from the selected group.
- `keywords`: broad award keyword search.
- `recipient_search_text`: searches recipient name, UEI, and DUNS.
- `award_ids`: Navigator surrounds the supplied ID with quotes because the
  provider documents quoted award IDs as exact rather than fuzzy matches.

Provider-supported agency, geography, amount, program, NAICS, PSC, TAS, DEFC,
and many other filters remain outside this release.

## Award groups and codes

| Group | Codes |
|---|---|
| contracts | A, B, C, D |
| grants | 02, 03, 04, 05 |
| loans | 07, 08 |
| IDVs | IDV_A, IDV_B, IDV_B_A, IDV_B_B, IDV_B_C, IDV_C, IDV_D, IDV_E |
| direct payments | 06, 10 |
| other assistance | 09, 11, -1 |

The compatibility group `other` combines direct-payment and other-assistance codes.

## Type-compatible fields

The API contract does not allow every field for every award type. Navigator
therefore requests a base set plus:

- contracts/IDVs: Award Amount, Total Outlays, contract type, NAICS, PSC, and
  applicable performance/order dates;
- grants/non-loan assistance: Award Amount, Total Outlays, Award Type, CFDA and
  assistance listings, and performance dates;
- loans: Issued Date, Loan Value, Subsidy Cost, CFDA and assistance listings.

`amount` normalizes Award Amount or Loan Value; it is not a transaction,
obligation, outlay, invoice, or payment. Those concepts require their own fields
or endpoints.

## Identity and updates

`generated_internal_id` builds the official award-profile URL. Resolve
recipient names with UEI and other identifiers. USAspending data can be updated
or corrected; preserve retrieval date, time window, filters, page, and messages.
