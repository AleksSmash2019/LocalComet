# База точек роста LocalComet — уроки 11 опенсорс-проектов (2026-09-03)

- Режим: read-only исследование + запись отчёта. Код не изменялся.
- Метод: веб-исследование актуальных docs/репозиториев aider, Continue.dev, Cline (+Kilo Code как наследник Roo Code),
  Goose, LM Studio, Jan, Ollama, Open WebUI, AnythingLLM, LiteLLM, llama.cpp server; сверка с текущим деревом
  LocalComet (ветка `feat/up00-wp01-windows-one-click-launch`, HEAD `d24d80e` + незакоммиченный WIP) и Vault-статусом v7.0.5.
- Класс доказательств: C (research/intent). Ничего из нижеперечисленного не является фактом о коде LocalComet,
  пока не проверено гейтами. C никогда не переопределяет A.
- Связанные документы: `audit/DEEP_AUDIT_2026-09-02.md`, `audit/GROWTH_AND_SECURITY_REVIEW_2026-09-03.md`.

---

## 0. Краткая карта текущего состояния LocalComet (от чего отталкиваемся)

Есть: approval-цепочка с одноразовыми токенами и TOML-реестром рисков (deny-by-default), SHA-256 + GGUF-magic +
host-pinning + TOCTOU-реверификация артефактов, evidence-цепочка с provenance-гейтом, managed runtime (CPU/Vulkan),
skills с pinned python + таймаутом (в WIP), Computer Use брокер с allowlist, кодинг-контур (checkpoint/rollback),
i18n ru/en, tight CSP (в WIP).

Нет (подтверждено аудитами 01–03.09): долгая память диалога (лимит 4 msg / 16 КБ gateway + `slice(-2)` на фронте);
персистентность чатов (task_ledger написан, к чату не подключён); очередь запросов (мгновенный `busy`);
авто-ретрай (`retryable=True` производится, потребитель отсутствует); дозагрузка моделей (нет HTTP Range);
отмена `tool.call` (cancel-конверт rejected); unattended-режим одобрений (TTL 120с, отказ = смерть хода);
встроенный RAG/knowledge (только web.fetch 10 КБ + web.search без лимита — H2); мультимодельность/роутер;
сервер-режим для сторонних приложений; рецепты/шаблоны задач; тянется расхождение watchdog 125с vs 615с в AGENTS.md.

---

## 1. Aider (Apache-2.0, терминал, ~эталон кодового агента)

Источники: aider.chat, docs (repomap, modes, watch), GitHub Aider-AI/aider, обзор 06.2026.

### 1.1 Repo Map через tree-sitter + PageRank — взять как есть идею
Aider строит карту всего репозитория (классы/функции/сигнатуры, без тел) через tree-sitter, ранжирует
графом PageRank по зависимостям файлов, укладывает в бюджет (дефолт 1024 токена, адаптивно расширяется),
кеширует в SQLite. LLM видит структуру всего проекта, не загружая файлы; нужные файлы дочитывает точечно
(`/add`). Это прямой ответ на BUG-5 LocalComet (память 2 сообщения): вместо «больше сообщений» — «умный
контекст»: карта символов проекта + релевантные куски. Ложится в gateway как новый контекстный слой между
каталогом и промптом, бюджет токенов — в `GatewayLimits` рядом с 16 КБ.

### 1.2 Режимы ask / code / architect (+editor-model) — взять
Три режима чата + двухмодельный architect (дорогая reasoning-модель планирует, дешёвая — правит; −30–50%
стоимости сложных задач). Для LocalComet: режим «Спросить» без мутаций (снимает половину approval-нагрузки и
страх «сломает»), режим «Архитектор» (план → approve плана → исполнение — готовый прототип unattended-режима
из §4 GROWTH_REVIEW). Связка с Ollama-совместимыми локалками: architect = большая модель, editor = малая.

### 1.3 Git-интеграция: автокоммит каждого шага осмысленным сообщением — взять частично
У aider каждое изменение — атомарный коммит с generated message; откат стандартным git. У LocalComet уже есть
checkpoint/rollback — не хватает «истории агента как git-истории»: коммит/тег на каждый approved ход
(опционально, в Projects). Даёт бесплатный undo, аудит и основу для рецептов (§5.2).

### 1.4 Watch mode (`--watch-files` + `AI?`/`AI!` комментарии) — взять для кодинг-контура
Aider следит за файлами и выполняет однострочные `AI!`-инструкции прямо из IDE без плагина. Для LocalComet:
маркер-комментарии в Workspace как второй вход задач (рядом с чатом) — дёшево, эффектно для кодинг-сценариев.

