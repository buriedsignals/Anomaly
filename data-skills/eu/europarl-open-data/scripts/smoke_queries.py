#!/usr/bin/env python3
"""Run cheap live queries through the European Parliament source adapter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _adapter():
    path = Path(__file__).resolve().parents[1] / "adapter.py"
    spec = importlib.util.spec_from_file_location("europarl_smoke_adapter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    adapter = _adapter()
    probes = [
        {"name": "Keller", "country": "FR", "limit": 2},
        {"q": "artificial intelligence", "language": "en", "limit": 2},
        {
            "resource": "adopted_texts",
            "q": "artificial intelligence",
            "language": "en",
            "limit": 2,
        },
    ]
    summary = []
    for query in probes:
        result = adapter.run(query, None)
        assert result["records"], f"empty live result for {query}"
        assert all(record.get("source_url") for record in result["records"])
        summary.append(
            {
                "query": query,
                "resource": result["resource"],
                "records": len(result["records"]),
                "first": result["records"][0],
            }
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
