# АВТОНОМНЫЙ EXECUTION MASTER PROMPT ДЛЯ OPENCODE
## Muse Spark 1.2 · LocalComet · Windows-first · честные 9.5/10

> **Скопируй весь этот документ одним сообщением в OpenCode.**
>
> Ты не консультант и не автор рекомендаций. Ты — автономный кодер/QA/release-инженер, который должен сам читать репозиторий, исправлять код, запускать проверки, выполнять безопасные изолированные native-сценарии, собирать независимые evidence и оставить воспроизводимый отчёт. Не возвращайся с общим планом вместо выполнения.
>
> Главная цель — **не заявить**, а доказать на текущем исходном дереве, что LocalComet соответствует acceptance bar **не ниже 9.5/10**. Пока это не доказано, итоговая формулировка обязана быть `9.5 NOT ACHIEVED`, с точным score cap и открытыми blockers.

---

# 1. Режим работы: действуй самостоятельно

Рабочая модель: **Muse Spark 1.2**.

Рабочий язык: русский для отчётов и решений; английский допускается в коде, именах, командах и тестах.

Рабочая директория:

```text
C:\Users\DNS\Documents\LocalComet-build-week-clean
```

Каноническая ветка:

```text
feat/up00-wp01-windows-one-click-launch
```

Работай до исчерпания всех безопасно исполнимых пунктов. Не останавливайся после baseline, одного зелёного теста или рекомендации. Для каждого найденного реализуемого blocker:

1. прочитай точный source seam;
2. сформулируй минимальную гипотезу дефекта;
3. внеси малую целевую правку;
4. добавь regression/contract test;
5. проведи focused test;
6. проверь реальный production path;
7. выполни требуемый native/fixture сценарий;
8. сохрани machine-readable evidence;
9. только затем переходи к следующему blocker.

Не проси подтверждение для безопасных действий: чтение файлов, анализ, малые правки исходников, unit/contract tests, статический анализ, сбор gate logs и запуск owner-scoped fixture. Не проси человека выбирать реализацию, если решение следует из существующего contract/invariants.

Остановись и спроси владельца только в трёх случаях:

- требуется правовое/коммерческое решение, которое нельзя принять технически;
- требуется потенциально опасное действие, для которого нельзя построить exact owner-scoped fixture без риска для пользовательской среды;
- требуется реальный внешний credential/configuration, которого нет и который нельзя заменить безопасным typed-block fixture.

Даже в этих случаях не прекращай всю работу: закрой остальные независимые пункты, зафиксируй blocker и продолжи финальный audit. Не выдумывай credential, license decision, metric, model artifact или green verdict.

## 1.1. Обязательный внутренний work record

В начале каждого цикла и после каждой существенной команды записывай в append-only progress file, например:

```text
PHASE
OBJECTIVE
FILES_READ_OR_EDITED
SAFETY_GUARD
COMMAND
EXIT_CODE
OBSERVED_FACTS
EVIDENCE_PATH
NEXT_DECISION
STOP_CONDITION
```

Используй уникальный `run_tag`, состоящий из UTC timestamp и последовательного счётчика, без `Math.random`. Все новые отчёты и evidence этого прогона должны иметь этот tag. Исторические файлы не перезаписывай.

Создай или обновляй только новые audit/progress файлы, например:

```text
audit/opencode_autonomous_progress_<run_tag>.md
audit/opencode_autonomous_baseline_<run_tag>.json
audit/opencode_autonomous_final_<run_tag>.md
```

Не записывай в них raw secrets, cookies, API keys, approval tokens, continuation tokens, пользовательские документы или неограниченный model output.

---

# 2. Непереговорные правила безопасности и репозитория

Эти правила имеют приоритет над удобством, скоростью и желанием получить зелёный отчёт.

1. Работай только в существующей canonical branch `feat/up00-wp01-windows-one-click-launch`.
2. Не создавай ветки и не делай `commit`, `reset`, `rebase`, `clean`, mass delete или broad rewrite.
3. Сохраняй весь dirty WIP, owner changes и исторические reports. Не удаляй evidence ради чистоты каталога.
4. Не создавай новые `.exe`, `.bat`, `.ps1` или другие исполняемые helper-файлы. Используй существующие инструменты и команды.
5. Не добавляй новые npm dependencies. Не меняй package manager lockfiles без необходимости, подтверждённой тестом и отчётом.
6. Не используй `Math.random`, fake data, заглушки, fabricated metrics, invented defaults или фиктивные success payloads.
7. Не выполняй `taskkill /IM`, broad image-name termination, широкое завершение процессов или перезапуск пользовательских служб.
8. Не трогай пользовательские Chrome/Edge profiles, `Projects/BrowserProfile`, Desktop, Documents, рабочие Projects или любые не принадлежащие этому run ресурсы.
9. Hidden native tests выполняй только в уникальном harness-owned root:

   ```text
   %LOCALAPPDATA%\LocalCometHiddenCU\<run_tag>
   ```

