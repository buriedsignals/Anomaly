# Task 17 notes

Capture opened from PRD M2 after task 16 completed. The capture lock must
resolve the exact detector inventory and the registry/template execution seam
before plan and test authorship begin.

Capture locked M2 to 20 total core detectors: retain the six existing M1 SQL
detectors and add 14 new detectors. The registry, SQL template, recommendation
bound, provenance, and local-only security boundaries are in scope; hosted and
Navigator surfaces are not.

Plan/test-author contract:

- AC1 write: `tests/test_detector_registry.py` requires stable metadata for all
  20 IDs, including input requirements, parameters, severity, output,
  assumptions, false positives, sensitive-output handling, and limits.
- AC2 write: deterministic discovery must reject duplicate IDs, unsafe package
  boundaries, malformed metadata, and executable case-supplied code.
- AC3 revise: existing recommendation and Gate A tests remain authoritative for
  the ten-detector bound; the new registry tests require explicit approval at
  the execution boundary.
- AC4 write: the catalogue assertion fixes the six existing IDs plus these 14
  new IDs: two temporal, two relational, two network, two text, two
  cross-dataset, two credential, and two domain detectors.
- AC5 write: a SQL-only user package with the documented metadata/query shape
  validates; mutation, external-reader, file-relation, and multi-statement SQL
  is rejected.
- AC6 revise: existing read-only/limits/provenance tests remain authoritative;
  the new registry contract requires lead status and detector/source/parameter
  provenance on returned outputs.
- AC7 write: focused tests scan the local detector surface for forbidden hosted,
  service, CLI, MCP, deployment, and membership concepts and verify a SQL-only
  `_template` package.

Refactor opportunity: null. The existing `anomaly.detect` and
`anomaly.recommend` behavior is consumer-observable and should be reused behind
the registry boundary rather than duplicated.

RED evidence: `env UV_CACHE_DIR=/private/tmp/anomaly-uv-cache uv run --extra
test pytest -q tests/test_detector_registry.py` -> `10 failed, 1 passed in
0.28s`; the registry module and SQL template do not yet exist, and the exact
20-package/template/provenance contract is therefore red.

Repair RED evidence: the focused contract now also proves that incomplete
metadata, symlinked package files, executable package files, synthetic
approved execution, absent user-package recommendation, empty placeholder
fixtures, and unredacted sensitive fixture output are unacceptable. The
prepared-case test intentionally fails until registry recommendation and
execution share the complete 20-detector catalogue and Gate A remains
mandatory.
