# Финальный аудит LocalComet — 2026-08-28

## Идентичность и исходное состояние

Ветка: `feat/up00-wp01-windows-one-click-launch`. HEAD: `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`. Финальный source tree digest: `6820f0b3eb2afbf17ec50eaa9751e4f1f64b49086bf0b6152505685f6d2c10c9`; `refresh_evidence.py` подтвердил 598 source files и green evidence gates. Рабочее дерево намеренно оставлено dirty: сохранены унаследованные WIP/history; `git status --short -uall` содержит 782 строк. Коммитов, reset/rebase/clean и массового удаления не выполнялось.

Последний `git diff --check`: exit 0. `py_compile` для изменённых Python seams: exit 0. Технический transient helper для cleanup interrupted browser run сохранён в `audit/cleanup_interrupted_browser.py` вместе с его cleanup artifact; он не является production authority.

## Что изменено в текущем продолжении

| Файл/область | Назначение | Риск/ограничение |
|---|---|---|
| `tools/run_isolated_hidden_desktop_cu.py` | Native fake-DOM/foreign/cancel/restart orchestration; strict broker-owned PID evidence; screenshot owner-context gating; cancellation full-P0 narrowed | Harness/evidence-layer change; не расширяет Rust authority; native evidence должна быть привязана к digest |
| `tests/test_hidden_evidence_contract.py` | Regression coverage для rollback own-preimage и cancellation predicates | Test-only |
| `desktop/localcomet-desktop/src-tauri/src/coding_commands.rs` | Rust-owned persisted approval checkpoint для честной app-boundary recovery | Production ledger behavior changed; covered by Rust gates and native restart |
| `desktop/localcomet-desktop/src-tauri/src/coding_orchestrator.rs` | Синхронизация continuation `awaiting_approval -> running` | Production coding state machine; compile-only truth preserved |
| `desktop/localcomet-desktop/src-tauri/permissions/coding.toml` | Allow already registered read-only list/recover commands | Capability surface расширена только для declared recovery reads |
| `desktop/localcomet-desktop/src-tauri/capabilities/main.json` | Current Tauri capability wiring used by restart probe | Must remain reviewed against ACL |
| `audit/*` | Fresh evidence, matrices, gate logs and report artifacts | Technical evidence, not legal clearance |

## Fresh native matrix

| Scenario | Current evidence | Verdict | Scope/remark |
|---|---:|---|---|
| Notepad UIA/type | 2 cases in `autonomous_20260828_110000_notepad_x2` | `VERIFIED_SUCCESS` ×2 | Hidden desktop, Rust broker PID/image, UIA marker SHA, owner cleanup |
| Browser readonly search | 2 successful isolated runs (`autonomous_20260828_111500_browser_x2` case 1 and `autonomous_20260828_113000_browser_02_current`) | `VERIFIED_SUCCESS` ×2 | Approval/request/action/input correlation, HTTPS Python title, isolated profile, listener PID/debug flag |
| Screenshot | 2 cases (`autonomous_20260828_081500_screenshot_01b`, `autonomous_20260828_081500_screenshot_02b`) | `VERIFIED_SUCCESS` ×2 | Owner context, capture PID, PNG bytes/SHA/rendered nonblank |
| Coding E2E | 2 cases in `autonomous_20260828_090000_coding_x2` | `VERIFIED_SUCCESS` ×2 | Real Tauri IPC; replay/tamper/rollback; production result honestly compile-only |
| Fake DOM approval | 2 separate current runs | `VERIFIED_BLOCKED` ×2 | Real Rust `run_tool_call` rejects fake token; no new Notepad PID |
| Foreign ownership | 2 cases in `autonomous_20260828_093000_foreign_x2` | `VERIFIED_BLOCKED` ×2 | Random unregistered close denied; same-title foreign PID survives; scope is not arbitrary registry spoofing |
| Application restart | `autonomous_20260828_100000_restart_final` | `VERIFIED_SUCCESS` | Fresh app/WebView phase 2: paused_for_review, requires_review=true, terminal=false, zero auto-start, duplicate approval `task_exists`, unchanged SHA |
| Cancellation | `autonomous_20260828_103000_cancel_final` | `PENDING_TERMINAL` | Model-turn Stop/Cancelled/worker dead/no new cards proven; post-grant continuation revocation/no replay remains open |

Browser batch additionally contains one fail-closed `VERIFIED_BLOCKED` case caused by hidden CDP port reuse inside the same batch; it is not counted as a success and is retained as diagnostic evidence.

## SEC matrix result

Superseding machine-readable matrix: `audit/sec_matrix_current_20260828_final.json`. Current closed rows are **SEC-002**, **SEC-011** (scoped), and **SEC-016**. **SEC-001, SEC-003–010, SEC-012–015 remain `NOT_INDEPENDENTLY_VERIFIED`** because the required native protected postcondition is absent. Source tests and Conor’s synthetic fixtures are retained as contract evidence, never promoted to A solely by their self-label.

## Performance and provenance

