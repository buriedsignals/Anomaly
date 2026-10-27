---
name: congress-press-releases
description: >-
  Use this skill to fetch US Congress members' press releases (full text,
  bioguide IDs) one month at a time from the Congress Press collection as
  press_releases rows of Anomaly's lobbying contract, filtered by member or
  text.
compatibility: Requires Python 3.11+ and network access to raw.githubusercontent.com.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/congress-press/press-releases
---

# Fetch member press releases as lobbying contract rows

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/congress-press/press-releases:press-releases` — Releases from one month, optionally filtered by member and text substring.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

```python
from pathlib import Path
from anomaly.sources.registry import discover_sources, load_source_adapter

entries = discover_sources(Path("data-skills"))
press = load_source_adapter(entries, "us/congress-press/press-releases")
result = press.run({"operation": "press-releases", "month": "2026-09",
                    "q": "private equity", "limit": 5000}, None)
```

Call once per month and concatenate the `records` into `press_releases.csv`
for `python -m anomaly.oneshot --tables press_releases=...`. Filters:
`bioguide_id` (exact) and `q` (case-insensitive substring of title or text).
`limit` defaults to 500; raise it to 5000 for a whole month.

## Source boundary

- Congress Press (Derek Willis, MIT licence) scrapes official House and
  Senate websites daily; 2001-2020 comes from the retired ProPublica Congress
  API. It is not comprehensive: gaps exist, some texts or dates are null, and
  duplicates are removed by URL only.
- An empty result does not show that a member said nothing on a topic.
- Quote releases from their official `url`, not from the collection.

Read [the API reference](references/api-reference.md) for file layout and
record format.

## Bundled resources

- `references/api-reference.md` — file layout, record format, caveats.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — interpretation cases.
