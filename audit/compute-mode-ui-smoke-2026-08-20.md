# Compute mode UI smoke — 2026-08-20

## Verified observations

- LocalComet dev build started successfully after a graceful close of the previous process.
- `startup.log` recorded `backend_start success` and the window `LocalComet` was visible.
- Vite endpoint `http://127.0.0.1:1420/` returned HTTP 200.
- The chat UI loaded in the connected local browser with Russian i18n and the existing effort selector.
- Settings opened successfully and the `Модели` section rendered the existing engine variant selector and model selector.
- The compute mode selector was intentionally not visible while the selected runtime was not installed. This confirms the requested `runtimeInstalled` visibility guard at the current empty-catalog state.
- No model/runtime artifacts were available in this dev AppData state, so the hybrid Qwen3.8 launch could not be attempted from this session without first restoring the managed artifact catalog/runtime state.

## Scope note

No destructive action was taken. The browser was used only for local UI inspection and refresh; no download, removal, approval, model connection, or runtime launch was submitted.

## External validation

The official `ggml-org/llama.cpp` CLI guide documents `--gpu-layers` / `--n-gpu-layers N` as the maximum number of layers stored in VRAM, with exact numeric values supported alongside `auto` and `all`. Therefore the LocalComet hybrid profile using a bounded numeric GPU-layer override is aligned with the upstream command semantics; the CPU profile using `0` is the expected no-layer-offload path. Source: https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md

## LC_START_101 recovery

A direct launch of the debug-target executable from `%LOCALAPPDATA%\LocalComet\CargoTarget\debug` reproduced `LC_START_101` with `sidecar_unavailable`. Source inspection showed that debug builds require `LOCALCOMET_TEST_PROJECT_ROOT` and `LOCALCOMET_TEST_PYTHON`; launching the executable directly does not provide those variables. The approved `tools/start_localcomet.py` launcher supplies them and successfully started the current build.

Verified after the corrected launch: `localcomet-desktop` remained running with a visible `LocalComet` window, `startup.log` recorded `single_instance success`, `window_display success`, and `backend_readiness success`, and the local UI loaded without the startup dialog. The independent PID 35488 `server.py` process on port 8787 was not stopped or modified.

The packaged-style failure was therefore a launch-path misuse of a debug executable, not evidence that the runtime or user model artifacts were corrupt.

## Post-recovery Model Manager check

After the corrected launcher restart, the local UI opened and Settings → Models rendered normally. Refresh completed without a new startup dialog, but the current `LocalCometDev` AppData presented an empty managed runtime/model catalog: the engine was shown as not installed, the selected model as unavailable, and the compute mode selector remained hidden by design because no runtime was reported installed. Consequently, this particular dev AppData could not perform the Qwen3.8 hybrid launch; the packaged AppData contains the larger model/runtime artifacts, but direct execution of its debug-target executable is not a valid launch path.
