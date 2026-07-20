# UP01-WP01 — Minimal Desktop Navigation and Settings

## Summary

This stacked change simplifies the LocalComet desktop primary rail to the product identity, Chat, and a bottom-aligned functional Settings action. Settings consolidates existing theme, language, and Diagnostics controls, uses bounded frontend-only persistence, and shows repository-proven About values. Diagnostics rows and close behavior are tightened for desktop and narrow layouts.

## Dependency

This branch is stacked on UP00-WP01 commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497` from `feat/up00-wp01-windows-one-click-launch`. Review and integration must preserve that dependency. It must not be rebased directly onto the expected main baseline `6c784ace543e345bdb8bd2f778be974dc89f2df5` without first integrating UP00-WP01.

## User-visible changes

- Primary rail contains only LocalComet, Chat, and Settings.
- Tasks and misleading/no-op rail actions are no longer rendered.
- Review Center remains in source but is not exposed in the minimal rail.
- Reserved Audit/Documents sidebar rows are no longer rendered.
- Theme and language quick controls move from the sidebar into Settings.
- Settings supports Appearance, Language, Diagnostics, and About only.
- `Ctrl+,`, Escape, and the close control provide keyboard access.
- Diagnostics visibility persists and long telemetry values no longer overlap labels.

## Persistence

`localcomet.ui.preferences.v1` contains only:

```json
{
  "theme": "system | light | dark",
  "locale": "ru | en",
  "diagnosticsPanel": "open | closed"
}
```

Parsing is defensive, unknown fields are ignored, invalid values use safe defaults, and no backend or network operation is invoked.

## Explicit exclusions

No backend, Rust command, Tauri IPC, model runtime, database/schema, Vault, network, telemetry, update, account, API-key, cloud, model-download, autonomous-task, approval, or installer-architecture feature is added. Chat and model-connect behavior remain unchanged.

## Validation

- `npm test`: PASS — 12 test files, 202 tests.
- `npm run check`: PASS — 0 errors; one pre-existing warning in the unrendered legacy `LanguageSwitcher.svelte`.
- `npm run build`: PASS.
- Rendered keyboard/accessibility flow: PASS — mouse, Enter, Space, `Ctrl+,`, Escape, focus return, semantic names and selected states.
- Responsive Diagnostics/Settings validation: PASS at 1280, 1024 (125% CSS-pixel equivalent), and 800 CSS pixels; no row overlap or horizontal overflow; sticky close remained visible.
- Authority-negative scan: PASS — no backend, Rust/Tauri command, IPC, Vault, network, telemetry, model-runtime, shell-authority, or installer-architecture change.
- Approved-path, unchanged-helper packaging: PASS — 225 sidecar checks, offline npm gates, Cargo fmt/check/clippy, 31 Rust tests, and unsigned NSIS bundle.
- Installer: `LocalComet_0.0.0_x64-setup.exe`, 12,272,900 bytes, SHA-256 `25f4524b7bd897bccfedc128a2ae36c217c5b3884b9c082f4652efa8a5a003b7`, Authenticode `NotSigned`.
- Installed Start Menu smoke: PASS — app identity `com.localcomet.desktop`, minimal rail, functional Settings, Light/English/Diagnostics persistence, Control Plane Connected, model-connect available, and one-window duplicate launch.
- Shutdown/orphan check: PASS — normal close left no `LocalComet` or `localcomet-core` process.
- Rollback rehearsal: PASS — conflict-free revert reproduced the exact UP00 base tree.

The unchanged UP00 helper hard-codes its predecessor branch name. Packaging therefore ran in a clean external clone whose local compatibility branch pointed to the exact UP01 implementation commit; the canonical feature branch, packaging source, installer architecture, scope, and shortcut behavior were not changed.

## Release status

Internal human review only. Nothing is pushed and no remote pull request is opened by this work package.

`UNSIGNED_INTERNAL_BUILD`
