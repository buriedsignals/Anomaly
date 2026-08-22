
            WITH norm_sf AS (
                SELECT DISTINCT
                    f.filing_uuid, f.registrant_name, f.client_name,
                    f.client_country, f.client_ppb_country,
                    f.filing_year, f.income, f.url,
                    upper(regexp_replace(coalesce(f.registrant_name,''), '[^A-Z0-9 ]', ' ', 'g')) AS norm_r
                FROM senate_filings f
                WHERE f.filing_year IN (2024, 2025, 2026)
                  AND EXISTS (SELECT 1 FROM senate_foreign_entities fe WHERE fe.filing_uuid = f.filing_uuid)
            ),
            norm_fara AS (
                SELECT DISTINCT
                    upper(regexp_replace(coalesce(registrant_name,''), '[^A-Z0-9 ]', ' ', 'g')) AS norm_r
                FROM fara_registrants
            ),
            activity_text AS (
                SELECT filing_uuid,
                       string_agg(coalesce(description,''), ' ' ORDER BY activity_index) AS act_text
                FROM senate_lobbying_activities GROUP BY 1
            ),
            fp_country_for_filing AS (
                SELECT filing_uuid,
                       string_agg(DISTINCT country, ',' ORDER BY country) AS fe_countries
                FROM senate_foreign_entities GROUP BY 1
            )
            SELECT
                sf.filing_uuid, sf.filing_year,
                sf.registrant_name, sf.client_name,
                sf.client_country, sf.client_ppb_country,
                fp.fe_countries,
                sf.income,
                (sf.client_country IS NOT NULL AND sf.client_country NOT IN ('US','United States of America'))::int AS sig_non_us_client,
                (sf.client_ppb_country IS NOT NULL AND sf.client_ppb_country NOT IN ('US','United States of America'))::int AS sig_non_us_ppb,
                (lower(coalesce(actv.act_text,'')) LIKE '%foreign government%' OR
                 lower(coalesce(actv.act_text,'')) LIKE '%embassy%' OR
                 lower(coalesce(actv.act_text,'')) LIKE '%fara%' OR
                 lower(coalesce(actv.act_text,'')) LIKE '%sanctions%' OR
                 lower(coalesce(actv.act_text,'')) LIKE '%ambassador%')::int AS sig_foreign_gov_topic,
                (lower(coalesce(sf.client_name,'')) LIKE '%national oil%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%state-owned%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%national bank%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%republic of%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%kingdom of%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%ministry of%' OR
                 lower(coalesce(sf.client_name,'')) LIKE '%embassy of%')::int AS sig_soe_pattern,
                sf.url
            FROM norm_sf sf
            LEFT JOIN activity_text actv ON actv.filing_uuid = sf.filing_uuid
            LEFT JOIN fp_country_for_filing fp ON fp.filing_uuid = sf.filing_uuid
            WHERE NOT EXISTS (SELECT 1 FROM norm_fara nf WHERE nf.norm_r = sf.norm_r)
              AND (
                  (sf.client_country IS NOT NULL AND sf.client_country NOT IN ('US','United States of America'))
               OR (sf.client_ppb_country IS NOT NULL AND sf.client_ppb_country NOT IN ('US','United States of America'))
               OR (lower(coalesce(actv.act_text,'')) LIKE '%foreign government%' OR
                   lower(coalesce(actv.act_text,'')) LIKE '%embassy%' OR
                   lower(coalesce(actv.act_text,'')) LIKE '%fara%' OR
                   lower(coalesce(actv.act_text,'')) LIKE '%sanctions%' OR
                   lower(coalesce(actv.act_text,'')) LIKE '%ambassador%')
               OR (lower(coalesce(sf.client_name,'')) LIKE '%national oil%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%state-owned%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%national bank%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%republic of%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%kingdom of%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%ministry of%' OR
                   lower(coalesce(sf.client_name,'')) LIKE '%embassy of%')
              )
            ORDER BY sf.income DESC NULLS LAST
            LIMIT ?
        
