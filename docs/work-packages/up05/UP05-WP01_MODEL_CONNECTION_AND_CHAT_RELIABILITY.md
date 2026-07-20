# UP05-WP01 Model Connection and Chat Reliability

Status: R2 implementation, installed real-model acceptance, rollback rehearsal, and local evidence complete; ready for human PR review.

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

The blocking synchronization failure found during R2 was more fundamental: `request_reserved_model_start` retained the model-request registry while performing an unbounded anonymous-pipe `write_all`/`flush`. A live but non-reading sidecar could therefore block cancellation and watchdog recovery behind the same registry. The final boundary makes the Windows pipe non-blocking, gives one writer a two-second bounded retry window, retires the sidecar after partial/broken delivery, preserves frame order, and invokes response callbacks only after unrelated request/router locks are released.

Contributing defects are also in scope: a manually toggled `modelConnected` flag can outlive a lost binding/readiness state; the main composer labels its button Stop but does not call cancellation; cancellation acknowledgement is discarded; event filtering has no client request ID or terminal lock; listener teardown cannot be reinitialized; and acceptance, first-token, inactivity, cancellation, and shutdown recovery are not represented as bounded request states.

## Implemented request/event sequence

1. App initialization owns a reinitializable shared listener before submission and derives readiness from current approved artifacts, managed runtime/model state, and the exact binding identity.
2. The frontend creates the request/session IDs before invoke, enters `submitted`, and creates one request-scoped user/assistant projection only after acceptance.
3. Rust validates the typed request, reserves its registry record, releases unrelated locks, writes the request through the single bounded pipe writer, and sends the synchronous acceptance before Python can publish request events.
4. Python posts the validated llama.cpp server alias while retaining the stable catalog model ID at trust/UI boundaries.
5. Strict request/session/model identity, sequence, cancellation precedence, and one-terminal rules govern every event. Empty or late chunks do not mutate chat state.
6. Non-empty chunks append to the one assistant message. Completion, cancellation, timeout, or failure finalize that message once and preserve any partial content.

## Completed bounded implementation

- Existing typed model commands/events now carry frontend-created request/session/model identity, submission time, binding identity, and fixed bounded generation values.
- Listener registration precedes submission; early terminal state cannot be overwritten by a later acceptance result.
- Rust and frontend enforce identity, strict sequence, one terminal, cancellation precedence, late-event rejection, and bounded cleanup.
- The stable catalog ID remains the authority-facing identity; only the validated server alias is used in the managed provider POST.
- Each accepted request owns one user message and one assistant message. Ordered content is visible in the actual chat and partial content survives interruption.
- Readiness is derived from approved installed metadata, compatible runtime, current model readiness, active binding, and matching runtime instance identity.
- Runtime capability text is kept intact for internal flag validation, and the exact 32-hex managed runtime instance identifier is validated separately from 24-hex request/session identifiers.
- Existing navigation, Settings, artifact authority, knowledge controls, and bounded external-local controls remain intact.

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

Windows job containment received only the bounded pipe-writer implementation required by the proven synchronization boundary. Artifact catalog/trust authority, knowledge/Vault modules, Review Center, Settings/navigation, acquisition/download behavior, and the legacy Tkinter control panel were not changed.

## Acceptance result and limitations

The final installer displayed two consecutive real managed-model responses, a request-scoped cancellation with immutable partial output after the terminal event, a successful retry, and another response after process-clean restart. Closing the app left no owned application, sidecar, or llama.cpp process. Automated affected-path suites, release build, security review, installer payload inspection, installed rollback, and source reverse-apply rehearsal passed.

The supplemental legacy auto-stability suite remains 18/20. Its two failures are stale assertions in unchanged `LocalComet_Control_Panel.py`/`modules/stability_test.py`: retired Russian menu/theme source markers and the removed `LocalCometControlPanel` class. R2-affected checks pass. The owner-provisioned Qwen bootstrap remains internal validation material, not an installer payload, public distribution artifact, quality baseline, or performance baseline.
