WITH params AS (
    SELECT CAST(? AS BIGINT) AS min_cases, CAST(? AS DOUBLE) AS min_share
),
cases AS (
    SELECT
        case_id,
        min(court_id) AS court_id,
        coalesce(min(division), '') AS division_key,
        coalesce(min(nature_of_suit), '') AS nature_key,
        min(assigned_judge_id) AS judge_id,
        min(assigned_judge_name) AS judge_name,
        min(date_filed) AS date_filed
    FROM court_cases
    WHERE assigned_judge_id IS NOT NULL
    GROUP BY case_id
),
markets AS (
    SELECT court_id, division_key, nature_key,
           count(*) AS total_cases,
           count(DISTINCT judge_id) AS judges_in_market,
           min(date_filed) AS first_filed,
           max(date_filed) AS last_filed
    FROM cases
    GROUP BY court_id, division_key, nature_key
),
judges AS (
    SELECT court_id, division_key, nature_key, judge_id,
           min(judge_name) AS judge_name,
           count(*) AS judge_cases
    FROM cases
    GROUP BY court_id, division_key, nature_key, judge_id
)
SELECT
    j.court_id,
    nullif(j.division_key, '') AS division,
    nullif(j.nature_key, '') AS nature_of_suit,
    j.judge_id,
    j.judge_name,
    j.judge_cases,
    m.total_cases,
    round(j.judge_cases / m.total_cases, 4) AS judge_share,
    m.judges_in_market,
    m.first_filed,
    m.last_filed
FROM judges j
JOIN markets m ON m.court_id = j.court_id AND m.division_key = j.division_key AND m.nature_key = j.nature_key
CROSS JOIN params
WHERE m.total_cases >= params.min_cases
  AND j.judge_cases / m.total_cases >= params.min_share
ORDER BY judge_share DESC, m.total_cases DESC, j.court_id, division, nature_of_suit, j.judge_id
LIMIT ?
