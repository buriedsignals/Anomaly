---
name: openfec-campaign-finance
description: >-
  Use this skill to search US federal candidate and committee registrations by
  name with official OpenFEC filters, and to fetch Schedule A itemized receipts
  and committee registration dates as campaign_finance contract rows for
  Anomaly detectors. Not for financial-total claims; check current FEC terms
  and acceptable-use limits.
compatibility: Requires Python 3.11+, a free api.data.gov key, and network access to api.open.fec.gov.
metadata:
  author: Buried Signals
  version: "1.1"
  source-id: us/fec/campaign-finance
---

# Query OpenFEC candidates, committees and receipts

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/fec/campaign-finance:search-candidates` — Search candidate registrations by name and optional office, geography, party, cycle, status, activity, and pagination filters.
- `us/fec/campaign-finance:search-committees` — Search committee registrations by name and optional type, designation, geography, party, cycle, filing frequency, treasurer, and pagination filters.
- `us/fec/campaign-finance:donations` — One row per itemized receipt for the named committees or contributors, in receipt-date order, read by keyset pagination.
- `us/fec/campaign-finance:recipients` — One row per committee with its first Statement of Organization date, by committee id or first-filing date range.
<!-- END GENERATED OPERATION STATUS -->
## Search entities, then resolve identifiers

```bash
catalogue query us/fec/campaign-finance --operation search-candidates \
  --input '{"q":"Warren","office":"S","state":"MA","per_page":10}'

catalogue query us/fec/campaign-finance --operation search-committees \
  --input '{"q":"ACTBLUE","per_page":10}'
```

Candidate IDs are office-specific: the same person can have different IDs for
different offices. Committee names are not unique and can change; preserve
`committee_id`, filing dates, cycle, type, and designation.

The two search operations return registration/entity data only. Receipts come
from the `donations` operation below; disbursements, independent expenditures,
cash, debt, and financial totals are not released.

## Fetch campaign_finance contract rows

`donations` reads `GET /v1/schedules/schedule_a/` and `recipients` reads
`GET /v1/committees/`. Every row already carries the contract column names of
`domains/campaign_finance.yaml`, so write the records to JSONL and pass them to
`anomaly.oneshot` without a column map:

```bash
catalogue query us/fec/campaign-finance --operation donations \
  --input '{"committee_id":"C00718866","two_year_transaction_period":2026,"min_amount":3000,"pages":5}'
catalogue query us/fec/campaign-finance --operation recipients \
  --input '{"min_first_f1_date":"2026-05-01","committee_type":"O"}'
python -m anomaly.oneshot --tables donations=donations.jsonl \
  --tables recipients=recipients.jsonl --request request.json --approved
```

Schedule A pages by keyset: the adapter passes `pagination.last_indexes` back
as the next request's parameters, as the OpenFEC docs require, and stops after
`pages` (at most 20 pages of 100). It refuses more than 10 `committee_id`
values per request. `is_individual` defaults to true, which keeps
non-earmarked individual contributions only and avoids counting a conduit
(ActBlue, WinRed) memo entry twice; set it to false to see contributions from
companies and organisations, for example when checking who funds a new super
PAC. Contributions from one person to a candidate's primary and general
elections are separate limits, so read `election_type` before calling repeated
gifts excessive.

| If OpenFEC publishes | map it to column | notes |
|---|---|---|
| Schedule A `sub_id` | `donations.donation_id` | FEC record number, unique per row |
| `committee_id` | `donations.recipient_id`, `recipients.recipient_id` | |
| `committee_name` (else `committee.name`) | `donations.recipient_name` | latest committee name |
| `committee.committee_type_full` | `donations.recipient_type` | |
| `contributor_name` | `donations.donor_name` | "LAST, FIRST" for individuals |
| `entity_type_desc` (else `entity_type`) | `donations.donor_type` | INDIVIDUAL, ORGANIZATION, PAC, ... |
| (not published) | `donations.donor_company_number` | always null |
| `contributor_employer` | `donations.donor_employer` | self-reported; placeholders such as "NOT EMPLOYED" and "SELF EMPLOYED" are common |
| `contributor_zip` | `donations.donor_postcode` | often 9-digit ZIP+4 |
| `contribution_receipt_amount` | `donations.amount` | USD |
| constant `USD` | `donations.currency` | |
| `contribution_receipt_date` | `donations.donation_date` | date part only |
| `election_type`, `memo_text`, `pdf_url` | extra columns `election_type`, `memo_text`, `url` | ignored by the runner, kept for verification |
| committees `name` | `recipients.name` | |
| `first_f1_date` (else `first_file_date`) | `recipients.registered_date` | first Statement of Organization |

The bulk "contributions by individuals" file uses different names for the same
fields: `SUB_ID`, `CMTE_ID`, `NAME`, `EMPLOYER`, `ZIP_CODE`,
`TRANSACTION_AMT`, `TRANSACTION_DT` (MMDDYYYY) and `ENTITY_TP`
(https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/);
map them with a `columns` object in the request and convert the date first.

## Apply FEC usage restrictions

OpenFEC identifies itself as the source and says data are updated nightly. Its
current Terms of Service and Acceptable Use Policy govern reuse. The current
policy includes a broad commercial-use restriction; federal law separately
restricts sale or use of individual-contributor information for solicitation or
commercial purposes. Users must assess their intended use against the current
official terms. The `donations` operation returns contributor names, employers and ZIP codes:
never use them to solicit contributions or for commercial purposes.

Read [the API reference](references/api-reference.md) for endpoint parameters,
codes, pagination, and official policies. Read [the query guide](references/query-guide.md)
for candidate and committee resolution.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved FEC docs, OpenAPI, and policies (Schedule A and recipients: this SKILL.md).
- `references/query-guide.md` — identity resolution, filter, and reporting workflow.
- `scripts/verify.py` and `assets/verification-cases.json` — live candidate and committee checks.
- `evals/evals.json` — identifier, financial-scope, cycle, and reuse cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
