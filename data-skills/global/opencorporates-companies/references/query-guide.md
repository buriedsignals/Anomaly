# OpenCorporates company-resolution guide

## Search candidates

Start with the registered or best-known name and a small page. Add the expected
jurisdiction only when justified.

```bash
catalogue query global/opencorporates/companies --operation search-companies \
  --input '{"q":"Barclays","jurisdiction_code":"gb","per_page":10,"page":1}'
```

Compare:

- jurisdiction and company number;
- legal name and previous names;
- address, company type, and incorporation date;
- current status and inactive mapping;
- publisher, source retrieval/update dates, and official registry link.

Do not select the first result on name alone. Similar or identical names can
exist in multiple jurisdictions and across historical entities.

## Exact lookup

When both provider jurisdiction and registry number are known:

```bash
catalogue query global/opencorporates/companies --operation get-company \
  --input '{"jurisdiction_code":"gb","company_number":"00102498"}'
```

Keep company numbers as strings. Preserve leading zeroes, punctuation, and the
returned jurisdiction code. If exact lookup fails, confirm the official
register's formatting before falling back to name search.

## Pagination and absence

- Page and per-page limits are explicit; page 100 is the provider ceiling.
- Record the total count and page scope.
- A no-result response can reflect alternate names, branch forms, jurisdiction
  choice, source lag, or missing coverage.
- Do not claim all companies were searched beyond the exposed provider window.

## Status and official verification

Use `status` only as the returned `current_status`. Report `inactive`
separately. For a time-sensitive legal-status claim, open `registry_url` or
`source_registry_url` and verify the current official record. State the source
retrieval date if the aggregated record is older.

This skill does not expose officers, beneficial ownership, filings, or full
corporate networks. Route those questions to a capable source rather than
inferring them from name, address, or group references.

## Reporting checklist

- Legal name, jurisdiction code, and exact company number.
- Search terms, filters, page, and result window.
- `status` and `inactive` reported without conflation.
- OpenCorporates and official registry URLs.
- Source publisher, retrieval/update timestamps, and source terms.
- Independent official-register corroboration for consequential current facts.
- ODbL attribution and share-alike assessment for downstream reuse.
