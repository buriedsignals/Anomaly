---
name: courtlistener-docket
description: >-
  Use this skill to search CourtListener's public RECAP federal-docket index or
  retrieve the indexed record for an exact CourtListener docket ID. Apply it to
  parties, courts, docket metadata, and up to three matching filing documents;
  never call the embedded matches a complete docket sheet or infer that an
  absent RECAP result means the case or filing does not exist.
compatibility: Requires Python 3.11+ and network access to www.courtlistener.com; a CourtListener token is optional but recommended for clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/docket
---

# Query CourtListener RECAP dockets

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/docket:search-dockets` — Search the RECAP index and return docket metadata plus no more than three matching filing-document summaries per docket.
- `us/courtlistener/docket:get-docket` — Run an exact docket_id search and return the matching indexed docket record, still subject to the three-document embedding limit.
<!-- END GENERATED OPERATION STATUS -->
## Search or retrieve

Use `search-dockets` for a party, case, filing term, or documented advanced
operator. Use `get-docket` only for a known CourtListener numeric docket ID.

```bash
catalogue query us/courtlistener/docket --operation search-dockets \
  --input '{"q":"Purdue Pharma","court":"nysb","limit":5}'
catalogue query us/courtlistener/docket --operation get-docket \
  --input '{"docket_id":16199029,"limit":1}'
```

The `documents` array contains no more than three matching RECAP filing
documents. When `more_documents` is true, additional matching filings exist.
This operation does not enumerate the docket sheet.

## Evidence discipline

- Preserve the exact query, selected court, result type, retrieval time, and ID.
- Treat counts over 2,000 as approximate; CourtListener documents about ±6%
  error for type `r` and `d` cardinality counts.
- Open `source_url` and underlying filing URLs before reporting legal claims.
- Distinguish absence from the RECAP index from absence in PACER or the court.
- Do not use the data for a prohibited FCRA purpose.

Read [the API reference](references/api-reference.md) for authentication,
limits, type `r`, result counts, and rights. Read
[the query guide](references/query-guide.md) for search and reporting practice.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved primary documentation and live contract observations.
- `references/query-guide.md` — query choice, truncated-document handling, and reporting checklist.
- `scripts/verify.py` and `assets/verification-cases.json` — live checks for both operations.
- `evals/evals.json` — behavioral cases for completeness, identifiers, and legal verification.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
