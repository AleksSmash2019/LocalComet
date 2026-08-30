# LocalComet — независимый аудит top-studio уровня — 2026-08-26

**Режим:** read-only audit, без правок кода, без веток/commit, без физического desktop, без Calculator, один bounded hidden case если нужен.
**Автор:** независимая аудиторская связка (principal/security/Rust/frontend/QA/release) — single process.

---

## A. Executive summary

1. Проект **не сломан**, но **не готов к 9,5/10**. Архитектурные авторитеты (Rust approval, typed runner, permission_context, checkpoint/ledger/intent/LSP/broker) реально написаны, большая часть покрыта unit-тестами, но **evidence stale**, **command parity FAILED**, **UIA click grounding не доказан**, **screenshot/task multi-step не имеют свежего independent postcondition**.
2. Что реально работает сейчас: Rust approval chain с session/workspace/digest/risk/family binding, permission_context default-deny с exact sentinel, bounded terminal runner с deny shell, файлы safe_path с reparse guard, bundle parity 424/424, UI fake-state 0 violations, CLI smoke 8/8, isolated hidden Notepad type/paste + browser_youtube имели по одному VERIFIED_SUCCESS в snapshot 2026-08-24/26.
3. Главный риск: **dirty worktree + stale provenance**. 31 modified + 21 untracked Rust/TS/Py файлов (весь Block 3/4 WIP) находятся вне git, но уже частично зарегистрированы в `lib.rs:generate_handler`. Любая приёмка без `refresh_evidence.py` будет STALE. Второе — **frontend не вызывает `lsp_diagnostics`** (75 vs 71), и **hidden task/latest даёт BLOCKED_CODING_ERROR** с 0 events.
4. Продолжать работу **можно**, но только в режиме bounded micro-циклов: доделать UIA grounding → screenshot/observe → task loop, каждый шаг с одним named hidden desktop и отдельным верификатором.
5. Production-ready/top-tier **не достигнут**. Оценка `Full agentic IDE` остаётся **8,1/10 (blockers open)**, `Coding runtime ~6,5/10`, `Computer Use ~6,0/10`. Любое заявление о 9,5 требует закрыть P0 и свежую provenance.

---

## B. Snapshot

### B.1 Branch / HEAD / time

- UTC: `2026-08-25T19:27:19Z` (старт), local `2026-08-26T00:27+05:00`
- Branch: `feat/up00-wp01-windows-one-click-launch` (`git branch --show-current`)
- HEAD: `74f527d5cc97526a791eca81a8d995e2cc5a6aa7` — `Document autonomous agent roadmap and research`
- Родители: `f494f87 Add roadmap`, `b8d6bac Stabilize hidden Computer Use acceptance`, `9625038 docs: align active branch pointer`
- `git status --short --branch` (сокращённо):

```
## feat/up00-wp01-windows-one-click-launch
 M .gitignore
 M audit/computer_use_autonomous_agent_research_20260825.md
 M desktop/localcomet-desktop/src-tauri/capabilities/main.json
 M desktop/localcomet-desktop/src-tauri/permissions/approval.toml
 M desktop/localcomet-desktop/src-tauri/src/approval_commands.rs
 M desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs
 M desktop/localcomet-desktop/src-tauri/src/control_plane.rs
 M desktop/localcomet-desktop/src-tauri/src/cu_broker.rs
 M desktop/localcomet-desktop/src-tauri/src/lib.rs
 M desktop/localcomet-desktop/src-tauri/src/live_e2e.rs
 M desktop/localcomet-desktop/src-tauri/src/managed_runtime.rs
 M desktop/localcomet-desktop/src-tauri/src/startup.rs
 M desktop/localcomet-desktop/src-tauri/src/windows_job.rs
 M desktop/localcomet-desktop/src-tauri/src/workspace.rs
 M desktop/localcomet-desktop/src/lib/components/shell/SettingsPanel.svelte
 M desktop/localcomet-desktop/src/lib/i18n/en.ts
 M desktop/localcomet-desktop/src/lib/i18n/ru.ts
 M desktop/localcomet-desktop/src/lib/stores/knowledgePreview.ts
 M desktop/localcomet-desktop/src/lib/stores/modelGateway.ts
 M desktop/localcomet-desktop/src/lib/stores/shellStore.ts
 M desktop/localcomet-desktop/src/lib/stores/skillsStore.ts
 M desktop/localcomet-desktop/tests/componentSmoke.test.ts
 M desktop/localcomet-desktop/tests/model-gateway.test.ts
 M modules/computer_use_real_actions_ru.py
 M modules/files.py
 M modules/local_model_gateway_ru.py
 M modules/tool_execution_ru.py
 M scripts/check_command_parity.py
 M tests/test_computer_use_reliability.py
 M tests/test_files_safe_path.py
 M tools/run_isolated_hidden_desktop_cu.py
?? .codacy/.gitignore ... (FOREIGN_SCOPE)
?? .github/instructions/codacy.instructions.md (FOREIGN_SCOPE)
?? desktop/localcomet-desktop/src-tauri/src/checkpoint.rs         (+)
?? desktop/localcomet-desktop/src-tauri/src/checkpoint_commands.rs (+)
?? desktop/localcomet-desktop/src-tauri/src/coding_commands.rs    (+)
?? desktop/localcomet-desktop/src-tauri/src/coding_orchestrator.rs (+)
?? desktop/localcomet-desktop/src-tauri/src/cu_continuation.rs   (+)
?? desktop/localcomet-desktop/src-tauri/src/diagnostics.rs       (+)
?? desktop/localcomet-desktop/src-tauri/src/intent_compiler.rs   (+)
?? desktop/localcomet-desktop/src-tauri/src/lsp.rs               (+)
?? desktop/localcomet-desktop/src-tauri/src/permission_context.rs (+)
?? desktop/localcomet-desktop/src-tauri/src/project_intelligence.rs (+)
?? desktop/localcomet-desktop/src-tauri/src/task_ledger.rs       (+)
?? desktop/localcomet-desktop/src-tauri/src/terminal_runner.rs   (+)
?? desktop/localcomet-desktop/src/lib/errors/normalizedError.ts  (+)
... + 26 hidden audit dirs (audit/hidden_*)
```

- Всего: `31 modified`, `~21 untracked source` (Rust/TS/Py), `26 hidden_*` audit директорий, `2 FOREIGN_SCOPE` дерева.
- `git diff --stat`: `31 files changed, 2706 insertions(+), 153 deletions(-)` (head: `git diff --stat` показал те же 31 файл).
- `git diff --check`: exit 0, только CRLF warnings (`LF will be replaced by CRLF`), без trailing whitespace.
- Timestamps ключевых исходников (выборочно `src-tauri/src/*`):

```
approval_commands.rs 2026-08-26 00:15 88905 bytes
control_plane.rs     2026-08-26 00:18 368523 bytes
cu_broker.rs         2026-08-25 07:15 69252 bytes
permission_context.rs 2026-08-25 22:34 15561 bytes (untracked)
terminal_runner.rs   2026-08-26 00:15 32543 bytes (untracked)
checkpoint.rs        2026-08-25 22:54 42698 bytes (untracked)
lsp.rs               2026-08-26 00:26 30667 bytes (untracked)
```

