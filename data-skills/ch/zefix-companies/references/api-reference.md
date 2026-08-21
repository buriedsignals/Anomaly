# Zefix API reference

## Evidence checked

Primary official material was fetched with Firecrawl and compared with the live
released route on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Current ZefixPublicREST Swagger UI | https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html | Published API family, endpoints, and authentication |
| Current OpenAPI document, provider version 2.7.2.3 | https://www.zefix.admin.ch/ZefixPublicREST/v3/api-docs | Machine-readable paths, schemas, and Basic security scheme |
| Federal Office of Justice Zefix page | https://www.bj.admin.ch/bj/en/home/wirtschaft/handelsregister/zefix.html | Provider and official-service context |
| Swiss OGD terms | https://opendata.swiss/en/terms-of-use/ | Reuse and source-attribution conditions |
| Released legacy endpoint | https://www.zefix.ch/ZefixREST/api/v1/firm/search.json | Live observed request and response behavior only; no current official contract found |

The final row is deliberately not presented as documentation. A successful
live response establishes point-in-time behavior, not a maintained contract.

## Two API families must remain distinct

| API family | Search route | Authentication | Navigator status |
|---|---|---|---|
| Legacy ZefixREST | `POST /ZefixREST/api/v1/firm/search.json` | No key observed | Released name search |
| Current ZefixPublicREST | `POST /ZefixPublicREST/api/v1/company/search` | HTTP Basic in current OpenAPI | Not wrapped |

The current OpenAPI also documents company detail by UID, EHRA ID, and CH-ID;
SOGC publications; cantonal registry offices; legal forms; and communities.
Those endpoints use different schemas and cannot be treated as documentation
for the released legacy adapter.

## Released request

`POST https://www.zefix.ch/ZefixREST/api/v1/firm/search.json`

```json
{"name": "Nestlé", "languageKey": "fr"}
```

| Navigator field | Legacy field | Contract |
|---|---|---|
| `name` | `name` | Required non-empty string; matching algorithm is undocumented in current official material. |
| `language` | `languageKey` | One of `de`, `en`, `fr`, or `it`; defaults to `en`. |

The adapter does not expose offset, limit, status, legal form, or canton input
because no current primary documentation for those legacy request fields was
found. Do not invent them from successor documentation.

## Observed response and normalization

The live response contains `list`, `hasMoreResults`, `offset`, `maxEntries`,
and `maxOffset`. A checked Nestlé query returned `maxEntries: 50`; the adapter
therefore treats the result as a bounded first page and exposes the returned
pagination metadata without claiming that pagination is supported.

| Normalized field | Legacy field | Interpretation |
|---|---|---|
| `name` | `name` | Registered display name supplied by Zefix. |
| `uid` | `uidFormatted`, otherwise `uid` | Swiss enterprise identifier; confirm this before resolving identity. |
| `chid` | `chidFormatted`, otherwise `chid` | Commercial-register identifier. |
| `legal_seat` | `legalSeat` | Registered legal seat in the returned record. |
| `status` | `status` | Common raw codes mapped below; unknown codes preserved. |
| `shab_date` | `shabDate` | Provider date field; do not infer its event meaning without the SOGC record. |
| `registry_url` | `cantonalExcerptWeb` | Cantonal register excerpt link supplied upstream. |
| `source_url` | constructed from `ehraid` | Zefix entity-page link for candidate inspection. |

Adapter status mappings are normalization choices, not a complete provider
enumeration:

| Raw | Normalized |
|---|---|
| `EXISTIEREND` | `active` |
| `GELOESCHT` | `deleted` |
| `IN_LIQUIDATION` | `in_liquidation` |
| `IN_AUFLOESUNG` | `in_dissolution` |

## Errors and no-result behavior

- A legacy 404 with `API.ZFR.SEARCH.NORESULT` is normalized to an empty result.
- Other 4xx responses are errors, not empty searches.
- 429 and 5xx responses should be retained as upstream failures and retried
  only with bounded backoff.
- No authoritative legacy rate-limit statement was found; this is not evidence
  of unlimited use.

## Licence and attribution

The current ZefixPublicREST OpenAPI points to Swiss OGD use conditions. Reuse is
permitted subject to the terms, including source indication. Preserve Zefix and
cantonal-register attribution. Because the legacy route is not in the current
published specification, recheck terms before bulk caching or redistribution.

## Known gaps and drift risks

- The released legacy endpoint lacks a current official specification.
- The provider can retire or change it independently of ZefixPublicREST.
- Observed broad matching does not establish exact, substring, phonetic, or
  fuzzy semantics.
- A first-page result is not an exhaustive company list.
- Status vocabulary may contain values outside the adapter's mapping.
- Legal status is time-sensitive; inspect the cantonal excerpt and SOGC
  publications for consequential claims.
