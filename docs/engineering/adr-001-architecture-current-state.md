# ADR-001: LocalComet Architecture — Current State Assessment

**Status:** Accepted
**Date:** 2026-07-25
**Author:** OpenCode architectural analysis

## Context

LocalComet / LocalAgent is a local Python agent with a console entry point (`next/app_v5.py`), a Tkinter control panel, and a Tauri/Svelte desktop shell. The codebase has grown organically over multiple build weeks. This ADR records the results of a full architectural audit: dependency analysis, layering violations, god-modules, and pattern compliance.

### Codebase Metrics

| Layer | Files | Lines | Role |
|-------|-------|-------|------|
| `core/` | 7 | 1,087 | Orchestration: router, planner, executor, LLM, state |
| `agents/` | 18 | 1,573 | Thin adapters with `handle(action, data)` |
| `modules/` | 140 | 63,051 | Implementation logic (browser, relay, desktop, knowledge, etc.) |
| `next/` | 5 | 1,862 | v5 console app, goal manager, task planner, queue, observer |
| `desktop/` | — | — | Tauri + Svelte desktop shell (separate runtime) |
| `tools/` | 47 | — | Test scripts, audits, launchers |
| `scripts/` | 2 | — | Utility scripts |
| Root | 3 | ~138 | `app.py` (legacy), `agent.py` (orphan), `config.py` |

## Intended Layering

```
next/app_v5.py  (entry point / CLI)
       │
       ▼
    core/       (orchestration: route → plan → execute)
       │
       ▼
   agents/      (thin adapters: handle(action, data))
       │
       ▼
   modules/     (implementation logic)
       │
       ▼
   config.py    (configuration constants)
```

Dependencies should flow **downward only**. Each layer should depend only on the layer directly below it.

## Findings

### 1. Circular Dependency: core ↔ modules (CRITICAL)

The intended layering is violated bidirectionally:

**core → modules** (4 files):
- `core/planner.py` → `modules.browser_direct`, `modules.natural_command_intents`
- `core/router.py` → `modules.natural_command_intents`
- `core/state.py` → `modules.project_paths`
- `core/executor.py` → `modules.browser_profile_ignore` (conditional)

**modules → core** (76 import sites across ~45 files):
- 40+ files import `core.state` (get_value, set_value)
- 6 files import `core.llm` (ask_llm)
- 3 files import `core.router` + `core.planner` + `core.executor` (full orchestration loop):
  - `modules/stability_test.py` (20 import sites)
  - `modules/automation_center.py` (3 import sites)
  - `modules/regression_commands.py` (3 import sites)

This creates a **circular dependency** between the orchestration layer and the implementation layer. The three modules that re-import the full route→plan→execute pipeline are effectively embedding a second orchestration loop inside `modules/`, bypassing the intended architecture.

### 2. God-Object: next/app_v5.py (HIGH)

`next/app_v5.py` is **2,039 lines**. Approximately 1,600 lines are a command-dispatch chain spread across 12 `_run_direct_*` functions:

- `_run_direct_automation_command()`
- `_run_direct_gpt_browser_command()`
- `_run_direct_chatgpt_relay_command()`
- `_run_direct_gpt_command()`
- `_run_direct_self_edit_command()`
- `_run_direct_maintenance_command()`
- `_run_direct_history_command()`
- `_run_direct_diagnostics_command()`
- `_run_direct_voice_command()`
- `_run_direct_notepad_command()`
- `_run_direct_workspace_command()`
- `_run_direct_browser_action_command()`

Additionally, a `SHORTCUTS` dict with 120+ entries duplicates routing logic that belongs in `core/router`. Every new command requires editing this file. There is no separation between CLI parsing and business logic.

### 3. God-Modules in modules/ (HIGH)

Top 10 largest files in `modules/`:

| File | Lines | Concern |
|------|-------|---------|
| `premium_task_panel_ru.py` | 2,957 | UI panel + LLM calls + state |
| `desktop_control_plane_ru.py` | 2,208 | Desktop control + IPC + state |
| `computer_use_contract_tests_ru.py` | 1,818 | Tests mixed with implementation |
| `local_model_gateway_ru.py` | 1,811 | Model routing + provider abstraction |
| `stability_test.py` | 1,664 | Test harness embedding full orchestration |
| `knowledge_change_review_ru.py` | 1,488 | Review workflow + UI + state |
| `localcomet_functional_test_center_ru.py` | 1,344 | Test center + execution |
| `knowledge_review_ui_projection_ru.py` | 1,291 | UI projection + review logic |
| `computer_use_full_control_mission_ru.py` | 1,117 | Mission control + action planning |
| `computer_use_multistep_loop_ru.py` | 979 | Multi-step execution loop |

