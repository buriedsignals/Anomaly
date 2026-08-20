from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from p2_helpers import NOW, create_p2_case, read_json, register, write_source


DETECTOR_ROOT = Path(__file__).parents[1] / "detectors"
DETECTOR_IDS = (
    "table.missingness_clusters",
    "table.duplicate_rows",
    "numeric.zscore_outliers",
    "numeric.level_shift",
    "categorical.rare_levels",
    "temporal.coverage_gaps",
)
LIMITS = {
    "memory_mb": 64,
    "timeout_seconds": 5,
    "threads": 1,
    "max_output_rows": 2,
}


def _detect_api():
    return importlib.import_module("anomaly.detect")


def _prepared_case(tmp_path: Path, *, source_text: str | None = None) -> Path:
    # Use the existing case/acquire/prepare contracts instead of manufacturing an
    # index. The token is deliberately credential-shaped for the persistence test.
    from anomaly.prepare import prepare_sources
    from anomaly.profile import profile_prepared

    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / "observations.csv",
            source_text
            or (
                "id,group,amount,observed_at,token\n"
                "1,A,10,2026-01-01,sk_live_TESTONLY_DETECTOR_SECRET\n"
                "2,A,11,2026-01-02,sk_live_TESTONLY_DETECTOR_SECRET\n"
                "3,B,100,2026-01-03,sk_live_TESTONLY_DETECTOR_SECRET\n"
                "4,B,,2026-01-10,sk_live_TESTONLY_DETECTOR_SECRET\n"
            ),
        ),
        "observations",
    )
    prepare_sources(root, now=NOW)
    profile_prepared(root, now=NOW)
    return root


def _run(root: Path, detector_ids=DETECTOR_IDS, *, limits=LIMITS):
    recommend = importlib.import_module("anomaly.recommend")
    recommend.recommend_detectors(root, now=NOW, max_detectors=10)
    recommend.approve_detector_plan(
        root,
        list(detector_ids),
        approved_by="test",
        now=NOW,
    )
    return _detect_api().execute_detectors(root, detector_ids, now=NOW, limits=limits)


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _all_persisted_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl", ".yaml", ".sql", ".md"}
    )


def _meta_scalar(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip('"\'')
    return None


def test_detector_catalog_contains_six_deterministic_packages() -> None:
    api = _detect_api()
    metadata = api.load_detector_metadata()
    by_id = {item["id"]: item for item in metadata}

    assert tuple(item["id"] for item in metadata) == tuple(sorted(DETECTOR_IDS))
    assert set(by_id) == set(DETECTOR_IDS)
    for detector_id in DETECTOR_IDS:
        package = DETECTOR_ROOT.joinpath(*detector_id.split("."))
        meta_path = package / "meta.yaml"
        query_path = package / "query.sql"
        assert meta_path.is_file(), detector_id
        assert query_path.is_file(), detector_id
        assert (package / "fixtures" / "input.csv").is_file(), detector_id
        assert (package / "fixtures" / "expected.json").is_file(), detector_id
        metadata_text = meta_path.read_text(encoding="utf-8")
        assert _meta_scalar(metadata_text, "id") == detector_id
        assert _meta_scalar(metadata_text, "version")
        assert _meta_scalar(metadata_text, "group")
        assert _meta_scalar(metadata_text, "query") == "query.sql"
        query = query_path.read_text(encoding="utf-8")
        assert "?" in query, detector_id
        assert not any(word in query.upper() for word in ("CREATE ", "INSERT ", "UPDATE ", "DELETE ", "ATTACH ", "COPY ", "INSTALL ", "LOAD "))


def test_metadata_loader_is_stable_and_does_not_load_case_files(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    marker = root / "case-code-executed"
    (root / "detectors" / "user").mkdir(parents=True)
    (root / "detectors" / "user" / "detector.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )

    metadata_a = _detect_api().load_detector_metadata()
    metadata_b = _detect_api().load_detector_metadata()
    assert metadata_a == metadata_b
    assert not marker.exists()
    assert not any(item["id"].startswith("user.") for item in metadata_a)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE injected AS SELECT 1",
        "INSERT INTO safe_table VALUES (1)",
        "UPDATE safe_table SET value = 1",
        "DELETE FROM safe_table",
        "DROP TABLE safe_table",
        "ALTER TABLE safe_table ADD COLUMN x INTEGER",
        "ATTACH DATABASE 'other.duckdb' AS other",
        "COPY safe_table TO 'outside.csv'",
        "INSTALL httpfs",
        "SELECT * FROM read_csv_auto(?)",
        "SELECT * FROM read_json_auto(?)",
        "SELECT * FROM parquet_scan(?)",
        "SELECT * FROM sqlite_scan(?, 'table')",
        "SELECT * FROM glob(?)",
        "SELECT * FROM query_table(?)",
        "SELECT * FROM json_execute_serialized_sql(?)",
        "SELECT * FROM sqlite_query(?, ?)",
    ],
)
def test_sql_sandbox_rejects_mutating_extension_and_external_reader_queries(sql: str) -> None:
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|mutat|external access)"):
        _detect_api().validate_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT "amount" FROM "tbl_abc" WHERE "group" = ?',
        'SELECT ? AS threshold, count(*) FROM "tbl_abc"',
        'SELECT "id" FROM "tbl_abc" WHERE "id" IN (?, ?)',
    ],
)
def test_sql_sandbox_accepts_quoted_identifiers_and_bound_parameters(sql: str) -> None:
    assert _detect_api().validate_read_only_sql(sql) is None


