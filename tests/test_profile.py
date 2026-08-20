from __future__ import annotations

import importlib
import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from p2_helpers import (
    NOW,
    create_p2_case,
    duckdb_count,
    generated_text_artifacts,
    instruction_bytes,
    read_json,
    sha256,
    register,
    write_json,
    write_parquet,
    write_source,
)

PROFILE_CSV = (
    "id,category,value,observed_at,latitude,longitude\n"
    "1,A,1.5,2026-01-01,51.5,-0.1\n"
    "2,A,,2026-01-02T12:00:00+00:00,,\n"
    "2,B,3.5,2026-01-03T00:00:00+02:00,52.0,0.2\n"
    "2,B,3.5,2026-01-03T00:00:00+02:00,52.0,0.2\n"
)


def _prepare_sources():
    return importlib.import_module("anomaly.prepare").prepare_sources


def _profile_api():
    module = importlib.import_module("anomaly.profile")
    return module.profile_prepared, module.PreparedDataError


def test_prepared_data_error_is_exposed_by_the_public_package_api() -> None:
    package = importlib.import_module("anomaly")
    profile_module = importlib.import_module("anomaly.profile")

    assert getattr(package, "PreparedDataError", None) is profile_module.PreparedDataError


def _prepared_case(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "case"
    create_p2_case(root)
    register(
        root,
        write_source(tmp_path / "incoming" / "profile.csv", PROFILE_CSV),
        "profile-editorial-source",
    )
    return root, _prepare_sources()(root, now=NOW)


def test_profile_contains_complete_metrics_and_mapped_temporal_geographic_coverage(
    tmp_path: Path,
) -> None:
    root, prepared = _prepared_case(tmp_path)
    profile_prepared, _ = _profile_api()

    first = profile_prepared(root, now=NOW)
    second = profile_prepared(root, now=NOW)

    assert second == first
    assert set(first) == {"schema_version", "profiled_at", "tables"}
    assert first["schema_version"] == 1
    assert first["profiled_at"] == NOW.isoformat()
    assert read_json(root / "data" / "prepared" / "profile.json") == first
    table = first["tables"][0]
    assert set(table) == {
        "table_id",
        "row_count",
        "duplicate_rows",
        "fields",
        "temporal_coverage",
        "geographic_coverage",
    }
    assert table["table_id"] == prepared["tables"][0]["table_id"]
    assert table["row_count"] == 4
    assert table["duplicate_rows"] == 1
    assert set(table["fields"]) == {
        "id",
        "category",
        "value",
        "observed_at",
        "latitude",
        "longitude",
    }
    for metrics in table["fields"].values():
        assert set(metrics) == {
            "missing_count",
            "missing_fraction",
            "cardinality",
            "range",
            "distribution",
        }
    assert table["fields"]["value"] == {
        "missing_count": 1,
        "missing_fraction": 0.25,
        "cardinality": 2,
        "range": {"min": 1.5, "max": 3.5},
        "distribution": [
            {"value": 3.5, "count": 2},
            {"value": 1.5, "count": 1},
        ],
    }
    assert table["fields"]["category"] == {
        "missing_count": 0,
        "missing_fraction": 0.0,
        "cardinality": 2,
        "range": None,
        "distribution": [
            {"value": "A", "count": 2},
            {"value": "B", "count": 2},
        ],
    }
    assert table["temporal_coverage"] == {
        "field": "observed_at",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T22:00:00+00:00",
    }
    assert table["geographic_coverage"] == {
        "latitude_field": "latitude",
        "longitude_field": "longitude",
        "row_count": 3,
        "bounds": {
            "min_latitude": 51.5,
            "max_latitude": 52.0,
            "min_longitude": -0.1,
            "max_longitude": 0.2,
        },
    }

    transforms_path = root / "data" / "prepared" / "transforms.json"
    transforms = read_json(transforms_path)
    observed = next(
        field
        for field in transforms["tables"][0]["fields"]
        if field["name"] == "observed_at"
    )
    observed["semantic_role"] = "label"
    write_json(transforms_path, transforms)

    remapped = profile_prepared(root, now=NOW + timedelta(seconds=1))

    assert remapped["tables"][0]["temporal_coverage"] is None


@pytest.mark.parametrize("corruption", ["missing-table", "loaded-shape", "prepared-shape"])
def test_profile_validates_every_loaded_table_and_prepared_shape_before_any_write(
    tmp_path: Path, corruption: str
) -> None:
    import duckdb

    root, prepared = _prepared_case(tmp_path)
    profile_prepared, PreparedDataError = _profile_api()
    table = prepared["tables"][0]
    index = root / "data" / "index.duckdb"
    if corruption in {"missing-table", "loaded-shape"}:
        with duckdb.connect(str(index)) as connection:
            connection.execute(f'DROP TABLE "{table["table_id"]}"')
            if corruption == "loaded-shape":
                connection.execute(
                    f'CREATE TABLE "{table["table_id"]}" (unexpected INTEGER)'
                )
                connection.execute(f'INSERT INTO "{table["table_id"]}" VALUES (1)')
    else:
        prepared_path = root / table["prepared"]["path"]
        write_parquet(prepared_path, [{"unexpected": 1}] * table["row_count"])
        manifest_path = root / "data" / "prepared" / "transforms.json"
        manifest = read_json(manifest_path)
        manifest["tables"][0]["prepared"]["sha256"] = sha256(prepared_path)
        write_json(manifest_path, manifest)
    before = instruction_bytes(root)

    with pytest.raises(PreparedDataError):
        profile_prepared(root, now=NOW)

    assert instruction_bytes(root) == before
    assert not (root / "data" / "prepared" / "profile.json").exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "source-id-type",
        "source-type",
        "source-member-types",
        "ambiguities-type",
        "ambiguity-member-types",
        "unknown-role",
        "incompatible-role",
    ],
)
def test_profile_rejects_every_invalid_transform_declaration_with_public_error(
    tmp_path: Path, corruption: str
) -> None:
    root, _ = _prepared_case(tmp_path)
    profile_prepared, PreparedDataError = _profile_api()
    manifest_path = root / "data" / "prepared" / "transforms.json"
    manifest = read_json(manifest_path)
    declaration = manifest["tables"][0]

    if corruption == "source-id-type":
        declaration["source_id"] = ["not", "a", "string"]
    elif corruption == "source-type":
        declaration["source"] = ["not", "a", "reference"]
    elif corruption == "source-member-types":
        declaration["source"] = {"path": 7, "sha256": ["not", "a", "hash"]}
    elif corruption == "ambiguities-type":
        declaration["ambiguities"] = {"not": "a list"}
    elif corruption == "ambiguity-member-types":
        declaration["ambiguities"] = [
            {
                "field": 7,
                "candidates": "geographic",
                "reason": ["not", "a", "string"],
            }
        ]
    elif corruption == "unknown-role":
        declaration["fields"][0]["semantic_role"] = "unbounded-editorial-role"
    else:
        temporal = next(
            field
            for field in declaration["fields"]
            if field["name"] == "observed_at"
        )
        temporal["semantic_role"] = "measure"
    write_json(manifest_path, manifest)
    before = instruction_bytes(root)

    with pytest.raises(PreparedDataError):
        profile_prepared(root, now=NOW)

    assert instruction_bytes(root) == before
    assert not (root / "data" / "prepared" / "profile.json").exists()


