
            WITH first_filing AS (
                SELECT
                    registrant_id,
                    min(filing_year * 10 + CAST(substr(filing_type, 2, 1) AS INTEGER)) AS first_yp
                FROM senate_filings
                WHERE filing_type IN ('Q1','Q2','Q3','Q4')
                GROUP BY 1
            ),
            recent_qs AS (
                SELECT max(filing_year * 10 + CAST(substr(filing_type, 2, 1) AS INTEGER)) AS max_yp
                FROM senate_filings
                WHERE filing_type IN ('Q1','Q2','Q3','Q4')
            ),
            new_regs AS (
                SELECT ff.registrant_id, ff.first_yp
                FROM first_filing ff, recent_qs r
                WHERE ff.first_yp >= r.max_yp - 2
            )
            SELECT
                f.registrant_id,
                any_value(f.registrant_name) AS registrant_name,
                count(DISTINCT f.filing_uuid) AS filings_in_window,
                count(DISTINCT f.client_id) AS distinct_clients,
                sum(coalesce(f.income, 0)) AS total_income,
                string_agg(DISTINCT f.client_name, ' | ') AS clients
            FROM senate_filings f
            JOIN new_regs nr ON f.registrant_id = nr.registrant_id
            WHERE f.filing_type IN ('Q1','Q2','Q3','Q4')
            GROUP BY 1
            HAVING total_income > 0
            ORDER BY total_income DESC
            LIMIT 200
        
