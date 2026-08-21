# CourtListener typed search API reference

## Evidence checked

Firecrawl fetched the current provider material on 2026-08-12:

| Evidence | URL | Supports |
|---|---|---|
| REST API v4.6 | https://www.courtlistener.com/help/api/rest/v4/ | auth, limits, formats, API families |
| Legal Search API | https://www.courtlistener.com/help/api/rest/v4/search/ | types, semantic/keyword modes, counts, snippets, caching |
| API root | https://www.courtlistener.com/api/rest/v4/ | current route inventory |
| Terms and policies | https://www.courtlistener.com/terms/ | use, FCRA, copyright, credentials |

Live queries verified all six documented type shapes.

## Type table

| Code | Provider meaning | Navigator entity |
|---|---|---|
| `o` | Opinion clusters with nested opinion documents | `OpinionCluster` |
| `r` | Federal dockets with up to three matching documents | `Docket` |
| `rd` | Individual federal PACER/RECAP filing documents | `RECAPDocument` |
| `d` | Federal docket metadata without filing metadata | `Docket` |
| `p` | Judicial people | `JudicialPerson` |
| `oa` | Oral-argument audio | `OralArgument` |

The adapter rejects unknown types and returns `record_type` on every row. Do
not interpret a field using another type's semantics.

## Keyword, semantic, fields, and sorting

Keyword search is default. `semantic=true` is documented only for case law
(`o`). Semantic GET sends q to CourtListener. The provider also documents a
privacy-oriented POST of a locally computed 768-dimensional embedding, but this
skill does not implement that mode.

Search fields use camelCase and can be placed in advanced `q` expressions.
`order_by` values vary by type; reproduce a reviewed front-end search URL rather
than guessing. `highlight=on` requests `<mark>`-bearing snippets.

## Result limitations

- `r` embeds at most three matching filing documents and exposes `more_docs`.
- `d` contains docket metadata but excludes filing metadata.
- `r` and `d` counts use cardinality aggregation and can be about ±6% wrong
  above 2,000 results.
- Relevance scores are search-ranking signals, not legal authority.
- Search results are cached for ten minutes. Alerts are recommended over polling.
- Long OR chains impose significant cost and are discouraged.

## Authentication, rights, and prohibited use

Optional token header: `Authorization: Token <token>`. Public experimentation
does not cancel the provider's request that deployed clients authenticate.
Current default authenticated limits are 5/minute, 50/hour, and 125/day.

Court records are often public domain, but filings can contain copyrighted
third-party works. Treat rights per record. CourtListener terms ban FCRA uses,
sharing/rotating credentials, and rate-limit evasion.
