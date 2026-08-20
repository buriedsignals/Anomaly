from __future__ import annotations

from pathlib import Path

import pytest

from anomaly.decode import DecodeError, UnsupportedFormatError, decode_records


def _write(path: Path, payload: str | bytes) -> Path:
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")
    return path


def _decode(path: Path, format_name: str) -> list[dict]:
    records = decode_records(path, format_name)
    assert isinstance(records, list)
    assert all(isinstance(record, dict) for record in records)
    assert all(isinstance(key, str) for record in records for key in record)
    return records


def test_decode_csv_preserves_headers_rows_quoted_and_empty_fields(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path / "vessels.csv",
        'imo,name,note\r\n123,Ada,"hello, world"\r\n456,,"two\nlines"\r\n,,\r\n',
    )

    assert _decode(source, "csv") == [
        {"imo": "123", "name": "Ada", "note": "hello, world"},
        {"imo": "456", "name": "", "note": "two\nlines"},
        {"imo": "", "name": "", "note": ""},
    ]


@pytest.mark.parametrize("payload", ["", "imo,name\n"])
def test_decode_csv_accepts_empty_datasets(tmp_path: Path, payload: str) -> None:
    source = _write(tmp_path / "empty.csv", payload)

    assert _decode(source, "csv") == []


@pytest.mark.parametrize(
    "payload",
    [
        "id,id\n1,2\n",
        "id,name\n1\n",
        "id,name\n1,Ada,extra\n",
        'id,name\n1,"unterminated\n',
    ],
)
def test_decode_csv_rejects_lossy_or_malformed_rows(
    tmp_path: Path,
    payload: str,
) -> None:
    source = _write(tmp_path / "invalid.csv", payload)

    with pytest.raises(DecodeError, match="(?i)(csv|header|column|field|row)"):
        decode_records(source, "csv")


def test_decode_json_preserves_an_object_as_one_record(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "one.json",
        '{"id": 1, "active": true, "note": null, "text": "Ada"}',
    )

    assert _decode(source, "json") == [
        {"id": 1, "active": True, "note": None, "text": "Ada"}
    ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('[{"id": 1}, {"id": 2}]', [{"id": 1}, {"id": 2}]),
        ("[]", []),
    ],
)
def test_decode_json_accepts_only_object_arrays(
    tmp_path: Path,
    payload: str,
    expected: list[dict],
) -> None:
    source = _write(tmp_path / "many.json", payload)

    assert _decode(source, "json") == expected


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "true",
        "7",
        '"record"',
        '[{"id": 1}, 2, {"id": 3}]',
        '{"id": 1, "id": 2}',
        '{"id": 1',
    ],
)
def test_decode_json_rejects_nonrecord_or_lossy_documents(
    tmp_path: Path,
    payload: str,
) -> None:
    source = _write(tmp_path / "invalid.json", payload)

    with pytest.raises(DecodeError):
        decode_records(source, "json")


@pytest.mark.parametrize("format_name", ["json", "jsonl"])
@pytest.mark.parametrize(
    ("lexeme", "expected", "expected_type"),
    [
        ("0", 0, int),
        ("123456789012345678901234567890", 123456789012345678901234567890, int),
        ("0.1", 0.1, float),
        ("1e308", 1e308, float),
        ("5e-324", 5e-324, float),
        ("-0.0", -0.0, float),
        ("0e-4000", 0.0, float),
    ],
)
def test_decode_json_formats_accept_standard_finite_python_numbers(
    tmp_path: Path,
    format_name: str,
    lexeme: str,
    expected: int | float,
    expected_type: type[int] | type[float],
) -> None:
    terminator = "\n" if format_name == "jsonl" else ""
    source = _write(
        tmp_path / f"finite.{format_name}",
        f'{{"value": {lexeme}}}{terminator}',
    )

    records = _decode(source, format_name)

    assert records == [{"value": expected}]
    assert type(records[0]["value"]) is expected_type


@pytest.mark.parametrize("format_name", ["json", "jsonl"])
@pytest.mark.parametrize("lexeme", ["1e400", "-1e400", "1e-4000", "-1e-4000"])
def test_decode_json_formats_reject_overflow_and_nonzero_to_zero_underflow(
    tmp_path: Path,
    format_name: str,
    lexeme: str,
) -> None:
    terminator = "\n" if format_name == "jsonl" else ""
    source = _write(
        tmp_path / f"out-of-range.{format_name}",
        f'{{"value": {lexeme}}}{terminator}',
    )

    with pytest.raises(
        DecodeError,
        match="(?i)(finite|number|numeric|range|represent|zero|precision)",
    ):
        decode_records(source, format_name)


