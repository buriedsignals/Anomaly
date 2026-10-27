WITH params AS (
    SELECT CAST(? AS DOUBLE) AS threshold,
           CAST(? AS INTEGER) AS window_days,
           CAST(? AS INTEGER) AS min_gifts
),
gifts AS (
    SELECT d.donation_id, d.recipient_id, d.recipient_name, d.donor_name, d.amount, d.donation_date,
           upper(trim(d.donor_name)) || coalesce('|' || nullif(upper(replace(trim(d.donor_postcode), ' ', '')), ''), '') AS donor_key
    FROM donations d, params p
    WHERE d.amount > 0
      AND d.amount < p.threshold
      AND d.donation_date IS NOT NULL
),
anchors AS (
    SELECT DISTINCT recipient_id, donor_key, donation_date AS window_start FROM gifts
),
windows AS (
    SELECT a.recipient_id, a.donor_key, a.window_start,
           max(g.donation_date) AS window_end,
           min(g.recipient_name) AS recipient_name,
           min(g.donor_name) AS donor_name,
           count(*) AS gifts,
           sum(g.amount) AS total_amount,
           max(g.amount) AS largest_gift
    FROM anchors a
    JOIN gifts g
      ON g.recipient_id = a.recipient_id
     AND g.donor_key = a.donor_key
     AND g.donation_date BETWEEN a.window_start AND a.window_start + (SELECT window_days FROM params)
    GROUP BY 1, 2, 3
    HAVING count(*) >= (SELECT min_gifts FROM params)
       AND sum(g.amount) >= (SELECT threshold FROM params)
)
SELECT recipient_id || '|' || donor_key AS candidate_id,
       recipient_id, recipient_name, donor_name, window_start, window_end,
       gifts, total_amount, largest_gift
FROM windows
QUALIFY row_number() OVER (PARTITION BY recipient_id, donor_key
                           ORDER BY total_amount DESC, window_start) = 1
ORDER BY total_amount DESC, candidate_id
LIMIT ?
