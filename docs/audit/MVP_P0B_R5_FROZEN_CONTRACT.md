# MVP-P0-B-R5 — FROZEN CONTRACT

Status: FROZEN (retroactive documentation)
Cycle: MVP-P0-B-R5
Date: 2026-07-30

## Scope

R5 established Rust-owned native approval with MessageBoxW consent.
This document records the frozen contract as implemented.

## Frozen Invariants

1. Rust-owned MessageBoxW consent (NativeWindowsApprovalPrompt)
2. No renderer decision parameter in request_approval
3. Reject/prompt failure create no token or record
4. Three independent CSPRNG identifiers: token (lcap_ + 64 hex), approvalId (appr_ + 32 hex), callId (call_ + 32 hex)
5. Seven-field camelCase ApprovalEnvelope: token, approvalId, callId, tool, riskLevel, commandFamily, expiresAtUnixMs
6. Forbidden capabilities absent: allow-run-tool-call, allow-set-workspace, allow-execute-approved
7. Activation false (TOOL_EXECUTION_ACTIVATION_ENABLED = false)
8. Model tools empty (no tool execution exposed)
9. Placeholder active
10. Renderer cannot reach tool_execution_ru.py

## Test Baseline at R5 Freeze

- p0b_r5_: 42 pass
- p0b_: 88 pass
- Rust workspace: 344 pass, 6 ignored
- Frontend: 334 pass in 22 files

## Addendum: MVP-P0-C-A2 PASS (2026-08-06)

Following the successful independent security audit (MVP-P0-C-A2), invariant #7 has been superseded:
- Activation true (`TOOL_EXECUTION_ACTIVATION_ENABLED = true`)
- Block 3 orchestration unblocked.
