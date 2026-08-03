# B5 Fixture Migration Acceptance

Статус: **FIXTURE MIGRATION ACCEPTED** (одобренное test-fixture изменение).
Дата: 2026-07-29. Tree digest: ae579fb9739c870b5987907a50313096f2872b79c051fdaa34299746def49632.
Подтверждено: @fixture-migration-reviewer (ses_054a224e4ffeV0qqVBYWW8wOKH), финальный @final-fixture-reviewer.

## Что изменено

10 тестовых фикстур B2/B3M/B4A в desktop/localcomet-desktop/src-tauri/src/control_plane.rs
мигрированы с string carrier на canonical parsed JSON object:

Через хелпер structured_tool_event (:5732-5752; "arguments": serde_json::from_str::<Value>(args)):
1. b2_enabled_request_reaches_next_strict_tool_validation_stage
2. b3m_permitted_tool_reaches_next_strict_stage
3. b3m_terminal_batch_all_permitted_reaches_placeholder
4. b3m_terminal_batch_with_forbidden_name_rejected_atomically
5. b3m_terminal_batch_with_unknown_name_rejected_atomically

Через raw_tool_event json! (string "{}"/"{...}" -> object {}/{...}):
6. b4a_valid_single_id_reaches_placeholder
7. b4a_distinct_terminal_ids_reach_placeholder
8. b4a_duplicate_terminal_id_rejected
9. b4a_duplicate_id_same_tool_rejected
10. b4a_adjacent_request_id_scope_independent

## Гарантии

- Carrier изменён string -> canonical object (ратифицированный Python->Rust carrier,
  docs/audit/B5_CONTRACT_RATIFIED.md: Python эмитит parsed object, build():2180-2185).
- Production behavior тестов НЕ ослаблен: ожидаемые сообщения сохранены
  (placeholder "not yet implemented" / "not permitted for this request" / "duplicate tool call id").
- Assertions НЕ изменены (те же assert!/assert_eq! по code+message; atomicity next_sequence==0/
  !terminal_seen/event_count==0 на месте).
- B5 RED-тесты (b5_missing_arguments_required, b5_null/string/stringified/empty/whitespace/
  array/number/boolean, atomicity, precedence) НЕ менялись; точные assert_eq! по code+message.
- b5_stringified_object_arguments_must_be_object намеренно оставлен со string carrier
  (проверяет отвержение stringified object — доказательство запрета dual carrier).
- Непadaющие B4A id-тесты (id-ошибка срабатывает раньше B5) не тронуты.

## Обоснование необходимости

Ратифицированный контракт (B5_CONTRACT_RATIFIED.md): metadata.tool_calls[*].arguments на Rust
event boundary обязан быть JSON object; string/stringified/null/array/number/boolean отвергаются
(B5 validation control_plane.rs:2857-2865). Старые фикстуры использовали string arguments
(до B5 arguments не валидировался, форма не имела значения). После B5 GREEN string отвергается,
поэтому 10 фикстур мигрированы к object для сохранения зелёного состояния (workspace 232/0/6).
Без миграции целевой workspace 232/0/6 недостижим (10 тестов упали бы на B5 "must be an object").

## Классификация

Это **одобренное test-fixture изменение** (форма входных arguments), а НЕ:
- production scope expansion (production изменён только B5 validation 2857-2865, deletions 35 неизменны);
- ослабление тестов (assertions сохранены);
- изменение B5 RED-тестов;
- изменение Python/frontend/schemas/registries/tracker.

Миграция за пределами строгого writer-scope "production validation block" — зафиксировано
честно и одобрено настоящим документом как необходимое следствие ратифицированного object carrier.
