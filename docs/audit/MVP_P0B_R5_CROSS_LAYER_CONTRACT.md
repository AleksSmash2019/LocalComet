# MVP-P0-B-R5 — CROSS-LAYER CONTRACT

Status: RETROACTIVE
Cycle: MVP-P0-B-R5
Date: 2026-07-30

## Rust → Frontend Contract

ApprovalEnvelope serialized as camelCase JSON:
- token: lcap_ + 64 hex chars
- approvalId: appr_ + 32 hex chars
- callId: call_ + 32 hex chars
- tool: string
- riskLevel: read_only | guarded | dangerous
- commandFamily: snake_case family string
- expiresAtUnixMs: positive integer, future timestamp

## Frontend Validation

validateApprovalEnvelope() in src/lib/bridge/approval.ts:
- Rejects snake_case aliases
- Validates token/approvalId/callId format via regex
- Checks expiry against Date.now()
- Validates commandFamily against COMMAND_FAMILIES array

## Protected Command Flow

1. Frontend calls requestApproval(tool, input)
2. Rust shows MessageBoxW, returns ApprovalEnvelope
3. Frontend passes token + approvalId + callId to protected command
4. Rust validates all three identifiers atomically
5. On success, operation proceeds; on failure, specific error code returned
