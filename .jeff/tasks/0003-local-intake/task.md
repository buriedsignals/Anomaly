# 0003 — Local file intake

## Goal

Register journalist-supplied local files into `data/sources.json` with hashes and handling metadata. No network.

## Acceptance criteria

- Supported local inputs can be registered: CSV, JSON, JSONL, Parquet, and XML when they are tabular or nested records.
- Each source record stores source ID, relative path, content hash, format, acquisition time, license, sensitivity, redistribution status, and reacquisition notes.
- When data cannot travel with the case, the record sets `included: false`, stores the observed hash, the reason, and how it may be reacquired.
- Raw files are copied into `data/raw/` only when handling policy permits.
- Intake does not open a network connection.
- Credentials never appear in `sources.json` or receipts.

## Non-goals

- Public-source adapters (M3).
- DuckDB preparation and profiling (0004).
- Executing any code found inside a case.

## Audit

Hashing, path containment, and secret redaction. Reject links, traversal, and writes outside the case folder.
