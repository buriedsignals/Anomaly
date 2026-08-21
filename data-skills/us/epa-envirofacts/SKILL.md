---
name: epa-envirofacts
description: >-
  Use this skill to query EPA Envirofacts for TRI facility identities or SDWIS
  public-water-system identities by exact ID, state, city, or name. Apply it to
  resolving facilities and systems, ownership, activity, and location; do not
  infer pollutant releases, violations, compliance, or drinking-water safety
  because those facts require different tables and evidence.
compatibility: Requires the Navigator CLI, Python 3.11+, and network access to data.epa.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/epa/envirofacts
---

# Query EPA Envirofacts

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current Navigator release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/epa/envirofacts:search-tri-facilities` — Query tri.tri_facility by exact identifier/state and case-insensitive name/city containment with bounded rows.
- `us/epa/envirofacts:search-water-systems` — Query sdwis.water_system by exact PWSID/state and case-insensitive name/city containment with bounded rows.
<!-- END GENERATED OPERATION STATUS -->
## Choose the program table

- `search-tri-facilities` queries `tri.tri_facility`.
- `search-water-systems` queries `sdwis.water_system`.

```bash
navigator query us/epa/envirofacts --operation search-tri-facilities \
  --input '{"state":"RI","name":"chemical","limit":10}'
navigator query us/epa/envirofacts --operation search-water-systems \
  --input '{"state":"VT","name":"Springfield","limit":10}'
```

The adapter uses the current `/dmapservice` grammar documented by EPA. Text
comparison is case-insensitive, exact identifiers use `equals`, name/city uses
`contains`, and results are sorted and bounded.

## Interpret narrowly

A TRI facility row identifies a facility in the TRI program; it does not say
which chemicals were reported or how much was released. A water-system row
identifies the system and activity metadata; it does not answer whether the
water is safe or whether violations exist. Use the relevant release,
monitoring, violation, or ECHO evidence for those claims.

Read [the API reference](references/api-reference.md) for current grammar,
tables, operators, and limits. Read [the query guide](references/query-guide.md)
for identity resolution and follow-up evidence.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved current EPA documentation and live table checks.
- `references/query-guide.md` — filter selection and claim-boundary checklist.
- `scripts/verify.py` and `assets/verification-cases.json` — live TRI and water-system checks.
- `evals/evals.json` — pollution, compliance, identity, and no-result cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
