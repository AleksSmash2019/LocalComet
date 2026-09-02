# LocalComet — независимый аудит, 2026-09-01

- Репозиторий: `C:\Users\DNS\Documents\LocalComet-build-week-clean`
- Ветка: `feat/up00-wp01-windows-one-click-launch` (единственная)
- HEAD: `fd4b100ac04ef4809615f646291f8b64879616af` + WIP
- Python: системный CPython `3.14.6` (`C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe`)
- Режим: read-only. Исходники не изменялись, коммитов/веток не создавалось, ничего не удалялось.

---

## 1. Executive summary

WIP-слой инженерно крепкий: `secure_fs.rs` — лучший код в репозитории (handle-relative, `OBJ_DONT_REPARSE`, RAII, честные коды ошибок), `gguf_metadata.rs` — panic-safe и bounded, i18n сбалансирован (975/975), ACL не имеет протечек и висячих разрешений.

Но **дерево сейчас красное**, и это прямо противоречит записи в Vault от 12:22 сегодня («все 21 гейт зелёные с первого прогона»). Зафиксировано **4 красных гейта**: `cargo test --lib` (4 теста), `check_bundle_parity`, `refresh_evidence`, `check_evidence_provenance`.

Главный риск не в безопасности, а в **честности состояния**: `secure_delete` сообщает об успешном удалении непустой папки, и сплэш-экран может перекрыть приложение навсегда из-за отсутствия таймаутов на уровень ниже.

**Обоснованный скор: 8.0/10**, а не 9.5. Скор 9.5 опирается на native-приёмку дерева `fd4b100`; WIP её не проходил (меню-своп удалил один из критериев 9.5 — нативное Win32-меню), а автоматическая батарея на WIP-дереве красная. Подробнее — раздел 6.

---

## 2. Состояние гейтов

| Гейт | exit | Ключевой вывод |
|---|---:|---|
| `npm run check` (svelte-check) | 0 | `svelte-check found 0 errors and 0 warnings` |
| `npm test` (vitest) | 0 | `Test Files 40 passed (40)`, `Tests 565 passed (565)` |
| `cargo test --lib -- --test-threads=1` | **101** | `762 passed; 4 failed; 7 ignored` |
| `cargo fmt --check` | 0 | чисто |
| `cargo clippy --all-targets --all-features -- -D warnings` | 0 | чисто |
| `py -3.14 -m pytest tests/ -q` | 0 | `399 passed, 1 skipped, 15 subtests passed` |
| `tools/test_v6846_tool_execution.py` | 0 | OK |
| `tools/test_bug1_inference_bundle_parity.py` | 0 | OK |
| `tools/test_adr015_tool_parsing.py` | 0 | `Ran 72 tests … OK (skipped=1)` |
| `tools/test_tool_risk_rust_parity.py` | 0 | risk/registry/parsing — совпадают (21 инструмент, 11 sidecar) |
| `scripts/check_bundle_parity.py` | **1** | `2 location(s) checked: 441 match, 2 stale` |
| `scripts/check_command_parity.py` | 0 | `79 commands registered and invoked (parity holds)` |
| `scripts/check_tool_risk_registry.py` | 0 | 7 console + 11 sidecar, 21 запись валидна |
| `scripts/check_ui_fake_state.py` | 0 | `no fake-state violations in 116 frontend file(s)` |
| `scripts/check_mockdata_imports.py` | 0 | OK |
| `tests/test_check_bundle_parity.py` | 0 | `Ran 5 tests … OK` (зелёный при красном реальном гейте) |
| `tests/test_evidence_model.py` | 0 | OK |
| `tests/test_trust_chain_gate.py` | 0 | OK |
| `tests/test_trust_chain_invariants.py` | 0 | `15 trust-chain files pass byte invariants` |
| `tests/test_tool_risk_registry_gate.py` | 0 | OK |
| `tests/test_mockdata_import_gate.py` | 0 | OK |
| `scripts/smoke_test.py --mode=cli` | 0 | `Results: 8 passed, 0 failed` |
| `check_real_sidecar_tests.py` (require) | 0 | `real-sidecar tests ran under require mode with no silent skips` |
| `scripts/refresh_evidence.py` | **1** | `[FAIL] evidence/cargo_test.txt exit=101`, tree=`943306f8…` |
| `scripts/check_evidence_provenance.py` | **1** | `FAIL: NONZERO_EXIT: cargo_test.txt exit_code=101` |

