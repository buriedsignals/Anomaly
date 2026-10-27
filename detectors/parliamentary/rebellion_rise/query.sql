WITH members AS (
    SELECT parliament, member_id, min(name) AS name
    FROM parl_members
    GROUP BY ALL
),
cast_votes AS (
    SELECT v.parliament, v.voting_id, v.member_id, lower(v.position) AS position, v.group_at_vote, t.vote_date
    FROM parl_member_votes v
    JOIN parl_votings t ON t.parliament = v.parliament AND t.voting_id = v.voting_id
    WHERE lower(v.position) IN ('for', 'against', 'abstain') AND v.group_at_vote IS NOT NULL
      AND v.group_at_vote NOT IN (SELECT trim(label) FROM unnest(string_split(?, '|')) AS t(label)) AND t.vote_date IS NOT NULL
),
group_positions AS (
    SELECT parliament, voting_id, group_at_vote, position, count(*) AS n
    FROM cast_votes
    GROUP BY ALL
),
group_lines AS (
    SELECT parliament, voting_id, group_at_vote, arg_max(position, n) AS line, max(n) AS top_n, sum(n) AS group_size
    FROM group_positions
    GROUP BY ALL
),
clear_lines AS (
    SELECT l.parliament, l.voting_id, l.group_at_vote, l.line
    FROM group_lines l
    WHERE l.group_size >= ?
      AND (
          SELECT count(*) FROM group_positions g
          WHERE g.parliament = l.parliament AND g.voting_id = l.voting_id
            AND g.group_at_vote = l.group_at_vote AND g.n = l.top_n
      ) = 1
),
periods AS (
    SELECT c.parliament, c.member_id,
           CAST(date_trunc('quarter', c.vote_date) AS DATE) AS period_start,
           count(*) AS votes_compared,
           count(*) FILTER (WHERE c.position <> l.line) AS rebellions
    FROM cast_votes c
    JOIN clear_lines l USING (parliament, voting_id, group_at_vote)
    GROUP BY ALL
    HAVING count(*) >= ?
),
changes AS (
    SELECT parliament, member_id, period_start, votes_compared,
           rebellions / votes_compared AS rate,
           lag(period_start) OVER w AS previous_period_start,
           lag(votes_compared) OVER w AS previous_votes_compared,
           lag(rebellions / votes_compared) OVER w AS previous_rate
    FROM periods
    WINDOW w AS (PARTITION BY parliament, member_id ORDER BY period_start)
)
SELECT
    c.member_id,
    m.name,
    c.parliament,
    c.previous_period_start,
    c.period_start,
    c.previous_votes_compared,
    c.votes_compared,
    round(c.previous_rate, 4) AS previous_rate,
    round(c.rate, 4) AS rate,
    round(c.rate - c.previous_rate, 4) AS increase
FROM changes c
LEFT JOIN members m ON m.parliament = c.parliament AND m.member_id = c.member_id
WHERE c.previous_rate IS NOT NULL AND c.rate - c.previous_rate >= ?
ORDER BY increase DESC, c.member_id, c.period_start
LIMIT ?