def test_sql_sandbox_rejects_identifier_injection_and_multiple_statements() -> None:
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|mutat|multiple statement)"):
        _detect_api().validate_read_only_sql('SELECT * FROM "tbl_abc; DROP TABLE x"')
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|mutat|multiple statement)"):
        _detect_api().validate_read_only_sql('SELECT 1; SELECT 2')


def test_execute_uses_read_only_duckdb_and_external_access_is_disabled(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    index = root / "data" / "index.duckdb"
    before = hashlib.sha256(index.read_bytes()).hexdigest()

    _run(root, ("table.missingness_clusters",))

    assert hashlib.sha256(index.read_bytes()).hexdigest() == before
    provenance = next((root / "evidence" / "runs").rglob("provenance.json")).read_text(encoding="utf-8")
    assert '"external_access": false' in provenance
    assert '"read_only": true' in provenance


def test_execute_applies_memory_time_thread_and_output_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = _detect_api()
    observed_threads: list[int] = []
    run_query = api._run_query

    def capture_threads(connection, query, parameters, timeout_seconds, max_output_rows):
        observed_threads.append(connection.execute("SELECT current_setting('threads')").fetchone()[0])
        return run_query(connection, query, parameters, timeout_seconds, max_output_rows)

    monkeypatch.setattr(api, "_run_query", capture_threads)
    root = _prepared_case(tmp_path)
    _run(root, ("table.missingness_clusters",), limits=LIMITS)

    assert observed_threads == [1]

    provenance = next((root / "evidence" / "runs").rglob("provenance.json"))
    record = read_json(provenance)
    assert record["limits"] == LIMITS
    assert record["limits"]["threads"] == 1
    assert record["limits"]["max_output_rows"] == 2

    import pyarrow.parquet as parquet

    outputs = list(provenance.parent.glob("*.parquet"))
    assert outputs
    assert all(parquet.read_table(path).num_rows <= LIMITS["max_output_rows"] for path in outputs)


def test_execute_writes_leads_only_full_parquet_preview_and_provenance(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    _run(root)

    run_dirs = [path for path in (root / "evidence" / "runs").iterdir() if path.is_dir()]
    assert len(run_dirs) == len(DETECTOR_IDS)
    for run_dir in run_dirs:
        parquet_outputs = list(run_dir.glob("*.parquet"))
        assert len(parquet_outputs) == 1
        assert (run_dir / "preview.json").is_file()
        assert (run_dir / "provenance.json").is_file()
        preview = read_json(run_dir / "preview.json")
        if isinstance(preview, list):
            rows = preview
        else:
            rows = preview.get("rows", preview.get("signals", []))
        assert isinstance(rows, list)
        assert all(row.get("status") == "lead" for row in rows)
        provenance = read_json(run_dir / "provenance.json")
        assert provenance["detector_id"] in DETECTOR_IDS
        assert provenance["detector_version"]
        assert provenance["detector_hash"].startswith("sha256:")

    signals = _jsonl(root / "evidence" / "signals.jsonl")
    assert signals
    assert all(row["status"] == "lead" for row in signals)
    assert all(row.get("severity") for row in signals)
    assert not (root / "findings" / "findings.json").exists()
    assert "confirmed" not in json.dumps(signals).lower()
    assert "probable" not in json.dumps(signals).lower()
    assert "supported" not in json.dumps(signals).lower()


def test_signals_jsonl_is_append_only_and_used_snapshots_are_inert(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    signals_path = root / "evidence" / "signals.jsonl"
    prior = {"signal_id": "prior", "status": "lead", "detector_id": "fixture"}
    signals_path.write_text(json.dumps(prior) + "\n", encoding="utf-8")

    _run(root, ("table.duplicate_rows",))

    lines = _jsonl(signals_path)
    assert lines[0] == prior
    snapshots = list((root / "detectors" / "used").glob("*.json"))
    assert snapshots
    for snapshot in snapshots:
        record = read_json(snapshot)
        assert set(("metadata", "implementation_hash", "parameters", "version")) <= set(record)
        assert record["implementation_hash"].startswith("sha256:")
        assert not (snapshot.with_suffix(".py")).exists()


def test_execution_never_runs_code_supplied_inside_case_and_redacts_sensitive_values(
    tmp_path: Path,
) -> None:
    root = _prepared_case(tmp_path)
    marker = root / "case-code-executed"
    used = root / "detectors" / "used"
    (used / "evil.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )

    _run(root, ("numeric.zscore_outliers",))
    assert not marker.exists()
    persisted = _all_persisted_text(root)
    assert "sk_live_TESTONLY_DETECTOR_SECRET" not in persisted
    assert "[redacted]" in persisted or "redacted_" in persisted
    assert not list((root / "detectors" / "used").glob("*.py"))


def test_execution_refuses_unknown_and_case_supplied_detector_ids(tmp_path: Path) -> None:
    root = _prepared_case(tmp_path)
    (root / "detectors" / "used" / "case-detector.json").write_text(
        json.dumps({"id": "case.supplied", "query": "SELECT 1"}), encoding="utf-8"
    )
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|unknown detector|case.supplied)"):
        _run(root, ("case.supplied",))
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|unknown detector|does.not.exist)"):
        _run(root, ("does.not.exist",))


@pytest.mark.parametrize(
    ("detector_id", "required_tokens"),
    [
        ("table.duplicate_rows", ("GROUP BY", "COUNT(", "HAVING")),
        ("categorical.rare_levels", ("GROUP BY", "COUNT(", "HAVING")),
        ("table.missingness_clusters", ("GROUP BY", "COUNT(", "HAVING")),
        ("numeric.zscore_outliers", ("AVG(", "STDDEV")),
        ("numeric.level_shift", ("LAG(", "OVER")),
        ("temporal.coverage_gaps", ("LAG(", "OVER", "DATE")),
    ],
)
def test_detector_queries_compute_data_dependent_semantics(
    detector_id: str, required_tokens: tuple[str, ...]
) -> None:
    query = (
        DETECTOR_ROOT.joinpath(*detector_id.split("."))
        / "query.sql"
    ).read_text(encoding="utf-8").upper()

    assert all(token in query for token in required_tokens), detector_id

def test_duplicate_rows_emits_no_lead_for_all_unique_input(tmp_path: Path) -> None:
    root = _prepared_case(
        tmp_path,
        source_text=(
            "id,group,amount,observed_at,token\n"
            "1,A,10,2026-01-01,token\n"
            "2,A,11,2026-01-02,token\n"
            "3,B,100,2026-01-03,token\n"
            "4,B,101,2026-01-10,token\n"
        ),
    )

    assert _run(root, ("table.duplicate_rows",)) == []
    assert _jsonl(root / "evidence" / "signals.jsonl") == []


def test_rare_levels_emits_no_lead_for_singleton_level(tmp_path: Path) -> None:
    root = _prepared_case(
        tmp_path,
        source_text=(
            "id,group,amount,observed_at,token\n"
            "1,A,10,2026-01-01,token\n"
            "2,A,11,2026-01-02,token\n"
            "3,A,12,2026-01-03,token\n"
            "4,B,100,2026-01-10,token\n"
        ),
    )

    assert _run(root, ("categorical.rare_levels",)) == []
    assert _jsonl(root / "evidence" / "signals.jsonl") == []


def test_detector_execution_does_not_use_fixture_labels_as_signal_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = _detect_api()
    fixture_only = {
        "candidate_id": "fixture-only-candidate",
        "category": "fixture-only-category",
        "severity": "fixture-only-severity",
    }
    monkeypatch.setattr(
        api, "_fixture_signal", lambda _detector_id: fixture_only, raising=False
    )

    root = _prepared_case(tmp_path)
    results = _run(root)
    persisted = _jsonl(root / "evidence" / "signals.jsonl")

    assert results == persisted
    assert all(row["status"] == "lead" for row in persisted)
    actual = {(row["detector_id"], row["candidate_id"]) for row in persisted}
    assert actual == {
        ("table.missingness_clusters", "row-group-B"),
        ("numeric.level_shift", "row-3"),
        ("numeric.zscore_outliers", "row-3"),
        ("temporal.coverage_gaps", "gap-2026-01-03"),
    }
    assert "fixture-only-" not in json.dumps(results)
    assert not actual & {
        ("table.missingness_clusters", "row-group-A"),
        ("table.duplicate_rows", "row-1"),
        ("numeric.zscore_outliers", "row-4"),
        ("numeric.level_shift", "window-2"),
        ("categorical.rare_levels", "level-Z"),
        ("temporal.coverage_gaps", "gap-2026-01-02"),
    }

@pytest.mark.parametrize(
    "namespace",
    (
        "data/prepared",
        "evidence",
        "detectors/used",
    ),
)
def test_parent_symlink_namespaces_are_rejected_before_external_io(
    tmp_path: Path, namespace: str
) -> None:
    root = _prepared_case(tmp_path)
    original = root / namespace
    external = tmp_path / f"external-{namespace.replace('/', '-')}"
    original.rename(external)
    marker = external / "external-marker.txt"
    marker.write_text("must remain untouched", encoding="utf-8")
    if namespace == "detectors/used":
        (external / "evil.py").write_text("must not be inspected", encoding="utf-8")
    before = {
        path.relative_to(external).as_posix(): (
            path.is_dir(),
            path.read_bytes() if path.is_file() else None,
        )
        for path in external.rglob("*")
    }
    original.symlink_to(external, target_is_directory=True)

    from anomaly.semantics import UnsafeCasePathError

    with pytest.raises(UnsafeCasePathError):
        _run(root, ("table.missingness_clusters",))

    after = {
        path.relative_to(external).as_posix(): (
            path.is_dir(),
            path.read_bytes() if path.is_file() else None,
        )
        for path in external.rglob("*")
    }
    assert after == before


@pytest.mark.parametrize(
    "sql",
    (
        "SELECT * FROM 'outside.csv'",
        'SELECT * FROM "outside.parquet"',
        "SELECT * FROM 'outside.json'",
        "SELECT * FROM $$outside.csv$$",
        "SELECT * FROM E'outside.csv'",
        "SELECT * FROM query('SELECT 1')",
        "SELECT * FROM read_duckdb(?)",
        "SELECT * FROM read_json_objects(?)",
    ),
)
def test_sql_sandbox_rejects_implicit_file_relations_and_nested_readers(sql: str) -> None:
    with pytest.raises(Exception, match=r"(?i)(unsafe|forbidden|rejected|external access)"):
        _detect_api().validate_read_only_sql(sql)


