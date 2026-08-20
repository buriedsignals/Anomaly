WITH ordered AS (
    SELECT
        "id",
        "observed_at",
        "amount",
        LAG("amount") OVER (ORDER BY "observed_at", "id") AS previous_amount,
        AVG("amount") OVER (
            ORDER BY "observed_at", "id"
            ROWS BETWEEN ? PRECEDING AND 1 PRECEDING
        ) AS prior_window_mean,
        STDDEV_POP("amount") OVER () AS overall_stddev
    FROM "{{table_id}}"
    WHERE "amount" IS NOT NULL AND "observed_at" IS NOT NULL
)
SELECT
    'row-' || COALESCE(CAST("id" AS VARCHAR), 'unknown') AS candidate_id,
    'distribution-shift' AS category,
    'medium' AS severity,
    "observed_at",
    "amount",
    previous_amount,
    prior_window_mean,
    "amount" - prior_window_mean AS level_delta,
    overall_stddev,
    COUNT(*) OVER () AS observation_count
FROM ordered
WHERE previous_amount IS NOT NULL
  AND ABS("amount" - prior_window_mean) >= COALESCE(overall_stddev, 0);
