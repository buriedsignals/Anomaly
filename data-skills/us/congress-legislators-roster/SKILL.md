---
name: congress-legislators-roster
description: >-
  Use this skill to fetch the current US Congress roster and current
  committee and subcommittee assignments from the public-domain
  unitedstates/congress-legislators project as legislators and
  committee_assignments rows of Anomaly's lobbying contract, joined on
  bioguide_id.
compatibility: Requires Python 3.11+ and network access to unitedstates.github.io.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/congress-legislators/roster
---

# Fetch the current Congress roster and committee seats

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/congress-legislators/roster:legislators` — Currently serving members with party, state, and chamber from their latest term.
- `us/congress-legislators/roster:committee-assignments` — Current committee and subcommittee seats with role, rank, and majority or minority side.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

```python
from pathlib import Path
from anomaly.sources.registry import discover_sources, load_source_adapter

entries = discover_sources(Path("data-skills"))
roster = load_source_adapter(entries, "us/congress-legislators/roster")
members = roster.run({"operation": "legislators"}, None)
seats = roster.run({"operation": "committee-assignments"}, None)
```

Write the two `records` lists to `legislators.csv` and
`committee_assignments.csv` for `python -m anomaly.oneshot --tables ...`.
Optional filters: `bioguide_id`, `state` (legislators), and `committee`
(case-insensitive name substring, assignments).

## Source boundary

- Current members and current seats only; the files change as the project
  re-scrapes House and Senate pages.
- `committee_name` for a subcommittee is `"<committee>: <subcommittee>"`, so
  a search for the parent committee also matches its subcommittees.
- `role` is the committee title (Chairman, Ranking Member, ...) or `Member`.
- CC0 1.0 public domain.

Read [the API reference](references/api-reference.md) for files and fields.

## Bundled resources

- `references/api-reference.md` — files, fields, licence.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — interpretation cases.
