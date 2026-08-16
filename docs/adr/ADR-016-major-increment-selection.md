# ADR-016: Major increment selection — Workspace/RAG/Memory over Task Center

Status: accepted (execution run-20260815T205414, 2026-08-15)
Spec: LOCALCOMET PRODUCTION EXECUTION SPECIFICATION v3, sections 0.3 / 1.1 (P0-9A vs P0-9B) / 9.D0.

## Decision

The single large product increment for this run is `workspace_memory`
(P0-9B). `task_center` (P0-9A) is deferred.

## Selection rule applied

Per spec 0.3 the increment is chosen by "maximum existing primitives +
minimum blast radius", decided at baseline from read-only exploration.

## Baseline facts (2026-08-15, pre-change)

### task_center primitives
- Python: `task_planner_orchestrator_ru.py` (plan-only, execution hard-disabled in v6.82),
  `autonomy_policy_ru.py`, `autonomous_run_state_ru.py` (RunStatus state machine),
  `autonomous_action_executor_ru.py` — implemented and tested, console-side only.
- Rust (src-tauri): zero task/plan coordinators, zero `task`/`plan` Tauri commands.
- Frontend: zero task UI; dangling `nav.tasks` i18n key referenced by no component.
- Sidecar control plane: no task/plan IPC method; only turn lifecycle
  (`turn.start_mock`, `turn.status`, `turn.cancel`).
- Persistence: none (`AutonomousRunState` in-memory only).

Delivering P0-9A DoD (Plan/Act, pause/resume/cancel, waiting_for_user,
sidecar-restart no-repeat, audit events) would require at least three new
production surfaces: sidecar task methods, Rust task commands, frontend Task
Center — a new subsystem crossing the Rust/Python/TS boundary, i.e.
maximum blast radius and mostly new persistent schemas.

### workspace_memory primitives
- Rust: `knowledge.rs` (turn preview/decide facade, bounded validators),
  `workspace.rs` (workspace identity/digest, symlink-escape rejection,
  approval-token invalidation on workspace change), knowledge review center
  commands, knowledge-model admission binding. Implemented and tested.
- Python: `knowledge_adapter_ru.py` (deterministic lexical index + retrieval
  over Vault notes with section-level provenance), `knowledge_contract_ru.py`,
  `knowledge_injection_ru.py`, `knowledge_change_proposal/review/decision`,
  control-plane knowledge context lifecycle with event contract;
  ~530 tests across tools/test_v68451e4..e9d.
- Frontend: real (non-mock) `knowledge.ts` / `knowledgeReview.ts` bridges,
  `knowledgePreview` store, review center components wired to backend commands.
- Persistence: Vault is env-pointed external markdown store (`LOCALCOMET_KNOWLEDGE_VAULT`),
  read-only by explicit design (`vault_write_authority: false`, `hard_stop: true`).

Delivering the workspace_memory DoD (retrievable indexed document, workspace
isolation, citations tied to real chunks, explicit memory save/delete) reuses
the production-wired Rust/Python/TS chain and adds no Vault write authority;
blast radius is one new sidecar-bound memory registry plus wiring of existing
knowledge surfaces.

## Verdict

`workspace_memory` wins on every selection criterion:

1. More existing production primitives (full Rust-Python-TS knowledge chain).
2. Fewer new persistent schemas (memory registry is bounded, session-scoped,
   no disk authority; no new task-state schema needed).
3. Fewer changed boundaries (no new IPC family; extends existing
   `memory.*`-style dispatch inside the established control plane).
4. Smaller blast radius (read-only knowledge remains read-only; new writes
   are limited to an explicit, user-confirmed, verified-deletable registry).

## Deferred: task_center

Reason: would require a new production subsystem across all three layers
(sidecar task methods + Rust task commands + Task Center UI) with no existing
desktop wiring — maximum blast radius, violates the single-increment rule if
built alongside workspace_memory.

Resume point: `modules/autonomous_run_state_ru.py` RunStatus machine and
`autonomous_action_executor_ru.py` approval-fingerprint executor are the
natural console-side foundation; desktop work starts at sidecar
`CONTROL_PLANE_METHODS` + `lib.rs` handler + a new `src/lib/stores/tasks.ts`.

## Related assumptions

AS-1: `pythoncore-3.11-64` runs gate scripts; `pythoncore-3.14-64` is
`LOCALCOMET_TEST_PYTHON` (per AGENTS.md real-sidecar guidance), avoiding the
venv-shim spawn failure.
AS-2: baseline dirty worktree (70 modified tracked files, 114 untracked
entries) pre-exists this run and is preserved untouched.
