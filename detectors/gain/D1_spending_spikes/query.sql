
            WITH quarterly AS (
                SELECT
                    registrant_id,
                    registrant_name,
                    filing_year,
                    filing_period,
                    sum(coalesce(income, 0)) AS total_income,
                    count(*) AS n_filings
                FROM senate_filings
                WHERE filing_type IN ('Q1','Q2','Q3','Q4')
                  AND income IS NOT NULL
                GROUP BY 1,2,3,4
            ),
            windowed AS (
                SELECT
                    registrant_id, registrant_name, filing_year, filing_period, total_income,
                    avg(total_income) OVER (PARTITION BY registrant_id ORDER BY filing_year, filing_period
                                            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prior_mean,
                    stddev_pop(total_income) OVER (PARTITION BY registrant_id ORDER BY filing_year, filing_period
                                                   ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prior_sd,
                    count(*) OVER (PARTITION BY registrant_id ORDER BY filing_year, filing_period
                                   ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prior_n
                FROM quarterly
            )
            SELECT
                registrant_id, registrant_name, filing_year, filing_period,
                total_income, prior_mean, prior_sd, prior_n,
                CASE WHEN prior_sd > 0 THEN (total_income - prior_mean) / prior_sd END AS z_score
            FROM windowed
            WHERE prior_n >= 3
              AND prior_sd > 0
              AND total_income >= 50000
              AND abs((total_income - prior_mean) / prior_sd) >= 2.0
            ORDER BY abs((total_income - prior_mean) / prior_sd) DESC
            LIMIT 200
        
