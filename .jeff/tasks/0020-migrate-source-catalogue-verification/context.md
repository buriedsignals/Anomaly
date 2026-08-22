# Context

## Paths and roles

- `tests/test_source_catalogue.py:16-37` — Anomaly/data-skills and sibling Navigator source-root constants plus text-resource path enumeration.
- `tests/test_source_catalogue.py:119-136` — Navigator inventory and Anomaly migration parity checks.
- `tests/test_source_catalogue.py:139-163` — Offline adapter loading and shared result-envelope validation.
- `tests/test_source_catalogue.py:166-198` — Forbidden hosted/Navigator surface scan and ThinkPol-specific scan.
- `src/anomaly/sources/registry.py:18-224` — SourceEntry discovery, request-time adapter loading, and result-envelope wrapping.
- `src/anomaly/sources/contract.py:12-53` — Shared source-result validation.
- `data-skills/` — 28 Anomaly source packages.
- `../navigator/data/skills/` — Current Navigator source catalogue with 29 package metadata entries, including `global/arbiter/case-studies`.

## Commands

- Targeted test: `uv run pytest tests/test_source_catalogue.py -q`
- Project test configuration: `pyproject.toml`

## Mechanical constraints

- Test-only changes for this task; do not edit Anomaly production code or mutate Navigator.
- Offline adapter fixtures replace `httpx` and reject requests.
- Do not run formatters, linters, or project-wide test suites.
