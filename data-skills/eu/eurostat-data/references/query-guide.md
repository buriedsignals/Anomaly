# Eurostat query guide

## Select the dataset before the value

1. Search dataflows with a precise statistical concept.
2. Compare candidate datacodes and titles; open the Data Browser link.
3. Inspect dimensions, unit, population, geography, frequency, seasonal
   adjustment, price basis, and methodology.
4. Choose a code only when those dimensions match the reporting question.

A plausible title is not enough. “Youth unemployment rate” and “youth
unemployment ratio” have different denominators.

## Build a bounded observation slice

Prefer component filters when dimension order is not known:

```json
{
  "dataset_code": "DEMO_GIND",
  "filters": {
    "FREQ": "A",
    "INDIC_DE": "POPTRT",
    "GEO": ["FR", "DE"],
    "TIME_PERIOD": "ge:2018+le:2023"
  },
  "limit": 100
}
```

Estimate scope from dimension cardinalities before increasing it. A local
`limit` does not protect the provider from an enormous cube request.

## Interpret an observation

Read together:

- dataset label and datacode;
- all dimension codes and labels;
- `unit` and frequency;
- time period and geography;
- `value`;
- `status` and `status_label`; and
- provider update time plus retrieval date.

Do not aggregate rates, indexes, seasonally adjusted values, or different units
without an explicit statistically valid method.

## No-result recovery

1. Confirm the datacode and current data structure.
2. Check each code against its codelist and preserve case.
3. Remove one component filter at a time.
4. Check whether the requested time/geography combination is represented.
5. Distinguish an empty cube from a provider error and report the exact slice.

## Revisions and comparisons

Record the access date because Eurostat can revise current values. This API
does not establish what the value was on an earlier retrieval date. Archive
source outputs when revision comparison is part of the reporting question.

## Reporting checklist

- Cite DOI or datacode link and access date.
- Preserve all dimensions, unit, status, and update/retrieval date.
- State any truncation or asynchronous limitation.
- Check dataset-specific methodology and reuse exceptions.
- Separate provider value from calculations and explain transformations.
