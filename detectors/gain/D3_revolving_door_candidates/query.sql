
            WITH personal AS (
                SELECT
                    lobbyist_id,
                    first_name, last_name,
                    any_value(covered_position) AS sample_position,
                    count(DISTINCT filing_uuid) AS filings_with_lobbyist,
                    count(DISTINCT covered_position) AS distinct_positions
                FROM senate_activity_lobbyists
                WHERE covered_position IS NOT NULL AND length(covered_position) >= 12
                GROUP BY 1,2,3
            ),
            with_clients AS (
                SELECT
                    p.*,
                    (
                        SELECT string_agg(DISTINCT f.client_name, ' | ')
                        FROM senate_activity_lobbyists al
                        JOIN senate_filings f USING (filing_uuid)
                        WHERE al.lobbyist_id = p.lobbyist_id
                          AND f.client_name IS NOT NULL
                    ) AS clients_lobbied_for
                FROM personal p
            )
            SELECT *
            FROM with_clients
            ORDER BY filings_with_lobbyist DESC
            LIMIT 500
        
