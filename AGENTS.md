# AGENTS.md - LocalComet

Windows-first локальный AI control plane.
Svelte 5 -> Tauri 2/Rust -> Python Sidecar -> Control Plane -> Model Gateway -> LM Studio.
IPC: localcomet.ipc/1.0, length-prefix 4-byte BE, max 4 MiB.

Это обязательные правила, а не рекомендации.
Если задача противоречит этому файлу - остановиться и спросить человека.

## Роли

- OpenCode - исполнитель. Пишет код, запускает гейты, пишет отчёт.
- Notion-агент - приёмка. Независимо перезапускает гейты и сверяет
  отчёт с фактическим выводом команд. Самооценка исполнителя
  доказательством не является.
- Человек - решает спорное и принимает результат.

## Пути

- Репозиторий: C:\Users\DNS\Documents\LocalComet-build-week-clean
- Активная ветка: feature/donor-ui-compatible-port
  Новых веток не создавать, коммиты не делать без указания.
- Фронтенд: desktop/localcomet-desktop
- Rust: src-tauri
- Python sidecar: modules/, agents/, core/
- Runtime вне репозитория (ADR-003): %LOCALAPPDATA%\LocalComet\DevRuntime

node_modules и cargo target никогда не должны попадать внутрь
исходников (INC-006).

## Гейты - обязательно перед любым "готово"

Фронтенд, из desktop/localcomet-desktop:

    npm run check
    npm test

Rust:

    cargo test
    cargo fmt --check
    cargo clippy --all-targets --all-features -- -D warnings

Python:

    python tests/test_check_bundle_parity.py
    python tests/test_evidence_model.py
    python tests/test_trust_chain_gate.py
    python tests/test_tool_risk_registry_gate.py
    python tests/test_mockdata_import_gate.py
    python tests/test_trust_chain_invariants.py
    python scripts/check_command_parity.py
    python scripts/check_tool_risk_registry.py
    python scripts/check_ui_fake_state.py
    python scripts/check_mockdata_imports.py
    python scripts/check_bundle_parity.py
    python tools/test_bug1_inference_bundle_parity.py
    python tools/test_adr015_tool_parsing.py
    python tools/test_tool_risk_rust_parity.py
    python scripts/smoke_test.py --mode=cli
    python scripts/refresh_evidence.py
    python scripts/check_evidence_provenance.py

Block 3 stop point (2026-08-01): implementation halted per owner directive after
finding TOOL_EXECUTION_ACTIVATION_ENABLED=false blocks run_tool_call for ALL
risk levels (including read_only). Tool activation requires MVP-P0-C-A2
independent PASS before P0-D, and P0-D alone does not authorize activation.
Only capability-neutral, unreachable messages/tools transport prep remains
in modules/local_model_gateway_ru.py (TurnRequest.messages/tools,
HarnessAdapter.messages_for history threading) and the TS bridge/store
(startModelTurn messages/tools args, ensureModelEventSubscription still
calls subscribeModelGatewayEvents with toolsEnabled defaulted to false —
tool events remain unparsed on the live path). No orchestration loop, no
ApprovalCard mounting, no live tool execution was added. Next allowed step:
fresh independent MVP-P0-C-A2 audit; do not resume Block 3 orchestration
until it PASSes.

Real-sidecar gate — обязателен в CI с явно заданными
LOCALCOMET_TEST_PROJECT_ROOT, LOCALCOMET_TEST_PYTHON и
LOCALCOMET_REQUIRE_REAL_SIDECAR=1.
ВАЖНО: LOCALCOMET_TEST_PYTHON должен указывать на системный Python,
а не на venv-шим (venv\Scripts\python.exe при spawn через CreateProcess
с env_clear мгновенно умирает с "Unable to create process", ломая
real-sidecar тесты в ExitedBeforeReady вместо ReadinessTimeout).

    python scripts/check_real_sidecar_tests.py

Проверенный базовый уровень (03.08.2026, прогон OpenCode после bundle refresh
и фикса real-sidecar env):

