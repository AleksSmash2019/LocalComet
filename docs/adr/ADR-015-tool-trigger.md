# ADR-015: F-TOOL-TRIGGER — эмиссия tool calls моделью и цикл одобрения

Date: 2026-07-27
Status: APPROVED (2026-07-27; 7 обязательных правок внесены: [ОБЯЗ-1] R7 prompt
injection + информированное одобрение, [ОБЯЗ-2] валидация tool до эмиссии,
[3] индикатор read_only с путями, [4] reject→approval_rejected + grant после клика,
[5] тесты сборки arguments escape/UTF-8, [6] лимит истории→invalid_payload,
[7] таблица покрытия в Блоке 4; решения Q1-Q7 зафиксированы)
Context: Очередь после ADR-013 (путь исполнения) и ADR-014 (conversation store).
ADR-013 построил путь grant→sidecar (run_tool_call, files.* с конфайнментом),
ApprovalCard реален, но не рендерится — нет триггера. ADR-015 добавляет эмиссию
tool calls моделью: модель запрашивает инструмент → UI одобряет → исполнение →
результат возвращается модели (multi-turn).

Связанные инварианты: INV-APPROVAL-001/002 (active, НЕ снимаются — эмиссия идёт
через существующий run_tool_call), INV-WORKSPACE, INV-UI-001.

---

## Problem

Модель не может запросить исполнение инструмента (DISCOVER 2026-07-27):
1. **Tool-маркеры отвергаются**: `_reject_tool_markers` (local_model_gateway_ru.py:1793-1803)
   рекурсивно бросает `invalid_payload` на `{tool_calls, function_call, tools, functions,
   arguments}` и `role=tool`; вызывается в `_parse_sse_event` (строка 1768) →
   `stream_protocol_error` → `model.turn.failed`. Зафиксировано тестами
   test_v68451e7b:499-512, test_v6845_model_gateway:315-324, test_v68451e6:890-897.
2. **Инструменты не анонсируются**: в теле `/v1/chat/completions`
   (local_model_gateway_ru.py:1145-1153) нет полей `tools`/`tool_choice`.
3. **assistant_context запрещает инструменты**: Rust `AssistantContext::trusted`
   (control_plane.rs:282-293) `filesystem=false, shell=false, tools=[]`; Python
   `_validate_assistant_context` требует ТОЧНОГО равенства эталону (строка 312);
   `build_system_instruction` (строки 1006/1027-1028) декларативно запрещает инструменты.
4. **Чат однооборотный**: `_validate_messages` (строки 1725-1739) допускает только
   роли `{system, user}` и поля `{role, content}`; `role=assistant`(tool_calls) и
   `role=tool`(tool_call_id) отвергаются. История модели не передаётся (один prompt).
5. **Нет события «запрос инструмента»**: MODEL_GATEWAY_EVENTS (строки 1490-1497) —
   6 методов, tool-call события нет. Frontend отвергает `tools_executed != 0`
   (bridge/modelGateway.ts:725-727, types/modelGateway.ts:109 литерал `0`).
6. **ApprovalCard не встроен**: не импортирован в AppShell.svelte (chat-region
   207-230); нет источника, вызывающего `requestApprovalForTool`.

## Decision

Включить эмиссию tool calls: модель получает анонс инструментов (OpenAI function
schema), gateway парсит `delta.tool_calls` (вместо отвержения), эмитит событие
«запрос инструмента», UI запускает цикл одобрения (read_only — автоисполнение,
guarded/dangerous — ApprovalCard), результат возвращается модели следующим
turn'ом (multi-turn agent loop). INV-APPROVAL-001/002 сохраняются: исполнение
только через `run_tool_call` (ADR-013).

### Архитектура цикла (multi-turn)

Координация: **turn завершается при запросе инструмента; цикл ведёт frontend**
(рекомендация, см. Open questions). Gateway остаётся stateless per-turn.

1. Frontend шлёт turn с полной историей messages `[system, user, assistant(tool_calls),
   tool(result), ...]` + `tools`-схемы.
