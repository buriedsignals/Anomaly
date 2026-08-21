# Wikidata `wbsearchentities` reference

## Evidence checked

Primary Wikimedia material was fetched with Firecrawl on 2026-08-12 and
compared with live item and property searches.

| Evidence | URL | Supports |
|---|---|---|
| Generated Action API help | https://www.wikidata.org/wiki/Special:ApiHelp/wbsearchentities | Parameters, types, defaults, continuation, returned match metadata |
| Wikibase API overview | https://www.mediawiki.org/wiki/Wikibase/API/en | Module scope and separation from entity retrieval |
| Wikidata licensing policy | https://www.wikidata.org/wiki/Wikidata:Licensing | CC0 structured-data scope and other-namespace distinction |

## Endpoint

`GET https://www.wikidata.org/w/api.php`

Fixed request parameters:

- `action=wbsearchentities`
- `format=json`
- `uselang=<language>` so returned display text follows the selection language

catalogue sends a descriptive User-Agent.

## Inputs

| catalogue | Provider | Contract |
|---|---|---|
| `q` | `search` | Required label, alias, term, or entity ID |
| `language` | `language`, `uselang` | Required by provider for search; catalogue defaults to `en` |
| `type` | `type` | `entity-schema`, `form`, `item`, `lexeme`, `property`, or `sense`; default item |
| `limit` | `limit` | 1–50; provider default 7, catalogue default 10 |
| `continue` | `continue` | Non-negative search offset |
| `strictlanguage` | `strictlanguage` | Disable language fallback when true |

The provider documents `language` as affecting selection while `uselang`
controls returned labels/descriptions. catalogue deliberately aligns them.

## Output and continuation

Each candidate can contain:

- entity ID;
- label and description;
- `match.type`, `match.language`, and `match.text`;
- concept/entity URL.

catalogue returns these as `id`, `name`, `description`, `match_type`,
`match_language`, `match`, and an HTTPS `source_url`. An upstream
`search-continue` value becomes `page.next_continue`; pass it unchanged as the
next `continue` value. Its presence means the current page is not exhaustive.

## Capability boundary

`wbsearchentities` resolves candidates using labels and aliases. It does not
return arbitrary statements, references, qualifiers, sitelinks, ownership,
corporate identifiers, or a fact-checked identity decision. Those require a
separate entity/statement operation such as `wbgetentities`, which this skill
does not release.

Search ranking can change with edits, aliases, language, and provider behavior.
For ambiguous names, compare descriptions and then inspect referenced statements
and primary sources before choosing an entity.

## Licence

Wikidata's policy places structured data in the main, property, and lexeme
namespaces under CC0. Text in other namespaces is licensed separately. This
operation returns structured entity-search data, but linked external sources
retain their own rights and must still be evaluated.
