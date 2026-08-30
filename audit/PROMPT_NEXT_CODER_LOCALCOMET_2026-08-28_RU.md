# МАСТЕР-ПРОМПТ ДЛЯ СЛЕДУЮЩЕГО КОДЕРА
## LocalComet — продолжение Windows-first hardening без потери контекста

> **Роль:** ты продолжаешь работу над существующим репозиторием LocalComet. Не начинай проект заново, не переписывай архитектуру и не делай вид, что аудит завершён. Сначала проверь фактическое состояние, затем исправляй только подтверждённые проблемы и сохраняй fail-closed поведение.

---

## 1. Обязательная точка входа

Работай **только** в существующем репозитории:

```text
C:\Users\DNS\Documents\LocalComet-build-week-clean
```

Рабочая ветка строго фиксирована:

```text
feat/up00-wp01-windows-one-click-launch
```

На момент передачи последний коммит:

```text
a85bd2b Harden continuation cancellation evidence seam
```

Предыдущий baseline HEAD до последнего коммита:

```text
74f527d5cc97526a791eca81a8d995e2cc5a6aa7
```

**Не создавай новую ветку. Не делай reset, rebase, clean, checkout поверх WIP или массовое удаление.** Не уничтожай незакоммиченные изменения: после коммита в рабочем дереве оставался большой dirty WIP-набор, включая audit artifacts и изменения других рабочих пакетов. Сначала выполни:

```powershell
cd C:\Users\DNS\Documents\LocalComet-build-week-clean
git branch --show-current
git rev-parse HEAD
git status --short -uall
git diff --check
git log -5 --oneline --decorate
```

Сохрани исходный вывод. Сравни его с этим handoff; текущий `git status` важнее любой старой заметки.

---

## 2. Что уже сделано

LocalComet является рабочей Windows development-сборкой. Базовый запуск:

```powershell
cd C:\Users\DNS\Documents\LocalComet-build-week-clean
py tools\launch_localcomet_dev.py
```

Проверка без запуска:

```powershell
py tools\launch_localcomet_dev.py --dry-run
```

Frontend-only режим:

```powershell
cd desktop\localcomet-desktop
npm run dev
```

В архитектуре сохранено разделение authority:

```text
Svelte 5 UI
  -> Tauri 2 / Rust authority
  -> confined Python sidecar
  -> control plane / model gateway
  -> local model runtime
```

Rust остаётся источником истины для approval, risk, grant, process ownership, workspace/session binding, terminal state и cleanup verdict. Frontend, DOM, LLM output, port, log, SQLite/app-data и self-report не являются самостоятельным доказательством.

В предыдущих итерациях были доведены или существенно укреплены следующие направления:

1. Approval correlation: request/action/approval/call/input-digest IDs связаны и проверяются.
2. Computer Use permissions: deny-by-default и scoped delegation через UI preferences → Rust → sidecar.
3. Browser acceptance: isolated profile, approved HTTPS host/title, CDP listener identity, matching PID/port, hidden desktop и exact cleanup.
4. Notepad acceptance: broker-owned PID/image, hidden desktop/UIA evidence и hash-bound proof.
5. Screenshot acceptance: broker context/capture PID, PNG bytes/hash и rendered evidence.
6. Coding E2E: approval, plan ledger, hash chain, rollback/negative paths и foreign ownership checks.
7. Restart/recovery: production path сохраняет `Created -> IntentCompiled -> AwaitingApproval` до выдачи coding grant; после restart existing approved plan продолжается только при exact patch SHA match.
8. Continuation registry: opaque continuation grant, issued/in-flight/revoked/completed state, session/workspace/action/input binding и replay rejection semantics.
9. Workspace binding: continuation registry должен получать Rust-owned workspace digest, а не canonical path из `ExecutionGrant.workspace`.
10. Cancellation: authoritative `model_turn_cancel`, worker dead, no new cards, composer recovered, Stop gone и positive Rust revoke.
11. Native harness: unique isolated root, hidden desktop, owner manifest/job object, exact PID cleanup, redacted artifacts и fail-closed analyzer.
12. Fault-injection hook: pending hook переведён из обычного release-runtime env behavior в explicit Cargo feature с isolated worker marker. Feature-enabled binary нельзя считать обычной production binary.

---

## 3. Что реально подтверждено

Перед последним коммитом были подтверждены:

| Проверка | Результат |
|---|---|
| `npm run check` | 0 errors, 0 warnings |
| Python `py_compile` для изменённых Python-файлов | успешно |
| `tests/test_hidden_evidence_contract.py` | 25 passed |
| Native Browser/Notepad/Screenshot/Coding сценарии | ранее проходили в isolated hidden desktop, но старые evidence требуют новой классификации после source changes |
| Native cancellation | реальный `continuation_consume_leased` → positive Rust revoke (`revoked=1`) → authoritative `Cancelled`, worker dead, no new cards, composer ready, Stop gone |