2. Gateway парсит ответ модели:
   - если `delta.tool_calls` — накапливает tool call (name + arguments), эмитит
     событие `model.tool.request` {tool, input, tool_call_id}; turn завершается
     терминальным событием `model.turn.tool_calls` (новое) с накопленными calls;
   - если content — обычный поток `model.output.delta` → `model.turn.completed`.
3. Frontend получает `model.tool.request`/`model.turn.tool_calls`:
   - read_only (files.read/list) → автоисполнение `runToolCall(tool, input)` (без
     токена, INV-APPROVAL: read_only не требует одобрения);
   - guarded/dangerous (files.write/create_folder/delete) → `requestApprovalForTool`
     → ApprovalCard → `confirmApproval` (requestApproval → runToolCall(token)).
4. Frontend добавляет в историю `assistant{tool_calls}` + `tool{tool_call_id, result}`
   и стартует следующий turn (шаг 1). Цикл до `model.turn.completed` (content) или
   лимита итераций.

### Форматы (проектируются, готовых нет)

- **OpenAI tools schema** (анонс в теле запроса): для 5 files.* по форматам input
  из tool_execution_ru.py:
  - files.read / files.list / files.delete / files.create_folder: `{path: string}`;
  - files.write: `{path: string, content: string}`.
  `{type:"function", function:{name, description, parameters:{type:"object",
  properties, required}}}`, `tool_choice:"auto"`.
- **tool_calls delta** (приём): OpenAI `choices[].delta.tool_calls[].function.
  {name, arguments}` (arguments — JSON-строка, накапливается по кускам).
- **Событие `model.tool.request`** (gateway→UI): `{request_id, turn_id, tool_call_id,
  tool, input}` (input = распарсенные arguments).
- **Tool-result message** (в истории): `{role:"tool", tool_call_id, content}` —
  требует разрешения ролей assistant/tool в `_validate_messages`.

### Изменения по слоям

**Python model gateway (modules/local_model_gateway_ru.py):**
- Инвертировать `_reject_tool_markers` (1793-1803): контролируемый приём
  `delta.tool_calls` (вместо reject); оставить reject для неконтролируемых маркеров.
- `_parse_sse_event` (1763-1790): разбор `delta.tool_calls` (накопление name+arguments).
- Тело запроса (1145-1153): добавить `tools`/`tool_choice`.
- `_expected_assistant_context`/`_validate_assistant_context` (202-314, равенство
  на 312) + `build_system_instruction` (994-1042): разрешить tools_available=true
  (инструменты в контексте, текст инструкции описывает доступные инструменты).
- `_validate_messages` (1725-1739): разрешить роли `assistant`(tool_calls) и
  `role=tool`(tool_call_id, content) для multi-turn.
- MODEL_GATEWAY_EVENTS (1490-1497): добавить `model.tool.request`,
  `model.turn.tool_calls`; `_turn_payload` (1508-1558): `tools_executed` реальный
  счётчик (не жёстко 0).

**Rust (src-tauri/src/control_plane.rs):**
- `AssistantContext::trusted` (263-296): включить инструменты (tools=[files.*],
  см. Open questions по filesystem flag).
- Снять fail-closed `tools_executed == 0` (validate_model_event_metadata 2859/2892,
  acceptance 2403/2439): реальный счётчик.
- `allowed_model_event_method` (3675-3708) + `validate_and_record_model_event`
  (2668-2792): новые события model.tool.request/model.turn.tool_calls.
- Путь исполнения (run_tool_call, build_tool_call_request) — переиспользуется без изменений.

**Frontend (src/):**
- bridge/modelGateway.ts: снять `tools_executed !== 0` (725-727), расширить
  `isModelMethod` (755-757) + `parseModelEvent` под новые события; types/modelGateway.ts
  (109): `tools_executed: number` (не литерал 0).
- stores/modelGateway.ts: `applyAcceptedModelEvent` (943-1019) — обработка
  model.tool.request/model.turn.tool_calls; оркестрация цикла (автоисполнение
  read_only / approval guarded / добавление tool-result в историю / следующий turn).
