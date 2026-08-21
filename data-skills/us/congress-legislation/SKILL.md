---
name: congress-legislation
description: >-
  Use this skill to list recently acted-on US federal bills and resolutions or
  retrieve congressional member records through the official Congress.gov API.
  Apply it to bounded legislative monitoring, exact Bioguide lookups, and
  Congress- or state-scoped member research; do not present its recent-title
  filter as full-text search or an update timestamp as legislative action.
compatibility: Requires the catalogue CLI, Python 3.11+, a free api.data.gov key, and network access to api.congress.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/congress/legislation
---

# Query Congress.gov bills and members

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/congress/legislation:search-bills` — List bills sorted by the provider's latest-action order, optionally scoped to a Congress and filtered client-side over at most 250 returned titles. This is not exhaustive full-text search.
- `us/congress/legislation:list-members` — Retrieve an exact member by Bioguide ID, current members by state, or a bounded member list for one Congress and optionally filter it by name or state.
<!-- END GENERATED OPERATION STATUS -->
## Keep the operation bounded

```bash
catalogue query us/congress/legislation --operation search-bills \
  --input '{"congress":119,"limit":10}'

catalogue query us/congress/legislation --operation list-members \
  --input '{"state":"VT","limit":10}'

catalogue query us/congress/legislation --operation list-members \
  --input '{"bioguide_id":"S000033"}'
```

The bill endpoint does not expose full-text search. `q` is a catalogue-owned,
case-insensitive title filter over at most 250 bills returned by the provider.
A miss therefore says nothing about older titles, summaries, actions, or text.

Member names are likewise filtered client-side over one Congress. Without an
explicit Congress the adapter derives the current Congress; use Bioguide ID for
exact historical identity. Current state lookups use the official state path.

## Interpret dates and identities

- `latest_action_date` is the date attached to the provider's latest action.
- `updated` and `updated_including_text` are data-update timestamps and can move
  without new legislative action.
- A bill list row does not include sponsors, cosponsors, subjects, summaries, or
  legislative text; open `source_url` before making those claims.
- A member can change party, chamber, district, or status. Preserve term history
  and retrieval date, and resolve people with `bioguide_id`.

Read [the API reference](references/api-reference.md) for supported endpoints
and upstream limits. Read [the query guide](references/query-guide.md) for a
reproducible reporting workflow.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved Library of Congress contracts.
- `references/query-guide.md` — bounded search, date interpretation, and identity checks.
- `scripts/verify.py` and `assets/verification-cases.json` — live bill and member checks.
- `evals/evals.json` — full-text, action-date, membership, and identity cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
