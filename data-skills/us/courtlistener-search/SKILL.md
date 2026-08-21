---
name: courtlistener-search
description: >-
  Use this skill for typed CourtListener discovery across opinion clusters,
  RECAP dockets, individual federal filing documents, docket metadata, judicial
  people, and oral-argument audio. Always choose one of the documented type
  codes o, r, rd, d, p, or oa and interpret the normalized record according to
  that type; never treat relevance as authority or a search miss as proof.
compatibility: Requires the Navigator CLI, Python 3.11+, and network access to www.courtlistener.com; a CourtListener token is optional but recommended for deployed clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/search
---

# Search CourtListener by record type

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current Navigator release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/search:search-court-records` — Search exactly one documented index and normalize the result shape according to the selected type code.
<!-- END GENERATED OPERATION STATUS -->
## Choose the type before querying

| Type | Search result |
|---|---|
| `o` | Case-law opinion clusters with nested opinions |
| `r` | Federal RECAP dockets with up to three matching documents |
| `rd` | Individual federal filing documents |
| `d` | Federal docket metadata without filing documents |
| `p` | Judicial people |
| `oa` | Oral-argument audio |

```bash
navigator query us/courtlistener/search --operation search-court-records \
  --input '{"q":"Purdue Pharma","type":"rd","limit":5}'
```

Use the narrower CourtListener docket, opinion, judge, or disclosure skill when
its richer domain-specific contract matches the task.

## Interpretation

- The `entity` and available fields change with `record_type`; absent fields
  from another type are not missing provider data.
- Type `r` embeds no more than three documents. Type `d` has no documents.
- Counts for `r` and `d` above 2,000 are approximate within about ±6%.
- Semantic search is accepted only for case law (`type=o`) and GET discloses q.
- Search is cached for ten minutes; use alerts rather than polling for monitoring.
- Open the primary record before reporting a legal proposition.

Read [the API reference](references/api-reference.md) for type contracts,
privacy, counts, snippets, throttles, and rights. Read
[the query guide](references/query-guide.md) for type selection and reporting.

## Bundled resources

- `references/api-reference.md` — official v4 search and REST evidence.
- `references/query-guide.md` — type selection, interpretation, and verification.
- `scripts/verify.py` and `assets/verification-cases.json` — live checks across representative types.
- `evals/evals.json` — wrong-type, completeness, semantic, and authority cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
