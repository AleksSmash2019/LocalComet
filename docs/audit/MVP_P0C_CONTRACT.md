# MVP-P0-C — CONTRACT

Status: IMPLEMENTED
Cycle: MVP-P0-C
Date: 2026-07-30

## Objective

Close the sidecar startup/readiness and IPC-health trust gap.

## Frozen Contracts

- docs/audit/MVP_P0C_HEALTH_PROTOCOL_CONTRACT.md (SHA-256: 17cb1f74bad4e781f2f10bba11d7f3c7bef1c86c003a2d44b9e878e6d06db25c)
- docs/audit/MVP_P0C_STATE_MACHINE_CONTRACT.md (SHA-256: dee4f831798cc8d74a6fbd9f5bbb1e9f25edb59f734ad109a02f030633c3e628)
- docs/audit/MVP_P0C_IPC_FRAMING_CONTRACT.md (SHA-256: 6a7474f1f6941ab6106dabd2050abbe529d7aee40ee01f630439b33371a24d8a)
- docs/audit/MVP_P0C_ERROR_CONTRACT.md (SHA-256: 9fc33ed8fda3dd739116990b370c370c9a4dc7add40c9a8f5bd9cc03ca2fb705)

## Changes Made

1. supervisor.rs: Added SidecarGeneration, SidecarReadinessState, validate_health_response, PendingHealthRegistry, exact health error codes, SidecarHealthSnapshot
2. supervisor.rs: Updated observe_lifecycle_frame to validate correlation fields (generationId, startupNonce, runtimeInstanceId, protocolVersion, capabilities.toolExecution)
3. supervisor.rs: Updated start() to allocate new generation with CSPRNG nonce and runtime instance ID
4. ipc.rs: Added reject_duplicate_keys (duplicate JSON key rejection), MAX_HEALTH_JSON_DEPTH, parse_health_frame
5. security/contracts/sidecar_health_malformed_frames_v1.json: Shared malformed-frame corpus (15 cases)
6. tools/test_p0c_sidecar_health.py: 37 Python P0-C tests
7. tests/p0c-sidecar-health.test.ts: 10 frontend P0-C tests
8. supervisor.rs: 36 Rust P0-C tests