`tree_digest` (текущее дерево): `943306f8deddb2e59be440a2fcf5bd8aa2e5070e7d3c36fc7fb75a2d0daf46df` (608 source files).

---

## 3. Findings

### AUD-001 — P1, reproduced — `secure_delete` сообщает об успехе для непустой папки

- Файл: `src-tauri/src/secure_fs.rs:694-762` (док-контракт `:29-31`, тест `:973`)
- Суть: возвращаемое значение оторвано от фактического результата. Удаление выполняется при закрытии хендла (`:757-758`), и его исход никогда не проверяется.
- Evidence:

```
---- secure_fs::windows_tests::delete_removes_file_and_empty_folder_but_refuses_non_empty_folder stdout ----
thread '...' panicked at src\secure_fs.rs:973:57:
non-empty folder refused: DeleteOutcome { path: "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet-secure-fs-delete-happy-...\full-dir" }
```

  При этом утверждения выше (удаление файла `:964` и пустой папки `:968`) проходят — значит механизм в целом работает, и `SetFileInformationByHandle` для непустой папки вернул успех.
- Последствие: брокер вернёт модели `{"tool":"files.delete","deleted":true}` (`:856-864`) для папки, которая не удалена. Док-блока обещание «a non-empty directory fails with STATUS_DIRECTORY_NOT_EMPTY» — не выполняется. Нарушение класса INV-UI-001 (ложное состояние), не обход approval.
- Честно не определено: удаляет ли NTFS папку в итоге. Определить в этой песочнице не удалось — ctypes-вызов `SetFileInformationByHandle` из Python стабильно отдаёт `ERROR_INVALID_PARAMETER (87)` даже на обычном файле (т.е. мой харнесс сломан, а не ОС), а `Add-Type` в PowerShell заблокирован политикой безопасности. Команда для фиксации: заменить `FileDispositionInfo` на `FileDispositionInfoEx` (class 21) с явной проверкой после `CloseHandle`, либо проверять пустоту каталога до установки disposition.
- Рекомендация: использовать `FILE_DISPOSITION_INFO_EX` + `FILE_DISPOSITION_FLAG_ON_CLOSE`/верификация пост-фактум, либо явно рекурсивно проверять emptiness.
- Часы: 2-3

### AUD-002 — P1, observed — `check_bundle_parity` красный: vendor-кэш рассинхронизирован

- Evidence:

```
FAIL: [build-source] STALE vendor file: _vendor\comtypes\gen\_944DE083_8FB8_45CF_BCB7_C477ACB2F897_0_1_0.py
FAIL: [deployed]    STALE vendor file: _vendor\comtypes\gen\_944DE083_8FB8_45CF_BCB7_C477ACB2F897_0_1_0.py
2 location(s) checked: 441 match, 2 stale, 0 missing in repo, 0 missing in shipped
Shipped sidecar is out of sync with source; refresh the bundle.   (exit 1)
```

- Причина — не только переводы строк, есть и реальный дрейф содержимого:

```
worktree : 315854 bytes, CRLF 9225, bare LF 0
HEAD     : 306652 bytes, CRLF 0,    bare LF 9230
equal ignoring CR: False        byte-identical: False
```

- Файл уже был `M` в `git status` в начале аудита (22:16), mtime — `2026-09-01 22:20:55` (внутри окна аудита), тогда как все соседние файлы в каталоге датируются `2026-08-21`. Конкретный писатель достоверно не установлен: `check_bundle_parity.py` не содержит операций записи (проверено), ни один не-vendor `.py` не упоминает `comtypes` (проверено grep по всему дереву).
- Последствие: deployed-runtime несёт версию HEAD (LF), исходник — CRLF+дрейф. Гейт красный; вся evidence-цепочка за ним тоже красная.
- Рекомендация: закрепить файл (`.gitattributes`: `modules/_vendor/** -text`), перегенерировать согласованно, обновить bundle.
- Часы: 1-2

