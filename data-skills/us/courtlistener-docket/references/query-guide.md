# RECAP docket query guide

## Search workflow

1. Choose a distinctive party, case, or filing term.
2. Add a verified CourtListener court ID when jurisdiction is known.
3. Run `search-dockets` and record query, court, result count, and retrieval time.
4. Resolve the candidate using docket number, court, parties, dates, judge, and
   PACER identifiers.
5. Open `source_url` and any material filing link.
6. If `more_documents` is true, state that the embedded set is truncated and
   use an authorized full-docket workflow outside this skill if needed.

## Exact ID workflow

Use `get-docket` only with a CourtListener numeric docket ID. Do not pass a
PACER case ID or a formatted court docket number as though it were that ID.

## Reporting checklist

- Court and docket number, CourtListener docket ID, and PACER case ID if present.
- Exact query and court filter.
- Retrieval date and whether the count is approximate.
- Whether embedded filing matches were truncated.
- Linked primary docket/filing reviewed and any access or coverage gap.
- Contradictory parties, dates, or identifiers resolved before publication.

Say “not found in this RECAP search” rather than “the case/filing does not exist.”
