# CourtListener judicial-person API reference

## Evidence checked

Primary provider pages were fetched with Firecrawl on 2026-08-12:

- REST API v4.6: https://www.courtlistener.com/help/api/rest/v4/
- American Judge and Justice API: https://www.courtlistener.com/help/api/rest/v4/american-judge-and-justice-api/
- Legal Search API: https://www.courtlistener.com/help/api/rest/v4/search/
- API root: https://www.courtlistener.com/api/rest/v4/
- Terms: https://www.courtlistener.com/terms/

Live `OPTIONS /api/rest/v4/people/` confirmed current person fields. Live search,
list-filter, and detail calls verified both upstream result shapes.

## Released modes

### Free-text discovery

`GET /api/rest/v4/search/?type=p&q=<name>`

The search index returns names, aliases, demographic labels, education names,
ABA ratings, political affiliations, and nested position summaries. These are
search-index documents with relevance metadata.

### Database name filtering

`GET /api/rest/v4/people/?name_first=<value>&name_last=<value>`

This returns database records, including nested education/affiliation/rating
objects and linked position URLs.

### Exact person

`GET /api/rest/v4/people/<person_id>/`

Use after resolving one CourtListener identifier. Positions remain links and
need the separate positions API for complete records; that expansion is not
released here.

## Material caveats from the provider

- The dataset is person-centric and includes judges, appointers, and other
  justice-system roles. A person record alone does not prove a judicial office.
- `is_alias_of` marks nickname/alias records. Usually the canonical record has
  a null value.
- Race and gender are **not self-reported**; the provider calls them best
  guesses and says values may be incorrect.
- Date granularity fields express how much is actually known. A stored
  `2010-01-01` with `%Y` granularity means only 2010 is known.
- Some Follow The Money fields have not been updated in many years.

## Authentication and use

Public experimentation can work keylessly, but CourtListener asks deployed
clients to authenticate using `Authorization: Token <token>`. Default
authenticated limits are currently 5/minute, 50/hour, and 125/day. Terms ban
FCRA uses and credential/rate-limit evasion. This skill does not grant a blanket
right to redistribute the provider's compilation.