### AUD-003 — P1, observed — evidence-цепочка красна как следствие AUD-001/002

- `refresh_evidence.py`: `tree_digest: 943306f8…` (608 файлов), `[FAIL] evidence/cargo_test.txt exit=101`, остальные 3 evidence OK → exit 1.
- `check_evidence_provenance.py`: `FAIL: NONZERO_EXIT: cargo_test.txt exit_code=101` → exit 1.
- Положительно: механизм evidence честно отказывается «зеленить» красный `cargo test`. Это корректное поведение, а не баг.
- Расхождение с базой: `AGENTS.md` фиксирует tree `82ea233e90459bf8…`, Vault — `b8e977e0…`. Текущий `943306f8…` — всё основное evidence (native E2E 12/12) относится к **другому** дереву.
- Часы: 0 (исправится вместе с AUD-001/002)

### AUD-004 — P1, candidate — сплэш-экран может перекрыть приложение навсегда

- Файлы: `src/routes/+page.svelte:8`, `src/lib/components/startup/StartupScreen.svelte:25-42`
- Условие: `startupReady = $controlPlaneBridgeState !== 'CONNECTING' && $modelGatewayStore.initialized`
- `initialized` выставляется в `true` только в ветках success (`stores/modelGateway.ts:365`) или catch (`:375`) внутри `initializeModelGateway()`. Если await не сеттлится — остаётся `false` навсегда.
- Оверлей: `position: fixed; inset: 0; z-index: 1000` — весь экран, нет кнопки закрытия, нет текста ошибки, нет таймаута.
- Ключевое наблюдение: **в слое `lib/bridge/*.ts` нет ни одного `setTimeout` / `AbortController` / `Promise.race`** (проверено grep) — таймаутов на invoke не существует в принципе.
- Эпистемика: candidate — механизм прослежен по коду, но «зависший invoke» я не воспроизводил (запуск приложения запрещён регламентом аудита).
- Рекомендация: bounded timeout на инициализацию + состояние ошибки/кнопка пропуска на сплэше.
- Часы: 3-4

### AUD-005 — P2, observed — junction-тесты в `secure_fs` зелёные без единой проверки

- `secure_fs.rs:984-987` и `:1010-1013`:

```rust
if !workspace.create_junction("link", &workspace.path("target")) {
    eprintln!("SKIP prerequisite: mklink /J is unavailable in this test environment");
    return;                       // <- тест завершается без assert
}
```

- На машине без прав на создание junction (или не-NTFS) оба теста проходят, не проверяя ничего — при том что это ровно те два теста, которые доказывают защиту от junction-эскалации.
- Рекомендация: падать, а не возвращаться; либо `#[ignore(reason = ...)]`.
- Часы: 0.5

### AUD-006 — P2, observed — граница `execute_broker_mutation` не покрыта тестами

- `secure_fs.rs:777-870` — ре-верификация grant (совпадение tool, expiry, `canonical_input_digest`). Это и есть security-граница WIP.
- Все 9 тестов модуля вызывают напрямую `windows_impl::{create_folder, delete, write_file}`; `execute_broker_mutation` не вызывается ни одним тестом.
- Следовательно: нет теста на «нет grant → отказ», «grant для другого tool», «истёкший grant», «digest не совпал».
- Часы: 2

### AUD-007 — P2, observed — `execute_approved`: мёртвый и при этом запрещённый ACL

- Зарегистрирован в `lib.rs`, реализован `approval.rs:461`, вызывается ровно один раз — `src/lib/bridge/approval.ts:112`; функция `executeApproved` не имеет ни одного вызывающего.
- **Не выдан ни одним permission-файлом** (проверено: grep по всем `permissions/*.toml` и `capabilities/*.json` — совпадений нет). Т.е. при реальном вызове Tauri отказал бы по ACL.
- При этом в Rust есть 8 unit-тестов (`approval.rs:1039-1306`), которые гоняют команду, недостижимую из UI и запрещённую ACL. Тесты доказывают корректность недостижимого пути.
- Смежно: `get_model_storage_info`, `open_model_storage_folder` зарегистрированы, permission определены в `control-plane.toml`, но **не выданы** в `main.json` — фичи-зомби.
- Рекомендация: удалить команду и её тесты, либо осознанно подключить и выдать permission.
- Часы: 1

