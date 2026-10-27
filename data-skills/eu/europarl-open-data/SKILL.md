---
name: europarl-open-data
description: >-
  Use this skill to query official European Parliament Open Data API v2 for
  current MEP candidates, one known MEP, plenary speech activities, and adopted
  texts. Apply it to Parliament identity and document discovery; do not use the
  source router as an unrestricted API proxy or infer legal effect, a complete
  transcript, or a person's identity from the normalized result alone.
compatibility: Requires Python 3.11+ and network access to data.europarl.europa.eu.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: eu/europarl/open-data
---

# Query European Parliament open data

`meta.yaml` is the executable contract. Use only operations marked **Released**
below even though the provider and source-level adapter cover more resources.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `eu/europarl/open-data:search-meps` — Filter the current MEP roster by documented country, group, term, and gender fields, with optional transparent local name matching.
- `eu/europarl/open-data:get-mep` — Retrieve one MEP record from the official person detail endpoint by European Parliament identifier.
- `eu/europarl/open-data:search-speeches` — Search plenary speech and speech-related activities using the provider's text and documented participant/date filters.
- `eu/europarl/open-data:search-adopted-texts` — Search adopted European Parliament texts using provider full text with optional year and procedure-type filters.
- `eu/europarl/open-data:parl-members` — One row per MEP with a mandate in the parliamentary term (default 10), with the country they represent.
- `eu/europarl/open-data:parl-affiliations` — Every political-group and national-party membership of the term's MEPs, ended ones included, with dates, short labels and the term each began in.
- `eu/europarl/open-data:parl-votings` — One row per electronic roll-call decision in the given plenary sittings (show-of-hands and secret votes are skipped).
- `eu/europarl/open-data:parl-member-votes` — One row per MEP on the roll of each roll-call vote: for, against or abstain from the decision's voter lists, and absent for MEPs with a mandate that day in no list.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete request and inspect the exact operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show eu/europarl/open-data:search-meps
   ```

2. Run one explicit operation:

   ```bash
   catalogue query eu/europarl/open-data --operation search-meps \
     --input '{"name":"Keller","country":"FR","limit":5}'
   catalogue query eu/europarl/open-data --operation get-mep \
     --input '{"mep_id":"22858","language":"en"}'
   catalogue query eu/europarl/open-data --operation search-speeches \
     --input '{"q":"artificial intelligence","language":"en","limit":10}'
   catalogue query eu/europarl/open-data --operation search-adopted-texts \
     --input '{"q":"artificial intelligence","language":"en","limit":10}'
   ```

3. Preserve Parliament identifiers, dates, activity/document type, files,
   provider links, page scope, and `European Parliament Open Data (CC BY 4.0)`
   attribution.

## Parliamentary contract rows

The `parl-*` operations return rows of `domains/parliamentary.yaml`, ready for
`anomaly.oneshot` without a column map (parliament is always `EP`):

```bash
catalogue query eu/europarl/open-data --operation parl-member-votes \
  --input '{"sitting_dates":["2025-10-22","2025-10-23"]}'
python -m anomaly.oneshot --tables parl_members=members.jsonl \
  --tables parl_votings=votings.jsonl --tables parl_member_votes=votes.jsonl \
  --tables parl_affiliations=affiliations.jsonl --request request.json --approved
```

Votes come from `GET /meetings/MTG-PL-{date}/decisions`, keeping decisions
whose `decision_method` is `VOTE_ELECTRONIC_ROLLCALL` (on 2025-10-22: 198 of
471 decisions; the rest were show of hands, electronic without names, or
secret). Each decision lists voters by person id; the list lengths equal the
published counts. MEPs and memberships come from `GET /meps?parliamentary-term=N`
and `GET /meps/{id,id,...}` (50 ids per request), group and party labels from
`GET /corporate-bodies/{id,...}`. A one-sitting member-votes call makes about 31 requests (747 MEPs, 629 groups and parties in term 10); the API allows 500 per endpoint per five minutes.

| Parliament publishes | column | notes |
|---|---|---|
| person `identifier` | `member_id` | also the id in voter lists (`person/{id}`) |
| person `label` | `parl_members.name` | |
| `represents` on the `MEMBER_PARLIAMENT` membership of `org/ep-N` | `parl_members.country` | 3-letter code mapped to EU 2-letter (EL, not GR) |
| `hasMembership` classified `EU_POLITICAL_GROUP` / `NATIONAL_POLITICAL_GROUP` | `parl_affiliations` rows, `affiliation_type` group / party | ended memberships kept; one row per role period |
| corporate body `label` | `org_name`, `group_at_vote` | short label (ECR, PPE, NI); a group gets a new body id each term |
| term of the mandate covering the membership start | `parl_affiliations.term` | group_switch compares only within a term |
| `memberDuring.startDate` / `endDate` | `start_date` / `end_date` | |
| decision `notation_votingId` | `voting_id` | |
| decision `activity_date`, `activity_label` | `vote_date`, `title` | |
| `decided_on_a_realization_of` | `dossier_id` | often empty |
| `had_voter_favor` / `_against` / `_abstention` | `position` for / against / abstain | `had_voter_intended_*` corrections are not applied |
| MEP with a mandate that day in no voter list | `position` absent | |
| group membership covering the vote date | `group_at_vote` | |

Read before using absences: in a four-sitting sample (2025-07-09/10,
2025-10-22/23) seven MEPs with open mandates appeared in no voter list,
among them the President, who chairs and rarely votes. The cause for the
other six is not established; check the MEP's official page before reporting
their rate. Roll-call votes are a subset of all votes and over-represent
amendments.

## Operation boundaries

- `search-meps` calls the current-roster endpoint. Because the API has no
  MEP-name filter, `name` performs a transparent local case-insensitive
  substring match after one filtered roster request.
- `get-mep` retrieves one provider person identifier and returns current
  memberships separately from ended raw memberships.
- `search-speeches` returns speech-related activity metadata, not transcript
  text or a quotation.
- `search-adopted-texts` returns adopted Parliament documents. Adoption is not
  publication in the Official Journal or proof of current legal effect.

Read [the API reference](references/api-reference.md) for endpoint/filter
mapping and [the query guide](references/query-guide.md) for identity,
speech, and document research patterns.

## Service and error discipline

The public API permits at most 500 requests to the same endpoint in five
minutes. Use collection filters, small pages, and bounded retries. The provider
can return HTTP success with an embedded `error` and no `data`; the adapter
raises that as an upstream contract failure rather than misreporting no results.

## Bundled resources

- `references/api-reference.md` — primary evidence, provider scope, mappings,
  rate limit, response caveats, and known drift.
- `references/query-guide.md` — person resolution and evidence chains.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
