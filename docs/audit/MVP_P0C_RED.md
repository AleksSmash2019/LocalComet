# MVP-P0-C — RED

Status: VERIFIED
Cycle: MVP-P0-C
Date: 2026-07-30

## Rust RED (12 runtime failures, 0 compile failures)

Command: cargo test --lib p0c_ -- --nocapture

Failing tests (RED):
1. p0c_wrong_generation_rejected — wrong generationId accepted by prefix-only correlation
2. p0c_wrong_nonce_rejected — wrong startupNonce accepted
3. p0c_wrong_runtime_instance_rejected — wrong runtimeInstanceId accepted
4. p0c_protocol_version_mismatch_rejected — protocolVersion=99 accepted
5. p0c_tool_execution_true_rejected — toolExecution=true accepted
6. p0c_tool_execution_missing_rejected — missing capabilities accepted
7. p0c_unknown_status_rejected — status="exploded" accepted
8. p0c_non_integer_generation_rejected — fractional generationId accepted
9. p0c_negative_timestamp_rejected — negative receivedAtUnixMs accepted
10. p0c_duplicate_request_id_key_rejected — duplicate JSON keys not rejected in Rust
11. p0c_duplicate_nonce_key_rejected — duplicate JSON keys not rejected in Rust
12. p0c_excessive_depth_rejected — no general JSON depth limit in Rust

Result: 24 passed; 12 failed

## Python RED

Not applicable — Python tests written as GREEN tests (testing the protocol contract).
37 tests, all pass.

## Frontend RED

Not applicable — frontend tests written as GREEN tests (testing the snapshot contract).
10 tests, all pass.

## RED Classification

All 12 Rust failures are in expected categories:
- Stale generation response accepted ✓
- Wrong nonce accepted ✓
- Wrong runtime instance accepted ✓
- toolExecution=true accepted ✓
- Duplicate JSON key accepted ✓
- Excessive JSON depth accepted ✓
- Health errors collapse generically ✓