### AUD-008 — P2, observed — 3 unit-теста зависят от состояния хоста

- Падают: `cu_broker::tests::broker_preflight_blocks_unknown_target_without_spawning` (`:2079`), `cu_broker::tests::open_app_rejects_url_field_strict_separation` (`:2468`), `intent_compiler::tests::compiled_open_url_reaches_url_validation` (`:706`) — все на `validate_broker_action("open_url", …).is_ok()`.
- Механизм подтверждён кодом: `plan_launch` → `resolve_program` (`:481-508`) → `registry_default_value` → `Command::new(r"C:\Windows\System32\reg.exe")` (`:514`). Браузеры (chrome/msedge/firefox) резолвятся **только** через реестр.
- В этой песочнице `reg.exe` заблокирован политикой: `PROGRAM BLOCKED BY SECURITY POLICY - reg.exe`. То есть 3 из 4 падений `cargo test` вызваны окружением аудита, а не дефектом кода.
- Но дефект всё равно есть: unit-тест не герметичен — его результат зависит от того, установлен ли на машине Chrome/Edge/Firefox.
- Рекомендация: инъекция поддельного резолвера программ в тестах.
- Часы: 3-4

### AUD-009 — P2, observed — unit-тест гейта зелёный при красном самом гейте

- `tests/test_check_bundle_parity.py` → exit 0 (`Ran 5 tests … OK`), в то время как `scripts/check_bundle_parity.py` → exit 1.
- Тест гоняет фикстуры, а не реальное дерево, и потому не может поймать реальный рассинхрон.
- Отдельно: детектор «missing files» в этом прогоне не сработал ни разу (`0 missing in repo, 0 missing in shipped`) — значит подтвердить, что он ловит отсутствующие в поставке файлы, данным прогоном нельзя; код счётчики содержит, но путь не упражнялся.
- Часы: 2

### AUD-010 — P2, observed — базовые числа в `AGENTS.md` устарели

| Метрика | AGENTS.md | Факт |
|---|---|---|
| vitest | 398 | **565** |
| cargo lib | 512 passed / 0 failed | **762 passed / 4 failed / 7 ignored** |
| command parity | 58 | **79** |
| INV-UI-001 файлов | 97 | **116** |
| tool risk registry | 19 записей | **21** |

- Часы: 0.5

### AUD-011 — P3, observed — в подсказке об ошибке пользователю отдаётся непереведённый идентификатор

- `MessageList.svelte:113-115`: при попадании в `safeClass` рендерится сырой токен `request_blocked_or_unavailable`, а не i18n-строка. В ru-локали пользователь видит английский идентификатор.
- Приватные данные **не протекают** (проверено специально): вход обрезается до 240 символов, токенизируется, и наружу отдаётся только код из фиксированного allowlist, отображённый в статичную i18n-строку. Сырой текст ошибки никогда не выводится.
- Часы: 0.5

### AUD-012 — P3, observed — `permissions/skills.toml` без завершающего перевода строки

- `git diff`: `\ No newline at end of file` на `:42`.
- Часы: 0.1

### AUD-013 — P2, observed — заявки Vault `Projects/LocalComet/Status.md` не подтверждаются

| Заявка Vault (12:22–12:45) | Факт аудита (22:16–22:35) |
|---|---|
| «все 21 гейт зелёные с первого прогона без ремонтов» | **4 красных**: cargo test, bundle parity, refresh_evidence, provenance |
| «Rust lib 756/0/7» | **762 passed / 4 failed / 7 ignored** |
| «parity 443» (зелёный) | **exit 1, 2 stale** |
| «evidence tree=b8e977e0» | **943306f8…** (другое дерево — ожидаемо) |
| «Vitest 558» | 565 (WIP добавил тесты) |
| Python 399/1, smoke 8/0, real-sidecar OK | **подтверждено** |

