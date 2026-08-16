# Changelog — MVP

## 2026-08-14 - Block 3 Orchestration & Full Computer Use (P1, MVP #4)

- **Orchestration Loop**: Внедрен и стабилизирован многошаговый цикл выполнения команд инструментов (Model Gateway -> Control Plane -> Tool Execution -> Shell Store). Обработка `messages: []` полностью типизирована и покрыта тестами.
- **Computer Use**: Инструмент `computer_use` (риск: dangerous) полностью активирован и интегрирован.
  - Настройки `uiPreferences.ts` обновлены для персистентного хранения разрешений.
  - По умолчанию включен доступ к ПК (`computerUse: true`).
  - Python-сайдкар корректно делегирует высокоуровневые экшены (open_app, click, type и др.) в `modules/computer_use_real_actions_ru.py` с соблюдением границ изоляции.
- **UI Aesthetics**: Иконки обновлены для соответствия премиальному стилю современных IDDE (stroke-width: 1.5).

## 2026-08-14 — Voice Mode & System Tools (P1, MVP #3)

Добавлен новый функционал и исправлена консистентность инструментов:

- `system.time` — зарегистрирован новый инструмент во всех слоях безопасности: добавлен в `security/invariants/tool_risk_levels.toml`, `modules/tool_execution_ru.py` (в `SUPPORTED_TOOLS`), `modules/local_model_gateway_ru.py` (в `TOOL_REGISTRY`). Обновлены тесты четности (`test_adr015_tool_parsing.py`, `test_tool_risk_rust_parity.py`) для синхронизации количества тулзов.
- **Voice Mode (Голосовой режим)** — внедрен в UI:
  - STT (Speech-to-Text): интеграция Web Speech API в `MessageComposer.svelte` для голосового ввода.
  - TTS (Text-to-Speech): интеграция синтеза речи в `MessageList.svelte`, автоматическое зачитывание ответов ассистента.
  - Состояние UI: добавлена переменная `voiceMode` в сторы приложения (`uiPreferences.ts`, `shellStore.ts`).
- **Audit & Tests**: Успешно проведена валидация всех инвариантов. Скрипт `Run-Gates.ps1` завершился с `Verdict: PASS` (66 из 66 тестов) после обновления provenance (доказательств). Багов и десинхронизаций между Python и Rust слоями нет.

## 2026-08-10 — Skills subsystem (P1, MVP #2)

Добавлена безопасная система skills (`modules/skills/`):

- `skills_contract.py` — версионированный manifest (`localcomet.skill/1.0`), строгая валидация, bounded-поля, permissions model (9 grantable + `secrets.access` всегда запрещён), semver/id/sha256 проверки, traversal-safe entrypoint.
- `skills_archive.py` — безопасная распаковка: allowlist `.zip`/`.tar.gz`, magic bytes, max размер/число файлов/распакованный объём, compression-bomb ratio guard, zip-slip и symlink rejection, device-entry denial.
- `skills_manager.py` — lifecycle: quarantine → validate → checksum → atomic install (staging+rename) → register **DISABLED by default** → explicit enable → disable → uninstall с cleanup. JSON-registry, `entrypoint_path` гейтит исполнение на ENABLED.
- `tests/test_skills_lifecycle.py` — 17 тестов (manifest, zip-slip, missing manifest, corrupt, lifecycle, checksum mismatch, execute-gate). Все зелёные.

Docs: `AUDIT.md`, `SECURITY.md` (threat model + skills security + честная MVP-оговорка по sandbox), `ARCHITECTURE.md`, `MVP_SCOPE.md`, `PERFORMANCE.md`.

Исправлено ранее: `check_command_parity.py` (utility-команды), `tools/__init__.py` (import smoke).

Не сделано: update/rollback, подписи пакетов, OS-sandbox (post-MVP, зафиксировано в SECURITY.md), UI для skills (отдельная задача, Tauri commands пока не добавлены).
