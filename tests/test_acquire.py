from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from anomaly.acquire import UnsupportedLocalSourceError, register_local_source
from anomaly.case import (
    CaseNotFoundError,
    UnsafeCasePathError,
    create_case,
    fork_case,
)

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

SUPPORTED = (
    ("vessels.csv", "imo,name\n123,Ada\n", "csv"),
    ("ports.json", '[{"id":1}]\n', "json"),
    ("calls.jsonl", '{"id":1}\n{"id":2}\n', "jsonl"),
    ("sail.parquet", b"PAR1", "parquet"),
    ("owners.xml", "<rows><row id=\"1\"/></rows>\n", "xml"),
)


def _create(root: Path):
    return create_case(
        root,
        title="Ship registry gaps",
        question="Which vessels disappear from AIS?",
        case_id="case-001",
        now=NOW,
    )


def _write_source(path: Path, payload: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> list[dict]:
    return json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))


def _register(root: Path, source: Path, source_id: str, **overrides: object):
    kwargs = {
        "source_id": source_id,
        "now": NOW,
        "license": "CC BY 4.0",
        "sensitivity": "public",
        "redistribution": "permitted",
        "reacquisition": "Request the same file from the port authority.",
        "included": True,
    }
    kwargs.update(overrides)
    return register_local_source(root, source, **kwargs)


def test_register_local_source_records_supported_formats(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    incoming = tmp_path / "incoming"

    for name, payload, format_name in SUPPORTED:
        source = _write_source(incoming / name, payload)
        _register(root, source, f"src-{format_name}")

    records = {record["format"]: record for record in _sources(root)}
    assert set(records) == {"csv", "json", "jsonl", "parquet", "xml"}
    for name, payload, format_name in SUPPORTED:
        record = records[format_name]
        relative = record["path"].replace("\\", "/")
        assert record["source_id"] == f"src-{format_name}"
        assert not Path(relative).is_absolute()
        assert relative.startswith("data/raw/")
        assert relative.endswith(name)
        copied = root / Path(*Path(relative).parts)
        assert copied.is_file()
        expected = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        assert copied.read_bytes() == expected


def test_register_local_source_stores_handling_metadata_hash_and_caller_clock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "vessels.csv", "imo,name\n")

    _register(
        root,
        source,
        "src-csv",
        license="ODbL-1.0",
        sensitivity="restricted",
        redistribution="forbidden",
        reacquisition="Re-copy from the locked newsroom drive.",
    )

    record = _sources(root)[0]
    assert record["source_id"] == "src-csv"
    assert record["content_hash"] == _sha256(source)
    assert record["format"] == "csv"
    assert record["acquired_at"] == NOW.isoformat()
    assert record["license"] == "ODbL-1.0"
    assert record["sensitivity"] == "restricted"
    assert record["redistribution"] == "forbidden"
    assert record["reacquisition"] == "Re-copy from the locked newsroom drive."
    assert record["included"] is True


def test_register_local_source_skips_raw_copy_when_not_included(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "secret.csv", "imo,name\n999,Hidden\n")

    _register(
        root,
        source,
        "src-secret",
        included=False,
        reason="Cannot leave the newsroom.",
        reacquisition="Re-copy from the locked newsroom drive.",
        sensitivity="restricted",
        redistribution="forbidden",
    )

    record = _sources(root)[0]
    assert record["included"] is False
    assert record["content_hash"] == _sha256(source)
    assert record["reason"] == "Cannot leave the newsroom."
    assert record["reacquisition"] == "Re-copy from the locked newsroom drive."
    assert not Path(record["path"]).is_absolute()
    assert list((root / "data" / "raw").rglob("*")) == []


def test_register_local_source_requires_reason_when_not_included(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "secret.csv", "imo,name\n")

    with pytest.raises(ValueError):
        _register(root, source, "src-secret", included=False)
    with pytest.raises(ValueError):
        _register(root, source, "src-secret", included=False, reason="")
    assert _sources(root) == []


def test_register_local_source_rejects_network_locations(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)

    for locator in (
        "https://example.com/vessels.csv",
        "http://example.com/vessels.csv",
        "file:///tmp/vessels.csv",
    ):
        with pytest.raises(UnsafeCasePathError):
            _register(root, locator, "src-net")

    assert _sources(root) == []


def test_register_local_source_rejects_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    target = _write_source(tmp_path / "real.csv", "imo,name\n")
    link = tmp_path / "alias.csv"
    link.symlink_to(target)

    with pytest.raises(UnsafeCasePathError):
        _register(root, link, "src-link")

    assert _sources(root) == []
    assert list((root / "data" / "raw").rglob("*")) == []

