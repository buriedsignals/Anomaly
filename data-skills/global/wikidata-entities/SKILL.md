---
name: wikidata-entities
description: >-
  Use this skill to resolve labels, aliases, or entity IDs to Wikidata item,
  property, lexeme, form, sense, or entity-schema candidates with descriptions,
  match metadata, HTTPS links, and continuation offsets. Apply it to entity
  reconciliation; do not treat first-ranked candidates as confirmed identity or
  expect arbitrary statements and identifiers from search.
compatibility: Requires Python 3.11+ and network access to www.wikidata.org.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/wikidata/entities
---

# Resolve Wikidata entities

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/wikidata/entities:search-entities` — Search labels, aliases, or IDs and return disambiguation metadata plus a continuation offset.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Inspect the operation and choose the correct entity type and language:

   ```bash
   catalogue data show global/wikidata/entities:search-entities
   ```

2. Retrieve candidate entities:

   ```bash
   catalogue query global/wikidata/entities --operation search-entities \
     --input '{"q":"OpenAI","language":"en","type":"item","limit":10}'
   ```

3. Compare IDs, descriptions, `match`, `match_type`, and `match_language`.
   Follow `page.next_continue` when more candidates are relevant.

4. Inspect the selected entity's statements and references with a separately
   capable operation, then corroborate consequential claims in primary records.

## Source boundary

This skill wraps `wbsearchentities`: labels/aliases/IDs in, candidate metadata
out. It does not retrieve arbitrary statements, qualifiers, references,
ownership, or cross-database identifiers. The first result is not necessarily
the intended entity.

Read [the API reference](references/api-reference.md) for language, type, and
continuation semantics and [the query guide](references/query-guide.md) for a
reproducible disambiguation workflow.

## Failure handling

A missing candidate may reflect language, alias, type, spelling, ranking, or
pagination. Try a native-language label or justified fallback and check
`next_continue`. Do not invent offsets or claim a universal absence.

## Bundled resources

- `references/api-reference.md` — official parameter, output, continuation,
  capability, and CC0 contract.
- `references/query-guide.md` — candidate disambiguation and pagination.
- `scripts/verify.py` with `assets/verification-cases.json` — live item and
  property checks.
- `evals/evals.json` — ambiguity, type, statement, and pagination cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
