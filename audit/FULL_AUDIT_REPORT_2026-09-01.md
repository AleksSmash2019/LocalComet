# ОТЧЁТ: Полный детализированный аудит LocalComet — 2026-09-01

- **Объект:** `C:\Users\DNS\Documents\LocalComet-build-week-clean`, ветка `feat/up00-wp01-windows-one-click-launch`, HEAD `fd4b100` + незакоммиченный WIP.
- **Режим:** read-only аудит; приложение не запускалось; системный CPython 3.14 (`py -3.14`); все прогоны — собственные, логи в `%LOCALAPPDATA%\Temp\localcomet_audit_20260901\`.
- **WIP на момент аудита:** 17 modified + 6 untracked (меню-своп AppMenuBar, StartupScreen, брендинг, gguf_metadata.rs, secure_fs.rs + broker-перехват files.*, ACL-фиксы skills, error-reasons фронтенда, машинно-регенерированный comtypes-кэш).

---

## 1. Executive summary

- Все гейты батареи зелёные **кроме одного**: `scripts/check_bundle_parity.py` — exit 1, «441 match, 2 stale»: машинно-регенерированный кэш `modules/_vendor/comtypes/gen/_944DE083_..._0_1_0.py` (mtime 2026-09-01 22:20:55, в окне аудита) разошёлся с бандлом. Это freshness-дефект синхронизации, не кода.
- WIP-слой качественный: `secure_fs.rs` — корректный TOCTOU-closed дизайн (NT handle-relative + OBJ_DONT_REPARSE + final-path реверификация), тесты покрывают junction/traversal/NUL/stream; ACL-добавки точно соответствуют фронтенду; i18n ru/en байт-паритет (937=937 ключей, 0 расхождений); `gguf_metadata.rs` — bounded, панико-безопасный.
- Главный риск: **нативное Win32-меню удалено в WIP** — канонический критерий 9.5 «нативное меню» на WIP-дереве более не выполняется; решение владельца не оформлено.
- Evidence-заявки fd4b100 подтверждены: native E2E 12/12 (`isolated_hidden_summary.json`: verified_success=12, model_ready=true), installer SHA-256 `5fce2524…b1bac` совпал с диском.
- Обоснованный скор **сейчас**: fd4b100 — 9.5 подтверждена; **WIP-дерево — 9.0** (меню-критерий снят, native revalidation WIP нет, installer не из этого дерева).

---

## 2. Состояние гейтов

| Гейт | exit | Ключевой вывод (дословно) |
|---|---:|---|
| `npm run check` | 0 | `svelte-check found 0 errors and 0 warnings` |
| `npm test` | 0 | `Tests 565 passed (565)` / `Test Files 40 passed (40)` |
| `cargo test --lib -- --test-threads=1` | 0 | `test result: ok. 766 passed; 0 failed; 7 ignored` |
| `cargo fmt --check` | 0 | ok |
| `cargo clippy --all-targets --all-features -- -D warnings` | 0 | ok (приватный `CARGO_TARGET_DIR=%LOCALAPPDATA%\Temp\localcomet-clippy-audit` — независимое воспроизведение по регламенту, т.к. общий target может удерживаться чужим cargo-процессом) |
| `py -3.14 -m pytest tests/ -q` (изолированный basetemp) | 0 | `399 passed, 1 skipped, 2 warnings, 15 subtests passed in 22.25s` |
| `tests/test_check_bundle_parity.py`, `test_evidence_model.py`, `test_trust_chain_gate.py`, `test_tool_risk_registry_gate.py`, `test_mockdata_import_gate.py`, `test_trust_chain_invariants.py` | 0 | все OK |
| `scripts/check_command_parity.py` | 0 | `OK: 79 commands registered and invoked (parity holds)` |
| `scripts/check_tool_risk_registry.py` | 0 | `OK: 7 console tool function(s) classified (5 mutating, all requiring approval); 11 sidecar tools covered; 21 registry entries valid` |
| `scripts/check_ui_fake_state.py` | 0 | `OK: no fake-state violations in 116 frontend file(s) (INV-UI-001)` |
| `scripts/check_mockdata_imports.py` | 0 | `OK: all 5 imports are in the allowlist` |
| `scripts/check_bundle_parity.py` | **1** | `2 location(s) checked: 441 match, 2 stale, 0 missing in repo, 0 missing in shipped` |
| `tools/test_bug1_inference_bundle_parity.py` | 0 | OK |
| `tools/test_adr015_tool_parsing.py` | 0 | `Ran 72 tests … OK (skipped=1)` |
| `tools/test_tool_risk_rust_parity.py` | 0 | `OK: Rust risk_level_for_tool matches tool_risk_levels.toml (21 tools)`; `OK: Rust REGISTERED_MODEL_TOOLS matches Python TOOL_REGISTRY (11 tools)` |
| `scripts/smoke_test.py --mode=cli` | 0 | `Results: 8 passed, 0 failed` |
| `check_real_sidecar_tests.py` (require-режим, системный python.exe) | 0 | `OK: real-sidecar tests ran under require mode with no silent skips` |
| `scripts/refresh_evidence.py` | 0 | `evidence refreshed: all gates green`, tree=`7449d5db08647c74…` |
| `scripts/check_evidence_provenance.py` | 0 | `OK: 4 evidence file(s) fresh and intact (tree=7449d5db08647c74...)` |

Примечания:
- Первый прогон скриптов был артефактом вызова (`py -3.14 python tests/...` — слово `python` ушло аргументом); перевыполнен корректно.
- Evidence tree изменился с заявленного в Vault `b8e977e0` на `7449d5db` — `refresh_evidence.py` входит в батарею и переписал evidence при прогоне аудита; provenance зелёный.

---

## 3. Findings

### AUD-001 · P1 · observed — Bundle-parity красный: машинно-регенерированный comtypes-кэш разошёлся с поставкой
- Evidence: `scripts/check_bundle_parity.py` exit 1, `FAIL: [build-source] STALE vendor file: _vendor\comtypes\gen\_944DE083_…py` ×2; mtime источника 2026-09-01 22:20:55 против бандла 15:29. SHA источника `60e6470f…`, shipped/deployed `5d185f62…`. Оба варианта кэша удовлетворяют импортам `UIAutomationClient.py` (602 имени; единственный внешний `tagRECT` приходит из `ctypes.wintypes`, строка 10 кэша). `@AutomationLog.txt` (12.8 КБ, «module 'comtypes' has no attribute 'gen'») регенерируется теми же прогонами.
- Суть: любой импорт `uiautomation` (pytest, hidden-tools) может перегенерировать кэш под typelib машины → parity падает до ручного byte-resync в обе локации. Регламент известен, но гейт ловит это пост-фактум, а в Status.md на 12:22 он был зелёным.
- Рекомендация: byte-copy в обе локации (`desktop/localcomet-desktop/src-tauri/binaries/app/modules/` и `%LOCALAPPDATA%\LocalCometDev\workspace\modules/`) перед коммитом; затем решить владельцу — коммитить машинный кэш (как `fd4b100`) или вынести политику регенерации в гейт. Часы: 0.5.

### AUD-002 · P1 · observed — 81 файл `modules/*.py` не входит ни в поставку, ни в `up00-runtime-manifest.json`
- Evidence: на диске 251 `.py` (без `__pycache__`); shipped `binaries/app/modules` — 170; manifest `sourceFiles` покрывает 117 модулей + docs/license/vendor; пересечение «не shipped и не в manifest» = 81 (`modules/ai_agent_core_ru.py`, `modules/browser.py`, `modules/automation_center.py`, …). Entrypoint `tools/run_localcomet_desktop_sidecar.py` ни один из них не импортирует.
- Суть: manifest описывает scope поставки (согласовано: installer extract-parity = 117 module files), но **не существует гейта**, который поймает класс SKILL-BUNDLE-01 — «shipped-код импортирует модуль, отсутствующий в бандле». `check_bundle_parity` проверяет byte-parity перечисленного, а не полноту import-closure.
- Рекомендация: гейт import-closure (AST-обход от entrypoint + skills) против manifest; либо явный exclusion-list legacy. Часы: 4–8.

### AUD-003 · P2 · observed — Мёртвый фронтенд-путь `execute_approved`
- Evidence: `src/lib/bridge/approval.ts:105` экспортирует `executeApproved` (invoke `execute_approved`); единственный потребитель — `tests/p0b-r5-approval-contract.test.ts:372`; в проде — ноль вызовов. Rust-команда существует (`approval_commands.rs:821`) и **не включена в ACL** (нет в `capabilities/main.json`/permission-sets) — реальный invoke был бы отклонён (fail-closed, дыры нет).
- Рекомендация: удалить экспорт+тест или перевести контрактный тест на mock; пометить команду как internal-only. Часы: 1.

### AUD-004 · P2 · candidate — Hardlink-лист как класс обхода в `secure_fs.rs`
- Evidence: `secure_fs.rs:632-692` (`write_file`) проверяет reparse/offline-атрибуты и final-path, но не проверяет `nNumberOfLinks > 1` из `BY_HANDLE_FILE_INFORMATION` (рутина `handle_attributes` уже читает эту структуру). Пре-существующий hardlink workspace-файла на внешний объект прошёл бы verification и запись пошла бы в общий inode.
- Суть: не воспроизведено; для эксплуатации нужен hardlink, созданный тем же пользователем вне broker-инструментов (мутирующих tools для hardlink в контракте нет) — эскалации привилегий нет, но инвариант «мутации строго внутри workspace» нарушим.
- Рекомендация: отказ при `nNumberOfLinks > 1` для write/delete + тест. Часы: 2–4.

### AUD-005 · P2 · observed — Нативное Win32-меню удалено в WIP; канон-заявка на WIP-дереве недействительна
- Evidence: `git diff …/lib.rs` — удалён весь блок `native_menu_setup` (был: коммит `25c38e7`, live-доказательство `GetMenu PRESENT(3)`); заменён `AppMenuBar.svelte` внутри WebView (`AppShell.svelte:182`). Status.md это честно фиксирует («нативное Win32-меню удалено в WIP»), но критерий score «собственное нативное меню» формально снимается.
- Рекомендация: оформить решение владельца (отказ от критерия или возврат меню) до коммита. Часы: 0 (решение) / 2–4 (откат).

### AUD-006 · P2 · observed — Stale-дубликат installer в `LocalComet-final-deliverables`
- Evidence: `C:\Users\DNS\Documents\LocalComet-final-deliverables\LocalComet_6.84.6_x64-setup.exe` — 14 683 523 B, SHA-256 `3f6817916d2d63e919e1c3bd52aa64c43bb366feffe5167305082f6c78205d77`, mtime Aug 16; актуальный `target/up00-wp01/cargo-target/release/bundle/nsis/…` — 15 385 860 B, SHA `5fce25242572bd8512fe0b35d358bbccf2d05663d5d116bdae03db0b576b1bac` (совпал с Vault, mtime 2026-08-31 16:37). Одно имя файла — два разных артефакта.
- Рекомендация: перезаписать/пометить deliverables после пересборки; перед релизом сверять SHA. Часы: 0.5.

### AUD-007 · P3 · observed — Счётчики Status.md от более раннего состояния WIP
- Evidence: Vault 12:22 заявляет vitest 558 / cargo lib 756; прогон аудита на том же дереве — 565 / 766 (разница = WIP-тесты `app-menu-bar.test.ts` +6, `model-gateway.test.ts` +2, Rust `secure_fs`/`gguf_metadata`/`managed_runtime`). Python 399/1 — совпал. Не расхождение фактов, а несвежая база.
- Рекомендация: обновить Status после parity-resync. Часы: 0.2.

### AUD-008 · P3 · observed — Мелочи качества
- `permissions/skills.toml` без завершающего `\n` (размер 949 байт).
- `tests/componentSmoke.test.ts` — бессмысленный `const unknown = render(MessageList, {}).body; // placeholder to keep render count stable`.
- `AGENTS.md` устарел: 58 команд против фактических 79 по `check_command_parity`.
- Часы: 0.5 суммарно.

### AUD-009 · P3 · candidate — `system.time` отсутствует в Rust `risk_level_for_tool`
- Evidence: `system.time` есть в TOML (read_only, `security/invariants/tool_risk_levels.toml:150`) и в Python `SUPPORTED_TOOLS` (`tool_execution_ru.py:47`, обработчик `:1074`), но в `approval_commands.rs:409` (`risk_level_for_tool`) его нет → вызов через `run_tool_call` получил бы `unknown_tool` (fail-closed). Обычный путь исполнения — sidecar; трассировку не завершил. Паритет-гейт это пропускает, потому что сравнивает Dangerous/Guarded-множества строго, а read_only — только как «не попал в mutating».
- Рекомендация: трассировать + добавить в Rust-маппинг или зафиксировать исключение. Часы: 1–2.

### AUD-010 · P3 · observed — `@AutomationLog.txt` и `audit/FULL_AUDIT_PROMPT_2026-09-01.md` не покрыты `.gitignore`
- Оба — untracked; `audit/*.log` (1.4 ГБ `staged_commit_gates_20260828.log`) игнорируется, а эти два файла — нет. Риск случайного коммита мусора. Часы: 0.2.

### AUD-011 · P3 · observed — `DIR_WALK_ACCESS` шире минимума
- `secure_fs.rs:319` запрашивает `FILE_ADD_FILE|FILE_ADD_SUBDIRECTORY` на всех промежуточных компонентах; в пределах владения workspace, обосновано комментарием в коде. Часы: 0 (принять).

### AUD-012 · P3 · candidate — StartupScreen не зависает при нормальных исходах
- `startupReady = bridgeState !== 'CONNECTING' && gateway.initialized`; оба исхода gateway-init (успех `modelGateway.ts:365`, ошибка `:375`) ставят `initialized=true`; ошибки bridge уходят в ERROR/UNAVAILABLE (`controlPlane.ts:74`). Навсегда оверлей не зависает при нормальных исходах; остаточный риск — только «invoke навсегда висит» (не воспроизведено). Часы: 0.

### AUD-013 · observed (positive) — Approval-контур и границы подтверждены
- Токен consumed до broker-перехвата (`approval_commands.rs:1096` `registry.execute_approved` → grant → `secure_fs::execute_broker_mutation` реверифицирует tool/expiry/digest `secure_fs.rs:789-806`); tombstone-TTL replay-защита (`approval.rs:590-604`); fail-closed fallback `unknown_tool`.
- Sidecar-мутации остались `feature_disabled` как defense-in-depth (`tool_execution_ru.py:373-412`; тесты `tools/test_v6846_tool_execution.py` закрепляют контракт).
- IPC: `MAX_FRAME_BYTES=4 MiB` (`ipc.rs:6`), TS `bounded()` лимиты, Python `MAX_STRING_CHARS=1 MiB`; test: frame > MAX rejected (`supervisor.rs:2155`).
- Risk-реестр: TOML 21 запись; `files.write/create_folder` = guarded+approval, `files.delete` = dangerous+approval — соответствует фактическому broker-исполнению после approval.
- Секреты: скан `src/`, `src-tauri/src`, `modules/`, `core/`, `agents/` — ключей/токенов/`.pem`/`.key` в репо не найдено.

---

## 4. WIP-приёмка

| Блок | Вердикт | Обоснование |
|---|---|---|
| `secure_fs.rs` + перехват `files.*` в `approval_commands.rs` | **accept-with-fixes** | Handle-relative/no-reparse логика корректна (NT-имена мимо Win32-нормализации, OBJ_DONT_REPARSE, attribute+final-path реверификация ДО усечения; non-Windows fail-closed; recursive delete структурно невозможен). Grant реверифицируется. Обходного пути мимо approval не найдено. Тесты: junction-компонент/лист, traversal/UNC/drive-relative/NUL/stream, kind-mismatch, missing-root — доказательные. Фиксы: AUD-004 (nLink), AUD-011 (опционально). |
| ACL-фиксы (`capabilities/main.json`, `permissions/skills.toml`) | **accept** | Полная карта: 32 FE-invoke → permission-sets покрывают все; новые `allow-skills-*` точно соответствуют `skillsStore.ts` invoke'ам; излишков не обнаружено. Nit: EOF-newline (AUD-008). |
| AppMenuBar/StartupScreen/+page.svelte | **accept-with-fixes** | a11y корректно (menubar/aria-expanded/Escape/Tab/Home/End, prefers-reduced-motion), i18n полная (937=937, used-but-missing: NONE), layout-сдвиг grid согласован (`--app-menubar-height`, ConversationSidebar grid-row 2, drawer/panel top-смещения). Фиксы: владелец должен закрыть AUD-005 (судьба нативного меню). Поведение при ошибке инициализации — оверлей скрывается (AUD-012). |
| `gguf_metadata.rs` + рекомендательная система | **accept** | Bounded reader: все чтения через Option-cursor, капы KV/строк/массивов (MAX_READ 32 MiB, MAX_KV 16384, MAX_STRING 4 MiB, MAX_ARRAY 4M), паника на битом файле невозможна; тесты v2/v3/garbage/truncation/bad-version. VRAM — из device-probe summary; probe-failure честно → None (не «CPU»). Типы Rust↔TS согласованы (валидатор exact-record, bounds 1024/99/131072); приоритет prefs над профилем согласован с «Применить»; auto-fit-ctx только для pure-auto GPU. |
| error-reasons (MessageList/modelGateway/i18n) | **accept** | Whitelist-коды → i18n-подсказки `chat.reason.*`, приватные данные не протекают (тест: `private.example`/`token` скрыты), en/ru паритет. |
| Тесты WIP | **accept-with-fixes** | +7 FE, +~10 Rust — в основном доказательные (валидация payload, junction-поведение, honest created flag). Слабые: source-inventory assertions в `app-menu-bar.test.ts` «закрепляют текст», не поведение; placeholder-render (AUD-008). |
| comtypes-кэш в WIP | **reject как ручной правке** | Машинная регенерация в окне аудита; решать byte-resync/политику (AUD-001), не коммитить «как есть» без сверки обеих локаций. |

---

## 5. Карта ACL (фронтенд-вызов → разрешение → статус)

Полная карта (32 invoke): все покрыты permission-sets.

| Группа FE-вызовов | Разрешение | Статус |
|---|---|---|
| `request_approval`, `resolve_tool_approval`, `run_tool_call`, `cu_broker_observe`, `cu_broker_continuation_consume/complete/revoke`, `intent_compile` | `allow-request-approval` (multi-set) | OK |
| `checkpoint_list/compare/restore_approval/restore_files/restore_task` | `allow-checkpoints` | OK |
| `coding_start_approval/start/events/list_tasks/recover_task/cancel` | `allow-coding` | OK |
| `skills_list/install/enable/disable/uninstall/compile` | `allow-skills-*` (6 отдельных, добавлены в WIP) | OK — синхронно с `skillsStore.ts` |
| `managed_*`, `model_*`, `knowledge_*`, `hf_*`, files-select, `lsp_diagnostics`, `speak_local_text`, `stop_local_text`, … | индивидуальные `allow-*` | OK |
| `execute_approved` | **нет ACL** | OK-fail-closed; прод-вызовов нет (AUD-003) |

Минимальность: не найдено разрешений без соответствующего вызова среди новых; pre-existing индивидуальные `allow-*` без прямого invoke (например `allow-scan-hardware` — вызов через обёртки bridge) — не помечено нарушением.

---

## 6. Score verification (заявленные критерии 9.5)

| Критерий | Evidence | Вердикт |
|---|---|---|
| Native E2E 12/12 | `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/notepad_e2e_20260831_reboot/isolated_hidden_summary.json`: `requested 12, submitted 12, verified_success 12, blocked 0, errors 0, model_ready true`; `isolated_launch.json` (desktop `LocalCometHiddenCU_3264`, port 1423, CU enabled), `isolation_selfcheck.json` присутствуют | **Подтверждено**, fd4b100, 31.08 (файлы класса A; прогоны не повторял — запрещено аудиту) |
| Stop→revoke→replay, restart recovery, coding seam | отчёты/артефакты 27–31.08, Vault Status/Timeline | Подтверждено как **класс B** (файлы есть, сам не перезапускал) |
| Нативное Win32-меню | код удалён в WIP (`lib.rs` diff) | **Недействительно на WIP** (AUD-005); верно только для fd4b100 |
| Installer provenance | SHA-256 `5fce2524…b1bac` совпал с диском (`target/up00-wp01/cargo-target/release/bundle/nsis/`), собран 31.08 из fd4b100, extract-parity 7z (117 module files), gates в packaged workspace 556/745 | **Подтверждено** для fd4b100; для WIP-дерева installer устареет при коммите |
| Лицензия/NOTICE | корневой MIT присутствует; `docs/THIRD-PARTY-NOTICES-rust.md` — 486 записей, включая `windows-sys | 0.61.2` после новых Wdk/IO фич | **Подтверждено** (npm-143 не пересчитывал построчно) |
| Latency/footprint | отчёты Vault (движковый бенчмарк 31.08: load 1.53s/TTFT 0.030s/309.5 tok/s; 2ч soak 238 запросов) | Класс B, не воспроизводил |
| Паритет-гейты | см. раздел 2 | Зелёные, **кроме** bundle-parity (AUD-001) |

**Честный вердикт по шкале:** fd4b100 — 9.5 обоснована. **WIP-дерево — 9.0**: меню-критерий снят (−0.5 по той же логике score-cap), автоматические гейты зелёные, native revalidation WIP отсутствует, релизный артефакт не соответствует дереву.

---

## 7. Чеклисты

### Перед коммитом WIP
1. Byte-resync comtypes-кэша в `binaries/app/modules` и `%LOCALAPPDATA%\LocalCometDev\workspace\modules` → `check_bundle_parity` зелёный (AUD-001).
2. Решение владельца по нативному меню (AUD-005) — зафиксировать в Vault.
3. Опционально до коммита: nLink-check в `secure_fs.rs` (AUD-004), удаление `executeApproved` (AUD-003), EOF-newline skills.toml (AUD-008).
4. Полная батарея гейтов заново + `refresh_evidence`/`check_evidence_provenance`; в отчёт — дословные последние строки.
5. Обновить Status.md (счётчики 565/766, новый evidence tree) и AGENTS.md (79 команд).
6. Добавить в `.gitignore` `@AutomationLog.txt` (AUD-010).

### Перед публичным релизом
1. Пересобрать installer **из закоммиченного дерева**, обновить SHA в Vault, перезаписать stale-копию в `LocalComet-final-deliverables` (AUD-006), повторить 7z extract-parity.
2. Native acceptance на финальном дереве (минимум: E2E-повтор, меню/меню-замена live, Stop→revoke→replay) — WIP её не имеет.
3. Гейт import-closure против manifest (AUD-002) — чтобы поставка не разошлась с кодом.
4. Owner: ревью формулировки MIT, npm-notices 143, clean-machine parity.

### Предложения по новым гейтам
- (а) import-closure sidecar vs manifest — ловит класс AUD-002 автоматически;
- (б) сверка «evidence tree ≠ Status tree» — ловит несвежие канон-заявки (AUD-007);
- (в) константный тест, что `risk_level_for_tool` покрывает все TOML-имена — закроет AUD-009;
- (г) гейт «shipped-кэш comtypes == source после любого pytest-прогона» (или перенос uiautomation-импортов в изолированный процесс с фиксацией typelib-кэша).

---

## 8. Приложения — дословные команды (воспроизводимость)

```
git status --porcelain                    # 17 M + 6 ?? (WIP-слой)
git log --oneline -20                     # HEAD fd4b100 …

cd desktop/localcomet-desktop
npm run check                             # exit 0; svelte-check found 0 errors and 0 warnings
npm test                                  # exit 0; Tests 565 passed (565)

cd src-tauri
cargo test --lib -- --test-threads=1      # exit 0; 766 passed; 0 failed; 7 ignored
cargo fmt --check                         # exit 0
CARGO_TARGET_DIR=%LOCALAPPDATA%\Temp\localcomet-clippy-audit \
  cargo clippy --all-targets --all-features -- -D warnings   # exit 0

cd <repo>
py -3.14 -m pytest tests/ -q --basetemp=%TEMP%\localcomet_audit_20260901\pytesttmp
                                          # exit 0; 399 passed, 1 skipped

for t in tests/test_check_bundle_parity.py tests/test_evidence_model.py \
         tests/test_trust_chain_gate.py tests/test_tool_risk_registry_gate.py \
         tests/test_mockdata_import_gate.py tests/test_trust_chain_invariants.py \
         scripts/check_command_parity.py scripts/check_tool_risk_registry.py \
         scripts/check_ui_fake_state.py scripts/check_mockdata_imports.py \
         tools/test_bug1_inference_bundle_parity.py tools/test_adr015_tool_parsing.py \
         tools/test_tool_risk_rust_parity.py; do py -3.14 "$t"; done
                                          # все exit 0

py -3.14 scripts/check_bundle_parity.py   # exit 1; "441 match, 2 stale"  ← AUD-001
py -3.14 scripts/smoke_test.py --mode=cli # exit 0; "8 passed, 0 failed"

LOCALCOMET_REQUIRE_REAL_SIDECAR=1 \
LOCALCOMET_TEST_PROJECT_ROOT=C:\Users\DNS\Documents\LocalComet-build-week-clean \
LOCALCOMET_TEST_PYTHON=C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe \
  py -3.14 scripts/check_real_sidecar_tests.py   # exit 0

py -3.14 scripts/refresh_evidence.py      # exit 0; tree=7449d5db08647c74...
py -3.14 scripts/check_evidence_provenance.py   # exit 0; 4 evidence files fresh and intact

# Installer provenance:
py -3.14 -c "import hashlib;print(hashlib.sha256(open(r'target/up00-wp01/cargo-target/release/bundle/nsis/LocalComet_6.84.6_x64-setup.exe','rb').read()).hexdigest())"
# → 5fce25242572bd8512fe0b35d358bbccf2d05663d5d116bdae03db0b576b1bac == Vault claim: True

# Native E2E evidence (чтение, не прогон):
Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/notepad_e2e_20260831_reboot/isolated_hidden_summary.json
# → {"requested_cases":12,"submitted":12,"verified_success":12,"blocked":0,"errors":0,"model_ready":true}
```

---

## Что НЕ сделано и почему

- Native/hidden запуски, Computer Use сценарии, Calculator — запрещены промтом аудита (заявки fd4b100 приняты как класс B с файлами-evidence).
- npm-notices (143 пакета) не пересчитывал построчно — проверена полнота Rust-нотисов после новых Wdk/IO фич.
- Полный dead-code анализ 251 модуля `modules/` за пределами shipped-scope не выполнялся (класс зафиксирован в AUD-002, полный список — отдельная задача).
- pytest legacy git-index failures не трогал (нет мандата на ремонт в read-only аудите).
