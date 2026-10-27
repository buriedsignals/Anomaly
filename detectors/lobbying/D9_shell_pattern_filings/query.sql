WITH activity_text AS (
    SELECT registration_id,
           string_agg(coalesce(description, ''), ' ' ORDER BY activity_index) AS act_text
    FROM lobbying_activities GROUP BY 1
),
lobbyist_text AS (
    SELECT registration_id,
           string_agg(coalesce(former_public_office, ''), ' | ') AS pos_text
    FROM lobbyists GROUP BY 1
),
scored AS (
    SELECT
        r.registration_id, r.period_start, r.filing_type,
        r.registrant_name, r.client_name,
        r.client_description AS client_desc,
        r.spend_high AS spend, r.url,
        (lower(coalesce(r.client_description, '')) LIKE '%sovereign%')::int AS sig_sovereign_client,
        (lower(coalesce(r.client_description, '')) LIKE '%established government%')::int AS sig_established_govt,
        (lower(coalesce(actv.act_text, '')) LIKE '%empress%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%annuit coeptis%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%king solomon%' OR
         lower(coalesce(actv.act_text, '')) LIKE '%sui generis%')::int AS sig_esoteric_terms,
        (lower(coalesce(lt.pos_text, '')) LIKE '%empress%' OR
         lower(coalesce(lt.pos_text, '')) LIKE '%head of state%' OR
         lower(coalesce(lt.pos_text, '')) LIKE '%assumed the presiden%' OR
         lower(coalesce(lt.pos_text, '')) LIKE '%queen%')::int AS sig_self_styled_title,
        (coalesce(r.posted_by_name, '') LIKE '%/%/%' OR coalesce(r.posted_by_name, '') LIKE '%LLC%')::int AS sig_posted_by_llc_slashes,
        (upper(coalesce(r.client_name, '')) LIKE '%GLOBAL PUBLIC BENEFIT%')::int AS sig_global_pbc_naming
    FROM lobbying_registrations r
    LEFT JOIN activity_text actv USING (registration_id)
    LEFT JOIN lobbyist_text lt USING (registration_id)
)
SELECT
    registration_id, period_start, filing_type,
    registrant_name, client_name, client_desc, spend,
    (sig_sovereign_client + sig_established_govt + sig_esoteric_terms +
     sig_self_styled_title + sig_posted_by_llc_slashes + sig_global_pbc_naming) AS shell_score,
    sig_sovereign_client, sig_established_govt, sig_esoteric_terms,
    sig_self_styled_title, sig_posted_by_llc_slashes, sig_global_pbc_naming,
    url
FROM scored
WHERE (sig_sovereign_client + sig_established_govt + sig_esoteric_terms +
       sig_self_styled_title + sig_posted_by_llc_slashes + sig_global_pbc_naming) >= ?
ORDER BY shell_score DESC, spend DESC NULLS LAST, registration_id
LIMIT ?
