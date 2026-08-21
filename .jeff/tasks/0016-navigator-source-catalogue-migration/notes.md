# Notes

- This is the sole `test-contract-repair` recovery episode after the first
  review/audit round. Production files were not edited.
- Required bundled skills read: Jeff `code-standards` 6.3.4 and `testing`
  6.3.4. The brief's canonical project coding-rules path,
  `/Users/tomvaillant/buried_signals/kit/coding-rules/SKILL.md`, is not
  readable in this environment and was not fabricated.
- Verified source facts: Navigator's
  `tools/navigator/osint-navigator/data/skills/` contains 30 metadata files,
  one of which is the `_template` example; its 29 non-template source package
  metadata files include `global/arbiter/case-studies`; Anomaly's
  `tools/anomaly/data-skills/` contains 28 metadata files, including the
  valid two-segment id `global/opensanctions` and
  `global/thinkpol/reddit-evidence`.

## Revised plan

- Approach: repair the proof contract in `tests/test_source_catalogue.py`
  around the authoritative Navigator inventory, one-to-one package migration,
  shared result states for every real catalogue adapter, catalogue-wide
  forbidden-surface absence, deterministic request-time loading, and registry
  symlink/duplicate-id rejection. Keep the implementation boundary local,
  networkless, and limited to tests plus plan records.
- YAGNI boundary: reuse the existing package metadata, adapters, result
  validator, registry, `tmp_path`, and import-loader seams. No production
  adapter, registry, service, CLI, hosted runtime, membership, metering,
  Navigator, web UI, deployment, or MCP implementation is added here.
- Complexity: complex. Audit remains required because registry discovery and
  dynamic adapter loading cross path-safety and dynamic-execution boundaries.
- Refactor opportunity: harmonize all real adapter result construction behind
  the shared result contract while preserving source-specific query behavior;
  the registry must remain source-id driven and must not gain per-source
  wiring.

## Acceptance dispositions

1. `revise`: `test_navigator_inventory_has_29_packages_and_exactly_28_one_to_one_migrations` derives the 29-package inventory from Navigator, excludes only Arbiter, and requires exactly one Anomaly metadata/skill/adapter package per remaining id. The derived id sets, counts, and package files are the consumer-observable seam.
2. `revise`: `test_shared_result_contract_enforces_each_real_adapter_state` loads every real catalogue adapter and exercises the shared success, unavailable, and error result states through `validate_source_result`. The validator result and state-specific error envelope are the deterministic seam.
3. `revise`: `test_registry_loads_real_adapters_only_after_request` checks repeatable source-id ordering and request-time loading for a real migrated source. Discovery order, module identity, and callable adapter are the consumer seam.
4. `revise`: `test_registry_rejects_symlink_escape_before_loading` and `test_registry_rejects_duplicate_ids` require fail-closed registry behavior for a symlink-parent escape and duplicate source ids. The typed `ValueError` safety boundary is the deterministic seam.
5. `revise`: `test_catalogue_contains_no_forbidden_hosted_or_navigator_surfaces` scans all catalogue files for the locked forbidden surfaces while allowing ordinary source-domain language such as data memberships. Catalogue-wide absence is the consumer seam.
6. `reuse`: `test_prd_m3_language_describes_catalogue_only_migration` continues to verify the existing PRD M3 catalogue wording; no redundant backlog test is added.

## Ordered slices

1. Establish the authoritative 29-to-28 inventory and one-to-one package
   migration contract.
2. Enforce the shared result contract's success/unavailable/error states for
   the real adapter set without network access.
3. Enforce catalogue-wide forbidden-surface absence and ThinkPol's ordinary
   local catalogue representation.
4. Enforce deterministic registry ordering, request-time loading, symlink
   escape rejection, and duplicate-id rejection.
5. Run only the targeted source-catalogue test and hand off RED to the
   implementation stage, retaining the required audit.

## RED evidence

- Command: `uv run --extra test pytest -q tests/test_source_catalogue.py`
- The first sandbox attempt was blocked by uv cache permissions. The approved
  retry of the revised targeted suite reached pytest and produced `7 failed,
  2 passed`.
- Decisive failures include: the current registry rejects
  `global/opensanctions`; discovery does not reject a symlink-parent escape;
  discovery does not reject duplicate ids; and the catalogue contains
  `navigator cli` text. The inventory and adapter-state tests also remain red
  until the registry accepts the locked inventory and real adapter contract.
