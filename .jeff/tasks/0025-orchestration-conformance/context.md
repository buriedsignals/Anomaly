# Context

## Relevant paths and symbols

- `.jeff/tasks/0025-orchestration-conformance/task.md:7` — locked acceptance criteria and non-goals.
- `.jeff/tasks/0025-orchestration-conformance/council-terminal-return.json:169` — F1–F5 vote results and summaries.
- `.jeff/tasks/0025-orchestration-conformance/council-terminal-return.json:211` — terminal synthesis and selected recovery.
- `src/anomaly/workflow.py:51` — durable `WorkflowRunner`.
- `src/anomaly/workflow.py:138` — artifact-identity reconciliation on state load.
- `src/anomaly/workflow.py:262` — suffix invalidation, durable state write, and README demotion.
- `src/anomaly/workflow.py:367` — bounded phase execution and runner-owned P7 README projection.
- `src/anomaly/workflow.py:489` — state-derived README completion/demotion projector.
- `src/anomaly/workflow.py:526` — public `run_workflow` dispatcher.
- `src/anomaly/product_workflow.py:40` — installed product input/pause loop and pre-read case-tree scan.
- `src/anomaly/product_workflow.py:70` — prevalidated source-batch registration loop.
- `src/anomaly/product_workflow.py:159` — P7 acceptance, report, and chart sequence.
- `src/anomaly/product_workflow.py:184` — `.anomaly` containment check retained after the whole-tree scan.
- `src/anomaly/product_workflow.py:225` — supplied source-list validation.
- `src/anomaly/case.py:255` — whole case-tree no-symlink and regular-file scanner.
- `src/anomaly/review.py:594` — report Markdown serializer with inert dataset text.
- `tests/test_pipeline_walk.py:223` — isolated event-store durability test with one direct P1 handler.
- `tests/test_pipeline_walk.py:295` — duplicate canonical source-batch pre-write contract.
- `tests/test_pipeline_walk.py:435` — completed-case Gate B invalidation and README demotion contract.
- `tests/test_pipeline_walk.py:469` — completed-case P7 retry failure and README demotion contract.
- `tests/test_pipeline_walk.py:499` — nested case-tree symlink pre-write contract.
- `tests/test_pipeline_walk.py:545` — invalidation matrix using the public completed-demo baseline.
- `tests/test_review.py:393` — direct report-body write without case completion contract.
- `tests/test_review.py:425` — dataset-text Markdown inertness contract.
- `tests/fixtures/orchestration_demo.csv:1` — deterministic checked-in input.

## Targeted commands

- RED: `uv run --extra test pytest tests/test_pipeline_walk.py::test_public_dispatcher_invalidates_changed_gate_b_from_p7 tests/test_pipeline_walk.py::test_readme_does_not_claim_completion_when_chart_generation_fails tests/test_pipeline_walk.py::test_public_dispatcher_rejects_duplicate_source_batch_before_registration tests/test_pipeline_walk.py::test_public_dispatcher_rejects_nested_case_symlink_before_durable_write tests/test_review.py::test_write_report_preserves_accepted_work_without_completing_case tests/test_review.py::test_write_report_serializes_dataset_text_as_inert_markdown -q`
- RED result: `6 failed in 0.52s`; each named test failed on its intended F1–F5 behavior.
- Preservation: `uv run --extra test pytest tests/test_pipeline_walk.py::test_successful_mutation_remains_resumable_when_event_store_is_unavailable tests/test_pipeline_walk.py::test_fresh_session_invalidates_changed_authoritative_inputs_from_earliest_phase -q`
- Preservation result: `10 passed in 1.62s`.
- Post-handoff result after implementation began: the same six-test command returned `6 passed in 0.45s`.

## Mechanical constraints

- Python requirement: `>=3.11`; test runner: pytest via `uv`.
- Public proof inputs use explicit timezone-aware `datetime` values and per-test `tmp_path` roots.
- Maximum failed attempts per phase is 3.
- P7 durable completion follows accepted findings, report body, chart files, and chart receipt.
- `canonical_key` is the existing source-identity normalizer.
- `_scan_case_tree` already rejects symlinks, special files, and executable files throughout a case tree.
- Plan-stage edits are limited to tests and task notes/context.
- Production, PRD, installed skill, detector modules, case format, and demo fixture are unchanged in this stage.
- No service, database, queue, scheduler, framework, network dependency, new phase, source adapter, or report feature is in scope.
- Task 20 ledger files are outside task 25's edit scope.
