SELECT
    payee_name,
    honoree_name,
    count(*) AS n_contributions,
    sum(coalesce(amount, 0)) AS total_amount,
    count(DISTINCT registration_id) AS distinct_reports,
    count(DISTINCT contributor_name) AS distinct_contributors
FROM political_contributions
WHERE payee_name IS NOT NULL OR honoree_name IS NOT NULL
GROUP BY 1, 2
ORDER BY total_amount DESC NULLS LAST, payee_name, honoree_name
LIMIT ?
