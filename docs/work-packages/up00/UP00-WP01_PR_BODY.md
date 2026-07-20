# UP00-WP01 — Windows one-click launch and installer baseline

> Draft prepared locally for human review. Do not push or create a remote pull request from this work package.

## Purpose

Package LocalComet as a per-user Windows desktop application that starts its existing managed backend automatically, waits for bounded readiness, handles duplicate launch safely, and shuts down without orphan processes.

## User-visible result

After one NSIS installation, the user starts `LocalComet` from the Start Menu or desktop. No terminal, repository checkout, Python, Node.js, npm, Cargo, Vite, or Tauri CLI is needed for installed launch.

## Exact scope

- Prospective governance/owner-decision records for this work package.
- Existing-sidecar runtime packaging and Windows NSIS configuration.
- Main/child no-console behavior.
- Bounded startup readiness, native startup failure, single-instance behavior, and process shutdown.
- Installer, shortcut, lifecycle, uninstall, negative-authority, and rollback verification.

## Exclusions

No IPC/schema/data-lifecycle redesign, UI redesign, model manager, Review Center, Prompt Studio, autonomous tasks, publication, approval mutation, Vault action, telemetry, updater, signing infrastructure, broad dependency upgrade, or UP01-UP10 implementation.

## Architecture decisions used

- `OR-01` prospective Architecture Governance Pack/Constitution ratification.
- Source Mapping `COMPLETED_AND_REMEDIATED` at `6c784ace543e345bdb8bd2f778be974dc89f2df5`.
- Existing Svelte static UI, Tauri 2 Rust boundary, framed pipe IPC, Python sidecar, Windows Job Object containment, LocalComet metadata/icon, and per-user app-data convention.

## Deferred decisions untouched

G03/G12 decomposition, G05 IPC versioning, G09 data lifecycle, public licensing, production performance baselines, production signing, and automatic updates.

## Files changed by category

- Desktop/package configuration: `desktop/localcomet-desktop/README.md`, `package.json`, `src-tauri/Cargo.toml`, `tauri.conf.json`, and `up00-runtime-manifest.json`.
- Windows installer: `desktop/localcomet-desktop/src-tauri/nsis/installer-hooks.nsh`.
- Desktop startup/lifecycle: `src-tauri/src/lib.rs`, `main.rs`, `single_instance.rs`, `startup.rs`, `supervisor.rs`, and `windows_job.rs`.
- Prospective governance: `OR-01_AUTHORITY_BOUNDARY.md`, `OR-01_DECISION_MATRIX.yaml`, and `OR-01_OWNER_RATIFICATION.md`.
- Work-package records: this PR body, rollback plan, test/acceptance plan, and work-package definition.
- Packaging and tests: `tools/build_up00_windows_installer.py`, `tools/test_up00_unready_sidecar.py`, and `tools/test_v6843_sidecar_supervisor.py`.

The branch changes 22 tracked paths with no tracked deletion. Generated Python, Node, Cargo, installer, install-smoke, and rollback outputs remain below ignored build/evidence roots and are not committed.

## Installer artifact

- Filename: `LocalComet_0.0.0_x64-setup.exe`
- Size: `12,273,194` bytes
- SHA-256: `58426bab541951d7b9f8ca8ce5f5e2d70e31c85ddd8055c2ea3c9fbde485ad5f`
- Package version: `0.0.0`
- Installed executable: `%LOCALAPPDATA%\Programs\LocalComet\LocalComet.exe`
- Installed executable size: `8,887,808` bytes
- Installed executable SHA-256: `b8a1b297acbf8a6a745f5f94aabfac0954d02433c018f5f3ce93e7a658cf4161`
- Signature: not signed, as required for `UNSIGNED_INTERNAL_BUILD`

## Tests and evidence

- Source/backend: changed Python files passed `py_compile`; the existing backend suite passed `225` checks; the packaged sidecar completed hello, health, shutdown, goodbye, and bounded exit without a repository Python dependency.
- Frontend: offline install resolved `84` packages with `0` vulnerabilities; `10` test files / `181` tests passed; Svelte check reported `0` errors and one unchanged accessibility warning; the production build passed.
- Rust/Tauri: format, offline check, all-target clippy with warnings denied, and `31` tests passed. The unsigned release and NSIS bundle completed successfully.
- Installer: silent current-user install exited `0`; `55` installer-owned files totaling `36,129,239` bytes were placed below `%LOCALAPPDATA%\Programs\LocalComet`; HKCU uninstall registration was present.
- Shortcuts: desktop and Start Menu shortcuts were both named `LocalComet`, targeted the same installed executable, and supplied no arguments.
- Readiness and UI: cold launch created one app and one required sidecar; the window appeared only after hello and health readiness. Direct UI inspection showed `Control Plane: Connected`.
- Console behavior: the GUI app owned no console window. The sidecar and its Windows-created `conhost.exe` helper both had `HWND 0`; all managed processes exited together.
- Duplicate and shutdown: a second shortcut launch retained the original app/sidecar PIDs and sidecar count `1`; normal close removed the app, sidecar, and helper with no orphan.
- Failure cleanup: an unresponsive fixture reached the bounded readiness timeout and was torn down without an orphan.
- Uninstall preservation: uninstall exited `0` and removed the install directory, both shortcuts, and registration. The existing user-data top-level fingerprint and startup-log size/hash were identical before and after uninstall.
- Authority-negative checks: no generic raw IPC, caller-controlled shell execution, Vault write, publication, automatic approval, telemetry, updater, login autostart, arbitrary network bootstrap, schema migration, or UP01-UP10 implementation was introduced.
- Rollback: a local disposable clone reverted the five implementation commits newest-first with `git revert --no-commit`; its staged tree exactly matched baseline tree `ac5cd9f2a5902db42ebe5403c6dc9fc14f4a114d`, then the feature state was restored. The canonical worktree remained unchanged and clean.

## Rollback

Uninstall without optional app-data deletion, preserve `%LOCALAPPDATA%\LocalComet`, and revert only this branch's commits in a disposable local clone. Never use rollback to delete user data or modify the Vault.

## Known limitations

- Unsigned internal build only.
- No production code signing or automatic updates.
- No public-release licensing or distribution claim.
- System WebView2 is a prerequisite; the installer adds no network bootstrap.

## Reviewer checklist

- [x] Governance commit is documentation-only and precedes source changes.
- [x] Only UP00-WP01 is authorized and implemented.
- [x] Existing IPC, data ownership, and architecture boundaries remain unchanged.
- [x] Installer is current-user and installer files do not overlap user data.
- [x] Both shortcuts target the installed executable.
- [x] Readiness, duplicate launch, shutdown, failure cleanup, and no-visible-console evidence pass.
- [x] Uninstall removes installer ownership and preserves user state.
- [x] Frontend, Rust/Tauri, backend, negative-authority, and rollback checks pass.
- [x] Artifact/evidence manifests and checksums verify.
- [x] `main` is unchanged; no push or remote PR occurred.

**Release warning:** `UNSIGNED_INTERNAL_BUILD`
