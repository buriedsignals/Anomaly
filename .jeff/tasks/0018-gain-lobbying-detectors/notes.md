# Task 18 notes

Capture started from the Buried Signals `gain-2026` repository. The source
contains D1–D12 definitions and committed anomaly CSV/provenance artifacts,
which provide a deterministic parity basis without live acquisition.

The 20 M2 core detectors remain separate; GAIN detectors are an additional
source family with source-bound provenance. User clarification locked the
registry direction: detector packages must be namespaced and grouped by data
type/category (a menu suitable for hundreds of future detectors), with GAIN
2026 Challenge attribution visible in package metadata/docs. GAIN is the first
source family, not a special execution path.

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

## Test-contract repair

The implementer kickback identified one focused-suite failure: substring
matching treated the legitimate byte-exact D3 fixture value `MCPC` as the
forbidden concept `mcp`. The scope assertion now matches escaped forbidden
terms on word boundaries, preserving the forbidden-scope behavior while
leaving production files, fixture bytes, and their hashes unchanged.

## Fresh repair plan evidence

The fresh plan adds only test contracts in `tests/test_gain_detectors.py`.
The implementation surface remains the single namespaced registry catalogue;
no second GAIN execution engine is specified.

Acceptance dispositions for this repair:

- AC1: revise — execute representative single-table and multi-table packages
  through a prepared case and Gate A, while checking category-aware bounded
  recommendation; the deterministic seam is registry execution and plan
  output.
- AC2: revise — require every declared parameter to have a bound SQL
  placeholder and require approved execution to produce normalized leads; the
  seam is DuckDB parameter binding and result status.
- AC3: revise — compare each local fixture's complete CSV rows and order with
  the matching source-checkout CSV, in addition to the stored hash; the seam
  is exact `csv.reader` equality.
- AC4: revise — require source/local/CSV/provenance hashes, parameters, signal
  identity, and run metadata in execution output; the seam is the normalized
  lead envelope.
- AC5: revise — retain Gate A approval setup and local-only forbidden-surface
  assertions; the seam is prepared-case approval and lexical scope scanning.
- AC6: revise — cover attribution, parameter semantics, duplicate-scope
  prevention, recommendation bounds, source parity, and complete lineage in
  deterministic focused tests.

Focused RED run:

`env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/test_gain_detectors.py`

Result: 7 failed, 18 passed. The failures are the intended missing contracts:
attribution/source URL, approved prepared-case execution, parameter binding,
multi-table duplicate execution, GAIN recommendation, and complete run
lineage.

Full-suite preservation run:

`env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/`

Result: 676 passed, 7 failed; all failures are the new GAIN RED tests.

## Recovery plan / test-author contract

Complexity: complex. Audit remains required because the repair changes registry
eligibility, SQL execution bounds, and replayable provenance.

Ordered slices:

1. Make package metadata authoritative: preserve declared group/category and
   stable ID ordering; move GAIN attribution and source repository into each
   package's metadata; keep family/menu filtering generic.
2. Make recommendation compatibility derive from declared required tables and
   fields, excluding multi-table detectors from sparse cases while retaining
   the global maximum of ten.
3. Enforce each package's declared memory bound (or narrow the documented
   execution contract before implementation if the runtime cannot enforce it).
4. Emit the PRD minimum top-level signal fields for real D1 leads and retain
   complete D3 table/source lineage in every lead.

Test changes are confined to `tests/test_gain_detectors.py`: package-level
attribution/source-field checks; metadata group preservation and ID ordering;
declared memory and over-bound rejection; PRD signal-envelope assertions;
complete D3 multi-table lineage; and sparse-case recommendation compatibility.
Existing fixture hash/order, parameter-placeholder, approval, local-only, and
duplicate-scope tests remain in place.

Targeted RED evidence:

`env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/test_gain_detectors.py`

Result: 8 failed, 22 passed. Failures are limited to the intended repair
contracts: package attribution fields, metadata-driven group/order behavior,
memory declaration/bound, PRD top-level signal fields, complete D3 lineage,
and sparse recommendation compatibility. No production files were changed.
