# LocalComet native Computer Use crash analysis

**Date:** 2026-08-27  
**Scope:** hidden Windows native Tauri runs only; no user desktop/profile/processes were used.  
**Current verdict:** the native Computer Use acceptance gate remains **NOT_INDEPENDENTLY_VERIFIED**. The project score remains **7.8/10**.

## 1. Hard facts

| Run | Binary evidence | Native observation | Result |
|---|---|---|---|
| `isolated_hidden_desktop_gpu_liveness_20260827` | Hidden run; PID 12004; source fingerprint recorded in run artifact | Model/tool path reached observation; native process exited with `0xC0000005`; subsequent CDP returned WinError 10061 | `NOT_INDEPENDENTLY_VERIFIED` |
| `isolated_hidden_desktop_native_child_monitor_notepad_20260827` | Verified compiled binary; native PID 25356; source fingerprint matched current run | `model_ready=true`, `submitted=1`; native PID 25356 exited `3221225477` (`0xC0000005`) during `turn_observation`; text and correlation proof absent | `NOT_INDEPENDENTLY_VERIFIED` |
| `isolated_hidden_desktop_invisible_notepad_20260827` | Verified compiled binary; native PID 17636; `LOCALCOMET_INVISIBLE=1` was set by the harness | Same `0xC0000005`/WinError 10061 pattern; `model_ready=true`, `submitted=1`; no independent Notepad text proof | `NOT_INDEPENDENTLY_VERIFIED` |
| `isolated_hidden_desktop_native_child_monitor_intent_notepad_20260827` | Verified compiled binary; native PID 9496 | Deterministic intent produced `NO_EVIDENCE`, `submitted=0`, and completed without the model Computer Use dispatch crash | `NOT_INDEPENDENTLY_VERIFIED` |
| `isolated_hidden_desktop_create_process_trace_20260827` | Current source build was verified before launch | Blocked before model setup because CDP port 9223 served foreign `http://localhost:1420/`; the harness correctly refused to interact | `VERIFIED_BLOCKED` at infrastructure/startup layer |

The PID 12004 failure is therefore not an orphaned-CDP success: the liveness guard observed the actual native process exit. A later run with a current verified binary reproduced the same exit code using native PID 25356. The process wrapper/native-child ambiguity was separately fixed in the harness; the reproduced compiled-binary runs do not depend on a live npm wrapper for native liveness.

## 2. What the evidence localizes

The basic hidden Tauri/WebView2 startup path is not sufficient to explain the crash. GPU mitigation alone did not remove it, and `LOCALCOMET_INVISIBLE=1` also did not remove it. The deterministic-intent run stayed native-stable when it did not submit the model-generated Computer Use call. The model-driven run reached `model_ready=true` and emitted a `computer_use` tool request before the native process disappeared.

The strongest current localization is therefore the **model Computer Use dispatch path after tool submission**, not the initial window bootstrap alone. Existing stage telemetry reached `broker_dispatch/start` and `broker_dispatch/pre_spawn` in the trace-sink run. No success, postcondition, continuation, or independent Notepad text evidence was recorded. The most specific remaining boundary is between broker pre-spawn and the Windows spawn/identity/postcondition path; the latest CreateProcess-marker run could not be used for causal proof because it was blocked earlier by a foreign CDP page.

## 3. Hypotheses explicitly weakened or rejected

| Hypothesis | Status | Reason |
|---|---|---|
| Stale WebView/CDP page was mistaken for a live native app | **Rejected for the reproduced crash runs** | The child-PID monitor checked the real `localcomet-desktop.exe`; PID 25356 exited with `0xC0000005` before the observation result. |
| WebView2 GPU compositor alone caused the access violation | **Weakened** | Harness-only `--disable-gpu` was active and the crash persisted. |
| Calling `window.show()` on the hidden desktop alone caused the crash | **Weakened** | Harness-only `LOCALCOMET_INVISIBLE=1` was active and the crash persisted. |
| The crash occurs during ordinary hidden startup before model dispatch | **Weakened** | Deterministic intent completed without the model Computer Use dispatch crash; model-driven runs reached submission/observation. |
| An arbitrary user process was killed or used as evidence | **Rejected by cleanup records** | Runs used owner manifests and owner-scoped cleanup; final LocalComet count was zero. |

## 4. Remaining candidate seams

The evidence does **not** prove a single faulting instruction or module. The remaining candidates are: a host-side Tauri/WebView event-loop or IPC callback triggered by the tool request; the host broker's hidden-desktop `CreateProcessW`/`GetProcessTimes`/handle lifecycle; hidden-desktop window enumeration/postcondition code; or a native dependency failure exposed only after tool dispatch. Rust panic is less consistent with the observed Windows access-violation exit code, but no debugger dump is available, so this remains a hypothesis rather than a conclusion.

The stage telemetry path was deliberately bounded and token-free. The current trace sink is restricted to an explicit hidden-harness report directory; it does not log request payloads, approval tokens, digests, or arbitrary production paths. A future native run must use the trace markers to distinguish `broker_create_process:enter`, `return`, `identity_return`, and `handles_closed`; it must not be classified as success unless the independent Notepad postcondition is also present.

## 5. Acceptance impact

The crash blocks at least the native Computer Use, open/type, browser, files/folders, approval-in-native-window, restart/recovery, and broad release acceptance criteria. Source-level gates remain separate and green where recorded; they cannot override this native verdict. The exact score-cap rule therefore keeps the project at **7.8/10** and checkpoint **14/20**.

## 6. Next safe work

The next implementation work is to make the broker boundary robust and observable without changing authorization semantics: preserve the fail-closed trace, add focused Windows-side tests for process identity/desktop binding where possible, review the actual `CreateProcessW` command-line and `STARTUPINFO` construction for native lifetime hazards, and then perform only one fresh bounded run after the source settles. If the faulting module remains unavailable, the correct result is to retain `NOT_INDEPENDENTLY_VERIFIED`, not to infer success from model readiness or a surviving CDP page.

**Supporting artifacts:**

- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_gpu_liveness_20260827/`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_native_child_monitor_notepad_20260827/`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_invisible_notepad_20260827/`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_native_child_monitor_intent_notepad_20260827/`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_create_process_trace_20260827/`
- `Projects/Reports/computer_use_real_actions/isolated_hidden_desktop_trace_sink_notepad_20260827/toolcall_trace.log`
- `tests/test_hidden_evidence_contract.py`
- `tools/run_isolated_hidden_desktop_cu.py`

## 7. Classification vocabulary

This report uses the project vocabulary exactly: `VERIFIED_SUCCESS`, `VERIFIED_BLOCKED`, `VERIFIED_FAILED`, `PENDING_TERMINAL`, and `NOT_INDEPENDENTLY_VERIFIED`. Model readiness, a submitted flag, an open CDP port, a frontend pill, or a log line is not an independent native action postcondition.