- Встроить ApprovalCard в AppShell.svelte chat-region (между MessageList 222 и
  MessageComposer 225).
- approvalStore: связать событие → `requestApprovalForTool` (метод уже есть).
- История messages: frontend ведёт историю (chatMessages/conversationStore) и шлёт
  её с turn (startLocalModelTurn расширяется до передачи messages).

### Семантика tools_executed — одно определение, один авторитет (условие владельца)

**Архитектурный факт:** цикл ведёт frontend — исполнение идёт
`frontend → run_tool_call → Rust → sidecar`, МИМО gateway. Gateway физически НЕ
наблюдает исполнение; он видит только запросы модели (и эмитит `model.tool.request`).

**Определение (единственное):** `tools_executed` в событии gateway = **число tool
calls, ЗАПРОШЕННЫХ моделью и эмитированных gateway как `model.tool.request` за turn**.
**Авторитет = gateway (Python)** — он наблюдает запросы и считает их. Поле отражает
запрошенные моделью tool calls, НЕ фактические исполнения. Фактические исполнения
наблюдает Rust через `run_tool_call` — это отдельная метрика, НЕ это поле.
**Рассинхрон исключён:** gateway сообщает только то, что наблюдает (запросы); Rust
НЕ валидирует это поле против фактических исполнений (иначе встроенный рассинхрон).

**ПРИМЕЧАНИЕ об имени поля (обязательно, условие владельца):** поле называется
`tools_executed`, но означает **requested** (запрошенные моделью). Имя историческое
(закреплено в замороженном контракте types/modelGateway.ts:109, Rust validation,
Python emit); переименование трогает замороженный контракт — НЕ делать сейчас.
Без этого примечания через месяц кто-нибудь «починит» валидацию против фактических
исполнений и вернёт рассинхрон. Семантика «запрошенные, не исполненные» — норма;
любое изменение требует нового ADR.

**Rust — авторитет и defense in depth (условие владельца):** Python-валидация до
эмиссии (`validate_tool_call`, [ОБЯЗ-2]) — ПЕРВАЯ линия, не единственная. Rust
валидирует события `model.tool.request`/`model.turn.tool_calls` независимо:
- схема полей события;
- имя инструмента ∈ реестра (TOOL_REGISTRY / risk_level_for_tool);
- события допустимы ТОЛЬКО при `tools ≠ []` в assistant_context текущего turn.
При `tools = []` событие tool-call от Rust отвергается (fail-closed, defense in depth).

**Снятие `tools_executed == 0` — gated (зеркально Python):** при `tools = []` в
контексте запрет `tools_executed == 0` остаётся активным ВО ВСЕХ ТРЁХ слоях
(Python emit, Rust validate_model_event_metadata, TS types/bridge). При `tools ≠ []`
поле принимает реальное значение (≥0). Зеркалит Python-подход (tools_enabled).

**Cross-layer parity-тест — блокер приёмки Block 2 (условие владельца, 3-е напоминание):**
тест `Python emit ↔ Rust validation ↔ TS types`: событие, эмитированное Python
(model.tool.request/model.turn.tool_calls с tools_executed), проходит Rust-валидацию
и парсится TS-типами без рассинхрона; при `tools = []` событие отвергается всеми
тремя слоями. Без этого теста Block 2 не принимается.

### Один водитель оркестрации (условие владельца)

В протоколе ДВА события несут tool calls: промежуточные `model.tool.request`
(по одному на запрошенный tool call) и терминальное `model.turn.tool_calls`
с НАКОПЛЕННЫМ списком. **Frontend действует ровно ОДИН раз за turn — по
терминальному событию `model.turn.tool_calls`.** `model.tool.request` —
ИНФОРМАЦИОННОЕ (прогресс/индикатор), НЕ триггер исполнения. Обработка обоих
событий как триггеров дала бы двойное исполнение одного tool call (для files.write
— двойная запись под одним одобрением).

**Исторический контекст:** первоначальная формулировка требовала побайтного
совпадения терминального списка с суммой промежуточных эмиссий. Следующий блок
уточняет и заменяет именно это требование; остальная архитектура одного водителя
оркестрации сохраняется.

