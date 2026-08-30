# LocalComet — strict acceptance snapshot

**Date:** 2026-08-27  
**Branch:** `feat/up00-wp01-windows-one-click-launch`  
**HEAD:** `74f527d5cc97526a791eca81a8d995e2cc5a6aa7`  
**WIP:** current dirty WIP is preserved; no commit, reset, rebase or cleanup was performed. A fresh post-native snapshot is recorded separately in the dashboard.

## Acceptance policy

A unit test, mock, architecture note, model self-report or frontend state is not sufficient for `VERIFIED_SUCCESS`. A success requires the real production path, an independent postcondition, repeatability, negative-path coverage and a saved trace. The accepted verdict vocabulary is `VERIFIED_SUCCESS`, `VERIFIED_BLOCKED`, `VERIFIED_FAILED`, `PENDING_TERMINAL` and `NOT_INDEPENDENTLY_VERIFIED`.

Critical Computer Use, provenance and data-safety blockers cap the release score regardless of the weighted average. A compile-only coding result is never equivalent to behavior verification. A timeout remains `PENDING_TERMINAL` until cleanup and a terminal verdict are proven. A blocked action is positive safety evidence only when the protected postcondition remains unchanged.

## Confirmed changes in this acceptance pass

The Rust approval payload and descriptor now carry optional model request/action correlation and the canonical input digest. Correlation syntax is validated before issuance. Frontend approval state gives the server event precedence over stale mutable UI correlation, and the modal renders the actual digest. The legacy approval card no longer uses an expiry timestamp as a request identifier; its remaining compatibility semantics are not treated as native prompt identity proof.

The Computer Use classifier remains fail-closed: a model/UI `PASS` cannot become independently verified when required process, text, screenshot, browser or correlation evidence is absent. Browser read-only cases require an HTTPS allowlisted URL, non-empty title, broker CDP port/PID and hidden-window PID. Composer readiness requires the explicit region marker in addition to an enabled editor and send control. Uncertain same-prompt submit retries reuse one logical token.

The native harness was additionally repaired after the follow-up run demonstrated a real navigation ambiguity: its old text fallback could click the HF navigation label `Подобрать модель`, leaving only the shell/sidebar and never reaching the composer. The product now exposes stable IDs for the chat setup action and managed primary install/connect action; the harness uses those IDs first and records bounded setup diagnostics. A harness-only WebView2 `--disable-gpu` probe then passed native startup, while the full model-driven Notepad run reached model readiness and submit but remained `NOT_INDEPENDENTLY_VERIFIED` because CDP observation failed with WinError 10061 and no independent text/correlation postcondition was recorded.

## Gate results

| Gate | Result |
|---|---|
| `npm run check` | PASS — `svelte-check`: 0 errors, 0 warnings |
| Full Vitest | PASS — 39 files, 552 tests |
| Rust full library suite | PASS — 727 passed, 0 failed, 7 ignored (`audit/gates_cycle7_rust_20260827.log`) |
| Rust formatting | PASS — `cargo fmt --all -- --check` |
| Rust clippy | PASS — `cargo clippy --all-targets --all-features -- -D warnings` |
| ADR-015 | PASS — 70 tests, 1 skipped |
| Command parity | PASS — 79 commands registered and invoked |
| Tool risk registry | PASS — 7 console tools, 11 sidecar tools, 21 registry entries valid |
| UI fake-state | PASS — 114 frontend files |
| Bundle parity | PASS — 430 shipped modules match source across 2 locations |
| CLI smoke | PASS — 8 passed, 0 failed |
| Real-sidecar | PASS — require mode, system CPython 3.14, no silent skips |
| Evidence refresh | PASS — `evidence refreshed: all gates green` |
| Evidence provenance | PASS — 4/4 current evidence files fresh and intact |
| Evidence tree | `40f20bc153703ee549081e3edf51e66fb48af3e84d303cea97161a17db9a306b` |

