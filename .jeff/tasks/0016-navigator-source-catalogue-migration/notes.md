# Notes

- Captured after installing Jeff 6.3.4 and initializing colocated Jujutsu.
- Baseline before task capture: `uv run --extra test pytest -q` — 628 passed.
- Scope decision: include ThinkPol as a catalogue source; do not carry
  Navigator's hosted-key/runtime model into Anomaly.

## Plan

- Approach: keep the existing source-package shape under `data-skills/`, add
  the 27 remaining in-scope Navigator packages beside the already migrated
  OpenParlData package, define one local adapter-result contract, and expose a
  deterministic registry that walks packages in sorted order and imports an
  adapter only after a source id is requested.
- YAGNI boundary: reuse the existing Agent Skill package shape, `meta.yaml`,
  `SKILL.md`, and `adapter.py`; do not add a service, CLI, hosted runtime,
  membership, metering, MCP, deployment, or a generated static catalogue.
- Complexity: complex. Audit required because discovery and on-demand loading
  are dynamic execution and path-safety boundaries.
- Refactor opportunity: harmonize the existing OpenParlData adapter metadata
  and result envelope with the new shared contract while preserving its public
  query behavior; do not duplicate source-specific routers in the registry.

## Acceptance dispositions

1. `write`: `test_migration_has_exact_navigator_inventory_and_complete_packages`
   observes exactly the 28 non-Arbiter ids, includes ThinkPol, recognizes
   OpenParlData, excludes only Arbiter, and requires each package's skill and
   adapter files. The sorted package walk and exact id set are the outcome seam.
2. `write`: `test_source_result_contract_covers_success_and_unavailable_states`
   observes metadata, licence, endpoint/operation, validation, normalized
   records, source hash, provenance, and typed unavailable/error states. The
   contract validator is the outcome seam.
3. `write`: `test_registry_is_deterministic_safe_and_loads_adapter_only_on_request`
   observes repeatable sorted discovery, no adapter import during discovery,
   on-demand loading by source id, and adapter execution. The temporary
   package, import marker, and repeated registry result are deterministic seams.
4. `write`: `test_registry_rejects_malformed_or_unsafe_packages` observes
   fail-closed rejection of an unsafe source id before loading or execution.
   The registry exception is the deterministic safety seam.
5. `write`: the inventory and metadata assertions represent ThinkPol through
   the same ordinary local catalogue contract; no hosted-key or membership
   field is accepted by the planned metadata contract. The shared contract and
   package inventory are the consumer seams.
6. `write`: the plan explicitly carries no Navigator CLI, service, web UI,
   deployment, or MCP surfaces; repository-level wording checks belong in the
   migration documentation/backlog update and its targeted test or static
   assertion. The absence of those production surfaces is the verification seam.
7. `write`: the source package documentation and PRD/backlog wording update are
   part of the implementation slice, with tests remaining local and networkless.
   Targeted package/inventory and static-text checks are the deterministic seam.

## Ordered slices

1. Define the source adapter result contract and validation/error envelope.
2. Migrate the 27 remaining in-scope skill packages and normalize ThinkPol and
   OpenParlData metadata to the catalogue-only contract.
3. Implement sorted safe discovery and request-time adapter loading.
4. Update PRD/backlog language to the catalogue-only M3 model.
5. Run the targeted source tests, then hand off for implementation and the
   required dynamic-loading audit.

## RED evidence

- Command: `uv run --extra test pytest -q tests/test_source_catalogue.py`
- Decisive RED: `ModuleNotFoundError: No module named 'anomaly.sources'` during
  collection. The baseline remains `uv run --extra test pytest -q` — 628
  passed before this task. The first sandbox attempt could not access the uv
  cache; the approved retry reached pytest and produced the RED above.
