# LocalComet / LocalAgent

Локальный Python-агент с маршрутизацией команд, планированием, выполнением через LLM и браузерной автоматизацией.

## Архитектура

```
user input
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Router  │────▶│ Planner  │────▶│ Executor │
│(core/)   │     │(core/)   │     │(core/)   │
└──────────┘     └──────────┘     └──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │  Agents  │
                                 │(agents/) │
                                 └──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │ Modules  │
                                 │(modules/)│
                                 └──────────┘
```

**Поток выполнения:**

1. **Router** (`core/router.py`) — определяет категорию команды (system, browser, code, file, windows и др.)
2. **Planner** (`core/planner.py`) — генерирует JSON-план действий через LLM
3. **Executor** (`core/executor.py`) — диспетчеризует план в соответствующий агент
4. **Agents** (`agents/`) — тонкие адаптеры, делегируют работу в modules
5. **Modules** (`modules/`) — реальная логика: браузер, ChatGPT relay, self-edit, автоматизация, диагностика

**LLM-доступ:** `core/llm.py` — LM Studio (локально) или OpenAI API (конфигурация в `config.py`).

**Состояние:** `core/state.py` + `memory/state.json` — персистентное хранилище ключ-значение.

**Workflow патчинга:** `request.md → response.json → validate → apply → after patch`

## Запуск

```powershell
# Основной консольный интерфейс (v5/v6)
python -m next.app_v5

# Tkinter-панель управления
python LocalComet_Control_Panel.py

# Патч-панель
python LocalComet_Patch_Panel.py
```

### Конфигурация

`config.py`:
- `LMSTUDIO_API` — эндпоинт LM Studio (по умолчанию `http://127.0.0.1:1234/v1/chat/completions`)
- `MODEL` — локальная модель (по умолчанию `qwen3-14b`)
- `OPENAI_MODEL` — модель OpenAI для relay
- `OPENAI_RESPONSES_API` — эндпоинт OpenAI Responses API

## Тестирование

```powershell
# Синтаксическая проверка изменённых файлов
python -m py_compile path/to/file.py

# Тесты моделей
python tools/model_tester.py
python tools/hard_model_tester.py

# Проверка GPT-моста
python tools/test_gpt_bridge.py

# Регрессионные тесты
python tools/test_v677_regression.py
python tools/test_v678_router_registry.py

# Stability test (через консоль)
# Ввести: stability test

# Полные flow-тесты
python test_full_flow.py
python test_full_flow2.py
python test_full_flow3.py
```

## Структура проекта

| Директория | Назначение |
|---|---|
| `agents/` | Тонкие агент-адаптеры. Каждый агент реализует `handle(action, data)` и делегирует работу в `modules/`. Включает: browser, code, file, operator, project, research, windows, system, workspace, diagnostics, history, maintenance, self_edit, gpt, chatgpt_relay, stability, automation, gpt_browser. |
| `core/` | Ядро оркестрации: маршрутизация (`router.py`), планирование через LLM (`planner.py`), выполнение (`executor.py`), доступ к LLM (`llm.py`), состояние (`state.py`), агентский цикл (`loop.py`), контекст проекта (`project_context.py`). |
| `modules/` | Реализация всей функциональности: браузерная автоматизация (browser*, computer_use_*), ChatGPT relay, self-edit, автоматизация, диагностика, workspace, отчёты, голосовое управление, knowledge-система, desktop-интеграция. ~140 модулей. |
| `next/` | Консольный интерфейс нового поколения (v5/v6): `app_v5.py` — главный цикл с shortcut-маппингом, `goal_manager.py` — анализ целей, `task_planner.py` — декомпозиция задач, `task_queue.py` — очередь задач, `observer.py` — наблюдение за страницей. |
| `desktop/` | Desktop-приложение на Tauri + SvelteKit: контракты IPC (`contracts/`), Rust-бэкенд и фронтенд (`localcomet-desktop/`). Управление артефактами, runtime-каталог, model-каталог. |
| `tools/` | Утилиты и тесты: тестеры моделей, GPT-bridge проверки, регрессионные тесты (v677–v6846), аудит-бандлы, preflight-проверки, инсталлятор, dev-лаунчер. |
| `scripts/` | Вспомогательные скрипты: генерация runtime-манифеста, ручной запуск model gateway. |

### Дополнительные файлы

| Файл | Назначение |
|---|---|
| `app.py` | Старый агентский цикл (legacy) |
| `agent.py` | Базовый агент-интерфейс |
| `config.py` | Конфигурация LLM-эндпоинтов |
| `LocalComet_Control_Panel.py` | Tkinter GUI панель управления |
| `LocalComet_Patch_Panel.py` | Панель применения патчей |
| `GenerateCapabilityMap.py` | Генерация карты возможностей |
| `memory/state.json` | Персистентное состояние агента |
| `Projects/` | Runtime-данные, отчёты, браузерный профиль |
| `docs/` | Архитектурная документация |
| `third_party/` | Сторонние зависимости |
