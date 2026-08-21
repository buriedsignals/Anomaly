---
name: thinkpol-reddit-evidence
description: >-
  Query ThinkPol's authenticated Reddit evidence API through Data catalogue.
  Use for case-insensitive AND search across archived submissions and comments,
  or when evaluating the provider's documented user-history, subreddit-user,
  quota, and AI-profile capabilities. Preserve provider and Reddit identifiers,
  distinguish indexed content from verified fact, and never treat generated
  profile attributes as established personal facts.
compatibility: Requires authorized local access to ThinkPol.
metadata:
  author: Buried Signals
  version: "1.1"
  source-id: global/thinkpol/reddit-evidence
---

# Query ThinkPol Reddit evidence

Use `meta.yaml` as the executable contract. Inspect the operation before every
query and execute only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `global/thinkpol/reddit-evidence:search-content` — Search ThinkPol's hydrated Reddit submissions and comments using one or more case-insensitive AND terms.

**Not released**

- `global/thinkpol/reddit-evidence:list-user-history` — A credential-backed unknown-user probe returned HTTP 500, so no record-bearing CSV response has been live-verified.
- `global/thinkpol/reddit-evidence:list-subreddit-users` — Live-verified but not released because the endpoint returned 4,215 unpaginated associations for one small subreddit and the provider does not define association semantics or a result bound.
- `global/thinkpol/reddit-evidence:get-quota` — Live-verified but not released because it exposes shared provider-account operational quota rather than public-record evidence.
- `global/thinkpol/reddit-evidence:analyze-profile` — Publicly documented but not released pending credential-backed verification and privacy, lawful-use, consent, quota, and editorial review.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Decide whether disclosing the search terms to ThinkPol is justified. Treat
   account identifiers and investigative terms as potentially sensitive even
   when they concern public content.

2. Inspect the exact contract:

   ```bash
   catalogue data show global/thinkpol/reddit-evidence:search-content
   ```

3. Run a bounded documented search:

   ```bash
   catalogue query global/thinkpol/reddit-evidence --operation search-content \
     --input '{"terms":["election","integrity"],"content_type":"comment"}'
   ```

   Multiple `terms` are ANDed. The public OpenAPI also supports non-negative
   `from` and `to` Unix timestamps and a `comment` or `submission` type filter.

4. Preserve the exact query, retrieval time, returned IDs, timestamps,
   subreddit, author label, and source URL. Inspect the surrounding Reddit or
   preserved context before relying on a record.

5. Attribute observations to ThinkPol and seek independent primary evidence
   for consequential claims. Report an empty response as a bounded negative
   search, never as proof of absence.

## Contract boundary

ThinkPol publishes an official Swagger UI and OpenAPI 3.0.3 document. The
machine-readable document defines `/v2/search`, not the `/v3/search` example
and phrase/cursor/popularity features advertised on the main product page.
This adapter therefore sends only the fields specified for `/v2/search`.

Authenticated probes verified search, quota, and the subreddit response shape.
Subreddit lookup remains unavailable because one small community returned
4,215 unpaginated associations whose meaning and result bound are undocumented;
quota remains unavailable because it is shared-account operational metadata.
An unknown username produced HTTP 500, so no record-bearing user-history CSV
has been live-verified. Profile analysis was not called because it can create
sensitive inferences and consume quota. Do not bypass those release gates with
a raw HTTP request.

Read [the API reference](references/api-reference.md) for the endpoint and
response mapping, documentation drift, terms, and privacy evidence. Read
[the query guide](references/query-guide.md) before handling usernames,
interpreting an empty result, or considering profile analysis.

## Authentication and failure handling

ThinkPol requires bearer authentication and vetted contractual access. This is
a catalogue source: Anomaly uses the locally configured credential. Never place the
credential in prompts, examples, assets, logs, or command arguments.

- On `auth_required`, report the source as temporarily unavailable; do
  not expose credentials in the catalogue or result envelope.
- On `invalid_input`, inspect `show` rather than adding website-only v3 flags.
- On `operation_unavailable`, stop; documentation alone does not release an
  operation.
- On a timeout, rate limit, or upstream error, preserve the failure and retry
  only after a bounded delay. Do not create a retry loop.

## Bundled resources

- [references/api-reference.md](references/api-reference.md) — primary-source
  evidence, full documented endpoint matrix, mappings, auth, terms, and drift.
- [references/query-guide.md](references/query-guide.md) — query construction,
  disclosure checks, interpretation cautions, and no-result recovery.
- `scripts/verify.py` — non-interactive bounded verification through catalogue.
- `assets/verification-cases.json` — executable released-operation test case.
- `evals/evals.json` — realistic agent evaluation prompts and expected behavior.

List the verification cases without contacting ThinkPol:

```bash
python3 scripts/verify.py --list
```

Run them only when network access and the configured credential are intended:

```bash
python3 scripts/verify.py --catalogue catalogue --timeout 90
```
