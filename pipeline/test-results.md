# B4A Closure Test Results

Fresh gate runs on current tree. Run by orchestrator gate driver (gate-runner agent
returned incomplete; orchestrator completed gates in official refresh_evidence format).

Tree digest: 8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88 (283 files)
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364
Branch: feature/donor-ui-compatible-port

| Command | Exit | Result | Evidence file |
|---|---:|---|---|
| cargo fmt --check | 0 | clean | artifacts/evidence/b4a_closure_fmt.txt |
| cargo test b4a_ -- --nocapture | 0 | 10 passed / 0 failed | artifacts/evidence/b4a_closure_b4a_tests.txt |
| cargo test b4c_ -- --nocapture | 0 | 6 passed / 0 failed | artifacts/evidence/b4a_closure_b4c_tests.txt |
| cargo test b3m_ -- --nocapture | 0 | 10 passed / 0 failed | artifacts/evidence/b4a_closure_b3m_tests.txt |
| cargo test b2_ -- --nocapture | 0 | 11 passed / 0 failed | artifacts/evidence/b4a_closure_b2_tests.txt |
| cargo test --workspace | 0 | 214 passed / 0 failed / 6 ignored | artifacts/evidence/b4a_closure_workspace_tests.txt |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean | artifacts/evidence/b4a_closure_clippy.txt |
| python tools/test_tool_risk_rust_parity.py | 0 | OK (10 risk tools, 5 registry tools) | artifacts/evidence/b4a_closure_risk_parity.txt |
| git diff --check | 0 | clean | artifacts/evidence/b4a_closure_diff_check.txt |
| python scripts/check_evidence_provenance.py (before refresh) | 1 | 4 STALE (expected pre-refresh) | artifacts/evidence/b4a_closure_provenance_before.txt |
| python scripts/refresh_evidence.py | 0 | all gates green | (writes cargo_test/trust_chain/cmd_parity/tool_risk_registry) |
| python scripts/check_evidence_provenance.py (after refresh) | 0 | 15 fresh and intact, 0 STALE | artifacts/evidence/b4a_closure_provenance_after.txt |

Git state snapshot: artifacts/evidence/b4a_closure_git_state.txt
Evidence manifest: artifacts/evidence/B4A_CLOSURE_MANIFEST.sha256

## Baseline reconciliation

Фактический текущий baseline (свежий прогон): 214 passed / 0 failed / 6 ignored.
Исторический снапшот audit/2026-07-28/02_gates_raw/cargo_test.txt фиксирует 163 passed
(состояние до добавления B2/B3M/B4C/B4A тестов). AGENTS.md:61 фиксирует 160 passed
(устарел). Текущее авторитетное значение = 214/0/6 (подтверждено свежим evidence).

---

# B5 RED Adversarial — baseline (2026-07-28)

Статус: B5_CONTRACT_BLOCKED (RED-тесты не создавались). Baseline до любых изменений:

| Command | Exit | Result | Evidence |
|---|---:|---|---|
| cargo fmt --check | 0 | clean | artifacts/evidence/b5_red_adversarial_preflight_fmt.txt |
| cargo test b4a_ | 0 | 10 passed / 0 failed | artifacts/evidence/b5_red_baseline_b4a.txt |
| cargo test b4c_ | 0 | 6 passed / 0 failed | artifacts/evidence/b5_red_baseline_b4c.txt |
| cargo test b3m_ | 0 | 10 passed / 0 failed | artifacts/evidence/b5_red_baseline_b3m.txt |
| cargo test b2_ | 0 | 11 passed / 0 failed | artifacts/evidence/b5_red_baseline_b2.txt |
| cargo test --workspace | 0 | 214 passed / 0 failed / 6 ignored | artifacts/evidence/b5_red_baseline_workspace.txt |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean | artifacts/evidence/b5_red_baseline_clippy.txt |
| python tools/test_tool_risk_rust_parity.py | 0 | OK | artifacts/evidence/b5_red_baseline_parity.txt |
| python scripts/check_evidence_provenance.py | 0 | 24 fresh | artifacts/evidence/b5_red_baseline_provenance.txt |
| git diff --check | 0 | clean | artifacts/evidence/b5_red_baseline_diffcheck.txt |

Tree digest: 8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88 (283 файла).

---

# B5 RED Adversarial (2026-07-28, tree cc18487b с B5-тестами)

Focused (cargo test b5_): 7 passed / 11 failed, exit 101.
- 11 failed = EXPECTED_B5_RED (placeholder вместо B5 error; production не валидирует arguments).
- 7 passed = 3 positive (valid object -> placeholder) + adjacent + 3 precedence.

