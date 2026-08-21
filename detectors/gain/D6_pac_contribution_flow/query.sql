
            SELECT
                payee_name,
                honoree_name,
                count(*) AS n_contributions,
                sum(coalesce(amount, 0)) AS total_amount,
                count(DISTINCT filing_uuid) AS distinct_filings,
                count(DISTINCT contributor_name) AS distinct_contributors
            FROM senate_contribution_items
            WHERE payee_name IS NOT NULL OR honoree_name IS NOT NULL
            GROUP BY 1,2
            ORDER BY total_amount DESC NULLS LAST
            LIMIT ?
        
