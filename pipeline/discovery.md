# pipeline/discovery.md — журнал фазы DISCOVER (сессия 2026-07-27)

Ветка: feature/donor-ui-compatible-port. Авторитет = байты на диске / актуальный код.

---

## Баг #1: request_model_turn_reserved (inference падает)

Корневая причина [ФАКТ, SHA-256]:
- Запущенный sidecar грузит gateway из бандла
  `%LOCALAPPDATA%\LocalComet\DevRuntime\cargo-target\debug\app\modules\local_model_gateway_ru.py`
  (SHA BC43AAE4..., 1928 строк).
  `ASSISTANT_CONTEXT_CONVERSATION_KEYS = {locale, project_context_available}` — 2 ключа (строка 68).
- Rust-мост `control_plane.rs:274-278` (AssistantContext::trusted) сериализует 3 ключа:
  {locale, project_context_available, selected_files_context_available}.
- `set(conversation) != expected` → `_validate_assistant_context` бандла (строка 261)
  бросает GatewayError("invalid_payload", "assistant conversation context is invalid").
- Исходник репо согласован (3 ключа и в Rust, и в Python; SHA 403A0640..., 1961 строка).
  Дефект = устаревший бандл (stale build artifact), не рассинхрон исходников.

Воспроизведение [ФАКТ, вывод команды]:
- Лог: `context=request_reserved_model_start code=invalid_payload message=assistant conversation context is invalid`.
- Тест `tools/test_bug1_inference_bundle_parity.py` (exit 1):
  PART A OK (repo gateway принимает payload моста), PART B FAIL (бандл отклоняет).

Зависимости: gateway импортирует modules.knowledge_injection_ru; бандл = полный срез из 11 модулей.
Кто вызывает: sidecar runner tools/run_localcomet_desktop_sidecar.py (sys.path.insert(root)),
root = cargo-target/debug/app (release-layout). Ошибка присутствует ТОЛЬКО в бандл-копии
(в workspace-копии этой строки нет) → запущен именно бандл.

---

## Баг #2: execute_approved → диспетчеризация инструментов

Классификация: (B) FEATURE_GAP — путь диспетчеризации ПОЛНОСТЬЮ ОТСУТСТВУЕТ по проекту.

Факты (все — актуальный код, не audit/):
- execute_approved (approval_commands.rs:108-136) валидирует scope, потребляет токен,
  возвращает grant {grant_id, tool, workspace, session}. НЕ диспетчеризует — намеренно
  (approval_commands.rs:103-107 "honest boundary").
- Поля grant input_digest/nonce = #[allow(dead_code)] "consumed by a downstream
  tool-execution path when one exists" (approval.rs:246-255).
- Frontend: обёртки requestApproval/executeApproved (bridge/approval.ts:16-39) НЕ вызываются
  ни одним компонентом; grant не потребляется. ApprovalCard.svelte — мок/disabled, честное
  состояние "Отключено" (INV-UI-001 соблюдён).
- Sidecar: tool/filesystem-методы → unsupported_method (desktop_sidecar_runtime_ru.py:170,
  desktop_control_plane_ru.py:390,2087-2088, local_model_gateway_ru.py:1460-1461).
  Закреплено регрессионным тестом smoke_test.py:114-123 (files.read обязан отклоняться).
- Rust: нет варианта ControlPlaneMethod для tool.call (control_plane.rs:54-110),
  нет литерала "tool.call" в src-tauri/src, нет команды run_tool_call в generate_handler!
  (lib.rs:212-256, 43 команды).
- command parity = 43; run_tool_call/tool.call отсутствуют.
- Ассистенту декларативно выключены filesystem/shell/tools (control_plane.rs:285-289).

Объём реализации пути: 10-15 файлов, ~500-900+ строк, 3 слоя (Rust/TS/Python),
затрагивает tool_risk_levels.toml + INV-UI-001 + инверсию smoke_test.py[06].
Вывод: фича, требует ADR + согласования владельца (п. 132, 144, 146). Не багфикс.

---

## Находка гейта bundle parity (scripts/check_bundle_parity.py)