@pytest.mark.parametrize("format_name", ["json", "jsonl"])
@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_decode_json_formats_reject_nonstandard_nonfinite_constants(
    tmp_path: Path,
    format_name: str,
    constant: str,
) -> None:
    terminator = "\n" if format_name == "jsonl" else ""
    source = _write(
        tmp_path / f"nonfinite.{format_name}",
        f'{{"value": {constant}}}{terminator}',
    )

    with pytest.raises(DecodeError, match="(?i)(json|constant|finite|number)"):
        decode_records(source, format_name)


def test_decode_jsonl_uses_only_lf_and_crlf_as_physical_record_boundaries(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path / "records.jsonl",
        '{"id": 1, "text": "before\u2028middle\u2029after"}\r\n'
        "\r\n"
        '{"id": 2}\n',
    )

    assert _decode(source, "jsonl") == [
        {"id": 1, "text": "before\u2028middle\u2029after"},
        {"id": 2},
    ]


def test_decode_jsonl_does_not_treat_bare_cr_as_a_record_boundary(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path / "bare-cr.jsonl", '{"id": 1}\r{"id": 2}\n')

    with pytest.raises(DecodeError, match=r"(?i)\bline 1\b"):
        decode_records(source, "jsonl")


@pytest.mark.parametrize(
    "invalid_record",
    [
        "not-json",
        "7",
        '{"id": 1, "id": 2}',
        '{"value": 1e400}',
        '{"value": 1e-4000}',
        '{"value": NaN}',
    ],
)
def test_decode_jsonl_reports_every_invalid_nonblank_physical_record_line(
    tmp_path: Path,
    invalid_record: str,
) -> None:
    source = _write(
        tmp_path / "invalid.jsonl",
        '{"ok": 1}\r\n\r\n' + invalid_record + '\r\n{"unreached": 4}\r\n',
    )

    with pytest.raises(DecodeError, match=r"(?i)\bline 3\b"):
        decode_records(source, "jsonl")


def test_decode_jsonl_reports_guarded_integer_failure_on_its_physical_line(
    tmp_path: Path,
) -> None:
    oversized_integer = "9" * 5_000
    source = _write(
        tmp_path / "oversized-integer.jsonl",
        f'{{"ok": 1}}\n{{"value": {oversized_integer}}}\n',
    )

    with pytest.raises(DecodeError, match=r"(?i)\bline 2\b"):
        decode_records(source, "jsonl")


def test_decode_jsonl_accepts_a_blank_only_dataset(tmp_path: Path) -> None:
    source = _write(tmp_path / "empty.jsonl", "\r\n  \r\n\t\n")

    assert _decode(source, "jsonl") == []


@pytest.mark.parametrize("record", ["\u2028", "\u2029"])
def test_decode_jsonl_rejects_unicode_separators_as_nonblank_physical_records(
    tmp_path: Path,
    record: str,
) -> None:
    source = _write(
        tmp_path / "unicode-separator.jsonl",
        f'{{"ok": 1}}\n{record}\n{{"unreached": 3}}\n',
    )

    with pytest.raises(DecodeError, match=r"(?i)\bline 2\b"):
        decode_records(source, "jsonl")


def _write_parquet(path: Path, columns: dict[str, list], schema: object) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pydict(columns, schema=schema)
    pq.write_table(
        table,
        path,
        compression=None,
        use_dictionary=False,
        write_statistics=False,
    )
    return path


def test_decode_parquet_preserves_rows_columns_nulls_and_primitives(
    tmp_path: Path,
) -> None:
    import pyarrow as pa

    source = _write_parquet(
        tmp_path / "records.parquet",
        {
            "id": [1, 2],
            "name": ["Ada", None],
            "active": [True, False],
            "score": [1.25, 2.5],
            "payload": [b"a", b"b"],
        },
        pa.schema(
            [
                ("id", pa.int64()),
                ("name", pa.string()),
                ("active", pa.bool_()),
                ("score", pa.float64()),
                ("payload", pa.binary()),
            ]
        ),
    )

    assert _decode(source, "parquet") == [
        {
            "id": 1,
            "name": "Ada",
            "active": True,
            "score": 1.25,
            "payload": b"a",
        },
        {
            "id": 2,
            "name": None,
            "active": False,
            "score": 2.5,
            "payload": b"b",
        },
    ]


