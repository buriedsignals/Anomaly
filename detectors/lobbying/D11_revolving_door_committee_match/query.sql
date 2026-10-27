WITH lobbyist_positions AS (
    SELECT DISTINCT
        lobbyist_id, name, former_public_office,
        CASE
            WHEN lower(former_public_office) LIKE '%armed services%' THEN 'armed_services'
            WHEN lower(former_public_office) LIKE '%ways and means%' THEN 'ways_means'
            WHEN lower(former_public_office) LIKE '%appropriation%' THEN 'appropriations'
            WHEN lower(former_public_office) LIKE '%finance%' THEN 'finance'
            WHEN lower(former_public_office) LIKE '%judiciary%' THEN 'judiciary'
            WHEN lower(former_public_office) LIKE '%intelligence%' THEN 'intelligence'
            WHEN lower(former_public_office) LIKE '%foreign relations%' THEN 'foreign_relations'
            WHEN lower(former_public_office) LIKE '%foreign affairs%' THEN 'foreign_affairs'
            WHEN lower(former_public_office) LIKE '%energy and commerce%' OR lower(former_public_office) LIKE '%energy & commerce%' THEN 'energy_commerce'
            WHEN lower(former_public_office) LIKE '%homeland security%' THEN 'homeland_security'
            WHEN lower(former_public_office) LIKE '%veterans%' THEN 'veterans_affairs'
            WHEN lower(former_public_office) LIKE '%health%' THEN 'health'
            WHEN lower(former_public_office) LIKE '%agriculture%' THEN 'agriculture'
            ELSE NULL
        END AS former_committee
    FROM lobbyists
    WHERE former_public_office IS NOT NULL AND length(former_public_office) >= 12
),
current_activities AS (
    SELECT
        l.lobbyist_id,
        r.registration_id, r.period_start,
        r.registrant_name, r.client_name, r.spend_high AS spend,
        a.general_issue_code, a.description, r.url
    FROM lobbyists l
    JOIN lobbying_activities a USING (registration_id)
    JOIN lobbying_registrations r USING (registration_id)
    WHERE year(r.period_start) IN (2024, 2025, 2026)
      AND r.filing_type IN ('Q1', 'Q2', 'Q3', 'Q4')
)
SELECT
    lp.lobbyist_id, lp.name,
    lp.former_committee, lp.former_public_office,
    ca.registration_id, ca.period_start,
    ca.registrant_name, ca.client_name, ca.general_issue_code,
    ca.description, ca.spend, ca.url
FROM lobbyist_positions lp
JOIN current_activities ca USING (lobbyist_id)
WHERE lp.former_committee IS NOT NULL
  AND (
      (lp.former_committee = 'armed_services'    AND ca.general_issue_code IN ('DEF', 'HOM', 'INT')) OR
      (lp.former_committee = 'ways_means'        AND ca.general_issue_code IN ('TAX', 'BUD', 'TRD', 'HCR')) OR
      (lp.former_committee = 'appropriations'    AND ca.general_issue_code IN ('BUD', 'DEF', 'HCR', 'EDU')) OR
      (lp.former_committee = 'finance'           AND ca.general_issue_code IN ('TAX', 'BUD', 'BAN', 'FIN')) OR
      (lp.former_committee = 'judiciary'         AND ca.general_issue_code IN ('LAW', 'IMM', 'BNK', 'CON', 'CIV')) OR
      (lp.former_committee = 'intelligence'      AND ca.general_issue_code IN ('INT', 'DEF', 'HOM', 'CSP')) OR
      (lp.former_committee = 'foreign_relations' AND ca.general_issue_code IN ('FOR', 'TRD', 'DEF')) OR
      (lp.former_committee = 'foreign_affairs'   AND ca.general_issue_code IN ('FOR', 'TRD', 'DEF')) OR
      (lp.former_committee = 'energy_commerce'   AND ca.general_issue_code IN ('ENG', 'HCR', 'TEC', 'TRA', 'CPT')) OR
      (lp.former_committee = 'homeland_security' AND ca.general_issue_code IN ('HOM', 'IMM', 'CSP')) OR
      (lp.former_committee = 'health'            AND ca.general_issue_code IN ('HCR', 'MED', 'HPI')) OR
      (lp.former_committee = 'agriculture'       AND ca.general_issue_code IN ('AGR', 'FOO', 'TRD'))
  )
  AND ca.spend > 0
ORDER BY ca.spend DESC NULLS LAST, lp.lobbyist_id, ca.registration_id, ca.general_issue_code
LIMIT ?
