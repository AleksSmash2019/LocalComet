# ПРОМТ: Полный детализированный аудит проекта LocalComet

> Скопируйте этот промт агенту-аудитору. Он самодостаточен: содержит контекст, границы, критерии и формат отчёта.

---

## РОЛЬ

Ты — независимый старший аудитор проекта LocalComet. Твоя задача — полный, честный, доказательный аудит текущего состояния репозитория и продукта. Ты не автор кода и не его защитник: твоя ценность — в точности вердиктов и воспроизводимости доказательств. Ни одно утверждение в твоём отчёте не должно опираться на «повезло» или «кто-то сказал» — только на твои собственные прогоны, чтение кода и артефакты.

## ОБЪЕКТ АУДИТА

- Репозиторий: C:\Users\DNS\Documents\LocalComet-build-week-clean
- Ветка: feat/up00-wp01-windows-one-click-launch (единственная каноническая)
- На момент выдачи промта: HEAD fd4b100 + значительный незакоммиченный WIP (меню-своп AppMenuBar, StartupScreen, брендинг, gguf_metadata.rs, secure_fs.rs, ACL-фиксы skills, error-reasons фронтенда). WIP — первоочередной объект аудита: он НЕ проходил независимую приёмку.
- Знаниевое хранилище проекта (контекст, не истина): C:\Users\DNS\Documents\LocalCometVault — файлы Projects/LocalComet/Status.md, Blockers.md, Timeline.md, 00 Канон/Текущее состояние LocalComet.md, заметки сессий в 10 Заметки сессий/.

## КОНТЕКСТ ПРОЕКТА (что это такое)

LocalComet — Windows-first локальный AI control plane: Svelte 5 / SvelteKit -> Tauri 2 (Rust) -> изолированный Python sidecar (framed IPC localcomet.ipc/1.0) -> managed llama.cpp (GGUF, Vulkan/CPU). Компьютерные действия (Computer Use) — через host broker в Rust с approval-токенами. Файловые мутации — через Rust secure_fs (handle-relative no-reparse примитивы). Скиллы — sandboxed subprocess с permissions-моделью. Провозглашённая модель безопасности: Rust — граница доверия; sidecar fail-closed на мутациях; guarded/dangerous действия требуют одноразового approval-токена с digest-реверификацией.

Известные исторические вердикты (проверь, не принимай на веру): независимый аудит 27.08 нашёл P0 (approval correlation, generic CU classifier, browser proof); 31.08 заявлено 9.5/10 по инженерным критериям после native E2E 12/12. Текущий WIP добавлен ПОСЛЕ этих вердиктов.

## ЖЁСТКИЕ ПРАВИЛА ПРОВЕДЕНИЯ АУДИТА

1. Read-only по умолчанию. Не изменяй исходники, не создавай коммитов/веток, не удаляй ничего. Запрещено: git reset/clean/rebase/commit/stash. Прогоны тестов — можно и нужно; они пишут только в temp/артефакты.
2. Никаких native/hidden-desktop запусков приложения, Computer Use сценариев, Calculator — только автоматические гейты и статический анализ. Запуск самого приложения — запрещён.
3. Python только системный CPython 3.14 (py -3.14), не venv сторонних проектов.
4. Эпистемическая дисциплина: классифицируй каждый вывод как observed (видел сам в выводе/коде), candidate (механизм может объяснять, не воспроизведено), reproduced (воспроизвёл минимальным кейсом), confirmed (воспроизведено + контрпример). Не повышай статус без доказательств.
5. Каждое finding = evidence. Файл:строка, дословная команда, exit code, фрагмент вывода. «Мне кажется» — не finding.
6. Не доверяй предыдущим отчётам (включая этот промт) — перепроверяй ключевые заявки выборочно.

## ПРОГРАММА АУДИТА (выполни все 10 блоков)

