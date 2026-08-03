# B5L Resource Limits Contract

Статус: **B5L RED** (только RED-тесты). Production implementation: **FORBIDDEN** в этой сессии.
Дата: 2026-07-29. Решение владельца по лимитам принято.

## Четыре лимита (generic)

| Лимит | Значение | Определение |
|---|---|---|
| MAX_ARGUMENT_BYTES | 65_536 | размер UTF-8 JSON-представления arguments (serde_json::to_string(&v).len()) |
| MAX_ARGUMENT_DEPTH | 32 | root object depth=1; вложенный object или array +1; scalar НЕ увеличивает |
| MAX_ARGUMENT_OBJECT_KEYS | 512 | суммарное количество ключей во всех вложенных объектах (включая root) |
| MAX_ARGUMENT_NODES | 4_096 | root + каждое object/array/scalar значение = отдельный узел |

## Граница

- значение ровно на лимите принимается (<=);
- значение больше лимита отвергается (>).

## Exact errors (code = "protocol_mismatch")

- bytes: "tool call arguments exceed maximum size"
- depth: "tool call arguments exceed maximum nesting depth"
- keys: "tool call arguments exceed maximum object key count"
- nodes: "tool call arguments exceed maximum node count"

## Validation order

1. B3M membership
2. B4A ID
3. B5 required/object
4. B5L bytes
5. B5L depth
6. B5L object keys
7. B5L nodes
8. strict placeholder

B5L встанет между B5 object (control_plane.rs:2865) и strict placeholder (:2867), внутри цикла for call.

## Две защитные границы

### Model -> Python (Python получает JSON string)

Finding **B5LP**: Python pre-parse resource limits для arguments ОТСУТСТВУЮТ.
- ToolCallAccumulator.build() (local_model_gateway_ru.py:2172-2186) передаёт неограниченную
  по размеру строку в json.loads без pre-parse size check.
- Depth не ограничена явно (json.loads без max_depth; default recursion limit CPython ~1000 ->
  RecursionError crash, не graceful rejection).
- _read_bounded (:2268) ограничивает весь response body (models-list 262_144; SSE per-event 16_384,
  per-stream 262_144), но НЕ суммарную накопленную строку arguments и не глубину/ключи/узлы.
- object_pairs_hook=_reject_duplicate_keys и parse_constant=_reject_json_constant покрывают
  duplicate keys и NaN/Infinity, но НЕ size/depth/keys/nodes.
- Теоретический потолок: 2048 SSE events x 16 KiB ~= 32 MiB накопленных arguments.

B5LP = отдельный finding (Python pre-parse resource limits). Production Python НЕ меняется в B5L RED.

### Python -> Rust (Rust получает parsed object)

Rust B5L (defense-in-depth, будущий GREEN) повторно проверяет parsed object arguments:
serialized bytes, depth, keys, nodes. Production Rust сейчас НЕ имеет этих лимитов
(grep MAX_ARGUMENT/exceed maximum в src-tauri/src = 0). IPC frame limit (4 MiB, ipc.rs:5) —
транспортный уровень, не валидация; тесты вызывают validate_and_record_model_event напрямую.

## Non-goals (B5L RED)

- НЕ реализовывать лимиты (только RED-тесты).
- НЕ менять production Rust/Python.
- НЕ менять B5-тесты.
- НЕ добавлять B6/provenance/execution binding/TOCTOU fix.
- НЕ включать tools, НЕ снимать placeholder.
- Python pre-parse limits (B5LP) — отдельный finding, не реализуется в B5L RED.

## RED-тесты (16)

8 positive (PASS, ожидают exact placeholder): small, exact byte/depth/key/node limit, unicode within,
valid batch, adjacent independent.
8 negative (RED = EXPECTED_B5L_RED, ожидают exact B5L error): byte/depth/key/node limit+1,
unicode byte limit+1, multiple violations precedence (depth раньше keys), invalid second call
batch atomic, failure does not mutate entry.

Test helpers (test-only, детерминированные): count_bytes/count_depth/count_keys/count_nodes +
builders args_with_bytes/depth/keys/nodes/unicode_bytes (с assert-верификацией точной границы) +
args_depth_and_keys_violation (depth 33 + keys 544 для precedence-теста). Фикстуры минимальные
(около границы), не DoS.

## Следующий шаг

B5L_GREEN (реализовать лимиты в seam :2865-2867, порядок bytes->depth->keys->nodes, exact errors).
B5LP (Python pre-parse limits) — отдельный finding для будущей работы.
