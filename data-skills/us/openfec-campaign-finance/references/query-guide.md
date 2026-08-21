# OpenFEC entity query guide

## Candidate resolution

1. Search a distinctive name with office, state, and cycle when known.
2. Preserve `candidate_id`; do not merge office-specific IDs on name alone.
3. Compare office, district, party, cycles, election years, filing dates, and
   principal committee IDs.
4. Open the FEC candidate page and retrieve the proper reports/totals/receipts
   before making a financial claim.

## Committee resolution

1. Search current and historical name variants.
2. Resolve with `committee_id`, not the displayed name.
3. Check committee type, designation, state, cycles, treasurer, affiliation,
   candidate IDs, and first/latest filing dates.
4. Treat amendment and processing timing as part of the evidence chain; retain
   the underlying filing/image when the claim depends on a filed statement.

## Reporting and policy checklist

- Operation, exact filters, page/per-page, sort, and retrieval date.
- Candidate ID plus office, or committee ID plus type/designation.
- Nightly-update and filing-processing limitations.
- Registration/entity result clearly separated from financial activity.
- OpenFEC attribution; no implication of FEC endorsement.
- Intended reuse checked against current Terms, AUP, and contributor rules.
