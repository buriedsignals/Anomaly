# ThinkPol API reference

## Contents

- [Evidence](#evidence)
- [Coverage matrix](#coverage-matrix)
- [Authentication, access, and quota](#authentication-access-and-quota)
- [`search-content`](#search-content)
- [`list-user-history`](#list-user-history)
- [`list-subreddit-users`](#list-subreddit-users)
- [`get-quota`](#get-quota)
- [`analyze-profile`](#analyze-profile)
- [Documentation drift and disconfirming evidence](#documentation-drift-and-disconfirming-evidence)
- [Errors, rights, and known limits](#errors-rights-and-known-limits)

## Evidence

Firecrawl retrieved the following official ThinkPol sources on 2026-08-12.
Provider claims are recorded as claims; they are not independently verified by
the existence of a provider page.

| Evidence | URL | Supports |
|---|---|---|
| Swagger UI | https://api.think-pol.com/swagger | Published operation list and production server |
| OpenAPI 3.0.3 | https://api.think-pol.com/static/swagger.yaml | Paths, parameters, authentication, response schemas, model enums |
| Product page | https://think-pol.com/ | Provider scope claims, v3 feature claims, access and request-retention statements |
| Terms of Service | https://think-pol.com/legal/terms | Eligibility, acceptable use, redistribution, IP, third-party rights |
| Privacy Policy | https://think-pol.com/legal/privacy | Processed data, purposes, restrictions, retention, objections and removal |
| Access page | https://think-pol.com/contact | Vetted, contractual access process |

The Swagger UI labels the API version `1.0.0`, the OpenAPI format `3.0.3`, and
two servers: `https://api.think-pol.com` and `https://api.r00m101.com`. Data
Navigator uses only the named ThinkPol production server.

## Coverage matrix

| Provider capability | Documented endpoint | Navigator operation | Release status | Verification |
|---|---|---|---|---|
| Hydrated submission/comment search | `GET /v2/search` | `search-content` | Released | Authenticated zero-result and 50-record searches passed through the adapter |
| User history CSV | `GET /user/{username}` | `list-user-history` | Unavailable | An authenticated unknown-user probe returned HTTP 500; parser fixture-tested, but no record-bearing CSV was verified |
| Users associated with subreddit | `GET /subreddit/{subreddit_name}` | `list-subreddit-users` | Unavailable | Authenticated probes returned JSON null for unknown names and an unpaginated 4,215-name array for `osinttools`; adapter and fixture tested |
| Remaining quota | `GET /quota` | `get-quota` | Unavailable | Authenticated integer response passed through the adapter; value withheld because it is shared-account metadata |
| AI-generated user profile | `GET /analyze/{username}` | `analyze-profile` | Unavailable | Not called live because it can trigger analysis; JSON parser fixture-tested |

The public OpenAPI does **not** document the older `/v2/user/{username}`,
`/v2/user/{username}/comments`, `/v2/posts/{id}/comments`, or
`/v3/search/popularity` paths that appeared in the previous adapter. They were
removed rather than preserved as implied API capabilities.

## Authentication, access, and quota

The OpenAPI defines HTTP bearer authentication with bearer format `JWT` for
`/quota`, `/user/{username}`, `/subreddit/{subreddit_name}`, and `/v2/search`.
The profile endpoint's optional `model`, `latest`, `refresh`, `sources`, and
`use_case` parameters each say they require a valid bearer token, although the
operation itself has no OpenAPI `security` declaration.

ThinkPol says access is vetted and contractual rather than self-service. The
public documentation does not define an exact request limit, quota unit,
renewal interval, price per request, or `429` recovery rule. The `/quota`
response is documented only as one integer representing remaining quota. An
authenticated probe on 2026-08-12 confirmed the integer shape; the account's
value was neither printed nor retained as verification evidence.

Navigator operators store the hosted credential server-side under key name
`thinkpol`. Members neither configure nor receive it. Do not preserve the value
in skill files, fixtures, commands, or logs.

## `search-content`

### Request

`GET https://api.think-pol.com/v2/search`

| Navigator field | Upstream parameter | Type | Documented semantics |
|---|---|---|---|
| `q` | one `terms` value | string | Data Navigator convenience for a single case-insensitive term |
| `terms` | repeated `terms` | array of strings | Required; multiple values are ANDed |
| `from` | `from` | integer | Optional Unix start timestamp; defaults to `0` |
| `to` | `to` | integer | Optional Unix end timestamp; defaults to current time |
| `content_type` | `type` | `comment` or `submission` | Optional collection filter; the provider calls submissions “posts” in prose |

The OpenAPI exposes no limit, offset, cursor, sort order, exact-phrase mode, or
popularity aggregation for `/v2/search`. The adapter does not invent them.

### Response

The response is one JSON object with required `submissions` and `comments`
arrays. No pagination or total-count field is specified.

| Normalized field | Upstream field | Interpretation |
|---|---|---|
| `entity` | response collection | `RedditSubmission` or `RedditComment` |
| `id` | `id` | Provider-returned Reddit content identifier |
| `title` | `title` | Submission title; required for submissions |
| `text` | `text` | Submission body or required comment text |
| `author` | `author` | Provider-returned username label, not verified identity |
| `subreddit` | `subreddit` | Provider-returned community name |
| `created_at` | `created_utc` | Integer creation timestamp |
| `score` | `score` | Provider-returned score at an unspecified collection time |
| `num_comments` | `num_comments` | Submission comment count at an unspecified collection time |
| `submission_id` | `submission_id` | Parent submission identifier for a comment |
| `parent_id` | `parent_id` | Immediate parent identifier for a comment |
| `source_url` | `submission_url`, `url`, or `comment_url` | Provider-returned Reddit link when present |

The OpenAPI requires `id`, `author`, `created_utc`, and `title` for a submission;
it requires `id`, `text`, and `author` for a comment. Other fields are optional
and may be absent or null.

Authenticated adapter probes on 2026-08-12 returned zero records for a
synthetic nonce query and 50 normalized comments for `disinformation`, bounded
from Unix timestamp `1751328000` through `1751414400`. The public contract has
no result limit or total-count field, so 50 must not be interpreted as either a
complete match count or a documented cap. Record contents were not retained in
the verification output.

## `list-user-history`

`GET /user/{username}` accepts a case-insensitive username and optional boolean
`latest`. The documented response is semicolon-separated CSV with four columns:

1. content text, optionally prefixed with `[title]` for posts;
2. content ID in brackets;
3. creation time formatted like `15:04 January 2006`;
4. subreddit name.

The OpenAPI provides no pagination, maximum history size, completeness claim,
stable CSV header rule, timezone, or direct Reddit URL. The adapter uses CSV
quoting rules, rejects rows that do not have four columns, strips brackets from
the ID, and preserves the provider endpoint as `source_url`.

An authenticated probe with a deliberately unknown username returned HTTP 500
with a plain-text body. Because that probe did not establish a record-bearing
CSV response, this operation remains unavailable.

## `list-subreddit-users`

`GET /subreddit/{subreddit_name}` returns a JSON array of strings. The provider
describes them only as users “associated with” the subreddit. The documentation
does not define whether association means posting, commenting, subscribing,
moderating, a time window, minimum activity, or current membership. Do not
upgrade this ambiguous relation into any stronger claim.

Live probes returned HTTP 200 with JSON `null` for unknown subreddit names and
an unpaginated array of 4,215 strings for `osinttools`. The adapter normalizes
the observed `null` no-result shape to an empty record set. No usernames were
printed or retained during verification. Because the provider publishes no
pagination, result bound, or association definition, the operation remains
unavailable even though its response shapes were verified.

## `get-quota`

`GET /quota` returns a JSON integer. No unit or reset timestamp is documented.
Data Navigator maps it to one `ApiQuota` record with `remaining` and the
provider endpoint URL. The live integer shape is verified, but Navigator does
not release shared provider-account quota as a public-record query operation.

## `analyze-profile`

`GET /analyze/{username}` documents these optional query parameters:

| Parameter | Contract |
|---|---|
| `model` | One of the five model identifiers enumerated in `meta.yaml` |
| `latest` | Fetch messages missing from the archive |
| `refresh` | Force profile re-processing |
| `sources` | Verify sources for the analysis |
| `use_case` | Only `law_enforcement` is enumerated |

The profile schema can return inferred age, sex, location, country, occupation,
relationship, income level, interests, brand mentions, life stage, and
personality. A `sources` map can associate an attribute value with comment IDs.
These are model-generated inferences, not verified facts. `refresh` can trigger
new processing, and the public documentation does not state cost per model or
analysis. The operation remains unreleased.

No live profile request was made: it could consume quota, initiate new
processing, and create sensitive personal inferences. Fixture coverage is not
evidence that the live response or safeguards are adequate.

## Documentation drift and disconfirming evidence

The product page shows a `GET /v3/search` example and advertises phrase mode,
cursor pagination, and popularity histograms. The current OpenAPI exposes only
`GET /v2/search` and none of those parameters. The machine-readable operation
contract controls the adapter until ThinkPol publishes a v3 schema or an
authorized live response establishes a different contract.

The product FAQ says ThinkPol does not collect or store inbound or outbound
customer data and counts only API request volume and type for billing. The
general privacy policy also says usage and analytics data may be collected.
These statements do not establish a technical or contractual guarantee that a
sensitive term is never observable in transit or logs. Treat every query as an
external disclosure.

## Errors, rights, and known limits

- The OpenAPI documents only `200` responses. On 2026-08-12, unauthenticated
  probes to the four bearer-secured paths returned `401`; an authenticated
  unknown-user request returned `500`, and unknown subreddit names returned
  `200` with JSON `null`. No authoritative `400`, `403`, `404`, `422`, `429`,
  or `5xx` response schema was published.
- ThinkPol's terms prohibit unauthorized surveillance or harassment,
  re-identification beyond the stated lawful use, discrimination, and
  redistribution or resale without authorization.
- The terms characterize ThinkPol data and materials as proprietary and say
  customers remain responsible for third-party content rights and applicable
  privacy law. Cache and redistribution are disabled in Data Navigator.
- The privacy policy says the archive processes public posts, comments,
  usernames, timestamps, community identifiers, engagement signals, and
  derived analytics. It provides objection, restriction, and removal paths.
- ThinkPol's 30B+ records, deleted-content coverage, latency, freshness, and
  uptime figures are provider claims. The bounded authenticated probes above
  do not constitute an independent coverage, freshness, or completeness audit.
