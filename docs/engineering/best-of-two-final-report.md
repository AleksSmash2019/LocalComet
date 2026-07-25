# Best-of-Two Integration: Final Report

**Branch:** `integration/best-of-two-local-agent`
**Base:** `continue/after-build-week-2026` @ `767a7e9`
**Date:** 2026-07-25
**Product:** LocalComet 6.84.6 (Svelte 5 + Tauri 2 + Rust + Python sidecar)
**Status:** CORE SECURITY COMPLETE; **Windows installer BUILT** (U-002 partial: built, not installed); `npm ci` blocked offline (U-001)

---

## 1. Executive Summary

**Что было.** Канонический LocalComet (v6.84.6) и параллельная реализация Local Agent
Desktop (donor, WP-1.45.4). Задача — перенести полезные, совместимые и доказуемые
улучшения donor в LocalComet, не наследуя его дефекты и не создавая дублирующих authority.

**Что сделано (две фазы).**

- *Фаза 1 (Best-of-Two, WP-A…G):* migration matrix, trust-chain (`.gitattributes` +
  EOL/BOM gate), реестры инвариантов и non-authorities, command-parity gate, модули
  `approval.rs` и `workspace.rs`, аудит-архив.
- *Фаза 2 (Studio Engineering Prompt, Tasks A–J):* подключение approval к продуктовому
  пути (Tauri-команды + Svelte bridge), evidence provenance, UI fake-state аудит,
  honest real-sidecar тесты, workspace IPC-схема + WorkspacePolicy, preflight, build.sh,
  bundle-проверка, smoke + harness.
- *Сборка:* **Windows-бандл собран** — `npx tauri build --bundles nsis` → exit 0
  (`LocalComet.exe` + `LocalComet_6.84.6_x64-setup.exe`); `cargo clippy -D warnings` и
  `cargo fmt --check` зелёные; Svelte собирается offline (vendored `node_modules`).

**Что осталось.** Установка/запуск инсталлятора и smoke установленного приложения
(требует GUI-сессии), `npm ci` (блокирован offline registry — U-001), полный GUI-флоу
approval (ждёт появления fs-tool исполнения в sidecar), CI workflow (отсутствует в
чекауте). См. `docs/unverified-ledger.md`.

**Главный итог:** security-ядро (approval, evidence, UI-integrity, real-sidecar honesty)
реализовано и **доказано инъекциями**. Критические дефекты donor не унаследованы.

---

## 2. Baseline

- LocalComet canonical: v6.84.6, Svelte 5 + Tauri 2 + Rust + Python monorepo
- Donor: Local Agent Desktop WP-1.45.4 (React 18 + Zustand, отдельный Python sidecar)
- Donor-архивы в среде: `lad-wp1454.tar.gz` + WP-брифы (в `audit/donor-briefs/`);
  2 материала отсутствуют (см. `audit/evidence-ledger.md`, DONOR-001)

### LocalComet уже реализует или превосходит donor

| Область | LocalComet | Donor |
|---|---|---|
| Windows Job Object (KILL_ON_JOB_CLOSE, ACTIVE_PROCESS=1) | Implemented | Not implemented |
| Process supervisor + active health probe | Implemented | Partially |
| Bounded stderr reader (4096 ring) | Implemented | Not implemented |
| IPC framing (4 MiB max, length-prefix) | Implemented | Partially |
| Artifact trust (SHA-256, GGUF, catalog guard, reparse rejection) | Implemented | Partially |
| Bounded pipe writes с таймаутом | Implemented | Not implemented |
| Sanitized sidecar env (-I, -B, PYTHONNOUSERSITE) | Implemented | Partially |
| Python discovery (фильтр WindowsApps stubs) | Implemented | Not implemented |
| Control plane bridge (request registry + timeouts) | Implemented | Partially |
| Model request lifecycle с watchdogs | Implemented | Not present |
| Correlated IPC (reply_to, type routing, sequence) | Implemented | Broken (dual transport) |
| TOCTOU (handles открыты при запуске) | Implemented | Not implemented |

---

## 3. Таблица задач A–J (Studio Engineering Prompt)

