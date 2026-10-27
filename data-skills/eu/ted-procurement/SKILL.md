---
name: ted-procurement
description: >-
  Use this skill to search published Tenders Electronic Daily procurement
  notices with TED expert syntax or validated CPV and buyer-country shortcuts.
  Apply it to bounded EU tender and award-notice discovery; do not infer an
  executed contract, winning supplier, or award value from the normalized
  search fields.
compatibility: Requires Python 3.11+ and network access to api.ted.europa.eu.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: eu/ted/notices
---

# Search published TED notices

`meta.yaml` is the executable contract. Use only released operations.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `eu/ted/notices:search-notices` — Run a bounded TED expert query, optionally constructed from validated CPV and buyer-country shortcuts.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete question and inspect the operation:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show eu/ted/notices:search-notices
   ```

2. Prefer validated shortcuts for a simple CPV/country question; use expert
   syntax only when the exact TED field semantics are known:

   ```bash
   catalogue query eu/ted/notices --operation search-notices \
     --input '{"cpv":"72000000","country":"DE","only_latest_versions":true,"limit":10,"page":1}'
   catalogue query eu/ted/notices --operation search-notices \
     --input '{"query":"classification-cpv=45000000 AND buyer-country=ESP","scope":"ALL","limit":10,"page":1}'
   ```

3. Preserve the exact expert query, scope, version setting, page, notice number,
   publication date, buyer metadata, and official notice link.

## Provider and release boundary

Published-notice search is anonymous. TED's validation, publication, management,
and preview APIs concern unpublished notice workflows and require credentials;
they are outside this skill. Search API v3 also documents XML download and
iteration-token pagination, but catalogue currently releases page-number mode
only. That mode retrieves at most 15,000 notices; the adapter caps each page at
100 even though the provider permits 250.

## Interpretation cautions

- CPV is hierarchical; a code's breadth changes the search meaning.
- Alpha-2 country shortcuts are converted to TED's alpha-3 values.
- Multilingual fields prefer English and otherwise fall back to the first value.
- The normalized fields do not establish notice subtype, contract execution,
  winner, lot structure, currency, or award value. Open `source_url` and inspect
  the full notice.

## Procurement contract mapping (not implemented)

This adapter does not fill `domains/procurement.yaml`; its search fields do not
carry winners or values. An agent reading full eForms notices (XML) can map
them as the OCDS for eForms profile does
(https://standard.open-contracting.org/profiles/eforms/latest/en/mapping/,
read 2026-10-27):

| If the notice publishes | map it to column |
|---|---|
| BT-105 Procedure Type (via the profile's procedure-type table; not set for oth-mult, oth-single) | `procurement_method` |
| BT-262 Main Classification Code (CPV) | `category_code` |
| BT-27 Estimated Value | `tender_value` |
| BT-131 Deadline Receipt Tenders | `tender_deadline` |
| BT-759 Received Submissions Count, per lot result | `number_of_tenderers` |
| BT-720 Tender Value of the winning tender | `award_value` |
| BT-145 Contract Conclusion Date | `award_date` |
| Winning tenderer organisation (OPT-300 / OPT-310 references) | `supplier_id`, `supplier_name` |

Read [the API reference](references/api-reference.md) for the official OpenAPI
constraints and [the query guide](references/query-guide.md) for procurement
evidence chains.

## Bundled resources

- `references/api-reference.md` — provider scope, request schema, pagination,
  response mapping, and reuse.
- `references/query-guide.md` — CPV/country construction and notice interpretation.
- `scripts/verify.py` with `assets/verification-cases.json` — live checks.
- `evals/evals.json` — agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
