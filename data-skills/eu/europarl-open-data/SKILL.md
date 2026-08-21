---
name: europarl-open-data
description: >-
  Use this skill to query official European Parliament Open Data API v2 for
  current MEP candidates, one known MEP, plenary speech activities, and adopted
  texts. Apply it to Parliament identity and document discovery; do not use the
  source router as an unrestricted API proxy or infer legal effect, a complete
  transcript, or a person's identity from the normalized result alone.
compatibility: Requires Python 3.11+ and network access to data.europarl.europa.eu.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: eu/europarl/open-data
---

# Query European Parliament open data

`meta.yaml` is the executable contract. Use only operations marked **Released**
below even though the provider and source-level adapter cover more resources.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `eu/europarl/open-data:search-meps` — Filter the current MEP roster by documented country, group, term, and gender fields, with optional transparent local name matching.
- `eu/europarl/open-data:get-mep` — Retrieve one MEP record from the official person detail endpoint by European Parliament identifier.
- `eu/europarl/open-data:search-speeches` — Search plenary speech and speech-related activities using the provider's text and documented participant/date filters.
- `eu/europarl/open-data:search-adopted-texts` — Search adopted European Parliament texts using provider full text with optional year and procedure-type filters.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete request and inspect the exact operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show eu/europarl/open-data:search-meps
   ```

2. Run one explicit operation:

   ```bash
   catalogue query eu/europarl/open-data --operation search-meps \
     --input '{"name":"Keller","country":"FR","limit":5}'
   catalogue query eu/europarl/open-data --operation get-mep \
     --input '{"mep_id":"22858","language":"en"}'
   catalogue query eu/europarl/open-data --operation search-speeches \
     --input '{"q":"artificial intelligence","language":"en","limit":10}'
   catalogue query eu/europarl/open-data --operation search-adopted-texts \
     --input '{"q":"artificial intelligence","language":"en","limit":10}'
   ```

3. Preserve Parliament identifiers, dates, activity/document type, files,
   provider links, page scope, and `European Parliament Open Data (CC BY 4.0)`
   attribution.

## Operation boundaries

- `search-meps` calls the current-roster endpoint. Because the API has no
  MEP-name filter, `name` performs a transparent local case-insensitive
  substring match after one filtered roster request.
- `get-mep` retrieves one provider person identifier and returns current
  memberships separately from ended raw memberships.
- `search-speeches` returns speech-related activity metadata, not transcript
  text or a quotation.
- `search-adopted-texts` returns adopted Parliament documents. Adoption is not
  publication in the Official Journal or proof of current legal effect.

Read [the API reference](references/api-reference.md) for endpoint/filter
mapping and [the query guide](references/query-guide.md) for identity,
speech, and document research patterns.

## Service and error discipline

The public API permits at most 500 requests to the same endpoint in five
minutes. Use collection filters, small pages, and bounded retries. The provider
can return HTTP success with an embedded `error` and no `data`; the adapter
raises that as an upstream contract failure rather than misreporting no results.

## Bundled resources

- `references/api-reference.md` — primary evidence, provider scope, mappings,
  rate limit, response caveats, and known drift.
- `references/query-guide.md` — person resolution and evidence chains.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
