# European Parliament query guide

## Route the question

| Reporting need | Operation | Required follow-up |
|---|---|---|
| Resolve a current MEP | `search-meps` | Compare candidate IDs; then `get-mep` |
| Inspect a known MEP | `get-mep` | Verify role/date on the official profile |
| Discover plenary speech activities | `search-speeches` | Retrieve transcript/source material separately |
| Discover adopted Parliament texts | `search-adopted-texts` | Check procedure, Official Journal, and current legal status |
| Query votes, declarations, questions, or arbitrary documents | Not released | Stop or use another authorized workflow |

## Resolve an MEP

1. Search the current roster with country or group where justified.
2. Treat local name results as candidates and compare ID, full name, country,
   group, current memberships, and Parliament link.
3. Use `get-mep` for the chosen ID.
4. Check membership start and end dates; do not substitute current roster data
   for the person's role at a historical event.

## Research a speech

1. Use a distinctive phrase and the correct search language.
2. Add person or sitting-date filters only from known evidence.
3. Preserve activity ID, title, date/time, type, participant IDs, and link.
4. Resolve each participant and locate the actual transcript or audiovisual
   source before quoting or paraphrasing.

An activity title such as “Artificial Intelligence Act (debate)” is not the
speaker's words. Search hits may include procedural or written-statement
activities as well as debate speeches.

## Research an adopted text

1. Search with a precise concept and preferred language.
2. Inspect document ID, title, date, parliamentary term, and file manifestation.
3. Trace the relevant procedure and compare versions or amendments.
4. Check EUR-Lex and the Official Journal for enacted text, entry into force,
   later amendments, and consolidated status.

## No-result and provider-error recovery

- For people, relax group/country or spelling one field at a time.
- For speech/text search, check language and try a more specific or documented
  phrase. Preserve the changed scope.
- If the provider embeds an error, do not report zero results. Record the error,
  retry once only if transient, and narrow a problematic broad query if that
  still answers the research question.

## Reporting checklist

- Attribute European Parliament Open Data under CC BY 4.0.
- Preserve exact IDs, links, operation, filters, limit, offset, and search date.
- Separate current from historical membership.
- Separate activity metadata from transcript evidence.
- Separate Parliament adoption from legal publication and effect.
