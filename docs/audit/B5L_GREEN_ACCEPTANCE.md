# B5L GREEN Acceptance

Статус: **B5L_GREEN_COMPLETE**. Дата: 2026-07-29. NEXT_ALLOWED=B5LP_RED.
Final tree digest: 0b9601963996cb231a822dfb2de031679712b1432cca4b11e43b86fac24e6fe8 (284 source files).
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364. Branch: feature/donor-ui-compatible-port.
Tracker: EA646B0A2C73F7AE714094A6DD3264BC03BDB8BBA6733D038352E8DF3DB1D3D4 (384 строки, не изменён).

## Четыре лимита (решение владельца)

| Лимит | Значение | Определение |
|---|---|---|
| MAX_ARGUMENT_BYTES | 65_536 | размер UTF-8 JSON-сериализации arguments (serde_json::to_string, не pretty-print) |
| MAX_ARGUMENT_DEPTH | 32 | root object=1; вложенный object/array +1; scalar не увеличивает container depth |
| MAX_ARGUMENT_OBJECT_KEYS | 512 | суммарное количество ключей во всех вложенных objects |
| MAX_ARGUMENT_NODES | 4_096 | root + каждый вложенный object + каждый array + каждый scalar value (имена ключей НЕ nodes) |

Граница: value <= limit разрешено (<=); value > limit ошибка (>).

## Exact errors (code = "protocol_mismatch")

- bytes: "tool call arguments exceed maximum size"
- depth: "tool call arguments exceed maximum nesting depth"
- keys: "tool call arguments exceed maximum object key count"
- nodes: "tool call arguments exceed maximum node count"

Precedence (при нескольких нарушениях): bytes -> depth -> keys -> nodes.

## Validation order

identity -> metadata allowlist -> lifecycle/sequence guards -> tools-enabled guard -> tool_calls container
-> tool name -> B3M membership -> B4A ID -> B5 required/object -> B5L bytes -> B5L depth -> B5L keys
-> B5L nodes -> strict placeholder -> no mutation for tool events.

B5L seam: после B5 object validation (control_plane.rs:2865) и до strict placeholder (:2867), внутри цикла for call.

## RED -> GREEN

- RED (tree dde088cfdc): b5l_ 8 passed / 8 failed (exit 101); 8 negative = EXPECTED_B5L_RED.
- GREEN (tree 0b960196): b5l_ **16 passed / 0 failed** (exit 0).
- Workspace: **248 passed / 0 failed / 6 ignored**.

## Production diff (минимальный)

Только desktop/localcomet-desktop/src-tauri/src/control_plane.rs:
1. 4 constants (MAX_ARGUMENT_BYTES/DEPTH/OBJECT_KEYS/NODES) после существующих constants (~41).
2. struct ArgumentMetrics { max_depth, object_key_count, node_count }.
3. fn measure_arguments(root: &Value) -> ArgumentMetrics — ИТЕРАТИВНЫЙ stack-based traversal
   (Vec<(&Value, usize)>, saturating_add, без рекурсии; scalar = node но не увеличивает container depth;
   object/array child получает depth+1).
4. B5L validation block в seam: serde_json::to_string(arguments).map_err(...)? (без unwrap/expect/panic);
   bytes check ДО traversal (traversal только для <= 65_536 bytes); затем depth -> keys -> nodes.

НЕ добавлено: универсальный JSON framework, новые модули/dependencies, кэш, cross-event state,
per-tool schema, Python/execution logic. ModelRequestEntry НЕ изменён (нет metric-полей).

## Atomicity

B5L validation block в seam (внутри цикла for call) возвращает Err ДО мутаций entry (:2893-2901,
после placeholder). Tool-ветка не содержит присваиваний entry.*. measure_arguments — чистая функция
(читает &Value, не мутирует). При отказе (B5L error) entry остаётся в исходном состоянии
(next_sequence==0, terminal_seen==false, event_count==0, started_seen==false, generated_bytes==0,
provider_id==None, harness_id==None). Batch: отказ call k прерывает функцию до мутаций -> все поля неизменны.
Тесты b5l_invalid_second_call_rejects_batch_atomically и b5l_failure_does_not_mutate_entry проверяют 7 полей.

## Безопасность

- Production tools: **DISABLED** (AssistantContext::trusted tools=Vec::new():302; call site :2134->:2144; нет пути включить).
- Strict placeholder: **ACTIVE** (:2867-2870); valid arguments проходят B5L, затем placeholder.
- B5L bounded: bytes check до traversal; traversal только для <= 65_536 bytes; итеративный (нет рекурсии); saturating_add (нет overflow).
- B5LP (Python pre-parse resource limits): **OPEN** (Python не имеет pre-parse limits для arguments; Python НЕ менялся в B5L; B5L = Rust defense-in-depth, не закрывает B5LP).
- B6: **NOT_STARTED**.
- TOCTOU: **OPEN**.

## Регрессия

B5 18/0; B4A 10/0; B4C 6/0; B3M 10/0; B2 11/0; clippy --all-targets -D warnings exit 0; fmt exit 0;
parity exit 0; git diff --check exit 0.

## Evidence

Current evidence (63 файла, tree 0b960196): 0 STALE / 0 BODY_MISMATCH (check_evidence_provenance.py exit 0).
B5_CURRENT_EVIDENCE_MANIFEST.sha256 (63 файла). b5l_green_*.txt (preflight, red_reconfirmation, focused,
b5/b4a/b4c/b3m/b2, workspace, fmt, clippy, parity, diff, security, agents).
Historical evidence (46 в historical/): 46 valid, 0 BODY_MISMATCH, original digests preserved
(check_historical_evidence.py exit 0). Не перемещались, digests не изменялись.

## Дифференциал Python/Rust (finding B5LP)

Python (Model -> Python) НЕ имеет pre-parse resource limits для arguments: ToolCallAccumulator.build()
(local_model_gateway_ru.py:2172-2186) передаёт неограниченную строку в json.loads (:2180) без size check;
depth не ограничена (нет setrecursionlimit/max_depth -> RecursionError crash, не graceful rejection);
_read_bounded/maximum_output_bytes к arguments не применяются; validate_tool_call (:2120) — per-tool schema,
не resource limit. B5LP = отдельный finding для будущей работы (NEXT_ALLOWED=B5LP_RED). Python НЕ менялся.

## Следующий шаг

B5LP_RED (Python pre-parse resource limits для arguments). B6/provenance/execution binding/TOCTOU fix — не начинались.
