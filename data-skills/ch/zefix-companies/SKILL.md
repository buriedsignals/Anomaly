---
name: zefix-companies
description: >-
  Use this skill to search the live public Zefix legacy endpoint for Swiss
  commercial-register company candidates, UID and CH-ID identifiers, legal
  seats, status, and cantonal excerpt links. Apply it to Swiss company-name
  resolution; do not imply that the bounded legacy response is exhaustive or
  that it is the same API as the current authenticated ZefixPublicREST spec.
compatibility: Requires Python 3.11+ and network access to www.zefix.ch.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: ch/zefix/companies
---

# Query Zefix company candidates

Use only operations marked **Released** below. `meta.yaml` is the executable
contract; the reference explains the material documentation gap around the
legacy route.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `ch/zefix/companies:search-companies` — Search the live legacy public Zefix route by company name and return its bounded first response page.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete question:

   ```bash
   catalogue data assess "<complete question>" --json
   ```

2. Inspect the released contract and read [the API reference](references/api-reference.md):

   ```bash
   catalogue data show ch/zefix/companies:search-companies
   ```

3. Query a specific name, then use UID, legal seat, and the cantonal excerpt to
   resolve candidates:

   ```bash
   catalogue query ch/zefix/companies --operation search-companies \
     --input '{"name":"Nestlé","language":"fr"}' --out zefix.json
   ```

4. Preserve `uid`, `chid`, `registry_url`, `source_url`, query language, and
   observation date. Treat every name match as a candidate.

## Source boundary

The released adapter calls the live, unauthenticated legacy endpoint at
`www.zefix.ch/ZefixREST`. The current official Swagger specification documents
the different `www.zefix.admin.ch/ZefixPublicREST` API, which requires HTTP
Basic authentication. Do not silently switch between them.

The released operation does not expose company detail, SOGC publications,
pagination, full-register export, or the authenticated successor endpoints.
Read [the query guide](references/query-guide.md) for bounded no-result recovery.

## Interpretation cautions

- Observed matching is broad; provider documentation available today does not
  establish exact, substring, or fuzzy semantics for this legacy route.
- A first-page response does not prove completeness even when
  `has_more_results` is false.
- Common raw German statuses are normalized, but an unknown value is preserved.
- Name and legal seat are not sufficient identity evidence; verify UID and the
  cantonal register excerpt.

## Bundled resources

- [API reference](references/api-reference.md) — primary evidence, endpoint
  distinction, mapping, licensing, and drift risks.
- [Query guide](references/query-guide.md) — candidate resolution and negative-search discipline.
- `scripts/verify.py` and `assets/verification-cases.json` — bounded live checks.
- `evals/evals.json` — forward agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
