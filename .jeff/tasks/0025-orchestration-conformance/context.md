# Context

## Relevant paths and symbols

- `.jeff/tasks/0025-orchestration-conformance/task.md:7` — locked acceptance criteria and non-goals.
- `.jeff/tasks/0025-orchestration-conformance/council-return.json:218` — F1–F8 blocker list; selected recovery is recorded at line 312.
- `.jeff/tasks/0025-orchestration-conformance/refute-r-p3retry.json:5` — P3 recommendation retry evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r-staleplan.json:5` — stale plan evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r-identity.json:5` — cross-gate test evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r2-runner.json:5` — missing/non-callable handler evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r2-source-recovery.json:5` — changed-source recovery evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r2-gatebmap.json:5` — Gate B phase-map evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-r2-readme.json:5` — README/chart ordering evidence.
- `.jeff/tasks/0025-orchestration-conformance/refute-audit-symlink.json:5` — `.anomaly` containment evidence.
- `src/anomaly/workflow.py:14` — canonical P0–P7 tuple.
- `src/anomaly/workflow.py:17` — artifact-identity phase map, including P3
  recommendation, P4 Gate A, and P7 Gate B ownership.
- `src/anomaly/workflow.py:51` — durable `WorkflowRunner`.
- `src/anomaly/workflow.py:118` — durable-tree creation.
- `src/anomaly/workflow.py:138` — identity reconciliation on state load.
- `src/anomaly/workflow.py:261` — suffix state invalidation.
- `src/anomaly/workflow.py:333` — linear runner execution with exact callable
  composition validation.
- `src/anomaly/workflow.py:486` — preserved public `run_workflow` dispatcher.
- `src/anomaly/product_workflow.py:41` — installed product input/pause loop.
- `src/anomaly/product_workflow.py:167` — exact production P0–P7 handlers.
- `src/anomaly/product_workflow.py:154` — P7 findings, report, charts, then README
  completion.
- `src/anomaly/product_workflow.py:180` — pre-run `.anomaly` containment check.
- `src/anomaly/acquire.py:31` — local registration and validated same-canonical-ID
  replacement.
- `src/anomaly/recommend.py:256` — recommendation API.
- `src/anomaly/recommend.py:334` — Gate A approval API.
- `src/anomaly/review.py:369` — Gate B acceptance API.
- `src/anomaly/review.py:594` — report body writer.
- `src/anomaly/review.py:663` — README completion projection.
- `src/anomaly/report.py:53` — chart generator.
- `src/anomaly/report.py:79` — chart directory and file writes.
- `src/anomaly/case.py:255` — case-tree symlink scan.
- `PRD.md:229` — canonical phase/gate order.
- `skills/anomaly/SKILL.md:69` — installed dispatcher description.
- `tests/test_pipeline_walk.py:150` — public Gate A pause helper.
- `tests/test_pipeline_walk.py:249` — identity mutation/phase matrix.
- `tests/test_pipeline_walk.py:280` — checked-in public demo and resume contract.
- `tests/test_pipeline_walk.py:335` — installed P1 three-attempt contract.
- `tests/test_pipeline_walk.py:363` — public P3 recommendation retry contract.
- `tests/test_pipeline_walk.py:390` — public stale-plan regeneration contract.
- `tests/test_pipeline_walk.py:412` — public source-replacement contract.
- `tests/test_pipeline_walk.py:434` — Gate A approver/reviewer rejection contract.
- `tests/test_pipeline_walk.py:450` — reviewer/Gate B journalist rejection contract.
- `tests/test_pipeline_walk.py:472` — public Gate B P7 invalidation contract.
- `tests/test_pipeline_walk.py:503` — README/chart failure contract.
- `tests/test_pipeline_walk.py:529` — pre-write `.anomaly` containment contract.
- `tests/test_pipeline_walk.py:551` — injected-handler suffix invalidation matrix.
- `tests/test_workflow.py:95` — fail-closed composition parameter set.
- `tests/fixtures/orchestration_demo.csv:1` — deterministic ten-row demo input.

## Targeted commands

- Causal RED: `uv run pytest tests/test_pipeline_walk.py tests/test_workflow.py -q`
- Causal RED result: `11 failed, 18 passed in 2.65s`; exit 1.
- Focused public path: `uv run pytest tests/test_pipeline_walk.py -q`
- Focused durable runner: `uv run pytest tests/test_workflow.py -q`
- Full suite: `uv run --extra test pytest tests/`

## Mechanical constraints

- Python requirement: `>=3.11`; test runner: pytest via `uv`.
- Public proof input keys are `now`, `sources`, `gate_a`, `review`, and `gate_b`; timestamps are explicit timezone-aware `datetime` values.
- P3 recommendation completes before the Gate A pause; Gate A is consumed by P4.
- P6 replay/review completes before the Gate B pause; Gate B is consumed by P7.
- Maximum failed attempts per phase is 3.
- Persisted case references and attempt paths are relative to the case root.
- Gate A and Gate B identities are caller inputs.
- Independent review input includes reviewer ID, verdicts, and draft-hash attestation.
- Each test uses its own pytest `tmp_path`; the checked-in CSV is read-only.
- Plan-stage edits are limited to tests and task notes/context.
- Production source, PRD, installed skill, detector modules, case format, and demo fixture are unchanged in this stage.
- No service, database, queue, scheduler, framework, network dependency, new phase, detector behavior, source adapter, report feature, or `ORCHESTRATION-SPINE.md` runtime dependency is in scope.
- Task 20 ledger files are outside task 25's edit scope.
