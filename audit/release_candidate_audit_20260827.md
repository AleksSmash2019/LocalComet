# LocalComet — current release-candidate audit

**Дата:** 27 августа 2026, UTC+5

**Ветка:** `feat/up00-wp01-windows-one-click-launch`

**HEAD:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`

**Статус:** `PENDING_TERMINAL`; completion и оценка `9/10+` не заявляются.

**Правило оценки:** по MASTERPROMPT source/contract tests не заменяют native protected-postcondition evidence. UI pill, body text, лог, открытый порт, self-report Python/model и совпадение image name не являются authority. Rust остаётся владельцем policy, approval, grant, host ownership и terminal verdict.

## 1. Исходное состояние и ограничения

Работа продолжалась только в canonical branch. Коммиты, новые ветки, reset, rebase, clean и broad process termination не выполнялись. Dirty owner WIP и исторические reports сохранены. Финальный snapshot после gate pack: `751` status records, из них `81` tracked records и `670` untracked records. `git diff --check` завершился с exit `0`; вывод содержит только стандартное предупреждение Git о возможной нормализации EOL для `.gitignore`, а не whitespace error. Exact hidden harness process guard в последней проверке: `active_exact_harness=0`.

Последний evidence refresh сообщает current tree digest:

`dc22a3b4e77280f3aef86ba277da3300b3a12b2a3cedf6b1cc09d52e08781634` (`589 source files`).

Нативные runs browser/Notepad/screenshot были выполнены после стабилизации application/sidecar поведения и перед последним изменением только performance-summary helper. Поэтому для acceptance они являются сильным current-code cutoff evidence, но byte-for-byte связь с итоговым digest `dc22…` должна считаться отдельным ограничением, пока независимый приёмщик не повторит native pack именно после этого последнего helper-only изменения.

## 2. Изменённые seams и риск

| Файл/область | Назначение правки | Остаточный риск |
|---|---|---|
| `tools/run_isolated_hidden_desktop_cu.py` | Pre-submit ToolCallCard baseline; strict same-turn correlation; exact browser listener PID/image/debug-port/profile identity; owner-scoped screenshot context, capture PID, rendered PNG/hash; bounded production Stop selector; fail-closed cancellation classification; parent→worker cancel forwarding; approval-required browser classification. | Native cancellation still has no backend safe-state/no-replay proof; restart and hostile native cases absent. |
| `modules/computer_use_real_actions_ru.py` | Hidden screenshot uses harness-owned context, exact desktop and broker-observed owner PID; visible-window capture filters by owner PID. | Sidecar remains non-authority; Rust capture/identity seam is not replaced. |
| `desktop/localcomet-desktop/src-tauri/src/supervisor.rs` | Sanitized sidecar environment forwards only exact `LC_HIDDEN_SCREENSHOT_OWNER_CONTEXT`. | No general authority is delegated to sidecar. |
| `desktop/localcomet-desktop/src/lib/components/chat/ToolCallCard.svelte` | Structured `data-cu-screenshot-capture-pid` projection for evidence extraction. | Projection is not authority. |
| `desktop/localcomet-desktop/src/lib/stores/modelGateway.ts` and related test | Bounded browser rewrite/continuation and macrotask terminalization so current ToolCallCard mounts before cleanup. | Acceptance still requires structured correlated fields. |
| `modules/local_model_gateway_ru.py` | Narrow deterministic official Python read-only URL fallback; explicit browser aliases; bounded/restrictive assistant instruction compatibility; current supported-locale validation. Generic search remains bounded task path. | This is a narrow compatibility path, not generic URL generation. |
| `tools/run_localcomet_desktop_sidecar.py` | Optional coordinator parameter preserves direct helper tests while production `main()` always passes the coordinator; tool-call dispatch still fails closed without it. | No authority change. |
| `tools/launch_localcomet_dev.py`, `tools/build_up00_windows_installer.py`, `desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json` | Controlled stage-only/refresh-build-source paths and Computer Use dependency closure for bundle parity. | Staging is not installer release proof. |
| `tests/test_hidden_evidence_contract.py`, `tests/test_cdp_driver_recovery.py`, `tools/test_up02_wp01_assistant_context.py` | Regression coverage for card baseline, browser identity, restrictive context and unsupported locale. | Tests remain contract evidence. |
| `tools/summarize_current_native_performance.py` | Updated deterministic report inputs to final browser/Notepad/screenshot tags; unmeasured metrics remain `NOT_MEASURED`. | It measures persisted harness timestamps only, not full latency/memory causal components. |
| `audit/sec_matrix_current_20260827.json` | Machine-readable SEC-001…SEC-016 inventory with actual status/evidence class and explicit native gaps. | All sixteen rows remain non-acceptance until protected native postconditions exist. |
| `audit/provenance_inventory_current_20260827.json` | Machine-readable component/license/provenance inventory with unresolved owner decisions. | It is not legal clearance. |

## 3. Fresh native evidence

| Scenario | Reports | Verdict | What is independently shown | What it does not show |
|---|---|---|---|---|
| Browser read-only search | `.../nine_20260827_browser_python_32/isolated_hidden_user_runs.jsonl`; `.../nine_20260827_browser_python_33/isolated_hidden_user_runs.jsonl` | `VERIFIED_SUCCESS` ×2 | One scoped card; exact approval request/model request/model action/approval/call/input correlation; `approval_required=true`; HTTPS `www.python.org`; title `Welcome to Python.org`; Chrome listener owner PID = broker PID; exact `chrome.exe`, debug-port flag, isolated profile, hidden-window PID; owner cleanup. | Does not close hostile fake-DOM/foreign approval, cancellation, restart, or SEC rows. |
| Notepad open/type | `.../nine_20260827_notepad_open_type_11/isolated_hidden_user_runs.jsonl`; `_12/...` | `VERIFIED_SUCCESS` ×2 | Exact synthetic marker `LocalComet isolated smoke test.` independently read by UIA; marker SHA-256 prefix/full recorded as `1e074c1c...09fd77`; one owned Notepad PID/desktop; exact cleanup. | Uses explicit hidden session capability and `approval_required=false`; not native approval-modal evidence. |
| Screenshot | `.../nine_20260827_screenshot_12/isolated_hidden_user_runs.jsonl`; `_13/...` and each `captured_window.png` | `VERIFIED_SUCCESS` ×2 | Window-scoped `gdi_bitblt`; `4,239` bytes; PNG magic/positive size; SHA-256 `b993e04bf2c4b4bbdb3dc14d5a4d590f494b31edaee6c97718484baffbb9cbf1`; `capture_pid` equals broker-owned Notepad PID; rendered ToolCallCard PNG verification; nonblank visual inspection; exact cleanup. | Screenshot is read-only observation; no cancel/restart proof. |
| Native cancellation | `.../nine_20260827_cancel_browser_01/isolated_hidden_user_runs.jsonl` | `PENDING_TERMINAL` | Real production Stop control observed/clicked (`data-composer-action=stop`, `aria=Остановить`) while approval was pending; no browser PID/port was evidenced before spawn; owner cleanup. | No Rust/model cancellation acknowledgement, safe-state checkpoint, stale-continuation rejection, or post-restart proof. This P0 remains open. |
| Recovery scenario | `.../nine_20260827_notepad_recovery_01/isolated_hidden_user_runs.jsonl` | `VERIFIED_FAILED` | Guarded open-app dispatch reached broker boundary. | Independent UI returned `No UI candidates found`; this is not process-boundary restart evidence. |
| Foreign same-title/wrong-PID | No native acceptance report | `NOT_INDEPENDENTLY_VERIFIED` | Rust/source wrong-owner guards and offline tests exist. | No production close/click case proves foreign process remains untouched. |
| Application restart/no replay | No application-level native report | `NOT_INDEPENDENTLY_VERIFIED` | Rust `task_ledger` separate-process/ledger contract test exists and passed. | No real LocalComet process-boundary run proves `paused_for_review`, zero host replay, old grant rejection and new attempt/approval. |

Historical diagnostics `_21`–`_27` remain preserved and are excluded from acceptance. Browser `_30`/`_31` were superseded for strict final cutoff by `_32`/`_33`.

## 4. Exact final gates

### Frontend

| Command | Exit | Final line/fact |
|---|---:|---|
| `npm run check` (from `desktop/localcomet-desktop`) | 0 | `svelte-check found 0 errors and 0 warnings` |
| `npm test` | 0 | `Test Files 39 passed (39)`; `Tests 555 passed (555)` |

### Rust

| Command | Exit | Final line/fact |
|---|---:|---|
| `cargo test --lib -- --test-threads=1` | 0 | `test result: ok. 732 passed; 0 failed; 7 ignored` |
| `cargo fmt --all -- --check` | 0 | no formatting errors |
| `cargo clippy --all-targets --all-features -- -D warnings` | 0 | completed without warnings/errors |

### Python mandatory pack under explicit system CPython 3.14

Environment: `LOCALCOMET_TEST_PROJECT_ROOT=<canonical root>`, `LOCALCOMET_TEST_PYTHON=C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe`, `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`.

| Command | Exit | Final result |
|---|---:|---|
| `python tests/test_check_bundle_parity.py` | 0 | `OK` |
| `python tests/test_evidence_model.py` | 0 | `OK: 4 evidence file(s) fresh and intact` |
| `python tests/test_trust_chain_gate.py` | 0 | `OK` |
| `python tests/test_tool_risk_registry_gate.py` | 0 | `OK` |
| `python tests/test_mockdata_import_gate.py` | 0 | `OK` |
| `python tests/test_trust_chain_invariants.py` | 0 | `OK: 15 trust-chain files pass byte invariants` |
| `python scripts/check_command_parity.py` | 0 | `OK: 79 commands registered and invoked` |
| `python scripts/check_tool_risk_registry.py` | 0 | `OK: 7 console tool functions; 11 sidecar tools; 21 registry entries valid` |
| `python scripts/check_ui_fake_state.py` | 0 | `OK: no fake-state violations in 114 frontend files` |
| `python scripts/check_mockdata_imports.py` | 0 | `ALL OK` |
| `python scripts/check_bundle_parity.py` | 0 | `OK: 430 shipped module(s) match source across 2 location(s)` |
| `python tools/test_bug1_inference_bundle_parity.py` | 0 | `ALL OK` |
| `python tools/test_adr015_tool_parsing.py` | 0 | `OK (skipped=1)` |
| `python tools/test_tool_risk_rust_parity.py` | 0 | `OK: parser self-tests passed` |
| `python scripts/smoke_test.py --mode=cli` | 0 | `SMOKE PASSED: real sidecar product path behaves as expected` |
| `python scripts/refresh_evidence.py` | 0 | `evidence refreshed: all gates green`; current digest `dc22a3b4e77280f3aef86ba277da3300b3a12b2a3cedf6b1cc09d52e08781634` |
| `python scripts/check_evidence_provenance.py` | 0 | `OK: 4 evidence file(s) fresh and intact` |
| `python scripts/check_real_sidecar_tests.py` | 0 | `OK: real-sidecar tests ran under require mode with no silent skips` |
| `python -m pytest -q tests tools --basetemp <new owned temp>` | 0 | `1360 passed, 2 skipped, 3 warnings, 409 subtests passed in 212.24s` |

Дополнительный focused set после harness/source changes: `95 passed, 7 subtests passed`.

Первый pack с exit `1` был диагностическим: его runner ошибочно передавал script path через PowerShell range `1..0`, а после исправления runner parity один раз был stale до staging. Эти failures superseded; persisted release pack находится в `audit/python_release_gate_pack_current_20260827.log` и содержит только exit `0`.

## 5. Performance

Источник: только persisted `started_utc`/`finished_utc`; это не fabricated end-to-end model profiling.

| Metric | n | p50 | p95 | max | failures |
|---|---:|---:|---:|---:|---:|
| browser read-only search | 2 | 4,767.139 ms | 4,807.922 ms | 4,812.453 ms | 0 |
| Notepad open/type | 2 | 14,888.750 ms | 14,916.951 ms | 14,920.085 ms | 0 |
| desktop screenshot | 2 | 3,201.588 ms | 3,211.216 ms | 3,212.286 ms | 0 |
| cancel browser diagnostic | 1 | 303,127.298 ms | 303,127.298 ms | 303,127.298 ms | 1 (`PENDING_TERMINAL`) |

`model_load_and_ready`, `first_response`, `first_tool_call`, `dispatch_to_observation`, `restart_recovery`, memory, ledger growth и `cancellation_to_safe_state` остаются `NOT_MEASURED` с reason, записанным в `audit/performance_current_20260827.json`. Следовательно performance row полностью release-closed не является.

## 6. SEC-001…SEC-016

Полная machine-readable matrix находится в `audit/sec_matrix_current_20260827.json`. Все 16 rows имеют `input`, `expected`, `actual`, `protected_postcondition`, `evidence_refs`, `evidence_class`, `verdict` и `reason`. На текущем срезе:

| Статус | Количество | Интерпретация |
|---|---:|---|
| `NOT_INDEPENDENTLY_VERIFIED` | 16 | Ни одна hostile row не закрыта native/protected-postcondition evidence полностью |
| `VERIFIED_SUCCESS` | 0 | Нет основания выдавать hostile acceptance |
| `VERIFIED_BLOCKED` | 0 | Blocked negative cases не были проведены как отдельные native rows |

Contract coverage существует для path traversal/reparse, command and risk registry, grant binding, ledger corruption/oversize, ordered failure, skill validation и UI evidence. Она остаётся contract-only и не поднимает SEC matrix до acceptance.

## 7. Provenance/legal inventory

`audit/provenance_inventory_current_20260827.json` создан в требуемом machine-readable schema. Он перечисляет application code, CPython, GGUF model, RHVoice, Piper, Cargo/npm/Python dependencies, skills и visual/evidence assets. Для unresolved items explicitly указаны `redistribution_status`, `commercial_status`, `notice_path`, `evidence_class` и `owner_decision_required`. Это **не** legal clearance. Наиболее заметные owner decisions: точный GGUF artifact provenance/license, RHVoice voice terms, Piper model terms, complete third-party notice bundle, skill/asset provenance и commercial redistribution.

## 8. Открытые P0/P1 blockers и score cap

| Blocker | Verdict/status | Why it remains open |
|---|---|---|
| B2 approval | Partially evidenced | Browser has two exact native approvals, but no negative fake/foreign approval case; Notepad/screenshot use session capability. |
| B3 cancellation/timeout | Open | Stop click is `PENDING_TERMINAL`; no Rust safe-state/no-replay proof. |
| B3 restart/recovery | Open | Only ledger child/contract proof; no application-level process-boundary recovery. |
| B4 foreign ownership | Open | No native same-title wrong-PID untouched postcondition. |
| B4 SEC-001…SEC-016 | Open | All 16 matrix rows are `NOT_INDEPENDENTLY_VERIFIED`. |
| Release performance | Partial | Three native metrics measured; required model/restart/memory/safe-state metrics remain `NOT_MEASURED`. |
| Release provenance/legal | Partial | Inventory exists, but multiple owner decisions and notices remain unresolved. |

**Оценка:** предыдущий audit cap `7.8/10` сохраняется как консервативный cap; новая оценка выше него в этом отчёте не заявляется. До закрытия всех P0 rows оценка **не может быть `9/10` или `9.5/10`**. Даже при сильных green contract gates текущий acceptance result — `PENDING_TERMINAL`, а не completion.

## 9. Следующий необходимый порядок работ

Сначала нужен отдельный application-level process-boundary harness, который доводит задачу до `WAITING_HOST`, завершает только exact owned app tree, после запуска получает read-only `paused_for_review`, доказывает zero host replay, rejection старого grant и новый `execution_attempt_id`/approval. Затем нужны native foreign same-title/wrong-PID, cancel-to-safe-state и hostile SEC fixtures с protected before/after postconditions. После этого следует повторить full gates и получить independent acceptance review. До этих шагов не следует менять verdicts в SEC matrix и не следует повышать score.

## Attachments / supporting evidence

- `audit/python_release_gate_pack_current_20260827.log`
- `audit/performance_current_20260827.json`
- `audit/sec_matrix_current_20260827.json`
- `audit/provenance_inventory_current_20260827.json`
- `audit/current_session_findings_20260827.md`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_browser_python_32/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_browser_python_33/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_notepad_open_type_11/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_notepad_open_type_12/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_screenshot_12/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_screenshot_13/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/nine_20260827_cancel_browser_01/isolated_hidden_user_runs.jsonl`
