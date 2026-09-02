# ГЛУБОКИЙ АУДИТ LocalComet — 2026-09-02

- **Режим:** read-only. Код не изменялся. Приложение не запускалось.
- **Объект:** ветка `feat/up00-wp01-windows-one-click-launch`, HEAD `fd4b100` + незакоммиченный WIP (удаление 22 мёртвых модулей, ~+7 073 / −26 734 строки, 86 файлов).
- **Метод:** 4 независимых исследовательских прохода по подсистемам (модельный шлюз/загрузка моделей; оркестрация и длинные задачи; Rust/Tauri безопасность; Python sidecar + фронтенд) + очная верификация ключевых фактов (grep/чтение исходников, отмечено «✓ проверено»).
- **Известные находки AUD-001..013** (аудит 2026-09-01) не дублируются; здесь только новое.
- **Гейты в этой сессии не запускались** — явно фиксирую. Базовое состояние по аудиту 2026-09-01: все зелёные, кроме bundle-parity (comtypes-кэш, лечится byte-resync).

---

## 1. Executive summary (для владельца, простым языком)

**Хорошие новости.** Ядро безопасности и качества крепкое: цепочка одобрений опасных действий (токены, digest, single-use, TTL), файловый слой secure_fs (защита от обхода путей), IPC-протокол (рамки, лимиты, UTF-8), сторожевой таймер сайдкара с автоперезапуском, доверенная загрузка моделей с SHA-256. Это подтверждено и прошлыми аудитами, и этим.

**Главная системная проблема.** LocalComet сегодня спроектирован для *коротких* диалогов и *коротких* компьютерных задач. Долгие агентные задачи (часы, десятки шагов) невозможны **по конструкции**, а не из-за багов:

1. Вся память о задаче живёт в оперативной памяти — перезапуск сайдкара или приложения уничтожает задачу без возможности продолжить.
2. Жёсткие потолки: генерация убивается через 125 секунд; модель видит только 2 последних сообщения истории (лимит шлюза 4 сообщения / 16 КБ промпт); 10 вызовов инструментов за ход; 8 шагов компьютерных задач; первая же ошибка завершает задачу; вторая параллельная задача получает отказ «занято» — очереди нет.
3. Опасный шаг без пользователя = смерть задачи: на одобрение даётся 120 секунд, потом отказ, а отказ завершает весь ход (нет режима «отказался и продолжил»).

**Стабильность моделей vs LM Studio.** Свой llama.cpp-сервер LocalComet запускает грамотно (закреплённый exe, эфемерный порт, API-ключ, job object), но: смерть llama.cpp замечается только «когда кто-то спросит» (автоперезапуска нет), догрузки прерванной скачивания нет (с нуля), горячей замены модели нет, а 125-секундный сторож может убить длинную легальную генерацию (4096 токенов при ~20 ток/с = 205 с > 125 с).

**Самая серьёзная уязвимость нового раунда:** команда диагностики LSP запускает rust-analyzer над любой папкой, выбранной фронтендом, без токена одобрения — rust-analyzer по умолчанию выполняет `build.rs` и proc-макросы проверяемого репозитория. «Попроси агента посмотреть чужой репозиторий» = запуск чужого кода вне цепочки одобрений.

---

## 2. Уязвимости (безопасность) — новое

### SEC-1 · P0 · LSP-диагностика исполняет код недоверенного репозитория вне цепочки одобрений
- `src-tauri/src/lsp.rs:482-509` — `lsp_diagnostics(workspace_path, rel_path)`: путь берётся из вебвью как есть (проверяется только абсолютность/существование), токен одобрения не требуется; доступ разрешён через `capabilities/main.json:39` (`allow-lsp-diagnostics`).
- `src-tauri/src/lsp.rs:289-297` — инициализация rust-analyzer БЕЗ `initializationOptions`, отключающего `cargo.buildScripts` / `procMacro` / flycheck → rust-analyzer выполняет `cargo metadata/check` с build-скриптами и proc-макросами.
- `src-tauri/src/lsp.rs:36-61` — сервер ищется в PATH/`%CARGO_HOME%\bin` или через `LOCALCOMET_LSP_SERVER_PATH`.
- Сценарий: «проверь проект X» → вебвью вызывает `lsp_diagnostics("C:\...\untrusted-repo", ...)` → сборка build.rs чужого репо = произвольный код с правами пользователя. `coding_start` требует токен, а эта дорога — нет.
- Направление исправления: привязать `workspace_path` к подтверждённому workspace; передавать `{"rust-analyzer":{"cargo":{"buildScripts":{"enable":false}},"procMacro":{"enable":false},"checkOnSave":{"enable":false}}}`; рассмотреть токен одобрения.