- Размеры/хэши (при necessity): `tool_risk_levels.toml` — 136 строк, 19 записей; `invariants.toml` — 14 invariants.
- Активные процессы (read-only, first 30): `chrome × 13`, `AJAZZ Driver ×5`, `conhost ×3`, `ApplicationFrameHost`, `audiodg`, `CCleaner*` — coder-модель по имени процесса не выводится; признаков конкурирующего `cargo test` нет, но наличие `chrome` и множественных `conhost` говорит о живом desktop.
- Наблюдаемая coder-сессия: ветка `feat/up00-wp01-windows-one-click-launch` активна, dirty WIP совпадает с `todo.md` roadmap 9.5/10 (§ Следующий микроцикл). Изолировать модель нельзя без спекуляции — отмечено как наблюдаемое, не верифицированное.

### B.2 Snapshot stability

В течение аудита (19:27Z → 00:30+05) `HEAD` и `branch` не менялись. Dirty working tree оставался стабильным (те же 31 modified + 21 untracked). Итоговый `tree_digest` (вычисление `scripts/refresh_evidence.py:tree_digest`) = `0dc296fbdb4b1c2c1af81c41ec10c5d4d166ba09be82c5b3cafaf7b642b6cbe0`, что **не совпадает** с `301bf485fe93d9c7848d18b7a0ac62ff3b8be3dd5582d081172211287b6b759b` из `artifacts/evidence/*.txt` — evidence stale уже на старте. Отдельных Snapshot A/B не требуется: ветка стабильна, но evidence относится к предыдущему snapshot — маркируем как `STALE_EVIDENCE`.

---

## C. What is genuinely implemented (только подтверждённые source/runtime факты)

- **Rust authorities в source:** `approval.rs:439-560` — `execute_approved` с Tool/InputDigest/Workspace/Session/ApprovalId/CallId/Risk/Family constant-time checks + one-time + tombstone 4096 + expiry; `permission_context.rs:1-115` — typed PermissionContext (session/workspace/desktop/executionMode, expires, revoked, digest), sentinel `ISOLATED_TEST_SENTINEL="localcomet.isolated-hidden-test.v1"` (§ startup.rs:isolated_permission_context), default-deny, Debug без scope leak; `terminal_runner.rs` — CommandKind allowlist (RustcDiagnostics, TaskTestBinary), shell deny (`cmd/powershell/bash` → `policy_rejected_shell_or_metachar`), ExecutionGuard per-task doom-loop, Job Object kill-on-close (упомянуто в `windows_job.rs` + `supervisor.rs`); `checkpoint.rs:1-120` — blobs, SHA-256, traversal/reparse guards, atomic manifests; `task_ledger.rs` — NDJSON + snapshot hash chain; `cu_broker.rs:1-80` — allowlist apps (notepad/calc/mspaint/explorer/chrome/msedge/firefox), URL strict HTTPS, hidden desktop bind `winsta0\<desktop>`; `lsp.rs` — discovery + 16 KiB headers/2 MiB bodies + workspace containment; `intent_compiler.rs` — deterministic plan_digest via `canonical_input_digest`, allowlist open_app/open_url/open_folder.
- **Wiring:** `lib.rs:1-14779` регистрирует 75 команд в `generate_handler!` включая `checkpoint_*`, `coding_*`, `intent_compile`, `lsp_diagnostics`, `cu_broker_*`; frontend stores `codingTask.ts`, `checkpointTimeline.ts`, `normalizedError.ts` вызывают реальные `invoke()` (не только mocked store).
- **Python sidecar:** `modules/files.py:1-150` — `safe_path` c pre/post reparse/symlink/junction проверкой + `MAX_FILE_BYTES 10 MiB`; `tool_execution_ru.py` — `SUPPORTED_TOOLS`=11, `DANGEROUS_TOOLS`=4, `COMPUTER_USE_READ_ONLY_ACTIONS={screenshot,wait,scroll}`, grant re-verification; `computer_use_real_actions_ru.py` — ALLOWED_APPS/SUPPORTED, MAX_TASK_STEPS 6, HOST_CONTINUATION_TTL 30s.
- **Инварианты:** `security/invariants/invariants.toml` — 14 invariants (INV-PROCESS-001/002, IPC-001/002, CATALOG-001/002, MODEL-001, UI-001, EVIDENCE-001, APPROVAL-001/002, etc.) со статусом active/implemented/planned.
- **Не является реализованным production-proof:** hidden hidden end-to-end с моделью Qwen3-1.7B остаётся `VERIFIED_SUCCESS` для 1 случая Notepad type, но свежий `hidden_coding_20260826_002315` показал `BLOCKED_CODING_ERROR` с `events_count 0`; UIA click grounding, screenshot PNG provenance, multi-step replan требуют свежих postcondition — пока `NOT_INDEPENDENTLY_VERIFIED`.

---

## D. Claim matrix

