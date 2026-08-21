---
name: gdelt-news
description: >-
  Use this skill to retrieve bounded GDELT DOC 2.0 ArticleList results for an
  explicit full-text query, time scope, sort order, and record limit. Apply it
  to worldwide news-coverage discovery and comparison. Do not call the ranked,
  capped result set exhaustive or treat the presence of an article as
  verification of its claims.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to api.gdeltproject.org.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/gdelt/news
---

# Search GDELT news coverage

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/gdelt/news:search-news` — Retrieve up to 250 ranked ArticleList records for a documented GDELT query and bounded time scope.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Inspect the operation and formulate a complete question:

   ```bash
   catalogue data show global/gdelt/news:search-news
   ```

2. Quote phrases and put documented operators inside `query`:

   ```bash
   catalogue query global/gdelt/news --operation search-news \
     --input '{"query":"\"OpenAI\" sourcecountry:unitedstates","timespan":"1d","sort":"DateDesc","maxrecords":25}'
   ```

3. Use either `timespan` or `startdatetime`/`enddatetime`. Preserve the exact
   query, time scope, sort, cap, retrieval time, and returned URLs.

4. Read each relevant article and verify its claims with primary evidence.

## Source boundary

catalogue releases JSON ArticleList search only. GDELT also documents timeline,
tone, imagery, gallery, and feed modes, but they are not exposed here.
ArticleList is ranked, capped at 250, and has no continuation cursor. It answers
"what coverage did this GDELT query return?", not "what are all the articles?"

Read [the API reference](references/api-reference.md) for query grammar and
field semantics and [the query guide](references/query-guide.md) before making
coverage-volume or absence claims.

## Failure handling

Plain-text provider errors usually indicate malformed or overly broad syntax.
Correct the query rather than repeating it. For 429, the adapter performs one
documented five-second backoff/retry; schedule a later attempt if throttling
persists. Surface 5xx failures rather than creating a retry loop.

## Bundled resources

- `references/api-reference.md` — official query, time, sort, result, licence,
  and field contract.
- `references/query-guide.md` — reproducible coverage-discovery workflow.
- `scripts/verify.py` with `assets/verification-cases.json` — one default live
  case and a second explicit case kept disabled to respect shared-egress
  throttling.
- `evals/evals.json` — completeness and truth-boundary cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
python3 scripts/verify.py --case country-filtered-coverage
```
