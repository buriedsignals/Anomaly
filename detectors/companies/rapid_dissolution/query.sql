SELECT company_id AS candidate_id, company_id, name, jurisdiction, incorporation_date, dissolution_date,
       date_diff('day', incorporation_date, dissolution_date) AS days_existed,
       registered_address, source_url
FROM companies
WHERE incorporation_date IS NOT NULL
  AND dissolution_date IS NOT NULL
  AND dissolution_date >= incorporation_date
  AND date_diff('day', incorporation_date, dissolution_date) <= ?
QUALIFY row_number() OVER (PARTITION BY company_id ORDER BY dissolution_date, name) = 1
ORDER BY days_existed, candidate_id
LIMIT ?
