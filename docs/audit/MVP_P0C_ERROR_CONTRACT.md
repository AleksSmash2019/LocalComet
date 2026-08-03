# MVP-P0-C — ERROR CONTRACT (FROZEN)

Status: FROZEN before RED
Cycle: MVP-P0-C
Date: 2026-07-30

## Public Health Error Codes

| Code | Meaning |
|------|---------|
| sidecar_not_running | Process not spawned or exited |
| sidecar_start_timeout | Process did not spawn in time |
| sidecar_health_timeout | health.check response not received before deadline |
| sidecar_health_frame_invalid | Frame malformed (size, UTF-8, depth, duplicate key, empty, multi-object) |
| sidecar_health_protocol_mismatch | protocolVersion != 1 |
| sidecar_health_request_unknown | requestId not in pending registry |
| sidecar_health_response_duplicate | requestId already completed |
| sidecar_health_generation_mismatch | generationId does not match current generation |
| sidecar_health_nonce_mismatch | startupNonce does not match current nonce |
| sidecar_health_runtime_mismatch | runtimeInstanceId does not match current instance |
| sidecar_health_capability_mismatch | toolExecution != false or missing |
| sidecar_health_status_invalid | status not in {starting, ready, degraded, stopping} |
| sidecar_process_exited | Process exited during health check |
| sidecar_stopping | Stop in progress; health checks rejected |

## Mapping Rules

- Every internal health failure maps through one exhaustive mapper function
- No generic "sidecar_error" collapse
- No two distinct failure classes share the same public code
- Messages must NOT leak: full startup nonce, request ID when unnecessary, sensitive paths, raw Python payload, stack traces

## Frontend Snapshot Fields

```
state: "stopped" | "starting" | "challenge_sent" | "ready" | "degraded" | "stopping" | "start_failed"
generationId: u64
runtimeInstanceId: string | null
lastSuccessfulHealthUnixMs: u64 | null
lastFailureCode: string | null
```

startup_nonce is NEVER exposed to frontend.
Renderer cannot set health state directly.
No fake-ready timer. Optimistic UI may show "starting" but never "ready" without Rust READY.
