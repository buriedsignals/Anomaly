"""Domain contracts: the shared tables a domain's detectors read.

A domain (lobbying, procurement, ...) is the only thing sources and detectors
share: sources name it as ``category``, detectors as ``data_type``. A domain
whose detectors join several tables declares those tables in
``domains/<domain>.yaml``. A column's meaning may end with a type hint in
parentheses, ``(integer)``, ``(number)`` or ``(date)``; other columns are text.
A column the source may not publish is marked ``(optional)`` or, with a type,
``(number, optional)``; the runner loads it as NULL when the file lacks it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from anomaly import detect

DOMAINS_ROOT = Path(__file__).resolve().parents[2] / "domains"
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_TYPES = {"integer": "BIGINT", "number": "DOUBLE", "date": "DATE"}
_HINT = re.compile(r"\((?:(integer|number|date)(, optional)?|(optional))\)\s*\.?\s*$")


class DomainError(ValueError):
    """A domain contract is missing or malformed."""


def column_type(meaning: str) -> str:
    """DuckDB type for a contract column, from its meaning's type hint."""
    match = _HINT.search(meaning)
    return _TYPES[match.group(1)] if match and match.group(1) else "VARCHAR"


def is_optional(meaning: str) -> bool:
    """True when a source may leave this contract column out."""
    match = _HINT.search(meaning)
    return bool(match and (match.group(2) or match.group(3)))


def load_domain(name: str, root: Path = DOMAINS_ROOT) -> dict[str, Any]:
    """Return ``{"domain", "description", "tables": {table: {"description", "columns": {column: meaning}}}}``."""
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise DomainError(f"invalid domain name: {name!r}")
    path = Path(root) / f"{name}.yaml"
    if path.is_symlink() or not path.is_file():
        raise DomainError(f"no contract for domain: {name}")
    contract = detect._parse_restricted_yaml(path.read_text(encoding="utf-8"))
    tables = contract.get("tables") if isinstance(contract, dict) else None
    if contract.get("domain") != name or not isinstance(tables, dict) or not tables:
        raise DomainError(f"malformed contract for domain: {name}")
    for table, spec in tables.items():
        columns = spec.get("columns") if isinstance(spec, dict) else None
        if not _NAME.fullmatch(str(table)) or not isinstance(columns, dict) or not columns or not all(
            _NAME.fullmatch(str(column)) and isinstance(meaning, str) for column, meaning in columns.items()
        ):
            raise DomainError(f"malformed table in domain {name}: {table}")
    return contract


def domain_names(root: Path = DOMAINS_ROOT) -> list[str]:
    return sorted(path.stem for path in Path(root).glob("*.yaml") if not path.is_symlink())
