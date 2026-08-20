# 0015 — Canonical case semantics

## Goal

Validate portable path-bearing case documents and identity relationships before acquisition or fork mutation. Filesystem safety, decoder behavior, concurrency, and resource quotas are separate concerns.

## Acceptance criteria

- One portable-component policy governs `source_id`, source basenames, `case_id`, and lineage identities: nonempty normalized text; no separators, control/forbidden characters, trailing dot/space, Windows device names, or drive syntax.
- Identity uniqueness uses a portable canonical key based on Unicode normalization and case folding. Canonically equivalent source IDs cannot share or alias raw/receipt namespaces.
- `case.json` has required typed identity/status/timestamp fields; `case_id` is portable and nonempty; `derived_from` is null or a distinct portable identity.
- `data/sources.json` is a list of complete typed records with unique canonical IDs, relative `data/raw/<id>/<basename>` paths, supported formats, SHA-256 hashes, inclusion metadata, and no recursive absolute/traversal/drive-relative path values.
- Receipt JSON is semantically consistent with its corresponding source record for the shared record fields and contains no unsafe recursive path values.
- Acquisition validates the complete existing manifest/receipts and requested canonical identity before writing raw bytes, receipts, or manifest state.
- Fork validates complete portable documents before child creation; requested child ID is portable and canonically distinct from the parent.
- POSIX and Windows absolute/traversal forms—including drive-relative `C:..\x`—fail closed.
- Valid acquisition, manifest, receipt, lifecycle, fork lineage, portability, and parent-preservation behavior remains deterministic.
- Tests are finite semantic matrices; no concurrent-writer, resource-quota, decompression, or descriptor-engine requirements.

## Non-goals

- Filesystem link/type scanning.
- Decoder implementation.
- P2 preparation/profile integration.

## Audit

Required: provenance consistency, canonical identity collisions, cross-platform path semantics, and pre-mutation validation ordering.