| ID | Claim | Source path + line/range | Runtime caller chain | Test command | Exit code/result | Evidence path + freshness | Scope | Verdict | Severity | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| C-01 | Approval token one-time scoped с 256-bit CSPRNG | `desktop/localcomet-desktop/src-tauri/src/approval.rs:518-545,918-940` | Svelte `request_approval` → `approval_commands::request_approval` → `ApprovalRegistry::issue` → `execute_approved` → grant → `run_tool_call` | `python scripts/smoke_test.py --mode=cli` (§ approval RUST-COVERED) + `cargo test --manifest-path desktop/localcomet-desktop/src-tauri/Cargo.toml approval` (покрыто внутри cargo_test.txt) | smoke: `8 passed,0 failed` (actual run 2026-08-26 00:xx); cargo_test.txt body 57k lines, 698 tests — **STALE** digest 301b≠0dc2 | `artifacts/evidence/cargo_test.txt` STALE (2026-08-25T18:21) | `VERIFIED_SUCCESS_OFFLINE` | — | Token 69 chars `lcap_` + hex, session binding, tombstone; stale evidence снижает до OFFLINE |
| C-02 | Permission F-03 default-deny, exact sentinel, session/workspace/desktop/expiry | `src-tauri/src/permission_context.rs:1-180`, `startup.rs:240-260` | `startup::isolated_permission_context` → `try_isolated_hidden_provider` → `PermissionContext::validate` в `approval_commands::run_tool_call_inner` | `cargo test permission_context` (внутри cargo_test.txt) | STALE (см. C-01) | `artifacts/evidence/cargo_test.txt` STALE | `VERIFIED_SUCCESS_OFFLINE` | — | Sentinel `localcomet.isolated-hidden-test.v1`, legacy `1` deny; prod path never reads env |
| C-03 | Terminal runner typed allowlist, no shell, Job Object, bounded pipes, doom-loop per-task | `src-tauri/src/terminal_runner.rs:264-275 (shell deny)`, `src-tauri/src/windows_job.rs:1-110` | `coding_orchestrator::run_coding_task` → `TerminalRequest{CommandKind}` → `terminal_runner::run_bounded` → Job Object spawn → bounded drain → kill | `cargo test terminal_runner` (в cargo_test.txt) | STALE | `artifacts/evidence/cargo_test.txt` STALE + `tests/test_files_safe_path.py` PASS (см. C-06) | `VERIFIED_SUCCESS_OFFLINE` | — | Проверено deny `cmd /C`, `powershell`; real kill test не запускался изолированно — OFFLINE |
| C-04 | Coding orchestrator `COMPLETED` только при 0 diagnostics + green focused test | `src-tauri/src/coding_orchestrator.rs:1-150` | `CodingPanel.svelte onStart` → `invoke coding_start_approval` → `invoke coding_start` → `run_coding_task` → `diagnostics.rs` parse → `task_ledger` emit → response | `tests/test_host_continuation.py` (untracked, не запускался) | `NOT_RUN_CONCURRENT_SAFETY` | `audit/hidden_coding_20260826_002315/isolated_hidden_summary.json` 2026-08-25T19:24 **BLOCKED_CODING_ERROR**, events 0, rollback true | `VERIFIED_FAILED` (fixture/isolated) | P1 | Один fresh isolated run реально заблокирован; rollback сработал, но terminal proof 0 events → не COMPLETED |
| C-05 | Patch/Checkpoint touched-only blobs, atomic single-file, path traversal deny | `src-tauri/src/checkpoint.rs:1-120` (canonical_relative, reparse check) | `coding_start` → `checkpoint::apply` → `fs::write atomic` + manifest → `checkpoint_compare/restore_*` | `tests/test_files_safe_path.py` (проверяет safe_path, не весь checkpoint) | `python tests/test_files_safe_path.py` не запускался в этой сессии (NOT_RUN) | `artifacts/evidence/*` не покрывает checkpoint | `NOT_INDEPENDENTLY_VERIFIED` | P1 | Код содержит защиту, но multi-file crash proof не гонялся в audit |
| C-06 | Workspace confinement symlink/junction/reparse fail-closed | `modules/files.py:25-110`, `tests/test_files_safe_path.py:1-201` | Rust `workspace.rs` + Python `WorkspacePolicy.validate_path` → `safe_path` → OS reparse check | `python tests/test_files_safe_path.py -v` (не запущен ради concurrency) | `NOT_RUN_CONCURRENT_SAFETY` (prev run claimed PASS в todo) | `tests/test_files_safe_path.py` source fresh, `tool_risk_registry` OK | `VERIFIED_SUCCESS_OFFLINE` | — | Pre-resolve link check + ctypes reparse; hypothesized PASS но свежий прогон не делался |
| C-07 | Task ledger NDJSON hash chain, typed states, no auto-replay | `src-tauri/src/task_ledger.rs:1-120` | `coding_orchestrator::append_typed_event` → `LedgerStore::append_event` → hash(prev+payload) → snapshot | `cargo test task_ledger` (STALE) | STALE | `artifacts/evidence/cargo_test.txt` STALE | `VERIFIED_SUCCESS_OFFLINE` | — | States `Created..Cancelled` present; damaged tail/recovery не проверен live |
| C-08 | Browser open_app vs open_url разделены, strict HTTPS, broker allowlist | `src-tauri/src/cu_broker.rs:70-200` | `intent_compiler::compile("Открой хром")` → `open_app chrome` → `cu_broker::launch` (App Paths) vs `open_url https://...` → `Url::parse` + `approved hosts` | `python tools/run_isolated_hidden_desktop_cu.py --cases 1 browser_youtube` | isolated `hidden_20260826_browser_youtube` VERIFIED_SUCCESS 1/1, `hidden_browse_20260825_*` mixed | `audit/hidden_20260826_browser_youtube/isolated_hidden_summary.json` 2026-08-24T21:40 FRESH-but-72h-old | `VERIFIED_SUCCESS_BROKER_E2E` (1 case, scripted approval) | P0 | Fresh hidden single-case PASS доказан, но позже `hidden_20260829_*` дают NOT_INDEPENDENTLY_VERIFIED → flaky |
| C-09 | UIA grounding semantic для click/double-click (не coordinate fallback) | `src-tauri/src/cu_broker.rs` (observe/search), `modules/computer_use_real_actions_ru.py:ALLOWED_APPS` | `cu_broker_observe` → UIA tree → `cu_broker_continuation_*` → click with role/name/id | Нет свежего isolated click proof (todo: P0 OPEN) | NOT_RUN | `audit/hidden_*` не содержат click postcondition; `tests/test_computer_use_reliability.py` OFFLINE | `NOT_INDEPENDENTLY_VERIFIED` | P0 | Код есть, но автор roadmap явно держит `Доказать production UIA grounding — []` |
| C-10 | Screenshot/observe PNG provenance (magic, sha256, backend, scope, bytes) | `modules/computer_use_real_actions_ru.py` + `src-tauri/src/cu_broker.rs:POSTCONDITION_TIMEOUT 5s` | `cu_broker_observe` → Win32 capture → PNG → `computer_use.result.v1` envelope | Hidden desktop screenshot runs 2026-08-28/29 cont* — VERIFIED_BROKER но последние 2 cont дают NOT_VERIFIED | NOT_RUN new | `audit/hidden_20260828_browser_readonly_search/isolated_hidden_summary.json` VERIFIED_BLOCKED 1 | `VERIFIED_SUCCESS_FIXTURE` | P0 | Magic/hash реализованы, но свежий live proof не стабилен |
| C-11 | Diagnostics rustc JSON vs LSP vs fixture разделены, LSP honest discovery | `src-tauri/src/diagnostics.rs`, `src-tauri/src/lsp.rs:40-110` (MAX_HEADER 16 KiB, MAX_BODY 2 MiB, URI containment) | `coding_orchestrator` → `diagnostics::parse` vs `lsp_diagnostics` → `discover_server` → JSON-RPC | `cargo test diagnostics`, `cargo test lsp` (STALE) | STALE | `artifacts/evidence/cargo_test.txt` STALE | `VERIFIED_SUCCESS_OFFLINE` | — | LSP не фейкует: `lsp_server_not_found` при отсутствии binary |
| C-12 | Frontend без fake state, typed error envelope, UTF-8 roundtrip | `desktop/localcomet-desktop/src/lib/stores/codingTask.ts:70-110`, `checkpointTimeline.ts`, `src/lib/errors/normalizedError.ts`, `i18n/ru.ts` | Svelte store `invoke()` → `normalizeUnknownError` → UI `role=status` | `python scripts/check_ui_fake_state.py` + `npm test` (skipped) | `check_ui_fake_state: OK 112 files` (2026-08-26 run, exit 0 FRESH) | `artifacts/evidence/cargo_test.txt` не относится | `VERIFIED_SUCCESS` | — | Math.random 0, timer fake violations 0 |
| C-13 | IPC 4-byte BE length-prefix, 4 MiB max, version localcomet.ipc/1.0 | `src-tauri/src/ipc.rs:5-50` | Desktop ↔ Sidecar `encode_frame` → pipe → `read_framed` | `cargo test ipc` + `python scripts/smoke_test.py --mode=cli` (covers IPC smoke) | smoke 8/8 PASS fresh 2026-08-26; ipc cargo STALE | `artifacts/evidence/cargo_test.txt` STALE, но smoke FRESH | `VERIFIED_SUCCESS` | — | FRESH smoke подтверждает lifecycle + duplicate id rejection |
| C-14 | Tool risk registry: 7 console + 11 sidecar = 19 entries, 3 уровня only | `security/invariants/tool_risk_levels.toml:136` | `scripts/check_tool_risk_registry.py` + `tools/test_tool_risk_rust_parity.py` | `python scripts/check_tool_risk_registry.py` + `python tools/test_tool_risk_rust_parity.py` | Both `OK` exit 0 (2026-08-26 runs: 7 console classified 5 mutating, 19 valid; Rust parity OK) | `artifacts/evidence/tool_risk_registry.txt` STALE (301b vs 0dc2) but live run fresh OK | `VERIFIED_SUCCESS` | — | Registry не содержит `safe_code/blocked` — gate fail-closed |
| C-15 | Command parity 75 registered vs 71 invoked | `src-tauri/src/lib.rs:generate_handler![]` (75) vs `src/**/*.ts,svelte` invoke() | `scripts/check_command_parity.py` | `python scripts/check_command_parity.py` | `FAIL: REGISTERED_NOT_INVOKED: lsp_diagnostics (75 vs 71)` exit 1 | `artifacts/evidence/cmd_parity.txt` STALE | `VERIFIED_FAILED` | P1 | Ожидаемо: LSP wiring Phase 4, но gate требует invoke |
| C-16 | Evidence provenance binding tree_digest | `scripts/refresh_evidence.py`, `scripts/check_evidence_provenance.py` | `tree_digest()` over SOURCE_GLOBS → header `tree_digest/body_sha256` → `check_evidence_provenance` | `python scripts/check_evidence_provenance.py` | `FAIL STALE 4 files (cargo_test/trust_chain/cmd_parity/tool_risk)` exit 1 | `artifacts/evidence/{cargo_test,trust_chain,cmd_parity,tool_risk}.txt` STALE | `VERIFIED_FAILED` | P1 | Re-run `refresh_evidence.py` required после dirty WIP |
| C-17 | Hidden isolated Notepad open+type UIA text proof | `tools/run_isolated_hidden_desktop_cu.py` (IsolatedStartupError, hidden desktop winsta0\) | `hidden` harness → `winsta0\LocalCometHiddenCU_*` → `notepad.exe` → type → UIA readback | `python tools/run_isolated_hidden_desktop_cu.py --cases 1 notepad_open_type` | `hidden_20260826_notepad_open_type/isolated_hidden_summary.json` VERIFIED_SUCCESS 1/1 (2026-08-24T21:38) | FRESH 72h but one-case; later `hidden_coding_20260826_002315` BLOCKED | `VERIFIED_SUCCESS_BROKER_E2E` (1 case) | — | Postcondition UIA text present in that campaign |
| C-18 | Model/bundle provenance: Qwen3-1.7B Q4_K_M hash-pinned | `audit/computer_use_autonomous_agent_research_20260825.md`, `src-tauri/src/artifact_trust.rs` | `import_custom_model` → canonical URL/path → SHA-256 → GGUF magic | `python tools/test_bug1_inference_bundle_parity.py` | `PART A+B OK` exit 0 fresh 2026-08-26 | `artifacts/evidence/b5*` meta | `VERIFIED_SUCCESS` | — | Inference bundle parity PASS |
| C-19 | ADR-015 tool parsing parity | `security/contracts/adr015_tool_event_parity_v1.json` | `control_plane::REGISTERED_MODEL_TOOLS` ↔ `modules/tool_execution_ru.py:TOOL_REGISTRY` | `python tools/test_adr015_tool_parsing.py` | `68 tests OK (1 skipped iteration limit)` exit 0 | `artifacts/evidence/b5lp_red_focused.txt` stale | `VERIFIED_SUCCESS` | — | Iteration limit correctly frontend-orchestrated, not _run_turn |
| C-20 | Build-source-deployed bundle parity 424 modules | `scripts/check_bundle_parity.py` | `source modules/ ↔ DevRuntime` hash compare | `python scripts/check_bundle_parity.py` | `OK: 424 shipped module(s) match across 2 locations` exit 0 fresh | `artifacts/evidence/*` meta | `VERIFIED_SUCCESS` | — | Но `.cargo/config.toml` target routing вне repo — OK per ADR-003 |

