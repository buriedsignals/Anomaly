# Typed CourtListener search guide

## Select the smallest correct type

- Legal-opinion research: `o`.
- One docket plus a few matching filings: `r`.
- Individual filing-document discovery: `rd`.
- Docket metadata without filing payloads: `d`.
- Judge/person discovery: `p`.
- Audio/transcript discovery: `oa`.

Use a domain-specific skill when you need its richer contract or safeguards.

## Run and interpret

```bash
catalogue query us/courtlistener/search --operation search-court-records \
  --input '{"q":"Purdue Pharma","type":"rd","limit":5}'
```

Record the exact type and query. Read only fields that belong to the returned
`entity`. Open `source_url` and any `download_url` before relying on content.
For `r`, state whether `more_documents` indicates truncation. For `r`/`d`, label
large counts approximate.

## No-result and monitoring discipline

A miss means only that the selected index, filters, and provider coverage did
not return a hit at that time. Try a justified type/operator change and state
it. Do not repeatedly poll cached search; use an authorized alert workflow.

## Reporting checklist

- Type code and entity interpretation.
- Exact query, court, order, semantic/highlight flags.
- Result identifier, URL, and retrieval time.
- Completeness/count caveats for docket types.
- Primary record read and relevant passage/file verified.
- Coverage gaps, contradictions, and alternative types checked.
