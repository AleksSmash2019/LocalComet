# UP05-WP01 Model Connection and Chat Reliability

Status: R2 pre-implementation contract recorded; implementation and installed acceptance pending.

Branch: `feat/up05-wp01-r2-real-model-chat`

Base: `fa664b16c48c0377841dc334b89b2b3868a0249c` (`feat/up05-wp00-managed-artifact-trust`)

## Objective and authority

This bounded package connects the UP05-WP00-approved managed llama.cpp runtime and bootstrap GGUF model to the existing LocalComet chat. The approved catalog remains the only artifact approval authority. The UI receives stable IDs and sanitized state only; it does not receive executable or model paths.

Approved runtime ID: `llama-cpp-windows-x86-64-cpu-bootstrap`

Approved model ID: `qwen2.5-1.5b-instruct-q4-k-m`

The package does not authorize model downloads, a general Model Library, cloud providers, API keys, arbitrary paths, directory scanning, generic IPC, generic shell, tools, agents, RAG, Vault access, legacy-checkout work, or unrelated navigation changes.

## Pre-implementation baseline

The exact WP00 base, clean index/tree, inactive Git operations, unchanged `main`/`origin/main`, and preserved prior blocked branch were verified before the R2 branch was created. The production artifact-trust test validated both installed artifacts, their catalog identities and hashes, compatibility, containment, and launchability.

A direct real loopback inference then passed with non-empty content, 16 JSON SSE chunks, 14 non-empty content chunks, exactly one `[DONE]`, 1027.458 ms load-to-ready, 382.014 ms first content, and 389.777 ms total request duration. The created runtime process was stopped and no new `llama-server` process remained. These observations are internal acceptance evidence, not production performance targets.

## Proven root cause

The defect has three independently proven transitions:

1. `managed_runtime.rs` launches llama.cpp with a sanitized alias (`localcomet-...`) and passes both that alias and the stable catalog model ID to the sidecar. `local_model_gateway_ru.py` retains both, but the completion POST sends the stable catalog ID instead of the server alias. A ready runtime can therefore reject the real managed chat request.
2. `LocalModelGateway._start_turn` starts the worker before returning its acceptance response. The sidecar async writer can emit model events before the synchronous response is written. Rust forwards model events outside the pending-request sequencing/terminal checks, and the frontend does not know the backend turn ID until the invoke resolves. A fast terminal event can be overwritten by the later frontend `Generating` update.
3. `MessageComposer.svelte` appends only a user fixture-style message. SSE deltas update `modelGatewayStore.generatedText`, while `MessageList.svelte` renders only `mockMessages`. No assistant chat message is created, appended, or finalized, so a successful stream is invisible in the actual chat.

Contributing defects are also in scope: a manually toggled `modelConnected` flag can outlive a lost binding/readiness state; the main composer labels its button Stop but does not call cancellation; cancellation acknowledgement is discarded; event filtering has no client request ID or terminal lock; listener teardown cannot be reinitialized; and acceptance, first-token, inactivity, cancellation, and shutdown recovery are not represented as bounded request states.

## Existing request/event sequence

1. App initialization installs one shared Tauri listener, then loads gateway and managed-artifact status.
2. The managed flow selects a stable model ID, validates catalog/install compatibility, starts llama.cpp, waits for health and `/v1/models`, attaches the runtime to the sidecar, and separately confirms an in-memory binding.
3. The composer appends and clears the user draft before backend acceptance, then invokes `model_turn_start` with only prompt and binding fingerprint.
4. Python starts the worker and returns a generated turn ID. Async `started`, delta, and terminal events can race ahead of that response.
5. Rust forwards model events by `run_id` without the normal request registry's sequence and terminal enforcement.
6. The frontend accepts events while no active turn ID exists, stores deltas in `generatedText`, and can overwrite an early terminal with `Generating` after invoke returns.
7. The rendered chat never observes `generatedText`.

The primary broken state transitions are therefore `Submitted -> event before Accepted`, `terminal -> Generating`, `SSE delta -> non-rendered projection`, and `Cancelling -> indefinite busy`.

## Minimum bounded implementation

- Extend only the existing typed model commands/events with a frontend-created request ID, chat session ID, approved model ID, submitted timestamp, and fixed bounded generation parameters.
- Register/retain the listener before submission; mark `Submitted` before invoke; accept or reject without overwriting an already terminal request.
- Carry the request ID on acceptance, content, cancellation, timeout, and terminal payloads. Enforce exact request/session/model association, strict sequence, one terminal, cancellation precedence, late-event rejection, and bounded registry cleanup.
- Preserve the stable catalog model ID at trust/UI boundaries but use the validated llama.cpp alias for the managed provider POST.
- Maintain one user message and one assistant message per accepted request. Append non-empty chunks in order and preserve partial assistant content on interruption.
- Derive truthful UI readiness from approved installed metadata, compatible runtime, runtime/model readiness, active backend binding, and matching model/runtime session identity.
- Add documented bounds for runtime startup, model load/readiness, request acceptance, first token, stream inactivity, cancellation acknowledgement, and shutdown.
- Keep the existing navigation, Settings, and bounded external-local controls intact; lead the approved bootstrap flow through the existing managed tab.

## Files involved

Expected bounded implementation owners are:

- `desktop/localcomet-desktop/src/lib/types/modelGateway.ts`
- `desktop/localcomet-desktop/src/lib/bridge/modelGateway.ts`
- `desktop/localcomet-desktop/src/lib/stores/modelGateway.ts`
- `desktop/localcomet-desktop/src/lib/stores/shellStore.ts`
- `desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte`
- `desktop/localcomet-desktop/src/lib/components/chat/MessageList.svelte`
- `desktop/localcomet-desktop/src/lib/components/model/ModelSetupDrawer.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte`
- `desktop/localcomet-desktop/src-tauri/src/control_plane.rs`
- `desktop/localcomet-desktop/src-tauri/src/managed_runtime.rs`
- `modules/local_model_gateway_ru.py`
- `modules/desktop_sidecar_runtime_ru.py`
- `tools/run_localcomet_desktop_sidecar.py` only if response-before-event serialization requires it
- focused frontend, Rust, Python, and integration tests

Explicitly excluded unless a failing changed-path test proves otherwise: artifact catalog/trust authority, Windows job containment, generic Control Plane demo/session behavior, knowledge/Vault modules, Review Center, Settings/navigation, acquisition/download code, general provider architecture, and legacy Tkinter control-panel implementation.

## Remaining limitations at this checkpoint

Implementation, complete automated verification, installer rebuild, Start Menu acceptance, cancellation/restart evidence, and rollback rehearsal remain pending. No claim of end-to-end completion is made by this initial contract.