Files exceeding ~500 lines likely violate the Single Responsibility Principle. The top 5 files alone account for 10,458 lines (16.6% of all module code).

### 4. Agents Importing core.state Directly (MEDIUM)

5 of 18 agents bypass the adapter pattern by importing `core.state` directly:

- `agents/browser_agent.py`
- `agents/code_agent.py`
- `agents/project_agent.py`
- `agents/system_agent.py`
- `agents/windows_agent.py`

All 5 import `get_value`/`set_value` for persisting last-action metadata. This couples the adapter layer to the orchestration layer's state management.

### 5. Orphan and Legacy Code (MEDIUM)

- **`agent.py`** (96 lines): Fully disconnected prototype. Hardcodes its own LLM URL and model (`google/gemma-4-e4b` vs `config.py`'s `qwen3-14b`). Contains a **command injection risk** in `search_web()` via unsanitized `subprocess.Popen(..., shell=True)`.
- **`app.py`** (37 lines): Legacy v3 entry point. Duplicates the route→plan→execute pipeline from `app_v5.py` without shortcuts, state, or logging.

### 6. Inconsistent Error Handling (LOW)

- `next/goal_manager.py` and `next/task_planner.py` handle LLM offline errors via `is_llm_offline_error()` / `format_llm_offline_message()`.
- `next/observer.py` does not handle LLM offline errors at all.

### 7. Dead Data (LOW)

- `next/goal_manager.py` extracts `success_criteria` from LLM analysis, but `app_v5.py` never consumes it downstream.

## Pattern Compliance

| Pattern | Status | Notes |
|---------|--------|-------|
| Agent adapter (`handle(action, data)`) | **18/18 compliant** | All agents follow the pattern |
| Route → Plan → Execute pipeline | **Compliant in core/** | `loop.py` chains correctly |
| Thin agents delegating to modules | **13/18 compliant** | 5 agents also import `core.state` |
| One-way dependency flow | **Violated** | Circular core ↔ modules |
| Single Responsibility | **Violated** | 10+ god-modules, 1 god-object |
| Configuration centralization | **Partially violated** | `agent.py` hardcodes config |
| No agents importing agents | **Compliant** | 0 cross-agent imports |

## Dependency Graph Summary

```
next/app_v5.py ──→ core/{router,planner,executor,state}
       │                    │
       │                    ├──→ agents/* (18 agents, via executor)
       │                    │         │
       │                    │         ├──→ modules/* (implementation)
       │                    │         │         │
       │                    │         │         └──→ core.state  ← CIRCULAR
       │                    │         │         └──→ core.llm    ← CIRCULAR
       │                    │         │         └──→ core.router ← CIRCULAR (3 files)
       │                    │         │
       │                    │         └──→ core.state (5 agents) ← VIOLATION
       │                    │
       │                    └──→ modules/* (4 core files) ← VIOLATION
       │
       └──→ modules/{history_log,browser_direct,voice_control}
```

## Recommendations

### Priority 1: Break the core ↔ modules cycle
- Extract `core.state` into a standalone `state/` package or a shared `common/` layer that both `core/` and `modules/` can import without circularity.
- Move `modules.project_paths` and `modules.natural_command_intents` into `core/` or a shared layer, since `core/` depends on them.
- Remove `core.router`/`core.planner`/`core.executor` imports from `modules/stability_test.py`, `modules/automation_center.py`, and `modules/regression_commands.py`. These should receive orchestration callbacks via injection rather than importing the orchestrator.

### Priority 2: Decompose app_v5.py
- Replace the 12 `_run_direct_*` functions with a command registry (dict or decorator-based) in `core/router` or a new `core/commands.py`.
- Move the `SHORTCUTS` dict into `core/router`.
- Separate CLI parsing (REPL loop) from command dispatch.

### Priority 3: Split god-modules
- `premium_task_panel_ru.py` (2,957 lines): separate UI rendering from LLM logic and state management.
- `desktop_control_plane_ru.py` (2,208 lines): separate IPC contract handling from control logic.
- `stability_test.py` (1,664 lines): move to `tools/` or `tests/` and inject orchestration dependencies.

### Priority 4: Clean up orphans
- Remove or refactor `agent.py` (security risk, dead code).
- Mark `app.py` as deprecated or remove it.

### Priority 5: Standardize state access in agents
- Provide a `modules/state_store.py` facade so agents never import `core.state` directly.

## Consequences

- The circular dependency makes it impossible to test `core/` or `modules/` in isolation.
- The god-object `app_v5.py` is the single highest-churn file and a merge-conflict hotspot.
- God-modules increase cognitive load and make targeted edits risky.
- The agent adapter pattern is well-followed and should be preserved.
- The route→plan→execute pipeline in `core/` is clean and should remain the canonical orchestration path.
