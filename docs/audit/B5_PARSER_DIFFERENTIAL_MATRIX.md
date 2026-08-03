# B5 Parser-Differential Matrix — Python ↔ Rust

Статус: B5 CONTRACT RATIFIED → PARSER-DIFFERENTIAL AUDIT. Дата: 2026-07-28.
Tree digest: 8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88.

Граница: Model → Python (arguments = JSON string) → Python parser/validate →
Python → Rust event (arguments = parsed JSON object). Rust получает УЖЕ
распарсенный `serde_json::Value` (IPC envelope парсится serde_json::from_slice,
control_plane.rs:1576). Повторного парсинга содержимого arguments в Rust нет.

Ключевой факт: на parsed-object seam классы **malformed JSON / trailing content /
duplicate keys / BOM / invalid surrogate НЕПРИМЕНИМЫ** — они отсеяны Python
parser'ом (_loads_json :2300-2327) и/или serde_json при IPC receive. `Value`
существует только как валидная JSON-структура.

---

## Матрица

| Input model string | Python parse | Python validation | Emitted event | Rust Value | Information lost | Verdict |
|---|---|---|---|---|---|---|
| 6.1 `{"path":"a.txt"}` (valid object) | OK → dict | OK (Mapping, required path, str) | model.tool.request + model.turn.tool_calls | `Value::Object` | исходный текст, whitespace, порядок ключей | совместимо; Rust B5 примет object (valid → placeholder) |
| 6.2 `{}` (empty object) | OK → {} | REJECT: missing required path (:2130) | нет → model.turn.failed | — | — | Python rejects / Rust B5 generic принял бы {}; Python — gatekeeper |
| 6.3 `{"path":"a.txt","evil":"1"}` (unknown field) | OK | REJECT: unknown field (:2127-2129) | нет | — | — | расхождение строгости (Python per-tool строже); до Rust не доходит |
| 6.4 `{"path":123}` (wrong field type) | OK | REJECT: invalid type (:2133-2135) | нет | — | — | Python rejects; Rust B5 (generic object) принял бы форму — Python gatekeeper |
| 6.5 `null` как arguments | OK (valid JSON) | REJECT: not Mapping (:2124) | нет | — | — | Python rejects; Rust B5 обязан отвергнуть null (wrong type) — defense-in-depth |
| 6.6 `"str"` / `[1,2]` / `5` / `true` как arguments | OK (valid JSON) | REJECT: not Mapping (:2124) | нет | — | — | Python rejects; Rust B5 отвергает non-object (wrong type) |
| 6.7 `""` (empty raw string) | не парсится | build() → {} (:2184) → REJECT missing path | нет | — | — | Python: empty→{}→reject; Rust B5: {} разрешён (расхождение строгости, Python фильтрует) |
| 6.8 `{"a":1,"a":2}` (duplicate keys) | REJECT: _reject_duplicate_keys (:2310-2316) → arguments=None → not Mapping | REJECT | нет | — | serde коллапсирует last-wins (если бы дошло) | Python rejects; на parsed seam duplicates невозможны; байзантин-сайдкар: serde last-wins молча (D3) |
| 6.9 `{"x":NaN}` / `Infinity` / `-Infinity` | REJECT: parse_constant (:2319-2320) | — | нет | — | — | оба отвергают (Python parse_constant + serde не парсит NaN) — консистентно |
| 6.10 `{"path":"a.txt"} garbage` (trailing) | REJECT: JSONDecodeError (:2306-2307) → None | REJECT | нет | — | — | отсеяно Python; на parsed seam неприменимо |
| 6.11 leading BOM | REJECT: JSONDecodeError (не utf-8-sig) | — | нет | — | — | отсеяно Python; serde тоже отвергает BOM |
| 6.12 invalid UTF-8 bytes | REJECT: _decode_utf8 strict (:2323-2327) | — | нет | — | — | оба строги к байтам |
| 6.13 `{"path":"\ud800"}` (lone surrogate) | ACCEPTS (str с суррогатом) | ACCEPTS (isinstance str) | сбой эмиссии: .encode("utf-8") → UnicodeEncodeError → invalid_json | никогда | — | D4: разрыв валидация/передача; turn падает нечисто (не model.turn.failed); serde отверг бы байты |
| 6.14 вложенность ×129-999 | OK (<1000 CPython) | OK/reject по схеме | (по схеме) | serde REJECT (depth 128) | — | D5/B5L: полоса Python accepts / Rust rejects (fail-closed, только от байзантина) |
| 6.15 вложенность ×1000+ | RecursionError — НЕ ловится (build() :2181 ловит только GatewayError) | — | крах потока без model.turn.failed | — | — | B5L gap: отсутствие чистого отказа в Python |
| 6.16 `{"z":"1","a":"2"}` (порядок ключей) | OK | OK | да | BTreeMap sorted | порядок (канонизирован) | порядок ключей эквивалентен (sort_keys=True ↔ BTreeMap); escaping `\b`/`\f` расходится (см. D6) |
| 6.17 mixed batch (valid + invalid call) | каждый call отдельно | invalid call → tool_validation_error → model.turn.failed (0 эмиссий, атомарно :850-856) | нет (весь batch) | — | — | Python атомарен; Rust batch atomicity: return Err до мутаций (2884+) |

