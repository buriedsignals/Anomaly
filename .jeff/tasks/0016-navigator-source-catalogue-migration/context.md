# Context

- `tools/anomaly/data-skills/` — Anomaly catalogue root; contains 28 `meta.yaml` files.
- `tools/anomaly/data-skills/global/opensanctions/` — catalogue package with source id `global/opensanctions`.
- `tools/anomaly/data-skills/global/thinkpol-reddit-evidence/` — catalogue package with source id `global/thinkpol/reddit-evidence`.
- `tools/navigator/osint-navigator/data/skills/` — Navigator inventory root; contains 30 `meta.yaml` files, including one `_template` example and 29 source package metadata files including Arbiter.
- `tools/navigator/osint-navigator/data/skills/global/arbiter-case-studies/meta.yaml:1` — excluded source id `global/arbiter/case-studies`.
- `tools/anomaly/src/anomaly/sources/contract.py:12` — `validate_source_result` entry point and result fields/states.
- `tools/anomaly/src/anomaly/sources/registry.py:64` — `discover_sources` entry point; `registry.py:75` — request-time adapter loading with typed dependency-unavailable fallback.
- `tools/anomaly/tests/test_source_catalogue.py` — targeted inventory, contract, forbidden-surface, loading, and registry-safety tests.
- `tools/anomaly/PRD.md:253` — acquisition route and catalogue migration wording; `PRD.md:547` — M3 backlog row.
- `tools/anomaly/.jeff/tasks/0016-navigator-source-catalogue-migration/task.md:13` — acceptance criteria.
- Targeted command: `uv run --extra test pytest -q tests/test_source_catalogue.py`.
- Baseline command: `uv run --extra test pytest -q`.
- Verified implementation facts: the targeted source-catalogue suite passes with `9 passed`; discovery sorts by source id, rejects any symlink below the catalogue root, rejects duplicate ids, and permits two-or-more-segment source ids. Adapter loading temporarily disables bytecode writes and returns an unavailable result when the optional HTTP client is absent.
- Verified catalogue facts: source surfaces no longer contain the locked hosted/runtime, Navigator-command, MCP, web-UI, deployment, or metering phrases; PRD M3 and backlog language state the revised 28-package local catalogue scope.
