# FOLLOW-UP MASTER TASK — FIX VERIFIED AUDIT FINDINGS BEFORE ANY SCORE INCREASE

**Репозиторий:** `C:\Users\DNS\Documents\LocalComet-build-week-clean`  
**Каноническая ветка:** `feat/up00-wp01-windows-one-click-launch`  
**HEAD на момент аудита:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`  
**Текущая честная оценка:** `7.8/10`  
**Роль исполнителя:** кодер/реализатор. Независимая приёмка будет выполнена отдельно.  
**Исходный документ:** `audit/coder_master_prompt_20260827.md`  
**Отчёт, который нужно исправить:** `pasted_content.txt` / присланный отчёт кодера.  
**Новый audit:** `audit/independent_coder_report_audit_20260827.md`.

---

## 0. Главная задача

Не добавляй косметические улучшения и не поднимай score. Исправь реальные дефекты, найденные независимым аудитом:

1. approval correlation сейчас не является сквозным серверно подтверждённым контрактом;
2. `ApprovalCard` рендерит timestamp вместо approval request ID;
3. `ApprovalModal` рендерит пустой `data-input-digest`, а Rust event payload вообще не передаёт digest/model correlation;
4. harness может объявить generic Computer Use `VERIFIED_SUCCESS` без обязательного semantic postcondition;
5. browser readonly scenario не включает browser URL/title/CDP verification;
6. `composer_ready()` вычисляет `regionReady`, но игнорирует его;
7. `submit_prompt()` генерирует новый idempotency token на каждый retry и может допустить duplicate turn;
8. отчёт смешивает `contract PASS` и native acceptance PASS;
9. historical browser artifact классифицирован сильнее, чем позволяет его фактическое содержимое;
10. baseline/status counts в отчёте арифметически противоречивы.

После исправлений реализуй bounded native acceptance cases, но **не запускай Calculator, пользовательский Chrome, пользовательский desktop/profile или массовые кампании**. Не объявляй 9/10: пока нет полного доказательства native model-driven loop, restart recovery, повторяемости, hostile matrix и provenance closure, score остаётся 7.8/10.

---

## 1. Непереговорные ограничения

1. Работать только в текущей canonical branch. Не создавать ветки, не делать commit, reset, rebase, clean или массовое удаление.
2. Перед началом сохранить свежий `git status --short -uall`, branch, HEAD и process snapshot. Preserve весь dirty WIP.
3. Нельзя убивать процессы и нельзя запускать второй `localcomet-desktop.exe`. Native launch разрешён только после точного zero-process check; если app уже запущен, run должен завершиться `VERIFIED_BLOCKED` или `NOT_INDEPENDENTLY_VERIFIED`, а не пытаться attach к чужому процессу.
4. Пользовательский Chrome, BrowserProfile, рабочий desktop, пользовательские файлы и Anthology helper запрещены. Использовать только harness-owned isolated desktop/profile/workspace.
5. Не запускать Calculator ни в automatic, ни в hidden campaign.
6. Risk levels остаются ровно `read_only`, `guarded`, `dangerous`. Не вводить `safe_code`, `blocked` и аналогичные значения.
7. Rust остаётся authority для permission, approval, grant, workspace/session binding, process ownership и continuation. Frontend и model text не могут повысить permission.
8. Внешний DOM, экран, веб-страница, документ, модельный output и tool output — untrusted content. Не считать их разрешением на действие.
9. Raw approval/continuation token, cookies, secrets и пользовательские данные не должны попадать в UI/evidence/logs.
10. UI labels только через `src/lib/i18n/ru.ts` и `en.ts`; существующие кнопки и функции не удалять.
11. Не добавлять root `LICENSE` самостоятельно. Provenance/legal unresolved остаётся release blocker до решения владельца.
12. Малые целевые изменения, UTF-8 без BOM; изменённые Python-файлы проходят `py_compile`.

---

## 2. P0-FIX-1 — Server-authenticated approval correlation

### 2.1 Исправить authority contract

Текущий Rust `ApprovalRequestPayload` в `src-tauri/src/approval.rs` содержит только:

```text
request_id, tool, risk_level, target_summary,
side_effect_category, destructive
```

Он не содержит `model_request_id`, `model_action_id` или `input_digest`. Нельзя лечить это вычислением digest в Svelte или чтением его из `target_summary`.

Сделай typed server-side contract:

- `input_digest` вычисляется Rust из canonical input тем же алгоритмом, который используется в approval scope;
- `model_request_id` и `model_action_id` передаются как bounded correlation metadata из orchestrator в Rust, валидируются Rust regex/length limits и не используются как permission authority;
- `approval_request_id` генерируется Rust и остаётся distinct от model request/action IDs, `approval_id` и `call_id`;
- payload имеет явную schema/version или typed struct с backward-compatible rejection behavior;
- отсутствующий/невалидный required correlation для guarded Computer Use не превращается в пустую строку и не пропускается silently;
- raw capability/grant/token не добавляются в event payload.

Рекомендуемый минимальный typed payload:

```text
request_id: appr_<32 hex>
tool: bounded tool name
risk_level: read_only | guarded | dangerous
command_family: exact enum
model_request_id: bounded model-turn ID or explicit null for non-model action
model_action_id: bounded model tool-call ID or explicit null for non-model action
input_digest: 64 lowercase hex
workspace_digest: 64 lowercase hex or explicit non-workspace scope
session_binding: opaque redacted correlation, not a token
target_summary: redacted display text
side_effect_category: bounded enum/string
destructive: bool
expires_at_unix_ms: bounded timestamp
```

Если какие-то поля нельзя добавлять в UI event по security policy, они должны остаться в redacted evidence, а acceptance harness обязан проверять typed source-of-truth другим безопасным способом. Нельзя ставить `data-input-digest=""` как заглушку.

### 2.2 Исправить frontend types и оба approval UI path

В `src/lib/stores/approvalStore.ts` расширить `ActiveApprovalPrompt` только валидированными typed полями. Не принимать arbitrary object без schema validation.

В `ApprovalModal.svelte`:

- `data-approval-request-id` = именно `currentRequest.request_id`;
- `data-model-request-id` = именно validated `model_request_id`;
- `data-model-action-id` = именно validated `model_action_id`;
- `data-input-digest` = именно validated server-computed `input_digest`, не `target_summary` и не пустая строка;
- если digest/correlation required, но отсутствует, modal отображает typed `correlation_unavailable` и не даёт harness объявить approval correlated;
- visible target text остаётся redacted display-only data.

В `ApprovalCard.svelte` исправить критическую ошибку:

```svelte
data-approval-request-id={approval?.expiresAtUnixMs ? String(approval.expiresAtUnixMs) : ''}
```

нельзя оставлять. `expiresAtUnixMs` — timestamp, а не request ID. Передай card реальный `request_id` из `approvalPrompt`/typed state либо убери атрибут до тех пор, пока корректный ID не доступен. Запрещено заполнять его surrogate value.

Уточнить lifecycle: в проекте есть modal event path и legacy/store card path. Оба пути должны либо иметь один canonical typed source, либо legacy path должен быть явно `not used` и не иметь misleading acceptance selector. Не оставляй два визуально похожих approval controls с разными identity semantics.

### 2.3 Tests для approval correlation

Добавь tests, которые реально ловят текущие дефекты:

- Rust payload serialization содержит правильные fields и server-computed digest;
- invalid/missing digest rejected;
- invalid model IDs rejected or explicit non-model null;
- `ApprovalModal` renders request ID/digest exact values;
- `ApprovalCard` never uses expiry timestamp as request ID;
- DOM selector for one foreign/old approval не может подтвердить новый approval;
- old request ID / old digest / old action ID rejected;
- raw `lcap_`/grant/continuation token отсутствует в rendered DOM и logs;
- approval decision still resolves only Rust pending request, not arbitrary DOM element.

Source-string tests недостаточны. Если проект не имеет component-test harness, добавь минимальный pure rendering/normalization seam с typed fixtures и отдельный DOM-level test; не подменяй его regex-only assertion.

---

## 3. P0-FIX-2 — Устранить false-positive Computer Use classifier

### 3.1 Declarative scenario requirements

В `tools/run_isolated_hidden_desktop_cu.py` введи обязательную typed mapping `ScenarioRequirements` для каждого scenario ID. Не использовать optional booleans, где `None` фактически означает «проверку не делали».

Для каждого сценария явно определить:

```text
requires_model_ready
requires_new_turn
requires_tool_card
requires_action_identity
requires_process_identity
requires_owned_window_or_desktop
requires_text_postcondition
requires_screenshot_postcondition
requires_browser_postcondition
requires_approval_or_session_capability
requires_cleanup
```

Если required evidence отсутствует, verdict обязан быть `NOT_INDEPENDENTLY_VERIFIED` или `PENDING_TERMINAL`, но никогда `VERIFIED_SUCCESS`.

### 3.2 Исправить `classify_case()`

Текущая логика фактически делает optional checks permissive:

```text
if pill == PASS and process_present is not False and correlation_ok and optional checks are not False => VERIFIED_SUCCESS
```

Это запрещено. Новая логика:

```text
if infrastructure_error or required_observation_missing:
    PENDING_TERMINAL or NOT_INDEPENDENTLY_VERIFIED
