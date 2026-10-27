WITH reports AS (
    SELECT
        register, registrant_id, any_value(registrant_name) AS registrant_name,
        coalesce(client_id, client_name, '') AS client_key, period_start,
        max((coalesce(spend_low, spend_high) + coalesce(spend_high, spend_low)) / 2.0) AS spend
    FROM lobbying_registrations
    WHERE coalesce(spend_low, spend_high) IS NOT NULL
    GROUP BY register, registrant_id, client_key, period_start
),
periods AS (
    SELECT register, registrant_id, any_value(registrant_name) AS registrant_name,
           period_start, sum(spend) AS total_spend
    FROM reports
    GROUP BY register, registrant_id, period_start
),
windowed AS (
    SELECT *,
           avg(total_spend) OVER prior AS prior_mean,
           stddev_pop(total_spend) OVER prior AS prior_sd,
           count(*) OVER prior AS prior_n
    FROM periods
    WINDOW prior AS (PARTITION BY register, registrant_id ORDER BY period_start
                     ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
)
SELECT
    register, registrant_id, registrant_name, period_start,
    total_spend, prior_mean, prior_sd, prior_n,
    (total_spend - prior_mean) / prior_sd AS z_score
FROM windowed
WHERE prior_n >= 3
  AND prior_sd > 0
  AND total_spend >= ?
  AND abs((total_spend - prior_mean) / prior_sd) >= ?
ORDER BY abs((total_spend - prior_mean) / prior_sd) DESC, registrant_id, period_start
LIMIT ?
