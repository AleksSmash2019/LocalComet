# pipeline/spec.md — PLAN (сессия 2026-07-27)

Цель сессии: три задачи от владельца по приоритетам раздела 6.
Формат: DISCOVER → PLAN → EXECUTE → VERIFY → ITERATE (раздел 11).

---

## Задача #1 [FIX] request_model_turn_reserved
- Статус DISCOVER/PLAN: корневая причина найдена (устаревший бандл sidecar: 2 ключа
  conversation против 3 у Rust). Исходник репо корректен.
- EXECUTE (автономно): написан падающий тест-воспроизведение
  tools/test_bug1_inference_bundle_parity.py (PART B FAIL, exit 1).
- VERIFY: Python-гейты прошли (command_parity, tool_risk, ui_fake_state, mockdata),
  py_compile теста OK.
- ФИКС: пересборка бандла — операционное действие владельца (решение получено:
  владелец пересобирает). После фикса: убрать DIAG-маркеры отдельным блоком [POLISH].
- Условие остановки достигнуто: автономная часть закрыта, фикс — за владельцем.

## Задача #2 [FIX] execute_approved → диспетчеризация инструментов
- DISCOVER: классификация (B) FEATURE_GAP. Путь диспетчеризации grant→инструмент
  ПОЛНОСТЬЮ отсутствует по проекту (нет run_tool_call, нет ControlPlaneMethod tool.call,
  нет обработчика в sidecar, нет потребителя grant в UI). Граница задокументирована
  (approval_commands.rs:103-107) и закреплена регрессионным тестом smoke_test.py:114-123.
- PLAN-вердикт: это фича (10-15 файлов, ~500-900+ строк, 3 слоя, tool_risk_levels.toml,
  INV-UI-001, инверсия smoke_test[06]). По п. 132/144/146 требует ADR + согласования.
- EXECUTE: ЗАБЛОКИРОВАН до решения владельца (самовольные фичи запрещены, п. 144/158).

## Задача #3 [POLISH] mockData → реальные stores (AgentInspector/ChatHeader/ConversationSidebar)
- DISCOVER: все три компонента (B) BLOCKED. Реальных stores-источников нет:
  нет conversation store (список+заголовки), нет agent telemetry store.
  AgentInspector к тому же осиротел (не рендерится; реальный аналог Diagnostics.svelte).
  ChatHeader частично реален (connection-summary), мок только заголовок.
- PLAN-вердикт: замена = создание новых stores/IPC = фича, не полировка (п. 112).
- EXECUTE: ЗАБЛОКИРОВАН до решения владельца.

---

## Условия остановки (п. 178)
- #1: автономная часть APPROVED (диагностика+тест); фикс операционный.
- #2, #3: STOP — требуется решение владельца (фичи/ADR). Дальнейший EXECUTE
  без явного «да» запрещён (п. 158).

## Требуется решение владельца (п. 168)
1. #2: реализуем путь исполнения инструментов (фича + ADR), или фиксируем как
   задокументированную границу? Рекомендация: зафиксировать границу сейчас
   (продукт offline-assistant без file-tools; путь = отдельный релиз с ADR).
2. #3: создаём реальный conversation store (фича) для ConversationSidebar+ChatHeader,
   или оставляем честный placeholder? Что делать с осиротевшим AgentInspector
   (удалить/интегрировать с Diagnostics)? Рекомендация: conversation store — отдельная
   фича; AgentInspector не трогать без решения (удаление = разрешение владельца).

---

# B5 RED Adversarial — contract decision (2026-07-28)

Статус: B5_CONTRACT_BLOCKED, NEXT_ALLOWED=NONE.

Источники авторитета конфликтуют по контракту tool_calls[*].arguments:
- Carrier (блокирующий): Rust-фикстуры STRING (control_plane.rs:5833+, structured_tool_event:5736)
  vs Python эмитит PARSED OBJECT (ToolCallAccumulator.build():2180-2185; эмиссия model.turn.tool_calls
  :877->:1026). IPC schema (desktop/contracts/localcomet_ipc_v1.schema.json) молчит (0 совпадений
  tool_calls/arguments). ADR-015:82 — string на проводе model->Python; :84 — parsed object в событии.
