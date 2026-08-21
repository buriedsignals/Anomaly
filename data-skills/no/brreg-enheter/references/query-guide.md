# Brønnøysund entity query guide

## Task routing

| Need | Operation | Inputs |
|---|---|---|
| Resolve a Norwegian registered name | `search-companies` | `navn`, small `size`, page 0 |
| Retrieve a known main entity | `get-company` | exact `organisasjonsnummer` |
| Find a branch or workplace sub-unit | Not released | Do not treat main-entity results as complete |
| Enumerate or monitor the register | Not released | Use an authorized bulk/update workflow |

## Resolve a name

1. Search the most specific registered-name form with a small page.
2. Compare organisation number, legal form, business address, industry, and
   provider link across all plausible candidates.
3. Choose a candidate only with an external discriminator.
4. Retrieve the exact organisation number with `get-company` before relying on
   mutable fields.

The provider can return historical names and similarly named entities. Search
rank is not identity evidence.

## Organisation-number lookup

Remove display spaces only when the underlying identifier is clearly nine
digits. Preserve leading zeros. Do not send names through the detail field or
guess a check digit.

## No-result recovery

1. Confirm spelling, legal suffix, and historical name.
2. Try a shorter provider name query, one change at a time.
3. Check whether the target is a sub-entity rather than a main entity.
4. Confirm the exact identifier through another primary record.
5. Report searched operation, name, page, size, and observation date.

## Interpret mutable fields

- Treat `employees` as the value currently supplied by the register, not a
  historical time series or independently audited headcount.
- Treat `bankrupt` as a point-in-time provider flag, not a legal conclusion
  detached from the record date and proceedings.
- Treat industry codes as classifications, not proof of all business activity.
- Do not normalize an unverified provider website into proof of ownership.

## Reporting checklist

- Preserve and show the nine-digit organisation number.
- Link the exact API record.
- Record query page and observation date.
- Say whether the result is a main entity.
- Seek a second primary record for consequential ownership, insolvency, or
  historical claims.
