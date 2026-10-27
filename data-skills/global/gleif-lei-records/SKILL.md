---
name: gleif-lei-records
description: >-
  Use this skill to search GLEIF Legal Entity Identifier records by full text,
  legal name, or exact LEI, optionally constrained by legal jurisdiction.
  Apply it to cross-border entity resolution and LEI status checks; do not
  treat missing LEI coverage as proof that an entity does not exist or equate
  a lapsed LEI registration with dissolution.
compatibility: Requires Python 3.11+ and network access to api.gleif.org.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/gleif/lei-records
---

# Query GLEIF LEI records

Use only released operations and treat `meta.yaml` as the executable contract.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/gleif/lei-records:search-lei-records` — Search LEI records by documented full-text, legal-name, or exact-LEI filters with bounded pagination.
- `global/gleif/lei-records:companies` — LEI records as companies-contract rows.
- `global/gleif/lei-records:company-controllers` — Direct and ultimate parents (Level 2) as company_controllers rows.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete request and inspect the released operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show global/gleif/lei-records:search-lei-records
   ```

2. Use full text for discovery, legal-name filtering to narrow candidates, or
   LEI mode only for a known 20-character identifier:

   ```bash
   catalogue query global/gleif/lei-records --operation search-lei-records \
     --input '{"q":"EQUINOR ASA","search_field":"legal_name","jurisdiction":"NO","limit":5,"page":1}'
   catalogue query global/gleif/lei-records --operation search-lei-records \
     --input '{"q":"OW6OFBNCKXC4US5C7523","search_field":"lei","limit":1}'
   ```

3. Preserve LEI, national `registered_as`, entity and registration statuses,
   renewal date, provider link, page metadata, and observation date.

## Source boundary

Released scope is the LEI-record collection with three documented filters.
Level 2 direct and ultimate parents are released through
`company-controllers`. Reporting exceptions, child lists, fuzzy completions,
and identifier mappings are documented but not released here. Read
[the API reference](references/api-reference.md) before adding filters or
interpreting statuses.

## Fill the companies contract

`companies` and `company-controllers` take the search inputs (`q`,
`search_field`, `jurisdiction`, `limit` up to 50) or one `lei`, and return
rows of `domains/companies.yaml`. For each record, `company-controllers` reads
`/lei-records/{lei}/direct-parent` and `/ultimate-parent`; a 404 means the
entity reported an exception (for example `NON_CONSOLIDATING`) instead of a
parent. Routes checked live on 2026-10-27 against the record links GLEIF
returns (`relationships.direct-parent.links.lei-record`); the Level 2 model is
described at https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-2-data-who-owns-whom.

| If the source publishes | map it to column |
|---|---|
| `attributes.lei` | `company_id` = `lei:` + LEI |
| `entity.jurisdiction` (subdivision such as `US-DE` cut to `US`), else `legalAddress.country` | `jurisdiction` |
| `entity.legalName.name`, `entity.status` | `name`, `status` |
| `entity.creationDate` | `incorporation_date` |
| `entity.expiration.date` when `expiration.reason` is `DISSOLVED` | `dissolution_date` |
| `entity.legalAddress` lines, postal code, city | `registered_address` |
| (not published) | `previous_name_count` stays empty |
| parent `lei` | `controller_id` and `controller_company_id` = `lei:` + parent LEI |
| parent `legalName.name`, `jurisdiction` | `controller_name`, `controller_country` |
| route used | `control_type` = `direct-parent` or `ultimate-parent` (one row when both name the same parent); `controller_kind` = `legal_entity` |

Parents are accounting-consolidation parents, not beneficial owners, and only
entities that hold an LEI appear.

## Interpretation cautions

- GLEIF covers LEI registrants, not every company, public body, or fund.
- `entity.status` describes the entity; `registration.status` describes its LEI
  record. `LAPSED` is not synonymous with dissolved.
- Full-text and legal-name results require candidate resolution against
  jurisdiction, national identifier, address, and another primary register.
- Legal-jurisdiction and legal-address country filters have different semantics.

## Bundled resources

- [API reference](references/api-reference.md) — official search modes,
  pagination, quota, field mapping, and terms.
- [Query guide](references/query-guide.md) — LEI and name-resolution patterns.
- `scripts/verify.py` and `assets/verification-cases.json` — bounded live checks.
- `evals/evals.json` — forward agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
