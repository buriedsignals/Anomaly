SELECT
    process_id,
    min(buyer_id) AS buyer_id,
    min(buyer_name) AS buyer_name,
    min(procurement_method) AS procurement_method,
    min(tender_published_date) AS tender_published_date,
    max(tender_deadline) AS tender_deadline,
    date_diff('day', min(tender_published_date), max(tender_deadline)) AS submission_days,
    max(tender_value) AS tender_value,
    min(currency) AS currency
FROM procurement_processes
WHERE tender_published_date IS NOT NULL
  AND tender_deadline IS NOT NULL
  AND (procurement_method IS NULL OR lower(procurement_method) IN ('open', 'selective'))
GROUP BY process_id
HAVING submission_days >= 0 AND submission_days < ?
ORDER BY submission_days, process_id
LIMIT ?
