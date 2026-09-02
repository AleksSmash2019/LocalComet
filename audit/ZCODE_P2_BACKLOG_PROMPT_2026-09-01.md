# ПРОМТ ДЛЯ ZCODE: P2-бэклог LocalComet (пункты 5–9 + финальный гейт-прогон)

Репозиторий: C:\Users\DNS\Documents\LocalComet-build-week-clean
Ветка: feat/up00-wp01-windows-one-click-launch (HEAD fd4b100 + незакоммиченный WIP).

## СТАТУС ВХОДА (уже выполнено и верифицировано — НЕ переделывать)
Пункты 1–4 предыдущего бэклога закрыты: hardlink-refusal в secure_fs.rs (NumberOfLinks, тесты hardlinked_leaf_is_refused_for_write/delete), прямые тесты execute_broker_mutation (5 шт: без grant / чужой tool / истёк / tampered path / happy path), system.time в risk_level_for_tool + строгий read-only паритет в tools/test_tool_risk_rust_parity.py (доказан в обе стороны), junction-SKIP заменён на assert. cargo test --lib = 774 passed / 0 failed / 7 ignored — зелёный. Твоя работа — пункты 5–9 ниже, затем финальный полный прогон.

## КОНТЕКСТ МОДЕЛИ БЕЗОПАСНОСТИ (не нарушать)
Rust — граница доверия; approval-токен одноразовый; risk-реестр security/invariants/tool_risk_levels.toml синхронизирован с approval_commands.rs::risk_level_for_tool и tools/test_tool_risk_rust_parity.py. Прод-поведение cu_broker менять запрещено (только тестовый seam). i18n: паритет ключей ru/en (сейчас 937=937) — не ломать.

---

## ПУНКТ 5 — Герметизация cu_broker open_url тестов (P2)
Файл: desktop/localcomet-desktop/src-tauri/src/cu_broker.rs. resolve_program (~строки 481–508) вызывает reg.exe через Command::new("C:\Windows\System32\reg.exe") — браузеры резолвятся только через реестр хоста. Три unit-теста зависят от хоста: broker_preflight_blocks_unknown_target_without_spawning (~:2079), open_app_rejects_url_field_strict_separation (~:2468), intent_compiler::tests::compiled_open_url_reaches_url_validation (intent_compiler.rs ~:706).
Сделай минимальный seam: трейт ProgramResolver (метод с семантикой текущего resolve_program) + RegistryResolver (существующий код reg.exe без изменений) + cfg(test)-fake с фиксированной таблицей App Paths (chrome/msedge/firefox присутствуют, unknown — нет). Проведи резолвер параметром через plan_launch до call-site; прод-код использует RegistryResolver как сейчас. Три теста переключи на fake — та же валидация, нулевая зависимость от хоста. Выбери наименьшую инвазию (допустим trait только в cfg(test), если prod не нуждается в подмене). Не меняй allowlist, URL-политики, hidden-desktop логику, APP_REGISTRY.

## ПУНКТ 6 — Мёртвый executeApproved (P2)
src/lib/bridge/approval.ts:105–125: экспорт executeApproved (invoke 'execute_approved') не имеет прод-вызовов; единственный потребитель tests/p0b-r5-approval-contract.test.ts:372; команда не выдана в ACL (реальный invoke был бы отклонён). Удали функцию executeApproved и ставшие неиспользуемыми типы. Тестовый блок p0b-r5 переведи на vi.mock('@tauri-apps/api/core') (мок grant + проверка валидации структуры) либо удали, если контракт уже покрыт другими тестами (проверь). Rust-команду execute_approved (approval_commands.rs:~815) и её 8 unit-тестов НЕ трогать — только doc-комментарий над fn: «internal-only: not granted via ACL; reserved for future trusted callers».

