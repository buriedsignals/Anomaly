from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import threading
from typing import Any, Callable

import duckdb
import pytest

from p2_helpers import NOW, create_p2_case, register, write_source


TABLE_ALPHA = "tbl_" + ("a" * 64)
TABLE_BETA = "tbl_" + ("b" * 64)
SOURCE_ALPHA_HASH = "sha256:" + ("1" * 64)
SOURCE_BETA_HASH = "sha256:" + ("2" * 64)
DETECTOR_ALPHA_HASH = "sha256:" + ("3" * 64)
DETECTOR_BETA_HASH = "sha256:" + ("4" * 64)
DETECTOR_ROOT = Path(__file__).parents[1] / "detectors"
DETECTOR_LIMITS = {
    "memory_mb": 64,
    "timeout_seconds": 5,
    "threads": 1,
    "max_output_rows": 2,
}


def _api():
    return importlib.import_module("anomaly.search")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _seed_search_case(tmp_path: Path) -> tuple[Path, tuple[Path, ...]]:
    root = tmp_path / "case"
    signals = [
        {
            "signal_id": "signal-alpha",
            "rank": 1,
            "status": "lead",
            "category": "outlier",
            "severity": "high",
            "confidence": 0.73,
            "statement": "Acme has a deterministic overbilling variance.",
            "warnings": ["Compare against the seasonal baseline."],
            "redacted": True,
            "preview": {
                "vendor": "Acme",
                "amount": 120,
                "access_token": "[redacted]",
                "note": "Bearer [redacted]",
            },
            "evidence_refs": [
                {
                    "source_id": "payments",
                    "table_id": TABLE_ALPHA,
                    "candidate_id": "row-1",
                }
            ],
            "source_hash": SOURCE_ALPHA_HASH,
            "detector_hash": DETECTOR_ALPHA_HASH,
            "run_id": "run-alpha",
            "detector_id": "numeric.zscore_outliers",
            "table_id": TABLE_ALPHA,
            "private_context": "classified-swordfish",
        },
        {
            "signal_id": "signal-beta",
            "rank": 2,
            "status": "lead",
            "category": "outlier",
            "severity": "low",
            "confidence": 0.25,
            "statement": "Beta remains within its expected range.",
            "warnings": [],
            "redacted": True,
            "preview": {"vendor": "Beta", "amount": 12},
            "evidence_refs": [
                {
                    "source_id": "payments",
                    "table_id": TABLE_ALPHA,
                    "candidate_id": "row-2",
                }
            ],
            "source_hash": SOURCE_ALPHA_HASH,
            "detector_hash": DETECTOR_ALPHA_HASH,
            "run_id": "run-alpha",
            "detector_id": "numeric.zscore_outliers",
            "table_id": TABLE_ALPHA,
        },
        {
            "signal_id": "signal-gamma",
            "rank": 1,
            "status": "lead",
            "category": "rare-level",
            "severity": "medium",
            "confidence": 0.51,
            "statement": "Gamma is a rare supplier.",
            "warnings": ["Review the sparse cohort."],
            "redacted": True,
            "preview": {"vendor": "Gamma", "count": 1},
            "evidence_refs": [
                {
                    "source_id": "vendors",
                    "table_id": TABLE_BETA,
                    "candidate_id": "row-3",
                }
            ],
            "source_hash": SOURCE_BETA_HASH,
            "detector_hash": DETECTOR_BETA_HASH,
            "run_id": "run-beta",
            "detector_id": "categorical.rare_levels",
            "table_id": TABLE_BETA,
        },
    ]
    signals_path = root / "evidence" / "signals.jsonl"
    signals_path.parent.mkdir(parents=True)
    signals_path.write_text(
        "".join(json.dumps(signal, sort_keys=True) + "\n" for signal in signals),
        encoding="utf-8",
    )

    run_alpha = root / "evidence" / "runs" / "run-alpha"
    run_beta = root / "evidence" / "runs" / "run-beta"
    alpha_metadata = root / "detectors" / "used" / "numeric__zscore_outliers.json"
    beta_metadata = root / "detectors" / "used" / "categorical__rare_levels.json"
    alpha_snapshot = {
        "schema_version": 1,
        "implementation_hash": DETECTOR_ALPHA_HASH,
        "version": "1.0.0",
        "metadata": {
            "id": "numeric.zscore_outliers",
            "title": "Allocation variance",
            "description": "Finds unusual spending values.",
            "group": "numeric",
            "signal_category": "outlier",
            "severity": "high",
            "assumptions": ["Amounts are comparable."],
            "false_positives": ["Seasonality."],
        },
    }
    beta_snapshot = {
        "schema_version": 1,
        "implementation_hash": DETECTOR_BETA_HASH,
        "version": "1.0.0",
        "metadata": {
            "id": "categorical.rare_levels",
            "title": "Rare levels",
            "description": "Finds sparse categories.",
            "group": "categorical",
            "signal_category": "rare-level",
            "severity": "medium",
            "assumptions": ["Categories are stable."],
            "false_positives": ["New suppliers."],
        },
    }
    _write_json(alpha_metadata, alpha_snapshot)
    _write_json(beta_metadata, beta_snapshot)
    _write_json(
        run_alpha / "provenance.json",
        {
            "schema_version": 2,
            "run_id": "run-alpha",
            "detector_id": "numeric.zscore_outliers",
            "detector_hash": DETECTOR_ALPHA_HASH,
            "detector_snapshot": "detectors/used/numeric__zscore_outliers.json",
            "detector_snapshot_hash": _canonical_json_hash(alpha_snapshot),
            "executed_at": "2026-08-21T10:00:00+00:00",
            "table_ids": [TABLE_ALPHA],
            "table_sources": {
                TABLE_ALPHA: {
                    "source_id": "payments",
                    "source_hash": SOURCE_ALPHA_HASH,
                }
            },
        },
    )
    _write_json(
        run_beta / "provenance.json",
        {
            "schema_version": 2,
            "run_id": "run-beta",
            "detector_id": "categorical.rare_levels",
            "detector_hash": DETECTOR_BETA_HASH,
            "detector_snapshot": "detectors/used/categorical__rare_levels.json",
            "detector_snapshot_hash": _canonical_json_hash(beta_snapshot),
            "executed_at": "2026-08-22T10:00:00+00:00",
            "table_ids": [TABLE_BETA],
            "table_sources": {
                TABLE_BETA: {
                    "source_id": "vendors",
                    "source_hash": SOURCE_BETA_HASH,
                }
            },
        },
    )
    alpha_output = run_alpha / "signals.parquet"
    beta_output = run_beta / "signals.parquet"
    alpha_output.write_bytes(b"canonical-alpha-output")
    beta_output.write_bytes(b"canonical-beta-output")

    index_path = root / "data" / "index.duckdb"
    index_path.parent.mkdir(parents=True)
    index_path.write_bytes(b"canonical-read-only-index")
    canonical_paths = (
        signals_path,
        run_alpha / "provenance.json",
        run_beta / "provenance.json",
        alpha_output,
        beta_output,
        alpha_metadata,
        beta_metadata,
        index_path,
    )
    return root, canonical_paths


