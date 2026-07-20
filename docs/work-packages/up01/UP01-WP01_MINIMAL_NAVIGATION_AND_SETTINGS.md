# UP01-WP01 — Minimal Desktop Navigation and Settings

## Authority and dependency

- Mission: `UP01-WP01_MINIMAL_DESKTOP_NAVIGATION_AND_SETTINGS`
- Branch: `feat/up01-wp01-minimal-navigation-settings`
- Exact base: `821d49c2130bfacb8dcb5ccd5371bd0a24105497`
- Dependency: UP00-WP01 (`feat/up00-wp01-windows-one-click-launch`)
- Release classification: `UNSIGNED_INTERNAL_BUILD`

This work package inherits the prospective governance ratification and authority boundaries recorded by UP00-WP01. It authorizes only the bounded frontend work described here.

## Objective and user problem

Make the desktop navigation calm and truthful by showing only the LocalComet identity, Chat, and Settings in the primary rail. Add a functional Settings drawer that consolidates theme, language, and Diagnostics controls. Remove visible placeholder promises and repair Diagnostics row overflow without changing chat, model connection, Control Plane, backend, IPC, Vault, or installer architecture.

The current UI exposes disabled Tasks and Settings actions, a Diagnostics rail action that does not open Diagnostics, a separate Review Center rail action, reserved Audit/Documents sidebar rows, and duplicate language/theme controls. Diagnostics close state and long telemetry rows are also inconsistent at desktop and narrow widths.

## Exact scope

### Navigation and view selection

| Surface | Current owner | Current behavior | UP01 behavior |
| --- | --- | --- | --- |
| Root view | `src/routes/+page.svelte` | Renders `AppShell` | Unchanged |
| Workspace selection | `src/lib/stores/shellStore.ts` | `chat` or `review` | Underlying modes preserved; visible rail exposes Chat only |
| Primary rail | `src/lib/components/shell/NavigationRail.svelte` | Local five-item array | Brand, Chat, bottom-aligned Settings only |
| Settings | No functional surface | Disabled rail placeholder | Frontend-only right drawer |
| Diagnostics | Shell stores plus `Diagnostics.svelte` | Header toggle; rail item is a no-op | Settings and header use one truthful visibility action |
| Sidebar preferences | `ConversationSidebar.svelte` | Separate language/theme quick controls | Removed from sidebar and consolidated in Settings |
| Sidebar placeholder rows | `conversationGroups` rendered by `ConversationSidebar.svelte` | Reserved Audit and disabled Documents rows show `Позже`/`Later` | Filtered from the rendered sidebar; fixture data remains reusable |

### Discovered rail entries

| Entry | Current state | Disposition |
| --- | --- | --- |
| LocalComet brand | Non-interactive identity | Keep |
| Chat | Functional, selects chat | Keep |
| Tasks / Задачи | Disabled placeholder with `later` / `позже` | Hide |
| Diagnostics | Marked enabled but only selects chat | Hide; Diagnostics remains available from Chat header and Settings |
| Review Center | Functional `review` workspace | Hide from the minimal rail; preserve all underlying view code |
| Settings | Disabled placeholder with `later` / `позже` | Replace with functional bottom rail action |

### Current state sources

- Theme: `themeMode` in `src/lib/stores/shellStore.ts`; resolved against `prefers-color-scheme` by `AppShell.svelte`; tokens live in `src/app.css`; currently memory-only.
- Locale: `locale` in `src/lib/i18n/index.ts`; currently persisted defensively under `localcomet.ui.language`.
- Diagnostics visibility: `inspectorVisible` and `inspectorDrawerOpen` in `shellStore.ts`; currently memory-only.
- Control Plane state: existing read-only `controlPlaneStore.bridgeState`; no bridge change is required.
- Versions: `DESKTOP_SHELL_VERSION` is `v6.84.5.1`; the existing title build label is `v6.84.5.1b`; UP00 records the internal status `UNSIGNED_INTERNAL_BUILD`.

## Settings surface

The right-side Settings drawer contains only:

1. Appearance: System, Light, Dark using the existing `themeMode` mechanism.
2. Language: Russian and English using the existing `locale` mechanism.
3. Diagnostics: show/hide the existing Diagnostics panel and display current Control Plane connection state read-only.
4. About: LocalComet, repository-proven version/build strings, and the existing internal-build classification.

Settings opens from the bottom rail action and `Ctrl+,`. Escape and the close control close it. Native buttons retain Enter and Space activation. The drawer is non-modal and does not trap focus.

