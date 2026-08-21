---
name: sec-edgar-filings
description: >-
  Use this skill for bounded full-text discovery across electronically filed SEC
  EDGAR documents and attachments since 2001. Apply exact/Boolean query, form,
  and date semantics carefully, open the filing for context, and disclose that
  the JSON route is a live but undocumented Full-Text Search UI backend.
compatibility: Requires the catalogue CLI, Python 3.11+, a descriptive requester User-Agent, and network access to efts.sec.gov and sec.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/sec-edgar/filings
---

# Search SEC EDGAR filing documents

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/sec-edgar/filings:search-filings` — Search the full text of EDGAR filing documents and attachments since 2001 with optional root-form and paired date filters, returning a bounded local slice of the live Full-Text Search backend response.
<!-- END GENERATED OPERATION STATUS -->
## Run a bounded search

```bash
catalogue query us/sec-edgar/filings --operation search-filings \
  --input '{"q":"\"material weakness\"","forms":"10-K","limit":10}'

catalogue query us/sec-edgar/filings --operation search-filings \
  --input '{"q":"cryptocurrency","forms":"8-K","startdt":"2025-01-01","enddt":"2025-12-31","limit":10}'
```

Supply both dates or neither. `forms` is a comma-separated root-form filter.
`limit` slices the response locally because the observed backend ignores its
apparent size control; `offset` maps to an empirically working but undocumented
`from` parameter. Preserve both in reported methods.

## Treat results as document hits

- Full-Text Search covers electronic filings and their attachments since 2001.
- Ordinary separated terms use implied AND. Quotation marks request an exact
  phrase; the official FAQ also documents OR, NOT, NEAR(), and suffix wildcard.
- A hit represents a filing document or attachment. Multiple hits can share an
  accession, and an attachment's `file_type` can differ from its `root_forms`.
- Open `source_url` and read the document before describing the disclosure.
- Filing metadata and documents can be amended, corrected, or removed.

The SEC documents the search interface, but its official public JSON API page
lists company submissions and XBRL APIs—not this `efts.sec.gov` route. Treat
backend shape and pagination as unstable and keep fixture/live checks current.

## Respect fair access

The adapter sends a requester-and-contact User-Agent. Override it with
`catalogue_SEC_UA="Organization contact@example.org"`. SEC guidance caps
automated access at 10 requests per second across machines and asks users to
download only what they need.

Read [the API reference](references/api-reference.md) for the evidence boundary
and query semantics. Read [the query guide](references/query-guide.md) for
document-level verification and negative-result handling.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved SEC search/API/access documentation.
- `references/query-guide.md` — reproducible search and filing verification.
- `scripts/verify.py` and `assets/verification-cases.json` — live phrase/date checks.
- `evals/evals.json` — endpoint, attachment, absence, and fair-access cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
