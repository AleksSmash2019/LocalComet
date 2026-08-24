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


## Roadmap до 9,5/10 — 2026-08-25

**Цель:** поднять LocalComet с текущих **8,1/10** до честного минимума **9,5/10** и, если все критерии реально закрываются, до **10/10**. Нельзя считать задачу закрытой по одному `exit 0`: каждый пользовательский поток должен иметь независимый postcondition proof, корректную authorization/correlation evidence и честный terminal verdict.

**Ограничения кампании:** только named hidden desktops для GUI; без физического пользовательского desktop; без автоматических Calculator-запусков; внешний Anthology helper не трогать; не запускать кампании на 100/200/1000 сценариев; сохранять Qwen3-1.7B Q4_K_M без silent substitution; не удалять отчёты, worktrees, stashes, модели и runtime caches вслепую.

| Шаг | Направление | Что сделать | Критерий завершения | Статус |
|---:|---|---|---|---|
| 1 | Baseline и acceptance matrix | Зафиксировать 8,1/10, commit `b8d6bac`, открытые blockers и единый список базовых действий | Matrix содержит browser, folders, files, Notepad, type/paste/key/hotkey/wait/scroll, click/double-click, screenshot, task и voice; для каждого задан verdict contract | DONE |
| 2 | Готовые skills | Провести read-only inventory доступных LocalComet/Obsidian skills и известных Computer Use подходов | Для каждого кандидата указаны источник, лицензия, зависимости, security risks, Windows compatibility и решение `adopt/adapt/reject`; без слепого копирования | IN_PROGRESS |
| 3 | Skill adapter | Подключить только принятые skills через существующий skills runtime и capability boundary | Skill не получает произвольный shell/filesystem; permissions explicit; deterministic dispatch, timeout, cancellation и error envelope покрыты tests | BLOCKED_BY_2 |
| 4 | Browser/open_url | Исправить текущую ошибку «Открой браузер хром», разделив `open_app chrome` и HTTPS `open_url`; добавить Chrome discovery, readiness, single-instance/reuse и честный failure | На новом hidden desktop: Chrome запускается/переиспользуется, HTTPS URL открывается, readiness подтверждается, invalid/non-HTTPS URL блокируется, никакого physical-browser control | P0 |
| 5 | Папки | Довести `open_folder`, list/create folder и navigation до workspace-constrained поведения | Valid folder работает; outside workspace, symlink/reparse, missing path и malformed input дают fail-closed result; independent filesystem postcondition | P0 |
| 6 | Файлы | Довести list/read/create/write с atomicity, encoding, size limits и recovery | Test files создаются только в temp workspace; bytes/hash/contents проверяются независимо; partial write и path escape не проходят | P0 |
| 7 | Notepad и базовые actions | Закрепить launch→readiness→type/paste→key/hotkey→wait→UIA proof; добавить устойчивость к focus/readiness race | Fresh hidden Notepad даёт `VERIFIED_SUCCESS` по exact marker/UIA/process/scope/correlation; errors остаются `VERIFIED_FAILED` или `NOT_INDEPENDENTLY_VERIFIED` | P0 |
| 8 | UIA grounding | Реализовать production-safe semantic grounding для click/double-click/scroll/drag; убрать search-only и coordinate-only false positives | Реальный target найден по role/name/automation id, target scope подтверждён, action postcondition проверен; coordinate fallback не считается PASS | P0 |
| 9 | Observe/screenshot | Довести hidden screenshot backend, capture metadata, scope/hash/bytes и observe-after-action | Fresh hidden screenshot имеет PNG magic, sha256, backend, scope, byte count и correlated action IDs; capture failure не превращается в PASS | P0 |
| 10 | Multi-step task | Замкнуть bounded observe→action→observe loop с max 8 steps, continuation, replan, stop и liveness | Один ограниченный task-level hidden flow получает `VERIFIED_SUCCESS` с каждым шагом correlated; timeout/cancel/uncertain state дают terminal non-PASS | P1 |
| 11 | Голос и характер | После стабилизации core flow подобрать спокойный русскоязычный voice profile, добавить лаконичный характер LocalComet и исправить Stop lifecycle | Voice start/stop idempotent, no replay loop, stale completion ignored; personality не меняет security decisions и не раскрывает внутренние данные | P1 |
| 12 | Security/performance/resources | Провести audit grants, allowlists, IPC limits, memory/temp/cache growth, process ownership и cleanup policy | Security-negative gates PASS; no orphan owned workers; memory/temporary files bounded; чужие процессы не останавливаются | P0/P1 |
| 13 | Verification matrix | Добавить deterministic tests и ограниченный hidden acceptance: по одному representative flow на каждый класс, без массовой кампании | Python/Rust/frontend/bundle/evidence gates PASS; каждый live row имеет один из корректных verdict classes и supporting proof | P0 |
| 14 | Release decision | Обновить evidence, Obsidian, scorecard и сделать один clean commit только после review | 9,5/10 разрешается только при закрытых P0 и доказанных representative flows; 10/10 — только при полном закрытии P0/P1, adaptive red-team, recovery и независимой повторной приёмке | FINAL |

