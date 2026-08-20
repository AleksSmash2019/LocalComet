---
title: LocalComet — итоговая скрытая верификация
date: 2026-08-20
status: verified_current
scope: security, runtime, UX/UI, model lifecycle, regression gates
---

# LocalComet — итоговая скрытая верификация

## Результат

В текущем рабочем дереве LocalComet завершён целевой цикл hardening и скрытой верификации. Ключевые security-границы, сценарий локального inference на Qwen3-1.7B, UX-состояния модели и поставляемый sidecar bundle проверены без открытия, закрытия или перезапуска пользовательского окна LocalComet. Новых веток и коммитов не создавалось; пользовательские модели и файлы не удалялись.

> Итог относится к текущему dev runtime и исходникам. Он не является заявлением о том, что каждая историческая зона проекта была переписана или что уже собран новый installer.

| Контур | Итог |
|---|---|
| Локальная базовая модель | Qwen3-1.7B Q4_K_M успешно прошла изолированный OpenAI-compatible chat smoke: первый ответ, продолжение разговора и новый чат вернули непустой ответ. |
| Security boundary | Проверены и закрыты точечные риски workspace mutations, DNS-rebinding/Proxy inheritance, default-folder Computer Use и integrity Skills. |
| Поставка sidecar | Build-source и `%LOCALAPPDATA%\LocalComet\DevRuntime` приведены к byte-for-byte parity: **258** совпадающих shipped-модулей. |
| Регрессии | Frontend, Rust, Python security/parity, CLI smoke, evidence provenance и require-mode real-sidecar прошли. |
| Обновление знаний | Результаты добавлены в существующую локальную заметку Obsidian Vault `2026-08-20 LocalComet effort-thinking и Vault.md`. |

## Выполненные улучшения

### Security и надёжность

В Python sidecar `files.create_folder` и `files.delete` отключены в fail-closed режиме. Это сознательный выбор: на Windows небезопасно выполнять такие мутации, пока не появится защищённая от junction/reparse-point гонок реализация. Пользователь получает честную блокировку, а не небезопасную «удобную» операцию.

`web.fetch` теперь отклоняет URL с credentials, ограничивает схему и порт, отключает proxy inheritance и фиксирует проверенный DNS-адрес для фактического подключения. Тем самым исключается смена адреса между проверкой и запросом, то есть DNS-rebinding. Computer Use больше не подменяет неизвестную папку рабочим root: такое действие возвращается как блокированное.

Перед разрешением `Skills` entrypoint повторно проверяется SHA-256 пакета. Дополнительно Rust Skills CLI resolver в release-сборке выбирает executable-скрипт только из package-bound местоположений; переменные тестовой среды и CWD fallback доступны лишь в debug-контуре. Это убирает возможность незаметно подменить CLI из произвольной директории процесса.

Canonical import custom GGUF теперь привязывает SHA-256 именно к импортируемому файлу и остаётся идемпотентным при повторном импорте. Изменённые Python-модули синхронизированы как с build source, так и с DevRuntime bundle, а parity затем перепроверена штатным гейтом.[2]

### UX/UI и модельный контур

Onboarding больше не утверждает, что «ИИ готов», когда готов только runtime: сообщение разделяет готовность движка и необходимость выбрать модель. Убрана постоянная декоративная вращающаяся hero-анимация; AppShell получил единый мягкий изумрудно-графитовый фон без отдельного визуального шума.

Кнопка голосового ввода отключена, пока нет действительно готовой модели. После отмены или ошибки распознавания черновик очищается, поэтому в строке чата не остаётся ложного текста. Qwen3.8-27B Q4_K_M была ранее обнаружена и штатно зарегистрирована в текущем LocalComet storage через hardlink; это не заменяет самостоятельное ресурсное тестирование её полного inference-профиля.

## Скрытый end-to-end тест Qwen3-1.7B

Для smoke создан изолированный сценарий `[tests/hidden_llama_runtime_smoke.ps1]`.[3] Он запускает только собственный `llama-server.exe` на loopback `127.0.0.1:18081` в CPU-only режиме, отправляет три OpenAI-compatible `/v1/chat/completions` запроса и в `finally` останавливает исключительно процесс, созданный этим тестом.

