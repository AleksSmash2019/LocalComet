# Полный исходный код (продолжение)

### ПУТЬ: docs/work-packages/up05/UP05-WP00_THREAT_MODEL.md (101 строк, 10294 байт)

````markdown
# LocalComet Repository Threat Model

<!-- Generated under the repository-scoped Codex Security threat-model contract. -->

## Overview

LocalComet is a local Windows agent application with a Tauri/Rust desktop trust boundary, a contained Python sidecar/control plane, local model runtime integration, bounded project workflows, and user-facing Svelte UI. Primary assets are the integrity of executable code and approved model/runtime artifacts, user project and application data, local credentials and process boundaries, typed request/event identity, and the owner's source-reviewed architecture authority.

Primary runtime surfaces include desktop/localcomet-desktop/src-tauri, desktop/localcomet-desktop/src, modules, core, agents, and the packaged Python runtime. Tests, docs, reports, and developer tools inform assurance but do not independently grant production authority.

## Threat Model, Trust Boundaries, and Assumptions

Trust boundaries:

1. Source review and build boundary: repository-controlled source, lockfiles, resources, and build configuration become a packaged desktop application. Unreviewed binaries and mutable AppData are outside this approval boundary.
2. Desktop frontend to Tauri boundary: Svelte is less trusted than Rust. Only typed, permissioned commands may cross; frontend input must not become raw paths, commands, environment, or approval state.
3. Tauri to Python sidecar boundary: framed typed control-plane messages cross a contained local process boundary. Request identity, schema, sequence, bounds, cancellation, and shutdown must fail closed.
4. Tauri to managed model runtime boundary: an external executable processes complex GGUF data and exposes loopback HTTP/SSE. Exact binary/model identity, contained paths, loopback binding, fixed arguments, credentials, readiness, resource bounds, and process cleanup matter.
5. Application to per-user AppData boundary: AppData is mutable by the user and other same-user processes. It may contain installed bytes and derived state but cannot create trust or override source approval.
6. LocalComet to project/Vault boundary: project files and the Obsidian Vault are user assets. Access must remain explicitly scoped; this work package grants none.
7. Acquisition boundary: official upstream pages and asset CDNs are network-controlled inputs until exact source identity, archive safety, bytes, format, license, and SHA-256 are verified and reviewed into source.
8. Installer/runtime boundary: packaged resources and per-user processes must not create persistent terminals, global PATH changes, firewall exposure, startup persistence, or unrestricted process authority.

Developer-controlled inputs include reviewed source catalogs, schemas, command registration, permissions, lockfiles, and build scripts. Operator-controlled inputs include prompts, explicit UI actions, bounded project choices, and installation of exact approved artifacts. Attacker-controlled inputs may include malformed frontend payloads, tampered AppData files, unapproved executables/models, malicious archive members, hostile model outputs, malformed local HTTP/SSE responses, and compromised same-user files.

Assumptions:

- The packaged application and reviewed commit are trusted roots for this local threat model.
- Windows same-user compromise can tamper with AppData, so exact revalidation is required; AppData secrecy or integrity is not assumed.
- Local model output is untrusted text and cannot authorize tools, files, commands, or approval.
- Loopback reduces remote exposure but does not prove process or model identity.
- Administrator/kernel compromise and malicious replacement of the packaged application itself are outside the guarantees of a user-mode source catalog.

Security invariants:

- Only source-reviewed catalog entries can approve runtime/model artifacts.
- Every executable/model is resolved from a stable ID through exact hash, size, type, compatibility, and path containment checks.
- No raw frontend/AppData path or mutable cache grants trust.
- Typed IPC cannot expand into generic shell, filesystem, process, or network authority.
- One request/event identity and terminal lifecycle remains isolated.
- Secrets, full private paths, environment dumps, and unrelated logs do not cross safe projections.
- Shutdown and failure do not leave owned privileged processes alive.

## Attack Surface, Mitigations, and Attacker Stories

Artifact acquisition and extraction face supply-chain substitution, malicious redirects, traversal, drive-relative members, duplicate/case-colliding entries, symlink/reparse members, unexpected installers/scripts, and archive bombs. Mitigations are strict official-source allowlists, one pinned asset, exact raw SHA-256, bounded extraction, member validation, and no execution before review.

Managed AppData faces unknown or tampered models/runtimes, filename spoofing, stale caches, path traversal, junction/reparse escape, time-of-check/time-of-use changes, and compatibility confusion. Mitigations are source-only approval, exact revalidation, safe relative paths, canonical descendant checks, reparse rejection, held model identity, stable IDs, and runtime/model compatibility references.

WP00 deliberately keeps installed state live-derived and creates no persistent inventory. A future optional cache cannot become authority: it must use a sibling temporary file, schema validation, flush and close, Windows-supported atomic replacement, reread, exact post-write validation, and reconciliation with the embedded catalog digest and current bytes. Missing, corrupt, stale, traversal-bearing, or unknown-ID cache content must cause safe reconstruction or rejection without granting approval.

Frontend/Tauri IPC faces malformed data, extra-field smuggling, ID/path confusion, unauthorized commands, and stale readiness. Mitigations are strict Rust ownership, Tauri permission allowlists, reconstructed safe TypeScript projections, stable-ID-only start commands, no mutation API, and fail-closed digest/schema matching.

Sidecar and model runtime protocols face spoofed readiness, duplicate/late/cross-request events, zero-token success, indefinite streams, cancellation races, oversized output, and credential leakage. Existing controls include bounded loopback transport, typed methods, per-turn IDs, output limits, contained processes, and sanitized logs. UP05-WP01 remains responsible for completing the chat lifecycle repairs.

Realistic attacker stories include a same-user process replacing a GGUF after provisioning, a crafted archive attempting path escape, a frontend payload containing traversal-like IDs, an AppData file claiming an unknown artifact is approved, or an unapproved executable placed under a plausible runtime filename. All must fail closed.

### WP00 control realization record

The reviewed schema-1 trust root has catalog digest `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`. It approves only:

- runtime `llama-cpp-windows-x86-64-cpu-bootstrap`: official llama.cpp `b10068`, revision `571d0d540df04f25298d0e159e520d9fc62ed121`, archive SHA-256 `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`, MIT;
- model `qwen2.5-1.5b-instruct-q4-k-m`: official `Qwen/Qwen2.5-1.5B-Instruct-GGUF` revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, GGUF SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, Apache-2.0.

Both were provisioned to catalog-declared managed paths and revalidated as contained and compatible. A real loopback inference produced `AI` with one non-empty content chunk and exactly one `[DONE]`; load-to-listen was 0.953 seconds, first content 114.378 milliseconds, total inference 123.099 milliseconds, three JSON SSE chunks were observed, and peak working set was 1,749,966,848 bytes. Graceful Ctrl+C shutdown left no orphan process.

Frontend 211/211 tests, Svelte check, production build, Rust fmt/check/warnings-denied clippy/tests, the production installed-artifact test, offline locked release build, Python checks, negative authority tests, and source/physical rollback rehearsals passed. The supplemental fast stability result was 17/19 solely because of two legacy checks in untouched control-panel code; all WP00-affected checks passed.

Out-of-scope stories include cloud multi-tenant isolation, remote account takeover, kernel-level process injection, administrator compromise, and physical attacks. Localhost-only exposure does not make malformed local protocol input irrelevant, but it generally lowers unauthenticated remote reachability.

## Severity Calibration (Critical, High, Medium, Low)

Critical:

- Generic command/process authority reachable from model output or untrusted frontend input.
- A source/installer supply-chain bypass that silently executes an unapproved binary across installations.
- Vault or broad user-file destruction reachable without explicit bounded authority.

High:

- AppData or inventory content authorizes an unknown executable/model.
- Traversal/reparse escape launches a binary outside the managed root.
- Hash/compatibility bypass executes tampered runtime bytes.
- Remote/LAN binding exposes an unauthenticated privileged model/control endpoint.

Medium:

- Typed event confusion contaminates another local request without broader code execution.
- A stale readiness state causes local user actions against the wrong approved model.
- Bounded local denial of service through malformed catalog/runtime responses with restart recovery.

Low:

- Safe metadata inconsistency that cannot grant approval or launch.
- Sanitized diagnostic inaccuracies without secret/path disclosure.
- Cosmetic UI state issues with no authority, integrity, or data-loss effect.

Severity falls when exploitation requires prior administrator/kernel control or replacement of the trusted packaged application. It rises when a same-user mutable input crosses into executable approval, arbitrary filesystem access, generic process authority, secret disclosure, or irreversible user-data impact.

Repository: git-remote-sha256:344e82ae9595cf6d13c8b89d3e77f32a310fd1a1c57eb9c4af39126e2086e2ba
Version: feat/up05-wp00-managed-artifact-trust; base 0467cf71e1cf0e0400d687c1829e7bd0de91eebc; final HEAD recorded in external UP05-WP00 evidence
````

### ПУТЬ: docs/work-packages/up05/UP05-WP01_MODEL_CONNECTION_AND_CHAT_RELIABILITY.md (82 строк, 8580 байт)

````markdown
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
````

### ПУТЬ: docs/work-packages/up05/UP05-WP01_PR_BODY.md (43 строк, 3394 байт)

````markdown
# UP05-WP01 PR Body

Status: local human-review record; no remote pull request is authorized or open.

## Summary

This R2 package repairs the existing approved managed-model connection and real chat lifecycle. It preserves UP05-WP00 artifact authority and the UP01 desktop shell while adding request-scoped typed acceptance, streaming, cancellation, timeout recovery, truthful readiness, and rendered assistant messages.

## Proven pre-change defects

- Managed llama.cpp chat used the stable catalog model ID in the provider POST instead of the validated server alias.
- The worker could emit events before the start response, and Rust forwarded model events outside request sequence/terminal enforcement.
- Real SSE content was stored in `generatedText`, while the chat rendered a separate fixture message collection.
- Manual connected state, composer Stop behavior, cancel acknowledgement, terminal filtering, and timeout recovery could leave false readiness or indefinite busy state.

## Bounded changes

- Extended existing typed model command/event payloads with stable request/session/model identity, timestamp, and bounded generation values.
- Used the managed server alias only at the validated provider boundary.
- Moved anonymous-pipe delivery outside unrelated request locks, gave it one owner and a two-second non-blocking bound, and retired the sidecar on partial/broken delivery.
- Enforced response-before-event ordering, strict request event sequencing, one terminal, cancellation precedence, and bounded cleanup.
- Rendered one assistant message per accepted request and appended real non-empty chunks in order.
- Derived chat readiness from approved installed artifacts plus current runtime/model/binding identity.
- Preserved runtime capability flags during internal probing and accepted the exact 32-hex managed runtime instance identity.
- Added focused frontend, Rust, Python, runtime, security-negative, installer, and installed acceptance evidence.

## Explicit non-authorities

No Model Library, download, cloud provider, API key, raw path, directory scan, generic shell, generic IPC, RAG, tool execution, agent framework, Vault change, legacy-checkout change, or unrelated navigation/Settings change is included.

## Verification

Frontend 230/230, Rust 74 passed plus 2 expected environment-gated ignored, Python affected suites, changed-file compilation, cargo fmt/check/warnings-denied Clippy, Svelte check/build, sidecar checks, source hygiene, security review, and offline installer build passed. The supplemental legacy stability suite remains 18/20 solely because of two stale checks in untouched Tkinter code.

The installed app connected the approved Qwen model and rendered two consecutive real answers. Stop produced one `cancelled` terminal with stable partial text and no late mutation; retry and process-clean restart both produced another response. The registered-uninstaller rollback preserved exact managed model/runtime hashes and reinstall restored the app. Source reconstruction/reverse-apply evidence proves the exact WP00 rollback target without changing the canonical checkout.

## Distribution

- `INTERNAL_BOOTSTRAP_MODEL`
- `UNSIGNED_INTERNAL_BUILD`
- `NOT_PUBLIC_DISTRIBUTION_READY`

Final internal installer: `LocalComet_0.0.0_x64-setup.exe`, 12,526,459 bytes, SHA-256 `4557672ade41947b3de4356e5ff8b97757643b78fff8ffbfe1e990d3f82ee4ff`.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP01_ROLLBACK.md (39 строк, 3499 байт)

````markdown
# UP05-WP01 Rollback

Status: source and installed rollback rehearsals passed.

## Source rollback

UP05-WP01 depends on the exact UP05-WP00 commit `fa664b16c48c0377841dc334b89b2b3868a0249c`. Revert only the R2 commits in reverse order. Do not reset, rewrite, or move `main`, the WP00 branch, or the prior blocked WP01 branch.

The completed rehearsal used external Git-object materializations, not a clone. It materialized the exact 359-file WP00 tree and a separate WP00 candidate, applied the bounded R2 patch forward, proved that candidate byte-identical to the exact 366-file implementation HEAD, and passed a reverse-apply check back to WP00. The canonical checkout was not mutated and no file was deleted. The approved catalog/trust proofs remained present and no GGUF or managed llama.cpp runtime payload was tracked.

Source result: PASS at `C:\Users\DNS\Documents\LocalComet-UP05-WP01-R2-Rollback-20260720T175300Z`; patch SHA-256 `87c93046ecbdd862538ae727eb5a8e1dc23d6f9113422e9ff655ef28a6eb5e88`.

## Runtime rollback

Before rollback, request bounded cancellation of any active inference, stop the managed runtime through its typed command, close LocalComet normally, and prove no LocalComet-owned `llama-server`, sidecar, or application process remains. If graceful cleanup reaches its bound, rely on the existing contained job/process ownership to terminate only the owned process tree and record the typed shutdown result.

UP05-WP01 does not change artifact approval or acquire new bytes. The approved model and llama.cpp installation under LocalComet-owned app data must remain unchanged and hash-valid across rollback.

## Installed application rollback

1. Resolve the current uninstaller only from the exact current-user LocalComet uninstall registration.
2. Verify the resolved executable remains under the expected per-user LocalComet installation directory.
3. Close the app and prove owned processes are stopped.
4. Run that exact uninstaller without selecting app-data removal.
5. Verify installer-owned executable, resources, shortcuts, and uninstall registration are removed.
6. Preserve LocalComet app data, including the approved managed runtime/model and their metadata.
7. If restoring a prior internal installer, validate its checksum and install it current-user; launch only through its Start Menu shortcut.

Never delete or recursively modify broad profile, app-data, repository, Vault, or legacy-checkout paths.

Completed result: PASS. The registered uninstaller exited 0; the installation root, Start Menu/Desktop shortcuts, and uninstall registration were absent afterward. The approved model remained 1,117,320,736 bytes with SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, and the approved runtime executable remained 9,216 bytes with SHA-256 `3a8aea5f889c4b4c2ec41c98f4e1ed484bb7a40c4096883acb23d3cfe26b59fb`. Reinstall exited 0 and restored the final installed executable, shortcuts, and registration.

## Data and compatibility

Chat messages introduced by this package are bounded in-memory UI state and are not a persistence migration. The package adds no database schema, registry data format, cloud state, API key, or model-format migration. Rollback therefore requires no user-data transform.

## Unsafe rollback stop

Stop with `BLOCKED_UNSAFE_ROLLBACK` if exact process ownership, exact installer ownership, preservation of managed artifacts, or the WP00 target tree cannot be proven without broad or destructive action.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP01_STATE_MACHINE.md (99 строк, 6947 байт)

````markdown
# UP05-WP01 State Machine

Status: implemented and verified R2 lifecycle. Durations below are internal reliability bounds, not production performance baselines.

## Independent state domains

| Domain | States | Authority |
| --- | --- | --- |
| Control Plane | `disconnected`, `connecting`, `connected`, `failed` | Sidecar supervisor hello/status and typed bridge result |
| Managed runtime | `unavailable`, `starting`, `ready`, `failed`, `stopping` | Tauri managed-runtime supervisor and contained process ownership |
| Model | `unavailable`, `validating`, `loading`, `ready`, `failed`, `unloading` | Catalog validation, managed launch session, exact model alias, and inference readiness probe |
| Inference request | `idle`, `submitted`, `accepted`, `streaming`, `completed`, `cancelling`, `cancelled`, `timed_out`, `failed` | Request-scoped typed lifecycle keyed by frontend-created request ID |

Control Plane connectivity does not advance runtime, model, or inference state. Catalog/install readiness alone does not mean the model is loaded. Runtime process readiness alone does not mean model-specific inference is ready.

## Truthful model-ready predicate

The UI may display model connected and enable Send only when every condition is true:

1. the source-controlled catalog identity is internally consistent;
2. the selected stable model ID is approved and installed with its expected size/hash;
3. a compatible approved runtime ID is installed and all required files validate;
4. the contained runtime process is `ready`, loopback-owned, and exposes the exact expected alias;
5. the model state is `ready` after bounded model load and a model-specific inference readiness probe;
6. the in-memory backend binding names the same stable model ID and current runtime instance ID;
7. frontend selection, managed status, readiness, and binding agree on the same model/session.

If any condition becomes false, readiness becomes false immediately, Send is disabled, and no inference request enters `submitted`.

## Typed request identity

Each request owns these immutable fields:

- `request_id`: frontend-created lowercase hexadecimal ID, known before submit;
- `chat_session_id`: bounded current local chat identifier;
- `model_id`: approved stable catalog model ID;
- `submitted_at_unix_ms`: non-negative frontend submission timestamp;
- `binding_fingerprint`: current backend-issued binding identity;
- `generation`: fixed bounded parameters supported by the local completion path.

The backend may retain an internal turn ID, but every acceptance, content event, terminal event, and cancellation acknowledgement carries the stable request ID. Absolute paths, credentials, and raw protocol frames never cross into the UI contract.

## Request transitions

```text
idle -> submitted -> accepted -> streaming -> completed -> idle
                    |             |
                    |             +-> cancelling -> cancelled -> idle
                    |             +-> timed_out -> idle
                    |             +-> failed -> idle
                    +-> cancelling -> cancelled -> idle
submitted -> failed (rejected or acceptance timeout) -> idle
accepted -> completed (valid zero-content terminal) -> idle
```

Rules:

- The listener is active before `submitted`.
- Only one active request is permitted in this bounded chat.
- Acceptance cannot overwrite a terminal state already observed for the same request.
- Content is accepted only for the exact active request/session/model and only in strictly increasing sequence.
- Empty content chunks do not mutate the assistant message or activity timers.
- The first accepted request event establishes the backend turn ID; later events must match it.
- Exactly one terminal transition is accepted. Duplicate terminal events and any event after terminal are ignored/rejected and never mutate UI.
- Once cancellation is accepted, `completed` and further content are invalid; only `cancelled`, `timed_out`, or `failed` may close the request.
- A terminal transition clears all request timers, releases bounded listener/request records, stops the spinner, and restores a usable composer when model readiness remains true.

## Chat-message projection

An accepted submission creates exactly one user message and exactly one assistant message keyed to the request ID. Non-empty content chunks append to that assistant in order. Completion finalizes it. Cancellation, timeout, or failure preserve current partial text and annotate terminal status without adding a second assistant message. A rejected submission leaves the draft available for retry and does not create an accepted user/assistant pair.

## Internal reliability bounds

| Bound | Value | Typed outcome |
| --- | ---: | --- |
| Runtime capability/process startup | 5 seconds per existing capability/process wait | `runtime_unavailable` or `runtime_start_timeout` |
| Model load and exact readiness | 300 seconds | `model_load_timed_out` |
| Tauri request acceptance | 5 seconds; frontend guard no longer than 6 seconds | `request_acceptance_timeout` |
| First non-empty content | 30 seconds after acceptance | `first_token_timeout` |
| Stream inactivity after content begins | 10 seconds | `stream_inactivity_timeout` |
| Overall inference | 120 seconds | `request_timed_out` |
| Cancellation acknowledgement | 5 seconds | `cancel_ack_timeout` followed by stable local terminal recovery |
| Runtime/process shutdown | 5 seconds total bounded ownership cleanup | `shutdown_timeout` with process containment retained |
| Sidecar pipe delivery | 2 seconds bounded non-blocking retry | typed delivery failure and owned sidecar retirement |

Implementation may retain a shorter safe existing bound, but it must not silently widen a bound. Timeout events are terminal exactly once and remain retryable only when the runtime/model session is still healthy.

## Error classes

User-visible errors are bounded and sanitized. At minimum the typed path distinguishes `runtime_unavailable`, `approved_model_unavailable`, `model_validation_failed`, `model_load_failed`, `model_load_timed_out`, `request_rejected`, `request_acceptance_timeout`, `first_token_timeout`, `stream_inactivity_timeout`, `stream_interrupted`, `request_cancelled`, `cancel_ack_timeout`, and `protocol_mismatch`.

No error exposes stack traces, credentials, absolute private paths, provider JSON, or SSE framing.

## Observed installed transitions

- Two consecutive requests reached `completed` with visible assistant content.
- A long request reached `streaming -> cancelling -> cancelled` with 14 chunks and preserved partial output; the message and metrics were unchanged after a further 2.6 seconds.
- The next request reached `completed`, proving cancellation cleanup and retry recovery.
- Closing and reopening the installed application left no owned orphan and produced another `completed` response after the runtime/model binding was re-established.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP01_TEST_AND_ACCEPTANCE_PLAN.md (97 строк, 8502 байт)

````markdown
# UP05-WP01 Test and Acceptance Plan

Status: R2 acceptance complete with one explicitly classified legacy limitation.

## Isolation and baseline

- Work only on `feat/up05-wp01-r2-real-model-chat` from `fa664b16c48c0377841dc334b89b2b3868a0249c`.
- Keep `main` and `origin/main` at `6c784ace543e345bdb8bd2f778be974dc89f2df5`.
- Do not move the previous blocked branch.
- Use locked/offline dependency modes and loopback inference only. Do not download or browse.
- Do not access the Vault or legacy checkout.
- Do not place generated reports, model/runtime bytes, credentials, or private paths in Git.

The production ignored artifact-trust test passed for the owner-provisioned bootstrap artifacts. A direct approved runtime/model streaming request produced non-empty content, 16 JSON chunks, 14 content chunks, exactly one `[DONE]`, and no orphan process. Observed timings were 1027.458 ms load, 382.014 ms first content, and 389.777 ms total. They are observations only.

## Frontend gates

- Run all existing Vitest tests.
- Add model-status tests for approved catalog/install/runtime/model/binding agreement.
- Add a pure chat reducer suite for one user/assistant pair, ordered non-empty chunks, partial preservation, and one terminal.
- Prove listener registration completes before submit.
- Prove request/session/model ID filtering, strict sequence, duplicate terminal rejection, late-token rejection, and no old-request contamination.
- Prove acceptance cannot resurrect an early terminal.
- Prove main-composer Stop targets only the active request.
- Prove cancellation acknowledgement, accepted-cancel precedence, acceptance timeout, first-token timeout, inactivity timeout, and retry recovery.
- Prove no submission occurs without truthful model readiness.
- Prove listener teardown/remount does not accumulate listeners or disable later initialization.
- Run Svelte/type check and production frontend build.

## Rust/Tauri gates

- Run `cargo fmt --check`.
- Run locked/offline `cargo check`.
- Run warnings-denied locked/offline Clippy.
- Run all Rust tests and focused typed command/event tests.
- Prove exact request payload fields, bounded generation values, event identity/sequence validation, one terminal, cancellation precedence, registry cleanup, and rejection of late/foreign events.
- Prove managed runtime is single-instance, loopback-owned, model-ready only after exact alias and inference readiness, and cleaned up on stop/drop.
- Prove bounded runtime startup, model load, cancel, log-reader, and shutdown paths.
- Run release build and Tauri NSIS bundle offline.

## Backend/runtime gates

- Run Python compile/static checks for changed files.
- Run existing model gateway, SSE UTF-8, managed runtime, desktop IPC, sidecar supervisor, and control-plane tests.
- Add a managed real/fake integration proving the outbound chat model field uses the validated alias while events retain the stable model ID.
- Prove response/acceptance is serialized before request events.
- Prove request identity validation, one active request, content ordering, empty-chunk handling, `[DONE]`, one terminal, cancellation, timed-out terminal mapping, second request, and shutdown cleanup.
- Re-run direct approved-model validation and real non-empty SSE inference after implementation.

## Security-negative gates

Reject an unknown model ID, tampered installed model, raw path input, unknown runtime ID, request/model mismatch, foreign request event, invalid sequence, duplicate terminal, and LAN endpoint. Static and runtime checks must confirm generic shell, raw IPC, frontend approval mutation, download behavior, and managed artifact bytes in the installer are absent.

## Legacy stability classification

Re-run `russian control panel menu` and `control panel init smoke` directly. Current evidence identifies them as stale assertions against the retired Tkinter tabbed panel and old `v6.02` class/version. The implementation does not touch that panel. Record their exact results; they block only if a changed model/chat dependency causes a new relevant failure.

Completed result: 18/20. Direct reruns reproduced only those two expected failures. `LocalComet_Control_Panel.py` and `modules/stability_test.py` are byte-identical to the exact WP00 base, so this is retained as a legacy limitation rather than reported as an R2 regression.

## Installed acceptance

After all source checks pass:

1. Build the internal NSIS installer from the final R2 implementation HEAD using the existing offline UP00 helper in a clean tracked-files materialized workspace. No clone, branch move, or canonical checkout mutation is used.
2. Copy the installer to the required external artifact directory and create checksums, install/setup guidance, and unsigned-internal notice.
3. Verify the package and installed tree contain no approved managed llama.cpp runtime, GGUF, runtime archive, or matching approved artifact hashes. The established private Python sidecar runtime remains an expected application resource.
4. Install current-user, resolve and launch the actual Start Menu shortcut, and inspect the rendered app through the in-app Browser when available.
5. Connect the approved model and record truthful runtime/model readiness.
6. Send `Ответь одним коротким словом: ГОТОВО`; require acceptance, visible non-empty assistant content, one terminal, and stopped generation state.
7. Send a second short prompt without restarting; require a second non-empty assistant response.
8. Start a longer response and press Stop; require terminal cancellation, no late mutation, and a usable next request.
9. Close the application; require no LocalComet-owned runtime orphan. Reopen from Start Menu, reconnect, and obtain another response.
10. Record load, first-token, total duration, chunk count, and terminal state as safe observations only.

Completed installed observations:

- Installer: `LocalComet_0.0.0_x64-setup.exe`, 12,526,459 bytes, SHA-256 `4557672ade41947b3de4356e5ff8b97757643b78fff8ffbfe1e990d3f82ee4ff`.
- First prompt rendered `Ваш запрос коротко обозначает состояние готовности, поэтому можно ответить: ГОТОВО.`; `completed`, 25 chunks, 95 ms first content, 592 ms total.
- Second prompt rendered `Четвертый.`; `completed`, 6 chunks, 41 ms first content, 153 ms total.
- Cancellation rendered partial `КОСМОС КОСМОС КОСМОС КОС`; `cancelled`, 14 chunks, 52 ms first content, 308 ms total; no mutation after 2.6 seconds.
- Retry rendered `NO`; `completed`, 1 chunk, 48 ms first content, 66 ms total.
- Restart rendered `OK`; `completed`, 1 chunk, 77 ms first content, 96 ms total. No application, installed sidecar, or llama.cpp orphan remained before restart.

## Rollback and closure gates

- Rehearse source rollback without a clone or destructive mutation: materialize exact WP00/R2 Git blobs externally, reconstruct R2 from WP00, prove exact HEAD equality, and pass the reverse-apply check back to the exact WP00 tree.
- Rehearse installed rollback through the exact registered per-user uninstaller while preserving managed app data, then restore the R2 installer if needed for final evidence.
- Confirm feature worktree/index clean, `main` and `origin/main` unchanged, old blocked branch unchanged, nothing pushed, and no pull request opened.

Completed automated results:

- Frontend: 230/230 Vitest; Svelte check 0 errors and one pre-existing `LanguageSwitcher.svelte` warning; production build PASS.
- Rust: fmt/check/warnings-denied Clippy PASS; 74 passed and 2 expected environment-gated ignored; focused pipe/lifecycle suites PASS, including a live non-reading sidecar bounded at about 2.01 seconds.
- Python: changed-file `py_compile` PASS; R2 backend 13/13; knowledge 86/86; SSE UTF-8 23/23; clean materialized legacy gateway/source-hygiene 9/9; sidecar source checks 225/225.
- Security/diff review and installer payload scan PASS; no GGUF, approved llama.cpp payload, runtime archive, matching managed-artifact hashes, generic shell, raw IPC, LAN endpoint, frontend approval mutation, or new download authority was introduced.
- Source rollback PASS at `C:\Users\DNS\Documents\LocalComet-UP05-WP01-R2-Rollback-20260720T175300Z`.
- Registered-uninstaller rollback PASS; installer-owned files, shortcuts, and registration were removed while the exact managed model/runtime bytes remained unchanged, then the final installer restored the app.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_APPROVED_MODEL_ACQUISITION_AND_MANAGER.md (46 строк, 2257 байт)

````markdown
# UP05-WP02 — Approved Model Acquisition and Basic Model Manager

## Baseline and scope

Phase A starts on `feat/up02-wp01-hf2-ui-hygiene-knowledge` at
`3f01a6b2baef51a27caa09914b5ec75dff365e55`. The checked baseline has a clean
worktree and index; `main` and `origin/main` both remain at
`6c784ace543e345bdb8bd2f778be974dc89f2df5`.

This work package adds one application-owned download path for the existing,
source-controlled bootstrap runtime and model. It does not create a marketplace,
accept user URLs, inspect arbitrary files, change AssistantContext authority, or
read the Vault.

