# European Parliament Open Data API reference

## Evidence checked

Primary Parliament material was fetched with Firecrawl and checked against API
v2 on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Open Data API v2 developer page and embedded OAS3 documentation | https://data.europarl.europa.eu/en/developer-corner/opendata-api | Paths, parameters, resource descriptions, 500-per-five-minute limit, CC BY 4.0 |
| Developer corner | https://data.europarl.europa.eu/en/developer-corner | Portal and API provenance |
| Release notes | https://data.europarl.europa.eu/release-notes | API v2 release and upstream-change context |

## Provider scope

The checked specification documents collections and detail routes for MEPs,
MEP declarations, corporate bodies, meetings, events, speeches, procedures,
documents, plenary and committee material, parliamentary questions, adopted
texts, and related feeds. Vote results are exposed under meeting relations.

Navigator releases four operations only:

| Endpoint | Operation | Verification |
|---|---|---|
| `GET /api/v2/meps/show-current` | `search-meps` | Live country plus local-name case and fixture |
| `GET /api/v2/meps/{mep-id}` | `get-mep` | Live ID 22858 and fixture |
| `GET /api/v2/speeches` | `search-speeches` | Live English text search and fixture |
| `GET /api/v2/adopted-texts` | `search-adopted-texts` | Live English text search and fixture |

All other resource paths in the source-level router are unwrapped. Agents must
not use the router's `resource` or raw `filters` fields to bypass operation
contracts.

## Common request behavior

- `format=application/ld+json` selects the normalized source format.
- `limit` and `offset` are provider collection controls. Navigator caps limit
  at 50; local MEP name matching fetches one current roster page of up to 1,000.
- `language` controls preferred normalization language.
- Provider text search uses `text` plus `search-language`.
- Collection totals appear under `meta.total` when returned.

The provider publishes a maximum of 500 requests to the same endpoint in five
minutes. No authentication is required for released endpoints. Data is CC BY
4.0; preserve attribution and exact record links.

## `search-meps`

| Navigator field | Behavior |
|---|---|
| `country` | `country-of-representation` provider filter. |
| `political_group` | `political-group` provider filter. |
| `parliamentary_term` | `parliamentary-term` provider filter. |
| `gender` | Provider `gender` filter. |
| `name` | Local case-insensitive substring over returned `label`; the API documents no MEP-name filter. |
| `limit`, `offset` | Applied to local name matches when `name` is present; otherwise sent upstream. |

Name matching can be incomplete if a future current roster exceeds the one
1,000-record fetch. The page object marks `local_name_filter: true`.

## `get-mep`

`mep_id` becomes `/meps/{mep-id}`. Current memberships are those whose
`memberDuring` has no `endDate`; historical memberships remain available only
with `include_raw`. Country comes from a current `represents` value and is
mapped from Parliament's alpha-3 authority code. Political group comes from a
current membership classified as `EU_POLITICAL_GROUP`.

Current membership is a provider time-model observation, not independent proof
that the role remains current at reporting time.

## `search-speeches`

| Navigator field | Provider parameter |
|---|---|
| `q` | `text` and default `search-language=<language>` |
| `person_id` | `person-id` |
| `sitting_date_start` | `sitting-date` |
| `sitting_date_end` | `sitting-date-end` |

Normalized records represent `Activity` objects and expose activity title,
date/time, activity type, participant-person IDs, and semantic record URL. They
do not include the speech transcript. The `person_ids` relation must be
resolved separately before attributing words to a named person.

## `search-adopted-texts`

| Navigator field | Provider parameter |
|---|---|
| `q` | `text` and default `search-language=<language>` |
| `year` | `year` |
| `process_type` | `process-type` |

The adapter selects the preferred-language expression, flattens its title, and
returns up to eight manifestation links. An adopted text is Parliament output;
it does not itself prove final EU legislation, Official Journal publication,
entry into force, implementation, or current consolidated effect.

## Response and error behavior

The usual body contains `data` and optional `meta`. Detail responses can still
return `data` as an array. HTTP 204 is normalized to an empty collection.

Disconfirming live behavior: on 2026-08-12, one broad adopted-text query for
`climate` returned HTTP success with `meta`, `searchResults`, and an embedded
`error` caused by an internal detail lookup, but no `data`. The adapter now
raises an upstream error in this shape instead of returning a false no-result.
Narrower `climate change` and `artificial intelligence` searches returned data.

## Known gaps and drift risks

- JSON-LD field shapes differ substantially across resources.
- Provider vocabularies are URI codes, not always human labels.
- Name matching is local and bounded; MEP identity remains ambiguous without ID.
- Current membership, group, country, contact, and document metadata can change.
- Some text-search hits can fail during the provider's internal hydration step.
- Search totals do not establish complete transcripts, legal effect, or current law.
