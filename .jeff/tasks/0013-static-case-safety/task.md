# 0013 — Static case safety

## Goal

Reject unsafe filesystem state present when a trusted operator starts a case operation. The host/harness owns concurrent-writer isolation and process resource quotas.

## Threat model

- Case content is untrusted data, never instructions or executable code.
- No hostile process is assumed to mutate the same case tree during one operation.
- Anomaly is not a filesystem sandbox or transaction engine.

## Acceptance criteria

- Before create/inspect/resume/acquisition/fork mutation, reject pre-existing absolute/traversal paths, symlinked components/leaves, hard-linked file leaves, wrong file/directory types, and nonregular entries in the relevant case tree.
- `create_case` checks its complete intended directories and fixed files before writing.
- Lifecycle `case.json` and `.anomaly/state.json` unsafe state fails before a mutating caller proceeds.
- `fork_case` scans the complete source tree without following links and rejects symlinks, multiply linked files, devices, FIFOs, sockets, and other nonregular content before creating the child.
- Fork never intentionally dereferences or imports external linked content.
- Valid create, inspect, resume, fork, acquisition, portability, lineage, and parent-preservation behavior remains deterministic.
- Tests cover unsafe state installed before entry. Tests must not require protection from concurrent post-validation namespace mutation, descriptor ceilings, or adversarial process scheduling.

## Non-goals

- Concurrent hostile-writer defense.
- POSIX descriptor transaction engine.
- CPU, memory, or file-descriptor quotas.
- Decoder or P2 behavior.

## Audit

Required: static path/link/type validation, external-content refusal, and no execution of case content.