## Current implementation

The approved catalog is
`desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json`.
`src-tauri/src/artifact_trust.rs` validates canonical catalog bytes, managed
relative paths, exact file hashes, model GGUF magic, and live installed state.
Managed roots are under `%LOCALAPPDATA%/LocalComet/runtimes/llama.cpp` and
`%LOCALAPPDATA%/LocalComet/models`.

`src-tauri/src/managed_runtime.rs` starts only the validated llama.cpp binary on
loopback and only connects the approved model. The first-use UI currently tells
the user to connect a model, but cannot acquire missing artifacts. The Settings
drawer has no Models section. Tauri CSP permits only the desktop IPC/loopback
connection; startup makes no artifact-network request.

## Minimum implementation

- Extend the catalog schema with immutable acquisition descriptors for the two
  already approved artifacts.
- Add a typed Rust acquisition manager with catalog-only URLs, redirect-host
  validation, streaming download, cancellation, verification, and atomic install.
- Expose only fixed Tauri commands taking safe artifact/job IDs.
- Add a Settings → Models section with explicit confirmation, bounded progress,
  retry, connection, disconnection, and safe bootstrap-model removal.
- Replace the missing-model dead end with truthful setup guidance.

## Explicit exclusions

No arbitrary URL, generic HTTP/filesystem/process command, cloud inference,
browser authentication, token, telemetry, update check, startup download,
runtime removal, model marketplace, AssistantContext internet authority, Vault
access, or project-context work is in this phase.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_APPROVED_REDIRECT_FIX_CHECKPOINT.md (75 строк, 3354 байт)

````markdown
# UP05-WP02 approved redirect correction checkpoint

Status: `CHECKPOINT_PHASE_A_APPROVED_REDIRECT_FIX_UI_SMOKE_PENDING`

## Source correction

The approved Qwen model URL returned an HTTPS `302` redirect to the exact host
`us.aws.cdn.hf.co`. The prior immutable allowlist did not contain that host, so
the backend correctly rejected the redirect before creating a payload.

Commit `38e64b3a9349a27d9b0df108bf1e4beda23ca3de` adds only
`us.aws.cdn.hf.co` to the entry-specific redirect-host allowlist for
`qwen2.5-1.5b-instruct-q4-k-m`. The runtime artifact does not inherit that
host.

The correction preserves the existing backend-owned contract: exact
case-normalized host equality, HTTPS-only URLs, no explicit port, no userinfo,
and no wildcard, suffix, dynamic, or frontend-provided redirect trust.

The following immutable model fields did not change:

- ID: `qwen2.5-1.5b-instruct-q4-k-m`
- URL: `https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Filename: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Expected bytes: `1117320736`
- Expected SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`

## Redirect evidence and tests

One header-only request to the exact committed model URL returned `302`, with
Location host `us.aws.cdn.hf.co` and HTTPS preserved. No response body or
model payload was saved, and no credentials were sent.

The focused regression tests passed:

- `model_redirect_authority_requires_exact_https_host` accepts the original
  host, each pre-existing exact host, and `us.aws.cdn.hf.co`.
- It rejects HTTP, an explicit port, userinfo, the exact-host suffix and prefix
  attacks, sibling/lookalike hosts, a trailing-dot variant, and an IP literal.
- `embedded_catalog_is_canonical_and_exactly_pinned` verifies the canonical
  catalog digest, the immutable model fields, the exact host list, and that
  the unrelated runtime entry does not inherit the model CDN host.

## Completed verification

- Focused Rust tests: passed.
- Complete Rust suite: `93 passed`, `2 expected ignored`, `0 failed`.
- Frontend suite: `17 files`, `265 passed`.
- Svelte check: `0 errors`; the one pre-existing `LanguageSwitcher` listbox
  tabindex warning remains unchanged.
- Production frontend build: passed.
- `cargo check --locked --offline`: passed.
- `cargo clippy --locked --offline --all-targets -- -D warnings`: passed.
- Normal offline NSIS build with the restored real sidecar: passed.

Generated NSIS artifact (not committed):

- `desktop/localcomet-desktop/src-tauri/target/release/bundle/nsis/LocalComet_0.0.0_x64-setup.exe`
- Bytes: `13864492`
- SHA-256: `77f0af06c5c28010d8899f45d9c7e9bcc5d0671fbf5090f01318fe9dc2c6e4ed`

## Packaged smoke status

`NOT STARTED`

Classification: `BLOCKED_PHASE_A_ACCEPTANCE_AUTOMATION_ENVIRONMENT`.

The Windows UI-control system could not attest the active browser/UI context;
policy therefore prohibited packaged interaction. This is an automation
environment blocker, not an installer, downloader, redirect-integrity, or
LocalComet product failure. No packaged redirect-acceptance result is claimed.

No model payload was downloaded. The normal-profile model was not accessed or
changed. Phase A remains open, and Phase B remains prohibited pending a new
authorized packaged smoke run.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_DOWNLOAD_STATE_MACHINE.md (26 строк, 1246 байт)

````markdown
# UP05-WP02 — Download State Machine

Each job is keyed by an opaque application-generated job ID and a catalog
artifact ID. Only one active job may exist for an artifact.

```text
awaiting_confirmation → checking_disk → downloading
                                        ↓
       cancelling ←────────────────────┘
           ↓
       cancelled

downloading → verifying_size → verifying_hash → validating_artifact
 → installing → completed
             └────────────────────────────────────────────→ failed
```

`cancelled`, `completed`, and `failed` are terminal. A state records expected
and received byte counts, calculation-safe percent, UTC millisecond timestamps,
and a bounded safe error code. A duplicate start returns the existing active
job rather than creating a second transfer.

Temporary bytes live only below `%LOCALAPPDATA%/LocalComet/acquisition`, named
from the opaque job ID and ending in `.partial`. Partial bytes are verified
before an atomic rename and are never an installed artifact. At startup, only
owned stale partial files are removed; they are never promoted.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_LLAMA_CPP_LICENSE_PROVENANCE.md (42 строк, 1774 байт)

````markdown
# UP05-WP02 llama.cpp MIT license provenance

## Recovered source-controlled asset

- Repository destination: `third_party/llama.cpp/LICENSE-MIT.txt`
- Bytes: `1078`
- SHA-256:
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`

The file was copied byte-for-byte from the existing approved LocalComet runtime
asset at:

`C:\Users\DNS\AppData\Local\LocalComet\runtimes\llama.cpp\llama-cpp-windows-x86-64-cpu-bootstrap\LICENSE-MIT.txt`

## Local provenance

`C:\Users\DNS\Documents\LocalComet-UP05-WP00-Evidence-20260720T130509Z\05_UPSTREAM_SOURCE_PINS.tsv`
records this exact source as the separate `runtime_license` artifact for
`ggml-org/llama.cpp` revision `571d0d540df04f25298d0e159e520d9fc62ed121`:

- acquired filename: `llama.cpp-LICENSE-MIT.txt`;
- bytes: `1078`;
- SHA-256:
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`;
- associated approved runtime archive:
  `llama-b10068-bin-win-cpu-x64.zip`, `18,007,324` bytes, SHA-256
  `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`.

`06_RUNTIME_ARCHIVE_VALIDATION.md` and
`08_MANAGED_INSTALLATION_RESULT.md` in the same evidence directory record that
the exact license asset was included in the 31-file approved runtime package by
the UP05-WP00 baseline.  `16_FINAL_RESULT.yaml` records its feature head as
`fa664b16c48c0377841dc334b89b2b3868a0249c`.

## Boundary

No network retrieval occurred and no license text was reconstructed.  This
checkpoint only restores a source-controlled metadata asset.  It does not
change the archive envelope, downloader, catalog behavior, runtime
installation, package, model, or executable trust.  A subsequent explicitly
scoped mission must wire this proven asset into the exact runtime
envelope/installable-member contract.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_PACKAGED_PROFILE_ISOLATION_FIX.md (50 строк, 2365 байт)

````markdown
# UP05-WP02 packaged profile isolation fix

## Root cause

The packaged startup log resolved %LOCALAPPDATA%\LocalComet directly, while
the backend passed Tauri's Windows known-folder local_data_dir() into the
managed artifact service. Changing the child process environment therefore
split frontend startup logging from backend model/runtime storage.

## Path map

| Consumer | Before | After |
| --- | --- | --- |
| Startup log | %LOCALAPPDATA%\LocalComet\logs | authoritative application-data root + logs |
| Approved model final path | Tauri local-data directory + LocalComet\models | authoritative root + models |
| Acquisition partial/staging | Tauri local-data directory + LocalComet\acquisition | authoritative root + acquisition |
| Installed-model discovery/removal | managed artifact roots from Tauri local-data directory | managed artifact roots from authoritative root |
| Runtime/model arguments and key state | managed artifact roots from Tauri local-data directory | managed artifact roots from authoritative root |

## Contract

LOCALCOMET_APP_DATA_ROOT is an opt-in exact LocalComet application-data
directory. It must be a nonempty absolute local filesystem path; empty,
relative, and Windows UNC paths are rejected. Invalid values stop startup
without falling back to the normal profile.

Without the override, the production root is unchanged:

app.path().local_data_dir()/LocalComet

The backend owns every model-related path. The frontend supplies no destination,
URL, hash, model, or staging path.

## Regression coverage

- default production path remains unchanged;
- absolute overrides select the exact root and startup logging uses it;
- empty, relative, and network-share overrides are rejected;
- runtime, model, state, and acquisition paths derive from one root;
- a synthetic model in a separate default profile is neither discovered nor
  selected as the managed-model removal destination;
- runtime --model and --api-key-file arguments use paths under that root.

## Packaged smoke result

The rebuilt NSIS package was launched with a fresh
LOCALCOMET_APP_DATA_ROOT. Startup logs and acquisition staging appeared only
under that root. No model/runtime directories were created, the UI remained in
the no-model setup state, and no LocalComet process remained after closing the
window. No model download or chat action was performed.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_PHASE_A_FINAL_CHECKPOINT.md (249 строк, 13670 байт)

````markdown
# UP05-WP02 Phase A final checkpoint

Status: `PASS_LC_PE01_PHASE_A_COMPLETE_CHECKPOINTED`

LC-PE01 Phase A is complete and checkpointed. Phase B Project Knowledge has
not started and remains outside this checkpoint.

## Repository checkpoint

- Branch: `feat/up05-wp02-approved-model-manager`
- Pre-checkpoint HEAD: `573434dd4a35250758fc65168929042e37fc48b4`
- `main`: `6c784ace543e345bdb8bd2f778be974dc89f2df5`
- `origin/main`: `6c784ace543e345bdb8bd2f778be974dc89f2df5`
- Tracked worktree and index were clean before this documentation file.
- The established generated sidecar tree under
  `desktop/localcomet-desktop/src-tauri/binaries/` remains untracked and is
  deliberately excluded from the checkpoint.

## Complete UP05-WP02 commit chain

1. `32b7a1834b423adfcaba417015c59c6ebc58c330` — `docs(up05): define approved acquisition and model manager`
2. `7381bf2f4340574891dcd8a3ae84f493298cd42e` — `feat(model): add approved artifact acquisition contract`
3. `79b78625c7db059679eabb26e439423032f83a59` — `feat(model): implement verified atomic artifact installation`
4. `94d0f354ab3b2b34ed10f8d4d7bb105c522182c9` — `feat(settings): add basic local model manager`
5. `c99dfc4f182a4b548599f9ea869293a609ea39bf` — `test(model): validate downloader and model-manager boundaries`
6. `46762ff3eafd6169f2dc9dfad30bc44694bc1fb7` — `docs(up05): record phase A verification blocker`
7. `c0a60d1ba3d228c8cea31c1724bec190be9256c1` — `fix(storage): unify packaged application data root`
8. `3c7bc0df6c150e204c6d76920cc62f2823d42c3f` — `docs(up05): record packaged profile isolation fix`
9. `38e64b3a9349a27d9b0df108bf1e4beda23ca3de` — `fix(catalog): allow exact approved Hugging Face redirect`
10. `7874a44995031767694dadeaf97a656e2ce5278b` — `docs(up05): checkpoint redirect fix pending packaged smoke`
11. `051801b9223438fc908a1f3297cd8fbf7ec1f893` — `fix(acquisition): persist bounded terminal failure diagnostics`
12. `e53393f60ca19c8d3a8a28cd3d57e5d06affa121` — `docs(up05): record runtime diagnostics checkpoint`
13. `4d135e07529f1d7e6dce459a7167f62080addf09` — `legal(runtime): add pinned llama.cpp MIT license asset`
14. `eaf20ceee2a76c8478562cd9c05890c189321214` — `fix(runtime): enforce exact archive envelope`
15. `3904b3aa6aa4e996f09a04176e8f0e0dd631a3e4` — `docs(up05): record runtime archive envelope`
16. `573434dd4a35250758fc65168929042e37fc48b4` — `fix(packaging): align startup-log scan with app-data root`

## Source, test, and package gates

- The immutable catalog owns the exact model/runtime URL, redirect allowlist,
  expected filename, byte count, SHA-256, and managed destination. The
  frontend supplies only a fixed artifact ID and explicit confirmation.
- The backend enforces HTTPS and exact redirect-host equality, bounded
  streaming, cancellation, expected size and SHA-256, runtime ZIP envelope
  validation, staging, same-volume atomic promotion, live post-install trust,
  and owned cleanup.
- `LOCALCOMET_APP_DATA_ROOT` is the single packaged startup, acquisition,
  model, runtime, and runtime-state root. Empty, relative, and UNC overrides
  fail closed.
- The latest complete Rust suite passed `103` tests, with the two intentional
  offline/bootstrap tests ignored. The real verified b10068 ZIP offline test
  also passed against a temporary test destination.
- Frontend verification passed `17` files and `265` tests.
- `cargo check --locked --offline` passed.
- `cargo clippy --locked --offline --all-targets -- -D warnings` passed.
- Svelte check completed with zero errors. The one pre-existing
  `LanguageSwitcher.svelte` listbox `tabindex` accessibility warning remains
  unchanged.
- The production frontend build passed.
- The normal locked/offline NSIS build with the restored generated sidecar
  passed; no package configuration override was used for the accepted
  candidate.
- Final package-source verification passed `234` checks. Its focused
  startup-log scan regressions passed `9` checks; the focused Rust
  app-data-root and startup suites passed `4` and `3` tests respectively.
- `git diff --check` is the final documentation gate before commit.

## Accepted current candidate

- Installer:
  `C:\Users\DNS\Documents\LocalComet\desktop\localcomet-desktop\src-tauri\target\release\bundle\nsis\LocalComet_0.0.0_x64-setup.exe`
- Installer bytes: `13878331`
- Installer SHA-256:
  `d17f84d0cbcb9a0503cc1c1196c80a126bc61565c04170c644b50530fd4c48eb`
- Installed executable:
  `C:\Users\DNS\AppData\Local\Programs\LocalComet\LocalComet.exe`
- Installed executable bytes: `14220288`
- Installed executable SHA-256:
  `97e8aee1806d6c7da18ff365e9f9b04e312d35a90ae989826381d8c0b0d93c51`
- Canonical NSIS uninstaller:
  `C:\Users\DNS\AppData\Local\Programs\LocalComet\uninstall.exe`
- Uninstaller bytes: `69394`
- Uninstaller SHA-256:
  `d8da71baa2cac61513bcd9920f47421bfb10cdae6fc69bfa785118747f030cf8`

## Profile isolation, redirect, and cancellation

The accepted application-data root is:

`C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet`

Packaged launches inherited this exact override. Startup logging, backend
readiness, acquisition, model discovery/removal, runtime discovery, runtime
arguments, API-key state, and cleanup resolved beneath it. No normal-profile
model path appeared in process arguments or isolated logs.

The Qwen URL remains revision-pinned. The exact observed redirect host
`us.aws.cdn.hf.co` was added only to that model entry. HTTPS-only exact-host
tests rejected ports, userinfo, wildcard/suffix/prefix variants, lookalikes,
trailing dots, and IP literals. Operator-assisted packaged transfer reached
non-zero progress, cancellation completed, and no final, partial, temporary,
staging, download, or duplicate payload remained.

Normal-profile directory metadata remained unchanged through every packaged
launch and installer operation. Its model content was never entered, opened,
hashed, loaded, removed, or modified by this work package.

## Runtime archive-envelope acceptance

- Runtime: `llama.cpp b10068`
- Approved archive: `llama-b10068-bin-win-cpu-x64.zip`
- Archive bytes: `18007324`
- Archive SHA-256:
  `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`
- Exact envelope: `51` top-level regular members.
- Install disposition: `30` pinned files.
- Recognized-not-installed disposition: `21` executable members; none was
  extracted, installed, or launched.
- Source-controlled injected license: `LICENSE-MIT.txt`, `1078` bytes,
  SHA-256
  `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`.
- Final runtime inventory: exactly `31` files, zero missing, mismatched,
  unexpected, or nested entries.

Bounded acquisition diagnostics proved the original archive-envelope failure,
cleanup-before/after records, and zero retained payload. The corrected envelope
then passed the synthetic suite, the independently verified real ZIP test, the
packaged runtime retry, and final live trust validation.

## Model lifecycle and local inference acceptance

- Model ID: `qwen2.5-1.5b-instruct-q4-k-m`
- Final model path:
  `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet\models\qwen2.5-1.5b-instruct-q4-k-m\qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Model bytes: `1117320736`
- Model SHA-256:
  `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`

The packaged model connected through the approved isolated `llama-server.exe`
on loopback. Health returned HTTP 200, the model was listed as owned by
`llamacpp`, one non-empty real local response completed, and no non-loopback
inference connection was observed. The operator then disconnected and removed
the model. The final file and managed directory disappeared, no process lock or
partial remained, and the runtime stayed 31/31. A complete approved redownload
promoted the model only after exact size and SHA-256 verification; no duplicate
or acquisition residue remained. The model was left installed and disconnected.

## Current-candidate continuity acceptance

Before the first uninstall, the complete isolated profile contained `43`
entries with signature
`ad3093bb2954a3c5a2f91767b1bfff72ef22417df274c9e1c148ae4c6ed7d0f5`.
The canonical current uninstaller exited `0`; installation files and registry
metadata were removed without touching that profile. The exact current
installer then exited `0`, restored the accepted executable identity, and left
the same profile signature.

The reinstalled candidate recognized both approved artifacts without starting
an acquisition. Operator-assisted connection started the isolated runtime with
the isolated GGUF argument, health returned HTTP 200, and one non-empty local
response completed. No non-loopback inference connection occurred. Disconnect
and normal application closure left no managed process; model/runtime hashes
remained exact.

Result: `PASS_CURRENT_CANDIDATE_UNINSTALL_REINSTALL_CONTINUITY` and
`PASS_POST_REINSTALL_LOCAL_CHAT`.

## Approved HF2 rollback rehearsal

The approved installer-level baseline is linked by its local evidence manifest
to source commit
`408ba67245827889976bf3febf5cf297756127d6` (`build(installer): authorize the
up02 hf2 offline bundle`).

- HF2 installer:
  `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\LocalComet_0.0.0_x64-setup.exe`
- HF2 installer bytes: `12536287`
- HF2 installer SHA-256:
  `9ac01a6218da251b7ec24772320af22de535d68c17e5d8529b01e7d48fb8ca34`
- Observed installed HF2 executable bytes: `10106880`
- Observed installed HF2 executable SHA-256:
  `d2904690353d46ac72c05de282a8e8eadb0dc8de9fcfaa0206fd42cea93abda5`

The evidence manifest did not pre-record an installed executable hash, so the
observed value above is recorded as the result of running the exact
evidence-approved installer. The baseline was not launched because it predates
the confirmed unified profile-root behavior.

After post-reinstall chat, the complete isolated profile signature was
`56087984a114666dd8acce47372c819e01d4ffeecb0fc6ed4aea5a9abca87099`.
It remained identical after current uninstall, HF2 install, HF2 uninstall, and
current-candidate restoration. Both uninstallers and both installers exited
`0`. The restored current executable exactly matched the accepted candidate.

The restored candidate then recognized runtime and model without acquisition.
The final operator check connected only the isolated runtime/model, passed
loopback health, sent no chat, disconnected, and closed normally. No
non-loopback inference connection or acquisition activity occurred.

Result: `PASS_HF2_ROLLBACK_INSTALL`, `PASS_CURRENT_CANDIDATE_RESTORATION`, and
`PASS_FINAL_PACKAGED_CONTINUITY`.

## Final state

- Current candidate is installed.
- Approved runtime remains installed at
  `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\Profile\LocalComet\runtimes\llama.cpp\llama-cpp-windows-x86-64-cpu-bootstrap`.
- Runtime remains exactly `31/31`; all bytes and SHA-256 values match the
  immutable catalog, and none of the 21 skipped executables is present.
- Approved model remains installed at the exact path, byte count, and SHA-256
  recorded above.
- Acquisition entries: `0`.
- Runtime-state entries after closure: `0`.
- Partial/staging/download/backup residue: `0`.
- `LocalComet.exe` processes: `0`.
- `localcomet-core.exe` processes: `0`.
- `llama-server.exe` processes: `0`.

## Authoritative evidence

- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-ProfileIsolation-20260721T011604Z\PACKAGED_PROFILE_ISOLATION_FIX_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-PackagedAcceptance-20260721T012950Z\PACKAGED_MODEL_ACCEPTANCE_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RedirectSmoke-20260721T022326Z\OPERATOR_REDIRECT_SMOKE_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\RUNTIME_INSTALL_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\RUNTIME_DIAGNOSTIC_RETRY_EVIDENCE.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\RUNTIME_ARCHIVE_CONTENT_DRIFT.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\LICENSE_PROVENANCE_BLOCKER.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\RUNTIME_ARCHIVE_ENVELOPE_EXTRACTION_PLAN.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-RuntimeArchiveContractRepair-20260721T033042Z\PACKAGING_SCAN_AND_RUNTIME_RETRY_RESULT.md`
- `C:\Users\DNS\Documents\LocalComet-UP05-WP02-FullPackagedAcceptance-20260721T024704Z\PHASE_A_OPERATOR_PACKAGED_MODEL_LIFECYCLE_20260721T054455Z.md`
- `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\CHECKSUMS.tsv`
- `C:\Users\DNS\Documents\LocalComet-UP02-WP01-HF2-Artifacts-20260720T221533Z\ACCEPTANCE.md`

The historical blocker reports are retained because they establish the profile,
redirect, and runtime-envelope failure modes that the final accepted chain
corrected. They do not override the later PASS evidence.

## Boundaries preserved

- No product source changed during installer continuity, rollback, or final
  checkpoint acceptance.
- Installers, installed binaries, model/runtime payloads, logs, screenshots,
  generated sidecar files, and external evidence are not staged or committed.
- `C:\Users\DNS\Documents\LocalAgent` and
  `C:\Users\DNS\Documents\LocalCometVault` were untouched.
- Nothing was merged, pushed, or submitted as a pull request.
- Phase B was not started.

LC-PE01 Phase A is complete and checkpointed.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_PR_BODY.md (24 строк, 1032 байт)

````markdown
# UP05-WP02 — Proposed Change Description

## Summary

Adds a deliberately narrow LocalComet bootstrap acquisition path and Settings
model manager for the already approved llama.cpp runtime and Qwen GGUF model.

## Security boundary

Catalog data, not the frontend, controls URLs, redirect hosts, expected bytes,
hashes, filenames, formats, and managed destinations. Downloads require a user
confirmation and do not grant the model, chat, or frontend internet authority.

## Validation

The source checkpoint passes focused Rust acquisition tests, frontend
bridge/UI tests, the full frontend test/check/build sequence, isolated locked
offline Rust checks, and warnings-denied Clippy. Normal Rust packaging checks,
release build, bundle, and isolated acquisition acceptance remain blocked by
the missing baseline sidecar resource
`binaries/localcomet-core-x86_64-pc-windows-msvc.exe`.

This branch is the dependency base for Phase B only after the Phase A gate is
unblocked and passes; it is not based on `main` and is not pushed.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_ROLLBACK.md (11 строк, 604 байт)

````markdown
# UP05-WP02 — Rollback

Phase A source rollback is a forward, reviewable return from the Phase A branch
to `3f01a6b2baef51a27caa09914b5ec75dff365e55`; it is rehearsed in an isolated
worktree and never destructively performed in the canonical checkout.

Removing the source feature does not remove user-managed runtime/model bytes.
The acquisition directory contains only owned partial and staging bytes; a
rollback never targets unrelated models, chats, settings, or any selected user
files. A restart with predecessor source continues to use only the existing
validated catalog installation behavior.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_RUNTIME_ACQUISITION_DIAGNOSTICS.md (43 строк, 2510 байт)

````markdown
# UP05-WP02 runtime acquisition diagnostics checkpoint

## Scope

Phase A records a bounded, backend-owned terminal failure event before removing
the owned acquisition partial or runtime staging directory.  It does not alter
the approved artifact catalog, source URLs, hashes, archive contract, or
frontend acquisition authority.

The event is appended and flushed to:

`<LOCALCOMET_APP_DATA_ROOT>/logs/acquisition-events.jsonl`

Each JSONL record contains only `schema_version`, `timestamp_utc_ms`, artifact
kind and immutable catalog ID, terminal status, bounded stage, existing bounded
error code, received and expected byte counts, cleanup completion, and final
artifact existence.  It contains no URL, query string, path, response body,
credential, or frontend-supplied diagnostic content.

## Runtime failure path

| Bounded stage | Existing backend error codes | Cleanup / published state |
| --- | --- | --- |
| `transfer` | `download_failed`, redirect/content-type/partial I/O and preflight failures | owned partial and staging are removed; job is `failed` with the original code |
| `size_verification` | `size_mismatch` | owned partial and staging are removed; job is `failed` |
| `hash_verification` | `hash_mismatch`, `hash_read_failed` | owned partial and staging are removed; job is `failed` |
| `archive_validation` | `invalid_runtime_archive`, `unexpected_runtime_member`, `runtime_member_hash_mismatch`, `missing_runtime_member` | owned partial and staging are removed; job is `failed` |
| `staging_extraction` | `staging_create_failed`, `staging_write_failed` | owned partial and staging are removed; job is `failed` |
| `atomic_promotion` | `atomic_install_failed` | owned partial and staging are removed; job is `failed` |
| `post_install_validation` | `post_install_validation_failed` | invalid installed output is removed, then owned temporary resources are removed; job is `failed` |

Cancellation remains a non-failure terminal state and produces no failure
event.  A diagnostic write failure is ignored so the original acquisition
error remains authoritative.  A successful acquisition produces no terminal
failure event.

## Focused coverage

Synthetic-fixture tests cover the stage mapping, distinct size/hash/archive/
staging/promotion/post-install outcomes, event persistence before cleanup,
partial and staging cleanup, no final artifact after failure, no event on
success, catalog-owned identity and backend-owned values, sensitive-query
exclusion, and app-data-root isolation.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_RUNTIME_ARCHIVE_ENVELOPE.md (71 строк, 3607 байт)

````markdown
# UP05-WP02 — Runtime archive envelope

## Approved runtime identity

The `llama-cpp-windows-x86-64-cpu-bootstrap` contract remains pinned to llama.cpp
`b10068`, `llama-b10068-bin-win-cpu-x64.zip`, `18,007,324` bytes, and SHA-256
`01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`.
The URL and redirect-host allowlist are unchanged.

## Exact archive envelope

The source-controlled catalog contains all 51 normalized top-level regular ZIP
members, each with an explicit disposition.  It has no default or pattern
disposition.  Unknown, missing, duplicate, unsafe, directory, symlink, or
case-colliding members fail before extraction.

`Install` contains exactly 30 files: `llama-server.exe` plus the 29 pinned DLLs
already hash-bound in `required_files`:

- `ggml-base.dll`, `ggml-cpu-alderlake.dll`, `ggml-cpu-cannonlake.dll`,
  `ggml-cpu-cascadelake.dll`, `ggml-cpu-cooperlake.dll`,
  `ggml-cpu-haswell.dll`, `ggml-cpu-icelake.dll`, `ggml-cpu-ivybridge.dll`,
  `ggml-cpu-piledriver.dll`, `ggml-cpu-sandybridge.dll`,
  `ggml-cpu-sapphirerapids.dll`, `ggml-cpu-skylakex.dll`,
  `ggml-cpu-sse42.dll`, `ggml-cpu-x64.dll`, `ggml-cpu-zen4.dll`,
  `ggml-rpc.dll`, `ggml.dll`, `libomp140.x86_64.dll`,
  `llama-batched-bench-impl.dll`, `llama-bench-impl.dll`,
  `llama-cli-impl.dll`, `llama-common.dll`, `llama-completion-impl.dll`,
  `llama-fit-params-impl.dll`, `llama-perplexity-impl.dll`,
  `llama-quantize-impl.dll`, `llama-server-impl.dll`, `llama-server.exe`,
  `llama.dll`, and `mtmd.dll`.

`RecognizedNotInstalled` contains exactly 21 ZIP members.  They are validated
as part of the envelope but are never opened for extraction, written to staging,
promoted, hashed as installed files, or launched:

- `ggml-rpc-server.exe`, `llama-batched-bench.exe`, `llama-bench.exe`,
  `llama-cli.exe`, `llama-completion.exe`, `llama-fit-params.exe`,
  `llama-gemma3-cli.exe`, `llama-gguf-split.exe`, `llama-imatrix.exe`,
  `llama-llava-cli.exe`, `llama-minicpmv-cli.exe`, `llama-mtmd-cli.exe`,
  `llama-mtmd-debug.exe`, `llama-perplexity.exe`, `llama-quantize.exe`,
  `llama-qwen2vl-cli.exe`, `llama-results.exe`,
  `llama-template-analysis.exe`, `llama-tokenize.exe`, `llama-tts.exe`, and
  `llama.exe`.

