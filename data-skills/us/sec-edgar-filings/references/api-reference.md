# SEC EDGAR Full-Text Search reference

## Evidence checked

Primary SEC material was fetched with Firecrawl on 2026-08-12:

| Evidence | URL |
|---|---|
| EDGAR Full-Text Search FAQ | https://www.sec.gov/edgar/search/efts-faq.html |
| Official EDGAR public API page | https://www.sec.gov/search-filings/edgar-application-programming-interfaces |
| Developer resources | https://www.sec.gov/about/developer-resources |
| Accessing EDGAR data and fair access | https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data |
| Webmaster FAQ, reuse and developer guidance | https://www.sec.gov/about/webmaster-frequently-asked-questions |

## Evidence boundary

The official Full-Text Search FAQ documents the search user interface and query
language. The official EDGAR API page identifies JSON APIs on `data.sec.gov`
for company submissions and XBRL data. It does not document
`https://efts.sec.gov/LATEST/search-index` as a supported, versioned public API.

catalogue uses that live JSON route because it backs the SEC search experience
and is queryable, but labels it as an undocumented UI-backend integration. Its
request parameters, response shape, paging, availability, and continued access
can change without a published API contract.

## Documented search behavior

The SEC says Full-Text Search covers the full text of electronically submitted
EDGAR filings since 2001, including attachments. The FAQ documents:

- implied AND between ordinary terms;
- quotation marks for exact phrases;
- capitalized Boolean OR and NOT;
- `NEAR()` or `NEAR(n)` proximity;
- a suffix `*` wildcard, not leading/middle wildcard and not inside exact or
  Boolean searches;
- form and filing-date filters, with dates represented as `YYYY-MM-DD`.

catalogue exposes `q`, comma-separated `forms`, and paired `startdt`/`enddt`.

## Empirically verified backend behavior

Live probes on 2026-08-12 showed that the backend returned 100 hits even when a
smaller apparent size value was sent. catalogue therefore requests once and
slices locally with `limit` (1–100). The observed `from` parameter changed the
returned offset and is exposed as `offset` (0–9900). These observations are not
official contracts and must be reverified after drift.

Response hits contain an accession, document filename, form/root form, filer
names and CIKs, dates, location/classification fields, file description, and
score. The adapter constructs a direct Archive URL. Results are documents or
attachments—not a unique filing, filer, or company count.

## Fair access and reuse

SEC guidance requires a User-Agent identifying the organization and contact and
sets a current maximum automated-access rate of 10 requests per second across
machines. It also asks clients to download only what they need. The adapter
makes one request per query and can use a caller-supplied `catalogue_SEC_UA`.

The SEC webmaster FAQ says Government-created sec.gov content and EDGAR public
filing content are free to access and reuse. Confirm rights for any separately
owned material or linked content outside that statement's scope.
