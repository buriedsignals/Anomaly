from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


TABLE_ALPHA = "tbl_" + ("a" * 64)
TABLE_BETA = "tbl_" + ("b" * 64)
SOURCE_ALPHA_HASH = "sha256:" + ("1" * 64)
SOURCE_BETA_HASH = "sha256:" + ("2" * 64)
DETECTOR_ALPHA_HASH = "sha256:" + ("3" * 64)
DETECTOR_BETA_HASH = "sha256:" + ("4" * 64)


def _api():
    return importlib.import_module("anomaly.search")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


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
            "preview": {"vendor": "Acme", "amount": 120},
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
    _write_json(
        run_alpha / "provenance.json",
        {
            "schema_version": 2,
            "run_id": "run-alpha",
            "detector_id": "numeric.zscore_outliers",
            "detector_hash": DETECTOR_ALPHA_HASH,
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

    alpha_metadata = root / "detectors" / "used" / "numeric__zscore_outliers.json"
    beta_metadata = root / "detectors" / "used" / "categorical__rare_levels.json"
    _write_json(
        alpha_metadata,
        {
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
        },
    )
    _write_json(
        beta_metadata,
        {
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
        },
    )

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


def _digests(paths: tuple[Path, ...]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_projection_filters_every_structured_facet_without_mutating_evidence(
    tmp_path: Path,
) -> None:
    root, canonical_paths = _seed_search_case(tmp_path)
    before = _digests(canonical_paths)
    api = _api()

    manifest = api.build_signal_projection(root)
    result = api.search_signals(
        root,
        filters={
            "detector_id": "numeric.zscore_outliers",
            "group": "numeric",
            "category": "outlier",
            "severity": "high",
            "source_id": "payments",
            "table_id": TABLE_ALPHA,
            "run_id": "run-alpha",
            "date": "2026-08-21",
            "review_state": "unreviewed",
        },
    )

    assert manifest["signal_count"] == 3
    assert (root / ".anomaly" / "search" / "signals.duckdb").is_file()
    assert (root / ".anomaly" / "search" / "signals-manifest.json").is_file()
    assert [item["signal_id"] for item in result["items"]] == ["signal-alpha"]
    item = result["items"][0]
    assert item["signal_ref"] == {
        "path": "evidence/signals.jsonl",
        "signal_id": "signal-alpha",
    }
    assert item["evidence_refs"] == [
        {
            "source_id": "payments",
            "table_id": TABLE_ALPHA,
            "candidate_id": "row-1",
        }
    ]
    assert item["severity"] == "high"
    assert item["confidence"] == 0.73
    assert item["status"] == "lead"
    assert item["review_state"] == "unreviewed"
    assert isinstance(item["query_score"], (int, float))
    assert _digests(canonical_paths) == before


@pytest.mark.parametrize(
    ("query", "expected_ids", "matched_field"),
    [
        ("OVERBILLING", ["signal-alpha"], "statement"),
        ("seasonal baseline", ["signal-alpha"], "warnings"),
        ("allocation", ["signal-alpha", "signal-beta"], "detector.title"),
        ("Acme", ["signal-alpha"], "preview.vendor"),
    ],
)
def test_lexical_search_reports_the_public_redacted_fields_that_matched(
    tmp_path: Path,
    query: str,
    expected_ids: list[str],
    matched_field: str,
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    result = api.search_signals(root, query=query)

    assert [item["signal_id"] for item in result["items"]] == expected_ids
    assert all(
        item["matched_on"] == [
            {"field": matched_field, "terms": query.casefold().split()}
        ]
        for item in result["items"]
    )
    assert api.search_signals(root, query="classified-swordfish")["items"] == []
    assert api.search_signals(root, query="' OR TRUE --")["items"] == []


def test_search_uses_repeatable_keyset_pages_with_no_duplicates(tmp_path: Path) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)

    first = api.search_signals(root, limit=2)
    second = api.search_signals(root, limit=2, cursor=first["next_cursor"])
    repeated_first = api.search_signals(root, limit=2)

    assert first == repeated_first
    assert [item["signal_id"] for item in first["items"]] == [
        "signal-alpha",
        "signal-beta",
    ]
    assert [item["signal_id"] for item in second["items"]] == ["signal-gamma"]
    assert first["next_cursor"]
    assert second["next_cursor"] is None


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            "evidence/signals.jsonl",
            "deterministic overbilling variance",
            "changed overbilling variance",
        ),
        (
            "evidence/runs/run-alpha/provenance.json",
            "2026-08-21T10:00:00+00:00",
            "2026-08-23T10:00:00+00:00",
        ),
        (
            "detectors/used/numeric__zscore_outliers.json",
            "Finds unusual spending values",
            "Finds exceptional spending values",
        ),
    ],
)
def test_query_rejects_a_projection_when_any_bound_input_changes(
    tmp_path: Path,
    relative: str,
    old: str,
    new: str,
) -> None:
    root, _ = _seed_search_case(tmp_path)
    api = _api()
    api.build_signal_projection(root)
    projection = root / ".anomaly" / "search" / "signals.duckdb"
    projection_before = hashlib.sha256(projection.read_bytes()).hexdigest()
    changed = root / relative
    changed.write_text(
        changed.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )

    with pytest.raises(api.StaleSignalProjectionError, match="(?i)stale"):
        api.search_signals(root)

    assert hashlib.sha256(projection.read_bytes()).hexdigest() == projection_before


def test_projection_refuses_a_symlinked_derived_index_boundary(tmp_path: Path) -> None:
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
