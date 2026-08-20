from __future__ import annotations

import importlib
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from p2_helpers import (
    NOW,
    assert_case_relative,
    create_p2_case,
    duckdb_count,
    duckdb_tables,
    generated_text_artifacts,
    read_json,
    register,
    sha256,
    write_parquet,
    write_source,
)


def _prepare_sources():
    return importlib.import_module("anomaly.prepare").prepare_sources


def _prepared_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in (root / "data" / "prepared").rglob("*")
        if path.is_file() and path.name != "transforms.json"
    )


def _generation_snapshot(root: Path) -> dict[str, str]:
    paths = [
        path
        for path in (root / "data" / "prepared").rglob("*")
        if path.is_file()
    ]
    index = root / "data" / "index.duckdb"
    if index.is_file():
        paths.append(index)
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(paths)
    }


def test_prepare_hash_verifies_before_using_the_public_record_decoder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anomaly.decode as public_decoder

    root = tmp_path / "valid-case"
    create_p2_case(root)
    record = register(
        root,
        write_source(tmp_path / "incoming" / "valid.csv", "id,name\n1,Ada\n"),
        "editorial-source",
    )
    calls: list[tuple[Path, str]] = []
    real_decode = public_decoder.decode_records

    def recording_decode(path: Path | str, format_name: str):
        calls.append((Path(path), format_name))
        return real_decode(path, format_name)

    monkeypatch.setattr(public_decoder, "decode_records", recording_decode)
    valid = _prepare_sources()(root, now=NOW)

    assert valid["replay"] == {"available": True, "reason": None, "sources": []}
    assert calls[0] == (root / record["path"], "csv")

    mismatch_root = tmp_path / "mismatch-case"
    create_p2_case(mismatch_root)
    mismatch = register(
        mismatch_root,
        write_source(tmp_path / "incoming" / "mismatch.csv", "id\n1\n"),
        "mismatch-source",
    )
    (mismatch_root / mismatch["path"]).write_text("id\n2\n", encoding="utf-8")
    calls.clear()

    unavailable = _prepare_sources()(mismatch_root, now=NOW)

    assert calls == []
    assert unavailable["replay"] == {
        "available": False,
        "reason": "required-sources-unavailable",
        "sources": [
            {"source_id": "mismatch-source", "reason": "source-hash-mismatch"}
        ],
    }
    assert unavailable["tables"] == []
    assert _prepared_files(mismatch_root) == []
    assert not (mismatch_root / "data" / "index.duckdb").exists()


def test_prepare_rejects_bytes_mutated_at_public_decoder_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anomaly.decode as public_decoder

    root = tmp_path / "case"
    create_p2_case(root)
    record = register(
        root,
        write_source(tmp_path / "incoming" / "records.csv", "id,name\n1,Ada\n"),
        "registered-source",
    )
    raw_path = root / record["path"]
    real_decode = public_decoder.decode_records
    calls = 0

    def mutate_then_decode(path: Path | str, format_name: str):
        nonlocal calls
        calls += 1
        raw_path.write_text("id,name\n999,Forged\n", encoding="utf-8")
        return real_decode(path, format_name)

    monkeypatch.setattr(public_decoder, "decode_records", mutate_then_decode)

    result = _prepare_sources()(root, now=NOW)

    assert calls == 1
    assert result["replay"] == {
        "available": False,
        "reason": "required-sources-unavailable",
        "sources": [
            {"source_id": "registered-source", "reason": "source-hash-mismatch"}
        ],
    }
    assert result["tables"] == []
    assert _prepared_files(root) == []
    assert not (root / "data" / "index.duckdb").exists()