Часть расхождения объяснима: запись делалась до того, как дерево изменилось. Но «все 21 гейт зелёные» и «parity» на текущем дереве неверны, и это должно быть исправлено в Vault до принятия решения о коммите.

---

## 4. Приёмка WIP по блокам

| Блок WIP | Вердикт | Обоснование |
|---|---|---|
| `secure_fs.rs` + перехват `files.*` в `approval_commands.rs` | **accept-with-fixes** | Архитектура сильная (handle-relative + `OBJ_DONT_REPARSE`, RAII, валидация компонентов до любого обращения к ОС, grant ре-верифицируется `secure_fs.rs:783-806`). Обход мимо approval не найден: перехват стоит **после** потребления одноразового токена, grant проверяется повторно. Блокирующее: AUD-001, AUD-005, AUD-006 |
| ACL: `capabilities/main.json` + `permissions/skills.toml` | **accept** | Добавлено 6 skills-permission, все 6 команд зарегистрированы и выданы; висячих разрешений нет, неизвестных идентификаторов нет, ни одна команда не вызвана фронтендом без разрешения. Пере-выдачи прав не обнаружено |
| `AppMenuBar` / `StartupScreen` / `+page.svelte` | **accept-with-fixes** | Условие скрытия сплэша логически верное, a11y присутствует (`aria-live`, `aria-label`, `prefers-reduced-motion`), i18n полный. Блокирующее: AUD-004 |
| `gguf_metadata.rs` + рекомендательная система | **accept** | Panic-safe: только `checked_add`/`checked_mul` + `?`, bounded `MAX_READ_BYTES`/`MAX_KV_PAIRS`/`MAX_STRING_BYTES`/`MAX_ARRAY_ITEMS`, вложенные массивы отвергаются, валидация magic+version. VRAM — из device-probe, при отсутствии подтверждённого устройства для vulkan рекомендация не выдаётся (`managed_runtime.rs:414-416`) — корректный fail-closed |
| error-reasons (`MessageList.svelte`, `modelGateway.ts`, i18n) | **accept** | i18n 975/975 ru↔en, приватные данные не протекают. Мелкое: AUD-011 |
| Тесты WIP | **accept-with-fixes** | Покрытие есть и оно осмысленное, но: junction-тесты могут пройти впустую (AUD-005), security-граница не покрыта (AUD-006) |
| Cargo.toml (новые feature-флаги) | **accept** | `Wdk_Foundation`, `Wdk_Storage_FileSystem`, `Win32_System_IO` — это feature уже присутствующей зависимости `windows-sys`; `Cargo.lock` не изменился → новых third-party зависимостей нет, NOTICE не требует обновления |

---

## 5. Карта ACL

Всего: зарегистрировано **79** команд, выдано **76**, вызывается из `src/` **32**.

- Висячих разрешений (выдано, но не зарегистрировано): **нет**
- Вызывается фронтендом без разрешения: **`execute_approved`** (единственный; см. AUD-007)
- Неизвестных идентификаторов в `main.json`: **нет**
- Permission определены, но не выданы: `allow-get-model-storage-info`, `allow-open-model-storage-folder`

| Фронтенд-вызов | Разрешение | Статус |
|---|---|---|
| `request_approval`, `resolve_tool_approval`, `run_tool_call`, `cu_broker_*`, `intent_compile` | `allow-request-approval` | OK |
| `skills_list/install/enable/disable/uninstall/compile` | `allow-skills-*` (добавлено в WIP) | OK — все 6 зарегистрированы |
| `checkpoint_compare/list/restore_*` | `allow-checkpoints` | OK |
| `coding_*` | `allow-coding` | OK |
| `lsp_diagnostics` | `allow-lsp-diagnostics` | OK |
| `speak_local_text`, `stop_local_text` | `allow-speak/stop-local-text` | OK |
| `execute_approved` | **нет** | **AUD-007** — мёртв + запрещён |
| `get_model_storage_info`, `open_model_storage_folder` | определено, не выдано | фичи-зомби |

---

## 6. Score verification (заявлено 9.5/10)