### 1.5 Lint/test после каждого изменения с автофиксом — взять
Aider прогоняет линтеры/тесты после каждой правки и сам чинит найденное. LocalComet: после `files.write` через
approval — hook «прогнать `cargo check`/`tsc`/целевой тест → при падении вернуть вывод модели следующим ходом».
Это готовый потребитель `retryable`-флагов (BUG-7): ретрай не слепой, а с новым контекстом ошибки.

### 1.6 Контекстная дисциплина (`/add /drop /tokens /clear`) — взять в UI
Aider в явном виде учит: >25k токенов контекста — надёжность правок падает; файлы добавляются/снимаются
вручную, бюджет виден (`/tokens`). LocalComet: индикатор «контекст N/лимит» + ручное attach/drop файлов в
композер + `/clear`-аналог. Дешёвый UI-слой поверх существующего gateway.

### 1.7 Copy/paste-режим для веб-чатов и voice-to-code — отложить
Нишевые фичи; voice в LocalComet уже есть (RHVoice/Piper), копипаст-режим не нужен при своём UI.

---

## 2. Continue.dev (Apache-2.0, IDE-расширение + Agent mode)

Источники: docs.continue.dev (context providers, MCP, rules, config.yaml, codebase-awareness).

### 2.1 `@`-контекст-провайдеры — взять как UX-паттерн
Набор `@code @docs @terminal @problems @os @currentFile...` — явное, discoverable добавление контекста.
LocalComet: `@`-меню в MessageComposer (файл из Projects, вывод терминала/рантайма, открытый документ,
URL). Технически — типизированные вложения к `model.turn.start`, не «магия».

### 2.2 Docs-indexing (`docs:` в config + Context7 MCP) — взять
Continue индексирует указанные доки и подмешивает релевантные куски; устаревшие `@Docs` заменены MCP.
LocalComet: встроенный индекс собственной документации + user-документов (см. RAG §7): маленький локальный
индекс (SQLite FTS + эмбеддинги через текущий движок, embeddings-эндпоинт уже есть в llama.cpp server).

### 2.3 Rules (`.continue/rules/*.md`, glob/regex/alwaysApply, генерация правила из диалога) — взять
Правила-уровни: alwaysApply / по glob / по решению агента; агент сам умеет создать правило из разговора
(`create_rule_block`). LocalComet: `.localcomet/rules/` в Projects + `AGENTS.md`-совместимость: правила проекта
подмешиваются в system message; команда «запомни как правило» пишет файл только через approval (память
принадлежит проекту, ADR-007 — механизм уже идеологически готов).

### 2.4 Agent mode с file/search/git-инструментами + Hub (переиспользуемые конфиги) — взять частично
Агентный режим = chat + инструменты навигации по коду. У LocalComet инструменты есть, не хватает «правил +
инструменты навигации в одном лице» и шаринга конфигов (Hub): экспорт/импорт пресета «модель+правила+инструменты»
файлом — задел под рецепты (§5).

### 2.5 config.yaml (models/context/rules/prompts/docs/mcpServers/data) — взять как формат
Декларативный YAML-агент — готовый формат для рецептов LocalComet и для user-пресетов моделей. Совместимость
с `.continue/mcpServers/*.json` даст бесплатную экосистему MCP-конфигов.

---

## 3. Cline (Apache-2.0, 58k+ звёзд) / Kilo Code (наследник Roo Code)

Источники: cline.bot, GitHub cline/cline, сравнения Cline vs Roo 2026.

### 3.1 Plan/Act-переключатель — взять обязательно (топ-приоритет UX)
Plan: агент исследует код, задаёт вопросы, кладёт письменную стратегию — ни байта не меняется. Act: исполнение
с approve каждого шага или auto-approve. Это ровно недостающий LocalComet «режим длинных задач»: план как
артефакт, который можно approve целиком (unattended для approved-плана), а не каждый tool.call отдельно.

### 3.2 Checkpoints перед каждым деструктивным шагом + Restore — взять
Cline/Roo ставят чекпоинт перед каждой опасной правкой, откат в один клик. LocalComet checkpoint есть на
уровне файлов — поднять до UI-сущности «точка восстановления» на ход (список, restore, diff). Связка с §1.3.

### 3.3 Моды Architect/Ask/Debug/Orchestrator (+custom modes marketplace) — взять
Roo/Kilo: 5 встроенных режимов с разными system prompt и тулсетом; кастомные моды публикуются. LocalComet:
режимы — естественное расширение §1.2; Debug-режим (анализ ошибок + трассировка) прямо ложится на кодинг-контур.

