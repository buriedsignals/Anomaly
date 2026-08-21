# Bluesky AppView API reference

## Evidence checked

Primary Bluesky material was fetched with Firecrawl on 2026-08-12 and compared
with direct live probes.

| Evidence | URL | Supports |
|---|---|---|
| `app.bsky.actor.getProfile` lexicon | https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/actor/getProfile.json | Required `actor`, detailed-profile response, no-auth statement |
| `app.bsky.feed.searchPosts` lexicon | https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json | Search fields, limits, output, pagination caveats, provider-dependent auth |
| API hosts and auth | https://docs.bsky.app/docs/advanced-guides/api-directory | Public AppView routing and preferred cached hostname |
| Rate limits | https://docs.bsky.app/docs/advanced-guides/rate-limits | Direct AppView is unauthenticated, cached, and described only as generously limited |

The official material does **not** assign the PDS limit of 3,000 requests per
five minutes to the direct AppView. That older registry claim was incorrect and
has been removed.

## Released profile operation

`GET https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile`

| Navigator field | Provider parameter | Meaning |
|---|---|---|
| `actor` | `actor` | Handle or DID; required |

Navigator returns one profile with the mutable handle and stable DID kept as
separate fields. Counts and profile text are time-sensitive user-generated
state. `created_at` and `indexed_at` are different timestamps.

## Implemented but unavailable search operation

`GET https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts`

| Navigator field | Provider contract |
|---|---|
| `q` | Required string; syntax is unspecified, although Lucene is recommended |
| `sort` | Known values `top` or `latest`; default `latest` |
| `since` | Inclusive ISO date/datetime over `sortAt`, which may differ from post `createdAt` |
| `until` | Exclusive ISO date/datetime over `sortAt` |
| `mentions` | Handle/DID mentioned through a rich-text facet |
| `author` | Handle/DID of author |
| `lang` | Post language field, subject to server detection behavior |
| `domain` | Linked hostname, subject to normalization |
| `url` | Linked URL, subject to normalization/fuzzy matching |
| `tag` | One or more tags without `#`; multiple tags are ANDed |
| `limit` | 1–100 |
| `cursor` | Opaque optional cursor |

The output may include `hitsTotal`, but the lexicon says it can be rounded or
truncated and that the cursor may not traverse the entire result set.

## Current live state

- `getProfile?actor=bsky.app` returned HTTP 200 and a detailed profile on
  2026-08-12.
- `searchPosts?q=journalism&limit=1` returned a CDN-level HTTP 403 from the same
  egress on 2026-08-12.
- The lexicon explicitly says search may require authentication for some
  providers. The direct AppView documentation says direct endpoints do not
  support authentication, so Navigator cannot repair this by attaching a token
  to `public.api.bsky.app`.

The search adapter remains fixture-tested but the operation is unavailable.

## Rights and evidence limits

The API contract does not place user posts or biographies under an open-content
licence. Do not redistribute content on the strength of the API's source-code
licence. Posts can be edited, deleted, moderated, or become unreachable; archive
evidentiary material under an authorized preservation workflow.
