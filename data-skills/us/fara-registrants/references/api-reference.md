# FARA.gov API reference

## Evidence checked

Fetched with Firecrawl on 2026-10-27, plus live adapter runs the same day.

| Evidence | URL | Supports |
|---|---|---|
| API home | https://efile.fara.gov/api/ | Scope: registrations, short forms, foreign principals |
| Endpoints | https://efile.fara.gov/ords/fara/r/fara_ws/api/endpoints | Registrants Active/Terminated/New, RegDocs, ForeignPrincipals; no authorization; ISO-8859-1; 5 requests per 10 s |
| Bulk data | https://efile.fara.gov/ords/fara/r/fara_ws/api/bulkdata | Bulk CSV/XML/JSON datasets as an alternative |

## Endpoints used

- `GET https://efile.fara.gov/api/v1/Registrants/json/Active`
- `GET https://efile.fara.gov/api/v1/Registrants/json/Terminated`

Responses (live 2026-10-27) are `{"REGISTRANTS_ACTIVE": {"ROW": [...]}}`
(or `REGISTRANTS_TERMINATED`); a one-row result is an object, not a list.
Row fields: `Registration_Number`, `Registration_Date`, `Termination_Date`
(terminated only), `Name`, `Business_Name`, `Address_1`, `Address_2`, `City`,
`State`, `Zip` (present only when set). Endpoints redirect; the adapter
follows redirects.

`documents_url` is `https://efile.fara.gov/api/v1/RegDocs/json/<number>`,
which lists the registrant's filed documents with PDF links (checked live for
registration 7785).

## Limits

5 requests per rolling 10 seconds (HTTP 429 when exceeded). No key. No
licence or reuse terms are stated on the API pages.
