# LocalComet — Документация проекта

## Обзор

LocalComet / LocalAgent — локальный Python-агент с маршрутизацией команд, LLM-планированием и браузерной автоматизацией.

## Архитектура

Поток: `Router → Planner → Executor → Agents → Modules`

- **Router** (`core/router.py`) — классификация команды по ключевым словам
- **Planner** (`core/planner.py`) — генерация JSON-плана через LLM
- **Executor** (`core/executor.py`) — диспетчеризация в агентов
- **Agents** (`agents/`) — тонкие адаптеры (18 агентов)
- **Modules** (`modules/`) — реализация (~140 модулей)

## Директории

| Директория | Назначение |
|---|---|
| `agents/` | Тонкие агент-адаптеры с `handle(action, data)` |
| `core/` | Ядро: router, planner, executor, llm, state, loop |
| `modules/` | Вся бизнес-логика: браузер, relay, self-edit, автоматизация |
| `next/` | Консоль v5/v6: app_v5, goal_manager, task_planner, task_queue |
| `desktop/` | Tauri + SvelteKit desktop-приложение |
| `tools/` | Тесты, утилиты, аудит, инсталлятор |
| `scripts/` | Вспомогательные скрипты (манифест, gateway) |

## Запуск

```powershell
python -m next.app_v5
python LocalComet_Control_Panel.py
```

## Тестирование

```powershell
python -m py_compile <file>
python tools/model_tester.py
python tools/hard_model_tester.py
python tools/test_gpt_bridge.py
python test_full_flow.py
```

## Конфигурация

`config.py`: LMSTUDIO_API, MODEL, OPENAI_MODEL, OPENAI_RESPONSES_API

## Workflow

`request.md → response.json → validate → apply → after patch`