The exact current gate logs are `audit/gates_cycle15_frontend_20260827.log`, `audit/gates_cycle15_rust_20260827.log` and `audit/gates_cycle16_python_20260827.log`. The hidden evidence/CDP regression suite is 26 tests after the native-process liveness guard and turn-observation exit check.

## Native acceptance status

Model-driven native Computer Use remains `NOT_INDEPENDENTLY_VERIFIED`. The earlier post-patch retry `isolated_hidden_desktop_postpatch_retry_20260827` failed at Tauri launch with `STATUS_ACCESS_VIOLATION` (`0xc0000005`). After the harness-only `--disable-gpu` mitigation, probe-only native startup completed `PROBE_DONE/ok=true`; the liveness-instrumented run `isolated_hidden_desktop_gpu_liveness_20260827` reached `model_ready=true` and `submitted=1`, then recorded native PID `12004` exiting with return code `3221225477` (`0xc0000005`) at `turn_observation`; no terminal pill, request/action correlation or expected Notepad text marker was observed. A later broker-telemetry run reproduced `model_ready=true`, `submitted=1` and the same `STATUS_ACCESS_VIOLATION`; its `tauri_app.log` records the crash, but no owned runtime telemetry marker was found, so the exact production crash location is not claimed. The separate deterministic-intent run ended `submitted=0/NO_EVIDENCE`. Final classification remains `NOT_INDEPENDENTLY_VERIFIED`; an independent native action/postcondition and acceptance run remain mandatory before any score increase.

Browser URL/title/CDP semantic proof, native modal approval, native restart recovery, native files/folders acceptance, production behavioral coding and repeated native cleanup remain open. Historical browser and Notepad artifacts remain historical and cannot be promoted by the new code or by the green unit gates.

## Release blockers

RHVoice `Elena` and `Aleksandr` registration and silent generation are verified, as are gender persistence, cancellation and Russian-only routing. Subjective voice quality still requires the user to listen. Copyright/license inventory remains a release blocker and is not legal clearance: root application license, RHVoice voice-specific terms, exact Qwen GGUF provenance and retained third-party notices remain unresolved.

## Honest score

**Current score: 7.8/10.** The current cycle materially hardens approval correlation, authoritative prompt expiry, fail-closed Computer Use classification, browser semantic policy, composer readiness, submit idempotency, legacy approval identity semantics, native setup selectors, managed-runtime lifecycle transitions, native-process liveness evidence, turn-observation crash evidence and harness-only GPU startup probing. It does not justify 9/10 or 9.5/10 because the native child exits with `0xc0000005` during model-driven turn observation, leaving no terminal action/text/correlation postcondition; deterministic intent has no broker action evidence; restart/recovery and release provenance remain incomplete, and licensing blockers remain open. The 9.5/10 value is a hard target, not an achieved score.

## Evidence files

- `audit/gates_cycle15_frontend_20260827.log`
- `audit/gates_cycle15_rust_20260827.log`
- `audit/gates_cycle16_python_20260827.log`
- `audit/strict_acceptance_20260827.md`
- `audit/copyright_license_audit_20260826.md`
- `audit/independent_coder_report_audit_20260827.md`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_followup_20260827/isolated_hidden_summary.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_followup_20260827/model_setup_blocked.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_postpatch_retry_20260827/native_terminal.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_postpatch_retry_20260827/tauri_app.log`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_probe_20260827/isolated_hidden_summary.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_notepad_20260827/isolated_hidden_summary.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_notepad_20260827/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_liveness_20260827/isolated_hidden_summary.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_liveness_20260827/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_broker_telemetry_notepad_20260827/isolated_hidden_summary.json`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_broker_telemetry_notepad_20260827/isolated_hidden_user_runs.jsonl`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_broker_telemetry_notepad_20260827/tauri_app.log`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_intent_notepad_liveness_20260827/isolated_hidden_user_runs.jsonl`
- `artifacts/evidence/*.txt` with current tree digest `40f20bc153703ee549081e3edf51e66fb48af3e84d303cea97161a17db9a306b`
