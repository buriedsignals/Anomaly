# 0005 — Six core detectors and execution

## Goal

Add the detector package contract, six generic M1 detectors, and a read-only execution engine that writes leads, not findings.

## Detectors

These are the M1 six. They are generic tabular detectors, not GAIN lobbying ports and not a user-authoring template.

1. `table.missingness_clusters`
2. `table.duplicate_rows`
3. `numeric.zscore_outliers`
4. `numeric.level_shift`
5. `categorical.rare_levels`
6. `temporal.coverage_gaps`

## Acceptance criteria

- Each detector is a package with `meta.yaml`, one `query.sql` (preferred) or trusted local `detector.py`, and fixtures.
- SQL is one parameterized read-only query. DDL, DML, ATTACH, COPY, extensions, and external readers are rejected.
- Execution opens DuckDB read-only with external access disabled and applies memory, time, thread, and output limits.
- Every output signal has `status: "lead"` and cannot emit a finding or a `confirmed`/`probable`/`supported` status.
- Full results land under `evidence/runs/` as Parquet plus a small JSON preview and `provenance.json`.
- Canonical leads append to `evidence/signals.jsonl`.
- `detectors/used/` stores inert snapshots (metadata, implementation hash, parameters, version). Code inside a shared case is never executed.
- Sensitive values are redacted before persistence.

## Non-goals

- User detector template and registry search (M2).
- GAIN lobbying detectors (M4).
- Recommendation and Gate A (0006).
- Replay, review, and report (0007).

## Audit

SQL sandbox, resource limits, redaction, and refusal to execute case-supplied code.
