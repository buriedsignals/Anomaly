---
name: icc-cases
description: >-
  Reference for the International Criminal Court's public case list
  (icc-cpi.int/cases): cases filterable by warrant or summons, crimes,
  defendant status, stage, and situation, each with a case page and court
  records. Catalogued only: no adapter or API; site terms restrict reuse.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/icc/cases
---

# ICC cases (catalogued, not queryable)

Status: **catalogued**. Anomaly has no adapter for this source; loading it
returns `unavailable` with `source-not-queryable`.

## What it is

The ICC's own list of cases (34 on 2026-10-27). Facets on
https://www.icc-cpi.int/cases:

- Warrant/summons: warrant of arrest, summons to appear.
- Crimes: crimes against humanity, war crimes, genocide, article 70 offences.
- State of defendant: at large, in ICC custody, convicted, acquitted, case
  closed.
- Stage: pre-trial, trial, reparation/compensation, closed.
- Situation (e.g. Darfur, Sudan; Democratic Republic of the Congo; Uganda).

Facets are URL parameters, e.g.
`https://www.icc-cpi.int/cases?f%5B0%5D=accused_states_cases%3A329` (at large).

## Access

- Auth: none. Cost: free.
- No API found. Read the case list and case pages in a browser, or build a
  journalist-supplied table by hand from them, recording each page URL and
  retrieval date.
- Court records: https://www.icc-cpi.int/documents and the records RSS feed
  https://www.icc-cpi.int/rss/records/all (not checked further).

## Licence

ICC terms (https://www.icc-cpi.int/disclaimer) allow personal,
non-commercial download and copying only, with no redistribution and no
compiled or derivative works without written permission
(PublicAffairs.Unit@icc-cpi.int). Quoting facts with attribution in
reporting is a legal question for your editor, not settled here.

## Limitations

- The list is small and changes with each warrant, arrest, or judgment;
  record the retrieval date.
- No adapter because automated compilation of the list conflicts with the
  terms' no-compilation clause unless the ICC grants permission (our
  reading, not legal advice).
