WITH first_seen AS (
    SELECT register, registrant_id, min(period_start) AS first_period
    FROM lobbying_registrations
    GROUP BY register, registrant_id
),
latest AS (
    SELECT register, max(period_start) AS latest_period
    FROM lobbying_registrations
    GROUP BY register
),
newcomers AS (
    SELECT f.register, f.registrant_id, f.first_period
    FROM first_seen f
    JOIN latest l USING (register)
    WHERE f.first_period > l.latest_period - CAST(? AS INTEGER)
),
reports AS (
    SELECT
        r.register, r.registrant_id, any_value(r.registrant_name) AS registrant_name,
        coalesce(r.client_id, r.client_name) AS client_key, any_value(r.client_name) AS client_name,
        r.period_start, count(DISTINCT r.registration_id) AS rows_in_period,
        max((coalesce(r.spend_low, r.spend_high) + coalesce(r.spend_high, r.spend_low)) / 2.0) AS spend
    FROM lobbying_registrations r
    JOIN newcomers n ON n.register = r.register AND n.registrant_id = r.registrant_id
    GROUP BY r.register, r.registrant_id, client_key, r.period_start
)
SELECT
    register, registrant_id,
    any_value(registrant_name) AS registrant_name,
    min(period_start) AS first_period,
    sum(rows_in_period) AS registrations,
    count(DISTINCT client_key) AS distinct_clients,
    sum(spend) AS total_spend,
    string_agg(DISTINCT client_name, ' | ') AS clients
FROM reports
GROUP BY register, registrant_id
ORDER BY total_spend DESC NULLS LAST, distinct_clients DESC, registrations DESC, registrant_id
LIMIT ?
