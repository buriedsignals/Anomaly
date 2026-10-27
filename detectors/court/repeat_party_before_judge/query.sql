WITH params AS (
    SELECT CAST(? AS BIGINT) AS min_cases, CAST(? AS DOUBLE) AS min_share,
           CAST(? AS VARCHAR) AS party_role, CAST(? AS VARCHAR) AS exclude_pattern
),
cases AS (
    SELECT case_id, min(court_id) AS court_id, min(assigned_judge_id) AS judge_id,
           min(assigned_judge_name) AS judge_name, min(date_filed) AS date_filed
    FROM court_cases
    WHERE assigned_judge_id IS NOT NULL
    GROUP BY case_id
),
parties AS (
    SELECT DISTINCT cp.case_id, cp.party_name, trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(upper(coalesce(cp.party_name, '')), '\([^)]*\)', ' ', 'g'), '[^A-Z0-9]+', ' ', 'g'), '\b(THE|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|LP|LLP|NA|COM|COMMON|STOCK|SHS|CL|CLASS)\b', ' ', 'g'), ' +', ' ', 'g')) AS party_key
    FROM case_parties cp
    CROSS JOIN params
    WHERE params.party_role = '' OR cp.party_role IS NULL OR lower(cp.party_role) = lower(params.party_role)
),
appearances AS (
    SELECT p.party_key, min(p.party_name) AS party_name, c.case_id, c.court_id, c.judge_id, c.judge_name, c.date_filed
    FROM parties p
    JOIN cases c ON c.case_id = p.case_id
    CROSS JOIN params
    WHERE p.party_key <> ''
      AND (params.exclude_pattern = '' OR NOT regexp_matches(p.party_key, params.exclude_pattern))
    GROUP BY p.party_key, c.case_id, c.court_id, c.judge_id, c.judge_name, c.date_filed
),
court_judges AS (
    SELECT court_id, count(DISTINCT judge_id) AS judges_in_court FROM cases GROUP BY court_id
),
party_totals AS (
    SELECT party_key, court_id, count(DISTINCT case_id) AS party_cases
    FROM appearances
    GROUP BY party_key, court_id
),
party_judges AS (
    SELECT party_key, court_id, judge_id,
           min(judge_name) AS judge_name,
           min(party_name) AS party_name,
           count(DISTINCT case_id) AS cases_before_judge,
           min(date_filed) AS first_filed,
           max(date_filed) AS last_filed
    FROM appearances
    GROUP BY party_key, court_id, judge_id
)
SELECT
    pj.party_name,
    pj.court_id,
    pj.judge_id,
    pj.judge_name,
    pj.cases_before_judge,
    pt.party_cases,
    round(pj.cases_before_judge / pt.party_cases, 4) AS judge_share,
    cj.judges_in_court,
    pj.first_filed,
    pj.last_filed
FROM party_judges pj
JOIN party_totals pt ON pt.party_key = pj.party_key AND pt.court_id = pj.court_id
JOIN court_judges cj ON cj.court_id = pj.court_id
CROSS JOIN params
WHERE pt.party_cases >= params.min_cases
  AND pj.cases_before_judge / pt.party_cases >= params.min_share
ORDER BY pj.cases_before_judge DESC, judge_share DESC, pj.court_id, pj.party_name, pj.judge_id
LIMIT ?
