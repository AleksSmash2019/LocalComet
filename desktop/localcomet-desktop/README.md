# LocalComet Desktop Shell v6.84.5

This release keeps the bounded v6.84.4 Control Plane bridge, preserves the v6.84.4.1 LocalComet visual system, and adds the first strictly local text-only model gateway.

## Purpose

v6.84.5 supports explicit local model discovery, explicit in-memory binding, one active text inference, bounded SSE streaming, cancellation, and truthful runtime telemetry. The existing Control Plane demo remains a bridge test facility only. It does not call a model, execute a tool, answer the prompt, access files, or persist state.

The desktop layout targets the Control Plane structure: Product Rail, Session Sidebar, Main Workspace, and Agent Inspector. At narrow widths, the Session Sidebar collapses first and the Agent Inspector becomes a drawer.

The minimum supported desktop window layout remains 1000 x 700.

## Architecture

- SvelteKit renders a static frontend into `build/`.
- Tauri loads those bundled assets into the native Windows WebView2 window.
- Production does not require a localhost server or exposed port.
- The Rust application starts exactly one primary window and exposes only seven explicit control-plane commands plus six explicit model-gateway commands.
- The Rust supervisor starts one contained sidecar process and talks to it through framed JSON over stdin/stdout.
- The Python sidecar uses the existing v6.84.1 IPC contract module and implements lifecycle messages only.
- Windows launch uses fixed child arguments, an explicit inherited-handle list, suspended process creation, and a Job Object configured to terminate the sidecar when the supervisor closes.
- v6.84.4 adds a Session / Thread / Turn / Item control-plane model in Python.
- Rust exposes exactly thirteen Tauri commands and one event channel: `localcomet://control-plane-event`.
- The request registry is bounded to 32 in-flight requests with per-request event and text limits.
- Event sequences are validated per request, and duplicate terminal responses or events after terminal responses are rejected.

## Control Plane Surface

Exact Tauri commands:

- `control_plane_bootstrap`
- `control_plane_create_session`
- `control_plane_close_session`
- `control_plane_create_thread`
- `control_plane_start_mock_turn`
- `control_plane_get_turn_status`
- `control_plane_cancel_turn`

Frontend-accessible shutdown, generic request dispatch, filesystem, shell, process, HTTP, provider, model, and environment commands are not exposed.

## Local Model Gateway Surface

Exact Tauri commands:

- `model_gateway_catalog`
- `model_gateway_probe`
- `model_gateway_list_models`
- `model_binding_set`
- `model_turn_start`
- `model_turn_cancel`

The only provider is `openai-compatible-local`. The only endpoint form is internally constructed as `http://127.0.0.1:<PORT>/v1`, where the UI provides only a decimal numeric port. The frontend exposes no URL, API key, custom header, proxy, temperature, tool, attachment, project-context, or persistence controls.

The fixed harness registry contains only `minimal` and `native-localcomet`. Model discovery requires an explicit user action, and a ModelBinding requires explicit confirmation of provider, harness, port, and an exact model ID returned by the current discovery result. Bindings are memory-only.

One local model turn may be active globally. Streaming is text-only and bounded; tool/function responses fail closed. Cancellation is idempotent and closes the active provider connection.

Python IPC methods supported by the control plane:

- `app.bootstrap`
- `app.status`
- `session.create`
- `session.get`
- `session.close`
- `thread.create`
- `thread.get`
- `turn.start_mock`
- `turn.status`
- `turn.cancel`

Lifecycle methods `app.health` and `app.shutdown` remain sidecar-internal.

## Demo Turn

`turn.start_mock` supports `complete` and `wait_for_cancel`. The complete path emits a fixed ten-event sequence ending in `turn.completed`. The cancellation path emits five startup/status events, remains `RUNNING`, and becomes `CANCELLED` only through `turn.cancel`.

The UI labels fixed demo content with a `DEMO` badge and states that there is no model inference or tool execution. It does not present demo text as a real model answer.

## Visual System

- Canonical comet mark is used in the title bar, product rail, and empty state.
- The security emblem is reserved for policy and verification contexts.
- `Local` renders in the primary text color and `Comet` renders in the accent green.
- Dark and light themes use semantic `--lc-*` tokens.
- Runtime telemetry uses `"Cascadia Mono", "JetBrains Mono", Consolas, monospace`.
- Disabled systems show `Not configured`, `Disabled`, `Not evaluated`, `Not run`, or `Unknown`.

## Toolchain

- Node.js 24 or compatible
- npm 11 or compatible
- Rust stable MSVC toolchain
- Cargo
- Windows WebView2 runtime

## Development Commands

