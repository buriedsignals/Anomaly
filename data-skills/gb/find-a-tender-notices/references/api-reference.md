# Find a Tender OCDS API reference

## Evidence checked

Primary UK government material was fetched with Firecrawl and checked against
the live API on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| Find a Tender data and API documentation | https://www.find-tender.service.gov.uk/Developer/Documentation | OCDS/record APIs, OCDS 1.1.5 profile, XML downloads, OGL |
| Release-package endpoint documentation | https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages | Exact inputs, cursor, date format, stages, response, 400/429/503 |
| UK open-contracting publication | https://www.gov.uk/government/publications/open-contracting | Official API URLs, filters, ID semantics and publication policy |
| OCDS EU profile | https://standard.open-contracting.org/profiles/eu/master/en/ | Mapping profile referenced by Find a Tender |

## Provider and released scope

Find a Tender publishes OCDS release packages and record packages plus daily
notice XML. The released catalogue operation covers collection release packages
only. Notice-ID/OCID detail and record-package history are roadmap items.

`GET https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages`

| catalogue field | Provider parameter | Contract |
|---|---|---|
| `limit` | `limit` | 1–100; provider default 100. When q is used the adapter fetches up to 100 before local filtering. |
| `cursor` | `cursor` | Opaque 1–300-character provider token from `links.next`. |
| `updatedFrom` | same | Earliest last-update timestamp, exactly `YYYY-MM-DDTHH:MM:SS`. |
| `updatedTo` | same | Latest last-update timestamp in the same format. |
| `stage` | `stages` | One of `planning`, `tender`, or `award`. |
| `q` | none | Local case-insensitive substring over tender JSON and buyer name on one fetched page. |

The adapter rejects reversed date windows, malformed cursor/date values, and
unsupported stages before sending a request.

## Pagination and identifiers

When more results exist, `links.next` supplies a URL containing the opaque next
cursor and the scope fields. catalogue returns both `next_url` and extracted
`next_cursor`. Preserve the same dates/stage and use only that token.

- `ocid`: procurement process identifier, shared across its releases.
- release `id`: unique within a procurement process and generally tied to a
  notice publication.
- party IDs: unique only within a release according to the provider docs.

Do not join parties globally on a release-local ID.

## Response mapping

| Normalized field | OCDS path | Interpretation |
|---|---|---|
| `ocid` | `release.ocid` | Procurement process pivot. |
| `release_id` | `release.id` | Specific release/notice identifier. |
| `name`, `description` | `tender.title`, `tender.description` | Tender-section text. |
| `buyer` | `buyer.name` | Release buyer display name. |
| `value_amount`, `value_currency` | `tender.value` | Tender-section value; not necessarily award/contract/payment. |
| `status` | `tender.status` | Tender-section status. |
| `tags` | `tag` | OCDS release stage/type signals. |
| `date` | `date` | Release date. |
| `source_url` | `/ocdsReleasePackages/{release_id}` | Exact official API release resource. |

The package also contains publisher, licence, extensions, publication policy,
package publication date, and links. catalogue preserves the package date and
next link in page metadata.

## Licence and service errors

Notice data is available under OGL v3.0 except where otherwise stated; the
site additionally attributes TED-derived schema/content. Preserve provenance,
licence, OCID, release ID, and notice source.

- 400: unrecognized or invalid parameter; correct it.
- 429: make no further request until at least the `Retry-After` seconds.
- 503: likewise honor `Retry-After`.
- Empty releases: valid bounded result for the exact page/window/stage.

## Known gaps and drift risks

- A procurement process can have many releases that amend or supersede data.
- Release packages are not the complete process history; record packages are
  designed for that purpose.
- Local term filtering is bounded to one page and is not upstream search.
- Tender, award, contract, and payment values are separate OCDS concepts.
- Buyer/supplier IDs can be release-local and supplied data can be incomplete.
- Notice mapping follows OCDS 1.1.5 with the provider's referenced extensions.
