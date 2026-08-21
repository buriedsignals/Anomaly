# EPA Envirofacts DMAP API reference

## Evidence checked

The current official page was fetched with Firecrawl on 2026-08-12:

- https://www.epa.gov/enviro/envirofacts-data-service-api

That page was last updated by EPA on June 2, 2026. Live read-only calls verified
the two schema-qualified tables used below.

## Current service grammar

Base: `https://data.epa.gov/dmapservice`

Documented shape:

```text
/<program.table>/<column>/<operator>/<value>/[and|or/...]/<first>:<last>/sort/<column>:<direction>/json
```

Important current details:

- Table names are schema-qualified (`program.table`).
- First record numbering begins at 1.
- Text comparisons are case-insensitive.
- Available operators include `equals`, `notEquals`, `lessThan`,
  `lessThanEqual`, `greaterThan`, `greaterThanEqual`, `beginsWith`, `endsWith`,
  `contains`, `excludes`, `like`, `notLike`, `in`, and `notIn`.
- The service allows joins and many output formats, but this skill deliberately
  releases only bounded JSON queries without arbitrary joins.
- EPA limits each request to completion under 15 minutes and recommends paging
  when more data is needed.

The earlier `/efservice` route still responded during the audit, but EPA's
current documentation specifies `/dmapservice`; catalogue now uses the current
contract rather than relying on the legacy route.

## Released tables

### TRI facilities

`tri.tri_facility`

Filters: `tri_facility_id`, `state_abbr`, `facility_name`, and `city_name`.
Rows expose identity/location, EPA registry ID, parent-company fields, preferred
coordinates, and closed indicator. They do not include chemical/release facts.

### Public water systems

`sdwis.water_system`

Filters: `pwsid`, `state_code`, `pws_name`, and `city_name`. Rows expose system
type/activity, population, connections, source and owner codes, location, and
deactivation date. They do not establish compliance, current test results, or safety.

## Scope and provenance

Envirofacts aggregates data from many EPA systems and state/local submissions.
Preserve the program table, identifier, filter, and retrieval date. Use EPA
metadata and the underlying program's documentation to interpret codes and
freshness. Facility and system names/owners can change; resolve with IDs.
