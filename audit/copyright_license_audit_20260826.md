# LocalComet — copyright и license audit

**Дата:** 26 августа 2026 года  
**Автор:** Manus AI  
**Объект:** рабочее дерево `LocalComet-build-week-clean`, ветка `feat/up00-wp01-windows-one-click-launch`  
**Статус:** технический inventory завершён; **юридическое разрешение на распространение не подтверждено**.

## 1. Итоговый вывод

Аудит не подтверждает возможность объявить LocalComet «полностью очищенным» для коммерческого или публичного распространения. Главный блокер — у самого приложения отсутствует root `LICENSE`, `NOTICE` или `COPYING`, а в исходных `.py`, `.ts`, `.svelte`, `.rs`, `.mjs`, `.json` и `.toml` файлах не обнаружены SPDX или copyright headers. Следовательно, права на авторский код проекта, условия использования и допустимая модель распространения не определены владельцем проекта. Это **BLOCKER / pending owner and legal decision**, а не разрешение выбрать лицензию по умолчанию.

Второй существенный блокер связан с TTS. RHVoice официально описывает себя как GPL-2.0 проект; его код и установленные SAPI-компоненты нельзя автоматически считать совместимыми с произвольной закрытой или коммерческой упаковкой. Кроме того, условия для конкретных voice releases Elena и Aleksandr нужно фиксировать отдельно: факт установки, имя SAPI-голоса, размер и SHA-256 не заменяют лицензионные условия voice data. RHVoice следует либо распространять только как явно внешний пользовательский компонент с подтверждёнными условиями, либо провести отдельный юридический review bundled distribution.[1] [2] [3]

Piper имеет MIT metadata на уровне официального `piper-voices` repository, однако upstream отдельно предупреждает, что условия конкретных голосов могут отличаться. Поэтому MIT metadata каталога не является автоматическим разрешением на упаковку каждого voice model. Для выбранных fallback-моделей Irina и Ruslan сохранены точные hashes, но нужен retained notice и проверка model/voice-specific terms перед bundling.[4]

Qwen3 upstream указывает Apache-2.0 для open-weight модели, но это не устанавливает лицензию конкретного GGUF-файла, quantization pipeline, conversion artifact или его model card. Точный Qwen3-1.7B GGUF в репозитории не tracked; его provenance и условия распространения остаются отдельным release gate.[5]

> **Честный verdict:** LocalComet может продолжать локальную разработку и внутренние тесты. Для release distribution сначала требуется определить лицензию собственного кода, составить обязательный NOTICE/SBOM bundle и принять отдельные решения по RHVoice, voice data, Piper models, Qwen GGUF, skills и visual assets.

## 2. Evidence vocabulary и методика

В отчёте используются классы из `AGENTS.md`: **A — verified current** (байты, текущий hash, exit code или текущий проверенный тест); **B — verified historical**; **C — intent/research**; **D — stale**; **E — contradictory**; **G — unsupported**. Research-only finding не переопределяет текущий byte/hash evidence.

Аудит был read-only в отношении исходного кода, за исключением минимальных подтверждённых correctness/packaging правок, перечисленных в разделе 9. Commit, reset, rebase, clean и удаление WIP не выполнялись. Локальные research notes сохранены в `/home/ubuntu/localcomet_copyright_research_20260826.md` и `/home/ubuntu/localcomet_tts_research_20260826.md`.

## 3. Inventory собственного кода и packaging boundary

В tracked source inventory обнаружены 438 `.py`, 175 `.md`, 115 `.json`, 90 `.ts`, 57 `.mjs`, 53 `.svelte`, 26 `.rs`, 25 `.txt`, 22 `.jsonl`, 13 `.png`, 12 `.toml`, 10 `.original`, 9 `.tsv`, 3 `.ps1`, 3 `.db`, 2 `.dll`, 1 `.pyi`, 1 `.sha256`, 1 `.svg` и 2 `.html`. Значительная часть PNG — evidence/demo screenshots, а не runtime UI assets. Это inventory фактических файлов, а не утверждение об авторстве всех байтов.

В корне проекта нет tracked `LICENSE`, `NOTICE` или `COPYING`. В `desktop/localcomet-desktop/src-tauri/tauri.conf.json` реально объявлены NSIS bundle, `icons/icon.ico`, external binary `binaries/localcomet-core`, ресурсы `binaries/app/`, `binaries/DLLs/`, Python license, Python DLL/zip files и runtime manifests. Piper models, RHVoice installers и voice assets в этой конфигурации не перечислены как Tauri resources. NSIS hook только изменяет install location и не добавляет license notices.

