# ADR-014: Conversation store — реальный источник списка разговоров

Date: 2026-07-27
Status: APPROVED (2026-07-27; обязательные правки [ОБЯЗ-1] маршрутизация стрима
по conversationId, [ОБЯЗ-2] rg-скан 'local-chat'; решения: in-memory,
model-gateway, mockData удалить отдельным [POLISH] с rg reference-scan)
Context: Дефект #8 — ConversationSidebar и ChatHeader используют mockData
(conversationGroups, conversationTitleById); реального conversation store нет.
Очередь: после ADR-013 (принят). Связан с F-TOOL-TRIGGER (UI-триггер tool calls).

Связанные инварианты: INV-UI-001 (UI не показывает ложное состояние — текущий
mockData его нарушает, показывая фиктивные разговоры «Демо отмены», «Аудит» и т.д.).

---

## Problem

- `ConversationSidebar.svelte:3` импортирует `conversationGroups` из mockData;
  `ChatHeader.svelte:4` — `conversationTitleById`. Оба показывают фиктивные
  разговоры (нарушение INV-UI-001).
- Реального источника списка разговоров нет (DISCOVER, 2026-07-27):
  - Нет `session.list`/`thread.list` ни в sidecar (`CONTROL_PLANE_METHODS`,
    desktop_control_plane_ru.py:106-122), ни в Rust (`ControlPlaneMethod`,
    control_plane.rs:52-80), ни в TS-bridge. Только одиночные
    create/get/close по заранее известному ID.
  - Sidecar хранит сессии в `dict` в памяти, `persistence=False`
    (desktop_control_plane_ru.py:341,828). При перезапуске всё теряется.
  - `controlPlaneStore` хранит ровно один `currentSession`/`currentThread`,
    не список (controlPlane.ts:32-33).
- Реальный чат идёт через **model gateway** (`model.turn.start` с
  `chatSessionId`-строкой, modelGateway.ts:705-718), НЕ через control-plane
  сессии/треды. Control-plane session/thread используется только для
  demo/knowledge (submitControlPlaneDemo, createPendingKnowledgeTurn).
- `chatMessages` (shellStore.ts:30) — один глобальный in-memory список,
  не привязан к `selectedConversationId`; история не персистируется.
- `selectedConversationId` (shellStore.ts:27) — строковый store
  (дефолт `'local-chat'`), не привязан ни к control plane, ни к model gateway.

## Decision

Создать **клиентский `conversationStore`** (Svelte store), управляющий списком
разговоров. Каждый разговор = клиентская сущность `{ id, title, createdAt }`,
где `id` используется как `chatSessionId` для model gateway (`model.turn.start`),
а история сообщений хранится на клиенте (per-conversation). Заменить mockData в
ConversationSidebar и ChatHeader на реальный store; привязать MessageComposer к
активному разговору.

Обоснование архитектуры: реальный чат уже идёт через model gateway
(stateless, `chatSessionId`-строка); control-plane session/thread — отдельная
модель для demo/knowledge. Conversation store — клиентская сущность над model
gateway; новых IPC-методов в первом релизе НЕ добавляется (используется
существующий `model.turn.start`). Список разговоров ведёт клиент (sidecar не
имеет list-метода и персистентности).

Принципы:
1. Никакого mockData в ConversationSidebar/ChatHeader (INV-UI-001).
2. Честные состояния: пустой список, «Новый чат» по умолчанию, реальные
   заголовки. Никаких фиктивных «Демо отмены»/«Аудит».
3. Первый релиз — in-memory (список и история теряются при перезагрузке).
   Это честно документируется; персистентность — отдельный follow-up.
4. Повторное использование существующих механизмов (model gateway,
   inferenceRequestStore, i18n), без параллельных сущностей (п. 147).

## Detailed design

### conversationStore (src/lib/stores/conversationStore.ts, НОВЫЙ)