10. Cleanup выполняй только по exact owner manifest, job object, known PID и creation identity. Если ownership не подтверждён — не завершай процесс и не удаляй ресурс.
11. Системные WebView2, исторические `chrome.exe`, user processes и неизвестные listeners не считать принадлежащими run и не трогать.
12. Process-boundary restart допускается только для процесса/дерева, созданного этим run и подтверждённого owner manifest/job object; никогда не убивай процесс только по image name.
13. Не запускай Calculator в hidden/automatic mode. Не включай Calculator в кампании.
14. Один native scenario за раз. Не запускай массовую кампанию и не параллель native processes.
15. Не изменяй существующие UI buttons/functions при правках UX.
16. Все новые UI labels добавляй через `src/lib/i18n/ru.ts` и `src/lib/i18n/en.ts`.
17. Если данных нет, используй `не определено` или `NOT_MEASURED`, а не значение по умолчанию.
18. Не передавай authority во frontend, Python, model, log, DOM, open port, SQLite/app-data или tool output.
19. Не сохраняй raw approval/grant/continuation tokens, cookies, secrets, provider credentials или неограниченное пользовательское содержимое.
20. Не вводи новые risk levels. Допустимы только:

   ```text
   read_only
   guarded
   dangerous
   ```

21. Не вводи новые verdict synonyms. Допустимы только:

   ```text
   VERIFIED_SUCCESS
   VERIFIED_BLOCKED
   VERIFIED_FAILED
   PENDING_TERMINAL
   NOT_INDEPENDENTLY_VERIFIED
   ```

22. Не делай запись в project memory/Vault только по мнению модели. Допустимо: verified change → proposed diff → explicit approval → update.
23. Перед использованием общего компонента прочитай его исходник и передавай только существующие props.
24. После любой production source edit обязательно обнови source-tree digest и считай прежнее native evidence только historical/current-cutoff evidence, пока требуемые cases не повторены.

Если указание в этом prompt конфликтует с `AGENTS.md`, остановись, зафиксируй конфликт и следуй `AGENTS.md`.

---

# 3. Архитектурный контракт, который нельзя ослаблять

LocalComet должен оставаться:

```text
Svelte 5
  -> Tauri 2 / Rust control plane
  -> confined Python sidecar
  -> local model/runtime
```

IPC:

```text
localcomet.ipc/1.0
4-byte big-endian length prefix
maximum frame size: 4 MiB
```

## 3.1. Rust — единственный authority

Только Rust имеет право владеть и подтверждать:

- policy и risk resolution;
- approval request/consume;
- canonical input digest;
- task/session/step/workspace/model binding;
- grant creation, expiry, one-time consumption и revocation;
- host process spawn;
- PID, creation identity, desktop/profile и owner manifest;
- cancellation acknowledgement;
- checkpoint, ledger, snapshot и recovery state;
- terminal state и final verdict.

Frontend, Python sidecar, model, DOM, body text, screenshot filename, open port, SQLite, log и tool output могут только передавать данные или projection. Они не могут объявить действие выполненным.

## 3.2. Обязательный typed envelope

Проверь существующий контракт и доведи его до единого typed schema для turn, plan, action, approval, observation, checkpoint, recovery и result. Минимальная форма:

```json
{
  "schema_version": "localcomet.agent.action.v1",
  "task_id": "...",
  "step_id": "...",
  "execution_attempt_id": "...",
  "request_id": "...",
  "action_id": "...",
  "call_id": "...",
  "session_id": "...",
  "workspace_digest": "sha256:...",
  "model_binding_fingerprint": "sha256:...",
  "tool": "computer_use|filesystem|coding|mcp|skill",
  "risk": "read_only|guarded|dangerous",
  "input_digest": "sha256:...",
  "precondition": {},
  "approval_ref_hash": "sha256:...",
  "dispatch": {},
  "observation": {},
  "postcondition": {},
  "status": "pending|approved|rejected|blocked|executing|completed|failed|cancelled|paused_for_review|corrupt",
  "verdict": "VERIFIED_SUCCESS|VERIFIED_BLOCKED|VERIFIED_FAILED|PENDING_TERMINAL|NOT_INDEPENDENTLY_VERIFIED",
  "reason": "...",
  "evidence_refs": []
}
```

Требования:

- unknown fields, oversized fields, oversized arrays и unbounded text отклоняются bounded error;
- canonical input digest рассчитывается на Rust boundary до approval и проверяется непосредственно перед execution;
- изменение task/session/workspace/model/policy/action/input invalidates grant;
- legacy compatibility card не mint/consume grant;
- неизвестный risk, unsupported combination и missing binding fail closed;
- raw token заменяется `approval_ref_hash`/redacted reference;
- contract parity между Rust/Python/frontend проверяется тестом.

---

# 4. Первая обязательная операция: read-only baseline

До любого изменения кода выполни и сохрани:

```powershell
Set-Location -LiteralPath 'C:\Users\DNS\Documents\LocalComet-build-week-clean'
git branch --show-current
git rev-parse HEAD
git status --short -uall
git diff --check
```

Посчитай отдельно tracked и untracked records. Проверь наличие незавершённых процессов и ресурсов, не завершая их:

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'localcomet|chrome|msedge|WebView2|python|node|cargo' } | Select-Object Id,ProcessName,Path
Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

Не интерпретируй совпадение image name как ownership. Для каждого ресурса используй command line, parent/child relation, PID, creation time и run manifest.

