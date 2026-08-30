# Independent audit отчёта кодера LocalComet

**Дата:** 2026-08-27  
**Объект:** `/home/ubuntu/upload/pasted_content.txt`  
**Каноническая ветка:** `feat/up00-wp01-windows-one-click-launch`  
**HEAD:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`  
**Правило аудита:** unit/contract/source evidence не заменяет native independent postcondition. Используем только статусы `VERIFIED_SUCCESS`, `VERIFIED_BLOCKED`, `VERIFIED_FAILED`, `PENDING_TERMINAL`, `NOT_INDEPENDENTLY_VERIFIED`.

## 1. Краткий вывод

Отчёт кодера **частично подтверждён**. Safe CLI guard launcher действительно реализован, frontend/Rust/Python gates действительно проходят, а новые стабильные selectors в composer и approval UI частично присутствуют. Однако несколько заявлений отчёта сильнее фактического кода.

Самая серьёзная проблема — заявленная approval correlation hardening не доведена до сквозного контракта. Rust event payload не содержит `model_request_id`, `model_action_id` или `input_digest` (`src-tauri/src/approval.rs:112-120`), `ApprovalModal.svelte:175` устанавливает `data-input-digest` в пустую строку при любом условии, а `ApprovalCard.svelte:86` записывает в `data-approval-request-id` значение `expiresAtUnixMs`, а не request ID. Это не косметика: acceptance harness или другой consumer может считать чужой/не тот approval коррелированным.

Вторая серьёзная проблема — harness классифицирует часть browser/generic Computer Use сценариев по слишком слабому условию. `browser_required` включается только для `scenario["id"] == "browser_youtube"` (`run_isolated_hidden_desktop_cu.py:3082-3093`), поэтому `browser_readonly_search` и `browser_second_readonly_search` не требуют URL/title/CDP postcondition. `classify_case()` возвращает `VERIFIED_SUCCESS` для `PASS`, если нет явного false в optional checks (`:2589-2620`). Для сценариев без `text_ok`, `screenshot_ok` или `browser_ok это позволяет PASS без semantic proof.

Третья проблема — `composer_ready()` вычисляет `regionReady`, но не использует его в итоговом условии (`:1875-1893`). Кроме того, `submit_prompt()` создаёт новый случайный idempotency token на каждый вызов (`:1949-1985`); это не защищает от duplicate turn при повторном вызове после неопределённого результата.

**Итоговая рекомендация:** технический baseline остаётся зелёным, но отчёт нельзя принимать как завершение P0-D или как движение к 9/10. Score **оставить 7,8/10**, пока не исправлены approval correlation, semantic classifier и не выполнена свежая native E2E matrix с повторяемыми postconditions.

---

## 2. Что подтверждено независимой проверкой

| Область | Verdict | Проверенный факт |
|---|---|---|
| Launcher `--help`/`--dry-run`/unknown flag | `VERIFIED_SUCCESS` для CLI contract | Независимый запуск system CPython: `--help` exit 0, `--dry-run` exit 0, `--unknown-flag` exit 2; до/после `localcomet-desktop.exe` — 0 процессов. |
| Frontend | `VERIFIED_SUCCESS` для code gates | `npm run check` exit 0; `npm test`: 39 files, 545 tests passed. |
| Rust | `VERIFIED_SUCCESS` для code gates | `cargo test --lib -- --test-threads=1`: 724 passed, 0 failed, 7 ignored; fmt и clippy `-D warnings` exit 0. |
| Python/evidence | `VERIFIED_SUCCESS` для mandatory gates | Независимый pack с system CPython 3.14 и `LOCALCOMET_REQUIRE_REAL_SIDECAR=1` завершён marker `ALL_INDEPENDENT_AUDIT_GATES_EXIT_0`; refresh/provenance tree `aa246c0fdd3bf011...`. |
| Launcher source order | `VERIFIED_SUCCESS` для конкретного guard | `_handle_launcher_cli_args()` вызывается в `main()` до `ensure_runtime_python`, `synchronize_runtime` и `launch_localcomet` (`tools/launch_localcomet_dev.py:1271-1275`). |
| Composer stable selectors | `VERIFIED_SUCCESS` только как source contract | `MessageComposer.svelte` содержит stable `data-testid`/`data-lc`, реальный Svelte binding сохранён. Native submit не доказан. |
| Historical Notepad | `VERIFIED_SUCCESS` исторически, но не current acceptance | В `audit/hidden_20260826_notepad_open_type` есть UIA marker/readback evidence; это один старый run в `session_capability` mode, не две свежие current-source повторы. |

