WITH parameters AS (SELECT ? AS min_delta_pct),
issues AS (
    SELECT
        register, registrant_id, registration_id,
        CAST(date_trunc('quarter', period_start) AS DATE) AS quarter,
        trim(unnest(string_split(issue_area, '|'))) AS issue_area,
        (coalesce(spend_low, spend_high) + coalesce(spend_high, spend_low)) / 2.0 AS spend
    FROM lobbying_registrations
    WHERE issue_area IS NOT NULL
),
per_quarter AS (
    SELECT register, issue_area, quarter,
           count(DISTINCT registrant_id) AS registrants,
           sum(spend) AS total_spend
    FROM issues
    WHERE issue_area <> ''
    GROUP BY register, issue_area, quarter
),
ordered AS (
    SELECT *,
           lag(total_spend) OVER issue_order AS prior_spend,
           lag(registrants) OVER issue_order AS prior_registrants
    FROM per_quarter
    WINDOW issue_order AS (PARTITION BY register, issue_area ORDER BY quarter)
),
deltas AS (
    SELECT *,
           CASE WHEN prior_spend > 0 THEN round(100.0 * (total_spend - prior_spend) / prior_spend, 1) END AS spend_delta_pct,
           CASE WHEN prior_registrants > 0 THEN round(100.0 * (registrants - prior_registrants) / prior_registrants, 1) END AS registrants_delta_pct
    FROM ordered
)
SELECT register, issue_area, quarter, registrants, prior_registrants, registrants_delta_pct,
       total_spend, prior_spend, spend_delta_pct
FROM deltas
WHERE (prior_spend > 0 AND abs(spend_delta_pct) >= (SELECT min_delta_pct FROM parameters))
   OR (prior_spend IS NULL AND prior_registrants > 0
       AND abs(registrants_delta_pct) >= (SELECT min_delta_pct FROM parameters))
ORDER BY abs(coalesce(total_spend - prior_spend, registrants - prior_registrants)) DESC, issue_area, quarter
LIMIT ?
