# Congress.gov query guide

## Bills

1. Choose a Congress when the reporting question permits it.
2. List recently acted-on bills without `q`, or use `q` only as a disclosed
   title filter over the bounded recent window.
3. Preserve bill type, number, Congress, latest action, update dates, and URL.
4. Open the bill page and inspect actions, sponsors, summaries, subjects, and
   text before making claims about content, movement, sponsorship, or passage.
5. For a negative finding, search the official site/full text with synonyms and
   earlier Congresses; do not generalize from a title-window miss.

## Members

1. Prefer `bioguide_id` for a known person.
2. Use `state` for current membership or `congress` for a historical roster.
3. Treat `name` as a bounded client-side filter, then verify Bioguide ID.
4. Check `current_member`, party, chamber, district, and dated terms separately.
5. Preserve the retrieval date because vacancies, party, district, and office
   can change.

## Reporting checklist

- Exact operation and bounded-search disclosure.
- Congress number, bill type/number, Bioguide ID, and limit.
- Latest-action date versus update timestamps.
- Source-page verification for sponsorship, text, status, and enactment.
- Retrieval date and negative-result limitations.
