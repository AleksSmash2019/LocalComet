# LocalComet — Technical Audit

Дата аудита: 2026-08-10. Аудитор: Hermes (supervisor). Ветка: `feature/donor-ui-compatible-port`, HEAD `375193f`.

## 1. Инвентаризация

### Стек
| Слой | Технология | LOC |
|------|-----------|-----|
| Frontend | Svelte 5 + SvelteKit + Vite 8 (Tauri 2 webview) | ~29.4k TS/Svelte |
| Desktop shell | Rust (Tauri 2), 22 файла | ~32.8k |
| Python sidecar / agents | Python 3.11/3.14, 134 модуля в `modules/` | ~138.5k |
| Тесты Python | 55 файлов | ~22.8k |
| Тесты TS | 26 файлов, 390 тестов | — |

### Точки входа
- Desktop app: `desktop/localcomet-desktop` (`npm run tauri dev`), Rust entry `src-tauri/src/lib.rs::run()`
- Python sidecar: запускается Rust `DesktopSidecarSupervisor`, протокол `localcomet.ipc/1.0` (length-prefix 4-byte BE, max 4 MiB)
- Legacy CLI: `next/app_v5.py`, `agent.py`, `app.py` (устаревшие пути, вне desktop-продукта)

### Реально работает (подтверждено гейтами 2026-08-10)
- Desktop UI + Control Plane bridge, 49 Tauri-команд (parity holds)
- Managed runtime (llama.cpp) lifecycle: catalog → download → verify SHA-256/GGUF → install → load → inference
- HF-браузер: search/list/download с coalescing progress, cancel, lifecycle stages
- Approval envelope для guarded/dangerous команд
- Files capability (confined, read-only, allowlist типов, 2 MiB)
- Smoke CLI: 8/8, sidecar hello/health/capabilities/duplicate-id/policy/tool.call/catalog/shutdown

### Заявлено, но не завершено / отсутствует
- **Skills/плагины как продуктовая система — ОТСУТСТВУЕТ.** `skills/` в репо нет (только внешние `.agents/.claude/.hermes` — это НЕ часть продукта). `modules/skills_loader_ru.py` упоминается в README, но файла нет. Есть только `modules/swiss_knife_skill_launcher.py` — это не loader, а отдельный workflow с deny-list. **Manifest/lifecycle/permissions/sandbox не реализованы.**
- Версионный дрейф: app 6.84.6 / shell 6.84.5.1 / IPC 6.84.1 / sidecar 6.84.3 / gateway 6.84.5
- Legacy CLI-пути (`next/`, `agent.py`, `app.py`, `LocalComet_Control_Panel.py`) дублируют продукт и путают границы модулей

## 2. Baseline (2026-08-10, все гейты зелёные)

| Метрика | Значение |
|---------|----------|
| svelte-check | 0 errors, 0 warnings |
| vitest | 390 passed / 26 файлов, ~1.6 s |
| cargo test | ok (unit в lib через отдельные таргеты) |
| cargo clippy `-D warnings` | clean |
| command parity | 49/49 |
| CLI smoke | 8/8 |
| trust-chain invariants | 15 файлов OK |
| bundle parity | OK |
| evidence provenance | 4 файла fresh (после refresh) |
| Реальные секреты в репо | не найдены (только lockfile integrity-хэши) |

Метрики cold start / TTFT / tokens/s / RAM-VRAM — **не измерялись** (нет bench-инфраструктуры).

## 3. Реестр проблем

| ID | Проблема | Серьёзность | Компонент | Последствия | План | Статус |
|----|----------|-------------|-----------|-------------|------|--------|
| A-01 | Skills-система отсутствует как продукт | **high** | product | Нет безопасной загрузки/enable/disable плагинов — блокер цели MVP #2 | Спроектировать manifest + lifecycle + permissions (см. SECURITY.md) | open |
| A-02 | Версионный дрейф 6.84.x | medium | versioning | Рассинхрон контрактов, ложная уверенность в совместимости | Единый source of truth версии | open |
| A-03 | Legacy CLI дублирует продукт | medium | architecture | Путаница границ, мёртвый код, риск правок не того пути | Пометить legacy / изолировать | open |
| A-04 | `open_model_storage_folder` открывает путь через shell | medium | artifact_trust.rs | Потенциально опасный spawn (explorer.exe) | Валидация что путь == model_root (уже есть), оставить под review | mitigated |
| A-05 | Нет bench-инфраструктуры производительности | low | observability | Нельзя подтвердить «быстрый inference» | Добавить bench harness | open |
| A-06 | Мусор в working tree (.agents/.claude/.freebuff/nul/run_7_cycles.py) | low | repo hygiene | Риск попадания в коммит | Исключить/удалить (по правилам — с разрешения) | open |

## 4. Что НЕ является доказательством (по AGENTS.md)
Авторитет: байты на диске, SHA-256, exit codes, пройденные тесты. Не авторитет: self-report, логи, markdown, состояние фронта.

## 5. Приоритеты
- **P0**: подтверждено отсутствие — RCE/потеря данных/обход approval не найдены в активных путях (approval envelope + workspace confinement + allowlist). Требует независимой верификации.
- **P1**: A-01 (skills), стабилизация inference UX, A-02.
- **P2**: A-03, A-05, упрощение дублирования.
- **P3**: второстепенные интеграции.
