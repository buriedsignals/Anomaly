---
name: congress-corral-members
description: >-
  Reference for Congress Corral, a free unofficial web app listing US members
  of Congress from a published Google Sheets CSV, with IDs for Bioguide,
  GovTrack, OpenSecrets, VoteSmart, FEC, and social accounts. Catalogued only:
  no adapter, weak provenance. Use it as a lead list, never as a record.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/congress-corral/members
---

# Congress Corral (catalogued, not queryable)

Status: **catalogued**. Anomaly has no adapter for this source; loading it
returns `unavailable` with `source-not-queryable`.

## What it is

A single-page app at https://localsearchamerica.com/cc/ (also
https://congresscorral.com) that loads one published Google Sheet of
members of Congress (538 listed on 2026-10-27) and links each member's
YouTube, news, and Wikipedia page-view tools.

## Access

- Auth: none. Cost: free.
- Data: the published CSV
  `https://docs.google.com/spreadsheets/d/e/2PACX-1vRH6TXNTVxFc6qyYn4NNdPwrkuYCe5r9-mXn_sCSJJZH9qC1GUDfspkxNgzFrBOFIv62NGKpVSWnsok/pub?output=csv`,
  found in the page HTML. Download it manually and register it as a
  journalist-supplied file.
- Columns (inferred from the page script, unverified against the CSV):
  `full_name`, `type`, `state`, `district`, `party`, `gender`, `birthday`,
  `religion`, `occupation`, `bioguide_id`, `govtrack_id`, `opensecrets_id`,
  `votesmart_id`, `fec_ids`, `cspan_id`, `wikipedia_id`, `ballotpedia_id`,
  social handles, `phone`, `address`, `contact_form`, `url`, `image`.

## Licence

None stated.

## Limitations

- Unofficial compilation; no maintainer, upstream source, or update date is
  stated. The sheet can change or vanish without notice.
- Religion and occupation labels overlap (the filters list "Catholic Church",
  "Catholicism", and "Roman Catholic" separately); do not count by them.
- Use the IDs only to reach official records (e.g. Bioguide, FEC via the
  `us/fec/campaign-finance` skill) and verify there.
