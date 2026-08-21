# GDELT DOC 2.0 ArticleList reference

## Evidence checked

Primary GDELT material was fetched with Firecrawl on 2026-08-12 and compared
with live ArticleList responses.

| Evidence | URL | Supports |
|---|---|---|
| DOC 2.0 documentation | https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ | Query grammar, modes, formats, time scopes, record cap, sorts, coverage caveats |
| GDELT Terms of Use | https://www.gdeltproject.org/about.html#termsofuse | Unrestricted dataset use/redistribution with GDELT citation |
| GDELT data portal | https://www.gdeltproject.org/data.html | Provider dataset and analysis-service scope |

The DOC documentation is an official launch/reference page rather than a
versioned OpenAPI document. Its stated API scope must therefore be checked
against live responses whenever fields are changed.

## Endpoint and fixed mode

`GET https://api.gdeltproject.org/api/v2/doc/doc`

Navigator fixes:

- `mode=artlist`
- `format=json`

It releases article discovery only. Timeline, tone, gallery, image, RSS, and
archive-feed modes remain provider scope, not Navigator capability.

## Query grammar

Operators are embedded inside `query`, separated by spaces; they are not
independent URL parameters. Documented text operators include:

- quoted exact phrases;
- uppercase `(a OR b)` blocks, without nested OR blocks;
- `-` exclusions;
- `domain:` and exact `domainis:`;
- `sourcecountry:` and `sourcelang:`;
- `nearN:`, `repeatN:`, `theme:`, `tone`, and `toneabs` forms.

GDELT's machine translation and source classification are provider-generated
signals. A query over translated coverage is not equivalent to a native-language
primary-source search.

## Time scope

| Field | Contract |
|---|---|
| `timespan` | Number plus `min`, `h`/`hours`, `d`/`days`, `w`/`weeks`, or `m`/`months`; minimum 15 minutes |
| `startdatetime` | `YYYYMMDDHHMMSS`; may be supplied without an end |
| `enddatetime` | `YYYYMMDDHHMMSS`; may be supplied without a start |

The provider documents a three-month default/window. Navigator intentionally
defaults to `1w`. A relative `timespan` cannot be combined with an exact
boundary, and start must not follow end.

## Sort and result bound

Allowed sort values:

- `DateDesc` — newest first;
- `DateAsc` — oldest first;
- `ToneDesc` — most positive first;
- `ToneAsc` — most negative first;
- `HybridRel` — provider relevance/popularity model.

ArticleList defaults to 75 provider results and accepts at most 250. Navigator
defaults to 25 and exposes the same maximum. The response has no continuation
cursor and no exhaustive hit count. A page therefore cannot prove absence or
complete enumeration.

## Normalized mapping

| Provider | Navigator | Caveat |
|---|---|---|
| `title` | `name` | Third-party article title |
| `url` | `url`, `source_url` | Publisher URL may change or disappear |
| `domain` | `domain` | Host observed by GDELT |
| `language` | `language` | Provider language assignment |
| `sourcecountry` | `source_country` | Outlet/source classification, not story location |
| `seendate` | `seen_date` | Time GDELT observed/indexed the item, not guaranteed original publication time |
| `socialimage` | `social_image` | Publisher-supplied link; may be generic, stale, or separately copyrighted |

## Errors and reuse

GDELT can return plain-text errors for malformed or overly broad queries. The
adapter surfaces a bounded excerpt rather than crashing while decoding JSON.
On 2026-08-12, a live HTTP 429 body explicitly instructed clients to limit
requests to one every five seconds. The adapter waits at least 5.5 seconds and
retries a 429 once, using a bounded `Retry-After` value when supplied. A second
429 and all 5xx responses are surfaced rather than looped.

The bundled verifier therefore enables one live query by default. Its second,
country-filtered case is retained but disabled; run it explicitly after a
cooldown with `--case country-filtered-coverage`.

GDELT permits unrestricted use and redistribution of its datasets with a
GDELT citation and link. That statement does not transfer copyright in linked
publisher articles or images.