def test_prepare_rejects_a_b_a_mutation_at_public_decoder_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anomaly.decode as public_decoder

    root = tmp_path / "case"
    create_p2_case(root)
    record = register(
        root,
        write_source(tmp_path / "incoming" / "records.csv", "id,name\n1,Ada\n"),
        "registered-source",
    )
    raw_path = root / record["path"]
    original = raw_path.read_bytes()
    real_decode = public_decoder.decode_records
    calls = 0

    def mutate_then_restore(path: Path | str, format_name: str):
        nonlocal calls
        calls += 1
        raw_path.write_text("id,name\n999,Forged\n", encoding="utf-8")
        raw_path.write_bytes(original)
        return real_decode(path, format_name)

    monkeypatch.setattr(public_decoder, "decode_records", mutate_then_restore)

    result = _prepare_sources()(root, now=NOW)

    assert calls == 1
    assert result["replay"]["available"] is False
    assert result["replay"]["reason"] == "required-sources-unavailable"
    assert result["tables"] == []
    assert _prepared_files(root) == []
    assert not (root / "data" / "index.duckdb").exists()


@pytest.mark.parametrize("failure", ["missing", "excluded", "invalid", "lossy"])
def test_prepare_is_all_or_nothing_for_every_required_source_failure(
    tmp_path: Path, failure: str
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "good.json", '[{"id": 1}]\n'),
        "good-source",
    )
    bad_payload = (
        '{"id": 1, "id": 2}\n'
        if failure == "invalid"
        else "id,name\n1\n"
        if failure == "lossy"
        else "id\n2\n"
    )
    bad = register(
        root,
        write_source(tmp_path / "incoming" / ("bad.json" if failure == "invalid" else "bad.csv"), bad_payload),
        "bad-source",
        included=failure != "excluded",
        reason="Cannot travel with this case." if failure == "excluded" else None,
    )
    if failure == "missing":
        (root / bad["path"]).unlink()

    result = _prepare_sources()(root, now=NOW)

    expected_reason = {
        "missing": "source-missing",
        "excluded": "source-excluded",
        "invalid": "source-decode-failed",
        "lossy": "source-decode-failed",
    }[failure]
    assert result["replay"] == {
        "available": False,
        "reason": "required-sources-unavailable",
        "sources": [{"source_id": "bad-source", "reason": expected_reason}],
    }
    assert result["tables"] == []
    assert read_json(root / "data" / "prepared" / "transforms.json") == result
    assert _prepared_files(root) == []
    assert not (root / "data" / "index.duckdb").exists()


def test_failed_reprepare_removes_every_prior_table_and_index(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "first.csv", "id\n1\n"),
        "first-source",
    )
    second = register(
        root,
        write_source(tmp_path / "incoming" / "second.csv", "id\n2\n"),
        "second-source",
    )
    first = _prepare_sources()(root, now=NOW)
    assert len(first["tables"]) == 2
    assert (root / "data" / "index.duckdb").is_file()

    (root / second["path"]).write_text("id\nforged\n", encoding="utf-8")
    failed = _prepare_sources()(root, now=NOW)

    assert failed["replay"]["available"] is False
    assert failed["tables"] == []
    assert _prepared_files(root) == []
    assert not (root / "data" / "index.duckdb").exists()