```ts
interface ConversationMeta {
  id: string;            // chatSessionId для model gateway
  title: string;         // отображаемый заголовок
  createdAt: number;     // unix ms
}
interface ConversationState {
  conversations: ConversationMeta[];   // список (порядок: новые сверху)
  activeId: string;                     // активный разговор
}
```

- `conversationStore = writable<ConversationState>(...)` — инициализируется
  одним разговором по умолчанию `{ id: 'local-chat', title: <new_chat> }`
  (соответствует текущему DEFAULT_CONVERSATION, сохраняет UX).
- `createConversation(): string` — генерирует id (валидный под chatSessionId-regex
  `/^[a-z0-9][a-z0-9_-]{0,63}$/`), добавляет в начало списка, делает активным;
  заголовок по умолчанию = i18n `item.new_chat`.
- `selectConversation(id)` — устанавливает activeId.
- `renameConversation(id, title)` — обновляет заголовок. Используется
  автозаголовком; ручной UI-триггер переименования — follow-up [3].
- `applyAutoTitle(id, prompt)` — автозаголовок из первого prompt [4]: первые
  ~40 символов (обрезка по границе слова + «…»), применяется только если
  заголовок ещё дефолтный (`item.new_chat`). Вызывается при первой отправке.
- `activeConversation = derived(...)` — активный ConversationMeta.
- `resetConversationStore()` — для тестов.
- `deleteConversation` — НЕ в первом релизе [5]: follow-up (store + UI вместе,
  без мёртвого кода; правила: нельзя удалить последний разговор, удаление
  активного переключает на соседний).

### История сообщений (per-conversation) и маршрутизация стрима [ОБЯЗ-1]

- `chatMessages` (shellStore) становится per-conversation:
  `Map<conversationId, Message[]>` в conversationStore. Первый релиз:
  in-memory Map.
- При переключении разговора отображается его история.
- `startLocalModelTurn(prompt, conversationId, fileIds)` — отправка в model
  gateway с `chatSessionId` активного разговора (вместо хардкода `'local-chat'`).
- **Маршрутизация чанков стрима — по `conversationId` ЗАПРОСА, не по `activeId`.**
  При старте turn фиксируется `originConversationId = activeId` (момент запроса).
  Все чанки стрима (model.output.delta / terminal-события) этого turn дописываются
  в историю `originConversationId`, даже если пользователь переключился на другой
  разговор во время генерации. Это исключает попадание чанков в чужой разговор
  (cross-conversation leakage). Реализация: маппинг `requestId →
  originConversationId` (в conversationStore или замыканием в обработчике стрима);
  append идёт по `originConversationId`, отображение — по `activeId`.
- Тест [ОБЯЗ-1] (vitest): начать turn в разговоре A → переключиться на B →
  эмитировать чанк стрима по requestId разговора A → чанк попадает в историю A,
  история B пуста; активный B отображает свою (пустую) историю.

### ConversationSidebar.svelte

- Убрать импорт `conversationGroups` из mockData.
- Рендер из `conversationStore.conversations` (одна группа «Локальные чаты»
  или плоский список; i18n `group.local_chats`).
- Кнопка «Новый чат» → `createConversation()` (i18n `sidebar.new_conversation`).
- Выбор → `selectConversation(id)`.
- Пустой список → честное состояние (i18n `conversation.empty`), хотя по
  умолчанию есть один «Новый чат».

### ChatHeader.svelte

- Убрать импорт `conversationTitleById` из mockData.
- Заголовок = `$activeConversation.title` (через i18n fallback на
  `item.new_chat`, если заголовок = ключ).

### i18n (ru.ts + en.ts, добавить)

- `conversation.empty`: «Нет разговоров» / «No conversations»
- `conversation.untitled`: «Без названия» / `Untitled`
- `sidebar.new_conversation`: «Новый чат» / `New chat` (кнопка создания)
- Переиспользовать существующие `group.local_chats`, `item.new_chat`.

### Тестирование (TDD)

