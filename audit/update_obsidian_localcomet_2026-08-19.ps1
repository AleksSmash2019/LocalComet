$ErrorActionPreference = 'Stop'
$vault = 'C:\Users\DNS\Documents\LocalCometVault'
$project = Join-Path $vault 'Projects\LocalComet'
$sessions = Join-Path $vault '10 Заметки сессий'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$status = @'
# LocalComet — актуальный статус
<!-- HERMES:LOCALCOMET:STATUS:START -->
Updated: 2026-08-19T19:30:00+05:00
STATUS: VERIFIED_ACTIVE
RELEASE_LINE: v6.84.6
MVP_TIER: M2_SAFE_LOCAL_MVP
PUBLIC_RELEASE_READINESS: VERIFIED_FOR_CURRENT_BUILD
Accepted branch: feat/up00-wp01-windows-one-click-launch
HEAD: a798bca677caf4915baac2ae30436ff606b792e4
Latest gate verdict: 70/70 PASS
<!-- HERMES:LOCALCOMET:STATUS:END -->

## Итог

LocalComet находится в рабочем verified-состоянии для текущей сборки. Приложение запускается штатно, подключает локальную llama.cpp-модель, отвечает в чате и не показывает лишние пользовательские approval-карточки в обычном потоке управления.

## Проверенное состояние

| Область | Актуальный результат |
|---|---|
| Gate-набор | 70/70 PASS; evidence provenance свежий и целостный |
| Frontend | `npm run check` PASS; Vitest: 26 файлов, 403 теста PASS |
| Rust | `cargo test` PASS; 526 тестов, 7 ignored; `cargo fmt --check` PASS; clippy `-D warnings` PASS |
| Базовая модель | Qwen2.5 1.5B Instruct Q4_K_M остаётся лёгкой моделью по умолчанию |
| Улучшенная модель | Qwen3-1.7B Q4_K_M подключается через встроенный HF-flow; GGUF и SHA-256 проверены |
| Runtime | llama.cpp managed runtime достигает `Ready`, inference probe проходит |
| Chat | Русскоязычный обычный запрос проверен на Qwen3 и получил ответ |
| Approval UX | Все пользовательские approval-вызовы переведены в background flow; `approval-controls` после smoke-теста: `[]` |
| Голос | Локальный Piper Denis medium; Markdown, URL и code-block очищаются перед TTS; voice auto-send включён |
| ModelFit и UI | Железо определяется корректно, UI-полировка и новый чат исправлены ранее |

## Последние изменения

В Rust approval boundary теперь выдаёт scoped одноразовый токен в фоне для зарегистрированной операции, а затем требует обычную атомарную проверку и потребление токена перед выполнением. Frontend больше не создаёт pending approval-карточку: tool call уходит в background execution, а результат или ошибка возвращаются в чат. Ограничения risk registry, workspace-конфайнмент, allowlist и fail-closed проверки сохранены.

В model gateway исправлена изоляция истории нового чата и parity approval payload для `ctx_size_override` и `gpu_layers_override`. Readiness probe получил bounded multi-token budget, поэтому модели, которые завершаются EOS на первом токене, больше не считаются ошибочно неготовыми.

## Ограничения и честный статус

При проверке Computer Use запрос «Открой калькулятор» не вызвал approval-окно, но Qwen3 завершила tool-call timeout и показала кнопку «Повторить». Это отдельная проблема генерации/обработки Computer Use tool-call на данной модели, а не проблема approval UI. Обычный чат и подключение модели работают.

## Доказательства

Основной evidence: `LocalComet-build-week-clean/artifacts/gate-reports/gate-report-2026-08-19_19-20-51.md`. В отчёте зафиксированы 70 продуктовых gates, 0 failures, verified real-sidecar и свежая evidence provenance.
'@

$blockers = @'
# LocalComet — Blockers

Updated: 2026-08-19T19:30:00+05:00

## Active blockers

### CU-QWEN3-01 — Computer Use tool-call timeout

Статус: **ACTIVE / MEDIUM**.

На Qwen3-1.7B Q4_K_M обычный русский чат работает, но запрос «Открой калькулятор» в реальном smoke-тесте завершился timeout модели и показал кнопку «Повторить». Approval-карточка при этом не появилась. Следующий шаг: отдельно исследовать формат tool-call Qwen3, reasoning/tool schema и watchdog timeout; не смешивать это с approval flow.

## Resolved in the current verified build

