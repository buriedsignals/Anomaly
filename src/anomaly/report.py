"""Deterministic SVG findings charts rendered from hash-bound Gate-B artifacts.

Charts are a post-report enrichment of P7: they read only accepted findings and
the replayed evidence bound by the Gate-B receipt, render pure-stdlib static
SVGs, and record a sha256 receipt so regeneration is verifiable and byte-
deterministic.  No network access, no imaging dependencies, no timestamps.
"""

from __future__ import annotations

import math
import json
import hashlib
import os
import xml.sax.saxutils
from pathlib import Path
from typing import Any

from anomaly.events import phase_event
from anomaly.review import (
    ReviewError,
    _hash_json,
    _owned,
    _read_json,
    _redact_text,
    _root,
    _text,
)

__all__ = ["ChartError", "generate_charts"]

#: Calculation kinds whose ``value`` is unit-free and therefore comparable
#: across claims on one axis.  Every other kind is skipped and recorded.
_COMPARABLE_KINDS = ("percentage", "ratio", "relative_difference")

_CHARTS_DIR = "findings/charts"
_RECEIPT_PATH = ".anomaly/receipts/charts.json"

_WIDTH = 720
_LABEL_WIDTH = 250
_PLOT_RIGHT_PAD = 90
_BAR_HEIGHT = 24
_BAR_GAP = 12
_TOP = 56
_BOTTOM_PAD = 16


class ChartError(RuntimeError):
    """A findings-chart contract was not satisfied."""


