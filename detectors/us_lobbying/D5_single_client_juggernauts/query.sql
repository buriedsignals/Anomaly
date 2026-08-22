
            SELECT
                registrant_id,
                any_value(registrant_name) AS registrant_name,
                count(DISTINCT client_id) AS distinct_clients,
                count(DISTINCT filing_uuid) AS filings,
                sum(coalesce(income, 0)) AS total_income,
                min(filing_year) AS earliest_year,
                max(filing_year) AS latest_year,
                string_agg(DISTINCT client_name, ' | ') AS clients
            FROM senate_filings
            WHERE filing_type IN ('Q1','Q2','Q3','Q4')
            GROUP BY 1
            HAVING distinct_clients BETWEEN 1 AND 2
               AND total_income >= ?
            ORDER BY total_income DESC
            LIMIT ?
        
