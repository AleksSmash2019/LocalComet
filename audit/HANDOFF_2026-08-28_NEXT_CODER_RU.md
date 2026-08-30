# LocalComet — handoff следующему кодеру

Дата: 2026-08-28  
Репозиторий: `C:\Users\DNS\Documents\LocalComet-build-week-clean`  
Ветка: `feat/up00-wp01-windows-one-click-launch`  
HEAD: `a85bd2b` — `Harden continuation cancellation evidence seam`.

## Запуск

```powershell
cd C:\Users\DNS\Documents\LocalComet-build-week-clean
py tools\launch_localcomet_dev.py
```

Проверка без запуска: `py tools\launch_localcomet_dev.py --dry-run`. Это рабочая development-сборка, не финальный release candidate.

## Состояние

Закоммичен только B3-related scope: Rust continuation registry и broker binding, approval ACL, frontend cancellation lifecycle, hidden native harness/evidence analyzer и focused contract tests. Остальной dirty WIP намеренно не затрагивался: после коммита оставалось 777 строк `git status --short -uall`; staged area пуст.

Перед коммитом подтверждены `npm run check` — 0 errors/0 warnings, Python `py_compile` — успешно и `tests/test_hidden_evidence_contract.py` — 25 passed. Native cancellation достигал реального `continuation_consume_leased`, Rust revoke с `revoked=1`, authoritative `model_turn_cancel` state `Cancelled`, dead worker, no new cards, ready composer и исчезнувший Stop.

## Незакрытый B3 blocker

Последний native replay diagnostic остаётся `PENDING_TERMINAL`: `post_grant_revocation_verified=true`, но `replay_rejected=false`. Для закрытия требуется ephemeral повторный consume того же grant через authority seam после revoke, typed `continuation_replayed`, без записи raw `cgr_`/`lease_id`, плюс доказательство отсутствия поздних consume/observe. Не считать отсутствие frontend-вызова доказательством.

Последний artifact: `Projects\Reports\computer_use_real_actions\isolated_hidden_desktop\autonomous_20260828_230000_postgrant_replay_diag`.

## Следующему кодеру

Сначала `git status`, `git log -1`, `git diff --check`; не делать reset/clean/rebase, broad staging или массовое удаление. Проверить, почему isolated invoke wrapper не сохранил replay event; сохранить Rust authority и feature-gate diagnostic hook. Затем targeted frontend/Rust/Python gates, два независимых native cancellation runs, affected browser run, source freeze, refresh digest и только после этого full mandatory gates и новый append-only Russian report/dashboard.

Запрещены broad process kills, `taskkill /IM`, touching user BrowserProfile/Chrome/Desktop/Documents/Projects, новые `.exe/.bat/.ps1`, npm dependencies и raw secret leakage. UI, DOM, LLM, port, log и self-report не являются authority evidence.

Полный handoff синхронизирован в Obsidian: `99 Handoffs/HANDOFF_2026-08-28_LOCALCOMET_NEXT_CODER.md`.

## Проверки

```powershell
cd C:\Users\DNS\Documents\LocalComet-build-week-clean\desktop\localcomet-desktop
npm run check
npm test
cd ..\..
py -m py_compile tools\run_isolated_hidden_desktop_cu.py tests\test_hidden_evidence_contract.py
py -m pytest -q tests\test_hidden_evidence_contract.py -p no:cacheprovider
```

Полный mandatory gate и fresh source digest после последних правок не подтверждены; не заявлять release-ready или 9/10.

## References

- [1] [AGENTS.md](../AGENTS.md)
- [2] [Latest native replay diagnostic](../Projects/Reports/computer_use_real_actions/isolated_hidden_desktop/autonomous_20260828_230000_postgrant_replay_diag/isolated_hidden_user_runs.jsonl)
- [3] [Commit a85bd2b](https://github.com/)

<!-- References are repository-local except the commit placeholder; replace with the canonical remote URL if available. -->

