# MVP-P0-C — IPC FRAMING CONTRACT (FROZEN)

Status: FROZEN before RED
Cycle: MVP-P0-C
Date: 2026-07-30

## Transport

Length-prefix 4-byte big-endian + UTF-8 JSON body.
Protocol: localcomet.ipc/1.0 (unchanged).

## Frame Limits

- MAX_FRAME_BYTES = 4,194,304 (4 MiB) — already enforced in ipc.rs
- MAX_HEALTH_JSON_DEPTH = 16 — NEW: general depth limit for health frames
- MAX_CORRELATION_FIELD_CHARS = 128 — max length for requestId, startupNonce, runtimeInstanceId fields

## Duplicate JSON Key Rejection

Rust MUST reject frames with duplicate JSON keys in health protocol messages.
Implementation: typed deserialization with a duplicate-detecting map visitor,
or a pre-parse scan. Smallest seam that can enforce this.

Python already rejects duplicate keys via object_pairs_hook=_reject_duplicate_keys.

## Depth Limit

Rust MUST reject health frames exceeding MAX_HEALTH_JSON_DEPTH = 16.
Python already enforces MAX_NESTING_DEPTH = 16 via validate_payload().

## Rejection Rules

| Condition | Error code |
|-----------|-----------|
| Frame > MAX_FRAME_BYTES | sidecar_health_frame_invalid |
| Empty frame | sidecar_health_frame_invalid |
| Invalid UTF-8 | sidecar_health_frame_invalid |
| Multiple JSON objects in one frame | sidecar_health_frame_invalid |
| Duplicate JSON key | sidecar_health_frame_invalid |
| Depth > MAX_HEALTH_JSON_DEPTH | sidecar_health_frame_invalid |
| Non-finite number | sidecar_health_frame_invalid |
| Unknown protocol version | sidecar_health_protocol_mismatch |
| Unknown health status | sidecar_health_status_invalid |
| Missing required field | sidecar_health_frame_invalid |

## Shared Malformed-Frame Corpus

security/contracts/sidecar_health_malformed_frames_v1.json

Both Rust and Python tests consume this same physical file.
Contains metadata descriptors (not raw invalid bytes) for each malformed case.

## Parity Requirement

Rust and Python must agree on malformed JSON behavior for all cases in the corpus.
No asymmetric acceptance: if Python rejects, Rust must reject, and vice versa.
