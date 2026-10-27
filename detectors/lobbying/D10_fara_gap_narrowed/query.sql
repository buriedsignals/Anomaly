WITH norm_sf AS (
    SELECT DISTINCT
        r.registration_id, r.registrant_name, r.client_name,
        r.client_country, r.client_ppb_country,
        year(r.period_start) AS filing_year, r.spend_high AS spend, r.url,
        trim(regexp_replace(regexp_replace(upper(coalesce(r.registrant_name, '')), '[^A-Z0-9]+', ' ', 'g'), ' AND ', ' ', 'g')) AS norm_r
    FROM lobbying_registrations r
    WHERE year(r.period_start) IN (2024, 2025, 2026)
      AND EXISTS (SELECT 1 FROM lobbying_foreign_entities fe WHERE fe.registration_id = r.registration_id)
),
norm_fara AS (
    SELECT DISTINCT
        trim(regexp_replace(regexp_replace(upper(coalesce(registrant_name, '')), '[^A-Z0-9]+', ' ', 'g'), ' AND ', ' ', 'g')) AS norm_r
    FROM foreign_agent_registrants
),
activity_text AS (
    SELECT registration_id,
           string_agg(coalesce(description, ''), ' ' ORDER BY activity_index) AS act_text
    FROM lobbying_activities GROUP BY 1
),
fe_countries AS (
    SELECT registration_id,
           string_agg(DISTINCT country, ',' ORDER BY country) AS fe_countries
    FROM lobbying_foreign_entities GROUP BY 1
),
flagged AS (
    SELECT
        sf.*, fp.fe_countries,
        (sf.client_country IS NOT NULL AND sf.client_country NOT IN ('US', 'United States of America'))::int AS sig_non_us_client,
        (sf.client_ppb_country IS NOT NULL AND sf.client_ppb_country NOT IN ('US', 'United States of America'))::int AS sig_non_us_ppb,
        (lower(coalesce(actv.act_text, '')) LIKE '%foreign government%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%embassy%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%fara%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%sanctions%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%ambassador%')::int AS sig_foreign_gov_topic,
        (lower(coalesce(sf.client_name, '')) LIKE '%national oil%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%state-owned%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%national bank%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%republic of%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%kingdom of%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%ministry of%' OR
         lower(coalesce(sf.client_name, '')) LIKE '%embassy of%')::int AS sig_soe_pattern
    FROM norm_sf sf
    LEFT JOIN activity_text actv ON actv.registration_id = sf.registration_id
    LEFT JOIN fe_countries fp ON fp.registration_id = sf.registration_id
    WHERE NOT EXISTS (SELECT 1 FROM norm_fara nf WHERE nf.norm_r = sf.norm_r)
)
SELECT
    registration_id, filing_year, registrant_name, client_name,
    client_country, client_ppb_country, fe_countries, spend,
    sig_non_us_client, sig_non_us_ppb, sig_foreign_gov_topic, sig_soe_pattern, url
FROM flagged
WHERE sig_non_us_client + sig_non_us_ppb + sig_foreign_gov_topic + sig_soe_pattern > 0
ORDER BY spend DESC NULLS LAST, registration_id
LIMIT ?
