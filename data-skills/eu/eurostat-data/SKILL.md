---
name: eurostat-data
description: >-
  Use this skill to discover official Eurostat SDMX 3.0 dataflows and retrieve
  explicitly filtered observations with dimension labels and quality status.
  Apply it to reproducible European statistical queries; do not assume a local
  output limit makes an upstream cube small, ignore status flags, or treat the
  latest dissemination value as a complete revision history.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to ec.europa.eu.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: eu/eurostat/data
---

# Discover and query Eurostat data

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `eu/eurostat/data:search-datasets` — Search current Eurostat dataflow codes and multilingual names locally after one official SDMX structure request.
- `eu/eurostat/data:get-observations` — Retrieve a bounded, explicitly filtered SDMX data cube and flatten provider values, dimensions, labels, and status flags.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete question and inspect the relevant contract:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show eu/eurostat/data:search-datasets
   ```

2. Discover candidate dataflows when the exact datacode is unknown:

   ```bash
   catalogue query eu/eurostat/data --operation search-datasets \
     --input '{"q":"youth unemployment","language":"en","limit":10}'
   ```

3. Inspect the chosen dataset's dimensions, unit, population, frequency, and
   status vocabulary, then send an explicitly scoped observation query:

   ```bash
   catalogue query eu/eurostat/data --operation get-observations \
     --input '{"dataset_code":"DEMO_GIND","filters":{"FREQ":"A","INDIC_DE":"POPTRT","GEO":"FR","TIME_PERIOD":"ge:2018+le:2023"},"limit":100}'
   ```

4. Preserve datacode, dimension codes and labels, unit, time period, status and
   status label, update/retrieval dates, source URL, and any truncation warning.

## Query discipline

Component arrays are OR values. Time ranges use SDMX operators such as
`ge:2018+le:2023`. Ordered `key` components follow the dataset structure; do
not constrain the same dimension in both `key` and `filters`.

`limit` caps normalized output after the provider response. It does not reduce
the upstream cube. The adapter therefore rejects unfiltered data requests
unless the user explicitly sets `allow_full_dataset`, and Comext/Prodcom
`DS-` datasets always require filters. Read
[the API reference](references/api-reference.md) before broad extraction.

## Interpretation cautions

- `first_n_observations` and `last_n_observations` apply per series.
- Value and status-bearing positions are returned; missing cells need not be zero.
- Eurostat can move 500,000–5,000,000-cell requests to asynchronous delivery
  and reject larger ones; this adapter is synchronous.
- Reuse normally requires source acknowledgment, with material and geography-
  specific exceptions. Cite datacode or DOI and access date.

## Bundled resources

- `references/api-reference.md` — SDMX paths, filtering, limits, response model,
  reuse evidence, and drift risks.
- `references/query-guide.md` — dataset selection and statistical interpretation.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