#### B6 GREEN: замороженное решение о равенстве (владелец, 2026-07-31)

- `B6_JSON_EQUALITY=ORDERED_SCHEMA_VALIDATED_STRUCTURAL_EQUALITY`.
- `OBJECT_KEY_ORDER_SIGNIFICANT=false`; `ARRAY_ORDER_SIGNIFICANT=true`.
- `DUPLICATE_KEYS=REJECT`; `UNKNOWN_FIELDS=REJECT`;
  `MISSING_DIFFERS_FROM_NULL=true`; `RAW_BYTE_EQUALITY_REQUIRED=false`.
- `TRANSPORT_CRYPTOGRAPHIC_INTEGRITY=DEFERRED_SEPARATE_MILESTONE`.

Терминальное `model.turn.tool_calls` должно точно равняться упорядоченному
накоплению ранее валидированных промежуточных `model.tool.request` в распарсенном
и прошедшем schema validation представлении. Равенство требует одинаковых длины
и порядка массива, call ID, имени инструмента, структуры/значений arguments и
наличия/отсутствия полей, определённых схемой. Порядок членов объекта, whitespace,
escape notation и лексические детали сериализации незначимы. Duplicate decoded
keys, неизвестные поля, невалидные числовые формы, нарушения схемы и неоднозначные
представления должны быть отвергнуты до provenance comparison.

Граница ответственности: Rust B6 seam получает уже десериализованный
`serde_json::Value`; поэтому он не может обнаружить потерянные при более раннем
JSON-разборе duplicate decoded keys. Их отклонение — обязательное требование
pre-parse boundary. На этом seam закрыта фиксированная оболочка tool call
`{id, name, arguments}` и неизвестные поля оболочки отклоняются. `arguments`
сравниваются структурно, но их допустимые ключи и точные числовые типы должны быть
проверены существующей per-tool schema до B6; Rust B6 не объявляет произвольные
argument keys известными и не изобретает отсутствующие per-tool схемы. Валидность
и диапазоны JSON-чисел сохраняют поведение `serde_json`; binary-float или decimal
canonicalization не вводится. Криптографическая целостность транспорта,
duplicate-preserving parser и расширение schema architecture вынесены за B6.

**Лимиты цикла N=5 итераций / ≤10 tool calls за turn** исполняет **frontend**
(он авторитет цикла, согласовано); gateway дополнительно ничего не считает
(только эмитит запрошенные моделью tool calls).

### Пограничные случаи терминальной развилки (условие владельца, до Rust)

**(1) Смешанный ответ (content + tool_calls в одном turn).** OpenAI-формат допускает
у assistant одновременно текст и tool_calls. Если модель настримила content-дельты,
а затем tool_calls — накопленный текст НЕ теряется: терминальное `model.turn.tool_calls`
несёт накопленный `text` (поле payload), чтобы Block 3 построил историю
`assistant{content, tool_calls}` — иначе модель потеряет собственные рассуждения
между итерациями цикла. `_run_turn` накапливает content-дельты и передаёт их в
терминальное событие. Тест: смешанный turn → терминал `model.turn.tool_calls`
с непустым `text` (= накопленный content) + tool_calls.

**(2) Невалидный tool call посреди стрима ([ОБЯЗ-2]).** Если модель выдала tool call
с именем вне реестра или битым JSON arguments — терминал `model.turn.failed`
с `invalid_payload`, БЕЗ частичной эмиссии валидных calls из того же turn'а
(всё или ничего — иначе frontend исполнит половину замысла модели). Валидация
каждого накопленного tool call (`validate_tool_call`: имя ∈ реестра + arguments
валидный JSON + схема) выполняется на терминале; при любом невалидном call —
`model.turn.failed` (не `model.turn.tool_calls`). Промежуточные `model.tool.request`
— информационные (прогресс), исполнение определяет только терминал. Негативный тест:
tool call с именем вне реестра / битым JSON → `model.turn.failed`/`invalid_payload`,
терминал НЕ `model.turn.tool_calls`.

