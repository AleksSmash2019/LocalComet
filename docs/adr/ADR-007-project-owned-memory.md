# ADR-007: Project-Owned Memory

Date: 2026-07-15
Status: ACCEPTED
Canonical text: LocalComet Vault, «03 Решения/ADR-007 Память принадлежит проекту» (id: adr.007.project-owned-memory)

## Problem

Agent memory that belongs to a single model or agent vendor makes the
project's knowledge hostage and lets model output silently rewrite what the
project knows.

## Decision

Memory belongs to the PROJECT, not to any agent: the knowledge store
(Markdown/Obsidian Vault) is agent-independent and usable by LocalComet,
Codex, OpenCode and future compatible agents. First runtime connection is
read-only. The write path is

Verified Project Change → Proposed Knowledge Update → Diff → Approval → Vault Update.

The path «Model Opinion → Silent Memory Rewrite» is forbidden.

## Consequences

- AGENTS.md запрещает тихую перезапись памяти мнением модели, ссылаясь на этот ADR.
- Knowledge review pipeline (e9b/e9c) реализует именно этот путь записи.
- Полный текст решения и история — в каноническом источнике (Vault).
