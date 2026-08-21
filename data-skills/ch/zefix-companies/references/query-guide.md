# Zefix company query guide

## Resolve a Swiss company

1. Search the most specific registered-name spelling available.
2. Keep every plausible result; do not choose by rank alone.
3. Compare `uid`, `chid`, legal seat, status, spelling, and the cantonal excerpt.
4. Open `registry_url` and confirm the current legal record.
5. Record the query text, language, returned page metadata, and observation date.

The UID is the strongest released pivot. Use it to join only after confirming
that the candidate is the intended legal entity.

## Name variants

Try one change at a time and record it:

- accented and unaccented spelling;
- current and former legal name;
- with and without legal-form suffix;
- a distinctive core term rather than a long trading style.

Do not describe these as fuzzy-search techniques. The released legacy matching
algorithm is not established by current provider documentation.

## No-result recovery

1. Confirm that the target should be in the Swiss commercial register.
2. Check spelling, accents, legal form, and historical names.
3. Try one broader name variant and preserve the changed scope.
4. Search the official Zefix interface or relevant cantonal register manually
   when identity or currency is material.
5. Report the negative result as a bounded legacy name search.

## Endpoint-boundary rule

Do not copy filters or paths from the current ZefixPublicREST specification into
the legacy request. The successor API requires Basic credentials and is not a
released catalogue operation. If authenticated migration is authorized, it
requires a new adapter contract, fixtures, references, and live verification.

## Reporting checklist

- Attribute the candidate to Zefix and link the exact Zefix/cantonal record.
- Preserve UID and CH-ID punctuation as returned.
- State that search results were bounded and name matching is undocumented.
- Separate provider status from independent confirmation of active operations.
- Verify important status or ownership claims in the cantonal excerpt and SOGC.
