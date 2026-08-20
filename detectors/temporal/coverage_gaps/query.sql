WITH ordered AS (
    SELECT
        "id",
        "observed_at",
        LAG("observed_at") OVER (ORDER BY "observed_at", "id") AS previous_observed_at
    FROM "{{table_id}}"
    WHERE "observed_at" IS NOT NULL
),
gaps AS (
    SELECT
        "id",
        previous_observed_at,
        "observed_at",
        DATE_DIFF('day', previous_observed_at, "observed_at") AS gap_days
    FROM ordered
    WHERE previous_observed_at IS NOT NULL
)
SELECT
    'gap-' || CAST(previous_observed_at AS DATE) AS candidate_id,
    'coverage' AS category,
    'medium' AS severity,
    previous_observed_at,
    "observed_at",
    gap_days,
    COUNT(*) OVER () AS observation_count
FROM gaps
WHERE gap_days > ?;