| Задача | Статус | Результат (верифицировано) |
|---|---|---|
| **A. Approval wiring** | ✅ DONE | `tool_risk_levels.toml` + gate (injection-proven); `approval_commands.rs` (`request_approval`/`execute_approved`/`set_workspace`) + `ApprovalState` + Svelte `approval.ts` → parity **42/42**; A.5 TTL sweep; A.6 grant expiry; A.7 session fix + `wrong_session` test |
| **B. Workspace IPC** | 🟡 PARTIAL | B.1 схема `workspace.set` в IPC-контракте; B.2 `modules/workspace_policy.py` (self-test OK); **B.3 = N/A** (sidecar не исполняет fs-tools) |
| **C. UI audit** | ✅ DONE | `Math.random`=0; 8 таймеров = polling/watchdog (OK); `check_ui_fake_state.py` (injection-proven); INV-UI-001 verified |
| **D. Real-sidecar tests** | ✅ DONE | `real_sidecar_env()` (panic при `REQUIRE`); `check_real_sidecar_tests.py`; D.3 — нет CI файла (DEFERRED) |
| **E. Evidence provenance** | ✅ DONE | `refresh_evidence.py` + `check_evidence_provenance.py` (injection → STALE, exit 1) |
| **F. Preflight** | ✅ DONE | `doctor.py`: npm registry UNREACHABLE (U-001), NSIS missing, WebView2 OK, Rust/Node/Python OK |
| **G. Build** | ✅ DONE | `build.sh` (**.ps1 НЕ создан — AGENTS.md запрещает**) |
| **H. Tauri bundle** | ✅ DONE | конфиг production-grade; icon.ico, NSIS hooks, Python DLLs, approved-artifacts catalog present |
| **I/J. Smoke + harness** | ✅ DONE | `localcomet_test_harness.py` + `scripts/smoke_test.py`: **8 passed, 0 failed** (реальный sidecar); шаги 9–12 = RUST-COVERED/N-A |

---

## 4. Ключевые находки

### 4.1. Desktop sidecar ≠ tool-executor (главная архитектурная находка)

Desktop sidecar (`desktop_sidecar_runtime_ru.py`) — это **model-gateway / knowledge /
session менеджер**. Он **не исполняет файловые инструменты**: `files.*` методы явно
отклоняются как `unsupported_method` (подтверждено smoke step 6 [прогон] и
`tools/test_v6843_sidecar_supervisor.py:441-456`, где `files.read` в списке
`blocked_methods`).

**Следствие:** Studio prompt предполагал tool-executing sidecar (как у donor). Это не
так для LocalComet. Поэтому:
- Approval/workspace enforcement живёт в **Rust** (`approval.rs`, `workspace.rs`,
  `approval_commands.rs`), а не в sidecar.
- Я **не фабриковал** фейковый `tool.call`/`files.patch` путь в sidecar (это нарушило бы
  запрет на «заглушки, выдаваемые за backend»). Шаги smoke 9–12 помечены RUST-COVERED/N-A.
- Workspace IPC round-trip в sidecar (B.3) = **N/A**: нечего охранять (нет fs-операций).

### 4.2. Нет unified AppState

LocalComet управляет отдельными managed states (`DesktopSidecarSupervisor`,
`ControlPlaneBridge`, `ArtifactTrustService`, и т.д.), а не единым `AppState`. Код
Studio prompt (с `state.approval_registry`, `state.control_plane`) адаптирован под
реальную архитектуру: создан `ApprovalState` (registry + workspace), управляемый через
`app.manage(...)`.

### 4.3. Критические дефекты donor НЕ унаследованы

| Дефект donor (WP-1.45.4) | LocalComet |
|---|---|
| Approval bypass (Python — второй consumer) | Rust-only atomic `execute_approved`, нет bypass |
| Workspace только в Rust-state | Rust validates + invalidates tokens; WorkspacePolicy primitive |
| Readiness принимает любой кадр | Требуется correlated health response (`desk-health-{seq}`) |
| Stderr не дренируется | Bounded stderr reader (4096 ring) |
| Два расходящихся IPC-транспорта | Единый `ipc.rs` |
| Unbounded event queue | `MAX_EVENTS_PER_REQUEST` + `MAX_EVENT_TEXT_PER_REQUEST` |

