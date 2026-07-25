# LocalComet — Аудит-гайд для архитектора

**Дата сборки архива:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent`
**Базовый commit:** `767a7e9df9a2b8951523e410b60fcabdc9c9cf93` (ветка `continue/after-build-week-2026`)
**Версия продукта:** 6.84.6
**Платформа сборки:** Windows 11 (10.0.26200), x86-64

Этот архив — самодостаточный срез канонического проекта LocalComet для архитектурного
аудита. Он содержит исходники, security-инварианты, доказательства (evidence),
инженерные отчёты и контекст донора (параллельная реализация Local Agent Desktop).

---

## 1. Что такое LocalComet

Локальный офлайн desktop-ассистент:

```
Svelte 5 (frontend)
   │  invoke()
   ▼
Tauri 2 + Rust (control plane, supervisor, artifact trust, approval)
   │  IPC (length-prefixed JSON по stdin/stdout)
   ▼
Python sidecar (core/, modules/, agents/) — LLM-маршрутизация, планирование, исполнение
```

- Консольный вход: `python -m next.app_v5`
- Desktop: `desktop/localcomet-desktop/` (Tauri 2 + Rust crate `localcomet-desktop`)
- Backend-логика: `core/`, `modules/`, `agents/`
- Персистентное состояние: `memory/state.json`
- Конфигурация LLM: `config.py` (LM Studio локально / OpenAI API)

**Workflow патчинга:** `request.md → response.json → validate → apply → after patch`.

---

## 2. Текущая честная классификация

> Функциональный локальный desktop-ассистент с production-grade containment процессов
> и artifact trust. Security-инфраструктура approval/workspace добавлена, но ещё не
> подключена к продуктовому пути end-to-end.

Это НЕ production-ready в смысле «можно отдавать внешним пользователям»: GUI, packaged
binary и Windows-сборка не верифицированы в этой среде (нет сети и WebView2).

---

## 3. Контекст: интеграция «Best of Two»

Параллельная реализация **Local Agent Desktop** (React 18 + Zustand, отдельный Python
sidecar, v0.1.0) прошла цикл независимых проверок WP-1.45.2 → WP-1.45.4. Её вердикты
и инженерные брифы лежат в `audit/donor-briefs/`.

**Ключевой вывод интеграции:** LocalComet desktop уже реализует или превосходит
большинство улучшений донора. Критические дефекты донора (обход approval, workspace
только в Rust-state, readiness «принимает любой кадр», не дренируется stderr, два
расходящихся IPC-транспорта) **не унаследованы**, потому что в LocalComet этих путей нет.

Полная карта переноса: `docs/engineering/best-of-two-migration-matrix.md`.
Итоговый отчёт: `docs/engineering/best-of-two-final-report.md`.

---

## 4. Что читать первым (приоритет для архитектора)

### 4.1. Security-critical модули Rust (проверять в первую очередь)

| Файл | Что делает | На что смотреть |
|---|---|---|
| `desktop/localcomet-desktop/src-tauri/src/approval.rs` | **НОВЫЙ.** Scoped one-time approval-токены (CSPRNG 256 бит, constant-time, atomic `execute_approved`) | ещё НЕ подключён к Tauri-командам — нет продуктового пути |
| `desktop/localcomet-desktop/src-tauri/src/workspace.rs` | **НОВЫЙ.** Валидация workspace, reparse-защита, инвалидация токенов при смене | ещё НЕ отправляет `workspace.set` в sidecar |
| `desktop/localcomet-desktop/src-tauri/src/windows_job.rs` | Windows Job Object: `KILL_ON_JOB_CLOSE` + `ACTIVE_PROCESS_LIMIT=1`, `CREATE_SUSPENDED`→assign→resume | non-Windows — заглушка, возвращающая ошибку (осознанно) |
| `desktop/localcomet-desktop/src-tauri/src/supervisor.rs` | Запуск sidecar, active health probe (`desk-health-{seq}`), bounded stderr reader (4096), shutdown | readiness требует `saw_python_hello && saw_health_ok` |
| `desktop/localcomet-desktop/src-tauri/src/ipc.rs` | Length-prefixed framing, max 4 МиБ, отклонение zero-length/oversized | единый транспорт (нет дубля) |
| `desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs` | Embedded catalog с pinned SHA-256, GGUF magic, reparse rejection, TOCTOU (handles держатся открытыми при запуске), streaming SHA-256 | catalog canonical (LF, no BOM, single final LF) |
| `desktop/localcomet-desktop/src-tauri/src/control_plane.rs` | Request registry, correlation по `reply_to`, type routing (event/response/error), sequence validation, bounded events | ~5000 строк, ядро моста |

### 4.2. Инварианты и non-authorities

- `security/invariants/invariants.toml` — 12 инвариантов с привязкой к тестам
  (`INV-PROCESS-001`, `INV-READINESS-001`, `INV-IPC-001/002`, `INV-CATALOG-001/002`,
  `INV-MODEL-001`, `INV-UI-001`, `INV-APPROVAL-001/002`, `INV-WORKSPACE-001`,
  `INV-EVIDENCE-001`).
- `security/invariants/non_authorities.toml` — 16 записей «что НЕ является authority»
  (LLM output, filename, repo name, HF metadata, app-data, frontend state, open port,
  process name, loopback без binding, previous run, presence of file, sidecar self-report
  без probe, redirect, markdown, log, cache).

### 4.3. Гейты и тесты

- `tests/test_trust_chain_invariants.py` — EOL/BOM/final-LF инвариант (14 файлов).
- `scripts/check_command_parity.py` — Svelte `invoke()` == Tauri `generate_handler!` (39/39).
- Rust unit-тесты: `cargo test` (143 passed, 6 ignored — real-sidecar тесты).

---

## 5. Результаты проверок (на момент сборки)

```
cargo test                          143 passed, 0 failed, 6 ignored
python tests/test_trust_chain_invariants.py   OK: 14 files pass byte invariants
python scripts/check_command_parity.py        OK: 39 commands (parity holds)
```

6 ignored Rust-тестов — интеграционные real-sidecar тесты, требующие
`LOCALCOMET_TEST_PROJECT_ROOT` и `LOCALCOMET_TEST_PYTHON`. Это осознанный skip, не провал.

---

## 6. Остаточные риски (открытые пункты для аудита)

1. **Approval не подключён к продуктовому пути.** `approval.rs` существует и покрыт
   тестами, но ни одна `#[tauri::command]` его не вызывает. Требуется продуктовое решение,
   какие инструменты GUARDED.
