# Context

- `tools/anomaly/data-skills/` — existing Anomaly source-package root.
- `tools/anomaly/data-skills/openparldata-parliamentary-data/` — already migrated OpenParlData skill, metadata, and adapter.
- `tools/anomaly/src/anomaly/acquire.py:27` — existing local source registration API and source-record hashing.
- `tools/navigator/osint-navigator/data/skills/` — verified Navigator source-package tree used for migration inventory.
- `tools/navigator/data-navigator/app/skills_registry.py` — verified Navigator registry implementation reference.
- `tools/anomaly/PRD.md:253` — acquisition route and Navigator source migration boundary.
- `tools/anomaly/.jeff/tasks/0016-navigator-source-catalogue-migration/task.md:13` — authoritative acceptance criteria.
- Targeted command: `uv run --extra test pytest -q tests/test_source_catalogue.py`.
- Baseline command: `uv run --extra test pytest -q`.
- Verified implementation: `data-skills/` contains 28 non-Arbiter source packages; `src/anomaly/sources/` contains the shared result contract and dynamic registry; no network, sleep, uncontrolled clock, or shared mutable test state was introduced.