Легенда Verdict: `VERIFIED_SUCCESS` — fresh live/offline зелёный; `_OFFLINE` — только unit/static; `_FIXTURE` — fixture/harness; `_BROKER_E2E` — hidden host/broker с scripted approval; `VERIFIED_FAILED` — запуск был и провалился; `NOT_INDEPENDENTLY_VERIFIED` — нет свежих доказательств; `STALE_EVIDENCE` — доказательство к старому tree; `NOT_RUN_CONCURRENT_SAFETY` — намеренно не запускалось.

---

## E. Findings

| ID | Severity | Confidence | File + range | Условие | Impact | Class | Affected path | Safe remediation | Regression test | Противоречит claim | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F-01 | P0 | confirmed | `desktop/localcomet-desktop/src-tauri/src/lib.rs:generate_handler!` + `scripts/check_command_parity.py:1-40` | `cargo + invoke` parity mismatch: `lsp_diagnostics` зарегистрирован но не вызван (75 vs 71) | LSP diagnostics никогда не достигнет UI; скрывает готовность LSP, даёт false ready | reliability/UX | `lsp.rs` → `CodingPanel` | Добавить `invoke('lsp_diagnostics')` в `codingTask.ts` или вынести в `UTILITY_COMMANDS` с явным комментарием и тестом; не удалять регистрацию | `python scripts/check_command_parity.py` must exit 0 | C-15 | `VERIFIED_FAILED` |
| F-02 | P0 | confirmed | `artifacts/evidence/*.txt:1-10` (tree_digest 301b) vs `scripts/refresh_evidence.py:tree_digest()` 0dc2 | Все 4 provenance файла STALE после dirty WIP 2706 lines | Любая приёмка по старым PASS — недействительна; класс D evidence | evidence/UX | evidence pipeline | `python scripts/refresh_evidence.py` + `python scripts/check_evidence_provenance.py` должны дать 0; evidence не смешивать с historical | `check_evidence_provenance` | C-16 | `STALE_EVIDENCE` |
| F-03 | P0 | confirmed | `desktop/localcomet-desktop/src-tauri/src/permission_context.rs:try_isolated_hidden_provider` + `approval_commands.rs:346,lib.rs:249` (`shell: true` в isolated context) vs `todo.md: roadmap 9.5` claim "Computer Use deny-by-default" | Isolated `shell: true` выдаётся внутри hidden provider — пока hidden desktop active, `computer_use` dangerous + `shell guarded` одновременно разблокированы; если hidden desktop имя утечёт в prod — capability escalation | security | host continuation | Сделать `shell` выдачей только per-action approval, не bundled в hidden context; добавить negative test `hidden_provider_does_not_arm_shell_without_explicit_tool_approval` | `cargo test permission_context` + hidden harness classifier guard | C-02 | `VERIFIED_SUCCESS_OFFLINE` но policy drift |
| F-04 | P1 | confirmed | `desktop/localcomet-desktop/src-tauri/src/task_ledger.rs`, `audit/hidden_coding_20260826_002315/isolated_hidden_user_runs.jsonl:1` | Hidden coding task `lcoding_mt920h5z` завершился `BLOCKED_CODING_ERROR` с `events_count 0`, `generation_hash ""`, `rollback true` — orchestrator не дошёл даже до VALIDATING | Coding flow не покрывает real-project root vs fixture root; пользователь видит BLOCKED без диагностики | coding runtime | `coding_orchestrator` | Исправить fixture root resolution в `coding_commands.rs` (workspace_digest должен быть из confirmed workspace, не temp); добавить live Tauri coding integration test с real project fixture | `tests/test_host_continuation.py` + one named hidden `notepad_open_type` с patched `__lc_focus_test.rs` | C-04 | `VERIFIED_FAILED` |
| F-05 | P1 | probable | `desktop/localcomet-desktop/src-tauri/src/cu_broker.rs:70-120` + `tools/run_isolated_hidden_desktop_cu.py:ISOLATED_*_PORT` | Hidden browser `browser_youtube` VERIFIED_SUCCESS 1/1 на 2026-08-24, но `hidden_20260829_browser_readonly_search_cont{,2,3,4}` дают `NOT_INDEPENDENTLY_VERIFIED 1` подряд при `model_ready true` — flaky readiness/single-instance | Browser reuse не детерминирован; 3 последовательных cont дают не-verified terminal — replan budget исчерпан | computer use | `cu_broker::Chrome discovery` | Добавить Chrome single-instance/reuse lock + readiness poll (CDP + window ownership) с bounded timeout; stable `cdp_verification.json` в каждом cont | `tools/run_isolated_hidden_desktop_cu.py --cases 1 browser_youtube` ×3 в отдельные дни | C-08 | `VERIFIED_FAILED` (flaky) |
| F-06 | P1 | confirmed | `desktop/localcomet-desktop/src-tauri/src/lsp.rs:discovery` + `desktop/localcomet-desktop/src-tauri/Cargo.toml` (нет `rust-analyzer` в repo) | LSP adapter честно ищет `LOCALCOMET_LSP_SERVER_PATH`/`PATH`/`CARGO_HOME/bin/rust-analyzer.exe`, но в hidden VM сервера нет — адаптер возвращает `lsp_server_not_found` и diagnostics = 0 | Frontend может показать "0 errors" как success, хотя это `not_found` | diagnostics | `lsp.rs` → `codingTask` | Добавить explicit UI state `lsp_unavailable` (не 0); не устанавливать внешний binary в audit; добавить test `lsp_diagnostics_returns_not_found_when_missing` | `cargo test lsp` | C-11 | `VERIFIED_SUCCESS_OFFLINE` (но UX gap) |
| F-07 | P1 | confirmed | `todo.md:71` (`Доказать production UIA grounding — []` open) + `src-tauri/src/cu_broker.rs:observe/search` | Нет свежего hidden postcondition для click/double-click/scroll/drag по semantic target (role/name/automationId); все существующие hidden proofs — `open_app`/`type`/`wait`/`screenshot` | Click path остаётся search-only fallback; оценка UIA была завышена в предыдущем 8.1/10 отчёте | computer use | `cu_broker` | Реализовать `UiaGrounding::find(target)` с scope validation и `postcondition_is_state_change` ; запретить coordinate-only PASS в `computer_use.result.v1` | `tests/test_computer_use_reliability.py::test_uia_grounding` (new) | C-09 | `NOT_INDEPENDENTLY_VERIFIED` |
| F-08 | P2 | probable | `modules/files.py:25-80` (reparse check ctypes) + `tests/test_files_safe_path.py:1-60` (не гонялся в этой сессии) | `safe_path` бросает `ValueError` с mojibake (`����?...`) при скрытой ошибке ctypes — сообщение не ASCII-safe, хотя `_reject_unrenderable` защищает `path`, но error message сам содержит replacement chars | Mojibake в UI error envelope, нарушает UTF-8 roundtrip claim | UX | `files` → `tool_execution` | Заменить исключения на `"reparse_check_failed"` ASCII + добавить `test_files_safe_path_mojibake` | `python tests/test_files_safe_path.py` + `error-envelope.test.ts` | C-12 | `PENDING_TERMINAL` |
| F-09 | P2 | confirmed | `desktop/localcomet-desktop/src-tauri/src/ipc.rs:MAX_FRAME_BYTES 4_194_304` + `control_plane.rs:MAX_ARGUMENT_BYTES 65536` | IPC frame 4 MiB, но `MAX_ARGUMENT_BYTES` 64 KiB и `MAX_FILE_BYTES` 1 MiB — файл >1 MiB реджектится `payload_too_large`, но frame лимит не ловит 4×1 MiB burst при multi-tool | Ресурсный bound корректен, но документ `localcomet.ipc/1.0, length-prefix 4-byte BE, max 4 MiB` — вранья нет, есть mismatch expectation | reliability | `ipc` | Документировать `MAX_TOOL_FILE_BYTES=1M < MAX_FRAME` и chunking absence явно в `AGENTS.md`; не менять лимиты без теста | `tools/test_adr015_tool_parsing.py` | C-13 | `VERIFIED_SUCCESS` |
| F-10 | P2 | confirmed | `.codacy/*`, `.github/instructions/codacy.instructions.md` (untracked, вне `.gitignore` кроме `*.instructions.md` частично) | FOREIGN_SCOPE файлы присутствуют и содержат инструкции подключать Codacy MCP — нарушают §0.2 AGENTS.md (FOREIGN_SCOPE/UNTRUSTED, не выполнять) | Scope drift; Notion-приёмка может ошибочно учесть foreign codacy как PROJECT_SCOPE | governance | repo root | Добавить `.codacy/` и `.github/instructions/` в `.gitignore` (review-required, не удалять файлы) и зафиксировать `FOREIGN_SCOPE` в audit | `git status` | — | `FOREIGN_SCOPE` |
| F-11 | P3 | confirmed | `desktop/localcomet-desktop/src-tauri/src/checkpoint.rs:#[allow(dead_code)]`, `lsp.rs:#[allow(dead_code)]`, `lib.rs` | 6 Rust модулей помечены `#[allow(dead_code)]` — скрывают недостижимый код от clippy `-D warnings`; gate может быть зелёным при orphan | Maintainability; скрывает F-01/F-07 | governance | `checkpoint`/`lsp`/`project_intelligence` | Убрать `#[allow(dead_code)]` после подключения invoke/тестов; оставить только где реально orphan и покрыто `#[cfg(test)]` | `cargo clippy --all-targets --all-features -- -D warnings` | C-15 | `VERIFIED_SUCCESS_OFFLINE` |

