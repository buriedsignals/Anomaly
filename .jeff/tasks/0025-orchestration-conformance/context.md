# Context

## Relevant paths and symbols

- `src/anomaly/workflow.py:38` — `WorkflowRunner`, durable state/events/attempts runner.
- `src/anomaly/workflow.py:122` — `WorkflowRunner.load_state` reads `.anomaly/state.json`.
- `src/anomaly/workflow.py:156` — `WorkflowRunner.append_event` appends runner events.
- `src/anomaly/workflow.py:172` — `WorkflowRunner.invalidate` removes downstream completed phases.
- `src/anomaly/workflow.py:237` — `WorkflowRunner.run_phase` owns retry and completion bookkeeping.
- `src/anomaly/workflow.py:304` — `run_workflow`, installed top-level runner function.
- `src/anomaly/events.py:24` — `log_event`, best-effort API event append.
- `src/anomaly/events.py:51` — `phase_event`, API event decorator.
- `src/anomaly/case.py:134` — case creation initializes `.anomaly/state.json`.
- `src/anomaly/case.py:220` — case resume reads phase/status from `.anomaly/state.json`.
- `src/anomaly/acquire.py:28` — P1 registration API decorator.
- `src/anomaly/acquire.py:92` — source receipt persistence.
- `src/anomaly/recommend.py:334` — Gate A approval API.
- `src/anomaly/recommend.py:380` — Gate A reads and writes case state with its receipt.
- `src/anomaly/review.py:56` — P6 replay API.
- `src/anomaly/review.py:179` — P5 draft API.
- `src/anomaly/review.py:246` — P6 independent review API.
- `src/anomaly/review.py:369` — Gate B acceptance API.
- `src/anomaly/review.py:475` — Gate B receipt and state persistence.
- `PRD.md:218` — linear workflow; P5 draft precedes P6 replay/review.
- `skills/anomaly/SKILL.md:25` — installed operating contract.
- `skills/anomaly/SKILL.md:60` — installed dispatch table.
- `tests/test_pipeline_walk.py:30` — deterministic timestamp and checked-in demo fixture path.
- `tests/test_pipeline_walk.py:164` — complete demo and fresh-session resume contract.
- `tests/test_pipeline_walk.py:188` — event-store failure/resume contract.
- `tests/test_pipeline_walk.py:222` — three-attempt blocked-state contract.
- `tests/test_pipeline_walk.py:263` — artifact/receipt invalidation matrix contract.
- `tests/test_skill.py:139` — installed runner and canonical documented-call-order contract.
- `tests/test_events.py:155` — direct API event-order contract.
- `tests/fixtures/orchestration_demo.csv:1` — deterministic ten-row demo dataset.

## Targeted commands

- RED contract: `uv run pytest tests/test_pipeline_walk.py tests/test_skill.py tests/test_events.py -q`
- Focused demo: `uv run pytest tests/test_pipeline_walk.py -q`

## Mechanical constraints

- Python requirement: `>=3.11`; test runner: pytest via `uv`.
- Persist case references and attempt paths relative to the case root.
- Maximum attempts per phase is 3.
- Human Gate A and Gate B approvals remain explicit.
- Replay and independent review precede Gate B promotion.
- No production source edits belong to the plan stage.
- No detector, source-adapter, report-feature, case-format, shared-package, service, database, scheduler, event-framework, network, or `ORCHESTRATION-SPINE.md` runtime dependency changes are in scope.
- Task 20 ledger files are not in task 25's edit scope.
