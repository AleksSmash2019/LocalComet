# UP00-WP01 test and acceptance plan

Every result must be captured with the exact command, exit code, UTC time, and relevant artifact identity. A failed command is not converted into a pass.

## A. Repository integrity

- Prove the initial `main` revision and commit subject.
- Prove the feature branch started at that revision and `main` never moved.
- Record tracked preimages/postimages for every changed path.
- Require no tracked deletion, no unrelated path change, no staged residue, and a clean final worktree.
- Scan changed text for machine-specific paths, secrets, Vault references, shell authority, telemetry, updater, publication, automatic approval, and login autostart.
- Keep generated dependencies/builds below ignored generated-output roots only.

## B. Frontend

In the generated workspace, with the lockfile and offline package cache:

```text
npm ci --offline
npm test
npm run check
npm run build
```

## C. Rust and Tauri

With the pinned lockfile and local Cargo cache:

```text
cargo fmt --all -- --check
cargo check --offline
cargo clippy --offline --all-targets -- -D warnings
cargo test --offline
npm run tauri -- build --bundles nsis --no-sign --ci -- --offline
```

Verify the resulting bundle is NSIS, current-user, unsigned, uses existing metadata/icons, and contains the staged sidecar/runtime files.

## D. Backend and sidecar

- Run `py_compile` for each changed Python file.
- Run the existing sidecar contract/supervisor checks in the isolated generated workspace.
- Run the new UP00 packaging/lifecycle checks.
- Launch the packaged sidecar with no repository Python dependency and validate hello, health, shutdown response, goodbye, and bounded exit.
- Exercise an unresponsive test sidecar and prove readiness timeout tears it down.
- Exercise repeated start on one supervisor and prove only one child.

## E. Installed application

Perform a bounded current-user installation from the generated installer.

- Record installer-owned paths before launch.
- Verify Start Menu and desktop shortcuts exist, are named `LocalComet`, and target the same installed executable.
- Launch with the Start Menu shortcut and prove the main window appears only after the startup log records readiness.
- Prove the required sidecar starts automatically and no terminal/developer tool is needed.
- Prove neither app nor sidecar owns a visible or persistent console window. If Windows creates a `conhost.exe` descendant for the console-subsystem sidecar, prove it has no window (`HWND 0`) and exits with the managed sidecar.
- Launch the desktop shortcut while the first instance is active; prove the second app exits and sidecar count stays one.
- Request normal window close; prove app and sidecar exit within the bounded timeout with no orphan.
- Verify an HKCU uninstall registration exists.

## F. Uninstall and data preservation

- Record every installer-owned path and shortcut before uninstall.
- Record the exact pre-existing top-level metadata fingerprint of the LocalComet per-user data root and the byte size/hash of the startup log.
- Run the generated uninstaller without selecting optional app-data deletion.
- Prove binaries, resources, shortcuts, and uninstall registration are removed.
- Prove the data-root fingerprint and startup log remain byte-identical after uninstall.
- Do not inspect or touch Vault content, projects, knowledge files, or unrelated user configuration.

## G. Negative authority

Diff and package scans must show no new generic raw IPC, shell plugin or caller-controlled command execution, Vault write, publication, automatic approval, telemetry/analytics, arbitrary network access, source-tree runtime state, login autostart, schema migration, or UP01-UP10 implementation.

## H. Rollback rehearsal

- Create a disposable local clone below the ignored build root from the local repository only.
- Verify the feature state and tests in that clone.
- Revert the branch commits newest-first without `reset --hard`, without deleting user data, and without touching the original worktree.
- Prove the disposable clone returns to the exact baseline tree and remains build-consistent for unchanged baseline checks.
- Reapply/restore the successful feature state in the disposable clone and rerun repository integrity.
- Leave the original feature branch unchanged and clean.

## Success gate

All categories A-H must pass. Any required failure that cannot be corrected inside the documented file scope produces the mission's exact blocker verdict.
