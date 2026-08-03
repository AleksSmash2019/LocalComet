# MVP-P0-C — ACCEPTANCE

Status: REMEDIATION IMPLEMENTED — PENDING FRESH INDEPENDENT A2
Cycle: MVP-P0-C
Date: 2026-08-01

## Acceptance Criteria

- [x] SidecarGeneration with generation_id, startup_nonce, runtime_instance_id
- [x] startup_nonce: scn_ + 64 hex (32 CSPRNG bytes), never exposed to renderer
- [x] runtime_instance_id: rti_ + 32 hex (16 CSPRNG bytes)
- [x] Typed health protocol (health.check request, health.status response)
- [x] protocolVersion = 1 enforced
- [x] Capability invariant: toolExecution=false required for READY
- [x] 13-step validation order implemented
- [x] PendingHealthRegistry bounded (MAX_PENDING_HEALTH_REQUESTS=8)
- [x] Completed tombstones bounded (MAX_COMPLETED_HEALTH_TOMBSTONES=32)
- [x] Duplicate JSON key rejection in Rust (reject_duplicate_keys)
- [x] JSON depth limit (MAX_HEALTH_JSON_DEPTH=16)
- [x] Shared malformed-frame corpus (15 cases)
- [x] 14 exact health error codes (no generic collapse)
- [x] SidecarHealthSnapshot excludes startup_nonce
- [x] 36 Rust P0-C tests pass
- [x] 37 Python P0-C tests pass
- [x] 10 frontend P0-C tests pass
- [x] All P0-B tests remain green
- [x] P0-B containment preserved (8/8 invariants)
- [x] B5LP remains exactly 10 intentional RED
- [x] Lifecycle transition ownership, generation-scoped observation, transactional startup rollback, and synchronous write-failure invalidation remediated
- [x] `local_model_gateway_ru.py` shipped copies synchronized without capability activation
- [x] Required real-sidecar gate wired into Windows validation CI

## Not Yet Accepted

- Fresh independent MVP-P0-C-A2 audit has not yet returned PASS
- P0-C is not declared complete
- Tool execution remains disabled; Block 3 / P0-D is not authorized

## Next Allowed

Fresh independent MVP-P0-C-A2 read-only audit only.
