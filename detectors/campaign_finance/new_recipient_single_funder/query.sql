WITH params AS (
    SELECT CAST(? AS INTEGER) AS max_age_days,
           CAST(? AS DOUBLE) AS min_top_share,
           CAST(? AS DOUBLE) AS min_total
),
early AS (
    SELECT r.recipient_id, r.name AS recipient_name, r.registered_date,
           d.donor_name, upper(trim(d.donor_name)) AS donor_key, d.amount, d.donation_date
    FROM recipients r
    JOIN donations d ON d.recipient_id = r.recipient_id
    CROSS JOIN params p
    WHERE r.registered_date IS NOT NULL
      AND d.donation_date IS NOT NULL
      AND d.amount > 0
      AND d.donation_date <= r.registered_date + p.max_age_days
),
by_donor AS (
    SELECT recipient_id, donor_key, min(donor_name) AS donor_name, sum(amount) AS donor_amount
    FROM early
    GROUP BY 1, 2
),
top_donor AS (
    SELECT recipient_id, donor_name AS top_donor, donor_amount AS top_donor_amount
    FROM by_donor
    QUALIFY row_number() OVER (PARTITION BY recipient_id ORDER BY donor_amount DESC, donor_key) = 1
),
totals AS (
    SELECT recipient_id,
           min(recipient_name) AS recipient_name,
           min(registered_date) AS registered_date,
           min(donation_date) AS first_donation_date,
           max(donation_date) AS last_donation_date,
           count(DISTINCT donor_key) AS donors,
           count(*) AS donations,
           sum(amount) AS total_amount
    FROM early
    GROUP BY 1
)
SELECT t.recipient_id AS candidate_id, t.recipient_id, t.recipient_name, t.registered_date,
       t.first_donation_date, t.last_donation_date, t.donors, t.donations, t.total_amount,
       d.top_donor, d.top_donor_amount, round(d.top_donor_amount / t.total_amount, 4) AS top_share
FROM totals t
JOIN top_donor d USING (recipient_id)
WHERE t.total_amount >= (SELECT min_total FROM params)
  AND d.top_donor_amount / t.total_amount >= (SELECT min_top_share FROM params)
ORDER BY t.total_amount DESC, t.recipient_id
LIMIT ?
