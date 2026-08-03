# B5 Contract Conflict — tool_calls[*].arguments

Статус микроцикла: **B5_CONTRACT_BLOCKED**
Дата: 2026-07-28
Оркестратор: opencode (qwen3.8-max-preview).
Tree digest: 8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88 (283 файла)
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364
Baseline (свежий): B4A 10/0, B4C 6/0, B3M 10/0, B2 11/0, Workspace 214/0/6, fmt/clippy/parity/diff/provenance exit 0.

Этот документ фиксирует варианты решения и НЕ выбирает ни один из них.
Выбор — за владельцем проекта. RED-тесты B5 не пишутся до разрешения конфликта,
поскольку exact error assertions (assert_eq! по коду и сообщению) невозможны без
утверждённого контракта.

---

## 1. Суть конфликта

Production Rust не валидирует `tool_calls[*].arguments` (control_plane.rs:2813-2857
читает только `name` :2814 и `id` :2830-2856; затем strict placeholder :2858-2861
"tool event semantic validation is not yet implemented"). B5 должен добавить валидацию
arguments в seam между :2856 и :2857 (внутри цикла `for call in tool_calls`).

Чтобы написать RED-тесты с точными assertions, нужен утверждённый контракт carrier
(внешний JSON-тип arguments) и точные коды/сообщения ошибок. Источники авторитета
расходятся по нескольким вопросам. Главный расхождение — carrier type.

---

## 2. Contract decision table

