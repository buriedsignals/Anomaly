WITH members AS (
    SELECT parliament, member_id, min(name) AS name
    FROM parl_members
    GROUP BY ALL
),
rolls AS (
    SELECT v.parliament, coalesce(t.chamber, '') AS chamber, v.member_id,
           count(*) AS votings,
           count(*) FILTER (WHERE lower(v.position) = 'absent') AS absences
    FROM parl_member_votes v
    JOIN parl_votings t ON t.parliament = v.parliament AND t.voting_id = v.voting_id
    WHERE lower(v.position) IN ('for', 'against', 'abstain', 'absent')
    GROUP BY ALL
    HAVING count(*) >= ?
),
medians AS (
    SELECT parliament, chamber, median(absences / votings) AS median_rate
    FROM rolls
    GROUP BY ALL
)
SELECT
    r.member_id,
    m.name,
    r.parliament,
    nullif(r.chamber, '') AS chamber,
    r.votings,
    r.absences,
    round(r.absences / r.votings, 4) AS absence_rate,
    round(d.median_rate, 4) AS median_rate
FROM rolls r
JOIN medians d USING (parliament, chamber)
LEFT JOIN members m ON m.parliament = r.parliament AND m.member_id = r.member_id
WHERE r.absences / r.votings >= greatest(? * d.median_rate, ?)
ORDER BY absence_rate DESC, r.absences DESC, r.member_id
LIMIT ?