Важно: после изменения source старые evidence нельзя автоматически считать свежими. Нужен новый source digest и повтор затронутых native cases.

---

## 4. Главный незакрытый blocker: B3 post-revoke replay

Последний native replay diagnostic был:

```text
Projects\Reports\computer_use_real_actions\isolated_hidden_desktop\autonomous_20260828_230000_postgrant_replay_diag
```

Он подтвердил:

```text
post_grant_revocation_verified = true
host_continuation_correlated = true
terminal_cancelled = true
backend_state = Cancelled
worker_alive = false
no_new_tool_cards = true
composer_ready_after = true
stop_control_gone = true
```

Но он остался:

```text
final_classification = PENDING_TERMINAL
replay_rejected = false
no_stale_host_replay = false
```

Причина: frontend/native diagnostic wrapper не сохранил отдельный post-revoke replay event. Пустой или отсутствующий последующий frontend-вызов **не является достаточным доказательством**, что авторитетный registry отверг повторное использование capability.

### Целевое доказательство B3

После реального сценария:

```text
real broker spawn/postcondition seam
  -> continuation issued
  -> continuation consumed and leased
  -> production Stop/cancel
  -> Rust revoke, revoked > 0
  -> same opaque grant replayed ephemerally through authority seam
  -> typed continuation_replayed rejection
  -> no later observe/consume
  -> terminal Cancelled
  -> worker dead and cleanup verified
```

Нельзя писать raw `cgr_` или `lease_id` в JSONL, trace, screenshot, DOM, stdout, report или persistent storage. Raw grant может жить только во временной in-memory переменной внутри legitimate authority/test seam и должен быть уничтожен после probe.

Analyzer должен принимать full safe state только если одновременно истинны:

```text
backend_acknowledged
terminal_cancelled
no_new_tool_cards
composer_ready_after
stop_control_gone
host_continuation_correlated
post_grant_revocation_verified
replay_rejected
no_stale_host_replay
trace_secret_free
```

`replay_rejected` должен означать именно typed authority response `continuation_replayed`, а не произвольную ошибку, отсутствие вызова или UI-состояние.

---

## 5. Стратегический порядок продолжения

### Этап A — baseline и безопасность изменений

1. Проверить ветку, HEAD, полный dirty status и diff-check.
2. Прочитать `AGENTS.md` и не считать старые отчёты текущей истиной.
3. Проверить, какие именно файлы были включены в `a85bd2b`, а какие остались dirty.
4. Не трогать пользовательские `BrowserProfile`, Chrome, Desktop, Documents или Projects.
5. Не использовать `taskkill /IM`, broad process kill или service restart.
6. Если native run оборвался, использовать только его `owned_run_manifest.json` и canonical exact-owner cleanup.

### Этап B — исправить B3 authority seam

1. Проверить реальные имена Tauri commands для consume, observe, complete и revoke.
2. Проверить, где находится raw continuation ref и когда он становится недоступен.
3. Предпочтительный дизайн — Rust-owned, feature-gated diagnostic seam, возвращающий только redacted/typed result.
4. Обычный production/default build не должен позволять пользователю активировать forced pending через внешний env.
5. Не ослаблять approval, session, workspace, hidden desktop или action/input binding ради прохождения теста.
6. Если diagnostic вызов размещается во frontend wrapper, он не должен становиться новой authority: authority должен оставаться Rust registry.
7. Добавить regression tests как минимум для:
   - revoked grant → replay returns `continuation_replayed`;
   - missing replay event → full safe predicate false;
   - replay after wrong request/session/workspace → rejected;
   - raw `cgr_`/`lease_id` in trace → rejected;
   - unexpected replay success → rejected;
   - replay event for wrong request ID → rejected.

### Этап C — native acceptance

1. Выполнить два независимых native B3 cancellation runs с уникальными tags.
2. Проверить `cancellation_workspace.json`: production `set_workspace` status/digest present.
3. Проверить JSONL row, `continuation_trace`, redacted invoke trace, Rust `toolcall_trace.log`, `cu_debug.jsonl`, manifest и cleanup.
4. Ожидаемый порядок: issue → consume requested → leased → Stop → revoke requested → revoke succeeded (`revoked > 0`) → replay rejection (`continuation_replayed`) → terminal cancel.
5. Убедиться, что после revoke нет consume/observe, capability не повторилась, worker dead, no new cards, composer ready, Stop gone.
6. После B3 повторить affected Browser case в том же source state. Старые Browser/Notepad/Screenshot evidence не повышают текущий verdict без refresh.

### Этап D — gates и provenance

Минимальные affected gates:

```powershell
cd C:\Users\DNS\Documents\LocalComet-build-week-clean\desktop\localcomet-desktop
npm run check
npm test

cd ..\..
py -m py_compile tools\run_isolated_hidden_desktop_cu.py tests\test_hidden_evidence_contract.py
py -m pytest -q tests/test_hidden_evidence_contract.py -p no:cacheprovider

cd desktop\localcomet-desktop\src-tauri
cargo test
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
```