| Suite | Exit | Result | Evidence |
|---|---:|---|---|
| cargo test b5_ | 101 | 7 passed / 11 failed (EXPECTED_B5_RED) | b5_red_adversarial_focused.txt |
| cargo test b4a_ | 0 | 10 passed / 0 failed | b5_red_adversarial_regressions.txt |
| cargo test b4c_ | 0 | 6 passed / 0 failed | b5_red_adversarial_regressions.txt |
| cargo test b3m_ | 0 | 10 passed / 0 failed | b5_red_adversarial_regressions.txt |
| cargo test b2_ | 0 | 11 passed / 0 failed | b5_red_adversarial_regressions.txt |
| cargo test --workspace | 101 | 221 passed / 11 failed / 6 ignored (11 = только b5) | b5_red_adversarial_workspace.txt |
| cargo fmt --check | 0 | clean | b5_red_adversarial_aux_gates.txt |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean | b5_red_adversarial_aux_gates.txt |
| python tools/test_tool_risk_rust_parity.py | 0 | OK | b5_red_adversarial_aux_gates.txt |
| git diff --check | 0 | clean | b5_red_adversarial_aux_gates.txt |

Baseline (до тестов, tree 8a0d1d80): B4A 10/0, B4C 6/0, B3M 10/0, B2 11/0, Workspace 214/0/6, все exit 0 (b5_ratify_*.txt).

---

# B5 GREEN (2026-07-28, tree ae579fb9)

| Suite | Exit | Result | Evidence |
|---|---:|---|---|
| cargo test b5_ | 0 | 18 passed / 0 failed | b5_green_focused.txt |
| cargo test --workspace | 0 | 232 passed / 0 failed / 6 ignored | b5_green_workspace.txt |
| cargo test b4a_ | 0 | 10 passed / 0 failed | b5_green_regressions.txt |
| cargo test b4c_ | 0 | 6 passed / 0 failed | b5_green_regressions.txt |
| cargo test b3m_ | 0 | 10 passed / 0 failed | b5_green_regressions.txt |
| cargo test b2_ | 0 | 11 passed / 0 failed | b5_green_regressions.txt |
| cargo fmt --check | 0 | clean | b5_green_aux_gates.txt |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean | b5_green_aux_gates.txt |
| python tools/test_tool_risk_rust_parity.py | 0 | OK | b5_green_aux_gates.txt |
| git diff --check | 0 | clean | b5_green_aux_gates.txt |

RED -> GREEN: B5 7/11 -> 18/0; Workspace 221/11/6 -> 232/0/6.

---

# B5 GREEN EVIDENCE CLOSURE (2026-07-29, tree ae579fb9)

| Suite | Exit | Result | Evidence |
|---|---:|---|---|
| cargo test b5_ | 0 | 18 passed / 0 failed | b5_closure_b5.txt |
| cargo test --workspace | 0 | 232 passed / 0 failed / 6 ignored | b5_closure_workspace.txt |
| cargo test b4a_ | 0 | 10 passed / 0 failed | b5_closure_b4a.txt |
| cargo test b4c_ | 0 | 6 passed / 0 failed | b5_closure_b4c.txt |
| cargo test b3m_ | 0 | 10 passed / 0 failed | b5_closure_b3m.txt |
| cargo test b2_ | 0 | 11 passed / 0 failed | b5_closure_b2.txt |
| cargo fmt --check | 0 | clean | b5_closure_fmt.txt |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean | b5_closure_clippy.txt |
| python tools/test_tool_risk_rust_parity.py | 0 | OK | b5_closure_parity.txt |
| git diff --check | 0 | clean | b5_closure_diffcheck.txt |
| python scripts/check_evidence_provenance.py | 0 | 0 STALE / 0 BODY_MISMATCH (65 fresh) | (closure refresh) |

---

# B5 EVIDENCE INTEGRITY REPAIR (2026-07-29, tree ae579fb9)

Fresh gates (b5_integrity_*, ae579fb9):
| Suite | Exit | Result |
|---|---:|---|
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test --workspace | 0 | 232 passed / 0 failed / 6 ignored |
| cargo test b4a_/b4c_/b3m_/b2_ | 0 | 10/0, 6/0, 10/0, 11/0 |
| cargo fmt --check | 0 | clean |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean |
| python tools/test_tool_risk_rust_parity.py | 0 | OK |
| git diff --check | 0 | clean |

Provenance (honest): check_evidence_provenance.py exit 1; 46 STALE (historical, original digests);
0 BODY_MISMATCH; 0 MISSING_FIELD; 75 files (29 current fresh + 46 historical STALE).
Status: B5_EVIDENCE_MODEL_BLOCKED (checker model does not support historical evidence).

---

# B5 EVIDENCE MODEL FIX (2026-07-29, tree 5255984dac8b2014)

