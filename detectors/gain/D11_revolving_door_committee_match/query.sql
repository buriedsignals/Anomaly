
            WITH lobbyist_positions AS (
                -- Distinct lobbyist + covered_position pairs with relevant keywords
                SELECT DISTINCT
                    lobbyist_id, first_name, last_name, covered_position,
                    -- Extract committee acronym/name from covered_position text
                    CASE
                        WHEN lower(covered_position) LIKE '%armed services%' THEN 'armed_services'
                        WHEN lower(covered_position) LIKE '%ways and means%' THEN 'ways_means'
                        WHEN lower(covered_position) LIKE '%appropriation%' THEN 'appropriations'
                        WHEN lower(covered_position) LIKE '%finance%' THEN 'finance'
                        WHEN lower(covered_position) LIKE '%judiciary%' THEN 'judiciary'
                        WHEN lower(covered_position) LIKE '%intelligence%' THEN 'intelligence'
                        WHEN lower(covered_position) LIKE '%foreign relations%' THEN 'foreign_relations'
                        WHEN lower(covered_position) LIKE '%foreign affairs%' THEN 'foreign_affairs'
                        WHEN lower(covered_position) LIKE '%energy and commerce%' OR lower(covered_position) LIKE '%energy & commerce%' THEN 'energy_commerce'
                        WHEN lower(covered_position) LIKE '%homeland security%' THEN 'homeland_security'
                        WHEN lower(covered_position) LIKE '%veterans%' THEN 'veterans_affairs'
                        WHEN lower(covered_position) LIKE '%health%' THEN 'health'
                        WHEN lower(covered_position) LIKE '%agriculture%' THEN 'agriculture'
                        ELSE NULL
                    END AS former_committee
                FROM senate_activity_lobbyists
                WHERE covered_position IS NOT NULL AND length(covered_position) >= 12
            ),
            current_activities AS (
                -- Current activities of those lobbyists, checking matching committee topics
                SELECT
                    al.lobbyist_id,
                    f.filing_uuid, f.filing_year, f.filing_period,
                    f.registrant_name, f.client_name, f.income,
                    a.general_issue_code, a.description, f.url
                FROM senate_activity_lobbyists al
                JOIN senate_lobbying_activities a USING (filing_uuid)
                JOIN senate_filings f USING (filing_uuid)
                WHERE f.filing_year IN (2024, 2025, 2026)
                  AND f.filing_type IN ('Q1','Q2','Q3','Q4')
            )
            SELECT
                lp.lobbyist_id, lp.first_name, lp.last_name,
                lp.former_committee, lp.covered_position,
                ca.filing_uuid, ca.filing_year, ca.filing_period,
                ca.registrant_name, ca.client_name, ca.general_issue_code,
                ca.description, ca.income, ca.url
            FROM lobbyist_positions lp
            JOIN current_activities ca USING (lobbyist_id)
            WHERE lp.former_committee IS NOT NULL
              AND (
                  (lp.former_committee = 'armed_services'   AND ca.general_issue_code IN ('DEF','HOM','INT')) OR
                  (lp.former_committee = 'ways_means'       AND ca.general_issue_code IN ('TAX','BUD','TRD','HCR')) OR
                  (lp.former_committee = 'appropriations'   AND ca.general_issue_code IN ('BUD','DEF','HCR','EDU')) OR
                  (lp.former_committee = 'finance'          AND ca.general_issue_code IN ('TAX','BUD','BAN','FIN')) OR
                  (lp.former_committee = 'judiciary'        AND ca.general_issue_code IN ('LAW','IMM','BNK','CON','CIV')) OR
                  (lp.former_committee = 'intelligence'     AND ca.general_issue_code IN ('INT','DEF','HOM','CSP')) OR
                  (lp.former_committee = 'foreign_relations' AND ca.general_issue_code IN ('FOR','TRD','DEF')) OR
                  (lp.former_committee = 'foreign_affairs'  AND ca.general_issue_code IN ('FOR','TRD','DEF')) OR
                  (lp.former_committee = 'energy_commerce'  AND ca.general_issue_code IN ('ENG','HCR','TEC','TRA','CPT')) OR
                  (lp.former_committee = 'homeland_security' AND ca.general_issue_code IN ('HOM','IMM','CSP')) OR
                  (lp.former_committee = 'health'           AND ca.general_issue_code IN ('HCR','MED','HPI')) OR
                  (lp.former_committee = 'agriculture'      AND ca.general_issue_code IN ('AGR','FOO','TRD'))
              )
              AND ca.income IS NOT NULL
              AND ca.income > 0
            ORDER BY ca.income DESC NULLS LAST
            LIMIT 200
        
