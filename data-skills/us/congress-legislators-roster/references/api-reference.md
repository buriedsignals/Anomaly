# congress-legislators reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27 (https://github.com/unitedstates/congress-legislators),
plus live adapter runs the same day.

## Files used

| File | URL | Shape |
|---|---|---|
| legislators-current | https://unitedstates.github.io/congress-legislators/legislators-current.json | List of members: `id.bioguide`, `name.official_full`/`first`/`last`, `terms[]` (`type` sen/rep, `state`, `party`) |
| committees-current | https://unitedstates.github.io/congress-legislators/committees-current.json | List of committees: `thomas_id`, `name`, `type`, `subcommittees[]` (`thomas_id`, `name`) |
| committee-membership-current | https://unitedstates.github.io/congress-legislators/committee-membership-current.json | Map from committee ID (parent `thomas_id`, or parent + subcommittee `thomas_id`) to members: `bioguide`, `name`, `party` (majority/minority), `rank`, `title` |

Live counts on 2026-10-27: 539 legislators, 49 committees, 230 membership
lists, 3,895 seats.

## Mapping

- `legislators`: `bioguide_id` = `id.bioguide`; `name` = `official_full` (or
  first + last); `party`, `state`, `chamber` from the latest term.
- `committee_assignments`: `committee_name` from committees-current
  (subcommittees as `"<committee>: <subcommittee>"`, unknown IDs fall back to
  the ID); `role` = `title` or `Member`.

## Licence

The project is dedicated to the public domain (CC0 1.0). Membership is
scraped from House and Senate websites and is current only.
