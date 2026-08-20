# 0010 — Case-tree safety

## Goal

Make case creation, lifecycle reads, and forks fail closed on namespace aliases and nonregular content. This task is independent of P2 decoding and profiling.

## Acceptance criteria

- `create_case` preflights the complete intended directory and fixed-file tree before writing any byte.
- Pre-existing symlinked components, symlink leaves, hard-linked file leaves, nonregular leaves, and file-at-directory/directory-at-file conflicts are rejected atomically.
- Root files and purpose directories cannot alias each other or an external inode.
- `inspect_case`, `resume_case`, and all mutating callers reject unsafe `case.json` and `.anomaly/state.json` reads before any mutation.
- `fork_case` preflights the entire source tree before creating the destination and rejects symlinks, hard-linked regular files, devices, sockets, FIFOs, and other nonregular entries.
- Fork never dereferences or imports out-of-case content. Valid regular cases remain portable; parent bytes remain unchanged; child identity/`derived_from` are correct.
- Existing create/resume/fork behavior and acquisition tests remain green.

## Non-goals

- CSV/JSON/JSONL/Parquet/XML decoding (0011).
- DuckDB preparation/profile behavior (0012).
- Generic sandbox or virtual filesystem.

## Audit

Required: path traversal, inode aliasing, link refusal, file-type validation, atomic preflight, and external-content import.