### SEC-2 · P1 · `skills.rs`: голый `python` из PATH, скрипт ищется относительно cwd, среда наследуется целиком, таймаута нет
- `src-tauri/src/skills.rs:21-22` — `LOCALCOMET_TEST_PYTHON` иначе голый `python` из PATH процесса.
- `:25-34` — скрипт `skills_cli.py` ищется тремя cwd-относительными фолбэками; в установленном приложении, запущенном из произвольной папки, последний фолбэк может подхватить подложенный файл. Подписи/хэша нет.
- `:41-49` — `Command::new(python)` наследует всю родительскую среду (в отличие от `minimal_sidecar_environment` в `supervisor.rs:1608-1650`), без job-контейнера и без таймаута.
- `:133-137` — `skills_install` пробрасывает путь архива от фронтенда без Rust-валидации.
- Исправление: резолвить скрипт от каталога exe/ресурсов, пиновать полный путь python.exe, allowlist среды, ограничение времени, валидация архива.

### SEC-3 · P1 · `browser.py::open_local_site` — обход ограничения Projects (legacy-консольный контур)
- `modules/browser.py:246-252` — `folder` от модели попадает в `PROJECTS_DIR / folder / "index.html"` без `safe_path()` (который везде используется, напр. `modules/files.py:122-136`). `open_url` (строки 226-235) отправляет сюда любую не-http(s) строку, включая `file://`. `folder="../.."` + `read_page` (275-301) = чтение index.html откуда угодно на диске в контекст модели.
- Исправление: `safe_path()`-контейнер + отказ от `file://`.

### SEC-4 · P2 · Брокер браузеров доверяет пользовательскому реестру (HKCU App Paths)
- `src-tauri/src/cu_broker.rs:547-559` — `chrome.exe` и др. резолвятся через HKCU **раньше** HKLM; same-user вредонос может перепривязать «запустить chrome» на свой бинарник (карта одобрения показывает ложную провенанс). Исправление: HKLM приоритетнее, показывать резолвнутый путь на карте.

### SEC-5 · P2 · CSP релиза содержит dev-источники и `unsafe-inline`/`data:`/`blob:`
- `src-tauri/tauri.conf.json:31` — `default-src` включает `http://localhost:1420/1421`, `ws://…`, `data:`, `blob:`. `script-src 'self'` корректен, `unsafe-eval` нет. Исправление: разделить devCsp/релизный csp, убрать dev-порты.

### SEC-6 · P2 · `allows_tool` для неизвестного инструмента = true (fail-open)
- `src-tauri/src/approval_commands.rs:358-379` — `_ => true`. Сейчас обхода нет (неизвестный инструмент падает на `risk_level_for_tool`), но новый инструмент без руки в `allows_tool` молча станет разрешённым. Исправление: инвертировать в allowlist.

### SEC-7 · P2 · URL-политика брокера пропускает `http://`, localhost, интранет, link-local
- `src-tauri/src/cu_broker.rs:259-290` и `intent_compiler.rs:171-213` — нет запрета `127.0.0.1`, RFC1918, `169.254.169.254`, `.local`; `http://` разрешён. Prompt-injected `open_url` = CSRF против роутера/локальных админок. Исправление: https-only для агентской навигации + denylist приватных хостов + показ класса хоста на карте одобрения.

### SEC-8 · P2 · `web.search` читает ответ без лимита и не проверяет grant на стороне Python
- `modules/tool_execution_ru.py:792-793` — `resp.read()` без ограничения (контраст: `_web_fetch:935` — 10 КБ). `web.search/web.fetch` отсутствуют в Python `DANGEROUS_TOOLS:56` — Rust-требование одобрения сайдкаром не перепроверяется; query-string = канал исходящего трафика модель-управляемый. Исправление: лимит чтения +Python-грант как для dangerous.