### 3.4 MCP Marketplace в один клик — взять
Cline: курируемый каталог MCP-серверов с установкой из панели. LocalComet: каталог skills/MCP в UI (skills уже
есть как сущность — добавить реестр + one-click install + allowlist по §6.4). Осторожно: предупреждение LM
Studio/Open WebUI — «MCP = исполнение кода, только доверенные источники».

### 3.5 Headless CLI + Kanban параллельных агентов (worktree-изоляция) — взять по частям
Cline CLI работает headless в CI; Kanban раздаёт агентам изолированные worktree с auto-commit и цепочками
зависимостей. LocalComet: headless-режим сайдкара для скриптов (рядом с `--mode=cli` smoke) + очередь задач как
первый шаг к параллельности (§6.2). Worktree-изоляция — готовый ответ на confinement-риски.

### 3.6 SDK для встраивания агента — отложить
Cline SDK (программный API агента). Для LocalComet актуально позже, когда появится сервер-режим (§8.3).

### 3.7 Урок провала: «$200 за один ран без Plan» — процессное
Все источники хором: multi-file задачи без pre-review плана сжигают токены. Вывод для LocalComet: для малых
локальных моделей (1.7B–27B) Plan-режим не роскошь, а экономия — планировщик может быть даже эвристическим
(детерминированный план из diff/stat), а не LLM.

---

## 4. Goose (MIT, Block, Rust+десктоп+CLI+API)

Источники: goose-docs.ai (permissions, recipes, session-recipes, recipe-reference), GitHub block/goose.

### 4.1 Три уровня разрешений на инструмент (Always allow / Ask before / Never allow) + режимы Manual/Smart — взять
Goose: per-tool трёхуровневые разрешения поверх режимов; рекомендация ≤25 активных инструментов (качество
выбора модели падает с ростом тулcета). LocalComet строже (риск из TOML, а не «мнение LLM») — но UX-слой
поверх: пользовательские overrides «всегда спрашивать/никогда» для guarded-инструментов + счётчик активных
тулов с предупреждением. Это же — «доверенный профиль» для длинных задач (§4 GROWTH_REVIEW п.7).

### 4.2 Recipes (YAML: instructions/prompt/extensions/parameters/retry/structured output/sub_recipes) — взять обязательно
Переиспользуемые шаблоны задач с параметрами, валидацией (`goose recipe validate`), retry-логикой с проверками
успеха (`retry: max_retries + checks: shell command + on_failure`), `/recipe` — сгенерировать рецепт из текущей
сессии, расписание по cron, sub-recipes с параллельным/последовательным исполнением, `max_turns` против
runaway-агентов. Для LocalComet это закрывает сразу BUG-7/9 (очередь+ретрай), unattended (расписание) и обмен
опытом. Формат — YAML по образцу recipe-reference, валидатор — гейт по образцу остальных `check_*.py`.

### 4.3 Scheduled jobs (cron, background/foreground) — взять
Фоновые recipe по расписанию с историей сессий. LocalComet: планировщик поверх очереди (§6.2) + Rust-сторона
должна уметь «нет человека» (см. §4.1 режимы). Безопасность: scheduled = только pre-approved recipe + дайджест.

### 4.4 Built-in Memory + Chat Recall + Todo extensions — взять
Память между сессиями, поиск по прошлым разговорам, таск-менеджмент внутри сессии. LocalComet: Memory =
персистентный task_ledger + embeddings-поиск по истории (см. §7); Todo = структурированный task-list из
compound task (уже есть max 8 шагов — добавить видимый чеклист в UI).

### 4.5 Goosehints / AGENT.md — взять (бесплатно)
Проектные инструкции из файла в корне репо, читаются каждый старт сессии. LocalComet уже требует AGENTS.md —
осталось реально инжектить его (и `.goosehints`-совместимость) в system message кодинг-задач.

### 4.6 Extension secrets в системном keyring — взять
Секреты MCP-расширений хранятся в OS keyring, не в конфиге. LocalComet: креды/токены (будущий server-auth,
MCP env) — только через OS credential store, никогда в SQLite/app-data. Перекликается с NA-005.

---

## 5. LM Studio (проприетарный, ориентир local-first UX)

Источники: lmstudio.ai/docs, llms-full.txt, гайды 2026 (v0.4.23, Engine Protocol, Bionic).

### 5.1 Engine Protocol (движки как версионируемые артефакты отдельно от приложения) — взять архитектурно
С 0.4.19 движки обновляются независимо от приложения. LocalComet UP05 уже задумывал runtime-neutral интерфейс:
оформить `runtime_id`-контракт + независимое версионирование бандлов CPU/Vulkan + `lms runtime update`-аналог
(проверка обновлений рантайма с SHA-пиннингом). Авто-restart (d24d80e) уже есть — добавить health-метрики движка.

