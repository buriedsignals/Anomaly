---
name: transparency-register-lobbying
description: >-
  Use this skill to fetch EU lobbying data as rows of Anomaly's lobbying
  contract: organisations in the EU Transparency Register (with declared
  clients and money ranges) as lobbying_registrations, and their meetings with
  Commissioners, cabinets and Directors-General as lobbying_contacts.
compatibility: Requires Python 3.11+ and network access to transparency-register.europa.eu and ec.europa.eu; no key.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: eu/transparency-register/lobbying
---

# Fetch EU Transparency Register data as lobbying contract rows

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `eu/transparency-register/lobbying:lobbying-registrations` — One row per declared client of a consultancy, or one row per organisation lobbying for itself.
- `eu/transparency-register/lobbying:lobbying-contacts` — One row per registered organisation and Commission participant in a published meeting.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Fetch registrations and contacts. Each call downloads the whole export
   (the register is about 120 MB) and filters locally, so narrow with `ids`,
   `q`, `country`, `category`, `meetings`, `since`/`until` and `limit`.

   ```python
   from pathlib import Path
   from anomaly.sources.registry import discover_sources, load_source_adapter

   eu = load_source_adapter(discover_sources(Path("data-skills")), "eu/transparency-register/lobbying")
   registrations = eu.run({"operation": "lobbying-registrations", "limit": 100000}, None)
   contacts = eu.run({"operation": "lobbying-contacts", "since": "2025-01-01"}, None)
   ```

2. Write each operation's `records` to `<table>.csv` and run the generic
   lobbying detectors:

   ```bash
   python -m anomaly.oneshot --tables lobbying_registrations=lobbying_registrations.csv \
     --tables lobbying_contacts=lobbying_contacts.csv --request request.json --approved
   ```

   Useful here: `single_client_juggernauts`, `missing_spend_filings`,
   `foreign_clients` and `contact_bursts`. For `foreign_clients`, pass the 27
   member states as `home_countries`, spelled as the register spells them:
   `AUSTRIA|BELGIUM|BULGARIA|CROATIA|CYPRUS|CZECH REPUBLIC|DENMARK|ESTONIA|FINLAND|FRANCE|GERMANY|GREECE|HUNGARY|IRELAND|ITALY|LATVIA|LITHUANIA|LUXEMBOURG|MALTA|NETHERLANDS|POLAND|PORTUGAL|ROMANIA|SLOVAKIA|SLOVENIA|SPAIN|SWEDEN`.
   `spending_spikes`, `issue_concentration_shifts` and `new_registrant_surge`
   compare periods; one export holds a single closed financial year per
   organisation, so they need several half-yearly snapshots concatenated
   (not read by this adapter).

## Column mapping

If the register publishes X, map it to column Y. The adapter does this; the
table is the contract for anyone loading the XLS export or older snapshots.

| Register or meetings field | Contract column |
|---|---|
| `identificationCode` | `registration_id` and `registrant_id` |
| source id `eu/transparency-register/lobbying` | `register` |
| `financialData/closedYear/startDate`, `endDate` (else `registrationDate`) | `period_start`, `period_end` |
| `name/originalName` | `registrant_name` |
| `closedYear/clients/client/name` (consultancies, one row per client) | `client_name`; `client_id` stays empty |
| none for clients; `headOffice/country` when the organisation lobbies for itself | `client_country` |
| client `revenue/range/min`, `max` (consultancies) or `costs/range/min`, `max` (own lobbying); `absoluteCost` sets both | `spend_low`, `spend_high` (a band with only a maximum has low 0) |
| `interests/interest/name`, joined with `\|` | `issue_area` |
| `registrationCategory` | `filing_type` |
| `headOffice/country` | `head_office_country` (extra column, not in the contract) |
| meeting `cabinet`, or `dgname (dgacronym)` | `lobbying_contacts.institution` |
| meeting `date`, `subject` | `contact_date`, `subject` |
| meeting `entities/entity/id`, `name` | `lobbying_contacts.registrant_id`, `registrant_name` |
| meeting `representatives/representative/name`, `title` | `official_name`, `official_title` |
| hash of export, institution, date, location, subject | `contact_id` |

The register names no individual lobbyists with former offices, so the
`lobbyists` table stays empty and the revolving-door detectors do not apply.

## Source boundary

- Money is a band for the closed financial year; detectors use the midpoint.
- Meeting exports cover only Commissioners, cabinet members and
  Directors-General, not other Commission staff, Parliament or Council.
- The exports repeat some meetings and entities verbatim; the adapter keeps
  one row per meeting, organisation and participant.
- Cite the Transparency Register and the retrieval date. No dataset licence
  is shown on data.europa.eu; the Commission reuse policy (Decision
  2011/833/EU) applies.
