# MVP-P0-B Contract: Authoritative Approval Unification

## Cycle: MVP-P0-B
## Finding: F-002
## Status: CONTRACT_RATIFIED

## Changes Required

### 1. approval.rs: Validate-then-consume (GAP-1 fix)

**Before:** `entries.remove(token)` then validate scope fields
**After:** `entries.get(token)` to validate, then `entries.remove(token)` only after ALL checks pass

Exact behavior:
- Locate token via `get()`
- Validate expiry, tool, digest, workspace, session (all constant-time)
- Only if ALL pass: `remove()` and construct grant
- If ANY fail: return error, token remains in map
- Expired tokens: remove on expiry check (they can never succeed anyway)

### 2. capabilities/main.json: Add 4 approval commands (CAP-1 fix)

Add these permissions:
- "allow-request-approval"
- "allow-execute-approved"
- "allow-run-tool-call"
- "allow-set-workspace"

### 3. approval_commands.rs: Token gate for 5 mutating commands

Add a helper `fn require_approval_token(state, tool, input, token) -> Result<ExecutionGrant, BridgeError>` that:
- Computes canonical_input_digest
- Locks registry + workspace
- Calls registry.execute_approved(token, tool, digest, workspace)
- Returns grant or typed error

Modify these commands to accept `token: String` and call the helper:
- start_approved_artifact_download: add token param, validate against "artifact.download" scope
- remove_managed_model: add token param, validate against "artifact.remove" scope
- managed_runtime_start: add token param, validate against "runtime.start" scope
- managed_runtime_stop: add token param, validate against "runtime.stop" scope
- model_binding_set: add token param, validate against "model.binding.set" scope

The `confirmed: bool` parameter becomes UI-only (ignored for authorization). Keep it for backward compat but do NOT use it as a gate.

### 4. Frontend: Update 3 invoke calls

In modelGateway.ts:
- setModelBinding: call requestApproval first, pass token
- startApprovedArtifactDownload: call requestApproval first, pass token
- removeManagedModel: call requestApproval first, pass token

For managed_runtime_start/stop: add token parameter.

### 5. Tests (approval.rs)

8 new tests:
- wrong_tool_rejects_without_consuming_token (RED)
- wrong_digest_rejects_without_consuming_token (RED)
- wrong_workspace_rejects_without_consuming_token (RED)
- wrong_session_rejects_without_consuming_token (RED)
- token_survives_invalid_attempt_then_succeeds (RED)
- forged_token_with_valid_prefix_is_rejected (GREEN)
- concurrent_consume_exactly_one_succeeds (GREEN)
- risk_level_metadata_cannot_bypass_scope_matching (GREEN)

### 6. Failure Policy (Option A ratified)

Once protected dispatch begins, the token is consumed. No retry.
Full idempotency deferred to P1-C.

## Non-goals

- Frontend single-flight (P1-C)
- Informed approval UI (P1-D)
- Execution binding across Rust/Python (P1-E)
- TOCTOU (P1-F)
- B6 (P1-G)
- Bundle parity (P0-D)
- Tool activation

## Exact Errors (existing, preserved)

- "approval registry is full" (RegistryFull)
- "approval token not found" (TokenNotFound)
- "approval tool mismatch" (ToolMismatch)
- "approval input digest mismatch" (InputDigestMismatch)
- "approval workspace mismatch" (WorkspaceMismatch)
- "approval session mismatch" (SessionMismatch)
- "approval token expired" (Expired)
- "approval token is invalid" (InvalidToken)
- "approval token already consumed" (AlreadyConsumed - now activated)

New error for missing token on guarded/dangerous commands:
- code: "approval_required", message: "tool execution requires approval"