### 5.2 OpenAI- + Anthropic-совместимый сервер + нативный REST/SDK + CLI + headless daemon — взять как сервер-режим
`lms server start`, `/v1/*`, `/v1/messages`, stateful chats, load/unload/download по API, `previous_response_id`,
`tool_choice`, streaming SSE, capabilities в `/v1/models` (`tool_use`). LocalComet: сервер-режим по формуле
LM Studio — loopback default, opt-in LAN с auth-токеном в момент открытия, idle-TTL auto-eviction моделей
(экономия VRAM при нескольких моделях). Плюс `capabilities`-массив — честное обнаружение возможностей вместо
догадок (снимает класс «UI выдумал состояние» системно).

### 5.3 MCP Host + tool confirmation с редактированием аргументов + always-allow — взять UX
Диалог подтверждения показывает точные аргументы, их можно отредактировать; «всегда разрешать» управляется в
настройках. LocalComet ApprovalCard: добавить edit-args перед approve — сильный UX-ход без потери строгости
(отредактированные аргументы = новый digest = новый approve, инвариант цел).

### 5.4 RAG «чат с документами» полностью офлайн (full-inject малых + retrieval больших) — взять
Перетащил PDF/DOCX/TXT → чат; короткое — целиком в контекст, длинное — RAG с настройкой. Ничего не покидает
машину. LocalComet: ровно этот UX поверх §7.

### 5.5 Discover-каталог + one-click MCP install (deeplink `Add to LM Studio`) — взять осторожно
Каталог моделей с встроенным снапшотом + живой статистикой; deeplink-кнопки установки MCP. LocalComet:
подписанный обновляемый каталог (vs зашитый в бинарник сейчас) + deeplink `Add to LocalComet` для skills/MCP —
только с проверкой подписи и allowlist хостов (урок Probllama).

### 5.6 Bionic (отдельный агентный продукт поверх того же рантайма) — стратегия
LM Studio выделил агентов (документы, кодинг, computer control, голос) в отдельный продукт на том же runtime.
Урок для LocalComet: держать ядро (control plane + runtime) отделённым от агентных слоёв — тогда «агент для
кода», «агент для ПК», «голос» переиспользуют approval/evidence бесплатно. Архитектурно уже так; не смешивать.

### 5.7 Idle TTL + CUDA tensor parallelism + MTP speculative decoding — взять в рантайм
Автовыгрузка простаивающих моделей; спекулятивное декодирование (MTP стабильно с 0.4.14). LocalComet: idle-TTL
в managed runtime + ngram-speculative флаги llama.cpp (бесплатное ускорение без доделки модели, см. §10.3).

---

## 6. Jan (Apache-2.0(?), open-source ChatGPT-замена, llama.cpp внутри)

Источники: jan.ai/docs, GitHub janhq/jan (0.8.4).

### 6.1 Projects (чаты + общие инструкции + файлы) — взять обязательно
Организация работы проектами: набор чатов с общими инструкциями и файлами. LocalComet Projects уже есть как
 confinement-граница — поднять до UX-сущности «Проект»: свои инструкции, свои файлы, своя история, свой дефолтный
 движок/модель. Это же решает «память»: память скоупится на проект, а не на 2 сообщения.

### 6.2 Assistants (именованные пресеты: модель+инструкции+инструменты) — взять
«Python Tutor», «Code Reviewer» как конфиг-обёртки + динамические переменные (`{{USER_NAME}}`, `{{DATE}}`).
LocalComet: пресеты ассистентов поверх рецептов (§4.2) — разница: assistant = persona, recipe = задача.

### 6.3 Local API server с привязкой 127.0.0.1/0.0.0.0 + API key + CORS + логи — взять как образец сервер-режима
Jan показывает эталонные настройки: бинд по умолчанию loopback, ключ обязателен при открытии наружу, CORS-
переключатель, server-side tool execution как opt-in, request timeout для медленного железа, живые логи
запросов. Скопировать панель настроек целиком при реализации §8.3.

### 6.4 Креды в backend-хранилище (не в UI-сторадже) — взять
Jan 0.8.4 перенёс settings/credentials в backend store. LocalComet: то же правило — секреты только Rust-side
(OS keyring по §4.6), фронт хранит лишь нечувствительные uiPreferences.

### 6.5 Token counter + per-model chat-template kwargs — взять
Счётчик токенов в UI (прозрачность контекста, §1.6) и per-model kwargs шаблонов чата — для LocalComet это
«профиль модели»: шаблон, стоп-строки, tool-формат на модель, а не глобально.

---

