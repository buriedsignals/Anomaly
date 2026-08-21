# Companies House company query guide

## Resolve a UK company

1. Search the most specific registered name or known number.
2. Compare company number, name, type, status, incorporation/cessation dates,
   address, and official link across candidates.
3. Retrieve the exact company number with `get-company`.
4. Preserve leading zeros and any letter prefix in notes and joins.
5. Check filings or other primary evidence when ownership, activity, or
   historical status matters.

## Pagination

Use `start_index` from zero and retain `items_per_page` and `total_results`.
Search results can change between pages. Do not use a huge sequence of detail
calls when a bounded search answers the question; respect 600 requests per five
minutes.

## No-result recovery

1. Confirm spelling, legal suffix, old name, and company-number formatting.
2. Try one distinctive fragment or the exact number.
3. Check whether the entity is a charity, unincorporated body, overseas entity,
   dissolved company, or another category outside ordinary search expectations.
4. Report exact term, page, date, and auth state.

## Interpret current status

`active` means the register reports active at observation time. It does not
prove trading, financial health, ownership, regulatory permissions, or
continuous activity on a past date. Use filing history, accounts, Gazette or
insolvency records, and dated primary evidence for those claims.

## Unreleased follow-ups

Officer, PSC, filing, charge, insolvency, and disqualification endpoints are
documented but not released. Do not pass raw paths or filters through this
skill. Route those needs to an authorized future operation or official site.

## Reporting checklist

- Preserve exact company number and official profile link.
- Record status observation date.
- Distinguish search snippet from registered-office profile.
- State when a claim requires officers, PSC, filings, or insolvency evidence.
- Honor OGL attribution and Companies House terms.
