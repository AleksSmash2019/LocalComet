# Аудит и восстановление LocalComet — 2026-10-04

Сессия: ZCode (GLM). Ветка: feat/up00-wp01-windows-one-click-launch. HEAD: 696bdac (не менялся, коммитов нет).
Задача владельца: «чини и проведи детальный аудит проекта, что ок и что не ок».

## 1. Исходное состояние (до работ)

git status: 20 файлов удалены в рабочем дереве (D), 16 изменены (M), 5 не отслеживаются (??).
HEAD 696bdac «docs: ModelFit in-window rework report and traps» (07.09), коммитов после 07.09 нет.

Удалённые (все восстановлены из git без потерь, `git restore`):
- desktop/localcomet-desktop/src/lib/i18n/ru.ts (главный языковой файл UI)
- desktop/localcomet-desktop/src/lib/stores/modelGateway.ts (центральное хранилище моделей)
- src-tauri/src: control_plane.rs, supervisor.rs, files.rs, artifact_acquisition.rs, artifact_trust.rs, artifact_trust_tests.rs
- modules: computer_use_contract_tests_ru.py, computer_use_real_actions_ru.py, local_model_gateway_ru.py, premium_task_panel_ru.py
- modules/_vendor/uiautomation/uiautomation.py
- tools: run_isolated_hidden_desktop_cu.py, test_adr015_tool_parsing.py, test_v68451e9b_knowledge_review.py, test_v68451e9c_review_projection.py
- .codacy/codacy.config.json, AUDIT_ROOT/mutation/M3.original, AUDIT_ROOT/mutation/M8.original

Причина удалений: не рефакторинг (ссылки не обновлены), а повреждение рабочего дерева
(вероятно оборвавшийся сеанс). Точная причина не установлена.

## 2. Повреждения МАШИНЫ (вне репозитория) — та же «чистка», другой период

Обнаружены и устранены обходными путями (система не изменялась):

| Повреждение | Симптом | Обход |
|---|---|---|
| node_modules/vite отсутствовал | svelte-check падал ERR_MODULE_NOT_FOUND | `npm ci` (восстановление по lock) |
| Кэш cargo: serde (facade) повреждён | E0583 file not found for module `de` | Полная перекачка `~/.cargo/registry` (486 крейтов, SHA-256 верификация) |
| Windows SDK 26100: ucrt.lib + заголовки выброшены; legacy_stdio_definitions.lib и oldnames.lib отсутствуют в ОБОИХ SDK (19041/26100) | LNK1104/LNK1181 | Каталог `C:\Users\DNS\AppData\Local\LocalComet\ToolchainRepair`: um-libs из официального ISO SDK 26100.7705 + ucrt-libs из ISO + 2 стаб-архива (legacy_stdio_definitions, oldnames — пустые, собраны из empty.obj) + LIB/INCLUDE на SDK 19041 |
| Python 3.14.6 (py -3.14): _socket, html/entities.py выброшены; hermes 3.11: enum; 3.12: html.entities | все гейты падали ModuleNotFoundError | Гейты через Astral CPython 3.11.15 (uv, `%APPDATA%\uv\python\...`) — цел |
| `winsdksetup /layout` не работает (считает SDK установленным) | — | ISO SDK скачан с официального fwlink, MSI извлечены msiexec /a |

Рекомендация владельцу (системное решение): переустановить Windows SDK 26100 и Python 3.14 —
после этого обходные LIB/INCLUDE можно убрать.

## 3. Правки кода в этой сессии (все — в рамках незакоммиченной работы 09.09)

1. `lib.rs`: возвращена строка `mod adaptive_params;` (утеряна; подтверждено зеркалом
   `%LOCALAPPDATA%\LocalCometDev\workspace` — там она есть).
2. `approval_commands.rs`, `managed_runtime.rs`: `use crate::adaptive_params;` (то же подтверждение).
3. `diagnostics.rs`: валидированный локальный `spans` подключён в RustcMessage вместо дубля-инлайна
   (clippy unused_variable; WIP собрал новый парсер, но не подключил).
4. `terminal_runner.rs`: `#[allow(dead_code)]` на 2 публичных метода TerminalResult (succeeded,
   stderr_is_complete) — часть будущей WIP-обвязки, контракт сохранён.
5. Бандлы синхронизированы: modules/ → binaries/app/modules + LocalCometDev/workspace/modules
   (после этого bundle parity 480/480).

Проверка парности фронтенда adaptive-команд: фронтенд-вызовов get_adaptive_model_params /
get_adaptive_runtime_args НЕТ ни в репо, ни в зеркале — работа 09.09 бэкенд-only, UI-часть не
начата. Поэтому check_command_parity честно красный.

## 4. Гейты (дословные последние строки)

Фронтенд (desktop/localcomet-desktop):
- `npm run check` → `svelte-check found 0 errors and 0 warnings`
- `npm test` → `Test Files 42 passed (42)` / `Tests 545 passed (545)`

Rust (src-tauri; сборка через ToolchainRepair + SDK 19041 LIB/INCLUDE):
- `cargo test` → `test result: ok. 777 passed; 0 failed; 7 ignored; 0 measured; 0 filtered out; finished in 3.77s` EXIT=0
- `cargo fmt --check` → (вывода нет) EXIT=0
- `cargo clippy --all-targets --all-features -- -D warnings` → `Finished \`dev\` profile [unoptimized + debuginfo] target(s) in 13.81s` EXIT=0

