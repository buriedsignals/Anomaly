WITH parameters AS (SELECT upper(trim(?)) AS home_countries),
declared AS (
    SELECT list_transform(string_split(home_countries, '|'), country -> trim(country)) AS countries
    FROM parameters
    WHERE home_countries <> ''
),
inferred AS (
    SELECT register, mode(upper(trim(client_country))) AS home_country
    FROM lobbying_registrations
    WHERE client_country IS NOT NULL AND trim(client_country) <> ''
    GROUP BY register
),
homes AS (
    SELECT register,
           coalesce((SELECT countries FROM declared), [home_country]) AS home_countries
    FROM inferred
)
SELECT
    r.register, r.registration_id, r.period_start,
    r.registrant_id, r.registrant_name,
    coalesce(r.client_name, r.registrant_name) AS represented,
    r.client_country,
    array_to_string(h.home_countries, '|') AS home_countries,
    r.spend_low, r.spend_high, r.url
FROM lobbying_registrations r
JOIN homes h USING (register)
WHERE r.client_country IS NOT NULL
  AND trim(r.client_country) <> ''
  AND NOT list_contains(h.home_countries, upper(trim(r.client_country)))
ORDER BY coalesce(r.spend_high, r.spend_low) DESC NULLS LAST, r.registration_id, represented
LIMIT ?
