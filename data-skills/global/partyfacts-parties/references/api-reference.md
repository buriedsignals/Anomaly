# Party Facts download tables reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27.

| Evidence | URL | Supports |
|---|---|---|
| Download page | https://partyfacts.herokuapp.com/download/ | Table URLs, UTF-8 encoding, Dataverse stable versions, `partyfacts_id` as merge key |
| Codebook | https://partyfacts.herokuapp.com/documentation/codebook/ | Column definitions, inclusion thresholds, core vs. external parties |
| Dataverse 2023 stable version | https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/TJINLQ | CC0 1.0 licence, file sizes and row counts |
| Party page and list filter | https://partyfacts.herokuapp.com/data/partycodes/1/ | Alpha-3 country codes (`?country=BIH`), three external links for ID 1 |
| Data import repository | https://github.com/hdigital/partyfactsdata | MIT licence for the repository software |

Not verified: the CSV downloads themselves (Firecrawl refused them as
anti-bot), so the live header rows are taken from the codebook, and the CSV
`country` column is assumed to use the same alpha-3 codes as the web filter.

## Endpoints

| Table | URL |
|---|---|
| Core parties | `GET https://partyfacts.herokuapp.com/download/core-parties-csv/` |
| External parties | `GET https://partyfacts.herokuapp.com/download/external-parties-csv/` |
| Countries (not released) | `GET https://partyfacts.herokuapp.com/download/countries-csv/` |
| Datasets (not released) | `GET https://partyfacts.herokuapp.com/download/datasets-csv/` |

No key. The adapter streams the table, follows redirects, and filters locally.

## Columns (codebook)

Core parties: `country`, `partyfacts_id`, `technical`, `name_short`, `name`,
`name_english`, `name_other`, `year_first`, `year_last`, `share`,
`share_year`, `new`, `wikipedia`, `description`, `comment`, `created`,
`modified`.

External parties: `country`, `dataset_key`, `dataset_party_id`, `name_short`,
`name`, `name_english`, `year_first`, `year_last`, `share`, `share_year`,
`description`, `comment`, `created`, `modified`, `external_id`,
`partyfacts_id`.

## Licence

The Dataverse stable versions are CC0 1.0. The live download page states no
separate licence. The MIT licence on GitHub covers the import repository's
software. Cite Döring and Regel (2019), Party Politics 25(2): 97–109,
doi:10.1177/1354068818820671, as the codebook requests.
