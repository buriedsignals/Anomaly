---
name: bluesky-posts
description: >-
  Use this skill to resolve public Bluesky handles or DIDs to detailed profiles
  and stable DIDs through the official AppView. Apply it to account identity
  resolution and profile preservation. Do not invoke the currently blocked
  post-search operation, treat handles as permanent, or treat biographies as
  independently verified identity claims.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to public.api.bsky.app.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/bluesky/posts
---

# Resolve Bluesky profiles

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/bluesky/posts:get-profile` — Resolve one public Bluesky handle or DID through app.bsky.actor.getProfile.

**Not released**

- `global/bluesky/posts:search-posts` — Public AppView searchPosts returned HTTP 403 from catalogue's egress on 2026-08-12; the lexicon permits providers to require authentication.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Inspect the operation before sending an account identifier:

   ```bash
   catalogue data show global/bluesky/posts:get-profile
   ```

2. Resolve the exact handle or stable DID:

   ```bash
   catalogue query global/bluesky/posts --operation get-profile \
     --input '{"actor":"bsky.app"}'
   ```

3. Preserve handle, DID, profile URL, profile/index timestamps, follower/follow
   counts, post count, and retrieval time. Use the DID for reconciliation.

4. Verify real-world identity outside Bluesky before attributing statements to
   a person or organization.

## Source boundary

The official profile lexicon is public and no-auth. The official search lexicon
declares richer filters but allows service providers to require auth. On
2026-08-12, the public AppView returned 403 for search and 200 for profile.
catalogue therefore releases profile lookup only.

The direct AppView documentation does not publish a numeric request ceiling;
it calls limits generous and directs users to contact Bluesky when limited.
Read [the API reference](references/api-reference.md) before assuming an auth or
rate-limit policy.

## Failure handling

An unresolved handle may be misspelled, renamed, deleted, moderated, or
temporarily unavailable. Do not translate that ambiguity into a claim. Do not
retry blocked search in a loop or attach an invented token to the public host.

## Bundled resources

- `references/api-reference.md` — official lexicon fields, auth boundary, live
  status, limits, and rights caveats.
- `references/query-guide.md` — identity resolution and preservation workflow.
- `scripts/verify.py` with `assets/verification-cases.json` — bounded live
  profile verification.
- `evals/evals.json` — ambiguity, completeness, and attribution cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
