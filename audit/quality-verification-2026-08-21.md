# LocalComet extended hidden quality verification — 2026-08-21

## Scope

This pass covers Computer Use, local-model response lifecycle, llama.cpp engine smoke, user-facing setup/chat controls, and reproducible test infrastructure. All operational checks were hidden. No user desktop action, browser session, model deletion, or external provider call was performed.

## Test-system additions

| Layer | Added coverage | Result |
|---|---|---|
| Computer Use | `tests/test_computer_use_quality_contracts.py` adds 7 deterministic fail-closed assertions: destructive/terminal block, unknown folders, unknown apps, secret-text confirmation, simulated hotkeys, and non-executing grounded fallback. | PASS — 7/7 |
| UI journey | `desktop/localcomet-desktop/tests/user-journey-quality.test.ts` adds 5 SSR contracts for first-run next action, discoverable effort, non-modal voice state, managed setup disclosure, and composer accessibility. | PASS — 5/5 |
| Quality runner | `scripts/run_hidden_quality_suite.py` groups existing Computer Use reliability, new Computer Use/UI contracts, and optional isolated runtime smoke. | PASS twice with `--runtime-smoke` |
| Model engine | Existing `tests/hidden_llama_runtime_smoke.ps1` runs Qwen3-1.7B via a loopback-only test server, checks first answer, continuation and fresh chat, then stops only that server. | PASS twice; latest run 1.99 seconds wall-clock |

## Open-source patterns adopted

The suite follows three practical tiers: deterministic unit/component tests, synthetic integration contracts, then an isolated model-runtime smoke. This reflects scoped integration practice in Ollama and clean separation of server readiness from actual completion behavior in llama.cpp.[1][2] Computer Use remains fixture/simulation-first and retains the LocalComet approval boundary instead of adopting unrestricted local execution.[3]

## Expanded hidden verification

| Gate | Current result |
|---|---|
| Svelte check | PASS — 0 errors, 0 warnings |
| Vitest | PASS — 27 files, 409 tests |
| Rust `cargo test` | PASS — 536 library tests |
| Rust formatting and clippy | PASS — `cargo fmt --check`; `cargo clippy --all-targets --all-features -- -D warnings` |
| Required Python/security/parity set | PASS, including bundle parity, trust chain, command parity, UI fake-state, ADR-015 parsing, CLI smoke and the new Computer Use contracts |
| Real sidecar require mode | PASS — no silent skip |
| Evidence/provenance | PASS — 4 files fresh and intact, tree `e72ada2544f41e06…` |

## Findings and decisions

The expanded tests exposed two test-assumption issues, not product failures: SSR starts the effort store at its truthful `Off` state, and the effort popup is correctly a `listbox` rather than a generic menu. The tests were corrected to verify actual UI contracts. No confirmed new engine, model-response or Computer Use product defect was found in this pass, so no speculative runtime tuning was applied.

## Deliberate limits

The isolated Qwen3-1.7B smoke is a **behavioral smoke**, not a benchmark for 27B throughput, GPU offload, or all hardware combinations. Real visible desktop automation is deliberately not part of this hidden suite; it remains behind approval/allowlists and must be tested by a user-approved visible acceptance session when needed.

## References

[1]: https://github.com/ollama/ollama/blob/main/integration/README.md
[2]: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
[3]: https://github.com/openinterpreter/openinterpreter
