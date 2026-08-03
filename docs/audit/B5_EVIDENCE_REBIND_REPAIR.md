# B5 Evidence Rebind Repair

Статус: **B5_EVIDENCE_MODEL_BLOCKED** (целостность восстановлена; checker model не поддерживает historical).
Дата: 2026-07-29. Current tree: ae579fb9739c870b5987907a50313096f2872b79c051fdaa34299746def49632 (283 файла).

## Почему rebinding был некорректен

В цикле B5 GREEN Evidence Closure 46 исторических evidence-файлов были перепривязаны к текущему
дереву ae579fb9 путём правки строки `# tree_digest:` (без реального повторного запуска команд).
Это **подмена provenance**: команда, выполненная на старом дереве (8a0d1d80 / cc18487b), стала
заявляться как выполненная на новом (ae579fb9). Gate `check_evidence_provenance.py` криптографически
корректен, но доверяет полю `tree_digest` как авторскому; перепривязка сфабриковала «свежесть»
правкой поля, которое gate проверяет, а не повторным прогоном. Body (stdout/stderr) при этом не
менялся — сфабрикована только tree-привязка.

## Что восстановлено

46 ложно перепривязанных файлов возвращены к исходным tree digest:
- **33 файла** -> оригинальное дерево `8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88`
  (B4A closure / baseline): b4a_closure_* (12), b5_ratify_* (10), b5_red_baseline_* (9),
  b5_red_adversarial_preflight{,_fmt} (2).
- **13 файлов** -> оригинальное дерево `cc18487be7113bd5e12ead31aff35f923bf34a70b77892bf135b99d9971cb498`
  (B5 RED): b5_green_red_* (5), b5_green_preflight_fmt (1), b5_red_adversarial_{focused,regressions,
  workspace,aux_gates,diff,contract,agents} (7).

Для каждого файла:
- `# tree_digest:` возвращён к исходному (извлечён из `# closure_rebind: original tree <hex64>`);
- ложная строка `# closure_rebind:` удалена;
- добавлена безопасная metadata-пометка `# evidence_status: HISTORICAL` (формат поддерживает
  произвольные `# key: value`; checker игнорирует лишние поля);
- **body (stdout/stderr), command, exit_code, timestamp, body_sha256 НЕ изменены** (body_sha256
  валиден у всех 46 — подтверждено аудитом, 0 BODY_MISMATCH).

Исходные digest достоверно извлекаемы и перекрёстно согласованы со старыми манифестами
(B4A_CLOSURE_MANIFEST 12/12, B5_RED_ADVERSARIAL_MANIFEST 18/18 — корректные исторические хеши байтов).

## Какие файлы подтверждают ae579fb9 (CURRENT_VALID, 29)

Реально выполнены на текущем дереве ae579fb9 (без rebind, tree_digest == current, body_sha256 валиден):
- 4 канонических: cargo_test.txt, trust_chain.txt, cmd_parity.txt, tool_risk_registry.txt
  (регенерированы refresh_evidence.py на ae579fb9);
- 10 b5_closure_*.txt (fmt, b5, b4a, b4c, b3m, b2, workspace, clippy, parity, diffcheck);
- 5 b5_green_*.txt (focused, regressions, workspace, aux_gates, diff);
- 10 b5_integrity_*.txt (свежие прогоны integrity-цикла: B5 18/0, B4A 10/0, B4C 6/0, B3M 10/0,
  B2 11/0, Workspace 232/0/6, fmt/clippy/parity/diff exit 0).

## Какие файлы являются историческими (HISTORICAL, 46)

46 файлов выше (33 + 13) — честные исторические снапшоты своих деревьев (8a0d1d80 / cc18487b).
Они STALE относительно текущего дерева ae579fb9 **по определению** (историческое evidence не может
быть fresh относительно нового дерева). Помечены `# evidence_status: HISTORICAL`.

## Манифесты (разделены)

- artifacts/evidence/B5_CURRENT_EVIDENCE_MANIFEST.sha256 — 29 файлов, tree ae579fb9 (текущие хеши).
- artifacts/evidence/B5_HISTORICAL_EVIDENCE_MANIFEST.sha256 — 46 файлов, MIXED original trees
  (8a0d1d80 x33 / cc18487b x13), хеши восстановленных оригинальных байтов, per-file аннотация дерева.
- B5_GREEN_CLOSURE_MANIFEST.sha256 (предыдущий) фиксирует перепривязанное состояние и более не
  является корректным долгосрочным артефактом (хеши 46 файлов изменились после восстановления).

## Были ли изменены body или timestamps

НЕТ. При восстановлении изменён только заголовок (tree_digest возвращён, closure_rebind удалён,
добавлен evidence_status). Body, command, exit_code, timestamp, body_sha256 каждого файла сохранены
байт-в-байт. 0 BODY_MISMATCH.

## Текущий честный provenance verdict

`python scripts/check_evidence_provenance.py`:
- exit 1;
- 46 STALE (исторические файлы, оригинальные digest != current) — **честно**;
- 0 BODY_MISMATCH;
- 0 MISSING_FIELD;
- 75 файлов всего (29 current fresh + 46 historical STALE).

## Почему это BLOCKED (checker model)

`check_evidence_provenance.py` требует `tree_digest == current` для ВСЕХ `*.txt` в artifacts/evidence
безусловно (строка 61). Категории HISTORICAL не существует: исторический файл с оригинальным digest
всегда STALE. Честное сохранение исторического evidence (оригинальные digest) несовместимо с зелёным
вердиктом checker'а. Изменение checker'а требует отдельного решения владельца (это изменение логики
гейта, может ослабить инвариант «stale evidence is worse than missing evidence»).

## Предложение по исправлению модели checker (код НЕ менялся)

Варианты (на решение владельца):
1. **Поле evidence_status.** Добавить в формат опциональное поле `# evidence_status: CURRENT|HISTORICAL`.
   Checker: для HISTORICAL пропускать проверку tree_digest на свежесть, но проверять body_sha256
   (целостность) и наличие/валидность original tree_digest. CURRENT проверяется как сейчас.
2. **Отдельный каталог.** Перенести историческое evidence в `artifacts/evidence/historical/`;
   checker проверяет только `artifacts/evidence/*.txt` (current), исторические хешируются отдельным
   манифестом (B5_HISTORICAL_EVIDENCE_MANIFEST) без требования свежести.
3. **Whitelist по манифесту.** Checker читает B5_HISTORICAL_EVIDENCE_MANIFEST.sha256 и исключает
   перечисленные там файлы из проверки свежести (но проверяет body_sha256 == манифестному хешу).

Любой вариант сохраняет инвариант целостности (body_sha256) и устраняет ложную дилемму
«перепривязать (подмена) vs STALE (блок)». До решения владельца checker не менялся; текущий честный
вердикт — 46 STALE / 0 BODY_MISMATCH, exit 1.

## Production / тесты

НЕ изменялись. control_plane.rs numstat 1486/35 (deletions 35 неизменны). B5 validation (2857-2865)
и placeholder (2867-2870) на месте. Tools disabled (:302). Tracker EA646B0A... (384 строки) не изменён.
Python/frontend/schemas/registries не изменены.

## Следующий шаг

B5_EVIDENCE_MODEL_BLOCKED, NEXT_ALLOWED=NONE (до решения владельца по модели checker).
После решения владельца (принятие одного из вариантов модели) возможен пересчёт honest provenance
и переход к B5L_RED. B5L/B6 не начинались.