| Проверка | Результат |
|---|---|
| Модель Qwen3-1.7B Q4_K_M доступна в managed storage | PASS |
| Тестовый `llama-server.exe` доступен | PASS |
| Порт `18081` до запуска свободен | PASS |
| Readiness `/health` | PASS |
| Первый chat completion | PASS, непустой ответ |
| Продолжение разговора с историей | PASS, непустой ответ |
| Новый независимый чат | PASS, непустой ответ |
| Очистка тестового процесса и порта | PASS: порт свободен, зависшего процесса на `18081` нет |

В запросах отключён Qwen thinking trace именно для короткого smoke-бюджета. Это позволяет проверить пользовательский финальный `content`, а не ошибочно принять внутренний reasoning trace за пустой ответ. Тест был полностью скрытым: он не управлял окном LocalComet и не затронул запущенную пользовательскую сессию.

## Пройденные гейты

Набор соответствует обязательным инструкциям репозитория.[1] Команды выполнялись на системном Python `C:\Users\DNS\AppData\Local\Python\pythoncore-3.14-64\python.exe` и в локальном рабочем дереве.

| Группа | Последний подтверждённый результат |
|---|---|
| Frontend | `npm run check` — без Svelte diagnostics; Vitest — **26 файлов, 404 теста PASS**. |
| Rust | `cargo test` — **529 passed, 0 failed, 7 ignored**; `cargo fmt --check` — PASS; `cargo clippy --all-targets --all-features -- -D warnings` — PASS. |
| Skills regression | `test_skills_lifecycle.py` — **21 tests OK**; entrypoint security — PASS. |
| Fail-closed regression | `test_tool_execution_fail_closed.py` — **4 tests OK**. |
| Registry/parity | Command parity — **60 commands registered and invoked**; tool-risk registry — **19 entries valid**; Rust/Python tool-risk parity — PASS. |
| UI и import policy | `check_ui_fake_state.py` — **104 frontend files**, без fake-state violations; mockdata import gate — PASS. |
| Bundle | **258 shipped modules** совпадают с source в двух locations. |
| CLI / real sidecar | CLI smoke — **8 passed, 0 failed**; require-mode real-sidecar — PASS, без silent skips. |
| Evidence | **4 evidence files fresh and intact**, tree `8ea24f8b7cf4eae1…`. |

## Честные границы и следующий безопасный шаг

Текущий запущенный экземпляр LocalComet намеренно не перезапускался. Файлы build source и DevRuntime обновлены, однако уже импортированные Python-модули живого sidecar не меняются «на лету». Следующий обычный запуск приложения применит синхронизированные байты без принудительного завершения пользовательского процесса.

| Не закрыто этой сессией | Почему это важно |
|---|---|
| Исторические `unwrap()` в Rust | Нужен отдельный системный план с классификацией, а не массовая механическая замена, которая сама может внести ошибки. |
| Legacy `agent.py` | Не был удалён или перемещён: правила проекта запрещают удаление без отдельного согласия. Требуется отдельное решение о карантине или удалении. |
| Full inference Qwen3.8-27B | Модель зарегистрирована, но текущий smoke специально использовал лёгкую 1.7B CPU-only модель; hybrid/GPU профиль 27B требует отдельного ресурсного прогона. |
| Инсталлятор | Новый installer не собирался: для этого нужен чистый worktree и отдельная release-процедура. |

Сайт `localcomet.online` остаётся готовым к ручной публикации: checkpoint `3c5a04e9` содержит шесть понятных маршрутов и production build. Публикацию следует запускать только кнопкой **Publish** в интерфейсе управления проекта.

## References

[1]: ../AGENTS.md "Обязательные правила и гейты репозитория LocalComet"
[2]: ../scripts/check_bundle_parity.py "Проверка byte-for-byte parity поставляемого sidecar"
[3]: ../tests/hidden_llama_runtime_smoke.ps1 "Изолированный скрытый smoke-сценарий Qwen3-1.7B"
