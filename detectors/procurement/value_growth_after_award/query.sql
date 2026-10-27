WITH awards AS (
    SELECT DISTINCT award_id, process_id, supplier_name, award_value, final_value, currency, award_date
    FROM procurement_awards
),
grouped AS (
    SELECT
        award_id,
        min(process_id) AS process_id,
        string_agg(supplier_name, ' | ' ORDER BY supplier_name) AS suppliers,
        min(award_value) AS award_value,
        max(final_value) AS final_value,
        min(currency) AS currency,
        min(award_date) AS award_date
    FROM awards
    GROUP BY award_id
),
processes AS (
    SELECT process_id, min(buyer_id) AS buyer_id, min(buyer_name) AS buyer_name
    FROM procurement_processes
    GROUP BY process_id
)
SELECT
    g.award_id,
    g.process_id,
    p.buyer_id,
    p.buyer_name,
    g.suppliers,
    g.award_value,
    g.final_value,
    g.final_value - g.award_value AS value_increase,
    round(g.final_value / g.award_value, 4) AS growth_ratio,
    g.currency,
    g.award_date
FROM grouped g
LEFT JOIN processes p USING (process_id)
WHERE g.award_value > 0
  AND g.final_value > g.award_value * (1 + ?)
  AND g.final_value - g.award_value >= ?
ORDER BY value_increase DESC, g.award_id
LIMIT ?
