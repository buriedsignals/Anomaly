# OpenSanctions API reference

## Evidence checked

Official material was fetched with Firecrawl on 2026-08-12. The generated API
schema identified itself as OpenSanctions API / yente 5.5.0 at retrieval time.

| Primary evidence | URL | Supports |
|---|---|---|
| Generated OpenAPI | https://api.opensanctions.org/openapi.json | Current paths, parameters, maxima, request/response schemas, security |
| API authentication | https://www.opensanctions.org/docs/api/authentication/ | `Authorization: ApiKey`, secret handling, public-interest keys |
| Matching request guide | https://www.opensanctions.org/docs/api/request/ | Query-by-example, dataset/topic filters, algorithms, threshold |
| Matching overview | https://www.opensanctions.org/docs/api/matching/ | Screening workflow and human interpretation |
| Search API | https://www.opensanctions.org/docs/api/search/ | Discovery syntax, facets, and warning against screening use |
| Entities API | https://www.opensanctions.org/docs/api/entities/ | Nested records, canonical redirects, referent lifetime, adjacent pagination |
| Commercial exemption/licensing | https://www.opensanctions.org/docs/commercial/exemption/ | Public-interest and commercial-use boundary |

## Authentication

- Base: `https://api.opensanctions.org`
- Header: `Authorization: ApiKey <key>` on every local API request
- Provide through the execution context.

The provider says it issues free API keys for qualifying journalism,
civil-society advocacy, and academic research. That does not waive the need to
follow the applicable data licence and API terms.

## Match for screening

`POST /match/{dataset}`

Body:

```json
{
  "queries": {
    "query": {
      "schema": "Person",
      "properties": {
        "name": ["Example Name"],
        "birthDate": ["1951"]
      }
    }
  }
}
```

Released query parameters:

| Parameter | Current provider contract |
|---|---|
| `limit` | Upstream max 500; catalogue deliberately caps at 50, default 5 |
| `threshold` | Match threshold, provider default 0.7; catalogue validates 0–1 |
| `algorithm` | `best`, `logic-v2`, `ofac`, `name-based`, `name-qualified`, `logic-v1`, or `regression-v1` |
| `topics` | Candidate must have at least one selected risk topic |
| `include_dataset` / `exclude_dataset` | Source-lineage filters within the selected scope |
| `exclude_schema` | Exclude entity types |
| `changed_since` | Match entities updated since the documented date/timestamp form |
| `exclude_entity_ids` | Up to 50 prior false-positive IDs/referents to exclude |

Filters are OR within one repeated parameter and AND across different
parameters. The provider recommends `default` to retain enriched/deduplicated
records, then topic filters to narrow risk meaning. A sanctions source can
include linked but non-target entities, so dataset membership alone is not a
sanctions determination.

catalogue returns candidate entity summaries plus provider `score` and `match`.
Scores depend on supplied attributes, algorithm, and scope. They require human
review and corroboration.

## Search for discovery

`GET /search/{dataset}`

The provider explicitly says search is not suitable for a screening process.
Search ranking measures text relevance rather than match quality. It supports:

- `q`, `schema`, `limit` (upstream max 500, catalogue max 50), and `offset`
  (upstream max 9499);
- include/exclude dataset and schema filters;
- `countries`, `topics`, `datasets`, and `field:value` property filters;
- `sort`, `fuzzy`, `simple`, `changed_since`, and `filter_op`;
- facets returned for countries, topics, and datasets by default.

OpenSanctions warns that the search query appears in the GET URL and can be
captured in server access logs. Treat lead names as an external disclosure.

## Retrieve an entity

`GET /entities/{entity_id}?nested=true|false`

The full response can include:

- schema, ID, properties, datasets, referents, and target flag;
- first/last-seen and last-change timestamps;
- nested sanctions, ownership, family, address, and other adjacent entities.

An adjacent entity or source dataset is not necessarily a targeted entity.
Interpret its schema, topic, and relationship.

Deduplication can merge IDs. The route returns 308 to the current canonical ID
while an old ID remains a referent. The provider says old referents are retained
for six months and recommends checking stored IDs roughly every three months,
not weekly. After cleanup, a stale ID can return 404.

## Licence and retention

OpenSanctions identifies its data as CC BY-NC 4.0 for non-commercial use and
requires a commercial licence for commercial use. Source-lineage datasets and
linked originals may have additional attribution/context requirements.

Because API-plan, privacy, and redistribution conditions can vary, catalogue
does not pre-authorize caching or redistribution. Determine whether the work is
non-commercial/public-interest, preserve attribution and lineage, minimize
stored personal data, and obtain the appropriate commercial licence when needed.