Run Node and Cargo commands from a clean-room copy when validating release containment. The source checkout should not retain `node_modules/` or `src-tauri/target/`.

## Validation Commands

```powershell
npm run check
npm run test
npm run build
cargo fmt --manifest-path src-tauri\Cargo.toml -- --check
cargo check --manifest-path src-tauri\Cargo.toml --locked
cargo clippy --manifest-path src-tauri\Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path src-tauri\Cargo.toml --locked -- --test-threads=1
npm run tauri build -- --no-bundle
```

## UP00-WP01 Windows installer

The owner-authorized Windows package keeps the existing static Svelte/Tauri/Rust/Python boundary. A generated build workspace stages a private CPython 3.14 runtime and the bounded existing sidecar dependency closure; no generated runtime, `node_modules`, Cargo target, or installer is committed.

From a clean `feat/up00-wp01-windows-one-click-launch` branch, run:

```powershell
npm run bundle:windows
```

The build helper copies tracked source to the ignored root `target/up00-wp01/` area, uses `npm ci --offline` and Cargo offline mode, runs the repository-supported frontend/backend/Rust checks, and invokes the pinned Tauri 2 NSIS target. The installed user does not need Python, Node.js, npm, Cargo, Vite, Tauri CLI, or the repository.

The NSIS package is current-user and unsigned. Installer-owned binaries are placed under `%LOCALAPPDATA%\Programs\LocalComet`; LocalComet user data and startup logs remain under `%LOCALAPPDATA%\LocalComet` and are not removed by the normal uninstall path. Tauri's pinned NSIS template creates `LocalComet` Start Menu and desktop shortcuts and the HKCU uninstall registration. WebView2 is treated as a Windows prerequisite; the installer does not add a network bootstrap.

Do not use this internal package as a public release. Production signing, automatic updates, public-release licensing, and distribution approval remain deferred.

## Production Build Behavior

`npm run build` creates deterministic static frontend assets in `build/`. Tauri production configuration points to that static output through `frontendDist`. The development Vite server is used only by Tauri development mode.

## Current Limits

- The Python sidecar is connected for lifecycle supervision, bounded control-plane demo requests, and one bounded local text model turn.
- Local model inference requires a user-operated OpenAI-compatible server bound to `127.0.0.1`.
- No file access is implemented.
- No autonomous execution is implemented.
- No localhost backend is exposed.
- No planner, action, browser, filesystem, tool, approval, Skill, Memory, Artifact, Channel, or persistence runtime is implemented.
- No Skills, Memory, Channels, or Document Workflow engines are implemented.
- Messages and UI state remain in memory and reset on reload.

## Accessibility

The shell includes semantic navigation and main landmarks, a skip link, keyboard-focus indicators, accessible labels on icon controls, disabled approval buttons with visible text, status text that does not rely on color alone, and reduced-motion CSS.

## Themes

The initial theme mode is system. Light and dark modes are implemented with semantic LocalComet Control Plane CSS custom properties and remain in memory only.

## Folder Structure

```text
desktop/localcomet-desktop/
  src/
    routes/
    lib/
      components/
      data/
      stores/
      types/
  static/
  tests/
  src-tauri/
```

The Agent Inspector component is stored with shell components because it is part of the desktop frame. No empty folders are tracked.

## Security Posture

The frontend does not call provider network APIs, shell APIs, or native file APIs. It talks only to fixed Tauri commands. The CSP is restrictive and allows inline styles only for Svelte/Tauri styling compatibility. The `ipc:` and `http://ipc.localhost` entries in `connect-src` are reserved for Tauri's internal IPC scheme and do not expose a backend.

The Rust supervisor is the only desktop code allowed to own the Python lifecycle sidecar. It does not expose a command bridge to Svelte, does not start shell interpreters, and does not forward broad environment variables or secrets.

The main capability allows only the thirteen explicit app commands plus event listen/unlisten. Tauri's app-command ACL is static through generated command permissions; there is no wildcard permission and no generic command.

## Originality

The visual layout is independently implemented for LocalComet. No Open WebUI source code, CSS, components, branding, logos, names, or assets are copied.

## Dependency Summary

Dependencies are resolved from the official npm registry and crates.io only. The project uses Svelte, SvelteKit, Vite, adapter-static, TypeScript, svelte-check, Vitest, Tauri CLI, Tauri, and tauri-build. No Tailwind, Electron, React, Vue, analytics, telemetry, updater, shell, filesystem, HTTP, SQL, notification, Monaco, CodeMirror, or third-party state framework dependency is included.

Next release:

v6.84.5.1 - Managed Local Model Runtime without LM Studio Dependency
