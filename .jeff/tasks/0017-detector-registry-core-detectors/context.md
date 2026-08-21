# Task 17 context

- `PRD.md:341-410` — detector groups, package template, metadata, and local
  onboarding rules.
- `src/anomaly/detect.py:15-22` — six existing built-in detector IDs.
- `src/anomaly/detect.py:198-247` — built-in metadata loading and ordering.
- `src/anomaly/detect.py:249-305` — read-only SQL validation.
- `src/anomaly/detect.py:514-704` — bounded detector execution and provenance.
- `src/anomaly/recommend.py:190-260` — deterministic recommendation bound and
  compatibility selection.
- `tests/test_detect.py` — existing SQL sandbox, limits, lead, and provenance
  behavior tests.
- `tests/test_recommend.py` — existing recommendation and Gate A approval tests.
- Focused command: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run
  --extra test pytest -q tests/test_detector_registry.py`.
- Constraint: plan stage may edit tests and task notes/context only; production
  source remains untouched.
