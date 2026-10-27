WITH members AS (
    SELECT parliament, member_id, min(name) AS name
    FROM parl_members
    GROUP BY ALL
),
current_interests AS (
    SELECT DISTINCT parliament, member_id, interest_id, lower(paid) AS paid, income_high
    FROM parl_interests
    WHERE end_date IS NULL
),
loads AS (
    SELECT parliament, member_id,
           count(*) AS interests,
           count(*) FILTER (WHERE paid = 'paid') AS paid_interests,
           count(*) FILTER (WHERE paid = 'unpaid') AS unpaid_interests,
           sum(income_high) AS income_high
    FROM current_interests
    GROUP BY ALL
)
SELECT
    l.member_id,
    m.name,
    l.parliament,
    l.interests,
    l.paid_interests,
    l.unpaid_interests,
    l.income_high
FROM loads l
LEFT JOIN members m ON m.parliament = l.parliament AND m.member_id = l.member_id
WHERE l.paid_interests >= ? OR l.income_high >= ?
ORDER BY l.paid_interests DESC, l.income_high DESC NULLS LAST, l.member_id
LIMIT ?