### Соблюдение инвариантов

- INV-APPROVAL-001/002: guarded/dangerous tool calls идут через execute_approved
  (run_tool_call, ADR-013) — сохранено. read_only — без токена (согласно
  tool_risk_levels.toml requires_approval=false).
- INV-WORKSPACE: исполнение в подтверждённом workspace (tool_execution_ru.py, ADR-013).
- INV-UI-001: ApprovalCard показывает реальные состояния; автоисполнение read_only
  с честным индикатором.

### Тесты к инверсии/изменению (только через ADR, по образцу ADR-013 R3)

- test_v68451e7b_sse_utf8_decoder.py:499-512 (test_tool_function_rejection_unchanged).
- test_v6845_model_gateway.py:306-324 (streaming fail-closed, text-only harness).
- test_v68451e6_knowledge_injection.py:890-897 (tool_call_rejection_preserved).
- test_up02_wp01_assistant_context.py:52-94 (capabilities.tools==[], fail-closed мутации).
- Frontend: model-gateway.test.ts:115,174, chat-reliability.test.ts:171 (tools_executed:0).
- check_tool_risk_registry.py: НЕ меняется (новые fs-функции не добавляются;
  исполнимые инструменты уже в tool_risk_levels.toml).

## Phasing (декомпозиция, п. 146)

Фича >5 файлов / >500 строк / 3 слоя → блоки:
- **Блок 1 [Python]**: приём tool_calls (инверсия `_reject_tool_markers` + парсинг
  `delta.tool_calls`, инкрементальная сборка arguments) + tools в теле запроса +
  assistant_context tools_available + системная инструкция (с маркировкой
  tool-результатов как данных, R7). **[ОБЯЗ-2]** валидация имени tool (∈ реестра
  5 files.*) и схемы arguments ДО эмиссии; вне реестра/невалид → ошибка модели.
  **[5]** тесты сборки arguments с разрезом посреди JSON-escape и UTF-8.
- **Блок 2 [Python/Rust]**: multi-turn messages (role=assistant/tool) + событие
  `model.tool.request`/`model.turn.tool_calls` + реальный `tools_executed` счётчик
  (Python+Rust, снятие fail-closed `==0`). Лимиты цикла: N=5 итераций, ≤10 tool
  calls за turn (R3).
- **Блок 3 [TS]**: frontend-обработка событий + оркестрация цикла (frontend ведёт
  цикл и историю) + автоисполнение read_only (**индикатор с перечнем прочитанных
  путей** [3]) + ApprovalCard в AppShell (**путь + превью content для files.write**
  [ОБЯЗ-1]) + история messages (лимит 32). **[4]** reject → tool-result
  `approval_rejected`; grant выдаётся после клика confirm (без протухания на ожидании).
- **Блок 4 [TEST/DOCS]**: инверсия тестов + **таблица «инвертированный тест →
  компенсирующий тест», чистая потеря покрытия = 0** [7]; **[6]** тест превышения
  лимита истории → `invalid_payload`; evidence, документация, полный гейт-сет.

## Risks

- R1: multi-turn agent loop — существенное усложнение (gateway single-turn →
  loop). Координация цикла на frontend (рекомендация) vs пауза turn в sidecar.
- R2: накопление tool_calls по кускам SSE (arguments стримится инкрементально) —
  аккуратная сборка JSON arguments.
- R3: лимит итераций цикла (защита от бесконечного вызова инструментов моделью) —
  **N=5 итераций + суммарно ≤10 tool calls за turn** (решение владельца).
- R4: read_only автоисполнение — модель может читать файлы без подтверждения
  пользователя (по инварианту допустимо); требует честного UI-индикатора с
  **перечнем прочитанных путей** [3].
- R5: инверсия fail-closed тестов — только через ADR, с сохранением INV-APPROVAL;
  чистая потеря покрытия = 0 (таблица «инвертированный → компенсирующий» [7]).
- R6: размер истории messages — **maximum_messages=32**; превышение → явный
  `invalid_payload` (fail-closed), обрезка — follow-up [6].