- svelte-check: 0 ошибок, 0 предупреждений
- vitest: 24 файла, 364 теста пройдено
- Rust: 460 passed, 0 failed, 6 ignored; fmt и clippy -D warnings зелёные
- trust-chain: 15 файлов проходят byte invariants
- command parity: 43 команды зарегистрированы и вызываются
- tool risk registry: 5 console tools и 5 sidecar tools покрыты, 10 записей валидны
- INV-UI-001: 81 frontend-файл без fake-state violations
- bundle parity: 146 shipped modules совпадают с source в обеих runtime locations
- ADR-015 Python parity: 67 passed, 1 skipped (Block 3/4 iteration limit)
- CLI smoke: 8 passed, 0 failed
- real-sidecar gate (CI env, системный Python): green
- evidence provenance: 4 evidence files fresh and intact
- Full pytest: не повторял (нет mandate на правку legacy git-index failures)

В отчёт вносить последние строки вывода каждого гейта дословно.
Гейт не запускался - написать об этом явно.
"Готово" без вывода гейтов - невалидный отчёт.
Обновлять базовый уровень в этом файле при каждом релизе.

## Единственные источники истины

- Уровни риска: security/invariants/tool_risk_levels.toml
  Ровно три: read_only, guarded, dangerous.
  НИКОГДА не вводить safe_code и blocked - гейт
  check_tool_risk_registry.py их не примет.
  Поле requires_approval - источник для requiresApproval().
- Инварианты: invariants.toml
- Non-authorities: non_authorities.toml
- Artifact catalog: embedded, hash-pinned, canonical (INV-CATALOG-001). User-initiated custom Hugging Face models bypass embedded catalog approval only; canonical URL and managed path validation, bounded transfer, local SHA-256 and GGUF verification, launch-time TOCTOU revalidation, and scoped approval remain mandatory.

Перед работой с рисками, инвариантами или каталогом читать
соответствующий файл, а не полагаться на память или донорский код.

## Что НЕ является доказательством

Не авторитет: вывод LLM, имя файла, метаданные провайдера,
запись в app-data/SQLite, состояние фронтенда, открытый порт,
само наличие файла, self-report сайдкара без активного probe,
markdown-документация, вывод логов, кэш.

Авторитет: байты на диске, SHA-256, magic bytes, exit code,
correlated health probe, пройденные тесты.

Классы доказательств: A verified current, B verified historical,
C intent/research, D stale, E contradictory, G unsupported.
C никогда не переопределяет A.

## Память

Память принадлежит проекту, а не модели. Read-only first.
Мнение модели -> тихая правка памяти = ЗАПРЕЩЕНО (ADR-007).
Допустимо только: verified change -> proposed diff -> approval -> Vault update.

## Жёсткие запреты

- Не удалять файлы без явного разрешения.
- Не создавать .exe / .bat / .ps1 без запроса.
- Не модифицировать Projects/BrowserProfile.
- Не трогать src-tauri/, bridge.py, notion-bridge.mjs, если задача
  не говорит об этом прямо.
- Не добавлять npm-зависимости.
- Никакого Math.random, заглушек и выдуманных данных.
- Не убивать процессы и не перезапускать службы.
- Не создавать ветки и не делать коммиты без указания.

## Стиль правок

- Малые целевые правки вместо перезаписи файла.
- UTF-8 без BOM.
- py_compile для всех изменённых Python-файлов.
- Подписи в UI только через i18n-ключи (src/lib/i18n/ru.ts и en.ts).
- Перед использованием общего компонента прочитать его исходник и
  использовать ровно те значения пропов, которые он принимает.
- Значений по умолчанию не выдумывать. Нет данных - показывать
  честное "не определено".
- UI не имеет права показывать ложное состояние бэкенда (INV-UI-001).
- При изменении UI не удалять существующие кнопки и функции.

## Порядок работы

request.md -> response.json -> validate -> apply -> after-patch проверка.

В начале любой задачи: git status и проверка, не сделана ли часть
работы предыдущим прогоном (мост мог оборваться). Исходное состояние
описать в отчёте.

## Формат отчёта

1. Исходное состояние: вывод git status и гейтов до начала.
2. Список изменённых файлов.
3. Какие гейты запущены и последние строки их вывода дословно.
4. Что НЕ сделано и почему.

Отчёт без пункта 3 невалиден независимо от пунктов 1-2.
