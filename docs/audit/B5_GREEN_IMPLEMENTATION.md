# B5 GREEN Implementation — arguments required + object validation

Статус: **B5 GREEN COMPLETE**. Дата: 2026-07-28.
Tree digest: ae579fb9739c870b5987907a50313096f2872b79c051fdaa34299746def49632 (283 файла).
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364. Branch: feature/donor-ui-compatible-port.
Контракт: docs/audit/B5_CONTRACT_RATIFIED.md. RED: docs/audit/B5_PARSER_DIFFERENTIAL_MATRIX.md.

## Результат

- B5 focused: 18 passed / 0 failed (было 7/11 в RED).
- Workspace: 232 passed / 0 failed / 6 ignored (было 221/11/6 в RED).
- Регрессии: B4A 10/0, B4C 6/0, B3M 10/0, B2 11/0.
- fmt / clippy (-D warnings) / parity / diff --check: exit 0.

## Production change (минимальная вставка, 9 строк)

control_plane.rs, validate_and_record_model_event, внутри цикла for call,
ПОСЛЕ B4A id duplicate (2856), ПЕРЕД strict placeholder (2867-2870):

```rust
let arguments = call.get("arguments").ok_or_else(|| {
    BridgeError::new("protocol_mismatch", "tool call arguments are required")
})?;
if !arguments.is_object() {
    return Err(BridgeError::new(
        "protocol_mismatch",
        "tool call arguments must be an object",
    ));
}
```

- missing arguments -> protocol_mismatch "tool call arguments are required".
- null/string/array/boolean/number (не object) -> protocol_mismatch "tool call arguments must be an object".
- {} и любой JSON object (включая вложенные) -> проходит, цикл продолжается к placeholder.
- Rust НЕ: парсит JSON string, принимает stringified object, делает dual carrier, null->{},
  per-tool schema, нормализует/изменяет arguments, сохраняет cross-event.
- Strict placeholder СОХРАНЁН (2867-2870). Validation order: B3M -> B4A -> B5 -> placeholder.
- Atomicity: B5 return Err внутри цикла ДО мутаций (2884+); entry не мутирует при отказе.

## Fixture migration (регрессионная правка, НЕ расширение)

Ратифицированный carrier = parsed JSON object. 10 существующих тестов B2/B3M/B4A использовали
STRING arguments (через хелперы structured_tool_event :5745 и raw_tool_event json!), что стало
несовместимо с B5 (string отвергается). Для достижения целевого workspace 232/0/6 мигрированы:

- Хелпер structured_tool_event: "arguments": args (string) -> serde_json::from_str::<Value>(args)
  (parsed object). Затрагивает тесты, использующие хелпер (B2/B3M/B4C).
- 5 B4A raw_tool_event тестов (b4a_valid_single_id, b4a_distinct_terminal_ids,
  b4a_duplicate_terminal_id, b4a_duplicate_id_same_tool, b4a_adjacent): json! "arguments":"{}"
  -> "arguments":{} (object); b4a_valid_single_id "arguments":"{\"path\":...}" -> object.

Все ассерты СОХРАНЕНЫ (изменена только форма входных arguments, не ожидаемые сообщения).
B5 RED-тесты НЕ изменены. Непadaющие B4A id-тесты (id-ошибка раньше B5) не тронуты.
B5 test b5_stringified_object_arguments_must_be_object намеренно оставлен со string carrier
(проверяет отвержение stringified object).

ВАЖНО (для владельца): миграция фикстур — за пределами строгого "production validation block"
(writer scope). Это неизбежное следствие ратифицированного object carrier: целевой workspace
232/0/6 недостижим без миграции 10 string-фикстур. Ассерты не ослаблены. Зафиксировано честно.

## Diff control

control_plane.rs numstat: 1486 insertions / 35 deletions (RED было 1476/35).
+10 insertions = 9 (production B5) + 1 (helper). Deletions НЕИЗМЕННЫ (35) -> ни одна
существующая строка production не модифицирована/удалена. Production изменён ТОЛЬКО B5-вставкой.
Python/frontend/schemas/registries/ModelRequestEntry/tracker НЕ изменены.

## Security posture

- Production tools: DISABLED (trusted() tools=Vec::new():302).
- Strict placeholder: ACTIVE (2867-2870); в production дополнительно tools-guard :2784.
- State atomicity: CONFIRMED (мутации 2884+ недостижимы для tool events).
- Scope expansion: НЕТ (нет B6/B5L/resource limits/per-tool schema/provenance/execution/TOCTOU).
- Workspace TOCTOU: OPEN.

## Evidence

artifacts/evidence/b5_green_{focused,regressions,workspace,aux_gates,diff}.txt (tree ae579fb9)
+ B5_GREEN_MANIFEST.sha256. Pre-patch RED snapshot: b5_green_red_*.txt (tree cc18487b).
RED evidence: b5_red_adversarial_*.txt (cc18487b). Provenance: файлы cc18487b/8a0d1d80 STALE
относительно ae579fb9 (дерево легитимно изменено GREEN-патчем) - ожидаемо, не tampering.

## Следующий шаг

B5L (arguments resource limits: размер/глубина/количество ключей/total nodes) - обязателен
до снятия placeholder и включения tools (по ратифицированному контракту, раздел 6).
B6, provenance, execution binding, TOCTOU fix - не начинались.
