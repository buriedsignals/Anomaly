# CourtListener financial-disclosure API reference

## Evidence checked

Firecrawl fetched current primary documentation on 2026-08-12:

| Evidence | URL |
|---|---|
| REST API v4.6 | https://www.courtlistener.com/help/api/rest/v4/ |
| Financial Disclosures API | https://www.courtlistener.com/help/api/rest/v4/financial-disclosures/ |
| API root | https://www.courtlistener.com/api/rest/v4/ |
| Terms and policies | https://www.courtlistener.com/terms/ |

Live `OPTIONS` on `/api/rest/v4/financial-disclosures/` confirmed the current
field contract. A live request confirmed that `person` works and `year` is
rejected with “Unknown filter parameters are not allowed.”

## Released endpoint

`GET https://www.courtlistener.com/api/rest/v4/financial-disclosures/?person=<id>&fields=...`

The parent record links a judge/person to report metadata and nested records:

- investments and disclosure positions;
- agreements and debts;
- gifts and reimbursements;
- non-investment and spouse income;
- source PDF, thumbnail, SHA-1, year, report type, amended flag, and extraction status.

This skill requires an exact CourtListener person ID. It does not release
cross-person searches on the separate nested-resource endpoints.

## Value codes, inference, and redaction

Investment/debt forms often disclose ranges, not exact amounts. Codes J through
P4 span `$1–$15,000` through `$50,000,001 or more`; `-1` marks failed
extraction. catalogue preserves the original code and supplies a readable range.

`has_inferred_values` means CourtListener inferred repeated/blank table cells
from layout. It must not be presented as explicitly reported content.

Rows can have `redacted=true`. The provider describes this as a signal for more
careful review. Never try to reconstruct a protected value from adjacent rows.

## Coverage and primary evidence

CourtListener describes these as records of current and former federal judges,
collected from Senate records and information requests to the judiciary, with
coverage limitations on a separate provider page. Extracted data can be
incomplete. The linked PDF is the primary report for publication checks.

## Authentication, limits, and rights

Public experimentation can work without authentication; deployed clients
should use `Authorization: Token <token>`. Current default authenticated limits
are 5/minute, 50/hour, and 125/day. Provider terms prohibit FCRA uses and
credential rotation. Treat document and extracted-data rights conservatively;
this bundle does not grant blanket redistribution permission.
