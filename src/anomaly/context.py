"""Read-only lookup of what Anomaly offers an investigation.

    python -m anomaly.context                  # every domain
    python -m anomaly.context --domain lobbying
    python -m anomaly.context --source global/partyfacts/parties

For each domain (a type of data such as lobbying or procurement) it lists the
data sources that cover it, with access, cost, licence and the SKILL.md that
explains how to get and use the data, and the detectors that read that type
of data. Core detectors that run on any table are listed once under
``any_table``. Detectors come from the published catalogue, so what is listed
is exactly what ``anomaly.oneshot`` will run. Nothing here touches the network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from anomaly import catalogue, domains

SOURCES_ROOT = Path(__file__).resolve().parents[2] / "data-skills"
_TOP = re.compile(r"^([a-z_]+):\s*(.*)$")
_CHILD = re.compile(r"^  ([a-z_]+):\s*(.*)$")
_COST = re.compile(r"\bcost:\s*([a-z_-]+)")
_INLINE = re.compile(r"([a-z_]+):\s*([^,}]+)")
_DETECTOR_FIELDS = (
    "id", "version", "title", "description", "required_tables", "required_fields",
    "parameters", "assumptions", "false_positives", "severity",
)


def _scalar(value: str) -> str:
    return value.strip().strip("'\"")


def _source(meta_path: Path, root: Path) -> dict[str, Any]:
    """Read the context fields of one source ``meta.yaml`` line by line.

    Source metadata uses YAML features the restricted detector parser does not
    support, so only the fields the lookup needs are read: top-level scalars and
    folded text, ``auth.type``/``setup_url``, ``license.data_license``,
    ``provides`` table names and every operation's ``cost``.
    """
    top: dict[str, str] = {}
    children: dict[str, dict[str, str]] = {}
    current, folded = None, False
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        top_match = _TOP.match(line)
        if top_match:
            current, value = top_match.groups()
            folded = value in {">-", ">", "|", "|-"}
            top[current] = "" if folded else _scalar(value)
            children.setdefault(current, {})
            # A flow mapping such as ``auth: {type: none}`` holds child fields inline.
            if value.startswith("{"):
                children[current] = dict(_INLINE.findall(value))
            continue
        if current and folded and line.startswith("  "):
            top[current] = (top[current] + " " + line.strip()).strip()
            continue
        child = _CHILD.match(line)
        if child and current:
            children[current][child.group(1)] = _scalar(child.group(2))
    package = meta_path.parent
    license_text = top.get("license") or children.get("license", {}).get("data_license", "")
    costs = sorted(set(_COST.findall(meta_path.read_text(encoding="utf-8"))))
    return {
        "id": top.get("id", ""),
        "title": top.get("title", ""),
        "description": top.get("description", ""),
        "domain": top.get("category", ""),
        "jurisdiction": top.get("jurisdiction", ""),
        "status": top.get("status", ""),
        "auth": children.get("auth", {}).get("type", "").strip() or "none",
        "setup_url": children.get("auth", {}).get("setup_url", ""),
        "cost": costs,
        "license": license_text,
        "provides": sorted(children.get("provides", {})),
        "skill": (package / "SKILL.md").relative_to(root.parent).as_posix(),
    }


def sources(root: Path = SOURCES_ROOT) -> list[dict[str, Any]]:
    root = Path(root)
    found = [
        _source(path, root) for path in sorted(root.rglob("meta.yaml"))
        if not path.is_symlink() and "_template" not in path.parts
    ]
    return sorted(found, key=lambda item: item["id"])


def _detectors() -> list[dict[str, Any]]:
    published = json.loads(catalogue.CATALOGUE_PATH.read_text(encoding="utf-8"))
    return [
        {**{key: entry[key] for key in _DETECTOR_FIELDS if key in entry}, "domain": entry.get("data_type")}
        for entry in published["detectors"]
    ]


def build(domain: str | None = None, root: Path = SOURCES_ROOT) -> dict[str, Any]:
    all_sources, detectors = sources(root), _detectors()
    names = sorted({item["domain"] for item in all_sources if item["domain"]}
                   | {item["domain"] for item in detectors if item["domain"]})
    if domain is not None and domain not in names:
        raise KeyError(f"unknown domain: {domain}")
    result: dict[str, Any] = {"domains": []}
    for name in names if domain is None else [domain]:
        contract = domains.load_domain(name) if name in domains.domain_names() else None
        result["domains"].append({
            "domain": name,
            "contract": None if contract is None else {
                table: list(spec["columns"]) for table, spec in contract["tables"].items()
            },
            "sources": [item for item in all_sources if item["domain"] == name],
            "detectors": [item for item in detectors if item["domain"] == name],
        })
    result["any_table"] = [item for item in detectors if not item["domain"]]
    return result


def source_skill(source_id: str, root: Path = SOURCES_ROOT) -> dict[str, Any]:
    match = next((item for item in sources(root) if item["id"] == source_id), None)
    if match is None:
        raise KeyError(f"unknown source: {source_id}")
    skill = Path(root).parent / match["skill"]
    return {**match, "skill_text": skill.read_text(encoding="utf-8")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anomaly.context", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--domain", help="only this domain")
    scope.add_argument("--source", help="one source, with its SKILL.md text")
    args = parser.parse_args(argv)
    try:
        payload = source_skill(args.source) if args.source else build(args.domain)
    except (KeyError, OSError, ValueError) as error:
        print(f"anomaly.context: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
