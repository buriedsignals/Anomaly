# Congress Press reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27, plus live adapter runs the same day.

| Evidence | URL | Supports |
|---|---|---|
| Repository README | https://github.com/dwillis/congress-press | File layout, record format, daily updates, caveats |
| Licence | https://github.com/dwillis/congress-press/blob/main/LICENSE | MIT, Copyright (c) 2026 Derek Willis |
| Congressional Data Coalition write-up | https://congressionaldata.org/congress-press/ | Provenance and scope (26 years, 860+ members, ~675,000 releases) |
| ProPublica Congress API docs | https://projects.propublica.org/api-docs/congress-api/ | "ProPublica's Congress API is no longer available" |

## Files

`https://raw.githubusercontent.com/dwillis/congress-press/main/data/YYYY/YYYY-MM.jsonl`,
one JSON object per line:

`url`, `title`, `date`, `date_source`, `source`, `domain`, `scraper`,
`member` (`bioguide_id`, `name`, `party`, `state`, `chamber`), `text`,
`collected_at`, `updated_at`.

2026-09 on 2026-10-27: 17 MB, 4,059 releases.

## Mapping

`bioguide_id` = `member.bioguide_id`, `member_name` = `member.name`; `date`,
`title`, `text`, `url` as is.

## Caveats (README)

Not comprehensive (departed members, scraper gaps); `text` can be null (page
removed or JavaScript-rendered); `date` can be null with `date_partial`;
deduplication by URL only; extracted text can carry page boilerplate.
2001-2020 records come from the ProPublica import.
