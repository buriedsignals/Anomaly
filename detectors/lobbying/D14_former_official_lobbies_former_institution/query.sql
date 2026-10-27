WITH former AS (
    SELECT DISTINCT
        l.lobbyist_id, l.name, l.former_public_office, l.former_office_institution,
        l.former_office_end, r.registrant_id,
        lower(trim(l.former_office_institution)) AS former_key
    FROM lobbyists l
    JOIN lobbying_registrations r USING (registration_id)
    WHERE length(trim(coalesce(l.former_office_institution, ''))) >= 3
),
matches AS (
    SELECT
        f.lobbyist_id, f.name, f.former_public_office, f.former_office_institution,
        f.former_office_end, c.registrant_id, c.registrant_name, c.institution,
        c.contact_id, c.contact_date, c.official_name
    FROM former f
    JOIN lobbying_contacts c ON c.registrant_id = f.registrant_id
    WHERE (lower(trim(c.institution)) = f.former_key
           OR (length(f.former_key) >= 6 AND strpos(lower(c.institution), f.former_key) > 0)
           OR (length(trim(c.institution)) >= 6 AND strpos(f.former_key, lower(trim(c.institution))) > 0))
      AND (f.former_office_end IS NULL
           OR (c.contact_date >= f.former_office_end
               AND c.contact_date <= f.former_office_end + CAST(? AS INTEGER)))
)
SELECT
    lobbyist_id, any_value(name) AS name,
    any_value(former_public_office) AS former_public_office,
    former_office_institution, max(former_office_end) AS former_office_end,
    registrant_id, any_value(registrant_name) AS registrant_name,
    any_value(institution) AS contacted_institution,
    count(DISTINCT contact_id) AS contacts,
    min(contact_date) AS first_contact,
    max(contact_date) AS last_contact,
    min(contact_date) - max(former_office_end) AS days_from_leaving_to_first_contact,
    string_agg(DISTINCT official_name, ' | ') AS officials
FROM matches
GROUP BY lobbyist_id, former_office_institution, registrant_id, lower(trim(institution))
ORDER BY contacts DESC, days_from_leaving_to_first_contact NULLS LAST, lobbyist_id
LIMIT ?
