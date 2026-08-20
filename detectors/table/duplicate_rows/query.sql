WITH grouped AS (
    SELECT *, COUNT(*) AS duplicate_count
    FROM "{{table_id}}"
    GROUP BY ALL
    HAVING COUNT(*) >= 1
),
qualifying AS (
    SELECT
        'row-' || COALESCE(CAST("id" AS VARCHAR), 'null') AS candidate_id,
        'duplication' AS category,
        'medium' AS severity,
        duplicate_count
    FROM grouped
    WHERE duplicate_count >= ?
)
SELECT candidate_id, category, severity, duplicate_count,
       duplicate_count AS observation_count
FROM qualifying
ORDER BY duplicate_count DESC, candidate_id;