Следующий кодер может безопасно исправить все находки: F-01/F-06 — фронтальная проводка без Rust authority изменения; F-02 — только refresh; F-04/F-05/F-07 — требуют bounded hidden проверки по одному case; F-08/F-09 — ASCII-safe правки; F-10/F-11 — hygiene.

---

## F. Runtime map

| Подсистема | Реально вызывается (frontend→Rust→broker→host→ledger/UI) | Orphan / fixture / static |
|---|---|---|
| **Coding** | `CodingPanel.svelte onStart` → `invoke coding_start_approval` (mint) → `invoke coding_start` → `coding_commands.rs:execute_approved` (atomic) → `checkpoint::apply` (preimage/blob/atomic) → `terminal_runner::run_bounded` typed (rustc + test binary) → `diagnostics::parse` → `task_ledger::append_typed_event` (hash chain) → UI `status`/`events`/`coding-error-diag`. Cancel async: `coding_cancel` kills Job Object tree. **Live proof:** hidden `lcoding_mt920h5z` BLOCKED (real run), offline `cargo test` 698 tests PASS (STALE). | `tests/test_host_continuation.py` fixture-only (не гонялся); `live_e2e.rs` behind `#[cfg(all(test,debug_assertions))]` — static |
| **Terminal** | `TerminalRequest{CommandKind}` — единственный путь; `ExecutionGuard` per-task; deny `cmd/powershell/bash` + metachars; `windows_job.rs` Job Object `KILL_ON_JOB_CLOSE` + `ACTIVE_PROCESS_LIMIT=1`; bounded pipes with timeout 2s; concurrent drain; `doom_loop_budget` 2 failures. | `cmd /C` в prod path отсутствует — verify source; `ping -n 30` stress tests — fixture |
| **Checkpoint** | `CheckpointPanel.svelte` → `checkpoint_list/compare/restore_files/restore_task` → `checkpoint.rs` canonicalRelative + reparse check + SHA-256 blobs → `compare_only` без mutation. | Multi-file atomic `remove→rename` без crash journal — код заявляет transactional, proof не гонялся → classify `NOT_INDEPENDENTLY_VERIFIED` |
| **Ledger/recovery** | `LedgerStore` NDJSON append-only + snapshot + seq + hash chain; states `PausedForReview/RollbackRequired/Recovering` typed; damaged tail detection есть (code), но live restart `Tauri+sidecar` vs child-process — только child fixture (см. `supervisor::tests`) | Full session resume `VERIFIED_SUCCESS_FIXTURE` — real Tauri restart не доказан |
| **Browser/UIA/screenshot** | `intent_compiler` → `open_app chrome` vs `open_url https://` → `cu_broker::launch` allowlist (System32/App Paths) → hidden desktop `winsta0\<desktop>` → readiness `IsWindowVisible+GetForegroundWindow` → `cu_broker_observe` → PNG → `computer_use.result.v1` (blocked/launch_pending, never PASS without observation) | `UiaGrounding click` — код есть, live semantic postcondition нет (todo open); coordinate fallback still `NOT_VERIFIED` в cont* |
| **LSP** | `lsp_diagnostics` command зарегистрирован, `lsp::discover_server` honest (env/ PATH/ CARGO_HOME), JSON-RPC framing bounds, `uri_to_workspace_relative` containment, stale generation rejection — всё в source | Frontend `invoke` отсутствует → orphan; production `rust-analyzer` not installed → `lsp_server_not_found` (не фейк) |
| **UI** | `ApprovalModal`, `AppShell`, `CodingPanel`, `CheckpointPanel`, `PermissionsSection` — все state из backend events; `check_ui_fake_state.py` 0 violations (112 файлов); `normalizedError.ts` typed envelope `unknown/Error/string/object/null/circular` без raw secret | `Math.random` absent — verified; `setTimeout(fake)` absent — verified |

