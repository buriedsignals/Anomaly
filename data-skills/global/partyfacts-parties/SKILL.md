---
name: partyfacts-parties
description: >-
  Use this skill to resolve political parties to Party Facts IDs and to join
  party records across political-science datasets (ParlGov, Manifesto Project,
  and other linked datasets) through the Party Facts crosswalk. It returns
  party names, countries, years, and dataset keys; it does not return funding,
  membership, or vote records.
compatibility: Requires Python 3.11+ and network access to partyfacts.herokuapp.com.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/partyfacts/parties
---

# Resolve and link political parties with Party Facts

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/partyfacts/parties:search-parties` — Filter core parties by case-insensitive name substring and/or ISO alpha-3 country.
- `global/partyfacts/parties:get-party` — Return the core-party row for one exact partyfacts_id.
- `global/partyfacts/parties:list-external-links` — Return external-party rows (dataset_key, dataset_party_id) mapped to one partyfacts_id.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Find candidate parties:

   ```bash
   catalogue query global/partyfacts/parties --operation search-parties \
     --input '{"q":"labour","country":"GBR","limit":10}'
   ```

2. Pick one `partyfacts_id` using country, years, and English name; confirm
   with `get-party` if needed.

3. List the linked dataset records and join on `dataset_key` +
   `dataset_party_id`:

   ```bash
   catalogue query global/partyfacts/parties --operation list-external-links \
     --input '{"partyfacts_id":1}'
   ```

## Source boundary

Party Facts is a crosswalk maintained by political scientists. Core parties
are Party Facts' own records; external parties are rows from linked datasets
mapped to a `partyfacts_id`. Links can be incomplete, multiple, or technical
(see the codebook). Inclusion thresholds mean small parties are often absent.
Every call downloads a full CSV table and filters locally; no query text leaves
the machine.

The adapter reads the live download tables, which change as users edit. For a
reproducible analysis, cite the run date or use a Dataverse stable version
(CC0 1.0) instead.

Read [the API reference](references/api-reference.md) for tables, columns, and
licence evidence and [the query guide](references/query-guide.md) for linking.

## Failure handling

An empty search may reflect spelling, language, or the country code (Party
Facts uses ISO alpha-3, following V-Dem units where they differ). Do not treat
absence as proof a party never existed.

## Bundled resources

- `references/api-reference.md` — tables, columns, licence evidence.
- `references/query-guide.md` — resolution and linking workflow.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — scope, disambiguation, and crosswalk cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
