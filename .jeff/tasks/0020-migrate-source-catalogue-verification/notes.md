# Plan

- Category: `code`
- Complexity: `simple`
- Audit call: `auditRequired: false`. This is a test-only migration-verification repair; production source and dependency behavior are unchanged, and the targeted suite is deterministic/offline.
- Refactor opportunity: Consolidate catalogue text traversal in `_text_files` so the forbidden-surface and source-specific scans share one metadata-safe resource filter; this preserves behavior while removing duplicated filesystem walking.

## Ordered slices

1. Point the parity comparison at the current sibling Navigator catalogue (`navigator/data/skills`), assert that the root exists, and retain the 29-package/28-non-Arbiter one-to-one inventory contract.
2. Add a shared text-resource iterator for checked-in `.json`, `.md`, `.py`, `.yaml`, and `.yml` resources that ignores hidden filesystem metadata such as `.DS_Store`; use it for catalogue-wide and ThinkPol-specific scans.
3. Keep the existing offline adapter contract, lazy-loading, source-specific, forbidden-surface, and registry safety tests; make the no-Arbiter condition explicit in the parity test.
4. Run only `uv run pytest tests/test_source_catalogue.py -q`; do not run formatters, linters, or project-wide suites.

## Acceptance dispositions

- Canonical Navigator root and 28-package parity — `revise`: the consumer-visible migration invariant is that Anomaly contains exactly the 28 non-Arbiter IDs from the current `navigator/data/skills` inventory. Deterministic seam: `test_navigator_inventory_has_29_packages_and_exactly_28_one_to_one_migrations` resolves the sibling root, compares sorted metadata IDs, checks 29 Navigator IDs with one Arbiter ID, checks 28 Anomaly IDs, and verifies each migrated package has `SKILL.md` and `adapter.py`.
- Metadata-safe scanning with intended resources preserved — `revise`: forbidden-surface and ThinkPol scans still inspect every checked-in text/resource suffix while excluding hidden metadata. Deterministic seam: `_text_files(SOURCE_ROOT)` and `_text_files(thinkpol_root)` enumerate stable sorted paths and decode only the declared text suffixes.
- Adapter result contract and offline behavior — `reuse`: existing `test_shared_result_contract_validates_each_real_adapter_output_without_network` loads all 28 adapters, patches `httpx` with an offline module, validates the shared envelope, metadata parity, hash, provenance, and status/error fields. Deterministic seam: `_offline_httpx`, `_offline_input`, `validate_source_result`, and the checked-in adapter bytes.
- Forbidden hosted/Navigator surfaces and source-specific checks — `reuse`/`revise`: existing catalogue-wide forbidden-pattern and ThinkPol key/quota/profile checks remain intact while using the safe iterator. Deterministic seam: checked-in text contents and fixed regex policy tuple.
- No Arbiter package in Anomaly — `revise`: add an explicit `ARBITER_ID not in anomaly_ids` assertion alongside the existing set-difference parity check. Deterministic seam: sorted `meta.yaml` inventory under `data-skills`.
- No Spotlight-specific personas, vaults, evidence cards, or report machinery — `skip`: this test-only change adds no production or Spotlight files; no additional observable contract is owed.

## Changed files

- `tests/test_source_catalogue.py`
- `.jeff/tasks/0020-migrate-source-catalogue-verification/notes.md`

## RED evidence before the test-contract update

Command: `uv run pytest tests/test_source_catalogue.py -q`

Observed: `2 failed, 9 passed in 0.45s`.

- `test_navigator_inventory_has_29_packages_and_exactly_28_one_to_one_migrations` resolved the removed `navigator/osint-navigator/data/skills` path and observed `len(navigator_ids) == 0` instead of 29.
- `test_catalogue_contains_no_forbidden_hosted_or_navigator_surfaces` attempted UTF-8 decoding of a binary metadata file (`.DS_Store`) and raised `UnicodeDecodeError`.

## Post-update targeted evidence

Command: `uv run pytest tests/test_source_catalogue.py -q`

Observed: `11 passed in 0.29s`.

No network access is permitted by the adapter fixtures; no formatter, linter, or project-wide suite was run.
