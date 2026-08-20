WITH frequencies AS (
    SELECT "group" AS level_value, COUNT(*) AS level_count
    FROM "{{table_id}}"
    WHERE "group" IS NOT NULL
    GROUP BY "group"
    HAVING COUNT(*) >= 1
),
total AS (
    SELECT SUM(level_count) AS observation_count
    FROM frequencies
),
eligible AS (
    SELECT
        'level-' || CAST(level_value AS VARCHAR) AS candidate_id,
        'rarity' AS category,
        'medium' AS severity,
        level_value,
        level_count,
        observation_count,
        level_count::DOUBLE / NULLIF(observation_count, 0) AS level_fraction
    FROM frequencies, total
    WHERE level_count::DOUBLE / NULLIF(observation_count, 0) <= ?
)
SELECT candidate_id, category, severity, level_value, level_count,
       observation_count, level_fraction
FROM eligible
ORDER BY level_count, candidate_id;
