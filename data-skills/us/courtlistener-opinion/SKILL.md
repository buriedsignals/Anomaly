---
name: courtlistener-opinion
description: >-
  Use this skill to search CourtListener case-law opinion clusters by text,
  cluster ID, or docket ID and inspect citations, status, snippets, and nested
  lead, concurrence, or dissent records. Apply it to legal-source discovery;
  do not treat relevance ranking or an indexed snippet as legal authority, and
  explicitly opt into unpublished or other non-default statuses.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to www.courtlistener.com; a CourtListener token is optional but recommended for deployed clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/opinion
---

# Query CourtListener opinions

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/opinion:search-opinions` — Search type=o by text or one exact indexed identifier and optionally include explicitly selected non-published statuses.
<!-- END GENERATED OPERATION STATUS -->
## Search case law

Provide exactly one of `q`, `cluster_id`, or `docket_id`:

```bash
catalogue query us/courtlistener/opinion --operation search-opinions \
  --input '{"q":"\"qualified immunity\"","court":"ca9","limit":5}'
```

Published opinions are the provider default. To broaden status scope, name it:

```bash
catalogue query us/courtlistener/opinion --operation search-opinions \
  --input '{"q":"qualified immunity","include_statuses":["Unpublished"],"limit":5}'
```

Semantic GET search is available only with `q` and sends that query to
CourtListener. It does not conceal a sensitive research term.

## Evidence discipline

- Use relevance to find candidates, never to decide controlling authority.
- Open the linked opinion, identify the court and status, and verify the cited
  passage in context before quoting or relying on it.
- Preserve cluster, docket, and nested opinion IDs; a cluster can contain
  multiple opinion documents with different roles.
- State whether non-published statuses were included.
- A no-result query is a coverage statement, not a conclusion about the law.

Read [the API reference](references/api-reference.md) for current type `o`
semantics, status flags, snippets, semantic search, and limits. Read
[the query guide](references/query-guide.md) for a defensible research loop.

## Bundled resources

- `references/api-reference.md` — primary API evidence and contract details.
- `references/query-guide.md` — search, status, source-reading, and reporting practice.
- `scripts/verify.py` and `assets/verification-cases.json` — live keyword and ID checks.
- `evals/evals.json` — authority, status, snippet, and no-result cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
