
            SELECT
                registrant_id, registrant_name,
                count(*) AS quarterly_filings_with_null_income,
                count(DISTINCT client_id) AS distinct_clients,
                min(filing_year || '-' || filing_period) AS first_seen,
                max(filing_year || '-' || filing_period) AS last_seen
            FROM senate_filings
            WHERE filing_type IN ('Q1','Q2','Q3','Q4')
              AND income IS NULL
            GROUP BY 1,2
            HAVING count(*) >= ?
            ORDER BY quarterly_filings_with_null_income DESC, distinct_clients DESC
            LIMIT ?
        
