# MVP Baseline Gate Results (2026-07-30)

## Python Gates

| Gate | Result | Classification |
|------|--------|----------------|
| tests/test_evidence_model.py | 10 tests OK | GREEN |
| scripts/check_evidence_provenance.py | 7 fresh, 0 STALE | GREEN |
| scripts/check_historical_evidence.py | 46 valid, 0 BODY_MISMATCH | GREEN |
| tools/test_adr015_tool_parsing.py | 65 tests: 54 ok, 10 FAIL, 1 skip | EXPECTED_RED (B5LP) |
| tools/test_v6846_tool_execution.py | 17 tests OK | GREEN |
| tools/test_tool_risk_rust_parity.py | OK (10 tools, 5 registry) | GREEN |
| tests/test_trust_chain_invariants.py | 15 files pass | GREEN |
| scripts/check_command_parity.py | 43 commands OK | GREEN |
| scripts/check_tool_risk_registry.py | 5 functions, 10 entries OK | GREEN |
| scripts/check_ui_fake_state.py | 81 files, 0 violations | GREEN |
| scripts/check_mockdata_imports.py | 8 files OK | GREEN |
| scripts/check_bundle_parity.py | 2 STALE (local_model_gateway_ru.py) | STALE_BUNDLE |
| tools/test_v6843_sidecar_supervisor.py | FAIL: node_modules exists | ENVIRONMENT_INVARIANT |
| scripts/refresh_evidence.py | all gates green | GREEN |

## Frontend Gates (desktop/localcomet-desktop)

| Gate | Result | Classification |
|------|--------|----------------|
| npm run check (svelte-check) | 0 errors, 0 warnings | GREEN |
| npm test (vitest) | 21 files, 308 tests passed | GREEN |

## Rust Gates (desktop/localcomet-desktop/src-tauri)

| Gate | Result | Classification |
|------|--------|----------------|
| cargo fmt --check | clean | GREEN |
| cargo test b5l_ | 16 passed, 0 failed | GREEN |
| cargo test b5_ | 18 passed, 0 failed | GREEN |
| cargo test --workspace | 248 passed, 0 failed, 6 ignored | GREEN |
| cargo clippy --workspace --all-targets -- -D warnings | clean | GREEN |

## Known Intentional Failures

1. B5LP 10 RED tests: Python resource limits not yet implemented (P1-A)
2. Bundle parity 2 stale: build-source and deployed copies of local_model_gateway_ru.py (P0-D)
3. Sidecar supervisor node_modules: source-tree invariant violation (P4-B / ENVIRONMENT_INVARIANT)

## Digest

- Tree: 06c557d94665494205a839bf0ec168113d1fb41cf50a60272ebfe0c2ef3f8a73
- Source files: 335
