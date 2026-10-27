WITH members AS (
    SELECT parliament, member_id, min(name) AS name
    FROM parl_members
    GROUP BY ALL
),
spans AS (
    SELECT DISTINCT parliament, member_id, lower(trim(org_name)) AS org_key, org_name, start_date, end_date
    FROM parl_affiliations
    WHERE affiliation_type = ? AND start_date IS NOT NULL AND org_name IS NOT NULL
),
ordered AS (
    SELECT parliament, member_id, org_key, org_name, start_date,
           lag(org_key) OVER w AS previous_key,
           lag(org_name) OVER w AS previous_name,
           lag(end_date) OVER w AS previous_end
    FROM spans
    WINDOW w AS (PARTITION BY parliament, member_id ORDER BY start_date, end_date NULLS LAST, org_key)
)
SELECT
    o.member_id,
    m.name,
    o.parliament,
    o.previous_name AS from_org,
    o.org_name AS to_org,
    o.previous_end AS from_end,
    o.start_date AS switch_date
FROM ordered o
LEFT JOIN members m ON m.parliament = o.parliament AND m.member_id = o.member_id
WHERE o.previous_key IS NOT NULL AND o.previous_key <> o.org_key
ORDER BY o.start_date DESC, o.member_id
LIMIT ?
