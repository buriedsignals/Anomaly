WITH awards AS (
    SELECT DISTINCT award_id, process_id, supplier_id, supplier_name, award_value, currency, award_date
    FROM procurement_awards
    WHERE award_value > 0 AND award_date IS NOT NULL
),
processes AS (
    SELECT process_id,
           min(coalesce(buyer_id, buyer_name)) AS buyer_key,
           min(buyer_name) AS buyer_name,
           coalesce(min(category_code), '') AS category_key,
           min(currency) AS currency
    FROM procurement_processes
    GROUP BY process_id
),
valued AS (
    SELECT
        a.award_id,
        a.supplier_id,
        a.supplier_name,
        a.award_value / count(*) OVER (PARTITION BY a.award_id) AS value,
        coalesce(a.currency, p.currency, '') AS currency_key,
        year(a.award_date) AS award_year,
        p.buyer_key,
        p.buyer_name,
        p.category_key
    FROM awards a
    JOIN processes p USING (process_id)
),
markets AS (
    SELECT buyer_key, category_key, award_year, currency_key,
           sum(value) AS market_value,
           count(DISTINCT award_id) AS market_awards,
           count(DISTINCT supplier_id) AS market_suppliers
    FROM valued
    GROUP BY ALL
    HAVING count(DISTINCT award_id) >= ?
),
suppliers AS (
    SELECT buyer_key, category_key, award_year, currency_key, supplier_id,
           min(supplier_name) AS supplier_name,
           min(buyer_name) AS buyer_name,
           sum(value) AS supplier_value,
           count(DISTINCT award_id) AS supplier_awards
    FROM valued
    GROUP BY ALL
)
SELECT
    s.supplier_id,
    s.supplier_name,
    s.buyer_key AS buyer_id,
    s.buyer_name,
    nullif(s.category_key, '') AS category_code,
    s.award_year,
    nullif(s.currency_key, '') AS currency,
    s.supplier_value,
    m.market_value,
    round(s.supplier_value / m.market_value, 4) AS supplier_share,
    s.supplier_awards,
    m.market_awards,
    m.market_suppliers
FROM suppliers s
JOIN markets m USING (buyer_key, category_key, award_year, currency_key)
WHERE s.supplier_value / m.market_value > ?
ORDER BY supplier_share DESC, s.supplier_value DESC, s.supplier_id
LIMIT ?
