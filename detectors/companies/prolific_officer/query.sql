WITH params AS (
    SELECT CAST(? AS INTEGER) AS min_companies,
           list_filter(list_transform(string_split(upper(?), '|'), r -> trim(r)), r -> r <> '') AS excluded_roles
),
holders AS (
    SELECT 'officer' AS holder_type, officer_id AS holder_id, name, company_id, company_name
    FROM company_officers
    WHERE resigned_on IS NULL
      AND officer_id IS NOT NULL
      AND NOT list_contains((SELECT excluded_roles FROM params), upper(trim(coalesce(role, ''))))
    UNION ALL
    SELECT 'controller', controller_id, controller_name, company_id, NULL
    FROM company_controllers
    WHERE ceased_on IS NULL
      AND controller_id IS NOT NULL
      AND controller_kind <> 'statement'
)
SELECT holder_type || '|' || holder_id AS candidate_id,
       holder_type, holder_id, min(name) AS name,
       count(DISTINCT company_id) AS companies,
       array_to_string(list_slice(list_sort(list_distinct(list(coalesce(company_name, company_id)))), 1, 5), '|') AS example_companies
FROM holders
GROUP BY holder_type, holder_id
HAVING count(DISTINCT company_id) >= (SELECT min_companies FROM params)
ORDER BY companies DESC, candidate_id
LIMIT ?