def test_register_local_source_rejects_an_in_case_destination_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "incoming.csv", "id,value\n1,original\n")
    case_path = root / "case.json"
    original_case = case_path.read_bytes()
    destination = root / "data" / "raw" / "new-source" / source.name
    destination.parent.mkdir(parents=True)
    destination.symlink_to(case_path)

    with pytest.raises(UnsafeCasePathError, match=r"(?i)(symlink|case path)"):
        _register(root, source, "new-source")

    assert case_path.read_bytes() == original_case
    assert _sources(root) == []


def test_register_local_source_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "vessels.csv", "imo,name\n")

    with pytest.raises(UnsafeCasePathError):
        _register(root, source, "../../outside")

    assert not (tmp_path / "outside").exists()
    assert _sources(root) == []
    for path in root.rglob("*"):
        resolved = path.resolve()
        assert resolved == root.resolve() or root.resolve() in resolved.parents


def test_register_local_source_does_not_write_outside_the_case(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "vessels.csv", "imo,name\n")
    _register(root, source, "src-csv")

    resolved_root = root.resolve()
    for path in root.rglob("*"):
        resolved = path.resolve()
        assert resolved == resolved_root or resolved_root in resolved.parents


PORTABLE_CREDENTIAL_SHAPED_SOURCE_COMPONENTS = (
    pytest.param(
        "analysis-ghp_notes",
        "evidence-sk_live_TESTONLY123.csv",
        id="embedded-github-and-stripe",
    ),
    pytest.param(
        "ghp_TESTONLY123",
        "analysis-ghp_notes.csv",
        id="classic-github-and-embedded-github",
    ),
    pytest.param(
        "source-sk_live_TESTONLY123",
        "evidence-github_pat_TESTONLY123.csv",
        id="stripe-and-fine-grained-github",
    ),
    pytest.param(
        "source-github_pat_TESTONLY123",
        "evidence-ghp_TESTONLY123.csv",
        id="fine-grained-and-classic-github",
    ),
)


@pytest.mark.parametrize(
    ("source_id", "basename"),
    PORTABLE_CREDENTIAL_SHAPED_SOURCE_COMPONENTS,
)
def test_register_preserves_structural_identities_while_redacting_metadata(
    tmp_path: Path,
    source_id: str,
    basename: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(
        tmp_path / "incoming" / basename,
        "id,n\n1,2\n",
    )
    secrets = (
        "sk_live_actualAcquisitionSecret123",
        "ghp_actualAcquisitionSecret456",
        "github_pat_actualAcquisitionSecret789",
    )
    expected_path = f"data/raw/{source_id}/{basename}"

    record = _register(
        root,
        source,
        source_id,
        license=f"License {secrets[0]}",
        sensitivity=f"Restricted {secrets[1]}",
        redistribution=f"Ask with {secrets[2]}",
        reacquisition=(
            f"Use {secrets[0]}, {secrets[1]}, and {secrets[2]} at the portal."
        ),
    )

    assert record["source_id"] == source_id
    assert record["path"] == expected_path
    assert record["content_hash"] == _sha256(source)
    assert record["format"] == "csv"
    assert record["acquired_at"] == NOW.isoformat()
    assert record["included"] is True
    assert record["license"] == "License [redacted]"
    assert record["sensitivity"] == "Restricted [redacted]"
    assert record["redistribution"] == "Ask with [redacted]"
    assert record["reacquisition"] == (
        "Use [redacted], [redacted], and [redacted] at the portal."
    )
    assert _sources(root) == [record]
    assert (root / expected_path).read_bytes() == source.read_bytes()
    assert _receipt_path(root, source_id).relative_to(root).as_posix() == (
        f".anomaly/receipts/{source_id}.json"
    )
    assert _read_receipt(root, source_id) == record
    persisted = json.dumps(
        {"manifest": _sources(root), "receipt": _read_receipt(root, source_id)}
    )
    for secret in secrets:
        assert secret not in persisted


def test_register_local_source_requires_an_existing_case(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "vessels.csv", "imo,name\n")
    with pytest.raises(CaseNotFoundError):
        _register(tmp_path / "missing", source, "src-csv")


def test_register_local_source_rejects_unsupported_format(tmp_path: Path) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "notes.txt", "not tabular\n")

    with pytest.raises(UnsupportedLocalSourceError):
        _register(root, source, "src-txt")

    assert _sources(root) == []
    assert list((root / "data" / "raw").rglob("*")) == []


