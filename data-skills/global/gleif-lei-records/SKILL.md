---
name: gleif-lei-records
description: >-
  Use this skill to search GLEIF Legal Entity Identifier records by full text,
  legal name, or exact LEI, optionally constrained by legal jurisdiction.
  Apply it to cross-border entity resolution and LEI status checks; do not
  treat missing LEI coverage as proof that an entity does not exist or equate
  a lapsed LEI registration with dissolution.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to api.gleif.org.
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
GLEIF also documents Level 2 ownership relationships, fuzzy completions, and
identifier mappings; those are not released here. Read
[the API reference](references/api-reference.md) before adding filters or
interpreting statuses.

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