Сверка SHA-256 бандла (DevRuntime/cargo-target/debug/app/modules) с репо:
11 модулей бандла, 9 совпадают, 2 STALE [ФАКТ, вывод гейта, exit 1]:
- local_model_gateway_ru.py: бандл 1928L / репо 1961L — модуль бага #1.
- knowledge_change_proposal_ru.py: бандл 785L / репо 783L — ВТОРОЙ рассинхрон
  (латентный, в knowledge-review; диагностика бага #1 его не выявляла).
Пересборка бандла обновит оба модуля. Гейт bundle parity детектирует класс
бага #1 (репо ≠ бандл); добавлен в Block 4 ADR-013 и служит проверкой
precondition #1 (PART B зелёный после пересборки).

## ADR-013 статус
APPROVED (2026-07-27) с 7 правками владельца. Каталог ADR = {001,008,009,013};
013 свободен (ADR-010/011/012 отсутствуют). Block 1 gated на пересборке бандла.

---

# B5LP RED Discovery

Session: 2026-07-30. Tree digest: 0b9601963996cb231a822dfb2de031679712b1432cca4b11e43b86fac24e6fe8

## Python boundary

Model input: SSE tool_calls deltas (OpenAI format) fed via ToolCallAccumulator.feed()
Raw arguments representation: str accumulated in ToolCallAccumulator._calls[index]["arguments"]
Parsing function: _loads_json() at modules/local_model_gateway_ru.py:2300 (json.loads with object_pairs_hook)
Duplicate-key behavior: _reject_duplicate_keys() at line 2310 raises GatewayError("invalid_payload", "duplicate JSON key rejected")
Top-level object validation: validate_tool_call() at line 2120 checks isinstance(arguments, Mapping)
Per-tool schema validation: validate_tool_call() at line 2120 checks registry, unknown fields, required fields, types
Event emission: _run_turn() at line 822-856 builds calls, validates, queues model.tool.request events

## Missing protections

Raw byte limit: ABSENT — no len(raw_arguments.encode("utf-8")) check before _loads_json
Pre-parse depth limit: ABSENT — no nesting depth scanner before json.loads
Post-parse key limit: ABSENT — no total object key count check after parsing
Post-parse node limit: ABSENT — no total node count check after parsing

## Testable seam

Function: ToolCallAccumulator.build() at modules/local_model_gateway_ru.py:2172
Test file: tools/test_adr015_tool_parsing.py (existing patterns: feed/build, _raises helper)
Fixture strategy: Construct arguments strings at exact limits and limit+1; feed via accumulator; call build()
State or output observable on failure: build() returns list[dict] with arguments field; GatewayError.code and .message

CRITICAL: build() at line 2181 catches GatewayError and sets arguments=None.
RED tests assert expected FUTURE behavior (GatewayError propagation with specific code/message).
Currently fails because no limit check exists and no error is raised.

## Authority evidence

| Claim | File:line | Evidence |
|---|---|---|
| ToolCallAccumulator defined | modules/local_model_gateway_ru.py:2138 | class ToolCallAccumulator |
| build() parses via _loads_json | modules/local_model_gateway_ru.py:2180 | arguments = _loads_json(raw_arguments.encode("utf-8")) |
| build() swallows GatewayError | modules/local_model_gateway_ru.py:2181-2182 | except GatewayError: arguments = None |
| _loads_json uses json.loads | modules/local_model_gateway_ru.py:2303 | json.loads(text, object_pairs_hook=_reject_duplicate_keys) |
| GatewayError has code+message | modules/local_model_gateway_ru.py:120-125 | self.code, self.message |
| validate_tool_call rejects non-Mapping | modules/local_model_gateway_ru.py:2124-2125 | if not isinstance(arguments, Mapping): raise |
| No MAX_ARGUMENT_BYTES in Python | (grep all *.py) | zero matches |
| No MAX_ARGUMENT_DEPTH in Python | (grep all *.py) | zero matches |
| Rust limits at control_plane.rs:42-45 | desktop/localcomet-desktop/src-tauri/src/control_plane.rs:42-45 | 65_536, 32, 512, 4_096 |

## Open blockers

None. Seam is fully testable. No production API changes needed for RED tests.