---

## 5. Test Results [прогон]

```
cargo test (2 run)          147 passed, 0 failed, 6 ignored   (approval: 15 tests)
cargo clippy -D warnings    OK (0 warnings; точечные #[allow(dead_code)] с обоснованием)
cargo fmt --check           OK
trust-chain gate            15 files pass byte invariants
cmd-parity gate             42 commands registered and invoked (parity holds)
tool-risk gate              5 tool functions classified (3 mutating, all require approval)
ui-fake-state gate          75 frontend files, 0 violations (Math.random=0)
evidence provenance         4 evidence files fresh and intact
smoke (real sidecar)        8 passed, 0 failed
workspace_policy            self-test OK
npm run build (offline)     OK (Svelte adapter-static, vendored node_modules)
tauri build --bundles nsis  OK (LocalComet.exe + LocalComet_6.84.6_x64-setup.exe)
```

### Injection-таблица (гейты доказаны падением)

| Gate | Что сломали | Что упало | Что защищает |
|---|---|---|---|
| tool_risk_registry | добавлен mutating `truncate_file` без записи | `UNCLASSIFIED_TOOL`, exit 1 | полнота классификации реальных fs-операций |
| ui_fake_state | `Math.random()` + `setTimeout(…,2000)` near state | 2 VIOLATION, exit 1 | UI не генерирует fake state |
| evidence_provenance | изменён `config.py` без refresh | `STALE`, exit 1 | evidence привязан к исходникам |
| real_sidecar_tests | `REQUIRE=1` без окружения | panic, 3 failed | нет silent-skip тестов |
| approval (cargo) | wrong tool/digest/workspace/session, replay, expired | соответствующий `ApprovalError` | atomic scoped authorization |

---

## 6. Invariants → active

Переведены в `active` с реальными `implementation`/`test_ids`/`verification_method`:
- **INV-APPROVAL-001** (guarded tool via atomic Rust authorization)
- **INV-APPROVAL-002** (one-time, scoped, CSPRNG token)
- **INV-EVIDENCE-001** (evidence bound to execution inputs)
- **INV-UI-001** (verified: `check_ui_fake_state.py`)

Остаётся `planned`: **INV-WORKSPACE-001** (IPC round-trip в sidecar — N/A до появления
fs-tool path; Rust workspace authority реализован).

---

## 7. Known Issues

| ID | Проблема | Статус |
|---|---|---|
| U-001 | npm registry UNREACHABLE (offline) — блокирует `npm ci`, не `npm run build` | BLOCKED (infra, не продукт) |
| U-002 | packaged installer | **PARTIAL — собран** (`tauri build` exit 0), не установлен/запущен |
| U-003 | 6 ignored real-sidecar тестов (требуют окружения) | DEFERRED (honest skip после Task D) |
| B-003 | workspace IPC в sidecar | N/A (нет fs-tools) |
| D-003 | CI workflow отсутствует в чекауте | DEFERRED |
| H-001 | doctor.py эвристики (C-linker, NSIS) vs реальная сборка | RESOLVED (cargo/tauri build — authority; NSIS cached by Tauri) |
| H-002 | app.health ≠ advertised capability | RESOLVED (правка теста; smoke 8/8) |
| DONOR-001 | 2 donor-материала отсутствуют | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL (Rust boundary реален; GUI ждёт fs-tools) |

Полный реестр: `docs/unverified-ledger.md`.

---

## 8. Changed / New Files

**Фаза 1 (Best-of-Two):**
```
.gitattributes                                  (hardened)
config.py, approved-artifacts.v1.json           (CRLF→LF fix)
src-tauri/Cargo.toml                            (+getrandom, +subtle)
src-tauri/src/approval.rs, workspace.rs         (NEW)
src-tauri/src/lib.rs                            (+mod approval, +mod workspace)
docs/engineering/best-of-two-migration-matrix.md (NEW)
security/invariants/{invariants,non_authorities}.toml (NEW)
scripts/check_command_parity.py                 (NEW)
tests/test_trust_chain_invariants.py            (NEW)
```

