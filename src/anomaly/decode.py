from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.parsers import expat

import pyarrow as pa
import pyarrow.parquet as parquet


class DecodeError(ValueError):
    """Raised when local input cannot be decoded without losing data."""


class UnsupportedFormatError(DecodeError):
    """Raised when no record decoder owns the requested format."""


class UnsafeXMLDecodeError(DecodeError):
    """Raised when XML contains declarations or references that are not inert."""


def decode_records(path: Path | str, format_name: str) -> list[dict[str, Any]]:
    """Decode a supported local file into records, or fail without partial output."""
    decoders: dict[str, Callable[[Path], list[dict[str, Any]]]] = {
        "csv": _decode_csv,
        "json": _decode_json,
        "jsonl": _decode_jsonl,
        "parquet": _decode_parquet,
        "xml": _decode_xml,
    }
    try:
        decoder = decoders[format_name]
    except (KeyError, TypeError) as error:
        raise UnsupportedFormatError(
            f"unsupported record format: {format_name!r}"
        ) from error
    return decoder(Path(path))


def _decode_csv(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8", newline="") as source:
            rows = csv.reader(source, strict=True)
            header = next(rows, None)
            if header is None:
                return []
            if len(header) != len(set(header)):
                raise DecodeError("CSV header contains duplicate field names")

            records: list[dict[str, Any]] = []
            for row in rows:
                if len(row) != len(header):
                    raise DecodeError(
                        f"CSV row ending on line {rows.line_num} has {len(row)} columns; "
                        f"expected {len(header)}"
                    )
                records.append(dict(zip(header, row, strict=True)))
            return records
    except DecodeError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        line = getattr(locals().get("rows"), "line_num", None)
        location = f" on line {line}" if line else ""
        raise DecodeError(f"invalid CSV data{location}: {error}") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise DecodeError(f"duplicate JSON key: {key!r}")
        record[key] = value
    return record


def _reject_json_constant(value: str) -> None:
    raise DecodeError(f"invalid JSON non-finite constant: {value}")


def _parse_json_float(lexeme: str) -> float:
    value = float(lexeme)
    if not math.isfinite(value):
        raise DecodeError(
            f"JSON number is not representable as a finite float: {lexeme}"
        )

    significand = lexeme.lower().partition("e")[0]
    if value == 0.0 and any(digit in significand for digit in "123456789"):
        raise DecodeError(
            f"JSON number loses its nonzero value as a finite float: {lexeme}"
        )
    return value


def _loads_json(payload: str) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_json_constant,
        parse_float=_parse_json_float,
    )


def _object_records(value: Any, *, context: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise DecodeError(f"{context} must contain one object or an array of objects")


def _decode_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = path.read_text(encoding="utf-8")
        value = _loads_json(payload)
        return _object_records(value, context="JSON document")
    except DecodeError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise DecodeError(f"invalid JSON data: {error}") from error


def _decode_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8", newline="") as source:
            payload = source.read()
    except (OSError, UnicodeError) as error:
        raise DecodeError(f"invalid JSONL text: {error}") from error

    records: list[dict[str, Any]] = []
    for line_number, physical_line in enumerate(payload.split("\n"), start=1):
        line = physical_line[:-1] if physical_line.endswith("\r") else physical_line
        if not line.strip(" \t"):
            continue
        try:
            value = _loads_json(line)
            if not isinstance(value, dict):
                raise DecodeError("record must contain one object")
        except (ValueError, RecursionError) as error:
            raise DecodeError(
                f"invalid JSONL record on line {line_number}: {error}"
            ) from error
        records.append(value)
    return records


def _decode_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        parquet_file = parquet.ParquetFile(path)
        schema = parquet_file.schema_arrow
        if len(schema.names) != len(set(schema.names)):
            raise DecodeError("Parquet schema contains duplicate column names")
        for field in schema:
            if pa.types.is_nested(field.type):
                raise DecodeError(
                    f"Parquet column {field.name!r} has unsupported nested "
                    f"non-primitive type {field.type}"
                )
        table = parquet_file.read()
        records = table.to_pylist()
    except DecodeError:
        raise
    except (OSError, pa.ArrowException) as error:
        raise DecodeError(f"invalid Parquet data: {error}") from error

    if not all(isinstance(record, dict) for record in records):
        raise DecodeError("invalid Parquet record shape: expected object rows")
    return records


def _refuse_unsafe_xml(payload: bytes) -> None:
    parser = expat.ParserCreate()

    def refuse(construct: str) -> None:
        raise UnsafeXMLDecodeError(f"unsafe XML {construct} is not supported")

    def refuse_namespace_declaration(_name: str, attributes: dict[str, str]) -> None:
        if any(
            name == "xmlns" or name.startswith("xmlns:") for name in attributes
        ):
            refuse("namespace declaration")

    parser.StartDoctypeDeclHandler = lambda *_: refuse("DOCTYPE declaration")
    parser.EntityDeclHandler = lambda *_: refuse("entity declaration")
    parser.UnparsedEntityDeclHandler = lambda *_: refuse(
        "external entity declaration"
    )
    parser.ExternalEntityRefHandler = lambda *_: refuse("external reference")
    parser.NotationDeclHandler = lambda *_: refuse("notation declaration")
    parser.SkippedEntityHandler = lambda *_: refuse("entity reference")
    parser.ProcessingInstructionHandler = lambda *_: refuse("processing instruction")
    parser.CommentHandler = lambda *_: refuse("comment")
    parser.StartElementHandler = refuse_namespace_declaration
    try:
        parser.Parse(payload, True)
    except UnsafeXMLDecodeError:
        raise
    except expat.ExpatError as error:
        raise DecodeError(f"invalid XML data: {error}") from error


def _decode_xml(path: Path) -> list[dict[str, Any]]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise DecodeError(f"invalid XML data: {error}") from error

    _refuse_unsafe_xml(payload)
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise DecodeError(f"invalid XML data: {error}") from error

    if root.tag != "rows":
        raise DecodeError("XML record shape must have a <rows> root")
    if root.attrib:
        raise DecodeError("XML <rows> root attributes are unsupported")
    if root.text and root.text.strip():
        raise DecodeError("XML <rows> cannot contain text outside records")

    records: list[dict[str, Any]] = []
    for row in root:
        if row.tag != "row":
            raise DecodeError("XML <rows> may contain only <row> records")
        if row.tail and row.tail.strip():
            raise DecodeError("XML <rows> cannot contain text outside records")
        if row.text and row.text.strip():
            raise DecodeError("XML <row> must use attributes or child fields")

        record: dict[str, Any] = dict(row.attrib)
        for field in row:
            if not isinstance(field.tag, str) or field.attrib or len(field):
                raise DecodeError("XML row child fields must be flat elements")
            if field.tag in record:
                raise DecodeError(
                    f"duplicate or conflicting XML field: {field.tag!r}"
                )
            if field.tail and field.tail.strip():
                raise DecodeError("XML <row> cannot contain mixed text")
            record[field.tag] = field.text or ""
        records.append(record)
    return records