## 7. Ollama (open-source рантайм + реестр)

Источники: docs.ollama.com, GitHub ollama/ollama (api.md, tool-calling, structured-outputs).

### 7.1 Modelfile (FROM/PARAMETER/SYSTEM/TEMPLATE как Dockerfile) — взять
Версионируемая «упаковка» модели+промпта+параметров в один артефакт + `ollama create/push` (шеринг кастомных
моделей). LocalComet: «профиль модели» файлом (база + system + параметры + tool-формат + SHA ожиданий) —
решает per-model капризы tool calling и даёт шаринг без бинарников.

### 7.2 `keep_alive` + `ollama ps/stop` + выгрузка пустым промптом — взять
Явное управление временем жизни модели в памяти (TTL на запрос). LocalComet managed runtime: `keep_alive`
параметр + `ps`-аналог (что загружено, сколько держим) + idle-eviction (перекличка с §5.7).

### 7.3 Parallel tool calling + agent loop в SDK-примерах — взять паттерн
Ollama документирует параллельные tool_calls и agent-цикл с явным склеиванием `thinking/content/tool_calls`
при стриминге. LocalComet gateway: разрешить параллельные независимые tool.calls в одном ходе (сейчас модель —
max 10 вызовов последовательно?) + канонический пример agent-loop для своих инструментов.

### 7.4 Structured outputs (`format: json|schema`, Pydantic/Zod-советы, temperature 0) — взять
JSON-schema на ответ + понижение temperature для детерминизма. LocalComet: schema-constrained выводы для
внутренних контрактов (парсинг tool_calls, классификации) — снижает «галлюцинация → действие», усиливает
approval-цепочку без её изменения. llama.cpp server это уже умеет (`response_format`) — только прокинуть.

### 7.5 Облачная ступенька (Ollama Cloud, `-cloud` суффикс, push своих моделей) — стратегия, не сейчас
Гибрид «локально по умолчанию, облако опционально для больших моделей». Для LocalComet — только как
отдалённая опция архитектуры (провайдерный интерфейс), без реализации: приватность — ключевое отличие.

---

## 8. Open WebUI (BSD-3 + branding clause, self-hosted платформа)

Источники: docs.openwebui.com (features, tools, pipelines/pipes), блог v0.11.1, GitHub.

### 8.1 Tool Approvals + `ask_user` (модель спрашивает структурированным вопросом) — взять оба
Апрув-карточка с точными аргументами + allow/deny с хоткеями, отказ возвращается модели (продолжает без
результата), решение липнет на разговор. `ask_user`: модель кладёт карточку-вопрос с 2–3 вариантами
(первый — recommended) + свободный ввод; без ответа чат ждёт (переживает reload). Для LocalComet `ask_user` —
недостающий примитив между «сделай» и «approve»: кларификация без убийства хода (лечит BUG-8 с фронта).

### 8.2 Агенты как конфиг-обёртки (Model presets: system+tools+knowledge+params, bound tools, access control) — взять
Модель + привязка знаний/тулов/параметров + per-user доступ. Перекличка с §6.2/§4.2: у LocalComet это
«assistant» (persona) поверх «recipe» (задача).

### 8.3 Knowledge/RAG по-взрослому: hybrid BM25+vector+rerank, 13 векторных БД, 8 OCR-движков, agentic retrieval, full-context mode — взять по частям
Минимальный жизнеспособный RAG для LocalComet (локально, без серверов): SQLite FTS (BM25-аналог) + эмбеддинги
текущего движка + rerank эвристикой/двумодельно; `#`-вставка документов в чат; full-context для коротких;
agentic retrieval (модель сама ищет по базе инструментами `query/grep/view` с пагинацией — скопировать набор
инструментов Open WebUI почти дословно: `query_knowledge_files/grep_knowledge_files/view_file`). OCR-движки —
позже, начать с текста/Markdown/PDF-text-layer.

### 8.4 Message queue («печатай, пока отвечает») + `/команды` (`/model /compact /fork /temporary /status`) — взять
Очередь сообщений (лечит BUG-9 с фронта: второе сообщение ждёт, а не «занято»); слеш-команды; `/compact` —
ручная компакция контекста (суммаризация — ответ на BUG-5!); `/fork` — ветвление диалога (дешёвая альтернатива
Plan-перебору); temporary-чаты без истории (приватный режим — в духе NA/приватности).

### 8.5 Память о пользователе (Memory facts между чатами) + артефакты (persistent key-value storage) — взять
Факты-память со скоупом + персистентное KV-хранилище артефактов (журналы, трекеры — personal/shared scopes).
LocalComet: Memory = проектная память (§6.1) + факты; KV = natural home для task_ledger и артефактов ходов.

