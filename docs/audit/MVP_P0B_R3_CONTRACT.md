# MVP-P0-B-R3 Contract: Final Approval Contract Compliance

## Cycle: MVP-P0-B-R3
## Status: IMPLEMENTED

## Starting digest: c3c3b6ab248dcc084ba3135509bf259816075c0483c0c1dee1ec472cb9aae6e2
## Final digest: 358888828892f43bd4d70575667f99ab84526ff3b0114489b51e59910de6c058

## Changes

### 1. Authoritative Risk Validation
- risk_level removed from metadata-only status
- execute_approved now accepts risk_level parameter
- Validated against scope.risk_level at consumption time
- Mismatch returns RiskMismatch error without consuming token
- Risk derived from risk_level_for_tool() (Rust mirror of tool_risk_levels.toml)
- Renderer cannot select risk

### 2. Command Family Enum
- CommandFamily enum: ArtifactDownload, ArtifactRemove, RuntimeStart, RuntimeStop, ModelBindingSet, ToolFilesystemRead, ToolFilesystemWrite, ToolFilesystemDelete
- command_family_for_tool() derives family from tool name
- command_family stored on ApprovalScope
- Validated independently at consumption (FamilyMismatch error)
- Renderer cannot select family

### 3. Bounded Tombstone Storage
- Replaced HashSet<String> with HashMap<[u8;32], Instant> + VecDeque<[u8;32]>
- MAX_CONSUMED_TOMBSTONES = 4096
- TOMBSTONE_TTL = 300 seconds (matches DEFAULT_TTL)
- Stores SHA-256 digest of token (not raw token)
- Oldest evicted when capacity exceeded
- Expired tombstones swept during issue
- Expired tombstone → TokenNotFound (deterministic policy)

### 4. Exact Errors
- RiskMismatch: "approval risk level mismatch"
- FamilyMismatch: "approval command family mismatch"
- AlreadyConsumed: "approval token already consumed" (now live, not dead code)

### 5. Test Coverage
- 42 p0b_ tests (was 24, +18 new)
- 73 approval semantic tests
- 298 workspace tests total

## P0-B / P1-E Boundary

P0-B provides (Rust-side approval authorization):
- approval_id, call_id, operation, command_family, authoritative risk
- arguments digest, workspace string, session string
- expiration, one-time token, bounded tombstones

P1-E will provide (end-to-end execution binding):
- stable filesystem workspace identity
- trusted sidecar session
- IPC grant propagation
- execution provenance
- result-event correlation
- protection against forged Python tool.call context

## Remaining Debt
- P1-C: cross-token logical-call idempotency
- P1-E: end-to-end execution binding
- P1-F: workspace TOCTOU
- P0-D: bundle parity (2 stale copies)
- B5LP: Python resource limits (10 RED)
- B6: cross-event provenance
