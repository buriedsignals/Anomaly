# Find a Tender query guide

## Prefer provider filters

For reproducible research, choose an update window and stage before using local
text filtering. A typical bounded query is:

```json
{
  "updatedFrom": "2026-08-01T00:00:00",
  "updatedTo": "2026-08-12T23:59:59",
  "stage": "award",
  "limit": 100
}
```

Follow `next_cursor` until the scoped window is complete. Record each cursor or
archive the returned releases. Do not change dates/stage mid-chain.

## Term filtering limitation

`q` searches only tender JSON and buyer name in the one page fetched by the
adapter. It is useful for triage, not historical full-text search. A no-match
result means “not present in this retrieved page,” not “absent from Find a
Tender.”

## Trace a procurement

1. Preserve the OCID and release ID.
2. Group releases by OCID and order them by date.
3. Read tags and stage-specific fields.
4. Use the official notice and, when available through an authorized workflow,
   the OCDS record package to see the compiled process.
5. Check later amendments, cancellations, award and contract releases.

## Values and awards

- `tender.value`: procurement/tender-section amount.
- award value: belongs under award objects.
- contract value: belongs under contract objects.
- amount paid: generally requires implementation/transaction data or another source.

Never relabel one as another. Currency and lot scope must travel with any amount.

## No-result recovery

1. Check date format/order, stage, and cursor continuity.
2. Continue all pages in the intended window.
3. Widen the update window explicitly and record the changed scope.
4. For full process history, use OCID and a record-package workflow.
5. Report whether q was local and how many releases it inspected.

## Reporting checklist

- Cite OCID, release ID, official API/notice link, and retrieval date.
- State date window, stage, page limit, cursor completion, and local-q use.
- Distinguish tender, award, contract, and payment evidence.
- Check later releases before claiming final status.
- Preserve OGL and TED-derived attribution where applicable.
