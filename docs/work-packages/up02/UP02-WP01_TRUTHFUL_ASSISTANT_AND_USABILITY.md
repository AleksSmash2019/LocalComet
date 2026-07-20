# UP02-WP01 — Truthful Assistant and Usability

## Objective

Make the local text assistant identify its LocalComet operating context, follow the selected interface locale by default, and refuse to claim capabilities that the current desktop application does not provide. Improve the existing chat state guidance without changing the product architecture or restoring unfinished product areas.

This work is stacked on UP05-WP01-R2-HF1 at `ee221944eca092580e333b804f4e408a89a0bc76`.

## User-visible problem

The approved bootstrap model currently receives only the user message on the managed minimal harness. It can therefore guess its identity, capability set, project knowledge, and preferred language. The chat also leaves a ready-but-empty conversation visually blank, exposes technical lifecycle words on assistant messages, and does not summarize capability boundaries in Settings.

## Relevant implementation discovered

| Concern | Current source | Current behaviour | Minimum change |
| --- | --- | --- | --- |
| Frontend turn request | `src/lib/bridge/modelGateway.ts` and `src/lib/stores/modelGateway.ts` | Sends IDs, model, timestamp, token limit, prompt, and binding fingerprint | Add the existing `ru`/`en` locale as a validated enum |
| Trusted desktop boundary | `src-tauri/src/control_plane.rs` | Validates the Tauri command and forwards an exact payload | Construct the immutable application/capability context here |
| Provider message assembly | `modules/local_model_gateway_ru.py` | Minimal harness sends `[user]`; native harness has a legacy static system message | Validate the trusted context and deterministically send `[system, user]` for every ordinary turn |
| Locale source | `src/lib/i18n/index.ts` via versioned UI preferences | `locale` is `ru` or `en` and persists through Settings | Snapshot the current locale for each turn; do not mutate it from model output |
| Readiness | model gateway, managed runtime, inference stores | Control Plane, runtime/model, and request lifecycle are separate stores | Preserve separation and improve localized labels/guidance |
| Empty state | `MessageList.svelte` | Only disconnected/no-message state is rendered; ready/no-message is blank | Add bounded unavailable, loading, and ready first-use copy |
| Request state | `MessageList.svelte` and `MessageComposer.svelte` | Non-completed assistant state is a raw technical string | Add localized lifecycle text and a bounded retry action for failed/timed-out turns |
| Capability summary | `SettingsPanel.svelte` | About shows only version/build values | Add read-only available/unavailable lists; no toggles |
| Installer | `tools/build_up00_windows_installer.py` | Builds the existing offline per-user NSIS package | Reuse only after source verification passes |

The current ordinary request message order is one `user` message. UP02 changes it to one deterministic trusted `system` message followed by the unchanged `user` message. Neither trusted context nor the system instruction is added to the rendered transcript.

## UI state model

- Model unavailable: send is disabled and the existing model-connect action is visible.
- Runtime/model validating or loading: send is disabled and bounded progress wording is shown without claiming readiness.
- Model ready: send is enabled when input is non-empty; the first-use state explains local chat and current capability limits.
- Request streaming: progressive text and Stop remain visible.
- Request failed or timed out: streaming stops, a localized safe explanation and retry action are shown.
- Request cancelled: partial text is preserved, cancellation is explicit, and a subsequent request remains possible.

Control Plane connection, managed runtime/model readiness, and request generation remain independently derived. The existing HF1 bounded transcript, near-bottom follow behaviour, keyboard scrolling, and reachable composer are preserved.

## Scope

Included: typed trusted assistant context, deterministic system instruction, locale transmission, chat-state wording, first-use guidance, read-only capability summary, tests, documentation, existing offline installer rebuild, and regression acceptance.

Excluded: internet, email, browser, files, Vault, RAG, Computer Use, shell, tools, cloud inference, API keys, model downloads, autonomous action, generic IPC, navigation redesign, and unrelated Agent/Browser/Computer Use source.

## Product limitations

The assistant is a probabilistic local model. The application supplies deterministic context and verifies behaviour semantically, but it cannot promise perfect wording. Project-specific context is unavailable in this package; users can paste or describe information in the chat, but LocalComet does not inspect their repository, files, or Vault for ordinary responses.