### SEC-9 · P3 (кластер)
- Синхронные Tauri-команды `run_tool_call`/`cu_broker_observe` блокируют UI-поток до 5 с (`approval_commands.rs:994`, `cu_broker.rs:32,1738-1790,1852-1858`) — сделать async/`spawn_blocking`.
- `emit("request_tool_approval")` broadcasts всем окнам; `resolve_tool_approval` не привязан к окну (`approval.rs:169`, `approval_commands.rs:436-462`) — использовать `emit_to("main")`.
- `cancel_artifact_download`/`get_artifact_download_state` без токена (`artifact_acquisition.rs:1294-1305`) — удобство, не дыра.
- llama.cpp наследует пользовательский PATH в остальном санитизированной среде (`managed_runtime.rs:1986-1987`) — риск late-binding DLL; задавать PATH=System32 всегда.
- `LOCALCOMET_INVISIBLE=1` скрывает окно при старте (`lib.rs:279-284`) — ок для скрытого тест-раннера, стоит гейтировать от сочетания с обычной сессией.

---

## 3. Баги и надёжность — новое

### BUG-1 · P0 · tool.call нельзя отменить; таймаут оставляет «зомби», который молча держит единственный слот
- `tools/run_localcomet_desktop_sidecar.py:115-122` — один worker, `lock.acquire(blocking=False)`; при таймауте Rust (`TOOL_CALL_TIMEOUT` 30 с / 180 с CU, `control_plane.rs:52-57`) просто уходит по таймауту (`wait_for_terminal`, `:2169-2207`) и удаляет запись — Python ДОрабатывает инструмент, слот занят, все новые tool.call получают `busy`. Health-пробы отвечают (инлайн, `:165-180`) → сторож перезапуска НЕ видит. Cancel-конверт в контракте есть (`desktop_ipc_contract_ru.py:279`), но не используется для tool.call.

### BUG-2 · P0 · Состояние задач только в памяти; рестарт сайдкара = потеря всего
- Rust: `control_plane.rs:975-998` (`ModelRequestRegistry`), при сбое живости `fail_pending` (`:2252-2269`) рассылает `model.turn.failed` и всё; `supervisor.rs:1054`.
- Sidecar: сессии/ходы — датаклассы в RAM (`desktop_control_plane_ru.py:244-287`).
- Фронтенд: `chatMessages = writable(...)` (`shellStore.ts:42`), localStorage/indexedDB нет; контракт `files.ts:78` прямо требует `current_process_memory_only`.
- При этом `task_ledger.rs` (персистентный, hash-chained, с `recover()` `:425`) существует — но подключён только к coding-оркестратору.

### BUG-3 · P1 · Неожиданное исключение: в tool-воркере = тихое зависание; в остальных обработчиках = смерть сайдкара
- `run_localcomet_desktop_sidecar.py:138-150` — ловится только `IPCProtocolError`; любое другое исключение (`tool_execution_ru.py:1008-1012` re-raise в `_skills_invoke`) убивает воркер-поток БЕЗ ответа → карточка вечное WAITING (нарушение INV-UI-001 духа).
- `:179-188, 224` — вне tool.call любое исключение убивает весь процесс. Достижимо: `desktop_control_plane_ru.py:1109` — `self._turns[turn_id].prompt_text` без `_require_turn` (KeyError = смерть).

### BUG-4 · P1 · 125-секундный сторож может убить легальную длинную генерацию ✓ проверено
- `control_plane.rs:62` `MODEL_REQUEST_WATCHDOG_TIMEOUT=125s`; `managed_runtime.rs` запускает llama.cpp c `--n-predict 4096` (`:1941-1942` ✓ проверено). 4096 токенов при 15-20 ток/с = 205-270 с → ход будет убит «по таймауту» без вины модели. LM Studio такого потолка не имеет.

### BUG-5 · P1 · Память модели = 2 сообщения; длинный диалог невозможен ✓ проверено
- `local_model_gateway_ru.py:487-488` — `maximum_prompt_bytes=16_384`, `maximum_messages=4` ✓; превышение = GatewayError `invalid_payload` (`:2907-2910`).
- Фронтенд обходит: `modelGateway.ts:1215-1218` `nonSeedMessages.slice(-2)` ✓ — модель не видит собственные ранние ответы. Компактации/суммаризации/токен-учёта нет нигде.

### BUG-6 · P1 · Смерть llama.cpp замечается лениво; автоперезапуска нет ✓ проверено
- `managed_runtime.rs:253-290` — exited-детект только внутри `status()` по факту запроса; периодического опроса нет (grep call-sites ✓). Никакой watchdog-тред не перезапускает упавший runtime (в отличие от сайдкара — там сторож образцовый).

