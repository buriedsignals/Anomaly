# 0006 — Detector recommendation and Gate A

## Goal

Recommend no more than 10 compatible detectors from the local registry and record the journalist-approved plan.

## Acceptance criteria

- Incompatible detectors are removed using required tables, fields, types, and coverage from `meta.yaml` plus the case profile.
- Remaining detectors are scored for relevance, data fit, expected utility, cost, and known false-positive risk.
- Selection diversifies across detector groups instead of returning near-duplicates.
- At most 10 detectors are recommended or runnable in one pass.
- `detectors/plan.json` records the recommended set, the approved subset, parameters, selection reasons, and blocked detectors.
- Detectors do not run until Gate A records journalist approval.

## Non-goals

- Implementing new detectors.
- User-authored detector packaging (M2).
- Drafting claims from signals.

## Audit

Recommendation must not execute untrusted SQL or write findings.