### Целевые критерии оценки

| Область | Минимум для 9,5/10 |
|---|---|
| Browser | Открытие Chrome и HTTPS-навигация независимо подтверждены на hidden desktop; readiness/reuse/error paths проверены |
| Folders/files | CRUD и navigation работают в разрешённом workspace, path escape/symlink/reparse/partial-write закрыты |
| Notepad/actions | Launch, focus, type, paste, key, hotkey, wait и UIA postcondition имеют live proof |
| UIA | Click/double-click/scroll/drag grounded по реальным semantic targets; search-only и coordinate-only доказательства отклоняются |
| Observe | Screenshot/observe proof независимы и содержат scope/hash/backend/bytes/correlation |
| Orchestration | Bounded task умеет продолжение, replan, stop, timeout и не теряет liveness |
| Security | Approval/session capability, grant digest, broker allowlist, IPC limits и fail-closed errors покрыты negative tests |
| UX/voice | Характер последователен и краток; русский голос приятен; Stop не допускает циклов и stale playback |
| Evidence | Свежие evidence, clean branch, reproducible commands; exit 0 не подменяет product PASS |

### Текущий dashboard checkpoint

- **DONE:** Calculator hidden/automatic guard; sidecar liveness; false-PASS classifier; canonical input digest; named-hidden Notepad single-case `VERIFIED_SUCCESS`; targeted gates; commit `b8d6bac`.
- **IN PROGRESS:** browser/open_url failure diagnosis; inventory/adaptation of ready-made skills.
- **OPEN P0:** browser; folders/files; UIA semantic grounding; screenshot revalidation; task-level live proof.
- **OPEN P1:** personality/voice polish; broader performance/resource audit.
- **Release rule:** до закрытия всех P0 итоговый статус остаётся `NOT_FINALLY_ACCEPTED`, даже если все offline tests зелёные.

### Следующий конкретный микроцикл

1. Завершить read-only browser diagnosis и сопоставить ошибку с точным execution path.
2. Выполнить inventory готовых skills и выбрать только совместимые с LocalComet boundary.
3. Исправить browser/open_url, затем добавить deterministic regressions.
4. Проверить один browser flow и один folder/file flow на свежих named hidden desktops.
5. Только после этого переходить к UIA grounding и screenshot/task acceptance.


## Автономный режим — дополнение после web-исследования — 2026-08-25

**Исследовательская база:** OpenAI Computer Use/API и CUA safety, Anthropic Computer Use и Building Effective Agents, OSWorld NeurIPS benchmark, OWASP Top 10 for Agentic Applications 2026 и NIST CAISI agent-hijacking evaluation. Полные findings и URLs сохранены в `audit/computer_use_autonomous_agent_research_20260825.md`.

### Как должен работать полностью автоматический LocalComet

Пользователь один раз задаёт цель обычным языком. LocalComet переводит её в typed plan с разрешёнными приложениями, доменами, путями, лимитом шагов, временем, retry budget и проверяемым postcondition. Далее цикл выполняется без ручного подтверждения каждого безопасного шага:

`goal → intent compile → plan → observe → choose skill/action → policy gate → execute → observe → verify → continue/replan → complete/stop`

На каждом шаге агент обязан получать ground truth из среды. После запуска приложения проверяется readiness, после ввода — реальное содержимое через UIA, после записи файла — bytes/hash, после browser navigation — URL/readiness, после клика — изменение состояния target. `PASS` без независимого postcondition запрещён.

Если агент встречает untrusted content, prompt injection, выход за scope, неизвестный target, попытку расширить allowlist, credential/login, delete, install, send/submit, financial/terms action, превышение бюджета или неопределённое состояние, он не продолжает молча: делает `PAUSED_FOR_REVIEW`/`BLOCKED` и показывает пользователю причину. Emergency Stop и handoff должны немедленно остановить pending work и заблокировать stale completions.

