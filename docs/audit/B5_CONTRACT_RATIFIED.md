# B5 Contract — RATIFIED

Статус: **B5 CONTRACT RATIFIED** (решение владельца принято как authority).
Дата: 2026-07-28. Tree digest: 8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88.
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364. Branch: feature/donor-ui-compatible-port.
Предыдущий статус: B5_CONTRACT_BLOCKED (см. docs/audit/B5_CONTRACT_CONFLICT.md — варианты A/B/C/D/E).

Этот документ фиксирует утверждённый контракт как единственный авторитет для B5 RED/GREEN.

---

## 1. Carrier (разрешение конфликта A)

Канонические границы:

```
Model output → Python:      arguments = JSON string
Python → Rust model event:  arguments = parsed JSON object
```

На Rust event boundary `metadata.tool_calls[*].arguments` **должен быть JSON object**.

Rust **отвергает**:
- JSON string;
- stringified object (напр. `"{\"path\":\"a.txt\"}"` как строка);
- null;
- array;
- number;
- boolean.

**Dual carrier запрещён.** Старые Rust-фикстуры, использующие string
(control_plane.rs:5833+, structured_tool_event:5736), **не являются authority**
для event boundary — они предшествуют B5 и не валидировали arguments.

Обоснование (фактическая эмиссия): Python `ToolCallAccumulator.build()`
(local_model_gateway_ru.py:2180-2185) парсит строку через `_loads_json` и эмитит
dict; empty string → `{}` (:2184); терминал `model.turn.tool_calls` (:877→:1026)
и `model.tool.request` (:869) несут object. `validate_tool_call` (:2124) требует
Mapping до эмиссии. IPC schema (desktop/contracts/localcomet_ipc_v1.schema.json)
молчит об arguments (не авторитет).

## 2. Error contract (разрешение конфликта B)

| Случай | code | message |
|---|---|---|
| Missing arguments (ключа нет) | `protocol_mismatch` | `tool call arguments are required` |
| Wrong type (string/null/array/number/boolean) | `protocol_mismatch` | `tool call arguments must be an object` |

Пустой объект `{}` **разрешён** (valid → достигает strict placeholder).

## 3. Scope (разрешение конфликта D)

B5 Rust проверяет **только**:
- presence (наличие ключа arguments);
- object type (Value::Object);
- validation order (B3M → B4A → B5);
- batch atomicity;
- exact errors;
- достижение strict placeholder для valid object.

B5 **НЕ проверяет**:
- per-tool schema (required/properties/unknown fields);
- workspace;
- permissions;
- approval;
- execution;
- resource limits;
- cross-event consistency;
- provenance.

## 4. Duplicate keys (разрешение конфликта C)

Duplicate JSON keys отвергаются на границе Python parser
(_reject_duplicate_keys, local_model_gateway_ru.py:2310-2316). Rust получает уже
разобранный object и **не обязан** восстанавливать исходные duplicate keys
(serde_json коллапсирует last-wins; на parsed-object seam duplicates невозможны).

## 5. arguments=None (разрешение конфликта E)

Python canonical event не должен содержать `"arguments": null`
(validate_tool_call:2124 отвергает None до эмиссии; event-emitter подтвердил
отсутствие обхода). Rust **обязан отвергать null как wrong type**
(defense-in-depth: malicious/buggy sidecar).

## 6. Resource limits → B5L

Размер, глубина, количество ключей и total nodes относятся к отдельному этапу
**B5L — arguments resource limits**. B5L **обязателен до снятия placeholder и
включения tools**. Существующие лимиты (не B5): 4 MiB IPC frame (ipc.rs:5),
cumulative event/text бюджеты (control_plane.rs:2872-2883), serde_json recursion
depth 128. Gap: нет выделенного per-arguments бюджета; Python json.loads без
лимита рекурсии (RecursionError не ловится в build():2181).

## 7. Validation order (фактический, подтверждён)

```
identity → metadata allowlist → lifecycle/sequence guards
→ tools-enabled guard (2784)
→ structured tool_calls container (2790/2800)
→ exactly-one для model.tool.request (2806)
→ tool name extraction (2814)
→ B3M membership (2820)
→ B4A ID validation (2830-2856)
→ [B5 arguments: presence + object type] ← seam между 2856 и 2857
→ strict placeholder (2858)
→ no mutation for tool events (2884+ недостижимы)
```

## 8. Security posture (подтверждено red-team)

- Production tools DISABLED (trusted() tools=Vec::new():302; call site 2134→2144).
- Strict placeholder ACTIVE (2858-2861); в production дополнительно недостижим
  из-за tools-guard 2784 (defense-in-depth).
- Workspace TOCTOU OPEN.
- Эксплуатируемого parser-differential bypass на честном пути нет
  (Python gatekeeper + Rust fail-closed).

## 9. Следующий шаг

B5 RED: добавить только тесты, доказывающие, что production не валидирует
arguments (rejection-тесты падают = EXPECTED_B5_RED; positive/precedence проходят).
B5 GREEN, B5L, B6 — не начинаются в этом цикле.
