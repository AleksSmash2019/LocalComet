# DEEP AUDIT + REFACTOR 2026-09-05

Ветка: `feat/up00-wp01-windows-one-click-launch`, старт с HEAD `5286b58` (рабочее дерево чистое).

## Методика

1. Базовый прогон всех гейтов до правок (все зелёные: svelte-check 0/0, vitest 537, cargo 777, parity 79 команд, bundle parity 423 модуля, real-sidecar green, evidence fresh).
2. Три независимых аудиторских прохода параллельно (Rust-слой, Python-сайдкар, фронтенд) + ручной проход по системным находкам прошлых сессий.
3. Применение только безопасных малых правок; каждый кластер проверяется тестами.

## Найдено и исправлено (в этом прогоне)

### Python-сайдкар

- **P2 ownership_request_id рассинхрон схем**: `TOOL_REGISTRY` (gateway) рекламировал `ownership_request_id` для computer_use, а Rust-схема (`control_plane.rs::model_tool_argument_schema`) его отвергает → schema-верный вызов модели падал `protocol_mismatch`. Поле удалено из `TOOL_REGISTRY` (грант-корреляция живёт в event envelope — инвариант P0.2).
- **P2 close_owned в модельном enum**: `close_owned` рекламировался модели, но требует `ownership_request_id`, который Rust-схема не принимает → гарантированный отказ после опасного approval. Удалён из enum `build_tool_schemas` (skills-сторона использует собственный путь, не задет).
- **P2 web.search cache shape**: cache-hit возвращал `results` как JSON-строку, cache-miss — список. Теперь hit декодирует JSON → оба пути возвращают список.
- **P2 IPv4-mapped IPv6 SSRF-зазор**: `_resolve_public_fetch_target` не разворачивал `::ffff:127.0.0.1` / 6to4 — `is_loopback` на wrapper-адресе ненадёжен на ряде CPython-билдов. Теперь embedded IPv4 разворачивается до проверок (проверено: `http://[::ffff:127.0.0.1]/` → policy_denied).
- **P2 SSE RecursionError**: `_loads_json` (путь SSE-событий и model-list) без depth-guard: глубоко вложенный JSON от провайдера ловил `RecursionError` → непрозрачный `internal_error`. Добавлен pre-parse `_scan_max_json_depth` + `except RecursionError` → честный `invalid_payload`.
- Инкрементальный byte-cap на SSE-накопление arguments: **отклонён** — ломает зафиксированный контракт B5LP-тестов (накопление с проверкой только в `build()` — документированная семантика `test_b5lp_raw_byte_limit_plus_one_rejected`, который ожидает успех `feed` и отказ `build`). SSE-бюджет (2048 событий × 16 KiB) остаётся общей границей.

### Rust

- **P1 orphan `.partial` disk exhaustion**: Range-resume ветка в `download_to_partial` недостижима (job_id уникален на попытку), при «resumable» отказе partial сохраняется, а `cleanup_stale_partials` чистил только `.runtime-staging` → осиротевшие partial до 128 ГБ каждый копились вечно. Добавлен свип `.partial` старше 24 ч (по `modified()`), имя валидируется `is_owned_partial_name` (artifact_acquisition.rs).
- **P2 DownloadRegistry unbounded growth**: `start_custom` valid-model path вставлял completed job без `registry.prune()` — каждое обращение к уже-валидной custom-модели росло реестр. Добавлен `prune()` (как в остальных путях).
- **P2 grant workspace binding**: `secure_fs::execute_broker_mutation` и `cu_broker::execute_broker_action` не сверяли `grant.workspace` с caller-переданным workspace (defense-in-depth разрыв для будущих callers). Добавлены проверки равенства (workspace_mismatch → blocked/error). Тесты cu_broker обновлены: тестовый грант `workspace: "ws"` + колл-сайты передают `Some("ws")`, зеркалируя прод-caller.
- **P2 skills/lsp env override в release** (SEC-2 хвост): `LOCALCOMET_TEST_PYTHON`, `LOCALCOMET_SKILLS_CLI_PATH`, `LOCALCOMET_LSP_SERVER_PATH` выбирали исполняемый интерпретатор/сервер/CLI в release-сборках — same-user env-переменная могла подменить исполняемое. Все три оверрайда обёрнуты в `#[cfg(debug_assertions)]` (та же политика, что supervisor.rs). Дополнительно: passthrough `LOCALCOMET_TEST_PROJECT_ROOT`/`LOCALCOMET_TEST_PYTHON` в child-env skills CLI — debug-only; сырой stdout CLI в ошибке UI обрезан до 256 байт; `skills_compile` отвергает arguments > 16384 байт до спавна (Windows cmdline 32767).
- **P2 lsp.rs read_framed OOM**: `read_line` буферизовал неограниченную строку заголовка до проверки лимита. Переписано на побайтовое чтение с жёстким капом `MAX_HEADER_BYTES` до выделения памяти.
- P3 `lsp_diagnostics` без привязки к confirmed workspace, P3 rotation `acquisition-events.jsonl` — **зафиксированы, не чинились** (требуют продукт-решения/крупнее правка).

