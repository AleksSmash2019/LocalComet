# LocalComet — полный независимый аудит, 2026-08-19

## 1. Исходное состояние

Аудит выполняется в проекте `C:\Users\DNS\Documents\LocalComet-build-week-clean` без изменения Obsidian Vault, без коммитов и без создания веток. В начале аудита активная ветка: `feat/up00-wp01-windows-one-click-launch`; HEAD: `a798bca`. `git status --short` содержит 311 записей: 219 tracked changes и 92 untracked audit/runtime artifacts, накопленных предыдущими сессиями. Эти изменения не очищались и не удалялись, поскольку проектные правила запрещают удаление без отдельного разрешения.

Последний gate-report до нового аудита: `artifacts/gate-reports/gate-report-2026-08-19_21-32-04.md`, verdict `PASS`, 69/69 product gates, 0 failures. Этот report является исходной исторической точкой; по завершении нового аудита полный gate-suite будет запущен повторно.

На момент первого process snapshot обнаруживался `localcomet-desktop` PID 8296, но последующий correlated snapshot не показал active target listeners на 8787/1420/9223. Runtime state не считается доказанным только по наличию процесса: для итогов используются exit codes, health probes, IPC responses и gate output.

## 2. Правила аудита

Проверяются статический код, frontend/Rust/Python parity, permissions и security contracts, packaged/dev launch, model runtime, чат, новый чат, ModelFit, HF browser, Computer Use, approval flow, skills, voice, settings, recovery after failures и release-readiness. Установщик до финальной приемки не собирается.

## 3. Рабочая классификация

Каждый результат будет помечен как verified current, reproduced defect, historical limitation, non-blocking UX issue или unverified. Наличие старого бинарника, markdown-самоотчёта или открытого порта не будет считаться доказательством без correlated probe.

## 4. Frontend static/test audit

`npm run check` завершился без диагностических ошибок; `npm test` завершился успешно: 26 test files, 403 tests passed, 0 failed. Отдельно подтверждены тестовые области review center, localization, managed artifacts, model selection, knowledge preview/control plane, chat reliability/usability, settings, UI hygiene и approval store.

## 5. Rust static/test audit

`cargo fmt --check`, `cargo test` и `cargo clippy --all-targets --all-features -- -D warnings` завершились успешно. Текущий Rust suite сообщил **533 tests passed**, 0 failed; отдельно прошли проверки approval scope/replay/idempotency, workspace confinement и symlink rejection, file TOCTOU/read safety, managed runtime arguments и artifact validation.

## 6. Python/bundle/security static audit

Текущий static слой прошёл без ошибок: 299 Python files compile clean; bundle parity — 220 shipped modules в двух locations; command parity — 60 registered/invoked commands; tool-risk registry — 7 console tools, 11 sidecar tools, 19 valid entries; INV-UI-001 — 101 frontend files without fake-state violations; mockData allowlist — 5 permitted imports; i18n — 536 used keys присутствуют в ru.ts и en.ts; historical evidence — 46 valid, 0 BODY_MISMATCH; current evidence provenance — 4 fresh and intact.

## 7. HF browser source audit

Исходник `HuggingFaceBrowser.svelte` подтверждает рабочий search/download flow: запросы проходят через Rust bridge, файлы репозитория раскрываются отдельно, GGUF quant/size отображаются, download progress/cancel/retry/error states предусмотрены. Подтверждён один accessibility/automation defect: search `<input>` имеет i18n `placeholder`, но не имеет `aria-label` или связанного видимого `<label>`. Это не блокирует ручной поиск, но затрудняет accessibility и CDP automation; кандидат на безопасную точечную UI-правку.

## 8. Live startup/model/chat audit

Через CDP подтверждён живой LocalComet UI. После штатного открытия Settings → Models и выбора `Qwen2.5 1.5B Instruct Q4_K_M` кнопка `Подключить` перевела runtime из `Validating` в `Ready`; итоговый status: `engine=llama.cpp`, `state=Ready`, `model_state=Ready`, `inference_ready=true`, `runtime_version=b10068`, `model_id=qwen2.5-1.5b-instruct-q4-k-m`, `last_error=null`.

После перехода Settings → Chat отправлены два разных русскоязычных запроса. Первый получил связный ответ о различии локальной и облачной модели; второй — отдельное объяснение ошибки floating-point `0.1 + 0.2` с примером исправления. В DOM нет dialogs/alerts и нет approval-card. История содержит оба запроса/ответа, composer снова доступен после завершения turn.