SOURCE_RECORD_FIELDS = (
    "source_id",
    "path",
    "content_hash",
    "format",
    "acquired_at",
    "license",
    "sensitivity",
    "redistribution",
    "reacquisition",
    "included",
)

UNPORTABLE_SOURCE_IDS = (
    pytest.param("", id="empty"),
    pytest.param(".", id="dot"),
    pytest.param("..", id="dot-dot"),
    pytest.param("nested/id", id="forward-separator"),
    pytest.param(r"nested\id", id="backslash-separator"),
    pytest.param("Cafe\u0301", id="not-unicode-normalized"),
    pytest.param("trailing.", id="trailing-dot"),
    pytest.param("trailing ", id="trailing-space"),
    pytest.param("bad:name", id="colon"),
    pytest.param('bad"name', id="quote"),
    pytest.param("bad<name", id="less-than"),
    pytest.param("bad>name", id="greater-than"),
    pytest.param("bad|name", id="pipe"),
    pytest.param("bad?name", id="question-mark"),
    pytest.param("bad*name", id="asterisk"),
    pytest.param("bad\nname", id="control"),
    pytest.param("bad\x7fname", id="delete-control"),
    pytest.param("bad\0name", id="nul"),
    pytest.param("CON", id="reserved-con"),
    pytest.param("prn.source", id="reserved-prn-with-extension"),
    pytest.param("AUX", id="reserved-aux"),
    pytest.param("nul.json", id="reserved-nul-with-extension"),
    pytest.param("COM1", id="reserved-com"),
    pytest.param("lpt9.source", id="reserved-lpt-with-extension"),
    pytest.param("COM¹", id="reserved-com-superscript-one"),
    pytest.param("com¹.source", id="reserved-com-superscript-one-with-extension"),
    pytest.param("com²", id="reserved-com-superscript-two"),
    pytest.param("COM².source", id="reserved-com-superscript-two-with-extension"),
    pytest.param("CoM³", id="reserved-com-superscript-three"),
    pytest.param("com³.SOURCE", id="reserved-com-superscript-three-with-extension"),
    pytest.param("LPT¹", id="reserved-lpt-superscript-one"),
    pytest.param("lpt¹.source", id="reserved-lpt-superscript-one-with-extension"),
    pytest.param("lpt²", id="reserved-lpt-superscript-two"),
    pytest.param("LPT².source", id="reserved-lpt-superscript-two-with-extension"),
    pytest.param("LpT³", id="reserved-lpt-superscript-three"),
    pytest.param("lpt³.SOURCE", id="reserved-lpt-superscript-three-with-extension"),
    pytest.param("CONIN$", id="reserved-console-input"),
    pytest.param("conin$.source", id="reserved-console-input-with-extension"),
    pytest.param("CONOUT$", id="reserved-console-output"),
    pytest.param("conout$.source", id="reserved-console-output-with-extension"),
    pytest.param("C:", id="drive-designator"),
    pytest.param(r"C:relative", id="drive-relative"),
)

UNPORTABLE_SOURCE_BASENAMES = (
    pytest.param("Cafe\u0301.csv", id="not-unicode-normalized"),
    pytest.param(r"nested\name.csv", id="backslash-separator"),
    pytest.param("trailing.csv.", id="trailing-dot"),
    pytest.param("trailing.csv ", id="trailing-space"),
    pytest.param("bad:name.csv", id="colon"),
    pytest.param('bad"name.csv', id="quote"),
    pytest.param("bad<name.csv", id="less-than"),
    pytest.param("bad>name.csv", id="greater-than"),
    pytest.param("bad|name.csv", id="pipe"),
    pytest.param("bad?name.csv", id="question-mark"),
    pytest.param("bad*name.csv", id="asterisk"),
    pytest.param("bad\nname.csv", id="control"),
    pytest.param("bad\x7fname.csv", id="delete-control"),
    pytest.param("CON.csv", id="reserved-con"),
    pytest.param("prn.CSV", id="reserved-prn-with-extension"),
    pytest.param("AUX.json", id="reserved-aux"),
    pytest.param("nul.xml", id="reserved-nul-with-extension"),
    pytest.param("COM1.csv", id="reserved-com"),
    pytest.param("lpt9.parquet", id="reserved-lpt-with-extension"),
    pytest.param("COM¹.csv", id="reserved-com-superscript-one"),
    pytest.param("com².CSV", id="reserved-com-superscript-two"),
    pytest.param("CoM³.csv", id="reserved-com-superscript-three"),
    pytest.param("LPT¹.csv", id="reserved-lpt-superscript-one"),
    pytest.param("lpt².CSV", id="reserved-lpt-superscript-two"),
    pytest.param("LpT³.csv", id="reserved-lpt-superscript-three"),
    pytest.param("CONIN$.csv", id="reserved-console-input"),
    pytest.param("conout$.CSV", id="reserved-console-output"),
    pytest.param("C:vessels.csv", id="drive-relative"),
)