### Инфраструктура гейтов

- **check_import_closure.py**: `modules/browser.py` и `modules/files.py` — shipped, но вне closure и вне EXCLUDED_LEGACY → advisory FAIL (EXIT=0 до фикса). Добавлены в EXCLUDED_LEGACY (тест-only импортеры: test_files_safe_path, test_sec_files_native_isolated_fixture; легаси-кластер browser_operator/browser_task_runner, тянущийся из agents/, вне closure). Гейт теперь: `OK: import closure of 58 modules covered by manifest and shipped (114 legacy excluded, 16 known-unshipped pinned)`.

### Проверено и чисто (без правок)

- system.time: WorkspacePolicy конструируется до диспетча; read_only согласован с реестром. Unreachable-статус подтверждён: нейзвестный CommandFamily → `unknown_tool` на approval-границе (fail-closed, не эксплуатируется).
- secure_fs primitives, files.rs, terminal_runner (allowlist, no-shell, job-object), hf_catalog (host pinning, no redirects), gguf_metadata, approval token lifecycle (single-consume, tombstone, idempotency) — чисто.
- web.fetch redirects полностью запрещены (`_NoRedirectHandler`), DNS-pinning через `_PinnedHTTP(S)Connection`, порты 80/443, креденшелы отклонены.
- skills.invoke permissions реально проверяются против манифеста; timeout 30с применяется (оговорка о внуках — открытым пунктом не ставится, Job Object — будущий харденинг).
- schema-парность Python↔Rust: seconds 0.1..30.0, max_steps 1..8, seed/max_tokens 1..8192 — идентичны на трёх сторонах.

## Изменённые файлы

- modules/local_model_gateway_ru.py (TOOL_REGISTRY, enum, _loads_json depth guard)
- modules/tool_execution_ru.py (web.search cache shape, IPv4-mapped/6to4 unwrap)
- desktop/localcomet-desktop/src-tauri/src/artifact_acquisition.rs (orphan partial sweep, registry.prune)
- desktop/localcomet-desktop/src-tauri/src/cu_broker.rs (grant workspace check)
- desktop/localcomet-desktop/src-tauri/src/secure_fs.rs (grant workspace check)
- desktop/localcomet-desktop/src-tauri/src/skills.rs (debug-only overrides, stdout bound, arguments cap)
- desktop/localcomet-desktop/src-tauri/src/lsp.rs (debug-only override, bounded header read)
- scripts/check_import_closure.py (EXCLUDED_LEGACY +2)

Бандл синхронизирован: `launch_localcomet_dev.py --stage-only` + ручная копия в LocalCometDev workspace (bundle parity 423 OK в обеих локациях).

## Гейты после правок (последние строки дословно)

- `npm run check` → `svelte-check found 0 errors and 0 warnings`
- `npm test` → `Tests 537 passed (537)`
- `cargo test` → `test result: ok. 777 passed; 0 failed; 7 ignored`
- `cargo fmt --check` → FMT_OK
- `cargo clippy --all-targets --all-features -- -D warnings` → Finished (0 warnings)
- `python scripts/check_command_parity.py` → `OK: 79 commands registered and invoked (parity holds)`
- `python scripts/check_tool_risk_registry.py` → `OK: 7 console tool function(s)...; 11 sidecar tools covered; 21 registry entries valid`
- `python scripts/check_ui_fake_state.py` → `OK: no fake-state violations in 111 frontend file(s) (INV-UI-001)`
- `python scripts/check_bundle_parity.py` → `OK: 423 shipped module(s) match source across 2 location(s)`
- `python scripts/check_import_closure.py` → `OK: import closure of 58 modules... (114 legacy excluded, 16 known-unshipped pinned)`
- `python tools/test_adr015_tool_parsing.py` → `OK (skipped=1)`
- `python tools/test_bug1_inference_bundle_parity.py` → `ALL OK`
- `python tools/test_tool_risk_rust_parity.py` → `OK: parser self-tests passed`
- `python scripts/smoke_test.py --mode=cli` → `SMOKE PASSED: real sidecar product path behaves as expected.`
- `python scripts/check_real_sidecar_tests.py` (с CI env) → `OK: real-sidecar tests ran under require mode with no silent skips`
- `python scripts/refresh_evidence.py` → `evidence refreshed: all gates green`
- `python scripts/check_evidence_provenance.py` → `OK: 4 evidence file(s) fresh and intact (tree=714f6a752cb89998...)`

## Не сделано (честно)

- FE-аудиторский агент ещё не вернулся к моменту промежуточной фиксации; его находки будут применены отдельным кластером.
- P3: lsp_diagnostics workspace-binding, acquisition-events.jsonl ротация, skills stdout-streaming через Popen+Job Object, контекстный бюджет gateway, дедупликация tool_call_id истории — backlog, требуют отдельных кластеров/решений владельца.
- Известные открытые P0 прошлых аудитов (signed updater, очередь задач, персистентность сессий) — вне скоупа этого прогона.
