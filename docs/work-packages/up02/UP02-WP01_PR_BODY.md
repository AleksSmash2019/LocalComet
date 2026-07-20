# UP02-WP01 PR Body

## Summary

- add an immutable LocalComet `AssistantContext` to the existing typed local-model request path;
- construct a deterministic system instruction before the unchanged user message;
- default model replies to the selected UI locale and declare project context unavailable;
- add bounded first-use, loading, failed/timed-out, cancelled, and retry guidance;
- add a localized read-only capability summary to Settings/About;
- preserve real streaming, Stop, retry, readiness, HF1 scrolling/composer behaviour, minimal navigation, and the offline installer.

## Trust boundary

The frontend sends only the existing validated locale enum. Tauri authors the full context with fixed capability values. The local gateway rejects missing, extra, unknown, or capability-changing fields and builds the provider system message deterministically. System content is not rendered or logged to user-visible diagnostics.

## Capability truth

Available: local chat and local model inference.

Unavailable: internet, email, browser, files, Vault, Computer Use, shell, and external tools. Project-specific context is not supplied. User text cannot change these values.

## Verification

The final evidence package records frontend, Rust/Tauri, backend, security-negative, installed semantic, 40-row regression, installer, uninstall/reinstall, process cleanup, and rollback results. Any critical truthfulness or existing-function regression failure blocks completion.

## Distribution

Internal unsigned build only. The bootstrap model/runtime are not bundled. No push or remote pull request is performed by this mission.
