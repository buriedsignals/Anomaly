# OCCRP Aleph entity-query guide

## Search and resolve

1. Start with a small, schema-filtered search when the expected entity type is
   known.
2. Compare names, countries, collection labels, and stable IDs across all
   candidates.
3. Inspect the candidate's source collection and underlying record.
4. Retrieve the exact ID only after documenting the resolution basis.

```bash
catalogue query global/occrp-aleph/entities --operation search-entities \
  --input '{"q":"Gazprom","schema":"Company","limit":10,"offset":0}'
```

If the expected collection is known and readable, add `collection_id`. Do not
use a guessed collection ID, and do not infer that a no-result response covers
collections the account cannot read.

Continue with the returned offset and unchanged filters when another page is
needed. Preserve query, schema, collection filter, offset, account scope, and
retrieval time.

## Exact retrieval

```bash
catalogue query global/occrp-aleph/entities --operation get-entity \
  --input '{"entity_id":"<exact-id>"}'
```

An ID is provider-specific and can expose sensitive collection context. Quote
it through JSON input rather than interpolating scraped content into a shell
command.

## Bounded relation expansion

```bash
catalogue query global/occrp-aleph/entities --operation expand-entity \
  --input '{"entity_id":"<exact-id>","limit":10,"properties":["directorshipDirector"]}'
```

For each returned record:

- retain the `relation` name and `relation_count`;
- inspect the source and intermediate edge entity where relevant;
- distinguish a person, company, document, asset, address, or relationship
  schema;
- verify whether the relationship is current, historical, alleged, extracted,
  or manually entered;
- avoid recursive expansion unless the research question and depth/size bound
  are explicit.

## No-result and error handling

- Remove only a filter that was genuinely optional.
- Check spelling, aliases, entity type, and offset.
- Confirm the account can see the expected collection.
- Treat a broad upstream 500 as a cue to narrow schema/collection, not to issue
  an even larger query.
- A 403 or absent private record is an access boundary, not evidence of absence.

## Reporting checklist

- Exact Aleph entity ID and link.
- Search query, schema, collection filter, limit, and offset.
- Collection label/ID and source-document provenance.
- Relation property and the evidence supporting its interpretation.
- Retrieval date and account-access boundary.
- Collection-specific sensitivity, licence, and republication assessment.
- Independent primary records used to corroborate identity or consequential
  claims.
