---
name: electoral-commission-donations
description: >-
  Use this skill to fetch donations reported to the UK Electoral Commission by
  parties, non-party campaigners and regulated donees, and the registers of
  parties and campaigners with their registration dates, as campaign_finance
  contract rows for Anomaly detectors.
compatibility: Requires Python 3.11+ and network access to search.electoralcommission.org.uk.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: gb/electoral-commission/donations
---

# Query UK Electoral Commission donations

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `gb/electoral-commission/donations:donations` — One row per reported donation matching the search term or accepted-date range.
- `gb/electoral-commission/donations:registrations` — One row per registered, lapsed or deregistered party or campaigner with its approval date.
<!-- END GENERATED OPERATION STATUS -->

## Fetch contract rows

The adapter reads the CSV exports behind the Commission's register search
(https://search.electoralcommission.org.uk/). Every row already carries the
column names of `domains/campaign_finance.yaml`, so write the records to JSONL
and pass them to `anomaly.oneshot` without a column map:

```bash
catalogue query gb/electoral-commission/donations --operation donations \
  --input '{"entity_types":["pp"],"from":"2025-01-01","to":"2026-06-30"}'
catalogue query gb/electoral-commission/donations --operation registrations \
  --input '{"entity_types":["pp"]}'
python -m anomaly.oneshot --tables donations=donations.jsonl \
  --tables recipients=recipients.jsonl --request request.json --approved
```

`entity_types` takes `pp` (political party), `ppm` (minor party), `tp`
(non-party campaigner), `perpar` (referendum participant) and `rd` (regulated
donee, such as an MP). The export ignores paging and returns every matching
row, so a donations query needs a search term or both `from` and `to`
(accepted dates); `max_rows` (default 10,000) truncates the result and the
page block says whether it did.

## Read the rules before reading the data

The Commission says there is no limit on the value of donations; recipients
may only accept them from permissible sources. Parties report donations over
11,180 GBP to the central party (over 2,230 GBP once that donor has given in
the calendar year) and over 2,230 GBP to accounting units
(https://www.electoralcommission.org.uk/political-registration-and-regulation/financial-reporting/donations-and-loans).
So the register is not a full list of gifts: smaller ones appear only once they
aggregate past a threshold (`is_aggregation`). There is no contribution limit
to be "near", so run `campaign_finance.maxed_donor_clusters` with a
`limit_amount` that means something for the question (for example a reporting
threshold), and expect postcode clusters only among company donors, since
individuals' postcodes are not published. `recipient_id` is the regulated
entity; a party's local branches appear in `accounting_unit` under the same id.

| If the Commission publishes | map it to column | notes |
|---|---|---|
| `ECRef` (donations) | `donations.donation_id` | e.g. C0840618 |
| `RegulatedEntityId` | `donations.recipient_id` | numeric entity id |
| `RegulatedEntityName` | `donations.recipient_name`, `recipients.name` | |
| `RegulatedEntityType` | `donations.recipient_type` | Political Party, Third Party, ... |
| `DonorName` | `donations.donor_name` | leading spaces trimmed |
| `DonorStatus` | `donations.donor_type` | Individual, Company, Trade Union, Public Fund, ... |
| `CompanyRegistrationNumber` | `donations.donor_company_number` | company donors only |
| (not published) | `donations.donor_employer` | always null |
| `Postcode` | `donations.donor_postcode` | not published for individuals |
| `Value` ("£50,000.00") | `donations.amount` | parsed to a number |
| constant `GBP` | `donations.currency` | |
| `ReceivedDate` (else `AcceptedDate`), dd/mm/yyyy | `donations.donation_date` | ISO date |
| `AcceptedDate`, `DonorId`, `AccountingUnitName`, `DonationType`, `IsAggregation`, `ReportingPeriodName` | extra columns `accepted_date`, `donor_id`, `accounting_unit`, `donation_type`, `is_aggregation`, `reporting_period` | ignored by the runner, kept for verification |
| `ECRef` (registrations) without its letter prefix | `recipients.recipient_id` | PP7931 -> 7931, equals `RegulatedEntityId` |
| `ApprovedDate` | `recipients.registered_date` | ISO date |

If you download a CSV from the search page yourself instead, its headers are
the left column above; map them with a `columns` object in the request and
convert `Value` and the dd/mm/yyyy dates first.

## Use and licence

The Commission states that it licenses information under the Open Government
Licence wherever possible (https://api.electoralcommission.org.uk/terms/); the
register export itself states no licence, so attribute the Electoral
Commission and check before republishing rows. Donations to Northern Ireland
recipients before 1 July 2017 are not published. A reported donation is a
lawful, accepted (or returned) gift until shown otherwise.
