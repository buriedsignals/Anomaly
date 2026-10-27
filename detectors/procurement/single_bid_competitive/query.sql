SELECT
    process_id,
    min(buyer_id) AS buyer_id,
    min(buyer_name) AS buyer_name,
    min(category_code) AS category_code,
    min(procurement_method) AS procurement_method,
    max(number_of_tenderers) AS number_of_tenderers,
    max(tender_value) AS tender_value,
    min(currency) AS currency
FROM procurement_processes
WHERE number_of_tenderers = 1
  AND lower(procurement_method) IN ('open', 'selective')
GROUP BY process_id
ORDER BY tender_value DESC NULLS LAST, process_id
LIMIT ?
