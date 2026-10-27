SELECT
    r.registration_id,
    r.period_start,
    r.registrant_name,
    r.client_name,
    r.client_country,
    r.client_ppb_country,
    fe.foreign_entity_name,
    fe.country AS foreign_entity_country,
    fe.ppb_country AS foreign_entity_ppb,
    r.spend_high AS spend,
    r.url
FROM lobbying_foreign_entities fe
JOIN lobbying_registrations r USING (registration_id)
ORDER BY r.spend_high DESC NULLS LAST, r.registration_id, fe.foreign_entity_name
LIMIT ?
