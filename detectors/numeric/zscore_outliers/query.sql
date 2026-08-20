WITH stats AS (
    SELECT
        AVG("amount") AS mean_amount,
        STDDEV_POP("amount") AS stddev_amount,
        COUNT("amount") AS value_count,
        SUM(CAST("amount" AS DOUBLE)) AS value_sum,
        SUM(CAST("amount" AS DOUBLE) * CAST("amount" AS DOUBLE)) AS square_sum
    FROM "{{table_id}}"
    WHERE "amount" IS NOT NULL
),
scored AS (
    SELECT
        "id",
        "amount",
        mean_amount,
        stddev_amount,
        ABS("amount" - mean_amount) / NULLIF(stddev_amount, 0) AS global_zscore,
        CASE
            WHEN value_count > 2 THEN
                ABS("amount" - ((value_sum - "amount") / (value_count - 1)))
                / NULLIF(
                    SQRT(
                        GREATEST(
                            0,
                            ((square_sum - ("amount" * "amount")) / (value_count - 1))
                            - POWER((value_sum - "amount") / (value_count - 1), 2)
                        )
                    ),
                    0
                )
            ELSE ABS("amount" - mean_amount) / NULLIF(stddev_amount, 0)
        END AS z_score
    FROM "{{table_id}}", stats
    WHERE "amount" IS NOT NULL
)
SELECT
    'row-' || COALESCE(CAST("id" AS VARCHAR), 'unknown') AS candidate_id,
    'outlier' AS category,
    'medium' AS severity,
    "amount",
    mean_amount,
    stddev_amount,
    global_zscore,
    z_score,
    COUNT(*) OVER () AS observation_count
FROM scored
WHERE z_score >= ?;
