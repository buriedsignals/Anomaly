WITH reports AS (
    SELECT
        register, registrant_id, any_value(registrant_name) AS registrant_name,
        coalesce(client_id, client_name) AS client_key, any_value(client_name) AS client_name,
        period_start, count(DISTINCT registration_id) AS rows_in_period,
        max((coalesce(spend_low, spend_high) + coalesce(spend_high, spend_low)) / 2.0) AS spend
    FROM lobbying_registrations
    WHERE coalesce(client_id, client_name) IS NOT NULL
    GROUP BY register, registrant_id, client_key, period_start
)
SELECT
    register,
    registrant_id,
    any_value(registrant_name) AS registrant_name,
    count(DISTINCT client_key) AS distinct_clients,
    sum(rows_in_period) AS registrations,
    sum(spend) AS total_spend,
    min(period_start) AS earliest_period,
    max(period_start) AS latest_period,
    string_agg(DISTINCT client_name, ' | ') AS clients
FROM reports
GROUP BY register, registrant_id
HAVING count(DISTINCT client_key) BETWEEN 1 AND 2
   AND sum(spend) >= ?
ORDER BY total_spend DESC, registrant_id
LIMIT ?