## License injection and final inventory

`LICENSE-MIT.txt` is deliberately not a ZIP member.  After archive identity and
envelope validation, acquisition verifies the source-controlled
`third_party/llama.cpp/LICENSE-MIT.txt` asset at exactly 1,078 bytes and SHA-256
`94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`, then
writes it into staging.  The promoted runtime therefore contains the 30
`Install` files plus this one license file, with no other member.

Post-install validation includes the injected license.  The launcher remains
bound to the installed `llama-server.exe` only.

## Bounded diagnostics and validation

Archive-envelope failures retain the existing structured diagnostic event and
may include a normalized member name, explicit disposition, and expected versus
observed member counts.  They never include redirect query strings, response
bodies, or frontend-provided authority.

The focused synthetic ZIP tests cover successful 51-member selection, skipped
executables, unknown executable/DLL/text members, missing installable and
recognized members, duplicate/traversal/directory rejection, disposition drift,
license identity failure, atomic promotion boundaries, and the bounded event
fields.  The separately ignored offline test accepts an explicit verified
archive path and validates the real b10068 archive only into a temporary test
directory.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_SECURITY_MODEL.md (25 строк, 1383 байт)

````markdown
# UP05-WP02 — Security Model

The approved artifact catalog is the authority for acquisition identity. It
supplies the exact HTTPS primary URL, redirect-host allowlist, filename, byte
count, SHA-256, archive/format details, and managed relative destination. The
frontend supplies only a validated catalog artifact ID, then only an opaque job
ID for polling or cancellation.

The downloader manually validates every HTTPS redirect before following it.
Certificate validation remains enabled. It sends no browser credentials,
cookies, tokens, or frontend-provided headers. The only permitted upstream
identities are the catalog-declared GitHub release and Hugging Face artifact
origins/CDNs.

Downloads stream to an owned temporary file. Exact size and SHA-256 are checked
before installation. GGUF bytes must have the `GGUF` magic. Runtime ZIP entries
must be listed catalog files with safe relative paths; traversal, absolute,
drive-relative, duplicate/case-colliding, symlink, and unexpected entries fail.
The verified staging directory or model file is atomically renamed into the
catalog-declared managed root and revalidated from disk.

The acquisition authority belongs only to the desktop downloader after an
explicit UI confirmation. The language model, chat request, JavaScript, and
AssistantContext retain no internet, generic filesystem, shell, Vault, or tool
authority.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP02_TEST_AND_ACCEPTANCE_PLAN.md (30 строк, 1579 байт)

````markdown
# UP05-WP02 — Test and Acceptance Plan

## Automated source verification

Focused Rust tests cover canonical acquisition metadata, confirmation and
unknown-ID rejection, HTTPS/redirect-host enforcement, GGUF magic validation,
runtime ZIP traversal/case-collision/hash rejection, owned partial cleanup,
valid-artifact reuse, conflicting-artifact rejection, duplicate-job handling,
and terminal-state immutability. They create only temporary test directories
and make no external network request.

Frontend tests prove the bridge accepts no URL, destination, hash, header,
generic HTTP, or generic filesystem arguments; reject malformed projected job
states; and keep Settings and first-use actions bounded. Existing managed
artifact and chat lifecycle tests continue to run.

## Installed acceptance gate

The required isolated-root acquisition acceptance remains mandatory: acquire
the catalog-approved runtime and model, validate, connect, obtain two real
responses, Stop/Retry, cancel an in-progress model transfer, remove the
disconnected model, and redownload it. The installed runtime/model in the user
root must not be touched.

As of the current source checkpoint, that gate cannot start because the normal
Tauri build stops before compilation: the baseline checkout is missing
`binaries/localcomet-core-x86_64-pc-windows-msvc.exe`, which the package
configuration requires. The isolated source-level checks use a temporary Tauri
configuration override only to validate Rust code; it is not evidence of a
bundle, installer, network-acquisition, or chat acceptance pass.
````

### ПУТЬ: GenerateCapabilityMap.py (19 строк, 651 байт)

````python
"""Minimal placeholder, created 2026-07-25.

The original capability map generation module NEVER existed in this
repository (legacy of fictitious reporting, incident M-04).  Test v677
verifies only the contract: import without side-effects plus
LOCALCOMET_ROOT portability.  Real capability map generation is a
deliberate backlog task: implement or remove together with the test.
"""
from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    value = os.environ.get("LOCALCOMET_ROOT", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parent
````

### ПУТЬ: LocalComet_Control_Panel.py (1111 строк, 39208 байт)

````python
from __future__ import annotations

import importlib
import json
import os
import runpy
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


LOCALCOMET_VERSION = "v6.82"
LOCALCOMET_VERSION_LABEL = "LocalComet v6.82 - Explainable Task Planner & Approval Gate"
LEGACY_CONTROL_PANEL_RETIRED_RU_V650G = "v6.50g legacy tabbed control panel retired; launches new Computer Use menu only"
NEW_MENU_PATCH_COMMAND_BRIDGE_RU_V650J = "v6.50j route Patch Panel commands through new Computer Use menu"
COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651 = "v6.51 управляй пк first-class Computer Use route"

ROOT_DIR = Path(os.environ.get("LOCALCOMET_ROOT") or Path(__file__).resolve().parent).resolve()

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    os.chdir(ROOT_DIR)
except Exception:
    pass


def _json_safe(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _target_patch_panel() -> Path:
    candidate = ROOT_DIR / "LocalComet_Patch_Panel.py"
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parent / "LocalComet_Patch_Panel.py"


def _target_new_menu_module() -> str:
    return "modules.premium_task_panel_ru"


def _normalize_command(command: str) -> str:
    return str(command or "").strip().lower().replace("ё", "е")


def _is_strict_project_stability_ru_command(command):
    try:
        from modules.strict_project_stability_ru import is_strict_project_check_command
        return is_strict_project_check_command(command)
    except Exception:
        return False


def _run_strict_project_stability_ru_command(command):
    from modules.strict_project_stability_ru import dispatch
    return dispatch(command)


def _is_computer_use_command_bridge(command: str) -> bool:
    try:
        from modules.computer_use_core_ru import is_computer_use_command
        if is_computer_use_command(command):
            return True
    except Exception:
        pass
    lower = _normalize_command(command)
    prefixes = (
        "управляй пк",
        "сделай на компьютере",
        "агент пк",
        "computer use",
        "pc computer",
    )
    return any(lower == prefix or lower.startswith(prefix + " ") for prefix in prefixes)


def _run_computer_use_command_bridge(command: str) -> Dict[str, Any]:
    from modules.computer_use_core_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "computer_use_core_ru",
        "plan": {"tool": "computer_use_core_ru", "action": "dispatch"},
        "result": result,
    }


def _is_patch_panel_bridge_command(command):
    lower = _normalize_command(command)
    if not lower:
        return False
    exact = {
        "help",
        "помощь",
        "команды",
        "что умеешь",
        "?",
        "статус",
        "status",
        "обнови статус",
        "обновить статус",
        "refresh",
        "принять патч",
        "прими патч",
        "применить патч",
        "apply",
        "accept",
        "принять патч и проверить",
        "импорт",
        "import",
        "импорт проверка",
        "импорт + проверка",
        "import validate",
        "выбрать response",
        "выбери response",
        "select response",
        "choose response",
        "сброс выбора response",
        "сбросить выбор response",
        "clear selected response",
        "reset response source",
        "проверить проект",
        "проверь проект",
        "verify",
        "verify project",
        "checks",
        "проверки",
        "открыть relay",
        "relay",
        "open relay",
        "открыть reports",
        "reports",
        "open reports",
        "открыть отчеты",
        "открыть downloads",
        "downloads",
        "open downloads",
        "открыть logs",
        "logs",
        "open logs",
        "копировать лог",
        "копировать итог",
        "copy summary",
        "copy final summary",
        "статус патча",
        "patch status",
        "patch ux status",
        "открыть последний отчет",
        "open last report",
        "copy log",
        "сохранить лог",
        "save log",
        "очистить лог",
        "clear log",
        "перечитать панель",
        "reload panel",
        "перечитать код панели",
        "soft reload",
    }
    if lower in exact:
        return True
    prefixes = (
        "выбрать response ",
        "выбери response ",
        "select response ",
        "choose response ",
        "response ",
        "source ",
    )
    return lower.startswith(prefixes)


def _run_patch_panel_bridge_command(command):
    try:
        patch_panel = importlib.import_module("LocalComet_Patch_Panel")
        runner = getattr(patch_panel, "run_patch_panel_chat_command", None)
        if not callable(runner):
            return {
                "mode": "patch_panel_bridge",
                "route": "patch_panel_compact_chat",
                "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
                "result": "STOP: LocalComet_Patch_Panel.run_patch_panel_chat_command не найден.",
            }
        result = runner(command)
        return {
            "mode": "command",
            "route": "patch_panel_compact_chat",
            "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
            "result": result,
        }
    except Exception as exc:
        return {
            "mode": "patch_panel_bridge",
            "route": "patch_panel_compact_chat",
            "plan": {"tool": "LocalComet_Patch_Panel", "action": "run_patch_panel_chat_command"},
            "result": "STOP: patch panel bridge failed: " + str(exc),
        }


def _is_plain_desktop_goal(text: str) -> bool:
    lower = _normalize_command(text)
    if not lower:
        return False
    desktop_verbs = (
        "открой", "открыть", "откройте", "открывай", "открывайте",
        "запусти", "запустить", "запускай",
        "покажи", "показать", "покажите",
        "закрой", "закрыть", "закройте",
        "нажми", "нажать",
        "кликни", "кликнуть",
        "введи", "ввести",
        "выбери", "выбрать",
        "переименуй", "переименовать",
        "скопируй", "скопировать",
        "перемести", "переместить",
        "сохрани", "сохранить",
    )
    for verb in desktop_verbs:
        if lower == verb or lower.startswith(verb + " "):
            return True
    screenshot_keywords = ("скриншот", "скрин", "screenshot", "snapshot")
    for maker in ("сделай", "сделать", "сделайте", "создай", "создать", "создайте"):
        for obj in screenshot_keywords:
            if lower == maker + " " + obj or lower.startswith(maker + " " + obj + " "):
                return True
            if lower == obj or lower.startswith(obj + " "):
                return True
    desktop_phrases = ("покажи рабочий стол", "показать рабочий стол", "открой рабочий стол", "рабочий стол")
    for phrase in desktop_phrases:
        if lower == phrase:
            return True
    return False


def _is_working_directory_guard_command_ru_v665b(command):
    try:
        from modules.working_directory_guard_ru import is_working_directory_guard_command
        return is_working_directory_guard_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "проверь рабочую папку",
            "working directory guard",
            "проверь рабочую директорию",
            "working dir guard",
        }


def _run_working_directory_guard_command_ru_v665b(command):
    from modules.working_directory_guard_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.working_directory_guard_ru",
        "plan": {"tool": "modules.working_directory_guard_ru", "action": "dispatch"},
        "result": result,
    }


def _is_screenshot_capture_policy_command_ru_v665c(command):
    try:
        from modules.screenshot_capture_policy_ru import is_screenshot_capture_policy_command
        return is_screenshot_capture_policy_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "статус скриншотов",
            "status screenshots",
            "screenshot storage status",
            "screenshot status",
            "скриншоты статус",
        }


def _run_screenshot_capture_policy_command_ru_v665c(command):
    from modules.screenshot_capture_policy_ru import dispatch as _scp_dispatch
    result = _scp_dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_capture_policy_ru",
        "plan": {"tool": "modules.screenshot_capture_policy_ru", "action": "dispatch"},
        "result": result,
    }


def _is_confirmed_app_action_command_ru_v669(command):
    try:
        from modules.confirmed_app_actions_ru import is_confirmed_app_action_command
        return is_confirmed_app_action_command(command)
    except Exception:
        return False


def _run_confirmed_app_action_command_ru_v669(command):
    from modules.confirmed_app_actions_ru import run_confirmed_app_action
    return run_confirmed_app_action(command)


def _is_plain_app_goal_ru_v669(command):
    try:
        from modules.confirmed_app_actions_ru import is_plain_app_goal
        return is_plain_app_goal(command)
    except Exception:
        return {"is_goal": False}


def _is_direct_allowlisted_app_command_ru_v672(command):
    try:
        from modules.confirmed_app_actions_ru import is_direct_allowlisted_app_command
        return is_direct_allowlisted_app_command(command)
    except Exception:
        return {"is_direct": False}


def _run_direct_allowlisted_app_command_ru_v672(command):
    from modules.confirmed_app_actions_ru import run_direct_allowlisted_app_action
    return run_direct_allowlisted_app_action(command)


def _is_confirmed_desktop_action_command_ru_v665g(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "подтвердить открыть браузер",
        "confirm open browser",
        "подтвердить запустить браузер",
    }


def _run_confirmed_desktop_action_command_ru_v665g(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    action_taken = "unknown"
    if lower in {"подтвердить открыть браузер", "confirm open browser", "подтвердить запустить браузер"}:
        action_taken = "open_browser"
        try:
            import webbrowser
            webbrowser.open("https://www.google.com")
            browser_opened = True
        except Exception as exc:
            browser_opened = False
            action_taken = f"open_browser_failed: {exc}"
    return {
        "mode": "confirmed_desktop_action",
        "route": "confirmed_desktop_actions",
        "real_action": True,
        "action": action_taken,
        "browser_opened": browser_opened,
        "message": (
            "Выполнено: браузер открыт по вашему подтверждению.\n"
            "Действие было разрешено (allowlisted).\n"
            "Никакие другие действия Computer Use не выполнялись.\n"
            "Снимки экрана не создавались."
        ),
        "result": {
            "command": "allowlisted_desktop_action",
            "action": action_taken,
            "browser_opened": browser_opened,
            "note": "Только разрешённые действия. Полный Computer Use не включён.",
        },
    }


def _run_base_panel_chat_command(command):
    text = str(command or "").strip()
    if _is_strict_project_stability_ru_command(text):
        route_name = "strict_project_stability_ru"
        result = _run_strict_project_stability_ru_command(text)
        return {
            "mode": "command",
            "route": route_name,
            "plan": {"tool": "strict_project_stability_ru", "action": "dispatch"},
            "result": result,
        }
    if _is_patch_panel_bridge_command(text):
        return _run_patch_panel_bridge_command(text)
    if _is_computer_use_command_bridge(text):
        return _run_computer_use_command_bridge(text)
    if _is_screenshot_capture_policy_command_ru_v665c(text):
        return _run_screenshot_capture_policy_command_ru_v665c(text)
    if _is_working_directory_guard_command_ru_v665b(text):
        return _run_working_directory_guard_command_ru_v665b(text)
    if _is_confirmed_app_action_command_ru_v669(text):
        return _run_confirmed_app_action_command_ru_v669(text)
    if _is_confirmed_desktop_action_command_ru_v665g(text):
        return _run_confirmed_desktop_action_command_ru_v665g(text)
    direct_app = _is_direct_allowlisted_app_command_ru_v672(text)
    if direct_app.get("is_direct"):
        return _run_direct_allowlisted_app_command_ru_v672(text)
    plain_app_goal = _is_plain_app_goal_ru_v669(text)
    if plain_app_goal.get("is_goal"):
        return {
            "mode": "requires_confirmation",
            "route": "confirmed_app_actions",
            "plan": {"tool": "confirmed_app_actions", "action": "confirm"},
            "result": plain_app_goal["confirmation_message"],
        }
    if _is_plain_desktop_goal(text):
        return {
            "mode": "requires_confirmation",
            "route": "confirmed_desktop_actions",
            "plan": {"tool": "confirmed_desktop_actions", "action": "confirm"},
            "result": f"Требуется подтверждение: {text}? Напиши: подтвердить {text}",
        }
    return {
        "mode": "new_menu_only",
        "route": "premium_task_panel_ru",
        "plan": {"tool": "premium_task_panel_ru", "action": "chat"},
        "result": (
            "Команда не распознана bridge-router. "
            "Для полного Computer Use используй: управляй пк <цель>, pc computer full control simulate <цель>, "
            "pc computer full control status. Для patch workflow: статус, выбрать response <path>, принять патч."
        ),
    }


def format_panel_chat_result(payload):
    result = payload.get("result", "")
    if isinstance(result, dict):
        return _json_safe(result)
    return str(result)


def _launch_patch_panel_passthrough() -> None:
    target = _target_patch_panel()
    if not target.exists():
        raise FileNotFoundError(f"LocalComet_Patch_Panel.py not found: {target}")
    sys.argv = [str(target), *sys.argv[1:]]
    runpy.run_path(str(target), run_name="__main__")


def _launch_new_menu_only() -> None:
    import tkinter as tk
    from modules.premium_task_panel_ru import auto_open_task_panel_if_enabled, open_task_panel

    root = tk.Tk()
    root.withdraw()
    result = open_task_panel(None)
    if isinstance(result, dict) and not result.get("ok", True):
        fallback = auto_open_task_panel_if_enabled(None)
        if isinstance(fallback, dict) and not fallback.get("ok", True):
            raise RuntimeError(str(fallback))
    root.mainloop()


def run_headless_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    source = Path(__file__).read_text(encoding="utf-8", errors="replace")
    notebook_marker = "ttk." + "Notebook"
    command_marker = "Command" + " Center"
    class_marker = "class " + "LocalCometControlPanel"

    add("version marker", f'LOCALCOMET_VERSION = "{LOCALCOMET_VERSION}"' in source, LOCALCOMET_VERSION)
    add("legacy retired marker", "LEGACY_CONTROL_PANEL_RETIRED_RU_V650G" in source, "")
    add("full control marker", "COMPUTER_USE_FULL_CONTROL_MISSION_RU_V651" in source, "")
    add("no legacy notebook ui", notebook_marker not in source, "")
    add("no legacy command center ui", command_marker not in source, "")
    add("no legacy LocalCometControlPanel class", class_marker not in source, "")
    add("patch command bridge marker", "NEW_MENU_PATCH_COMMAND_BRIDGE_RU_V650J" in source, "")

    try:
        bridge_probe = run_panel_chat_command("pc computer full control status")
        result = bridge_probe.get("result") if isinstance(bridge_probe, dict) else {}
        add("computer use full control status route", isinstance(result, dict) and result.get("mode") == "computer_use_full_control_status", bridge_probe)
    except Exception:
        add("computer use full control status route", False, traceback.format_exc())

    try:
        full_probe = run_panel_chat_command("pc computer full control simulate открой блокнот и напиши hello")
        result = full_probe.get("result") if isinstance(full_probe, dict) else {}
        add("computer use full control simulate route", isinstance(result, dict) and result.get("outcome") == "done", result)
    except Exception:
        add("computer use full control simulate route", False, traceback.format_exc())

    try:
        patch_panel = _target_patch_panel()
        add("patch panel fallback exists", patch_panel.exists(), str(patch_panel))
    except Exception:
        add("patch panel fallback exists", False, traceback.format_exc())

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "legacy_control_panel_new_menu_only_self_check",
        "version": LOCALCOMET_VERSION,
        "summary": summary,
        "checks": checks,
    }


def main() -> None:
    if "--self-check" in sys.argv:
        print(_json_safe(run_headless_self_check()))
        return
    if "--patch-panel" in sys.argv:
        _launch_patch_panel_passthrough()
        return
    _launch_new_menu_only()



LOCALCOMET_AGENT_AUTO_TEST_CENTER_RU_V655B = "v6.55b agent automation functional test center repair installed"


# BEGIN v6.56 Professional Panel Capability Audit control bridge
LOCALCOMET_PANEL_CAPABILITY_AUDIT_RU_V656 = "v6.56 panel capability audit bridge installed"


def _is_panel_capability_audit_command_ru_v656(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "pc panel capability audit",
        "pc task panel audit",
        "panel capability audit",
        "аудит панели",
        "аудит меню",
        "статус аудита панели",
        "pc panel capability audit status",
    }