| Объект | Текущее evidence | Класс | Release consequence |
|---|---|---:|---|
| Собственный код LocalComet | Root license/notice отсутствуют; source headers не найдены | A | **BLOCKER:** владелец должен выбрать и юридически подтвердить license policy |
| Tauri application packaging | `tauri.conf.json`, `up00-runtime-manifest.json`, NSIS hook | A | Packaging boundary известен, но notice bundle неполный |
| Tracked visual files | PNG evidence/demo, один SVG logo, один ICO; provenance fields отсутствуют | A | Attribution/source inventory нужен до публичной упаковки |
| Fonts/audio/model files в tracked app tree | В tracked inventory отдельные font/audio/onnx/gguf files не обнаружены | A | Снижает текущий bundled scope, но не подтверждает права на внешние local artifacts |

## 4. Rust dependencies

`cargo metadata --format-version 1 --locked` перечислил **487 package entries**. У 486 packages непустое Cargo license expression; единственное отсутствие — собственный `localcomet-desktop 6.84.6`, что согласуется с отсутствием root application license.

Основная часть выражений — MIT/Apache/BSD/Zlib/Unicode и их комбинации. Отдельно зафиксированы пять MPL-2.0 packages (`cssparser 0.36.0`, `cssparser-macros 0.6.1`, `dtoa-short 0.3.5`, `option-ext 0.2.0`, `selectors 0.36.1`), `r-efi 5.3.0` и `r-efi 6.0.0` с выражением `MIT OR Apache-2.0 OR LGPL-2.1-or-later`, а также `webpki-root-certs 1.0.9` с `CDLA-Permissive-2.0`. Cargo metadata — полезный inventory, но для release нужен notice generation/retention и review package source licenses.

`webpki-root-certs` содержит Mozilla trusted root certificates. Официальный crates.io metadata указывает CDLA-Permissive-2.0; официальный текст этой лицензии требует, чтобы текст соглашения был доступен вместе с shared Data, при этом не накладывает ограничений на Results.[6] [7] Следовательно, CDLA text должен попасть в полную third-party notice set, если соответствующий crate входит в распространяемый binary.

## 5. npm dependencies

`desktop/localcomet-desktop/package-lock.json` — lockfileVersion 3 с **143 package entries**; у всех entries заполнено lockfile `license` поле. Локально получено следующее распределение: 104 MIT, 13 `Apache-2.0 OR MIT`, 12 MPL-2.0, 5 Apache-2.0, 4 BSD-3-Clause, 3 ISC, 1 0BSD и 1 `MIT OR Apache-2.0`. 12 MPL-2.0 entries относятся к `lightningcss 1.32.0` platform packages и являются dev-only по lock metadata. Production direct packages включают `@tauri-apps/api` с `Apache-2.0 OR MIT` и `@tauri-apps/plugin-dialog` с `MIT OR Apache-2.0`.

Это хороший lockfile-level inventory без missing license metadata, но он не заменяет сохранённые upstream license texts и не покрывает автоматически лицензии встроенных WebView/browser binaries, если они когда-либо станут частью distribution.

## 6. Python requirements, vendored code и runtime

Pinned `requirements.txt` содержит 14 packages. PyPI JSON metadata явно указала license/classifier для `faster-whisper 1.2.1` (MIT), `openai 2.24.0` (Apache-2.0), `PyAutoGUI 0.9.54` (BSD), `pyperclip 1.11.0` (BSD), `pywin32 311` (PSF), `requests 2.33.0` (Apache-2.0) и Apache classifier для `vosk 0.3.45`. Для `json-repair`, `numpy`, Pillow, Playwright, `pyttsx3`, `sounddevice` и SpeechRecognition PyPI license field был пустым/null. Пустое metadata поле **не является доказательством non-free license**.

Для части gaps сделан upstream cross-check: json-repair repository содержит MIT license marker; NumPy 2.4.3 tag содержит BSD-style license text; Pillow 12.3.0 содержит MIT-CMU license и исходные PIL/Pillow notices; Playwright Python 1.61.0 содержит Apache-2.0; pyttsx3 repository маркирован MPL-2.0; Vosk API repository маркирован Apache-2.0.[8] [9] [10] [11] [12] Для `sounddevice` и SpeechRecognition exact upstream license file в этом цикле не зафиксирован, поэтому их status остаётся **C/G pending upstream notice**, а не автоматически permissive.

