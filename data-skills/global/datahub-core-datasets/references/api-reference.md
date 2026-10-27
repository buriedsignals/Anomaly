# DataHub Core data package reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27.

| Evidence | URL | Supports |
|---|---|---|
| GDP dataset page | https://datahub.io/core/gdp | `_r/-/` file layout, CSV link, CC-BY-4.0 licence |
| GDP datapackage.json | https://datahub.io/core/gdp/_r/-/datapackage.json | `licenses`, `last_updated`, `resources[].path`, `schema.fields` |
| Country list page | https://datahub.io/core/country-list | ODC-PDDL-1.0 licence; `datapackage.yml` descriptor (the `.json` URL returned 404) |
| Core collection | https://datahub.io/core | Collection of Core datasets |

Not verified: CSV downloads (Firecrawl anti-bot refusal), DataHub terms of
use, and rate limits.

## URLs

- Package page: `https://datahub.io/core/<dataset>`
- Descriptor: `GET https://datahub.io/core/<dataset>/_r/-/datapackage.json`
- Resource: `GET https://datahub.io/core/<dataset>/_r/-/<resources[].path>`

No key. The adapter follows redirects and streams resources.

## Package fields used

`name`, `title`, `description`, `last_updated`, `licenses[]` (`name`, `path`,
`title`), `resources[]` (`name`, `path`, `format`, `schema.fields[].name`).