| # | Вопрос | Rust (code/tests) | Python | Schema | ADR/Tests | Конфликт? |
|---|--------|-------------------|--------|--------|-----------|-----------|
| 1 | arguments required/optional | не проверяется (не читается) | де-факто required: build() всегда даёт значение (empty→{}) :2184 | OpenAI `required` — про поля внутри, не про arguments | фикстуры всегда содержат arguments | частично: на Rust-уровне не определено |
| 2 | **Внешний тип (carrier)** | **STRING** (фикстуры :5833, 5883; helper :5736 args:&str) | **PARSED OBJECT** (build :2180-2185; эмиссия :877→:1026, :869) | IPC schema МОЛЧИТ (0 совпадений tool_calls/arguments) | ADR-015:82 string на проводе; :84 parsed object в событии | **ДА — ГЛАВНЫЙ** |
| 3 | если string: парсинг/top-level | n/a (зависит от #2) | string парсится _loads_json :2180; top-level должен быть Mapping :2124 | — | — | зависит от #2 |
| 4 | допустим ли {} | не проверяется | структурно да (build порождает {}), семантически НЕТ для всех 5 tools (missing required path) :2130-2132 | required:[path] / [path,content] :2112 | test_adr015:143 files.read {} → invalid_payload | нюанс generic vs per-tool |
| 5 | null/array/bool/number/string scalar | не проверяется | НЕТ (не Mapping → "tool arguments must be an object") :2124-2125 | — | — | нет (Python однозначен); Rust должен решить |
| 6 | duplicate JSON keys | serde_json: last wins (молча) | ОТВЕРГАЮТСЯ (_reject_duplicate_keys :2310-2316) | — | — | **ДА — parser differential** |
| 7 | неизвестные поля | не проверяется | ОТВЕРГАЮТСЯ (unknown field :2127-2129) | additionalProperties НЕ задан (не запрещает) :2098-2117 | — | **ДА — schema↔Python divergence** |
| 8 | B5 = только generic object shape? | не определено | per-tool schema (required/properties/type) :2120-2135 | per-tool :2098 | ADR-015:150-154 Rust defense-in-depth | **ДА — scope не определён** |
| 9 | per-tool schema = B5 или позже? | не определено | уже в Python | — | ADR-015 не разделяет явно B5/B6 | **ДА — не определено** |
| 10 | exact error code | protocol_mismatch (конвенция tool-events :2785-2858) | invalid_payload (validate_tool_call :2122-2135) | — | — | **ДА — code convention** |
| 11 | exact error messages | не определены (B5 нет) | "tool arguments must be an object" и др. :2125-2135 | — | — | зависит от #10; зеркалировать Python? |
| 12 | validation order | id(B4A) → [B5 seam] → placeholder :2856→2858 | name+schema на терминале :824-829 | — | — | нет (seam установлена) |
| 13 | batch atomicity | return Err до мутаций :2858 < :2884 (CONFIRMED) | invalid → model.turn.failed, 0 эмиссий (атомарно) :850-856 | — | — | нет (оба атомарны) |
| 14 | размер/глубина | MAX_MODEL_EVENT_TEXT_PER_REQUEST :2878 (текст событий); нет arguments-specific | нет явного лимита глубины (gap); _read_bounded payload_too_large :2295; MAX_TOOL_CALLS_PER_TURN=10 :39 | — | — | частично: лимиты не согласованы |

---

## 3. Конфликт A — carrier type (главный, блокирующий)

Два взаимоисключающих варианта:

### Вариант A1: carrier = PARSED OBJECT
Основания:
- Python эмитит parsed object: ToolCallAccumulator.build() :2180-2185 парсит строку
  через _loads_json и кладёт dict; терминал model.turn.tool_calls :877→:1026 и
  model.tool.request :869 несут dict.
- Python-тесты фиксируют object: test_adr015_tool_parsing.py:88, 426, 649-650, 839
  (`calls[0]["arguments"] == {"path": "a.txt"}`).
- ADR-015:84 — «input = распарсенные arguments» (в событии object).
- validate_tool_call :2124 требует Mapping (object).

Следствия выбора A1:
- Rust B5 валидирует «arguments должен быть Value::Object»; null/bool/number/string/array → reject.
- String-specific тесты (malformed JSON, whitespace-only, trailing content, duplicate keys
  как строка) НЕ применимы на Rust-seam (Rust получает уже распарсенный serde_json Value;
  malformed JSON невозможен, duplicate keys коллапсируются serde_json last-wins).
- **Существующие Rust-фикстуры B4A/B4C/B3M/B2 (arguments = string, :5833+) станут
  НЕВАЛИДНЫ** для B5 GREEN: они будут отвергнуты как «не object». Потребуется решение:
  обновить фикстуры (модификация существующих тестов) или принять оба carrier.

### Вариант A2: carrier = JSON STRING (с парсингом в object)
Основания:
- Существующие Rust-фикстуры используют string: structured_tool_event :5723-5742 (args:&str),
  фикстуры :5833, 5883, 5897, 5917, 5936, 5955, 6001-6002, 6021-6022, 6045-6046, 6077, 6082.
- ADR-015:82 — «arguments — JSON-строка, накапливается по кускам» (wire-формат OpenAI).
- Тестовые требования задания (malformed JSON / whitespace-only / trailing content /
  parsed-X) подразумевают string carrier.

Следствия выбора A2:
- Rust B5 парсит string → требует top-level object; malformed/whitespace/trailing/scalar/array → reject.
- **Production-события (Python эмитит object) будут ОТВЕРГНУТЫ** Rust B5 как «не string»,
  т.е. B5 GREEN сломает production-поток (валидные tool calls от sidecar не пройдут).
  Потребуется: либо Python ре-сериализует arguments обратно в string перед эмиссией
  (модификация Python), либо Rust принимает оба carrier.

### Вариант A3: dual carrier (принять и object, и string→parse)
Основания: совместить A1 и A2, defense-in-depth.
Следствия: усложнение; нужно определить, считается ли string-carrier легитимным на
Rust-seam; дублирует парсинг (Python уже парсит); неоднозначность duplicate keys
(serde_json last-wins при парсинге string vs Python reject).

### Дополнительный фактор: carrier = None
Python build() :2181-2182 устанавливает arguments=None при ошибке парсинга (GatewayError).
Хотя validate_tool_call затем отвергает None до эмиссии (invalid → model.turn.failed),
это показывает, что «arguments» в сыром виде может быть null. Любое решение B5 должно
явно обработать null (см. вопрос #5).

Почему оркестратор не выбирает: выбор A1 ломает существующие Rust-тесты; выбор A2 ломает
production-поток; выбор A3 вносит неоднозначность. Каждый вариант имеет авторитетное
обоснование и реальные последствия. Требуется решение владельца.

---

## 4. Конфликт B — error code

- Rust tool-event ошибки используют `protocol_mismatch` (control_plane.rs:2785-2858).
- Python arguments-ошибки используют `invalid_payload` (validate_tool_call :2122-2135).

Варианты:
- B-1: B5 в Rust использует `protocol_mismatch` (консистентно с соседними B4A/B3M/B4C guard'ами).
- B-2: B5 в Rust использует `invalid_payload` (зеркалит Python; согласуется с семантикой «payload невалиден»).
- B-3: разные коды для разных подслучаев (например missing/type → protocol_mismatch, schema → invalid_payload).

Оркестратор не выбирает.

---

## 5. Конфликт C — duplicate JSON keys (parser differential)

- Python: отвергает (_reject_duplicate_keys :2310-2316, "duplicate JSON key rejected").
- Rust serde_json: при парсинге строки duplicate keys коллапсируются (last wins), молча.

Следствие: если carrier = string и Rust парсит сам (A2/A3), Rust пропустит duplicate keys,
которые Python отверг бы → расхождение. Для закрытия нужен кастомный парсер (object_pairs_hook
аналог) или запрет string carrier (A1). Зависит от Конфликта A.

---

## 6. Конфликт D — scope: generic shape vs per-tool schema

- Python выполняет per-tool schema validation (required/properties/type) :2120-2135.
- ADR-015:150-154 — Rust defense-in-depth (схема + имя ∈ реестра), но не разделяет явно,
  что входит в B5, а что в следующий этап (B6 consistency / per-tool schema).

Варианты:
- D-1: B5 = только generic object shape (arguments должен быть object; без per-tool полей).
  Per-tool schema (required/properties/unknown fields) — отдельный этап.
- D-2: B5 = generic shape + per-tool schema (зеркало Python validate_tool_call).
- D-3: B5 = generic shape; unknown fields/required — B6.

Тестовые требования задания (пункты 26 unknown properties, 27 nested invalid type) относятся
к per-tool schema; их принадлежность B5 зависит от выбора D. Оркестратор не выбирает.

---

## 7. Сопутствующие наблюдения (не блокирующие, но требуют решения при GREEN)

- Нет явного лимита глубины вложенности ни в Python (gap, @python-parser-auditor), ни в Rust
  (serde_json default). Resource-exhaustion через глубокую вложенность не закрыт ни одним слоем.
- Lone/invalid surrogates: Python json.loads принимает lone surrogate в str; serde_json отвергает
  при парсинге → расхождение (carrier-зависимо).
- IPC schema (desktop/contracts/localcomet_ipc_v1.schema.json) НЕ задаёт tool_calls/arguments
  (payload = free-form object maxProperties:256, :64-67) → тип arguments не ограничен контрактом IPC.
- run_tool_call (approval_commands.rs:151-204) — отдельная граница исполнения (tool/input/token
  от фронтенда), НЕ гейтится B5 seam в control_plane.rs. B5 валидирует model-declared calls
  перед (пока несуществующим) пробросом в UI; реальное исполнение — отдельный авторизационный контур.
- Эксплуатационная оценка @security-red-team-lead: сегодня gap LATENT (двойная защита:
  empty tools :2784 + placeholder :2858), не активная уязвимость; станет активной при снятии
  placeholder в B5 GREEN без корректного контракта carrier.

---

## 8. Что нужно от владельца для разблокировки

1. Утвердить carrier (A1 object / A2 string / A3 dual) — главный вопрос.
2. Утвердить error code (B-1/B-2/B-3).
3. Утвердить scope B5 (D-1 generic / D-2 generic+schema / D-3 generic, schema→B6).
4. Решить политику duplicate keys и surrogates (следствие carrier).
5. Решить, обновлять ли существующие Rust-фикстуры (string) при выборе A1.
6. (Опционально) установить лимиты глубины/размера arguments.

До этих решений B5 RED тесты с exact assertions написать невозможно без риска
ложной приёмки или фиксации неверного контракта.

---

## 9. Evidence

- Baseline gates: artifacts/evidence/b5_red_baseline_*.txt (10 файлов, все exit 0).
- Agent reports: pipeline/loop-status.md (секция B5), artifacts/evidence/b5_red_adversarial_agents.txt.
- Contract analysis: artifacts/evidence/b5_red_adversarial_contract.txt.

Независимые agent verdicts (wave 1, 9/9): @wire-contract-archaeologist (конфликт carrier),
@rust-control-plane-auditor (seam 2856/2857), @python-parser-auditor (object/Mapping, no depth limit),
@schema-authority-auditor (IPC schema не авторитет), @adversarial-input-designer (17 классов, 8 STR-only),
@precedence-attacker (matrix), @atomicity-attacker (CONFIRMED), @baseline-gate-runner (ALL_GREEN),
@security-red-team-lead (latent gap, carrier differential, None carrier).