Vendored `modules/_vendor/comtypes` сопоставлен с upstream `comtypes 1.4.16`, который имеет MIT license. Локальная vendored copy не содержит собственного LICENSE/NOTICE file. Это не делает код автоматически запрещённым, но создаёт конкретное attribution нарушение риска: notice нужно сохранить рядом с vendored source или в unified notices bundle.[13]

Файл `desktop/localcomet-desktop/src-tauri/binaries/LICENSE.python.txt` присутствует и содержит Python/Windows runtime notice material. `up00-runtime-manifest.json` перечисляет CPython runtime и Python/skills source surface, включая modules skills manager/archive/contract/invoker, четыре обычных builtin skills и `notepad-bounded-note` после исправления. Для полноценного binary release ещё необходима проверка DLL- и Python-stdlib notices против фактически упакованных bytes.

## 7. Models и TTS assets

### 7.1 RHVoice

RHVoice official pages describe statistical parametric synthesis, voices built from recordings of natural speech, small model footprints, Windows prebuilt binaries and SAPI5 compatibility. Repository `LICENSE.md` был browser-confirmed как GPL-2.0. Это устанавливает существенный engine-level constraint; конкретные Elena/Aleksandr Windows installers и voice data требуют отдельной проверки release notice и redistribution terms.[1] [2] [3]

В локальной Windows installation установлены SAPI voices `Elena` и `Aleksandr`. Installers были до установки проверены по официальным GitHub release size/SHA-256: Elena 8,228,573 bytes, SHA-256 `23E1301869E842F8F91FE64CC34533F9996724EC609962A24E6D5DEE7828B643`; Aleksandr 10,502,655 bytes, SHA-256 `6F89681EEF32D9D0F05F05592953904A7AF938AB2C7926827AE4F7A8D806F593`. Беззвучный SAPI WAV smoke подтвердил регистрацию и generation, но не субъективное качество голоса. Эти данные — **A для локальных bytes/registration**, но license permission конкретного release пока **C/G pending**.

Текущий LocalComet использует fixed exact SAPI names: female → Elena, male → Aleksandr; при отсутствии конкретного RHVoice voice fallback идёт только в same-gender Piper model. Вызов PowerShell встроен в Rust как fixed script: absolute `%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe`, fixed voice names, no user-controlled command string, no script file creation, and no unrelated process control. Это технический security evidence, но не license clearance.

### 7.2 Piper

Официальный `rhasspy/piper-voices` v1.0.0 repository указывает MIT metadata и русские profiles Denis, Dmitri, Irina и Ruslan. Однако voice-specific terms должны сохраняться отдельно от repository metadata.[4]

Выбранные fallback artifacts в `C:\Users\DNS\Documents\piper`:

| File | Bytes | SHA-256 | Current role |
|---|---:|---|---|
| `ru_RU-irina-medium.onnx` | 63,201,294 | `8FF38212D23DA300BBE3705C645E6E5B9475F0BFDE01558EB17813E22ACAAAAA` | female fallback |
| `ru_RU-irina-medium.onnx.json` | 4,765 | `C2EC28BB38E2B59E93B959B3E40348C1AFEBBD272F30FED5D41205D08E98A9D7` | female config |
| `ru_RU-ruslan-medium.onnx` | 63,201,294 | `72A5F88E0B20928064EB45D88E1DAA21F8AF62D18613580D32CBB4AED48DCF7F` | male fallback |
| `ru_RU-ruslan-medium.onnx.json` | 4,882 | `706A4FB17BC304ABD07809B552DEAE615E64DCBFFBFBD09854BA37CA59E88117` | male config |

Локальный folder также содержит unselected Denis/Dmitri/Ryan files и Piper runtime DLLs. Наличие и hash match не подтверждают право на redistribution; невыбранные artifacts следует либо включить в notice inventory, либо исключить из release bundle.

### 7.3 Qwen3 GGUF

Upstream Qwen3 repository описывает open-weight release с Apache-2.0, но exact GGUF quantization file не tracked в LocalComet и не имеет зафиксированного model-card/license record в текущем repository inventory. Поэтому статус exact Qwen3-1.7B GGUF — **G/C unresolved provenance**. До release нужны canonical URL, exact revision, SHA-256, model card, quantizer provenance и check of any additional terms.[5]

## 8. Skills и third-party provenance

