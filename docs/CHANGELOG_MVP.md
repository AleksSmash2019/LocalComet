# Changelog — MVP

## 2026-08-10 — Skills subsystem (P1, MVP #2)

Добавлена безопасная система skills (`modules/skills/`):

- `skills_contract.py` — версионированный manifest (`localcomet.skill/1.0`), строгая валидация, bounded-поля, permissions model (9 grantable + `secrets.access` всегда запрещён), semver/id/sha256 проверки, traversal-safe entrypoint.
- `skills_archive.py` — безопасная распаковка: allowlist `.zip`/`.tar.gz`, magic bytes, max размер/число файлов/распакованный объём, compression-bomb ratio guard, zip-slip и symlink rejection, device-entry denial.
- `skills_manager.py` — lifecycle: quarantine → validate → checksum → atomic install (staging+rename) → register **DISABLED by default** → explicit enable → disable → uninstall с cleanup. JSON-registry, `entrypoint_path` гейтит исполнение на ENABLED.
- `tests/test_skills_lifecycle.py` — 17 тестов (manifest, zip-slip, missing manifest, corrupt, lifecycle, checksum mismatch, execute-gate). Все зелёные.

Docs: `AUDIT.md`, `SECURITY.md` (threat model + skills security + честная MVP-оговорка по sandbox), `ARCHITECTURE.md`, `MVP_SCOPE.md`, `PERFORMANCE.md`.

Исправлено ранее: `check_command_parity.py` (utility-команды), `tools/__init__.py` (import smoke).

Не сделано: update/rollback, подписи пакетов, OS-sandbox (post-MVP, зафиксировано в SECURITY.md), UI для skills (отдельная задача, Tauri commands пока не добавлены).
