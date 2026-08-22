# M5 capture notes

- Milestone: M5 from PRD §9.
- Predecessor: task 18 / M4 is terminal and pruned in `.jeff/config.json`.
- Scope is local-only registry scaling and portable journalist handoff.
- Explicit exclusions: hosted runtime/service, web UI, deployment, MCP,
  membership, metering, network acquisition, and publication.
- Capture must produce the task graph and RED-first plan before production
  implementation.

## Capture / RED-first test-author context

- Bundled `cook-plan.md` was not present at the requested cache path; the
  available Jeff `cook/SKILL.md` and its references were used, together with
  bundled `code-standards` and `testing` guidance.
- Existing coverage already proves the basic ten-detector cap, deterministic
  ordering, SQL-only user package validation, relative source paths, several
  symlink/source-hash fork guards, and legacy Gate B promotion behavior.
- New RED contracts are in `tests/test_m5_handoff.py`. They intentionally
  describe the missing public behavior: metadata-filtered bounded registry
  search, user origin/version/implementation hash/signal contract, parent
  case-content-hash provenance with selected-phase fork reset, executable
  artifact rejection, explicit replay-unavailable results, and invalidation
  of Gate B after methodology changes.
- Production files and task state are untouched. The implementation plan must
  keep all case references relative, validate at import/fork boundaries, use
  one registry, preserve the ten-detector cap, and add no hosted/UI/MCP or
  service surface.
- RED evidence: `./.venv/bin/pytest -q tests/test_m5_handoff.py` exits 1 with
  6 failing tests. Failures are the intended missing contracts, not fixture or
  collection errors: filtered search API, user metadata fields, fork lineage
  and reset, executable fork rejection, unavailable replay status, and Gate B
  invalidation after methodology drift.

## Repair / test-author scope

- Production code remains untouched. Task state remains untouched; this note is
  context for the repair handoff only.
- Add strict RED coverage for the three review/audit blockers: default registry
  discovery must remain bounded to the safe ten-detector maximum; missing
  detector dependencies must return explicit `replay-unavailable` status; and
  detector metadata, version, or implementation-hash drift must invalidate
  replay, review, and Gate B even when `query.sql` is unchanged.
- The focused RED command is `./.venv/bin/pytest -q tests/test_m5_handoff.py`.
  Strict evidence on 2026-08-22: exit 1, `5 failed, 6 passed`; all five
  failures are the intended new contracts, with no collection or fixture
  errors. A passing implementation must preserve the existing 10-detector cap
  and all prior handoff behavior.
