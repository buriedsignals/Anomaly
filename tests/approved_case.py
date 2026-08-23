"""Shared builder for a prepared, approved detector case in tests.

Synthetic by design: tiny inline CSV payloads, no external fixtures. Keeps
pipeline/execution contract tests independent of any real investigation data.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path


def _api():
    return importlib.import_module("anomaly.detectors.registry")


def _all_detectors() -> list[dict[str, object]]:
    root = Path(__file__).parents[1] / "detectors"
    detectors = [
        _api().validate_detector_package(path.parent)
        for path in sorted(root.rglob("meta.yaml"))
        if "_template" not in path.parts
    ]
    return sorted(
        detectors,
        key=lambda item: (
            int(str(item["source_detector_id"])[1:])
            if str(item.get("source_detector_id", "")).startswith("D")
            and str(item["source_detector_id"])[1:].isdigit()
            else 10**9,
            item["id"],
        ),
    )


def approved_case(
    tmp_path: Path,
    source_ids: tuple[str, ...] = ("senate_filings",),
    detector_ids: tuple[str, ...] = ("us_lobbying.spending_spikes",),
    source_payloads: dict[str, str] | None = None,
) -> Path:
    from anomaly.prepare import prepare_sources
    from anomaly.recommend import approve_detector_plan
    from p2_helpers import NOW, create_p2_case, register, write_source

    root = tmp_path / "case"
    create_p2_case(root)
    for index, source_id in enumerate(source_ids):
        payload = (source_payloads or {}).get(
            source_id,
            "id,registrant_id,registrant_name,filing_year,filing_period,income,filing_type\n"
            "1,1,Example,2025,Q1,100,Q1\n",
        )
        source = write_source(
            tmp_path / f"{source_id}-{index}.csv",
            payload,
        )
        register(root, source, source_id)
    prepare_sources(root, now=NOW)
    plan = _api().recommend_detectors(root, max_detectors=10)
    plan["recommended"] = list(detector_ids)
    plan["parameters"] = {
        detector_id: next(item["parameters"] for item in _all_detectors() if item["id"] == detector_id)
        for detector_id in detector_ids
    }
    table_ids = [
        table["table_id"]
        for table in json.loads(
            (root / "data" / "prepared" / "transforms.json").read_text()
        )["tables"]
    ]
    plan["reasons"] = {
        detector_id: {"table_ids": table_ids} for detector_id in detector_ids
    }
    (root / "detectors" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    approve_detector_plan(root, list(detector_ids), approved_by="test-journalist", now=NOW)
    return root