UNSAFE_RECURSIVE_PATH_VALUES = (
    pytest.param("/tmp/outside.csv", id="posix-absolute"),
    pytest.param("../outside.csv", id="posix-traversal"),
    pytest.param("archive/../../outside.csv", id="nested-posix-traversal"),
    pytest.param(r"C:\outside.csv", id="windows-drive-absolute"),
    pytest.param("C:/outside.csv", id="windows-drive-absolute-forward"),
    pytest.param(r"\\server\share\outside.csv", id="windows-unc"),
    pytest.param(r"\rooted\outside.csv", id="windows-rooted"),
    pytest.param(r"C:..\outside.csv", id="windows-drive-relative-traversal"),
    pytest.param(r"C:archive\outside.csv", id="windows-drive-relative"),
)


def _write_sources(root: Path, payload: object) -> None:
    (root / "data" / "sources.json").write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


def _receipt_path(root: Path, source_id: str) -> Path:
    return root / ".anomaly" / "receipts" / f"{source_id}.json"


def _read_receipt(root: Path, source_id: str) -> dict[str, object]:
    return json.loads(_receipt_path(root, source_id).read_text(encoding="utf-8"))


def _write_receipt(root: Path, source_id: str, payload: object) -> None:
    _receipt_path(root, source_id).write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


def _document_snapshot(root: Path) -> dict[str, bytes]:
    paths = [
        root / "case.json",
        root / "data" / "sources.json",
        *sorted((root / ".anomaly" / "receipts").glob("*.json")),
        *sorted((root / "data" / "raw").glob("*/*")),
    ]
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in paths
    }


def _seed_record(
    root: Path,
    tmp_path: Path,
    *,
    source_id: str = "existing-source",
) -> dict[str, object]:
    source = _write_source(
        tmp_path / "incoming" / f"{source_id}.csv",
        "imo,name\n123,Ada\n",
    )
    return _register(root, source, source_id)


def _assert_document_preflight_rejects(
    root: Path,
    tmp_path: Path,
    operation: str,
) -> None:
    candidate = _write_source(
        tmp_path / "candidate" / "new-source.csv",
        "imo,name\n456,Grace\n",
    )
    child = tmp_path / "child"
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        if operation == "acquire":
            _register(root, candidate, "new-source")
        else:
            fork_case(root, child, case_id="child-case", now=NOW)

    assert _document_snapshot(root) == before
    assert not child.exists()
    assert not (root / "data" / "raw" / "new-source").exists()
    assert not _receipt_path(root, "new-source").exists()


@pytest.mark.parametrize("source_id", UNPORTABLE_SOURCE_IDS)
def test_register_rejects_source_ids_outside_the_portable_component_policy(
    tmp_path: Path,
    source_id: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "incoming" / "vessels.csv", "imo,name\n")
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        _register(root, source, source_id)

    assert _document_snapshot(root) == before


