# OCCRP Aleph entity API reference

## Evidence checked

Aleph's public user documentation does not currently provide a complete REST
reference for these routes, and the live OCCRP deployment returned 404 for
common `/openapi.json` and `/swagger.json` paths. To avoid inventing a contract,
the implementation evidence below was fetched with Firecrawl on 2026-08-12 from
the official `alephdata/aleph` repository and compared with the existing OCCRP
endpoint.

| Primary evidence | URL | Supports |
|---|---|---|
| Entity API route code | https://github.com/alephdata/aleph/blob/develop/aleph/views/entities_api.py | Search, detail, expansion routes and parameters |
| Entity route tests | https://github.com/alephdata/aleph/blob/develop/aleph/tests/test_entities_api.py | Search filters, sort, exact retrieval, and expansion response shape |
| View-context authentication tests | https://github.com/alephdata/aleph/blob/develop/aleph/tests/test_view_context.py | `ApiKey` for API keys, `Token` for session tokens, permission behavior |
| Graph expansion logic | https://github.com/alephdata/aleph/blob/develop/aleph/logic/expand.py | Property-grouped adjacency and bounded expansion behavior |
| Mixed graph developer guide | https://docs.aleph.occrp.org/developers/mixed-graphs/ | Official use of account host/API-key configuration and mixed document/entity graph model |

## Authentication

Base: `https://aleph.occrp.org/api/2`

Navigator sends:

```text
Authorization: ApiKey <user API key>
```

The official authentication tests are explicit: `Authorization: Token ...`
parses a signed session token, while user API keys use `ApiKey` (or a raw key for
legacy compatibility). The former adapter incorrectly labeled an API key as
`Token`; this migration corrects that defect.

Invalid keys can initially behave like an anonymous request for compatibility;
protected collection access then fails with a permission response. Do not treat
anonymous public results as evidence that the key was accepted.

## Search entities

`GET /entities` (also implemented as `/search` for broader search behavior)

Released parameters:

| Navigator | Provider | Meaning |
|---|---|---|
| `q` | `q` | Search string; provider supports its search syntax |
| `schema` | `filter:schemata` | FollowTheMoney schema filter |
| `collection_id` | `filter:collection_id` | One readable collection |
| `limit` | `limit` | Navigator restricts to 1–50 although upstream route docs allow a much larger maximum |
| `offset` | `offset` | Navigator bounds to 0–10,000 |

The upstream result includes total, total type, limit, offset, facets/links, and
FollowTheMoney entities. Navigator normalizes schema, ID, caption/name,
collection label/ID, countries, and the Aleph entity page URL.

The provider route requires only anonymous browsing permission at the code
level, but the actual visible set is authorization-dependent. OCCRP collections
can be public, private, or shared selectively.

## Get an entity

`GET /entities/{entity_id}`

The route returns one entity visible to the requester. The provider excludes
some large text/numeric fields from this view and adds presentation-oriented
fields. Navigator extracts a stable summary; it does not claim to reproduce
every FollowTheMoney property.

## Expand graph relations

`GET /entities/{entity_id}/expand`

Parameters:

- `limit`: number of adjacent entities returned per property; Navigator bounds
  this to 1–50.
- `filter:property`: one or more FollowTheMoney property names.

The response groups results by property. Each group has `property`, `count`,
and an `entities` list. The expansion code locates adjacent graph nodes through
entity-valued properties and edge entities. Navigator flattens the groups while
retaining `relation` and `relation_count` on every record.

This is one bounded graph hop, not a complete network traversal. A property can
represent many kinds of relationships. Interpret it with the FollowTheMoney
data dictionary and source record before using words such as owner, director,
associate, or control.

## Capability and provenance boundary

Aleph includes much more than these three routes: document search and content,
facets, collections, exports, matching, reconciliation, ingestion, statements,
bookmarks, and writes. Those operations are not released here.

Entities can be extracted from documents, loaded from structured datasets, or
entered by investigators. The collection is therefore essential provenance.
The provider does not impose one universal content licence across all
collections; inspect collection metadata and underlying documents before reuse.
