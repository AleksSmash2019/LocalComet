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

To be finalized after implementation:

- `npm test`
- `npm run check`
- `npm run build`
- rendered keyboard, responsive, Diagnostics, and screenshot validation
- authority-negative diff scan
- unchanged-path internal NSIS rebuild and installed Start Menu smoke test
- clean shutdown/orphan check
- disposable rollback rehearsal

## Release status

Internal human review only. Nothing is pushed and no remote pull request is opened by this work package.

`UNSIGNED_INTERNAL_BUILD`
