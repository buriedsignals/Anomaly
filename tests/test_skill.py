from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "anomaly" / "SKILL.md"
REVIEWER_PATH = REPO_ROOT / "agents" / "anomaly-data-reviewer.md"


def _required_text(path: Path) -> str:
    assert path.is_file(), f"required installed artifact is missing: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _anomaly_skill_copies() -> list[str]:
    copies: list[str] = []
    for path in REPO_ROOT.rglob("SKILL.md"):
        if path.name != "SKILL.md" or path.parent.name != "anomaly":
            continue
        if any(part in {".jj", ".venv", ".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        copies.append(path.relative_to(REPO_ROOT).as_posix())
    return sorted(copies)


def _reviewer_copies() -> list[str]:
    return sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPO_ROOT.rglob("anomaly-data-reviewer.md")
        if not any(part in {".jj", ".venv", ".pytest_cache", "__pycache__"} for part in path.parts)
    )


def test_exactly_one_anomaly_skill_and_one_reviewer_are_installed() -> None:
    _required_text(SKILL_PATH)
    _required_text(REVIEWER_PATH)

    assert _anomaly_skill_copies() == ["skills/anomaly/SKILL.md"]
    assert _reviewer_copies() == ["agents/anomaly-data-reviewer.md"]


def test_installed_skill_and_reviewer_follow_workspace_metadata_conventions() -> None:
    skill = _required_text(SKILL_PATH)
    reviewer = _required_text(REVIEWER_PATH)

    assert skill.startswith("---\n")
    for field in ("name: anomaly", "description:", "version:", "invocable_by:"):
        assert field in skill

    assert reviewer.startswith("---\n")
    for field in ("name: anomaly-data-reviewer", "description:", "iteration_limit:"):
        assert field in reviewer


def test_skill_declares_linear_p0_to_p7_sequence_and_both_gates() -> None:
    skill = _required_text(SKILL_PATH)
    phases = re.findall(r"(?im)^\s*#{1,6}\s*(P[0-7])(?:\s|$)", skill)

    assert phases == [f"P{number}" for number in range(8)]
    assert skill.index("Gate A") < skill.index("P4")
    assert skill.index("Gate B") < skill.index("P7")
    assert skill.index("Gate A") < skill.index("Gate B")
    assert re.search(r"(?i)no finishing branches|linear", skill)


def test_skill_contracts_durable_state_bounded_retries_resume_and_portable_paths() -> None:
    skill = _required_text(SKILL_PATH)

    for path in (".anomaly/state.json", ".anomaly/events.jsonl", ".anomaly/receipts", ".anomaly/attempts"):
        assert path in skill
    assert re.search(r"(?i)(?:bounded|finite|max(?:imum)?|limit(?:ed)?).{0,80}retries?", skill)
    assert re.search(r"(?i)resume.{0,120}(?:event|receipt|state)", skill)
    assert re.search(r"(?i)(?:relative paths?|portable).{0,160}(?:move|copy|relocat)", skill)
    assert re.search(r"(?i)last completed event|resume from", skill)


def test_skill_marks_missing_data_and_detector_code_as_unavailable() -> None:
    skill = _required_text(SKILL_PATH)

    assert re.search(r"(?i)missing.{0,100}data", skill)
    assert re.search(r"(?i)detector code.{0,100}(?:missing|unavailable|absent)", skill)
    assert re.search(r"(?i)replay.{0,100}unavailable", skill)
    assert re.search(r"(?i)never.{0,100}(?:approximate|assume|substitute)", skill)


def test_reviewer_is_read_only_for_drafts_and_cannot_promote_findings() -> None:
    reviewer = _required_text(REVIEWER_PATH)

    assert re.search(r"(?i)findings/review\.json", reviewer)
    assert re.search(r"(?i)(?:never|must not|cannot|read[- ]only).{0,120}draft", reviewer)
    assert re.search(r"(?i)(?:never|must not|cannot).{0,120}(?:promot|accept|materializ).{0,80}finding", reviewer)

    prohibition = re.compile(
        r"(?i)\b(?:never|must\s+not|do\s+not|cannot|no|read[- ]only|prohibited|forbidden)\b"
    )
    mutation = re.compile(
        r"(?i)\b(?:write|edit|modify|change|update|promot|accept|materializ)\w*\b"
    )
    for line in reviewer.splitlines():
        if re.search(r"(?i)findings/(?:draft\.json|findings\.json)", line) and mutation.search(line):
            assert prohibition.search(line), f"active draft/finding mutation: {line!r}"


def test_reviewer_has_no_case_execution_contact_publishing_or_knowledge_system_instructions() -> None:
    reviewer = _required_text(REVIEWER_PATH)

    # Negative prohibitions are allowed, but no active command or tool
    # instruction may teach the reviewer to perform these operations.
    forbidden = re.compile(
        r"(?i)\b(?:execute-shell|subprocess|shell|bash|python|publish|contact|upload|vault|"
        r"openknowledge|obsidian|spotlight|knowledge\s+system)\b"
    )
    prohibition = re.compile(
        r"(?i)\b(?:never|must\s+not|do\s+not|cannot|no|without|read[- ]only|"
        r"prohibited|forbidden|disallowed)\b"
    )
    for line in reviewer.splitlines():
        if forbidden.search(line):
            assert prohibition.search(line), f"active forbidden instruction: {line!r}"
    assert not re.search(r"(?im)^\s*```(?:bash|sh|shell|python)", reviewer)


def test_skill_does_not_route_into_external_knowledge_systems() -> None:
    skill = _required_text(SKILL_PATH)
    forbidden = re.compile(r"(?i)\b(?:Spotlight|OpenKnowledge|Obsidian|vault)\b")
    prohibition = re.compile(
        r"(?i)\b(?:never|must\s+not|do\s+not|cannot|no|without|read[- ]only|"
        r"prohibited|forbidden|disallowed)\b"
    )
    for line in skill.splitlines():
        if forbidden.search(line):
            assert prohibition.search(line), f"active external-system instruction: {line!r}"


def test_skill_local_invocation_wires_the_durable_runner_and_returns_a_portable_case() -> None:
    skill = _required_text(SKILL_PATH)
    assert "anomaly.workflow.run_workflow" in skill
    required_calls = (
        "anomaly.prepare.prepare_sources",
        "anomaly.recommend.recommend_detectors",
        "anomaly.recommend.approve_detector_plan",
        "anomaly.detect.execute_detectors",
        "anomaly.review.draft_findings",
        "anomaly.review.replay_signals",
        "anomaly.review.record_review",
        "anomaly.review.accept_findings",
        "anomaly.review.write_report",
    )

    positions = []
    for call in required_calls:
        assert call in skill
        positions.append(skill.index(call))
    assert positions == sorted(positions)
    assert re.search(r"(?i)(?:portable case folder|case folder.*portable)", skill)
    assert re.search(r"(?i)all case (?:paths|references) are relative", skill)


