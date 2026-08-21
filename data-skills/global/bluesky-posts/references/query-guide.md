# Bluesky profile query guide

## Resolve identity carefully

1. Query the exact handle or DID with `get-profile`.
2. Preserve both `handle` and `did`; use the DID as the durable account key.
3. Record `created_at`, `indexed_at`, counts, profile URL, and retrieval time.
4. Corroborate real-world identity through an official site, organization,
   signed statement, or another primary source.

```bash
catalogue query global/bluesky/posts --operation get-profile \
  --input '{"actor":"bsky.app"}'
```

## Do not route to blocked search

`search-posts` is not released. The public AppView returned 403 on the current
egress, and the direct AppView does not accept authentication. Do not bypass the
registry by retrying the same request repeatedly.

If supported search access is added later:

- use explicit author/language/date/domain/tag filters rather than relying on
  undocumented query-string syntax;
- preserve `created_at` separately from `indexed_at` and the search `sortAt`
  boundary;
- treat `hitsTotal` as approximate and the cursor as non-exhaustive;
- archive cited posts promptly and retain their AT URI, DID, and web URL.

## Reporting checklist

- State that the biography and display name are self-published profile data.
- Do not imply that a handle is permanent or that a follower count is current
  beyond the retrieval time.
- Attribute quoted posts to the preserved account state; separately verify any
  factual assertion inside them.
- Treat deletion, non-resolution, and search unavailability as unknown state,
  not proof of absence or wrongdoing.