def _run_panel_capability_audit_command_ru_v656(command):
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from modules.panel_capability_audit_ru import dispatch as panel_audit_dispatch

    result = panel_audit_dispatch(command)
    return {
        "mode": "command",
        "route": "panel_capability_audit_ru",
        "plan": {"tool": "panel_capability_audit_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.56 Professional Panel Capability Audit control bridge

PATCH_PANEL_UX_RELIABILITY_CONTROL_BRIDGE_RU_V657 = "v6.57 patch panel UX commands added to control bridge"

# BEGIN v6.58 Developer Velocity Toolkit control bridge
LOCALCOMET_DEVELOPER_VELOCITY_TOOLKIT_RU_V658 = "v6.58 developer velocity toolkit lite installed"


def _is_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {
            "последний сбой",
            "последняя ошибка",
            "события патча",
            "таймлайн патча",
            "статус разработки",
            "статус проекта",
            "debug пакет",
            "собрать debug пакет",
            "first failure",
            "last failure",
            "patch events",
            "patch timeline",
            "green gate",
            "green gate status",
            "debug package",
        }


def _run_developer_velocity_command_ru_v658(command):
    from modules.localcomet_developer_velocity_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "localcomet_developer_velocity_ru",
        "plan": {"tool": "localcomet_developer_velocity_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.58 Developer Velocity Toolkit control bridge

# BEGIN v6.61 Context Pack Generator bridge
LOCALCOMET_CONTEXT_PACK_RU_V661 = "v6.61 context pack generator bridge installed"


def _is_context_pack_command_ru_v661(command):
    try:
        from modules.context_pack_ru import is_context_pack_command
        return is_context_pack_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent context pack", "agent context pack", "context pack"}


def _run_context_pack_command_ru_v661(command):
    from modules.context_pack_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.context_pack_ru",
        "plan": {"tool": "modules.context_pack_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.61 Context Pack Generator bridge

# BEGIN v6.62 Plan Contract Generator bridge
LOCALCOMET_PLAN_CONTRACT_RU_V662 = "v6.62 plan contract generator bridge installed"


def _is_plan_contract_command_ru_v662(command):
    try:
        from modules.plan_contract_ru import is_plan_contract_command
        return is_plan_contract_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent plan contract", "agent plan contract", "plan contract"}


def _run_plan_contract_command_ru_v662(command):
    from modules.plan_contract_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.plan_contract_ru",
        "plan": {"tool": "modules.plan_contract_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.62 Plan Contract Generator bridge

# BEGIN v6.63 Risk Classifier bridge
LOCALCOMET_RISK_CLASSIFIER_RU_V663 = "v6.63 risk classifier bridge installed"


def _is_risk_classifier_command_ru_v663(command):
    try:
        from modules.risk_classifier_ru import is_risk_classifier_command
        return is_risk_classifier_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet agent risk classify", "agent risk classify", "risk classify"}


def _run_risk_classifier_command_ru_v663(command):
    from modules.risk_classifier_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.risk_classifier_ru",
        "plan": {"tool": "modules.risk_classifier_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.63 Risk Classifier bridge

# BEGIN v6.64a Repository Weight Audit bridge
LOCALCOMET_REPO_WEIGHT_AUDIT_RU_V664A = "v6.64a repo weight audit bridge installed"


def _is_repo_weight_audit_command_ru_v664a(command):
    try:
        from modules.repo_weight_audit_ru import is_repo_weight_audit_command
        return is_repo_weight_audit_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet repo weight audit", "repo weight audit", "repo weight"}


def _run_repo_weight_audit_command_ru_v664a(command):
    from modules.repo_weight_audit_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.repo_weight_audit_ru",
        "plan": {"tool": "modules.repo_weight_audit_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64a Repository Weight Audit bridge

# BEGIN v6.64b Storage Cleanup Plan bridge
LOCALCOMET_STORAGE_CLEANUP_PLAN_RU_V664B = "v6.64b storage cleanup plan bridge installed"


def _is_storage_cleanup_plan_command_ru_v664b(command):
    try:
        from modules.storage_cleanup_plan_ru import is_storage_cleanup_plan_command
        return is_storage_cleanup_plan_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet storage cleanup plan", "storage cleanup plan", "cleanup plan"}


def _run_storage_cleanup_plan_command_ru_v664b(command):
    from modules.storage_cleanup_plan_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.storage_cleanup_plan_ru",
        "plan": {"tool": "modules.storage_cleanup_plan_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64b Storage Cleanup Plan bridge

# BEGIN v6.64c Screenshot Retention Dry Run bridge
LOCALCOMET_SCREENSHOT_RETENTION_DRY_RUN_RU_V664C = "v6.64c screenshot retention dry run bridge installed"


def _is_screenshot_retention_dry_run_command_ru_v664c(command):
    try:
        from modules.screenshot_retention_dry_run_ru import is_screenshot_retention_dry_run_command
        return is_screenshot_retention_dry_run_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots retention dry run", "screenshots retention dry run", "screenshot dry run"}


def _run_screenshot_retention_dry_run_command_ru_v664c(command):
    from modules.screenshot_retention_dry_run_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_retention_dry_run_ru",
        "plan": {"tool": "modules.screenshot_retention_dry_run_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64c Screenshot Retention Dry Run bridge

# BEGIN v6.64d Screenshot Storage Policy Simulator RU bridge


def _is_screenshot_storage_policy_simulator_command_ru_v664d(command):
    try:
        from modules.screenshot_storage_policy_simulator_ru import is_screenshot_storage_policy_simulator_command
        return is_screenshot_storage_policy_simulator_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots storage policy simulate", "screenshots storage policy simulate", "storage policy simulate"}


def _run_screenshot_storage_policy_simulator_command_ru_v664d(command):
    from modules.screenshot_storage_policy_simulator_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_storage_policy_simulator_ru",
        "plan": {"tool": "modules.screenshot_storage_policy_simulator_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64d Screenshot Storage Policy Simulator RU bridge

# BEGIN v6.64e Screenshot Retention Policy Config RU bridge


def _is_screenshot_retention_policy_config_command_ru_v664e(command):
    try:
        from modules.screenshot_retention_policy_config_ru import is_screenshot_retention_policy_config_command
        return is_screenshot_retention_policy_config_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"localcomet screenshots retention policy write", "screenshots retention policy write", "retention policy write"}


def _run_screenshot_retention_policy_config_command_ru_v664e(command):
    from modules.screenshot_retention_policy_config_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.screenshot_retention_policy_config_ru",
        "plan": {"tool": "modules.screenshot_retention_policy_config_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.64e Screenshot Retention Policy Config RU bridge

# BEGIN v6.67 Task Contract Registry RU bridge


def _is_task_contract_registry_command_ru_v667(command):
    try:
        from modules.task_contract_registry_ru import _match_registry_command
        return _match_registry_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"task contract registry", "реестр контрактов задач"} or lower.startswith("контракт команды ") or lower.startswith("contract for ")


def _run_task_contract_registry_command_ru_v667(command):
    from modules.task_contract_registry_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.task_contract_registry_ru",
        "plan": {"tool": "modules.task_contract_registry_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.67 Task Contract Registry RU bridge

# BEGIN v6.68 App Harness Registry RU bridge


def _is_app_harness_registry_command_ru_v668(command):
    try:
        from modules.app_harness_registry_ru import _match_app_harness_command
        return _match_app_harness_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"app harness status", "app harness registry", "реестр приложений", "app registry"} or lower.startswith("app harness plan ") or lower.startswith("план запуска ")


def _run_app_harness_registry_command_ru_v668(command):
    from modules.app_harness_registry_ru import dispatch
    result = dispatch(command)
    return {
        "mode": "command",
        "route": "modules.app_harness_registry_ru",
        "plan": {"tool": "modules.app_harness_registry_ru", "action": "dispatch"},
        "result": result,
    }


# END v6.68 App Harness Registry RU bridge

# BEGIN v6.76a MINIMAL ROUTER BRIDGES
LOCALCOMET_DEVELOPMENT_SAFETY_BRIDGE_RU_V676A = (
    "v6.76a development safety orchestrator bridge installed"
)
LOCALCOMET_REVIEWER_BRIDGE_RU_V676A = (
    "v6.76a reviewer bridge installed"
)


def _normalize_v676a_command(command):
    return str(command or "").strip().lower().replace("ё", "е")


def _is_development_safety_command_ru_v676a(command):
    lower = _normalize_v676a_command(command)
    return lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
        "report",
        "pc dev safety report",
        "preflight audit",
        "pc preflight audit",
        "diff limit status",
        "pc diff limit status",
        "opencode recovery status",
        "pc opencode recovery status",
    }


def _run_development_safety_command_ru_v676a(command):
    try:
        from modules.development_safety_orchestrator_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "development_safety_orchestrator_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "mode": "command",
        "route": "modules.development_safety_orchestrator_ru",
        "plan": {
            "tool": "modules.development_safety_orchestrator_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_reviewer_bridge_command_ru_v676a(command):
    lower = _normalize_v676a_command(command)
    return (
        lower in {
            "status",
            "reviewer bridge status",
            "статус ревью",
            "pc reviewer bridge status",
            "report",
            "reviewer bridge report",
            "pc reviewer bridge report",
        }
        or lower == "создай запрос ревью"
        or lower.startswith("создай запрос ревью ")
        or lower == "reviewer bridge create"
        or lower.startswith("reviewer bridge create ")
    )


def _run_reviewer_bridge_command_ru_v676a(command):
    try:
        from modules.reviewer_bridge_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "reviewer_bridge_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "mode": "command",
        "route": "modules.reviewer_bridge_ru",
        "plan": {
            "tool": "modules.reviewer_bridge_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_maintenance_diagnostics_command_ru_v681(command):
    try:
        from modules.maintenance_diagnostics_ru import is_diagnostics_command
        return is_diagnostics_command(command)
    except Exception:
        lower = _normalize_v676a_command(command)
        return lower in {
            "диагностика проекта",
            "project diagnostics",
            "maintenance status",
        }


def _run_maintenance_diagnostics_command_ru_v681(command):
    try:
        from modules.maintenance_diagnostics_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "maintenance_diagnostics_error",
            "version": "v6.81",
            "warnings": [f"maintenance_diagnostics_error:{type(exc).__name__}"],
        }
    return {
        "mode": "command",
        "route": "modules.maintenance_diagnostics_ru",
        "plan": {
            "tool": "modules.maintenance_diagnostics_ru",
            "action": "dispatch",
        },
        "result": result,
    }


def _is_task_planner_command_ru_v682(command):
    try:
        from modules.task_planner_orchestrator_ru import is_task_plan_command
        return is_task_plan_command(command)
    except Exception:
        lower = _normalize_v676a_command(command)
        return (
            lower.startswith("спланируй задачу ")
            or lower.startswith("план задачи ")
            or lower.startswith("task plan ")
        )


def _run_task_planner_command_ru_v682(command):
    try:
        from modules.task_planner_orchestrator_ru import dispatch
        result = dispatch(command)
    except Exception as exc:
        result = {
            "ok": False,
            "mode": "explainable_task_plan",
            "version": "v6.82",
            "warnings": [f"task_planner_error:{type(exc).__name__}"],
        }
    return {
        "mode": "command",
        "route": "modules.task_planner_orchestrator_ru",
        "plan": {
            "tool": "modules.task_planner_orchestrator_ru",
            "action": "dispatch",
        },
        "result": result,
    }


PANEL_ROUTES = (
    (
        "development_safety_ru_v676a",
        _is_development_safety_command_ru_v676a,
        "_run_development_safety_command_ru_v676a",
    ),
    (
        "reviewer_bridge_ru_v676a",
        _is_reviewer_bridge_command_ru_v676a,
        "_run_reviewer_bridge_command_ru_v676a",
    ),
    (
        "maintenance_diagnostics_ru_v681",
        _is_maintenance_diagnostics_command_ru_v681,
        "_run_maintenance_diagnostics_command_ru_v681",
    ),
    (
        "task_planner_orchestrator_ru_v682",
        _is_task_planner_command_ru_v682,
        "_run_task_planner_command_ru_v682",
    ),
    (
        "app_harness_registry_ru_v668",
        _is_app_harness_registry_command_ru_v668,
        "_run_app_harness_registry_command_ru_v668",
    ),
    (
        "task_contract_registry_ru_v667",
        _is_task_contract_registry_command_ru_v667,
        "_run_task_contract_registry_command_ru_v667",
    ),
    (
        "screenshot_retention_policy_config_ru_v664e",
        _is_screenshot_retention_policy_config_command_ru_v664e,
        "_run_screenshot_retention_policy_config_command_ru_v664e",
    ),
    (
        "screenshot_storage_policy_simulator_ru_v664d",
        _is_screenshot_storage_policy_simulator_command_ru_v664d,
        "_run_screenshot_storage_policy_simulator_command_ru_v664d",
    ),
    (
        "screenshot_retention_dry_run_ru_v664c",
        _is_screenshot_retention_dry_run_command_ru_v664c,
        "_run_screenshot_retention_dry_run_command_ru_v664c",
    ),
    (
        "storage_cleanup_plan_ru_v664b",
        _is_storage_cleanup_plan_command_ru_v664b,
        "_run_storage_cleanup_plan_command_ru_v664b",
    ),
    (
        "repo_weight_audit_ru_v664a",
        _is_repo_weight_audit_command_ru_v664a,
        "_run_repo_weight_audit_command_ru_v664a",
    ),
    (
        "risk_classifier_ru_v663",
        _is_risk_classifier_command_ru_v663,
        "_run_risk_classifier_command_ru_v663",
    ),
    (
        "plan_contract_ru_v662",
        _is_plan_contract_command_ru_v662,
        "_run_plan_contract_command_ru_v662",
    ),
    (
        "context_pack_ru_v661",
        _is_context_pack_command_ru_v661,
        "_run_context_pack_command_ru_v661",
    ),
    (
        "developer_velocity_ru_v658",
        _is_developer_velocity_command_ru_v658,
        "_run_developer_velocity_command_ru_v658",
    ),
    (
        "panel_capability_audit_ru_v656",
        _is_panel_capability_audit_command_ru_v656,
        "_run_panel_capability_audit_command_ru_v656",
    ),
)


_run_panel_chat_command_before_v676a_minimal = _run_base_panel_chat_command


def run_panel_chat_command(command):
    text = str(command or "").strip()
    for _route_name, matcher, handler_name in PANEL_ROUTES:
        if matcher(text):
            handler = globals()[handler_name]
            return handler(text)
    return _run_panel_chat_command_before_v676a_minimal(command)


# END v6.76a MINIMAL ROUTER BRIDGES


if __name__ == "__main__":
    main()
````

### ПУТЬ: LocalComet_Patch_Panel.py (667 строк, 28677 байт)

````python
from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional, Tuple


PATCH_PANEL_VERSION = "v6.58"
PATCH_PANEL_NAME = "Patch Panel UX Reliability + Developer Velocity Service RU"
PATCH_PANEL_RETIRED_SERVICE_VERSION = "v6.52b"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent

PROJECTS_DIR = ROOT_DIR / "Projects"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REPORTS_DIR = PROJECTS_DIR / "Reports"
LOGS_DIR = PROJECTS_DIR / "Logs"
RESPONSE_FILE = RELAY_DIR / "response.json"
BAD_RESPONSE_FILE = RELAY_DIR / "bad_response.json"
SELECTED_RESPONSE_SOURCE_FILE = RELAY_DIR / "selected_response_source.txt"
USER_DOWNLOADS_DIR = Path.home() / "Downloads"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value: Any, limit: int = 3500) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[trimmed]"


def _ensure_project_import_path() -> None:
    root_text = str(ROOT_DIR)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _fresh_import(module_name: str):
    _ensure_project_import_path()
    importlib.invalidate_caches()
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _read_text(path: Path, default: str = "") -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return default
    return default


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")


def _copy_file_bytes(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def validate_response_payload(payload: Any) -> Tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "response.json должен быть JSON object."
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False, "response.json должен содержать непустую строку summary."
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        return False, "response.json должен содержать непустой список operations."
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            return False, f"operation #{index} не является object."
        if "type" not in operation:
            return False, f"operation #{index} должен использовать ключ type."
        if "op" in operation:
            return False, f"operation #{index} использует запрещенный ключ op."
        if operation.get("type") not in {"create", "replace", "append", "delete"}:
            return False, f"operation #{index} имеет неизвестный type: {operation.get('type')}"
        if not isinstance(operation.get("path"), str) or not operation.get("path", "").strip():
            return False, f"operation #{index} должен содержать path."
    tests = payload.get("tests")
    if not isinstance(tests, list) or not tests:
        return False, "response.json должен содержать непустой список tests."
    return True, "OK"


def _load_response_payload(path: Path) -> Tuple[bool, str, Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return False, f"Файл response не найден: {path}", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception as exc:
        return False, f"Не удалось прочитать JSON: {exc}", {}
    ok, reason = validate_response_payload(payload)
    if not ok:
        return False, reason, payload if isinstance(payload, dict) else {}
    return True, "OK", payload


def _response_candidates_from_downloads() -> List[Path]:
    if not USER_DOWNLOADS_DIR.exists():
        return []
    candidates = [
        path for path in USER_DOWNLOADS_DIR.glob("response*.json")
        if path.is_file() and path.resolve() != RESPONSE_FILE.resolve()
    ]
    unique: Dict[str, Path] = {}
    for path in candidates:
        try:
            unique[str(path.resolve())] = path
        except Exception:
            continue
    return sorted(unique.values(), key=lambda item: item.stat().st_mtime, reverse=True)


def _selected_response_source() -> Optional[Path]:
    text = _read_text(SELECTED_RESPONSE_SOURCE_FILE).strip()
    if not text:
        return None
    try:
        path = Path(text)
    except Exception:
        return None
    try:
        if path.exists() and path.is_file() and path.resolve() != RESPONSE_FILE.resolve():
            return path
    except Exception:
        return None
    return None


def find_latest_response_file() -> Optional[Path]:
    selected = _selected_response_source()
    if selected is not None:
        return selected
    candidates = _response_candidates_from_downloads()
    return candidates[0] if candidates else None


def reset_selected_response_source_text() -> str:
    _write_text(SELECTED_RESPONSE_SOURCE_FILE, "")
    return "OK: выбранный response сброшен."


def import_specific_response_text(source: Path) -> str:
    source = Path(source)
    ok, reason, payload = _load_response_payload(source)
    if not ok:
        _write_text(BAD_RESPONSE_FILE, f"{source}\n\n{reason}\n\n{_short(payload)}")
        return (
            "STOP: выбранный response*.json не прошел локальную проверку.\n"
            f"Файл: {source}\n"
            f"Причина: {reason}\n"
            f"bad_response: {BAD_RESPONSE_FILE}"
        )
    _copy_file_bytes(source, RESPONSE_FILE)
    _write_text(SELECTED_RESPONSE_SOURCE_FILE, str(source))
    return (
        "OK: response.json импортирован.\n"
        f"Источник: {source}\n"
        f"Цель: {RESPONSE_FILE}\n"
        f"Summary: {payload.get('summary')}\n"
        f"Операций: {len(payload.get('operations', []))}\n"
        f"Тестов: {len(payload.get('tests', []))}"
    )


def import_latest_response_text() -> str:
    latest = find_latest_response_file()
    if latest is None:
        return (
            "STOP: не найден новый response*.json.\n"
            "Активный Projects/ChatGPTRelay/response.json не используется как источник, "
            "чтобы не переустановить старый patch.\n"
            f"Downloads: {USER_DOWNLOADS_DIR}\n"
            "Используй команду 'выбрать response C:\\path\\response.json'."
        )
    return import_specific_response_text(latest)


def validate_output_is_success(text: str) -> bool:
    lower = str(text or "").lower()
    success_markers = ["relay response: ✅ проверка пройдена", "✅ проверка пройдена", "проверка пройдена"]
    hard_fail_markers = [
        "relay response: ❌",
        "json parse error",
        "нет списка operations",
        "operations missing",
        "операций: 0",
        "stop:",
        "traceback",
        "assertionerror",
    ]
    return any(marker in lower for marker in success_markers) and not any(marker in lower for marker in hard_fail_markers)


def _code_lines_are_zero(text: str) -> bool:
    found_code = False
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().lower()
        if not line.startswith("code:"):
            continue
        found_code = True
        value = line.split(":", 1)[1].strip()
        if value not in {"0", "0.0"}:
            return False
    return True if found_code else True


def apply_output_is_success(text: str) -> bool:
    raw = str(text or "")
    lower = raw.lower()
    success_markers = ["patch успешно применен", "patch registry:"]
    hard_fail_markers = [
        "ошибка применения patch",
        "изменения откачены",
        "patch применен, но тесты упали",
        "patch не применен",
        "relay response не импортирован",
        "traceback",
        "assertionerror",
    ]
    if any(marker in lower for marker in hard_fail_markers):
        return False
    if not _code_lines_are_zero(raw):
        return False
    return any(marker in lower for marker in success_markers)


def _format_json_compact(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=True, indent=2)
    except Exception:
        return str(payload)


def validate_relay_response_text() -> str:
    agent = _fresh_import("agents.chatgpt_relay_agent")
    return str(agent.handle("validate_response", {}))


def apply_relay_response_text() -> str:
    agent = _fresh_import("agents.chatgpt_relay_agent")
    return str(agent.handle("apply_response", {}))


def after_patch_text() -> str:
    agent = _fresh_import("agents.automation_agent")
    return str(agent.handle("after_patch", {}))


def run_project_checks_text() -> str:
    lines: List[str] = []
    try:
        center = _fresh_import("modules.localcomet_functional_test_center_ru")
        result = center.run_full_suite(write_report=True)
        lines.append("--- FUNCTIONAL TEST CENTER ---")
        lines.append(_format_json_compact({
            "ok": result.get("ok"),
            "mode": result.get("mode"),
            "version": result.get("version"),
            "summary": result.get("summary"),
            "report": result.get("report"),
        }))
        if not result.get("ok"):
            lines.append("STOP: functional test center не green.")
            return "\n".join(lines)
    except Exception:
        lines.append("--- FUNCTIONAL TEST CENTER ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: functional test center завершился исключением.")
        return "\n".join(lines)

    try:
        core = _fresh_import("modules.computer_use_core_ru")
        contracts = core.dispatch("pc computer contracts")
        lines.append("\n--- COMPUTER USE CONTRACTS ---")
        lines.append(_format_json_compact({
            "ok": contracts.get("ok"),
            "mode": contracts.get("mode"),
            "summary": contracts.get("summary"),
            "report": contracts.get("report"),
        }))
        if not contracts.get("ok") or contracts.get("summary", {}).get("failed", 0) != 0:
            lines.append("STOP: pc computer contracts не прошли.")
            return "\n".join(lines)
    except Exception:
        lines.append("\n--- COMPUTER USE CONTRACTS ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: computer use contracts завершились исключением.")
        return "\n".join(lines)

    try:
        strict = _fresh_import("modules.strict_project_stability_ru")
        strict_result = strict.dispatch("проверь проект")
        lines.append("\n--- STRICT PROJECT STABILITY ---")
        lines.append(_format_json_compact({
            "ok": strict_result.get("ok"),
            "score": strict_result.get("score"),
            "summary": strict_result.get("summary"),
            "report": strict_result.get("report"),
        }))
        summary = strict_result.get("summary", {})
        if not strict_result.get("ok") or summary.get("hard_failures", 1) != 0 or summary.get("warnings", 1) != 0:
            lines.append("STOP: strict_project_stability не прошел zero-warning gate.")
            return "\n".join(lines)
    except Exception:
        lines.append("\n--- STRICT PROJECT STABILITY ---")
        lines.append(traceback.format_exc())
        lines.append("STOP: strict_project_stability завершился исключением.")
        return "\n".join(lines)

    lines.append("\nOK: проект проверен. functional/contracts/strict green.")
    return "\n".join(lines)


def import_validate_apply_check_text() -> str:
    lines: List[str] = [f"LocalComet retired Patch Panel service {PATCH_PANEL_VERSION}", f"started_at: {_now()}"]
    import_result = import_latest_response_text()
    lines.append("\n--- IMPORT ---")
    lines.append(import_result)
    if not import_result.lstrip().startswith("OK:"):
        lines.append("\nSTOP: импорт response не прошел.")
        return "\n".join(lines)

    validate_result = validate_relay_response_text()
    lines.append("\n--- VALIDATE ---")
    lines.append(validate_result)
    if not validate_output_is_success(validate_result):
        lines.append("\nSTOP: relay validate не прошел. patch не применялся.")
        return "\n".join(lines)

    apply_result = apply_relay_response_text()
    lines.append("\n--- APPLY ---")
    lines.append(apply_result)
    if not apply_output_is_success(apply_result):
        lines.append("\nSTOP: apply не прошел. after patch и проверки не запущены.")
        return "\n".join(lines)

    try:
        after_result = after_patch_text()
    except Exception:
        after_result = traceback.format_exc()
    lines.append("\n--- AFTER PATCH ---")
    lines.append(after_result)

    checks_result = run_project_checks_text()
    lines.append("\n--- VERIFY ---")
    lines.append(checks_result)
    if "STOP:" in checks_result:
        lines.append("\nSTOP: patch применен, но проверки проекта не green.")
    else:
        lines.append("\nOK: patch принят и проверен через новое меню/backend service.")
    return "\n".join(lines)


def refresh_status_snapshot() -> str:
    lines: List[str] = [
        f"Patch backend service: {PATCH_PANEL_VERSION} - retired GUI",
        f"Project: {ROOT_DIR}",
        f"Relay response: {RESPONSE_FILE}",
        f"Downloads: {USER_DOWNLOADS_DIR}",
        f"updated_at: {_now()}",
    ]
    selected = _selected_response_source()
    latest = _response_candidates_from_downloads()[0] if _response_candidates_from_downloads() else None
    lines.append(f"selected response source: {selected if selected else 'нет'}")
    lines.append(f"latest Downloads response: {latest if latest else 'нет'}")
    if RESPONSE_FILE.exists():
        ok, reason, payload = _load_response_payload(RESPONSE_FILE)
        lines.append(f"active relay response.json: {'ok' if ok else 'bad'}")
        if ok:
            lines.append(f"active response summary: {_short(payload.get('summary'), 500)}")
            lines.append(f"operations: {len(payload.get('operations', []))}")
            lines.append(f"tests: {len(payload.get('tests', []))}")
        else:
            lines.append(f"active response reason: {reason}")
    else:
        lines.append("active relay response.json: отсутствует")
    try:
        project_paths = _fresh_import("modules.project_paths")
        status = project_paths.status()
        lines.append(f"project_paths: {status.get('version')} ok={status.get('ok')}")
    except Exception:
        lines.append("project_paths: ошибка")
        lines.append(_short(traceback.format_exc(), 1000))
    try:
        patch_registry = _fresh_import("modules.patch_registry")
        latest_patch = patch_registry.get_latest_patch()
        lines.append(f"latest registry version: {latest_patch.get('version') or 'нет'}")
        lines.append(f"latest registry status: {latest_patch.get('status') or 'нет'}")
    except Exception:
        lines.append("patch registry: ошибка")
        lines.append(_short(traceback.format_exc(), 1000))
    return "\n".join(lines)


def open_path(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(str(path))
        return f"Открыто: {path}"
    return f"Папка существует: {path}"


def retired_notice_text() -> str:
    return (
        "LocalComet Patch Panel GUI retired.\n"
        "Используй новое меню LocalComet Computer Use Core RU.\n"
        "Команды patch/test теперь доступны прямо в новом меню: выбрать patch, принять патч, тест."
    )


def run_headless_self_check() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    sample_patch = {
        "summary": "vX sample",
        "operations": [{"type": "create", "path": "tools/install_sample.py", "content": "print('ok')"}],
        "tests": ["python tools\\install_sample.py"],
    }
    ok, reason = validate_response_payload(sample_patch)
    add("response schema accepts valid patch", ok, reason)

    bad_patch = {"summary": "bad", "operations": [{"op": "create", "path": "x.py"}], "tests": ["python x.py"]}
    ok, reason = validate_response_payload(bad_patch)
    add("response schema rejects op key", not ok and "op" in reason, reason)

    success_text = "Patch успешно применен.\nPatch Registry: v6.52b записан\nSTDOUT:\n{\"failed\": 0}\nCODE: 0\n"
    add("apply detector accepts failed zero summaries", apply_output_is_success(success_text), success_text)

    failure_text = "Ошибка применения patch. Изменения ОТКАЧЕНЫ.\nCODE: 0\n"
    add("apply detector rejects rollback failure", not apply_output_is_success(failure_text), failure_text)

    nonzero_text = "Patch успешно применен.\nPatch Registry: v6.52b записан\nCODE: 1\n"
    add("apply detector rejects nonzero code", not apply_output_is_success(nonzero_text), nonzero_text)

    add("status snapshot returns text", "Project:" in refresh_status_snapshot(), "")
    add("retired notice mentions new menu", "новое меню" in retired_notice_text().lower(), "")

    source_text = _read_text(Path(__file__).resolve())
    add("no PatchPanelApp class", ("class " + "PatchPanelApp") not in source_text, "")
    add("no tkinter GUI in retired service", ("import " + "tkinter") not in source_text and ("tk." + "Tk") not in source_text, "")

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "retired_patch_panel_service_self_check",
        "version": PATCH_PANEL_VERSION,
        "summary": summary,
        "checks": checks,
    }


def _launch_new_menu() -> None:
    target = ROOT_DIR / "LocalComet_Control_Panel.py"
    if target.exists():
        os.execv(sys.executable, [sys.executable, str(target)])
    print(retired_notice_text())


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        result = run_headless_self_check()
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        raise SystemExit(0 if result.get("ok") else 1)
    if "--status" in sys.argv:
        print(refresh_status_snapshot())
        raise SystemExit(0)
    _launch_new_menu()

# BEGIN v6.57 Patch Panel UX Reliability backend bridge
PATCH_PANEL_UX_RELIABILITY_RU_V657 = "v6.57 patch panel UX reliability backend bridge installed"

try:
    _patch_panel_import_validate_apply_check_text_before_ux_ru_v657
except NameError:
    _patch_panel_import_validate_apply_check_text_before_ux_ru_v657 = import_validate_apply_check_text

try:
    _patch_panel_refresh_status_snapshot_before_ux_ru_v657
except NameError:
    _patch_panel_refresh_status_snapshot_before_ux_ru_v657 = refresh_status_snapshot

try:
    _patch_panel_run_headless_self_check_before_ux_ru_v657
except NameError:
    _patch_panel_run_headless_self_check_before_ux_ru_v657 = run_headless_self_check


def _patch_panel_ux_ru_v657():
    import importlib
    return importlib.import_module("modules.patch_panel_ux_reliability_ru")


def import_validate_apply_check_text() -> str:
    raw_text = str(_patch_panel_import_validate_apply_check_text_before_ux_ru_v657())
    try:
        ux = _patch_panel_ux_ru_v657()
        classification = ux.classify_and_report(raw_text)
        return str(classification.get("final_summary") or "") + "\n" + raw_text
    except Exception:
        return (
            "=== PATCH UX FINAL SUMMARY v6.57 ===\n"
            "❌ Ошибка formatter-а итогового статуса. Raw log сохранен ниже.\n"
            "Статус: ERROR\n"
            "Версия: v6.57\n"
            "Тесты: неизвестно\n"
            "Rollback: проверь raw log\n"
            "=== RAW LOG BELOW ===\n"
            + raw_text
        )


def refresh_status_snapshot() -> str:
    base = str(_patch_panel_refresh_status_snapshot_before_ux_ru_v657())
    try:
        ux = _patch_panel_ux_ru_v657()
        status = ux.dispatch("patch ux status")
        return base + "\npatch_panel_ux: " + json.dumps(status, ensure_ascii=True, sort_keys=True)
    except Exception as exc:
        return base + "\npatch_panel_ux: error " + str(exc)


def run_patch_panel_chat_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"статус патча", "patch status", "patch ux status", "статус patch ux"}:
        return refresh_status_snapshot()
    if lower in {"принять патч", "прими патч", "применить патч", "apply", "accept", "apply patch"}:
        return import_validate_apply_check_text()
    if lower in {"тест", "проверить проект", "проверь проект", "verify", "checks", "проверки"}:
        return run_project_checks_text()
    if lower in {"открыть reports", "reports", "open reports", "открыть отчеты", "открыть последний отчет", "open last report"}:
        try:
            ux = _patch_panel_ux_ru_v657()
            report = Path(ux._reports_dir() / "latest_patch_panel_ux_report.md")
            if report.exists() and hasattr(os, "startfile"):
                os.startfile(str(report))
                return f"Открыт последний UX отчет: {report}"
        except Exception:
            pass
        return open_path(REPORTS_DIR)
    if lower in {"открыть relay", "relay", "open relay"}:
        return open_path(RELAY_DIR)
    if lower in {"копировать итог", "copy summary", "copy final summary"}:
        try:
            ux = _patch_panel_ux_ru_v657()
            report = Path(ux._reports_dir() / "latest_patch_panel_ux_report.json")
            if report.exists():
                payload = json.loads(report.read_text(encoding="utf-8"))
                return str(payload.get("final_summary") or payload)
        except Exception as exc:
            return "STOP: не удалось прочитать итог patch UX: " + str(exc)
        return "Patch UX итог еще не найден."
    if lower.startswith(("выбрать response ", "выбери response ", "select response ", "choose response ", "response ", "source ")):
        parts = str(command).split(" ", 2)
        path_text = parts[2].strip() if len(parts) >= 3 else ""
        if lower.startswith(("response ", "source ")):
            path_text = str(command).split(" ", 1)[1].strip()
        return import_specific_response_text(Path(path_text))
    if lower in {"help", "помощь", "команды", "что умеешь", "?"}:
        return (
            "Patch Panel UX v6.57 команды:\n"
            "- выбрать response <path>\n"
            "- принять патч\n"
            "- тест\n"
            "- статус патча\n"
            "- открыть последний отчет\n"
            "- копировать итог\n"
            "- открыть relay\n"
            "- открыть reports"
        )
    return "STOP: неизвестная patch-panel команда v6.57: " + str(command)


def run_headless_self_check() -> Dict[str, Any]:
    base = _patch_panel_run_headless_self_check_before_ux_ru_v657()
    checks = list(base.get("checks", [])) if isinstance(base, dict) else []
    try:
        ux = _patch_panel_ux_ru_v657()
        ux_result = ux.run_self_check()
        checks.append({"name": "patch panel ux reliability self check", "ok": bool(ux_result.get("ok")), "details": ux_result})
        success_sample = "Patch успешно применен.\nPatch Registry: v6.57 записан\nCODE: 0\nOK: проект проверен. functional/contracts/strict green."
        checks.append({"name": "patch panel ux success summary is green", "ok": ux.classify_patch_workflow_text(success_sample).get("color") == "success", "details": ""})
        rollback_sample = "Patch применен, но тесты упали. Изменения ОТКАЧЕНЫ.\nCODE: 1"
        checks.append({"name": "patch panel ux rollback summary is red", "ok": ux.classify_patch_workflow_text(rollback_sample).get("status") == "ROLLED_BACK_TESTS_FAILED", "details": ""})
    except Exception:
        checks.append({"name": "patch panel ux reliability self check", "ok": False, "details": traceback.format_exc()})
    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    return {
        "ok": summary["failed"] == 0,
        "mode": "retired_patch_panel_service_self_check",
        "version": "v6.57",
        "summary": summary,
        "checks": checks,
    }
# END v6.57 Patch Panel UX Reliability backend bridge

# BEGIN v6.58 Developer Velocity Toolkit patch panel bridge
PATCH_PANEL_DEVELOPER_VELOCITY_BRIDGE_RU_V658 = "v6.58 developer velocity patch panel commands installed"


def _is_patch_panel_developer_velocity_command_ru_v658(command):
    try:
        from modules.localcomet_developer_velocity_ru import is_developer_velocity_command
        return is_developer_velocity_command(command)
    except Exception:
        lower = str(command or "").strip().lower().replace("ё", "е")
        return lower in {"последний сбой", "события патча", "статус разработки", "debug пакет"}


def _run_patch_panel_developer_velocity_command_ru_v658(command):
    from modules.localcomet_developer_velocity_ru import dispatch
    return dispatch(command)


try:
    _run_patch_panel_chat_command_before_developer_velocity_ru_v658
except NameError:
    _run_patch_panel_chat_command_before_developer_velocity_ru_v658 = run_patch_panel_chat_command


def run_patch_panel_chat_command(command):
    text = str(command or "").strip()
    if _is_patch_panel_developer_velocity_command_ru_v658(text):
        return _run_patch_panel_developer_velocity_command_ru_v658(text)
    if text.lower().replace("ё", "е") in {"help", "помощь", "команды", "что умеешь", "?"}:
        base = _run_patch_panel_chat_command_before_developer_velocity_ru_v658(command)
        return str(base) + "\n\nDeveloper Velocity v6.58:\n- последний сбой\n- события патча\n- статус разработки\n- debug пакет"
    return _run_patch_panel_chat_command_before_developer_velocity_ru_v658(command)

# END v6.58 Developer Velocity Toolkit patch panel bridge





````

### ПУТЬ: localcomet_runtime_manifest.json (237 строк, 8791 байт)

````json
{
  "entrypoints": [
    "app.py",
    "config.py",
    "GenerateCapabilityMap.py",
    "LocalComet_Control_Panel.py",
    "next/app_v5.py"
  ],
  "runtime": [
    "agents/automation_agent.py",
    "agents/browser_agent.py",
    "agents/chatgpt_relay_agent.py",
    "agents/code_agent.py",
    "agents/diagnostics_agent.py",
    "agents/file_agent.py",
    "agents/gpt_agent.py",
    "agents/gpt_browser_agent.py",
    "agents/history_agent.py",
    "agents/maintenance_agent.py",
    "agents/operator_agent.py",
    "agents/project_agent.py",
    "agents/research_agent.py",
    "agents/self_edit_agent.py",
    "agents/stability_agent.py",
    "agents/system_agent.py",
    "agents/windows_agent.py",
    "agents/workspace_agent.py",
    "core/executor.py",
    "core/llm.py",
    "core/loop.py",
    "core/planner.py",
    "core/project_context.py",
    "core/router.py",
    "core/state.py",
    "next/goal_manager.py",
    "next/observer.py",
    "next/task_planner.py",
    "next/task_queue.py"
  ],
  "lazy_runtime": [
    "modules/agent_onboarding_demo.py",
    "modules/agentos_kernel_blueprint.py",
    "modules/agents_project_intelligence.py",
    "modules/ai_agent_core_ru.py",
    "modules/ai_agent_memory_ru.py",
    "modules/ai_patch_planner_ru.py",
    "modules/ai_project_map_ru.py",
    "modules/app_harness_registry_ru.py",
    "modules/auto_verification.py",
    "modules/automation_center.py",
    "modules/autonomous_action_executor_ru.py",
    "modules/autonomous_run_state_ru.py",
    "modules/autonomy_policy_ru.py",
    "modules/browser.py",
    "modules/browser_actions.py",
    "modules/browser_autopilot.py",
    "modules/browser_direct.py",
    "modules/browser_harness_ru.py",
    "modules/browser_operator.py",
    "modules/browser_profile_ignore.py",
    "modules/browser_super.py",
    "modules/browser_task_runner.py",
    "modules/chatgpt_desktop_bridge.py",
    "modules/chatgpt_relay.py",
    "modules/codegen.py",
    "modules/codex_agent_mode_ru.py",
    "modules/codex_bridge.py",
    "modules/codex_connector.py",
    "modules/command_center_ui.py",
    "modules/command_explorer_ru.py",
    "modules/computer_use_agent_mission_ru.py",
    "modules/computer_use_auto_action_ru.py",
    "modules/computer_use_click_planner_ru.py",
    "modules/computer_use_contract_tests_ru.py",
    "modules/computer_use_core_ru.py",
    "modules/computer_use_focus_guard_ru.py",
    "modules/computer_use_full_control_mission_ru.py",
    "modules/computer_use_grounding_ru.py",
    "modules/computer_use_loop_ru.py",
    "modules/computer_use_multistep_loop_ru.py",
    "modules/computer_use_observe_vision_ru.py",
    "modules/computer_use_real_actions_ru.py",
    "modules/computer_use_safety_ru.py",
    "modules/computer_use_schema_ru.py",
    "modules/computer_use_screen_diff_ru.py",
    "modules/computer_use_test_fixtures_ru.py",
    "modules/computer_use_trace_ru.py",
    "modules/computer_use_type_guard_ru.py",
    "modules/computer_use_visual_guard_ru.py",
    "modules/confirmed_app_actions_ru.py",
    "modules/context_pack_ru.py",
    "modules/debug_package_ru.py",
    "modules/desktop_action_planner.py",
    "modules/desktop_control_plane_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "modules/desktop_observer.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/development_safety_orchestrator_ru.py",
    "modules/diagnostics.py",
    "modules/executor_adapter_registry_ru.py",
    "modules/feature_verification.py",
    "modules/files.py",
    "modules/first_failure_extractor_ru.py",
    "modules/git_status.py",
    "modules/global_update_center.py",
    "modules/gpt_browser_bridge.py",
    "modules/gpt_client.py",
    "modules/green_gate_status_ru.py",
    "modules/history_log.py",
    "modules/knowledge_adapter_ru.py",
    "modules/knowledge_change_proposal_ru.py",
    "modules/knowledge_change_review_decision_ru.py",
    "modules/knowledge_change_review_ru.py",
    "modules/knowledge_contract_ru.py",
    "modules/knowledge_injection_ru.py",
    "modules/knowledge_review_ui_projection_ru.py",
    "modules/llm_provider.py",
    "modules/local_llm_picker.py",
    "modules/local_model_gateway_ru.py",
    "modules/localcomet_agent_auto_test_center_ru.py",
    "modules/localcomet_developer_velocity_ru.py",
    "modules/localcomet_functional_test_center_ru.py",
    "modules/maintenance.py",
    "modules/maintenance_diagnostics_ru.py",
    "modules/natural_command_intents.py",
    "modules/open_source_gui_boost.py",
    "modules/panel_capability_audit_ru.py",
    "modules/parallel_worktree_executor_protocol_ru.py",
    "modules/patch_event_timeline_ru.py",
    "modules/patch_panel_ux_reliability_ru.py",
    "modules/patch_registry.py",
    "modules/pc_agent_actions.py",
    "modules/pc_agent_core.py",
    "modules/pc_agent_knowledge.py",
    "modules/pc_codex_core.py",
    "modules/pc_codex_executor.py",
    "modules/pc_codex_mode.py",
    "modules/pc_control_core.py",
    "modules/pc_desktop_primitives.py",
    "modules/pc_screen_planner.py",
    "modules/pc_ui_parser_adapter.py",
    "modules/plan_contract_ru.py",
    "modules/premium_native_ui_ru.py",
    "modules/premium_task_panel_ru.py",
    "modules/premium_ui_launcher.py",
    "modules/premium_ui_now.py",
    "modules/premium_ui_prototype.py",
    "modules/project_audit_bundle_ru.py",
    "modules/project_health.py",
    "modules/project_one_command_check_ru.py",
    "modules/project_paths.py",
    "modules/regression_commands.py",
    "modules/relay_diagnostics.py",
    "modules/repo_analyzer_ru.py",
    "modules/repo_weight_audit_ru.py",
    "modules/report_opener.py",
    "modules/repository_preflight_ru.py",
    "modules/research.py",
    "modules/reviewer_bridge_ru.py",
    "modules/risk_classifier_ru.py",
    "modules/russian_command_context.py",
    "modules/safety_cleanup_center.py",
    "modules/screenshot_capture_policy_ru.py",
    "modules/screenshot_retention_dry_run_ru.py",
    "modules/screenshot_retention_policy_config_ru.py",
    "modules/screenshot_storage_policy_simulator_ru.py",
    "modules/self_edit.py",
    "modules/stability_test.py",
    "modules/storage_cleanup_plan_ru.py",
    "modules/strict_project_stability_ru.py",
    "modules/swiss_knife_skill_launcher.py",
    "modules/task_clarifier.py",
    "modules/task_contract_registry_ru.py",
    "modules/task_planner_orchestrator_ru.py",
    "modules/true_auto_relay.py",
    "modules/voice.py",
    "modules/voice_control.py",
    "modules/windows.py",
    "modules/working_directory_guard_ru.py",
    "modules/workspace.py"
  ],
  "tests": [
    "test_full_flow.py",
    "test_full_flow2.py",
    "test_full_flow3.py",
    "test_working_directory_guard.py",
    "tools/test_gpt_bridge.py",
    "tools/test_up00_unready_sidecar.py",
    "tools/test_up02_wp01_assistant_context.py",
    "tools/test_up02_wp01_security_negative.py",
    "tools/test_up05_wp01_model_chat_backend.py",
    "tools/test_v677_regression.py",
    "tools/test_v678_router_registry.py",
    "tools/test_v679_retention.py",
    "tools/test_v6801_audit_bundle.py",
    "tools/test_v6802_bundle_security.py",
    "tools/test_v680_reproducibility.py",
    "tools/test_v681_diagnostics.py",
    "tools/test_v682_task_planner.py",
    "tools/test_v683_autonomy_policy.py",
    "tools/test_v6841_desktop_ipc.py",
    "tools/test_v6842_desktop_shell.py",
    "tools/test_v6843_sidecar_supervisor.py",
    "tools/test_v6844_control_plane.py",
    "tools/test_v68451_managed_runtime.py",
    "tools/test_v68451d3_start_localcomet.py",
    "tools/test_v68451d_dev_launcher.py",
    "tools/test_v68451e4_knowledge_adapter.py",
    "tools/test_v68451e5_knowledge_control_plane.py",
    "tools/test_v68451e6_knowledge_injection.py",
    "tools/test_v68451e7_desktop_knowledge_preview.py",
    "tools/test_v68451e7b_sse_utf8_decoder.py",
    "tools/test_v68451e9a_knowledge_change_proposal.py",
    "tools/test_v68451e9b_knowledge_review.py",
    "tools/test_v68451e9c_human_review_decision.py",
    "tools/test_v68451e9c_review_projection.py",
    "tools/test_v68451e9d_knowledge_review_producer.py",
    "tools/test_v6845_model_gateway.py",
    "tools/test_v6846_knowledge_operations_command_center.py",
    "tools/test_v684_action_executor.py"
  ],
  "tools": [
    "scripts/generate_runtime_manifest.py",
    "scripts/manual_model_gateway.py",
    "tools/build_up00_windows_installer.py",
    "tools/create_project_audit_bundle.py",
    "tools/hard_model_tester.py",
    "tools/launch_localcomet_dev.py",
    "tools/localcomet_preflight_audit.py",
    "tools/model_tester.py",
    "tools/run_localcomet_desktop_sidecar.py",
    "tools/smoke_sse_utf8.py",
    "tools/start_localcomet.py",
    "tools/validate_localcomet_vault.py",
    "tools/verify_project_audit_bundle.py"
  ]
}
````

### ПУТЬ: localcomet_test_harness.py (107 строк, 3885 байт)

````python
"""LocalComet test harness for smoke testing.

Wraps the REAL DesktopSidecarRuntime (modules/desktop_sidecar_runtime_ru.py)
and drives it in-process over the same IPC message contract the desktop bridge
uses. This does NOT duplicate product logic and does NOT open a private IPC
channel: it calls the same handle_message() entry point the runner uses.

Scope note: the desktop sidecar is a model-gateway / knowledge / session
manager. It performs NO filesystem tool execution (files.* methods are
unsupported_method). Approval and workspace confinement are enforced in the
Rust control plane (src-tauri/src/approval.rs, workspace.rs) and are covered by
cargo tests, not by this Python smoke.
"""

from __future__ import annotations

import time
from typing import Any

from modules.desktop_ipc_contract_ru import make_hello, make_request
from modules.desktop_sidecar_runtime_ru import make_runtime


class ApprovalRequired(Exception):
    pass


class InputDigestMismatch(Exception):
    pass


class TokenNotFound(Exception):
    pass


class WorkspaceViolation(Exception):
    pass


class LocalCometHarness:
    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = project_root
        self.runtime = make_runtime()
        self._counter = 0
        self._hello_seen = False
        self._capabilities: list[str] = []
        self._runtime_version = "unknown"

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"smoke-{prefix}-{self._counter:06d}"

    def start_sidecar(self, workspace: str | None = None) -> tuple[int, str]:
        hello = make_hello(self._next_id("hello"), session_nonce="smoke-nonce-000000000000")
        replies = self.runtime.handle_message(hello)
        for reply in replies:
            if reply.get("type") == "hello":
                payload = reply["payload"]
                self._hello_seen = True
                self._capabilities = list(payload.get("capabilities", []))
                self._runtime_version = payload.get("runtime_version", "unknown")
                return (0, self._runtime_version)
        raise RuntimeError("sidecar did not answer the desktop hello")

    def readiness_probe(self, timeout_ms: int = 5000) -> tuple[str, int]:
        started = time.monotonic()
        replies = self.runtime.handle_message(
            make_request(self._next_id("health"), "app.health", {})
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        for reply in replies:
            if reply.get("type") == "response" and reply.get("payload", {}).get("status") == "ok":
                return ("ok", elapsed_ms)
        return ("error", elapsed_ms)

    def runtime_health(self) -> dict[str, Any]:
        replies = self.runtime.handle_message(
            make_request(self._next_id("health"), "app.health", {})
        )
        for reply in replies:
            if reply.get("type") == "response":
                return reply["payload"]
        raise RuntimeError("no health response")

    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request and return the first response/error envelope."""
        replies = self.runtime.handle_message(
            make_request(self._next_id("req"), method, payload)
        )
        for reply in replies:
            if reply.get("type") in ("response", "error"):
                return reply
        raise RuntimeError(f"no terminal reply for {method}")

    def sidecar_pid(self) -> int:
        return 0  # in-process harness; no OS process

    def shutdown(self) -> None:
        try:
            self.runtime.handle_message(
                make_request(self._next_id("shutdown"), "app.shutdown", {})
            )
        finally:
            self.runtime.close()
````

### ПУТЬ: memory/state.json (1097 строк, 33307 байт)

````json
{
  "desktop_observer: да": "да",
  "last_desktop_observation_report": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\desktop_observe_20260725_054252.md",
  "last_desktop_screenshot": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\screenshots\\desktop_20260725_054252.bmp",
  "last_desktop_active_window": "Статус запуска Задания 1",
  "last_desktop_observation": "{\"created_at\": \"2026-07-25T05:42:52\", \"active_window\": {\"title\": \"Статус запуска Задания 1\", \"class\": \"Chrome_WidgetWin_1\", \"rect\": {\"left\": -9, \"top\": -9, \"right\": 2057, \"bottom\": 1113, \"width\": 2066, \"height\": 1122}, \"hwnd\": 657376}, \"windows\": [{\"title\": \"Статус запуска Задания 1\", \"class\": \"Chrome_WidgetWin_1\", \"rect\": {\"left\": -9, \"top\": -9, \"right\": 2057, \"bottom\": 1113, \"width\": 2066, \"height\": 1122}, \"hwnd\": 657376}, {\"title\": \"OpenCode\", \"class\": \"Chrome_WidgetWin_1\", \"rect\": {\"left\": -25600, \"top\": -25600, \"right\": -25410, \"bottom\": -25569, \"width\": 190, \"height\": 31}, \"hwnd\": 2622358}, {\"title\": \"Telegram Web - Google Chrome\", \"class\": \"Chrome_WidgetWin_1\", \"rect\": {\"left\": -7, \"top\": -7, \"right\": 2055, \"bottom\": 1111, \"width\": 2062, \"height\": 1118}, \"hwnd\": 11143340}, {\"title\": \"Windows PowerShell\", \"class\": \"ConsoleWindowClass\", \"rect\": {\"left\": 179, \"top\": 179, \"right\": 1074, \"bottom\": 697, \"width\": 895, \"height\": 518}, \"hwnd\": 6293468}, {\"title\": \"C:\\\\WINDOWS\\\\system32\\\\cmd.exe\", \"class\": \"ConsoleWindowClass\", \"rect\": {\"left\": -7, \"top\": -7, \"right\": 2055, \"bottom\": 1111, \"width\": 2062, \"height\": 1118}, \"hwnd\": 13042118}, {\"title\": \"Windows PowerShell\", \"class\": \"ConsoleWindowClass\", \"rect\": {\"left\": -7, \"top\": -7, \"right\": 2055, \"bottom\": 1111, \"width\": 2062, \"height\": 1118}, \"hwnd\": 4063288}, {\"title\": \"FastVPN\", \"class\": \"HwndWrapper[FastVPN.exe;;435cb4aa-848c-48c2-9dba-40730f5bd91f]\", \"rect\": {\"left\": 789, \"top\": 85, \"right\": 1989, \"bottom\": 760, \"width\": 1200, \"height\": 675}, \"hwnd\": 3277956}, {\"title\": \"Интерфейс ввода Windows\", \"class\": \"Windows.UI.Core.CoreWindow\", \"rect\": {\"left\": 0, \"top\": 0, \"right\": 2048, \"bottom\": 1152, \"width\": 2048, \"height\": 1152}, \"hwnd\": 329312}, {\"title\": \"NVIDIA GeForce Overlay\", \"class\": \"CEF-OSC-WIDGET\", \"rect\": {\"left\": 0, \"top\": 0, \"right\": 2047, \"bottom\": 1152, \"width\": 2047, \"height\": 1152}, \"hwnd\": 131234}, {\"title\": \"Program Manager\", \"class\": \"Progman\", \"rect\": {\"left\": 0, \"top\": 0, \"right\": 2048, \"bottom\": 1152, \"width\": 2048, \"height\": 1152}, \"hwnd\": 65832}], \"screenshot_path\": \"C:\\\\Users\\\\DNS\\\\AppData\\\\Local\\\\Temp\\\\localcomet_v678_self_check_64klh305\\\\Projects\\\\Reports\\\\desktop_observer\\\\screenshots\\\\desktop_20260725_054252.bmp\", \"screenshot_error\": \"PIL unavailable, used BMP fallback: No module named 'PIL'\", \"report_path\": \"C:\\\\Users\\\\DNS\\\\AppData\\\\Local\\\\Temp\\\\localcomet_v678_self_check_64klh305\\\\Projects\\\\Reports\\\\desktop_observer\\\\desktop_observe_20260725_054252.md\"}",
  "pc_desktop_primitives_windows": {
    "ok": true,
    "mode": "desktop_windows",
    "generated_at": "2026-07-25T05:42:52",
    "platform": "Windows-11-10.0.26200-SP0",
    "active_window": {
      "title": "Статус запуска Задания 1",
      "class": "Chrome_WidgetWin_1",
      "rect": {
        "left": -9,
        "top": -9,
        "right": 2057,
        "bottom": 1113,
        "width": 2066,
        "height": 1122
      },
      "hwnd": 657376,
      "safety": {
        "safe": true,
        "matched_terms": [],
        "reason": ""
      }
    },
    "windows": [
      {
        "title": "Статус запуска Задания 1",
        "class": "Chrome_WidgetWin_1",
        "rect": {
          "left": -9,
          "top": -9,
          "right": 2057,
          "bottom": 1113,
          "width": 2066,
          "height": 1122
        },
        "hwnd": 657376,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "OpenCode",
        "class": "Chrome_WidgetWin_1",
        "rect": {
          "left": -25600,
          "top": -25600,
          "right": -25410,
          "bottom": -25569,
          "width": 190,
          "height": 31
        },
        "hwnd": 2622358,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "Telegram Web - Google Chrome",
        "class": "Chrome_WidgetWin_1",
        "rect": {
          "left": -7,
          "top": -7,
          "right": 2055,
          "bottom": 1111,
          "width": 2062,
          "height": 1118
        },
        "hwnd": 11143340,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "Windows PowerShell",
        "class": "ConsoleWindowClass",
        "rect": {
          "left": 179,
          "top": 179,
          "right": 1074,
          "bottom": 697,
          "width": 895,
          "height": 518
        },
        "hwnd": 6293468,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "C:\\WINDOWS\\system32\\cmd.exe",
        "class": "ConsoleWindowClass",
        "rect": {
          "left": -7,
          "top": -7,
          "right": 2055,
          "bottom": 1111,
          "width": 2062,
          "height": 1118
        },
        "hwnd": 13042118,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "Windows PowerShell",
        "class": "ConsoleWindowClass",
        "rect": {
          "left": -7,
          "top": -7,
          "right": 2055,
          "bottom": 1111,
          "width": 2062,
          "height": 1118
        },
        "hwnd": 4063288,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "FastVPN",
        "class": "HwndWrapper[FastVPN.exe;;435cb4aa-848c-48c2-9dba-40730f5bd91f]",
        "rect": {
          "left": 789,
          "top": 85,
          "right": 1989,
          "bottom": 760,
          "width": 1200,
          "height": 675
        },
        "hwnd": 3277956,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "Интерфейс ввода Windows",
        "class": "Windows.UI.Core.CoreWindow",
        "rect": {
          "left": 0,
          "top": 0,
          "right": 2048,
          "bottom": 1152,
          "width": 2048,
          "height": 1152
        },
        "hwnd": 329312,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "NVIDIA GeForce Overlay",
        "class": "CEF-OSC-WIDGET",
        "rect": {
          "left": 0,
          "top": 0,
          "right": 2047,
          "bottom": 1152,
          "width": 2047,
          "height": 1152
        },
        "hwnd": 131234,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      },
      {
        "title": "Program Manager",
        "class": "Progman",
        "rect": {
          "left": 0,
          "top": 0,
          "right": 2048,
          "bottom": 1152,
          "width": 2048,
          "height": 1152
        },
        "hwnd": 65832,
        "safety": {
          "safe": true,
          "matched_terms": [],
          "reason": ""
        }
      }
    ],
    "count": 10
  },
  "pc_desktop_primitives_screenshot": {
    "ok": true,
    "mode": "desktop_screenshot_metadata",
    "generated_at": "2026-07-25T05:42:52",
    "screenshot_path": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\screenshots\\desktop_20260725_054252.bmp",
    "screenshot_error": "PIL unavailable, used BMP fallback: No module named 'PIL'",
    "report_path": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\desktop_observe_20260725_054252.md",
    "active_window": {
      "title": "Статус запуска Задания 1",
      "class": "Chrome_WidgetWin_1",
      "rect": {
        "left": -9,
        "top": -9,
        "right": 2057,
        "bottom": 1113,
        "width": 2066,
        "height": 1122
      },
      "hwnd": 657376
    },
    "windows_count": 10
  },
  "ui_parser_last_parse": {
    "ok": true,
    "mode": "ui_parser_adapter_parse",
    "generated_at": "2026-07-25T05:42:52",
    "backend": "desktop_window_parser",
    "omniparser_compatible": true,
    "schema": {
      "version": "localcomet_ui_element_v2",
      "description": "OmniParser-compatible LocalComet UI element schema without requiring heavy parser dependencies.",
      "element": {
        "id": "string",
        "element_type": "window|button|input|text|icon|image|menu|unknown",
        "text": "string",
        "bbox": {
          "x": "int",
          "y": "int",
          "width": "int",
          "height": "int"
        },
        "center": {
          "x": "int",
          "y": "int"
        },
        "confidence": "float 0..1",
        "clickable": "bool",
        "source": "desktop_observer|desktop_primitives|screen_parser_adapter|omniparser_future|manual",
        "metadata": "dict"
      }
    },
    "screen": {
      "screenshot_path": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\screenshots\\desktop_20260725_054252.bmp",
      "screenshot_error": "PIL unavailable, used BMP fallback: No module named 'PIL'",
      "report_path": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\Reports\\desktop_observer\\desktop_observe_20260725_054252.md",
      "windows_count": 10,
      "active_window_title": "Статус запуска Задания 1"
    },
    "elements": [
      {
        "id": "active_window",
        "element_type": "window",
        "text": "Статус запуска Задания 1",
        "bbox": {
          "x": -9,
          "y": -9,
          "width": 2066,
          "height": 1122
        },
        "center": {
          "x": 1024,
          "y": 552
        },
        "confidence": 1.0,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Chrome_WidgetWin_1",
          "hwnd": 657376,
          "active": true,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_1",
        "element_type": "window",
        "text": "Статус запуска Задания 1",
        "bbox": {
          "x": -9,
          "y": -9,
          "width": 2066,
          "height": 1122
        },
        "center": {
          "x": 1024,
          "y": 552
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Chrome_WidgetWin_1",
          "hwnd": 657376,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_1_title_text_1",
        "element_type": "text",
        "text": "Статус",
        "bbox": {
          "x": -9,
          "y": -9,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 101,
          "y": 3
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Статус запуска Задания 1",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_1_title_text_2",
        "element_type": "text",
        "text": "запуска",
        "bbox": {
          "x": 679,
          "y": -9,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 789,
          "y": 3
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Статус запуска Задания 1",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_1_title_text_3",
        "element_type": "text",
        "text": "Задания",
        "bbox": {
          "x": 1367,
          "y": -9,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1477,
          "y": 3
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Статус запуска Задания 1",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_2",
        "element_type": "window",
        "text": "OpenCode",
        "bbox": {
          "x": -25600,
          "y": -25600,
          "width": 190,
          "height": 31
        },
        "center": {
          "x": -25505,
          "y": -25584
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Chrome_WidgetWin_1",
          "hwnd": 2622358,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_2_title_text_1",
        "element_type": "text",
        "text": "OpenCode",
        "bbox": {
          "x": -25600,
          "y": -25600,
          "width": 190,
          "height": 24
        },
        "center": {
          "x": -25505,
          "y": -25588
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "OpenCode",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_3",
        "element_type": "window",
        "text": "Telegram Web - Google Chrome",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 2062,
          "height": 1118
        },
        "center": {
          "x": 1024,
          "y": 552
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Chrome_WidgetWin_1",
          "hwnd": 11143340,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_3_title_text_1",
        "element_type": "text",
        "text": "Telegram",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 103,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Telegram Web - Google Chrome",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_3_title_text_2",
        "element_type": "text",
        "text": "Web",
        "bbox": {
          "x": 508,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 618,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Telegram Web - Google Chrome",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_3_title_text_3",
        "element_type": "text",
        "text": "Google",
        "bbox": {
          "x": 1023,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1133,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Telegram Web - Google Chrome",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_3_title_text_4",
        "element_type": "text",
        "text": "Chrome",
        "bbox": {
          "x": 1538,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1648,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Telegram Web - Google Chrome",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_4",
        "element_type": "window",
        "text": "Windows PowerShell",
        "bbox": {
          "x": 179,
          "y": 179,
          "width": 895,
          "height": 518
        },
        "center": {
          "x": 626,
          "y": 438
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "ConsoleWindowClass",
          "hwnd": 6293468,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_4_title_text_1",
        "element_type": "text",
        "text": "Windows",
        "bbox": {
          "x": 179,
          "y": 179,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 289,
          "y": 191
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Windows PowerShell",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_4_title_text_2",
        "element_type": "text",
        "text": "PowerShell",
        "bbox": {
          "x": 626,
          "y": 179,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 736,
          "y": 191
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Windows PowerShell",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_5",
        "element_type": "window",
        "text": "C:\\WINDOWS\\system32\\cmd.exe",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 2062,
          "height": 1118
        },
        "center": {
          "x": 1024,
          "y": 552
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "ConsoleWindowClass",
          "hwnd": 13042118,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_5_title_text_1",
        "element_type": "text",
        "text": "C:\\WINDOWS\\system32\\cmd.exe",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 103,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "C:\\WINDOWS\\system32\\cmd.exe",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_6",
        "element_type": "window",
        "text": "Windows PowerShell",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 2062,
          "height": 1118
        },
        "center": {
          "x": 1024,
          "y": 552
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "ConsoleWindowClass",
          "hwnd": 4063288,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_6_title_text_1",
        "element_type": "text",
        "text": "Windows",
        "bbox": {
          "x": -7,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 103,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Windows PowerShell",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_6_title_text_2",
        "element_type": "text",
        "text": "PowerShell",
        "bbox": {
          "x": 1024,
          "y": -7,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1134,
          "y": 5
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Windows PowerShell",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_7",
        "element_type": "window",
        "text": "FastVPN",
        "bbox": {
          "x": 789,
          "y": 85,
          "width": 1200,
          "height": 675
        },
        "center": {
          "x": 1389,
          "y": 422
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "HwndWrapper[FastVPN.exe;;435cb4aa-848c-48c2-9dba-40730f5bd91f]",
          "hwnd": 3277956,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_7_title_text_1",
        "element_type": "text",
        "text": "FastVPN",
        "bbox": {
          "x": 789,
          "y": 85,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 899,
          "y": 97
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "FastVPN",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_8",
        "element_type": "window",
        "text": "Интерфейс ввода Windows",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 2048,
          "height": 1152
        },
        "center": {
          "x": 1024,
          "y": 576
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Windows.UI.Core.CoreWindow",
          "hwnd": 329312,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_8_title_text_1",
        "element_type": "text",
        "text": "Интерфейс",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 110,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Интерфейс ввода Windows",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_8_title_text_2",
        "element_type": "text",
        "text": "ввода",
        "bbox": {
          "x": 682,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 792,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Интерфейс ввода Windows",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_8_title_text_3",
        "element_type": "text",
        "text": "Windows",
        "bbox": {
          "x": 1364,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1474,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Интерфейс ввода Windows",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_9",
        "element_type": "window",
        "text": "NVIDIA GeForce Overlay",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 2047,
          "height": 1152
        },
        "center": {
          "x": 1023,
          "y": 576
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "CEF-OSC-WIDGET",
          "hwnd": 131234,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_9_title_text_1",
        "element_type": "text",
        "text": "NVIDIA",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 110,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "NVIDIA GeForce Overlay",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_9_title_text_2",
        "element_type": "text",
        "text": "GeForce",
        "bbox": {
          "x": 682,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 792,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "NVIDIA GeForce Overlay",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_9_title_text_3",
        "element_type": "text",
        "text": "Overlay",
        "bbox": {
          "x": 1364,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1474,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "NVIDIA GeForce Overlay",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_10",
        "element_type": "window",
        "text": "Program Manager",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 2048,
          "height": 1152
        },
        "center": {
          "x": 1024,
          "y": 576
        },
        "confidence": 0.96,
        "clickable": true,
        "source": "desktop_primitives",
        "metadata": {
          "class": "Progman",
          "hwnd": 65832,
          "active": false,
          "safety": {
            "safe": true,
            "blocked_terms": [],
            "reason": ""
          }
        }
      },
      {
        "id": "window_10_title_text_1",
        "element_type": "text",
        "text": "Program",
        "bbox": {
          "x": 0,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 110,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Program Manager",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      },
      {
        "id": "window_10_title_text_2",
        "element_type": "text",
        "text": "Manager",
        "bbox": {
          "x": 1024,
          "y": 0,
          "width": 220,
          "height": 24
        },
        "center": {
          "x": 1134,
          "y": 12
        },
        "confidence": 0.62,
        "clickable": false,
        "source": "screen_parser_adapter",
        "metadata": {
          "parent_window": "Program Manager",
          "derived": true,
          "note": "Heuristic title token element. Future OmniParser backend will replace this with real OCR/UI parsing."
        }
      }
    ],
    "elements_count": 33,
    "warnings": [
      "This is a lightweight adapter. It does not perform OCR yet.",
      "Window rectangles are real; button/input/text elements are heuristic until OmniParser backend is installed.",
      "No click/type action has been executed."
    ],
    "errors": [],
    "path": "C:\\Users\\DNS\\AppData\\Local\\Temp\\localcomet_v678_self_check_64klh305\\Projects\\PCAgent\\UIParser\\ui_parse_20260725_054252.json"
  }
}
````

### ПУТЬ: modules/agent_onboarding_demo.py (843 строк, 25397 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import textwrap

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
ONBOARDING_DIR = PROJECTS_DIR / "PCAgent" / "Onboarding"
DEMO_DIR = PROJECTS_DIR / "PCAgent" / "DemoWorkspace"
DEMO_SITE_DIR = DEMO_DIR / "demo-site"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agent_onboarding_demo"

QUICKSTART_AGENTS_FILE = ONBOARDING_DIR / "AGENTS_LocalComet_QUICKSTART.md"
ONBOARDING_CHECKLIST_FILE = ONBOARDING_DIR / "onboarding_checklist.json"
DEMO_REQUEST_FILE = DEMO_DIR / "demo_site_request.md"

AGENT_FORMULA = {
    "LLM": {
        "plain": "Мозг агента.",
        "localcomet": "LM Studio / Qwen / ChatGPT relay / local model smoke checks.",
    },
    "Tools": {
        "plain": "Руки агента.",
        "localcomet": "pc desktop, pc screen, pc exec, pc boost, pc agentos, project patch workflow.",
    },
    "Loop": {
        "plain": "Цикл достижения цели.",
        "localcomet": "observe -> plan -> dry-run -> confirm -> execute -> report.",
    },
    "Memory": {
        "plain": "Память и рабочее пространство.",
        "localcomet": "core.state, Projects/PCAgent, Projects/Reports, patch registry, future knowledge graph.",
    },
}

SAFETY_PROFILE = {
    "admin_terminal": "denied",
    "arbitrary_shell": "denied",
    "execute_all_commands": "denied",
    "auto_yes_all": "denied",
    "secrets_passwords_tokens_ssh": "denied",
    "delete_files": "denied",
    "quarantine_files": "allowed_after_confirmation",
    "read_project_files": "allowed",
    "project_changes": "response_json_patch_only",
    "desktop_actions": "dry_run_then_explicit_confirmation",
    "reports": "required_for_workflows",
}

ONBOARDING_STEPS = [
    {
        "id": "understand_agent",
        "title": "Понять, что агент это LLM + Tools + Loop + Memory.",
        "command": "pc onboard explain",
        "status": "ready",
    },
    {
        "id": "check_localcomet_stack",
        "title": "Проверить LocalComet stack и safety-профиль.",
        "command": "pc onboard localcomet",
        "status": "ready",
    },
    {
        "id": "check_lmstudio",
        "title": "Проверить локальную модель / LM Studio.",
        "command": "pc onboard lmstudio",
        "status": "manual_check",
    },
    {
        "id": "optional_qwen_cli",
        "title": "Qwen CLI как внешний reference agent, не как доверенный executor.",
        "command": "pc onboard qwen",
        "status": "optional",
    },
    {
        "id": "generate_agents_md",
        "title": "Создать безопасный AGENTS.md quickstart draft.",
        "command": "pc onboard agents.md",
        "status": "ready",
    },
    {
        "id": "demo_site",
        "title": "Сделать безопасный demo-site workflow через request/draft files.",
        "command": "pc demo site plan",
        "status": "ready",
    },
]

LOCALCOMET_QUICKSTART_AGENTS_MD = """# AGENTS.md — LocalComet Quickstart

## What is this agent?

LocalComet is a local safety-first AI agent. It is not just a chatbot. It is a system made of four parts:

```text
LLM    -> reasoning brain
Tools  -> safe hands
Loop   -> plan/dry-run/confirm/execute/report
Memory -> project context, reports, state, skill registry
```

## Golden Workflow

```text
1. Understand the user's goal.
2. Check safety with semantic firewall.
3. Observe project/screen context.
4. Pick a safe skill.
5. Create a plan.
6. Run dry-run.
7. Ask for explicit confirmation when needed.
8. Execute one bounded safe step.
9. Save report.
10. Suggest the next step.
```

## LocalComet Safety Rules

```yaml
admin_terminal: denied
arbitrary_shell: denied
execute_all_commands: denied
auto_yes_all: denied
secrets_passwords_tokens_ssh: denied
delete_files: denied
quarantine_files: allowed_after_confirmation
read_project_files: allowed
project_changes: response_json_patch_only
desktop_actions: dry_run_then_explicit_confirmation
reports: required_for_workflows
```

## Useful Commands

```text
pc onboard status
pc onboard explain
pc onboard safety
pc agentos firewall <intent>
pc screen plan <goal>
pc desktop windows
pc exec dry <goal>
pc exec run подтверждаю: <goal>
pc demo site plan
pc demo site request
```

## Demo Task

Use the safe demo workflow:

```text
pc demo site plan
pc demo site dry
pc demo site request
```

The agent must not run a web server or shell command automatically. It creates draft files and a patch/request plan first.
"""


DEMO_INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LocalComet Demo Site</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="page">
    <section class="hero" aria-labelledby="hero-title">
      <p class="eyebrow">LocalComet Demo Workspace</p>
      <h1 id="hero-title">Добро пожаловать!</h1>
      <p class="lead">
        Это безопасный draft-сайт, созданный через LocalComet onboarding workflow.
        Никакие shell-команды не выполнялись автоматически.
      </p>
      <a class="button" href="#details">Посмотреть детали</a>
    </section>
    <section id="details" class="card">
      <h2>Как работает агент</h2>
      <p>LLM думает, tools действуют, loop ведёт задачу до результата, memory сохраняет контекст.</p>
    </section>
  </main>
</body>
</html>
"""

DEMO_STYLES_CSS = """* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: Arial, sans-serif;
  background: linear-gradient(135deg, #4f46e5, #7c3aed, #0f172a);
  color: #ffffff;
}

.page {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: 72px 0;
}

.hero {
  min-height: 70vh;
  display: grid;
  align-content: center;
  text-align: center;
}

.eyebrow {
  margin: 0 0 16px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.76);
}

h1 {
  margin: 0;
  font-size: clamp(44px, 9vw, 92px);
  line-height: 0.95;
}

.lead {
  max-width: 720px;
  margin: 24px auto;
  font-size: clamp(18px, 2.5vw, 24px);
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.88);
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  padding: 0 22px;
  border-radius: 999px;
  background: #ffffff;
  color: #4f46e5;
  text-decoration: none;
  font-weight: 700;
}

.card {
  margin-top: 40px;
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(14px);
}
"""

DEMO_README = """# Demo Site Draft

This folder was generated by LocalComet Agent Onboarding + Demo Workspace.

## Safety

No shell command was executed.
No local server was started automatically.
No admin terminal was used.
No secrets were requested.

## Files

- `index.html`
- `styles.css`

Open `index.html` manually in a browser or create a LocalComet patch/deploy workflow later.
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    ONBOARDING_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _localcomet_stack():
    stack = [
        "PC Codex Core",
        "PC Codex Executor",
        "Screen-Aware Planner",
        "Open-Source GUI Boost Base",
        "Desktop Interaction Primitives",
        "AgentOS Kernel + Skills Blueprint",
    ]
    return {
        "ok": True,
        "items": stack,
        "pipeline": "observe -> plan -> dry-run -> confirm -> execute -> report",
        "safe_execution": "confirmed action only",
    }


def status():
    payload = {
        "ok": True,
        "mode": "agent_onboarding_demo",
        "generated_at": _now(),
        "formula": AGENT_FORMULA,
        "steps_count": len(ONBOARDING_STEPS),
        "safety_profile": SAFETY_PROFILE,
        "last_checklist": get_value("agent_onboarding_last_checklist", ""),
        "last_demo": get_value("agent_onboarding_last_demo", ""),
        "commands": [
            "pc onboard status",
            "pc onboard explain",
            "pc onboard checklist",
            "pc onboard localcomet",
            "pc onboard qwen",
            "pc onboard lmstudio",
            "pc onboard safety",
            "pc onboard agents.md",
            "pc onboard report",
            "pc demo site plan",
            "pc demo site dry",
            "pc demo site request",
            "pc demo site files",
            "pc demo site report",
        ],
    }
    set_value("agent_onboarding_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "Agent Onboarding + Demo Workspace:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- steps_count: {payload.get('steps_count')}",
        "",
        "Agent formula:",
    ]
    for key, item in payload.get("formula", {}).items():
        lines.append(f"- {key}: {item.get('plain')} | LocalComet: {item.get('localcomet')}")
    lines.append("")
    lines.append("Commands:")
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def explain():
    payload = {
        "ok": True,
        "mode": "agent_explanation",
        "generated_at": _now(),
        "short": "ИИ-агент = LLM + Tools + Loop + Memory.",
        "formula": AGENT_FORMULA,
        "localcomet_translation": [
            "LLM: мозг для рассуждения.",
            "Tools: безопасные модули desktop/screen/exec/project/browser.",
            "Loop: план -> dry-run -> подтверждение -> действие -> отчёт.",
            "Memory: state, reports, project context, skills registry.",
        ],
        "why_localcomet_is_safer": [
            "No admin terminal by default.",
            "No arbitrary shell.",
            "No auto-yes for unknown commands.",
            "No secrets/tokens/passwords.",
            "Project edits through response.json patch workflow.",
        ],
    }
    set_value("agent_onboarding_explain", payload)
    return payload


def checklist():
    _ensure_dirs()
    items = []
    for step in ONBOARDING_STEPS:
        items.append({
            "id": step["id"],
            "title": step["title"],
            "command": step["command"],
            "status": step["status"],
            "done": step["status"] in {"ready", "optional"},
        })

    payload = {
        "ok": True,
        "mode": "agent_onboarding_checklist",
        "generated_at": _now(),
        "items": items,
        "safety_profile": SAFETY_PROFILE,
        "path": str(ONBOARDING_CHECKLIST_FILE),
    }
    _write_json(ONBOARDING_CHECKLIST_FILE, payload)
    set_value("agent_onboarding_last_checklist", payload)
    return payload


def localcomet():
    payload = {
        "ok": True,
        "mode": "localcomet_stack_check",
        "generated_at": _now(),
        "stack": _localcomet_stack(),
        "recommended_first_commands": [
            "pc agentos status",
            "pc onboard explain",
            "pc screen status",
            "pc desktop status",
            "pc exec status",
        ],
    }
    set_value("agent_onboarding_localcomet", payload)
    return payload


def qwen_reference():
    payload = {
        "ok": True,
        "mode": "qwen_cli_reference",
        "generated_at": _now(),
        "positioning": "Qwen CLI can be treated as an external reference/coding agent, not a trusted executor inside LocalComet.",
        "safe_use": [
            "Use it for comparison or manual coding workflows.",
            "Do not paste secrets into external agents.",
            "Do not run unknown install commands through LocalComet.",
            "Do not grant auto-approve all commands.",
            "LocalComet remains the orchestrator for project safety.",
        ],
        "localcomet_alternative": [
            "pc edit <goal>",
            "pc agentos firewall <intent>",
            "response.json patch workflow",
            "Auto Verification + Full Stability",
        ],
    }
    set_value("agent_onboarding_qwen_reference", payload)
    return payload


def lmstudio_reference():
    payload = {
        "ok": True,
        "mode": "lmstudio_reference",
        "generated_at": _now(),
        "purpose": "Local LLM backend for private/offline reasoning.",
        "checklist": [
            "Model loads successfully.",
            "Local server is running.",
            "Tool-use capable model preferred.",
            "Large context configured when hardware allows.",
            "Compact prompt enabled when context pressure appears.",
            "Model smoke test passes in LocalComet.",
        ],
        "localcomet_commands": [
            "lmstudio diagnostics",
            "model smoke",
            "auto verification full",
        ],
    }
    set_value("agent_onboarding_lmstudio_reference", payload)
    return payload


def safety():
    payload = {
        "ok": True,
        "mode": "onboarding_safety_profile",
        "generated_at": _now(),
        "profile": SAFETY_PROFILE,
        "plain_rules": [
            "Не запускаем cmd/powershell/shell из чата.",
            "Не используем режим администратора для агента.",
            "Не подтверждаем все команды подряд.",
            "Не даём агенту пароли, токены, SSH-ключи.",
            "Не удаляем файлы; при необходимости только quarantine.",
            "Любые изменения проекта идут через patch + tests + rollback.",
        ],
    }
    set_value("agent_onboarding_safety", payload)
    return payload


def generate_agents_md():
    _ensure_dirs()
    _write_text(QUICKSTART_AGENTS_FILE, LOCALCOMET_QUICKSTART_AGENTS_MD)
    payload = {
        "ok": True,
        "mode": "quickstart_agents_md",
        "generated_at": _now(),
        "path": str(QUICKSTART_AGENTS_FILE),
        "note": "Draft only. Review before copying anywhere else.",
        "safe": True,
    }
    set_value("agent_onboarding_agents_md", payload)
    return payload


def demo_site_plan():
    payload = {
        "ok": True,
        "mode": "demo_site_plan",
        "generated_at": _now(),
        "goal": "Create a simple one-page demo site in a safe workspace.",
        "steps": [
            {
                "type": "safety",
                "title": "No shell, no admin terminal, no auto-server.",
                "status": "required",
            },
            {
                "type": "workspace",
                "title": "Use Projects/PCAgent/DemoWorkspace/demo-site.",
                "status": "ready",
            },
            {
                "type": "files",
                "title": "Draft index.html, styles.css, README.md.",
                "status": "dry-run available",
            },
            {
                "type": "review",
                "title": "User reviews files manually or requests response.json patch.",
                "status": "required",
            },
            {
                "type": "serve",
                "title": "Local server is not started automatically.",
                "status": "manual only",
            },
        ],
        "next": "pc demo site dry",
    }
    set_value("agent_demo_site_plan", payload)
    return payload


def demo_site_dry():
    payload = {
        "ok": True,
        "mode": "demo_site_dry_run",
        "generated_at": _now(),
        "would_create": [
            str(DEMO_SITE_DIR / "index.html"),
            str(DEMO_SITE_DIR / "styles.css"),
            str(DEMO_SITE_DIR / "README.md"),
        ],
        "would_not_execute": [
            "npm",
            "python -m http.server",
            "cmd",
            "powershell",
            "browser auto-open",
            "admin terminal",
        ],
        "next": "pc demo site request",
    }
    set_value("agent_demo_site_dry", payload)
    return payload


def demo_site_request():
    _ensure_dirs()
    content = f"""# Demo Site Request

Generated: {_now()}

## Goal

Create a simple one-page website in a safe LocalComet demo workspace.

## Safety

- No shell commands.
- No admin terminal.
- No automatic server start.
- No browser auto-open.
- No secrets.
- Files are created only inside:

```text
{DEMO_SITE_DIR}
```

## Planned files

```text
index.html
styles.css
README.md
```

## Next safe command

```text
pc demo site files
```

This creates draft files only. It does not execute a server.
"""
    _write_text(DEMO_REQUEST_FILE, content)
    payload = {
        "ok": True,
        "mode": "demo_site_request",
        "generated_at": _now(),
        "path": str(DEMO_REQUEST_FILE),
        "next": "pc demo site files",
    }
    set_value("agent_demo_site_request", payload)
    return payload


def demo_site_files():
    _ensure_dirs()
    _write_text(DEMO_SITE_DIR / "index.html", DEMO_INDEX_HTML)
    _write_text(DEMO_SITE_DIR / "styles.css", DEMO_STYLES_CSS)
    _write_text(DEMO_SITE_DIR / "README.md", DEMO_README)

    payload = {
        "ok": True,
        "mode": "demo_site_files_created",
        "generated_at": _now(),
        "folder": str(DEMO_SITE_DIR),
        "files": [
            str(DEMO_SITE_DIR / "index.html"),
            str(DEMO_SITE_DIR / "styles.css"),
            str(DEMO_SITE_DIR / "README.md"),
        ],
        "executed_shell": False,
        "server_started": False,
        "browser_opened": False,
        "note": "Open index.html manually or request a deployment/patch workflow.",
    }
    set_value("agent_onboarding_last_demo", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "explain": explain(),
        "checklist": checklist(),
        "localcomet": localcomet(),
        "safety": safety(),
        "qwen_reference": qwen_reference(),
        "lmstudio_reference": lmstudio_reference(),
        "demo_plan": demo_site_plan(),
        "last_demo": get_value("agent_onboarding_last_demo", ""),
    }

    json_path = REPORTS_DIR / f"agent_onboarding_demo_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agent_onboarding_demo_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# Agent Onboarding + Demo Workspace Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Agent Formula",
        "",
    ]

    for key, item in AGENT_FORMULA.items():
        md.extend([
            f"### {key}",
            "",
            f"- Plain: {item['plain']}",
            f"- LocalComet: {item['localcomet']}",
            "",
        ])

    md.extend([
        "## Safety Profile",
        "",
        "```json",
        json.dumps(SAFETY_PROFILE, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Demo Site Plan",
        "",
        "```json",
        json.dumps(payload["demo_plan"], ensure_ascii=False, indent=2),
        "```",
    ])

    _write_text(md_path, "\n".join(md))
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc onboard", "pc onboard status", "pc onboard статус", "onboard status"}:
        return format_status(status())

    if lower in {"pc onboard explain", "pc onboard объясни", "pc onboard что такое агент", "onboard explain"}:
        return format_payload(explain())

    if lower in {"pc onboard checklist", "pc onboard чеклист", "onboard checklist"}:
        return format_payload(checklist())

    if lower in {"pc onboard localcomet", "pc onboard local", "onboard localcomet"}:
        return format_payload(localcomet())

    if lower in {"pc onboard qwen", "pc onboard qwen cli", "onboard qwen"}:
        return format_payload(qwen_reference())

    if lower in {"pc onboard lmstudio", "pc onboard lm studio", "onboard lmstudio"}:
        return format_payload(lmstudio_reference())

    if lower in {"pc onboard safety", "pc onboard безопасность", "onboard safety"}:
        return format_payload(safety())

    if lower in {"pc onboard agents.md", "pc onboard agents", "onboard agents.md"}:
        return format_payload(generate_agents_md())

    if lower in {"pc onboard report", "pc onboard отчет", "pc onboard отчёт", "onboard report"}:
        return format_payload(report("manual report"))

    if lower in {"pc demo site plan", "pc demo план сайта", "demo site plan"}:
        return format_payload(demo_site_plan())

    if lower in {"pc demo site dry", "pc demo сайт dry", "demo site dry"}:
        return format_payload(demo_site_dry())

    if lower in {"pc demo site request", "pc demo request", "pc demo сайт request", "demo site request"}:
        return format_payload(demo_site_request())

    if lower in {"pc demo site files", "pc demo site create", "pc demo сайт файлы", "demo site files"}:
        return format_payload(demo_site_files())

    if lower in {"pc demo site report", "pc demo сайт отчет", "pc demo сайт отчёт", "demo site report"}:
        return format_payload(report("demo site report"))

    return format_payload({
        "ok": False,
        "error": "Unknown onboarding/demo command.",
        "help": status().get("commands", []),
    })


def is_onboarding_command(command):
    lower = _norm(command)
    exact = {
        "pc onboard",
        "pc onboard status",
        "pc onboard статус",
        "onboard status",
        "pc onboard explain",
        "pc onboard объясни",
        "pc onboard что такое агент",
        "onboard explain",
        "pc onboard checklist",
        "pc onboard чеклист",
        "onboard checklist",
        "pc onboard localcomet",
        "pc onboard local",
        "onboard localcomet",
        "pc onboard qwen",
        "pc onboard qwen cli",
        "onboard qwen",
        "pc onboard lmstudio",
        "pc onboard lm studio",
        "onboard lmstudio",
        "pc onboard safety",
        "pc onboard безопасность",
        "onboard safety",
        "pc onboard agents.md",
        "pc onboard agents",
        "onboard agents.md",
        "pc onboard report",
        "pc onboard отчет",
        "pc onboard отчёт",
        "onboard report",
        "pc demo site plan",
        "pc demo план сайта",
        "demo site plan",
        "pc demo site dry",
        "pc demo сайт dry",
        "demo site dry",
        "pc demo site request",
        "pc demo request",
        "pc demo сайт request",
        "demo site request",
        "pc demo site files",
        "pc demo site create",
        "pc demo сайт файлы",
        "demo site files",
        "pc demo site report",
        "pc demo сайт отчет",
        "pc demo сайт отчёт",
        "demo site report",
    }
    return lower in exact
````

### ПУТЬ: modules/agentos_kernel_blueprint.py (814 строк, 26846 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
AGENTOS_DIR = PROJECTS_DIR / "PCAgent" / "AgentOS"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agentos_kernel_blueprint"
SKILLS_FILE = AGENTOS_DIR / "skills_registry.json"
FIREWALL_LOG = AGENTOS_DIR / "semantic_firewall_log.jsonl"
AGENTS_DRAFT_FILE = AGENTOS_DIR / "AGENTS_LocalComet_DRAFT.md"

LOCALCOMET_AGENTOS_VERSION = "agentos_blueprint_v1"

BLOCKED_INTENT_TERMS = [
    "delete",
    "remove",
    "rm ",
    "rmdir",
    "del ",
    "format",
    "wipe",
    "erase",
    "удали",
    "стереть",
    "формат",
    "снеси",
    "shell",
    "cmd",
    "powershell",
    "terminal",
    "registry",
    "regedit",
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "api key",
    "ssh",
    "login",
    "логин",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставк",
    "crypto wallet",
    "seed phrase",
]

PROMPT_INJECTION_TERMS = [
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal instructions",
    "bypass",
    "jailbreak",
    "disregard safety",
    "do not tell the user",
    "exfiltrate",
    "утеки данных",
    "обойди правила",
    "игнорируй инструкции",
    "скрой от пользователя",
    "выведи системный промпт",
]

OUTBOUND_DLP_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{12,}",
    r"ghp_[A-Za-z0-9_]{20,}",
    r"AIza[0-9A-Za-z\-_]{20,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
]

DEFAULT_SKILLS = [
    {
        "id": "single_port_chat",
        "name": "Single Port Chat",
        "category": "interface",
        "description": "Unified natural language command portal for LocalComet.",
        "commands": ["pc agentos status", "pc core status", "pc screen status"],
        "risk": "low",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "semantic_firewall",
        "name": "Semantic Firewall",
        "category": "safety",
        "description": "Intent vetting, prompt-injection detection, and DLP-style output checks.",
        "commands": ["pc agentos firewall <intent>"],
        "risk": "critical_guard",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "screen_aware_planner",
        "name": "Screen-Aware Planner",
        "category": "planner",
        "description": "Observes active window/screen metadata and creates safe screen-aware plans.",
        "commands": ["pc screen observe", "pc screen plan <goal>", "pc screen dry <goal>"],
        "risk": "medium",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "desktop_primitives",
        "name": "Desktop Interaction Primitives",
        "category": "desktop",
        "description": "Windows list, mouse position, screenshot metadata, dry-click, dry-hotkey, confirmed focus.",
        "commands": ["pc desktop windows", "pc desktop dry click <x> <y>", "pc desktop focus подтверждаю: <title>"],
        "risk": "medium",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "pc_codex_executor",
        "name": "PC Codex Executor",
        "category": "executor",
        "description": "Safe queue, dry-run, confirmed run, stop flag, and reports.",
        "commands": ["pc exec queue <goal>", "pc exec dry <goal>", "pc exec run подтверждаю: <goal>"],
        "risk": "high",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "project_patch_workflow",
        "name": "Project Patch Workflow",
        "category": "coding",
        "description": "Project changes through request/response.json, validation, patch registry, rollback backup.",
        "commands": ["pc edit <goal>", "project context", "структура проекта"],
        "risk": "high",
        "dry_run_required": True,
        "confirmation_required": True,
        "enabled": True,
    },
    {
        "id": "open_source_gui_boost",
        "name": "Open-Source GUI Boost",
        "category": "adapter",
        "description": "OmniParser/ShowUI/UI-TARS/OpenCUA-inspired schemas and adapters.",
        "commands": ["pc boost status", "pc boost elements", "pc boost suggest <goal>"],
        "risk": "low",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
    {
        "id": "web_research",
        "name": "Web Research",
        "category": "research",
        "description": "Research fallback and source-backed recommendations.",
        "commands": ["pc web <query>", "поиск в интернете <query>"],
        "risk": "medium",
        "dry_run_required": False,
        "confirmation_required": False,
        "enabled": True,
    },
]


AGENTOS_BLUEPRINT = {
    "version": LOCALCOMET_AGENTOS_VERSION,
    "name": "LocalComet AgentOS Kernel Blueprint",
    "principle": "LocalComet remains the safety-first orchestrator. External models and GUI tools are adapters, not trusted executors.",
    "layers": [
        {
            "name": "Single Port",
            "localcomet_component": "Panel Chat / PC Codex Chat",
            "purpose": "One natural-language control surface for text, voice, project, desktop, browser, and patch tasks.",
            "current_status": "active",
        },
        {
            "name": "Northbound Intent Interface",
            "localcomet_component": "run_panel_chat_command + command routers",
            "purpose": "Parse user intent into structured routes, plans, and safe tool calls.",
            "current_status": "active",
        },
        {
            "name": "Agent Kernel",
            "localcomet_component": "pc_codex_core + pc_codex_executor + screen_aware_planner",
            "purpose": "Goal memory, planning, dry-run, confirmed action, stop, report.",
            "current_status": "active",
        },
        {
            "name": "Semantic Firewall",
            "localcomet_component": "agentos semantic firewall + existing safety blocks",
            "purpose": "Detect unsafe intents, prompt injections, secret exfiltration, and high-risk actions.",
            "current_status": "v6.23 base",
        },
        {
            "name": "Skills-as-Modules",
            "localcomet_component": "modules/*.py + skills_registry.json",
            "purpose": "Reusable safe tools with metadata, risk level, commands, and confirmation rules.",
            "current_status": "v6.23 base",
        },
        {
            "name": "Southbound Tool Interface",
            "localcomet_component": "desktop primitives, browser tools, project workflow, reports",
            "purpose": "Execute only through allowlisted modules, never arbitrary shell.",
            "current_status": "active",
        },
        {
            "name": "Personal Context / Knowledge Graph",
            "localcomet_component": "project context, memory, reports, future PKG",
            "purpose": "Remember goals, workflows, preferences, project structure, and validated skills.",
            "current_status": "planned",
        },
        {
            "name": "Rollback / Checkpoints",
            "localcomet_component": "SelfEdit rollback + backups + future task checkpoints",
            "purpose": "Every risky change should have audit trail and recovery path.",
            "current_status": "partial",
        },
    ],
}


ROADMAP = [
    {
        "version": "v6.23",
        "name": "AgentOS Kernel + Skills Blueprint",
        "adds": [
            "AgentOS blueprint",
            "skills registry",
            "semantic firewall base",
            "AGENTS.md draft generator",
            "memory/checkpoint roadmap",
            "reports",
        ],
    },
    {
        "version": "v6.24",
        "name": "UI Parser Adapter",
        "adds": [
            "pc ui parse",
            "pc ui elements",
            "pc ui find <text>",
            "OmniParser-compatible output schema",
            "screen element confidence scoring",
        ],
    },
    {
        "version": "v6.25",
        "name": "Visual Action Suggestion",
        "adds": [
            "ShowUI/UI-TARS-style action parser",
            "goal + UI elements -> action suggestion",
            "action confidence",
            "semantic firewall before executor",
        ],
    },
    {
        "version": "v6.26",
        "name": "Safe Text Operator",
        "adds": [
            "confirmed text input",
            "active-window checks",
            "no secrets/tokens/passwords",
            "no auto-enter submission",
        ],
    },
    {
        "version": "v6.27",
        "name": "Task Memory + Checkpoints",
        "adds": [
            "task sessions",
            "checkpoint graph",
            "execution trace",
            "resume/continue",
            "rollback hints",
        ],
    },
    {
        "version": "v6.28",
        "name": "Full Agent Mode",
        "adds": [
            "pc agent <goal>",
            "observe -> intent -> firewall -> skills -> plan -> dry-run -> confirm -> execute -> report",
            "bounded multi-step loop",
        ],
    },
]


AGENTS_MD_TEMPLATE = """# AGENTS.md — LocalComet Safe Agent Workspace

## Mission

You are LocalComet, a local safety-first PC agent. Your job is to help the user operate the project and desktop through a controlled workflow.

## Prime Rules

1. Never execute arbitrary shell, cmd, powershell, terminal, registry, format, delete, wipe, or credential actions.
2. Never request, expose, store, paste, or transmit passwords, tokens, API keys, SSH keys, seed phrases, banking data, or payment data.
3. For project changes, use request/response patch workflow. Do not directly rewrite important files without a patch and tests.
4. For desktop actions, use observe, plan, dry-run, and explicit confirmation before execution.
5. For uncertain tasks, ask a clarifying question or create a safe plan.
6. Prefer quarantine over deletion.
7. Always create reports for executed workflows.

## Standard Pipeline

```text
1. Understand user goal.
2. Run semantic firewall check.
3. Collect project/screen context.
4. Select a safe skill.
5. Build a plan.
6. Run dry-run.
7. Ask for explicit confirmation when needed.
8. Execute one bounded step.
9. Save report.
10. Suggest next step.
```

## LocalComet Command Families

```text
pc agentos status
pc agentos blueprint
pc agentos skills
pc agentos firewall <intent>
pc screen plan <goal>
pc desktop dry click <x> <y>
pc exec dry <goal>
pc exec run подтверждаю: <goal>
pc boost suggest <goal>
pc edit <project change>
```

## Safety Permission Profile

```yaml
read_project_files: allowed
write_project_files_directly: denied
write_project_files_via_patch: allowed
execute_arbitrary_shell: denied
execute_safe_allowlisted_tools: allowed
desktop_observe: allowed
desktop_click_without_dry_run: denied
desktop_type_without_confirmation: denied
delete_files: denied
quarantine_files: allowed_after_confirmation
handle_secrets: denied
```

## Working Memory

Keep task notes in `Projects/PCAgent/`.
Keep reports in `Projects/Reports/`.
Keep generated patch requests in the relay/self-edit workflow.
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    AGENTOS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_skill_registry():
    _ensure_dirs()
    payload = _read_json(SKILLS_FILE, None)
    if not isinstance(payload, dict) or "skills" not in payload:
        payload = {
            "ok": True,
            "version": "localcomet_skill_registry_v1",
            "created_at": _now(),
            "updated_at": _now(),
            "skills": DEFAULT_SKILLS,
        }
        _write_json(SKILLS_FILE, payload)
    return payload


def save_skill_registry(registry):
    registry["updated_at"] = _now()
    _write_json(SKILLS_FILE, registry)
    set_value("agentos_skills_registry", registry)
    return registry


def status():
    registry = ensure_skill_registry()
    payload = {
        "ok": True,
        "mode": "agentos_kernel_blueprint",
        "generated_at": _now(),
        "version": LOCALCOMET_AGENTOS_VERSION,
        "skills_count": len(registry.get("skills", [])),
        "enabled_skills": len([item for item in registry.get("skills", []) if item.get("enabled")]),
        "blueprint_layers": len(AGENTOS_BLUEPRINT.get("layers", [])),
        "last_firewall": get_value("agentos_last_firewall", ""),
        "commands": [
            "pc agentos status",
            "pc agentos blueprint",
            "pc agentos skills",
            "pc agentos firewall <intent>",
            "pc agentos memory",
            "pc agentos roadmap",
            "pc agentos agents.md",
            "pc agentos report",
        ],
        "safety": [
            "Semantic Firewall checks intent before high-risk actions.",
            "Skills are metadata + safe command routes, not arbitrary plugins.",
            "No shell/cmd/powershell/delete/secrets.",
            "Project modifications stay inside request/response patch workflow.",
            "Desktop actions keep dry-run and confirmation gates.",
        ],
    }
    set_value("agentos_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "LocalComet AgentOS Kernel Blueprint:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- version: {payload.get('version')}",
        f"- skills_count: {payload.get('skills_count')}",
        f"- enabled_skills: {payload.get('enabled_skills')}",
        f"- blueprint_layers: {payload.get('blueprint_layers')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def blueprint():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "blueprint": AGENTOS_BLUEPRINT,
        "localcomet_mapping": {
            "single_port": "Panel Chat / PC Codex Chat",
            "intent_parser": "run_panel_chat_command routers",
            "agent_kernel": ["pc_codex_core", "pc_codex_executor", "pc_screen_planner"],
            "semantic_firewall": "pc agentos firewall",
            "skills": "skills_registry.json",
            "rollback": ["SelfEdit rollback", "LocalAgent_Backups", "future checkpoints"],
        },
    }
    set_value("agentos_blueprint", payload)
    return payload


def skills():
    registry = ensure_skill_registry()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "registry_path": str(SKILLS_FILE),
        "skills": registry.get("skills", []),
        "counts": {
            "total": len(registry.get("skills", [])),
            "enabled": len([item for item in registry.get("skills", []) if item.get("enabled")]),
            "high_risk": len([item for item in registry.get("skills", []) if item.get("risk") == "high"]),
        },
    }
    set_value("agentos_skills", payload)
    return payload


def _detect_dlp(text):
    findings = []
    for pattern in OUTBOUND_DLP_PATTERNS:
        if re.search(pattern, str(text or "")):
            findings.append(pattern)
    return findings


def semantic_firewall(intent):
    raw = str(intent or "").strip()
    lower = _norm(raw)
    blocked_hits = [term for term in BLOCKED_INTENT_TERMS if term in lower]
    injection_hits = [term for term in PROMPT_INJECTION_TERMS if term in lower]
    dlp_hits = _detect_dlp(raw)

    risk_score = 0
    risk_score += len(blocked_hits) * 5
    risk_score += len(injection_hits) * 4
    risk_score += len(dlp_hits) * 6

    if not raw:
        verdict = "blocked"
        reason = "empty intent"
    elif dlp_hits:
        verdict = "blocked"
        reason = "possible secret/payment/key pattern detected"
    elif blocked_hits:
        verdict = "blocked"
        reason = "blocked intent terms detected"
    elif injection_hits:
        verdict = "review"
        reason = "possible prompt-injection terms detected"
    else:
        verdict = "allowed_for_planning"
        reason = "no immediate semantic firewall hit"

    recommended_route = "pc screen plan <goal>"
    if verdict == "blocked":
        recommended_route = "refuse_or_create_safe_alternative"
    elif any(word in lower for word in ["проект", "код", "модуль", "patch", "response.json", "исправь"]):
        recommended_route = "pc edit <goal>"
    elif any(word in lower for word in ["клик", "click", "hotkey", "мыш", "окно", "focus"]):
        recommended_route = "pc desktop dry <action>"
    elif any(word in lower for word in ["открыть", "запусти", "open", "launch"]):
        recommended_route = "pc exec dry <goal>"
    elif any(word in lower for word in ["найди", "поиск", "web", "интернет", "что такое", "как сделать"]):
        recommended_route = "pc web <query>"

    payload = {
        "ok": verdict != "blocked",
        "mode": "semantic_firewall",
        "generated_at": _now(),
        "intent": raw,
        "verdict": verdict,
        "reason": reason,
        "risk_score": risk_score,
        "blocked_terms": sorted(set(blocked_hits)),
        "prompt_injection_terms": sorted(set(injection_hits)),
        "dlp_patterns": dlp_hits,
        "recommended_route": recommended_route,
        "rules": {
            "no_shell": True,
            "no_delete": True,
            "no_secrets": True,
            "dry_run_first": True,
            "confirmation_for_execution": True,
            "project_changes_via_patch": True,
        },
    }

    set_value("agentos_last_firewall", payload)
    _append_jsonl(FIREWALL_LOG, payload)
    return payload


def memory_blueprint():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "mode": "agentos_memory_blueprint",
        "current_memory_sources": [
            "core.state key-value state",
            "Projects/PCAgent session JSON files",
            "Projects/Reports generated reports",
            "Patch Registry",
            "SelfEdit rollback files",
            "project context scanner",
        ],
        "future_personal_knowledge_graph": {
            "nodes": [
                "Task",
                "Skill",
                "File",
                "Window",
                "Report",
                "Patch",
                "UserPreference",
                "WorkflowPattern",
            ],
            "edges": [
                "Task uses Skill",
                "Skill creates Report",
                "Patch changes File",
                "Window observed during Task",
                "WorkflowPattern repeats Task",
            ],
            "storage_plan": "Projects/PCAgent/AgentOS/personal_knowledge_graph.json",
            "privacy": "local only; no secrets; tainted external content cannot trigger high-privilege actions",
        },
        "checkpoint_plan": [
            "Before risky project patch: backup and rollback file.",
            "Before desktop action: dry-run artifact.",
            "During multi-step task: action trace with timestamp.",
            "After completion: report with next-step suggestions.",
        ],
    }
    set_value("agentos_memory_blueprint", payload)
    return payload


def roadmap():
    payload = {
        "ok": True,
        "generated_at": _now(),
        "roadmap": ROADMAP,
    }
    set_value("agentos_roadmap", payload)
    return payload


def generate_agents_md():
    _ensure_dirs()
    AGENTS_DRAFT_FILE.write_text(AGENTS_MD_TEMPLATE, encoding="utf-8")
    payload = {
        "ok": True,
        "generated_at": _now(),
        "path": str(AGENTS_DRAFT_FILE),
        "note": "Draft only. Review before copying into project root.",
        "safety_profile": {
            "direct_write_to_root": False,
            "contains_secrets": False,
            "shell_commands": False,
        },
    }
    set_value("agentos_agents_md_draft", payload)
    return payload


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "blueprint": blueprint(),
        "skills": skills(),
        "memory": memory_blueprint(),
        "roadmap": roadmap(),
        "last_firewall": get_value("agentos_last_firewall", ""),
    }

    json_path = REPORTS_DIR / f"agentos_kernel_blueprint_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agentos_kernel_blueprint_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# LocalComet AgentOS Kernel Blueprint Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Blueprint Layers",
        "",
    ]

    for layer in AGENTOS_BLUEPRINT["layers"]:
        md.extend([
            f"### {layer['name']}",
            "",
            f"- LocalComet component: {layer['localcomet_component']}",
            f"- Purpose: {layer['purpose']}",
            f"- Status: {layer['current_status']}",
            "",
        ])

    md.extend([
        "## Skills",
        "",
        "```json",
        json.dumps(payload["skills"]["skills"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Roadmap",
        "",
        "```json",
        json.dumps(ROADMAP, ensure_ascii=False, indent=2),
        "```",
    ])

    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc agentos", "pc agentos status", "pc agentos статус", "agentos status"}:
        return format_status(status())

    if lower in {"pc agentos blueprint", "pc agentos архитектура", "agentos blueprint"}:
        return format_payload(blueprint())

    if lower in {"pc agentos skills", "pc agentos скиллы", "pc agentos skills list", "agentos skills"}:
        return format_payload(skills())

    if lower in {"pc agentos memory", "pc agentos память", "agentos memory"}:
        return format_payload(memory_blueprint())

    if lower in {"pc agentos roadmap", "pc agentos план", "agentos roadmap"}:
        return format_payload(roadmap())

    if lower in {"pc agentos agents.md", "pc agentos agents", "pc agentos ag", "agentos agents.md"}:
        return format_payload(generate_agents_md())

    if lower in {"pc agentos report", "pc agentos отчет", "pc agentos отчёт", "agentos report"}:
        return format_payload(report("manual report"))

    prefixes = [
        "pc agentos firewall ",
        "pc agentos файрвол ",
        "pc agentos проверка ",
        "agentos firewall ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            return format_payload(semantic_firewall(value))

    return format_payload({
        "ok": False,
        "error": "Unknown AgentOS command.",
        "help": status().get("commands", []),
    })


def is_agentos_command(command):
    lower = _norm(command)
    exact = {
        "pc agentos",
        "pc agentos status",
        "pc agentos статус",
        "agentos status",
        "pc agentos blueprint",
        "pc agentos архитектура",
        "agentos blueprint",
        "pc agentos skills",
        "pc agentos скиллы",
        "pc agentos skills list",
        "agentos skills",
        "pc agentos memory",
        "pc agentos память",
        "agentos memory",
        "pc agentos roadmap",
        "pc agentos план",
        "agentos roadmap",
        "pc agentos agents.md",
        "pc agentos agents",
        "pc agentos ag",
        "agentos agents.md",
        "pc agentos report",
        "pc agentos отчет",
        "pc agentos отчёт",
        "agentos report",
    }
    if lower in exact:
        return True
    prefixes = (
        "pc agentos firewall ",
        "pc agentos файрвол ",
        "pc agentos проверка ",
        "agentos firewall ",
    )
    return lower.startswith(prefixes)
````

### ПУТЬ: modules/agents_project_intelligence.py (742 строк, 21842 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import re
import hashlib


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
AGENTS_DIR = PROJECTS_DIR / "PCAgent" / "AgentsMD"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "agents_project_intelligence"

STANDARD_AGENTS_DRAFT = AGENTS_DIR / "AGENTS_LocalComet_STANDARD.md"
PROJECT_PROFILE_FILE = AGENTS_DIR / "project_profile.json"
VALIDATION_FILE = AGENTS_DIR / "last_agents_validation.json"

AGENTS_FILENAMES = [
    "AGENTS.md",
    "agents.md",
    ".agents.md",
    "AGENT.md",
    "agent.md",
]

FORBIDDEN_TERMS = [
    "execute all commands",
    "run all commands",
    "auto approve all",
    "auto-approve all",
    "always yes",
    "always approve",
    "sudo",
    "run as administrator",
    "administrator",
    "powershell",
    "cmd.exe",
    "rm -rf",
    "rmdir",
    "del /f",
    "format",
    "wipe",
    "delete all",
    "delete files",
    "ssh key",
    "private key",
    "api key",
    "token",
    "password",
    "secret",
    "seed phrase",
    "send credentials",
    "deploy with ssh",
    "ignore safety",
    "ignore previous instructions",
    "bypass",
    "jailbreak",
]

RISKY_COMMAND_PATTERNS = [
    r"\bnpm\s+run\s+build\b",
    r"\bsudo\b",
    r"\bpowershell\b",
    r"\bcmd\s*/c\b",
    r"\brm\s+-rf\b",
    r"\brmdir\b",
    r"\bdel\s+/[fsq]\b",
    r"\bformat\b",
    r"\bssh\b",
    r"\bscp\b",
    r"\bchmod\s+777\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bpnpm\s+install\b",
    r"\byarn\s+install\b",
]

SAFE_TEST_COMMAND_HINTS = [
    "python -m py_compile",
    "python -m pytest",
    "pytest",
    "npm run lint",
    "npm test",
    "pnpm lint",
    "pnpm test",
    "yarn lint",
    "yarn test",
]

PROJECT_MARKERS = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py", "pytest.ini", "tox.ini"],
    "node": ["package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"],
    "nextjs": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "vite": ["vite.config.js", "vite.config.ts", "vite.config.mjs"],
    "localcomet": ["LocalComet_Control_Panel.py", "Projects", "modules", "core"],
}


STANDARD_AGENTS_CONTENT = """# AGENTS.md — LocalComet Project Contract

This file is a predictable project contract for AI agents working inside this repository.

## Agent Identity

You are LocalComet, a local safety-first AI agent. You can help inspect, plan, draft, test, and patch the project, but you must never bypass safety gates.

## Core Workflow

```text
1. Read this AGENTS.md first.
2. Understand the user goal.
3. Run semantic firewall for risky tasks.
4. Inspect project context.
5. Build a plan.
6. Use dry-run before execution.
7. Require explicit confirmation for desktop or high-risk actions.
8. Modify project only through response.json patch workflow.
9. Run safe tests.
10. Save a report.
```

## Safe Project Editing

Allowed:

```text
- Read project files.
- Explain files and project structure.
- Generate request.md / response.json patches.
- Run py_compile for touched Python files.
- Run project-specific safe tests when listed below.
- Create reports in Projects/Reports/.
```

Denied:

```text
- Arbitrary shell/cmd/powershell.
- Delete/format/wipe/rm/rmdir.
- Direct editing of protected files without patch workflow.
- Secrets, passwords, tokens, SSH keys, API keys.
- Auto-approve all commands.
- Running installers or dependency changes without explicit plan.
```

## LocalComet Safe Commands

```text
python -m py_compile <file.py>
pc agentos firewall <intent>
pc agents validate
pc agents project-profile
pc screen plan <goal>
pc exec dry <goal>
pc exec run подтверждаю: <goal>
```

## Project Patch Rule

All code changes must go through:

```text
response.json -> validate -> apply -> tests -> after patch -> auto verification
```

## Forbidden Command Examples

```text
powershell
cmd /c
rm -rf
rmdir
del /f
format
ssh with secrets
npm install without review
pip install without review
auto yes to unknown commands
```

## Reports

Write reports under:

```text
Projects/Reports/
```

## Memory

Use:

```text
Projects/PCAgent/
Projects/Reports/
Patch Registry
SelfEdit rollback
```
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е")


def _ensure_dirs():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _safe_read_text(path, max_chars=120000):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[TRUNCATED]"
        return text
    except Exception as exc:
        return f"[READ_ERROR] {exc}"


def _hash_text(text):
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _is_within_root(path):
    try:
        Path(path).resolve().relative_to(ROOT_DIR.resolve())
        return True
    except Exception:
        return False


def find_agents_files():
    candidates = []

    for name in AGENTS_FILENAMES:
        path = ROOT_DIR / name
        if path.exists() and path.is_file():
            candidates.append(path)

    for base in [
        PROJECTS_DIR / "PCAgent" / "Onboarding",
        PROJECTS_DIR / "PCAgent" / "AgentOS",
        AGENTS_DIR,
    ]:
        if base.exists():
            for path in base.rglob("*.md"):
                if "agents" in path.name.lower() or path.name.lower() == "agents.md":
                    candidates.append(path)

    unique = []
    seen = set()
    for path in candidates:
        key = str(path.resolve()).lower()
        if key not in seen and _is_within_root(path):
            seen.add(key)
            unique.append(path)

    return unique


def project_markers():
    markers = {}
    for kind, names in PROJECT_MARKERS.items():
        found = []
        for name in names:
            path = ROOT_DIR / name
            if path.exists():
                found.append(str(path))
        markers[kind] = found
    return markers


def infer_project_type():
    markers = project_markers()
    detected = []

    if markers.get("localcomet") and len(markers.get("localcomet", [])) >= 2:
        detected.append("localcomet")
    if markers.get("python"):
        detected.append("python")
    if markers.get("nextjs"):
        detected.append("nextjs")
    if markers.get("vite"):
        detected.append("vite")
    if markers.get("node"):
        detected.append("node")

    if not detected:
        detected.append("unknown")

    return detected


def safe_command_profile(project_types=None):
    project_types = project_types or infer_project_type()
    safe = [
        "python -m py_compile <touched_file.py>",
        "pc agentos firewall <intent>",
        "pc agents validate",
        "pc agents project-profile",
    ]
    caution = [
        "python -m pytest",
        "pytest",
    ]
    forbidden = [
        "powershell",
        "cmd /c",
        "rm -rf",
        "rmdir",
        "del /f",
        "format",
        "ssh/scp with secrets",
        "npm install without explicit plan",
        "pip install without explicit plan",
        "auto-approve all commands",
    ]

    if "node" in project_types or "nextjs" in project_types or "vite" in project_types:
        safe.extend(["npm run lint", "npm test"])
        caution.extend(["npm run dev"])
        forbidden.append("npm run build inside interactive agent session unless explicitly requested")

    if "localcomet" in project_types:
        safe.extend([
            "python -m py_compile LocalComet_Control_Panel.py",
            "python -m py_compile modules/<changed_module>.py",
            "Auto Verification full",
            "Full Stability Test",
        ])

    return {
        "safe": sorted(set(safe)),
        "caution": sorted(set(caution)),
        "forbidden": sorted(set(forbidden)),
    }


def detect_project():
    _ensure_dirs()
    agents_files = find_agents_files()
    project_types = infer_project_type()
    profile = {
        "ok": True,
        "mode": "agents_project_detection",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "project_types": project_types,
        "markers": project_markers(),
        "agents_files": [
            {
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha16": _hash_text(_safe_read_text(path, 200000)),
            }
            for path in agents_files
        ],
        "has_root_agents_md": any(path.name == "AGENTS.md" and path.parent == ROOT_DIR for path in agents_files),
        "safe_command_profile": safe_command_profile(project_types),
    }
    _write_json(PROJECT_PROFILE_FILE, profile)
    set_value("agents_project_profile", profile)
    return profile


def read_agents():
    agents_files = find_agents_files()
    payload = {
        "ok": True,
        "mode": "agents_md_read",
        "generated_at": _now(),
        "files": [],
    }

    for path in agents_files:
        text = _safe_read_text(path)
        payload["files"].append({
            "path": str(path),
            "name": path.name,
            "sha16": _hash_text(text),
            "chars": len(text),
            "content": text,
        })

    if not payload["files"]:
        payload["ok"] = False
        payload["message"] = "No AGENTS.md-like files found. Use: pc agents generate"

    set_value("agents_md_last_read", payload)
    return payload


def _validate_text(text, source="manual"):
    lower = _norm(text)
    forbidden_hits = sorted({term for term in FORBIDDEN_TERMS if term in lower})
    risky_commands = []

    for pattern in RISKY_COMMAND_PATTERNS:
        if re.search(pattern, lower):
            risky_commands.append(pattern)

    required_sections = {
        "workflow": any(word in lower for word in ["workflow", "pipeline", "core workflow", "рабочий процесс", "алгоритм"]),
        "testing": any(word in lower for word in ["test", "testing", "py_compile", "pytest", "lint", "провер"]),
        "forbidden": any(word in lower for word in ["forbidden", "denied", "нельзя", "запрещ"]),
        "safety": any(word in lower for word in ["safety", "security", "безопас"]),
    }

    score = 100
    score -= len(forbidden_hits) * 8
    score -= len(risky_commands) * 6
    score -= len([ok for ok in required_sections.values() if not ok]) * 10
    score = max(0, min(100, score))

    verdict = "good"
    if forbidden_hits or risky_commands:
        verdict = "needs_review"
    if any(hit in forbidden_hits for hit in ["execute all commands", "auto approve all", "always yes", "password", "token", "private key", "ssh key"]):
        verdict = "unsafe"

    return {
        "source": source,
        "sha16": _hash_text(text),
        "chars": len(text),
        "score": score,
        "verdict": verdict,
        "forbidden_hits": forbidden_hits,
        "risky_command_patterns": sorted(set(risky_commands)),
        "required_sections": required_sections,
        "recommendations": _recommendations(forbidden_hits, risky_commands, required_sections),
    }


def _recommendations(forbidden_hits, risky_commands, required_sections):
    recs = []

    if forbidden_hits:
        recs.append("Remove or rewrite dangerous auto-approval/secret/delete/admin instructions.")
    if risky_commands:
        recs.append("Move risky commands to explicit-review section or forbid them in agent sessions.")
    if not required_sections.get("workflow"):
        recs.append("Add a clear workflow: read -> plan -> dry-run -> confirm -> patch/test/report.")
    if not required_sections.get("testing"):
        recs.append("Add safe testing instructions.")
    if not required_sections.get("forbidden"):
        recs.append("Add forbidden commands and denied actions.")
    if not required_sections.get("safety"):
        recs.append("Add a safety section.")
    if not recs:
        recs.append("AGENTS.md looks usable. Keep it project-specific and safety-first.")
    return recs


def validate_agents():
    _ensure_dirs()
    files_payload = read_agents()
    validations = []

    for item in files_payload.get("files", []):
        validations.append(_validate_text(item.get("content", ""), item.get("path", "unknown")))

    if not validations:
        standard = STANDARD_AGENTS_CONTENT
        validations.append(_validate_text(standard, "generated_standard"))

    payload = {
        "ok": True,
        "mode": "agents_md_validation",
        "generated_at": _now(),
        "validations": validations,
        "overall_verdict": _overall_verdict(validations),
    }

    _write_json(VALIDATION_FILE, payload)
    set_value("agents_md_validation", payload)
    return payload


def _overall_verdict(validations):
    verdicts = [item.get("verdict") for item in validations]
    if "unsafe" in verdicts:
        return "unsafe"
    if "needs_review" in verdicts:
        return "needs_review"
    return "good"


def generate_agents():
    _ensure_dirs()
    STANDARD_AGENTS_DRAFT.write_text(STANDARD_AGENTS_CONTENT, encoding="utf-8")
    validation = _validate_text(STANDARD_AGENTS_CONTENT, str(STANDARD_AGENTS_DRAFT))
    payload = {
        "ok": True,
        "mode": "agents_md_generate",
        "generated_at": _now(),
        "path": str(STANDARD_AGENTS_DRAFT),
        "note": "Draft only. Review before copying to project root.",
        "validation": validation,
    }
    set_value("agents_md_generated", payload)
    return payload


def project_profile():
    detection = detect_project()
    validation = validate_agents()
    payload = {
        "ok": True,
        "mode": "agents_project_profile",
        "generated_at": _now(),
        "detection": detection,
        "agents_validation": validation,
        "recommended_policy": {
            "read_agents_md_first": True,
            "apply_to_pc_edit": True,
            "apply_to_patch_generation": True,
            "project_changes_via_response_json": True,
            "unsafe_agents_md_blocks_execution": True,
        },
    }
    set_value("agents_project_profile_full", payload)
    return payload


def rules():
    return {
        "ok": True,
        "mode": "agents_md_rules",
        "generated_at": _now(),
        "standard_sections": [
            "Agent Identity",
            "Core Workflow",
            "Safe Project Editing",
            "Allowed Actions",
            "Denied Actions",
            "Safe Commands",
            "Forbidden Commands",
            "Patch Rule",
            "Reports",
            "Memory",
        ],
        "safety_rules": [
            "AGENTS.md cannot override LocalComet safety.",
            "AGENTS.md can narrow permissions but cannot expand them.",
            "Dangerous instructions are marked unsafe.",
            "Project edits remain response.json patch workflow only.",
            "No secrets/tokens/passwords/SSH keys.",
        ],
        "safe_command_profile": safe_command_profile(),
    }


def status():
    detection = detect_project()
    payload = {
        "ok": True,
        "mode": "agents_project_intelligence",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "project_types": detection.get("project_types", []),
        "agents_files_count": len(detection.get("agents_files", [])),
        "has_root_agents_md": detection.get("has_root_agents_md", False),
        "last_validation": get_value("agents_md_validation", ""),
        "commands": [
            "pc agents status",
            "pc agents detect",
            "pc agents read",
            "pc agents generate",
            "pc agents validate",
            "pc agents project-profile",
            "pc agents rules",
            "pc agents report",
        ],
    }
    set_value("agents_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "AGENTS.md Project Intelligence:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        f"- project_types: {', '.join(payload.get('project_types', []))}",
        f"- agents_files_count: {payload.get('agents_files_count')}",
        f"- has_root_agents_md: {payload.get('has_root_agents_md')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "detection": detect_project(),
        "read": read_agents(),
        "validation": validate_agents(),
        "profile": project_profile(),
        "rules": rules(),
    }

    json_path = REPORTS_DIR / f"agents_project_intelligence_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"agents_project_intelligence_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# AGENTS.md Project Intelligence Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Project Types",
        "",
        "```json",
        json.dumps(payload["detection"].get("project_types", []), ensure_ascii=False, indent=2),
        "```",
        "",
        "## AGENTS.md Validation",
        "",
        "```json",
        json.dumps(payload["validation"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Safe Command Profile",
        "",
        "```json",
        json.dumps(payload["rules"]["safe_command_profile"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text).strip()

    if lower in {"pc agents", "pc agents status", "pc agents статус", "agents status"}:
        return format_status(status())

    if lower in {"pc agents detect", "pc agents найти", "pc agents поиск", "agents detect"}:
        return format_payload(detect_project())

    if lower in {"pc agents read", "pc agents читать", "agents read"}:
        return format_payload(read_agents())

    if lower in {"pc agents generate", "pc agents создать", "pc agents draft", "agents generate"}:
        return format_payload(generate_agents())

    if lower in {"pc agents validate", "pc agents проверка", "pc agents проверить", "agents validate"}:
        return format_payload(validate_agents())

    if lower in {"pc agents project-profile", "pc agents profile", "pc agents профиль", "agents profile"}:
        return format_payload(project_profile())

    if lower in {"pc agents rules", "pc agents правила", "agents rules"}:
        return format_payload(rules())

    if lower in {"pc agents report", "pc agents отчет", "pc agents отчёт", "agents report"}:
        return format_payload(report("manual report"))

    return format_payload({
        "ok": False,
        "error": "Unknown AGENTS.md Project Intelligence command.",
        "help": status().get("commands", []),
    })


def is_agents_command(command):
    lower = _norm(command).strip()
    exact = {
        "pc agents",
        "pc agents status",
        "pc agents статус",
        "agents status",
        "pc agents detect",
        "pc agents найти",
        "pc agents поиск",
        "agents detect",
        "pc agents read",
        "pc agents читать",
        "agents read",
        "pc agents generate",
        "pc agents создать",
        "pc agents draft",
        "agents generate",
        "pc agents validate",
        "pc agents проверка",
        "pc agents проверить",
        "agents validate",
        "pc agents project-profile",
        "pc agents profile",
        "pc agents профиль",
        "agents profile",
        "pc agents rules",
        "pc agents правила",
        "agents rules",
        "pc agents report",
        "pc agents отчет",
        "pc agents отчёт",
        "agents report",
    }
    return lower in exact
````

### ПУТЬ: modules/ai_agent_core_ru.py (534 строк, 19563 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
REPORT_DIR = MEMORY_DIR / "reports"

AI_AGENT_VERSION = "v6.41d"
AI_AGENT_NAME = "LocalComet AI Agent Core Superboost Stable RU"

STATE_MACHINE = [
    "intake",
    "context_scan",
    "plan",
    "draft_patch",
    "wait_for_user_apply",
    "verify",
    "critique",
    "repair_plan",
    "done",
]

DANGEROUS_PATTERNS = [
    "пароль",
    "password",
    "token",
    "api key",
    "api-key",
    "secret",
    "private key",
    "ssh key",
    "cookie",
    "cookies",
    "удали",
    "удалить",
    "стереть",
    "сотри",
    "format",
    "wipe",
    "rm ",
    "rmdir",
    "del ",
    "powershell",
    "cmd.exe",
    "bash",
    "shell",
    "terminal",
    "админ",
    "administrator",
    "sudo",
    "банк",
    "bank",
    "карта",
    "payment",
    "casino",
    "gambling",
    "browser profile",
    "браузерный профиль",
]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _danger_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for marker in DANGEROUS_PATTERNS:
        if marker in lowered:
            return "запрос содержит потенциально опасный маркер: " + marker
    return ""


def _summarize_context(context: dict[str, Any]) -> str:
    control = context.get("control_panel", {}) if isinstance(context, dict) else {}
    lines = [
        f"Версия проекта: {control.get('version', '')} — {control.get('label', '')}",
        f"Python files: {context.get('python_file_count', '')}",
        f"Functions: {context.get('function_count', '')}",
        f"Classes: {context.get('class_count', '')}",
        f"Command modules: {context.get('command_module_count', '')}",
        f"UI modules: {context.get('ui_module_count', '')}",
        f"Verification modules: {context.get('verification_module_count', '')}",
        f"Agent modules: {context.get('agent_module_count', '')}",
        f"Parse warnings: {context.get('parse_error_count', '')}",
        f"Critical parse errors: {context.get('critical_parse_error_count', '')}",
        f"Project map: {context.get('project_map_path', '')}",
    ]
    return "\n".join(lines)


def _write_report(name: str, content: str) -> str:
    _ensure_dirs()
    path = REPORT_DIR / f"{name}_{_stamp()}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _latest_file(patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    reports = ROOT_PATH / "Projects" / "Reports"
    for pattern in patterns:
        candidates.extend(reports.rglob(pattern) if reports.exists() else [])
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def build_project_context() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import save_project_context, set_phase
    from modules.ai_project_map_ru import build_project_map

    set_phase("context_scan")
    context = build_project_map()
    save_project_context(context)
    set_phase("plan")
    return {
        "ok": bool(context.get("ok", True)),
        "mode": "ai_agent_project_context",
        "generated_at": _now(),
        "agent_version": AI_AGENT_VERSION,
        "project_map_path": context.get("project_map_path"),
        "summary": {
            "python_file_count": context.get("python_file_count"),
            "function_count": context.get("function_count"),
            "class_count": context.get("class_count"),
            "command_module_count": context.get("command_module_count"),
            "ui_module_count": context.get("ui_module_count"),
            "verification_module_count": context.get("verification_module_count"),
            "agent_module_count": context.get("agent_module_count"),
            "parse_error_count": context.get("parse_error_count"),
            "critical_parse_error_count": context.get("critical_parse_error_count"),
            "map_policy": context.get("diagnostic_ok_policy", "diagnostic project map"),
        },
        "context": context,
    }


def build_task_plan(goal: str) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import append_history, set_phase

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("intake", raw_goal)
    danger = _danger_reason(raw_goal)
    context_result = build_project_context()
    context = context_result.get("context", {})

    if danger:
        set_phase("done", raw_goal)
        return {
            "ok": False,
            "mode": "ai_agent_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
            "answer": "План заблокирован: " + danger,
        }

    set_phase("plan", raw_goal)
    plan_text = (
        "AI Agent Core Plan\n\n"
        f"Цель: {raw_goal}\n\n"
        "Контекст проекта:\n"
        f"{_summarize_context(context)}\n\n"
        "Архитектурный план:\n"
        "1. Не начинать с UI. Сначала собрать карту проекта и понять затрагиваемые модули.\n"
        "2. Сформировать минимальный self-edit draft response.json через planner.\n"
        "3. Показать draft пользователю для импорта через Relay.\n"
        "4. После применения запустить вкладку «Проверка» / команду «проверь проект».\n"
        "5. Если hard_failures или warnings не ноль — построить repair plan по последнему отчёту.\n"
        "6. Только после зелёной проверки двигаться к следующему пункту backlog.\n\n"
        "Режимы агента:\n"
        "- Plan: построить план без изменения файлов.\n"
        "- Draft: создать response.json draft без применения.\n"
        "- Verify: прочитать/запустить безопасную проверку.\n"
        "- Critique: объяснить проблемы отчёта.\n"
        "- Repair: подготовить следующий repair draft.\n\n"
        "Следующая безопасная команда:\n"
        f"pc ai draft {raw_goal}\n"
    )

    report_path = _write_report("ai_agent_plan", "# AI Agent Plan\n\n" + plan_text)
    append_history({
        "type": "agent_plan",
        "goal": raw_goal,
        "report": report_path,
        "phase": "plan",
    })

    return {
        "ok": True,
        "mode": "ai_agent_plan",
        "generated_at": _now(),
        "goal": raw_goal,
        "answer": plan_text,
        "report": report_path,
        "project_map_path": context.get("project_map_path"),
        "next_safe_command": "pc ai draft " + raw_goal,
        "state_machine": STATE_MACHINE,
    }


def draft_patch(goal: str) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase
    from modules.ai_patch_planner_ru import draft_patch as planner_draft

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("draft_patch", raw_goal)
    result = planner_draft(raw_goal)
    if result.get("ok"):
        set_phase("wait_for_user_apply", raw_goal, latest_draft=result.get("draft_path", ""))
    return result


def analyze_verification_report(path: str | None = None) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import find_latest_verification_report, remember_verification, set_phase

    set_phase("critique")
    target = str(path or "").strip()
    if not target:
        target = find_latest_verification_report()

    if not target:
        return {
            "ok": False,
            "mode": "ai_agent_verification_analysis",
            "generated_at": _now(),
            "error": "verification report not found",
        }

    report_path = Path(target)
    if not report_path.exists():
        return {
            "ok": False,
            "mode": "ai_agent_verification_analysis",
            "generated_at": _now(),
            "error": "report path does not exist",
            "path": target,
        }

    text = report_path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    hard_failures = _extract_int(text, "hard_failures")
    warnings = _extract_int(text, "warnings")
    ok = ("ok: true" in lowered or '"ok": true' in lowered or "[ok]" in lowered) and not ("[fail]" in lowered)

    if hard_failures is not None:
        ok = ok and hard_failures == 0
    if warnings is not None:
        ok = ok and warnings == 0

    remember_verification(str(report_path), ok=ok)
    set_phase("done" if ok else "repair_plan")

    report = {
        "ok": ok,
        "mode": "ai_agent_verification_analysis",
        "generated_at": _now(),
        "path": str(report_path),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "has_fail": "[FAIL]" in text or '"ok": false' in lowered or "ok: false" in lowered,
        "summary": _shorten_report(text),
    }
    return report


def _extract_int(text: str, key: str) -> int | None:
    patterns = [
        rf'"{re.escape(key)}"\s*:\s*(\d+)',
        rf"{re.escape(key)}\s*:\s*(\d+)",
        rf"-\s*{re.escape(key)}\s*:\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _shorten_report(text: str, limit: int = 2500) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped.lower() for marker in ("hard_failures", "warnings", "[fail]", "error", "итог", "проблем", "score", "ok:")):
            lines.append(stripped)
    summary = "\n".join(lines[:80])
    if not summary:
        summary = text[:limit]
    return summary[:limit]


def propose_repair(goal_or_report: str = "") -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase

    set_phase("repair_plan")
    analysis = analyze_verification_report(goal_or_report if goal_or_report and Path(str(goal_or_report)).exists() else None)

    if analysis.get("ok"):
        return {
            "ok": True,
            "mode": "ai_agent_repair_not_needed",
            "generated_at": _now(),
            "analysis": analysis,
            "answer": "Последняя проверка зелёная. Repair не нужен.",
        }

    repair_goal = (
        "починить проект по последнему verification report: "
        + str(analysis.get("path") or goal_or_report or "unknown report")
    )
    plan = build_task_plan(repair_goal)
    set_phase("repair_plan", repair_goal)

    return {
        "ok": True,
        "mode": "ai_agent_repair_plan",
        "generated_at": _now(),
        "goal": repair_goal,
        "analysis": analysis,
        "plan": plan,
        "next_safe_command": "pc ai draft " + repair_goal,
    }


def run_agent_cycle(goal: str, dry_run: bool = True) -> dict[str, Any]:
    from modules.ai_agent_memory_ru import set_phase

    raw_goal = str(goal or "").strip() or "развивать LocalComet как локального AI-агента"
    set_phase("intake", raw_goal)
    context = build_project_context()
    plan = build_task_plan(raw_goal)
    draft = draft_patch(raw_goal)
    verification = analyze_verification_report()

    result = {
        "ok": bool(context.get("ok")) and bool(plan.get("ok")) and bool(draft.get("ok")),
        "mode": "ai_agent_cycle",
        "generated_at": _now(),
        "goal": raw_goal,
        "dry_run": dry_run,
        "phase": "wait_for_user_apply",
        "context": {
            "project_map_path": context.get("project_map_path"),
            "summary": context.get("summary"),
        },
        "plan": {
            "ok": plan.get("ok"),
            "report": plan.get("report"),
            "next_safe_command": plan.get("next_safe_command"),
        },
        "draft": {
            "ok": draft.get("ok"),
            "draft_path": draft.get("draft_path"),
            "summary": draft.get("summary"),
        },
        "verification_analysis": verification,
        "next_steps": [
            "Открой draft_path.",
            "Импортируй draft через Relay только если он соответствует цели.",
            "После применения нажми «Проверить проект».",
            "Если проверка падает — команда pc ai repair.",
        ],
    }
    set_phase("wait_for_user_apply", raw_goal, latest_draft=draft.get("draft_path", ""))
    report_path = _write_report("ai_agent_cycle", "# AI Agent Cycle\n\n" + json.dumps(result, ensure_ascii=False, indent=2))
    result["report"] = report_path
    return result


def run_verification() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import remember_verification, set_phase

    set_phase("verify")
    try:
        from modules.strict_project_stability_ru import dispatch as strict_dispatch

        result = strict_dispatch("проверь проект")
        if isinstance(result, dict):
            remember_verification(str(result.get("report", "")), ok=bool(result.get("ok")))
            result["called_by"] = "ai_agent_core_ru"
            return result
    except Exception as exc:
        return {
            "ok": False,
            "mode": "ai_agent_verify_error",
            "generated_at": _now(),
            "error": str(exc),
        }

    return {
        "ok": False,
        "mode": "ai_agent_verify_error",
        "generated_at": _now(),
        "error": "strict verification returned non-dict result",
    }


def _format_status_summary() -> dict[str, Any]:
    from modules.ai_agent_memory_ru import status as memory_status

    memory = memory_status()
    return {
        "phase": memory.get("phase"),
        "active_goal": memory.get("active_goal"),
        "latest_draft": memory.get("latest_draft"),
        "latest_verification_report": memory.get("latest_verification_report"),
        "memory_dir": memory.get("memory_dir"),
    }


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_core_status",
        "generated_at": _now(),
        "agent_version": AI_AGENT_VERSION,
        "agent_name": AI_AGENT_NAME,
        "state_machine": STATE_MACHINE,
        "summary": _format_status_summary(),
        "commands": [
            "pc ai status",
            "pc ai context",
            "pc ai plan <цель>",
            "pc ai draft <цель>",
            "pc ai cycle <цель>",
            "pc ai verify",
            "pc ai repair",
            "агент статус",
            "агент контекст",
            "агент план <цель>",
            "агент черновик <цель>",
        ],
    }


def report() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_core_report",
        "generated_at": _now(),
        "status": status(),
        "memory": _format_status_summary(),
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")

    if text in {"pc ai status", "ai agent status", "агент статус", "статус агента"}:
        return status()

    if text in {"pc ai context", "ai agent context", "агент контекст", "проанализируй проект", "контекст проекта"}:
        return build_project_context()

    if text in {"pc ai report", "агент отчет", "агент отчёт"}:
        return report()

    if text in {"pc ai verify", "агент проверка"}:
        return run_verification()

    if text in {"pc ai repair", "агент repair", "почини по последнему отчету", "почини по последнему отчёту"}:
        return propose_repair()

    for prefix in ("pc ai plan ", "агент план ", "спланируй "):
        if text.startswith(prefix):
            return build_task_plan(raw[len(prefix):].strip())

    for prefix in ("pc ai draft ", "агент черновик ", "сделай патч для "):
        if text.startswith(prefix):
            return draft_patch(raw[len(prefix):].strip())

    for prefix in ("pc ai cycle ", "агент цикл "):
        if text.startswith(prefix):
            return run_agent_cycle(raw[len(prefix):].strip(), dry_run=True)

    if text in {"pc ai plan", "агент план"}:
        return build_task_plan("развивать LocalComet как локального AI-агента")

    if text in {"pc ai draft", "агент черновик"}:
        return draft_patch("развивать LocalComet как локального AI-агента")

    if text in {"pc ai cycle", "агент цикл"}:
        return run_agent_cycle("развивать LocalComet как локального AI-агента", dry_run=True)

    return {
        "ok": False,
        "mode": "ai_agent_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc ai status, pc ai context, pc ai plan <цель>, pc ai draft <цель>, pc ai repair",
    }


def is_ai_agent_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return (
        text.startswith("pc ai ")
        or text.startswith("агент план ")
        or text.startswith("агент черновик ")
        or text.startswith("агент цикл ")
        or text.startswith("сделай патч для ")
        or text.startswith("спланируй ")
        or text in {
            "агент статус",
            "статус агента",
            "агент контекст",
            "проанализируй проект",
            "контекст проекта",
            "агент проверка",
            "агент repair",
            "почини по последнему отчету",
            "почини по последнему отчёту",
        }
    )
````

### ПУТЬ: modules/ai_agent_memory_ru.py (296 строк, 10046 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
STATE_PATH = MEMORY_DIR / "agent_state.json"
PROJECT_CONTEXT_PATH = MEMORY_DIR / "project_context.json"
TASK_HISTORY_PATH = MEMORY_DIR / "task_history.json"
BACKLOG_PATH = MEMORY_DIR / "agent_backlog.json"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_memory_dir() -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, data: Any) -> Path:
    ensure_memory_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_state() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_state",
        "created_at": _now(),
        "updated_at": _now(),
        "agent_version": "v6.41d",
        "phase": "idle",
        "active_goal": "",
        "latest_project_map": "",
        "latest_context": str(PROJECT_CONTEXT_PATH),
        "latest_draft": "",
        "latest_verification_report": "",
        "latest_repair_plan": "",
        "stable_version": "",
        "notes": [
            "LocalComet AI Agent Core is safe-by-default.",
            "Patches are drafted for Relay and are not applied automatically.",
            "Project verification is the gate after every applied patch.",
        ],
    }


def load_state() -> dict[str, Any]:
    ensure_memory_dir()
    state = _read_json(STATE_PATH, default_state())
    if not isinstance(state, dict):
        state = default_state()
    state.setdefault("ok", True)
    state.setdefault("mode", "ai_agent_state")
    state.setdefault("phase", "idle")
    state.setdefault("active_goal", "")
    state.setdefault("agent_version", "v6.41d")
    state["updated_at"] = _now()
    return state


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    payload["updated_at"] = _now()
    _write_json(STATE_PATH, payload)
    return payload


def set_phase(phase: str, goal: str | None = None, **extra: Any) -> dict[str, Any]:
    state = load_state()
    state["phase"] = str(phase or "idle")
    if goal is not None:
        state["active_goal"] = str(goal)
    for key, value in extra.items():
        state[key] = value
    return save_state(state)


def append_history(event: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_memory_dir()
    history = _read_json(TASK_HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    item = dict(event)
    item.setdefault("generated_at", _now())
    history.append(item)
    history = history[-300:]
    _write_json(TASK_HISTORY_PATH, history)
    return history


def save_project_context(context: dict[str, Any]) -> dict[str, Any]:
    _write_json(PROJECT_CONTEXT_PATH, context)
    state = load_state()
    state["latest_context"] = str(PROJECT_CONTEXT_PATH)
    if context.get("project_map_path"):
        state["latest_project_map"] = str(context.get("project_map_path"))
    save_state(state)
    append_history({
        "type": "project_context",
        "ok": bool(context.get("ok", True)),
        "path": str(PROJECT_CONTEXT_PATH),
        "summary": {
            "python_files": context.get("python_file_count"),
            "functions": context.get("function_count"),
            "command_modules": context.get("command_module_count"),
        },
    })
    return context


def save_backlog(items: list[dict[str, Any]]) -> Path:
    return _write_json(BACKLOG_PATH, items)


def load_backlog() -> list[dict[str, Any]]:
    data = _read_json(BACKLOG_PATH, [])
    return data if isinstance(data, list) else []


def seed_default_backlog(force: bool = False) -> list[dict[str, Any]]:
    existing = load_backlog()
    if existing and not force:
        return existing

    items = [
        {
            "id": "AI-0001",
            "priority": "P0",
            "status": "ready",
            "title": "Project Map",
            "why": "Агенту нужна карта проекта перед любым планом.",
            "command": "pc ai context",
        },
        {
            "id": "AI-0002",
            "priority": "P0",
            "status": "ready",
            "title": "Patch Draft Planner",
            "why": "Агент должен готовить безопасный response.json draft, а не просто советовать.",
            "command": "pc ai draft <цель>",
        },
        {
            "id": "AI-0003",
            "priority": "P1",
            "status": "planned",
            "title": "Verification Critic",
            "why": "После проверки агент должен читать отчёт и предлагать repair.",
            "command": "pc ai repair",
        },
        {
            "id": "AI-0004",
            "priority": "P1",
            "status": "planned",
            "title": "Plan/Act UX",
            "why": "Нужно разделить планирование и действие как у сильных coding agents.",
            "command": "pc ai plan <цель>",
        },
        {
            "id": "AI-0005",
            "priority": "P2",
            "status": "planned",
            "title": "Agent Workspace Shell",
            "why": "Красивый shell имеет смысл после рабочего агентского ядра.",
            "command": "pc ai cycle <цель>",
        },
    ]
    save_backlog(items)
    return items


def find_latest_verification_report() -> str:
    reports_root = ROOT_PATH / "Projects" / "Reports"
    if not reports_root.exists():
        return ""

    candidates: list[Path] = []
    for folder_name in ("strict_project_stability", "auto_verification"):
        folder = reports_root / folder_name
        if folder.exists():
            candidates.extend(folder.glob("*.json"))
            candidates.extend(folder.glob("*.md"))

    candidates.extend(reports_root.glob("*auto_stability_test*.md"))
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        return ""

    latest = max(candidates, key=lambda item: item.stat().st_mtime)
    return str(latest)


def remember_draft(path: str, goal: str) -> dict[str, Any]:
    state = set_phase("wait_for_user_apply", goal, latest_draft=path)
    append_history({
        "type": "draft_patch",
        "goal": goal,
        "draft_path": path,
        "phase": "wait_for_user_apply",
    })
    return state


def remember_verification(path: str, ok: bool | None = None) -> dict[str, Any]:
    state = load_state()
    state["latest_verification_report"] = str(path or "")
    state["phase"] = "done" if ok else "critique"
    save_state(state)
    append_history({
        "type": "verification_report",
        "ok": ok,
        "path": path,
        "phase": state["phase"],
    })
    return state


def status() -> dict[str, Any]:
    state = load_state()
    backlog = seed_default_backlog(force=False)
    latest_report = find_latest_verification_report()
    if latest_report and state.get("latest_verification_report") != latest_report:
        state["latest_verification_report"] = latest_report
        save_state(state)

    return {
        "ok": True,
        "mode": "ai_agent_memory_status",
        "generated_at": _now(),
        "memory_dir": str(MEMORY_DIR),
        "state_path": str(STATE_PATH),
        "project_context_path": str(PROJECT_CONTEXT_PATH),
        "task_history_path": str(TASK_HISTORY_PATH),
        "backlog_path": str(BACKLOG_PATH),
        "phase": state.get("phase"),
        "active_goal": state.get("active_goal"),
        "latest_draft": state.get("latest_draft"),
        "latest_verification_report": state.get("latest_verification_report") or latest_report,
        "backlog_items": len(backlog),
    }


def report() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "ai_agent_memory_report",
        "generated_at": _now(),
        "status": status(),
        "state": load_state(),
        "backlog": seed_default_backlog(force=False),
        "history": _read_json(TASK_HISTORY_PATH, [])[-20:],
    }


def dispatch(command: str) -> dict[str, Any]:
    text = str(command or "").strip().lower().replace("ё", "е")
    if text in {"pc ai memory", "pc ai memory status", "агент память", "память агента"}:
        return status()
    if text in {"pc ai memory report", "агент память отчет", "агент память отчёт"}:
        return report()
    if text in {"pc ai backlog", "агент backlog", "агент задачи"}:
        return {
            "ok": True,
            "mode": "ai_agent_memory_backlog",
            "generated_at": _now(),
            "backlog_path": str(BACKLOG_PATH),
            "items": seed_default_backlog(force=False),
        }
    return {
        "ok": False,
        "mode": "ai_agent_memory_unknown_command",
        "generated_at": _now(),
        "command": command,
        "hint": "Используй: pc ai memory, pc ai backlog",
    }


def is_ai_agent_memory_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text.startswith("pc ai memory") or text in {"агент память", "память агента", "агент backlog", "агент задачи"}
````

### ПУТЬ: modules/ai_patch_planner_ru.py (301 строк, 10866 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_PATH = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT_PATH / "Projects" / "AgentMemory"
DRAFT_DIR = MEMORY_DIR / "drafts"
PLANS_DIR = MEMORY_DIR / "plans"

DANGEROUS_PATTERNS = [
    "пароль",
    "password",
    "token",
    "api key",
    "api-key",
    "secret",
    "private key",
    "ssh key",
    "cookie",
    "cookies",
    "удали",
    "удалить",
    "стереть",
    "сотри",
    "format",
    "wipe",
    "rm ",
    "rmdir",
    "del ",
    "powershell",
    "cmd.exe",
    "bash",
    "shell",
    "terminal",
    "админ",
    "administrator",
    "sudo",
    "банк",
    "bank",
    "карта",
    "payment",
    "casino",
    "gambling",
    "browser profile",
    "браузерный профиль",
]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_slug(text: str) -> str:
    lowered = str(text or "agent_task").strip().lower().replace("ё", "е")
    lowered = re.sub(r"[^a-zа-я0-9]+", "_", lowered, flags=re.IGNORECASE)
    lowered = lowered.strip("_")
    return lowered[:48] or "agent_task"


def _danger_reason(goal: str) -> str:
    lowered = str(goal or "").lower().replace("ё", "е")
    for marker in DANGEROUS_PATTERNS:
        if marker in lowered:
            return "цель содержит потенциально опасный маркер: " + marker
    return ""


def _load_context() -> dict[str, Any]:
    try:
        from modules.ai_project_map_ru import build_project_map

        return build_project_map()
    except Exception as exc:
        return {
            "ok": False,
            "mode": "ai_patch_planner_context_error",
            "error": str(exc),
        }


def build_patch_plan(goal: str) -> dict[str, Any]:
    _ensure_dirs()
    raw_goal = str(goal or "").strip() or "улучшить LocalComet как AI-агента"
    danger = _danger_reason(raw_goal)

    context = _load_context()
    stamp = _stamp()
    plan_path = PLANS_DIR / f"agent_plan_{stamp}_{_safe_slug(raw_goal)}.md"

    if danger:
        plan_text = (
            "# AI Agent Patch Plan\n\n"
            f"- generated_at: {_now()}\n"
            f"- goal: {raw_goal}\n"
            f"- blocked: true\n"
            f"- reason: {danger}\n"
        )
        plan_path.write_text(plan_text, encoding="utf-8")
        return {
            "ok": False,
            "mode": "ai_patch_plan_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
            "plan_path": str(plan_path),
        }

    summary = context.get("control_panel", {}) if isinstance(context, dict) else {}
    plan_text = (
        "# AI Agent Patch Plan\n\n"
        f"- generated_at: {_now()}\n"
        f"- goal: {raw_goal}\n"
        f"- current_version: {summary.get('version', '')}\n"
        f"- project_map: {context.get('project_map_path', '') if isinstance(context, dict) else ''}\n\n"
        "## Strategy\n\n"
        "1. Сузить цель до минимального безопасного изменения.\n"
        "2. Использовать карту проекта, а не угадывать файлы.\n"
        "3. Сформировать response.json draft с одним installer в tools/.\n"
        "4. Не применять patch автоматически.\n"
        "5. После применения запустить строгую проверку проекта.\n"
        "6. Если проверка падает — построить repair plan по отчёту.\n\n"
        "## Target areas\n\n"
        "- modules/ai_agent_core_ru.py\n"
        "- modules/ai_project_map_ru.py\n"
        "- modules/ai_patch_planner_ru.py\n"
        "- modules/ai_agent_memory_ru.py\n"
        "- modules/premium_task_panel_ru.py\n"
        "- LocalComet_Control_Panel.py\n"
    )
    plan_path.write_text(plan_text, encoding="utf-8")

    return {
        "ok": True,
        "mode": "ai_patch_plan",
        "generated_at": _now(),
        "goal": raw_goal,
        "plan_path": str(plan_path),
        "context_path": context.get("project_map_path", "") if isinstance(context, dict) else "",
        "target_files": [
            "modules/ai_agent_core_ru.py",
            "modules/ai_project_map_ru.py",
            "modules/ai_patch_planner_ru.py",
            "modules/ai_agent_memory_ru.py",
            "modules/premium_task_panel_ru.py",
            "LocalComet_Control_Panel.py",
        ],
        "next_step": "pc ai draft " + raw_goal,
    }


def _draft_installer_content(goal: str, stamp: str) -> str:
    safe_goal = repr(str(goal or "agent task"))
    return (
        "from pathlib import Path\n"
        "import json\n"
        "from datetime import datetime\n\n"
        "ROOT_PATH = Path(__file__).resolve().parents[1]\n"
        "REPORT_DIR = ROOT_PATH / 'Projects' / 'AgentMemory' / 'applied_drafts'\n"
        "REPORT_DIR.mkdir(parents=True, exist_ok=True)\n"
        f"MARKER = REPORT_DIR / 'agent_draft_marker_{stamp}.json'\n"
        "payload = {\n"
        "    'ok': True,\n"
        "    'mode': 'ai_agent_draft_marker',\n"
        "    'generated_at': datetime.now().replace(microsecond=0).isoformat(),\n"
        f"    'goal': {safe_goal},\n"
        "    'note': 'Safe marker generated by AI Agent Core. Replace this draft with concrete code changes after human review.',\n"
        "}\n"
        "MARKER.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')\n"
        "print('AI Agent draft marker written:', MARKER)\n"
    )


def draft_patch(goal: str) -> dict[str, Any]:
    _ensure_dirs()
    raw_goal = str(goal or "").strip() or "улучшить LocalComet как AI-агента"
    danger = _danger_reason(raw_goal)
    if danger:
        return {
            "ok": False,
            "mode": "ai_patch_draft_blocked",
            "generated_at": _now(),
            "goal": raw_goal,
            "reason": danger,
        }

    plan = build_patch_plan(raw_goal)
    stamp = _stamp()
    slug = _safe_slug(raw_goal)
    draft_path = DRAFT_DIR / f"response_agent_draft_{stamp}_{slug}.json"
    installer_path = f"tools/install_ai_agent_draft_marker_{stamp}.py"

    draft = {
        "summary": (
            "AI Agent Draft Patch: safe human-review draft generated by LocalComet AI Agent Core. "
            "This first-stage draft creates a marker report only, so the Relay pipeline can be verified before concrete code modifications. "
            "No browser, npm, shell, cmd, powershell, backend, delete, deploy, token, API-key, secret, or destructive actions are added."
        ),
        "operations": [
            {
                "type": "create",
                "path": installer_path,
                "content": _draft_installer_content(raw_goal, stamp),
            }
        ],
        "tests": [
            f"python {installer_path.replace('/', '\\\\')}",
            f"python -m py_compile {installer_path.replace('/', '\\\\')}",
            "python -c \"from pathlib import Path; files=list(Path('Projects/AgentMemory/applied_drafts').glob('agent_draft_marker_*.json')); assert files; print(files[-1])\"",
        ],
    }

    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        from modules.ai_agent_memory_ru import remember_draft
        remember_draft(str(draft_path), raw_goal)
    except Exception:
        pass

    return {
        "ok": True,
        "mode": "ai_patch_draft",
        "generated_at": _now(),
        "goal": raw_goal,
        "draft_path": str(draft_path),
        "plan_path": plan.get("plan_path") if isinstance(plan, dict) else "",
        "summary": draft["summary"],
        "operations": len(draft["operations"]),
        "tests": len(draft["tests"]),
        "next_steps": [
            "Открыть draft_path.",
            "Проверить summary/operations/tests.",
            "Импортировать draft через Relay только после человеческого подтверждения.",
            "После применения нажать «Проверить проект».",
        ],
    }


def status() -> dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "ai_patch_planner_status",
        "generated_at": _now(),
        "draft_dir": str(DRAFT_DIR),
        "plans_dir": str(PLANS_DIR),
        "draft_count": len(list(DRAFT_DIR.glob("response_agent_draft_*.json"))),
        "plan_count": len(list(PLANS_DIR.glob("agent_plan_*.md"))),
    }


def report() -> dict[str, Any]:
    _ensure_dirs()
    return {
        "ok": True,
        "mode": "ai_patch_planner_report",
        "generated_at": _now(),
        "status": status(),
        "latest_drafts": [str(path) for path in sorted(DRAFT_DIR.glob("response_agent_draft_*.json"), reverse=True)[:10]],
        "latest_plans": [str(path) for path in sorted(PLANS_DIR.glob("agent_plan_*.md"), reverse=True)[:10]],
    }


def dispatch(command: str) -> dict[str, Any]:
    raw = str(command or "").strip()
    text = raw.lower().replace("ё", "е")
    if text in {"pc ai patch planner status", "планировщик патчей статус"}:
        return status()
    if text in {"pc ai patch planner report", "планировщик патчей отчет", "планировщик патчей отчёт"}:
        return report()
    if text.startswith("pc ai draft "):
        return draft_patch(raw[len("pc ai draft "):].strip())
    if text.startswith("сделай патч для "):
        return draft_patch(raw[len("сделай патч для "):].strip())
    return {
        "ok": False,
        "mode": "ai_patch_planner_unknown_command",
        "generated_at": _now(),
        "command": raw,
        "hint": "Используй: pc ai draft <цель>",
    }


def is_ai_patch_planner_command(command: str) -> bool:
    text = str(command or "").strip().lower().replace("ё", "е")
    return text.startswith("pc ai draft ") or text.startswith("сделай патч для ") or text.startswith("pc ai patch planner")
````

