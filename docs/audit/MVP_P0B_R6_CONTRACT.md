# MVP-P0-B-R6 — CONTRACT

Status: IMPLEMENTED
Cycle: MVP-P0-B-R6
Date: 2026-07-30

## Objective

Fix four independently verified blockers from R5-A1:
1. model.binding.set frontend/Rust contract mismatch (confirmed parameter)
2. Generic approval_denied error collapse in run_tool_call
3. Rust/TypeScript commandFamily divergence (8 vs 5)
4. Six missing R5 documents

## Frozen Contracts

- docs/audit/MVP_P0B_R6_MODEL_BINDING_CONTRACT.md
  SHA-256: 9b094d9264a059252a1c38fe2e6025eb48d0c650ad95d835f3d798197e365962
- docs/audit/MVP_P0B_R6_COMMAND_FAMILY_CONTRACT.md
  SHA-256: 50d7d31d874d2e9a903354db03bf9d10ed5149ff52d0f3089ed1e9a7811100f2
- security/contracts/approval_command_families_v1.json
  SHA-256: 84cb07b1efc4dd88a99df7118a209f323ed78905ee446ac070ba2facbacccc8b

## Changes Made

1. Removed confirmed: bool from model_binding_set Tauri command signature
2. Removed confirmed from canonical digest payload (5-field semantic payload)
3. Added Rust-owned confirmed=true only after validate_approval_token succeeds
4. Fixed run_tool_call to use approval_error_code(&error) instead of "approval_denied"
5. Added tool_filesystem_read/write/delete to TypeScript ApprovalCommandFamily
6. Created shared manifest security/contracts/approval_command_families_v1.json
7. Created six missing R5 docs and four R6 docs