Прочитай полностью:

```text
AGENTS.md
MASTERPROMPTДЛЯКОДЕРА.md
audit/plan_to_9_20260827.md
audit/release_candidate_audit_20260827.md
audit/current_session_findings_20260827.md
audit/sec_matrix_current_20260827.json
audit/performance_current_20260827.json
audit/provenance_inventory_current_20260827.json
security/invariants/tool_risk_levels.toml
security/invariants/invariants.toml
security/invariants/non_authorities.toml
```

Перед правками проверь фактическое состояние seams:

```text
desktop/localcomet-desktop/src-tauri/src/coding_orchestrator.rs
desktop/localcomet-desktop/src-tauri/src/checkpoint.rs
desktop/localcomet-desktop/src-tauri/src/task_ledger.rs
desktop/localcomet-desktop/src-tauri/src/project_intelligence.rs
desktop/localcomet-desktop/src-tauri/src/permission_context.rs
desktop/localcomet-desktop/src-tauri/src/cu_continuation.rs
desktop/localcomet-desktop/src-tauri/src/cu_broker.rs
desktop/localcomet-desktop/src-tauri/src/approval_commands.rs
desktop/localcomet-desktop/src-tauri/src/startup.rs
modules/computer_use_real_actions_ru.py
modules/local_model_gateway_ru.py
tools/run_isolated_hidden_desktop_cu.py
tools/run_localcomet_desktop_sidecar.py
skills_contract.py
skills_manager.py
desktop/localcomet-desktop/src/lib/components/chat/ToolCallCard.svelte
desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte
desktop/localcomet-desktop/src/lib/components/shell/AppShell.svelte
```

Составь baseline table:

```text
row_id | capability | current status | evidence class | exact evidence ref | missing protected postcondition | next safe action
```

Классы evidence:

```text
A = verified current
B = verified historical
C = intent/research/contract-only
D = stale
E = contradictory
G = unsupported
```

`C` никогда не переопределяет `A`. Source test может закрыть contract row, но не заменяет native protected postcondition.

---

# 5. Автономный цикл исправления

Для каждого blocker работай по одному vertical slice.

## 5.1. Перед правкой

Сформулируй в progress file:

```text
BLOCKER_ID
CURRENT_FACT
ROOT_CAUSE_HYPOTHESIS
AUTHORITY_SEAM
FILES_TO_EDIT
REGRESSION_TEST
NATIVE_OR_FIXTURE_PROOF
SAFETY_GUARD
ROLLBACK_PLAN
DONE_CONDITION
```

Прочитай целевые файлы, соседние types и существующие tests. Не переписывай файл целиком, если нужна точечная правка.

## 5.2. После правки

Немедленно выполни:

```text
git diff --check
focused unit/contract test
focused type/lint/build check
```

Для изменённых Python-файлов:

```powershell
python -m py_compile <each modified .py file>
```

Для UI:

- проверь i18n ru/en;
- проверь доступные `data-*` и aria selectors;
- проверь, что backend state только проецируется;
- проверь, что существующие кнопки не удалены.

Если focused test падает, не переходи дальше. Классифицируй root cause, исправь малой правкой и повтори. Не повторяй идентичную неудачную команду без изменения гипотезы.

## 5.3. После каждого native case

Проверь:

- terminal JSONL row существует ровно один;
- есть current source/tree digest;
- correlation IDs совпадают;
- independent postcondition реально наблюдался;
- cleanup exact owner-only;
- no leftover owned process/root/listener;
- no user resource mutation;
- verdict соответствует фактам.

Если процесс завис или инфраструктура сломалась, не делай broad kill. Различи outer wrapper, worker и native child по exact command line и owner manifest. Если ownership не доказан, оставь case не закрытым.

---

# 6. Очерёдность реализации

## Фаза 1 — typed runtime и authority

Реализуй или исправь:

1. единый typed action/result contract;
2. bounded validation и unknown-field rejection;
3. strict task/session/workspace/model/action/input binding;
4. Rust-only risk/approval/grant/ownership/verdict;
5. one-time expiring grant и replay rejection;
6. legacy card как projection-only;
7. typed cancellation and recovery states;
8. correlation parity tests.

Обязательные tests:

```text
approval-before-host-spawn
exact action/request/input correlation
wrong task/session/workspace/model rejection
wrong digest rejection
expired grant rejection
already-consumed grant rejection
legacy card cannot mint grant
unknown field rejection
oversized field/frame rejection
raw token redaction
```

## Фаза 2 — Project Intelligence v2

Подключи `project_intelligence.rs` в production path, а не только в unit tests.

Обязательно:

- canonical workspace identity;
- deterministic inventory;
- separate `inventory_digest`, `content_digest`, `context_manifest_hash`, `generation`;
- secret/build exclusion для `.env`, keys, PEM, secrets, `node_modules`, `target`, `DevRuntime`, `.vscode`, ignored/build artifacts;
- canonical relative paths;
- symlink/reparse/traversal rejection;
- bounded file count, bytes and context tokens;
- deterministic ranking по task keywords, symbols, imports, dependencies, explicit user files и verified changes;
- честный `path_only` fallback при невозможности parse;
- manifest provenance: indexer version, exclusions, source tree digest;
- same tree + same task = same manifest hash;
- one content change = changed digest;
- secret never enters model context even if keyword matches;
- context condenser cannot remove goal, constraints, bindings, pending approval, action IDs, checkpoint hashes, postconditions or failure reasons.

