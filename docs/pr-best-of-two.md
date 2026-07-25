# PR: Best-of-Two Wiring Sprint v6.84.6

**Ветка:** `integration/best-of-two-local-agent` → `continue/after-build-week-2026`
**Дата:** 2026-07-25
**Base:** `continue/after-build-week-2026` @ `767a7e9` (прямой предок HEAD — мерж fast-forward, конфликтов нет)

> ℹ️ **Целевая ветка:** `continue/after-build-week-2026`. Ветка `main` в репозитории
> не существует (ни локально, ни в origin); существующие ветки — `build-week-2026` и
> `continue/after-build-week-2026`. Мерж в целевую ветку = fast-forward, конфликтов нет.

---

## Summary

Ветка подключает security-ядро, перенесённое из параллельной реализации Local Agent
Desktop, к продуктовому пути LocalComet: approval-токены (CSPRNG, scoped, one-time)
теперь выдаются и атомарно потребляются через Tauri-команды, добавлены evidence
provenance, UI fake-state и tool-risk гейты, honest real-sidecar тесты и in-process
smoke. Ключевое архитектурное уточнение: desktop sidecar **не исполняет file-tools**
(`files.*` = `unsupported_method`), поэтому approval/workspace enforcement живёт в Rust,
а не в sidecar. Все гейты зелёные, Windows-инсталлятор собирается.

---

## Changes

| Файл | Тип | Описание |
|---|---|---|
| `src-tauri/src/approval.rs` | NEW | CSPRNG 256-bit токены, constant-time scope validation, atomic `execute_approved`, TTL sweep, grant expiry (15 тестов) |
| `src-tauri/src/approval_commands.rs` | NEW | Tauri-команды `request_approval`/`execute_approved`/`set_workspace` + `ApprovalState` |
| `src-tauri/src/workspace.rs` | NEW | Rust workspace authority: canonicalization, reparse rejection, token invalidation (7 тестов) |
| `src-tauri/src/lib.rs` | MOD | wiring: `mod approval/approval_commands/workspace`, `ApprovalState`, +3 handlers (parity 42/42) |
| `src-tauri/src/supervisor.rs` | MOD | `real_sidecar_env()`: silent-skip → panic при `LOCALCOMET_REQUIRE_REAL_SIDECAR` |
| `src-tauri/Cargo.toml` / `Cargo.lock` | MOD | +`getrandom`, +`subtle` |
| `src/lib/bridge/approval.ts` | NEW | Svelte bridge для approval/set_workspace команд |
| `desktop/contracts/localcomet_ipc_v1.schema.json` | MOD | `workspace.set` request/response контракт |
| `modules/workspace_policy.py` | NEW | переиспользуемый примитив confinement (self-test OK) |
| `security/invariants/invariants.toml` | NEW | 12 инвариантов; APPROVAL-001/002, EVIDENCE-001, UI-001 → active |
| `security/invariants/non_authorities.toml` | NEW | 16 записей «что НЕ является authority» |
| `security/invariants/tool_risk_levels.toml` | NEW | 5 инструментов (3 mutating → approval) |
| `scripts/check_tool_risk_registry.py` | NEW | gate полноты классификации (injection-proven) |
| `scripts/check_command_parity.py` | NEW | Svelte invoke == Tauri handler (42/42) |
| `scripts/check_ui_fake_state.py` | NEW | Math.random / long-timer-near-state gate (75 файлов, 0 нарушений) |
| `scripts/refresh_evidence.py` | NEW | evidence с tree digest |
| `scripts/check_evidence_provenance.py` | NEW | STALE-детекция (injection-proven) |
| `scripts/check_real_sidecar_tests.py` | NEW | CI gate для require-mode |
| `scripts/smoke_test.py` | NEW | in-process smoke реального sidecar (8/0) |
| `localcomet_test_harness.py` | NEW | harness, драйвит реальный `DesktopSidecarRuntime` |
| `scripts/doctor.py` | NEW | preflight (Rust/linker/Node/npm/Python/WebView2/NSIS) |
| `scripts/build.sh` | NEW | 7-step fail-fast pipeline (`.ps1` не создан — AGENTS.md) |
| `tests/test_trust_chain_invariants.py` | NEW | EOL/BOM/final-LF инварианты (15 файлов) |
| `.gitattributes` | MOD | усилен для trust-chain файлов |
| `config.py`, `approved-artifacts.v1.json` | MOD | CRLF→LF fix |
| `docs/engineering/best-of-two-final-report.md` | NEW | итоговый отчёт (2 фазы) |
| `docs/engineering/best-of-two-migration-matrix.md` | NEW | карта donor→LocalComet |
| `docs/unverified-ledger.md` | NEW | 9 записей недоказанного |
| `audit/AUDIT_GUIDE.md`, `audit/*.md`, `audit/manifest.sha256`, `audit/LocalComet-AUDIT-2026-07-25.txt` | NEW | аудит-гайд + текстовый аудит (donor-бинарники исключены) |

