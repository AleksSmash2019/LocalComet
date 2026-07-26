# Local Agent Desktop WP-1.45.4 screen disposition

Source studied as a visual and UX reference only:
`audit/donor-briefs/lad-wp1454.tar.gz`.

The React components, Zustand store, mock bridge, timer-driven states, static
catalog authority, browser speech recognition, and client-generated evidence
are not ported. LocalComet's Svelte stores, typed bridges, Tauri commands, and
hash-pinned artifact catalogs remain authoritative.

Reviewed against the extracted WP-1.45.4 snapshot on 2026-07-26 before the
ADAPT surfaces below were completed.

| Donor area | Disposition | LocalComet decision |
| --- | --- | --- |
| AppShell | ADAPT | **Owner-directed override:** reproduce the donor's visual shell in Svelte: 224 px labelled application navigation on wide screens, 208 px conversation column, 48 px header, compact typography, flat translucent surfaces, donor palette, borders, radii, focus and responsive states. Existing Svelte routing, stores, drawers, accessibility and real Control Plane status remain canonical. React/Zustand behavior is rejected. |
| Command Center | ADAPT | **Owner-directed override:** reproduce the donor's centered 768 px chat composition, compact runtime/model bar, message bubble geometry, empty state and composer styling around the existing real managed-model turns, validated streaming events, cancellation, native selected files and diagnostics. Donor fake streaming, random telemetry, planner/tool simulation, timer states, browser attachments and voice behavior remain rejected. |
| ModelHub | SUPERSEDED | `ModelManagerSection` and artifact-acquisition state use embedded hash-pinned catalogs, exact byte progress, validation, removal, and managed-runtime readiness. The donor static catalog, RAM slider, timer downloads, and mutable Hugging Face flow are rejected. |
| Donor model picker | SUPERSEDED | `ModelSetupDrawer` and the managed-model controls already expose real loopback probes, discovered models, approved managed artifacts, runtime startup, and binding. Browser hardware guesses and artificial scan/recommendation states are rejected. |
| Onboarding | SUPERSEDED | The Svelte setup workspace now derives its checklist only from control-plane, approved-artifact, managed-runtime, and model-binding state. Unknown values remain explicit; no persisted completion, persona, hardware, or app-data claim is introduced. |
| Plan Review | DEFER | There is no canonical desktop planner request, typed executable plan, correlated step execution, or tool-result path. Rust approval grants do not dispatch tools. The donor token-discarding execution path is REJECTED. The existing Knowledge Review Center is a separate feature. |
| SettingsHub | SUPERSEDED | The settings drawer is now a tabbed hub preserving real theme, locale, diagnostics, capability, version, approved-model, and observability controls. Unsupported permission profiles, model parameters, MCP, reset, and diagnostic-export controls are omitted. |
| Logs / Evidence Room | SUPERSEDED | The bounded read-only Observability Room uses validated control-plane events and sanitized managed-runtime log tails, explicitly distinguishes diagnostics from authoritative evidence, and exposes no fake export action. A persisted provenance-bearing evidence browser remains DEFER. |
| Multi-chat | DEFER | Current UI has one global transcript and the backend does not own or reconstruct conversation history from `chat_session_id`. UI-only conversation buckets would misrepresent model context and persistence. |
| Voice UI | DEFER | No typed desktop voice commands, microphone permission flow, or transcript events exist. The donor browser SpeechRecognition path is REJECTED because it may use cloud processing and conflicts with the local-only posture. |

## Implemented ADAPT surfaces

- Onboarding: `src/lib/components/onboarding/OnboardingScreen.svelte` exposes a
  setup workspace driven by live Control Plane bootstrap, canonical catalog,
  installed-artifact validation, managed-runtime, and binding state.
- SettingsHub: `src/lib/components/shell/SettingsPanel.svelte` provides donor-
  style Interface, Models, Logs, and About tabs while retaining the existing
  model manager and capability boundaries.
- Logs / Observability Room:
  `src/lib/components/logs/ObservabilityRoom.svelte` renders validated session
  events and sanitized managed-runtime tails, explicitly labelled as
  non-authoritative and non-persistent diagnostic data.
- AppShell, Command Center, ModelHub, and model picker retain the existing
  Svelte command/store logic and use the compact donor-inspired visual system;
  their disposition remains SUPERSEDED rather than ADAPT because these
  production implementations predate and exceed the donor behavior.

## Explicit rejections

- React/JSX/TSX and Zustand architecture.
- Fake ready states, random telemetry, timer-driven downloads, and simulated
  model startup.
- Static frontend model catalogs as installation or compatibility authority.
- Client-generated logs represented as evidence.
- Browser SpeechRecognition in the desktop local-only path.
- Plan execution that discards approval tokens or bypasses Rust approval.

## Deferred and rejected donor subpaths

| Donor subpath | Disposition | Reason |
| --- | --- | --- |
| Plan execution loop | REJECT | Client-owned approvals and step dispatch cannot replace scoped Rust grants and correlated execution results. |
| Client-only conversation buckets and export | REJECT | They would imply model context and persistence that the backend does not provide. |
| Browser SpeechRecognition | REJECT | It has no typed desktop permission or local-STT boundary and may use cloud processing. |
| Client-generated evidence and diagnostic bundle | REJECT | Frontend rows and an unimplemented export action are not authoritative evidence. |
| RAM slider and browser hardware recommendation | REJECT | User assertions and browser guesses cannot establish runtime compatibility. |
| Arbitrary Hugging Face installation | REJECT | It bypasses the embedded, hash-pinned approved artifact catalog. |