def test_credential_bearing_manifest_field_name_cannot_leak_from_profile(
    tmp_path: Path,
) -> None:
    import duckdb
    import pyarrow.parquet as parquet

    secret = "ghp_TESTONLY_PROFILE_FIELD_123456"
    root, prepared = _prepared_case(tmp_path)
    manifest_path = root / "data" / "prepared" / "transforms.json"
    manifest = read_json(manifest_path)
    declaration = manifest["tables"][0]
    old_name = declaration["fields"][0]["name"]
    declaration["fields"][0]["name"] = secret

    prepared_path = root / declaration["prepared"]["path"]
    prepared_table = parquet.read_table(prepared_path)
    prepared_table = prepared_table.rename_columns(
        [secret if name == old_name else name for name in prepared_table.schema.names]
    )
    parquet.write_table(prepared_table, prepared_path, compression="zstd")
    declaration["prepared"]["sha256"] = sha256(prepared_path)
    write_json(manifest_path, manifest)

    table_id = prepared["tables"][0]["table_id"]
    with duckdb.connect(str(root / "data" / "index.duckdb")) as connection:
        connection.execute(
            f'ALTER TABLE "{table_id}" RENAME COLUMN "{old_name}" TO "{secret}"'
        )

    profile_prepared, PreparedDataError = _profile_api()
    returned: dict | None = None
    try:
        returned = profile_prepared(root, now=NOW)
    except PreparedDataError:
        pass

    profile_path = root / "data" / "prepared" / "profile.json"
    profile_json = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    instruction_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "instructions").glob("*.md")
    )
    assert secret not in json.dumps(returned, sort_keys=True)
    assert secret not in profile_json
    assert secret not in instruction_text


