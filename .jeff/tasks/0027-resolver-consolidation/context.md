# Context

## Locked task and council lineage

- `.jeff/tasks/0027-resolver-consolidation/task.md:7` — AC1-AC9 and the no-runner non-goal.
- `.jeff/tasks/0027-resolver-consolidation/task.json:8` — current stage `plan`; line 9 locks category `code`.
- `.jeff/tasks/0027-resolver-consolidation/council-final.json:360` — cycle-2 synthesis; line 391 selects `causal-subgraph-reconstruction`.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-1.json` through `refute-final-11.json` — eleven surviving cycle-2 findings.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-1.json` and `refute-final-9.json` — P1 source-registry and P7 README promotion provenance cases.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-2.json` and `refute-final-7.json` — fork destination namespace containment.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-3.json` through `refute-final-5.json` — whitespace gates and attempt/promotion proof seams.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-8.json` — rollback-progress restart.
- `.jeff/tasks/0027-resolver-consolidation/refute-final-10.json` and `refute-final-11.json` — direct attempt/event pre-write containment.

## Relevant production and installed-content paths

- `src/anomaly/workflow.py:22` — sole P0-P7 owner registry and bounded phase write tuples.
- `src/anomaly/workflow.py:85` — per-phase required input names.
- `src/anomaly/workflow.py:94` — pure `resolve_workflow` decision.
- `src/anomaly/workflow.py:132` — installed dynamic owner loading.
- `src/anomaly/workflow.py:158` — public `run_workflow` dispatcher and recovery entry.
- `src/anomaly/workflow_inputs.py:25` — public input normalization.
- `src/anomaly/workflow_inputs.py:39` — capability derivation.
- `src/anomaly/workflow_inputs.py:83` — source request normalization.
- `src/anomaly/workflow_inputs.py:116` — gate mapping completeness predicate.
- `src/anomaly/attempts.py:29` — bounded `run_attempts` utility.
- `src/anomaly/attempts.py:43` — durable attempt counter and attempt loop.
- `src/anomaly/attempts.py:138` — failure cleanup/evidence path.
- `src/anomaly/attempts.py:164` — failure state/event recording.
- `src/anomaly/_attempt_workspace.py:25` — journalled workspace promotion.
- `src/anomaly/_attempt_workspace.py:57` — public-entry interrupted-promotion recovery.
- `src/anomaly/_attempt_workspace.py:82` — entry-by-entry promotion application.
- `src/anomaly/_attempt_workspace.py:109` — promotion rollback.
- `src/anomaly/_attempt_workspace.py:166` — persisted promotion journal parsing.
- `src/anomaly/owners.py:37` — one resolved-owner consumer.
- `src/anomaly/identities.py:8` — artifact identity-to-phase mapping.
- `src/anomaly/identities.py:22` — recorded/current identity comparison.
- `src/anomaly/identities.py:42` — identity capture through a sealed phase.
- `src/anomaly/identities.py:85` — identity artifact path mapping.
- `src/anomaly/state.py:12` — `MAX_ATTEMPTS = 3`.
- `src/anomaly/state.py:32` — snapshot identity invalidation and README projection entry.
- `src/anomaly/state.py:104` — atomic JSON persistence.
- `src/anomaly/state.py:122` — durable error sanitizer entry.
- `src/anomaly/case.py:102` — public `create_case` writer.
- `src/anomaly/case.py:139` — whole-tree-scanned `inspect_case` reader.
- `src/anomaly/case.py:147` — whole-tree-scanned `resume_case` reader.
- `src/anomaly/case.py:257` — unresolved-path ancestor and descendant scan.
- `src/anomaly/case.py:157` — public `fork_case` destination normalization and copy.
- `src/anomaly/readme.py:7` — marker-owned output links.
- `src/anomaly/readme.py:24` — README state projection.
- `src/anomaly/semantics.py:58` — shared assignment credential pattern.
- `src/anomaly/semantics.py:101` — shared recursive credential sanitizer.
- `src/anomaly/events.py:25` — standalone best-effort `log_event` writer.
- `skills/anomaly/SKILL.md:39` — current state/event/attempt authority text.
- `skills/anomaly/SKILL.md:46` — current durable-runner wording.
- `skills/anomaly/SKILL.md:207` — current abstract Verbs section.
- `skills/anomaly/SKILL.md:232` — current last-completed-event resume wording.
- `skills/anomaly/SKILL.md:247` — current `MAX_ATTEMPTS` owner wording.

## Plan-owned test seams

- `tests/test_pipeline_walk.py:191` — P1/P7 promotion write-set fixtures.
- `tests/test_pipeline_walk.py:398` — Gate A whitespace ID pauses before P4 attempts.
- `tests/test_pipeline_walk.py:425` — Gate B whitespace ID pauses before P7 attempts.
- `tests/test_pipeline_walk.py:625` — hard exit after durable count write reconciles missing failure evidence.
- `tests/test_pipeline_walk.py:674` — producer-ordered applied-prefix promotion rollback.
- `tests/test_pipeline_walk.py:722` — second interruption during rollback resumes on the next public restart.
- `tests/test_pipeline_walk.py:789` — false non-original P1/P7 provenance preserves live source registry/README.
- `tests/test_pipeline_walk.py:819` — direct `run_attempts` rejects a symlinked case before durable writes.
- `tests/test_case.py:429` — fork rejects a symlinked destination ancestor without external copy.
- `tests/test_events.py:304` — direct `log_event` rejects a symlinked event store without append.
- `tests/test_workflow.py:12` — pure ready/resume result and snapshot immutability.
- `tests/test_review.py:425` — inert standalone bare-URL serialization.
- `tests/fixtures/orchestration_demo.csv` — checked-in canonical workflow input.

## Commands

- Focused RED: `uv run --extra test pytest tests/test_pipeline_walk.py tests/test_case.py tests/test_events.py -q`.
- Focused RED result: `8 failed, 206 passed in 8.69s` (exit 1).
- Jeff project gate command after implementation: `uv run --extra test pytest tests/`.

## Mechanical constraints

- Python package root: `src/anomaly`; commands run from the repository root through `uv`.
- Public installed dispatcher: `anomaly.workflow.run_workflow`.
- Dynamic instruction paths: `skills/anomaly/SKILL.md` and `agents/anomaly-data-reviewer.md`.
- Case, attempt, and promotion paths persisted in JSON are relative paths.
- Maximum attempts per phase: 3.
- Human Gate A and Gate B pauses consume no phase attempt.
- `.anomaly/state.json` completion is authoritative; `.anomaly/events.jsonl` is observational.
- `WorkflowRunner`, `PhaseResult`, `RetryLimitExceeded`, `product_workflow.py`, handler composition, compatibility aliases, state-level `gate`, and `last_completed_phase` are absent from production.
- Plan-stage mutations are limited to tests, this task's `notes.md`, and this task's `context.md`.
- No full-suite command, production edit, installed-content edit, product-doc edit, commit, formatter, or linter runs in this plan stage.
- Repository mutation uses Jujutsu.