Перед release acceptance обязательны все gates из `AGENTS.md`, включая:

```text
scripts/check_real_sidecar_tests.py
scripts/refresh_evidence.py
scripts/check_evidence_provenance.py
full pytest -q tests tools --basetemp <owned> -p no:cacheprovider
```

Каждая команда должна быть записана с exit code и последней строкой вывода. Если gate не запускался или завершился timeout/error, так и писать; не заменять это словом green.

После source freeze выполнить refresh evidence/provenance и получить новый текущий digest. Не использовать старый digest `6820f0b3…` или более ранние snapshots как текущие.

### Этап E — следующие SEC blockers после B3

После defensible B3 proof переходить к SEC matrix по приоритету:

| Приоритет | Направление |
|---|---|
| P0 | files/reparse/UNC/path confusion, negative approval, stale grant, foreign ownership |
| P0 | corrupted ledger/recovery, ordered failure, cancellation/no-replay |
| P1 | non-allowlisted URL/profile, cross-session/workspace grant, oversized input |
| P1 | prompt injection/no-upload, hostile skill archive/tamper, headless OAuth/MCP |
| P1 | provenance, performance measurements and owner decisions |

Каждый SEC row закрывать только current independently verified postcondition. Если native proof отсутствует, оставлять `NOT_INDEPENDENTLY_VERIFIED`.

---

## 6. Правила коммитов и рабочего дерева

Текущий коммит `a85bd2b` уже создан по явному запросу владельца. Дальше:

- работать только в указанной ветке;
- не создавать новые ветки;
- не делать reset/rebase/clean;
- не смешивать unrelated WIP в коммит B3;
- перед staging показывать точный список файлов;
- не коммитить audit dumps, runtime, `node_modules`, Cargo target, user data и временные secret-bearing artifacts;
- новый коммит создавать только после явного запроса владельца или согласованного workflow;
- не удалять файлы без явного разрешения;
- не добавлять npm dependencies;
- не создавать новые `.exe`, `.bat` или `.ps1`;
- не менять Rust authority на frontend-only imitation;
- не повышать оценку и не писать «готово» без свежих gates и evidence.

---

## 7. Где лежит контекст

Репозиторийный handoff:

```text
audit/HANDOFF_2026-08-28_NEXT_CODER_RU.md
audit/PROMPT_NEXT_CODER_LOCALCOMET_2026-08-28_RU.md
```

Obsidian handoff:

```text
C:\Users\DNS\Documents\LocalCometVault\99 Handoffs\HANDOFF_2026-08-28_LOCALCOMET_NEXT_CODER.md
```

Obsidian status:

```text
C:\Users\DNS\Documents\LocalCometVault\Projects\LocalComet\Status.md
```

Ключевые исходники:

```text
tools/run_isolated_hidden_desktop_cu.py
tests/test_hidden_evidence_contract.py
desktop/localcomet-desktop/src-tauri/src/cu_broker.rs
desktop/localcomet-desktop/src-tauri/src/cu_continuation.rs
desktop/localcomet-desktop/src-tauri/src/approval_commands.rs
desktop/localcomet-desktop/src-tauri/permissions/approval.toml
desktop/localcomet-desktop/src-tauri/Cargo.toml
desktop/localcomet-desktop/src/lib/stores/modelGateway.ts
```

Правила проекта:

```text
AGENTS.md
```

---

## 8. Формат будущего отчёта владельцу

Будущий отчёт писать на русском и append-only. Он должен содержать:

1. Исходные branch/HEAD/status/digest и факт наличия dirty WIP.
2. Список изменённых файлов и назначение каждого изменения.
3. Все выполненные gates: точная команда, exit code и последняя строка.
4. Native matrix: run tag, scenario, approval/request/action correlation, workspace/session binding, process PID/image, CDP/desktop proof, cancellation trace, replay result и cleanup.
5. Полную SEC matrix со статусом каждой строки.
6. Performance/provenance measurements и их ограничения.
7. Что не сделано, почему не сделано и какой evidence нужен дальше.
8. Score cap без оптимистичного округления; если B3 или P0 остаётся open, не заявлять 9/10 или release-ready.

> **Главное:** продолжай автономно, но сохраняй честность evidence. Рабочий запуск LocalComet уже есть; задача следующего кодера — превратить текущий рабочий development state в независимо подтверждённый security/release state, начиная с B3 post-revoke replay и не ломая существующий dirty WIP.

## References

- [1] `AGENTS.md` — binding project rules and mandatory gates.
- [2] `audit/HANDOFF_2026-08-28_NEXT_CODER_RU.md` — concise handoff.
- [3] `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/autonomous_20260828_230000_postgrant_replay_diag` — latest fail-closed B3 diagnostic.
- [4] Commit `a85bd2b` — current B3-related checkpoint.

