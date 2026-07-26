# План работы команды из 10 агентов

## Классификация архитектуры

### Старая архитектура (v3)
- **Вход:** `app.py` — "LocalComet v3 — Agent Loop"
- **Папки:** `agents/`, `core/`, `modules/`
- **Паттерн:** route → plan → execute (линейный pipeline)
- **Агенты:** 18 тонких адаптеров `handle(action, data)`
- **Проблема:** циклическая зависимость core ↔ modules

### Новая архитектура (v5/v6)
- **Вход:** `next/app_v5.py` — "LocalComet v6.02 - Command Center"
- **Папки:** `next/`, `desktop/`, `tools/`, `scripts/`
- **Паттерн:** goal → plan → queue → observe (оркестрация задач)
- **Компоненты:** goal_manager, task_planner, task_queue, observer
- **Desktop:** IPC-контракты, sidecar runtime

### Общий слой
`core/` и `modules/` используются обеими архитектурами.

---

## Распределение задач

| # | Агент | Роль | Приоритет |
|---|-------|------|-----------|
| 1 | agent_01_architect | Разрыв цикла core ↔ modules | P1 |
| 2 | agent_02_refactor_app | Декомпозиция app_v5.py | P2 |
| 3 | agent_03_god_modules | Разделение god-модулей | P3 |
| 4 | agent_04_security | Безопасность и легаси | P4 |
| 5 | agent_05_testing | Тестирование | P2 |
| 6 | agent_06_desktop | Десктопное приложение | P3 |
| 7 | agent_07_browser | Браузерная автоматизация | P3 |
| 8 | agent_08_knowledge | Система знаний | P3 |
| 9 | agent_09_ui | UI и Control Panel | P4 |
| 10 | agent_10_docs_ci | Документация и CI | P2 |

---

## Детальные задачи

### 1. Архитектор (P1)
Разорвать циклическую зависимость core ↔ modules:
- Вынести `core/state.py` → `common/state_store.py`
- Убрать импорты core.router/planner/executor из modules
- Создать интерфейс для modules → core

### 2. Рефакторинг app_v5 (P2)
Декомпозировать `next/app_v5.py` (2039 строк):
- Заменить 12 функций `_run_direct_*` на реестр команд `core/commands.py`
- Перенести SHORTCUTS (120+ записей) в `core/router.py`
- Оставить в app_v5 только REPL-цикл

### 3. Декомпозиция god-модулей (P3)
Разделить модули > 1500 строк:
- `premium_task_panel_ru` (2957) → panel_core + panel_widgets + panel_state
- `desktop_control_plane_ru` (2208) → control_plane + ipc_handler + supervisor
- `computer_use_contract_tests_ru` (1818) → contract_fixtures + contract_runner
- `local_model_gateway_ru` (1811) → gateway_core + model_registry + health_check
- `stability_test` (1664) → test_runner + test_fixtures + test_reporter

### 4. Безопасность и легаси (P4)
- Устранить shell-инъекцию в `agent.py:search_web()`
- Убрать хардкод LLM URL из agent.py
- Заменить `app.py` на редирект к `next/app_v5`
- Убрать прямые импорты core.state из 5 агентов

### 5. Тестирование (P2)
- Создать pytest-совместимый runner для tools/
- Интеграционные тесты для next/task_planner, next/goal_manager
- Покрыть regression_commands и auto_verification
-_target: 80% покрытие core/ и next/_

### 6. Десктоп (P3)
- Развитие `desktop/contracts/` IPC-схем
- Синхронизация sidecar runtime с control plane
- Тесты для desktop IPC в tools/

### 7. Браузерная автоматизация (P3)
Консолидация 10+ browser_* модулей:
- Создать `modules/browser_facade.py` — единая точка входа
- Устранить дублирование: browser_direct, browser_autopilot, browser_super, browser_operator
- Единый интерфейс для agents/browser_agent.py

### 8. Система знаний (P3)
Унификация 11 knowledge_* модулей:
- Pipeline: proposal → review → decision → injection
- Единый `modules/knowledge_pipeline.py`
- Интеграция с core/state для персистентности

### 9. UI и Control Panel (P4)
- Стабилизация `LocalComet_Control_Panel.py`
- Убрать дублирование premium_ui_* (3 модуля → 1)
- Интеграция с command_center_ui

### 10. Документация и CI (P2)
- Создать `docs/engineering/adr-002-target-architecture.md`
- Настроить GitHub Actions: py_compile + tools/ тесты
- Обновить README.md с новой архитектурой
- Документировать контракты для каждого агента

---

## Порядок выполнения

```
Фаза 1 (P1-P2): architect → refactor_app → security → testing → docs_ci
Фаза 2 (P3):    god_modules → desktop → browser → knowledge
Фаза 3 (P4):    ui
```

## Критерии готовности

- [ ] Нет циклических импортов core ↔ modules
- [ ] app_v5.py < 300 строк
- [ ] Нет модулей > 800 строк
- [ ] Все агенты используют фасад state_store
- [ ] Покрытие тестами core/ и next/ ≥ 80%
- [ ] CI проходит без ошибок
