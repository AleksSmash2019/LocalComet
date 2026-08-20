# Qwen3.8 27B Q4_K_M engine crash test — 2026-08-20

## Scope

This was a controlled engine stress test requested by the user. No existing model was deleted, no source files were changed, and the test used the LocalComet artifact acquisition and managed-runtime command path. The selected runtime was `llama.cpp b10068` with the Vulkan bootstrap on an NVIDIA RTX 5070 12 GB system.

## Artifact acquisition and verification

The model was downloaded through LocalComet's Tauri approval and artifact download flow from the canonical Hugging Face URL:

`https://huggingface.co/bartowski/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q4_K_M.gguf`

The download job completed with exact size equality. The authoritative custom-artifact registry and validation cache both report a valid artifact.

| Field | Verified value |
|---|---|
| Display name | `Qwen3.8-27B-Q4_K_M.gguf` |
| Artifact ID | `custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff` |
| Expected/observed bytes | `17,772,537,440` / `17,772,537,440` |
| Expected/observed SHA-256 | `e103abf9d914d1d7b2f2592f055f2759a71195c350a01c135f71aaae86bca52b` / same |
| Artifact validation | `installation_status=valid`, `validation_code=valid` |
| Runtime readiness | `readiness=ready`, `launchable=true`, `compatibility=compatible` |
| License metadata | `null`, displayed as `Не определена` |
| Storage path | `%LOCALAPPDATA%\\LocalCometDev\\app-data\\models\\custom\\custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff\\Qwen3.8-27B-Q4_K_M.gguf` |

## Runtime test

The runtime start request used the Vulkan runtime, the verified custom SHA-256, and default context/GPU-layer preferences. The request passed the managed readiness check. During the subsequent start/validation operation, the LocalComet desktop process disappeared and CDP port 9223 closed. At the same time, the sidecar on port 8787 remained listening, which means the desktop process did not complete its normal supervisor cleanup path.

The last managed-runtime log record is:

`timestamp_unix=1787183182 phase=validation status=begin code=LC_START_...`

There is no corresponding validation success/failure record, no runtime-ready record, and no Windows Application Error event or dump in the inspected recent logs. Therefore the verified conclusion is that **the desktop/runtime start path aborted during validation or engine startup**, but the exact native fault code is not yet proven from the available logs. It is not appropriate to claim a confirmed Vulkan out-of-memory error without a native crash record.

## Recovery state

The LocalComet desktop process is no longer running after the stress test. The Python sidecar remains on port 8787. The downloaded file and validation records are intact. Existing Qwen2.5 models remain untouched. The next safe recovery action is to start LocalComet again in visible mode using the normal launcher, then run the smaller Qwen3 model first and keep the 27B artifact installed but not selected as the default.

## User-facing conclusion

The 27B file was successfully downloaded and cryptographically verified. On this machine, the Vulkan start attempt is not currently stable: the application disappeared before producing a normal runtime failure report. The engine needs a guarded failure path for oversized custom models so that a failed start returns a visible error and performs supervisor cleanup instead of leaving the sidecar behind.
