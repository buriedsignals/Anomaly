# Install a pinned local EmbeddingGemma runtime

## Goal

Add an optional, pinned local EmbeddingGemma 300M runtime without making semantic search a core-install dependency.

## Acceptance criteria

- Complete core Anomaly installation successfully when the model is skipped.
- After core install, show local-only behavior, download size, Gemma Terms URL and version, and Install or Skip choices.
- Never accept model terms on the user’s behalf or persist a Hugging Face token.
- Install a signed architecture-appropriate pinned artifact and verify its checksum and upstream revision.
- Store the model outside cases with a manifest and local consent receipt.
- Smoke-test offline query and document embeddings at 512 normalized dimensions.
- Provide a later model-install command when installation is skipped.

## Non-goals

- Case indexing.
- Semantic ranking.
- Remote embedding APIs.

## Audit

Required: model supply chain, signature/checksum verification, license consent, secret handling, cache containment, and offline guarantees.
