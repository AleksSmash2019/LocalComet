# Известные дефекты и неполные границы

## Подтверждённое

1. **Workspace propagation не реализован end-to-end.** `INV-WORKSPACE-001` имеет `planned`, пустые implementation/tests (`invariants.toml:200-208`). Локальная validation/invalidation есть, sidecar `workspace.set` round-trip оставлен future path (`workspace.rs:16-21`; `approval_commands.rs:103-107`).
2. **Approval grants не исполняют tools.** `execute_approved` создаёт grant metadata, но не dispatches operation; sidecar filesystem methods unsupported (`approval_commands.rs:100-107`). Production Svelte caller для `bridge/approval.ts` не найден; ApprovalCard buttons disabled.
3. **Пять desktop mutating operations не показаны проходящими через approval token.** Binding/download/removal используют `confirmed: bool`, runtime start/stop не принимают grant. Это расходится с `requires_approval=true` в canonical registry.
4. **Real-sidecar test может быть фактически пропущен.** Без `LOCALCOMET_TEST_PROJECT_ROOT`/`LOCALCOMET_TEST_PYTHON` test returns successfully after internal SKIP (`supervisor.rs:716-736`). Общий green cargo result не доказывает real Python launch.
5. **Catalog/model invariants имеют пустые registry test bindings.** `INV-CATALOG-001`, `INV-CATALOG-002`, `INV-MODEL-001`: `test_ids=[]`; related Rust tests есть, dedicated machine binding нет.
6. **Evidence invariant ссылается на отсутствующий named test.** `check_evidence_provenance_detects_stale` объявлен в registry, но найден только там; checker сам существует и свежий run прошёл.
7. **Tool-risk checker ограничен.** Он introspects `modules/files.py`/`safe_path`; desktop rows проверяются по schema/value, не на consumption grant в Rust.
8. **Legacy mock/demo production path остаётся.** `turn.start_mock`, `control_plane_start_mock_turn`, `mockData.ts` demo tool/approval/verification fixtures присутствуют. `INV-UI-001` checker семантические mock APIs не классифицирует.
9. **Multi-chat backend отсутствует.** UI имеет IDs/fixtures, но visible sidebar сводит их к одному chat; transcript глобальный, backend history по `chat_session_id` не реконструирует.
10. **Project Knowledge preview не production-reachable.** Tested `KnowledgePreviewPanel` не рендерится normal composer; вместо него `KnowledgeToggle` сообщает unavailable.
11. **Approval, tool and verification cards не production-reachable.** Компоненты присутствуют/тестируются, но imports from production render tree не найдены.
12. **Persisted evidence/log browser отсутствует.** Observability показывает bounded current-session events/runtime tails и прямо не называет их evidence.
13. **Packaged install smoke частичный.** `docs/unverified-ledger.md` оставляет install/installed launch/non-admin/path-with-spaces/Cyrillic непроверенными.
14. **Старый desktop README устарел.** Он утверждает 13 commands и отсутствие file/artifact/approval surfaces, тогда как текущая регистрация содержит 42 commands и safe file selection/artifact management. README нельзя использовать как current authority.
15. **Frontend warning остаётся.** Fresh `npm run check`: `LanguageSwitcher.svelte:56:5`, listbox interactive role without tabindex; 0 errors, 1 warning.
16. **Tauri CLI не доступен как global Cargo subcommand.** `cargo tauri --version` завершился exit 101. Локальный npm package `@tauri-apps/cli` pinned 2.11.4 и доступен через npm scripts после dependencies install.
17. **CI Python suite имеет большую baseline ignore-list.** `.github/workflows/validation.yml:20-39` явно исключает test files из pytest; CI green не означает полный Python suite.

## Явно deferred/rejected

Plan Review/execution, persisted evidence export, backend multi-chat, voice/local-STT, permission profiles, model parameters, MCP, diagnostic export/reset, arbitrary Hugging Face install and browser hardware recommendation. Донорские fake timers/random telemetry/client evidence intentionally rejected, а не недоделаны как обещанная функция.

## UI показывает недоступность вместо данных

- Model not ready/not connected disables composer until backend-derived readiness.
- Safe files may report capability unavailable.
- Project context unavailable in normal chat.
- Control Plane distinguishes unknown/connecting/unavailable/error.
- Runtime/model errors remain visible; no runtime log lines has explicit empty state.
- Internet, email, browser, Vault, Computer Use, shell and external tools are unavailable in Settings.
- BLOCKED/stale Knowledge Review decisions remain unavailable.
- Approval actions remain disabled because no connected execution flow exists.

## TODO/FIXME/stub scan

No literal TODO/FIXME was found in first-party `desktop`, `modules`, or `scripts` source during this review. Explicit DEFER records are in `audit/donor-screen-port-matrix.md`. Absence of these words does not remove the concrete incomplete boundaries above.
