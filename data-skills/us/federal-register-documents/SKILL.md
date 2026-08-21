---
name: federal-register-documents
description: >-
  Use this skill to search FederalRegister.gov documents since 1994 by term,
  type, and agency with ordering and pagination. Apply it to discovery of US
  rules, proposed rules, notices, and presidential documents; verify material
  legal text against the linked govinfo PDF because FederalRegister.gov is an
  unofficial prototype edition.
compatibility: Requires the catalogue CLI, Python 3.11+, and network access to www.federalregister.gov.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/federal-register/documents
---

# Search FederalRegister.gov documents

Use only released operations and treat `meta.yaml` as the executable contract.

<!-- BEGIN GENERATED OPERATION STATUS -->
## Current catalogue release status

`meta.yaml` is authoritative. Execute only operations listed as **Released** below;
other sections in this playbook may document provider or unreleased adapter scope.

**Released**

- `us/federal-register/documents:search-documents` — Search documents by term with optional documented type and agency filters, ordering, and page controls.
<!-- END GENERATED OPERATION STATUS -->
## Workflow

1. Assess the complete request and inspect the released contract:

   ```bash
   catalogue data assess "<complete question>" --json
   catalogue data show us/federal-register/documents:search-documents
   ```

2. Search with explicit document codes and bounded pagination:

   ```bash
   catalogue query us/federal-register/documents --operation search-documents \
     --input '{"q":"PFAS","type":"PRORULE","agency":"environmental-protection-agency","order":"newest","per_page":10,"page":1}'
   ```

3. Preserve document number, document type, agencies, publication and effective
   dates, page metadata, and both URLs. Open `official_pdf_url` before quoting
   or relying on legal text.

## Source boundary

The released operation wraps document search. Provider detail, facets, issues,
agencies, public-inspection documents, images, and suggested searches remain
unwrapped. The provider states that FederalRegister.gov XML is not the official
legal edition; [the API reference](references/api-reference.md) records that
boundary and the primary documentation.

## Interpretation cautions

- `RULE`, `PRORULE`, `NOTICE`, and `PRESDOCU` are provider codes.
- Search coverage begins in 1994; an empty result says nothing about earlier
  Federal Register material.
- Publication date is not effective date, compliance date, or legal status.
- Search excerpts and abstracts are discovery aids, not substitutes for the
  official PDF and incorporated material.

## Bundled resources

- [API reference](references/api-reference.md) — official OpenAPI contract,
  prototype warning, filters, paging, and response mapping.
- [Query guide](references/query-guide.md) — rulemaking search and verification patterns.
- `scripts/verify.py` and `assets/verification-cases.json` — bounded live checks.
- `evals/evals.json` — forward agent-behavior cases.

```bash
python3 scripts/verify.py --list
python3 scripts/verify.py
```
