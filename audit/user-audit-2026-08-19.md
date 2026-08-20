# LocalComet — пользовательский аудит 2026-08-19

## Исходное состояние

- Repository: `C:\Users\DNS\Documents\LocalComet-build-week-clean`
- Branch: `feat/up00-wp01-windows-one-click-launch`
- HEAD: `a798bca677caf4915baac2ae30436ff606b792e4`
- LocalComet started successfully with PID 25384 and a valid main window.
- Initial runtime state: `Stopped`, model state `Unavailable`; installation `Installed`.
- Initial UI has no dialogs, alerts or pending approval controls.

## Main-screen controls discovered

Chat, HF Models, Pick a model, New chat, sidebar collapse/show controls, Settings, local-model setup CTA, diagnostics toggle, Add files and Send.

## Initial observations

The application starts without a startup error. The empty state is truthful: no local model is connected and the send control is disabled until a model is ready. The approval surface is empty at startup.

Further audit steps: navigation and new-chat lifecycle; model catalog, custom GGUF, ModelFit and runtime; settings, skills, permissions, voice and Computer Use; then complete gate rerun.

## Settings/UI checks

- Settings opened successfully.
- Tabs observed: Interface, Models, Skills, Permissions, Logs, About.
- Theme buttons Светлая, Тёмная and Системная were clicked in sequence and returned to System; no dialog or alert appeared.
- Models tab exposes CPU and GPU (Vulkan) engine options, installed Qwen2.5 1.5B (1066 MiB), Qwen2.5 7B (4466 MiB), and Qwen3-1.7B Q4_K_M (1223 MiB), plus Connect, Delete model, Install skill, Disconnect and Delete controls. Destructive controls were inspected but not activated.
- Skills tab shows builtin diagnostics-reader, project-inspector, runtime-doctor and workspace-inspector entries enabled; no "Command not found" text observed.
- Permissions snapshot shows filesystem, external tools and Computer Use enabled; Internet and command execution are separately represented and not enabled in the captured state.

## ModelFit checks

ModelFit opened from the main CTA and its iframe loaded normally. The scan completed in about 30 seconds without hanging. It reported an Intel Core i7-14700KF (20 cores / 28 threads), 32 GB RAM with 16 GB available, NVIDIA GeForce RTX 5070 with 12 GB VRAM, 91 GB free SSD space, Windows 11 Pro x86_64 and CUDA available. The scenario flow opened successfully; selecting the general-assistant scenario produced a Qwen3 8B Q5 recommendation with a 96.7 score and a full-GPU launch suggestion. Copy, export-report and alternatives controls responded; alternatives included Qwen3 14B, Qwen3 4B, TinyLlama 1.1B and Mistral 7B v0.3 among others. No error dialog appeared.

## ModelFit registry update and live verification

The bundled ModelFit registry was extended from 31 to 35 entries with Qwen3.5 0.8B, Qwen3.5 2B, Qwen3.5 4B and Phi-4 Mini (3.8B). The updater is `audit/update_modelfit_registry.py`; it validates one entry per new ID, preserves the shared `D()` quantization estimator and synchronizes both `static/modelfit.html` and `build/modelfit.html` when present. Qwen3.5-2B and Qwen3.5-4B advertise llama.cpp/LM Studio/KoboldCpp/text-generation-webui only; Qwen3.5-0.8B retains its `qwen3.5:0.8b` Ollama tag.

During the first live reopen, a missing object separator in the newly inserted minified array was detected as `Unexpected token '{'`. The updater was corrected to repair that boundary idempotently; the static and build bundles were then synchronized and `check_bundle_parity.py` passed with 220 shipped modules.

