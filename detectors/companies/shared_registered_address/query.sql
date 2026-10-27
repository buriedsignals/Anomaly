WITH params AS (SELECT CAST(? AS INTEGER) AS min_companies),
keyed AS (
    SELECT company_id, name, jurisdiction, dissolution_date, incorporation_date, registered_address,
           lower(regexp_replace(registered_address, '[^\p{L}\p{N}]', '', 'g')) AS address_key
    FROM companies
    WHERE registered_address IS NOT NULL
),
grouped AS (
    SELECT address_key,
           min(registered_address) AS registered_address,
           count(DISTINCT company_id) AS companies,
           count(DISTINCT company_id) FILTER (WHERE dissolution_date IS NULL) AS current_companies,
           string_agg(DISTINCT upper(jurisdiction), '|' ORDER BY upper(jurisdiction)) AS jurisdictions,
           min(incorporation_date) AS first_incorporated,
           max(incorporation_date) AS last_incorporated,
           array_to_string(list_slice(list_sort(list_distinct(list(name))), 1, 5), '|') AS example_companies
    FROM keyed
    WHERE address_key <> ''
    GROUP BY address_key
    HAVING count(DISTINCT company_id) >= (SELECT min_companies FROM params)
)
SELECT address_key AS candidate_id, registered_address, companies, current_companies, jurisdictions,
       first_incorporated, last_incorporated, example_companies
FROM grouped
ORDER BY companies DESC, candidate_id
LIMIT ?
