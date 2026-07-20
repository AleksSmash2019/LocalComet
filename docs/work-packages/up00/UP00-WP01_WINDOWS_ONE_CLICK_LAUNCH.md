# UP00-WP01 — Windows One-Click Launch and Installer Baseline

**Status:** authorized implementation work package

**Owner decision:** `OR-01`

**Baseline:** `6c784ace543e345bdb8bd2f778be974dc89f2df5`

**Branch:** `feat/up00-wp01-windows-one-click-launch`

**Release classification:** `UNSIGNED_INTERNAL_BUILD`

## Purpose

Produce a normal per-user Windows installation of LocalComet. After one installation, a user launches `LocalComet` from the Start Menu or desktop without a repository checkout, terminal, Python, Node.js, npm, Cargo, Vite, or Tauri CLI.

The launch sequence is:

```text
Windows shortcut
  -> LocalComet.exe
  -> single-instance gate
  -> contained localcomet-core.exe
  -> bounded existing IPC hello and health response
  -> LocalComet window becomes visible and usable
```

## Source-grounded implementation

- Keep the current Svelte static frontend and Tauri 2 shell.
- Keep the current Rust `DesktopSidecarSupervisor`, framed stdin/stdout IPC, and Python entry point.
- Materialize the local CPython runtime and the existing sidecar dependency closure only in generated packaging output.
- Bundle the interpreter under the already-established release-sidecar name `localcomet-core.exe`; invoke it with fixed isolated arguments through the existing Windows Job Object launcher.
- Hide the main window until the current hello plus `app.health` exchange succeeds within a fixed timeout.
- Use a Windows named mutex for an exit-safe second launch; add no single-instance IPC protocol.
- Use Tauri's current-user NSIS support, existing `LocalComet` name, `com.localcomet.desktop` identifier, `0.0.0` package version, and existing icon.
- Place installer-owned binaries under `%LOCALAPPDATA%\Programs\LocalComet`; keep logs under `%LOCALAPPDATA%\LocalComet\logs`; do not place runtime state in Git.

## Scope

- Windows release subsystem/no-console behavior.
- Deterministic generated packaging workspace and private sidecar runtime staging.
- NSIS current-user bundle activation, Start Menu shortcut, desktop shortcut, and uninstall registration.
- Bounded startup, readiness, visible failure, duplicate-start prevention, normal shutdown, and failure cleanup.
- Tests and evidence for source, package, install, shortcut, process, uninstall, negative-authority, and rollback behavior.

## Exclusions

No UI redesign, command/event/capability change, IPC redesign, database or schema migration, user-data lifecycle change, Vault action, model manager change, Review Center change, Prompt Studio change, autonomous-task change, publication, signing, updater, login autostart, telemetry, dependency-major upgrade, or UP01-UP10 implementation.

## Acceptance criteria

1. A Windows NSIS installer is produced from the pinned Tauri major version and classified `UNSIGNED_INTERNAL_BUILD`.
2. Installation is current-user and does not require administrator rights.
3. Installer-owned files are separated from the established `%LOCALAPPDATA%\LocalComet` user-data root.
4. Start Menu and desktop shortcuts named `LocalComet` both target the installed executable.
5. Installed launch needs no terminal or developer tool and creates no persistent console window.
6. Exactly one required sidecar is started automatically through structured fixed arguments.
7. The application window is not shown as ready until bounded hello and health readiness succeeds.
8. Startup failure produces a sanitized native explanation with phase, retry guidance, log location, and safe-close guidance.
9. A second launch exits safely without a second sidecar.
10. Normal close and failed readiness leave no managed orphan.
11. Uninstall removes installer-owned files, shortcuts, and registration while preserving user-owned data and logs by default.
12. Frontend, Python/backend, Rust/Tauri, installer, installed-launch, authority-negative, and rollback checks pass.
13. The feature branch is clean, `main` is unchanged, and nothing is pushed or opened remotely.

## Deferred limitations

Production signing, automatic updates, public-release licensing, production performance baselines, and broader architecture/data/contract decisions remain deferred. WebView2 is treated as a Windows runtime prerequisite; this internal installer adds no network bootstrap.