Shipped builtin manifests currently identify `author: LocalComet`, but do not carry a license/provenance field. Registry metadata also lacks a formal license field. Это допустимо для внутренней разработки только как project-owned intent; для public redistribution нужно явно определить, что является собственным кодом, что imported/copied, и какие notices применяются.

Declarative v2 `notepad-bounded-note` имеет `trustTier: builtin_verified`, fixed allowlisted Computer Use actions, bounded `text` parameter, host risk labels and explicit approvals. Legacy Python entrypoints use `shell=False`, bounded stdout/stderr, 30-second timeout and filtered environment, but this is **not an OS sandbox**. Community legacy skills therefore require explicit trust/review and cannot be advertised as fully sandboxed.

В старой installed copy `modules/skills/installed/system-doctor/entrypoint.py` обнаружен one-byte newline drift относительно source; registry does not contain `system-doctor`. Это WIP/runtime drift evidence, не основание для удаления. Его нужно reconcile before a clean release.

## 9. Подтверждённые correctness/packaging changes в этом цикле

Был исправлен реальный packaging defect: `notepad-bounded-note` содержал `entrypoint.py`, `skill.json` и `workflow.json`, но `up00-runtime-manifest.json` и `scripts/check_bundle_parity.py` не перечисляли эти файлы; build-source bundle также их не содержал. Три entries добавлены в manifest и parity allowlist, source files синхронизированы в build-source resources, JSON syntax проверен. После этого parity gate подтвердил: `OK: 430 shipped module(s) match source across 2 location(s) (bundle parity holds)`. Расширение manifest увеличило staged resource identity count с 69 до измеренных 72; соответствующий launcher constant `EXPECTED_TAURI_RESOURCE_IDENTITIES` исправлен с 69 до 72. После этого canonical launcher успешно прошёл resource staging и запустил responding native LocalComet (PID 17996, title `LocalComet`). Эти три source files остаются untracked WIP; без будущего add/commit clean installer builder сознательно остановится на clean-worktree precondition.

Также удалена лишняя `en`-ветка из `MessageList.svelte`: автоматическая озвучка теперь вызывается только при `$locale === 'ru'`, синхронно с Russian-only TTS bridge. В `uiPreferences.test.ts` добавлена adversarial проверка, что polluted `voiceGender: 'robot'` нормализуется в default `female`. Stale test wording “Piper” заменено на neutral “local speech”.

## 10. Risk ledger

| Asset / surface | Provenance/version/hash | Known license evidence | Distribution risk | Required action |
|---|---|---|---|---|
| LocalComet own code | Current repository; root license absent | No root LICENSE/NOTICE; no SPDX headers | **BLOCKER**: app distribution terms undefined | Owner/legal decision; do not add license silently |
| RHVoice engine | Installed Elena/Aleksandr SAPI; installer hashes above | Upstream engine GPL-2.0; voice-specific terms unresolved | **BLOCKER** for bundled proprietary/commercial packaging until reviewed | Decide external dependency vs compliant bundle; retain exact notices |
| Piper voice models | Irina/Ruslan hashes above; Piper voices v1.0.0 | Repository MIT metadata; voice-specific terms separate | High/pending; model bytes alone do not clear redistribution | Retain upstream/model notices and exact voice terms |
| Qwen3 GGUF | Exact file absent from tracked tree | Upstream Qwen3 Apache-2.0 only | **BLOCKER** for bundling exact GGUF without model-card evidence | Record URL/revision/hash/quantizer/model terms |
| Rust crates | 487 Cargo metadata entries | 486 license expressions; local crate missing | Medium; mixed MPL/LGPL/CDLA expressions require notices | Generate/retain cargo license report; include CDLA text |
| npm lock | 143 entries, no missing lock metadata | MIT/Apache/BSD/ISC/MPL expressions | Medium; metadata is not full notice bundle | Generate npm third-party notices and inspect packaged binaries |
| Python requirements | 14 pinned packages | 7 explicit PyPI; several upstream cross-checks; sounddevice/SpeechRecognition pending | Medium/pending | Pin exact upstream license files and transitive notices |
| comtypes vendored copy | Local `_vendor/comtypes`, upstream 1.4.16 | Upstream MIT; local notice absent | Medium attribution gap | Add retained MIT notice in release notice bundle |
| `webpki-root-certs` | Cargo 1.0.9 | CDLA-Permissive-2.0 | Low/medium conditional data notice | Ship CDLA text with binary/data notice |
| Builtin skills | LocalComet manifests; registry lacks license fields | Intent says LocalComet; no explicit license | Medium provenance ambiguity | Add skill provenance/license metadata after owner decision |
| Legacy installed skills | Registry and installed copies; one drifted system-doctor | Per-skill license absent | High if public/community code is redistributed | Reconcile, inventory, trust-review or exclude |
| PNG/SVG/ICO assets | Tracked paths, provenance not recorded | Unknown | Medium for public release | Create asset source/author/license ledger and notices |
| Python/Windows runtime | `LICENSE.python.txt`, runtime-manifest, DLLs | Existing runtime notices; exact bundle audit pending | Medium | Verify every shipped byte against notice set |