Во время проверки обнаружены две ошибки только в старом audit helper `cdp_select_model_start.mjs`: он ожидал точное совпадение option text без license/size suffix и старое имя кнопки запуска. Helper исправлен на `startsWith` и фактическую кнопку `Подключить`; продуктовый UI не изменялся.

## 9. Live ModelFit audit

ModelFit открылся штатно через Chat → Подобрать модель. Scan завершился и показал i7-14700KF, 20/28 CPU, 32 GB RAM (16 GB available), RTX 5070 12 GB VRAM, Windows 11 Pro x86_64, CUDA, 93 GB SSD. Сценарий «Программирование» выдал DeepSeek Coder 6.7B Q5, полностью на GPU, с Ollama и llama.cpp launch instructions. Сценарий «Лёгкий чат» выдал новую запись **Qwen3.5 2B Q5 / llama.cpp**, score 97.1, ожидаемая скорость 96–200 tok/s, 2.5 GB RAM + 3.0 GB VRAM; честно указано, что Ollama недоступна для этой записи.

В текущем живом scan не обнаружено зависания или JavaScript error. Продолжение проверки должно охватить alternatives, advanced/manual overrides и remaining ModelFit scenario buttons.

### ModelFit alternatives

Для light-chat alternatives реально отображаются: Gemma 4 12B Unified как quality option, Qwen2.5 3B как fastest, Qwen3.5 0.8B как weak-PC option, Llama 3.2 3B как balance, а также Qwen3.5 2B, Qwen2.5 3B, Llama 3.2 3B, Gemma 2 2B, Qwen2.5 1.5B и SmolLM2 1.7B в таблице. UI показывает размер, quant, RAM, engine и итоговый score; expanded registry действительно участвует в ranking.

## 10. Live HF-browser audit

HF browser открылся штатно и показал approved artifacts/runtime. После исправления audit helper (он ранее только менял input value, но не нажимал «Найти») product flow проверен на запросе `Qwen2.5`: UI вернул реальные GGUF repositories, включая bartowski/Qwen2.5-7B-Instruct-GGUF, Qwen/Qwen2.5-3B-Instruct-GGUF, Qwen/Qwen2.5-Coder-7B-Instruct-GGUF, Qwen/Qwen2.5-1.5B-Instruct-GGUF и другие. Прямой Rust API с `filter=gguf` также возвращает результаты.

Итог: пустой результат предыдущего пробега был ложным сигналом тестового helper-а, а не product bug. Реальный остаточный дефект подтверждён только для accessibility: search input имеет placeholder `Поиск модели… (например, qwen2, llama, gemma)`, но не имеет `aria-label`/visible label.

### HF repository expansion

Открытие `Qwen/Qwen2.5-1.5B-Instruct-GGUF` раскрыло таблицу GGUF files с quant badges (`Q2_K`, `Q3_K_M`, …) и кнопками «Скачать». Dialogs/alerts отсутствуют. В текущем API часть sibling sizes приходит как `null`, поэтому UI честно отображает `—` вместо выдуманного размера; это соответствует правилу не подменять неизвестные данные.

## 11. Parallel track — runtime/ModelFit

`audit/verify_modelfit_registry.py` прошёл для static и build bundles. Все 14 расширенных записей уникальны: Qwen3.5 0.8B/2B/4B, Phi-4 Mini, Qwen3-VL 4B/8B, Ministral 3 3B, Gemma 4 E2B/E4B/12B, Phi-4 14B, Qwen3-Coder 30B A3B, Mistral Small 3.2 24B и Qwen3 30B A3B; отдельный mmproj contract для Qwen3-VL подтверждён; Qwen3.5-2B engines не содержат Ollama. JS audit helpers проходят `node --check`.

## 12. Skills fix — final live verification

Причина дефекта `Invalid JSON from CLI` была подтверждена как runtime path failure: Tauri запускался из изолированного `LocalCometDev` workspace, а `skills_cli.py` находился в source/runtime workspace. Backend resolver в `desktop/localcomet-desktop/src-tauri/src/skills.rs` теперь проверяет `LOCALCOMET_SOURCE_ROOT`, `LOCALCOMET_TEST_PROJECT_ROOT`, runtime/package layout, `current_exe()` parents и CWD fallbacks; при пустом stdout показывает stderr или явный `skills_cli_not_found`, а не маскирует проблему общим сообщением.