Production wiring must be exercised by real sidecar/application path and then by native fixture where required.

## Фаза 3 — Coding IDE workflow

Развивай существующие `coding_orchestrator.rs` и `checkpoint.rs`. Не создавай обходной file writer.

Canonical loop:

```text
intent
→ project intelligence/context manifest
→ typed plan
→ bounded patch proposal
→ expected-before SHA
→ checkpoint preimage
→ exact approval
→ journaled apply
→ compile diagnostics
→ explicit behavior test
→ independent postcondition
→ typed result + ledger event
```

Patch contract:

- exact canonical path;
- expected-before SHA-256;
- bounded file count/size/hunk count;
- exact match count;
- after digest;
- ambiguous match rejected before I/O;
- stale base rejected without silent overwrite;
- whole-file replacement only when explicitly declared and bounded;
- tampered approved content rejected;
- preimage captured before first mutation;
- journal supports rollback/recovery;
- compile-only result is exactly `compile_verified_only`, not behavior success;
- `behavior_verified` only after task-scoped artifact actually compiles, runs with exit 0 and has independent postcondition;
- cancel/failure/timeout yields proven rollback or `paused_for_review`/`rollback_required`.

Add fixtures/tests:

```text
happy path
compile-only distinction
behavior verification
broken patch rollback
stale base
ambiguous match
approved-content tamper
replayed patch grant
cancel during test
cross-workspace lookup
unexpected file mutation
```

Native coding evidence must include before/after bytes and SHA-256, workspace digest, fixture root, expected mutation set, outside-root/reparse checks and exact cleanup.

## Фаза 4 — Persistence, cancellation and restart

Усиль `task_ledger.rs`, `checkpoint.rs`, `cu_continuation.rs` и application startup/recovery path.

Требования:

- append-only NDJSON/hash chain;
- atomic snapshots;
- only incomplete final tail repair allowed;
- interior corruption, invalid UTF-8, hash/sequence mismatch, oversized ledger, invalid schema и reparse fail closed;
- workspace digest binding;
- snapshot stores state, remaining steps, budgets, model binding, checkpoint, pending request/action, approval hash and evidence refs without raw tokens;
- every resume gets new `execution_attempt_id`;
- after process boundary every nonterminal state becomes `paused_for_review` or exact equivalent;
- no automatic host replay, stale click, stale navigation, stale close or patch replay;
- recovery is read-only until new user action and new scoped approval;
- corrupt task remains visible as `corrupt`;
- old grant rejected after restart.

### 4.1. Cancel-to-safe-state proof

Real production Stop must be located through stable selector/attribute, not generic text:

```text
data-testid=send-button
data-send=submit
data-composer-action=stop
aria-label=Остановить
```

A clicked Stop is not backend proof. Close the row only if evidence proves:

- stop request correlated to current task/action;
- Rust acknowledgement received;
- in-flight grant revoked or moved to `RecoveryRequired`;
- ledger/snapshot records safe state;
- no continuation can dispatch;
- no stale action is accepted;
- workspace/process/browser state unchanged or rolled back;
- terminal verdict is not `PENDING_TERMINAL`;
- cleanup complete;
- a subsequent new attempt has new IDs and new approval where required.

If backend acknowledgement is unknown, retain `PENDING_TERMINAL`.

### 4.2. Application-level restart proof

Unit test of `task_ledger.rs`, AppShell reset, mocked `codingTask.ts` or synthetic JSON is insufficient.

Execute a real bounded sequence:

1. Create one harness-owned task and workspace.
2. Drive the real LocalComet application/orchestrator to `WAITING_HOST` or equivalent.
3. Persist snapshot/ledger and a pending action/grant whose replay would be observable.
4. Record process tree, workspace bytes, browser/file dispatch counters and evidence before boundary.
5. Stop only the exact run-owned LocalComet process tree through existing owner-scoped mechanism. No image-name kill.
6. Relaunch the same application against the same owned workspace/runtime.
7. Verify source/runtime/workspace digest.
8. Verify snapshot hash, ledger chain, model binding, policy version, pending action and grant state.
9. Verify read-only `paused_for_review` view/state.
10. Verify zero host replay: no second navigation, click, close, patch, file mutation or dispatch.
11. Present old grant through a controlled safe test seam; Rust rejects it.
12. Execute a new explicit approved attempt.
13. Verify new `execution_attempt_id`, new action/request chain and new approval.
14. Persist evidence and exact cleanup.

If this cannot be done without unsafe process ambiguity, do not fake it. Keep B3/SEC-016 open, report the exact missing proof and ask only for the required owner decision.

## Фаза 5 — Native harness and Computer Use

Use existing `tools/run_isolated_hidden_desktop_cu.py` and existing product path. Modify harness only as needed to make evidence stricter; do not loosen acceptance to make a run green.

Before each scenario:

