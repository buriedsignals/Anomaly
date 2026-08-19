# 0002 — Portable P0 case folder

## Goal

Create or resume an Anomaly case folder whose root is only `AGENTS.md`, `README.md`, and `case.json`, with the six purpose-based parent directories from `PRD.md` §3.

## Acceptance criteria

- Creating a new case writes the tree in `PRD.md` §3.
- `AGENTS.md` is generated from a fixed Anomaly template. Source text and arbitrary case content are never interpolated into it.
- `README.md` states the question, status, last completed phase, included/missing data, where to find methodology/evidence/findings/unresolved work, whether replay is possible, and how to fork.
- `case.json` stores `case_id`, `title`, timestamps, `status`, `workflow_version`, and `derived_from`. It never stores an absolute path.
- Existing folders offer resume or fork. Progress is read from `.anomaly/state.json` and `.anomaly/events.jsonl`, never inferred only from report files.
- `.anomaly/` holds `state.json`, `events.jsonl`, `receipts/`, and `attempts/`.
- Copying the case to another directory does not require path edits.

## Non-goals

- Registering or acquiring data.
- Detector execution, review, or report generation beyond the README stub.
- Full fork-and-rerun semantics beyond creating a new `case_id` and `derived_from` pointer.

## Audit

Path handling and template generation. Reject traversal and absolute-path persistence.