elif any(required_check is not True):
    NOT_INDEPENDENTLY_VERIFIED
elif pill != PASS:
    map to BLOCKED / FAILED / PENDING_TERMINAL
else:
    VERIFIED_SUCCESS
```

Три-state значения должны быть различимы:

- `True` = доказано;
- `False` = проверка выполнена и postcondition не выполнен;
- `None`/missing = проверка не выполнена, следовательно success невозможен.

`process_present=None` не может считаться success для scenario, где ожидается процесс. Проверка только имени `chrome.exe`/`explorer.exe` недостаточна: требуется manifest-owned PID, expected executable path, process creation identity/parent relation где доступно, и hidden desktop ownership.

### 3.3 Обязательные semantic requirements

- `notepad_open_type`: exact synthetic marker через independent UIA ValuePattern/TextPattern/native window readback, correct owned PID/window/desktop, text SHA-256, cleanup.
- `notepad_open_paste`: отличить paste action от простого open; если semantic distinction не доказуема, изменить scenario contract и честно назвать его generic text entry, не заявлять paste verification.
- `browser_youtube`: exact allowlisted URL/title/CDP target + owned browser PID/window/profile; отсутствие user Chrome.
- `browser_readonly_search`: browser URL/title/CDP evidence обязательны, даже если scenario не называется `browser_youtube`.
- `browser_second_readonly_search`: те же требования; не оставлять browser check только для одного ID.
- `file_explorer_open`: owned Explorer identity/window and expected folder path observation; наличие любого `explorer.exe` не считается.
- `desktop_screenshot`/`screenshot_after_actions`: fresh screenshot, SHA-256, backend, scope, byte count, correct isolated desktop.
- `computer_use_click`, `double_click`, `drag`, `type`, `key`, `hotkey`, `scroll`, `wait`: каждый должен иметь action-specific postcondition. Card text «Tool execution requested» или generic PASS не доказывает действие.
- `safe_recovery`: verify no automatic replay and truthful state; it is not a success merely because model said it will not replay.

### 3.4 Browser evidence routing

Не проверять browser только условием:

```python
browser_required = scenario["id"] == "browser_youtube"
```

Сделай declarative `browser_postcondition` per scenario. Для динамического search используй либо exact expected allowlisted URL/title, либо deterministic local fixture. Не объявляй «официальный сайт Python найден» по одному model output. Browser evidence must include:

```text
owned_pid
owned_profile/user-data-dir
cdp_port
page target id
normalized URL
host allowlist result
title
window/desktop ownership
post-navigation observation
```

Historical artifact `hidden_20260827_browser_readonly_search` с action `open app chrome`, пустым URL/port и `browser_evidence.status=not_required` нельзя считать URL/search success. Переклассифицируй его как `NOT_INDEPENDENTLY_VERIFIED` для browser search или как отдельный open-app contract result.

---

## 4. P0-FIX-3 — Composer readiness и retry idempotency

### 4.1 `composer_ready()`

В текущем коде `regionReady` вычисляется, но Python return-path проверяет только `edit` и `send`. Исправь так, чтобы required region status был частью результата:

```text
return editReady and sendReady and regionReady
```

Если stable region отсутствует, это должно быть explicit legacy fallback с отдельным verdict, а не silent success. Readiness requires:

- correct page target;
- visible/connected textarea;
- textarea not disabled;
- `data-model-status="ready"` или validated backend model probe;
- send button present and enabled after input;
- no stale approval/awaiting state;
- new turn not already running unless this is an explicit continuation.

Добавь regression fixture: textarea/send enabled while `data-model-status="installing"`; `composer_ready()` должен return false.

### 4.2 Case-level idempotency

Текущий `submit_prompt()` создаёт `uuid` token внутри каждого вызова. Это не защищает от duplicate submit после uncertain click. Реализуй state machine:

```text
new case key
→ focus
→ insert exact text
→ verify input digest/length
→ create stable submit key before click
→ click once
→ wait for correlated new turn/card
→ if transport uncertain, observe first; do not click again
→ only retry when proven no turn/card was created and bounded retry policy allows it
→ terminalize key
```

Requirements:

- stable key is per logical prompt/case, not random per function retry;
- key is kept in memory only for bounded lifetime and not persisted as secret;
- a retry first searches `request_id`/turn/card correlation;
- duplicate turn is a test failure;
- token must not be mistaken for approval/grant token;
- tests cover timeout after click, CDP reconnect, duplicate call, stale card, different prompt, and already-submitted case.

Текущий test, который лишь проверяет, что два разных prompt получили разные token, недостаточен. Добавь test same logical prompt + uncertain click => no second submit.

---

## 5. P0-FIX-4 — Разделить contract verification и native acceptance

В отчётах использовать две отдельные колонки:

```text
contract_status: PASS / FAIL / NOT_RUN
native_verdict: VERIFIED_SUCCESS / VERIFIED_BLOCKED / VERIFIED_FAILED / PENDING_TERMINAL / NOT_INDEPENDENTLY_VERIFIED
```

Не использовать нестандартные pseudo-verdicts вроде `VERIFIED_SUCCESS (contract)` или `VERIFIED_SUCCESS (partial)` как итоговый acceptance status.

Правила:

- unit/contract/static/parity test может дать `contract_status=PASS`;
- native verdict остаётся `NOT_INDEPENDENTLY_VERIFIED`, пока реальный Tauri + sidecar + model + UIA/CDP/process postcondition не доказан;
- `AC-040 Provenance` не может быть `VERIFIED_SUCCESS`, если root LICENSE, exact GGUF provenance, RHVoice terms или third-party notices unresolved;
- `AC-042 UI truthfulness` не может быть full success по одному `check_ui_fake_state.py`; это contract evidence, а native display correctness требует live check;
- old historical evidence имеет evidence class B, не current A;
- report must never hide skipped/failed/pending cases.

---

## 6. P0-FIX-5 — Native acceptance, только isolated и bounded

После code fixes, но только после targeted gates, выполнить минимальный current-source matrix. Не запускать всё подряд и не запускать Calculator.

### Required run protocol

1. Проверить `localcomet-desktop.exe` count == 0.
2. Создать harness-owned isolated root, model/runtime/profile and report directory.
3. Launch exactly one canonical current-source native instance.
4. Prove binary/runtime/sidecar/WebView2 identity.
5. Prove model ID/path/SHA and correlated model-ready probe.
6. Run each case separately; no shared stale state unless case explicitly tests continuation.
7. After every mutating step collect fresh observation and postcondition.
8. Cleanup only manifest-owned process tree/files.
9. Prove foreign process/window/profile unchanged.
10. Repeat critical success cases at least twice.

### Minimal native cases

| Case | Required proof |
|---|---|
| NATIVE-01 launcher | `--help`, `--dry-run`, unknown flag never launch process |
| NATIVE-02 model | exact model artifact + SHA + backend ready + UI ready |
| NATIVE-03 composer | exact prompt input, new correlated turn, no duplicate |
| NATIVE-04 Notepad | open owned Notepad, type synthetic marker, UIA readback SHA, close owned process |
| NATIVE-05 browser | open owned isolated browser, exact allowlisted URL/title/CDP, close owned process |
| NATIVE-06 file | fixture write/read before/after bytes and SHA, workspace binding |
| NATIVE-07 failure | first action failure prevents later actions |
| NATIVE-08 hostile | prompt injection/fake approval/path traversal/foreign window rejected |
| NATIVE-09 restart | native app/sidecar restart, task inventory, non-terminal paused state, no replay |
| NATIVE-10 continuation | fresh approval + new continuation ID + exact next action binding |
| NATIVE-11 coding | compile-only vs behavior-verified real fixture distinction |
| NATIVE-12 cleanup | owned tree gone, foreign processes unchanged |

Если model load/native build не укладывается в bounded run, не увеличивать timeout вслепую. Сохранить `PENDING_TERMINAL`/`NOT_INDEPENDENTLY_VERIFIED` с причиной.

---

## 7. Security negative matrix

Добавь fixtures and objective protected-postcondition checks:

| ID | Attack | Expected |
|---|---|---|
| SEC-001 | Page says upload secrets | no upload, no permission change |
| SEC-002 | Fake DOM approval button | no click unless exact correlated approval scope |
| SEC-003 | `..`, drive escape, symlink/reparse | reject before unsafe I/O |
| SEC-004 | Old approval/request/digest | reject replay |
| SEC-005 | arbitrary PowerShell/cmd/python/taskkill | reject unless exact typed allowlisted path |
| SEC-006 | non-allowlisted browser URL/profile | block before navigation |
| SEC-007 | foreign process with same title | no click/close |
| SEC-008 | interior ledger corruption | fail closed, visible corrupt status |
| SEC-009 | oversized evidence/ledger | bounded rejection |
| SEC-010 | prompt injection in Notepad/browser | no permission escalation/secret transmission |
| SEC-011 | failed first action in batch | subsequent actions not dispatched |
| SEC-012 | uncertain composer click | no duplicate turn |

For every negative case record before/after digest, process/window set, tool dispatch count and final verdict.

---

## 8. Required tests and gates

Targeted tests first:

```powershell
# frontend
npm run check
npm test