### BUG-7 · P1 · Retry-флаги существуют, но никто их не потребляет; первая ошибка = конец задачи
- `local_model_gateway_ru.py:1636-1642` — `empty_model_output` помечен `retryable=True`; `BridgeError::with_retryable` (`control_plane.rs:505`) — но циклов ретрая нет ни в сайдкаре, ни в Rust, ни в FE (`retryLocalModelTurn` — только ручной, `modelGateway.ts:1355`).
- `core/loop.py:47-50` — любое исключение шага = `return error_text` (задача умерла); `next/app_v5.py:2018-2021` — одно исключение убивает очередь.

### BUG-8 · P1 · Одобрение: 120 с TTL, отказ = смерть хода; unattended-режима нет
- `approval.rs:14` (TTL 120 с), `:179-197` (timeout → Reject); `modelGateway.ts:1536-1547` — `blocked` → терминализация всего запроса `tool_execution_blocked`. Отсутствие пользователя на 3 минуты гарантированно убивает задачу на первом опасном действии.

### BUG-9 · P1 · Конкурентность = мгновенный отказ, очереди нет
- `local_model_gateway_ru.py:1080-1082` — вторая инференция → `GatewayError("busy")`, retryable, но очередь не строится; tool.call — тот же паттерн (`run_localcomet_desktop_sidecar.py:115-122`). Rust-реестр пускает 32 запроса (`control_plane.rs:20`), но под ним всё сериализуется отказами.

### BUG-10 · P2 · Утечки/неограниченный рост (долгоживущий процесс)
- `computer_use_continuation_ru.py:37,144` — `_consumed` растёт вечно; `_prune_expired` (`:160-165`) никогда не вызывается.
- `modules/files.py:218-233` — `rollback` читает файлы целиком без `MAX_FILE_BYTES`; журнал `_rollback_journal:203` не очищается.
- `local_model_gateway_ru.py:471-479` — `_cu_debug` пишет в захардкоженный `%TEMP%\localcomet-cu-debug.txt` ПО УМОЛЧАНИЮ, append-only, без ротации.
- `stores/controlPlane.ts:55` — `lastSequenceByReplyTo` не чистится; `controlPlane.ts:25` — только 100 событий в памяти (для аудита длинного прогона недостаточно, персистенции нет).
- `modules/tool_execution_ru.py:336-348` — `_files_list` без лимита записей; >10k записей падает в `IPCProtocolError` → путь тихого зависания BUG-3.

### BUG-11 · P2 · Расхождение источников истины (не покрыто гейтами)
- Python `COMPUTER_USE_READ_ONLY_ACTIONS` (`tool_execution_ru.py:64-66`: screenshot/wait/wait_for_window/observe/scroll) ≠ Rust (`approval_commands.rs:572-573`: + cursor_position/mouse_move). Легальные хост-вызовы mouse_move получают `approval_required` от Python. Гейта на CU action-sets нет (parity-гейты покрывают только tool-реестры).
- `desktop_sidecar_runtime_ru.py:338` — health пин `"toolExecution": False` при реально работающем tool.call; `supervisor.rs:559-565` убивает сайдкар при `True`. Двойной смысл — мина при рефакторинге.
- Sequence-нумерация: control-plane ответы используют `sequence=len(result.events)`, остальное — глобальный счётчик (`desktop_sidecar_runtime_ru.py:365-372`).

### BUG-12 · P2 · Фронтенд control-plane конвейер без страховки
- `bridge/controlPlane.ts:43-49` — `validateEvent` в listen-callback без try/catch (модельный шлюз так обёрнут, этот — нет); `stores/controlPlane.ts:146,158` — `event.metadata.title` без проверки → TypeError убивает поток событий вместо честной ошибки.
- `modelGateway.ts:1387` — ранняя рассинхронизация sequence молча выбрасывает событие (лимит буфера 2048, `:107`).

