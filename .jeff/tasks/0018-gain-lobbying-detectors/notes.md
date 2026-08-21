# Task 18 notes

Capture started from the Buried Signals `gain-2026` repository. The source
contains D1–D12 definitions and committed anomaly CSV/provenance artifacts,
which provide a deterministic parity basis without live acquisition.

The 20 M2 core detectors remain separate; GAIN detectors are an additional
source family with source-bound provenance.

## Capture plan

The RED contract is in `tests/test_gain_detectors.py`. It treats the twelve
detectors as a separate `gain.*` family, pins the committed source SQL hashes,
schemas, row counts, CSV hashes, and D1-D12 ordering, and requires local
implementation/provenance hashes to remain distinct from the source hash.

Acceptance dispositions:

- AC1: write — catalogue discovery must expose exactly twelve `gain.*`
  packages with source detector IDs and metadata distinct from M2.
- AC2: write — metadata and tests pin source SQL hashes, output columns,
  parameters, and deterministic ordering.
- AC3: write — package fixtures must reproduce each committed source CSV.
- AC4: write — normalized leads must retain source family, detector ID, SQL
  hash, source hash, local detector hash, table ID, and run metadata.
- AC5: write — execution must use the existing local approval, read-only,
  bounded path and reject unapproved execution.
- AC6: write — focused tests cover all twelve fixtures, hashes, provenance,
  approval bounds, and forbidden hosted/orchestration scope.

Refactor opportunity: harmonize the GAIN family with the existing registry's
single catalogue and normalized result envelope; do not create a second
execution engine.
