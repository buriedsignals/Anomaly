---
name: datahub-core-datasets
description: >-
  Use this skill to read DataHub Core reference datasets (for example GDP or
  other curated tables) as data packages: inspect a dataset's licence,
  resources, and fields, then fetch bounded pages of CSV rows with the
  dataset's licence attached. It needs a known dataset name; it does not
  search DataHub.
compatibility: Requires Python 3.11+ and network access to datahub.io.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/datahub/core-datasets
---

# Read DataHub Core datasets

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/datahub/core-datasets:get-package` — Return the package title, description, per-dataset licences, last_updated, and each resource's path, format, URL, and field names.
- `global/datahub/core-datasets:fetch-resource` — Stream one CSV resource listed in datapackage.json and return at most 1000 rows from an offset, each carrying the dataset licence.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Read the package and note its licence and resource names:

   ```bash
   catalogue query global/datahub/core-datasets --operation get-package \
     --input '{"dataset":"gdp"}'
   ```

2. Fetch rows from one CSV resource, following `next_offset`:

   ```bash
   catalogue query global/datahub/core-datasets --operation fetch-resource \
     --input '{"dataset":"gdp","resource":"gdp","limit":100}'
   ```

3. Trace consequential figures to the upstream publisher named in the
   package description before reporting them.

## Source boundary

DataHub Core repackages data from other publishers into a standard format.
Licences differ per dataset (e.g. `gdp` is CC-BY-4.0, `country-list` is
ODC-PDDL-1.0); each record carries its own. Some packages publish only
`datapackage.yml` and are not supported. Only relative resource paths under
the dataset are fetched. Rows are returned as raw CSV strings in `values`;
types are in the package's field schema.

Read [the API reference](references/api-reference.md) for URLs and evidence
and [the query guide](references/query-guide.md) for paging.

## Failure handling

An `invalid-source-request` usually means an unknown dataset, a
YAML-only package, or a missing `resource` name when several CSVs exist.

## Bundled resources

- `references/api-reference.md` — URL layout, package fields, evidence.
- `references/query-guide.md` — package-first workflow and paging.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — licence, scope, and provenance cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
