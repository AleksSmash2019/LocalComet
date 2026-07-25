#!/usr/bin/env bash
# LocalComet release build pipeline (Linux/CI).
#
# NOTE: A Windows build.ps1 is intentionally NOT provided because the project
# rules (AGENTS.md) forbid creating .ps1 files. On Windows, run the same steps
# manually or via this script under Git-Bash/WSL.
#
# Each step fails fast: a broken product is never bundled.
set -euo pipefail
START=$(date +%s)

step() { echo ""; echo "[$1/7] $2..."; }

step 1 "Preflight"
python3 scripts/doctor.py

step 2 "Gates"
python3 tests/test_trust_chain_invariants.py
python3 scripts/check_command_parity.py
python3 scripts/check_tool_risk_registry.py
python3 scripts/check_ui_fake_state.py

step 3 "Evidence provenance"
python3 scripts/refresh_evidence.py
python3 scripts/check_evidence_provenance.py

step 4 "Rust: fmt + clippy + tests"
(
  cd desktop/localcomet-desktop/src-tauri
  cargo fmt --check
  cargo clippy --all-targets --all-features -- -D warnings
  cargo test --release
)

step 5 "Frontend: npm ci + build"
(
  cd desktop/localcomet-desktop
  npm ci
  npm run build
)

step 6 "Smoke test (pre-bundle)"
if [ -f scripts/smoke_test.py ]; then
  python3 scripts/smoke_test.py --mode=cli
else
  echo "smoke_test.py not present; skipping (see docs/unverified-ledger.md)"
fi

step 7 "Tauri bundle"
(
  cd desktop/localcomet-desktop
  npx tauri build
)

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "=== BUILD COMPLETE ==="
echo "Time: ${ELAPSED}s"
