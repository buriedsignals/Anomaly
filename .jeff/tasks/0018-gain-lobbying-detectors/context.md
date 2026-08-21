# Task 18 context

- `src/anomaly/detectors/registry.py`: local detector discovery, recommendation,
  approval gate, bounded DuckDB execution, and normalized leads.
- `tests/test_detector_registry.py`: M2 registry contract and case execution
  tests.
- `tests/test_gain_detectors.py`: task 18 RED contract for the separate GAIN
  detector family.
- `/private/tmp/gain-2026-work/data-detective/skills/detect/scripts/query.py`:
  source D1-D12 SQL catalog and parameter defaults.
- `/private/tmp/gain-2026-work/data-detective/skills/detect/references/detectors.md`:
  source detector descriptions and parameter documentation.
- `/private/tmp/gain-2026-work/case-trace/data-detective/anomalies/D*.csv`:
  committed source result fixtures.
- `/private/tmp/gain-2026-work/case-trace/data-detective/anomalies/D*.provenance.json`:
  source SQL hashes, schemas, row counts, and run metadata.
- Focused command: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/test_gain_detectors.py`.
- Constraints: plan stage may edit tests and task notes/context only; no live
  acquisition, hosted keys/runtime, orchestration, service, UI, deployment,
  membership, metering, CLI, or MCP concepts.