### 8.6 Automations (cron-промпты в чат/канал) + Task management (модель ведёт task-list) — взять
Перекличка с §4.3/§4.4: планировщик + видимый чеклист. У Open WebUI — destination picker (чат vs канал):
для LocalComet destination = чат vs проект-лог.

### 8.7 Админ-панель будущего: usage analytics (токены/стоимость), model arena/ELO, banners, webhooks — отложить, но заложить схему
Сейчас single-user, но token-учёт (LLM10) нужен уже: логировать токены/время на ход в evidence — это и LLM10-
квоты, и данные для будущей арены, и база троттлинга.

### 8.8 Урок безопасности: Workspace Tools = shell-доступ — подтвердить текущий курс
Open WebUI прямо пишет: создание тулов = shell на сервере, только доверенным. LocalComet уже строже
(allowlist + approval + TOML). Держать планку; H1/H2 из аудита 03.09 — ровно этот класс.

---

## 9. AnythingLLM (MIT, all-in-one RAG+агенты, desktop+docker)

Источники: docs.anythingllm.com, GitHub Mintplex-Labs/anything-llm, обзоры 2026.

### 9.1 Workspaces как первичная абстракция (свои документы+RAG-настройки+модель+история) — взять обязательно
Изоляция по проектам из коробки, разные модели на workspace. Сильнейший аргумент за §6.1: у LocalComet
workspace уже есть в IPC — осталось дать ему документы, память и модель.

### 9.2 Два режима документов: Embed (RAG, персистентно) vs Attach (целиком в чат, разово) — взять UX
Чёткое разделение «в базу навсегда» vs «в этот чат целиком». Копировать дословно в UI загрузки документов.

### 9.3 Vector-cache (не пере-эмбеддить) + настраиваемые чанкинг/пороги/rerank — взять
Кеш эмбеддингов по хэшу чанка; chunk 1000 + overlap; top-4–6 с фильтром по score. Детали реализации §8.3.

### 9.4 Intelligent Skill Selection (−80% токенов: подмешивать только релевантные тулы) — взять
Динамический отбор инструментов под запрос вместо «всегда весь тулсет». Лечит и токены, и качество вызова
(перекличка с лимитом 25 тулов у Goose). Для LocalComet: ретривер «запрос → подмножество tools» перед ходом;
особенно важно для малых моделей.

### 9.5 Model Router (правила → лучший провайдер/модель) — взять как идею
Автомаршрутизация по правилам. LocalComet-адаптация: роутер «сложность задачи → тир модели/движка»
(эвристика: длина, код?, инструменты?) + явный override. Дешёвый шаг к мультидвижку UP05.

### 9.6 Agent Flows (no-code canvas: API+LLM+файлы) + `@agent` в чате — взять поздно
Визуальный конструктор цепочек. Интересно, но после рецептов (§4.2): canvas = GUI над recipe-YAML.

### 9.7 Embed-виджет для сайта + Telegram-бот + browser extension — не брать
Чужая продуктовая поверхность; LocalComet — десктоп-first.

---

## 10. LiteLLM (MIT, gateway) + llama.cpp server (MIT, движок)

Источники: docs.litellm.ai (fallbacks, routing, budgets), GitHub ggml-org/llama.cpp (server README, speculative.md).

### 10.1 Fallbacks по классам ошибок (общие / context-window / content-policy) + retries внутри группы — взять обязательно
Разделить: retry внутри того же движка/модели vs fallback на другую модель/движок. Context-window fallback —
готовый ответ на переполнение контекста: вместо `prompt_too_large` — автоматический даунгрейд (большой контекст →
суммаризация → меньшая модель). Pre-call проверка `max_input_tokens` до вызова. Ложится в gateway рядом с
`GatewayLimits`; fallback-путь обязан заново вязать approval-digest (риск-инвариант!).

### 10.2 Cooldowns (`allowed_fails` + `cooldown_time`) + health-probe роутинг — взять
Выводить упавший деплой из пула до ошибок пользователей. У LocalComet авто-restart уже есть (d24d80e) —
добавить cooldown-счётчик и «ленивый детект → фоновый сторож 1 Гц» (BUG-6 хвост из GROWTH_REVIEW).

### 10.3 Budgets/spend tracking (provider/model/tag, async post-request logging) — взять
Бюджеты $/день, spend-логи с `attempted_fallbacks/original_model_group`, всё — фоновыми задачами вне hot path.
LocalComet: token/время-логирование на ход (§8.7) + дневные квоты на серию задач (LLM10 закрывается полностью:
n-predict/ctx clamp уже есть, не хватало квот и fallback-учёта).