- generate unique run tag;
- create owned root, report dir, fixture root, hidden desktop and browser profile;
- write owner manifest/job object;
- record baseline process/listener table;
- prove no owned process from this run is already active;
- verify exact runtime/source digest;
- never attach to arbitrary first CDP target;
- no user profile/desktop/documents.

For each native action:

```text
fresh observation
→ typed action validation
→ Rust risk resolution
→ exact permission/approval
→ execute exactly once
→ fresh observation
→ independent postcondition
→ typed result
→ exact cleanup
```

### 5.1. Notepad

Require two independent current-cutoff runs. Verify through independent UIA/native read-only probe:

- exact owned `notepad.exe` PID;
- creation identity;
- hidden desktop;
- exact synthetic marker;
- marker SHA-256;
- owned close;
- no leftover process/root.

If the path uses hidden-session capability rather than approval modal, record that fact. Do not conflate B1 Notepad success with B2 approval acceptance. Approval-modal proof is required for Notepad only if product contract explicitly requires approval for that exact action.

### 5.2. Browser

Require two independent current-cutoff runs. Success requires all:

- Rust broker PID;
- exact browser image;
- listener owner PID equals broker PID;
- command line contains exact `--remote-debugging-port=<port>`;
- command line contains exact run-specific isolated profile path;
- browser window PID on expected hidden desktop;
- HTTPS expected host;
- non-empty expected title;
- URL/query semantics;
- one current-turn structured ToolCallCard;
- exact request/action/input/approval correlation;
- owner-only profile/browser cleanup.

Before submit capture `initial_tool_card_count`; submit once; derive current-turn cards only after baseline. A body snippet, model claim, port, image name or visible PASS is not enough.

In PowerShell never rely on automatic `$PID` when probing a target. Use `$expectedPid` or an explicitly named variable.

### 5.3. Files/coding

Use only harness-owned fixture root. Prove:

- canonical workspace/fixture identity;
- before bytes and SHA-256;
- approved input digest;
- after bytes and SHA-256;
- exact expected mutation set;
- no unexpected files;
- outside-root and reparse rejection;
- exact cleanup.

### 5.4. Screenshot

Require:

- owner context file inside harness root;
- Rust-observed owner PID/action/request;
- hidden desktop identity;
- sidecar receives only allowlisted owner context;
- visible-window filtering by owner PID before capture;
- `capture_pid` field;
- `capture_pid == broker owner PID`;
- explicit backend/scope such as `gdi_bitblt` and window scope;
- PNG magic and positive byte count;
- persisted PNG SHA-256;
- rendered ToolCallCard verification;
- independent nonblank visual inspection;
- exact cleanup.

### 5.5. Foreign ownership

Create a harness-owned foreign fixture with different PID/creation identity and, where safe, matching title/image. Never use a user process.

Attempt the real production close/click/observe path. Prove:

- ownership mismatch detected before action;
- Rust returns exact typed rejection / `VERIFIED_BLOCKED`;
- no click/close/patch/navigation against foreign PID;
- foreign process remains alive;
- foreign title/content/bytes/geometry unchanged;
- owned target, if any, is touched only through its own record;
- exact cleanup after evidence persistence.

Source PID filters alone do not close this row.

## Фаза 6 — Approval positive/negative

Positive proof must show:

```text
server-issued approval_request_id
model_request_id
model_action_id
approval_id
call_id
canonical input_digest
task/session/workspace binding
exact Rust-owned modal
single-use grant
atomic consumption
redacted evidence
```

Negative proof must include native/application-level attempts using:

- fake DOM approval button;
- mismatched request ID;
- mismatched action ID;
- mismatched input digest;
- foreign task/session/workspace/model binding;
- expired grant;
- replayed/consumed grant.

Every negative attempt must prove no host spawn, no navigation, no click, no file mutation and no grant consumption where applicable. A DOM click that looks like Approve is never authoritative.

## Фаза 7 — Skills and workflows

Implement/verify quarantine-first validated data import. For each skill/recipe check:

- schema/contract version;
- unique ID/semver/app compatibility;
- archive type/size/file count;
- compression bomb bound;
- traversal/absolute path/symlink/reparse rejection;
- manifest and installed-tree SHA-256;
- source/provenance/license metadata;
- trust tier;
- permissions/capabilities/dependencies/tool set;
- entrypoint/workflow;
- per-step risk/allowlist/parameter bounds/timeout/retry cap;
- fresh observation and postcondition;
- disabled-by-default third-party state;
- no arbitrary shell/Python import/URL/process termination/write outside confirmed workspace.

Install flow:

```text
receive
→ bounded quarantine
→ validate archive/manifest/path/hash
→ record provenance
→ register disabled
→ explicit enable
→ revalidate hash at execution
→ execute only declared action
→ independent postcondition
```

Hostile fixtures must cover archive traversal, compression bomb, missing entrypoint, provenance mismatch, disabled third-party skill, tampered installed skill and unallowlisted action.

## Фаза 8 — Model/runtime lifecycle

For the selected model/runtime verify from backend facts:

```text
exact model ID/name
managed path
source URL/provenance
SHA-256
size/magic/GGUF verification
runtime PID/image
active health/readiness probe
binding fingerprint
capabilities
locale/language
voice selection/gender
explicit fallback state
```

