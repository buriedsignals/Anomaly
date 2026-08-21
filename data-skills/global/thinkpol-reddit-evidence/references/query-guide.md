# ThinkPol Reddit-evidence query guide

## Task routing

| Research need | Operation | Status | Evidence returned |
|---|---|---|---|
| Search archived submissions and comments | `search-content` | Released | Hydrated records with provider-returned IDs, metadata, and links |
| Retrieve one username's history export | `list-user-history` | Unavailable | An unknown-user probe returned HTTP 500; no record-bearing CSV is live-verified |
| List users associated with a subreddit | `list-subreddit-users` | Unavailable | Live array shape, but unpaginated and without defined association semantics or a result bound |
| Inspect remaining account quota | `get-quota` | Unavailable | Live integer, withheld because it is shared-account metadata with no public unit or reset rule |
| Generate inferred personal attributes | `analyze-profile` | Unavailable | Model-generated profile requiring separate safeguards |

Do not call an unavailable operation directly. Provider documentation explains
capability but does not override Data Navigator's release gate.

## Decide whether to disclose the query

ThinkPol is an external service. Before querying, consider whether the term,
username, subreddit, timestamp window, or combination would expose a
confidential source, unpublished allegation, target list, protected identity,
or investigative hypothesis. Use a safer approved workflow when the disclosure
would be disproportionate.

ThinkPol says it counts request volume and type rather than storing customer
request data, but its general privacy policy also covers usage analytics. Do
not convert a provider statement into a zero-logging guarantee.

## Construct a documented search

Start with one term and, where useful, one content type:

```bash
navigator query global/thinkpol/reddit-evidence --operation search-content \
  --input '{"q":"disinformation","content_type":"comment"}'
```

Use repeated terms only when an AND query matches the research question:

```bash
navigator query global/thinkpol/reddit-evidence --operation search-content \
  --input '{"terms":["election","integrity"],"content_type":"submission"}'
```

Bound a period with Unix timestamps when the reporting question has a clear
time range. `from` must not be later than `to`.

The public `/v2/search` contract does not expose exact-phrase mode, result
limit, ordering, cursor pagination, or popularity buckets. Do not pass the
marketing page's v3 example parameters to the released operation.

## Interpret records

Treat a returned record as evidence that ThinkPol's index returned those fields
for that query at that retrieval time. It does not by itself establish:

- that the named author controls a particular real-world identity;
- that the text is authentic, complete, still online, or true;
- when a score or comment count was observed;
- that ThinkPol indexed all relevant Reddit content or deletions;
- that a missing result proves no matching content exists.

Preserve query terms, filters, retrieval time, content ID, author label,
subreddit, content timestamp, parent/submission IDs, and provider-returned URL.
Open or separately preserve the surrounding Reddit context before publication.

## No-result recovery

1. Confirm term spelling, timestamp units, and content type.
2. If multiple terms were supplied, record that they are ANDed and remove only
   a constraint the reporting question permits you to broaden.
3. Search comments and submissions separately when collection type matters.
4. Record every attempted scope and the retrieval time.
5. Report `no_results` as a bounded provider search, not a universal negative.

## User and subreddit operations

If these operations are later released, preserve the exact username or
subreddit spelling. The user-history timestamp is a provider-formatted string,
not a normalized timezone-aware timestamp. A subreddit-user result means only
that ThinkPol returned an association; it does not prove membership,
endorsement, moderation, present activity, or wrongdoing.

The live API returned JSON `null` for unknown subreddit names and an
unpaginated 4,215-name array for one small community. The adapter normalizes
`null` to no results, but the operation remains unavailable until its scope can
be bounded and the provider defines what an association represents.

## Profile analysis boundary

Do not run `analyze-profile` while it is unavailable. Even after future release:

- require an explicit lawful purpose and any required consent or approval;
- request source verification and inspect the cited comment IDs;
- label every demographic, location, economic, relationship, interest, and
  personality field as model-generated inference;
- seek independent evidence before any consequential use;
- never use it for harassment, discrimination, re-identification, or automated
  adverse decisions.

An AI profile is a hypothesis generator with substantial false-positive and
privacy risk, not an identity record or factual biography.