### Дословные независимые gate facts

- Frontend: `CHECK_EXIT=0`; `TEST_EXIT=0`; `Test Files 39 passed (39)`; `Tests 545 passed (545)`.
- Rust: `test result: ok. 724 passed; 0 failed; 7 ignored`.
- Python: `evidence refreshed: all gates green`; `OK: 4 evidence file(s) fresh and intact`; final marker `ALL_INDEPENDENT_AUDIT_GATES_EXIT_0`.
- Current status после аудита: branch canonical; `STATUS_RECORDS=722`, `TRACKED=62`, `UNTRACKED=660`; latest process check `LOCALCOMET_PROCESS_COUNT=0`.

---

## 3. Критические findings

### FINDING-001 — Approval UI correlation фактически не сквозная

**Severity:** P0 security/reliability.  
**Status:** `VERIFIED_FAILED` для заявленного P0-D.8 contract; не означает, что весь approval broker сломан.

**Доказательства:**

1. Rust `ApprovalRequestPayload` содержит только `request_id`, `tool`, `risk_level`, `target_summary`, `side_effect_category`, `destructive` (`src-tauri/src/approval.rs:112-120`). В нём нет `model_request_id`, `model_action_id` или `input_digest`.
2. `ApprovalModal.svelte:170-175` добавляет stable attributes, но `data-input-digest={currentRequest.target_summary ? '' : ''}` всегда пустой.
3. `ApprovalCard.svelte:84-86` содержит `data-approval-request-id={approval?.expiresAtUnixMs ? String(approval.expiresAtUnixMs) : ''}`. Timestamp expiration не является approval request ID.
4. Текущие frontend approval tests проверяют invoke/store flow, но не DOM rendering этих attributes. Source-string selector test не обнаруживает неправильное значение.

**Impact:** generic selector может найти элемент с `data-approval-request-id`, но correlation с реальным request не доказана; digest attribute даёт ложную видимость evidence. В modal и card существуют разные state paths, и ни один не подтверждает полный server-authenticated tuple.

**Что принять:** только после typed server→frontend payload, server-computed digest, корректного request ID в обоих UI paths, отсутствие raw token, component/DOM tests и negative test на чужой approval.

### FINDING-002 — Browser semantic acceptance routing неполная

**Severity:** P0 acceptance integrity.  
**Status:** `VERIFIED_FAILED` для claim, что browser readonly scenario уже защищён URL/title postcondition.

**Доказательства:**

- `SCENARIO_EXPECTED_PROCESS` содержит `browser_readonly_search` и browser process, но `browser_required = scenario["id"] == "browser_youtube"` (`run_isolated_hidden_desktop_cu.py:3082-3093`). Поэтому readonly search не вызывает `browser_youtube_evidence()`.
- `browser_second_readonly_search` вообще не имеет browser-specific required check.
- Historical artifact `audit/hidden_20260827_browser_readonly_search/isolated_hidden_user_runs.jsonl` классифицирован `VERIFIED_SUCCESS`, но action был только `{"action":"open app","target":"chrome"}`, `browser_evidence.status` — `not_required`, `browser_url` и `browser_cdp_port` пустые.

**Impact:** открытие приложения и наличие любого `chrome.exe` могут попасть в PASS, хотя URL/title/navigation/search не доказаны. Это false-positive acceptance, не просто недостающий тест.

### FINDING-003 — Generic classifier допускает PASS без обязательного semantic proof

**Severity:** P0 acceptance integrity.  
**Status:** `VERIFIED_FAILED` для сильного claim native action verification.

`classify_case()` возвращает `VERIFIED_SUCCESS`, когда `pill == "PASS"`, process не равен `False`, correlation true и optional checks не равны `False`. Для generic scenarios `process_present` часто `None`, а `text_ok`, `screenshot_ok` и `browser_ok` не заданы. В результате PASS card может стать `VERIFIED_SUCCESS` без доказательства, что модель выполнила заявленный click, type, hotkey, drag, wait или search.

