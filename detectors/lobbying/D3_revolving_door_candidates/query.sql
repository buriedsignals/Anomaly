WITH former AS (
    SELECT
        lobbyist_id,
        any_value(name) AS name,
        any_value(former_public_office) AS sample_office,
        any_value(former_office_institution) AS sample_institution,
        max(former_office_end) AS latest_office_end,
        count(DISTINCT registration_id) AS registrations_with_lobbyist,
        count(DISTINCT former_public_office) AS distinct_offices
    FROM lobbyists
    WHERE length(trim(coalesce(former_public_office, ''))) >= 4
      AND lower(trim(former_public_office)) NOT IN ('none', 'n/a', 'null', 'not applicable')
    GROUP BY lobbyist_id
)
SELECT
    f.*,
    (
        SELECT string_agg(DISTINCT coalesce(r.client_name, r.registrant_name), ' | ')
        FROM lobbyists l
        JOIN lobbying_registrations r USING (registration_id)
        WHERE l.lobbyist_id = f.lobbyist_id
    ) AS lobbied_for
FROM former f
ORDER BY registrations_with_lobbyist DESC, lobbyist_id
LIMIT ?