| Критерий score-cap | Evidence | Вердикт |
|---|---|---|
| Native E2E 12/12 | Vault, датировано 2026-08-31, дерево `fd4b100` | **Принят, но не за WIP** — WIP native-приёмку не проходил |
| Stop→revoke→replay | Rust unit + seam | Принят (не native на WIP) |
| Restart recovery | Unit/inner-seam | Принят частично |
| Coding seam | Code seam (Vault: «native behavioral acceptance не доказана») | Частично |
| **Нативное Win32-меню приложения** | было live на `25c38e7`/`fd4b100` | **Аннулировано WIP** — нативное меню удалено, заменено Svelte `AppMenuBar`. Критерий 9.5 больше не выполняется |
| Installer provenance | Vault: SHA-256 `5fce2524…b1bac` из `fd4b100` | **Не проверяемо** — артефакта `.exe` в дереве нет (`find` по `*.exe` — пусто). Плюс installer собран из `fd4b100`, а не из текущего WIP-дерева |
| Latency / footprint | Vault 31.08 | Принят, дерево `fd4b100` |
| Licenses / notices | `LICENSE` MIT (21 строка), `Cargo.lock` не менялся | Принят; WIP не добавил зависимостей |
| Автоматическая батарея гейтов | этот аудит | **Не принят** — 4 красных гейта |

**Честный скор сейчас: 8.0/10.** Обоснование: инженерная база крепкая (Rust-граница, panic-safe парсеры, 565+762+399 автоматических тестов, real-sidecar в require-режиме зелёный), но (а) один из критериев 9.5 удалён самим WIP, (б) батарея гейтов красная, (в) WIP не имеет native-приёмки, (г) есть P1-дефект честности состояния. 9.5 возвращается после устранения AUD-001/002/003 и повторной приёмки.

---

## 7. Чеклисты

### Перед коммитом WIP (минимальная приёмка)

1. Исправить AUD-001 (`secure_delete` → честный результат) и переписать/дополнить тест `:960-977`.
2. Привести vendor-кэш в согласованное состояние + `.gitattributes` (AUD-002) → `check_bundle_parity` exit 0.
3. `cargo test --lib` → 0 failed. Отдельно перепроверить 3 `open_url`-теста **вне песочницы** (без блокировки `reg.exe`), чтобы отделить AUD-008 от окружения.
4. `refresh_evidence` + `check_evidence_provenance` → exit 0, зафиксировать новый `tree_digest`.
5. AUD-005: junction-тесты обязаны падать, если фикстура не создалась.
6. AUD-006: минимум 4 теста на `execute_broker_mutation` (нет grant / чужой tool / истёк / digest mismatch).
7. Обновить базовые числа в `AGENTS.md` (AUD-010).
8. Обновить `Projects/LocalComet/Status.md`: убрать «все 21 гейт зелёные», зафиксировать удаление нативного меню и его влияние на скор.

### Перед публичным релизом

1. Полная native-приёмка **на финальном дереве** (меню-своп, сплэш, файловые мутации через новый брокер).
2. Решение владельца по судьбе нативного Win32-меню — это критерий скора.
3. Собрать installer **из финального дерева**, записать SHA-256, повторить extract-parity.
4. AUD-004: таймауты на инициализацию + escape-хэтч на сплэше (релиз-блокер: приложение не должно уходить в чёрный экран).
5. Удалить или подключить `execute_approved` (AUD-007).
6. Clean-machine parity на второй машине.
7. Юридическое ревью `LICENSE` (держатель — плейсхолдер «LocalComet Project Owner»).

### Предлагаемые новые гейты

1. **Broker-return honesty gate**: статическая проверка, что ни одна функция брокера не возвращает «успех» до подтверждения результата (класс AUD-001).
2. **Real-tree parity test**: `tests/` должен прогонять `check_bundle_parity` по настоящему дереву, а не по фикстурам (класс AUD-009).
3. **No-silent-test-skip gate**: запрет паттерна `if !fixture { eprintln!("SKIP"); return; }` внутри `#[test]` (класс AUD-005).
4. **Hermeticity gate**: запрет `Command::new("reg.exe")` и других внешних вызовов на путях, покрытых unit-тестами (класс AUD-008).
5. **ACL-reachability gate**: пересечение registered ∩ granted ∩ frontend-invoked; любая команда, зарегистрированная и не выданная, либо вызванная без выдачи — ошибка (класс AUD-007).
6. **Splash-liveness gate**: тест, что оверлей снимается при ошибке инициализации и по таймауту (класс AUD-004).