The application was switched from Chat to ModelFit and reopened through the normal UI, without `Page.reload`. The updated page loaded without a JavaScript error. A real scan completed in about 35 seconds and again reported i7-14700KF, 32 GB RAM, RTX 5070 with 12 GB VRAM, 91 GB SSD, Windows 11 Pro x86_64 and CUDA. Selecting the `Лёгкий чат` scenario recommended **Qwen3.5 2B**, Q5, llama.cpp, with a 97.1 score, 96–200 tok/s estimate, 2.5 GB memory plus 3.0 GB VRAM and full-GPU mode. The launch text correctly stated that Ollama is not advertised for this model and offered llama.cpp/LM Studio instead.

## Final gates after registry update

The full `Run-Gates.ps1` run completed successfully at 2026-08-19 20:27:18. The report is `artifacts/gate-reports/gate-report-2026-08-19_20-24-19.md`; it records **69 product gates, 69 pass, 0 fail, Verdict: PASS**. The run included `npm run check` with 0 Svelte errors/warnings, `npm test` with 403 passed tests, `cargo test` with 526 passed / 0 failed / 7 ignored, `cargo fmt --check`, `cargo clippy -D warnings`, Python compilation, bundle parity, evidence provenance, all security/regression suites and CLI smoke. Bundle parity remained green at 220 shipped modules across 2 locations.

The first live ModelFit attempt exposed and then fixed one registry-separator defect; the final live reopen, scan and recommendation flow completed without JavaScript errors or hanging. Obsidian/Vault was intentionally not modified in this pass because this task was limited to the LocalComet repository and no current instruction authorized a Vault write.

## Расширение ModelFit — live scan текущего прохода

После расширения bundled registry LocalComet был штатно запущен поверх существующего Vite runtime и ModelFit открыт через пользовательский UI без Page.reload. Iframe `/modelfit.html` загрузился без JavaScript-ошибок. Живой скан завершился примерно за 35 секунд и показал: Intel Core i7-14700KF, 20/28 ядер/потоков, AVX2, 32 GB RAM (19 GB доступно и безопасный лимит), NVIDIA GeForce RTX 5070 с 12 GB VRAM, 94 GB свободного SSD, Windows 11 Pro x86_64, CUDA и DirectML. UI подтвердил полноценное GPU-ускорение и список локальных движков.

В расширенном live-проходе ModelFit сценарий «Программирование» завершился без ошибки и выдал DeepSeek Coder 6.7B, Q5, Ollama, с оценкой 100 и полным GPU-режимом на RTX 5070. Система показала 47.1–98.2 ток/с, 4.0 GB RAM + 7.0 GB VRAM и 4.7 GB на диске; llama.cpp-команда также присутствует. Это подтверждает, что сценарный алгоритм продолжает работать с новым каталогом.

В расширенном сценарном тесте вкладка «Альтернативы» отобразила новые записи: Mistral Small 3.2 24B как вариант максимального качества, Qwen3-VL 4B как быстрый vision-вариант, Qwen3.5 0.8B как вариант для слабого ПК, а также Qwen3-VL 8B и Gemma 4 E4B в таблице. Затем сценарий «Русский язык» выдал Qwen3-VL 8B, Q5, Ollama, с итоговой оценкой 100, 39.5–82.3 ток/с и 8 GB VRAM. Запусковая секция также показала llama.cpp-команду. Новые записи реально участвуют в сортировке, а не только присутствуют в исходном массиве.

Дополнительные live-сценарии ModelFit: «Максимальное качество» корректно выбрал Qwen3-VL 8B Q5 с оценкой 97.5; «Анализ документов» выбрал тот же Qwen3-VL 8B с оценкой 97.8; «Лёгкий чат» выбрал именно Qwen3.5 2B Q5 на llama.cpp с оценкой 97.1, 96–200 ток/с, 2.5 GB RAM + 3.0 GB VRAM и честным сообщением, что Ollama для этой записи недоступен. Это подтверждает корректное разделение рекомендаций по аппаратной нагрузке и сценарию.

