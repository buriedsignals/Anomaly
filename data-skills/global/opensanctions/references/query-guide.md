# OpenSanctions screening and investigation guide

## Screen a known subject

1. Gather only reliable identity attributes from lawful, attributable sources.
2. Choose the correct FollowTheMoney schema.
3. Use `match-entity`, normally against `default`, with a documented risk-topic
   scope and threshold.
4. Review every candidate and false-positive explanation manually.
5. Retrieve plausible candidate IDs and inspect designation/program lineage.
6. Verify current status in the issuing authority's primary record.

```bash
navigator query global/opensanctions --operation match-entity \
  --input '{"schema":"Person","properties":{"name":["Arkadii Rotenberg"],"birthDate":["1951"]},"dataset":"default","topics":["sanction"],"threshold":0.8,"algorithm":"logic-v2","limit":5}'
```

Do not modify birth dates, nationality, or identifiers simply to increase a
score. Record which attributes were supplied and why the chosen threshold fits
the review process.

## Use search only for discovery

```bash
navigator query global/opensanctions --operation search-entities \
  --input '{"q":"\"Wagner Group\"","schema":"Organization","dataset":"default","limit":10,"offset":0,"filter_op":"AND"}'
```

Search is appropriate for exploring spellings, entities, datasets, topics, and
facets. It is not an automated screening decision. Search query strings are
logged upstream, so do not send a sensitive subject name under an assumption of
non-disclosure.

## Candidate review

For every plausible candidate, compare:

- canonical and referent IDs;
- names, aliases, birth/incorporation dates, countries, addresses, and
  identifiers;
- schema and whether the record is the subject or an adjacent relationship;
- `target`, risk topics, datasets, sanctions program, authority, and dates;
- first/last seen and last-change timestamps;
- contradictions and missing attributes.

A high score with mismatched strong identifiers remains a likely false positive.
A low/no score with sparse input remains inconclusive.

## Exact record and canonical IDs

```bash
navigator query global/opensanctions --operation get-entity \
  --input '{"entity_id":"Q7747","nested":true}'
```

If the provider redirects, update the stored canonical ID while preserving the
old referent and decision history. Recheck stored IDs at the provider's
recommended cadence, not continuously.

## No-result discipline

Report:

- dataset/topic scope;
- schema and supplied attributes;
- algorithm and threshold;
- query date and provider freshness;
- spellings/languages tried;
- whether all relevant primary lists were independently checked.

Say “no candidate met this configured query” rather than “not sanctioned” or
“clear.”

## Reporting checklist

- Exact subject identity and independent resolution basis.
- Match/search operation and complete non-secret input scope.
- Candidate ID, score, risk topics, target flag, datasets, program, authority,
  and relevant dates.
- Human-review reasoning, conflicts, and false-positive decision.
- Primary issuing-authority source and retrieval time.
- Privacy/disclosure basis and retention minimization.
- CC BY-NC or commercial-licence assessment and attribution.
