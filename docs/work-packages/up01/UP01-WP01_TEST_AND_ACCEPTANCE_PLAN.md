# UP01-WP01 Test and Acceptance Plan

## Preconditions

- Canonical repository: `C:\Users\DNS\Documents\LocalComet`
- Branch: `feat/up01-wp01-minimal-navigation-settings`
- Base: `821d49c2130bfacb8dcb5ccd5371bd0a24105497`
- Clean index/worktree before packaging
- No Vault access and no network-dependent installation

## Repository-supported frontend commands

Run from `desktop/localcomet-desktop`:

```powershell
npm test
npm run check
npm run build
```

The package has no repository-defined lint or formatting script. The unchanged UP00 packaging helper additionally runs offline npm, Cargo formatting/check/clippy/test, sidecar readiness, and the NSIS build.

## Static and unit acceptance

- All Vitest tests pass.
- `svelte-check` reports no errors or warnings introduced by UP01.
- The production Vite build succeeds.
- Preference tests cover valid values, invalid JSON, invalid values, unknown fields, safe defaults, legacy locale fallback, and storage failure.
- Store tests prove theme, locale, and Diagnostics persistence without persisting Settings state or unrelated data.
- Server-rendered component tests prove only Chat and Settings rail actions render, Settings is functional, sidebar placeholders are absent, and preference controls are consolidated.

## Interaction flow

The flow under test is: app loads into Chat -> Settings opens from the bottom rail or `Ctrl+,` -> theme, language, and Diagnostics controls update existing frontend state -> Escape or Close dismisses Settings -> Diagnostics remains usable and closable.

Verify:

1. Chat remains active and functional.
2. Settings opens from mouse, Enter, Space, and `Ctrl+,`.
3. Settings closes from Escape and its close control.
4. Tasks, Review Center, rail Diagnostics, reserved Audit, and Documents are not rendered in the production navigation surfaces.
5. No visible navigation tooltip contains `позже`, `later`, `coming soon`, or `reserved`.
6. Every visible rail action has a real handler, focus state, accessible name, tooltip, and truthful active state.
7. Theme changes among System, Light, and Dark.
8. Locale changes between Russian and English.
9. Diagnostics opens and closes from Settings and from the existing Chat header control.
10. Existing Control Plane connection state is displayed read-only in Settings.
11. Refresh/restart restores theme, locale, and Diagnostics visibility.
12. Invalid or extra stored values do not break startup.

## Accessibility acceptance

- Keyboard-only traversal reaches Chat, Settings, all Settings controls, and Close.
- Native semantic buttons handle Enter and Space.
- Focus is visible against existing tokens.
- Opening Settings moves focus to Close; closing returns focus to the Settings action when possible.
- The drawer is non-modal and has no focus trap.
- Selected theme/language/Diagnostics state is programmatically exposed.
- Long Diagnostics values wrap and expose full text by tooltip/title.
- Existing reduced-motion handling remains effective.

## Layout acceptance

Capture local screenshots after tests pass for:

1. minimal primary rail;
2. Settings — Appearance;
3. Settings — Language;
4. Settings — Diagnostics;
5. closed Settings with Diagnostics visible;
6. Diagnostics rows without overlap.

Validate the current desktop layout and a narrower supported desktop viewport, including CSS-pixel equivalents for 100% and 125% Windows scaling. Check for clipped controls, text overlap, rail overlap, scroll traps, hidden close controls, and duplicate route/navigation UI.

## Authority-negative acceptance

Diff and repository scans must prove the patch adds no:

- Python or Rust source change;
- Tauri command, IPC contract, capability, or generic shell execution;
- backend or Vault write;
- database/schema change;
- model runtime change;
- network call, remote font, remote icon, telemetry, or update check;
- prompt/chat/model/path/token/credential persistence;
- hidden placeholder feature implementation.

## Regression and installer acceptance

After frontend acceptance and clean commits:

- Rebuild the unsigned current-user NSIS installer with the unchanged UP00 packaging implementation.
- Record any branch-guard compatibility handling explicitly; do not modify or bypass installer architecture.
- Install without deleting or migrating user data.
- Launch from the Start Menu and confirm the minimal rail, Settings, theme, language, Diagnostics, and Control Plane connection.
- Confirm model-connect remains available.
- Close normally and confirm the desktop app, sidecar, and helper leave no orphan process.
- Preserve installed user data.
- Record installer filename, bytes, SHA-256, and unsigned status.

## Evidence outputs

Write only bounded reports and screenshots to the external UP01 evidence directory. Do not commit screenshots, source copies, environment dumps, credentials, personal prompts, or Vault content.
