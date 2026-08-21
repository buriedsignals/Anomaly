# M2 detector registry, core detectors, and user template

## Goal

Build Anomaly's local detector catalogue so a journalist can discover bounded,
metadata-driven detectors, run the approved subset against prepared case data,
and add a SQL detector using one documented package template.

## Capture scope to lock

- Define the detector metadata and execution contract from the PRD.
- Provide a local registry with deterministic discovery, validation, and bounded
  recommendation/execution behavior.
- Port 20–30 useful core detectors with fixtures and provenance.
- Provide one user detector package template and validation path.

## Acceptance criteria

1. A detector package has stable metadata covering identity/version, group,
   description, required inputs, parameters, signal severity, expected output,
   assumptions, false positives, sensitive-output handling, and resource limits.
2. The local registry discovers and validates built-in and user-template detector
   packages deterministically, with malformed, duplicate, unsafe, and out-of-
   scope packages rejected before execution.
3. The registry recommends and runs no more than 10 compatible detectors per
   pass, with explicit user approval before execution and provenance-bearing
   outputs stored as lead signals.
4. Exactly 20 core detectors are implemented with fixtures, deterministic
   outputs, and documented input requirements: the six existing M1 detectors
   plus 14 new detectors.
5. A journalist can create a SQL detector from the documented template, validate
   it, and have it recommended alongside built-ins when compatible.
6. Detector execution uses read-only, bounded case-data access and preserves
   hashes, parameters, detector identity, and source provenance in outputs.
7. Tests cover registry discovery/validation, recommendation bounds, template
   onboarding, representative detector behavior, provenance, and forbidden
   hosted/service/CLI scope.

## Non-goals

- Navigator source migration; that is complete in task 16.
- Hosted keys, hosted runtime, membership, metering, deployment, web UI, MCP,
  or a Navigator CLI/service.
- Porting the GAIN lobbying corpus; that is M4.
- Scaling to hundreds or journalist handoff; that is M5.

## Audit

Expected because detector discovery, SQL execution, filesystem boundaries,
case-data access, and sensitive-output handling are security-relevant.
