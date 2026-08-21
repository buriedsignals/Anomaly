#!/usr/bin/env python3
"""Run bounded live verification cases through the public catalogue contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "assets" / "verification-cases.json"


class ConfigurationError(ValueError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run source-specific verification cases through `catalogue query` "
            "and emit one bounded JSON summary."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help="case file (default: assets/verification-cases.json)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="run only this case ID; repeat to select several",
    )
    parser.add_argument(
        "--catalogue",
        default="catalogue",
        help="catalogue executable path (default: catalogue)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="seconds allowed per query (default: 60)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list cases without making network requests",
    )
    return parser


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{label} must be a JSON object")
    return value


def _load(path: Path) -> tuple[str, list[dict[str, Any]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read case file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"invalid JSON in {path}: {exc}") from exc
    payload = _object(payload, "case file")
    source_id = payload.get("source_id")
    cases = payload.get("cases")
    if not isinstance(source_id, str) or not source_id:
        raise ConfigurationError("source_id must be a non-empty string")
    if not isinstance(cases, list) or not cases:
        raise ConfigurationError("cases must be a non-empty array")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(cases):
        case = _object(raw, f"cases[{index}]")
        case_id = case.get("id")
        operation = case.get("operation")
        if not isinstance(case_id, str) or not case_id:
            raise ConfigurationError(f"cases[{index}].id must be a non-empty string")
        if case_id in seen:
            raise ConfigurationError(f"duplicate case ID: {case_id}")
        seen.add(case_id)
        if not isinstance(operation, str) or not operation:
            raise ConfigurationError(f"{case_id}.operation must be a non-empty string")
        _object(case.get("input"), f"{case_id}.input")
        _object(case.get("expect"), f"{case_id}.expect")
        validated.append(case)
    return source_id, validated


def _select(
    cases: list[dict[str, Any]], requested: list[str] | None
) -> list[dict[str, Any]]:
    if requested:
        wanted = set(requested)
        available = {case["id"] for case in cases}
        unknown = sorted(wanted - available)
        if unknown:
            raise ConfigurationError(
                f"unknown case ID(s): {', '.join(unknown)}; "
                f"available: {', '.join(sorted(available))}"
            )
        return [case for case in cases if case["id"] in wanted]
    return [case for case in cases if case.get("enabled", True)]


def _parse_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    for candidate in (completed.stdout, completed.stderr):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("catalogue did not return a JSON object")


def _assertions(payload: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    statuses = expect.get("statuses", ["ok"])
    if not isinstance(statuses, list) or not all(isinstance(v, str) for v in statuses):
        raise ConfigurationError("expect.statuses must be an array of strings")
    if payload.get("status") not in statuses:
        failures.append(
            f"status {payload.get('status')!r} is not one of {statuses!r}"
        )
    # Expected terminal statuses such as auth_required or operation_unavailable
    # are valid environment findings, not successful data queries. They do not
    # carry a records array and must not be judged against record assertions.
    if payload.get("status") != "ok":
        return failures
    records = payload.get("records")
    if not isinstance(records, list):
        failures.append("records is not an array")
        records = []
    minimum = expect.get("min_records", 0)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        raise ConfigurationError("expect.min_records must be a non-negative integer")
    if len(records) < minimum:
        failures.append(f"returned {len(records)} records; expected at least {minimum}")
    required = expect.get("required_fields", [])
    if not isinstance(required, list) or not all(isinstance(v, str) for v in required):
        raise ConfigurationError("expect.required_fields must be an array of strings")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            failures.append(f"records[{index}] is not an object")
            continue
        missing = [field for field in required if record.get(field) in (None, "")]
        if missing:
            failures.append(f"records[{index}] missing values for: {', '.join(missing)}")
    return failures


def _run_case(
    source_id: str,
    case: dict[str, Any],
    catalogue: str,
    timeout: float,
) -> dict[str, Any]:
    command = [
        catalogue,
        "query",
        source_id,
        "--operation",
        case["operation"],
        "--input",
        json.dumps(case["input"], ensure_ascii=False, separators=(",", ":")),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"catalogue executable not found: {catalogue!r}; use --catalogue PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        return {
            "id": case["id"],
            "operation": case["operation"],
            "passed": False,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "failures": [f"query exceeded {timeout:g} seconds"],
        }
    try:
        payload = _parse_result(completed)
        failures = _assertions(payload, case["expect"])
    except (ValueError, ConfigurationError) as exc:
        payload = {}
        failures = [str(exc)]
    expected_statuses = case["expect"].get("statuses", ["ok"])
    expected_terminal_status = (
        isinstance(expected_statuses, list)
        and payload.get("status") in expected_statuses
        and payload.get("status") != "ok"
    )
    if completed.returncode != 0 and not expected_terminal_status:
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        failures.append(
            f"catalogue exited {completed.returncode}: "
            f"{error.get('code') or payload.get('status') or 'query failed'}"
        )
    return {
        "id": case["id"],
        "operation": case["operation"],
        "passed": not failures,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "status": payload.get("status"),
        "live_verified": payload.get("status") == "ok" and not failures,
        "records": len(payload.get("records") or []),
        "failures": failures,
    }


def main() -> int:
    args = _parser().parse_args()
    if args.timeout <= 0:
        print("Error: --timeout must be greater than zero", file=sys.stderr)
        return 2
    try:
        source_id, cases = _load(args.cases)
        selected = _select(cases, args.case_ids)
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.list:
        print(
            json.dumps(
                {
                    "source_id": source_id,
                    "cases": [
                        {
                            "id": case["id"],
                            "operation": case["operation"],
                            "enabled": case.get("enabled", True),
                        }
                        for case in cases
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not selected:
        print("Error: no enabled verification cases", file=sys.stderr)
        return 2
    try:
        results = [
            _run_case(source_id, case, args.catalogue, args.timeout)
            for case in selected
        ]
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    passed = all(result["passed"] for result in results)
    print(
        json.dumps(
            {
                "source_id": source_id,
                "passed": passed,
                "case_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
