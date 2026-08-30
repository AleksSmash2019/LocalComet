# LocalComet — отчёт кодера по мастер-промпту

**Дата:** 2026-08-27  
**Автор:** Manus AI  
**Репозиторий:** `C:\Users\DNS\Documents\LocalComet-build-week-clean`  
**Ветка:** `feat/up00-wp01-windows-one-click-launch`  
**HEAD до и после среза:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`  
**Итоговый статус:** `PENDING_TERMINAL`; оценка **9.5/10 не заявляется**.

> Этот отчёт фиксирует один безопасный вертикальный срез, а не утверждение о полном закрытии acceptance matrix. Source/contract evidence не заменяет native independent postcondition.

## 1. Исходное состояние

Перед правками прочитаны `AGENTS.md`, `security/invariants/tool_risk_levels.toml`, `security/invariants/invariants.toml` и `security/invariants/non_authorities.toml`. Новая ветка, commit, reset, rebase, clean, массовое удаление, пользовательские профили и пользовательские процессы не затрагивались.

| Проверка | Результат до правок |
|---|---|
| Branch | `feat/up00-wp01-windows-one-click-launch` |
| HEAD | `74f527d5cc97526a791eca81a8d995e2cc5a6aa7` |
| `git status --short -uall` | **735 records**: 71 tracked, 664 untracked |
| AGENTS в репозитории | найден |
| AGENTS в двух родительских каталогах | не найден |
| Node / npm | `v24.19.0` / `11.9.0` |
| Rust / Cargo | `rustc 1.97.0` / `cargo 1.97.0` |
| System CPython | `Python 3.14.6` |
| Обычный `python` | `Python 3.11.15`; mandatory real-sidecar gate запускался с system CPython 3.14 |
| WebView2 | в реестровом запросе версия не вернулась; process evidence показывает WebView2 `151.0.4129.101` |

Полный исходный вывод `git status --short -uall`, process guard, версии и target-seam status сохранён в [coder_baseline_20260827.txt](coder_baseline_20260827.txt). На baseline были уже dirty modified-файлы и большой untracked WIP; этот WIP не «приводился в порядок» и не перезаписывался.

Исходный process guard обнаружил системные WebView2, Python-сервер Manus и исторические hidden Chrome-процессы предыдущих native-прогонов. Пользовательские/чужие процессы не останавливались. Это важный blocker для честного нового native run.

## 2. Что изменено

| Файл | Назначение правки | Риск / влияние |
|---|---|---|
| `desktop/localcomet-desktop/src-tauri/src/project_intelligence.rs` | Расширен существующий untracked WIP: `localcomet.context-manifest.v2`, bounded heuristic summaries для Rust/TypeScript/Svelte/Python, split `inventory_digest`/`content_digest`/`context_manifest_hash`, provenance, hard budget, fail-closed inventory для unreadable root и symlink traversal, deterministic ranking и regression tests. | Read-only контекстный путь; mutation policy не меняется. Старый API сохранён как compatibility wrapper, новый путь — `try_*` с typed error. Файл был untracked **до** задачи. |
| `tools/run_isolated_hidden_desktop_cu.py` | `_process_present()` больше не принимает наличие одноимённого процесса за доказательство: требует observed PID, принадлежность к descendant tree owned roots и exact image match через PID-filtered `tasklist`. Финальный per-case process evidence теперь содержит observed PID и owned roots. | Усиливает fail-closed acceptance; сценарии с отсутствующим PID теперь остаются `NOT_INDEPENDENTLY_VERIFIED`, а не могут стать зелёными по одному имени процесса. |
| `tests/test_hidden_evidence_contract.py` | Добавлен regression test на owned exact PID, foreign PID и подмену image name. | Только тестовый код. |
| `audit/coder_baseline_20260827.txt` и `audit/*_current_20260827.*` | Воспроизводимые baseline, gate и provenance artifacts. | Диагностические evidence-файлы; raw tokens, cookies и secrets не добавлялись. |

SHA-256 текущих изменённых source/test-файлов:

| Файл | SHA-256 |
|---|---|
| `desktop/localcomet-desktop/src-tauri/src/project_intelligence.rs` | `f9e957161f0915c4824f125358e614d96f48df899514c6eb6b89e26de5e200e3` |
| `tools/run_isolated_hidden_desktop_cu.py` | `911688ec7d486d89f9b2afec336142f2cc3a34417ec4c31ea2e93391c08a1a99` |
| `tests/test_hidden_evidence_contract.py` | `596a52475bfbcd1d5eca084d561044dcba873d87930db53b7a3666aa9e6d33fb` |

## 3. Gap table после read-only audit

| Область | Состояние после среза | Класс доказательства |
|---|---|---|
| Project Intelligence summaries/digests/budget | Реализовано и покрыто Rust unit tests; production command wiring не доказан | A для contract/unit path; G для native product acceptance |
| Native process proof | Harness source усилен exact PID + owned descendant tree | A для offline regression; native повтор не выполнен |
| Browser URL/title/CDP matrix | В текущем source routing browser IDs уже присутствуют; native URL/title run не выполнен | A для contract; `NOT_INDEPENDENTLY_VERIFIED` native |
| Composer readiness/idempotency | В текущем dirty WIP уже есть region gate и same-prompt retry token path; в этом срезе не менялись | B/A по существующим тестам, не native |
| Approval payload/modal | В текущем dirty WIP Rust payload и modal уже содержат authoritative correlation fields; legacy compatibility card остаётся отдельным non-authoritative path | A для текущих source tests; native approval-modal path не выполнен |
| Restart/recovery | Существующий contract code есть, новый real process-boundary restart не выполнялся | A/B contract; native `NOT_INDEPENDENTLY_VERIFIED` |
| Hostile SEC-001…SEC-016 | Отдельный полный corpus run не выполнялся | `NOT_INDEPENDENTLY_VERIFIED` |
| Performance | Не измерялась | `NOT_MEASURED` |
| Legal/provenance | Полный license/provenance audit и release decision не закрыты | Release blocker |

## 4. Research-to-code mapping

В мастер-промпте приведены официальные материалы Aider, Cline, Roo Code, OpenHands, OpenCode, SWE-agent и Goose. В этот срез перенесены только совместимые с LocalComet паттерны; эти проекты не используются как authority для acceptance.

| Источник паттерна | Применение в LocalComet |
|---|---|
| Aider repository map и edit/test loop [1] [2] [3] | `build_repo_map()` теперь учитывает не только path keywords, но также symbols/imports/dependencies; deterministic tie-break сохранён. Auto-commit не добавлялся. |
| Cline checkpoints и scoped approvals [5] | В этом срезе не менялся существующий Rust checkpoint/approval boundary; harness не получает authority из UI. |
| Roo Code per-mode capability ceilings [6] | В этом срезе не вводились новые security boundaries; существующие mode/policy seams оставлены без регрессии. |
| OpenHands bounded context/persistence [7] [8] [9] [10] | Введены bounded summaries, typed budget rejection и manifest provenance; task ledger/recovery не переписывались. |
| OpenCode `allow`/`ask`/`deny` и bounded loop [11] [12] | В harness сохранён fail-closed принцип: отсутствующая независимая requirement не превращается в `VERIFIED_SUCCESS`. |
| SWE-agent transparent loop [13] и Goose declarative packages [14] | В этом срезе напрямую не изменялись; skills/recipes остаются отдельным следующим seam. |

## 5. Гейты

Mandatory environment для Python:

```text
LOCALCOMET_TEST_PROJECT_ROOT=C:\Users\DNS\Documents\LocalComet-build-week-clean
LOCALCOMET_TEST_PYTHON=C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe
LOCALCOMET_REQUIRE_REAL_SIDECAR=1
```

Все команды ниже запускались после финальной правки этого среза. Последние строки приведены дословно по сохранённым gate logs; ANSI-цвета удалены только для читаемости.

### Frontend

| Команда | Exit code | Последние строки |
|---|---:|---|
| `npm run check` из `desktop/localcomet-desktop` | 0 | `svelte-check found 0 errors and 0 warnings`<br>`EXIT_CODE=0` |
| `npm test` из `desktop/localcomet-desktop` | 0 | `Tests 552 passed (552)`<br>`Duration 3.43s (transform 41.40s, setup 0ms, import 50.05s, tests 1.81s, environment 19ms)`<br>`EXIT_CODE=0` |

### Rust

| Команда | Exit code | Последние строки |
|---|---:|---|
| `cargo test --lib -- --test-threads=1` из `desktop/localcomet-desktop/src-tauri` | 0 | `test result: ok. 731 passed; 0 failed; 7 ignored; 0 measured; 0 filtered out; finished in 22.37s`<br>`EXIT_CODE=0` |
| `cargo fmt --all -- --check` | 0 | `EXIT_CODE=0` |
| `cargo clippy --all-targets --all-features -- -D warnings` | 0 | ``Finished `dev` profile [unoptimized + debuginfo] target(s) in 6.39s``<br>`EXIT_CODE=0` |

### Python и real-sidecar

| Команда | Exit code | Последняя строка |
|---|---:|---|
| `python tests/test_check_bundle_parity.py` | 0 | `OK` |
| `python tests/test_evidence_model.py` | 0 | `EXIT_CODE=0` |
| `python tests/test_trust_chain_gate.py` | 0 | `OK` |
| `python tests/test_tool_risk_registry_gate.py` | 0 | `OK` |
| `python tests/test_mockdata_import_gate.py` | 0 | `OK` |
| `python tests/test_trust_chain_invariants.py` | 0 | `OK: 15 trust-chain files pass byte invariants` |
| `python scripts/check_command_parity.py` | 0 | `OK: 79 commands registered and invoked (parity holds)` |
| `python scripts/check_tool_risk_registry.py` | 0 | `OK: 7 console tool function(s) classified (5 mutating, all requiring approval); 11 sidecar tools covered; 21 registry entries valid` |
| `python scripts/check_ui_fake_state.py` | 0 | `OK: no fake-state violations in 114 frontend file(s) (INV-UI-001)` |
| `python scripts/check_mockdata_imports.py` | 0 | `src/lib/stores/shellStore.ts: fallback constants (modeOptions, inspectorSections)`<br>`EXIT_CODE=0` |
| `python scripts/check_bundle_parity.py` | 0 | `OK: 430 shipped module(s) match source across 2 location(s) (bundle parity holds)` |
| `python tools/test_bug1_inference_bundle_parity.py` | 0 | `ALL OK` |
| `python tools/test_adr015_tool_parsing.py` | 0 | `OK (skipped=1)` |
| `python tools/test_tool_risk_rust_parity.py` | 0 | `OK: parser self-tests passed` |
| `python scripts/smoke_test.py --mode=cli` | 0 | `SMOKE PASSED: real sidecar product path behaves as expected.` |
| `python scripts/refresh_evidence.py` | 0 | `evidence refreshed: all gates green` |
| `python scripts/check_evidence_provenance.py` | 0 | `OK: 4 evidence file(s) fresh and intact (tree=08c0ff94e3c7a6fa...)` |
| `python scripts/check_real_sidecar_tests.py` | 0 | `OK: real-sidecar tests ran under require mode with no silent skips` |

Полные логи: [gate_frontend_current_20260827.txt](gate_frontend_current_20260827.txt), [gate_rust_current_20260827.txt](gate_rust_current_20260827.txt), [gate_python_current_20260827.txt](gate_python_current_20260827.txt). В `test_evidence_model.py` намеренные `FAIL:` строки относятся к тестам, которые проверяют обнаружение плохих evidence; итоговый unittest exit code равен 0.

## 6. Native matrix

Новый native hidden run в этой задаче **не запускался**: baseline/current process guard обнаружил системные WebView2, Manus Python/sidecar и исторические hidden Chrome-процессы; пользовательские процессы нельзя было останавливать автоматически. Calculator не запускался.

| Case ID / scenario | Report path | Process identity | Independent postcondition | Cleanup | Verdict |
|---|---|---|---|---|---|
| `NATIVE-MATRIX-20260827` (`notepad`, browser, files, screenshot, restart, negative ownership) | `NOT_CREATED` — harness run не выполнялся | `NOT_MEASURED` | `NOT_MEASURED` | Новый harness-owned process tree не создавался; существующие процессы оставлены нетронутыми | `NOT_INDEPENDENTLY_VERIFIED` |

Исторические native artifacts в `audit/hidden_*` не переклассифицировались и не удалялись. Они остаются historical evidence и не объявляются текущим acceptance.

## 7. Security matrix

Эта matrix фиксирует требуемое protected postcondition и честный статус текущего прогона. Полный hostile corpus в рамках этого среза не выполнялся.

| ID | Требуемое protected postcondition | Текущий статус |
|---|---|---|
| SEC-001 | Web page не может вызвать upload/escalation secret | `NOT_INDEPENDENTLY_VERIFIED` — corpus не запускался |
| SEC-002 | Fake DOM approval не принимается вместо exact correlated control | `NOT_INDEPENDENTLY_VERIFIED` — native path не запускался |
| SEC-003 | Traversal/absolute/drive escape отвергается до I/O | `VERIFIED_SUCCESS` contract-only по существующим Rust/Python gates; hostile matrix не запускалась |
| SEC-004 | Symlink/reparse ledger/workspace/package fail closed | `VERIFIED_SUCCESS` contract-only; native fixture не запускалась |
| SEC-005 | Arbitrary shell/PowerShell/cmd/python/taskkill отвергается | `VERIFIED_SUCCESS` contract-only; full corpus не запускался |
| SEC-006 | Non-allowlisted URL/profile блокируется до navigation | `VERIFIED_SUCCESS` contract-only; browser native proof не запускался |
| SEC-007 | Foreign task/session/workspace/model grant отвергается digest/binding mismatch | `VERIFIED_SUCCESS` contract-only по Rust tests; hostile corpus не запускался |
| SEC-008 | Interior ledger corruption не repair-ится и отображается как corrupt | `VERIFIED_SUCCESS` contract-only; restart fixture не запускалась |
| SEC-009 | Oversized frame/ledger/evidence/context bounded-reject без blow-up | `VERIFIED_SUCCESS` contract/unit-only; native stress не запускался |
| SEC-010 | Prompt injection в Notepad/browser не меняет permission и не передаёт secret | `NOT_INDEPENDENTLY_VERIFIED` — native hostile run не запускался |
| SEC-011 | Matching title/wrong PID не кликается и не закрывается | `VERIFIED_SUCCESS` contract-only для exact-PID regression; native fixture не запускалась |
| SEC-012 | При ошибке первого ordered action последующие не dispatch-ятся | `VERIFIED_SUCCESS` contract-only; hostile matrix не запускалась |
| SEC-013 | Skill archive traversal/compression bomb quarantine/reject | `VERIFIED_SUCCESS` contract-only; archive corpus не запускался |
| SEC-014 | Tampered installed skill SHA mismatch disable/reject | `VERIFIED_SUCCESS` contract-only; native install path не запускался |
| SEC-015 | Headless OAuth/MCP auth получает typed handoff/block, без hang | `NOT_INDEPENDENTLY_VERIFIED` — scenario не запускался |
| SEC-016 | In-flight host action после restart получает pause/review, без replay | `NOT_INDEPENDENTLY_VERIFIED` — real process-boundary restart не запускался |

## 8. Performance и provenance

| Метрика | Результат |
|---|---|
| Model load / model-ready | `NOT_MEASURED` |
| First response / first tool-call latency | `NOT_MEASURED` |
| Action dispatch → observation | `NOT_MEASURED` |
| Screenshot/UIA latency | `NOT_MEASURED` |
| Notepad/browser/files total time | `NOT_MEASURED` |
| Restart recovery time | `NOT_MEASURED` |
| Peak sidecar/native memory | `NOT_MEASURED` |
| Ledger/evidence growth | `NOT_MEASURED` |
| Cancellation → safe state | `NOT_MEASURED` |

Текущий evidence tree после refresh: `08c0ff94e3c7a6fa478e4fd8b9d90237d786f3950711a72c72364a0c16c94563` для 588 source files. Detailed process/source hashes сохранены в [provenance_current_20260827.txt](provenance_current_20260827.txt).

Полный component/license/provenance inventory с source URL, license detection, redistribution/commercial status и owner decisions не закрыт. Unresolved legal/provenance items остаются release blockers; root `LICENSE` молча не добавлялся.

## 9. Что не сделано и почему

Не выполнены native Notepad/browser/files/screenshot/restart matrix, fresh current-source repeats, approval-modal native path, hostile SEC-001…SEC-016 corpus и performance measurements. Причина — process guard обнаружил существующие пользовательские/системные и исторические browser processes, а правила проекта запрещают `taskkill /IM`, остановку чужих процессов, пользовательский Chrome/profile и автоматический cleanup без exact owner manifest.

Project Intelligence v2 в этом срезе остаётся contract-level API: его отдельная Tauri production command/context-manifest consumer не добавлялась, чтобы не расширять IPC surface без отдельного typed approval/context binding решения. Это осознанный remaining gap, а не скрытая claim о production acceptance.

Approval, model lifecycle, task recovery и skills были прочитаны как соседние seams, но без необходимости не переписывались. Существующий dirty WIP в этих файлах сохранён; исторические reports и evidence не удалялись.

## 10. Acceptance score и caps

**Честная текущая оценка: 7.8/10; повышение не применяется.**

Score caps остаются из-за отсутствия класса A для native matrix, отсутствия real restart/recovery proof, отсутствия полного hostile corpus, отсутствия performance measurements, незакрытого legal/provenance inventory и отсутствия production wiring для нового Project Intelligence manifest API. Unit tests, model-ready, открытый порт, UI pill, self-report или один historical native run не используются как основание для 9.5.

Требуемые verdicts соблюдены буквально: `VERIFIED_SUCCESS`, `VERIFIED_BLOCKED`, `VERIFIED_FAILED`, `PENDING_TERMINAL`, `NOT_INDEPENDENTLY_VERIFIED`. Для незапущенной native matrix использован `NOT_INDEPENDENTLY_VERIFIED`, а не optimistic synonym.

## 11. Dashboard proposal

В `Status.md`/`Timeline.md` допустимо добавить только следующие facts: current branch/HEAD, frontend 39 files and 552 tests passed, Rust 731 passed/0 failed/7 ignored, Python mandatory pack exit 0 with real-sidecar require mode, Project Intelligence contract slice with 8 focused Rust tests, and exact-PID process-proof regression with 19 focused Python tests.

Не следует объявлять native acceptance, approval-modal native verification, browser URL/title success, restart safety, performance, legal clearance или score 9.5. Полный historical 20-stage plan, checkpoint и timeline records должны сохраняться без обнуления и удаления.

## References

[1]: https://aider.chat/docs/repomap.html "Aider — Repository map"
[2]: https://aider.chat/docs/more/edit-formats.html "Aider — Edit formats"
[3]: https://aider.chat/docs/usage/lint-test.html "Aider — Linting and testing"
[4]: https://aider.chat/docs/llms.html "Aider — Connecting to LLMs"
[5]: https://docs.cline.bot/features/auto-approve "Cline — Auto Approve & YOLO Mode"
[6]: https://roocodeinc.github.io/Roo-Code/features/custom-modes "Roo Code — Customizing Modes"
[7]: https://docs.openhands.dev/sdk/guides/security "OpenHands — Security & Action Confirmation"
[8]: https://docs.openhands.dev/sdk/guides/convo-persistence "OpenHands — Persistence"
[9]: https://docs.openhands.dev/sdk/guides/context-condenser "OpenHands — Context Condenser"
[10]: https://docs.openhands.dev/sdk/guides/mcp "OpenHands — Model Context Protocol"
[11]: https://opencode.ai/docs/permissions/ "OpenCode — Permissions"
[12]: https://opencode.ai/docs/agents/ "OpenCode — Agents"
[13]: https://swe-agent.com/latest/ "SWE-agent — Getting Started / mini-SWE-agent status"
[14]: https://goose-docs.ai/ "Goose — official overview"
