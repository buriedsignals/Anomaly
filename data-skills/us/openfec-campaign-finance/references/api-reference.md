# OpenFEC candidate and committee API reference

## Evidence checked

Primary FEC material was fetched with Firecrawl on 2026-08-12:

| Evidence | URL |
|---|---|
| FEC API overview | https://www.fec.gov/data/open-government-data/ |
| Official OpenAPI/Swagger document | https://api.open.fec.gov/swagger/ |
| Terms of Service | https://github.com/fecgov/FEC/blob/master/TERMS-OF-SERVICE.md |
| Acceptable Use Policy | https://github.com/fecgov/FEC/blob/master/OPENFEC-ACCEPTABLE-USE-POLICY.md |
| Individual contributor information guidance | https://www.fec.gov/updates/sale-or-use-contributor-information/ |

The OpenAPI document is the parameter and response contract used by the
adapter. The FEC overview says API data are updated nightly and records are tied
to underlying forms by file or image identifiers.

## Candidate search

`GET https://api.open.fec.gov/v1/candidates/search/`

Released parameters are `q`, `state`, `party`, `cycle`, `office`,
`election_year`, `candidate_status`, `incumbent_challenge`,
`is_active_candidate`, `sort`, `page`, and `per_page` (1–100). The provider also
offers identifier, filing-date, district, year, and fund-status filters that are
not exposed here.

A candidate ID identifies a registration for an office, not a universal person:
one person running for multiple offices can have multiple candidate IDs. Cycles
are two-year election cycles. Use filing dates and principal committee IDs for
follow-up rather than treating a name match as resolved identity.

## Committee search

`GET https://api.open.fec.gov/v1/committees/`

Released parameters are `q`, `state`, `party`, `cycle`, `year`,
`committee_type`, `designation`, `filing_frequency`, `treasurer_name` (exposed
as `treasurer`), `sort`, `page`, and `per_page` (1–100). The OpenAPI explicitly
states that committee names are not unique and recommends `committee_id` for
record lookup.

The normalized row preserves full and coded committee type/designation,
organization type, frequency, candidate and sponsor IDs, cycles, treasurer,
affiliation, and first/latest filing dates. It does not contain financial totals
or transactions.

## Authentication and use policy

A free api.data.gov key is required. Navigator accepts `openfec` or a shared
`data_gov` key. The FEC asks services to identify OpenFEC as the data source and
not imply FEC endorsement.

The current Acceptable Use Policy prohibits listed conduct and includes a broad
commercial-use restriction. Federal campaign-finance law separately restricts
sale or use of individual-contributor information for solicitation or
commercial purposes; the FEC describes limited exceptions such as bona fide
news/publication uses whose principal purpose is not solicitation or commercial
activity. This is a source summary, not legal advice: check the linked current
policies for the intended use. Contributor data are outside this skill's release.
