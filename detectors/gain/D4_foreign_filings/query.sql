
            SELECT
                f.filing_uuid,
                f.filing_year,
                f.filing_period,
                f.registrant_name,
                f.client_name,
                f.client_country,
                f.client_ppb_country,
                fe.foreign_entity_name,
                fe.country AS foreign_entity_country,
                fe.ppb_country AS foreign_entity_ppb,
                f.income,
                f.url
            FROM senate_foreign_entities fe
            JOIN senate_filings f USING (filing_uuid)
            ORDER BY f.income DESC NULLS LAST
            LIMIT ?
        
