# MVP-P0-C — STATE MACHINE CONTRACT (FROZEN)

Status: FROZEN before RED
Cycle: MVP-P0-C
Date: 2026-07-30

## States

```
STOPPED → STARTING → CHALLENGE_SENT → READY → DEGRADED → STOPPING → STOPPED
```

Failed states: START_FAILED (from STARTING/CHALLENGE_SENT on timeout/error)

## Transition Rules

| Trigger | From | To | Condition |
|---------|------|----|-----------|
| launch() | STOPPED | STARTING | new generation allocated |
| process spawned | STARTING | CHALLENGE_SENT | health.check sent |
| correlated health.status=ready | CHALLENGE_SENT | READY | all 13 validation steps pass |
| correlated health.status=degraded | CHALLENGE_SENT/READY | DEGRADED | all correlation valid |
| health timeout | CHALLENGE_SENT | START_FAILED | deadline exceeded |
| process exit | any active | STOPPED | immediate |
| stop() | any active | STOPPING | before process wait |
| stop complete | STOPPING | STOPPED | process exited |
| restart | STOPPED | STARTING | new generation + nonce |

## Invariants

- Process existence alone NEVER means READY
- Only one fully correlated health.status=ready transitions to READY
- Stale/malformed/mismatched responses do NOT change readiness
- Process exit IMMEDIATELY clears READY
- Stop clears READY BEFORE waiting for process exit
- Restart allocates new generation AND nonce before launch
- Old generation responses can NEVER restore READY
- Duplicate READY for same completed request: ignored, recorded safely
- Response for unknown request ID: rejected
- Out-of-order response for superseded challenge: rejected
- Second process cannot inherit previous process readiness state

## Validation Order (13 steps)

1. Frame validity (size, UTF-8, single JSON object)
2. Message type = "health.status"
3. protocolVersion = 1
4. requestId syntax (hreq_ + 32 hex)
5. Pending request existence
6. generationId match
7. startupNonce match (exact equality)
8. runtimeInstanceId match
9. Deadline/expiry check
10. status enum valid
11. Capability invariant (toolExecution=false)
12. Atomic completion (one-time)
13. Readiness transition

Invalid attempts at steps 1-11 do NOT consume the pending request.
Step 12 completes the request exactly once.
Duplicate valid responses return distinct duplicate classification.

## Registry Bounds

- MAX_PENDING_HEALTH_REQUESTS = 8
- MAX_COMPLETED_HEALTH_TOMBSTONES = 32
- PENDING_HEALTH_TTL = 10 seconds
- COMPLETED_TOMBSTONE_TTL = 60 seconds
- Eviction: oldest-first, deterministic
