from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from anomaly.acquire import UnsupportedLocalSourceError, register_local_source
from anomaly.case import CaseNotFoundError, UnsafeCasePathError, create_case

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


def test_register_local_source_redacts_credentials_from_sources_and_receipts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    _create(root)
    secret = "sk_live_anomalySecretValue"
    source = _write_source(tmp_path / secret / "payload.csv", "id,n\n1,2\n")

    _register(
        root,
        source,
        "src-1",
        reacquisition=f"Use token={secret} at the portal",
    )

    persisted = (root / "data" / "sources.json").read_text(encoding="utf-8")
    assert secret not in persisted
    assert "src-1" in persisted
    receipts = [
        path
        for path in (root / ".anomaly" / "receipts").rglob("*")
        if path.is_file()
    ]
    assert receipts
    for receipt in receipts:
        text = receipt.read_text(encoding="utf-8")
        assert secret not in text
        assert "src-1" in text
        assert _sha256(source) in text


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
