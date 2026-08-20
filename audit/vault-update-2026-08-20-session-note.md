---
type: session_update
status: verified_current
evidence_class: A
authority: repository_and_gate_run
updated: "2026-08-20"
last_reviewed: "2026-08-20"
project: LocalComet
---

# LocalComet — effort/thinking и local Vault integration — 2026-08-20

## Итог

LocalComet v6.84.6 доведён до рабочего состояния после добавления системы effort/thinking. Финальный прогон `Run-Gates.ps1` завершился результатом **71/71 PASS**.

В чат-композере доступны четыре уровня: **Off**, **Low**, **Medium** и **High**. Бюджеты размышления составляют соответственно 0, 512, 2048 и 8192 токенов. Некорректные или неподдерживаемые значения безопасно откатываются к Off. Reasoning передаётся отдельным stream channel и показывается в сворачиваемом блоке под ответом, не смешиваясь с видимым текстом ответа. Выбор уровня сохраняется между запусками и блокируется во время генерации.

## Модель

Установленная модель Qwen3-1.7B Q4_K_M назначена предпочтительной, когда её artifact доступен и проходит проверку. Artifact ID: `custom-hf-72962196cbe48a1dc6b432301cb3666a0aad360a53a43139094d52aa62b0f4f6`. Qwen2.5 1.5B остаётся детерминированным fallback.

Для runtime добавлен формат reasoning `deepseek`; gateway поддерживает per-request `thinking_budget_tokens`. Frontend, Rust и Python regression suites проходят.

## Проверки

Финальный gates report: `gate-report-2026-08-20_02-38-15.md`.

Подтверждены `npm run check` без Svelte diagnostics, 403 frontend tests, `cargo fmt --check`, `cargo test`, `cargo clippy --all-targets --all-features -- -D warnings`, Python compilation, bundle parity, evidence provenance, model gateway, knowledge-injection и CLI smoke tests.

Новый local Vault adapter прошёл 7/7 unit tests. Проверены чтение и список Markdown, create/update proposal flow, optimistic concurrency, traversal и absolute path rejection, `.obsidian` exclusion, symlink escape, byte limit и tampered proposal rejection.

## Локальная интеграция с Vault

LocalComet настроен на локальную папку `C:\Users\DNS\Documents\LocalCometVault`. Workspace identity успешно принята backend с `status: ok`, а выбор сохранён в `localcomet.workspace.v1` для восстановления после перезапуска.

Интеграция использует только файловую систему. Obsidian application, Obsidian REST API, MCP, browser session и cloud integration не используются. Adapter работает с UTF-8 Markdown, применяет ограничение canonical root, optimistic SHA-256 checks и atomic writes. Удаление и переименование не предоставляются.

Реальный Vault проверен только в read-only режиме: обнаружено 435 Markdown-файлов. В рамках этой сессии ни один файл Vault не создавался, не изменялся, не удалялся и не перемещался.

## Связанные материалы

- [[2026-08-19 LocalComet актуальное verified состояние]]
- [[00 История и карта проекта]]
- [[00 Единый индекс знаний]]

Источник текущего состояния: рабочее дерево `C:\Users\DNS\Documents\LocalComet-build-week-clean`, gate report и verification artifacts от 2026-08-20.
