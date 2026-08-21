
            WITH lobbyist_positions AS (
                SELECT DISTINCT lobbyist_id, first_name, last_name, covered_position
                FROM senate_activity_lobbyists
                WHERE lower(covered_position) LIKE '%' || 'finance' || '%'
            ),
            current_committee_members AS (
                SELECT DISTINCT m.bioguide_id, m.name AS member_name, m.party, m.state, a.role
                FROM congress_committee_assignments a
                JOIN congress_members m USING (bioguide_id)
                WHERE lower(a.committee_name) LIKE '%' || 'finance' || '%'
            ),
            press_attacks AS (
                SELECT pr.bioguide_id, pr.member_name, pr.date, pr.title, pr.url,
                       substr(pr.text, 1, 200) AS excerpt
                FROM press_releases pr
                WHERE lower(pr.text) LIKE '%apollo%'
                  AND lower(pr.text) LIKE '%private equity%'
            ),
            lobbying_for_target AS (
                SELECT DISTINCT f.filing_uuid, f.registrant_name, f.client_name, f.income,
                       lp.first_name AS lobbyist_first, lp.last_name AS lobbyist_last,
                       lp.covered_position
                FROM senate_filings f
                JOIN senate_activity_lobbyists al USING (filing_uuid)
                JOIN lobbyist_positions lp ON lp.lobbyist_id = al.lobbyist_id
                WHERE lower(f.client_name) LIKE '%apollo%'
                  AND f.filing_year IN (2024, 2025, 2026)
            )
            SELECT
                lft.registrant_name      AS lobbying_firm,
                lft.client_name          AS lobbied_client,
                lft.lobbyist_first || ' ' || lft.lobbyist_last AS lobbyist,
                lft.covered_position     AS former_role,
                (SELECT count(*) FROM current_committee_members) AS current_committee_members,
                (SELECT count(*) FROM press_attacks)             AS attack_press_releases,
                (SELECT count(DISTINCT member_name) FROM press_attacks
                 WHERE bioguide_id IN (SELECT bioguide_id FROM current_committee_members))
                                          AS committee_members_attacking,
                lft.income
            FROM lobbying_for_target lft
            ORDER BY lft.income DESC NULLS LAST
            LIMIT 200
        
