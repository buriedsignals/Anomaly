# Notes — 0011

Operator approved separating format semantics from P2 integration after task 0009 silently lost attribute-only XML rows and non-object JSON/JSONL values.

This task owns only a deterministic local records decoder and its fixtures. It must make loss visible as an error rather than inventing or filtering rows. Task 0012 consumes the decoder.
