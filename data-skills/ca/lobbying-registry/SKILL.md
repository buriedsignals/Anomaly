---
name: lobbying-registry
description: >-
  Use this skill to fetch Canada's federal Registry of Lobbyists as rows of
  Anomaly's lobbying contract: registrations (lobbying_registrations), the
  lobbyists and former public offices they declare (lobbyists), and monthly
  communication reports with designated public office holders
  (lobbying_contacts).
compatibility: Requires Python 3.11+ and either network access to lobbycanada.gc.ca or the two ZIP exports downloaded in a browser; no key.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: ca/ocl/registry-of-lobbyists
---

# Fetch Canada's Registry of Lobbyists as lobbying contract rows

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `ca/ocl/registry-of-lobbyists:lobbying-registrations` — One row per registration version.
- `ca/ocl/registry-of-lobbyists:lobbyists` — One row per lobbyist and declared public office on each selected registration.
- `ca/ocl/registry-of-lobbyists:lobbying-contacts` — One row per designated public office holder in a current (not superseded) monthly communication report.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Get the exports. The adapter downloads them from lobbycanada.gc.ca, which
   refused scripted downloads with a Cloudflare challenge in testing. If the
   result is `upstream-unavailable`, download the two ZIPs from the dataset
   pages in a browser and pass their paths:
   - Registrations: https://open.canada.ca/data/en/dataset/70ef2117-1095-4d77-80eb-b87f2bada2a4
   - Communication reports: https://open.canada.ca/data/en/dataset/a34eb330-7136-4f5e-9f5f-3ba41df58b06

   ```python
   from pathlib import Path
   from anomaly.sources.registry import discover_sources, load_source_adapter

   ca = load_source_adapter(discover_sources(Path("data-skills")), "ca/ocl/registry-of-lobbyists")
   regs = ca.run({"operation": "lobbying-registrations", "since": "2020-01-01",
                  "registrations_zip": "registrations_enregistrements_ocl_cal.zip"}, None)
   people = ca.run({"operation": "lobbyists", "since": "2020-01-01",
                    "registrations_zip": "registrations_enregistrements_ocl_cal.zip"}, None)
   contacts = ca.run({"operation": "lobbying-contacts", "since": "2020-01-01",
                      "communications_zip": "communications_ocl_cal.zip"}, None)
   ```

2. Write each operation's `records` to `<table>.csv` and run the generic
   lobbying detectors:

   ```bash
   python -m anomaly.oneshot --tables lobbying_registrations=lobbying_registrations.csv \
     --tables lobbyists=lobbyists.csv --tables lobbying_contacts=lobbying_contacts.csv \
     --request request.json --approved
   ```

   Useful here: `former_official_lobbies_former_institution`,
   `revolving_door_candidates`, `contact_bursts`, `new_registrant_surge` and
   `issue_concentration_shifts`. The registry publishes no money, so the
   spend detectors return nothing.

## Column mapping

If the register publishes X, map it to column Y. The adapter does this; the
table is the contract for anyone loading the CSV files another way.

| Registry file and column | Contract column |
|---|---|
| `Registration_PrimaryExport.REG_ID_ENR` (one id per registration version) | `registration_id` |
| source id `ca/ocl/registry-of-lobbyists` | `register` |
| `EFFECTIVE_DATE_VIGUEUR`, `END_DATE_FIN` | `period_start`, `period_end` |
| consultant (`REG_TYPE_ENR` 1): `RGSTRNT_NUM_DECLARANT`, registrant first + last name | `registrant_id`, `registrant_name` |
| in-house (`REG_TYPE_ENR` 2, 3): `org-` + `CLIENT_NUM`, `EN_CLIENT_NM_AN` | `registrant_id`, `registrant_name` (no client) |
| consultant: `CLIENT_NUM`, `EN_CLIENT_NM_AN` | `client_id`, `client_name` |
| none (only a free-text address) | `client_country` stays empty |
| none | `spend_low`, `spend_high` stay empty |
| `SMT-` codes in `Registration_SubjectMattersExport` and `Registration_SubjectMatterDetails Export`, named by `Codes_SubjectMatterTypesExport`, joined with `\|` | `issue_area` |
| `REG_TYPE_ENR` (consultant, in-house corporation, in-house organization) | `filing_type` |
| registration page `vwRg?cno=CLIENT_NUM&regId=REG_ID_ENR` | `url` |
| `Registration_ConsultantLobbyistsExport` / `InHouseLobbyistsExport`: `LBBYST_ID_LBBYST`, first + last name | `lobbyists.lobbyist_id`, `name` (linked to registrations by registrant number and client profile, or client profile for in-house) |
| `Registration_PublicOfficeExport.TITLE_TITRE`, `INSTITUTION`, `POS_END_DATE_FIN_POSTE` (else `DPOH_LAST_DATE_FIN_TCPD`) | `former_public_office`, `former_office_institution`, `former_office_end` (one row per office) |
| `Communication_PrimaryExport.COMLOG_ID` (reports named in `PREV_COMLOG_ID_PRECEDNT` are dropped as superseded) | `lobbying_contacts.contact_id` |
| `COMM_DATE` | `contact_date` |
| consultant: `REGISTRANT_NUM_DECLARANT`; in-house: `org-` + `CLIENT_ORG_CORP_NUM` | `lobbying_contacts.registrant_id` (same ids as registrations) |
| `Communication_DPOHExport` DPOH first + last name, `DPOH_TITLE_TITRE_TCPD` | `official_name`, `official_title` |
| `INSTITUTION`, or `OTHER_INSTITUTION_AUTRE` when it is Other | `institution` |
| subject-matter codes of the report | `subject` |

Extra columns (`firm_name`, `client_profile_id`, `client_name` on contacts)
are ignored by the runner.

## Source boundary

- Every update creates a registration version; count registration numbers,
  not rows, when reporting how many registrations exist.
- Consultant contacts are linked to the consultant, not the client, so
  `former_official_lobbies_former_institution` links a lobbyist and a contact
  through the same consultant or organisation, not the same person.
- The real files' character encoding and date format were not verified
  (download blocked in testing); the adapter reads UTF-8 and takes the first
  ten characters of dates in `YYYY-MM-DD` form.
- Cite the Office of the Commissioner of Lobbying of Canada, the retrieval
  date, and its Open Data Licence Agreement.