## ПУНКТ 7 — Splash: bounded timeout + escape hatch (P2)
src/routes/+page.svelte: startupReady = $controlPlaneBridgeState !== 'CONNECTING' && $modelGatewayStore.initialized; в bridge-слое нет setTimeout/AbortController — «висящий» invoke перекрывает приложение навсегда (оверлей z-index 1000, без выхода).
Сделай: (1) в +page.svelte таймер 20с от монтирования (onDestroy очистка; отмена при startupReady); по истечении startupTimedOut=true, если ещё не ready; (2) StartupScreen.svelte: при timedOut показывает текст i18n startup.timeout (ru: «Запуск дольше обычного. Можно продолжить с ограниченной функциональностью или перезапустить приложение.»; en: «Startup is taking longer than usual. Continue with limited functionality or restart the app.») и кнопку startup.continue (ru «Продолжить», en «Continue»), скрывающую оверлей (минимально инвазивно: колбэк-проп onContinue -> локальный dismissed в +page.svelte; условие показа: {#if !startupReady && !dismissed}); (3) ключи startup.timeout и startup.continue добавить в ru.ts И en.ts симметрично; (4) a11y: кнопка фокусируема, текст в существующей aria-live области.
Тест: новый desktop/localcomet-desktop/tests/startup-screen.test.ts (паттерн render из svelte/server как в componentSmoke): timedOut=true -> содержит текст timeout и кнопку «Продолжить»; без timedOut -> не содержит.

## ПУНКТ 8 — import-closure гейт (P2)
Новый scripts/check_import_closure.py (только stdlib): AST-обход (модуль ast) локальных импортов от корней tools/run_localcomet_desktop_sidecar.py и modules/skills/builtin/*/entrypoint.py. Разрешены импорты modules.* (включая modules._vendor.*). Обрабатывай import X / from X import Y, абсолютные modules.* и относительные from . внутри пакетов modules. Строй транзитивное замыкание по файлам modules/**/*.py (без __pycache__).
Сверка: (а) каждый модуль замыкания обязан быть в desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json (sourceFiles, префикс modules/) И существовать в shipped-дереве desktop/localcomet-desktop/src-tauri/binaries/app/modules; (б) каждый shipped modules/*.py обязан быть либо в замыкании, либо в явном EXCLUDED_LEGACY frozenset в начале скрипта (заполни фактически: замыкание вычисли, остальное из shipped внеси в список с комментарием legacy; ожидаемо ~140–150).
Verdict в стиле гейтов репозитория: «OK: import closure of N modules covered by manifest and shipped (M legacy excluded)» / «FAIL: closure module X missing from manifest» / «FAIL: shipped module Y unreachable and not excluded». Exit 0/1. Гейт обязан быть зелёным сразу на текущем дереве.

## ПУНКТ 9 — Актуализация чисел AGENTS.md
Обнови ТОЛЬКО устаревшие базовые числа в AGENTS.md (правила и список гейтов не менять): vitest 398→565 (или финальное число после пункта 7); cargo lib «512 passed / 0 failed / 6 ignored»→фактическое число финального прогона (сейчас 774/0/7, после пунктов 5–6 может вырасти — впиши факт); command parity 58→79; INV-UI-001 97→116; tool risk registry 19→21. Каждое число сверяй с фактом, не выдумывай.

## ПУНКТ 10 — Финальный полный гейт-прогон (обязателен, порядок именно такой)
1. cd desktop/localcomet-desktop: npm run check; npm test
2. cd src-tauri: cargo test --lib -- --test-threads=1; cargo fmt --check (если дрейф — cargo fmt только на своих файлах); cargo clippy --all-targets --all-features -- -D warnings
3. В корне: py -3.14 -m pytest tests/ -q (basetemp изолированный вне репо, например %TEMP%\lc_zcode_basetemp)
4. py -3.14 tools\test_tool_risk_rust_parity.py
5. py -3.14 scripts\check_bundle_parity.py (если красный по comtypes-кэшу: официальный resync py -3.14 tools\launch_localcomet_dev.py --stage-only; py -3.14 tools\build_up00_windows_installer.py --refresh-build-source; перепрогони — pytest может перегенерировать кэш)
6. py -3.14 scripts\check_import_closure.py (новый, пункт 8)
7. py -3.14 scripts\smoke_test.py --mode=cli
8. LOCALCOMET_REQUIRE_REAL_SIDECAR=1 LOCALCOMET_TEST_PYTHON=C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe py -3.14 scripts\check_real_sidecar_tests.py
9. py -3.14 scripts\refresh_evidence.py; py -3.14 scripts\check_evidence_provenance.py — зафиксируй итоговый tree_digest

## ЖЁСТКИЕ ОГРАНИЧЕНИЯ
- Никаких git-коммитов/веток/reset/clean/stash. Ничего не удалять (кроме кода executeApproved в approval.ts — это sanctioned правка).
- Python только системный py -3.14 (C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe), не venv.
- Приложение не запускать, native/hidden-desktop не выполнять, Calculator не трогать.
- Не трогать: gguf_metadata.rs, MessageList.svelte, AppMenuBar.svelte, modules/_vendor/**, Cargo.toml (новые зависимости запрещены), security/invariants/tool_risk_levels.toml.
- Существующие зелёные тесты не деградировать; новый функционал — только в рамках пунктов.

## ОТЧЁТ НАЗАД
По каждому пункту 5–9: изменённые/созданные файлы, суть правки, имена новых тестов дословно. Финальный прогон: команда → exit code → ключевые финальные строки (числа тестов, tree_digest). Для пункта 8: итоговые N (closure) и M (legacy excluded). Отклонения от задания и что не сделано — отдельно.