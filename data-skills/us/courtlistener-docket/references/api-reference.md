# CourtListener RECAP docket API reference

## Evidence checked

Primary provider material was fetched with Firecrawl on 2026-08-12; live JSON
and `OPTIONS` requests were used only to verify the documented contract.

| Evidence | URL | Supports |
|---|---|---|
| REST API v4.6 | https://www.courtlistener.com/help/api/rest/v4/ | authentication, limits, serialization, API families |
| Legal Search API | https://www.courtlistener.com/help/api/rest/v4/search/ | type `r`, fields, counts, snippets, caching |
| API root | https://www.courtlistener.com/api/rest/v4/ | current endpoint inventory |
| Terms and policies | https://www.courtlistener.com/terms/ | FCRA prohibition, credential/rate rules, mixed copyright warning |

## Endpoint and authentication

`GET https://www.courtlistener.com/api/rest/v4/search/`

catalogue always supplies `type=r`, `q`, `Accept: application/json`, and a
descriptive User-Agent. If configured, it sends:

```text
Authorization: Token <courtlistener-token>
```

CourtListener warns that many APIs are open for experimentation but deployed
clients should authenticate. Its current default authenticated limits are five
requests/minute, 50/hour, and 125/day, with higher access depending on
membership or agreement. A token is therefore not generically described as a
rate-limit increase.

## Search contract

Released inputs are `q`, `court`, `order_by`, `highlight`, and local `limit`
(1–20). `get-docket` translates an exact integer to `q=docket_id:<id>`.

The provider documents type `r` as one federal docket result with **up to three
nested matching documents**. `meta.more_docs=true` means there are additional
matches. Those three records are not a full docket sheet. Full entry/document
pagination requires other APIs not released here.

The provider says type `r` and `d` counts use cardinality aggregation and can
have about ±6% error above 2,000 results. catalogue exposes
`count_is_approximate` for that condition.

Search fields are camelCase and advanced operators belong in `q`. The API
recommends building/refining a front-end search and reusing its GET parameters.
Long OR chains are expensive and discouraged.

## Coverage, caching, and evidence

Search responses are cached for ten minutes. The provider recommends alerts,
not polling, for new-result monitoring. RECAP is a large public archive, not a
claim of complete PACER coverage. A missing search result is inconclusive.

Open every linked docket and filing before relying on a legal or factual claim.
Preserve docket ID, court ID, query, retrieval time, and the
`more_documents` limitation.

## Rights and prohibited use

CourtListener's terms state that judicial opinions, motions, and other filings
are generally public domain, while some filings can embed third-party
copyrighted works. That is not a blanket redistribution licence. The terms also
prohibit using CourtListener-derived information for FCRA eligibility or
consumer-report purposes and forbid account/token rotation to evade limits.
