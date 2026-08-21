# FederalRegister.gov API reference

## Evidence checked

Primary provider material was fetched with Firecrawl and checked against the
live API on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| FederalRegister.gov API documentation | https://www.federalregister.gov/developers/documentation/api/v1 | No-key access, document coverage, routes, and unofficial-prototype warning |
| NARA Federal Register API OpenAPI source | https://raw.githubusercontent.com/usnationalarchives/federalregister-api-core/main/data/open_api_v3.yml | Search parameters, enums, paging, response fields, and endpoint inventory |
| GovInfo Federal Register collection | https://www.govinfo.gov/app/collection/FR | Official PDF collection used for legal-text verification |

## Authority boundary

FederalRegister.gov states that its XML is not the official legal edition and
describes the site as a prototype. Use the JSON API for discovery. Verify
material text and legal effect against `official_pdf_url`, which points to the
govinfo PDF, and inspect any incorporated authority.

## Provider scope and released coverage

The provider documents document search, one/multiple document retrieval,
facets, agencies, issues, public-inspection documents, images, and suggested
searches. Search covers Federal Register documents since 1994.

catalogue releases only `GET /api/v1/documents.json` search. Date ranges, CFR
parts, RINs, dockets, topics, sections, presidents, facets, and the other route
families remain unwrapped.

## `search-documents`

| catalogue field | Provider parameter | Semantics |
|---|---|---|
| `q` | `conditions[term]` | Required full-text term. |
| `type` | `conditions[type][]` | `RULE`, `PRORULE`, `NOTICE`, or `PRESDOCU`. |
| `agency` | `conditions[agencies][]` | Provider agency slug, not display name. |
| `order` | `order` | `relevance`, `newest`, `oldest`, or `executive_order_number`. |
| `per_page` | `per_page` | Provider documents up to 1,000; catalogue deliberately caps at 100. |
| `page` | `page` | One-based page number. |

The response provides `count`, `description`, `total_pages`, `next_page_url`,
and `results`. catalogue exposes the count, current page, returned count, total
pages, and next-page URL. Treat these as provider search metadata, not a legal
count independent of search semantics.

## Response mapping

| Normalized field | Provider field | Interpretation |
|---|---|---|
| `name` | `title` | Provider document title. |
| `document_number` | `document_number` | Federal Register document number. |
| `type` | `type` | Human-readable returned document type. |
| `agencies` | `agencies[].name` | Provider agency names. |
| `publication_date` | `publication_date` | Publication date only. |
| `effective_on` | `effective_on` | Provider effective-date field when present; verify in official text. |
| `abstract` | `abstract` | Discovery summary, not controlling text. |
| `source_url` | `html_url` | FederalRegister.gov HTML representation. |
| `official_pdf_url` | `pdf_url` | GovInfo PDF link used for official-text verification. |

## Authentication, limits, and reuse

- No API key is required for the released public search.
- No exact request-rate rule was found in the checked documentation. Keep live
  checks bounded and honor 429 responses.
- Most underlying Federal Register text is a United States government work,
  but third-party submissions, images, and incorporated material can have
  separate rights. Do not apply a blanket public-domain claim to attachments.

## Errors and no-result behavior

- Invalid type or order codes are rejected locally.
- A successful empty result is bounded by term, filters, page, and the 1994
  coverage boundary.
- Invalid agency slugs can produce empty results rather than identity guidance;
  confirm slugs from the provider's agencies resource.
- Provider 4xx requires corrected input; 429 and 5xx permit bounded retry.

## Known gaps and drift risks

- Search begins in 1994 and cannot support claims about earlier material.
- Publication, effective, compliance, comment-close, and termination dates are
  different legal events.
- Abstracts and excerpts can omit qualifications in the full document.
- FederalRegister.gov HTML/XML can differ from the official PDF.
- Search totals and ordering can change as documents or metadata are updated.
- A document can correct, amend, delay, withdraw, or supersede another; search
  results alone do not establish current legal effect.
