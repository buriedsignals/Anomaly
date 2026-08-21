# Eurostat SDMX 3.0 API reference

## Evidence checked

Primary Eurostat material was fetched with Firecrawl and checked against the
live dissemination service on 2026-08-12.

| Evidence | URL | Supports |
|---|---|---|
| SDMX 3.0 getting started | https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started/sdmx3.0 | Dataflow, structure, codelist, key, filtering, and response-format model |
| SDMX 3.0 data-query guidelines | https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/sdmx3-0/data-query | Exact path, `c` semantics, operators, observation windows, formats, asynchronous behavior |
| SDMX 3.0 structure-query guidelines | https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/sdmx3-0/structure-queries | Dataflow discovery and structure-detail parameters |
| Eurostat copyright and reuse notice | https://ec.europa.eu/eurostat/help/copyright-notice | Source acknowledgment, commercial/non-commercial reuse, exceptions, citation format |

## Provider and released scope

Eurostat exposes SDMX data, dataflows, data structures, concepts, codelists,
constraints, metadata, several output formats, and a separate asynchronous
workflow for large results. Navigator releases:

| Operation | Provider request | Adapter behavior |
|---|---|---|
| `search-datasets` | `GET /structure/dataflow/ESTAT/*/1.0?detail=allstubs&compress=false` | Parses all current dataflow stubs, then matches code/name/description locally. |
| `get-observations` | `GET /data/dataflow/ESTAT/{code}/{version}/{key?}` | Sends component filters, requests JSON-stat 2.0, and flattens bounded positions. |

`DS-` Comext/Prodcom codes route to the official Comext SDMX base. Structure
and codelist lookup are documented provider capabilities but not released
operations.

## Dataset discovery

Search is a local case-insensitive substring over dataflow code, multilingual
names, and descriptions returned by one official structure request. Results are
sorted by datacode and locally paged with `offset` and `limit`.

Annotations may provide observation count, oldest/latest period, update time,
and metadata URL. They are nullable; their absence does not mean no data or no
metadata exists.

## Observation request

Path form:

```text
/data/dataflow/ESTAT/{dataset_code}/{version}/{key}
```

| Navigator input | Provider form | Semantics |
|---|---|---|
| `key` | path key | Dimension values in data-structure order; `*` wildcard and trailing omission supported. |
| `filters.DIM` | `c[DIM]` | Order-independent component filter. |
| array filter | comma-separated values | OR, such as `c[GEO]=FR,DE`. |
| time range | operators joined with `+` | Example `ge:2018+le:2023`. |
| `first_n_observations` | `firstNObservations` | Oldest N observations per matching series. |
| `last_n_observations` | `lastNObservations` | Latest N observations per matching series. |

Do not repeat a dimension constrained in an ordered key as a component filter.
`firstNObservations` and `lastNObservations` are mutually exclusive.

The adapter requests JSON-stat 2.0 and `compress=false`. It validates dataset,
version, key, and dimension syntax; requires a scoped key or filters unless
`allow_full_dataset` is explicit; and always rejects unfiltered `DS-` downloads.

## Output semantics

The JSON-stat cube declares dimension IDs, sizes, category indexes/labels,
values, and optional status positions. The adapter returns each value- or
status-bearing position with:

- datacode, dataset label, and provider update timestamp;
- dimension codes and labels;
- time period and unit when identifiable;
- value, including `null` when the provider supplies only a status;
- status code and provider status label; and
- a Data Browser source link.

Missing cube positions are not automatically zero. A provisional, estimated,
confidential, break-in-series, or other status must travel with the value.

## Size and asynchronous limits

Eurostat documentation says potentially large requests are delivered
asynchronously. Provider guidance describes estimated 500,000–5,000,000-cell
queries moving to asynchronous delivery and larger requests being rejected.
Navigator does not implement that workflow. Its `limit` truncates normalized
output and cannot make a broad upstream request cheap.

## Reuse

Eurostat authorizes commercial and non-commercial reuse of statistical data,
metadata, publications, and tools when the source is acknowledged, subject to
specific exceptions. Third-party material, logos/trademarks, certain non-EU or
non-EFTA geography data, and specified trade data require extra care. The
official citation examples use dataset DOI or datacode link plus access date.

## Known gaps and drift risks

- The dissemination API serves current observations, not a full revision archive.
- Dataset structures, codelists, labels, and values can change.
- Dataset discovery metadata annotations are often absent.
- A local result cap can hide valid later cube positions.
- Status-only positions and sparse cubes require source-aware interpretation.
- Dataset-specific reuse exceptions override general permission.