def test_profile_updates_three_generated_sections_atomically_and_preserves_unrelated_content(
    tmp_path: Path,
) -> None:
    root, _ = _prepared_case(tmp_path)
    profile_prepared, PreparedDataError = _profile_api()
    journalist_notes = {
        "methodology.md": "\nJournalist methodology note: KEEP-ME.\n",
        "context.md": "\nJournalist context note: KEEP-ME.\n",
        "data-dictionary.md": "\nJournalist dictionary note: KEEP-ME.\n",
        "handling.md": "\nJournalist handling note: KEEP-ME.\n",
    }
    for name, note in journalist_notes.items():
        path = root / "instructions" / name
        path.write_text(path.read_text(encoding="utf-8") + note, encoding="utf-8")
    handling_before = (root / "instructions" / "handling.md").read_bytes()

    profile_prepared(root, now=NOW)
    first = instruction_bytes(root)
    profile_bytes = (root / "data" / "prepared" / "profile.json").read_bytes()
    profile_prepared(root, now=NOW)
    second = instruction_bytes(root)

    assert second == first
    assert first["handling.md"] == handling_before
    for name in ("methodology.md", "context.md", "data-dictionary.md"):
        text = first[name].decode("utf-8")
        assert journalist_notes[name].strip() in text
        assert text.count("<!-- anomaly:p2:start -->") == 1
        assert text.count("<!-- anomaly:p2:end -->") == 1
    table_id = read_json(root / "data" / "prepared" / "transforms.json")["tables"][0][
        "table_id"
    ]
    import duckdb

    with duckdb.connect(str(root / "data" / "index.duckdb")) as connection:
        connection.execute(f'DROP TABLE "{table_id}"')

    with pytest.raises(PreparedDataError):
        profile_prepared(root, now=NOW + timedelta(seconds=1))

    assert instruction_bytes(root) == first
    assert (root / "data" / "prepared" / "profile.json").read_bytes() == profile_bytes



@pytest.mark.parametrize(
    "failure",
    [KeyboardInterrupt, BaseException],
    ids=["keyboard-interrupt", "base-exception"],
)
def test_profile_commit_restores_exact_prior_bytes_on_base_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
) -> None:
    profile_module = importlib.import_module("anomaly.profile")
    root, _ = _prepared_case(tmp_path)
    profile_prepared, _ = _profile_api()
    profile_prepared(root, now=NOW)
    prior_instructions = instruction_bytes(root)
    profile_path = root / "data" / "prepared" / "profile.json"
    prior_profile = profile_path.read_bytes()
    real_replace = profile_module.os.replace
    injected = False

    def fail_context_replace_once(
        source: Path | str, destination: Path | str
    ) -> None:
        nonlocal injected
        if not injected and Path(destination).name == "context.md":
            injected = True
            raise failure("injected base exception")
        real_replace(source, destination)

    monkeypatch.setattr(profile_module.os, "replace", fail_context_replace_once)

    with pytest.raises(failure, match="injected base exception"):
        profile_prepared(root, now=NOW + timedelta(seconds=1))

    assert injected
    assert instruction_bytes(root) == prior_instructions
    assert profile_path.read_bytes() == prior_profile

