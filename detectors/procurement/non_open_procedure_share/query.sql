WITH processes AS (
    SELECT DISTINCT process_id, buyer_id, buyer_name, lower(procurement_method) AS method
    FROM procurement_processes
),
buyers AS (
    SELECT
        buyer_id,
        min(buyer_name) AS buyer_name,
        count(DISTINCT process_id) FILTER (WHERE method IS NOT NULL) AS processes,
        count(DISTINCT process_id) FILTER (WHERE method IS NULL) AS unknown_method_processes,
        count(DISTINCT process_id) FILTER (WHERE method IN ('limited', 'direct')) AS non_open_processes
    FROM processes
    GROUP BY buyer_id
    HAVING count(DISTINCT process_id) FILTER (WHERE method IS NOT NULL) >= ?
),
shares AS (
    SELECT *, non_open_processes / processes AS non_open_share FROM buyers
),
fence AS (
    SELECT quantile_cont(non_open_share, 0.75)
           + 1.5 * (quantile_cont(non_open_share, 0.75) - quantile_cont(non_open_share, 0.25)) AS upper_fence
    FROM shares
)
SELECT
    buyer_id,
    buyer_name,
    processes,
    unknown_method_processes,
    non_open_processes,
    round(non_open_share, 4) AS non_open_share,
    round(upper_fence, 4) AS iqr_upper_fence,
    non_open_share >= upper_fence AS above_iqr_fence
FROM shares, fence
WHERE non_open_share >= ?
ORDER BY non_open_share DESC, processes DESC, buyer_id
LIMIT ?
