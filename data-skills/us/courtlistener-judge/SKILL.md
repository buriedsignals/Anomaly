---
name: courtlistener-judge
description: >-
  Use this skill to search CourtListener's judicial-person index or retrieve an
  exact person ID with biography, education, political-affiliation, ABA-rating,
  and position-link data. Preserve alias and date-granularity fields, and treat
  race and gender as provider-inferred, potentially incorrect attributes rather
  than self-reported facts.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to www.courtlistener.com; a CourtListener token is optional but recommended for deployed clients.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/courtlistener/judge
---

# Query CourtListener judicial people

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/courtlistener/judge:search-judges` — Use free-text type=p search or database first/last-name filters and return a bounded set of judicial-person records.
- `us/courtlistener/judge:get-judge` — Retrieve the database record for an exact CourtListener person ID, including nested education and affiliation summaries plus position URLs.
<!-- END GENERATED OPERATION STATUS -->
## Search, resolve, retrieve

Use free text for discovery, exact name components for database filtering, and
`get-judge` only after resolving a provider ID:

```bash
catalogue query us/courtlistener/judge --operation search-judges \
  --input '{"q":"Ruth Bader Ginsburg","limit":5}'
catalogue query us/courtlistener/judge --operation get-judge \
  --input '{"person_id":2738}'
```

Free-text and database-filter results have different upstream shapes; the
adapter normalizes their shared meaning but preserves links and granularity.

## Identity and demographic discipline

- Check `is_alias_of` before treating a record as a distinct person.
- Preserve `date_dob_granularity` and `date_dod_granularity`. A placeholder
  January 1 date can mean only the year is known.
- CourtListener explicitly says race and gender are not self-reported and can
  be wrong. Do not present them as verified identity facts.
- `position_urls` are links, not full position records; follow and corroborate
  them before reporting tenure, appointment, or employer claims.
- Resolve names with independent sources when identity matters.

Read [the API reference](references/api-reference.md) for people/search behavior,
fields, aliases, date granularity, and authentication. Read
[the query guide](references/query-guide.md) for identity resolution and reporting.

## Bundled resources

- `references/api-reference.md` — Firecrawl-preserved official judge and REST documentation plus OPTIONS evidence.
- `references/query-guide.md` — search modes, alias review, granularity, and corroboration.
- `scripts/verify.py` and `assets/verification-cases.json` — live search and exact-person checks.
- `evals/evals.json` — demographic, alias, date, and linked-position cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
