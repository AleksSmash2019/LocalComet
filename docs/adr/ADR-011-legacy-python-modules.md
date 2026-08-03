# ADR-011: Legacy Python Modules Disposition

Date: 2026-07-27
Status: PROPOSED (requires human approval for deletion)
Context: Level-up audit item 1 (63K lines legacy Python)

## Problem

140 Python files in `modules/` (74,420 lines total). Only 10 are on the
production path (desktop_sidecar_runtime_ru.py transitive deps). The remaining
130 files (63,208 lines) are unreachable from the Svelte/Tauri frontend.

## Classification

| Category | Files | Lines | Action |
|----------|-------|-------|--------|
| PRODUCTION | 10 | 11,212 | KEEP — active sidecar path |
| DEAD | 9 | 4,843 | DELETE — zero references anywhere |
| INTERNAL_DEP | 55 | 27,608 | DELETE CANDIDATES — self-referencing clusters, no external entry point |
| DEV_TOOL | 27 | 13,827 | KEEP — referenced from tools/ and scripts/ |
| NEEDS_HUMAN | 39 | 16,930 | DEFER — wired into old agents/core donor arch |

## DEAD files (safe to delete, 9 files, 4,843 lines)

1. agent_onboarding_demo.py (843 lines)
2. agents_project_intelligence.py (742 lines)
3. codex_agent_mode_ru.py (525 lines)
4. codex_connector.py (860 lines)
5. computer_use_screen_diff_ru.py (57 lines)
6. premium_native_ui_ru.py (740 lines)
7. premium_ui_launcher.py (518 lines)
8. premium_ui_now.py (259 lines)
9. premium_ui_prototype.py (299 lines)

## INTERNAL_DEP clusters (55 files, 27,608 lines)

Largest clusters with no external caller:
- computer_use_* (22 files) — desktop automation, no entry point
- pc_* (10 files) — PC agent framework, no entry point
- ai_agent_* (4 files) — AI agent core, no entry point
- chatgpt_* (2 files) — ChatGPT relay, no entry point

These form closed import graphs. Deleting them requires verifying no
INTERNAL_DEP file is imported by a DEV_TOOL or NEEDS_HUMAN file.

## NEEDS_HUMAN (39 files, 16,930 lines)

Most referenced: files.py (120 refs), project_paths.py (82 refs),
windows.py (41 refs), research.py (31 refs), workspace.py (22 refs).
These are shared utilities used by agents/ and core/ directories.
Decision requires product owner: is the old donor architecture
(agents/, core/) still needed?

## Decision

- DELETE 9 DEAD files immediately (after gate verification)
- KEEP 10 PRODUCTION + 27 DEV_TOOL files
- DEFER 55 INTERNAL_DEP + 39 NEEDS_HUMAN to product owner decision
- Do NOT delete INTERNAL_DEP without verifying cross-references first

## Consequences

- Deleting 9 DEAD files removes 4,843 lines with zero risk
- Full cleanup of INTERNAL_DEP would remove 27,608 more lines but needs
  careful cross-reference analysis
- NEEDS_HUMAN resolution depends on product direction for agents/core
