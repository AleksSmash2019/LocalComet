# Отчёт: установленная версия — детальный обход и исправление багов

Дата: 2026-09-07
Ветка: feat/up00-wp01-windows-one-click-launch
Коммит: 338c5ff (fix(skills): resolve bundled interpreter and CLI path in release layout)

## 1. Исходное состояние

git status до начала: чисто (последний коммит 0408813).
Установленная версия найдена: `C:\Users\DNS\AppData\Local\Programs\LocalComet`, v7.0.5 (LocalComet.exe от 06.09.2026 16:18, sha256 5cd62586…).

## 2. Как проверялась установленная версия

Hidden-isolated desktop + loopback CDP (tools/sweep_installed_release.py, SWEEP_EXE=<installed exe>):
- обход всех воркспейсов (Чат, Модели HF, Подобрать модель) реальными кликами;
- обход всех 8 вкладок настроек (Интерфейс, Модели, Навыки, Разрешения, Контрольные точки, Задачи кодирования, Логи, О приложении);
- открытие ModelFit-окна, скан железа;
- сбор uncaught exceptions / console errors / failed network requests;
- проверка localStorage-ключей персистентности.

## 3. Найденные баги

### Баг 1 (исправлен): вкладка «Навыки» не работает в релизе
Дословная ошибка в UI: «bundled python.exe not found next to python314.dll», затем «skills_cli.py not found in trusted locations».
Причина (2 дефекта в skills.rs):
1. Упаковщик копирует python.exe под именем `localcomet-core-{triple}.exe` (tools/build_up00_windows_installer.py:255), отдельного python.exe в релиз-лейауте нет — resolve_pinned_python его и искал.
2. skills_cli.py в релизе лежит в `<install>/app/scripts/`, а резолв искал только `../../../scripts/` от exe (путь dev-сборки).

Фикс (desktop/localcomet-desktop/src-tauri/src/skills.rs): интерпретатор — sibling `python.exe` ИЛИ `localcomet-core.exe`; CLI-путь — сначала `app/scripts/skills_cli.py`, затем старый dev-путь.

### Не баг (честное сообщение UI)
- «Контрольные точки: checkpoint operations require a confirmed workspace» — подтверждённая рабочая область в скрытом тестовом окружении не выбиралась; сообщение само по себе корректно.
- Ошибка «pinned python interpreter not found» при прогоне свежесобранного exe из cargo-target — ожидаемо: рядом с cargo-target/release/LocalComet.exe нет python314.dll (полный лейаут собирается только внутри NSIS-бандла). Контроль: старый установленный exe показывает старую ошибку, свежий — новую строку фикса.

## 4. Изменённые файлы

- desktop/localcomet-desktop/src-tauri/src/skills.rs (resolve_pinned_python + cli_path) — закоммичено 338c5ff.
- Память сессии (вне репозитория).

## 5. Гейты (последние строки вывода дословно)

- cargo test: `test result: ok. 777 passed; 0 failed; 7 ignored; 0 measured; 0 filtered out`
- cargo fmt --check: exit 0 (пустой вывод)
- cargo clippy --all-targets --all-features -- -D warnings: `Finished `dev` profile [optimized+debuginfo] target(s) in 7.44s`
- npm run check (desktop/localcomet-desktop): `svelte-check found 0 errors and 0 warnings`
- npm test: `Tests  545 passed (545)`
- python tests/test_check_bundle_parity.py: `OK`
- python tests/test_evidence_model.py (после refresh_evidence): `OK: 4 evidence file(s) fresh and intact (tree=dddddddddddddddd...)`
- python tests/test_trust_chain_gate.py: `OK`
- python tests/test_trust_chain_invariants.py: `OK: 15 trust-chain files pass byte invariants`
- python scripts/check_command_parity.py: `OK: 79 commands registered and invoked (parity holds)`
- python scripts/check_tool_risk_registry.py: `OK: 7 console tool function(s) classified (5 mutating, all requiring approval); 11 sidecar tools covered; 21 registry entries valid`
- python scripts/check_ui_fake_state.py: `OK: no fake-state violations in 113 frontend file(s) (INV-UI-001)`
- python scripts/check_mockdata_imports.py: `src/lib/stores/shellStore.ts: fallback constants (modeOptions, inspectorSections)` + `OK: 423 shipped module(s) match source across 2 location(s) (bundle parity holds)` (последний — check_bundle_parity.py; строки check_mockdata_imports — информационный вывод гейта, код выхода 0)
- python tools/test_bug1_inference_bundle_parity.py: `ALL OK`
- python tools/test_adr015_tool_parsing.py: `OK (skipped=1)`
- python tools/test_tool_risk_rust_parity.py: `OK: parser self-tests passed`
- python scripts/smoke_test.py --mode=cli: `SMOKE PASSED: real sidecar product path behaves as expected.`
- python scripts/refresh_evidence.py: `evidence refreshed: all gates green` (tree=be3d834d4c842d53…)
- python scripts/check_evidence_provenance.py: `OK: 4 evidence file(s) fresh and intact (tree=be3d834d4c842d53...)`
- python scripts/check_real_sidecar_tests.py (с LOCALCOMET_REQUIRE_REAL_SIDECAR=1, LOCALCOMET_TEST_PROJECT_ROOT, системный py -3.14): `OK: real-sidecar tests ran under require mode with no silent skips`

