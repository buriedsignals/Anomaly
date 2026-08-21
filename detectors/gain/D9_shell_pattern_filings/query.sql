
            WITH activity_text AS (
                SELECT filing_uuid,
                       string_agg(coalesce(description,''), ' ' ORDER BY activity_index) AS act_text
                FROM senate_lobbying_activities GROUP BY 1
            ),
            lobbyist_text AS (
                SELECT filing_uuid,
                       string_agg(coalesce(covered_position,''), ' | ') AS pos_text
                FROM senate_activity_lobbyists GROUP BY 1
            ),
            scored AS (
                SELECT
                    f.filing_uuid,
                    f.filing_year, f.filing_period, f.filing_type,
                    f.registrant_name, f.client_name,
                    f.client_general_description AS client_desc,
                    f.income, f.url,
                    -- Shell-pattern signals (each adds 1 to score)
                    (lower(coalesce(f.client_general_description,'')) LIKE '%sovereign%')::int                              AS sig_sovereign_client,
                    (lower(coalesce(f.client_general_description,'')) LIKE '%established government%')::int                 AS sig_established_govt,
                    (lower(coalesce(actv.act_text,'')) LIKE '%empress%' OR
                     lower(coalesce(actv.act_text,'')) LIKE '%annuit coeptis%' OR
                     lower(coalesce(actv.act_text,'')) LIKE '%king solomon%' OR
                     lower(coalesce(actv.act_text,'')) LIKE '%sui generis%')::int                                              AS sig_esoteric_terms,
                    (lower(coalesce(lt.pos_text,'')) LIKE '%empress%' OR
                     lower(coalesce(lt.pos_text,'')) LIKE '%head of state%' OR
                     lower(coalesce(lt.pos_text,'')) LIKE '%assumed the presiden%' OR
                     lower(coalesce(lt.pos_text,'')) LIKE '%queen%')::int                                                    AS sig_self_styled_title,
                    (f.posted_by_name LIKE '%/%/%' OR f.posted_by_name LIKE '%LLC%')::int                                    AS sig_posted_by_llc_slashes,
                    (upper(coalesce(f.client_name,'')) LIKE '%GLOBAL PUBLIC BENEFIT%')::int                                  AS sig_global_pbc_naming
                FROM senate_filings f
                LEFT JOIN activity_text actv USING (filing_uuid)
                LEFT JOIN lobbyist_text lt USING (filing_uuid)
            )
            SELECT
                filing_uuid, filing_year, filing_period, filing_type,
                registrant_name, client_name, client_desc, income,
                (sig_sovereign_client + sig_established_govt + sig_esoteric_terms +
                 sig_self_styled_title + sig_posted_by_llc_slashes + sig_global_pbc_naming) AS shell_score,
                sig_sovereign_client, sig_established_govt, sig_esoteric_terms,
                sig_self_styled_title, sig_posted_by_llc_slashes, sig_global_pbc_naming,
                url
            FROM scored
            WHERE (sig_sovereign_client + sig_established_govt + sig_esoteric_terms +
                   sig_self_styled_title + sig_posted_by_llc_slashes + sig_global_pbc_naming) >= 2
            ORDER BY shell_score DESC, income DESC NULLS LAST
            LIMIT 100
        