Дополнительно `tools/launch_localcomet_dev.py` теперь передаёт `LOCALCOMET_SOURCE_ROOT` в дочерний Tauri environment. После rebuild и штатного запуска через launcher прямой CDP invoke `skills_list` вернул `success=true` и четыре builtin skills: `diagnostics-reader`, `project-inspector`, `runtime-doctor`, `workspace-inspector`; все имеют `state=ENABLED`, `builtin=true`, версии `1.0.0`. Settings → Навыки также отрисовал карточки после завершения асинхронной загрузки. Дефект классифицирован как **verified fixed**.

## 13. Invisible audit mode

Все финальные live-проверки выполнялись без управления пользовательским Chrome: LocalComet запускался через официальный launcher с `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9223`, `LOCALCOMET_INVISIBLE=1`, а сценарии выполнялись CDP/DOM probes. В `src-tauri/src/lib.rs` добавлен test-only environment branch: при `LOCALCOMET_INVISIBLE=1` setup вызывает `window.hide()` вместо обычного `window.show()`; обычный пользовательский запуск не меняется. Консоль launcher также запускалась hidden.

Практическая оговорка: WebView2/Win32 probe в отдельных запусках возвращал `IsWindowVisible=true` при пустом заголовке окна, хотя окно не использовалось для взаимодействия и скрывалось внешним `ShowWindow(SW_HIDE)`. Поэтому **CDP/background execution verified**, но универсальная гарантия OS-level headless desktop для всех WebView2 builds остаётся unverified; это не влияет на product runtime contract и требует отдельного Windows window-lifecycle hardening, если понадобится абсолютный zero-paint режим.

## 14. HF accessibility fix — final live verification

В `HuggingFaceBrowser.svelte` к существующему локализованному search input добавлен `aria-label={$t('hf.search_placeholder')}`. Ключ присутствует в `ru.ts` и `en.ts`. После полного hidden relaunch live probe вернул:

```json
[{"type":"text","placeholder":"Поиск модели… (например, qwen2, llama, gemma)","ariaLabel":"Поиск модели… (например, qwen2, llama, gemma)"}]
```

Запрос `Qwen2.5` снова вернул реальные Hugging Face repositories и GGUF-oriented results. Дефект классифицирован как **verified fixed**.

## 15. Final hidden user-flow audit

Базовая модель `Qwen2.5 1.5B Instruct Q4_K_M` была выбрана и подключена через штатную кнопку `Подключить`; runtime перешёл `Validating → Ready`. Финальный status: `engine=llama.cpp`, `state=Ready`, `model_state=Ready`, `inference_ready=true`, `runtime_version=b10068`, `runtime_id=llama-cpp-windows-x86-64-vulkan-bootstrap`, `model_id=qwen2.5-1.5b-instruct-q4-k-m`, `last_error=null`.

Скрытым CDP smoke-проходом подтверждены chat send/receive, сохранение runtime Ready после ответа и очистка истории через `Новый чат` (`message-summary=[]`). Settings → Разрешения показал активный control `Управление компьютером` и отсутствие approval-card. ModelFit scan завершился без зависания и показал i7-14700KF (20/28), 32 GB RAM, RTX 5070 12 GB VRAM, 92 GB SSD, Windows 11 Pro x86_64 и CUDA. Проверены переходы `Сценарий → Рекомендация → Альтернативы`; light-chat recommendation — Qwen3.5 2B Q5 / llama.cpp, score 97.1, alternatives отображаются.

Один factual-quality limitation подтверждён на минимальной Qwen2.5 1.5B: на запрос о GGUF модель выдала неверное расширение термина (`Generic Game Unpacker`). Это не transport/UI/runtime failure: turn принят, завершён, runtime остался Ready, но малая модель имеет подтверждённое ограничение factual reliability. Для production-quality factual answers рекомендуется пользовательская модель большего размера; базовый default 1.5B оставлен согласно требованию доступности на слабом ПК.

## 16. Final gates and release readiness

Первый полный прогон после правок дал `68 pass, 1 fail`: только `check_evidence_provenance.py` из-за устаревших generated evidence files (`trust_chain.txt`, `tool_risk_registry.txt`, `cargo_test.txt`). Штатный `scripts/refresh_evidence.py` обновил все четыре evidence files с текущим tree digest `5617bc3a547ab07bddd5f08b63612877907199073fcbdf0268b8c1dc83e87ddd`, после чего полный прогон был повторён.

Финальный gate report: `artifacts/gate-reports/gate-report-2026-08-19_23-25-19.md`. Дословный итоговый прогон:

