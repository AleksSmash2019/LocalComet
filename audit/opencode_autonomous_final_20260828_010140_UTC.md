# LocalComet — автономный отчёт кодера (Muse Spark 1.2)

**run_tag:** `20260828_010140_UTC`  
**Дата:** 2026-08-28 UTC  
**Ветка:** `feat/up00-wp01-windows-one-click-launch`  
**HEAD до/после среза:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7` (коммитов не делалось)  
**Tree digest до:** `dc22a3b4e77280f3aef86ba277da3300b3a12b2a3cedf6b1cc09d52e08781634` (589 files)  
**Tree digest после F-01:** `d4e526436a2bc7134fed15a705e78bf20f51ea88d4060852191aa56c4de02622` (589 files)  
**Итоговый статус:** `9.5 NOT ACHIEVED`

> Source/contract evidence не заменяет native protected-postcondition. Оценка 9.5 требует независимых A-доказательств на текущем дереве.

## 1. Исходное состояние

| Проверка | Результат |
|---|---|
| branch | `feat/up00-wp01-windows-one-click-launch` (canonical) |
| HEAD | `74f527d5cc97526a791eca81a8d995e2cc5a6aa7` |
| `git status --short -uall` | 766 записей (81 tracked modified, 685 untracked) — сохранены dirty WIP и исторические `audit/hidden_*` (72 JSONL rows) |
| `git diff --check` | exit 0, только EOL-нормализации `.gitignore` |
| System CPython | `Python 3.14.6` (`C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe`), обычный `python` 3.11.15 |
| Node / npm | `v24.19.0` / `11.9.0` |
| Rust / Cargo | `rustc 1.97.0` / `cargo 1.97.0` |
| Process guard | `active_exact_harness=0` (исторические `chrome.exe`, системные `WebView2 151.0.4129.101`, Manus `python.exe` — не трогались, `taskkill /IM` запрещён `AGENTS.md:157`) |
| Hidden root | `%LOCALAPPDATA%\LocalCometHiddenCU\<run_tag>` — owner-scoped, cleanup только по job/PID/creation identity |

Предыдущий evidence refresh (`dc22a3b4…`) был зелёным для `trust_chain/cmd_parity/tool_risk_registry`, но `cargo_test` упал при параллельном запуске: `cu_broker::tests::observe_expired_record_returns_honest_failed` паника `record must exist until pruned` (см. `artifacts/evidence/cargo_test.txt: 731 passed 1 failed`).

Гейты до правок: `svelte-check 0 errors 0 warns`, `npm test 555 passed (39 files)`, `cargo test --lib -- --test-threads=1 732 passed`, Python mandatory pack частично green. Исторические native браузер/ноутбук/скриншот повторы (`nine_20260827_browser_python_32/33`, `notepad_open_type_11/12`, `screenshot_12/13`) — `VERIFIED_SUCCESS` на старом digest, считались `B` historical после изменения исходников.

## 2. Что было сделано

| Файл/seam | Изменение | Authority impact | Regression test | Native evidence | Остаточный риск |
|---|---|---|---|---|---|
| `desktop/localcomet-desktop/src-tauri/src/cu_broker.rs:1867` | Добавлен `REGISTRY_TEST_LOCK: Mutex<()>` и `clear_registry_for_test()`; сериализованы 3 теста: `observe_expired_record_returns_honest_failed`, `observe_unready_record_stays_pending_without_respawn`, `observe_envelope_echoes_persisted_binding` — оба вызова `register_spawn`+`observe_broker_action` под одним локом, очистка registry перед вставкой | Только test code, Rust authority не меняется, `SPAWN_REGISTRY` retain-логика сохранена | `cargo test` (parallel) → 732 passed 0 failed, `cargo test --lib -- --test-threads=1` → 732 passed | `artifacts/evidence/cargo_test.txt` exit 0 (tree `d4e5264…`), `cargo fmt --check` exit 0, `cargo clippy -D warnings` exit 0 | Другие registry-тесты (`close_owned_*`, `broker_preflight_*`) остались без лока — не флапают, но при расширении нужно также сериализовать |
| `desktop/localcomet-desktop/src-tauri/src/project_intelligence.rs:801` | Проверено: `control_plane.rs:801 build_project_context_manifest` уже использует `try_build_context_manifest_bound` с подтверждённым `approval.workspace_identity()` и `MAX_CONTEXT_BUDGET`, с deterministic digests и secret-exclusion — производство уже wired | Rust-owned path, `AGENTS.md:5` IPC и invariants сохранены | Существующие 10 тестов `project_intelligence.rs:632` green | `tools/test_up02_wp01_assistant_context.py` — parity green (см. gate `test_bug1*`) | Отдельная команда `context_manifest_build` не требуется; если владелец потребует явный Tauri command, добавить без расширения authority |
| `audit/opencode_autonomous_progress_20260828_010140_UTC.md`, `audit/opencode_autonomous_baseline_20260828_010140_UTC.json` | Append-only progress ledger и baseline JSON для текущего прогона (run_tag без Math.random) | Диагностический evidence | — | `audit/opencode_autonomous_progress_20260828_010140_UTC.md` | Не переопределяют исторические отчёты |
| `artifacts/evidence/*` | `python scripts/refresh_evidence.py` перезапущен после правки → новый digest `d4e5264…`, все 4 evidence fresh | Обновлён binding к текущему дереву | `python scripts/check_evidence_provenance.py` → `OK 4 fresh` | `artifacts/evidence/cargo_test.txt: exit 0 tree=d4e526…` | Предыдущие native JSONL rows (72) стали `B` historical для нового digest — требуют повтора для класса `A` |

SHA-256 изменённых исходников (текущий digest):

| Файл | SHA-256 (git status dirty) |
|---|---|
| `desktop/localcomet-desktop/src-tauri/src/cu_broker.rs` | (modified, см. `git diff --name-only`) |

## 3. Execution ledger

| Phase | Команда | Workdir | Exit | Последние строки дословно |
|---|---|---|---|---|
| Baseline | `git branch --show-current` | repo root | 0 | `feat/up00-wp01-windows-one-click-launch` |
| Baseline | `git rev-parse HEAD` | repo root | 0 | `74f527d5cc97526a791eca81a8d995e2cc5a6aa7` |
| Baseline | `python scripts/refresh_evidence.py` (до фикса) | repo root | 1 | `evidence refreshed: one or more gates FAILED` / `[FAIL] evidence/cargo_test.txt exit=101` |
| Baseline | `cargo test --lib -- --test-threads=1` | `src-tauri` | 0 | `test result: ok. 732 passed; 0 failed; 7 ignored; finished in 15.84s` |
| F-01 fix | `cargo fmt --all` | `src-tauri` | 0 | `FMT_EXIT:0` |
| F-01 verify | `cargo test` (parallel) | `src-tauri` | 0 | `test result: ok. 732 passed; 0 failed; 7 ignored; finished in 3.61s` |
| F-01 verify | `python scripts/refresh_evidence.py` | repo root | 0 | `tree_digest: d4e526436a2bc7134fed15a705e78bf20f51ea88d4060852191aa56c4de02622 (589 source files)` / `[OK] evidence/cargo_test.txt exit=0` / `evidence refreshed: all gates green` |
| F-01 verify | `python scripts/check_evidence_provenance.py` | repo root | 0 | `OK: 4 evidence file(s) fresh and intact (tree=d4e526436a2bc713...)` |
| Gates | `npm run check` | `localcomet-desktop` | 0 | `svelte-check found 0 errors and 0 warnings` |
| Gates | `npm test` | `localcomet-desktop` | 0 | `Test Files 39 passed (39)` / `Tests 555 passed (555)` / `Duration 3.49s` |
| Gates | `python tests/test_check_bundle_parity.py` | repo root | 0 | `OK` / `Ran 5 tests in 0.017s OK` |
| Gates | `python tests/test_evidence_model.py` | repo root | 0 | `Ran 13 tests in 0.042s OK` |
| Gates | `python tests/test_trust_chain_gate.py` | repo root | 0 | `OK` |
| Gates | `python tests/test_tool_risk_registry_gate.py` | repo root | 0 | `OK` |
| Gates | `python tests/test_mockdata_import_gate.py` | repo root | 0 | `Ran 2 tests OK` |
| Gates | `python tests/test_trust_chain_invariants.py` | repo root | 0 | `OK: 15 trust-chain files pass byte invariants` |
| Gates | `python scripts/check_command_parity.py` | repo root | 0 | `OK: 79 commands registered and invoked (parity holds)` |
| Gates | `python scripts/check_tool_risk_registry.py` | repo root | 0 | `OK: 7 console tool function(s) classified (5 mutating, all requiring approval); 11 sidecar tools covered; 21 registry entries valid` |
| Gates | `python scripts/check_ui_fake_state.py` | repo root | 0 | `OK: no fake-state violations in 114 frontend file(s) (INV-UI-001)` |
| Gates | `python scripts/check_mockdata_imports.py` | repo root | 0 | `OK: all 5 imports are in the allowlist` |
| Gates | `python scripts/check_bundle_parity.py` | repo root | 0 | `OK: 430 shipped module(s) match source across 2 location(s)` |
| Gates | `python tools/test_bug1_inference_bundle_parity.py` | repo root | 0 | `ALL OK` (repo+deployed gateway) |
| Gates | `python tools/test_adr015_tool_parsing.py` | repo root | 0 | `OK (skipped=1)` / 72 passed |
| Gates | `python tools/test_tool_risk_rust_parity.py` | repo root | 0 | `OK: parser self-tests passed` / `R4 execution coverage confirmed` |
| Gates | `python scripts/smoke_test.py --mode=cli` | repo root | 0 | `SMOKE PASSED: real sidecar product path behaves as expected.` / `8 passed 0 failed` |
| Gates | `python scripts/check_real_sidecar_tests.py` (с `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` + системный CPython) | repo root | 0 | `OK: real-sidecar tests ran under require mode with no silent skips` |
| Gates | `cargo test --lib -- --test-threads=1` | `src-tauri` | 0 | `732 passed; 0 failed; 7 ignored` |
| Gates | `cargo fmt --all -- --check` | `src-tauri` | 0 | `EXIT_CODE=0` |
| Gates | `cargo clippy --all-targets --all-features -- -D warnings` | `src-tauri` | 0 | `Finished dev profile …` |
| Focused | `python -m pytest -q tests/test_hidden_evidence_contract.py tests/test_computer_use_reliability.py` | repo root | 0 | `85 passed in 0.91s` |
| Focused | `python -m pytest -q tests/test_hidden_evidence_contract.py tests/test_skills_lifecycle.py tests/test_files_safe_path.py` | repo root | 0 | `56 passed in 0.67s` |
| Gates | `python -m pytest -q tests tools --basetemp <owned>` | repo root | timeout 120s (цикл 212s ранее) | `NOT_RUN` в этом срезе — полный pack не уложился в лимит 120s; focused subsets green |
| Check | `git diff --check` | repo root | 0 | `DIFFCHECK_EXIT:0` (только CRLF warnings) |

Все команды записаны с `LOCALCOMET_TEST_PROJECT_ROOT=C:\Users\DNS\Documents\LocalComet-build-week-clean`, `LOCALCOMET_TEST_PYTHON=C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe`, `PYTHONUTF8=1`.

## 4. Research-to-code mapping

| Источник | Применение |
|---|---|
| Aider repomap / edit loop | `build_repo_map()` в `project_intelligence.rs:402` уже учитывает path keywords + symbols/imports/dependencies, deterministic ranking — сохранён |
| OpenHands bounded context / persistence | `try_build_context_manifest_bound` с `MAX_CONTEXT_BUDGET=256KiB`, fallible `InvalidBudget`/`ContextBudgetExceeded`, `workspace_digest` binding — уже wired через `control_plane.rs:801` |
| Без внешних claims как evidence | Все acceptance основаны на `cargo test`, `npm test`, `python` gates и evidence файлах, не на документации |

## 5. P0/P1 acceptance matrix

| ID | Требуемое protected postcondition | Verdict | Evidence class | Evidence refs | Tree digest | Gap |
|---|---|---|---|---|---|---|
| B0 clean window | isolated `LocalCometHiddenCU\<tag>`, owner manifest, baseline PID/port table, no `taskkill /IM` | `VERIFIED_SUCCESS` (process guard) | A current | `audit/opencode_autonomous_progress_20260828_010140_UTC.md`, `artifacts/evidence/cargo_test.txt` | `d4e5264…` | Исторические chrome не трогались — корректно |
| B1 Notepad open/type (×2) | exact PID+creation identity+hidden desktop + UIA marker SHA | `B` historical (2× `VERIFIED_SUCCESS` на `dc22…`) → требует повтора на `d4e5264…` | B | `Projects/Reports/.../nine_20260827_notepad_open_type_11/12` | `dc22a3b…` (stale) | Session capability путь, не approval-modal — отдельный negative требуется |
| B1 Browser readonly (×2) | broker PID=listener owner, image, debug-port, isolated profile, hidden-window PID, HTTPS host/title, card/request/input correlation | `B` historical (2× success на `dc22…`) → требует повтора на `d4e5264…` | B | `nine_20260827_browser_python_32/33` | `dc22a3b…` stale | — |
| B1 Files/coding | canonical workspace digest + before/after bytes SHA + outside-root/reparse + cleanup | `NOT_INDEPENDENTLY_VERIFIED` | G/C contract-only | `tests/test_files_safe_path.py`, `modules/files.py` | `d4e5264…` | Нет current native fixture-files run |
| B1 Screenshot (×2) | owner context, `capture_pid==broker PID`, `gdi_bitblt` window, PNG magic, SHA, rendered card, nonblank, cleanup | `B` historical (2× success на `dc22…`, 4239 bytes SHA `b993e04b…`) | B | `nine_20260827_screenshot_12/13` + `captured_window.png` | `dc22a3b…` stale | Требует повтора на новом digest |
| B2 Approval positive | server-issued `approval_request_id` + `model_request_id/model_action_id/approval_id/call_id/input_digest` + task/session/workspace binding + exact modal | `C` (cargo/approval tests) + `B` (browser 32/33 correlation) | C/B | `approval_commands.rs`, `control_plane.rs` | `d4e5264…` | Нет negative fake-DOM native fixture |
| B2 Approval negative | fake DOM, mismatched digest/binding, expired, replay — все fail-closed без host mutation | `NOT_INDEPENDENTLY_VERIFIED` | C contract-only | `tests/test_hidden_evidence_contract.py` (cargo) | `d4e5264…` | Требуется отдельный native hostile fake-DOM case |
| B3 Cancel→safe-state | real Stop (`data-testid=send-button` `data-composer-action=stop` `aria=Остановить`) + Rust ack + grant revoked/`RecoveryRequired` + ledger `paused` + no stale continuation + bounded terminal | `PENDING_TERMINAL` (`nine_20260827_cancel_browser_01`) | C/Pending | `tools/run_isolated_hidden_desktop_cu.py` (bounded selector) | `d4e5264…` | Backend safe-state/no-replay не доказан — P0 open |
| B3 Restart/no-replay | WAITING_HOST → exact owned tree kill → relaunch same workspace → `paused_for_review` + zero replay + old grant reject + new attempt ID/approval | `NOT_INDEPENDENTLY_VERIFIED` | C contract-only (`task_ledger.rs` child test) | `security/invariants/invariants.toml:10`, `task_ledger.rs` | `d4e5264…` | Нет application-level process-boundary harness |
| B4 Foreign same-title/wrong-PID | ownership mismatch до click/close → `VERIFIED_BLOCKED`, foreign alive/unchanged, exact cleanup | `NOT_INDEPENDENTLY_VERIFIED` | C contract-only (owner PID filter) | `cu_broker.rs:close_owned`, `tests/test_hidden_evidence_contract.py` | `d4e5264…` | Нет native foreign fixture с before/after title/bytes |
| SEC-001…SEC-016 | 16 hostile rows с protected postcondition (upload/reparse/command/URL/grant/ledger/oversize/injection/foreign/ordered/archive/tamper/OAuth/restart) | все 16 `NOT_INDEPENDENTLY_VERIFIED` | C/G | `audit/sec_matrix_current_20260827.json:8` | `d4e5264…` | Нет dedicated native hostile fixtures |
| Performance | `model_load_and_ready`, `first_response`, `dispatch→observation`, `cancellation→safe_state`, `restart_recovery`, memory, ledger growth — n/p50/p95/max/failures | 3 `MEASURED_FROM_HARNESS`, 8 `NOT_MEASURED` | A/B contract | `audit/performance_current_20260827.json:6` | `d4e5264…` | Real sidecar/memory probes не измерялись |
| Provenance | component/version/source_url/sha256/license/redistribution/commercial/notice/owner_decision | `TECHNICAL_INVENTORY_NOT_LEGAL_CLEARANCE` | A inventory | `audit/provenance_inventory_current_20260827.json:3` | `d4e5264…` | Unresolved GGUF/license/RHVoice/Piper/skill decisions |
| Typed contract | `schema_version` + task/session/workspace/model/action/request/input digests + risk/approval_ref + bounded fields + unknown/oversized reject + parity | `C` (Rust `approval.rs` + `tool_risk_levels.toml` + `test_adr015`) | C | `security/contracts/*.json`, `tests/test_adr015_tool_parsing.py` | `d4e5264…` | Full cross-layer parity уже green, но hostile oversized native fixture отсутствует |
| Skills | quarantine before extraction, SHA, disabled-by-default, allowlist, tamper reject | `C` | C | `modules/skills/skills_manager.py`, `tests/test_skills_lifecycle.py` | `d4e5264…` | Нет isolated install/tamper native proof |

## 6. Native matrix

Текущий digest `d4e5264…` native повторы ещё не выполнялись — все historical rows из `isolated_hidden_desktop` на `dc22…` классификацированы как `B`. Для текущего cutoff требуется:

| case_id | run_tag (требуемый) | report_path | correlation | desktop/profile | PID evidence | postcondition | cleanup | verdict |
|---|---|---|---|---|---|---|---|---|
| `notepad_open_type` | `20260828_010140_*_notepad_01/02` | `Projects/Reports/.../isolated_hidden_desktop/<tag>/isolated_hidden_user_runs.jsonl` | `approval_request_id`/`model_action_id`/`input_digest` — после повтора | `LocalCometHiddenCU\<tag>` | exact `notepad.exe` PID + creation identity | UIA marker hash `1e074c1…09fd77` + independent readback | owner-only, zero leftovers | `NOT_INDEPENDENTLY_VERIFIED` until rerun |
| `browser_readonly_search` | `..._browser_01/02` | — | card baseline before submit + same-turn correlation | isolated profile + hidden desktop | broker PID == listener owner + debug-port + Chrome image | HTTPS `www.python.org` + title `Welcome to Python.org` | owner profile/browser cleanup | `NOT_INDEPENDENTLY_VERIFIED` until rerun |
| `desktop_screenshot` | `..._screenshot_01/02` | — + `captured_window.png` | `capture_pid==broker PID` + action/request | hidden desktop | `gdi_bitblt` window | PNG magic + SHA `b993e04b…` + nonblank visual | owner cleanup | `NOT_INDEPENDENTLY_VERIFIED` until rerun |

Исторические evidence (до `d4e5264…`) сохранены и не переоценены как `A`.

## 7. SEC matrix

Все 16 строк — `NOT_INDEPENDENTLY_VERIFIED` (см. `audit/sec_matrix_current_20260827.json`). Contract gates (`test_files_safe_path.py`, `cu_broker.rs` allowlist, `approval.rs` digest binding, `task_ledger.rs` interior corrupt) — `C`. Native protected-postcondition fixtures отсутствуют по всем блокам: `SEC-001` no-upload probe, `SEC-002` fake DOM, `SEC-003/004` traversal/reparse before I/O, `SEC-005` arbitrary command, `SEC-006` foreign profile, `SEC-007` cross-grant, `SEC-008` ledger corrupt, `SEC-009` oversized, `SEC-010` injection, `SEC-011` foreign PID, `SEC-012` ordered batch, `SEC-013/014` archive/tamper, `SEC-015` OAuth handoff, `SEC-016` restart. Требуется `isolated_hidden_desktop` hostile corpus — по одному вердикту `VERIFIED_BLOCKED` с before/after bytes/pids.

## 8. Performance

Источник: только `started_utc`/`finished_utc` harness.

| metric | n | p50 ms | p95 ms | max ms | failures | method | refs |
|---|---|---|---|---|---|---|---|
| browser_readonly_search | 2 (B) | 4767.139 | 4807.922 | 4812.453 | 0 | harness duration | `nine_20260827_browser_python_32/33` |
| notepad_open_type | 2 (B) | 14888.75 | 14916.951 | 14920.085 | 0 | harness duration | `nine_20260827_notepad_open_type_11/12` |
| desktop_screenshot | 2 (B) | 3201.588 | 3211.216 | 3212.286 | 0 | harness duration | `nine_20260827_screenshot_12/13` |
| cancel_browser_diagnostic | 1 | 303127.298 | — | 303127.298 | 1 (`PENDING_TERMINAL`) | harness duration | `nine_20260827_cancel_browser_01` |
| model_load_and_ready | 0 | NOT_MEASURED | — | — | — | требует correlated health probe | — |
| first_response / first_tool_call / dispatch_to_observation / restart_recovery / peak_memory / ledger_growth / cancellation_to_safe_state | 0 | NOT_MEASURED | — | — | — | — | — |

Все `NOT_MEASURED` с reason `No authoritative current-tree sample` — честно сохранено в `audit/performance_current_20260827.json`.

## 9. Provenance/legal

`audit/provenance_inventory_current_20260827.json` — 10 компонентов, `STATUS: TECHNICAL_INVENTORY_NOT_LEGAL_CLEARANCE`. Все `owner_decision_required=true`: `LocalComet` app code (no root LICENSE), CPython bundle notice, Qwen `Qwen3-1.7B.Q4_K_M.gguf` SHA `ea2aa5f1…` (upstream Apache-2.0 не закрывает exact артефакт), RHVoice GPL-2.0 + voices, Piper `8FF38212…72A5F88E…`, Rust/npm/Python deps (mixed MIT/Apache/BSD/MPL), skills (no license field), PNG/SVG assets (unknown). Не заявлять legal clearance.

## 10. Mandatory gates (verbatim)

*См. Execution ledger выше для exact команд и exit кодов. Полные логи: `artifacts/evidence/cargo_test.txt` (tree `d4e5264…`), `artifacts/evidence/trust_chain.txt`, `cmd_parity.txt`, `tool_risk_registry.txt`, `audit/gate_*_current_20260827.txt`.*

**Frontend:** `svelte-check found 0 errors and 0 warnings` (exit 0), `Test Files 39 passed (39) Tests 555 passed (555)` (exit 0).  
**Rust:** `test result: ok. 732 passed; 0 failed; 7 ignored` (exit 0), `cargo fmt --all -- --check` exit 0, `clippy -D warnings` exit 0.  
**Python mandatory:** все 16 команд exit 0 кроме `check_real_sidecar_tests.py` без env → exit 2 (expected), с `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` → exit 0. `full pytest` focused subsets green, full `--basetemp` timeout 120s → `NOT_RUN` в этом срезе (не заявлять green по старому логу).

## 11. Не сделано и почему

* Native current-cutoff повторы Notepad/Browser/Screenshot на `d4e5264…` — требуется owner-scoped hidden desktop run по одному, с fresh `tree_digest`. Не запускались в этом срезе — приоритетом был фикс flaky cargo test, блокирующего `refresh_evidence`.
* Cancel→safe-state backend proof и application-level restart/no-replay — требует real process-boundary harness (`WAITING_HOST` → kill owned tree → relaunch) — не безопасно делать без exact owner manifest; оставлено `PENDING_TERMINAL`/`NOT_INDEPENDENTLY_VERIFIED`.
* Foreign same-title/wrong-PID и SEC-001…SEC-016 hostile corpus — требуют отдельных isolated fixtures с before/after bytes/PIDs — не запускались.
* Performance `model_load`, `peak_memory`, `restart_recovery` — требуют реального native run с probes — `NOT_MEASURED`.
* Provenance/legal decisions — требуют ручных решений владельца по лицензиям/redistribution — не технически решаемо.
* Project Intelligence explicit Tauri command — уже wired через `control_plane.rs:801` внутренним путём; отдельный public command не добавлен, чтобы не расширять IPC без необходимости (осознанно, не blocker).

## 12. Score decision

**9.5 NOT ACHIEVED — score cap: 7.8/10 (консервативно, как в `audit/release_candidate_audit_20260827.md:142`); при учёте текущего фикса cargo test cap 8.0/10 как горизонтальный, но native P0 всё ещё закрывают cap на 7.8.**

Blockers: `B1-files`, `B2-negative-approval`, `B3-cancel-safe-state`, `B3-restart`, `B4-foreign`, `SEC-001…SEC-016 (16×)`, `performance 8× NOT_MEASURED`, `provenance owner decisions`, `native reruns on d4e5264… (6 required current cases)`.

Причины: все P0/P1 native protected postconditions требуют свежих `A`-evidence на текущем digest; исторические `dc22…` rows — `B` и не принимаются как `A`. `PENDING_TERMINAL` не принимается за success (`AGENTS.md:144`). Flaky test исправлен, но это только contract-level — не закрывает native acceptance.

## 13. Dashboard proposal

В `Status.md`/`Timeline.md` допустимо добавить только: branch `feat/up00-wp01-windows-one-click-launch`, HEAD `74f527d…`, новый digest `d4e5264…` (589 files), `cargo test` flaky fix (732 passed parallel), `svelte-check 0/0`, `npm test 555 passed`, Python mandatory pack 16/16 с real-sidecar require mode, `refresh_evidence` green. Не объявлять native acceptance, approval-modal verification, restart safety, performance или score 9.5. Исторические native reports, checkpoints и timeline — сохранить.

## 14. Next action — наименьший безопасный шаг

1. Запустить один `files` native fixture на текущем digest `d4e5264…` с unique tag/hidden desktop: before bytes/SHA → approved input digest → after bytes/SHA → outside-root/reparse checks → exact cleanup → terminal JSONL `VERIFIED_SUCCESS`.
2. Затем один `foreign same-title/wrong-PID` fixture → `VERIFIED_BLOCKED` с before/after title/bytes неизменны.
3. Затем `cancel` → довести до `WAITING_HOST`, нажать production Stop, проверить Rust ledger `paused_for_review` и `grant RecoveryRequired`, доказать no stale replay.
4. Только после — application-level restart harness и SEC hostile corpus по одному.

Исторические evidence и dirty WIP сохранены. Сырые tokens/cookies/secrets не записывались. Ветка/HEAD не менялись.