---

## 8. Приложения — воспроизводимость

```bash
# Блок 1
git rev-parse --abbrev-ref HEAD; git log --oneline -20; git status --porcelain; git diff --stat

# Блок 2
cd desktop/localcomet-desktop            && npm run check && npm test
cd desktop/localcomet-desktop/src-tauri  && cargo test --lib -- --test-threads=1
                                            cargo fmt --check
                                            cargo clippy --all-targets --all-features -- -D warnings
py -3.14 -m pytest tests/ -q --basetemp="C:/Users/DNS/AppData/Local/Temp/lcaudit-pt"
py -3.14 tools/test_v6846_tool_execution.py
py -3.14 tools/test_bug1_inference_bundle_parity.py
py -3.14 tools/test_adr015_tool_parsing.py
py -3.14 tools/test_tool_risk_rust_parity.py
py -3.14 scripts/check_bundle_parity.py
py -3.14 scripts/check_command_parity.py
py -3.14 scripts/check_tool_risk_registry.py
py -3.14 scripts/check_ui_fake_state.py
py -3.14 scripts/check_mockdata_imports.py
py -3.14 tests/test_check_bundle_parity.py
py -3.14 tests/test_evidence_model.py
py -3.14 tests/test_trust_chain_gate.py
py -3.14 tests/test_trust_chain_invariants.py
py -3.14 tests/test_tool_risk_registry_gate.py
py -3.14 tests/test_mockdata_import_gate.py
py -3.14 scripts/smoke_test.py --mode=cli
LOCALCOMET_TEST_PROJECT_ROOT="C:/Users/DNS/Documents/LocalComet-build-week-clean" \
LOCALCOMET_TEST_PYTHON="C:/Users/DNS/AppData/Local/Python/pythoncore-3.14-64/python.exe" \
LOCALCOMET_REQUIRE_REAL_SIDECAR=1 py -3.14 scripts/check_real_sidecar_tests.py
py -3.14 scripts/refresh_evidence.py && py -3.14 scripts/check_evidence_provenance.py

# Линейка сравнения vendor-файла (AUD-002)
py -3.14 -c "
p='modules/_vendor/comtypes/gen/_944DE083_8FB8_45CF_BCB7_C477ACB2F897_0_1_0.py'
import subprocess
wt=open(p,'rb').read(); head=subprocess.run(['git','show','HEAD:'+p],capture_output=True).stdout
print(len(wt), wt.count(b'\r\n')); print(len(head), head.count(b'\r\n'))
print('equal ignoring CR:', wt.replace(b'\r\n',b'\n')==head.replace(b'\r\n',b'\n'))"

# Реестр side-effect примитивов сайдкара (Блок 4)
grep -rnE "subprocess\.(Popen|run|call)|socket\.|urllib|shutil\.rmtree|os\.(remove|rename|makedirs)" \
  --include=*.py modules/ core/ agents/ | grep -v "_vendor\|test_"
```

**Оговорки метода (эпистемическая честность):**

- Первый прогон `pytest` дал 11 ошибок — это был дефект моего харнесса (git-bash путь `/tmp/...` не резолвится pytest-asyncio). После перехода на нативный Windows-путь: 399 passed / exit 0. В отчёт включён второй, корректный прогон.
- 3 из 4 падений `cargo test` вызваны блокировкой `reg.exe` в песочнице аудита (AUD-008) и на обычной машине разработчика, где установлен Chrome/Edge/Firefox, должны быть зелёными. Это требует обязательной перепроверки вне песочницы перед коммитом.
- AUD-001: не удалось определить, удаляется ли непустая папка физически, — ctypes/PowerShell-пробы заблокированы политикой песочницы. Формулировка findings это явно отражает.
- Запуск приложения, Computer Use и native-сценарии не выполнялись — в соответствии с регламентом аудита.
