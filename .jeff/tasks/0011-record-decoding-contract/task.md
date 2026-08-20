# 0011 — Record-decoding contract

## Goal

Decode every acquisition-supported local format into records without silently discarding source content. Unsupported shapes fail closed with an explicit error.

## Acceptance criteria

- One deterministic decoder contract handles CSV, JSON, JSONL, Parquet, and XML.
- CSV preserves every row and header field.
- JSON accepts an object as one record or an array containing only objects. Scalar/mixed arrays fail explicitly; no members are filtered.
- JSONL requires one object per nonblank line and reports the failing line.
- Parquet preserves rows, columns, nulls, and primitive values through a local deterministic reader.
- XML supports row data expressed as attributes, child elements, or both; conflicting duplicate keys fail explicitly.
- Empty valid datasets are distinguished from invalid or lossy shapes.
- Decoder output contains only record dictionaries and does not execute embedded content, use the network, or mutate a case.
- Positive, negative, mixed-shape, boundary, and losslessness fixtures cover each format.

## Non-goals

- Case paths or fork safety (0010).
- DuckDB index, semantic mapping, or profile generation (0012).
- Arbitrary XML document-to-object inference beyond an explicit repeated-record structure.

## Audit

Required: untrusted structured input, parser limits, entity/external-reference refusal, unsafe deserialization, and silent-loss prevention.
