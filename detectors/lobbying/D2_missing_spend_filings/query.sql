WITH money_types AS (
    SELECT DISTINCT register, coalesce(filing_type, '') AS kind
    FROM lobbying_registrations
    WHERE coalesce(spend_low, spend_high) IS NOT NULL
),
reports AS (
    SELECT
        r.register, r.registrant_id, any_value(r.registrant_name) AS registrant_name,
        coalesce(r.client_id, r.client_name, '') AS client_key, r.period_start,
        max(coalesce(r.spend_low, r.spend_high)) AS spend
    FROM lobbying_registrations r
    JOIN money_types m ON m.register = r.register AND m.kind = coalesce(r.filing_type, '')
    GROUP BY r.register, r.registrant_id, client_key, r.period_start
)
SELECT
    register, registrant_id, any_value(registrant_name) AS registrant_name,
    count(*) AS reports_without_spend,
    count(DISTINCT nullif(client_key, '')) AS distinct_clients,
    min(period_start) AS first_seen,
    max(period_start) AS last_seen
FROM reports
WHERE spend IS NULL
GROUP BY register, registrant_id
HAVING count(*) >= ?
ORDER BY reports_without_spend DESC, distinct_clients DESC, registrant_id
LIMIT ?
