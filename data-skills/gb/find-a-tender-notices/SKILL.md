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

## Fill the procurement contract

`procurement-processes` and `procurement-awards` return rows of the procurement
domain contract (`domains/procurement.yaml`). Pin both calls to the same
`updatedFrom`/`updatedTo` window (and cursor) so they read the same releases,
write each to CSV, and run the procurement detectors:

```bash
catalogue query gb/find-a-tender/notices --operation procurement-processes \
  --input '{"stage":"award","limit":100,"updatedFrom":"2026-10-20T00:00:00","updatedTo":"2026-10-27T00:00:00"}'
python -m anomaly.oneshot --tables procurement_processes=processes.csv \
  --tables procurement_awards=awards.csv --request request.json --approved
```

Use `stage: tender` for `short_submission_period` (award releases carry no
submission period). Contract change notices (tag `contractAmendment`) appeared
in unfiltered pages on 2026-10-27; fetch without `stage` to include them.

| If the source publishes | map it to column |
|---|---|
| `ocid`, plus `tender/lots/id` when the tender has lots | `process_id` = `ocid/lot` (or `ocid`) |
| `buyer/id`, `buyer/name` | `buyer_id`, `buyer_name` |
| (service jurisdiction) | `country` = `GB` |
| `tender/classification/id`, else the first CPV in `tender/items` or `awards/items` | `category_code` |
| `tender/procurementMethod` (open, selective, limited, direct) | `procurement_method` |
| `tender/lots/value`, else `tender/value` (`amount`, else `amountGross`) | `tender_value`, `currency` |
| `tender/tenderPeriod/startDate`, else the release `date` of a first `tender` release | `tender_published_date` |
| `tender/tenderPeriod/endDate` | `tender_deadline` |
| `bids/statistics` with `measure` = `bids` for the lot, else `tender/numberOfTenderers` | `number_of_tenderers` |
| `ocid` + `awards/id` | `award_id` = `ocid/award id` |
| `awards/relatedLots[0]` | `process_id` |
| `awards/suppliers/id`, `awards/suppliers/name` (one row per supplier) | `supplier_id`, `supplier_name` |
| `awards/value`, else the sum of `contracts/value` with that `awardID` | `award_value`, `currency` |
| `awards/date`, else `contracts/dateSigned`, else the release `date` | `award_date` |
| `contracts/value` on a `contractAmendment` release (row with only `award_id` and `final_value`) | `final_value` |

Procurement Act 2023 notices (legal basis `2023/54`) sometimes publish only
`amountGross` and a `tenderPeriod` without `startDate`; pre-2025 notices
(Public Contracts Regulations 2015) publish net `amount`. Values from the two
regimes are not strictly comparable.

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