## 11. Recommended release sequence

Сначала владелец должен выбрать собственную application license policy и определить, является ли LocalComet proprietary, source-available или open-source проектом. Нельзя выводить это из наличия MIT/Apache зависимостей: permissive dependency license не лицензирует application code.

Далее следует создать reproducible SBOM/notice generation step, который собирает Cargo expressions, npm licenses, Python package license files, CPython/Windows notices, llama.cpp MIT notice, comtypes MIT notice, CDLA text, skill provenance and asset ledger. Этот step должен работать от фактически пакуемого manifest, а не от имени файлов или текущего app-data состояния.

RHVoice нужно вынести в отдельное legal decision: либо явно объявить, что пользователь самостоятельно устанавливает RHVoice и LocalComet лишь обнаруживает exact SAPI voices, либо проверить GPL/voice terms и построить compliant bundle. Piper fallback и Qwen3 GGUF должны иметь отдельные model-card records; upstream code/repository license недостаточен.

Наконец, до release нужно reconcile untracked `notepad-bounded-note` files, stale legacy installed copies and all generated runtime resources. В текущем цикле это намеренно не превращалось в commit, потому что `AGENTS.md` запрещает commit без отдельного указания.

## 12. Verification snapshot

| Gate | Последний подтверждённый результат |
|---|---|
| Focused frontend | `5 passed`, `73 passed` |
| Full Vitest | `39 passed`, `543 passed` |
| `npm run check` | exit 0 |
| Full Rust | `720 passed`, `7 ignored`; fmt/clippy exit 0 |
| Bundle parity after workflow fix | `OK: 430 shipped module(s) match source across 2 location(s) (bundle parity holds)` |
| ADR-015 parser | `Ran 70 tests ... OK (skipped=1)` |
| Tool risk registry | `21 registry entries valid` |
| CLI smoke | `Results: 8 passed, 0 failed` |
| Real-sidecar gate | `OK: real-sidecar tests ran under require mode with no silent skips` using system CPython 3.14 |
| Evidence refresh/provenance | `evidence refreshed: all gates green`; `OK: 4 evidence file(s) fresh and intact`; final2 tree `35f4eb2d22805f251101ac7a921c65686a5c3d414f3bc9757738e9dd9fb46168` |
| Native window | one responding `localcomet-desktop` PID 17996, title `LocalComet`, launched by canonical launcher only after process count was 0 |
| Computer Use model-driven verdict | `NOT_INDEPENDENTLY_VERIFIED`; no claim of production readiness |

## References

[1]: https://github.com/RHVoice/RHVoice/blob/master/LICENSE.md "RHVoice LICENSE.md"
[2]: https://github.com/RHVoice/RHVoice "RHVoice official repository"
[3]: https://rhvoice.org/ "RHVoice official website"
[4]: https://huggingface.co/rhasspy/piper-voices/blob/v1.0.0/README.md "Piper voices v1.0.0 README/model metadata"
[5]: https://github.com/QwenLM/Qwen3 "Qwen3 official repository"
[6]: https://crates.io/crates/webpki-root-certs "webpki-root-certs crates.io metadata"
[7]: https://cdla.dev/permissive-2-0/ "CDLA-Permissive-2.0 official text"
[8]: https://github.com/mangiucugna/json_repair "json-repair upstream repository"
[9]: https://github.com/numpy/numpy/blob/v2.4.3/LICENSE.txt "NumPy 2.4.3 LICENSE.txt"
[10]: https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE "Pillow 12.3.0 LICENSE"
[11]: https://github.com/microsoft/playwright-python/blob/v1.61.0/LICENSE "Playwright Python 1.61.0 LICENSE"
[12]: https://github.com/nateshmbhat/pyttsx3 "pyttsx3 upstream repository"
[13]: https://github.com/enthought/comtypes/blob/1.4.16/LICENSE.txt "comtypes 1.4.16 LICENSE"
