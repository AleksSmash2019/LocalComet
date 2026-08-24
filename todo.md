- [ ] Проверить фактическое состояние backend-процесса, порта и журналов запуска LocalComet.
- [ ] Найти причину ERR_CONNECTION_REFUSED без удаления файлов и без остановки сторонних процессов.
- [ ] Подтвердить восстановление доступа окна LocalComet к локальному сервису.
- [x] Сверить указанные в приложенном аудите источники и shipped runtime с актуальным кодом.
- [ ] Определить, какие подтверждённые проблемы требуют отдельного согласования до исправления.
- [x] Проверить все исходные и installed entrypoint скиллов на shell=True и непроверенный shell-режим.
- [x] Проверить покрытие security-теста всеми поставляемыми entrypoint скиллов.
- [ ] Проверить реестр на включённые тестовые скиллы и рассинхрон лимита времени вызова.
- [x] Убрать выполнение через shell и оставить только явные списки аргументов с allowlist для разрешённых действий.
- [x] Проверить, что исправления синхронизированы в поставляемом runtime и не раскрывают внутренние детали в UI.
- [x] Проверить доступность Qwen 1.7B и подготовить изолированный hidden smoke-сценарий без управления видимым окном.
- [x] Выполнить hidden пользовательские сценарии: запуск, первый ответ, новый чат и корректная ошибка при недоступности.
- [x] Зафиксировать результаты hidden проверки и не менять пользовательскую сессию без явного согласования.
- [x] После hidden проверки обновить фон desktop-интерфейса: зелёная комета, мягкий световой след и ненавязчивые орбитальные линии с сохранением контраста текста.
- [x] Исправить голосовой ввод: при отсутствии подключённой модели не оставлять распознанный черновик в строке чата и всегда очищать его при отмене или ошибке.
- [x] Переработать кометный фон: убрать крупные орбиты, ослабить свечение и оставить один спокойный брендовый акцент вне рабочей зоны.
- [x] Убрать отдельную комету и сделать единый мягкий фон, покрывающий sidebar, рабочее поле и нижнюю строку приложения.
- [x] Доработать единый фон: добавить мягкие зелёные слои, деликатную виньетку и глубину без заметных декоративных объектов.
- [x] Проверить наличие файла и запись Qwen 3.8 27B в реестре моделей без запуска или переключения модели.
- [x] Повторно найти Qwen 3.8 27B на всём диске C, включая скрытые системные каталоги, без перемещения или удаления файла.
- [x] Добавить найденный Qwen3.8-27B-Q4_K_M.gguf в текущий LocalComet штатным импортом и подтвердить его видимость в списке.
- [x] Диагностировать и устранить LC_START_101, затем подтвердить запуск без потери регистрации Qwen 3.8 27B.
- [x] Исправить canonical contract импорта пользовательского GGUF и добавить regression test успешной регистрации валидной модели.
- [x] Закрыть текущий экземпляр LocalComet по разрешению пользователя и запустить приложение заново после проверок.
- [x] Снять скрытый baseline LocalComet: репозиторий, runtime, ресурсы и доступные модели без изменения пользовательской сессии.
- [x] Исследовать лучшие практики LM Studio, Ollama и llama.cpp для локального inference и UX.
- [x] Провести скрытый аудит критических пользовательских потоков, производительности, безопасности и восстановления ошибок.
- [x] Реализовать только подтверждённые улучшения с unit и regression-проверками.
- [x] Прогнать изолированные end-to-end и ресурсные сценарии и подготовить честный отчёт об ограничениях.
- [ ] Оценить и усилить архитектуру запуска, восстановление после сбоев и прозрачность состояния runtime.
- [x] Закрыть подтверждённые security-hardening риски в workspace, web.fetch, skills и Computer Use.
- [ ] Улучшить модельный UX: preflight ресурсов, объяснение CPU/GPU/Hybrid, очередь и безопасный unload.
- [x] Провести UX/UI-проход по первому запуску, чату, голосу, Computer Use, ошибкам и визуальной иерархии.
- [x] После hidden проверки обновить фон desktop-интерфейса: мягкая глубина, изумрудные акценты и сохранение контраста текста.
- [x] Восстановить выпадающий выбор verified установленных моделей в Model Setup Drawer вместо ошибочного стартового экрана подключения.
- [x] Удалить по прямому указанию пользователя только managed артефакт Qwen2.5 1.5B, сохранив Qwen3-1.7B и Qwen3.8-27B.
- [x] Удалить по прямому указанию пользователя Qwen2.5 7B и показывать в селекторе только установленные валидные модели.
- [x] Провести скрытый функциональный аудит Computer Use: окна, приложения, заметки, файлы, разрешения, ошибки и восстановление.
- [x] Исправить подтверждённые отказные сценарии Computer Use и отполировать его UI без удаления пользовательских данных.
- [x] Провести детальный UX/UI-аудит LocalComet: первый запуск, модели, compute-режим, чат, Computer Use, ошибки и доступность.
- [x] Реализовать и скрыто проверить приоритетные UX/UI улучшения без ложных backend-состояний.
- [x] Снять hidden baseline Computer Use, ответов локальной модели и engine runtime; сопоставить его с подходящими open-source практиками.
- [x] Внедрить и проверить только совместимые с LocalComet улучшения надёжности и отзывчивости model/engine/Computer Use контуров.
- [x] Построить воспроизводимые hidden regression-тесты Computer Use, UI и model-engine lifecycle с явными failure assertions.
- [x] Прогнать расширенный quality-набор многократно и исправить только подтверждённые дефекты до финальной verified-документации.
- [ ] Независимо проверить F-01—F-04 из приложенного аудита: permission enforcement, Computer Use approval path, regression-gate contract и вложенные UI preferences.
- [ ] После явного согласования boundary исправить подтверждённые security/functional defects и добавить negative regression coverage.
- [ ] Пассивно определить причину зависания tools/test_v6846_tool_execution.py без остановки процесса или пользовательских компонентов.
- [ ] Внедрить backend-authoritative per-session capability state и permission_denied до tool dispatch.
- [ ] Убрать allowlisted Computer Use bypass и требовать scoped one-time approval grant на опасное действие.
- [ ] Исправить shared nested agentPermissions defaults и привести F-03 regression к fail-closed security contract.