@pytest.mark.parametrize("basename", UNPORTABLE_SOURCE_BASENAMES)
def test_register_rejects_basenames_outside_the_portable_component_policy(
    tmp_path: Path,
    basename: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(tmp_path / "incoming" / basename, "imo,name\n")
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        _register(root, source, "portable-source")

    assert _document_snapshot(root) == before


def test_register_rejects_nul_in_source_basename_before_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = str(tmp_path / "incoming") + "/bad\0name.csv"
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        _register(root, source, "portable-source")

    assert _document_snapshot(root) == before


@pytest.mark.parametrize(
    ("existing_id", "requested_id"),
    [
        pytest.param("same-source", "same-source", id="exact"),
        pytest.param("Data", "data", id="ascii-casefold"),
        pytest.param("Straße", "STRASSE", id="unicode-casefold"),
        pytest.param("Café", "CAFE\u0301", id="normalization-and-casefold"),
    ],
)
def test_requested_source_id_must_be_canonically_unique_before_writes(
    tmp_path: Path,
    existing_id: str,
    requested_id: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path, source_id=existing_id)
    candidate = _write_source(
        tmp_path / "candidate" / "replacement.csv",
        "imo,name\n456,Grace\n",
    )
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        _register(root, candidate, requested_id)

    assert _document_snapshot(root) == before


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_existing_source_ids_must_be_canonically_unique(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    first = _seed_record(root, tmp_path, source_id="Straße")
    alias = dict(first)
    alias["source_id"] = "STRASSE"
    alias["path"] = "data/raw/STRASSE/Straße.csv"
    _write_sources(root, [first, alias])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("shape", ["not-list", "non-record"])
def test_case_mutations_require_sources_to_be_a_list_of_records(
    tmp_path: Path,
    operation: str,
    shape: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    payload: object = {"sources": [record]} if shape == "not-list" else [record, 7]
    _write_sources(root, payload)

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("corruption", ["missing", "wrong-type"])
@pytest.mark.parametrize("field", SOURCE_RECORD_FIELDS)
def test_case_mutations_require_complete_typed_source_records(
    tmp_path: Path,
    operation: str,
    corruption: str,
    field: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    if corruption == "missing":
        record.pop(field)
    else:
        record[field] = "true" if field == "included" else 7
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("not-a-timestamp", id="invalid"),
        pytest.param("2026-08-21", id="date-only"),
        pytest.param(
            "2026-08-21\x0012:00:00",
            id="nul-date-time-separator",
        ),
        pytest.param(
            "2026-08-21\n12:00:00",
            id="newline-date-time-separator",
        ),
        pytest.param(
            "2026-08-21🐍12:00:00",
            id="arbitrary-unicode-date-time-separator",
        ),
    ],
)
def test_case_mutations_require_iso_acquisition_timestamps(
    tmp_path: Path,
    operation: str,
    value: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["acquired_at"] = value
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt["acquired_at"] = value
    _write_receipt(root, str(record["source_id"]), receipt)
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(
    "content_hash",
    [
        "sha256:abc",
        "sha256:" + ("g" * 64),
        "md5:" + ("0" * 32),
    ],
)
def test_case_mutations_require_canonical_sha256_content_hashes(
    tmp_path: Path,
    operation: str,
    content_hash: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["content_hash"] = content_hash
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_case_mutations_reject_unsupported_manifest_format(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["format"] = "xlsx"
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("reason", [None, "", 7])
def test_excluded_source_records_require_nonempty_typed_reason(
    tmp_path: Path,
    operation: str,
    reason: object,
) -> None:
    root = tmp_path / "case"
    _create(root)
    source = _write_source(
        tmp_path / "incoming" / "excluded.csv",
        "imo,name\n123,Ada\n",
    )
    record = _register(
        root,
        source,
        "excluded-source",
        included=False,
        reason="Not permitted to travel.",
    )
    if reason is None:
        record.pop("reason")
    else:
        record["reason"] = reason
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(
    "source_id",
    ["CON", "Cafe\u0301", r"nested\source", r"C:relative"],
)
def test_existing_manifest_source_ids_use_the_portable_component_policy(
    tmp_path: Path,
    operation: str,
    source_id: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["source_id"] = source_id
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(
    "path",
    [
        "/tmp/existing.csv",
        "../outside.csv",
        r"C:\outside.csv",
        r"C:..\outside.csv",
        r"C:archive\outside.csv",
        "evidence/existing.csv",
        "data/raw/other/existing-source.csv",
        "data/raw/existing-source/nested/existing-source.csv",
        r"data\raw\existing-source\existing-source.csv",
        "data/raw/existing-source/CON.csv",
        "data/raw/existing-source/Cafe\u0301.csv",
    ],
)
def test_manifest_path_must_match_its_canonical_raw_identity_relation(
    tmp_path: Path,
    operation: str,
    path: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["path"] = path
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_manifest_format_must_match_the_source_basename_extension(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["format"] = "json"
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("unsafe", UNSAFE_RECURSIVE_PATH_VALUES)
def test_manifest_rejects_unsafe_recursive_path_values(
    tmp_path: Path,
    operation: str,
    unsafe: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record["provenance"] = {"mirrors": [{"local_path": unsafe}]}
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt["provenance"] = record["provenance"]
    _write_receipt(root, str(record["source_id"]), receipt)
    _write_sources(root, [record])

    _assert_document_preflight_rejects(root, tmp_path, operation)


RECEIPT_MISMATCHES = (
    pytest.param("source_id", "other-source", id="source-id"),
    pytest.param(
        "path",
        "data/raw/other-source/existing-source.csv",
        id="path",
    ),
    pytest.param("content_hash", "sha256:" + ("1" * 64), id="content-hash"),
    pytest.param("format", "json", id="format"),
    pytest.param(
        "acquired_at",
        "2026-08-20T12:00:00+00:00",
        id="acquired-at",
    ),
    pytest.param("license", "ODbL-1.0", id="license"),
    pytest.param("sensitivity", "restricted", id="sensitivity"),
    pytest.param("redistribution", "forbidden", id="redistribution"),
    pytest.param("reacquisition", "Request a new export.", id="reacquisition"),
    pytest.param("included", False, id="included"),
)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(("field", "other"), RECEIPT_MISMATCHES)
def test_receipt_shared_fields_must_equal_the_manifest_record(
    tmp_path: Path,
    operation: str,
    field: str,
    other: object,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt[field] = other
    if field == "included":
        receipt["reason"] = "Receipt says the file was excluded."
    _write_receipt(root, str(record["source_id"]), receipt)

    _assert_document_preflight_rejects(root, tmp_path, operation)

SHARED_EXTENSION_MISMATCHES = (
    pytest.param(
        "provenance",
        {"local_path": "archive/manifest.csv"},
        {"local_path": "archive/receipt.csv"},
        id="nested-provenance",
    ),
    pytest.param(
        "handling_notes",
        ["manifest reviewed"],
        ["receipt reviewed"],
        id="arbitrary-extension",
    ),
    pytest.param(
        "review_history",
        {"checks": [{"accepted": True}]},
        {"checks": [{"accepted": 1}]},
        id="recursive-json-bool-versus-integer",
    ),
)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(
    ("field", "manifest_value", "receipt_value"),
    SHARED_EXTENSION_MISMATCHES,
)
def test_receipt_arbitrary_shared_fields_must_equal_the_manifest_record(
    tmp_path: Path,
    operation: str,
    field: str,
    manifest_value: object,
    receipt_value: object,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    record[field] = manifest_value
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt[field] = receipt_value
    _write_sources(root, [record])
    _write_receipt(root, str(record["source_id"]), receipt)

    _assert_document_preflight_rejects(root, tmp_path, operation)


def test_source_receipts_allow_safe_receipt_only_fields(
    tmp_path: Path,
) -> None:
    root = tmp_path / "parent"
    child = tmp_path / "child"
    _create(root)
    record = _seed_record(root, tmp_path)
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt_only = {
        "review": {
            "evidence_path": "reports/source-review.html",
            "decision": "accepted",
        }
    }
    receipt["receipt_context"] = receipt_only
    _write_receipt(root, str(record["source_id"]), receipt)
    candidate = _write_source(
        tmp_path / "incoming" / "second.csv",
        "imo,name\n456,Grace\n",
    )

    _register(root, candidate, "second-source")
    fork_case(root, child, case_id="child-case", now=NOW)

    assert (
        _read_receipt(root, str(record["source_id"]))["receipt_context"]
        == receipt_only
    )
    assert (
        _read_receipt(child, str(record["source_id"]))["receipt_context"]
        == receipt_only
    )


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_source_receipt_identity_uses_canonical_filename_and_json_suffix(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path, source_id="Straße")
    canonical_receipt = (
        root / ".anomaly" / "receipts" / "archive" / "STRASSE.JSON"
    )
    canonical_receipt.parent.mkdir()
    _receipt_path(root, "Straße").replace(canonical_receipt)

    if operation == "acquire":
        candidate = _write_source(
            tmp_path / "candidate" / "new-source.csv",
            "imo,name\n456,Grace\n",
        )
        _register(root, candidate, "new-source")
        assert len(_sources(root)) == 2
    else:
        child = tmp_path / "child"
        fork_case(root, child, case_id="child-case", now=NOW)
        assert (
            child / ".anomaly" / "receipts" / "archive" / "STRASSE.JSON"
        ).read_bytes() == canonical_receipt.read_bytes()


NON_SOURCE_RECEIPT_KINDS = (
    "detector",
    "replay",
    "review",
    "user-approval",
)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("kind", NON_SOURCE_RECEIPT_KINDS)
def test_shared_receipt_store_accepts_portable_non_source_receipt_kinds(
    tmp_path: Path,
    operation: str,
    kind: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path)
    receipt_path = root / ".anomaly" / "receipts" / f"{kind}.json"
    receipt_path.write_text(
        json.dumps(
            {
                "kind": kind,
                "status": "accepted",
                "evidence": {
                    "artifact": f"reports/{kind}/summary.html",
                    "checks": ["identity", "provenance"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    if operation == "acquire":
        candidate = _write_source(
            tmp_path / "candidate" / "new-source.csv",
            "imo,name\n456,Grace\n",
        )
        _register(root, candidate, "new-source")
        assert receipt_path.is_file()
    else:
        child = tmp_path / "child"
        fork_case(root, child, case_id="child-case", now=NOW)
        if kind == "replay":
            assert not (child / ".anomaly" / "receipts" / "replay.json").exists()
            assert json.loads((child / "evidence" / "replay.json").read_text())["status"] == "unavailable"
        else:
            assert (
                child / ".anomaly" / "receipts" / f"{kind}.json"
            ).read_bytes() == receipt_path.read_bytes()


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("kind", NON_SOURCE_RECEIPT_KINDS)
def test_recognized_non_source_kind_takes_precedence_over_filename_collision(
    tmp_path: Path,
    operation: str,
    kind: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path, source_id=kind)
    archived_source_receipt = (
        root / ".anomaly" / "receipts" / "archive" / f"{kind.upper()}.JSON"
    )
    archived_source_receipt.parent.mkdir()
    _receipt_path(root, kind).replace(archived_source_receipt)
    non_source_receipt = _receipt_path(root, kind)
    non_source_receipt.write_text(
        json.dumps({"kind": kind, "status": "accepted"}) + "\n",
        encoding="utf-8",
    )

    if operation == "acquire":
        candidate = _write_source(
            tmp_path / "candidate" / "new-source.csv",
            "imo,name\n456,Grace\n",
        )
        _register(root, candidate, "new-source")
        assert len(_sources(root)) == 2
        assert archived_source_receipt.is_file()
        assert non_source_receipt.is_file()
    else:
        child = tmp_path / "child"
        fork_case(root, child, case_id="child-case", now=NOW)
        assert (
            child
            / ".anomaly"
            / "receipts"
            / "archive"
            / f"{kind.upper()}.JSON"
        ).read_bytes() == archived_source_receipt.read_bytes()
        if kind == "replay":
            assert not (child / ".anomaly" / "receipts" / "replay.json").exists()
            assert json.loads((child / "evidence" / "replay.json").read_text())["status"] == "unavailable"
        else:
            assert (
                child / ".anomaly" / "receipts" / f"{kind}.json"
            ).read_bytes() == non_source_receipt.read_bytes()


@pytest.mark.parametrize(
    ("receipt_stem", "requested_id"),
    [
        pytest.param("review", "REVIEW", id="ascii-casefold"),
        pytest.param("Straße", "STRASSE", id="unicode-casefold"),
    ],
)
def test_requested_source_id_rejects_canonical_non_source_receipt_key_before_writes(
    tmp_path: Path,
    receipt_stem: str,
    requested_id: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    non_source_receipt = _receipt_path(root, receipt_stem)
    non_source_receipt.write_text(
        json.dumps({"kind": "review", "status": "accepted"}) + "\n",
        encoding="utf-8",
    )
    candidate = _write_source(
        tmp_path / "candidate" / "new-source.csv",
        "imo,name\n456,Grace\n",
    )
    before = _document_snapshot(root)

    with pytest.raises(UnsafeCasePathError):
        _register(root, candidate, requested_id)

    assert _document_snapshot(root) == before
    assert not (root / "data" / "raw" / requested_id).exists()

REJECTED_RECEIPT_ARTIFACTS = (
    pytest.param("archive/malformed.JSON", "{not-json", id="malformed-json"),
    pytest.param("archive/not-a-record.JsOn", "[]", id="json-non-record"),
    pytest.param(
        "archive/unsafe.json",
        json.dumps(
            {
                "kind": "review",
                "evidence": {"artifact": r"C:..\outside.html"},
            }
        ),
        id="unsafe-recursive-value",
    ),
    pytest.param(
        "archive/unrecognized.txt",
        json.dumps({"kind": "review", "status": "accepted"}),
        id="unrecognized-extension",
    ),
)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize(("relative", "content"), REJECTED_RECEIPT_ARTIFACTS)
def test_case_mutations_reject_invalid_recursive_receipt_artifacts(
    tmp_path: Path,
    operation: str,
    relative: str,
    content: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path)
    artifact = root / ".anomaly" / "receipts" / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(content, encoding="utf-8")

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_canonical_source_receipt_aliases_cannot_duplicate_manifest_identity(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path, source_id="Straße")
    alias = root / ".anomaly" / "receipts" / "archive" / "STRASSE.JSON"
    alias.parent.mkdir()
    alias.write_bytes(_receipt_path(root, "Straße").read_bytes())

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("shape", [[], "not-a-record"])
def test_existing_receipts_must_be_typed_records(
    tmp_path: Path,
    operation: str,
    shape: object,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    _write_receipt(root, str(record["source_id"]), shape)

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
def test_receipt_must_correspond_to_a_manifest_source(
    tmp_path: Path,
    operation: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    _seed_record(root, tmp_path)
    orphan = _read_receipt(root, "existing-source")
    orphan["source_id"] = "orphan-source"
    orphan["path"] = "data/raw/orphan-source/orphan.csv"
    _write_receipt(root, "orphan-source", orphan)

    _assert_document_preflight_rejects(root, tmp_path, operation)


@pytest.mark.parametrize("operation", ["acquire", "fork"])
@pytest.mark.parametrize("unsafe", UNSAFE_RECURSIVE_PATH_VALUES)
def test_receipt_rejects_unsafe_recursive_path_values(
    tmp_path: Path,
    operation: str,
    unsafe: str,
) -> None:
    root = tmp_path / "case"
    _create(root)
    record = _seed_record(root, tmp_path)
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt["provenance"] = {"mirrors": [{"local_path": unsafe}]}
    _write_receipt(root, str(record["source_id"]), receipt)

    _assert_document_preflight_rejects(root, tmp_path, operation)


def test_safe_recursive_metadata_remains_portable_for_acquisition_and_fork(
    tmp_path: Path,
) -> None:
    root = tmp_path / "parent"
    child = tmp_path / "child"
    _create(root)
    record = _seed_record(root, tmp_path)
    provenance = {
        "mirrors": [{"local_path": "archive/2026/existing-source.csv"}]
    }
    record["provenance"] = provenance
    receipt = _read_receipt(root, str(record["source_id"]))
    receipt["provenance"] = provenance
    _write_sources(root, [record])
    _write_receipt(root, str(record["source_id"]), receipt)
    second = _write_source(
        tmp_path / "incoming" / "second.json",
        '{"imo": 456, "name": "Grace"}\n',
    )

    second_record = _register(root, second, "second-source")
    parent_before = _document_snapshot(root)
    forked = fork_case(root, child, case_id="child-case", now=NOW)

    assert _sources(root) == [record, second_record]
    assert _sources(child) == [record, second_record]
    assert _read_receipt(child, "existing-source")["provenance"] == provenance
    assert forked.record.case_id == "child-case"
    assert forked.record.derived_from["case_id"] == "case-001"
    assert forked.record.derived_from["case_hash"].startswith("sha256:")
    assert _document_snapshot(root) == parent_before


def test_valid_normalized_unicode_source_components_remain_portable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "parent"
    child = tmp_path / "child"
    _create(root)
    source = _write_source(
        tmp_path / "incoming" / "Véssels-東京.csv",
        "imo,name\n123,Ada\n",
    )

    record = _register(root, source, "Données-東京")
    parent_before = _document_snapshot(root)
    fork_case(root, child, case_id="child-case", now=NOW)

    assert record["path"] == "data/raw/Données-東京/Véssels-東京.csv"
    assert (root / str(record["path"])).read_bytes() == source.read_bytes()
    assert _read_receipt(root, "Données-東京") == record
    assert _document_snapshot(root) == parent_before
    assert _sources(child) == [record]


def test_valid_acquisition_receipts_and_forks_are_deterministic(
    tmp_path: Path,
) -> None:
    first_parent = tmp_path / "first-parent"
    second_parent = tmp_path / "second-parent"
    first_child = tmp_path / "first-child"
    second_child = tmp_path / "second-child"
    source = _write_source(
        tmp_path / "incoming" / "vessels.csv",
        "imo,name\n123,Ada\n",
    )
    _create(first_parent)
    _create(second_parent)

    first_record = _register(first_parent, source, "vessels-source")
    second_record = _register(second_parent, source, "vessels-source")
    first_before = _document_snapshot(first_parent)
    second_before = _document_snapshot(second_parent)
    first_fork = fork_case(
        first_parent,
        first_child,
        case_id="child-case",
        now=NOW,
    )
    second_fork = fork_case(
        second_parent,
        second_child,
        case_id="child-case",
        now=NOW,
    )

    assert first_record == second_record
    assert _document_snapshot(first_parent) == first_before
    assert _document_snapshot(second_parent) == second_before
    assert _document_snapshot(first_child) == _document_snapshot(second_child)
    assert first_fork == second_fork