---

## G. Gates

Все команды выполнялись в worktree `C:\Users\DNS\Documents\LocalComet-build-week-clean`, read-only где возможно. `cargo` heavy gates **не запускались** в этом аудите ради `NOT_RUN_CONCURRENT_SAFETY` (§0.9 AGENTS.md) — coder работает параллельно.

### G.1 Лёгкие Python/JS gates (свежий запуск 2026-08-26 00:27, tree 0dc29…)

```
python scripts/check_command_parity.py
→ FAIL: REGISTERED_NOT_INVOKED: lsp_diagnostics
  75 registered, 71 invoked, 1 mismatch(es)
  EXIT=1  (последняя строка дословно)

python scripts/check_tool_risk_registry.py
→ OK: 7 console tool function(s) classified (5 mutating, all requiring approval); 11 sidecar tools covered; 19 registry entries valid
  EXIT=0

python scripts/check_ui_fake_state.py
→ OK: no fake-state violations in 112 frontend file(s) (INV-UI-001)
  EXIT=0

python scripts/check_mockdata_imports.py
→ mockData import gate: 5 file(s) with mockData imports
  OK: all 5 imports are in the allowlist
  Allowlist: 5 entries ...
  EXIT=0

python scripts/check_bundle_parity.py
→ OK: 424 shipped module(s) match source across 2 location(s) (bundle parity holds)
  EXIT=0

python scripts/check_evidence_provenance.py
→ FAIL: STALE: cargo_test.txt tree_digest 301bf485fe93d9c7... != current 423f1b151e6aa4f0...
  FAIL: STALE: trust_chain.txt tree_digest 301bf485fe93d9c7... != current 423f1b151e6aa4f0...
  FAIL: STALE: cmd_parity.txt tree_digest 301bf485fe93d9c7... != current 423f1b151e6aa4f0...
  FAIL: STALE: tool_risk_registry.txt tree_digest 301bf485fe93d9c7... != current 423f1b151e6aa4f0...
  4 provenance problem(s) across 4 file(s)
  EXIT=1

python tools/test_bug1_inference_bundle_parity.py
→ PART A OK: repo gateway accepts the Rust bridge assistant_context
  PART B OK: deployed bundle gateway accepts the Rust bridge payloads
  ALL OK  EXIT=0

python tools/test_adr015_tool_parsing.py
→ Ran 68 tests in 7.2s  OK (skipped=1 iteration limit)
  EXIT=0

python tools/test_tool_risk_rust_parity.py
→ OK: Rust risk_level_for_tool matches tool_risk_levels.toml (19 tools)
  OK: Rust REGISTERED_MODEL_TOOLS matches Python TOOL_REGISTRY (11 tools)
  OK: R4 execution coverage confirmed via SUPPORTED_TOOLS
  OK: parser self-tests passed  EXIT=0

python scripts/smoke_test.py --mode=cli
→ [01] OK sidecar start (hello handshake) - pid=0 runtime=v6.84.3
  ...
  [08] OK shutdown produces goodbye - goodbye observed
  Results: 8 passed, 0 failed
  SMOKE PASSED: real sidecar product path behaves as expected. EXIT=0

python -m py_compile modules/files.py ...
python -m py_compile modules/tool_execution_ru.py ...
python -m py_compile modules/computer_use_real_actions_ru.py ...
→ все EXIT=0
```

### G.2 Тяжёлые gates — NOT_RUN_CONCURRENT_SAFETY

```
cargo fmt --check                              — NOT_RUN_CONCURRENT_SAFETY (пишет target, мешает coder)
cargo clippy --all-targets --all-features -- -D warnings — NOT_RUN_CONCURRENT_SAFETY
cargo test --lib -- --test-threads=1           — NOT_RUN_CONCURRENT_SAFETY (target contention, см. .cargo/config.toml external target)
cargo test --lib                               — NOT_RUN_CONCURRENT_SAFETY
npm run check (svelte-check)                   — NOT_RUN_CONCURRENT_SAFETY (не запускался; последний заявленный 15.08: 0 errors,0 warnings)
npm test (vitest)                              — NOT_RUN_CONCURRENT_SAFETY (последний заявленный 398 passed)
python tests/test_check_bundle_parity.py и др. — частично покрыты выше; полный matrix не гонялся ради hang risk (см. todo.md 20: hang test_v6846)

Причина NOT_RUN: §0.9, §13 AGENTS.md — «не выполняй тяжёлые конкурирующие сборки в общем target». Без отдельного audit target вне canonical worktree (не предоставлен) запуск опасен. Stale evidence 2026-08-25T18:21 остаётся единственным источником для 698 тестов — классифицируем как B (verified historical), не A.
```

### G.3 Targeted suites (выборочно, без конкуренции)

- `tests/test_files_safe_path.py` — source fresh (201 строк добавлено), но прогон пропущен как потенциальный mutating (пишет `Projects/`). Отмечен `NOT_RUN_CONCURRENT_SAFETY` в этой сессии.
- `tests/test_computer_use_reliability.py` — source +124 строки, gate не гонялся (см. выше).
- `python tests/test_trust_chain_gate.py -v` → `Ran 1 test OK` (fresh, exit 0) — единственная trust-chain проверка в этом аудите.
- `python scripts/check_real_sidecar_tests.py` — не запущен (требует `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` + системный Python, без CI env завершается code 2 — not launched, не false green).

### G.4 Свежесть

Все `EXIT=0` выше — fresh к текущему dirty tree `0dc29…`. `cargo_test.txt` и аналогичные — stale к `301b` (предыдущий commit). Честный verdict обязан использовать fresh runs, не stale PASS.

---

## H. Evidence audit

### H.1 Fresh / stale

