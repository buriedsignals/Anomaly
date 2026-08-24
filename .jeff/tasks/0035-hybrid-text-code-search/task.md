# Add optional hybrid text and code retrieval

## Goal

Add optional local semantic retrieval over approved text or code fields and redacted signal content.

## Acceptance criteria

- Store embeddings and manifests as rebuildable projections under .anomaly/search and never as evidence.
- Chunk text within source, table, and field boundaries and retain source hash, table, candidate or row, and field references.
- Preserve language, path, symbol, and line range for code when available.
- Use EmbeddingGemma document, query, and code-retrieval prompts for their intended modes.
- Apply handling and structured filters before retrieval.
- Fuse lexical and cosine candidates deterministically and return component scores, matched_on details, and canonical references.
- Keep exact identifier, path, and symbol search primary for code.
- Version model, prompt, dimensions, chunker, and content hashes without persistent HNSW.

## Non-goals

- Remote embedding APIs.
- Embedding unapproved fields.
- Treating retrieval similarity as evidentiary confidence.

## Audit

Required: embedding eligibility, local-only execution, projection containment, query filtering, sensitive-data exclusions, and attribution.
