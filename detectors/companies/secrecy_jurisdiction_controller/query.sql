WITH params AS (
    SELECT list_filter(list_transform(string_split(upper(?), '|'), j -> trim(j)), j -> j <> '') AS codes
),
home AS (
    SELECT company_id, min(name) AS company_name, min(upper(trim(jurisdiction))) AS jurisdiction
    FROM companies
    GROUP BY company_id
),
flagged AS (
    SELECT c.company_id, h.company_name,
           coalesce(h.jurisdiction,
                    CASE WHEN c.company_id NOT LIKE 'lei:%' THEN upper(split_part(c.company_id, ':', 1)) END) AS company_jurisdiction,
           c.controller_id, c.controller_name,
           upper(trim(c.controller_country)) AS controller_country,
           c.controller_company_id, c.control_type, c.notified_on
    FROM company_controllers c
    LEFT JOIN home h USING (company_id)
    WHERE c.controller_kind = 'legal_entity'
      AND c.ceased_on IS NULL
      AND list_contains((SELECT codes FROM params), upper(trim(c.controller_country)))
)
SELECT company_id || '|' || controller_id AS candidate_id,
       company_id, company_name, company_jurisdiction,
       controller_id, controller_name, controller_country, controller_company_id, control_type, notified_on
FROM flagged
WHERE company_jurisdiction IS DISTINCT FROM controller_country
QUALIFY row_number() OVER (PARTITION BY company_id, controller_id ORDER BY control_type NULLS LAST) = 1
ORDER BY controller_country, candidate_id
LIMIT ?