```text
[69/69] smoke_test --mode=cli ...
    PASS (0.1s)
Report: C:\Users\DNS\Documents\LocalComet-build-week-clean\artifacts\gate-report
```

Итог: **69/69 PASS, 0 failures**. Прошли frontend check/test, Rust fmt/test/clippy, Python compile, bundle/command/tool-risk/i18n/UI invariants, skills lifecycle/security, managed runtime, sidecar/control plane, Computer Use, knowledge operations и CLI smoke. Установщик не собирался, Obsidian Vault не изменялся, коммиты и ветки не создавались.

### Изменённые в этой финальной итерации файлы

| Файл | Назначение |
|---|---|
| `desktop/localcomet-desktop/src-tauri/src/skills.rs` | Robust skills CLI path resolver и диагностируемая ошибка CLI |
| `tools/launch_localcomet_dev.py` | Передача `LOCALCOMET_SOURCE_ROOT` в Tauri child environment |
| `desktop/localcomet-desktop/src-tauri/src/lib.rs` | Hidden test branch через `LOCALCOMET_INVISIBLE=1` |
| `desktop/localcomet-desktop/src/lib/components/model/HuggingFaceBrowser.svelte` | Локализованный `aria-label` для HF search input |
| `audit/cdp_user_eval.mjs` | Audit-only probe для точного HF aria verification |
| `audit/full-audit-2026-08-19.md` | Этот финальный отчёт |
| `evidence/*` | Обновлены штатным `scripts/refresh_evidence.py` после stale provenance gate |

## 17. End-to-end UX polish pass — 2026-08-20

После отдельного baseline-прогона обычного пользователя внесены только малые UI-правки, не затрагивающие backend, IPC, permissions, model gateway, Computer Use или download contracts.

| Изменение | Пользовательский эффект | Защита от регрессии |
|---|---|---|
| Всегда видимый локализованный status badge в `ChatHeader.svelte` | Пользователь сразу видит `Модель: готова`, `загрузка` или ошибку рядом с выбранной моделью | Badge питается тем же backend-derived `connectionSummary`; fake-ready state не добавлен |
| Более сфокусированный `EmptyState.svelte` | Первый чат получает аккуратную карточку с мягким градиентом, тенью и responsive-укладкой; prompt cards и CTA сохранены | Только CSS, существующие props/actions не изменены |
| Sticky action footer в `ModelManagerSection.svelte` | Setup/Connect/Disconnect остаются доступными при прокрутке длинного каталога и технических карточек | Существующие кнопки не удалены и не переименованы; изменено только позиционирование/фон |
| Локализация ModelFit navigation в `ConversationSidebar.svelte` | При переключении на английский пункт `Find a suitable model` больше не остаётся русским hardcoded label | Использован существующий `modelfit.title` key из `en.ts`/`ru.ts` |

Скрытый end-to-end проход после relaunch подтвердил: Settings → Models → подключение Qwen2.5 1.5B (`Validating → Ready`), Chat → отправка ответа, Новый чат → пустая история при сохранённом Ready runtime, HF search `Qwen2.5` с aria-label и реальными результатами, ModelFit scan → hardware → light-chat recommendation, отсутствие approval-card regression в Chat/Computer Use controls, а также доступные voice input/output controls. Визуальные snapshots показали, что status badge, first-use card и sticky model action footer вписываются в существующую композицию и не создают мерцания в скрытом режиме.

Первый gate-run после UX-правок получил ожидаемый stale evidence provenance; `scripts/refresh_evidence.py` обновил generated evidence с актуальным tree digest `e7ba8e8b55601d6a7e758d644247b9d5a7531551ef6d107138752a3fbb11c08a`. Повторный полный прогон завершился **69/69 PASS, 0 failures**. Финальный report: `artifacts/gate-reports/gate-report-2026-08-20_00-14-30.md`.

### UX-polish working files

`desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte`, `desktop/localcomet-desktop/src/lib/components/common/EmptyState.svelte`, `desktop/localcomet-desktop/src/lib/components/model/ModelManagerSection.svelte`, `desktop/localcomet-desktop/src/lib/components/shell/ConversationSidebar.svelte`, `audit/ux-polish-baseline-2026-08-19.md` и этот отчёт. Функциональные actions, existing buttons, routes, model catalog, Computer Use permissions, local Piper voice path и security gates сохранены. Установщик не собирался; Vault не изменялся.
