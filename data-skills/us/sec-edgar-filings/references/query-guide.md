# EDGAR full-text query guide

## Define and preserve the search

1. Record the exact query string and whether it uses phrase, implied-AND,
   Boolean, proximity, or wildcard semantics.
2. Choose root forms deliberately; amendments and attachments can have a
   different `form` or `file_type` while sharing a root form.
3. Use both start and end dates for reproducible time-bounded work.
4. Record limit, offset, total relation, retrieval date, and the backend's
   undocumented status.

## Verify document hits

1. Deduplicate or group by accession when counting filings.
2. Resolve filer identity with CIK, not display name alone; preserve all CIKs
   and filer names when a hit contains more than one.
3. Open `source_url`, locate the terms, read surrounding sections, and identify
   whether the hit is the primary filing or an attachment/exhibit.
4. Check amendments and later filings before reporting a current claim.

## Handle negative results

A no-result query is bounded by post-2001 electronic coverage, exact syntax,
forms, dates, attachment/index behavior, corrections/removals, and an
undocumented backend. Try documented synonyms and query forms, inspect company
submissions/indexes, and state the search method rather than asserting absence.

## Reporting checklist

- Query syntax, forms, paired dates, limit/offset, and retrieval time.
- CIK, accession, root form, document type/filename, and direct URL.
- Document context read and amendments checked.
- Document versus filing/filer counts distinguished.
- SEC User-Agent and fair-access guidance followed.