def _seed_canonical_detector_case(tmp_path: Path) -> Path:
    from anomaly.prepare import prepare_sources
    from anomaly.profile import profile_prepared

    root = tmp_path / "pipeline-case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / "observations.csv",
            (
                "id,group,amount,observed_at\n"
                "1,A,10,2026-01-01\n"
                "2,A,11,2026-01-02\n"
                "3,B,100,2026-01-03\n"
                "4,B,,2026-01-10\n"
            ),
        ),
        "observations",
    )
    prepare_sources(root, now=NOW)
    profile_prepared(root, now=NOW)
    recommend = importlib.import_module("anomaly.recommend")
    recommend.recommend_detectors(root, now=NOW, max_detectors=10)
    recommend.approve_detector_plan(
        root,
        ["numeric.zscore_outliers"],
        approved_by="test",
        now=NOW,
    )
    return root


def _digests(paths: tuple[Path, ...]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _rewrite_signals(root: Path, transform: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    path = root / "evidence" / "signals.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text(
        "".join(json.dumps(transform(row), sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_projection_returns_exact_public_redacted_shape_without_mutating_evidence(
    tmp_path: Path,
) -> None:
    root, canonical_paths = _seed_search_case(tmp_path)
    before = _digests(canonical_paths)
    api = _api()

    manifest = api.build_signal_projection(root)
    result = api.search_signals(root, filters={"severity": "high"})

    assert manifest["signal_count"] == 3
    assert set(manifest["inputs"]) == {
        "evidence/signals.jsonl",
        "evidence/runs/run-alpha/provenance.json",
        "evidence/runs/run-beta/provenance.json",
        "detectors/used/numeric__zscore_outliers.json",
        "detectors/used/categorical__rare_levels.json",
    }
    assert (root / ".anomaly" / "search" / "signals.duckdb").is_file()
    assert (root / ".anomaly" / "search" / "signals-manifest.json").is_file()
    assert result["items"] == [
        {
            "signal_id": "signal-alpha",
            "rank": 1,
            "status": "lead",
            "category": "outlier",
            "severity": "high",
            "confidence": 0.73,
            "statement": "Acme has a deterministic overbilling variance.",
            "warnings": ["Compare against the seasonal baseline."],
            "redacted": True,
            "preview": {
                "vendor": "Acme",
                "amount": 120,
                "note": "Bearer [redacted]",
            },
            "evidence_refs": [
                {
                    "source_id": "payments",
                    "table_id": TABLE_ALPHA,
                    "candidate_id": "row-1",
                }
            ],
            "source_hash": SOURCE_ALPHA_HASH,
            "detector_hash": DETECTOR_ALPHA_HASH,
            "run_id": "run-alpha",
            "detector_id": "numeric.zscore_outliers",
            "table_id": TABLE_ALPHA,
            "signal_ref": {
                "path": "evidence/signals.jsonl",
                "signal_id": "signal-alpha",
                "run_id": "run-alpha",
            },
            "source_id": "payments",
            "date": "2026-08-21",
            "review_state": "unreviewed",
            "detector": {
                "title": "Allocation variance",
                "description": "Finds unusual spending values.",
                "group": "numeric",
                "signal_category": "outlier",
                "severity": "high",
                "assumptions": ["Amounts are comparable."],
                "false_positives": ["Seasonality."],
            },
            "matched_on": [],
            "query_score": 0,
        }
    ]
    assert _digests(canonical_paths) == before


@pytest.mark.parametrize(
    ("filter_key", "filter_value", "expected_ids"),
    [
        ("detector_id", "numeric.zscore_outliers", ["signal-alpha", "signal-beta"]),
        ("group", "numeric", ["signal-alpha", "signal-beta"]),
        ("category", "outlier", ["signal-alpha", "signal-beta"]),
        ("severity", "high", ["signal-alpha"]),
        ("source_id", "payments", ["signal-alpha", "signal-beta"]),
        ("table_id", TABLE_ALPHA, ["signal-alpha", "signal-beta"]),
        ("run_id", "run-alpha", ["signal-alpha", "signal-beta"]),
        ("date", "2026-08-21", ["signal-alpha", "signal-beta"]),
        ("review_state", "reviewed", []),
    ],
)
def test_each_structured_filter_independently_constrains_results(
    tmp_path: Path,
    filter_key: str,
    filter_value: str,
    expected_ids: list[str],
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    result = api.search_signals(root, filters={filter_key: filter_value})

    assert [item["signal_id"] for item in result["items"]] == expected_ids


@pytest.mark.parametrize(
    ("query", "expected_ids", "matched_fields", "expected_score"),
    [
        ("OVERBILLING", ["signal-alpha"], ["statement"], 1),
        ("seasonal baseline", ["signal-alpha"], ["warnings"], 1),
        ("allocation", ["signal-alpha", "signal-beta"], ["detector.title"], 1),
        (
            "unusual spending",
            ["signal-alpha", "signal-beta"],
            ["detector.description"],
            1,
        ),
        (
            "comparable",
            ["signal-alpha", "signal-beta"],
            ["detector.assumptions"],
            1,
        ),
        (
            "seasonality",
            ["signal-alpha", "signal-beta"],
            ["detector.false_positives"],
            1,
        ),
        ("Acme", ["signal-alpha"], ["statement", "preview.vendor"], 2),
    ],
)
def test_lexical_search_reports_every_public_field_and_retrieval_score(
    tmp_path: Path,
    query: str,
    expected_ids: list[str],
    matched_fields: list[str],
    expected_score: int,
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    result = api.search_signals(root, query=query)

    expected_matches = [
        {"field": field, "terms": query.casefold().split()} for field in matched_fields
    ]
    assert [item["signal_id"] for item in result["items"]] == expected_ids
    assert all(item["matched_on"] == expected_matches for item in result["items"])
    assert all(item["query_score"] == expected_score for item in result["items"])
    assert api.search_signals(root, query="classified-swordfish")["items"] == []
    assert api.search_signals(root, query="' OR TRUE --")["items"] == []


def test_search_uses_repeatable_keyset_pages_and_retrieval_only_scores(tmp_path: Path) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    first = api.search_signals(root, limit=2)
    second = api.search_signals(root, limit=2, cursor=first["next_cursor"])
    repeated_first = api.search_signals(root, limit=2)
    lexical = api.search_signals(root, query="allocation")

    assert first == repeated_first
    assert [item["signal_id"] for item in first["items"]] == [
        "signal-alpha",
        "signal-beta",
    ]
    assert [item["signal_id"] for item in second["items"]] == ["signal-gamma"]
    assert first["next_cursor"]
    assert second["next_cursor"] is None
    assert [item["query_score"] for item in first["items"] + second["items"]] == [
        0,
        0,
        0,
    ]
    assert [(item["severity"], item["confidence"], item["query_score"]) for item in lexical["items"]] == [
        ("high", 0.73, 1),
        ("low", 0.25, 1),
    ]


@pytest.mark.parametrize("changed_input", ["signal", "provenance", "detector"])
def test_query_rejects_then_explicitly_rebuilds_each_bound_input_family(
    tmp_path: Path,
    changed_input: str,
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    initial_manifest = api.build_signal_projection(root)
    projection = root / ".anomaly" / "search" / "signals.duckdb"
    manifest_path = root / ".anomaly" / "search" / "signals-manifest.json"
    derived_before = _digests((projection, manifest_path))

    if changed_input == "signal":
        def change_statement(row: dict[str, Any]) -> dict[str, Any]:
            if row["signal_id"] == "signal-alpha":
                return {**row, "statement": "Acme has a revised invoice variance."}
            return row

        _rewrite_signals(root, change_statement)
        query = {"query": "revised invoice"}
    elif changed_input == "provenance":
        provenance_path = root / "evidence" / "runs" / "run-alpha" / "provenance.json"
        provenance = _read_json(provenance_path)
        provenance["executed_at"] = "2026-08-23T10:00:00+00:00"
        _write_json(provenance_path, provenance)
        query = {"filters": {"date": "2026-08-23"}}
    else:
        snapshot_path = root / "detectors" / "used" / "numeric__zscore_outliers.json"
        snapshot = _read_json(snapshot_path)
        snapshot["metadata"]["description"] = "Finds exceptional spending values."
        _write_json(snapshot_path, snapshot)
        provenance_path = root / "evidence" / "runs" / "run-alpha" / "provenance.json"
        provenance = _read_json(provenance_path)
        provenance["detector_snapshot_hash"] = _canonical_json_hash(snapshot)
        _write_json(provenance_path, provenance)
        query = {"query": "exceptional spending"}

    with pytest.raises(api.StaleSignalProjectionError, match="(?i)stale"):
        api.search_signals(root)
    assert _digests((projection, manifest_path)) == derived_before

    rebuilt_manifest = api.build_signal_projection(root)
    rebuilt_result = api.search_signals(root, **query)

    assert rebuilt_manifest["projection_identity"] != initial_manifest["projection_identity"]
    expected_ids = (
        ["signal-alpha"]
        if changed_input == "signal"
        else ["signal-alpha", "signal-beta"]
    )
    assert [item["signal_id"] for item in rebuilt_result["items"]] == expected_ids


@pytest.mark.parametrize("missing_field", ["detector_snapshot", "detector_snapshot_hash"])
def test_projection_requires_run_bound_detector_snapshot_fields(
    tmp_path: Path, missing_field: str
) -> None:
    root, _ = _seed_search_case(tmp_path)
    provenance_path = root / "evidence" / "runs" / "run-alpha" / "provenance.json"
    provenance = _read_json(provenance_path)
    del provenance[missing_field]
    _write_json(provenance_path, provenance)
    api = _api()

    with pytest.raises(api.SignalSearchError, match="(?i)(snapshot|provenance|hash)"):
        api.build_signal_projection(root)


@pytest.mark.parametrize(
    "filters",
    [
        {"bogus": "value"},
        {1: "value", "bogus": "value"},
    ],
)
def test_malformed_filter_keys_use_the_public_search_error(
    tmp_path: Path, filters: dict[Any, str]
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    with pytest.raises(api.SignalSearchError, match="(?i)filter"):
        api.search_signals(root, filters=filters)


def test_canonical_repeated_runs_keep_immutable_run_bound_detector_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seed_canonical_detector_case(tmp_path)
    detector_root = tmp_path / "detector-packages"
    shutil.copytree(DETECTOR_ROOT, detector_root)
    detect = importlib.import_module("anomaly.detect")
    monkeypatch.setattr(detect, "_detector_root", lambda: detector_root)
    detector_ids = ("numeric.zscore_outliers",)

    first_rows = detect.execute_detectors(
        root, detector_ids, now=NOW, limits=DETECTOR_LIMITS
    )
    first_provenance_path = next((root / "evidence" / "runs").rglob("provenance.json"))
    first_provenance = _read_json(first_provenance_path)
    first_snapshot_path = root / first_provenance["detector_snapshot"]
    first_snapshot_bytes = first_snapshot_path.read_bytes()

    metadata_path = detector_root / "numeric" / "zscore_outliers" / "meta.yaml"
    metadata_path.write_text(
        metadata_path.read_text(encoding="utf-8").replace(
            "Identifies numeric observations far from their column mean.",
            "Identifies exceptional numeric observations far from their column mean.",
        ),
        encoding="utf-8",
    )
    second_rows = detect.execute_detectors(
        root, detector_ids, now=NOW + timedelta(seconds=1), limits=DETECTOR_LIMITS
    )
    provenance_paths = sorted((root / "evidence" / "runs").rglob("provenance.json"))
    provenances = [_read_json(path) for path in provenance_paths]
    snapshot_paths = [root / provenance["detector_snapshot"] for provenance in provenances]

    assert first_rows and len(second_rows) == len(first_rows)
    assert snapshot_paths[0] != snapshot_paths[1]
    assert first_snapshot_path.read_bytes() == first_snapshot_bytes
    for provenance, snapshot_path in zip(provenances, snapshot_paths, strict=True):
        snapshot_hash = provenance["detector_snapshot_hash"]
        assert snapshot_path.is_relative_to(root / "detectors" / "used")
        assert snapshot_path.stem.endswith(snapshot_hash.removeprefix("sha256:"))
        assert snapshot_path.is_file()
        assert snapshot_hash == _canonical_json_hash(_read_json(snapshot_path))


def test_projection_pages_repeated_signal_identity_by_run_aware_reference(
    tmp_path: Path,
) -> None:
    root, _ = _seed_search_case(tmp_path)
    signals_path = root / "evidence" / "signals.jsonl"
    rows = [
        json.loads(line)
        for line in signals_path.read_text(encoding="utf-8").splitlines()
    ]
    alpha = next(row for row in rows if row["signal_id"] == "signal-alpha")
    repeated = {**alpha, "run_id": "run-alpha-repeat"}
    signals_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in [*rows, repeated]
        ),
        encoding="utf-8",
    )
    first_provenance_path = root / "evidence" / "runs" / "run-alpha" / "provenance.json"
    repeated_provenance = {
        **_read_json(first_provenance_path),
        "run_id": "run-alpha-repeat",
        "executed_at": "2026-08-24T10:00:00+00:00",
    }
    _write_json(
        root / "evidence" / "runs" / "run-alpha-repeat" / "provenance.json",
        repeated_provenance,
    )
    api = _api()

    manifest = api.build_signal_projection(root)
    pages = []
    cursor = None
    for _ in range(4):
        page = api.search_signals(root, limit=1, cursor=cursor)
        pages.append(page)
        cursor = page["next_cursor"]
        if cursor is None:
            break
    repeated_first = api.search_signals(root, limit=1)
    items = [item for page in pages for item in page["items"]]

    assert manifest["signal_count"] == 4
    assert pages[0] == repeated_first
    assert cursor is None
    assert [(item["signal_id"], item["run_id"]) for item in items] == [
        ("signal-alpha", "run-alpha"),
        ("signal-alpha", "run-alpha-repeat"),
        ("signal-beta", "run-alpha"),
        ("signal-gamma", "run-beta"),
    ]
    assert [item["signal_ref"] for item in items] == [
        {
            "path": "evidence/signals.jsonl",
            "run_id": item["run_id"],
            "signal_id": item["signal_id"],
        }
        for item in items
    ]


def test_verified_search_never_returns_rows_from_a_concurrent_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)
    verified = threading.Event()
    continue_search = threading.Event()
    original_verified_projection = api.verified_projection

    def pause_after_verification(*args: Any, **kwargs: Any):
        projection = original_verified_projection(*args, **kwargs)
        verified.set()
        continue_search.wait()
        return projection

    monkeypatch.setattr(api, "verified_projection", pause_after_verification)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(api.search_signals, root)
        verified.wait()

        def replace_alpha(row: dict[str, Any]) -> dict[str, Any]:
            if row["signal_id"] == "signal-alpha":
                return {
                    **row,
                    "signal_id": "signal-rebuilt",
                    "statement": "Rebuilt projection row.",
                }
            return row

        _rewrite_signals(root, replace_alpha)
        api.build_signal_projection(root)
        continue_search.set()
        try:
            result = pending.result()
        except api.StaleSignalProjectionError:
            result = None

    if result is not None:
        assert [item["signal_id"] for item in result["items"]] == [
            "signal-alpha",
            "signal-beta",
            "signal-gamma",
        ]


def test_verified_search_never_serves_rows_from_an_index_swapped_between_hash_check_and_attach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, canonical_paths = _seed_search_case(tmp_path)
    before = _digests(canonical_paths)
    api = _api()
    api.build_signal_projection(root)
    projection = importlib.import_module("anomaly._signal_projection")
    original_open_private_projection = projection._open_private_projection
    derived_index = root / ".anomaly" / "search" / "signals.duckdb"
    parked_index = root / ".anomaly" / "search" / "signals.verified.duckdb"
    planted_index = tmp_path / "planted-signals.duckdb"
    with duckdb.connect(str(planted_index)) as connection:
        # kiss: only the columns an unfiltered read_rows selects are needed to bind
        connection.execute(
            "CREATE TABLE signals ("
            "signal_id VARCHAR NOT NULL, run_id VARCHAR NOT NULL, "
            "payload_json VARCHAR NOT NULL, search_fields_json VARCHAR NOT NULL)"
        )
        connection.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?)",
            [
                "signal-poison",
                "run-poison",
                json.dumps(
                    {
                        "signal_id": "signal-poison",
                        "run_id": "run-poison",
                        "statement": "attacker poison payload",
                    }
                ),
                "[]",
            ],
        )

    def swap_derived_index_inside_the_attach_window(raw: bytes):
        derived_index.rename(parked_index)
        shutil.copyfile(planted_index, derived_index)
        try:
            return original_open_private_projection(raw)
        finally:
            derived_index.unlink()
            parked_index.rename(derived_index)

    monkeypatch.setattr(
        projection,
        "_open_private_projection",
        swap_derived_index_inside_the_attach_window,
    )

    result = api.search_signals(root)

    assert [item["signal_id"] for item in result["items"]] == [
        "signal-alpha",
        "signal-beta",
        "signal-gamma",
    ]
    assert "poison" not in json.dumps(result)
    assert _digests(canonical_paths) == before


def test_projection_refuses_an_input_symlink_swapped_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_search_case(tmp_path)
    projection = importlib.import_module("anomaly._signal_projection")
    original_safe_input = projection._safe_input_file
    signals_path = root / "evidence" / "signals.jsonl"
    parked_signals = root / "evidence" / "signals.original.jsonl"
    outside_signals = tmp_path / "outside-signals.jsonl"
    outside_signals.write_text(
        signals_path.read_text(encoding="utf-8").replace(
            "deterministic overbilling", "outside symlink payload"
        ),
        encoding="utf-8",
    )
    swapped = False

    def swap_after_validation(case_root: Path, relative: str) -> Path:
        nonlocal swapped
        validated = original_safe_input(case_root, relative)
        if relative == "evidence/signals.jsonl" and not swapped:
            swapped = True
            signals_path.rename(parked_signals)
            signals_path.symlink_to(outside_signals)
        return validated

    monkeypatch.setattr(projection, "_safe_input_file", swap_after_validation)
    api = _api()

    with pytest.raises(api.SignalSearchError, match="(?i)(unsafe|symlink|contain)"):
        api.build_signal_projection(root)

    assert parked_signals.read_text(encoding="utf-8").find("outside symlink payload") == -1


def test_projection_refuses_a_search_directory_swapped_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, canonical_paths = _seed_search_case(tmp_path)
    before = _digests(canonical_paths)
    outside = tmp_path / "outside-search"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"unchanged")
    projection = importlib.import_module("anomaly._signal_projection")
    original_prepare_search_root = projection._prepare_search_root
    parked_search_root = root / ".anomaly" / "search.original"

    def swap_after_validation(case_root: Path) -> Path:
        search_root = original_prepare_search_root(case_root)
        search_root.rename(parked_search_root)
        search_root.symlink_to(outside, target_is_directory=True)
        return search_root

    monkeypatch.setattr(projection, "_prepare_search_root", swap_after_validation)
    api = _api()

    with pytest.raises(api.SignalSearchError, match="(?i)(search|projection|unsafe|symlink|contain)"):
        api.build_signal_projection(root)

    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"unchanged"
    assert _digests(canonical_paths) == before


def test_projection_refuses_a_preexisting_symlinked_derived_index_boundary(
    tmp_path: Path,
) -> None:
    root, canonical_paths = _seed_search_case(tmp_path)
    before = _digests(canonical_paths)
    outside = tmp_path / "outside"
    outside.mkdir()
    search_root = root / ".anomaly" / "search"
    search_root.parent.mkdir(parents=True)
    search_root.symlink_to(outside, target_is_directory=True)
    api = _api()

    with pytest.raises(api.SignalSearchError, match="(?i)(search|projection|unsafe|symlink)"):
        api.build_signal_projection(root)

    assert list(outside.iterdir()) == []
    assert _digests(canonical_paths) == before
