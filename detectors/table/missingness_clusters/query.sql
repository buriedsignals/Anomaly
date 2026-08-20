WITH total AS (
    SELECT COUNT(*) AS observation_count
    FROM "{{table_id}}"
),
clusters AS (
    SELECT "group" AS cluster_value, COUNT(*) AS missing_count
    FROM "{{table_id}}"
    WHERE "amount" IS NULL AND "group" IS NOT NULL
    GROUP BY "group"
    HAVING COUNT(*) >= 1
)
SELECT
    'row-group-' || CAST(cluster_value AS VARCHAR) AS candidate_id,
    'completeness' AS category,
    'medium' AS severity,
    cluster_value,
    missing_count,
    observation_count,
    missing_count::DOUBLE / NULLIF(observation_count, 0) AS missing_fraction
FROM clusters, total
WHERE missing_count::DOUBLE / NULLIF(observation_count, 0) >= ?;