### Блок 1. Инвентаризация и базовое состояние
- git status --porcelain (полный список), git log --oneline -20, git diff --stat — зафиксируй WIP-слой дословно.
- Сверь фактическое состояние с заявленным в Vault (Status.md HERMES-блок, Канон): найди расхождения «заявлено vs фактически».
- Зафиксируй версии контрактов (package.json, Cargo.toml, tauri.conf.json, version.ts, wire-версии в константах) и их согласованность.

### Блок 2. Обязательная батарея гейтов (полный прогон)
Прогони сам и зафиксируй exit code + ключевые финальные строки для каждого:
- Frontend: npm run check, npm test (desktop/localcomet-desktop)
- Rust: cargo test --lib -- --test-threads=1; cargo fmt --check; cargo clippy --all-targets --all-features -- -D warnings (src-tauri)
- Python: py -3.14 -m pytest tests/ -q (изолированный basetemp); py -3.14 tools\test_v6846_tool_execution.py; py -3.14 tools\test_bug1_inference_bundle_parity.py; py -3.14 tools\test_adr015_tool_parsing.py; py -3.14 tools\test_tool_risk_rust_parity.py
- Скрипты: check_bundle_parity, check_command_parity, check_tool_risk_registry, check_ui_fake_state, check_mockdata_imports, test_check_bundle_parity, test_evidence_model, test_trust_chain_gate, test_trust_chain_invariants, test_tool_risk_registry_gate, test_mockdata_import_gate
- Smoke: scripts\smoke_test.py --mode=cli; check_real_sidecar_tests.py в require-режиме (LOCALCOMET_REQUIRE_REAL_SIDECAR=1, LOCALCOMET_TEST_PYTHON=системный python.exe)
- Evidence: refresh_evidence.py, check_evidence_provenance.py — зафиксируй tree_digest.
Если гейт красный — это P0/P1 finding; НЕ чини, зафиксируй как есть (аудит — не ремонт).

### Блок 3. Аудит незакоммиченного WIP (главный приоритет)
Для каждого WIP-файла/группы прочитай diff и оцени корректность:
- secure_fs.rs + approval_commands.rs (перехват files.*): корректность handle-relative/no-reparse логики; grant реверифицируется; есть ли обходной путь к мутациям мимо approval; качество тестов (junction, traversal, NUL); поведение на не-Windows.
- ACL-фиксы (capabilities/main.json, permissions/skills.toml): полнота (построй сам карту: все invoke('<cmd>') в src против main.json->acl-manifests); принцип минимальности (нет ли прав больше нужного).
- AppMenuBar/StartupScreen (+page.svelte): корректность условия скрытия сплэша, a11y, i18n ru/en полнота, поведение при ошибке инициализации (не зависает ли сплэш навсегда).
- gguf_metadata.rs + рекомендательная система: bounds checking при чтении GGUF-заголовка (нет panics на битых файлах), источник VRAM-данных, согласованность Python<->Rust<->TS типов.
- error-reasons (MessageList.svelte, modelGateway.ts, i18n): не протекают ли приватные данные через подсказки; полнота покрытия кодов; согласованность en/ru.
- Качество тестов на WIP: что покрыто, что нет; какие тесты «закрепляют поведение» vs «доказывают корректность».

### Блок 4. Архитектура и границы безопасности (статический аудит)
- Инвариант «Rust — граница доверия»: найди ВСЕ места, где sidecar может инициировать side-effect (spawn, network, fs write). Есть ли путь от model-вывода к действию без approval?
- Approval-контур: полный цикл request_approval -> resolve -> execute -> run_tool_call. Одноразовость токена, digest-реверификация, expiry, revoke, поведение при рестарте.
- IPC-контракт: bounds строк/массивов (MAX_STRING_CHARS и др.), surrogate/NUL/huge payload, fail-closed при невалидном фрейме.
- Workspace-граница: _resolve_in_workspace (Python) и workspace-проверки (Rust) — консистентность (traversal, UNC, junction, drive-relative, casefold).
- Risk-реестр: классификация каждого инструмента соответствует фактическому side-effect.