def test_successful_generation_commit_rolls_back_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare_module = importlib.import_module("anomaly.prepare")
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "first.csv", "id\n1\n"),
        "first-source",
    )
    prepare_module.prepare_sources(root, now=NOW)
    prior_generation = _generation_snapshot(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "second.csv", "id\n2\n"),
        "second-source",
    )
    index_path = root / "data" / "index.duckdb"
    real_replace = prepare_module.os.replace
    injected = False

    def fail_index_replace_once(source: Path | str, destination: Path | str) -> None:
        nonlocal injected
        if not injected and Path(destination) == index_path:
            injected = True
            raise OSError("injected generation replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(prepare_module.os, "replace", fail_index_replace_once)

    with pytest.raises(OSError, match="injected generation replace failure"):
        prepare_module.prepare_sources(root, now=NOW + timedelta(seconds=1))

    assert injected
    assert _generation_snapshot(root) == prior_generation


@pytest.mark.parametrize(
    "failure",
    [KeyboardInterrupt, BaseException],
    ids=["keyboard-interrupt", "base-exception"],
)
def test_prepare_commit_restores_exact_prior_generation_on_base_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
) -> None:
    prepare_module = importlib.import_module("anomaly.prepare")
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "first.csv", "id\n1\n"),
        "first-source",
    )
    prepare_module.prepare_sources(root, now=NOW)
    prior_generation = _generation_snapshot(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "second.csv", "id\n2\n"),
        "second-source",
    )
    index_path = root / "data" / "index.duckdb"
    real_replace = prepare_module.os.replace
    injected = False

    def fail_index_replace_once(source: Path | str, destination: Path | str) -> None:
        nonlocal injected
        if not injected and Path(destination) == index_path:
            injected = True
            raise failure("injected base exception")
        real_replace(source, destination)

    monkeypatch.setattr(prepare_module.os, "replace", fail_index_replace_once)

    with pytest.raises(failure, match="injected base exception"):
        prepare_module.prepare_sources(root, now=NOW + timedelta(seconds=1))

    assert injected
    assert _generation_snapshot(root) == prior_generation


def test_unavailable_generation_commit_rolls_back_on_unlink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    record = register(
        root,
        write_source(tmp_path / "incoming" / "records.csv", "id\n1\n"),
        "registered-source",
    )
    _prepare_sources()(root, now=NOW)
    prior_generation = _generation_snapshot(root)
    (root / record["path"]).unlink()
    index_path = root / "data" / "index.duckdb"
    real_unlink = Path.unlink
    injected = False

    def fail_index_unlink_once(path: Path, *args, **kwargs) -> None:
        nonlocal injected
        if not injected and path == index_path:
            injected = True
            raise OSError("injected generation unlink failure")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_index_unlink_once)

    with pytest.raises(OSError, match="injected generation unlink failure"):
        _prepare_sources()(root, now=NOW + timedelta(seconds=1))

    assert injected
    assert _generation_snapshot(root) == prior_generation