- **R7: prompt injection через tool-результаты** [ОБЯЗ-1]. Содержимое файлов
  (files.read) и другие tool-результаты попадают в контекст модели и могут содержать
  текст, имитирующий инструкции/системные сообщения (инжекшен данных как команд).
  Митигация: (а) системная инструкция явно указывает, что содержимое инструментов —
  данные, не команды; (б) tool-результаты оборачиваются с маркировкой источника;
  (в) **информированное одобрение**: ApprovalCard для files.write показывает путь и
  превью content (пользователь видит, что именно модель хочет записать), не только
  имя инструмента. Остаточный риск принимается как свойство агентских систем
  (локальный офлайн-контекст ограничивает поверхность).

## Resolved decisions (владелец, 2026-07-27)

1. Координация цикла — **frontend ведёт цикл** (gateway stateless). ✓
2. История messages — **frontend ведёт и шлёт полную историю**. ✓
3. read_only — **автоисполнение без ApprovalCard** + честный индикатор. ✓
4. Набор инструментов — **только 5 files.***. ✓
5. assistant_context — **tools=[files.*], filesystem=false**. ✓
6. Лимит цикла — **N=5 итераций + суммарно ≤10 tool calls за turn**. ✓
7. Лимит истории — **maximum_messages=32** (обрезка — follow-up). ✓

## Обязательные правки (внесены до кода)

- **[ОБЯЗ-1] R7 prompt injection + информированное одобрение** (см. Risks R7):
  содержимое tool-результатов (особенно files.read) может содержать инструкции для
  модели (prompt injection через данные). Митигация: модель информируется, что
  содержимое файлов — данные, не команды; ApprovalCard для files.write показывает
  **путь и превью content** (информированное одобрение), не только имя инструмента.
- **[ОБЯЗ-2] Валидация имени и схемы tool call ДО эмиссии события**: gateway
  проверяет, что запрошенный моделью tool ∈ реестра (5 files.*) и arguments
  соответствуют схеме (required-поля, типы). Tool вне реестра или невалидная схема
  → **ошибка модели** (model.turn.failed / tool-result с ошибкой), НЕ событие
  одобрения. Это исключает эмиссию произвольных/опасных tool calls.
- **[3] Индикатор read_only**: при автоисполнении read_only UI показывает
  **перечень прочитанных путей** (список path из files.read/list), не просто факт.
- **[4] Отклонение approval**: при reject ApprovalCard → в историю добавляется
  tool-result `approval_rejected` (модель видит отказ). **Grant выдаётся после
  клика confirm** (requestApproval → сразу execute_approved/runToolCall), а не
  заранее — исключает протухание grant (GRANT_TTL=30s) на время ожидания карточки.
- **[5] Тесты сборки arguments**: SSE стримит `arguments` инкрементально; разрез
  может пройти посреди JSON-escape (`\"`, `\\`) или multi-byte UTF-8. Тесты
  (Python) покрывают сборку arguments с разрезом посреди escape-последовательности
  и посреди UTF-8 символа (инкрементальный UTF-8 декодер уже есть — переиспользовать).
- **[6] Превышение лимита истории**: при maximum_messages=32 превышение →
  явный `invalid_payload` (fail-closed); стратегия обрезки истории — follow-up.
- **[7] Таблица покрытия в Блоке 4**: для каждого инвертированного теста —
  компенсирующий тест; **чистая потеря покрытия = 0** (таблица «инвертированный
  тест → компенсирующий тест» в отчёте Блока 4).

## Consequences

- Модель получает возможность запрашивать инструменты; появляется multi-turn
  agent loop (чат перестаёт быть однооборотным).
- ApprovalCard встраивается в UI (триггер от model gateway события).
- read_only инструменты исполняются автоматически, guarded/dangerous — через одобрение.
- Снимается ряд fail-closed запретов (tool-маркеры, tools_executed==0, role=tool) —
  только через ADR, с сохранением INV-APPROVAL-001/002.
- Gateway/frontend усложняются (multi-turn, история, оркестрация цикла).