Отдельно `_process_present()` использует `tasklist` и проверяет только имя image (`:2440-2453`), а не manifest-owned PID, process creation identity и hidden desktop. Наличие пользовательского `chrome.exe`/`explorer.exe` не доказывает, что процесс создан текущим harness.

**Требование:** перейти от optional booleans к declarative `ScenarioRequirement`, где semantic postcondition обязательна для каждого scenario ID. `None` при required proof должен вести к `NOT_INDEPENDENTLY_VERIFIED`, а не к PASS.

### FINDING-004 — `composer_ready()` игнорирует model region readiness

**Severity:** P1 reliability, потенциально P0 для acceptance.  
**Status:** `VERIFIED_FAILED` для claim строгой readiness.

В `composer_ready()` вычисляется:

```javascript
const regionReady = !stableRegion || stableRegion.getAttribute('data-model-status') === 'ready';
```

но return содержит только `{edit, send, regionReady}`, а Python-условие на `:1890-1893` проверяет только `edit` и `send`. Таким образом `regionReady=false` не блокирует дальнейший flow. Сейчас textarea обычно disabled до model ready, но это случайная косвенная защита, а не соблюдённый contract.

### FINDING-005 — Idempotency token не защищает retry

**Severity:** P1 reliability.  
**Status:** `NOT_INDEPENDENTLY_VERIFIED`; implementation claim overstated.

`submit_prompt()` создаёт `token = f"lc-submit-{uuid.uuid4().hex}"` при каждом вызове. `window.__lcSubmitTokens` помечает token после click, но следующий retry получает новый token и может снова click Send. Тест `test_duplicate_submission_token_differs_between_prompts` проверяет, что разные prompts получили разные tokens; он не проверяет uncertain-click/retry одного и того же prompt и не доказывает отсутствие duplicate turn.

Нужен case-level idempotency key, сохраняемый до подтверждения нового turn/card, плюс retry state machine: после uncertain click сначала искать correlated new turn, а не сразу выполнять второй click.

### FINDING-006 — Approval correlation native path фактически не выполняется

**Severity:** P0 acceptance gap.  
**Status:** `NOT_INDEPENDENTLY_VERIFIED`.

В native hidden harness guarded scenarios используют explicit session capability, после чего `approval_required = False` и `authorization_mode = "session_capability"` (`run_isolated_hidden_desktop_cu.py:3066-3073`). Это допустимый отдельный режим, но он не доказывает user approval modal path. Поэтому stable attributes approval modal/card нельзя объявлять native-tested только из session-capability run.

### FINDING-007 — Contract PASS смешан с acceptance PASS

**Severity:** P1 reporting integrity.  
**Status:** `VERIFIED_FAILED` для формата acceptance matrix.

В отчёте используются статусы вроде `VERIFIED_SUCCESS (contract)` и `VERIFIED_SUCCESS (partial)`, хотя master-prompt закрепляет ровно пять verdicts и требует отделять code/contract verification от native independent acceptance. `AC-013`, `AC-014`, `AC-015`, `AC-016`, `AC-022`, `AC-030`, `AC-040`, `AC-042` должны иметь отдельную колонку `contract_status=PASS`, но native verdict оставаться `NOT_INDEPENDENTLY_VERIFIED`, пока соответствующее postcondition не выполнено в production path.

Особенно проблемен `AC-040`: root LICENSE и third-party/model/voice provenance unresolved, поэтому `VERIFIED_SUCCESS (partial)` нельзя использовать для release provenance. Это должен быть `NOT_INDEPENDENTLY_VERIFIED` плюс release blocker.

### FINDING-008 — Baseline отчёта внутренне противоречив

**Severity:** P1 reproducibility.  
**Status:** `VERIFIED_FAILED` для reproducible baseline claim.

В начале отчёта указано `58 tracked + 660 untracked` и одновременно «совпадает с 717 грязных, 58 tracked/659 untracked». Арифметика не сходится: 58+660=718. Независимый post-audit snapshot показал `722 records: 62 tracked, 660 untracked`, branch/HEAD совпадают, native process count — 0. Это не доказывает вредных source changes, но baseline обязан быть точным и снабжаться timestamp/command output.

### FINDING-009 — Historical browser artifact нельзя считать URL acceptance

