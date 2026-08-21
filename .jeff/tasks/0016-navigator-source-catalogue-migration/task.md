# M3 Navigator source catalogue migration

## Goal

Migrate the 28 non-Arbiter Navigator source packages into Anomaly's dynamic
source catalogue. ThinkPol Reddit Evidence is included as a normal catalogue
entry. Anomaly must not model hosted keys, hosted runtime, membership, metering,
the Navigator service, the Navigator CLI, or MCP as part of this migration.

The catalogue consists of source skill files and a registry that discovers and
loads a source adapter dynamically when the user requests that source.

## Acceptance criteria

- The source inventory is explicit: 29 Navigator packages are accounted for;
  only `global/arbiter/case-studies` is excluded; the existing
  `ch/openparldata/parliamentary-data` package is recognized as already
  migrated.
- Anomaly defines and tests one source-adapter contract covering metadata,
  licence, endpoint/operation, validation, normalized output, source hash,
  provenance, and unavailable/error state.
- Registry discovery is deterministic, rejects malformed or unsafe packages,
  and loads adapters on demand by source id without hardcoded per-source app
  wiring.
- ThinkPol is represented by its skill and adapter metadata under the same
  catalogue contract as every other source; no hosted-key or membership
  concept is introduced.
- RED tests cover registry discovery and one-to-one adapter migration before
  production implementation.
- The migration preserves the no-CLI, no-service, no-membership, no-MCP rule.
- PRD and backlog language describe the revised catalogue-only model.

## Non-goals

- Expanding the detector registry (M2).
- Porting GAIN lobbying detectors (M4).
- Recreating Navigator's web UI, CLI, hosted execution, membership, metering,
  MCP, or deployment surfaces.
- Migrating `global/arbiter/case-studies`.

## Audit

Audit is required if adapter loading, source content, or registry discovery
introduces dynamic execution, path traversal, command execution, or network
request policy changes.