## 6. Артефакты сборки

Новый установщик (с фиксом, source_commit 338c5ff):
`target/up00-wp01/cargo-target/release/bundle/nsis/LocalComet_7.0.5_x64-setup.exe`
15 514 616 байт, sha256 `793b6020d213cbc297fc8afa7ce10f258386545e501615c4cfba4bd5211738b3`

## 7. Что НЕ сделано и почему

- Установленная копия НЕ обновлялась новым установщиком: запуск инсталлятора поверх установленной программы — действие на системе пользователя, требует явного решения владельца.
- Реальный чат-turn с загруженной моделью в скрытом окружении не прогонялся (модель не загружена в изолированном LOCALAPPDATA; статус UI честно показывает «Модель не загружена»).
- Полная CDP-верификация «Навыков» в УСТАНОВЛЕННОЙ копии станет возможной после установки нового установщика (см. пункт 7.1).

---

# Дополнение 07.09 (вторая волна): озвучка и ModelFit-окно

## Найденные баги

### Баг 2 (исправлен, c19a9c7): при озвучке ответа мигает консоль
piper.exe и powershell.exe (SAPI) запускались без CREATE_NO_WINDOW — на каждый ответ всплывало консольное окно. Фикс: creation_flags(0x0800_0000) в voice.rs для обоих запусков. Остальные места запуска проверены: sidecar и терминалы уже защищены (windows_job.rs), reg.exe/nvidia-smi уже скрывались (hardware.rs).

### Баг 3 (исправлен, b243020 + 95a7506): «Подобрать модель» открывает окно, оторванное от интерфейса
Окно ModelFit было независимым (не привязано к главному). Хотелось owner-поведение (поверх главного, сворачивается/закрывается вместе с ним). В ходе исправления найдены 2 скрытых дефекта фреймворка (tauri 2.11.5), оба подтверждены CDP-пробами:
1. JS-путь WebviewWindow(parent:'main') зависает навсегда — команда create_webview_window не завершается ни успехом, ни ошибкой.
2. Rust-путь parent(&main) из рабочего потока зависает так же: owner-HWND резолвится блокирующим запросом к event loop.

Итоговое решение: окно создаётся в Rust на главном потоке (open_modelfit_window, run_on_main_thread + канал с таймаутом 15с), фронтенд просто вызывает команду. Проверено на видимом десктопе: команда завершается ОК, окно создаётся, скан железа внутри него работает.

Примечание о верификации: на скрытом тестовом десктопе owner-окна не создаются (ограничение самой среды) — проверка там даёт ложный отказ; финальная проверка выполнена на видимом десктопе с изолированным профилем данных.

## Гейты после второй волны (последние строки дословно)

- cargo test: `test result: ok. 777 passed; 0 failed; 7 ignored; ...`
- cargo fmt --check: exit 0
- cargo clippy --all-targets --all-features -- -D warnings: `Finished ... target(s) in 6.74s`
- npm run check: `svelte-check found 0 errors and 0 warnings`
- npm test: `Tests  545 passed (545)`
- python tests/* (check_bundle_parity, evidence_model, trust_chain_gate, tool_risk_registry_gate, mockdata_import_gate, trust_chain_invariants): `OK`
- python scripts/check_command_parity.py: `OK: 79 commands registered and invoked (parity holds)`
- python scripts/check_tool_risk_registry.py: `OK: 7 console tool function(s) ...; 21 registry entries valid`
- python scripts/check_ui_fake_state.py: `OK: no fake-state violations in 113 frontend file(s) (INV-UI-001)`
- python scripts/check_bundle_parity.py: `OK: 423 shipped module(s) match source across 2 location(s) (bundle parity holds)`
- python tools/test_bug1_inference_bundle_parity.py: `ALL OK`
- python tools/test_adr015_tool_parsing.py: `OK (skipped=1)`
- python tools/test_tool_risk_rust_parity.py: `OK: parser self-tests passed`
- python scripts/smoke_test.py --mode=cli: `SMOKE PASSED: real sidecar product path behaves as expected.`
- python scripts/refresh_evidence.py: `evidence refreshed: all gates green` (tree=971dc34f…)
- python scripts/check_evidence_provenance.py: `OK: 4 evidence file(s) fresh and intact (tree=971dc34f...)`
- python scripts/check_real_sidecar_tests.py (CI env): `OK: real-sidecar tests ran under require mode with no silent skips`

## Артефакт

Новый установщик (source_commit 95a7506):
`target/up00-wp01/cargo-target/release/bundle/nsis/LocalComet_7.0.5_x64-setup.exe`
15 514 114 байт, sha256 `39718b94c3732e014a4168fc79501e87090afd7cac49780f3a17f196273c3590`

Коммиты: 338c5ff (навыки), c19a9c7 (озвучка+первый шаг ModelFit), b243020 (owner из Rust), 95a7506 (main-thread).
