# Qwen3.8 27B crash-test visual findings — 2026-08-20

The hidden LocalComet runtime was opened through CDP on port 9223. The ModelFit screen opened correctly. The Hugging Face browser displayed the approved artifacts and the search field, but the backend search returned no results for `Qwen3.8-27B`, `qwen`, and the full repo ID; the canonical Hugging Face repo was therefore used through LocalComet's own Tauri `request_approval` + `start_approved_artifact_download` flow.

The downloaded artifact is:

- Display name: `Qwen3.8-27B-Q4_K_M.gguf`
- Repository: `bartowski/Qwen3.8-27B-GGUF`
- Expected bytes: `17,772,537,440`
- SHA-256: `e103abf9d914d1d7b2f2592f055f2759a71195c350a01c135f71aaae86bca52b`
- Artifact ID: `custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff`
- License metadata: `null` / UI label `Не определена`

The Tauri download job reached `completed` with `received_bytes == expected_bytes`. The model manager select contains the custom model and it can be selected. The Settings model card currently shows `Не установлено` despite the completed custom download because the direct Tauri download path bypassed the frontend store refresh; this is a UI state refresh issue, not yet a verified runtime launch.

The selected runtime is `llama.cpp b10068` with GPU Vulkan. The UI reports NVIDIA GeForce RTX 5070 and 11,943 MiB / 11,175 MiB free in the engine card before loading. The Qwen3.8 model is 16,949 MiB in the model manager. The next safe step is to refresh managed status from the same runtime, select the custom model, and invoke the normal managed connect/start path; no existing model has been removed.
