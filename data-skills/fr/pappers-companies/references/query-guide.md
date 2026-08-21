# Pappers company query guide

## Resolve a company credit-efficiently

1. Search a distinctive legal-name fragment with `par_page` 3–5.
2. Compare SIREN, name, legal form, NAF, address, status, and source link.
3. Retrieve only the selected nine-digit SIREN.
4. Verify consequential fields against INSEE, INPI/RNE, BODACC, or another
   appropriate French primary record.
5. Record operation, page, result count, credit implication, and observation date.

Do not retrieve a full profile for every loose name match unless the user has
authorized the credit cost and the research question requires it.

## SIREN and SIRET

- SIREN: nine digits, identifies the legal unit; released for detail.
- SIRET: fourteen digits, identifies an establishment; not a released input.

Preserve leading zeros. Do not truncate a SIRET into a SIREN unless the source
and task clearly establish that transformation.

## No-result recovery

1. Confirm accents, legal suffix, current/former denomination, and SIREN digits.
2. Try one narrower or broader name variant and record it.
3. Check partial-diffusion and source-coverage limitations.
4. Use an official French register to confirm the entity and identifier.
5. Report 404/no-result as bounded provider evidence.

## Pagination and ownership boundaries

Ordinary pages cover only the first 400 matches. Do not call them exhaustive.
Provider cursor search is not released. Officers, beneficial owners, accounts,
documents, and BODACC publications require separate operations; never smuggle
them through extra parameters. Beneficial-owner access can also require lawful
authorization.

## Reporting checklist

- Preserve SIREN and Pappers link.
- State retrieval date and source integration limitations.
- Distinguish employee-band label from code.
- Treat null diffusion fields as unknown.
- Verify status, ownership, or legal-proceeding claims in the primary register.
