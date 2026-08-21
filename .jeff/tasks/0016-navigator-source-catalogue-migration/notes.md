# Notes

- This is the bounded test-contract repair after the first review/audit round.
- The second independent review round passed the security audit but found the
  real-adapter envelope and lazy-loading tests still under-specified; those
  findings are routed to a fresh plan/test-author pass.
- The current checkpoint includes production catalogue and registry changes;
  earlier wording that production files were not edited was stale and is
  superseded by the checkpoint evidence.
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
  forbidden-surface absence including catalogue CLI/key commands, deterministic
  request-time loading, and registry symlink/duplicate-id rejection. Keep the
  implementation boundary local, networkless, and limited to tests plus plan
  records.
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
2. `revise`: `test_shared_result_contract_validates_each_real_adapter_output_without_network` loads every real catalogue adapter through an offline HTTP module and validates its returned success, unavailable, or error envelope with `validate_source_result`. The validator result and typed error envelope are the deterministic seam.
3. `revise`: `test_registry_loads_real_adapters_only_after_request` checks repeatable source-id ordering, side-effect-free discovery, request-time loading, and non-loading of a distinct unrequested adapter. Discovery side effects, module identity, and callable adapter are the consumer seam.
4. `revise`: `test_registry_rejects_symlink_escape_before_loading` and `test_registry_rejects_duplicate_ids` require fail-closed registry behavior for a symlink-parent escape and duplicate source ids. The typed `ValueError` safety boundary is the deterministic seam.
5. `revise`: `test_catalogue_contains_no_forbidden_hosted_or_navigator_surfaces` scans all catalogue files for the locked forbidden surfaces while allowing ordinary source-domain language such as data memberships. Catalogue-wide absence is the consumer seam.
6. `reuse`: `test_prd_m3_language_describes_catalogue_only_migration` continues to verify the existing PRD M3 catalogue wording; no redundant backlog test is added.

## Ordered slices

1. Establish the authoritative 29-to-28 inventory and one-to-one package
   migration contract.
2. Enforce the shared result contract's success/unavailable/error states for
   the real adapter set through an offline HTTP module.
3. Enforce catalogue-wide forbidden-surface absence and ThinkPol's ordinary
   local catalogue representation.
4. Enforce deterministic registry ordering, side-effect-free discovery,
   request-time loading, unrequested-adapter non-loading, symlink escape
   rejection, and duplicate-id rejection.
5. Run only the targeted source-catalogue test and hand off RED to the
   implementation stage, retaining the required audit.

## RED evidence

- Command: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/test_source_catalogue.py`
- The revised targeted suite reached pytest and produced `2 failed, 5 passed`.
- Decisive failures are consumer-observable: a real OpenParlData adapter call
  propagates the offline upstream exception instead of returning a validated
  unavailable/error envelope, and the catalogue contains `catalogue cli`.
- The suite also asserts that discovery does not add real adapter modules and
  that loading one requested adapter leaves a distinct unrequested adapter
  unloaded; those assertions are green against the current registry.

## Fresh plan/test-author pass: review repair

- Approach: strengthen the existing real-adapter envelope test with exact source-hash, requested-source provenance, and discovered-metadata assertions; strengthen the isolated malformed-package test with a callable `run` definition followed by a non-callable final overwrite.
- YAGNI boundary: reuse `discover_sources`, `load_source_adapter`, `SourceEntry.metadata`, the existing offline HTTP fixture, `hashlib`, and `tmp_path`; edit no production or catalogue files.
- Complexity: simple. Audit remains required because the tests cover dynamic adapter discovery and request-time loading safety.
- Refactor opportunity: harmonize registry validation so AST discovery and loaded-module validation share one callable-`run` predicate without adding per-source wiring.
- Acceptance dispositions: AC2 `revise` — each real adapter result must preserve the discovered operation, licence, endpoint, exact adapter-content hash, and requested-source provenance; the validated result envelope is the deterministic seam. AC3 `revise` — discovery must reject an adapter whose final `run` attribute is non-callable after overwrite; the isolated `ValueError` boundary is the deterministic seam. Other criteria `reuse`.
- Ordered slices: (1) add exact real-adapter metadata/hash/provenance assertions; (2) make the malformed adapter overwrite `run` with a non-callable final attribute; (3) run the mandated targeted test command and hand off RED.
- RED evidence: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra test pytest -q tests/test_source_catalogue.py` produced `2 failed, 7 passed in 0.50s`. The real-adapter test failed with `KeyError: 'adapter'` because provenance did not identify the requested source; the malformed-package test failed because discovery did not raise `ValueError` for the overwritten non-callable `run`.

## Fresh plan/test-author pass

- This pass adds two proof obligations from the latest review: ThinkPol-specific
  absence of API-key retrieval, quota, and profile-operation surfaces; and
  deterministic discovery rejection when `adapter.py` has no callable `run`.
- `test_thinkpol_catalogue_has_no_key_quota_or_profile_surfaces` scans the
  ThinkPol package as the consumer-visible catalogue boundary.
- `test_registry_rejects_adapter_without_callable_run` creates an isolated
  malformed package and requires discovery to fail with a typed `ValueError`
  before any request-time load.
- Existing catalogue, registry, and PRD tests are reused; no production or
  catalogue files are edited in this pass.
- Complexity remains complex and audit remains required because the added
  contracts cover source-content policy and dynamic adapter-discovery safety.
- Fresh RED evidence: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run
  --extra test pytest -q tests/test_source_catalogue.py` produced `2 failed, 7
  passed`. The ThinkPol test failed on the existing `api_key` surface; the
  malformed-package test failed because discovery did not raise `ValueError`.
