WITH params AS (
    SELECT CAST(? AS DOUBLE) AS limit_amount,
           CAST(? AS DOUBLE) AS near_limit_ratio,
           CAST(? AS INTEGER) AS window_days,
           CAST(? AS INTEGER) AS min_donors
),
maxed AS (
    SELECT d.*, upper(trim(d.donor_name)) AS donor_key
    FROM donations d, params p
    WHERE d.amount >= p.limit_amount * p.near_limit_ratio
      AND d.donation_date IS NOT NULL
),
keyed AS (
    SELECT recipient_id, recipient_name, 'employer' AS shared_by, upper(trim(donor_employer)) AS shared_value,
           donor_key, donor_name, donation_id, amount, donation_date
    FROM maxed
    WHERE nullif(trim(donor_employer), '') IS NOT NULL
      AND upper(trim(donor_employer)) NOT IN (
          'SELF', 'SELF EMPLOYED', 'SELF-EMPLOYED', 'RETIRED', 'NONE', 'N/A', 'NA',
          'NOT EMPLOYED', 'UNEMPLOYED', 'HOMEMAKER', 'STUDENT',
          'INFORMATION REQUESTED', 'INFORMATION REQUESTED PER BEST EFFORTS', 'REQUESTED'
      )
    UNION ALL
    SELECT recipient_id, recipient_name, 'postcode', upper(replace(trim(donor_postcode), ' ', '')),
           donor_key, donor_name, donation_id, amount, donation_date
    FROM maxed
    WHERE nullif(trim(donor_postcode), '') IS NOT NULL
),
anchors AS (
    SELECT DISTINCT recipient_id, shared_by, shared_value, donation_date AS window_start FROM keyed
),
windows AS (
    SELECT a.recipient_id, a.shared_by, a.shared_value, a.window_start,
           max(k.donation_date) AS window_end,
           min(k.recipient_name) AS recipient_name,
           count(DISTINCT k.donor_key) AS donors,
           count(*) AS donations,
           sum(k.amount) AS total_amount,
           array_to_string(list_sort(list(DISTINCT k.donor_name)), ' | ') AS donor_names
    FROM anchors a
    JOIN keyed k
      ON k.recipient_id = a.recipient_id
     AND k.shared_by = a.shared_by
     AND k.shared_value = a.shared_value
     AND k.donation_date BETWEEN a.window_start AND a.window_start + (SELECT window_days FROM params)
    GROUP BY 1, 2, 3, 4
    HAVING count(DISTINCT k.donor_key) >= (SELECT min_donors FROM params)
)
SELECT recipient_id || '|' || shared_by || '|' || shared_value AS candidate_id,
       recipient_id, recipient_name, shared_by, shared_value, window_start, window_end,
       donors, donations, total_amount, donor_names
FROM windows
QUALIFY row_number() OVER (PARTITION BY recipient_id, shared_by, shared_value
                           ORDER BY donors DESC, total_amount DESC, window_start) = 1
ORDER BY donors DESC, total_amount DESC, candidate_id
LIMIT ?