2. **Workspace не передаётся в sidecar.** Валидация и инвалидация токенов работают,
   но `workspace.set.request/response` в Python sidecar ещё не реализован.
3. **UI fake-state аудит не проведён.** Svelte-сторы не проверены на `Math.random()`
   в путях состояния и таймерный прогресс (INV-UI-001).
4. **Packaged binary не tested.** Нужны сеть + WebView2 + NSIS.
5. **6 ignored тестов** — real-sidecar интеграция (требуют окружения).
6. **Отсутствуют donor-материалы:** `LocalComet_Detailed_Static_Audit_2026-07-25.txt`,
   `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` (см. `audit/evidence-ledger.md`).

---

## 7. Как верифицировать (команды)

```powershell
# Rust-тесты (в desktop/localcomet-desktop/src-tauri)
cargo test
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings

# Python-гейты (в корне)
python tests/test_trust_chain_invariants.py
python scripts/check_command_parity.py

# Консольный агент
python -m next.app_v5
```

---

## 8. Карта архива

```
audit/
  AUDIT_GUIDE.md                     ← этот файл
  evidence-ledger.md                 ← что присутствует/отсутствует
  manifest.sha256                    ← SHA-256 ключевых файлов
  donor-briefs/                      ← контекст донора (WP-1.45.2/3/4 + master prompt)
docs/engineering/
  best-of-two-migration-matrix.md    ← карта переноса donor→LocalComet
  best-of-two-final-report.md        ← итоговый отчёт интеграции
security/invariants/
  invariants.toml                    ← реестр инвариантов
  non_authorities.toml               ← реестр non-authorities
artifacts/evidence/
  best-of-two-evidence.json          ← machine-readable evidence прогонов
desktop/localcomet-desktop/src-tauri/src/
  approval.rs  workspace.rs          ← НОВЫЕ security-модули
  windows_job.rs  supervisor.rs  ipc.rs  artifact_trust.rs  control_plane.rs  lib.rs
tests/test_trust_chain_invariants.py
scripts/check_command_parity.py
.gitattributes                       ← усилен для trust-chain файлов
```

---

## 9. Правила проекта (из AGENTS.md)

- Не удалять файлы. Не создавать `.exe`/`.bat`/`.ps1`.
- Малые безопасные изменения; целевые правки вместо переписывания.
- `py_compile` для изменённых Python-файлов; `stability test` после важных изменений.
- Не модифицировать `Projects/BrowserProfile`.
- Сохранять workflow `request.md → response.json → validate → apply → after patch`.
- Не удалять существующие кнопки/функции из UI.
