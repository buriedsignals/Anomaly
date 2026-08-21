# Envirofacts query guide

## Resolve a TRI facility

1. Prefer exact `tri_facility_id` or `epa_registry_id` from prior evidence.
2. Otherwise combine state with a distinctive facility/city substring.
3. Compare address, parent company, coordinates, and closed indicator.
4. Record the identifier and retrieval date.
5. Query separate TRI release tables for chemical, year, medium, and quantity.

## Resolve a water system

1. Prefer an exact PWSID.
2. Otherwise use state plus system name/city.
3. Check activity/deactivation, system type, population, owner/source codes.
4. Use SDWIS monitoring/violation evidence or state primacy records for water
   quality and compliance questions.

## Reporting checklist

- Exact program table and query filters.
- Stable facility/PWS identifier and geographic resolution.
- Retrieval date and known name/ownership changes.
- Identity fields separated from release, violation, compliance, or safety claims.
- Appropriate follow-up dataset and primary evidence cited.
- No-result language limited to the queried table and provider coverage.
