# M4 port GAIN lobbying detectors

## Goal

Port the useful GAIN `data-detective` lobbying detector battery into Anomaly's
local detector catalogue while preserving signal behavior and provenance.

## Captured source

- Repository: `https://github.com/buriedsignals/gain-2026`
- Source package: `data-detective/skills/detect`
- Detector definitions: D1 through D12 in `scripts/query.py` and
  `references/detectors.md`
- Parity artifacts: `case-trace/data-detective/anomalies/D*.csv` and matching
  `.provenance.json` files

## Acceptance criteria

1. D1–D12 are represented as local Anomaly detector packages with stable IDs,
   metadata, SQL, hashes, and provenance distinct from the 20 M2 core detectors.
2. The port preserves the source detector semantics, parameters, output fields,
   and deterministic ordering; source SQL hashes and Anomaly hashes are both
   recorded for traceability.
3. Fixtures reproduce the stored GAIN anomaly result sets for every detector,
   including row identity and ordering where the source artifact defines them.
4. Detector outputs use Anomaly's normalized lead/provenance contract and retain
   source detector ID, version, SQL hash, input/source hashes, and run metadata.
5. Ported detectors execute through the local registry's bounded, read-only,
   approval-gated path without hosted keys, hosted runtime, service, CLI, web UI,
   deployment, membership, metering, or MCP concepts.
6. Tests cover all 12 detectors, parity fixtures, hash/provenance translation,
   parameter validation, recommendation bounds, and forbidden-surface scope.

## Non-goals

- Re-running the external GAIN acquisition pipeline or downloading live public
  data during Anomaly tests.
- Porting GAIN's orchestration, agent personas, report UI, or external-data
  integrations.
- M5 registry scaling and journalist handoff.

## Audit

Required because this task ports SQL/data-processing code and provenance-bearing
outputs across a repository boundary.
