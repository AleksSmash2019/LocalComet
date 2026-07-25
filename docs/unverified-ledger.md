# LocalComet — Реестр недоказанного (Unverified Ledger)

**Дата:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent` @ `767a7e9`

Каждая запись: что утверждается → почему не доказано в этой среде → какой
минимальный доступ закрыл бы вопрос → статус.

Правило: утверждение без доказательства помечается `[ЗАЯВЛЕНО]` и не считается
закрытым. Этот реестр — источник правды о границах доказанности.

---

## U-001. npm registry недостижим (infrastructure, не продукт)

- **Утверждается:** `npm ci` / `npm install` необходимы для сборки Svelte-фронтенда.
- **Почему не доказано:** `npm ping` → UNREACHABLE (offline/blocked). Подтверждено
  `scripts/doctor.py` [прогон]. Это блокирует `tauri build` и vitest-прогон.
- **Минимальный доступ:** сеть к `registry.npmjs.org` (или вендоринг `node_modules`).
- **Статус:** BLOCKED (infrastructure). Не является дефектом продукта.

## U-002. Packaged binary / installer

- **Утверждается:** NSIS-инсталлятор для Windows собирается.
- **Статус: СОБРАН [прогон].** `npx tauri build --bundles nsis` → exit 0
  (release-компиляция ~29-42s). Артефакты:
  - `LocalComet.exe`: 14 547 968 B, sha256=`2bfdd0c78ba619c128398157fbeb7190deb4ff0c68eb92368ebc59c5ca52ad78`
  - `LocalComet_6.84.6_x64-setup.exe`: 13 963 772 B, sha256=`7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f`
  - `npm run build` работает **offline** (`node_modules` vendored, 104 МБ) — U-001
    блокирует `npm ci`, но не сборку при наличии зависимостей.
  - Tauri использует **cached NSIS** (см. H-001).
- **Остаётся недоказанным:** установка и запуск инсталлятора (требует интерактивной
  GUI-сессии), smoke установленного приложения, поведение на путях с пробелами/кириллицей,
  стандартный пользователь без admin.
- **Статус:** PARTIAL — инсталлятор собран и хеширован, но не установлен/запущен.

## U-003. 6 ignored real-sidecar тестов требуют окружения

- **Утверждается:** интеграционные тесты supervisor.rs проходят против реального sidecar.
- **Почему не доказано:** тесты помечены `#[ignore]` / требуют
  `LOCALCOMET_TEST_PROJECT_ROOT` + `LOCALCOMET_TEST_PYTHON`. Без них — честный SKIP
  (после фикса Task D: panic при `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`).
- **Минимальный доступ:** установленный sidecar + указанные env-переменные.
- **Статус:** DEFERRED (требует окружения). Метрика «147 passed» семантически честна
  после Task D (silent-skip устранён).

## B-003. Workspace IPC round-trip в sidecar — N/A

- **Утверждается:** sidecar получает `workspace.set` и применяет WorkspacePolicy к
  файловым операциям.
- **Почему не доказано / N/A:** desktop sidecar **не исполняет файловые инструменты**
  (`files.*` = `unsupported_method`, подтверждено smoke step 6 [прогон]). Propagating
  workspace в sidecar нечего охранять. Workspace authority — Rust approval scope
  (`workspace.rs` + `approval_commands.rs::set_workspace`), реализовано и покрыто тестами.
- **Что сделано:** схема `workspace.set` добавлена в IPC-контракт; `modules/workspace_policy.py`
  — тестированный примитив (self-test [прогон]).
- **Минимальный доступ для активации:** появление fs-tool исполнения в sidecar.
- **Статус:** N/A (INV-WORKSPACE-001 остаётся `planned` до появления fs-tool path).

## D-003. CI workflow отсутствует в чекауте

- **Утверждается:** CI устанавливает sidecar до `cargo test` и ставит
  `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`.
- **Почему не доказано:** `.github/workflows/` пуст в этом чекауте (несмотря на
  коммит `ci: add validation workflow` в истории — файлы не present).
- **Минимальный доступ:** восстановить/создать `.github/workflows/ci.yml`.
- **Статус:** DEFERRED. Gate `scripts/check_real_sidecar_tests.py` готов к подключению.

## H-001. doctor.py эвристики vs реальная сборка

- **C-linker:** в чистом PowerShell doctor.py помечает MISSING (`cc`/`cl`/`link` не на
  PATH, `ziglang` не установлен), но cargo успешно линкует (147 тестов + release-сборка)
  через rustup MSVC-детекцию [прогон]. В Git Bash (MSYS) doctor.py находит линкер (OK).
  Эвристика консервативна.
- **NSIS:** doctor.py помечает `makensis` MISSING (не на PATH), НО Tauri 2 использует
  **cached NSIS** (от build-week, в кэше Tauri), поэтому `tauri build --bundles nsis`
  успешно создаёт инсталлятор [прогон] (см. U-002).
- **Интерпретация:** реальный `cargo build` / `tauri build` — authority, не эвристика
  preflight.
- **Статус:** RESOLVED (ложноположительные эвристики; продукт линкуется и бандлится).

## H-002. app.health не является advertised capability

- **Утверждается:** smoke step 4 ожидал `app.health` в advertised capabilities.
- **Почему ложное:** `app.health` — lifecycle-endpoint, обрабатывается ДО проверки
  capabilities; в hello advertised маркер `"lifecycle"`, а не `"app.health"`.
  Подтверждено: capabilities = 26 методов incl. `lifecycle` + `model.catalog.get` [прогон].
- **Статус:** RESOLVED (правка в тесте, не в продукте; smoke 8/8 green).

## DONOR-001. Отсутствуют donor-материалы

- **Утверждается:** полная верификация donor-дефектов по исходникам Local Agent Desktop.
- **Почему не доказано:** в среде отсутствуют
  `LocalComet_Detailed_Static_Audit_2026-07-25.txt` и
  `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` (см. `audit/evidence-ledger.md`).
  Утверждения о donor-дефектах — из `WP-1.45.4_Independent_Verification` [ЗАЯВЛЕНО].
- **Минимальный доступ:** указанные файлы / полные исходники donor.
- **Статус:** ЗАЯВЛЕНО (относительно donor-кода).

## APPROVAL-UI-001. Approval-команды не вызываются реальным GUI-флоу

- **Утверждается:** пользователь инициирует guarded tool через approval в UI.
- **Почему не доказано:** Tauri-команды `request_approval`/`execute_approved`
  зарегистрированы и покрыты (parity 42/42, cargo test), Svelte bridge
  `approval.ts` существует, но продуктового UI-флоу, инициирующего guarded
  fs-tool, нет (sidecar не исполняет fs-tools — см. B-003).
- **Статус:** PARTIAL. Rust authorization boundary реален и атомарен; продуктовый
  GUI-путь появится вместе с fs-tool исполнением.

---

## Сводка

| ID | Область | Статус |
|---|---|---|
| U-001 | npm registry | BLOCKED (infra) |
| U-002 | packaged installer | PARTIAL (собран, не установлен) |
| U-003 | real-sidecar тесты | DEFERRED (env) |
| B-003 | workspace IPC в sidecar | N/A |
| D-003 | CI workflow | DEFERRED |
| H-001 | C-linker preflight | RESOLVED (false-positive) |
| H-002 | app.health capability | RESOLVED (тест) |
| DONOR-001 | donor-материалы | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL |
