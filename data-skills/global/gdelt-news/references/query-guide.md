# GDELT coverage query guide

## Build a bounded discovery query

1. Put exact names or phrases in quotes.
2. Add documented operators inside the query for outlet country, language,
   domain, exclusions, or themes.
3. Set a relative or exact time scope; never both.
4. Choose a sort that matches the question and a deliberate record limit.
5. Open and verify the returned reporting and its primary evidence.

```bash
catalogue query global/gdelt/news --operation search-news \
  --input '{"query":"\"climate change\" sourcecountry:france","timespan":"3d","sort":"DateDesc","maxrecords":25}'
```

For an exact interval:

```bash
catalogue query global/gdelt/news --operation search-news \
  --input '{"query":"\"OpenAI\"","startdatetime":"20260801000000","enddatetime":"20260812235959","sort":"DateAsc","maxrecords":50}'
```

## Interpret fields correctly

- `source_country` classifies the source/outlet, not the event or people in the
  article.
- `seen_date` is GDELT's observation timestamp, not necessarily the first
  publication time.
- `language` and translated search behavior are provider classifications.
- `HybridRel` includes provider relevance and outlet-popularity signals.
- `social_image` is a publisher link, not a verified depiction of the story.

## Completeness boundary

ArticleList is a ranked, capped page with no cursor. Even at `maxrecords: 250`,
it cannot establish:

- every article about a subject;
- no coverage outside the monitored/indexed corpus;
- no match beyond the returned ranking;
- no native-language report missed by translation or extraction.

Use multiple focused windows, languages/operators, publisher archives, and
primary-source databases when completeness matters. Describe the method as
"GDELT returned N matching records for this query and window," not "there were
N stories."

## Reporting checklist

- Preserve the exact query, window, sort, limit, response time, and URLs.
- Cite GDELT when reusing its dataset.
- Attribute and verify each publisher's claims separately.
- State monitoring, translation, ranking, and source-classification limits.
