---
name: opensanctions
description: >-
  Use this skill to screen a described person, company, vessel, or other
  FollowTheMoney entity through OpenSanctions query-by-example matching, conduct
  investigative full-text discovery, or retrieve one exact entity with nested
  relationships and source-lineage identifiers. Apply it to sanctions, PEP,
  debarment, and watchlist research; do not equate search relevance or match
  scores with identity, target status, or grounds for an adverse decision.
compatibility: Requires the catalogue CLI, Python 3.11+, an OpenSanctions API key, and network access to api.opensanctions.org.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/opensanctions
---

# Query OpenSanctions

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/opensanctions:match-entity` — Rank candidates for a structured query-by-example using explicit dataset, topic, algorithm, and threshold controls.
- `global/opensanctions:search-entities` — Search the OpenSanctions sanctions, PEP, and watchlist entity index with bounded pagination, facets, filters, and explicit search syntax controls.
- `global/opensanctions:get-entity` — Retrieve one exact entity ID, optionally including nested adjacent entities and canonical referents.
<!-- END GENERATED OPERATION STATUS -->
## Choose the correct operation

- Use `match-entity` to screen a known subject with structured attributes.
- Use `search-entities` for investigator-facing discovery and facets. Its
  ranking is search relevance, not match quality.
- Use `get-entity` only after obtaining an exact provider ID.

Inspect the contract before sending identity data upstream:

```bash
catalogue data show global/opensanctions:match-entity
```

## Screening example

Use all reliable attributes, an explicit scope, and a reviewed threshold:

```bash
catalogue query global/opensanctions --operation match-entity \
  --input '{"schema":"Person","properties":{"name":["Arkadii Rotenberg"],"birthDate":["1951"],"nationality":["Russia"]},"dataset":"default","topics":["sanction"],"threshold":0.8,"algorithm":"logic-v2","limit":5}'
```

Review every candidate, score, match flag, topics, datasets, identifiers, and
source evidence. A score above threshold is not a final identity decision.

## Discovery and exact retrieval

```bash
catalogue query global/opensanctions --operation search-entities \
  --input '{"q":"\"Wagner Group\"","schema":"Organization","dataset":"default","limit":10,"offset":0,"filter_op":"AND"}'
catalogue query global/opensanctions --operation get-entity \
  --input '{"entity_id":"<exact-id>","nested":true}'
```

Read [the API reference](references/api-reference.md) for current filters,
matching algorithms, search/privacy semantics, canonical-ID redirects, and
licensing. Read [the query guide](references/query-guide.md) for screening
review, false-positive handling, and evidence reporting.

## Identity and risk discipline

- Search rankings and match scores solve different tasks; neither proves
  identity.
- Dataset membership does not necessarily mean the entity is itself targeted.
  Inspect `topics`, `target`, nested sanctions, and the original designation.
- PEP, relative/associate, debarment, and sanctions classifications have
  different meanings. Report the precise topic and source.
- A no-match result is not proof that a subject is clear. Coverage, spelling,
  scope, attributes, source freshness, and threshold all matter.
- Never automate an adverse decision from this output. Use human review and
  independent primary-source verification.

## Privacy, authentication, and reuse

Store the key with `catalogue keys set opensanctions`. Match sends structured
identity attributes in a POST body; search uses a GET query string that the
provider warns can enter access logs. Do not send confidential lead names
without considering that disclosure.

OpenSanctions documents free keys for qualifying public-interest work and a
CC BY-NC data licence for non-commercial use; commercial use requires the
applicable licence. This skill conservatively does not pre-authorize caching or
redistribution.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved official OpenAPI and
  documentation for matching, search, entities, authentication, and licence.
- `references/query-guide.md` — structured screening, discovery, candidate
  review, canonical IDs, and reporting.
- `scripts/verify.py` with `assets/verification-cases.json` — credential-aware
  match, search, and exact-entity checks.
- `evals/evals.json` — search/match, target, no-match, privacy, and human-review
  behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