**Severity:** P0 evidence quality.  
**Status:** `VERIFIED_FAILED` для конкретного historical browser evidence.

`hidden_20260827_browser_readonly_search` содержит final classification `VERIFIED_SUCCESS`, но `browser_evidence.status=not_required`, URL/title/CDP пустые, action — только `open app chrome`. Это должно быть переклассифицировано как `NOT_INDEPENDENTLY_VERIFIED` или как отдельный `VERIFIED_SUCCESS` только для `open_app`, но не для browser URL/search scenario.

---

## 4. Что не следует считать проблемой

Safe launcher guard — реальное полезное изменение. Проверка до `ensure_runtime_python` и независимый CLI rerun подтверждают, что `--help`/`--dry-run` не запускают native app. Это улучшение нужно сохранить.

Stable composer selectors — хорошая подготовка к deterministic harness, но это только contract. `npm test` и `svelte-check` зелёные, однако текущие tests в основном source/store-level; они не доказывают, что живой WebView2 отправляет prompt и получает новый correlated turn.

Historical Notepad artifact не нужно удалять или объявлять бесполезным. Он является сильным историческим UIA proof в `session_capability` mode, но не заменяет две свежие current-source повторы и не доказывает modal approval path.

---

## 5. Итоговая классификация отчёта

| Блок | Итог |
|---|---|
| CLI safety improvement | Принять как `VERIFIED_SUCCESS` для ограниченного launcher contract |
| Frontend/Rust/Python gates | Принять как `VERIFIED_SUCCESS` для текущего code gate snapshot |
| Stable composer attributes | `VERIFIED_SUCCESS` только contract-level |
| Approval correlation hardening | `VERIFIED_FAILED` — payload/digest/card ID не соответствуют claim |
| Browser readonly native acceptance | `NOT_INDEPENDENTLY_VERIFIED`; один historical artifact слабый и misclassified |
| Generic CU semantic verification | `NOT_INDEPENDENTLY_VERIFIED` до classifier/harness fix |
| Native model-driven loop | `NOT_INDEPENDENTLY_VERIFIED` |
| Native restart/recovery | `NOT_INDEPENDENTLY_VERIFIED` |
| Coding behavior verification | `NOT_INDEPENDENTLY_VERIFIED` |
| Hostile corpus | `NOT_INDEPENDENTLY_VERIFIED` для 9/12 cases |
| Performance | `NOT_MEASURED` как measurement label; native acceptance verdict не выдавать |
| Legal/provenance | Release blocker; не clearance |
| Score | **7.8/10**, не 7.9 и не 9/10 |

---

## 6. Обязательный порядок исправлений

1. Исправить server-authenticated approval correlation: Rust payload → typed frontend state → modal/card attributes → component tests → negative foreign-approval test.
2. Ввести declarative semantic requirements для harness и запретить PASS без required postcondition. Исправить browser IDs и owner-scoped process proof.
3. Исправить `composer_ready()` и case-level retry idempotency; добавить regression tests.
4. Не менять acceptance verdictы на optimistic status; отделить `contract_status` от native verdict.
5. Запустить два свежих isolated current-source прогона Notepad, browser URL/title, fixture files, screenshot и cleanup; Calculator не запускать.
6. Провести native Tauri/sidecar restart recovery с `paused_for_review`, no replay и новым approval/continuation ID.
7. Провести hostile SEC-001..012 и performance JSON с реальными `n/p50/p95/max`.
8. Обновить evidence tree и dashboard только после свежего mandatory pack и provenance check.

## References

[1]: https://developers.openai.com/api/docs/guides/tools-computer-use — OpenAI Computer Use guidance on isolated environments, ordered action loop and post-action verification.

[2]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool — Anthropic Computer Use guidance on ordered actions, halting and confirmation boundaries.

[3]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview — Microsoft UI Automation control patterns and observable control capabilities.

[4]: https://learn.microsoft.com/en-us/microsoft-edge/webview2/how-to/webdriver — Microsoft WebView2 automation and exact target attachment guidance.

[5]: https://osworld-v1.xlang.ai/ — OSWorld execution-based desktop evaluation.

[6]: https://www.nist.gov/itl/ai-risk-management-framework — NIST AI Risk Management Framework.
