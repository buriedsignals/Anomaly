from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

_OUTPUTS = (
    "## Outputs\n\n"
    "- [accepted findings](findings/findings.json)\n"
    "- [report](findings/report.md)\n"
    "- [unresolved work](findings/unresolved.md)\n"
)
_MARKED_OUTPUTS = (
    "<!-- anomaly:outputs:start -->\n"
    f"{_OUTPUTS}"
    "<!-- anomaly:outputs:end -->\n"
)


class ReadmeProjectionError(RuntimeError):
    pass


def project_readme(root: Path, snapshot: Mapping[str, Any], completed: str | None) -> None:
    """Update only Anomaly-owned README fields and the bounded outputs block."""
    readme_path = root / "README.md"
    if not readme_path.is_file():
        return
    if readme_path.is_symlink():
        raise ReadmeProjectionError("README.md must be a regular case file")
    original = readme_path.read_text(encoding="utf-8")
    readme = re.sub(
        r"(?ms)<!-- anomaly:outputs:start -->\n.*?<!-- anomaly:outputs:end -->\n?",
        "",
        original,
    )
    phase = completed or "P0"
    values = {
        "Status": "complete" if phase == "P7" and snapshot.get("status") == "complete" else "active",
        "Last completed phase": phase,
    }
    for label, value in values.items():
        readme, count = re.subn(
            rf"(?m)^{re.escape(label)}: .*?$",
            f"{label}: {value}",
            readme,
            count=1,
        )
        if not count:
            readme += ("" if readme.endswith("\n") else "\n") + f"\n{label}: {value}\n"
    if values["Status"] == "complete":
        readme += ("" if readme.endswith("\n") else "\n") + "\n" + _MARKED_OUTPUTS
    if readme == original:
        return
    temporary = readme_path.with_suffix(".md.tmp")
    temporary.write_text(readme, encoding="utf-8")
    temporary.replace(readme_path)