def test_structural_table_and_path_identities_are_stable_distinct_and_editorial_free(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    records = [
        register(
            root,
            write_source(tmp_path / "incoming" / f"same-{number}.csv", "id\n1\n"),
            source_id,
        )
        for number, source_id in enumerate(("north-editorial", "south-editorial"), 1)
    ]

    first = _prepare_sources()(root, now=NOW)
    second = _prepare_sources()(root, now=NOW)

    assert second == first
    tables = first["tables"]
    assert len({table["table_id"] for table in tables}) == 2
    for record, table in zip(records, tables, strict=True):
        assert re.fullmatch(r"tbl_[0-9a-f]{64}", table["table_id"])
        assert record["source_id"] == table["source_id"]
        assert record["source_id"] not in table["table_id"]
        assert record["source_id"] not in table["prepared"]["path"]
        prepared = assert_case_relative(root, table["prepared"]["path"], "data/prepared")
        assert prepared.stem == table["table_id"]
    assert {table["table_id"] for table in tables} == duckdb_tables(
        root / "data" / "index.duckdb"
    )


def test_table_ids_ignore_editorial_source_ids_and_resolve_duplicate_collisions(
    tmp_path: Path,
) -> None:
    def prepare_case(name: str, source_ids: tuple[str, ...]) -> tuple[dict, dict]:
        root = tmp_path / name
        create_p2_case(root)
        for number, source_id in enumerate(source_ids):
            register(
                root,
                write_source(
                    tmp_path / "incoming" / name / str(number) / "shared.csv",
                    "id,name\n1,Ada\n",
                ),
                source_id,
            )
        first = _prepare_sources()(root, now=NOW)
        second = _prepare_sources()(root, now=NOW)
        return first, second

    single_a, _ = prepare_case("single-a", ("north-editorial",))
    single_b, _ = prepare_case("single-b", ("renamed-editorial",))
    assert single_a["tables"][0]["table_id"] == single_b["tables"][0]["table_id"]

    duplicate_a, duplicate_a_repeat = prepare_case(
        "duplicates-a", ("north-editorial", "south-editorial")
    )
    duplicate_b, duplicate_b_repeat = prepare_case(
        "duplicates-b", ("renamed-north", "renamed-south")
    )
    ids_a = [table["table_id"] for table in duplicate_a["tables"]]
    ids_b = [table["table_id"] for table in duplicate_b["tables"]]

    assert duplicate_a_repeat == duplicate_a
    assert duplicate_b_repeat == duplicate_b
    assert len(set(ids_a)) == 2
    assert set(ids_b) == set(ids_a)
    assert all(re.fullmatch(r"tbl_[0-9a-f]{64}", table_id) for table_id in ids_a)


def test_table_ids_ignore_basename_but_keep_duplicate_occurrences_distinct(
    tmp_path: Path,
) -> None:
    def prepare_single(case_name: str, source_id: str, basename: str) -> str:
        root = tmp_path / case_name
        create_p2_case(root)
        register(
            root,
            write_source(
                tmp_path / "incoming" / case_name / basename,
                "id,name\n1,Ada\n",
            ),
            source_id,
        )
        return _prepare_sources()(root, now=NOW)["tables"][0]["table_id"]

    first_id = prepare_single("basename-a", "north-editorial", "alpha.csv")
    second_id = prepare_single("basename-b", "renamed-editorial", "beta.csv")
    assert first_id == second_id

    duplicate_root = tmp_path / "basename-duplicates"
    create_p2_case(duplicate_root)
    for source_id in ("north-editorial", "south-editorial"):
        register(
            duplicate_root,
            write_source(
                tmp_path / "incoming" / "basename-duplicates" / "shared.csv",
                "id,name\n1,Ada\n",
            ),
            source_id,
        )
    duplicate = _prepare_sources()(duplicate_root, now=NOW)
    duplicate_ids = [table["table_id"] for table in duplicate["tables"]]
    assert len(duplicate_ids) == 2
    assert len(set(duplicate_ids)) == 2


def test_transform_manifest_is_exact_hash_bound_and_portable(tmp_path: Path) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    source = register(
        root,
        write_source(tmp_path / "incoming" / "records.jsonl", '{"id": 1}\n{"id": 2}\n'),
        "editorial-records",
    )

    result = _prepare_sources()(root, now=NOW)

    assert set(result) == {"schema_version", "prepared_at", "replay", "tables"}
    assert result["schema_version"] == 1
    assert result["prepared_at"] == NOW.isoformat()
    assert read_json(root / "data" / "prepared" / "transforms.json") == result
    table = result["tables"][0]
    assert set(table) == {
        "source_id",
        "table_id",
        "source",
        "prepared",
        "row_count",
        "fields",
        "ambiguities",
    }
    assert table["source"] == {
        "path": source["path"],
        "sha256": source["content_hash"],
    }
    raw = assert_case_relative(root, table["source"]["path"], "data/raw")
    prepared = assert_case_relative(root, table["prepared"]["path"], "data/prepared")
    assert table["source"]["sha256"] == sha256(raw)
    assert table["prepared"] == {
        "path": table["prepared"]["path"],
        "sha256": sha256(prepared),
        "format": "parquet",
    }
    for reference in (table["source"]["path"], table["prepared"]["path"]):
        assert not Path(reference).is_absolute()
        assert ".." not in Path(reference).parts


def test_credential_bearing_registered_structural_path_is_unavailable(
    tmp_path: Path,
) -> None:
    secret = "sk_live_TESTONLY_SOURCE_PATH_123456"
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / f"records-{secret}.csv",
            "id,name\n1,Ada\n",
        ),
        f"source-{secret}",
    )

    result = _prepare_sources()(root, now=NOW)

    assert result["replay"] == {
        "available": False,
        "reason": "required-sources-unavailable",
        "sources": [
            {
                "source_id": "source-[redacted]",
                "reason": "source-path-unsafe",
            }
        ],
    }
    assert result["tables"] == []
    assert _prepared_files(root) == []
    assert not (root / "data" / "index.duckdb").exists()


