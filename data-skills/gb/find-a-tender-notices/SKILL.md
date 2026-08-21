---
name: find-a-tender-notices
description: >-
  Use this skill to retrieve UK Find a Tender OCDS release packages by update
  window, contracting stage, and cursor, with optional term filtering limited
  to one fetched page. Apply it to procurement-notice discovery and process
  tracking; do not call local term results exhaustive or equate tender value
  with an award, contract, or payment.
compatibility: Requires Python 3.11+ and network access to www.find-tender.service.gov.uk.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: gb/find-a-tender/notices
---

# Query Find a Tender OCDS releases

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `gb/find-a-tender/notices:search-notices` — Retrieve one bounded Find a Tender release page by update window, stage, and cursor, then optionally filter that page locally by term.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete question and inspect the operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show gb/find-a-tender/notices:search-notices
   ```

2. Prefer upstream date/stage filters. Follow only the returned cursor for the
   same scope:

   ```bash
   catalogue query gb/find-a-tender/notices --operation search-notices \
     --input '{"updatedFrom":"2026-08-01T00:00:00","updatedTo":"2026-08-12T23:59:59","stage":"tender","limit":10}'
   ```

3. Use `q` only as a transparent convenience over one fetched page:

   ```bash
   catalogue query gb/find-a-tender/notices --operation search-notices \
     --input '{"q":"software","stage":"tender","limit":20}'
   ```

4. Preserve OCID, release ID, tags, buyer, tender status/value, release date,
   exact API record, update window, cursor, and package publication date.

## Source boundary

The provider documents release packages, record packages, notice/OCID detail,
stage and date filtering, and cursor pagination. catalogue currently releases
only collection release pages. It fetches up to 100 releases when local `q`
filtering, so a miss does not establish absence outside that page.

OCDS `ocid` identifies a procurement process; release `id` identifies one
notice/release within it. A process can contain planning, tender, award, change,
and other releases. Read [the API reference](references/api-reference.md) and
[the query guide](references/query-guide.md) before making award claims.

## Failure handling

Dates must use `YYYY-MM-DDTHH:MM:SS`. Cursors are opaque and scope-bound. On
429 or 503, the provider instructs clients to wait at least the `Retry-After`
header. Do not restart cursor pagination with an invented token.

## Bundled resources

- `references/api-reference.md` — official OCDS contract, filters, cursor,
  licence, response mapping, and retry behavior.
- `references/query-guide.md` — notice-to-procurement evidence chains.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