### BUG-13 · P2 · Прочее
- `ApprovalModal.svelte:75-95` — после одной неудавшейся попытки resolve таймер авто-дизмиса не перезаводится → карточка живёт вечно, пока Rust уже всё отменил.
- Traceback с локальными путями (`C:\Users\DNS\...`) возвращается в чат-карточки (`computer_use_real_actions_ru.py:2634-2635` → `tool_execution_ru.py:423-501` → `modelGateway.ts:1519,1527`); санитайзер применяется только к логам.
- `computer_use_full_control_mission_ru.py:987-1129` — перепатч `_plan_actions`/`_execute_action` блоком «v6.53 upgrade» внизу модуля — хрупко при рефакторинге.
- Скачивание модели без resume: `.partial` пересоздаётся с нуля, HTTP Range не используется (`artifact_acquisition.rs:679-694`, `cleanup_stale_partials:222` ✓ проверено).
- `browser.py` глобальные `_playwright/_browser/_page` без блокировок (`:10-13,82-99`); `_is_closed_error` матчит подстроку `"closed"` (`:37`).
- i18n: ru=en 977=977 ключей — паритет в норме; 15 из 27 кодов `chat.reason.*` не имеют ключей (грейсфол на сырой код — не ложное состояние, но непереведено).
- Версии согласованы: Cargo.toml = tauri.conf.json = version.ts = package.json = sidecar = 7.0.5 ✓ проверено.

---

## 4. Модельный путь: чего не хватает до «LM Studio-стабильности»

Что УЖЕ есть (сильные стороны): pinned llama.cpp + эфемерный порт + API-ключ + job object с memory ceiling; SSE-стриминг end-to-end с inactivity-timeout (10 с/45 с управляемый) и честной отменой (`local_model_gateway_ru.py:2362`, FE `cancelLocalModelTurn` с 5-с таймером ack); каталог HF с https-pinning, redirect-валидацией, per-member hash/size, zip-контейном; настройки `--ctx-size` (clamp 1024..131072, override ✓) и `--gpu-layers` (override + `--fit off` ✓ проверено).

Чего НЕТ (gap-лист против LM Studio):

| # | Возможность LM Studio | LocalComet сегодня | Приоритет роста |
|---|---|---|---|
| 1 | Генерация без искусственного потолка времени | 125-с сторож убивает ход (`control_plane.rs:62`) при `--n-predict 4096` | **P0**: перенести лимит на per-stream inactivity (уже есть 10-45 с), сторож только для «ничего не происходит» |
| 2 | Смерть сервера = мгновенно видно, модель перезапускается | Ленивый status-чек, автоперезапуска нет (`managed_runtime.rs:253-290`) | **P0**: фоновый poll + авто-restart + пере-attach хода |
| 3 | Память диалога на всю сессию | 2 сообщения / 4 msg / 16 КБ (`local_model_gateway_ru.py:487-488`, FE `slice(-2)`) | **P0**: поднять лимиты + компакция истории (суммаризация, токен-учёт) |
| 4 | Очередь запросов при занятой модели | Мгновенный отказ `busy` (`local_model_gateway_ru.py:1080-1082`) | **P1**: bounded queue или честный «подожди, идёт генерация» UI |
| 5 | Прогресс загрузки модели / VRAM-оценка | Не найдено событий прогресса загрузки | **P1**: прогресс-события старта runtime |
| 6 | Горячая замена модели | Не найдено (`grep hot_swap/swap_model/set_model` — пусто ✓) | **P1**: перезапуск runtime с новой GGUF без рестарта приложения |
| 7 | Догрузка прерванного скачивания | Скачивание с нуля, нет HTTP Range (`artifact_acquisition.rs:679-694`) | **P1**: Range-resume |
| 8 | Keep-loaded TTL | Runtime живёт до явной остановки — фактически ок, но не конфигурируется | **P3** |
| 9 | Внешний сервер (LM Studio/OpenAI-compat) как бэкенд | Убран из desktop-пути (остатки только в legacy `auto_verification.py`, `browser_operator.py`) | **P2** (опция): provider-слой с выбором бэкенда |

Внешние LM Studio-эндпоинты в коде desktop-пути НЕ используются (✓ проверено: совпадения только в legacy-модулях вне цепочки шлюза).

---

## 5. Длительные агентные задачи: readiness-план

Фундамент есть: `task_ledger.rs` (NDJSON + snapshot hash-chain + `recover()`), `checkpoint.rs`, `coding_orchestrator.rs` (resume от AwaitingApproval, rollback), autonomy-политика с бюджетами, компьютерные миссии пишут run.json/events.jsonl. Но всё это не подключено к диалоговому агентному циклу.

**Фаза 1 — «выживает» (P0):**
1. Персистентное состояние задачи: подключить `task_ledger.rs` к чат-циклу (или персистенть `_Turn/_Thread` в сайдкаре); при рестарте сайдкара — восстанавливать незавершённые задачи в возобновляемое состояние вместо `fail_model_requests`.
2. Отменяемые tool.call: `tool.cancel` метод + кооперативные проверки отмены + убийство/отсоединение воркера по таймауту (BUG-1).
3. Очередь задач вместо `busy`-отказов (BUG-9), персистентная.
4. Авто-ретрай с backoff по уже существующим `retryable`-флагам (BUG-7).

