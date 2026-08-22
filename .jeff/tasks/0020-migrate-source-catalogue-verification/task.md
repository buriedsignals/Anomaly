# Repair migrated source catalogue verification after Navigator move

## Goal
Make Anomaly's fetched 28-package source migration independently verifiable after the Data Navigator source skills moved into `anomaly/data-skills/`.

## Acceptance criteria
- Update `tests/test_source_catalogue.py` to resolve the current canonical Navigator source root (`navigator/data/skills`) or replace that external comparison with an explicit checked-in inventory contract.
- Ignore filesystem metadata such as `.DS_Store` when scanning source resources; preserve validation of all intended text/resource files.
- The 28 non-Arbiter package parity, adapter result contract, forbidden hosted/Navigator surfaces, and source-specific checks pass without network access.
- No Arbiter package is added to Anomaly.
- No Spotlight-specific personas, vaults, evidence cards, or report machinery are added.

## Non-goals
- Do not change Anomaly detector behavior.
- Do not delete or mutate the Navigator repository.
- Do not implement the Spotlight Arbiter integration here.

## Known RED evidence
`uv run pytest tests/test_source_catalogue.py -q` currently fails because the test resolves a removed `navigator/osint-navigator/data/skills` path and because `.DS_Store` cannot be decoded as UTF-8.