def test_ordinary_registered_source_path_remains_exact_in_transforms(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    source = register(
        root,
        write_source(tmp_path / "incoming" / "records.csv", "id,name\n1,Ada\n"),
        "ordinary-source",
    )

    result = _prepare_sources()(root, now=NOW)

    assert result["replay"]["available"] is True
    assert result["tables"][0]["source"]["path"] == source["path"]
    assert read_json(root / "data" / "prepared" / "transforms.json")["tables"][0][
        "source"
    ]["path"] == source["path"]

def test_duckdb_is_queryable_and_deterministically_rebuilt_for_all_five_formats(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    incoming = tmp_path / "incoming"
    sources = (
        write_source(incoming / "rows.csv", "id,name\n1,Ada\n2,Bea\n"),
        write_source(incoming / "rows.json", '[{"id": 1}, {"id": 2}]\n'),
        write_source(incoming / "rows.jsonl", '{"id": 1}\n{"id": 2}\n'),
        write_parquet(incoming / "rows.parquet", [{"id": 1}, {"id": 2}]),
        write_source(
            incoming / "rows.xml",
            "<rows><row><id>1</id></row><row><id>2</id></row></rows>\n",
        ),
    )
    for number, source in enumerate(sources, 1):
        register(root, source, f"editorial-{number}")

    first = _prepare_sources()(root, now=NOW)
    index = root / "data" / "index.duckdb"
    expected_tables = {table["table_id"] for table in first["tables"]}
    assert duckdb_tables(index) == expected_tables
    assert {duckdb_count(index, table) for table in expected_tables} == {2}
    first_manifest = (root / "data" / "prepared" / "transforms.json").read_bytes()
    index.unlink()

    rebuilt = _prepare_sources()(root, now=NOW)

    assert rebuilt == first
    assert (root / "data" / "prepared" / "transforms.json").read_bytes() == first_manifest
    assert duckdb_tables(index) == expected_tables
    assert {duckdb_count(index, table) for table in expected_tables} == {2}


def test_duckdb_physical_types_and_rows_match_prepared_parquet(
    tmp_path: Path,
) -> None:
    import duckdb
    import pyarrow.parquet as parquet

    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / "typed.csv",
            (
                "id,amount,observed_at,label\n"
                "1,1.5,2026-01-01,Ada\n"
                "2,2.0,2026-01-02,Bea\n"
            ),
        ),
        "typed-source",
    )

    prepared = _prepare_sources()(root, now=NOW)
    table = prepared["tables"][0]
    table_id = table["table_id"]
    parquet_table = parquet.read_table(root / table["prepared"]["path"])
    names = parquet_table.schema.names
    expected_rows = [
        tuple(row[name] for name in names) for row in parquet_table.to_pylist()
    ]

    with duckdb.connect(str(root / "data" / "index.duckdb"), read_only=True) as connection:
        physical = connection.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table_id],
        ).fetchall()
        actual_rows = connection.execute(
            f'SELECT * FROM "{table_id}" ORDER BY "id"'
        ).fetchall()

    assert physical == [
        ("id", "BIGINT"),
        ("amount", "DOUBLE"),
        ("observed_at", "TIMESTAMP WITH TIME ZONE"),
        ("label", "VARCHAR"),
    ]
    assert actual_rows == expected_rows


