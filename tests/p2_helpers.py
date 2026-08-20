from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anomaly.acquire import register_local_source
from anomaly.case import create_case

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def create_p2_case(root: Path) -> None:
    create_case(
        root,
        title="Portable source profile",
        question="What does the supplied data contain?",
        case_id="case-p2",
        now=NOW,
    )


def write_source(path: Path, payload: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")
    return path


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def register(
    root: Path,
    source: Path,
    source_id: str,
    *,
    included: bool = True,
    reason: str | None = None,
    license: str = "CC BY 4.0",
    sensitivity: str = "public",
    redistribution: str = "allowed",
    reacquisition: str = "Reopen the local source archive.",
) -> dict[str, Any]:
    return register_local_source(
        root,
        source,
        source_id=source_id,
        now=NOW,
        license=license,
        sensitivity=sensitivity,
        redistribution=redistribution,
        reacquisition=reacquisition,
        included=included,
        reason=reason,
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def assert_case_relative(root: Path, reference: str, namespace: str) -> Path:
    assert isinstance(reference, str)
    relative = Path(reference)
    assert not relative.is_absolute()
    assert ".." not in relative.parts
    assert relative.as_posix().startswith(namespace.rstrip("/") + "/")
    resolved = (root / relative).resolve()
    resolved.relative_to(root.resolve())
    assert resolved.is_file()
    return resolved


def duckdb_tables(index: Path) -> set[str]:
    import duckdb

    with duckdb.connect(str(index), read_only=True) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    return {row[0] for row in rows}


def duckdb_count(index: Path, table_id: str) -> int:
    import duckdb

    assert table_id.replace("_", "").isalnum()
    with duckdb.connect(str(index), read_only=True) as connection:
        return connection.execute(f'SELECT count(*) FROM "{table_id}"').fetchone()[0]


def instruction_bytes(root: Path) -> dict[str, bytes]:
    return {
        name: (root / "instructions" / name).read_bytes()
        for name in (
            "methodology.md",
            "context.md",
            "data-dictionary.md",
            "handling.md",
        )
    }


def generated_text_artifacts(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md"}:
            yield path, path.read_text(encoding="utf-8")