Python (интерпретатор: uv CPython 3.11.15, т.к. системные повреждены):
- tests/test_check_bundle_parity.py EXIT=0 `OK`
- tests/test_evidence_model.py EXIT=0 `OK: 4 evidence file(s) fresh and intact (tree=2421ec5d284f623c...)`
- tests/test_trust_chain_gate.py EXIT=0 `OK`
- tests/test_tool_risk_registry_gate.py EXIT=0 `OK`
- tests/test_mockdata_import_gate.py EXIT=0 `OK`
- tests/test_trust_chain_invariants.py EXIT=0 `OK: 15 trust-chain files pass byte invariants`
- scripts/check_command_parity.py EXIT=1 `81 registered, 74 invoked, 2 mismatch(es)` — КРАСНЫЙ (WIP)
- scripts/check_tool_risk_registry.py EXIT=0 `OK: 7 console tool function(s) ... 21 registry entries valid`
- scripts/check_ui_fake_state.py EXIT=0 `OK: no fake-state violations in 114 frontend file(s) (INV-UI-001)`
- scripts/check_mockdata_imports.py EXIT=0 (2 информационные записи, нарушений нет)
- scripts/check_bundle_parity.py EXIT=0 `OK: 480 shipped module(s) match source across 2 location(s) (bundle parity holds)`
- tools/test_bug1_inference_bundle_parity.py EXIT=0 `ALL OK`
- tools/test_adr015_tool_parsing.py EXIT=0 `OK (skipped=1)`
- tools/test_tool_risk_rust_parity.py EXIT=0 `OK: parser self-tests passed`
- scripts/check_i18n_keys.py EXIT=0 `OK: 612 used i18n key(s) present in ru.ts (1009) and en.ts (1009)`
- scripts/smoke_test.py --mode=cli EXIT=0 `Results: 8 passed, 0 failed` / `SMOKE PASSED: real sidecar product path behaves as expected.`
- scripts/check_real_sidecar_tests.py (CI env, Astral python) EXIT=0 `OK: real-sidecar tests ran under require mode with no silent skips`
- scripts/refresh_evidence.py → `[FAIL] evidence/cmd_parity.txt exit=1 tree=2421ec5d284f623c...` (честная запись красного parity)
- scripts/check_evidence_provenance.py EXIT=1 `FAIL: NONZERO_EXIT: cmd_parity.txt exit_code=1` — КРАСНЫЙ (следствие WIP)
- scripts/check_vault_repo_parity.py → `RESULT: PASS (0 violations, 43 warning(s))`

НЕ запускался: полный pytest по legacy-набору (нет мандата; исторические красные от git-index не пересматривались).

## 5. Аудит: что ОК

- Целостность репозитория восстановлена: 0 удалений, все 777 Rust-тестов, 545 vitest,
  svelte-check 0/0, trust-chain, tool-risk, INV-UI-001, bundle parity 480/480, ADR-015,
  CLI smoke, real-sidecar, i18n-полность, vault parity — зелёные.
- Review Center: смонтирован в AppShell (AppShell.svelte:253) — старый аудит-пункт «unreachable» устарел.
- system.time: полностью зарегистрирован в control_plane.rs (объявление + схема аргументов +
  read_only риск) — старый аудит-пункт «недостижим» закрыт.
- Chat persistence и очередь ходов на месте (chatHistory.test.ts: persists/restores — зелёные).
- Ошибки E0433/E0277 из WIP устранены минимально, сверены с зеркалом рантайма (совпадение 1:1).

## 6. Аудит: что НЕ ок

P1 — незакоммиченная работа 09.09 (adaptive model launching) неполна:
  - бэкенд готов (adaptive_params.rs 428 строк, 2 команды, 777 тестов зелёные),
    но UI-вызовы не написаны → check_command_parity красный (2 registered-not-invoked),
    из-за него красный и provenance. Это единственные 2 красных гейта.
  - ~26 файлов лежат незакоммиченными с 09.09 — это и создало окно для потерь
    (модифицированный lib.rs уже терял строку; повезло, что зеркало сохранилось).
P2 — тулчейн машины повреждён «чисткой» (SDK x2, Python 3.14/3.12/3.11-hermes, node_modules,
  cargo registry). Пока работает через обходы; надёжное решение — переустановка SDK и Python
  (действие владельца, требует админ-прав).
P3 — подписанного автообновления по-прежнему нет (updater в tauri.conf.json/Cargo.toml отсутствует).
P4 — мусор в репо: outputs/ (аудит 09-13, вне git), .mimosa/ (артефакты сканера) — кандидат на уборку.

## 7. Не сделано и почему

- Не коммитил (нет указания).
- Не дописывал UI-обвязку adaptive-команд (это продуктовое решение: где и как UI использует
  адаптивные параметры; без него parity остаётся честно красным).
- Не правил системные установки (SDK/Python) — требует согласия и админ-прав; обходы не трогают систему.
- Не запускал приложение (после правок Rust первый запуск пересоберёт exe; по запросу).