---

## Реальные parser-differential (не bypass на честном пути)

- **D2 — run_tool_call слабее Python по содержимому input.** validate_tool_call_payload
  (control_plane.rs:3351-3397) требует лишь присутствия ключа `input`; тип/схема не
  проверяются (null/[]/42/вложенный объект проходят в сайдкар). Python-схема такое
  отвергает. Направление Frontend→Rust; защита — digest привязывает grant к точному
  input (подмена после approval невозможна), но схемный контроль делегирован сайдкару.
  **Вне B5** (B5 валидирует model-declared arguments, не run_tool_call input).
- **D3 — duplicate keys: Python отвергает, serde_json коллапсирует (last wins).**
  На честном пути недостижимо (Python — отправитель). Байзантин-сайдкар может послать
  Rust кадр с дубликатами (в т.ч. на уровне envelope) — Rust молча свернёт. Решение
  владельца (duplicates = граница Python) безопасно в B5 (execution заблокирован).
- **D4 — lone surrogates: разрыв валидация/передача.** Python принимает в str, но
  эмиссия гибнет на .encode("utf-8"); turn завершается IPCProtocolError, не чистым
  model.turn.failed. Дефект чистоты отказа, класс B5L.
- **D5 — глубина: serde_json 128 vs CPython ~1000.** Полоса 129-999: Python accepts /
  Rust rejects (fail-closed). ≥1000: RecursionError в Python не ловится. B5L.
- **D9 — утрата исходной строковой формы.** Rust видит канонический reencode объекта;
  сырой JSON модели до Rust не доходит. Для плоской str-only схемы безопасно; носитель —
  класс B (verified historical, канонические байты Python), не A.

- **D6 — escaping `\b`/`\f` в канонизации (минорный, найден @final-parser-differential-reviewer).**
  Python `_json_bytes` (local_model_gateway_ru.py:2336, json.dumps) эмитит короткие формы
  `\b`/`\f`; Rust `escape_json_string` (approval.rs:300-314) обрабатывает явно только
  `\n`/`\r`/`\t`, а `\b`/`\f` идут через `c.is_control()` (:309) → `\u0008`/`\u000c`.
  Следствие: SHA-256 дайджесты расходятся для строк с backspace/form-feed. НЕ B5 parsed-seam
  differential и НЕ bypass (placeholder :2858; canonical_input_digest используется в
  Rust-самосогласованном grant-пути). Требует унификации канонизации до использования
  кросс-граничного дайджеста (B5 GREEN / grant-binding hardening).

## Эквивалентности (нет расхождений)

- NaN/Infinity: тройной слой (parse_constant → allow_nan=False → serde).
- Порядок ключей: sort_keys=True ↔ BTreeMap (порядок совпадает; НО escaping `\b`/`\f` расходится — см. D6).
- UTF-8: оба строги к байтам.
- Trailing garbage / malformed: отсеяны Python до объекта.

## Verdict

Эксплуатируемого parser-differential bypass на честном пути **нет**: Python — строгий
gatekeeper (per-tool schema до эмиссии :822-856), носитель канонизирован, Rust B5
дополнительно fail-closed (placeholder :2858 + tools-guard :2784). Совокупный приём
сегодня: ∅. Зафиксированные риски (D2/D3/D4/D5) — требования к B5 GREEN/B5L и к
следующим фазам, не блокеры B5 RED.
