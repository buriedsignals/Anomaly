---
name: data-navigator-ch-openparldata-parliamentary-data
description: |
  Query harmonized Swiss parliamentary records from OpenParlData.ch: people,
  memberships and interests; or affairs, meetings, speeches, votes and docs.
  Public CC BY 4.0 API, no key.

  Triggers on Swiss parliamentary research:
  - "find Swiss parliamentarians named X"
  - "what interests did politician X declare?"
  - "find Swiss parliamentary affairs / speeches / votes about X"
---

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current Navigator release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `ch/openparldata/parliamentary-data:search-persons` — Search Persons using the fields returned by the current OpenParlData.ch — Swiss Parliamentary Data adapter.

**Not released**

- `ch/openparldata/parliamentary-data:search-affairs` — Operation-level fixture coverage is not available; this operation is not released yet.
- `ch/openparldata/parliamentary-data:list-person-interests` — Operation-level fixture coverage is not available; this operation is not released yet.
<!-- END GENERATED OPERATION STATUS -->
# Data Navigator — OpenParlData.ch

## Purpose and routing

OpenParlData.ch harmonizes federal, cantonal, and municipal Swiss parliamentary
data. One registry-loaded skill routes two related domains inside one adapter:

| Domain | Resources | Typical query |
|---|---|---|
| People and roles | `persons`, `memberships`, `interests`, `access_badges`, `groups`, `bodies` | Find a politician, then traverse to interests, memberships, speeches, or votes. |
| Parliamentary work | `affairs`, `votings`, `votes`, `speeches`, `meetings`, `docs`, `events`, `agendas`, `texts`, `news` | Search an issue, inspect its record, then traverse to votes, documents, or speeches. |

The adapter infers `persons` from `name`/`person_id` and `affairs` from `q` or
`affair_id`. Set `resource` explicitly for every other table. This is a single
portable multi-operation skill, matching Data Navigator's OpenSanctions pattern;
there are no runtime sub-skills to fetch.

## Auth and licence

No key. Data is CC BY 4.0. Preserve the returned attribution: **Source:
OpenParlData.ch**.

## Invocation

```bash
# People
navigator query ch/openparldata/parliamentary-data --input '{"name":"Müller","filters":{"active":true},"limit":5}'

# Affairs (q defaults to the affairs resource)
navigator query ch/openparldata/parliamentary-data --input '{"q":"Klima","search_mode":"natural","language":"de","filters":{"body_key":"CHE"},"limit":5}'

# Relation traversal: declared interests for a known person
navigator query ch/openparldata/parliamentary-data --input '{"resource":"persons","id":123,"relation":"interests","limit":20}'

# Individual votes in a known voting
navigator query ch/openparldata/parliamentary-data --input '{"resource":"votings","id":105037,"relation":"votes","limit":100}'
```

Add `--out results.json` (or `.csv`) for a file plus a compact summary.

## Inputs

| Param | Notes |
|---|---|
| `resource` | Upstream table. Optional only when inference from `name`, `person_id`, `affair_id`, or `q` is unambiguous. |
| `q` / `name` | Search text. `q` defaults to affairs; `name` defaults to persons. |
| `id` | One record ID. Add `relation` to traverse a documented relation. |
| `filters` | Upstream field filters, e.g. `{"body_key":"CHE","active":true}`. |
| `search_mode` | `partial` (default), `exact`, `natural`, or `boolean`. |
| `search_scope` | Comma-separated `metadata`, `docs`, `texts`, and/or `speeches`. |
| `language` | Output language preference: `de`, `fr`, `it`, `rm`, `en`; fallback defaults to German. |
| `sort_by` | Upstream sort field; prefix with `-` for descending. |
| `expand` / `fields` | Embed relations or select fields. Both are comma-separated. |
| `limit` / `offset` | Adapter cap 100 records; upstream offset cap 100,000. |
| `include_raw` | Include the full upstream object when normalized fields are insufficient. |

## Output

Every record includes `resource`, `id`, and `source_url`, plus useful
resource-specific fields. People include party, role, district and active
status; affairs include title, type and status; roll calls include counts or
the individual member's vote. `include_raw: true` retains every upstream field.

## Gotchas

- Coverage differs sharply by parliament. A null field generally means that
  the originating body did not publish it, not that the fact does not exist.
- `partial` is substring search. Use `natural` for multi-word concepts and
  `boolean` for explicit `&`, `|`, `!`, and `<->` operators.
- Search language and output language are separate. Set `search_language` when
  precision matters; keep `language_fallback` for sparse translations.
- Deep pagination stops at offset 100,000. Full-table work belongs in the
  gzipped NDJSON exports at <https://files.openparldata.ch/exports/>.
- A vote is evidence of one recorded division. Inspect the related affair,
  voting meaning, corrections, and source link before characterizing it.

## Source-local helper

Run the maintained live probes from `data/`:

```bash
uv run python skills/ch/openparldata-parliamentary-data/scripts/smoke_queries.py
```

API documentation: <https://api.openparldata.ch/documentation>