Superseding performance artifact: `audit/performance_current_20260828_final.json`. It measures only persisted native scenario intervals. Model readiness, first response/tool call, dispatch-to-observation, memory, ledger growth, restart latency and full cancellation-to-safe-state are explicitly `NOT_MEASURED`; no synthetic samples were invented.

Superseding provenance artifact: `audit/provenance_inventory_current_20260828_final.json`. It is a **technical inventory, not legal clearance**. Exact model/voice/license, notices, redistribution and commercial-use decisions remain owner/legal blockers.

## Final gates

| Gate | Exit | Last recorded output |
|---|---:|---|
| `npm run check` | 0 | [39m |
| `npm test` | 0 | [2m   Duration [22m 3.54s[2m (transform 44.11s, setup 0ms, import 52.55s, tests 1.78s, environment 14ms)[22m |
| `cargo test` | 0 | test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s |
| `cargo fmt --check` | 0 | (no output) |
| `cargo clippy --all-targets --all-features -- -D warnings` | 0 | Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.72s |
| `Python mandatory pack (18 explicit commands)` | 0 | OK: real-sidecar tests ran under require mode with no silent skips |
| `python scripts/check_real_sidecar_tests.py` | 0 | OK: real-sidecar tests ran under require mode with no silent skips |
| `full pytest -q tests tools --basetemp <unique> -p no:cacheprovider` | 0 | 1385 passed, 2 skipped, 413 subtests passed in 214.54s (0:03:34) |
| `python scripts/check_evidence_provenance.py` | 0 | OK: 4 evidence file(s) fresh and intact (tree=6820f0b3eb2afbf1...) |
| `git diff --check` | 0 | warning: in the working copy of 'tools/test_adr015_tool_parsing.py', CRLF will be replaced by LF the next time Git touches it |
| `py_compile modified Python seams` | 0 | (no output) |

Full pytest final rerun: **1385 passed, 2 skipped, 413 subtests passed in 214.54s (0:03:34), exit 0**. Real-sidecar gate: exit 0 with `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` and system CPython 3.14.6.

## Score decision

**9/10 не достигнуто и не заявляется.** Консервативный release score cap остаётся **8.0/10**: cancellation full P0 post-grant proof отсутствует; 13 SEC rows остаются open/not independently verified; hostile skills, headless OAuth/MCP, prompt-injection and outbound/no-upload native proof are absent; measured performance coverage is partial; provenance/legal owner decisions are unresolved. Это не измеренная метрика качества, а fail-closed cap по acceptance blockers.

Что действительно улучшено: app-boundary restart/recovery теперь подтверждён реальным production Tauri path; fake-DOM denial, scoped foreign-owner denial, current browser/Notepad/screenshot/coding runs и gates — fresh/current на digest `6820f0b3eb2afbf17ec50eaa9751e4f1f64b49086bf0b6152505685f6d2c10c9`. Это повышает доказанную поверхность, но не превращает incomplete SEC/P0 set в 9/10.

## Остаточные blockers

1. Для полного B3 cancellation нужен реальный approved/consumed in-flight host continuation, доказанная revoke/no-replay после Stop и независимый protected postcondition.
2. Нужны native protected-postcondition fixtures для SEC-001, 003–010, 012–015, особенно no-upload, non-allowlisted URL/profile, cross-session grant, corrupt ledger, bounded resources, injection, ordered failure, skills tamper/quarantine и headless OAuth/MCP.
3. Нужны owner/legal решения по GGUF, RHVoice/Piper, notices, redistribution/commercial use и skill/asset licenses.
4. Нужны dedicated readiness/latency/memory/ledger/cancellation performance protocols; current measured intervals не заменяют их.

## Dashboard

Append-only current dashboard update выполнен в `pipeline/mvp-program-status.md` и `pipeline/loop-status.md`; historical sections не переписаны.


## Приложение — Python gate ledger

Все 18 обязательных Python-команд повторно выполнены с system CPython 3.14.6 и exit 0; полный дословный stdout/stderr каждой команды сохранён в отдельных файлах `audit/final2_python_*.log`. Ключевые tails: `test_check_bundle_parity.py` — `OK`; `test_evidence_model.py` — `OK: 4 evidence file(s) fresh and intact`; `test_trust_chain_invariants.py` — `OK: 15 trust-chain files pass byte invariants`; `check_command_parity.py` — `OK: 79 commands registered and invoked (parity holds)`; `check_bundle_parity.py` — `OK: 430 shipped module(s) match source across 2 location(s) (bundle parity holds)`; `test_adr015_tool_parsing.py` — `OK (skipped=1)`; CLI smoke — `SMOKE PASSED: real sidecar product path behaves as expected.`; `refresh_evidence.py` — `evidence refreshed: all gates green`; `check_evidence_provenance.py` — `OK: 4 evidence file(s) fresh and intact (tree=6820f0b3eb2afbf1...)`; real-sidecar — `OK: real-sidecar tests ran under require mode with no silent skips`. Full pytest final rerun: `1385 passed, 2 skipped, 413 subtests passed in 214.54s`, exit 0. Первая full-pytest попытка остановилась только из-за отсутствовавшего test-runtime `psutil`; после установки этого внешнего runtime-пакета повтор зелёный. Не было добавлено project dependency.
