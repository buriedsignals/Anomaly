# M5 scale registry and journalist handoff

## Goal

Scale Anomaly's detector catalogue for hundreds of detectors and make a
portable case folder inspectable, forkable, replayable, and reviewable by a
second journalist.

## Acceptance criteria

1. Registry discovery and search remain bounded and deterministic as the
   catalogue grows; metadata/category filtering loads only relevant detector
   records and recommendations/runs remain capped at 10 per pass.
2. The documented detector template and registry validation support future
   user-origin detectors without family-specific branches, while preserving
   origin, version, implementation hash, provenance, and the existing signal
   contract.
3. A portable case handoff has only the approved root files and purpose-based
   directories from PRD §3, uses relative references, records missing or
   omitted data in sources.json, and rejects traversal, links, and executable
   detector code on import/validation.
4. A second journalist can inspect README, AGENTS, methodology, context,
   data-dictionary, handling, source records, detector history, evidence,
   findings, unresolved work, and runtime logs without hidden absolute paths.
5. Forking creates a new case_id with parent case/hash provenance, leaves the
   parent unchanged, resets to a selected phase, and marks replay unavailable
   rather than approximating when required data or matching detector code is
   absent.
6. Re-exploration changes to data, methodology, semantic mappings, detector
   versions, or parameters require new detector runs, review, and Gate B
   approval; cases do not merge automatically.
7. Tests cover bounded search/recommendation, user detector handoff, portable
   path/hash validation, fork isolation, replay-unavailable behavior, and
   review/approval gates. No hosted runtime, service, UI, deployment, MCP,
   membership, or metering surfaces are introduced.

## Non-goals

- Hosted case storage, collaboration service, web UI, deployment, MCP, or
  external sharing automation.
- Network acquisition, publication, contacting subjects, or newsroom workflow
  beyond local portable artifacts.
- Replacing the existing local detector execution or source catalogue with a
  second registry implementation.

## Audit

Required because this milestone changes registry trust boundaries, portable
case import/fork behavior, hashes, and journalist-facing handoff artifacts.
