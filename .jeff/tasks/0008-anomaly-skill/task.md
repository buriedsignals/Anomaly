# 0008 — Anomaly skill and data reviewer

## Goal

Ship exactly one installed skill and one independent reviewer that run the linear P0–P7 workflow against the deterministic code from 0002–0007.

## Acceptance criteria

- `skills/anomaly/SKILL.md` is the only installed skill. Source adapters, detector packages, and case folders are not skills.
- `agents/anomaly-data-reviewer.md` is the independent reviewer. It cannot edit drafts or promote findings.
- The skill implements P0–P7 with Gate A and Gate B, durable `.anomaly/` state, bounded retries, and resume from the last completed event.
- The skill does not add Spotlight personas, vaults, evidence cards, or ingest/report machinery.
- The skill does not upload, publish, or write case material to OpenKnowledge, Obsidian, or any other knowledge system.
- A moved case still opens through relative paths. Missing data or missing detector code marks replay unavailable.
- An end-to-end local-file run on Tom's data can produce a portable case folder.

## Non-goals

- M2 user-detector template.
- M3 Navigator source migration.
- M4 GAIN detector ports.
- Extra finishing branches or multimedia production.

## Audit

Skill text must not instruct the agent to execute case-supplied code or to contact subjects.
