# LocalComet — Security Model

Дата: 2026-08-10. Источник истины по рискам: `security/invariants/tool_risk_levels.toml` (ровно три уровня: `read_only`, `guarded`, `dangerous`).

## 1. Границы доверия (threat model)

| # | Граница | Механизм защиты (текущий) |
|---|---------|---------------------------|
| 1 | Пользователь → UI | Локальный webview (Tauri), нет remote origin |
| 2 | UI → backend | Tauri commands, validate* на каждом ответе, command parity gate |
| 3 | Backend → inference | Managed llama.cpp, `--jinja`, bounded probes, health poll |
| 4 | Backend → FS | Workspace confinement, digest, reparse-point denial, allowlist типов, 2 MiB |
| 5 | Skill → host | **НЕ РЕАЛИЗОВАНО** — см. §3 |
| 6 | Model file → loader | SHA-256 + GGUF magic verify, canonical URL, launch-time TOCTOU revalidation |
| 7 | Архив → extractor | **Частично** (skills не реализованы); artifacts — hash-pinned catalog |
| 8 | Конфиг → runtime | Валидация манифестов, строгие схемы |
| 9 | Логи → секреты | Sanitized tails, без prompt/токенов |
| 10 | Локальные интерфейсы | 127.0.0.1 bind, no-redirect/no-proxy для внешних запросов |

## 2. Что проверено (2026-08-10)
- Нет захардкоженных секретов (scan по api-key/secret/token/bearer/sk-*) — только lockfile integrity-хэши.
- Approval envelope для guarded/dangerous: `token`, `approvalId`, `callId`, expiry, scope.
- Workspace escape блокируется (`policy_blocked` на `../escape.txt` — smoke step 06).
- Files capability: reparse-point/symlink denial, invalid-UTF8/binary denial, size cap.
- Раскрытие stack trace пользователю: нет (error codes вместо traceback).

## 3. Skills — модель безопасности (проект)

**Принцип: недоверенный skill НИКОГДА не исполняется в основном процессе sidecar и не получает секреты.**

### 3.1 Жизненный цикл
`upload → quarantine → validate archive → validate manifest → inspect permissions → verify checksum → install (atomic) → register → DISABLED by default → explicit enable → execute (restricted) → disable → uninstall (cleanup)`

Код skill **не исполняется** во время сканирования/валидации/установки.

### 3.2 Manifest (версионированный, строгая схема)
Обязательные поля: `id`, `name`, `version`, `entrypoint`, `permissions`.
Опциональные: `description`, `author`, `compatibleAppVersion`, `capabilities`, `configSchema`, `checksum`, `dependencies`.
Manifest не является доверенным — валидируется по схеме, все строки ограничены по длине, пути проверяются на traversal.

### 3.3 Permissions model
`filesystem.read`, `filesystem.write`, `network`, `model.invoke`, `clipboard`, `process.spawn`, `settings.read`, `settings.write`, `ui.extension`.
`secrets.access` — **запрещён всегда**, не выдаётся.
Разрешения показываются пользователю ДО enable. Skill запрашивает минимум.

### 3.4 Изоляция (MVP-уровень, честно)
- Skill исполняется в **отдельном процессе** Python с ограниченным IPC.
- Таймаут выполнения, отмена задачи, ограниченный рабочий каталог (sandbox dir).
- Нет наследования лишних env vars (env allowlist).
- Сеть: только если `network` permission; loopback-only по умолчанию.

**ОГОВОРКА MVP (честно, без ложных обещаний):** полноценной OS-sandbox (seccomp/job objects с жёсткими лимитами памяти/CPU) в MVP НЕТ. Поэтому:
- сторонние skills НЕ включаются автоматически;
- UI показывает предупреждение о недоверенном коде;
- исполнение в отдельном процессе + permissions + timeout + cwd-confinement;
- «полная безопасность» НЕ заявляется.

### 3.5 Загрузка архива (upload)
- Allowlist расширений: только `.zip`/`.tar.gz` skill-пакета.
- Magic bytes проверка (PK\x03\x04 / \x1f\x8b).
- Max размер архива, max распакованный размер, max число файлов (compression-bomb guard).
- Запрет абсолютных путей, `..`, symlink в архиве.
- SHA-256 checksum пакета, карантин → атомарное перемещение после валидации.
- Очистка temp при сбое, безопасные сообщения об ошибках.

## 4. Skills API
`list`, `upload`, `validate`, `install`, `enable`, `disable`, `uninstall`, `inspect_permissions`, `inspect_errors`, `get_version`. (`update/rollback` — post-MVP.)

## 5. Известные ограничения
- A-04: `open_model_storage_folder` делает spawn ОС-оболочки с валидированным model_root (принятый риск, под review).
- Нет rate limiting на loopback inference (локальная модель, accepted).