## Preference persistence boundary

The frontend-only record is:

```json
{
  "theme": "system",
  "locale": "ru",
  "diagnosticsPanel": "closed"
}
```

- Key: `localcomet.ui.preferences.v1`
- Allowed `theme`: `system`, `light`, `dark`
- Allowed `locale`: `ru`, `en`
- Allowed `diagnosticsPanel`: `open`, `closed`
- Invalid JSON and invalid values fall back independently to safe defaults.
- Unknown fields are ignored and are not written back.
- A read-only fallback from the existing `localcomet.ui.language` key preserves the prior locale when the versioned record is absent.
- Settings open/closed state is not persisted.
- No prompts, chat content, model data, credentials, paths, tokens, Vault data, or machine-specific values are stored.
- No backend write, Tauri command, IPC request, network request, migration framework, or telemetry is introduced.

## Proposed files

Create:

- `desktop/localcomet-desktop/src/lib/components/shell/SettingsPanel.svelte`
- `desktop/localcomet-desktop/src/lib/stores/uiPreferences.ts`
- `desktop/localcomet-desktop/tests/uiPreferences.test.ts`

Modify:

- `desktop/localcomet-desktop/src/lib/components/shell/NavigationRail.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/AppShell.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/ConversationSidebar.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte`
- `desktop/localcomet-desktop/src/lib/components/agent/Diagnostics.svelte`
- `desktop/localcomet-desktop/src/lib/components/common/TelemetryRow.svelte`
- `desktop/localcomet-desktop/src/lib/stores/shellStore.ts`
- `desktop/localcomet-desktop/src/lib/i18n/index.ts`
- `desktop/localcomet-desktop/src/lib/i18n/en.ts`
- `desktop/localcomet-desktop/src/lib/i18n/ru.ts`
- `desktop/localcomet-desktop/src/lib/version.ts`
- relevant bounded frontend tests under `desktop/localcomet-desktop/tests/`
- the four UP01 work-package documents in this directory

## Explicit exclusions

The following remain unchanged:

- all Python application/backend modules;
- `desktop/localcomet-desktop/src-tauri/**` and every Rust command or Tauri capability;
- `src/lib/bridge/**`, Control Plane and model gateway contracts;
- `src/lib/components/model/**` and the model-connect workflow;
- `src/lib/components/chat/**` and chat behavior;
- `src/lib/components/review/**` and the underlying Review Center workspace;
- `src/lib/components/shell/AgentInspector.svelte` and its unrendered legacy fixture content;
- installer configuration and installer architecture;
- databases, telemetry, network access, Vault content, `Projects/BrowserProfile`, and UP02–UP10.

## Accessibility requirements

- Every visible rail action is a semantic button with a real handler, concise localized label and tooltip, native Enter/Space support, visible focus, and truthful active state.
- The Settings close control receives initial focus and is keyboard reachable; closing returns focus to the Settings rail action when possible.
- Settings does not trap focus.
- Theme, language, and Diagnostics choices expose selected state through `aria-pressed` or equivalent semantics.
- Diagnostics values wrap within their row and expose the full value through an accessible tooltip.
- Existing contrast tokens and reduced-motion behavior are preserved.

## Visual acceptance criteria

- The primary rail contains only brand, Chat, and bottom-aligned Settings.
- No rendered primary-navigation tooltip contains `позже`, `later`, `coming soon`, or `reserved`.
- Reserved Audit/Documents sidebar rows and duplicate language/theme controls are not rendered.
- Settings is usable at the current desktop width and at a narrower supported Windows desktop width.
- Diagnostics labels and values remain separated with no overlap at 100% and 125% scaling equivalents.
- Diagnostics remains scrollable and its close control remains visible.
- Chat layout, model connection, title bar, Control Plane status, typography, icons, and color tokens remain recognizable and functional.

## Rollback

Rollback is by reverting the UP01 commits in reverse order or abandoning this stacked branch and returning to exact commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497`. The preference record is frontend-only and safe to leave in place; the predecessor ignores it. No backend, IPC, schema, Vault, or user-content rollback is required.

## No-backend-authority statement

UP01-WP01 grants no authority to add or change Python backend behavior, Rust commands, Tauri IPC, generic shell execution, network access, model runtime behavior, database/schema state, Vault behavior, telemetry, automatic approvals, autonomous tasks, publication, or UP02–UP10 features.