- Error code: Rust protocol_mismatch (tool-events :2785-2858) vs Python invalid_payload (validate_tool_call :2122-2135).
- Duplicate JSON keys: serde_json last-wins vs Python reject (_reject_duplicate_keys :2310-2316).
- Scope: generic object shape vs per-tool schema (ADR-015:150-154 не разделяет B5/B6 явно).

Подтверждено (не конфликтует): production Rust не валидирует arguments (читает name :2814 и id :2830-2856);
B5 seam = между :2856 и :2857; strict placeholder :2858-2861 активен; production tools disabled
(trusted() tools=Vec::new() :302); atomicity CONFIRMED (мутации :2884+ недостижимы для tool events).

Документ вариантов (без выбора): docs/audit/B5_CONTRACT_CONFLICT.md.
RED-тесты не писались: exact assertions (assert_eq! по коду и сообщению) невозможны без утверждённого контракта.
Условие остановки: решение владельца по конфликтам A (carrier), B (error code), D (scope).

---

# B5 CONTRACT RATIFICATION + RED — результат (2026-07-28)

Статус: B5 RED выполнен (ожидает финальной red-team приёмки). NEXT_ALLOWED после приёмки = B5 GREEN.

Ратифицированный контракт (docs/audit/B5_CONTRACT_RATIFIED.md):
- Carrier на Rust event boundary = parsed JSON object. Rust отвергает string/stringified/null/array/number/boolean. Dual запрещён.
- missing -> protocol_mismatch "tool call arguments are required".
- wrong type -> protocol_mismatch "tool call arguments must be an object".
- {} разрешён (valid -> strict placeholder).
- Scope: presence + object type + order + batch atomicity + exact errors + placeholder для valid. НЕ per-tool schema/workspace/permissions/approval/execution/resource limits/cross-event/provenance.
- Duplicate keys = граница Python parser. null отвергается как wrong type. Resource limits -> B5L (до снятия placeholder и включения tools).

B5 seam: control_plane.rs между 2856 и 2857 (внутри for-call цикла, после B4A id duplicate, перед placeholder 2858).

RED: 18 тестов b5_*; 11 EXPECTED_B5_RED (production не валидирует arguments -> placeholder), 7 passing (positive/precedence/adjacent). Regression зелёный (b4a/b4c/b3m/b2), workspace падает только на b5, clippy/fmt/parity/diff exit 0. Production не изменён (только test-module additions).

Условие остановки достигнуто: RED доказывает отсутствие B5 arguments validation. Следующий шаг (после приёмки) = B5 GREEN (реализовать валидацию в seam, не снимая placeholder).

---

# B5 GREEN - результат (2026-07-28)

Статус: B5 GREEN COMPLETE. NEXT_ALLOWED = B5L (arguments resource limits).

Production: минимальная B5 validation (arguments required + object type) в seam 2857-2865
(после B4A id, перед placeholder). code protocol_mismatch; missing -> "tool call arguments are required";
!is_object -> "tool call arguments must be an object"; {} разрешён. Placeholder сохранён.
Порядок B3M -> B4A -> B5 -> placeholder. Atomicity сохранена. Scope: только presence + object type
(НЕ per-tool schema/resource limits/cross-event/provenance/execution).

Регрессионная правка: 10 фикстур B2/B3M/B4A мигрированы string->object (ратифицированный carrier),
ассерты сохранены. Необходимо для workspace 232/0/6. За пределами строгого writer-scope - зафиксировано.

Gates: B5 18/0; Workspace 232/0/6; B4A/B4C/B3M/B2 зелёные; fmt/clippy/parity/diff exit 0.

Следующий шаг: B5L (resource limits: размер/глубина/keys/total nodes) - обязателен до снятия
placeholder и включения tools. B6/provenance/execution/TOCTOU не начинались.

---

# B5L RED - статус (2026-07-29)

Статус: B5L RED (только RED-тесты).
Production implementation: FORBIDDEN (в этой сессии).
Следующий шаг (после приёмки): B5L_GREEN.

Лимиты (решение владельца): MAX_ARGUMENT_BYTES=65_536, MAX_ARGUMENT_DEPTH=32,
MAX_ARGUMENT_OBJECT_KEYS=512, MAX_ARGUMENT_NODES=4_096.
Порядок: B3M -> B4A -> B5 required/object -> B5L bytes -> depth -> keys -> nodes -> placeholder.
Exact errors (protocol_mismatch): exceed maximum size / nesting depth / object key count / node count.

