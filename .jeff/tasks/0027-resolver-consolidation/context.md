# Context

## Relevant paths and symbols

- `src/anomaly/workflow.py:21` — compact fixed P0-P7 owner registry.
- `src/anomaly/workflow.py:37` — pure `resolve_workflow` selects phase/status/owner/missing/attempt/resume detail.
- `src/anomaly/workflow.py:75` — `invoke_resolved_owner` loads only fixed installed skill/persona paths.
- `src/anomaly/workflow.py:101` — `run_workflow` is the sole public resolve/consume/seal/re-resolve dispatcher.
- `src/anomaly/owners.py:37` — consumes exactly one resolved deterministic or dynamic owner.
- `src/anomaly/owners.py:110` — deterministic replay precedes dynamic independent review and sealing.
- `src/anomaly/attempts.py:21` — bounded attempt staging, retry evidence and successful sealing.
- `src/anomaly/state.py:34` — canonical snapshot loading and earliest identity invalidation.
- `src/anomaly/state.py:93` — atomic state writes normalize obsolete `last_completed_phase` and state-level `gate` projections away.
- `src/anomaly/identities.py:22` — authoritative artifact identity comparison and capture.
- `src/anomaly/readme.py:24` — bounded generated Outputs projection preserves unrelated README content.
- `src/anomaly/product_workflow.py` — deleted; no competing product loop or handler map remains.
- `src/anomaly/review.py:655` — dataset Markdown escaping also neutralizes bare HTTP(S) autolinks.
- `skills/anomaly/SKILL.md:67` — installed dispatch table and P0-P7 ownership documentation.
- `skills/anomaly/SKILL.md:206` — runtime verb and `invoke-skill` documentation.
- `agents/anomaly-data-reviewer.md:1` — installed independent reviewer persona.
- `tests/test_workflow.py:12` — focused pure resolver RED contract.
- `tests/test_workflow.py:53` — focused dynamic skill/persona loading and invocation RED contract.
- `tests/test_pipeline_walk.py:185` — checked-in CSV public dynamic-owner completion/resume test with positive README/link assertions.
- `tests/test_pipeline_walk.py:438` — completed Gate-B invalidation test with trailing journalist README content.
- `tests/test_review.py:425` — dataset-derived Markdown inertness test including a bare HTTPS URL.
- `tests/fixtures/orchestration_demo.csv` — checked-in demo input.

## Commands

- Targeted RED: `uv run --extra test pytest tests/test_workflow.py::test_resolver_is_pure_and_reports_durable_resume_detail tests/test_workflow.py::test_resolved_reasoning_owner_is_loaded_and_invoked_once tests/test_pipeline_walk.py::test_checked_in_demo_runs_canonical_path_and_resumes_without_repeating_work tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`
- Targeted GREEN: the same command passed `6 passed in 0.39s`.
- Project gate configured by Jeff: `uv run --extra test pytest tests/`

## Mechanical constraints

- Python package root: `src/anomaly`; tests run through `uv` from the repository root.
- Public installed entry: `anomaly.workflow.run_workflow`.
- Installed dynamic instruction paths are repository-owned `skills/anomaly/SKILL.md` and `agents/anomaly-data-reviewer.md`.
- Case paths and persisted attempt paths are relative; the public dispatcher scans the whole case tree before resume/read/write.
- Human Gate A and Gate B pauses consume no failure attempt.
- Maximum attempts per executed phase: 3.
- Event logging is best-effort; state/artifact promotion is durable.
- Implement-stage changes are confined to production modules, PRD/installed-skill wording, and this directly verified context map; plan-authored tests remain untouched by the implementer.