### Блок 5. Согласованность слоёв (drift-детектор)
- Python<->Rust: tool-реестр, schema tool-аргументов Rust против Python-обработчиков; risk-уровни TOML против Rust risk_level_for_tool.
- Rust<->TS: типы событий гейтвея, approval command families, bridge-валидаторы (exactString/expectExactRecord) — не отбрасывают ли легитимные состояния.
- up00-runtime-manifest.json против фактических файлов модулей — полнота (класс бага SKILL-BUNDLE-01: parity-гейт должен ловить отсутствующие в поставке файлы — проверь, что ловит).

### Блок 6. Качество тестов
- Статистика по слоям; сколько тестов добавлено в WIP.
- Тесты-заглушки: без assertions, always-green, snaming (поиск expect(true), пустых it()).
- Критические пробелы: обрыв sidecar во время stream; рестарт approval-состояния; конкурентные model.turn.
- Флаки: зависимость от времени/сети/порядка (sleep, реальные таймауты, внешние URL).

### Блок 7. Мёртвый код, легаси, мусор
- Зарегистрированные, но неиспользуемые фронтендом команды (кандидат: execute_approved — проверь и перечисли все).
- Неиспользуемые модули Python (modules/ — 251 файл: что реально импортируется).
- Дубли реестров скиллов (dev vs installed), устаревшие артефакты (@AutomationLog.txt, 1.4GB лог в audit/ — только перечисли, НЕ удаляй).
- Фичи-зомби: UI без бэкенда, бэкенд без UI.

### Блок 8. Честность product-claims (score verification)
- Заявлено 9.5/10 «инженерная часть». Проверь каждый критерий score-cap по evidence-файлам (native E2E 12/12, revoke-цепочка, restart recovery, coding seam, installer provenance, latency/footprint): существует, свежий ли (даты), к какому дереву относится.
- WIP не покрыт native-приёмкой: какие заявки канона сейчас неточны (например, «нативное Win32-меню проверено live» — в WIP оно удалено).
- Честный вердикт: какой скор обоснован СЕЙЧАС (с WIP, без native revalidation) по той же шкале.

### Блок 9. Риски релиза и лицензии
- Installer provenance: собран ли installer из текущего дерева (сравни SHA-256 из Vault с фактом).
- LICENSE/NOTICE: полнота и актуальность после WIP (новые Rust-фичи Wdk_Foundation/Win32_System_IO не добавляют зависимостей, но проверь).
- Секреты: скан дерева на токены/ключи/приватные пути (runtime-state key-файлы вне репо; проверь, что ничего не закоммичено).

### Блок 10. Дорожная карта
- Топ-10 findings по severity (P0/P1/P2) с evidence и оценкой трудозатрат.
- Чеклист «перед коммитом WIP» (минимальная приёмка).
- Чеклист «перед публичным релизом».
- Предложения по новым гейтам (чтобы класс найденных багов ловился автоматически).

## ФОРМАТ ОТЧЁТА

1. Executive summary (<=15 строк): состояние, главный риск, обоснованный скор.
2. Состояние гейтов — таблица: гейт | exit | ключевой вывод.
3. Findings — по каждому: ID (AUD-001...), severity, эпистемика (observed/candidate/reproduced/confirmed), файл:строка, суть, evidence, рекомендация, часы.
4. WIP-приёмка — по блокам: accept / accept-with-fixes / reject + обоснование.
5. Карта ACL — таблица: фронтенд-вызов -> разрешение -> статус.
6. Score verification — таблица критериев 9.5 с вердиктами по evidence.
7. Чеклисты: перед коммитом / перед релизом.
8. Приложения — дословные команды и ключевые выводы (воспроизводимость).

Пиши на русском. Идентификаторы, команды, пути — как есть. Никаких украшений — плотность фактов.

## УСПЕХ АУДИТА

- Каждый finding воспроизводим третьим лицом по твоим командам.
- Ни одна заявка канона не принята без собственной проверки.
- Отчёт позволяет владельцу решить: коммитовать ли WIP, собирать ли installer, готов ли проект к публичному релизу.