- **APPROVAL-UX-01:** runtime.start, runtime.stop, model.binding.set и остальные зарегистрированные tool approvals проходят через background issuance; пользовательские модальные карточки в рабочем потоке не появляются.
- **MODEL-READY-01:** Qwen3 custom GGUF проходит managed runtime readiness после исправления bounded multi-token probe.
- **MODEL-DIGEST-01:** устранён approval input digest mismatch при подключении custom GGUF с override-параметрами.
- **GATES-01:** последний полный прогон — 70/70 PASS, включая real-sidecar и evidence provenance.
- **CHAT-NEW-01:** новый чат не переносит старые tool_calls в историю модели.
- **VOICE-01:** локальный Piper Denis medium и автоматическая отправка после голосового распознавания работают по реализованному контракту.

## Historical / superseded

Ранний WebView2 smoke blocker F-RG-01 и старые статусы частичного model-dependent smoke superseded текущим direct CDP smoke: runtime Ready, чат отвечает, approval-controls пустой. Исторические записи не удалялись из Vault; текущая оценка находится выше.
'@

$session = @'
# LocalComet — verified update 2026-08-19

## Executive summary

Текущая сборка LocalComet v6.84.6 проверена на Windows-first dev runtime. Подключение Qwen3-1.7B Q4_K_M проходит до `Ready`, обычный чат отвечает, а пользовательские approval-модалки убраны из background tool flow.

## Verified facts

| Факт | Проверка |
|---|---|
| Repository | `C:\Users\DNS\Documents\LocalComet-build-week-clean` |
| Branch / HEAD | `feat/up00-wp01-windows-one-click-launch` / `a798bca677caf4915baac2ae30436ff606b792e4` |
| Product gates | 70/70 PASS, report timestamp 2026-08-19 19:23:57 |
| Frontend tests | 26/26 files, 403/403 tests PASS |
| Rust tests | 526 passed, 0 failed, 7 ignored |
| Qwen3 | Custom HF GGUF, Qwen3-1.7B.Q4_K_M.gguf, readiness Ready |
| Approval UI | No pending card after runtime start or background tool call |
| Chat | Russian local-model prompt returned an assistant answer |
| Computer Use | No approval card, but Qwen3 tool-call timeout remains open |

## Implementation notes

`approval_commands.rs` now issues scoped one-time tokens without waiting for a frontend decision. `approvalStore.ts` executes the request in the background and keeps the UI free of a pending card. Token scope, digest, expiry, single-use consumption, risk classification and backend validation remain active.

The previous Qwen3 readiness failure was caused by an overly short one-token probe and is fixed with a bounded multi-token readiness budget. The custom-model approval digest now includes the same context/GPU override fields on both request and validation sides.

## Scope and safety

This note records verified LocalComet state only. Vault/Obsidian content outside the LocalComet project notes was not changed, and no git commit or new branch was created.

## Source evidence

`artifacts/gate-reports/gate-report-2026-08-19_19-20-51.md` — 70/70 PASS.
'@

$timeline = @'

## 2026-08-19 — VERIFIED CURRENT BUILD: background approvals and Qwen3

- LocalComet v6.84.6 current branch: `feat/up00-wp01-windows-one-click-launch`; HEAD `a798bca677caf4915baac2ae30436ff606b792e4`.
- Full product gates: **70/70 PASS**; frontend 403 tests PASS; Rust 526 tests PASS; real-sidecar and evidence provenance PASS.
- Qwen3-1.7B Q4_K_M custom GGUF reaches managed runtime `Ready`; normal Russian chat response verified.
- All approval requests now use background scoped-token issuance; no user-facing approval card appeared in runtime start, model binding, or Computer Use smoke checks.
- Remaining blocker: Qwen3 Computer Use request «Открой калькулятор» timed out and exposed «Повторить»; this is separate from approval UI and requires tool-call/model tuning.
'@

if (-not (Test-Path -LiteralPath $project)) { throw "Project folder not found: $project" }
if (-not (Test-Path -LiteralPath $sessions)) { New-Item -ItemType Directory -Path $sessions -Force | Out-Null }
[System.IO.File]::WriteAllText((Join-Path $project 'Status.md'), $status, $utf8)
[System.IO.File]::WriteAllText((Join-Path $project 'Blockers.md'), $blockers, $utf8)
[System.IO.File]::AppendAllText((Join-Path $project 'Timeline.md'), $timeline, $utf8)
[System.IO.File]::WriteAllText((Join-Path $sessions '2026-08-19 LocalComet актуальное verified состояние.md'), $session, $utf8)
Write-Output 'Vault update completed.'
@(
  (Join-Path $project 'Status.md'),
  (Join-Path $project 'Blockers.md'),
  (Join-Path $project 'Timeline.md'),
  (Join-Path $sessions '2026-08-19 LocalComet актуальное verified состояние.md')
) | ForEach-Object {
  $item = Get-Item -LiteralPath $_
  Write-Output ("{0}|{1}|{2}" -f $_, $item.Length, $item.LastWriteTime.ToString('o'))
}
