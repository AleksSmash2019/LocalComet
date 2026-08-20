# LocalComet quality baseline — 2026-08-21

## Source and runtime state

The working tree is intentionally not clean and contains a large set of pre-existing modified and untracked audit artifacts. No file is to be removed as part of this pass. The main LocalComet process was not running when the baseline was sampled; the most recent startup log nevertheless records `LC_START_200`. This is a runtime observation, not proof of an active model or sidecar.

## Existing coverage

| Area | Current baseline |
|---|---|
| Python test files | 15 `test_*.py` files, including a focused 5-case Computer Use reliability test. |
| Frontend test files | 26 Vitest files. |
| Computer Use contracts | Existing synthetic-fixture contract suite covers safe click/type, file-change confirmation, destructive-goal block and fixture restoration. |
| Model runtime | The existing hidden `Qwen3-1.7B` llama.cpp smoke script exercises first response, continuation and a new chat on an isolated loopback port. |

## Current hidden model result

`tests/hidden_llama_runtime_smoke.ps1` completed successfully on the isolated CPU Qwen3-1.7B profile. The first response, continuation and fresh-chat responses completed; wall-clock execution was **1.99 seconds**. This is a smoke signal, not a throughput benchmark or a claim for the larger 27B model.

## Test-system gap to close

Current checks are distributed across component smoke, model gateway tests, Computer Use contracts and scripts. The next work item is an explicit reproducible quality suite that asserts the user-visible invariants of: model lifecycle, engine selection fallback, Computer Use action/result states and the first-run UI path.

## Confirmed test targets

`test_computer_use_reliability.py` currently covers Unicode input, dialog classification, a simulated Notepad plan and clipboard preservation. It does not explicitly assert unknown-folder blocking, sensitive-text rejection, destructive-goal rejection, or unknown application non-execution. The extended suite will add those fail-closed regressions without operating the desktop.

The frontend Model Gateway tests already model terminal turn telemetry, successful and failed Computer Use calls, malformed tool event rejection, and Vulkan fallback payload preservation. The supplemental UI suite will focus on rendered user-facing truth: the effort control, non-modal voice failure path, model setup's selected-model disclosure, and the onboarding next action.