def test_owned_block_markers_in_field_names_cannot_corrupt_markdown_or_reprofile(
    tmp_path: Path,
) -> None:
    start = "<!-- anomaly:p2:start -->"
    end = "<!-- anomaly:p2:end -->"
    root = tmp_path / "case"
    create_p2_case(root)
    payload = json.dumps(
        [
            {
                f"headline {start} hostile": "alpha",
                f"footer {end} hostile": "omega",
            }
        ]
    )
    register(
        root,
        write_source(tmp_path / "incoming" / "hostile.json", payload + "\n"),
        "hostile-fields",
    )
    _prepare_sources()(root, now=NOW)
    profile_prepared, _ = _profile_api()

    first_profile = profile_prepared(root, now=NOW)
    first_instructions = instruction_bytes(root)
    second_profile = profile_prepared(root, now=NOW)
    second_instructions = instruction_bytes(root)

    assert second_profile == first_profile
    assert second_instructions == first_instructions
    for name in ("methodology.md", "context.md", "data-dictionary.md"):
        text = second_instructions[name].decode("utf-8")
        assert text.count(start) == 1
        assert text.count(end) == 1


def test_profile_preserves_crlf_journalist_bytes_outside_owned_blocks(
    tmp_path: Path,
) -> None:
    root, _ = _prepared_case(tmp_path)
    start = b"<!-- anomaly:p2:start -->"
    end = b"<!-- anomaly:p2:end -->"
    prefix = b"# Journalist heading\r\n\r\nKeep-before: \xc3\xa9\r\n"
    suffix = b"\r\nKeep-after: exact bytes\r\n"
    original = prefix + start + b"\r\nstale generated text\r\n" + end + suffix
    targets = [
        root / "instructions" / name
        for name in ("methodology.md", "context.md", "data-dictionary.md")
    ]
    for path in targets:
        path.write_bytes(original)
    profile_prepared, _ = _profile_api()

    profile_prepared(root, now=NOW)
    first = {path: path.read_bytes() for path in targets}
    profile_prepared(root, now=NOW)
    second = {path: path.read_bytes() for path in targets}

    assert second == first
    for content in second.values():
        assert content.startswith(prefix)
        assert content.endswith(suffix)
        assert content.count(start) == 1
        assert content.count(end) == 1


def test_moved_case_rebuilds_profiles_and_queries_using_only_relative_references(
    tmp_path: Path,
) -> None:
    source_root, first_prepare = _prepared_case(tmp_path / "source")
    profile_prepared, _ = _profile_api()
    first_profile = profile_prepared(source_root, now=NOW)
    moved_root = tmp_path / "handoff" / "renamed-case"
    moved_root.parent.mkdir()
    shutil.copytree(source_root, moved_root)
    (moved_root / "data" / "index.duckdb").unlink()
    (moved_root / "data" / "prepared" / "profile.json").unlink()
    for table in first_prepare["tables"]:
        (moved_root / table["prepared"]["path"]).unlink()

    moved_prepare = _prepare_sources()(moved_root, now=NOW)
    moved_profile = profile_prepared(moved_root, now=NOW)

    assert moved_prepare == first_prepare
    assert moved_profile == first_profile
    index = moved_root / "data" / "index.duckdb"
    assert {
        duckdb_count(index, table["table_id"]) for table in moved_prepare["tables"]
    } == {4}
    persisted = "\n".join(text for _, text in generated_text_artifacts(moved_root))
    assert str(source_root.resolve()) not in persisted
    assert str(moved_root.resolve()) not in persisted
    for table in moved_prepare["tables"]:
        assert not Path(table["source"]["path"]).is_absolute()
        assert not Path(table["prepared"]["path"]).is_absolute()
