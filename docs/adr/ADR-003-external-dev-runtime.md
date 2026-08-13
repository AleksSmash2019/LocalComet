# ADR-003: External DevRuntime Workspace

Date: 2026-07-15
Status: ACCEPTED
Canonical text: LocalComet Vault, «03 Решения/ADR-003 Внешнее рабочее пространство DevRuntime» (id: adr.003.external-devruntime)

## Problem

Development runs of the desktop app must not write runtime state, model
caches, or test artifacts into the repository checkout: dirty trees break
evidence provenance and gate digests, and runtime payloads do not belong in
git.

## Decision

The development runtime lives OUTSIDE the repository at
`%LOCALAPPDATA%\LocalComet\DevRuntime` (see `tools/launch_localcomet_dev.py`).
The repository tree stays source-only; anything generated at runtime goes to
the external workspace.

## Consequences

- AGENTS.md и launcher-документы ссылаются на этот ADR как на authority.
- Гейты чистоты дерева (staged/untracked проверки) полагаются на внешнее
  расположение DevRuntime.
- Полный текст решения и история — в каноническом источнике (Vault).
