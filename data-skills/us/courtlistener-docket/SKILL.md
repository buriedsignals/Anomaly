---
name: courtlistener-docket
description: >-
  Use this skill to search CourtListener's public RECAP federal-docket index or
  retrieve the indexed record for an exact CourtListener docket ID. Apply it to
  parties, courts, docket metadata, and up to three matching filing documents;
  never call the embedded matches a complete docket sheet or infer that an
  absent RECAP result means the case or filing does not exist.
compatibility: Requires Python 3.11+ and network access to www.courtlistener.com; a CourtListener token is optional but recommended for clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/docket
---

# Query CourtListener RECAP dockets

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/docket:search-dockets` — Search the RECAP index and return docket metadata plus no more than three matching filing-document summaries per docket.
- `us/courtlistener/docket:get-docket` — Run an exact docket_id search and return the matching indexed docket record, still subject to the three-document embedding limit.
- `us/courtlistener/docket:court-cases` — List one court's dockets, optionally by filing-date range, from the /dockets/ database endpoint as court domain rows.
- `us/courtlistener/docket:case-parties` — One request per docket id to /parties/ with nested results filtered to that docket; one row per party and role.
- `us/courtlistener/docket:case-counsel` — One request per docket id to /attorneys/ with nested results filtered to that docket; the endpoint publishes no firm, so firm_name is empty.
<!-- END GENERATED OPERATION STATUS -->
## Search or retrieve

Use `search-dockets` for a party, case, filing term, or documented advanced
operator. Use `get-docket` only for a known CourtListener numeric docket ID.

```bash
catalogue query us/courtlistener/docket --operation search-dockets \
  --input '{"q":"Purdue Pharma","court":"nysb","limit":5}'
catalogue query us/courtlistener/docket --operation get-docket \
  --input '{"docket_id":16199029,"limit":1}'
```

The `documents` array contains no more than three matching RECAP filing
documents. When `more_documents` is true, additional matching filings exist.
This operation does not enumerate the docket sheet.

## Court domain rows

`court-cases`, `case-parties` and `case-counsel` fill the court domain contract
(`domains/court.yaml`) from the PACER database endpoints, so their rows can be
written to CSV and passed to `anomaly.oneshot --tables`. These endpoints need a
CourtListener token (anonymous requests got HTTP 401 on 2026-10-27), and an
account starts at 5 requests a minute, 50 an hour and 125 a day
(https://wiki.free.law/c/courtlistener/help/api/rest/v4/rest-api-v47). Each
call is bounded: at most 5 docket pages, or 10 docket ids with one request each.

```bash
catalogue query us/courtlistener/docket --operation court-cases \
  --input '{"court":"txnd","filed_after":"2024-01-01","filed_before":"2024-12-31","pages":2}'
catalogue query us/courtlistener/docket --operation case-parties --input '{"docket_ids":[4214664]}'
```

| CourtListener field | Contract column |
|---|---|
| docket `id` | `case_id` (court_cases, case_parties, case_counsel) |
| `court_id` | `court_cases.court_id` |
| `case_name`, `docket_number` | `case_name`, `docket_number` |
| `date_filed`, `date_terminated` | `date_filed`, `date_terminated` (empty while open, or when RECAP has a stale copy) |
| `nature_of_suit` | `nature_of_suit` (empty for criminal dockets) |
| `federal_dn_office_code` (the office digit before the colon in 2:07-cv-34911) | `division` |
| person id at the end of `assigned_to`, `assigned_to_str` | `assigned_judge_id`, `assigned_judge_name`; the id is the `person_id` of the judge and financial-disclosures skills, so it joins `judge_interests.judge_id` |
| `absolute_url` | `url` |
| party `name`, `party_types[].name` for this docket | `case_parties.party_name`, `party_role` (one row per role; empty when none) |
| attorney `name` | `case_counsel.counsel_name`; `firm_name` stays empty (not published by /attorneys/) |

## Evidence discipline

- Preserve the exact query, selected court, result type, retrieval time, and ID.
- Treat counts over 2,000 as approximate; CourtListener documents about ±6%
  error for type `r` and `d` cardinality counts.
- Open `source_url` and underlying filing URLs before reporting legal claims.
- Distinguish absence from the RECAP index from absence in PACER or the court.
- Do not use the data for a prohibited FCRA purpose.

Read [the API reference](references/api-reference.md) for authentication,
limits, type `r`, result counts, and rights. Read
[the query guide](references/query-guide.md) for search and reporting practice.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved primary documentation and live contract observations.
- `references/query-guide.md` — query choice, truncated-document handling, and reporting checklist.
- `scripts/verify.py` and `assets/verification-cases.json` — live checks for both operations.
- `evals/evals.json` — behavioral cases for completeness, identifiers, and legal verification.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
