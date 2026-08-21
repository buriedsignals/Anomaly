# CourtListener case-law search API reference

## Evidence checked

Firecrawl fetched the provider's REST v4.6, Legal Search API, API root, and
terms pages on 2026-08-12:

- https://www.courtlistener.com/help/api/rest/v4/
- https://www.courtlistener.com/help/api/rest/v4/search/
- https://www.courtlistener.com/api/rest/v4/
- https://www.courtlistener.com/terms/

## Type `o`

`GET https://www.courtlistener.com/api/rest/v4/search/?type=o&q=...`

Type `o` returns case-law opinion clusters with nested opinion documents. The
cluster groups case metadata; nested items can represent lead, combined,
concurrence, dissent, or other opinion types. Preserve both cluster and opinion
IDs when citing evidence.

Published results are the default. The provider documents these explicit
additional status flags:

- `stat_Unpublished=on`
- `stat_Errata=on`
- `stat_Separate=on`
- `stat_In-chambers=on`
- `stat_Relating-to=on`
- `stat_Unknown=on`

catalogue maps reviewed `include_statuses` values to those flags. It does not
silently widen the status scope.

## Search behavior

Keyword search is the default. `semantic=true` invokes semantic search and is
available only for case law. With GET, the query is sent to CourtListener; the
more private documented option uses a locally generated 768-dimensional
embedding in POST, which this skill does not release.

`highlight=on` requests highlights. Snippets can contain HTML `<mark>` elements
and show indexed excerpts rather than a complete opinion. `meta.score.bm25` is a
search-ranking value, not a legal-authority score.

catalogue accepts exactly one of:

- `q` for text/operator search;
- `cluster_id`, translated to the documented advanced field expression;
- `docket_id`, likewise translated to an indexed field expression.

## Authentication and limits

Optional token header: `Authorization: Token <token>`. CourtListener asks
deployed clients to authenticate even where public experimentation works. The
documented default authenticated limits are 5/minute, 50/hour, and 125/day.
Search results are cached for ten minutes; do not poll them for monitoring.

## Rights and use

Judicial opinions are generally public domain, but provider terms warn that
some records can contain third-party copyrighted material. Inspect the linked
record before reuse. CourtListener data may not be used for a prohibited FCRA
purpose, and limits may not be evaded through multiple accounts or token rotation.
