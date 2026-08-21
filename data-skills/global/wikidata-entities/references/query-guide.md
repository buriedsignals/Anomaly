# Wikidata entity-resolution guide

## Resolve candidates, not conclusions

1. Search the best-known label in the appropriate language and entity type.
2. Compare all returned IDs, descriptions, and match metadata.
3. Follow `next_continue` when plausible candidates may occur beyond one page.
4. Open the selected entity and inspect statements, references, qualifiers, and
   external identifiers through a separately capable tool.
5. Confirm consequential identity claims against primary records.

```bash
navigator query global/wikidata/entities --operation search-entities \
  --input '{"q":"OpenAI","language":"en","type":"item","limit":10}'
```

For a property rather than an item:

```bash
navigator query global/wikidata/entities --operation search-entities \
  --input '{"q":"official website","language":"en","type":"property","limit":10}'
```

Continue an unchanged search scope:

```bash
navigator query global/wikidata/entities --operation search-entities \
  --input '{"q":"Mercury","language":"en","type":"item","limit":10,"continue":10}'
```

Use only the returned offset; do not infer or skip arbitrary values when a
reproducible page sequence matters.

## Disambiguation checks

- A label match can be an alias rather than the displayed label; preserve
  `match`, `match_type`, and `match_language`.
- Descriptions are concise community-edited clues, not authoritative evidence.
- `strictlanguage: true` can exclude useful fallback candidates; state when it
  was used.
- Items and properties are different entity types; QIDs and PIDs are not
  interchangeable.
- A first-ranked result is not an identity decision.

## Reporting checklist

- Preserve query, language, type, pagination offsets, candidate IDs, and
  retrieval time.
- State the basis for selecting one candidate over alternatives.
- Cite primary sources for facts obtained after resolution.
- Treat changes, vandalism, sparse descriptions, and missing statements as
  possible; do not turn a Wikidata absence into a universal negative claim.
