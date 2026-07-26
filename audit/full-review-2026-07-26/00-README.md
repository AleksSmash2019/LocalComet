# LocalComet full review archive, 2026-07-26

Self-contained text review snapshot of repository `C:\Users\DNS\Documents\LocalComet-build-week-clean`, branch `feature/donor-ui-compatible-port`, including tracked, staged, unstaged and untracked source present at collection time. Source code was not reverted or committed.

## Recommended reading order

1. `00-README.md`: scope, map and entry points.
2. `01-tree.txt`: repository paths and byte sizes; generated/build/dependency directories are excluded.
3. `02-git-state.txt`: branch/status/log/stat, unstaged diff, staged diff, combined tracked diff, untracked list and stash list.
4. `20-architecture.md`: actual desktop runtime, startup, message/model/event paths and security boundaries.
5. `21-tauri-commands.md`: all 42 commands with definitions, types, callers and registry risk.
6. `22-frontend-map.md`: route, all Svelte components, stores, bridges and production reachability.
7. `31-invariants.md`: machine registries, non-authorities, risk policy and fresh status.
8. `40-ui-state.md` and `41-known-defects.md`: donor disposition, current UI and explicit gaps.
9. `30-gates.txt`: complete fresh command output with exit codes; use this instead of summaries.
10. `50-logs.txt`: last 200 lines of both requested logs plus code map; logs are non-authoritative.
11. `60-build-run.md`: commands, observed tool versions, environment and prerequisites.
12. `10-source-01.md` through `10-source-26.md`: full eligible text source in repository order.
13. `99-manifest.sha256`: SHA-256 of every payload file except the manifest itself.

`98-build-audit.py` is the textual collector used to create generated artifacts. It remains in the archive for review/reproducibility and is not product code.

## Project summary

LocalComet is Windows-first local AI software. The repository contains two materially different surfaces:

- Current desktop path: Svelte 5/SvelteKit static UI -> Tauri 2/Rust -> isolated Python sidecar -> Control Plane/Model Gateway -> managed llama.cpp or a loopback OpenAI-compatible local provider.
- Larger legacy Python agent: `core/`, `agents/`, `modules/`, `next/` and Tkinter/console entry points. These files exist in the repository but are not automatically exposed to the desktop WebView.

Desktop IPC protocol is `localcomet.ipc/1.0`: JSON frames with a 4-byte big-endian length prefix and 4 MiB maximum. Tauri entry is `desktop/localcomet-desktop/src-tauri/src/main.rs`; Rust setup/command registration is `src-tauri/src/lib.rs`; UI entry is `src/routes/+page.svelte`; Python desktop runner is `tools/run_localcomet_desktop_sidecar.py`; dispatch is `modules/desktop_sidecar_runtime_ru.py`; model adapter is `modules/local_model_gateway_ru.py`.

Security authority is machine-readable in `security/invariants/invariants.toml`, `security/invariants/non_authorities.toml` and `security/invariants/tool_risk_levels.toml`. Embedded catalog bytes/hash, local byte validation, exit codes and correlated active probes are authority. UI state, logs, filenames, open ports and documentation are not.

## Source bundle rules

Included suffixes: `.rs`, `.svelte`, `.ts`, `.js`, `.json`, `.toml`, `.md`, `.css`, `.html`, `.bat`, `.ps1`, `.py`, `.yml`, `.yaml`, `.lock`. `package-lock.json` and `Cargo.lock` are named with sizes but contents are intentionally omitted. Destination audit files are excluded from their own source bundle to avoid recursion.

Excluded directories: `.git`, `node_modules`, `target`, `.svelte-kit`, `dist`, `build`. Binary/image/archive/model files are not embedded as content; their repository presence and size remain visible in `01-tree.txt`. Untracked CPython stdlib `.py` files under `Python/` are included because they were text in the dirty working tree; DLL/EXE/PYD/LIB files are not.

Files over 200 KB are emitted in marked `часть N/M` pieces without content omission. Bundle documents are approximately 300 KB; a single complete entry may make a document larger.

## Secrets

Text collection applies line-attributed replacement markers of the form `[REDACTED: secret in <source>:<line>]` for Notion tokens, Bearer values, `sk-` key-shaped strings, literal token/password/key assignments and URL credentials. `.env` is not an included suffix and its content is not copied. Redaction also covers test strings that look like credentials; therefore those specific source lines are intentionally not byte-identical. File header byte/line counts describe the original file.

## Fresh verification headline

Every command in `30-gates.txt` exited 0. Rust library result is `148 passed; 0 failed; 6 ignored`; frontend has 18 files / 286 tests passed; svelte-check has 0 errors and 1 warning. The warning and all ignored/unproven boundaries are listed in `41-known-defects.md`.
