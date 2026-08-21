# Federal Register document query guide

## Search codes

| Research need | `type` |
|---|---|
| Final rule | `RULE` |
| Proposed rule | `PRORULE` |
| Agency notice | `NOTICE` |
| Presidential document | `PRESDOCU` |

Use a provider agency slug such as `environmental-protection-agency`, not an
abbreviation such as `EPA`, when filtering by agency.

## Discovery workflow

1. Search the most distinctive term or phrase with a small page.
2. Add document type and agency only when the reporting question supplies that
   scope.
3. Preserve document number, type, agency, publication date, both URLs, and
   search page metadata.
4. Open the govinfo PDF and locate the relevant section before quoting or
   characterizing the legal text.
5. Check related proposed rules, final rules, corrections, delays, withdrawals,
   and judicial or statutory developments before claiming current effect.

## Rulemaking timeline discipline

Do not collapse these events:

- proposal publication;
- comment deadline;
- final-rule publication;
- effective date;
- compliance date;
- amendment, delay, correction, withdrawal, or termination.

Use `publication_date` only for publication. Treat `effective_on` as provider
metadata that still requires verification in the official PDF.

## No-result recovery

1. Confirm the 1994 coverage boundary.
2. Check terminology, acronyms, chemical names, docket number, and RIN in other
   official sources.
3. Remove agency and type one at a time.
4. Try a broader term and record the changed scope.
5. Report term, filters, order, page, page size, date searched, and result count.

An empty search does not prove that no rule, notice, or older Federal Register
document exists.

## Official-text verification

`source_url` is useful for readable discovery and metadata. For consequential
claims, use `official_pdf_url`, confirm document number and page, and cite the
specific official text. Inspect attachments or incorporated material under
their own authority and rights.

## Reporting checklist

- Preserve document number and agency.
- Distinguish type code from returned human-readable type.
- State publication and effective dates separately.
- Cite the govinfo PDF for legal text.
- State the bounded search scope and 1994 coverage limit.
- Check whether later documents changed the rule's status.
