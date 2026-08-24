from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

IDENTITY_PHASES = {
    "source": "P1",
    "prepared": "P2",
    "recommendation": "P3",
    "gate_a": "P4",
    "detector": "P4",
    "draft": "P5",
    "replay": "P6",
    "review": "P6",
    "gate_b": "P7",
}
_NON_SOURCE_RECEIPTS = {"charts.json", "gate-a.json", "gate-b.json", "replay.json"}


def changed_identities(root: Path, recorded: Mapping[str, Any]) -> tuple[str, list[str]] | None:
    changed = [
        name
        for name, digest in recorded.items()
        if name in IDENTITY_PHASES and digest != artifact_identity(root, name)
    ]
    if not changed:
        return None
    return min((IDENTITY_PHASES[name] for name in changed), key=_phase_index), changed


def capture_identities(root: Path, state: dict[str, Any], through_phase: str) -> None:
    identities = dict(state.get("identities", {}))
    through_index = _phase_index(through_phase)
    for name, phase in IDENTITY_PHASES.items():
        if _phase_index(phase) <= through_index:
            digest = artifact_identity(root, name)
            if digest is not None:
                identities[name] = digest
    state["identities"] = identities


def artifact_identity(root: Path, name: str) -> str | None:
    if name == "recommendation":
        return _recommendation_identity(root)
    files = _identity_files(root, name)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        digest.update(_relative(root, path).encode("utf-8"))
        digest.update(b"\0")
        if path.is_symlink() or not path.is_file():
            digest.update(b"unavailable")
        else:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _recommendation_identity(root: Path) -> str | None:
    try:
        plan = json.loads((root / "detectors" / "plan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(plan, dict):
        return None
    payload = {key: plan.get(key) for key in ("recommended", "parameters", "reasons", "blocked")}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _identity_files(root: Path, name: str) -> list[Path]:
    if name == "source":
        candidates = [root / "data" / "sources.json", root / "data" / "raw"]
        receipts = root / ".anomaly" / "receipts"
        if receipts.is_dir():
            candidates.extend(path for path in receipts.iterdir() if path.name not in _NON_SOURCE_RECEIPTS)
    else:
        relative = {
            "prepared": ("data/prepared", "data/index.duckdb"),
            "gate_a": ("detectors/plan.json", ".anomaly/receipts/gate-a.json"),
            "detector": ("detectors/used",),
            "draft": ("findings/draft.json",),
            "replay": ("evidence/replay.json", ".anomaly/receipts/replay.json"),
            "review": ("findings/review.json",),
            "gate_b": (".anomaly/receipts/gate-b.json",),
        }[name]
        candidates = [root / path for path in relative]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir() and not candidate.is_symlink():
            files.extend(path for path in candidate.rglob("*") if path.is_file() or path.is_symlink())
        elif candidate.exists() or candidate.is_symlink():
            files.append(candidate)
    return sorted(set(files), key=lambda path: _relative(root, path))


def _phase_index(phase: str) -> int:
    return int(phase[1:])


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
