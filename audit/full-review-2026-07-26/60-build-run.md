# Сборка и запуск

Версии получены: 2026-07-26T21:30:51+05:00

## Версии инструментов

```text
$ node --version
v24.18.0
exit_code=0
$ npm --version
11.16.0
exit_code=0
$ rustc --version --verbose
rustc 1.97.0 (2d8144b78 2026-07-07)
binary: rustc
commit-hash: 2d8144b7880597b6e6d3dfd63a9a9efae3f533d3
commit-date: 2026-07-07
host: x86_64-pc-windows-msvc
release: 1.97.0
LLVM version: 22.1.6
exit_code=0
$ cargo --version --verbose
cargo 1.97.0 (c980f4866 2026-06-30)
release: 1.97.0
commit-hash: c980f4866141969fab6254a680546a277789d6f0
commit-date: 2026-06-30
host: x86_64-pc-windows-msvc
libgit2: 1.9.2 (sys:0.20.4 vendored)
libcurl: 8.20.0-DEV (sys:0.4.88+curl-8.20.0 vendored ssl:Schannel)
os: Windows 10.0.26200 (Windows 11 Professional) [64-bit]
exit_code=0
$ cargo tauri --version
error: no such command: `tauri`

help: a command with a similar name exists: `miri`

help: view all installed commands with `cargo --list`
help: find a package to install `tauri` with `cargo search cargo-tauri`
exit_code=101
$ python --version
Python 3.14.6
exit_code=0
```

`cargo tauri --version` выше фактически не работает (`exit_code=101`): global Cargo subcommand не установлен. Проект pin-ит npm CLI `@tauri-apps/cli` 2.11.4 в `package.json`; используемый путь — `npm run tauri -- ...` после установки dependencies.

## Предпосылки

- Windows x64 с WebView2.
- Node/npm и Rust MSVC, версии текущей машины приведены выше.
- CPython для supported dev launcher; launcher проверяет CPython 3.14.
- npm dependencies из `package-lock.json`; содержимое lock намеренно не дублируется в source bundle, размер указан там.
- Для managed inference нужны runtime/model bytes, прошедшие embedded-catalog size/hash/magic validation. Открытый порт или filename этого не заменяет.

## Supported development launch

Из корня репозитория:

```powershell
python tools\start_localcomet.py doctor
python tools\start_localcomet.py
```

Launcher использует clean-room workspace, Cargo target и app-data вне source checkout под `%LOCALAPPDATA%\LocalCometDev`; выполняет preflight, synchronizes source, ставит dependencies при изменении lock и запускает Tauri dev. Диагностика: `python tools\start_localcomet.py status` и `python tools\start_localcomet.py logs`.

Прямой frontend development из `desktop/localcomet-desktop`:

```powershell
npm ci
npm run dev
npm run tauri -- dev
```

Vite слушает `127.0.0.1:1420` только в dev. Production загружает static `build/` в WebView и не требует localhost frontend server.

## Build and validation

```powershell
# desktop/localcomet-desktop
npm ci
npm run build
npm run check
npm test
npm run tauri -- build --no-bundle

# desktop/localcomet-desktop/src-tauri
cargo check
cargo test
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings

# repository root
python tests/test_trust_chain_invariants.py
python scripts/check_command_parity.py
python scripts/check_tool_risk_registry.py
python scripts/check_ui_fake_state.py
python scripts/refresh_evidence.py
python scripts/check_evidence_provenance.py
```

Для direct Cargo validation repository policy требует target вне исходников, например `CARGO_TARGET_DIR=%LOCALAPPDATA%\LocalComet\DevRuntime\cargo-target`. Фактический run в `30-gates.txt` использовал текущий environment и существующий `src-tauri/target`, что видно в Cargo output; это не clean-room containment run.

Windows installer entry from frontend: `npm run bundle:windows`. Он вызывает `tools/build_up00_windows_installer.py --build`; package current-user, unsigned, NSIS и не является public release (`desktop/localcomet-desktop/README.md:127-141`).

## Environment

| Variable | Фактическая роль |
|---|---|
| `LOCALAPPDATA` | Default app-data/logs and external dev runtime roots on Windows |
| `LOCALCOMET_APP_DATA_ROOT` | Exact absolute local app-data override; empty/relative/network path rejected |
| `LOCALCOMET_TEST_PROJECT_ROOT` | Debug/test-only sidecar source root; supported launcher sets it |
| `LOCALCOMET_TEST_PYTHON` | Debug/test-only exact Python executable; supported launcher sets it |
| `LOCALCOMET_REQUIRE_REAL_SIDECAR` | Makes missing real-sidecar test prerequisites fail rather than internally skip |
| `CARGO_TARGET_DIR` | Must point outside source checkout for direct Cargo work under repository policy |
| `LOCALCOMET_PERF` | Enables artifact-trust performance logging when accepted by implementation |
| `LOCALCOMET_RUNTIME_ARCHIVE_VALIDATION_PATH` | Operator path for the ignored explicit runtime-envelope validation test |
| `LOCALCOMET_KNOWLEDGE_VAULT`, `LOCALCOMET_KNOWLEDGE_PROJECT_ROOT` | Authority-bearing knowledge variables; supported desktop launcher removes them |
| `SystemRoot`, `PATH`, `ProgramFiles` | Selected lifecycle/runtime-safe Windows values used by Rust launch code |

No API token, password or remote-provider key is required for the bounded managed local model path. Secrets are intentionally not documented in this archive.
