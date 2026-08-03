# ADR-013: Путь исполнения инструментов через execute_approved

Date: 2026-07-27
Status: APPROVED (2026-07-27; 7 обязательных правок владельца внесены; код —
после подтверждения пересборки бандла по багу #1, см. Precondition)
Context: Дефект/задача #2 «execute_approved — диспетчеризация инструментов не
срабатывает после одобрения». DISCOVER (pipeline/discovery.md) установил: это
FEATURE_GAP — путь grant→инструмент отсутствует по проекту. Владелец утвердил
реализацию фичи (решение 2026-07-27).

Связанные инварианты: INV-APPROVAL-001 (active), INV-APPROVAL-002 (active),
INV-WORKSPACE-001 (planned), INV-EVIDENCE-001 (active).

---

## Problem

`execute_approved` (approval_commands.rs:108) атомарно валидирует scope,
потребляет одноразовый токен и создаёт `ExecutionGrant`, но **не диспетчеризует**
исполнение: sidecar возвращает `unsupported_method` для любых tool/filesystem
методов (desktop_sidecar_runtime_ru.py:170). Поля grant `input_digest`/`nonce` —
`#[allow(dead_code)]` «consumed by a downstream tool-execution path when one
exists» (approval.rs:246-249). Инфраструктура одобрения реализована и покрыта
тестами как фундамент, но потребитель grant отсутствует во всех трёх слоях.

Отсутствие пути — задокументированная граница (approval_commands.rs:103-107),
закреплённая регрессионным тестом smoke_test.py:114-123 (`files.read` обязан
отклоняться с `unsupported_method`).

## Decision

Построить end-to-end путь исполнения инструментов:
**UI → Tauri `run_tool_call` → атомарный `execute_approved` (Rust, авторитет) →
IPC `tool.call` → sidecar-исполнитель с workspace-конфайнментом → ответ → UI.**

Принципы:
1. Rust остаётся единственным авторитетом авторизации (INV-APPROVAL-001:
   owner = approval.rs + approval_commands.rs). Любой guarded/dangerous вызов
   проходит через `execute_approved` ДО отправки в sidecar. Bypass отсутствует:
   sidecar достижим только через Rust-мост, который шлёт `tool.call` исключительно
   после успешного `execute_approved`.
2. read_only инструменты (`files.read`, `files.list`; requires_approval=false)
   исполняются БЕЗ токена — согласно tool_risk_levels.toml.
3. Исполнение в sidecar ограничено подтверждённым workspace через
   `WorkspacePolicy.validate_path` (resolve + relative_to, symlink-безопасно).
   `modules/files.py::safe_path` НЕ используется (привязан к Projects/,
   prefix-небезопасен).
4. IPC-изменение аддитивное и обратно-совместимое: новый метод `tool.call`
   (METHOD_RE допускает), формат кадра localcomet.ipc/1.0 не меняется, новые
   ERROR_CODES не нужны (используются approval_required / policy_blocked /
   unsupported_method / invalid_payload).

## Detailed design

### Rust (src-tauri/src/)

- `control_plane.rs`: новый вариант `ControlPlaneMethod::ToolCall` → wire
  `"tool.call"`; добавить в `CONTROL_PLANE_METHOD_VOCABULARY`; таймаут
  (предложение: 5s, как model.turn.start). Payload-схема валидируется
  `validate_payload_for_method`.
- Новая команда `run_tool_call(tool: String, input: Value, token: Option<String>)`:
  1. `risk_level_for_tool(&tool)` (approval_commands.rs:57).
  2. Если requires_approval (guarded/dangerous): token обязателен;
     `digest = canonical_input_digest(&input)`;
     `registry.execute_approved(token, tool, digest, workspace.canonical_path)`
     → grant (атомарно, одноразово); проверка `grant.is_expired()`.
     Без token → `BridgeError::new("approval_required", ...)`.
  3. Если read_only: token игнорируется, grant не создаётся.
  4. Диспетчеризация `bridge.request(ToolCall, payload)` где payload =
     `{tool, input, workspace: canonical_path, workspace_digest, session,
     grant_id?}`.
  5. Возврат результата sidecar в UI.
- `lib.rs`: регистрация `run_tool_call` в `generate_handler!` (parity).
- `approval.rs`: снять `#[allow(dead_code)]` с `input_digest`/`nonce` после
  подключения потребителя (input_digest уже сверяется в execute_approved;
  nonce остаётся материалом grant).

### Python sidecar (modules/)

- `desktop_sidecar_runtime_ru.py`: новый capability tuple
  `TOOL_EXECUTION_CAPABILITIES = ("tool.call",)`; включить в
  `ALLOWED_REQUEST_METHODS`; ветка маршрутизации в `handle_message` до строки 170;
  объявить в capabilities hello/health.
- Новый модуль-исполнитель (предложение: `modules/tool_execution_ru.py`):
  - строит `WorkspacePolicy(workspace, workspace_digest, session)`;
  - для каждого инструмента вызывает `policy.validate_path(target)` ДО операции;
  - реализует `files.read`, `files.list`, `files.write`, `files.create_folder`,
    `files.delete` (utf-8, pathlib, Windows-поведение — п. 88);
  - ошибки: path outside workspace → `policy_blocked`; прочее →
    `invalid_payload`/`internal_error` (все коды уже в ERROR_CODES).
- `desktop_control_plane_ru.py`/контракт: при необходимости — типизированная
  валидация payload `tool.call` (по образцу approval.submit).

### Frontend (src/)

- `bridge/approval.ts` (или новый bridge): обёртка `runToolCall(tool, input, token?)`
  → `invoke('run_tool_call', ...)`.
- Реальный approval-поток вместо мок/disabled `ApprovalCard.svelte`:
  `requestApproval(tool, input)` → показ карты → `executeApproved`/`runToolCall`.
  Заменить `ApprovalMock` на реальные данные; снять `disabled`.
- i18n: переиспользовать `approval.*`; добавить ключи состояний
  (approval_required, grant_expired, policy_blocked) в ru.ts + en.ts (п. 141).

### Контрактные изменения

- Новый IPC-метод `tool.call` (аддитивно).
- `smoke_test.py[06]`: инвертировать. Новое поведение:
  - `files.read` (read_only) → успех без approval;
  - `files.write` без grant → `approval_required`;
  - `files.write` с валидным grant → успех;
  - путь вне workspace → `policy_blocked`.
  Это изменение ожидаемого поведения фиксируется данным ADR.

### Размер payload (large files, правка #5; уточнение Block 2)

Чанкование в первом релизе НЕ вводится (простота + безопасность). Действующая
граница — `MAX_TOOL_FILE_BYTES = 1_000_000`, ограничена IPC-лимитом на строку
`MAX_STRING_CHARS = 1 MiB` (desktop_ipc_contract_ru.py), а не 4 MiB кадром:
контент файла передаётся как JSON-строка в payload, поэтому обязан быть ниже
построчного лимита с запасом на JSON-экранирование. Поведение:
- `files.write`: если размер входного content превышает лимит инструмента —
  отказ `invalid_payload` ДО записи (валидация в sidecar).
- `files.read`: если размер файла-результата превышает лимит — отказ
  `payload_too_large` (проверка по stat ДО чтения, память не выделяется).
- Оба исхода покрыты pytest (Block 2) и возвращают коды из замкнутого ERROR_CODES.

### Реестр инструментов и parity (правка #7)

Все 5 инструментов files.* присутствуют в tool_risk_levels.toml (секция Console
agent filesystem operations) и зеркале risk_level_for_tool (approval_commands.rs:57):
- `files.read` — read_only, requires_approval=false;
- `files.list` — read_only, requires_approval=false;
- `files.write` — guarded, requires_approval=true;
- `files.create_folder` — guarded, requires_approval=true;
- `files.delete` — **dangerous**, requires_approval=true (подтверждено).

command parity: 43 → 44 (добавляется `run_tool_call`); отражается в справочнике
команд и проверяется scripts/check_command_parity.py (Block 4).

## Security analysis

- INV-APPROVAL-001: соблюдается — guarded/dangerous только через атомарный
  execute_approved; bypass нет (sidecar достижим лишь через мост). witness-тесты
  approval.rs остаются; добавляются тесты run_tool_call (оба исхода, п. 78).
- INV-APPROVAL-002: не затрагивается (токены/сравнения без изменений).
- INV-WORKSPACE-001 (planned): фактически активируется в части «fs-операции
  привязаны к workspace». **Активация требует правки invariants.toml
  (status planned→active, implementation, test_ids) — отдельно, только с
  письменного разрешения владельца (п. 153).**
- INV-EVIDENCE-001: доказательства исполнения tool.call должны включать
  source-digest/argv/exit-code — учесть в evidence-скриптах.
- Поверхность атаки (п. 145): sidecar получает возможность писать/удалять файлы
  в workspace. Митигация: workspace-конфайнмент (validate_path), utf-8,
  ограничение размера payload (MAX_FRAME_BYTES), approval для мутаций.

## Alternatives considered

1. Исполнение в Rust (не в sidecar). Плюс: нет нового IPC-метода. Минус:
   filesystem-примитивы и confinement уже живут в Python (workspace_policy.py),
   дублирование; sidecar — принятое место runtime-логики. Отклонено.
2. Передача grant в sidecar с криптоверификацией. Плюс: sidecar независимо
   проверяет. Минус: grant — Rust-side состояние; sidecar и так доверяет мосту
   (как для model.turn.start). Избыточно. Отклонено.
3. Оставить границу (не реализовывать). Отклонено владельцем.

## Risks

- R1: расширение роли Python-sidecar (fs-операции) — новая ответственность,
  нужны тесты конфайнмента (symlink/junction escape на Windows).
- R2: INV-WORKSPACE-001 «fs blocked during transition» (workspace.set round-trip)
  не реализован; в первом релизе workspace берётся из ApprovalState, смена
  workspace инвалидирует токены (уже работает), но «блокировка fs на время
  перехода» — отдельная работа.
- R3: инверсия smoke_test[06] меняет зафиксированное поведение — только через
  данный ADR.
- R4: read_only fs-операции без approval — confinement обязателен и для read_only.
  Усилено тестом (правка #4): явный pytest-кейс files.read (read_only, без approval)
  с путём вне workspace И через symlink → policy_blocked.
- R5: крупные файлы (правка #5). Поведение при превышении MAX_FRAME_BYTES
  (4 MiB, desktop_ipc_contract_ru.py) специфицировано в разделе «Размер payload»:
  чанкование НЕ вводится в первом релизе; oversized — явная ошибка.
- R6: grant потреблён, tool.call упал по таймауту (правка #6). Токен одноразовый
  (INV-APPROVAL-002), grant создаётся заново только через новое одобрение.
  Поведение: Rust возвращает ошибку timeout, grant уже потреблён (атомарно в
  execute_approved) — это приемлемо (пользователь одобряет заново). Фиксируется в
  ADR и в UI-состоянии (сообщение «требуется повторное одобрение»). Повторная
  отправка того же tool.call без нового токена → approval_required.

## Phased rollout (блоки, раздел 2)

**Precondition (обязательно, правка владельца #1):** Block 1 НЕ стартует, пока не
подтверждена пересборка бандла по багу #1 — вывод
`python tools/test_bug1_inference_bundle_parity.py` должен быть `ALL OK` (PART B
зелёный) на пересобранном sidecar. Это гарантирует, что рабочая среда sidecar
соответствует исходникам до наслоения нового функционала.

- Блок 1 [FEATURE] Rust: ControlPlaneMethod::ToolCall + run_tool_call (каркас) +
  тесты (happy-path read_only, approval_required, wrong_scope, expired,
  grant_consumed_on_timeout). TDD.
- Блок 2 [FEATURE] Python: tool.call routing + tool_execution_ru.py +
  workspace-конфайнмент + pytest. TDD. Обязательные pytest-кейсы (правка #4, R4):
  - files.read (read_only, БЕЗ approval) с путём ВНЕ workspace → policy_blocked;
  - files.read через symlink/junction, ведущий наружу workspace → policy_blocked
    (resolve ДО проверки containments);
  - files.write/files.delete без grant → approval_required (на стороне Rust);
  - oversized read/write → поведение по разделу «Размер payload».
- Блок 3 [FEATURE] Frontend: bridge runToolCall + реальный ApprovalCard + i18n +
  vitest. UI-состояние для исхода «grant потреблён, tool.call упал по таймауту»
  (правка #6): сообщение о необходимости повторного одобрения (токен одноразовый).
- Блок 4 [TEST/DOCS]: инверсия smoke_test[06], command parity (43→44:
  +run_tool_call), обновление README/справочника команд, evidence. Полный гейт-сет.
  **Новый гейт bundle parity (правка #2):** скрипт сверки хеша/версии развёрнутого
  бандла sidecar (DevRuntime/.../app/modules) с исходниками репо — защита от
  повторения бага #1 (репо ≠ бандл), критично после добавления tool_execution_ru.py.
- Опционально (отдельно, с разрешения): активация INV-WORKSPACE-001.

Замечание по нумерации (правка #3): номер 013 проверен свободным; каталог решений
на 2026-07-27 = {ADR-001, ADR-011, ADR-012, ADR-013} (ADR-008→011, ADR-009→012
переименованы по решению владельца; ADR-010 отсутствует).

Критерий готовности (п. 143): end-to-end сценарий UI→Rust→sidecar→UI работает;
тесты на happy-path/ошибку ввода/отказ зависимости; гейты зелёные; документация
обновлена; INV-APPROVAL-001 witness-тесты проходят.

## Resolved decisions (владелец, 2026-07-27)

1. Исполнитель fs-операций — **Python sidecar** (да).
2. read_only tools (files.read/list) — **без approval**, инверсия smoke_test[06]
   фиксируется этим ADR (да).
3. Объём первого релиза — **только files.*** в границах workspace; artifact/runtime
   остаются на выделенных командах (да).
4. Активация INV-WORKSPACE-001 — **отдельным решением после первого релиза**
   (правка invariants.toml только с письменного разрешения, п. 153).

Дополнительные обязательные правки (внесены выше): #1 precondition пересборки
бандла; #2 гейт bundle parity в Block 4; #3 нумерация 013 свободна; #4 усиление
R4 pytest-кейсами; #5 раздел «Размер payload»; #6 R6 grant+timeout и UI-состояние;
#7 реестр инструментов и parity 43→44.

## Consequences

- Появляется реальный путь исполнения инструментов; grant перестаёт быть тупиком.
- Python-sidecar получает fs-ответственность в границах workspace.
- smoke_test[06] меняет смысл; command parity +1 (run_tool_call).
- INV-APPROVAL-001 остаётся активным и усиливается end-to-end покрытием.

## Scope and follow-ups (поправка объёма, 2026-07-27)

Реализовано (end-to-end, подтверждено тестами слоёв + smoke_test):
**UI-bridge → Rust → sidecar** — `runToolCall` (bridge/approval.ts) → Tauri
`run_tool_call` → атомарный `execute_approved` (Rust, INV-APPROVAL-001) → IPC
`tool.call` → sidecar `tool_execution_ru.py` (files.* с workspace-конфайнментом)
→ результат обратно. `approvalStore` и `ApprovalCard` реальны и покрыты vitest.

НЕ реализовано (отдельная фича, в очереди): **UI-триггер tool-call запросов**.
Заблокировано отсутствием эмиссии tool calls моделью: ассистенту декларативно
выключены инструменты (`filesystem/shell/tools = false`, control_plane.rs),
model gateway отвергает tool-маркеры в ответе модели (test_v68451e7b). Поэтому
`ApprovalCard` пока не рендерится в `AppShell` — нет реального источника
запросов на подтверждение (п. 137: триггер без реального источника не ставится).

Зарегистрировано в очередь (после ADR-014, IPC не параллелить):
- F-TOOL-TRIGGER: эмиссия tool-call запросов моделью + интеграция ApprovalCard
  в chat UI (pending-approval → requestApproval → runToolCall), i18n состояний
  уже добавлено. До этого путь исполняется и тестируется на уровне bridge→Rust→
  sidecar; пользовательский UI-триггер появляется только вместе с реальным
  источником tool calls.
