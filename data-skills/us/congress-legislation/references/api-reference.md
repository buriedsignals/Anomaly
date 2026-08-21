# Congress.gov API reference

## Evidence checked

Primary Library of Congress material was fetched with Firecrawl on 2026-08-12:

| Evidence | URL |
|---|---|
| Congress.gov API endpoint index | https://api.congress.gov/ |
| Bill API contract in the official repository | https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/BillEndpoint.md |
| Member API contract in the official repository | https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/MemberEndpoint.md |

## Released bill endpoint

`GET https://api.congress.gov/v3/bill[/{congress}]`

The provider documents bill lists as sorted by date of latest action. Lists can
be scoped by Congress and, on a more specific route, bill type. List rows carry
Congress, type, number, title, origin chamber, latest action, update date,
update-date-including-text, and an API URL.

The API does **not** document a bill full-text query parameter. Navigator never
sends one: `q` fetches at most 250 list rows and filters their titles locally.
It is a recent-window discovery aid, not corpus search. The exact bill endpoint
and separate actions, amendments, committees, cosponsors, related bills,
subjects, summaries, text, and titles endpoints are provider capabilities but
not released as operations here.

## Released member endpoints

- `GET /member/{bioguideId}` — exact member detail.
- `GET /member/{stateCode}?currentMember=true` — current state membership.
- `GET /member/congress/{congress}` — member list for one Congress.

The official member contract says the unscoped `/member` list cannot be
filtered. Navigator therefore scopes name searches to one Congress and filters
the bounded response locally. For prior Congresses the provider specifically
recommends `currentMember=false` for complete data; current-Congress scans use
`currentMember=true`. Exact historical identity should use Bioguide ID.

Term and party history are dated. Redistricting can cause a member associated
with an earlier district to appear in some district-scoped data, so current
office claims require current-member and term checks.

## Authentication and reproducibility

Congress.gov requires a free api.data.gov key. Navigator accepts a
source-specific `congress` key or a shared `data_gov` key. Preserve operation,
Congress, filters, limit, returned identifiers, provider update dates, and
retrieval date.