Evidence checks:
| Check | Exit | Result |
|---|---:|---|
| python scripts/check_evidence_provenance.py (current) | 0 | 39 valid, 0 STALE, 0 BODY_MISMATCH |
| python scripts/check_historical_evidence.py (historical) | 0 | 46 valid, 0 BODY_MISMATCH, original digests preserved |

Gates (tree 5255984dac8b2014):
| Suite | Exit | Result |
|---|---:|---|
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test --workspace | 0 | 232 passed / 0 failed / 6 ignored |
| cargo test b4a_/b4c_/b3m_/b2_ | 0 | 10/0, 6/0, 10/0, 11/0 |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean |
| cargo fmt --check | 0 | clean |
| git diff --check | 0 | clean |

Status: B5_EVIDENCE_MODEL_FIXED, NEXT_ALLOWED=B5L_RED.

---

# B5L RED (2026-07-29, tree dde088cfdc)

| Suite | Exit | Result |
|---|---:|---|
| cargo test b5l_ (focused) | 101 | 8 passed / 8 failed (EXPECTED_B5L_RED) |
| cargo test --workspace | 101 | 240 passed / 8 failed / 6 ignored |
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test b4a_/b4c_/b3m_/b2_ | 0 | 10/0, 6/0, 10/0, 11/0 |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean |
| cargo fmt --check | 0 | clean |
| git diff --check | 0 | clean |
| check_evidence_provenance.py (current) | 0 | 48 fresh, 0 STALE, 0 BODY_MISMATCH |
| check_historical_evidence.py (historical) | 0 | 46 valid, 0 BODY_MISMATCH |

INTENTIONAL_RED=B5L. Status: B5L RED (awaiting final review).

---

# B5L GREEN (2026-07-29, tree 0b960196)

| Suite | Exit | Result |
|---|---:|---|
| cargo test b5l_ (focused GREEN) | 0 | 16 passed / 0 failed |
| cargo test --workspace | 0 | 248 passed / 0 failed / 6 ignored |
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test b4a_/b4c_/b3m_/b2_ | 0 | 10/0, 6/0, 10/0, 11/0 |
| cargo clippy --workspace --all-targets -- -D warnings | 0 | clean |
| cargo fmt --check | 0 | clean |
| python tools/test_tool_risk_rust_parity.py | 0 | OK |
| git diff --check | 0 | clean |
| check_evidence_provenance.py (current) | 0 | 63 fresh, 0 STALE, 0 BODY_MISMATCH |
| check_historical_evidence.py (historical) | 0 | 46 valid, 0 BODY_MISMATCH |

Status: B5L_GREEN_COMPLETE, NEXT_ALLOWED=B5LP_RED.

---

# B5LP RED Test Results (2026-07-30)

Tree digest: 0b9601963996cb231a822dfb2de031679712b1432cca4b11e43b86fac24e6fe8
HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364

## Pre-change baseline

| Command | Exit | Result |
|---|---:|---|
| python tools/test_adr015_tool_parsing.py | 0 | 45 tests, OK (skipped=1) |
| python tools/test_v6846_tool_execution.py | 0 | 17 tests, OK |
| cargo test b5l | 0 | 16 passed / 0 failed |
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test --workspace | 0 | 248 passed / 0 failed / 6 ignored |
| cargo fmt --check | 0 | clean |
| cargo clippy | 0 | clean |
| python tools/test_tool_risk_rust_parity.py | 0 | OK |

## Focused intentional RED

| Command | Exit | Result |
|---|---:|---|
| python tools/test_adr015_tool_parsing.py | 1 | 65 tests, FAILED (failures=10, skipped=1) |

Classification:
- EXPECTED_EXISTING_PASS: 54 (44 existing + 10 B5LP positive/guards)
- EXPECTED_B5LP_RED: 10 (all "GatewayError not raised")
- INVALID_TEST_FAILURE: 0
- UNRELATED_REGRESSION: 0

INTENTIONAL_RED=B5LP

## Complete Python gate

| Command | Exit | Result |
|---|---:|---|
| python tools/test_adr015_tool_parsing.py | 1 | 10 intentional RED failures |
| python tools/test_v6846_tool_execution.py | 0 | 17 tests OK |

## Rust regressions

| Command | Exit | Result |
|---|---:|---|
| cargo test b5l | 0 | 16 passed / 0 failed |
| cargo test b5_ | 0 | 18 passed / 0 failed |
| cargo test --workspace | 0 | 248 passed / 0 failed / 6 ignored |
| cargo clippy | 0 | clean |
| cargo fmt --check | 0 | clean |
| python tools/test_tool_risk_rust_parity.py | 0 | OK |
| git diff --check | 0 | clean |

## Provenance state

| Command | Exit | Result |
|---|---:|---|
| check_evidence_provenance.py | 0 | 63 fresh, 0 STALE |
| check_historical_evidence.py | 0 | 46 valid, 0 BODY_MISMATCH |
