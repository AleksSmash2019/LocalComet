# UP05-WP01 State Machine

Status: owner-authorized R2 contract. Durations below are internal reliability bounds, not production performance baselines.

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

Implementation may retain a shorter safe existing bound, but it must not silently widen a bound. Timeout events are terminal exactly once and remain retryable only when the runtime/model session is still healthy.

## Error classes

User-visible errors are bounded and sanitized. At minimum the typed path distinguishes `runtime_unavailable`, `approved_model_unavailable`, `model_validation_failed`, `model_load_failed`, `model_load_timed_out`, `request_rejected`, `request_acceptance_timeout`, `first_token_timeout`, `stream_inactivity_timeout`, `stream_interrupted`, `request_cancelled`, `cancel_ack_timeout`, and `protocol_mismatch`.

No error exposes stack traces, credentials, absolute private paths, provider JSON, or SSE framing.
