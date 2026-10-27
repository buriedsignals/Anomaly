WITH params AS (
    SELECT CAST(? AS BIGINT) AS min_name_length, CAST(? AS BIGINT) AS year_slack
),
cases AS (
    SELECT
        case_id,
        min(court_id) AS court_id,
        min(case_name) AS case_name,
        min(docket_number) AS docket_number,
        min(date_filed) AS date_filed,
        max(date_terminated) AS date_terminated,
        min(assigned_judge_id) AS judge_id,
        min(assigned_judge_name) AS judge_name,
        min(url) AS url
    FROM court_cases
    WHERE assigned_judge_id IS NOT NULL AND date_filed IS NOT NULL
    GROUP BY case_id
),
parties AS (
    SELECT DISTINCT case_id, party_name, party_role, trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(upper(coalesce(party_name, '')), '\([^)]*\)', ' ', 'g'), '[^A-Z0-9]+', ' ', 'g'), '\b(THE|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|LP|LLP|NA|COM|COMMON|STOCK|SHS|CL|CLASS)\b', ' ', 'g'), ' +', ' ', 'g')) AS party_key
    FROM case_parties
),
holdings AS (
    SELECT judge_id, report_year, counterparty, value_low, value_high, url AS report_url,
           trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(upper(coalesce(counterparty, '')), '\([^)]*\)', ' ', 'g'), '[^A-Z0-9]+', ' ', 'g'), '\b(THE|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|LP|LLP|NA|COM|COMMON|STOCK|SHS|CL|CLASS)\b', ' ', 'g'), ' +', ' ', 'g')) AS holding_key
    FROM judge_interests
    WHERE lower(interest_type) = 'investment' AND report_year IS NOT NULL
),
matches AS (
    SELECT
        c.case_id, c.court_id, c.case_name, c.docket_number, c.date_filed, c.date_terminated,
        c.judge_id, c.judge_name, c.url,
        p.party_name, p.party_role,
        h.counterparty AS holding, h.report_year, h.value_low, h.value_high, h.report_url,
        CASE WHEN h.holding_key = p.party_key THEN 'exact' ELSE 'prefix' END AS match_type
    FROM cases c
    JOIN parties p ON p.case_id = c.case_id
    JOIN holdings h ON h.judge_id = c.judge_id
    CROSS JOIN params
    WHERE least(length(p.party_key), length(h.holding_key)) >= params.min_name_length
      AND (h.holding_key = p.party_key
           OR starts_with(h.holding_key, p.party_key || ' ')
           OR starts_with(p.party_key, h.holding_key || ' '))
      AND h.report_year >= year(c.date_filed) - params.year_slack
      AND (c.date_terminated IS NULL OR h.report_year <= year(c.date_terminated) + params.year_slack)
)
SELECT
    case_id,
    court_id,
    case_name,
    docket_number,
    date_filed,
    date_terminated,
    judge_id,
    judge_name,
    party_name,
    party_role,
    holding,
    match_type,
    min(report_year) AS first_report_year,
    max(report_year) AS last_report_year,
    max(value_low) AS max_value_low,
    max(value_high) AS max_value_high,
    min(report_url) AS report_url,
    url
FROM matches
GROUP BY case_id, court_id, case_name, docket_number, date_filed, date_terminated, judge_id, judge_name,
         party_name, party_role, holding, match_type, url
ORDER BY match_type, max_value_low DESC NULLS LAST, date_filed, case_id, party_name, holding
LIMIT ?