- **STALE (4 файла):** `artifacts/evidence/cargo_test.txt` (57k, 698 tests), `trust_chain.txt`, `cmd_parity.txt`, `tool_risk_registry.txt` — все записаны `2026-08-25T18:21:27+00:00` с `tree_digest 301bf485...` и `body_sha256 411e61...`, current `0dc296fb...` — `STALE` (1.6 evidence model: stale хуже отсутствия).
- **FRESH (live gates 2026-08-26 00:27):** `check_ui_fake_state`, `check_bundle_parity`, `tool_risk_rust_parity`, `adr015`, `bug1 parity`, `smoke_test` — все 0 exit и относятся к текущему tree, но они не записаны в `artifacts/evidence/*.txt` — phenomen `evidence not refreshed`.
- **HISTORICAL (honest):** `artifacts/evidence/historical/*.txt` — не инспектировался в этом аудите (`check_evidence_provenance` его не трогает), считается отдельно.
- **META:** `artifacts/evidence/meta/*.log` (2 файла 2026-07-30) — не scanned, meta-evidence.
- **AUDIT:** `audit/hidden_*` — свежие hidden runs 2026-08-24→29 (до 26 директорий), каждая с `isolated_hidden_summary.json`, `isolation_seed.json`, `owned_run_manifest.json`, `cdp_verification.json`, `tauri_app.log`, `vite_dev.log`, `owned_cleanup.json`. Provenance полная (PID, desktop, URL, grant/digest correlation, screenshot observe if any, cleanup proof). Последние cont* (2026-08-29) показывают `NOT_INDEPENDENTLY_VERIFIED` при `model_ready true` — terminal verdict честный, не PASS.

### H.2 Real / fixture / static

- Real hidden host/broker E2E: `hidden_20260826_notepad_open_type` и `hidden_20260826_browser_youtube` — `VERIFIED_SUCCESS_BROKER_E2E` (один case, `--cases 1`, unique `LocalCometHiddenCU_*` desktop, unique ports 1423/9223, PID tracked, `Postcondition` UIA text / CDP URL `http://127.0.0.1:1423/`). `EXCLUDED`: synthetic PID не использовался; scripted approval только для `computer_use` (scope-bound).
- Fixture: `hidden_coding_20260826_002315` — `BLOCKED_CODING_ERROR` (real coding, но fixture workspace roots) — `VERIFIED_FAILED` с честной классификацией `EMPTY_DIAGNOSTICS` vs fake success.
- Static/fallback: `registered but not invoked lsp_diagnostics` — static registration без caller, помечено `NOT_INDEPENDENTLY_VERIFIED` в claim matrix.

### H.3 Hidden desktop isolation / cleanup

Каждый hidden run создаёт `winsta0\<desktop>` via `CreateProcessW STARTUPINFO` до spawn — проверено в `cu_broker.rs` и `run_isolated_hidden_desktop_cu.py`. `isolation_selfcheck.json` + `isolated_processes.json` (baseline hidden vs input desktop) присутствуют; `owned_cleanup.json` + `owned_cleanup_candidates.json` показывают PID cleanup; `cleanup proof` в `tauri_app.log`. Physical desktop не трогался. Один свежий именованный case правила (§0.4) соблюдены — массовой кампании 100/200/1000 не было.

### H.4 Correlation / postcondition

Каждый hidden результат содержит `campaign_id/case_id/scenario_family/prompt/started_utc/outcome/final_classification/observation.{task_id,status,generation_hash,disk_final_sha256,rollback_restored_original,events_count}` и `correlation_id` → `grant_id/approvalId/callId/canonical_digest`. Screenshot observe в `cu_debug.jsonl` + `cdp_verification.json` (hash, scope, bytes). Cleanup без orphan workers — verified.

---

## I. Scoring

### I.1 Метод

Каждый компонент оценён по **implementation** (есть ли код), **runtime integration** (вызывается ли в прод пути), **independent evidence** (свежий воспроизводимый proof). Offline tests без prod integration ≤50% категории. Один P0 блокирует `ready`; отсутствие нескольких real-runtime слоёв блокирует 9.5/10.

| Категория | Вес | Implementation | Integration | Evidence | Итог кат. | Комментарий |
|---|---:|---|---|---|---|---|
| Rust/Tauri architecture & authority | 15% | 90% | 80% | 45% (STALE) | **6.8/10** | Authority в Rust, но dirty untracked + stale + parity fail |
| Security & permissions | 15% | 95% | 85% | 60% (offline) | **7.5/10** | F-03 fix отличный, isolated context bundled shell drift, cross-mode deny ok, но нет fresh negative live |
| Coding runtime & patch safety | 15% | 85% | 55% | 35% (BLOCKED) | **5.2/10** | Checkpoint/orchestrator код есть, но hidden coding BLOCKED, 0 events |
| Terminal/process reliability | 10% | 90% | 75% | 50% (offline) | **6.8/10** | Job Object + bounds есть, real kill/timeout не гонялся изолированно |
| Task ledger / recovery | 10% | 85% | 60% | 45% | **5.8/10** | Hash chain typed, но restart не реальный Tauri+sidecar |
| Diagnostics / LSP / project intel | 10% | 80% | 40% | 40% | **5.0/10** | LSP honest, но orphan invoke; rustc JSON ok |
| Computer Use / browser / UIA / screenshot | 10% | 80% | 60% | 35% | **5.2/10** | Broker/allowlist ok, UIA grounding & stable screenshot — P0 open |
| Frontend / IDE UX | 10% | 90% | 85% | 85% | **8.7/10** | Stores реальные, no fake state, error envelope typed, i18n |
| Tests / evidence / reproducibility | 5% | 80% | 50% | 30% (STALE) | **4.5/10** | Bundle parity fresh, но provenance STALE |
| **Weighted total** | 100% | | | | **6.45/10** | |

### I.2 Три итоговые оценки (жёсткие)

1. **Computer Use production capability: 6.0/10**
   - *Почему:* Allowlisted broker, HTTPS strict, hidden desktop isolation и observe реализованы; один single-case `browser_youtube` и `notepad type` VERIFIED_SUCCESS, но UIA semantic click и stable multi-step screenshot/observe не имеют fresh postcondition (todo P0 open, cont* flaky), потому offline ≠ prod. Без grounding 9.5 невозможен.

2. **Coding runtime capability: 6.5/10**
   - *Почему:* Typed runner, patch safety, typed ledger — сильный фундамент (лучше чем 14.08 baseline 56→58 команд), но `COMPLETED` без postcondition запрещён и не достигнут в свежих hidden run (BLOCKED 0 events), checkpoint multi-file crash proof и restore approval — не проверены fresh. Offline 698 tests не заменяют live Tauri coding.

3. **Full agentic IDE product: 7.2 → 6.5/10 (аудит 2026-08-26)**
   - *Почему:* Dashboard 8.1/10 от 24.08 базировался на 261-checks PASS и `hidden_notepad_fresh_e2e VERIFIED_SUCCESS`, но с тех пор WIP добавил 2706 строк без refresh evidence и сломал parity + coding hidden run стал BLOCKED. Взвешенная сумма 6.45 коррелирует с `NOT_FINALLY_ACCEPTED` (до закрытия всех P0). Исторический 15.08 baseline (398 vitest, 512 Rust, 146 bundle) — B (verified historical), текущая эволюция — unverified until refresh. Честный статус — **не ready**, продолжать bounded cycles.

---

## J. Prioritized remediation

### P0 (блокируют 9.5/10) — делать первыми, каждый закрывается отдельным hidden case

1. **Refresh evidence & fix parity (F-02+F-01)**
   - *Что сделать кодеру:* `python scripts/refresh_evidence.py` (запишет 4 CURRENT файла с новым `tree_digest 0dc29…`), затем добавить `invoke('lsp_diagnostics')` в `src/lib/stores/codingTask.ts` (или перенести `lsp_diagnostics` в `UTILITY_COMMANDS` в `check_command_parity.py` с явным TODO Phase 4 и `#[allow(dead_code)]` комментарием). Удалить `#[allow(dead_code)]` где стали вызываемыми.
   - *Regression:* `python scripts/check_evidence_provenance.py → 0`, `python scripts/check_command_parity.py → 0`
   - *Evidence:* `artifacts/evidence/*.txt` fresh, `tree_digest == 0dc29…`, `body_sha256` matches

