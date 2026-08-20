# Hybrid/offload research notes — 2026-08-20

## Sources opened

1. [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
2. [LM Studio 0.3.14 Multi-GPU Controls](https://lmstudio.ai/blog/lmstudio-v0.3.14)

## Confirmed findings

The official llama.cpp server README documents `--ctx-size N` as the prompt context size, with `0` meaning the value loaded from the model. It documents `--gpu-layers` / `--n-gpu-layers N` as the maximum number of layers stored in VRAM and, in the current README, supports an exact number, `auto`, or `all`. It also documents split modes for multi-GPU use. The README does not make a blanket promise that a manually fixed GPU-layer value is optimal for every model and device.

The official LM Studio 0.3.14 article describes a dedicated-GPU-memory mode in which model weights are kept within dedicated GPU memory; if the weights are too large, LM Studio automatically reduces GPU offload so the remainder stays in system RAM. The article explicitly distinguishes model weights from context buffers: context may still spill into shared GPU memory as the context grows. It also states that, in LM Studio's testing, splitting weights between dedicated GPU memory and system RAM was faster than using shared GPU memory, while noting that behavior can vary by system.

## Immediate implication for LocalComet

The current LocalComet Hybrid profile (`ctx=2048`, `gpu_layers=8`) is a manual fixed profile, not an automatic fit policy. A robust design should preserve manual Hybrid for reproducibility but add an Auto/Fit policy that lets llama.cpp determine a safe layer allocation, uses a bounded minimum context, and records the resolved runtime parameters. The Qwen3.8 failure must still be treated separately from model loading: the direct current llama.cpp endpoint returned content successfully, so engine fitting and gateway/UI event compatibility are distinct concerns.

## Additional official LM Studio findings

The official `lms load` documentation exposes `--gpu` values `0-1`, `off`, and `max`. A numeric fraction means a percentage of layers offloaded to GPU; if the flag is omitted, LM Studio automatically determines optimal GPU usage. The same command exposes `--context-length` and `--estimate-only`; the estimator accounts for context length and other resource factors before loading.

The official Per-model Defaults documentation states that load settings can be saved per model and reused by both the app and `lms load`. It specifically lists GPU offload, context size, and Flash Attention as model-level defaults, while still allowing load-time changes before starting a model.

These sources support adding an explicit `auto/fit` mode in LocalComet rather than pretending that a fixed eight-layer preset is universally optimal. They also support keeping manual overrides available for reproducibility and exposing an estimate/readiness phase before inference.

## Official llama.cpp multi-GPU findings

The current official llama.cpp multi-GPU guide states that `--fit on|off` auto-fits **unset** arguments to device memory and warns that the feature is not supported with tensor split. It also warns that `--ctx-size` may need to be set manually to make a model fit. The guide describes layer splitting as the default/most compatible multi-GPU strategy and explains that when a model does not fit in accelerator VRAM, otherwise part of it must run from slower system RAM.

This is directly relevant to LocalComet: a true Auto/Fit mode must not pass a fixed `--gpu-layers` value if it expects llama.cpp to choose the allocation, and it must pass a bounded context override when memory is tight. The existing manual Hybrid mode can remain an explicit reproducible fallback (`--gpu-layers 8`, `--ctx-size 2048`).