RED: 16 тестов b5l_* (8 positive PASS placeholder, 8 negative EXPECTED_B5L_RED).
focused 8 passed / 8 failed (exit 101); workspace 240 passed / 8 failed / 6 ignored.
Существующие 232 теста зелёные (b5 18/0, b4a 10/0, b4c 6/0, b3m 10/0, b2 11/0).
Production не изменён (control_plane.rs deletions 35; B5L только в test module).
Finding B5LP: Python pre-parse resource limits для arguments ОТСУТСТВУЮТ (отдельный finding).
Контракт: docs/audit/B5L_RESOURCE_LIMITS_CONTRACT.md.

---

# B5L GREEN - статус (2026-07-29)

Статус: B5L_GREEN_COMPLETE. NEXT_ALLOWED=B5LP_RED.
Лимиты реализованы (Rust defense-in-depth): bytes 65_536 / depth 32 / keys 512 / nodes 4_096.
Итеративный traversal (saturating_add, без рекурсии). Precedence bytes->depth->keys->nodes.
RED 8/8 -> GREEN 16/0; workspace 248/0/6. Production diff минимальный (constants + measure_arguments + block).
B5LP (Python pre-parse limits) = NEXT_ALLOWED (Python не менялся). B6 NOT_STARTED. TOCTOU OPEN.

---

# B5LP RED Specification

Session: 2026-07-30. Tree digest: 0b9601963996cb231a822dfb2de031679712b1432cca4b11e43b86fac24e6fe8

## Goal

Add test-only coverage proving that Python currently lacks the ratified argument resource limits.

## Limits

Bytes: 65_536 (MAX_ARGUMENT_BYTES)
Depth: 32 (MAX_ARGUMENT_DEPTH, root=1)
Object keys: 512 (MAX_ARGUMENT_OBJECT_KEYS, total across all objects)
Nodes: 4_096 (MAX_ARGUMENT_NODES, root + objects + arrays + scalars; key names not counted)

## Exact errors

| Violation | Code | Exact message |
|---|---|---|
| Raw byte size > 65536 | invalid_payload | tool arguments exceed maximum size |
| Depth > 32 | invalid_payload | tool arguments exceed maximum nesting depth |
| Object keys > 512 | invalid_payload | tool arguments exceed maximum object key count |
| Nodes > 4096 | invalid_payload | tool arguments exceed maximum node count |

## Validation order

Raw bytes
→ pre-parse depth
→ JSON parsing
→ duplicate-key rejection
→ top-level object validation
→ keys
→ nodes
→ per-tool schema
→ event emission

## Allowed files

- tools/test_adr015_tool_parsing.py (append B5LP test class)
- pipeline/discovery.md
- pipeline/spec.md
- pipeline/loop-status.md
- pipeline/changes.md
- pipeline/test-results.md
- docs/audit/**
- artifacts/evidence/**

## Forbidden files

- modules/local_model_gateway_ru.py (production Python)
- modules/tool_execution_ru.py (production Python)
- desktop/localcomet-desktop/src-tauri/src/** (production Rust)
- desktop/localcomet-desktop/src-tauri/tests/** (Rust tests)
- desktop/localcomet-desktop/src/** (frontend)
- security/invariants/** (schemas)
- pipeline/task-tracker.md (tracker)
- All other production code

## Expected focused RED

- Existing/positive passes: 8 tests (tests 1-8)
- Expected B5LP RED failures: 10 tests (tests 9-15, 18-20)
- Scanner guard passes: 2 tests (tests 16-17, pass now, guard GREEN correctness)
- Invalid failures: 0

## Stop conditions

- production modification → SCOPE_VIOLATION
- broken baseline → B5LP_RED_BASELINE_INVALID
- no test seam → B5LP_TEST_SEAM_BLOCKED
- invalid test failure → B5LP_RED_INVALID
- unrelated regression → B5LP_RED_REGRESSION
- insufficient agent capacity → B5LP_RED_BLOCKED_BY_AGENT_CAPACITY