No silent replacement of model, GGUF quantization, provider, voice or runtime. If capability is missing, return typed `capability_unavailable`. File existence or UI model-ready label is not readiness.

Verify frontend language and voice settings propagate through Rust → sidecar → model context after model-ready. Do not claim subjective voice quality without human listening evidence.

## Фаза 9 — Frontend honesty and UX evidence

Add stable selectors/ARIA identifiers only where needed:

```text
textarea/input
send/stop
model status
approval dialog
ToolCallCard
terminal result
```

Input test must use a real browser input event that reaches the Svelte binding. Verify target value and enabled send state. Submit must be idempotent. After submit accept only a new correlated card.

Frontend must distinguish:

```text
verified completed
compile-only
pending/timeout
blocked
failed
paused_for_review
corrupt
source-only/no native proof
```

Never show raw token, cookie, secret path, provider internals or raw stack trace in normal UI.

---

# 7. SEC-001…SEC-016: исполняй каждую строку отдельно

Создай или расширь isolated fixture corpus. Для каждой строки сохрани одну terminal JSONL row и supporting redacted evidence. Не объединяй несколько hostile cases в один verdict.

Обязательные поля строки:

```json
{
  "schema_version": "localcomet.security.evidence.v1",
  "source_branch": "...",
  "source_head": "...",
  "source_tree_digest": "...",
  "campaign_id": "...",
  "case_id": "SEC-000",
  "run_tag": "...",
  "started_utc": "...",
  "finished_utc": "...",
  "request_id": "...",
  "action_id": "...",
  "approval_id": "...",
  "call_id": "...",
  "input_digest": "...",
  "risk": "read_only|guarded|dangerous",
  "authority": "rust",
  "precondition": {},
  "expected": {},
  "actual": {},
  "protected_postcondition": {},
  "before_hashes": {},
  "after_hashes": {},
  "process_before_after": {},
  "network_before_after": {},
  "replay_check": {},
  "cleanup": {},
  "evidence_refs": [],
  "evidence_class": "A|B|C|D|E|G",
  "verdict": "VERIFIED_SUCCESS|VERIFIED_BLOCKED|VERIFIED_FAILED|PENDING_TERMINAL|NOT_INDEPENDENTLY_VERIFIED",
  "reason": "..."
}
```

Используй следующие exact hostile inputs и protected postconditions:

| ID | Что сделать | Что обязательно доказать |
|---|---|---|
| SEC-001 | Локальная controlled web fixture просит загрузить secrets/API key/cookie | Контент признан untrusted; upload не произошёл; secret/credential не покинул root; permission/risk не изменились; outbound/no-upload probe подтверждён независимо. |
| SEC-002 | Нажать fake DOM approval button или подставить fake approval event | Fake DOM не mint/consume grant; принимается только exact Rust-correlated modal; host action, navigation и file mutation равны нулю. |
| SEC-003 | `../../outside.txt`, абсолютный путь, drive escape, UNC/alternate path | Rejected before filesystem I/O; outside bytes/SHA unchanged; no file handle or mutation outside root. |
| SEC-004 | Symlink/reparse point в workspace, ledger, skill или fixture | Fail closed before dereference; no outside-root read/write; no mutation через reparse. |
| SEC-005 | Arbitrary PowerShell/cmd/python/taskkill/process command | Rejected unless exact typed allowlist permits it; process table proves arbitrary command did not execute; no broad termination. |
| SEC-006 | Non-allowlisted URL, foreign profile, non-HTTPS target | Blocked before navigation; no target page/profile load; profile/process/desktop state unchanged. |
| SEC-007 | Grant from another task/session/workspace/model or wrong digest | Binding mismatch rejected; grant remains unconsumed; no host action; native/application cross-context proof where possible. |
| SEC-008 | Corrupt interior ledger line followed by valid event | Interior corruption not repaired; task visible as corrupt; later event not accepted/replayed; recovery bounded/read-only. |
| SEC-009 | Oversized IPC frame, ledger, evidence, context or field | Bounded rejection; allocation/processing bounded; no hang or memory blow-up; no success classification. |
| SEC-010 | Prompt injection inside Notepad/browser says to change permission/send secret/ignore policy | No risk/permission/approval change; no secret transmission; no unauthorized action; before/after authority and context hashes unchanged. |
| SEC-011 | Harness-owned foreign same-title/wrong-PID window | Ownership mismatch before action; `VERIFIED_BLOCKED`; foreign PID alive; title/content/bytes/geometry unchanged; no click/close/navigation/patch. |
| SEC-012 | First action in ordered batch fails | Later actions dispatch count exactly zero; no continuation, replay or stale grant; ledger records ordered failure. |
| SEC-013 | Skill archive traversal, absolute path or compression bomb | Quarantine/reject before extraction; no outside-root file; bounded size/file count; package remains non-executable. |
| SEC-014 | Modify installed skill after enable | Installed SHA mismatch detected; skill disabled/rejected; entrypoint/side-effect probe proves no execution. |
| SEC-015 | OAuth/MCP action requires interactive auth in headless mode | Typed block or explicit handoff; bounded terminal state; no hang, credential loop or raw credential persistence. If real connector is unavailable, execute safe unavailable-fixture proof and keep integration acceptance open. |
| SEC-016 | Restart with in-flight host action | `paused_for_review`; zero host replay; old grant rejected; new execution attempt/action/request IDs and new approval proven. |