**Фаза 2 — «тянется часами» (P1):**
5. Переструктурировать потолки: вместо per-request lifetime (125 с, 10 tool calls, 8 шагов) — per-step бюджеты + чекпоинты между шагами.
6. Компакция контекста (суммаризация старых ходов, токен-учёт) — BUG-5.
7. Unattended-режим одобрений: очереди одобрений с длинным TTL / deny-and-continue / батч-гранты по классам действий (BUG-8).
8. Подключить wall-clock бюджет: `runtime_seconds_used` отсутствует в `AutonomousRunState` (`autonomous_run_state_ru.py:54-75`), лимит 900 с в `autonomy_policy_ru.py:102-119` — мёртвый код.
9. Watchdog управляемого llama.cpp с авто-перезапуском (BUG-6).

**Фаза 3 — «качественно» (P2):**
10. Доуerved-лог чат-задач (сейчас только CU-миссии пишут events.jsonl) — разбор полёта после крэша.
11. Реальный итеративный агентный цикл: результаты инструментов возвращаются модели как continuation-ходы (сейчас ход терминален после tool calls; есть только 2 жёстко ограниченных continuation).
12. Бюджет replans (`max_replans=3` зарезервирован, не тратится никем) + wiring `first_failure_extractor` в контроллер ретраев.
13. Гигиена стоп-файлов: TTL/автоочистка `agent_mission_stop_requested.json` (`computer_use_agent_mission_ru.py:331` — застрявший файл блокирует все будущие миссии).
14. Консолидация patch-on-patch определений в `computer_use_full_control_mission_ru.py`.

---

## 6. Что проверено и чисто (без находок)

- ACL-матрица: 88 команд `lib.rs:311-391` против capabilities/permissions и всех `invoke()` фронтенда — соответствие полное (кроме известных execute_approved и get/open_model_storage_info).
- Цепочка одобрений: 256-бит CSPRNG токены, constant-time сравнение, single-use + tombstone, TTL 300 с/гранты 30 с, инвалидация при смене workspace, idempotency-реестр.
- secure_fs: NT handle-relative + OBJ_DONT_REPARSE + реверификация final-path; reparse-точки отклоняются на каждом предке.
- IPC-контракт: 4 MiB в обе стороны, 0-длина/частичные/UTF-8/дубли ключей/NaN/циклы — fail-closed.
- cu_broker: deny-by-default, статический реестр из 9 целей, реверификация grant по байтам, hidden-режим fail-closed.
- artifact_trust: https-pinning, ручной redirect-цикл с валидацией хоста на каждом хопе, SHA-256 при скачивании, zip member-allowlist, TOCTOU-контроль, approval-гейт.
- Модельный шлюз: все блокирующие чтения с дедлайнами + watchdog-тред; широкий except конвертируется в честный `model.turn.failed`.
- `_web_fetch`: SSRF-защиты (scheme/port allowlist, приватные IP, DNS-pinning, без редиректов/прокси, 10 КБ лимит).
- gguf_metadata: bounded-курсор, без паник на атакующих байтах.
- Секреты: ключей/токенов в дереве нет; телеметрии нет; devtools в релизе выключены.

---

## 7. Формальности отчёта (по AGENTS.md)

1. **Исходное состояние:** ветка `feat/up00-wp01-windows-one-click-launch`; git status — 86 изменённых файлов WIP (удаление мёртвых модулей и сопутствующее), HEAD `fd4b100`. Гейты в этой сессии не запускались — база взята из аудита 2026-09-01 (все зелёные, кроме bundle-parity/comtypes, AUD-001).
2. **Изменённые файлы:** код НЕ изменялся. Создан только этот отчёт.
3. **Гейты:** не запускались (read-only аудит, фокус на анализе кода). При фиксации любых находок из этого отчёта — полный battery по AGENTS.md обязателен.
4. **Не сделано:** динамическое тестирование (запуск приложения/эксплойтов), fuzzing IPC, аудит сторонних зависимостей (cargo audit/npm audit), проверка установленного инсталлятора. Приоритет верификации — SEC-1 (LSP) и BUG-1 (tool-call zombie) на живой системе.
