WITH parameters AS (SELECT ? AS target_committee, ? AS client_pattern),
lobbyist_positions AS (
    SELECT DISTINCT lobbyist_id, name, former_public_office
    FROM lobbyists
    WHERE lower(former_public_office) LIKE '%' || (SELECT target_committee FROM parameters) || '%'
),
current_committee_members AS (
    SELECT DISTINCT m.bioguide_id, m.name AS member_name, m.party, m.state, a.role
    FROM committee_assignments a
    JOIN legislators m USING (bioguide_id)
    WHERE lower(a.committee_name) LIKE '%' || (SELECT target_committee FROM parameters) || '%'
),
press_attacks AS (
    SELECT pr.bioguide_id, pr.member_name
    FROM press_releases pr
    WHERE lower(pr.text) LIKE (SELECT client_pattern FROM parameters)
      AND lower(pr.text) LIKE '%private equity%'
),
lobbying_for_target AS (
    SELECT DISTINCT r.registration_id, r.registrant_name, r.client_name, r.spend_high AS spend,
           lp.name AS lobbyist, lp.former_public_office
    FROM lobbying_registrations r
    JOIN lobbyists l USING (registration_id)
    JOIN lobbyist_positions lp ON lp.lobbyist_id = l.lobbyist_id
    WHERE lower(r.client_name) LIKE (SELECT client_pattern FROM parameters)
      AND year(r.period_start) IN (2024, 2025, 2026)
)
SELECT
    lft.registrant_name AS lobbying_firm,
    lft.client_name AS lobbied_client,
    lft.lobbyist,
    lft.former_public_office AS former_role,
    (SELECT count(*) FROM current_committee_members) AS current_committee_members,
    (SELECT count(*) FROM press_attacks) AS attack_press_releases,
    (SELECT count(DISTINCT member_name) FROM press_attacks
     WHERE bioguide_id IN (SELECT bioguide_id FROM current_committee_members)) AS committee_members_attacking,
    lft.spend
FROM lobbying_for_target lft
ORDER BY lft.spend DESC NULLS LAST, lft.registration_id, lft.lobbyist
LIMIT ?
