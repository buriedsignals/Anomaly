"""Local detector catalogue APIs."""

import re
from pathlib import PurePosixPath
from typing import Any


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DETECTOR_ID = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\Z")


def is_valid_snapshot_reference(
    detector_id: Any,
    snapshot_path: Any,
    snapshot_hash: Any,
    *,
    allow_legacy: bool = False,
) -> bool:
    """Return whether a snapshot path is safely bound to its detector and hash."""
    if (
        not isinstance(detector_id, str)
        or _DETECTOR_ID.fullmatch(detector_id) is None
        or not isinstance(snapshot_path, str)
        or not isinstance(snapshot_hash, str)
        or _SHA256.fullmatch(snapshot_hash) is None
    ):
        return False
    detector_name = detector_id.replace(".", "__")
    canonical_name = (
        f"{detector_name}__{snapshot_hash.removeprefix('sha256:')}.json"
    )
    if not allow_legacy:
        return snapshot_path == f"detectors/used/{canonical_name}"
    parts = PurePosixPath(snapshot_path).parts
    return (
        len(parts) == 3
        and parts[:2] == ("detectors", "used")
        and parts[2] in {canonical_name, f"{detector_name}.json"}
    )
