---
name: companies-house-companies
description: >-
  Use this skill to search UK Companies House company summaries and retrieve a
  basic profile by exact company number with a member-provided API key. Apply it
  to company identity and current register checks; preserve leading zeros and
  do not infer directors, beneficial ownership, continuous trading, or
  historical status from the released fields.
compatibility: Requires Python 3.11+, a Companies House Live REST API key, and network access to api.company-information.service.gov.uk.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: gb/companies-house/companies
---

# Query Companies House companies

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `gb/companies-house/companies:search-companies` — Search official Companies House company summaries by term with offset pagination.
- `gb/companies-house/companies:get-company` — Retrieve official basic company information by exact Companies House company number.
- `gb/companies-house/companies:companies` — Company profiles, or every company an advanced search returns for a registered-office location, as companies-contract rows.
- `gb/companies-house/companies:company-officers` — A company's officers as company_officers rows.
- `gb/companies-house/companies:officer-appointments` — One officer's appointments across companies as company_officers rows.
- `gb/companies-house/companies:company-controllers` — A company's persons with significant control as company_controllers rows.
<!-- END GENERATED OPERATION STATUS -->
## Authentication and quota

Provide a Live REST API key through the execution context.
catalogue sends the key as the HTTP Basic username with an empty password and
keeps it out of prompts. Companies House publishes a limit of 600 requests per
five minutes; exceeding it returns 429. A 401 means unauthorised, not quota.

## Workflow

1. Assess the full request and inspect the operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show gb/companies-house/companies:search-companies
   ```

2. Search candidates with a small page, then retrieve the exact number:

   ```bash
   catalogue query gb/companies-house/companies --operation search-companies \
     --input '{"q":"BP","items_per_page":5,"start_index":0}'
   catalogue query gb/companies-house/companies --operation get-company \
     --input '{"company_number":"00102498"}'
   ```

3. Preserve company number exactly, status, type, dates, registered address,
   official profile URL, page metadata, and observation date.

## Boundaries and cautions

- Search rank and name are candidate evidence; resolve with the company number.
- Leading zeros and letter prefixes are meaningful.
- Basic profile status does not prove current commercial activity or status on
  a historical date.
- Filings, charges, insolvency, registers, disqualifications, and PSC
  statements are documented provider scope but not released here.
- Register data is filed information and can be corrected or updated.

## Fill the companies contract

`companies`, `company-officers`, `officer-appointments` and
`company-controllers` return rows of `domains/companies.yaml`. Write each to
CSV and run the companies detectors with
`python -m anomaly.oneshot --tables companies=... --tables company_officers=... --tables company_controllers=...`.
Endpoints follow the Public Data API specification
(https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference,
read 2026-10-27). No key was configured when these operations were written, so
they are tested offline against the documented response shapes only.

```bash
catalogue query gb/companies-house/companies --operation companies \
  --input '{"location":"10 Queen Street Place","limit":2000}'
catalogue query gb/companies-house/companies --operation officer-appointments \
  --input '{"officer_id":"<id from company-officers>"}'
```

| If the source publishes | map it to column |
|---|---|
| `company_number` | `company_id` = `gb:` + number (leading zeros kept); `jurisdiction` = `GB` |
| `company_name`, `company_status` | `name`, `status` |
| `date_of_creation`, `date_of_cessation` | `incorporation_date`, `dissolution_date` |
| `registered_office_address` (premises, lines, locality, region, postal code; care-of and country dropped) | `registered_address` |
| `previous_company_names[]` (profile only; empty from advanced search) | `previous_name_count` |
| officer `links.officer.appointments` (`/officers/{id}/appointments`) | `officer_id` |
| officer `name`, `officer_role`, `appointed_on`, `resigned_on` | `name`, `role`, `appointed_on`, `resigned_on` |
| appointment `appointed_to.company_number`, `.company_name` | `company_id`, `company_name` |
| PSC `kind` individual / corporate-entity or legal-person / super-secure | `controller_kind` = `individual` / `legal_entity` / `statement` |
| PSC `name` (+ `date_of_birth` year-month for a person) | `controller_id` = `gb:psc:` + upper-case name (+ `\|YYYY-MM`), `controller_name` |
| PSC `country_of_residence` (person) or `identification.country_registered` (entity) | `controller_country`, as free text: convert to ISO alpha-2 before running `secrecy_jurisdiction_controller` |
| UK `identification.registration_number` | `controller_company_id` = `gb:` + number zero-padded to 8 digits |
| `natures_of_control[]`, `notified_on`, `ceased_on` | `control_type` (joined by `\|`), `notified_on`, `ceased_on` |

Advanced search returns at most 5,000 companies per request (`size`), and
`location` matches the registered-office address text; an address count is only
as complete as that search. PSCs carry no register-wide identifier, so the same
person under two spellings counts twice in `prolific_officer`.

Read [the API reference](references/api-reference.md) and
[the query guide](references/query-guide.md) for response vocabulary,
pagination, no-result recovery, and follow-up verification.

## Bundled resources

- `references/api-reference.md` — official endpoint, profile, quota, auth,
  licensing, response mapping, and errors.
- `references/query-guide.md` — identity resolution and historical cautions.
- `scripts/verify.py` with `assets/verification-cases.json` — credentialed checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