def test_type_and_semantic_mappings_are_deterministic_and_surface_ambiguity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(
            tmp_path / "incoming" / "mapped.csv",
            (
                "id,amount,observed_at,name,location\n"
                "1,1.5,2026-01-01,Ada,London\n"
                "2,2.0,2026-01-02,Bea,51.5 -0.1\n"
            ),
        ),
        "mapped-source",
    )

    first = _prepare_sources()(root, now=NOW)
    second = _prepare_sources()(root, now=NOW)

    assert second == first
    table = first["tables"][0]
    mappings = {field["name"]: field for field in table["fields"]}
    assert mappings["id"] == {
        "name": "id",
        "type": "integer",
        "semantic_role": "identifier",
    }
    assert mappings["amount"] == {
        "name": "amount",
        "type": "float",
        "semantic_role": "measure",
    }
    assert mappings["observed_at"] == {
        "name": "observed_at",
        "type": "datetime",
        "semantic_role": "temporal",
    }
    assert mappings["name"] == {
        "name": "name",
        "type": "text",
        "semantic_role": "label",
    }
    assert table["ambiguities"] == [
        {
            "field": "location",
            "candidates": ["geographic", "text"],
            "reason": "multiple semantic roles match",
        }
    ]


def test_empty_and_only_excluded_cases_persist_explicit_unreplayable_state(
    tmp_path: Path,
) -> None:
    for state in ("empty", "excluded"):
        root = tmp_path / state
        create_p2_case(root)
        if state == "excluded":
            register(
                root,
                write_source(tmp_path / "incoming" / "excluded.csv", "id\n1\n"),
                "excluded-source",
                included=False,
                reason="Redistribution is unavailable.",
            )

        result = _prepare_sources()(root, now=NOW)

        expected_sources = (
            []
            if state == "empty"
            else [{"source_id": "excluded-source", "reason": "source-excluded"}]
        )
        assert result["replay"] == {
            "available": False,
            "reason": "no-included-sources"
            if state == "empty"
            else "required-sources-unavailable",
            "sources": expected_sources,
        }
        assert result["tables"] == []
        assert read_json(root / "data" / "prepared" / "transforms.json") == result
        assert not (root / "data" / "index.duckdb").exists()


def test_generated_p2_identifiers_keys_values_and_payloads_contain_no_credentials(
    tmp_path: Path,
) -> None:
    import duckdb

    secrets = (
        "sk_live_TESTONLY_PREPARE_123456",
        "ghp_TESTONLY_PREPARE_123456",
        "github_pat_TESTONLY_PREPARE_123456",
    )
    root = tmp_path / "case"
    create_p2_case(root)
    source = write_source(
        tmp_path / "incoming" / "ordinary.csv",
        f"id,{secrets[0]},{secrets[1]}\n1,{secrets[2]},{secrets[0]}\n",
    )
    register(
        root,
        source,
        "ordinary-source",
        license=f"Restricted {secrets[0]}",
        reacquisition=f"Use {secrets[1]}",
    )

    prepared = _prepare_sources()(root, now=NOW)
    profile_prepared = importlib.import_module("anomaly.profile").profile_prepared
    profiled = profile_prepared(root, now=NOW)

    generated = json.dumps({"prepared": prepared, "profiled": profiled}, sort_keys=True)
    generated += "\n".join(
        path.relative_to(root).as_posix() for path in root.rglob("*")
    )
    generated += "\n".join(text for _, text in generated_text_artifacts(root))
    for path in (root / "data" / "prepared").rglob("*"):
        if path.is_file():
            generated += path.read_bytes().decode("utf-8", errors="ignore")
    generated += (root / "data" / "index.duckdb").read_bytes().decode(
        "utf-8", errors="ignore"
    )
    table_id = prepared["tables"][0]["table_id"]
    with duckdb.connect(str(root / "data" / "index.duckdb"), read_only=True) as connection:
        generated += json.dumps(
            connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ? ORDER BY ordinal_position",
                [table_id],
            ).fetchall()
        )
        generated += json.dumps(
            connection.execute(f'SELECT * FROM "{table_id}"').fetchall()
        )
    for secret in secrets:
        assert secret not in generated