**Итого:** 33 файла, +5175 / −19.

---

## Security

- **Approval enforcement:** CSPRNG (`getrandom`, 256 бит), constant-time сравнение
  (`subtle`), scope = tool + canonical input digest + workspace + session + expiry,
  one-time consume, TTL sweep, execution-grant expiry (30 c). Нет bypass-пути:
  guarded tool проходит только через `execute_approved`.
- **Invariants активированы:** INV-APPROVAL-001, INV-APPROVAL-002, INV-EVIDENCE-001,
  INV-UI-001 (с `verification_method`).
- **Evidence provenance:** каждое доказательство привязано к tree digest исходников;
  изменение кода без refresh → STALE (injection-proven).
- **UI integrity:** frontend не генерирует fake backend state (`Math.random`=0,
  таймеры = polling/watchdog).
- **Ключевая находка:** desktop sidecar НЕ исполняет file-tools (`files.*` =
  `unsupported_method`); approval/workspace enforcement живёт в **Rust**, а не в sidecar.
  Критические дефекты donor (approval bypass, dual IPC, readiness «любой кадр»,
  не дренируется stderr) **не унаследованы**.

---

## Test Results [прогон]

```
cargo test            147 passed, 0 failed, 6 ignored
smoke (real sidecar)  8 passed, 0 failed
cargo clippy -D warnings  OK (0 warnings)
cargo fmt --check     OK
ui-fake-state         75 files, 0 violations
evidence provenance   4 files fresh (tree=d5c4c42c…)
tool-risk registry    5 tools (3 mutating → approval)
trust-chain           15 files OK
command parity        42/42
build                 LocalComet_6.84.6_x64-setup.exe (13.32 MB, SHA-256: 7fc82beb…)
                      LocalComet.exe (13.87 MB, SHA-256: 2bfdd0c7…)
```

---

## Known Issues / Unverified

Из `docs/unverified-ledger.md`:

| ID | Проблема | Статус |
|---|---|---|
| U-001 | npm registry UNREACHABLE (offline) — блокирует `npm ci`, не `npm run build` | BLOCKED (infra) |
| U-002 | packaged installer | PARTIAL — собран, не установлен/запущен (требует GUI) |
| U-003 | 6 ignored real-sidecar тестов (требуют окружения) | DEFERRED (honest skip) |
| B-003 | workspace IPC в sidecar | N/A (sidecar не исполняет fs-tools) |
| D-003 | CI workflow отсутствует в чекауте | DEFERRED |
| DONOR-001 | 2 donor-материала отсутствуют | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL (Rust boundary реален; GUI ждёт fs-tools) |

---

## Commits

| Hash | Сообщение |
|---|---|
| `4fa48fe` | feat(approval): CSPRNG scoped one-time tokens + product wiring |
| `822575e` | feat(workspace): WorkspacePolicy primitive + IPC schema workspace.set |
| `4a69094` | chore(audit): invariant registries + trust-chain and evidence gates |
| `cddd0e8` | test(sidecar): honest real-sidecar skip + in-process smoke harness |
| `4b0418e` | build: preflight doctor.py + build.sh pipeline |
| `36af461` | docs: best-of-two final report, unverified ledger, audit guide |
| `8b23f8c` | chore(invariants): activate INV-APPROVAL-001/002, INV-EVIDENCE-001; verify INV-UI-001 |

---

## Merge checklist

- [x] Все гейты зелёные (вывод показан)
- [x] Конфликтов с base нет (fast-forward)
- [x] **Целевая ветка:** `continue/after-build-week-2026` (`main` не существует; fast-forward, без конфликтов)
- [ ] Push ветки в origin (`integration/best-of-two-local-agent` ещё не запушена)
- [ ] Рецензент: проверить approval boundary и unverified-ledger перед мержем
