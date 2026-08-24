# Verify Anomaly public demo in the installed agent pipeline

## Goal

After task 25 is green, verify the installed Anomaly skill through a real supported agent harness using the checked-in demo CSV, actual Gate A/Gate B turns, and a fresh independent data-reviewer context. Use an isolated case root and retain concise public-readiness evidence.

## Acceptance criteria

- Install/register the current candidate in an isolated temporary user environment and verify the Anomaly dispatcher and reviewer manifest are available to the supported harness.
- Invoke the installed skill and complete create → source registration → preparation/profile → recommendation → Gate A approval → detector execution → draft/replay → independent reviewer → Gate B approval → report/charts.
- Gate A and Gate B end their turns and cannot be closed by the orchestrator, reviewer, or silence.
- Restart the harness once after detector execution or draft creation; the fresh session resumes from the authoritative durable state without repeating accepted work.
- The reviewer runs in a distinct fresh context and returns a draft-hash attestation before Gate B.
- Record relative paths to the portable case, state/attempt evidence, gate receipts, report, and charts. Confirm no absolute case path or credential enters the artifacts.
- Full repository suite is green for the exact candidate; cleanup removes only isolated installation state and leaves the portable case usable.

## Non-goals

- No live acquisition adapter, network access, publication, new detector, new report feature, new automated harness, or production code change.
- No claim that the demo CSV certifies statistical fitness for every investigation; it certifies orchestration, deterministic execution, reviewer separation, gates, resume, and portable output.

## Approval and audit

No irreversible shared mutation is planned. The operation plan must stop for approval if it cannot remain inside isolated installation/case roots. Audit is required because installation, detector execution, path custody, and cleanup boundaries are exercised.
