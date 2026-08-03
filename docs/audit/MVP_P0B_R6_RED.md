# MVP-P0-B-R6 — RED

Status: VERIFIED
Cycle: MVP-P0-B-R6
Date: 2026-07-30

## Rust RED (5 runtime failures, 0 compile failures)

Command: cargo test p0b_r6 -- --nocapture
Working directory: desktop/localcomet-desktop/src-tauri

Failing tests (RED):
1. p0b_r6_model_binding_command_has_no_confirmed_parameter — confirmed: bool present in signature
2. p0b_r6_model_binding_digest_excludes_confirmed — "confirmed" in pre-validation payload
3. p0b_r6_model_binding_approval_and_execution_input_equal — 5-field vs 6-field digest mismatch
4. p0b_r6_model_binding_internal_confirmed_after_consume — confirmed appears before validate_approval_token
5. p0b_r6_all_approval_errors_use_exact_mapper — "approval_denied" string in approval_commands.rs

Result: 13 passed; 5 failed; 0 ignored

## Frontend RED (4 runtime failures, 0 compile failures)

Command: npx vitest run tests/p0b-r6-model-binding-contract.test.ts
Working directory: desktop/localcomet-desktop

Failing tests (RED):
1. p0b_r6_frontend_family_manifest_matches_runtime_set — TS has 5, manifest has 8
2. p0b_r6_frontend_accepts_all_rust_family_values — TS rejects tool_filesystem_* families
3. p0b_r6_frontend_tool_filesystem_read_family_accepted — Unknown command family
4. p0b_r6_frontend_tool_filesystem_write_family_accepted — Unknown command family

Result: 10 passed; 4 failed

## RED Classification

All failures are in the expected categories:
- confirmed remains in Rust command contract ✓
- confirmed remains in digest ✓
- frontend/Rust semantic input mismatch ✓
- compatibility true exists before approval consumption ✓
- generic approval_denied remains ✓
- Rust/TS family sets diverge ✓
- valid Rust family rejected by TS ✓
- required R5 docs absent ✓
