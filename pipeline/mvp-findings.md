# MVP Program Findings

## Accepted Findings

### F-001: Legacy arbitrary shell execution reachable
- Severity: CRITICAL
- Files: modules/self_edit.py, next/app_v5.py, modules/windows.py, agents/windows_agent.py, core/executor.py, modules/files.py, agents/file_agent.py
- Milestone: M2 (Safe Local MVP)
- Micro-cycle: MVP-P0-A
- State: COMPLETE
- Evidence: tools/test_p0a_legacy_quarantine.py (24 tests), artifacts/evidence/ (7 fresh)
- Owner decisions: Quarantine required; no deletion without approval
- Completion criteria: P0_LEGACY_EXECUTION_QUARANTINED — MET

### F-002: Approval authority not unified
- Severity: CRITICAL
- Files: desktop/localcomet-desktop/src-tauri/src/approval_commands.rs, approval.rs, artifact_acquisition.rs, managed_runtime.rs, control_plane.rs, capabilities/main.json
- Milestone: M2
- Micro-cycle: MVP-P0-B
- State: COMPLETE
- Completion criteria: P0_APPROVAL_AUTHORITY_UNIFIED — MET

### F-003: Sidecar health correlation prefix-only
- Severity: HIGH
- Files: supervisor module (Rust)
- Milestone: M2
- Micro-cycle: MVP-P0-C
- State: NOT_STARTED
- Completion criteria: P0_HEALTH_CORRELATION_FIXED

### F-004: Bundle parity stale (2 copies)
- Severity: HIGH
- Files: local_model_gateway_ru.py (build-source, deployed)
- Milestone: M1
- Micro-cycle: MVP-P0-D
- State: NOT_STARTED
- Completion criteria: P0_BUNDLE_PARITY_RESTORED

### F-005: Command/test authority ambiguity
- Severity: MEDIUM
- Files: tools/test_v6846.py (missing), tools/test_v6846_tool_execution.py (exists), AGENTS.md
- Milestone: M1
- Micro-cycle: MVP-P0-E
- State: NOT_STARTED
- Completion criteria: P0_TEST_AUTHORITY_FIXED

### F-006: B5LP Python resource limits absent
- Severity: HIGH
- Files: modules/local_model_gateway_ru.py
- Milestone: M2
- Micro-cycle: MVP-P1-A
- State: NOT_STARTED (10 intentional RED tests exist)
- Completion criteria: B5LP_GREEN_COMPLETE

### F-007: IPC pre-parse depth safety absent
- Severity: HIGH
- Files: Python IPC decoder
- Milestone: M2
- Micro-cycle: MVP-P1-B
- State: NOT_STARTED
- Completion criteria: P1_IPC_PREPARSE_LIMITS_COMPLETE

### F-008: Frontend approval double execution
- Severity: HIGH
- Files: ApprovalCard.svelte, approval.ts, approval_commands.rs
- Milestone: M2
- Micro-cycle: MVP-P1-C
- State: NOT_STARTED
- Completion criteria: P1_APPROVAL_IDEMPOTENCY_COMPLETE

### F-009: Uninformed approval UI
- Severity: MEDIUM
- Files: ApprovalCard.svelte
- Milestone: M2
- Micro-cycle: MVP-P1-D
- State: NOT_STARTED
- Completion criteria: P1_INFORMED_APPROVAL_COMPLETE

### F-010: Workspace/session/grant binding incomplete
- Severity: CRITICAL
- Files: Python sidecar tool.call, Rust control_plane
- Milestone: M2
- Micro-cycle: MVP-P1-E
- State: NOT_STARTED
- Completion criteria: P1_EXECUTION_BINDING_COMPLETE

### F-011: Workspace TOCTOU
- Severity: CRITICAL
- Files: Python tool execution, Rust workspace
- Milestone: M2
- Micro-cycle: MVP-P1-F
- State: NOT_STARTED
- Completion criteria: P1_WORKSPACE_TOCTOU_CLOSED

### F-012: B6 cross-event provenance absent
- Severity: HIGH
- Files: Rust control_plane
- Milestone: M2
- Micro-cycle: MVP-P1-G
- State: NOT_STARTED
- Completion criteria: B6_GREEN_COMPLETE

### F-013: Asymmetric IPC validation
- Severity: HIGH
- Files: Rust ipc.rs, Python IPC decoder
- Milestone: M2
- Micro-cycle: MVP-P1-H
- State: NOT_STARTED
- Completion criteria: P1_IPC_CONTRACT_PARITY_COMPLETE

### F-014: Incomplete execution bounds
- Severity: HIGH
- Files: Python tool execution
- Milestone: M2
- Micro-cycle: MVP-P1-I
- State: NOT_STARTED
- Completion criteria: P1_EXECUTION_BOUNDS_COMPLETE

### F-015: Source-tree node_modules invariant violation
- Severity: LOW
- Files: desktop/localcomet-desktop/node_modules
- Milestone: M3
- Micro-cycle: MVP-P4-B
- State: NOT_STARTED
- Classification: ENVIRONMENT_INVARIANT
- Completion criteria: RELEASE_BUILD_HYGIENE_COMPLETE