@phase_event("P7", "generate_charts")
def generate_charts(root: Path) -> dict[str, Any]:
    """Render deterministic SVG charts from Gate-B accepted findings.

    Refuses without writing anything unless ``.anomaly/receipts/gate-b.json``
    exists and still binds the current findings, review, and replay artifacts.
    """
    root = _root(root)
    gate_b = _gate_b_artifacts(root)

    claims = [claim for claim in gate_b["findings"].get("claims", []) if isinstance(claim, dict)]
    categories = _category_counts(claims)
    values, skipped = _comparable_values(claims)
    detectors = _detector_counts(gate_b["replay"])

    payloads = {
        "claims-by-category.svg": _bar_chart(
            "Accepted claims by category", categories, counts=True
        ).encode("utf-8"),
        "claim-values-by-rank.svg": _bar_chart(
            "Claim calculation values by rank", values, counts=False
        ).encode("utf-8"),
        "signals-per-detector.svg": _bar_chart(
            "Signals per detector", detectors, counts=True
        ).encode("utf-8"),
    }

    charts_dir = _owned(root, _CHARTS_DIR)
    charts_dir.mkdir(parents=True, exist_ok=True)
    # Idempotent regeneration: drop anything a prior generation left behind
    # before committing the new set.
    for path in charts_dir.iterdir():
        if path.is_file() and path.name not in payloads:
            path.unlink()
    digests: dict[str, str] = {}
    for name, blob in sorted(payloads.items()):
        _atomic_write(charts_dir / name, blob)
        digests[name] = "sha256:" + hashlib.sha256(blob).hexdigest()

    manifest = {
        "kind": "charts",
        "gate": "B",
        "findings_identity": "findings/findings.json",
        "findings_hash": gate_b["receipt"]["findings_hash"],
        "replay_identity": "evidence/replay.json",
        "replay_hash": _hash_json(gate_b["replay"]),
        "charts": dict(sorted(digests.items())),
        "notes": {
            "comparable_kinds": list(_COMPARABLE_KINDS),
            "skipped_claims": skipped,
            "text": "All chart text passes the case redaction filter; keys are sorted and no timestamp enters the output.",
        },
    }
    _atomic_write(
        _owned(root, _RECEIPT_PATH),
        (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    return manifest


def _gate_b_artifacts(root: Path) -> dict[str, Any]:
    """Mirror the write_report Gate-B verification; refuse otherwise."""
    def load(relative: str) -> Any:
        try:
            return _read_json(_owned(root, relative))
        except ReviewError as error:
            raise ChartError(f"required artifact is unavailable: {relative}") from error

    findings = load("findings/findings.json")
    receipt = load(".anomaly/receipts/gate-b.json")
    review_path = _owned(root, "findings/review.json")
    replay_path = _owned(root, "evidence/replay.json")
    review = load("findings/review.json")
    replay = load("evidence/replay.json")
    if (
        not isinstance(findings, dict)
        or findings.get("status") != "accepted"
        or not isinstance(receipt, dict)
        or receipt.get("kind") != "review"
        or receipt.get("gate") != "B"
        or receipt.get("findings_hash") != _hash_json(findings)
        or receipt.get("accepted_claim_ids")
        != [claim.get("claim_id") for claim in findings.get("claims", []) if isinstance(claim, dict)]
        or not review_path.is_file()
        or receipt.get("review_hash") != _hash_json(review)
        or not replay_path.is_file()
        or receipt.get("replay_hash") != _hash_json(replay)
        or receipt.get("replay_status") != "replayed"
    ):
        raise ChartError("hash-bound Gate B receipt is required")
    if not isinstance(findings.get("claims"), list) or not isinstance(replay.get("runs"), list):
        raise ChartError("invalid accepted findings or replay")
    return {"findings": findings, "receipt": receipt, "review": review, "replay": replay}


def _claim_labels(claim: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    candidates = [claim.get("category"), *(claim.get("categories") or [])]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip() and candidate not in labels:
            labels.append(candidate)
    return labels


def _category_counts(claims: list[dict[str, Any]]) -> list[tuple[str, float]]:
    counts: dict[str, int] = {}
    for claim in claims:
        for label in _claim_labels(claim):
            counts[label] = counts.get(label, 0) + 1
    return [(label, float(counts[label])) for label in sorted(counts)]


def _comparable_values(claims: list[dict[str, Any]]) -> tuple[list[tuple[str, float]], list[dict[str, str]]]:
    entries: list[tuple[int, str, float]] = []
    skipped: list[dict[str, str]] = []
    for claim in claims:
        claim_id = _text(claim.get("claim_id", "claim"))
        calculation = claim.get("calculation")
        kind = calculation.get("kind") if isinstance(calculation, dict) else None
        value = calculation.get("value") if isinstance(calculation, dict) else None
        numeric = (
            kind in _COMPARABLE_KINDS
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        if numeric:
            rank = claim.get("rank")
            order = rank if isinstance(rank, int) and not isinstance(rank, bool) else 10**9
            entries.append((order, claim_id, float(value)))
        elif isinstance(calculation, dict):
            skipped.append(
                {
                    "claim_id": claim_id,
                    "reason": f"calculation kind '{_text(kind)}' yields no value comparable across claims",
                }
            )
        else:
            skipped.append({"claim_id": claim_id, "reason": "claim carries no calculation"})
    entries.sort(key=lambda item: (item[0], item[1]))
    return [(claim_id, value) for _, claim_id, value in entries], sorted(
        skipped, key=lambda item: item["claim_id"]
    )


def _detector_counts(replay: dict[str, Any]) -> list[tuple[str, float]]:
    counts: dict[str, int] = {}
    for run in replay.get("runs", []):
        if not isinstance(run, dict):
            continue
        detector = run.get("detector_id")
        signal_count = run.get("signal_count")
        if (
            isinstance(detector, str)
            and detector.strip()
            and isinstance(signal_count, int)
            and not isinstance(signal_count, bool)
            and signal_count >= 0
        ):
            counts[detector] = counts.get(detector, 0) + signal_count
    return [(detector, float(counts[detector])) for detector in sorted(counts)]


def _format_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.6g}"


def _bar_chart(title: str, items: list[tuple[str, float]], *, counts: bool) -> str:
    """Render a fixed-layout horizontal bar chart; callers pre-sort ``items``."""
    height = _TOP + max(len(items), 1) * (_BAR_HEIGHT + _BAR_GAP) - _BAR_GAP + _BOTTOM_PAD
    plot_width = _WIDTH - _LABEL_WIDTH - _PLOT_RIGHT_PAD
    peak = max((value for _, value in items), default=0.0)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}" role="img">',
        f"  <title>{xml.sax.saxutils.escape(_redact_text(title))}</title>",
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        "  <text x=\"16\" y=\"34\" font-family=\"monospace\" font-size=\"18\" "
        f"fill=\"#111111\">{xml.sax.saxutils.escape(_redact_text(title))}</text>",
    ]
    if not items:
        parts.append(
            "  <text x=\"16\" y=\"72\" font-family=\"monospace\" font-size=\"13\" "
            "fill=\"#555555\">no chartable records</text>"
        )
    for index, (label, value) in enumerate(items):
        y = _TOP + index * (_BAR_HEIGHT + _BAR_GAP)
        text = xml.sax.saxutils.escape(_redact_text(label))
        parts.append(
            f"  <text x=\"{_LABEL_WIDTH - 12}\" y=\"{y + _BAR_HEIGHT - 6}\" "
            "font-family=\"monospace\" font-size=\"12\" fill=\"#333333\" "
            f"text-anchor=\"end\">{text}</text>"
        )
        if peak > 0 and value > 0:
            bar_width = int(round(plot_width * value / peak))
            parts.append(
                f"  <rect x=\"{_LABEL_WIDTH}\" y=\"{y}\" width=\"{bar_width}\" "
                f"height=\"{_BAR_HEIGHT}\" fill=\"#35507a\"/>"
            )
            parts.append(
                f"  <text x=\"{_LABEL_WIDTH + bar_width + 8}\" y=\"{y + _BAR_HEIGHT - 6}\" "
                "font-family=\"monospace\" font-size=\"12\" fill=\"#333333\">"
                f"{xml.sax.saxutils.escape(_format_number(value))}</text>"
            )
        else:
            shown = "0" if counts else _format_number(value)
            parts.append(
                f"  <rect x=\"{_LABEL_WIDTH}\" y=\"{y}\" width=\"2\" "
                f"height=\"{_BAR_HEIGHT}\" fill=\"#b9c4d6\"/>"
            )
            parts.append(
                f"  <text x=\"{_LABEL_WIDTH + 12}\" y=\"{y + _BAR_HEIGHT - 6}\" "
                "font-family=\"monospace\" font-size=\"12\" fill=\"#333333\">"
                f"{shown}</text>"
            )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _atomic_write(target: Path, blob: bytes) -> None:
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_bytes(blob)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