Проверен экран ручного уточнения железа ModelFit. Он показывает текущие значения RAM 31.8 GB, VRAM 11.7 GB и свободный диск 94 GB, а также выбор производителя GPU (Авто/NVIDIA/AMD/Intel/Apple). Экран явно сообщает, что данные анализируются локально, сетевые запросы к характеристикам ПК не выполняются, а читаются только CPU/RAM/GPU/диск/ОС. Кнопки «Применить» и «К выбору сценария» доступны.

Для проверки аппаратных границ в ручных overrides задан профиль 8 GB RAM, 4 GB VRAM и 50 GB диска. ModelFit сохранил профиль и пересчитал рекомендации без ошибки. Для «Лёгкого чата» он выбрал Qwen3.5 2B Q4 на llama.cpp: 2.2 GB RAM + 3.0 GB VRAM, 1.2 GB на диске, итоговый score 89.6 и честное предупреждение использовать Q4/закрыть лишние приложения. Это подтверждает, что registry корректно деградирует по квантизации на слабом ПК.

Для CPU-only проверки задано 16 GB RAM, 0 VRAM и 50 GB диска. В сценарии «Программирование» ModelFit выбрал DeepSeek Coder 6.7B Q4 и не выдал ложный full-GPU статус: режим — GPU + CPU (частичная выгрузка). Интерфейс предупредил, что модель не помещается в VRAM, будет медленнее полной GPU-загрузки и займёт более 75% доступной RAM. Это подтверждает корректное hardware-fit поведение на пограничном профиле.

## LC_START_101 — packaged backend start

Во время продолжения пользовательского тестирования установленный LocalComet показал `LC_START_101` на фазе `packaged backend start`. Диагностика startup.log и launcher doctor установила конкретную причину: оставшиеся dev-процессы занимали `127.0.0.1:1420` (Vite) и `127.0.0.1:8787` (Python sidecar). Поэтому packaged launcher не мог получить собственный backend/sidecar и сообщал `sidecar_unavailable`. Сам packaged `localcomet-core.exe` и встроенный Python были дополнительно проверены прямым пустым IPC probe: runner завершился с exit code 0 и выдал корректный `py-hello-000001` hello.

Dev LocalComet был закрыт через `CloseMainWindow`, затем оставшиеся launcher processes остановлены штатным CTRL_BREAK без `Stop-Process`/`taskkill`. После освобождения портов установленный LocalComet был запущен повторно: процессы `LocalComet` и `localcomet-core` оставались живы, а новый startup.log завершился `phase=window_display status=success code=LC_START_200`; нового LC_START_101 не появилось. Добавлен технический audit helper `audit/graceful_ctrl_break_detached.py`, его синтаксис проверен через py_compile.

После startup-проверки дополнительно выполнены точечные regression suites: `npm test -- --run tests/approval.test.ts` — 6/6 PASS; `cargo test approval_commands --lib` — 30 passed, 0 failed, 503 filtered. Тесты подтверждают, что model/tool approval boundary выдаёт scoped token в фоне и не создаёт пользовательскую pending-карточку в текущем исходном контракте. Обнаруженная на скриншоте карточка относилась к ранее запущенному устаревшему executable, собранному до background-approval правок.

## Итоговый gate-прогон после LC_START_101

Полный `Run-Gates.ps1` повторно завершён с результатом **69/69 PASS, 0 FAIL**, verdict `PASS` (`gate-report-2026-08-19_21-32-04.md`). Frontend: `npm run check` — 0 ошибок и предупреждений, `npm test` — 26 файлов и 403 теста PASS. Rust: `cargo test` — 526 passed, 0 failed, 7 ignored; `cargo fmt --check` и `clippy -D warnings` PASS. Python compile, bundle parity, sidecar, approval, security, tool-risk, command parity и CLI smoke PASS. После этого `refresh_evidence.py` и `check_evidence_provenance.py` также завершились успешно: 4 evidence-файла свежие и целостные.
