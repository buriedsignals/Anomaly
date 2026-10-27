WITH params AS (
    SELECT CAST(? AS BIGINT) AS min_name_length, CAST(? AS BIGINT) AS year_slack
),
cases AS (
    SELECT
        case_id,
        min(court_id) AS court_id,
        min(case_name) AS case_name,
        min(date_filed) AS date_filed,
        max(date_terminated) AS date_terminated,
        min(assigned_judge_id) AS judge_id,
        min(assigned_judge_name) AS judge_name,
        min(url) AS url
    FROM court_cases
    WHERE assigned_judge_id IS NOT NULL AND date_filed IS NOT NULL
    GROUP BY case_id
),
names AS (
    SELECT case_id, party_name AS matched_name, 'party' AS matched_as FROM case_parties
    UNION
    SELECT case_id, counsel_name, 'counsel' FROM case_counsel
    UNION
    SELECT case_id, firm_name, 'firm' FROM case_counsel WHERE firm_name IS NOT NULL
),
keyed AS (
    SELECT case_id, matched_name, matched_as, trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(upper(coalesce(matched_name, '')), '\([^)]*\)', ' ', 'g'), '[^A-Z0-9]+', ' ', 'g'), '\b(THE|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|LP|LLP|NA|COM|COMMON|STOCK|SHS|CL|CLASS)\b', ' ', 'g'), ' +', ' ', 'g')) AS name_key FROM names
),
benefits AS (
    SELECT judge_id, report_year, lower(interest_type) AS interest_type, counterparty, description,
           value_low, value_high, url AS report_url, trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(upper(coalesce(counterparty, '')), '\([^)]*\)', ' ', 'g'), '[^A-Z0-9]+', ' ', 'g'), '\b(THE|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|LP|LLP|NA|COM|COMMON|STOCK|SHS|CL|CLASS)\b', ' ', 'g'), ' +', ' ', 'g')) AS source_key
    FROM judge_interests
    WHERE lower(interest_type) IN ('gift', 'reimbursement') AND report_year IS NOT NULL
)
SELECT DISTINCT
    c.case_id,
    c.court_id,
    c.case_name,
    c.date_filed,
    c.date_terminated,
    c.judge_id,
    c.judge_name,
    k.matched_name,
    k.matched_as,
    b.interest_type,
    b.counterparty AS benefit_source,
    b.description AS benefit_description,
    b.report_year,
    b.value_low,
    b.value_high,
    CASE WHEN b.source_key = k.name_key THEN 'exact' ELSE 'prefix' END AS match_type,
    b.report_url,
    c.url
FROM cases c
JOIN keyed k ON k.case_id = c.case_id
JOIN benefits b ON b.judge_id = c.judge_id
CROSS JOIN params
WHERE least(length(k.name_key), length(b.source_key)) >= params.min_name_length
  AND (b.source_key = k.name_key
       OR starts_with(b.source_key, k.name_key || ' ')
       OR starts_with(k.name_key, b.source_key || ' '))
  AND b.report_year >= year(c.date_filed) - params.year_slack
  AND (c.date_terminated IS NULL OR b.report_year <= year(c.date_terminated) + params.year_slack)
ORDER BY match_type, c.date_filed, c.case_id, k.matched_name, b.report_year, b.counterparty
LIMIT ?