def test_decode_parquet_accepts_an_empty_typed_table(tmp_path: Path) -> None:
    import pyarrow as pa

    source = _write_parquet(
        tmp_path / "empty.parquet",
        {"id": [], "name": []},
        pa.schema([("id", pa.int64()), ("name", pa.string())]),
    )

    assert _decode(source, "parquet") == []


def test_decode_parquet_rejects_nonprimitive_nested_shape(tmp_path: Path) -> None:
    import pyarrow as pa

    source = _write_parquet(
        tmp_path / "nested.parquet",
        {"items": [[1, 2]]},
        pa.schema([("items", pa.list_(pa.int64()))]),
    )

    with pytest.raises(DecodeError, match="(?i)(parquet|shape|primitive|nested|type)"):
        decode_records(source, "parquet")


def test_decode_parquet_rejects_corrupt_input(tmp_path: Path) -> None:
    source = _write(tmp_path / "invalid.parquet", b"not parquet")

    with pytest.raises(DecodeError, match="(?i)parquet"):
        decode_records(source, "parquet")


def test_decode_xml_preserves_attribute_child_and_combined_rows(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path / "owners.xml",
        """<rows>
  <row id="1" name="Ada"/>
  <row><id>2</id><name>Grace</name></row>
  <row id="3"><name>Lin</name><active>true</active></row>
</rows>
""",
    )

    assert _decode(source, "xml") == [
        {"id": "1", "name": "Ada"},
        {"id": "2", "name": "Grace"},
        {"id": "3", "name": "Lin", "active": "true"},
    ]


def test_decode_xml_accepts_an_empty_rows_container(tmp_path: Path) -> None:
    source = _write(tmp_path / "empty.xml", "<rows/>")

    assert _decode(source, "xml") == []


@pytest.mark.parametrize(
    ("boundary", "payload"),
    [
        (
            "rows",
            '<rows xmlns:unused="urn:unused"><row id="1"/></rows>',
        ),
        (
            "row",
            '<rows><row xmlns:unused="urn:unused" id="1"/></rows>',
        ),
        (
            "field",
            '<rows><row><name xmlns:unused="urn:unused">Ada</name></row></rows>',
        ),
    ],
)
def test_decode_xml_rejects_namespace_declarations_before_normalization(
    tmp_path: Path,
    boundary: str,
    payload: str,
) -> None:
    source = _write(tmp_path / f"namespace-{boundary}.xml", payload)

    with pytest.raises(DecodeError, match=r"(?i)\bnamespace declarations?\b"):
        decode_records(source, "xml")


@pytest.mark.parametrize(
    "payload",
    [
        '<rows><row id="attribute"><id>child</id></row></rows>',
        '<rows><row><id>1</id><id>2</id></row></rows>',
        '<rows source="must-not-be-dropped"><row id="1"/></rows>',
        '<rows><row id="1"/><metadata>not a row</metadata></rows>',
        '<rows><row><nested><id>1</id></nested></row></rows>',
        '<rows>outside<row id="1"/></rows>',
    ],
)
def test_decode_xml_rejects_lossy_or_unsupported_shapes(
    tmp_path: Path,
    payload: str,
) -> None:
    source = _write(tmp_path / "invalid-shape.xml", payload)

    with pytest.raises(
        DecodeError,
        match="(?i)(xml|duplicate|conflict|attribute|container|root|record|row|shape|flat|text)",
    ):
        decode_records(source, "xml")


@pytest.mark.parametrize(
    "payload",
    [
        '<!DOCTYPE rows [<!ENTITY value "expanded">]><rows><row><name>&value;</name></row></rows>',
        '<!DOCTYPE rows SYSTEM "https://example.invalid/rows.dtd"><rows/>',
        '<!DOCTYPE rows [<!ENTITY value SYSTEM "file:///etc/passwd">]><rows><row><name>&value;</name></row></rows>',
    ],
)
def test_decode_xml_rejects_entity_and_external_constructs(
    tmp_path: Path,
    payload: str,
) -> None:
    source = _write(tmp_path / "unsafe.xml", payload)

    with pytest.raises(
        DecodeError,
        match="(?i)(xml|doctype|entity|external|reference|unsafe)",
    ):
        decode_records(source, "xml")


def test_decode_records_rejects_an_unowned_format(tmp_path: Path) -> None:
    source = _write(tmp_path / "records.txt", "id\n1\n")

    with pytest.raises(UnsupportedFormatError, match="(?i)(unsupported|format)"):
        decode_records(source, "text")
