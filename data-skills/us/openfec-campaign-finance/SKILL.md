---
name: openfec-campaign-finance
description: >-
  Use this skill to search US federal candidate and committee registrations by
  name with official OpenFEC filters and stable FEC identifiers. Apply it to
  candidate/committee identity and filing-history discovery, not transaction or
  financial-total claims; check current FEC terms and acceptable-use limits.
compatibility: Requires Python 3.11+, a free api.data.gov key, and network access to api.open.fec.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/fec/campaign-finance
---

# Query OpenFEC candidates and committees

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/fec/campaign-finance:search-candidates` — Search candidate registrations by name and optional office, geography, party, cycle, status, activity, and pagination filters.
- `us/fec/campaign-finance:search-committees` — Search committee registrations by name and optional type, designation, geography, party, cycle, filing frequency, treasurer, and pagination filters.
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

These operations return registration/entity data only. They do not return
receipts, individual contributors, disbursements, independent expenditures,
cash, debt, or financial totals. Open the linked FEC profile and use the
appropriate documented endpoint for those questions.

## Apply FEC usage restrictions

OpenFEC identifies itself as the source and says data are updated nightly. Its
current Terms of Service and Acceptable Use Policy govern reuse. The current
policy includes a broad commercial-use restriction; federal law separately
restricts sale or use of individual-contributor information for solicitation or
commercial purposes. This skill does not release contributor records, but users
must still assess their intended use against the current official terms.

Read [the API reference](references/api-reference.md) for endpoint parameters,
codes, pagination, and official policies. Read [the query guide](references/query-guide.md)
for candidate and committee resolution.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved FEC docs, OpenAPI, and policies.
- `references/query-guide.md` — identity resolution, filter, and reporting workflow.
- `scripts/verify.py` and `assets/verification-cases.json` — live candidate and committee checks.
- `evals/evals.json` — identifier, financial-scope, cycle, and reuse cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
