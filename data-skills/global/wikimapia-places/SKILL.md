---
name: wikimapia-places
description: >-
  Reference for Wikimapia's beta API: crowd-sourced places by ID, bounding
  box, nearest point, or text search, with a free API key. Catalogued only:
  no adapter. Use for location leads (building names, site outlines), never
  as authoritative geography.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: global/wikimapia/places
---

# Wikimapia places (catalogued, not queryable)

Status: **catalogued**. Anomaly has no adapter for this source; loading it
returns `unavailable` with `source-not-queryable`.

## What it is

Wikimapia is a crowd-sourced map where users outline and describe places.
Place records carry title, description, categories, polygon geometry,
location, last editor, photos, and comments
(https://wikimapia.org/api/).

## Access

- Auth: free API key. Log in at wikimapia.org, then create one at
  https://wikimapia.org/api/?action=create_key.
- Cost: free.
- Base URL: `http://api.wikimapia.org/` with `key=<key>`, `function=...`,
  `format=json` (xml is the default).
- Functions:
  - `place.getbyid` — `id`
  - `place.getbyarea` — `bbox=lon_min,lat_min,lon_max,lat_max` (or separate
    coordinates, or `x`/`y`/`z` tile); `category` filters; `page`, `count`
  - `place.getnearest` — `lat`, `lon`; `category`; `page`, `count`
  - `place.search` — `q`; optional `lat`, `lon`, `distance` (metres)
- Example from the docs:
  `http://api.wikimapia.org/?key=example&function=place.search&q=eiffel`.

## Licence

Contradictory. The terms (https://wikimapia.org/terms_reference.html, 1.F)
grant CC BY-SA 3.0 for commercial and non-commercial use; the API page says
"free for non-commercial use". Public use must link the original place URL
and mention "Wikimapia.org" (terms 1.G). Assume non-commercial, attributed
use until clarified.

## Limitations

- Beta API; rate limits are not documented on the API page.
- Crowd-sourced: any user can draw or rename a place. Check against
  official cadastral or satellite sources before relying on it.
- The API is plain HTTP (`http://api.wikimapia.org/`) in the docs; the key
  travels in the query string.