- vitest `tests/conversationStore.test.ts`: создание/выбор/переименование;
  активный разговор по умолчанию; per-conversation история; id валиден под
  chatSessionId-regex; автозаголовок из первого prompt (~40 симв.).
- **[ОБЯЗ-1] vitest маршрутизации стрима**: turn в разговоре A → переключение
  на B → чанк по requestId A попадает в историю A (не B); активный B показывает
  свою историю.
- vitest для ConversationSidebar/ChatHeader: рендер из реального store
  (без mockData); новый чат появляется в списке; заголовок активного.
- **[ОБЯЗ-2]** после перевязки: `rg "local-chat"` по
  `desktop/localcomet-desktop/src` — остаётся только внутренний дефолт id
  (DEFAULT_CONVERSATION); хардкод в UI/отправке устранён. Вывод скана — в отчёте.
- mockData gate: ConversationSidebar/ChatHeader выпадают из импортов mockData
  (записи allowlist становятся инертными; не править allowlist — п. 153).

## Границы и совместимость

- **approvalStore глобален** [6]: `approvalStore` (ADR-013) не привязан к
  разговору — pending approval остаётся глобальным при переключении разговоров
  (approval-запрос первого релиза не несёт `conversationId`). Привязка approval
  к разговору — follow-up (при необходимости).
- **[ОБЯЗ-2]** после перевязки выполняется rg-скан остатков хардкода
  `'local-chat'`: допустим только внутренний дефолт id (`DEFAULT_CONVERSATION`);
  хардкод в UI/логике отправки устраняется. Результат скана — в отчёте блока.

## Scope and follow-ups

Реализовано (первый релиз): клиентский conversationStore (in-memory), реальные
список/заголовки, автозаголовок из первого prompt, маршрутизация стрима по
conversationId запроса [ОБЯЗ-1], привязка MessageComposer к активному разговору,
замена mockData в ConversationSidebar/ChatHeader, i18n, vitest (TDD).

НЕ реализовано (follow-up, честно):
- **Персистентность разговоров и истории** (cross-reload). Sidecar
  `persistence=False`, list-метода нет. Варианты: localStorage для метаданных
  + истории (клиент), либо sidecar `session.list` + файловое хранилище
  (требует IPC-расширения и ADR). Отдельная фича.
- **Унификация control-plane session/thread модели с чат-разговорами.**
  Сейчас чат = model gateway (stateless), control-plane сессии = demo/knowledge.
  Сведение в единую модель — архитектурная работа (отдельный ADR).
- **Ручной UI-триггер переименования** разговора [3] (метод store есть,
  используется автозаголовком; inline-rename в UI — follow-up).
- **deleteConversation** [5] (store + UI вместе: нельзя удалить последний,
  удаление активного переключает на соседний).
- **Привязка approval к разговору** [6] (approvalStore глобален в первом релизе).

## Risks

- R1: in-memory история теряется при перезагрузке — честно документируется;
  пользователь предупреждён (локальный офлайн-ассистент, персистентность —
  follow-up). Не маскировать (INV-UI-001).
- R2: chatSessionId-regex (`/^[a-z0-9][a-z0-9_-]{0,63}$/`) ограничивает формат
  id разговора — генератор id обязан ему соответствовать (валидация в store).
- R3: per-conversation история в памяти может расти — первый релиз без лимита;
  лимит/очистка — follow-up (мониторить).
- R4: два пути чата (model gateway vs control-plane demo) остаются — ADR-014
  не унифицирует их (явно вынесено в follow-up), чтобы не расширять scope.

## Consequences

- ConversationSidebar/ChatHeader больше не используют mockData (INV-UI-001
  соблюдён для этих компонентов; дефект #8 закрыт в части списка/заголовков).
- Реальный список разговоров + заголовки; MessageComposer привязан к активному
  разговору (chatSessionId).
- mockData conversationGroups/conversationTitleById становятся неиспользуемыми
  (кандидаты на удаление отдельным блоком, с разрешения).
- Персистентность и унификация с control-plane — отдельные follow-up фичи.
