WITH params AS (
    SELECT CAST(? AS DOUBLE) AS min_years, nullif(CAST(? AS VARCHAR), '') AS as_of_text, CAST(? AS BIGINT) AS civil_only
),
cases AS (
    SELECT
        case_id,
        min(court_id) AS court_id,
        min(case_name) AS case_name,
        min(docket_number) AS docket_number,
        min(nature_of_suit) AS nature_of_suit,
        min(assigned_judge_id) AS judge_id,
        min(assigned_judge_name) AS judge_name,
        min(date_filed) AS date_filed,
        max(date_terminated) AS date_terminated,
        min(url) AS url
    FROM court_cases
    WHERE date_filed IS NOT NULL
    GROUP BY case_id
),
settings AS (
    SELECT
        coalesce(CAST(params.as_of_text AS DATE),
                 (SELECT max(greatest(date_filed, coalesce(date_terminated, date_filed))) FROM cases)) AS as_of_date,
        params.min_years,
        params.civil_only
    FROM params
),
pending AS (
    SELECT c.*, s.as_of_date,
           round(datediff('day', c.date_filed, s.as_of_date) / 365.25, 2) AS years_pending
    FROM cases c
    CROSS JOIN settings s
    WHERE c.date_filed <= s.as_of_date
      AND (c.date_terminated IS NULL OR c.date_terminated > s.as_of_date)
      AND datediff('day', c.date_filed, s.as_of_date) / 365.25 > s.min_years
      AND (s.civil_only = 0 OR c.nature_of_suit IS NOT NULL)
)
SELECT
    case_id,
    court_id,
    case_name,
    docket_number,
    nature_of_suit,
    judge_id,
    judge_name,
    date_filed,
    as_of_date,
    years_pending,
    count(*) OVER (PARTITION BY court_id, judge_id) AS judge_long_pending,
    url
FROM pending
ORDER BY years_pending DESC, case_id
LIMIT ?
