# GLEIF LEI query guide

## Choose the narrowest mode

| Known evidence | Mode | Follow-up |
|---|---|---|
| Exact 20-character LEI | `lei` | Compare returned LEI and source record. |
| Exact or near-exact registered legal name | `legal_name` | Add legal jurisdiction when known. |
| Trading name, fragment, or uncertain term | `fulltext` | Treat all results as candidates. |

Do not use a broad full-text result when the request provides an exact LEI.

## Resolve an entity

1. Search with the narrowest justified mode and a small limit.
2. Compare legal name, legal jurisdiction, `registered_as`, legal address,
   entity category, and status.
3. Pivot `registered_as` into the relevant national company register.
4. Preserve the exact LEI and GLEIF source URL.
5. Record observation date and both entity and registration status.

Same-name results and shared addresses are not ownership evidence.

## No-result recovery

1. Validate the LEI length or legal-name spelling.
2. Remove legal jurisdiction only if it may have been misidentified.
3. Move from `legal_name` to `fulltext` for broader candidate discovery.
4. Search the relevant national register; the target may not have an LEI.
5. Report every changed filter and the bounded page searched.

## Status and currency

- `status` is the legal-entity layer supplied in the record.
- `registration_status` is the LEI-record layer.
- `next_renewal_date` is not a company dissolution or licence-expiry date.
- A current record does not establish historical status on another date.

## Ownership requests

The released operation does not traverse direct or ultimate parent relations.
Do not infer ownership from a company name, address, managing LOU, or identifier
similarity. Use a future documented Level 2 operation or another authoritative
ownership source.

## Reporting checklist

- Include the exact LEI and provider link.
- State filter mode, jurisdiction, page, and observation date.
- Preserve both status layers without conflation.
- Confirm national identifiers in the relevant primary register.
- State that GLEIF coverage is limited to LEI records.