### Профили автономности

| Профиль | Что разрешено | Когда использовать |
|---|---|---|
| Assist | План и действия предлагаются, пользователь подтверждает | Новые/неизвестные сценарии и sensitive data |
| Bounded autonomous | Агент сам выполняет действия внутри заранее заданного scope и budgets | Основной целевой режим LocalComet |
| Supervised autonomous | Автономный loop, но с visible monitoring и takeover на browser/external side effects | Browser forms, login, внешние сайты |
| Unrestricted desktop | Произвольное управление без scope, stop и evidence | Не поддерживать: это небезопасно и не является критерием качества |

### Definition of Done для уровней

| Уровень | Объективное условие |
|---|---|
| 8,1/10 | Рабочие broker/Notepad foundations, liveness и targeted contracts; открытые browser/UIA/screenshot/task blockers |
| 9,5/10 | Все P0 закрыты: browser, folders/files, Notepad actions, semantic UIA grounding, screenshot/observe, bounded task; representative hidden flows имеют independent proofs; нет false PASS |
| 10/10 | Уровень 9,5 плюс adaptive red-team/agent-hijacking tests, reliable recovery/cancellation, memory/resource budgets, UX/voice polish, reproducible cross-app workflows, clean evidence и независимая повторная acceptance; никаких известных P0/P1 blockers |

### Autonomous-agent implementation board

- [ ] **A1 Intent compiler:** typed task plan, expected postconditions, allowed scope и risk class.
- [ ] **A2 Planner/skill router:** выбор готового skill или native primitive без права расширить permissions.
- [ ] **A3 Observation ledger:** screenshot/UIA/DOM/filesystem observations с untrusted-content marker и hashes.
- [ ] **A4 Policy gate:** action-by-action decision для ReadOnly/Guarded/Dangerous, domain/path/process allowlists и confirmation checkpoints.
- [ ] **A5 Execution loop:** ordered batches, max steps/time/retries, idempotency keys, checkpoints и continuation.
- [ ] **A6 Verifier:** независимые postconditions для browser, folders, files, Notepad, clicks и task completion.
- [ ] **A7 Recovery controller:** bounded retry, replan, backoff, rollback/cleanup, `PAUSED_FOR_REVIEW` при uncertainty.
- [ ] **A8 Stop/handoff:** immediate cancel, stale-result rejection, visible status, manual takeover и emergency Stop.
- [ ] **A9 Security tests:** indirect prompt injection, untrusted file/page instructions, exfiltration, download-run/RCE, phishing-like send и scope escalation.
- [ ] **A10 Resource/observability:** task ledger, correlation IDs, action/observation digest, memory/temp/process budgets и diagnostic redaction.
- [ ] **A11 Representative acceptance:** browser→file, Notepad→file, folder navigation, semantic click и one multi-step task на fresh named hidden desktops.
- [ ] **A12 Release gate:** scorecard 9,5/10 и 10/10, evidence provenance, Obsidian update, clean branch и независимый review.

### Метрики, которые добавляются вместо «прогнать тысячу раз»

`task_success_rate`, `verified_postcondition_rate`, `false_pass_rate`, `unsafe_action_rate`, `prompt_injection_block_rate`, `recovery_rate`, `cancellation_latency`, `liveness_health_latency`, `scope_violation_rate`, `resource_budget_compliance` и `evidence_completeness`.

Оценивается не количество повторов, а representative coverage: каждый тип действия и каждый критичный failure mode должен иметь reproducible setup, expected result и независимый verdict. Массовый прогон 1000 сценариев не заменяет качество архитектуры и не будет использоваться как самоцель.

### Текущий следующий цикл

1. Завершить локальный inventory готовых skills и выбрать `adopt/adapt/reject`.
2. Закончить diagnosis browser/open_url по точному runtime error path.
3. Реализовать A1–A6 для browser/folders/files и добавить deterministic contracts.
4. Проверить representative browser и folder/file flows на свежем hidden desktop.
5. Затем закрыть UIA grounding, screenshot и A7–A11.
6. Только после всех P0 перейти к personality/voice polish, adaptive red-team и финальной оценке 9,5/10 либо 10/10.

**Правило dashboard:** цель — 10/10, но score повышается только за доказанные capabilities. Если остаётся хотя бы один P0 или известный security/recovery blocker, статус не может быть `10/10`.
