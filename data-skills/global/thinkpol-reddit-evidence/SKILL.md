---
name: thinkpol-reddit-evidence
description: Search ThinkPol's documented Reddit submission and comment archive.
---

# ThinkPol Reddit Evidence

This is a local Anomaly catalogue source for bounded searches of ThinkPol's
documented Reddit archive. Use the `search-content` operation with `q` or
`terms`, and optionally `content_type`, `from`, and `to`.

Search terms and identifiers leave the local catalogue for the documented
source endpoint. Preserve the exact query, retrieval time, returned IDs,
timestamps, subreddit, author label, and source URL. An empty response is a
bounded negative search, not proof of absence.

Read [the query guide](references/query-guide.md) for query construction and
interpretation cautions.
