# LocalComet — MVP Scope

## Входит в MVP
1. Рабочий desktop UI (chat, models, settings, diagnostics) — **есть**.
2. Загрузка/запуск локальных GGUF-моделей через managed llama.cpp — **есть**.
3. HF-браузер с прогрессом/cancel/lifecycle — **есть**.
4. Approval-gated tool execution, files capability — **есть**.
5. **Skills: безопасная загрузка, установка, enable/disable, uninstall** — **добавляется (этот MVP-блок)**.
   - manifest + strict validation
   - quarantine + archive safety (zip-slip/compression-bomb/symlink guards)
   - permissions model + user consent before enable
   - isolated process execution + timeout + cwd-confinement
6. Стабильность при ошибках (sanitized errors, error codes, no stack trace leak) — **есть/усиливается**.
7. Воспроизводимые гейты качества (npm/cargo/python) — **есть**.

## НЕ входит в MVP (post-MVP)
- Несколько inference-движков (контракт ModelRuntime зафиксирован, реализация — только llama.cpp).
- Skill update/rollback, подписи/сигнатуры пакетов (checksum — да, подпись — post-MVP).
- OS-level sandbox (seccomp/job objects) — зафиксировано как оговорка в SECURITY.md.
- Расширенная кастомизация, второстепенные интеграции.

## Критерии готовности MVP
- Все гейты зелёные (svelte-check, vitest, cargo test/fmt/clippy, python gates, smoke).
- Skills: полный lifecycle покрыт тестами (validate/zip-slip/size/permissions/enable-disable/uninstall).
- Нет P0-уязвимостей; P1 закрыты или задокументированы.
