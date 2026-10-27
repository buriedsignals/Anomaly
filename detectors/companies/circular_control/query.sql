WITH RECURSIVE params AS (SELECT CAST(? AS INTEGER) AS max_depth),
edges AS (
    SELECT DISTINCT company_id AS child, controller_company_id AS parent
    FROM company_controllers
    WHERE controller_company_id IS NOT NULL
      AND ceased_on IS NULL
),
walk(start_id, current_id, path, depth) AS (
    SELECT child, parent, [child, parent], 1
    FROM edges
    UNION ALL
    SELECT w.start_id, e.parent, list_append(w.path, e.parent), w.depth + 1
    FROM walk w
    JOIN edges e ON e.child = w.current_id
    WHERE w.current_id <> w.start_id
      AND w.depth < (SELECT max_depth FROM params)
      AND (e.parent = w.start_id OR NOT list_contains(w.path, e.parent))
),
cycles AS (
    SELECT start_id, depth, array_to_string(path, ' > ') AS cycle_path
    FROM walk
    WHERE current_id = start_id
)
SELECT start_id AS candidate_id, start_id AS company_id, depth AS cycle_length, cycle_path
FROM cycles
QUALIFY row_number() OVER (PARTITION BY start_id ORDER BY depth, cycle_path) = 1
ORDER BY cycle_length, candidate_id
LIMIT ?