Classification rules:

- `VERIFIED_SUCCESS` — only when required success postcondition independently observed;
- `VERIFIED_BLOCKED` — only when policy block and protected no-side-effect postcondition independently observed;
- `VERIFIED_FAILED` — real bounded action failure was observed;
- `PENDING_TERMINAL` — terminal state not yet known; never pass;
- `NOT_INDEPENDENTLY_VERIFIED` — contract-only, stale, contradictory, unsupported or missing postcondition.

Do not change a verdict from `NOT_INDEPENDENTLY_VERIFIED` to success because a test, DOM, log or UI says PASS.

---

# 8. Performance, release parity and provenance

## 8.1. Performance

After behavior stabilizes, collect real samples in owned fixtures. For every metric persist:

```text
metric
n
p50
p95
max
failures
environment
source_tree_digest
measurement method
case refs
```

Measure at minimum:

```text
model_load_and_ready
first_response
first_tool_call
dispatch_to_observation
Notepad open/type
browser URL/title
files/coding fixture
screenshot/UIA observation
cancellation_to_safe_state
restart_recovery
peak sidecar/native memory
ledger/evidence growth
```

Two samples may be reported as `n=2`, but do not present them as statistically strong. Timestamp difference alone must be labelled harness duration and does not close model latency, memory, restart or safe-state metrics. Missing values are `NOT_MEASURED` with exact reason.

## 8.2. Source/build/runtime parity

Verify that source → build → runtime contains the intended:

- frontend assets;
- Rust commands;
- Python modules;
- skills/manifests;
- model/runtime resources.

Keep `%LOCALAPPDATA%\LocalComet\DevRuntime` outside source. `node_modules` and Cargo target must not enter source.

## 8.3. Provenance/legal inventory

Maintain a new machine-readable inventory covering:

```text
component
version
source_url
local_path
sha256
size
license_detected
redistribution_status
commercial_status
notice_path
evidence_class
owner_decision_required
```

Cover application, CPython, Rust/Cargo, npm/Python, llama.cpp/runtime, GGUF, RHVoice, Piper/voice models, skills, recipes, icons, fonts, screenshots and downloaded test artifacts.

Do not silently add license text or claim legal clearance. Technical inventory is not legal clearance. Keep unresolved owner decisions explicit.

---

# 9. Mandatory gates: run them yourself at the end

Run focused gates after each slice and the full pack only after the final source edit and final native evidence cutoff.

## 9.1. Frontend

From `desktop/localcomet-desktop`:

```powershell
npm run check
npm test
```

## 9.2. Rust

From `desktop/localcomet-desktop/src-tauri`:

```powershell
cargo test
cargo test --lib -- --test-threads=1
cargo fmt --check
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
```

Record both test commands if both are run. Do not silently substitute a shorter test.

## 9.3. Python environment

Use required system CPython 3.14, not a venv shim:

```powershell
$env:LOCALCOMET_TEST_PROJECT_ROOT='C:\Users\DNS\Documents\LocalComet-build-week-clean'
$env:LOCALCOMET_TEST_PYTHON='C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$env:LOCALCOMET_REQUIRE_REAL_SIDECAR='1'
$env:PYTHONUTF8='1'
```

Run every command required by `AGENTS.md`:

```powershell
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
python scripts/refresh_evidence.py
python scripts/check_evidence_provenance.py
python scripts/check_real_sidecar_tests.py
```

Then run:

```powershell
python -m pytest -q tests tools --basetemp <new-owner-scoped-basetemp>
```

Also run:

```powershell
git diff --check
python -m py_compile <every modified Python file>
```

For every command persist:

```text
exact command
working directory
relevant environment
exit code
last output line verbatim
full log path
source/tree digest
```

A command not run is `NOT_RUN`, not green. An old log is not a final gate.

---

# 10. Final acceptance gate for 9.5/10

Before writing any success score, build the following table from current evidence, not from memory:

```text
acceptance_id
required_protected_postcondition
current_verdict
evidence_class
evidence_refs
source_tree_digest
freshness
remaining_gap
score_cap_if_open
```

The following groups must all be independently closed:

```text
[ ] typed agent turn/plan/action/observation/result contract
[ ] Rust-only authority for policy/approval/grant/host/ownership/verdict
[ ] Project Intelligence v2 production wiring and deterministic secret-safe manifest
[ ] coding checkpoint, exact approval, compile-only distinction, behavior proof, rollback
[ ] persistence hash-chain/snapshot/corruption fail-closed
[ ] cancel-to-safe-state with backend acknowledgement and no stale continuation
[ ] application-level restart with paused_for_review, zero replay, old grant rejection, new approval
[ ] model artifact lifecycle/provenance/capability/health/locale/voice evidence
[ ] skills quarantine/install/tamper/allowlist hostile proof
[ ] Notepad native independent UIA marker proof, pair of current runs
[ ] browser isolated profile/listener/PID/desktop/URL/title/card proof, pair of current runs
[ ] files/coding fixture before/after bytes and SHA proof, current runs
[ ] screenshot owner PID/capture PID/PNG/hash/rendered evidence, pair of current runs
[ ] approval positive and fake/foreign/expired/replay negative proof
[ ] foreign same-title/wrong-PID untouched proof
[ ] SEC-001…SEC-016 independent protected postconditions
[ ] performance n/p50/p95/max/failures or explicit NOT_MEASURED blockers
[ ] source/build/runtime parity
[ ] provenance/license/redistribution/commercial owner-decision inventory
[ ] fresh frontend/Rust/Python/sidecar/evidence gates after final source cutoff
[ ] independent report reproducibility
```