**Фаза 2 (Studio Prompt):**
```
security/invariants/tool_risk_levels.toml        (NEW)
scripts/check_tool_risk_registry.py              (NEW, injection-proven)
scripts/check_ui_fake_state.py                   (NEW, injection-proven)
scripts/refresh_evidence.py                      (NEW)
scripts/check_evidence_provenance.py             (NEW, injection-proven)
scripts/check_real_sidecar_tests.py              (NEW)
scripts/doctor.py                                (NEW)
scripts/build.sh                                 (NEW; .ps1 не создан — AGENTS.md)
scripts/smoke_test.py                            (NEW, 8/8 green)
localcomet_test_harness.py                       (NEW)
modules/workspace_policy.py                      (NEW, self-test OK)
src-tauri/src/approval_commands.rs               (NEW)
src-tauri/src/approval.rs                        (TTL sweep, grant expiry, session fix, +4 tests)
src-tauri/src/supervisor.rs                      (real_sidecar_env honest skip)
src-tauri/src/lib.rs                             (+approval_commands, +ApprovalState, +3 handlers)
src/lib/bridge/approval.ts                       (NEW)
desktop/contracts/localcomet_ipc_v1.schema.json  (+workspace.set messages)
security/invariants/invariants.toml              (APPROVAL/EVIDENCE/UI → active)
docs/unverified-ledger.md                        (NEW)
```

---

## 9. Audit Archive Anchor

Аудит-архив (срез проекта для архитектора):
```
artifacts/audit/localcomet-audit-2026-07-25.tar.gz
  SHA-256: 5001057f6f246494a577926aa4191704abe06db3e05c45ee49571cdd5a35119b
  Size:    14 722 705 bytes (569 files)
  Parts:   .part1 2c37fc8b…  .part2 4c0c573b…  .part3 b438806c… (склейка верифицирована)
Текстовый аудит:
audit/LocalComet-AUDIT-2026-07-25.txt
  SHA-256: 04580f386cef8cbde77fb8b34d9ec4522b838f1d499fb7e6ce0784e069f5d71d
```

Примечание: указанный tar-архив — срез на конец фазы Best-of-Two. Работа фазы Studio
Prompt задокументирована в этом отчёте, в `docs/unverified-ledger.md` и в изменённых
файлах; актуальный tree_digest исходников фиксируется в `artifacts/evidence/*.txt`
через `scripts/refresh_evidence.py` (финальный tree_digest: `d5c4c42ce0d01b65…`,
282 файла).

### Windows build artifacts [прогон]

Собраны через `npx tauri build --bundles nsis` (exit 0):
```
src-tauri/target/release/LocalComet.exe
  size:   14 547 968 bytes (13.87 MB)
  sha256: 2bfdd0c78ba619c128398157fbeb7190deb4ff0c68eb92368ebc59c5ca52ad78

src-tauri/target/release/bundle/nsis/LocalComet_6.84.6_x64-setup.exe
  size:   13 963 772 bytes (13.32 MB)
  sha256: 7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f
```
Инсталлятор собран, но не устанавливался/не запускался (требует GUI-сессии) — см. U-002.

---

## 10. Classification

LocalComet desktop корректно классифицировать как **функциональный локальный desktop-
ассистент с production-grade containment процессов, artifact trust, доказанным
Rust approval/evidence/UI-integrity ядром и собираемым Windows-инсталлятором**.

Основание для additions к классификации (подтверждено доказательствами):
- end-to-end Rust approval authorization (atomic, scoped, one-time) — INV-APPROVAL-001/002 active;
- evidence provenance с source binding — INV-EVIDENCE-001 active;
- UI не генерирует fake backend state — INV-UI-001 verified;
- Windows-бандл собирается (`tauri build --bundles nsis` exit 0, хеши зафиксированы) — U-002 partial.

НЕ подтверждено (не менять классификацию в эту сторону): установка/запуск инсталлятора
и smoke установленного приложения (требует GUI-сессии), полный GUI approval-флоу
(ждёт fs-tool исполнения в sidecar), `npm ci` (блокирован offline registry — U-001).
