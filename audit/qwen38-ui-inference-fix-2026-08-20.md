# Qwen3.8 UI inference fix — 2026-08-20

## Root cause

The Python gateway and llama.cpp inference path worked independently, and Rust acceptance projection initially omitted `effort`. After adding `effort` to the Rust acceptance contract, `model_turn_start` validated successfully but the first model event still failed. The Python `model.turn.started` and subsequent events include `effort` in event metadata. Rust `validate_model_event_metadata` treated that field as an unknown extra key, returned `protocol_mismatch` (`model event metadata shape mismatch`), and `route_model_event` emitted a synthetic `model.turn.failed` event. The UI therefore displayed the generic retry error immediately after acceptance.

## Fix

`control_plane.rs` now carries the requested effort on `ModelRequestEntry`, includes `effort` in the exact event metadata allowlist, validates it against the reserved turn effort, and projects it with the event metadata. Existing acceptance and `model.turn.start` payload contracts also include and validate `effort`. `live_e2e.rs` was updated for the new reserve signature. Regression fixtures now include `effort: "off"` and verify that missing effort is rejected.

## Confirmed tests

- `cargo fmt` completed successfully.
- `cargo test typed_model_command_payloads_are_exact --lib --no-default-features` — PASS.
- `cargo test model_acceptance_requires_all_immutable_fields --lib --no-default-features` — PASS.
- `cargo test model_event --lib --no-default-features` — 7/7 PASS.
- `cargo test model_event_metadata_is_transactional_exact_and_projected --lib --no-default-features` — PASS.

## Final UI smoke

The patched Tauri/WebView2 build launched through the supported hidden launcher. Managed runtime status was READY with model `Qwen3.8-27B-Q4_K_M.gguf`, `inference_ready=true`, and `last_error=null`. The UI prompt `Ответь одним коротким предложением по-русски: модель запущена?` produced the assistant response `Да, модель запущена.`. The compact failure probe returned `null`, confirming no fresh `model.turn.failed` event.

The temporary frontend probe used during diagnosis is being removed before final gates; the audit helper remains available for future diagnostics.
