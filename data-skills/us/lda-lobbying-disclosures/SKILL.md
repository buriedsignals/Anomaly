---
name: lda-lobbying-disclosures
description: >-
  Use this skill to fetch US federal lobbying filings (LD-1/LD-2) and LD-203
  contribution reports from LDA.gov as rows of Anomaly's lobbying contract
  tables, ready for the lobbying detectors. Each operation fills one table:
  the generic lobbying_registrations or lobbyists, or the US extension tables
  lobbying_foreign_entities, lobbying_activities or political_contributions.
compatibility: Requires Python 3.11+ and network access to lda.gov (which refused non-US requests in testing); an LDA.gov key is optional.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/lda/lobbying-disclosures
---

# Fetch LDA filings as lobbying contract rows

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/lda/lobbying-disclosures:lobbying-registrations` — One row per LD-1/LD-2 filing matching the filters.
- `us/lda/lobbying-disclosures:lobbyists` — One row per lobbyist and disclosed covered position on the matching filings.
- `us/lda/lobbying-disclosures:lobbying-foreign-entities` — One row per foreign entity listed on the matching filings.
- `us/lda/lobbying-disclosures:lobbying-activities` — One row per lobbying activity (issue) on the matching filings.
- `us/lda/lobbying-disclosures:political-contributions` — One row per contribution item on the matching LD-203 reports.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Pick a bounded scope: a registrant or client (name or ID) and a filing
   year. Look IDs up at https://lda.gov/registrants/public/registrant-client/lookup/.
2. Run each operation with the same filters and enough `pages` (25 filings
   per page, up to 40) to cover the scope. `page.count` and `page.next` in
   the result say whether more remain.

   ```python
   from pathlib import Path
   from anomaly.sources.registry import discover_sources, load_source_adapter

   entries = discover_sources(Path("data-skills"))
   lda = load_source_adapter(entries, "us/lda/lobbying-disclosures")
   result = lda.run({"operation": "lobbying-registrations", "registrant_id": 682,
                     "filing_year": 2025, "pages": 10}, None)
   ```

3. Write each operation's `records` to `<table>.csv` (columns already match
   `domains/lobbying.yaml`) and run the detectors:

   ```bash
   python -m anomaly.oneshot --tables lobbying_registrations=lobbying_registrations.csv \
     --tables lobbyists=lobbyists.csv --request request.json --approved
   ```

   The generic lobbying detectors need only `lobbying_registrations` (and
   `lobbyists` for revolving-door candidates). The US-only detectors also read
   `lobbying_foreign_entities`, `lobbying_activities`,
   `political_contributions`, or the FARA and Congress tables.

Filing-based operations re-read the same filings; with no key, LDA.gov allows
15 requests per minute, so a free key helps (pass a context whose
`get_key_optional("lda")` returns it instead of `None`)
for anything beyond a few pages. The adapter waits once when the API asks for
a pause of 60 seconds or less.

## Column mapping

If the register publishes X, map it to column Y. The adapter does this; the
table is the contract for anyone loading LDA bulk files another way.

| LDA field | Contract column |
|---|---|
| `filing_uuid` | `registration_id` (all tables) |
| source id `us/lda/lobbying-disclosures` | `lobbying_registrations.register` |
| `filing_year` + `filing_period` (quarter, mid-year, year-end) | `period_start`, `period_end` (first and last day of the period) |
| `registrant.id`, `registrant.name` | `registrant_id`, `registrant_name` |
| `client.id`, `client.name`, left empty when `client.client_self_select` is true | `client_id`, `client_name` |
| `client.country` | `client_country` |
| `income`, or `expenses` when there is no income | `spend_low` and `spend_high` (exact amount, so low = high) |
| `lobbying_activities[].general_issue_code`, joined with `|` | `issue_area` |
| `filing_type` (`Q1`..`Q4`, `RR`, `1A` ...) | `filing_type` |
| `filing_document_url` | `url` |
| `client.general_description`, `client.ppb_country`, `posted_by_name` | `client_description`, `client_ppb_country`, `posted_by_name` (read by US detectors) |
| `lobbyists[].lobbyist.id`, first + last name | `lobbyists.lobbyist_id`, `lobbyists.name` |
| `lobbyists[].covered_position` | `lobbyists.former_public_office` (no institution or end date is published) |
| `foreign_entities[]` | `lobbying_foreign_entities` |
| `lobbying_activities[]` code, description, position | `lobbying_activities` |
| LD-203 `contribution_items[]` | `political_contributions` |

LDA publishes no meetings with named officials, so `lobbying_contacts` stays
empty and the contact detectors do not apply.

## Source boundary

- Amendments keep their own `filing_type` codes; generic detectors keep one
  spend value per registrant, client and period, so an amendment replaces the
  original when its amount is higher.
- `client_id` is the API's client record ID.
- Covered positions are self-disclosed free text.
- Cite the retrieval date and state that the Senate Office of Public Records
  cannot vouch for the data or analyses after retrieval (API terms).
- LDA.gov returned HTTP 403 to direct requests from a Swiss network on
  2026-10-27; run from a network the API accepts.

Read [the API reference](references/api-reference.md) for endpoints, fields,
and limits.

## Bundled resources

- `references/api-reference.md` — endpoints, field mapping, terms, limits.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — scope and interpretation cases.