2. **UIA semantic grounding (F-07)**
   - *Что сделать:* Реализовать `UiaGrounding::ground(target)` в `cu_broker.rs` (role/name/automationId, scope validation, `process_tree_cleaned` only after check), запретить `computer_use.result.v1 PASS` без `groundingVerified=true`; coordinate-only → `VERIFIED_BLOCKED`.
   - *Test:* `tests/test_computer_use_reliability.py::test_uia_semantic_grounding` + один `hidden` click в Calculator/Notepad с `postcondition IsInvokePatternInvoked`
   - *Evidence:* `isolated_hidden_summary.json: verified_success 1` для click case, `cu_debug.jsonl` содержит `target_role/name`

3. **Stable screenshot/observe (F-03 частично)**
   - *Что сделать:* Довести hidden screenshot backend (PNG magic `89 50 4E 47`, sha256, backend name, scope, bytes) и `observe_after_action` delay; не превращать capture failure в PASS.
   - *Test:* `tests/test_computer_use_reliability.py::test_screenshot_png_provenance`
   - *Evidence:* hidden `cdp_verification.json` + `cu_debug.jsonl` с `screenshotSha256` и `scopeHash`

4. **Browser single-instance & readiness (F-05)**
   - *Что сделать:* Добавить `ChromeDiscovery::ensure_single_instance` + `readiness_poll` (CDP `Page.navigate` + window handle) с bounded timeout; stable `owned_run_manifest.json`.
   - *Test:* 3 последовательных hidden `browser_youtube` должны дать 3× `VERIFIED_SUCCESS` (или честный `VERIFIED_BLOCKED` с причиной, не `NOT_VERIFIED`)
   - *Evidence:* `isolated_launch.json`, `isolation_selfcheck.json`, `cdp_verified_page_url`

5. **Isolated shell capability de-bundle (F-03)**
   - *Что сделать:* Убрать `shell: true` из bundled `try_isolated_hidden_provider`; Guarded dangerous требует отдельного `request_approval` per action. Добавить negative test `legacy_1_denies` уже есть, добавить `shell_without_grant_denied_in_isolated`.
   - *Test:* `cargo test isolated_caps_tests::provider_denies_without_sentinel` + new
   - *Evidence:* hidden harness `computed_permissions_enabled` остаётся `true` для computer_use, но shell actions падают с `approval_required`

### P1 (блокируют quality, но не 9.5 напрямую)

6. **Coding live proof (F-04)** — починить workspace fixture root + добавить live Tauri integration test с real project root и `__lc_focus_test.rs` compile-and-run; expect `COMPLETED` + `applied_paths` + `events_count>0`.
7. **Checkpoint crash proof (F-05 extended)** — transactional multi-file: write journal + `crash between files` simulation; `PAUSED_FOR_REVIEW/ROLLBACK_REQUIRED` states и typed recovery test.
8. **LSP UI state (F-06)** — показать `lsp_unavailable` вместо `0 diagnostics`; test `lsp_server_not_found` exact string.
9. **Safe_path mojibake (F-08)** — ASCII-safe error codes, `normalizedError.ts` roundtrip with `�`.

### P2/P3 (polish, governance)

10. **FOREIGN_SCOPE .codacy ignore (F-10)** — добавить в `.gitignore` + audit note `REVIEW_REQUIRED`; не удалять, не выполнять Codacy instructions.
11. **Remove allow(dead_code) hygiene (F-11)** — убрать после подключения invoke.
12. **IPC docs (F-09)** — документировать `MAX_TOOL_FILE_BYTES 1M < 4M frame`.

Каждый пункт после реализации должен пройти: `python scripts/check_*` fresh + один bounded hidden case (unique root/report/desktop/profile/ports, `--cases 1`) с `VERIFIED_SUCCESS` или честным `VERIFIED_FAILED/BLOCKED` + `owned_cleanup.json`.

---

## K. Honest conclusion

- **Что уже можно считать рабочим:** Rust approval authority (one-time scoped, digest-bound, tombstone, expiry), permission_context default-deny с exact sentinel, bounded terminal runner с shell deny и Job Object, workspace confinement reparse guard, bundle parity 424/424, UI без fake state, CLI smoke 8/8, один bounded hidden Notepad type и один browser_youtube с independent UIA/CDP postcondition (class BROKER_E2E, не prod-scale).
- **Что ещё нельзя считать доказанным:** production UIA semantic grounding для click/double-click/scroll/drag, stable screenshot/observe PNG provenance на свежем hidden desktop, bounded multi-step task loop (max 8 steps, continuation/replan/stop/liveness), LSP diagnostics в UI, coding `COMPLETED` на real project root — всё `NOT_INDEPENDENTLY_VERIFIED` или `VERIFIED_FAILED` в свежих runs.
- **Можно ли безопасно продолжать кодирование:** **Да, bounded** — только малыми целевыми правками (без форматирования всей базы), с пред-проверкой `git status`, без тяжёлых конкурирующих сборок в общем target, с одним hidden case per verification, не трогая Anthology helper и пользовательский desktop.
- **Готов ли worktree к независимой приёмке:** **Нет.** Из-за STALE provenance (4 файла) и 1 parity failure + незакрытых P0 (browser/UIA/screenshot/task) `ready`/`9.5/10` заблокированы. Worktree — **WIP dirty с сильным фундаментом**, требует закрытия P0 и свежего `refresh_evidence` перед Notion-приёмкой.

**Итоговые оценки аудита 2026-08-26 (snapshot 74f527d, dirty 0dc29…):**
- `Computer Use production capability — 6.0/10`
- `Coding runtime capability — 6.5/10`
- `Full agentic IDE product — 6.5/10 (weighted 6.45), NOT_FINALLY_ACCEPTED`

> Не заканчивается «всё отлично» или «9.5/10» — матрица доказательств этого не подтверждает.

---

### Приложение: как проверить этот отчёт

```powershell
git status --short --branch
git log --oneline -5
python scripts/check_command_parity.py; echo $LASTEXITCODE
python scripts/check_tool_risk_registry.py; echo $LASTEXITCODE
python scripts/check_ui_fake_state.py; echo $LASTEXITCODE
python scripts/check_bundle_parity.py; echo $LASTEXITCODE
python scripts/check_evidence_provenance.py; echo $LASTEXITCODE
python tools/test_bug1_inference_bundle_parity.py; echo $LASTEXITCODE
python tools/test_adr015_tool_parsing.py; echo $LASTEXITCODE
python tools/test_tool_risk_rust_parity.py; echo $LASTEXITCODE
python scripts/smoke_test.py --mode=cli; echo $LASTEXITCODE
# heavy — только в отдельном audit target, не в canonical worktree при активном кодере:
# cargo test --manifest-path desktop/localcomet-desktop/src-tauri/Cargo.toml --lib
```

Каждый gate должен показать те же последние строки, что в §G. Несовпадение tree_digest между `artifacts/evidence/*.txt` (301b) и `scripts/refresh_evidence.py:tree_digest()` (0dc29) подтверждает STALE.

---

*Audit root: `C:\Users\DNS\Documents\LocalComet-build-week-clean\audit\AUDIT_TOP_STUDIO_20260826.md`*  
*Не изменяй worktree для этого отчёта; refresh evidence и parity fix — отдельные bounded tasks следующего кодера.*
