WITH monthly AS (
    SELECT
        registrant_id, any_value(registrant_name) AS registrant_name, institution,
        CAST(date_trunc('month', contact_date) AS DATE) AS month,
        count(DISTINCT contact_id) AS contacts,
        string_agg(DISTINCT official_name, ' | ') AS officials
    FROM lobbying_contacts
    WHERE contact_date IS NOT NULL AND institution IS NOT NULL
    GROUP BY registrant_id, institution, month
),
spans AS (
    SELECT registrant_id, institution,
           sum(contacts) AS total_contacts,
           date_diff('month', min(month), max(month)) + 1 AS active_months
    FROM monthly
    GROUP BY registrant_id, institution
)
SELECT
    m.registrant_id, m.registrant_name, m.institution, m.month, m.contacts,
    s.total_contacts, s.active_months,
    round(s.total_contacts / s.active_months, 2) AS mean_per_month,
    round(m.contacts / (s.total_contacts / s.active_months), 2) AS burst_ratio,
    m.officials
FROM monthly m
JOIN spans s USING (registrant_id, institution)
WHERE m.contacts >= ?
  AND m.contacts / (s.total_contacts / s.active_months) >= ?
ORDER BY burst_ratio DESC, m.contacts DESC, m.registrant_id, m.month
LIMIT ?