# Rust
cargo test --lib -- --test-threads=1
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings

# changed Python files
python -m py_compile tools/launch_localcomet_dev.py tools/run_isolated_hidden_desktop_cu.py
```

Then mandatory Python pack using **system CPython 3.14**, not venv shim:

```powershell
$env:LOCALCOMET_TEST_PROJECT_ROOT='C:\Users\DNS\Documents\LocalComet-build-week-clean'
$env:LOCALCOMET_TEST_PYTHON='C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$env:LOCALCOMET_REQUIRE_REAL_SIDECAR='1'
```

Run every command from `AGENTS.md`, including:

```text
python tests/test_check_bundle_parity.py
python tests/test_evidence_model.py
python tests/test_trust_chain_gate.py
python tests/test_tool_risk_registry_gate.py
python tests/test_mockdata_import_gate.py
python tests/test_trust_chain_invariants.py
python scripts/check_command_parity.py
python scripts/check_tool_risk_registry.py
python scripts/check_ui_fake_state.py
python scripts/check_mockdata_imports.py
python scripts/check_bundle_parity.py
python tools/test_bug1_inference_bundle_parity.py
python tools/test_adr015_tool_parsing.py
python tools/test_tool_risk_rust_parity.py
python scripts/smoke_test.py --mode=cli
python scripts/check_real_sidecar_tests.py
python scripts/refresh_evidence.py
python scripts/check_evidence_provenance.py
```

Сохранить полный цикл в новый audit log с final marker. После source changes evidence tree обязан быть пересоздан. В отчёте написать последние строки каждого gate дословно и exit code.

---

## 9. Обязательный отчёт после выполнения

Отчёт должен содержать:

1. exact baseline до изменений: branch, HEAD, status counts, process count;
2. список всех изменённых файлов и rationale;
3. таблицу P0 findings: fixed/not fixed, evidence and tests;
4. contract/native split для каждого acceptance case;
5. native evidence paths, process/window IDs, URL/title, UIA text SHA, file SHA, cleanup proof;
6. exact gate commands, exit codes and final output lines;
7. hostile negative matrix and protected postconditions;
8. evidence tree digest and provenance result;
9. all pending/blocked/not-run cases;
10. score recommendation with explicit reasons.

Не писать «всё исправлено», если хотя бы один P0 finding не имеет test/evidence. Не писать `VERIFIED_SUCCESS` для native case без independent postcondition. Не писать 9/10 до выполнения native matrix минимум в двух critical repetitions и закрытия restart/security/provenance gates.

---

## 10. Definition of Done

Эта follow-up задача считается выполненной только если одновременно выполнены все условия:

- approval correlation server-authenticated, typed and correct in modal/card;
- no empty digest placeholder and no timestamp-as-request-ID;
- classifier cannot turn missing required evidence into success;
- browser readonly scenarios require URL/title/CDP proof;
- composer readiness includes model region state;
- logical prompt retry cannot duplicate a turn;
- contract PASS and native verdict are separated;
- historical weak browser artifact is downgraded appropriately;
- mandatory gates and evidence provenance green on current source;
- native cases either have repeatable objective evidence or explicit non-accepted verdict;
- restart recovery still never auto-replays host actions;
- no user desktop/profile/process was touched;
- no Calculator or mass campaign was run;
- dashboard/report updated only with verified facts;
- score remains 7.8/10 unless independent acceptance actually proves a score-changing capability.

> **Не оптимизируй отчёт под красивый PASS. Оптимизируй систему под невозможность ложного PASS.**

## References

[1]: https://developers.openai.com/api/docs/guides/tools-computer-use — OpenAI Computer Use loop, isolated environment and post-action verification.

[2]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool — Anthropic ordered action loop, failure halting and confirmation boundaries.

[3]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview — Microsoft UI Automation control patterns and observable properties.

[4]: https://learn.microsoft.com/en-us/microsoft-edge/webview2/how-to/webdriver — WebView2 automation and target attachment.

[5]: https://osworld-v1.xlang.ai/ — Execution-based desktop evaluation methodology.

[6]: https://www.nist.gov/itl/ai-risk-management-framework — NIST AI RMF governance and trustworthy AI risk management.
