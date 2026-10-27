SELECT company_id AS candidate_id, company_id, name, jurisdiction, previous_name_count,
       incorporation_date, status, source_url
FROM companies
WHERE previous_name_count >= ?
QUALIFY row_number() OVER (PARTITION BY company_id ORDER BY previous_name_count DESC, name) = 1
ORDER BY previous_name_count DESC, candidate_id
LIMIT ?
