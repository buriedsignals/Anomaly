
            WITH per_q AS (
                SELECT
                    a.general_issue_code,
                    f.filing_year,
                    f.filing_period,
                    count(DISTINCT f.registrant_id) AS registrants,
                    sum(coalesce(f.income, 0)) AS total_income
                FROM senate_lobbying_activities a
                JOIN senate_filings f USING (filing_uuid)
                WHERE f.filing_type IN ('Q1','Q2','Q3','Q4')
                  AND a.general_issue_code IS NOT NULL
                GROUP BY 1,2,3
            ),
            ordered AS (
                SELECT
                    general_issue_code, filing_year, filing_period, registrants, total_income,
                    lag(total_income) OVER (PARTITION BY general_issue_code
                                            ORDER BY filing_year, filing_period) AS prior_income,
                    lag(registrants) OVER (PARTITION BY general_issue_code
                                           ORDER BY filing_year, filing_period) AS prior_registrants
                FROM per_q
            )
            SELECT *,
                   CASE WHEN prior_income > 0 THEN round(100.0 * (total_income - prior_income) / prior_income, 1) END AS income_delta_pct,
                   CASE WHEN prior_registrants > 0 THEN round(100.0 * (registrants - prior_registrants) / prior_registrants, 1) END AS registrants_delta_pct
            FROM ordered
            WHERE prior_income IS NOT NULL
              AND prior_income > 0
              AND abs((total_income - prior_income) / prior_income) * 100 >= 25
            ORDER BY abs(total_income - prior_income) DESC
            LIMIT 500
        
