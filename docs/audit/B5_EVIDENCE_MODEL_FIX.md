# B5 Evidence Model Fix

Статус: **B5_EVIDENCE_MODEL_FIXED**. Дата: 2026-07-29. NEXT_ALLOWED=B5L_RED.
Решение владельца: исторические evidence хранятся отдельно от current evidence.

## Current tree

ae579fb9739c870b5987907a50313096f2872b79c051fdaa34299746def49632 ->
**5255984dac8b2014c22b62b0e5a71f1f2923c3481f7ef86a02f08446f88d89f1** (284 source files).

Дерево изменилось с ae579fb9 на 5255984dac8b2014, потому что модификация checker-скриптов
(scripts/check_evidence_provenance.py + новый scripts/check_historical_evidence.py) находится
в scripts/, который входит в refresh_evidence.SOURCE_GLOBS. Это легитимное следствие: current
evidence перегенерирован на новом дереве (выходы гейтов идентичны — checker-скрипты не влияют
на cargo test/clippy).

## Что сделано

1. **46 HISTORICAL-файлов перемещены** в artifacts/evidence/historical/ (mv; байты/body/digest/
   timestamp сохранены). Исходные tree_digest сохранены: 33 файла -> 8a0d1d80... (B4A closure/
   baseline), 13 файлов -> cc18487b... (B5 RED). Пометка # evidence_status: HISTORICAL сохранена.
   B5_HISTORICAL_EVIDENCE_MANIFEST.sha256 перемещён в historical/.
2. **29+ current-файлов остались** в artifacts/evidence/ (top-level). После перегенерации на новом
   дереве current evidence = 39 файлов (29 исходных + 10 свежих b5_modelfix-гейтов этого цикла),
   все на tree 5255984dac8b2014.
3. **scripts/check_evidence_provenance.py модифицирован** (минимально, без whitelist):
   - docstring описывает модель current/historical;
   - glob ограничен top-level (защитный фильтр p.parent == EVIDENCE_DIR; glob("*.txt") и так не
     рекурсивен, historical/ не посещается);
   - REQUIRED_FIELDS и логика body_sha256 НЕ изменены; индивидуальных whitelist-исключений нет.
   - current evidence обязаны совпадать с текущим tree digest (STALE иначе).
4. **scripts/check_historical_evidence.py создан** (отдельная проверка historical):
   - glob historical/*.txt (пин 46);
   - REQUIRED_FIELDS + evidence_status == HISTORICAL;
   - body_sha256 == sha256(body) (целостность, иначе BODY_MISMATCH);
   - tree_digest обязан быть ОРИГИНАЛЬНЫМ (8a0d1d80/cc18487b) и НЕ текущим (иначе WRONG_TREE);
   - manifest integrity: historical/B5_HISTORICAL_EVIDENCE_MANIFEST.sha256 (set-равенство +
     whole-file SHA-256, 0 расхождений).
   - НЕ требует tree_digest == current (исторические имеют оригинальные).
5. **Current evidence перегенерирован** на tree 5255984dac8b2014 (refresh_evidence.py для 4
   канонических + свежие прогоны гейтов для b5_* файлов). B5_CURRENT_EVIDENCE_MANIFEST.sha256
   регенерирован (39 файлов, 5255984dac8b2014).

## Результаты проверок

Current evidence (check_evidence_provenance.py):
- exit 0; **39 valid, 0 STALE, 0 BODY_MISMATCH** (tree 5255984dac8b2014).

Historical evidence (check_historical_evidence.py):
- exit 0; **46 valid, 0 BODY_MISMATCH, original digests preserved**.

Гейты (свежие, tree 5255984dac8b2014):
- B5: 18 passed / 0 failed.
- Workspace: 232 passed / 0 failed / 6 ignored.
- B4A 10/0; B4C 6/0; B3M 10/0; B2 11/0.
- cargo clippy --workspace --all-targets -- -D warnings: exit 0.
- cargo fmt --check: exit 0.
- git diff --check: exit 0.

## Манифесты

- artifacts/evidence/B5_CURRENT_EVIDENCE_MANIFEST.sha256 — 39 файлов, tree 5255984dac8b2014.
- artifacts/evidence/historical/B5_HISTORICAL_EVIDENCE_MANIFEST.sha256 — 46 файлов, MIXED
  original trees (8a0d1d80 x33 / cc18487b x13), хеши восстановленных оригинальных байтов.
- Старые манифесты (B4A_CLOSURE, B5_RED_ADVERSARIAL) содержат корректные исторические хеши;
  B5_GREEN_CLOSURE/B5_GREEN_MANIFEST superseded (следы отменённой перепривязки).

## Гарантии (чего НЕ делали)

- НЕ удаляли историю (46 файлов сохранены в historical/).
- НЕ заменяли старые digest текущим (оригинальные 8a0d1d80/cc18487b сохранены).
- НЕ переписывали stdout/timestamps/body исторических файлов (body_sha256 валиден у всех 46).
- НЕ добавляли индивидуальных whitelist-исключений в checker.
- НЕ меняли production Rust/Python/frontend/tests (control_plane.rs numstat 1486/35, deletions 35
  неизменны; B5 validation 2857-2865 + placeholder 2867-2870 на месте; tools disabled :302;
  tracker EA646B0A..., 384 строки).
- НЕ начинали B5L/B6.

## Production / тесты

НЕ изменялись. control_plane.rs numstat 1486/35. B5 validation (arguments required + is_object,
2857-2865) и strict placeholder (2867-2870) на месте. Tools disabled (trusted() tools=Vec::new():302).
Tracker EA646B0A2C73F7AE714094A6DD3264BC03BDB8BBA6733D038352E8DF3DB1D3D4 (384 строки) не изменён.

## Следующий шаг

B5L_RED (arguments resource limits: размер/глубина/количество ключей/total nodes) — обязателен
до снятия placeholder и включения tools. B6/provenance/execution binding/TOCTOU fix — не начинались.

Рекомендация: добавить `python scripts/check_historical_evidence.py` в список гейтов AGENTS.md
(требует отдельного решения владельца, AGENTS.md защищён).