## Current continuation board — 2026-08-24

Контекст этой секции актуальнее исторических пунктов выше. Старые пункты не удаляются и не переписываются.

- [x] Зафиксировать единую ветку `feat/up00-wp01-windows-one-click-launch` и текущий HEAD `962503816099ce2cddf412b51ae0fe77fc299f20` до commit.
- [x] Обновить Obsidian `Status.md`, `Blockers.md`, единый индекс, корневую страницу и session note текущей фактической оценкой **7,2/10**.
- [x] Сохранить все текущие WIP-наработки: screenshot IPC/UI, pinned Qwen3, host CU broker, bounded task contracts, parser/schema/risk changes, UI cleanup и runtime parity.
- [x] Добавить explicit capability mappings для `import_custom_model`, `cu_broker_observe`, `speak_local_text` и `stop_local_text`; capability/security contract tests PASS.
- [x] Исправить repo-level Cargo routing: target/build directories больше не указывают абсолютный machine-specific путь и резолвятся наружу из репозитория.
- [x] Восстановить in-memory archive helpers для Skills lifecycle; `tests/test_skills_lifecycle.py` PASS.
- [x] Исправить hidden UIA type-test import boundary и сохранить fail-closed UIA assertions.
- [x] Исправить security-negative false positive для `std::process::ExitStatus` и оставить запрет реальных `exit()/abort()` вызовов.
- [x] Запретить Calculator в hidden/automatic host-broker mode до любого spawn; alias regression переведён в pure no-spawn test.
- [x] Проверить новый Calculator guard и pure alias test: PASS; новые Calculator runs не выполнять.
- [x] Не трогать внешний пользовательский helper `N:\ANTHOLOGY\...\start_helper.ps1` и его процессы; ownership LocalComet не доказан, внешние процессы не изменялись.
- [x] Устранить sidecar liveness starvation во время длительного Computer Use call: single-flight coordinator, health interleave, busy response, runtime RLock; real-runtime regression PASS.
- [x] Повторно доказать named-hidden цепочку Notepad: host broker launch → readiness/continuation → type → independent UIA text proof; one case `VERIFIED_SUCCESS`.
- [ ] Доказать production UIA grounding для безопасных click/double-click без coordinate/search-only fallback.
- [x] Выполнить post-fix targeted gate matrix и refresh evidence provenance: CURRENT evidence **4/4 fresh and intact**, tree `19fa0c05d9582b46...`; полный auto-discovered matrix не запускался повторно из-за прежнего hang.
- [ ] Сделать commit только после финальной проверки состава всех сохранённых изменений; удаление reports/worktrees/stashes/models не входит в текущий scope.


### Checkpoint — 2026-08-24 после Calculator guard и liveness patch

- [x] Подтвердить отсутствие Calculator execution path в Rust tests; alias test теперь pure no-spawn.
- [x] Добавить hidden/automatic host-broker guard, блокирующий Calculator до любого spawn.
- [x] Устранить обнаруженную runner starvation seam: `tool.call` работает single-flight daemon worker, `app.health` interleaves, concurrent tool call получает bounded `busy`.
- [x] Добавить и пройти v6.84.3 regression: **261 checks PASS**, включая real-runtime state-lock interleave и hidden-harness classifier/scenario guards.
- [x] Полный Rust library suite: **568 passed, 0 failed, 7 ignored**; `cargo fmt --check` и clippy `-D warnings` PASS.
- [x] Evidence provenance refresh: **4/4 fresh and intact**, current tree `19fa0c05d9582b469c927c5745fbb6c49f76826d052eec95c6cceb73d63fe770`.
- [x] Bundle parity после runtime sync: **422/422 modules match**, exit 0.
- [x] Повторить единственный безопасный named-hidden Notepad flow после liveness/digest patch и получить independent UIA text proof: `VERIFIED_SUCCESS`; Calculator не запускался.
- [x] Обновить score/status перед commit: текущая оценка **8,1/10**, public acceptance остаётся `NOT_FINALLY_ACCEPTED` из-за открытых click/screenshot/task blockers.