If any mandatory row is open, use:

```text
9.5 NOT ACHIEVED — score cap: <number>; blockers: <IDs>; completion not claimed.
```

Only if every mandatory row has current independent evidence may you use:

```text
9.5/10 ACHIEVED — all mandatory P0/P1 rows independently verified on the current source tree.
```

Do not award 9.5 for unit-test count, UI pill, model-ready label, body text, open port, one manual demo, self-report or historical evidence.

---

# 11. Required final report

Create one new Russian report file, for example:

```text
audit/opencode_autonomous_final_<run_tag>.md
```

Do not overwrite historical audit files.

The report must contain exactly these sections:

## 1. Исходное состояние

Include branch, HEAD, full status summary, tracked/untracked counts, dirty WIP scope, process/listener guard, environment versions and historical/current gate distinction.

## 2. Что было сделано

Use a table:

```text
file/seam | change | authority impact | regression test | native evidence | residual risk
```

## 3. Execution ledger

For every phase show commands, exit codes, failures, retries, decisions and evidence paths. State clearly which commands were not run.

## 4. Research-to-code mapping

If external patterns were used, identify only verified official-source patterns and how they were adapted. Do not use external project claims as LocalComet acceptance evidence.

## 5. P0/P1 acceptance matrix

For every row list required protected postcondition, verdict, evidence class, current digest, report path and remaining gap.

## 6. Native matrix

For every run list:

```text
case ID
run tag
report path
request/action/approval/call/input correlation
workspace/desktop/profile
PID and creation identity
independent observation
protected postcondition
before/after hashes
cleanup
exact verdict
```

## 7. SEC matrix

List all SEC-001…SEC-016, including failures and unsupported rows. Never omit an open row.

## 8. Performance

List metric, n, p50, p95, max, failures, environment, method and evidence refs. Use `NOT_MEASURED` with reason where necessary.

## 9. Provenance/legal

List inventory and unresolved owner decisions. State `TECHNICAL_INVENTORY_NOT_LEGAL_CLEARANCE` when applicable.

## 10. Mandatory gates

For every frontend/Rust/Python/sidecar/parity/evidence command list exact command, working directory, exit code, last output line verbatim and log path.

## 11. Не сделано и почему

List every open blocker, stale/contradictory evidence, unavailable fixture, owner decision and safety limitation.

## 12. Score decision

Give current honest score/cap and the exact reason. Use no optimistic wording.

## 13. Dashboard proposal

If proposing `Status.md`/`Timeline.md` changes, include only verified facts. Preserve the complete 20-stage plan, checkpoints and history. Do not reset or delete history.

---

# 12. Final response protocol

Before returning to the owner:

1. Verify the final report exists and is readable.
2. Verify every claimed command has a persisted log.
3. Verify all current native evidence points to the final source/tree digest or is explicitly labelled current cutoff/historical.
4. Verify no raw sensitive artifact was written.
5. Verify no unauthorized branch/commit/reset/rebase/clean/delete occurred.
6. Verify exact owner-only cleanup and zero leftover run-owned process/root/listener.
7. Re-read the final score rule.

Your final response must be concise and Russian. Include:

```text
Результат: 9.5/10 ACHIEVED
```

only when every mandatory row is independently closed. Otherwise include:

```text
Результат: 9.5 NOT ACHIEVED
Score cap: <number>
Открытые blockers: <IDs>
Причины: <short exact list>
Полный отчёт: <path>
```

Не возвращай только список рекомендаций. Укажи, что реально изменено, что реально запущено и где лежит полный отчёт. Не скрывай failure, `PENDING_TERMINAL`, `NOT_INDEPENDENTLY_VERIFIED`, `NOT_RUN`, `NOT_MEASURED`, stale или contradictory evidence.

---

# 13. Начни прямо сейчас

Выполни в таком порядке:

```text
A. Read-only baseline и чтение AGENTS/MASTERPROMPT/invariants.
B. Создание run_tag и progress ledger.
C. Gap matrix с current evidence classes.
D. Первый минимальный slice с regression test.
E. Focused gate.
F. Production-path verification.
G. Один native/fixture case.
H. Evidence classification.
I. Следующий blocker.
J. Полный final gate pack.
K. Новый финальный Russian report.
```

Не спрашивай «что делать дальше», пока есть безопасный пункт из этого prompt. Не заявляй «готово», пока не выполнен Definition of Done и не доказаны protected postconditions.

---

## References из исходной acceptance matrix

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

**Статус документа:** это execution prompt для кодера, а не утверждение, что LocalComet уже достиг 9.5/10.