### 10.4 llama.cpp server: slots/continuous batching, router mode, resumable SSE, sleeping mode — взять
- Parallel slots + continuous batching: несколько конкурентных ходов без «занято» (фундамент очереди §6.2).
  Осторожно: concurrency × approval — гранты уже session-scoped, держать.
- Router mode (несколько инстансов за одним endpoint, роутинг по модели): готовый мультидвижок UP05 на уровне
  процесса.
- Resumable streaming (SSE replay buffer, PR #23226): переживание обрыва стрима — complementar к inactivity-
  watchdog (BUG-4): watchdog отличает «тишина» от «обрыв», replay buffer доставляет хвост.
- Sleeping mode: выгрузка в сон вместо kill — быстрее рестарт, меньше VRAM-пиков.
- Monitoring endpoints (`/slots`, метрики): честный источник для UI-статусов вместо self-report (NA-012!).

### 10.5 llama.cpp `--tools` (built-in read/grep/glob/exec/write/edit) — НЕ брать как есть, взять как чеклист
Апстрим честно пишет «do not enable in untrusted environments» и по умолчанию режет CORS до localhost.
LocalComet уже делает то же строже (брокер + approval). Использовать список как сверку покрытия, не как код.

### 10.6 ngram speculative decoding (без доп. модели, shared pool между слотами) — взять
`ngram-map-k/ngram-mod` дают ускорение без draft-модели; пул общий на слоты. Включить флагами managed runtime
по тирам железа (адаптивный харнес d24d80e уже знает RAM/ядра — добавить spec-тир). EAGLE/MTP — позже.

### 10.7 Multimodal (mmproj, OAI-совместимо) — взять вслед за движком
Скриншоты/изображения в контекст для Computer Use grounding (vision-понимание UI вместо слепых координат).
Зависит от mmproj-артефактов в каталоге (INV-CATALOG-001 распространяется).

---

## 11. Сводная приоритизированная база (эффект/усилия)

### P0 — ощутимый потолок качества (брать первым)
1. **Память диалога**: repo-map-lite (tree-sitter символы + PageRank, §1.1) + лимиты вверх (≥32 msg/≥128 КБ) +
   `/compact` + индикатор контекста (§1.6, §8.4). Источники: aider, Open WebUI.
2. **Projects как workspace** (§6.1, §9.1): инструкции + файлы + модель + история на проект; память скоупится.
3. **Очередь + message queue** (§8.4, §6.2, §10.4): bounded queue вместо `busy`; печать во время генерации.
4. **Plan/Act + ask_user** (§3.1, §8.1): план-артефакт, approve плана, кларификация без смерти хода. Лечит BUG-8/9.
5. **RAG-минимум** (§8.3, §9.2, §9.3): FTS + embeddings + `#`-вставка + Embed/Attach + vector-cache.

### P1 — надёжность и стоимость
6. **Fallbacks по классам + context-window pre-check** (§10.1): ретрай внутри / фолбэк наружу / даунгрейд.
7. **Авто-ретрай с контекстом ошибки** (§1.5, §4.2): lint/test-hook после write; recipe `retry.checks`.
8. **Range-дозагрузка** (вне опенсорса, из GROWTH_REVIEW; подтверждается UX всех каталогов).
9. **Checkpoints как UI + git-история ходов** (§1.3, §3.2): точка восстановления на ход, restore, diff.
10. **Intelligent tool selection + лимит тулcета** (§9.4, §4.1): ретривер подмножества tools; варнинг >25.
11. **Персистентность чатов + Memory facts + KV-артефакты** (§4.4, §8.5): task_ledger → чат; факты; KV для артефактов.
12. **Фоновый сторож + cooldowns + keep_alive/idle-TTL** (§10.2, §7.2, §5.7): 1 Гц poll, счётчик падений, eviction.

### P2 — режимы, рецепты, сервер
13. **Режимы Ask/Architect/Debug + per-tool Always/Ask/Never** (§1.2, §3.3, §4.1): доверенные профили.
14. **Recipes YAML + validate-гейт + `/recipe` из сессии + cron** (§4.2, §4.3, §8.6): формат, валидатор, планировщик.
15. **ApprovalCard edit-args + липкие решения** (§5.3, §8.1): правка аргументов = новый digest+approve.
16. **Сервер-режим по формуле LM Studio/Jan** (§5.2, §6.3): loopback default, opt-in LAN + токен, capabilities,
    load/unload/download по API, живые логи, timeout для слабого железа.
17. **Engine Protocol-лайт + Modelfile-профили + per-model kwargs** (§5.1, §7.1, §6.5): версионирование рантаймов,
    файл-профиль модели, шаблон/стоп-строки/tool-формат на модель.
18. **Параллельные tool_calls + structured outputs для внутренних контрактов** (§7.3, §7.4).

### P3 — стратегическое
19. **MCP-маркетплейс + реестр skills с подписью** (§3.4, §5.5): one-click install только доверенных.
20. **Automations с destination + Telegram-мост — нет** (§8.6 взять без Telegram; §9.7 не брать).
21. **Model Router эвристический** (§9.5): сложность → тир модели; явный override.
22. **Арена/ELO + analytics-схема** (§8.7): заложить token-логи сейчас, сравнение позже.
23. **Speculative ngram + multimodal mmproj + router mode движка** (§10.6, §10.7, §10.4).
24. **Headless CLI-режим + Agent Flows-canvas поверх recipe-YAML** (§3.5, §9.6) — после P2.

---

## 12. Чего НЕ брать (анти-паттерны, замеченные у доноров)

1. Телеметрия и аккаунты ради фич (Jan требует аккуратности; LocalComet — no telemetry, держать).
2. Fail-open разрешения и «мнение LLM» как уровень риска (слабость Goose; у нас TOML — преимущество).
3. Внешние шрифты/CDN в CSP, `data:/blob:` в script/connect (наш tight-CSP в WIP — держать).
4. Неподписанные обновления каталога/движков (все реестра-доноры страдают; у нас hash-pin — распространить).
5. Workspace Tools для недоверенных (Open WebUI предупреждает; у нас и так deny-by-default).
6. Облако как дефолт (Ollama Cloud — опция, не норма; приватность — дифференциатор).
7. Безлимитный контекст как «решение» (aider: >25k — падение надёжности; карта+компакция вместо свалки).
8. Массовый тулсет без отбора (Goose ≤25, AnythingLLM −80%: отбор обязателен).
9. Секреты в конфигах/промптах (Goose keyring, Jan backend store — только так).
10. Скрытые фолбэки моделей (Qwen2.5 как silent fallback — уже запрещено Vault-каноном; Ollama учит явному пину).

---

## 13. Предлагаемые фазы (для владельца и основного кодера, не поручение)

- **Фаза A (P0, UX-разблокировка):** очередь + message queue; Plan/Act-каркас + ask_user; Projects-workspace;
  RAG-минимум; память вверх + /compact + индикатор контекста.
- **Фаза B (P1, надёжность):** fallbacks + pre-check; lint/test-hook + recipe-retry; Range; checkpoints-UI;
  tool selection; персистентность + KV; сторож + idle-TTL.
- **Фаза C (P2, экосистема):** режимы + per-tool overrides; recipes + cron; edit-args; сервер-режим; профили
  моделей + версионирование рантаймов; параллельные calls + structured outputs.
- **Фаза D (P3, стратегия):** маркетплейс; роутер; арена; spec/mmproj/router-mode; headless + canvas.
- Сквозное на всех фазах: каждый пункт — с гейтом (партитет/инвариант/evidence), секреты — в keyring/backend,
  approve-цепочка не ослабляется ни на шаг (fallback/recipe/schedule заново вяжут digest).

## 14. Формальности (по AGENTS.md)

1. Исходное состояние: ветка `feat/up00-wp01-windows-one-click-launch`, HEAD `d24d80e`, WIP-дифф 24 файла +
   `audit/GROWTH_AND_SECURITY_REVIEW_2026-09-03.md` (untracked) — без изменений с аудита 03.09.
2. Изменённые файлы: создан только этот отчёт — `audit/GROWTH_BASE_OPENSOURCE_2026-09-03.md`. Код не тронут.
3. Гейты в этой задаче не запускались (исследование класса C; свежие зелёные прогоны — из аудита 03.09:
   svelte-check 0/0, vitest 570, cargo 776/0/7, fmt+clippy clean, parity 79/21/421, smoke 8/0, real-sidecar OK,
   evidence STALE по причине WIP). Перед реализацией любого пункта §11 — полная батарея обязательна.
4. Не сделано: сверка каждой фичи донора с текущим кодом построчно (только точечные привязки), оценка в
   человеко-часах, прототипы. Источники: aider.chat + GitHub Aider-AI/aider; docs.continue.dev; cline.bot +
   GitHub cline/cline; goose-docs.ai + GitHub block/goose; lmstudio.ai/docs; jan.ai/docs + GitHub janhq/jan;
   docs.ollama.com + GitHub ollama/ollama; docs.openwebui.com + openwebui.com/blog/v0-11-1; docs.anythingllm.com;
   docs.litellm.ai; GitHub ggml-org/llama.cpp (tools/server README, speculative.md).
