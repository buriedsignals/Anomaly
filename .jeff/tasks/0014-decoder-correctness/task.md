# 0014 — Decoder correctness

## Goal

Decode acquisition-supported local formats deterministically without silently dropping or changing records. Host/harness isolation owns CPU, memory, and hostile compression limits.

## Resource boundary

- Anomaly does not promise to sandbox adversarial compressed files or predict Python object-memory amplification.
- The host/harness enforces process memory, CPU, timeout, and file-size budgets.
- Decoder failures remain explicit and return no partial result.

## Acceptance criteria

- One local decoder contract handles CSV, JSON, JSONL, Parquet, and XML.
- CSV preserves all rows and header fields.
- JSON accepts one object or an object-only array; scalar/mixed arrays fail explicitly without filtering.
- JSON numbers use standard finite Python numeric behavior; nonfinite overflow and nonzero-to-zero underflow fail explicitly.
- JSONL uses actual LF/CRLF physical records—not `str.splitlines()` Unicode separators—and every invalid nonblank record reports its physical line.
- Parquet preserves rows, columns, nulls, and primitive values for valid local files; invalid/corrupt shapes fail explicitly. Host limits bound resource consumption.
- XML repeated rows preserve attributes and child elements; duplicate/conflicting keys, unsupported container attributes, and entity/external-reference constructs fail explicitly.
- Empty valid datasets are distinct from invalid/lossy shapes.
- Output contains record dictionaries only; decoding is local, inert, case-independent, and makes no network calls.
- Positive, negative, mixed-shape, boundary, U+2028, and losslessness fixtures cover all formats.

## Non-goals

- Adversarial decompression or Python object-memory guarantees.
- Process quotas or sandboxing.
- Case safety and P2 integration.

## Audit

Required: silent-loss prevention, XML external-reference refusal, inert local parsing, and network/execution absence. Host-owned resource quotas are explicitly out of scope.
