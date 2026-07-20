# UP05-WP02 — Approved Model Acquisition and Basic Model Manager

## Baseline and scope

Phase A starts on `feat/up02-wp01-hf2-ui-hygiene-knowledge` at
`3f01a6b2baef51a27caa09914b5ec75dff365e55`. The checked baseline has a clean
worktree and index; `main` and `origin/main` both remain at
`6c784ace543e345bdb8bd2f778be974dc89f2df5`.

This work package adds one application-owned download path for the existing,
source-controlled bootstrap runtime and model. It does not create a marketplace,
accept user URLs, inspect arbitrary files, change AssistantContext authority, or
read the Vault.

## Current implementation

The approved catalog is
`desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json`.
`src-tauri/src/artifact_trust.rs` validates canonical catalog bytes, managed
relative paths, exact file hashes, model GGUF magic, and live installed state.
Managed roots are under `%LOCALAPPDATA%/LocalComet/runtimes/llama.cpp` and
`%LOCALAPPDATA%/LocalComet/models`.

`src-tauri/src/managed_runtime.rs` starts only the validated llama.cpp binary on
loopback and only connects the approved model. The first-use UI currently tells
the user to connect a model, but cannot acquire missing artifacts. The Settings
drawer has no Models section. Tauri CSP permits only the desktop IPC/loopback
connection; startup makes no artifact-network request.

## Minimum implementation

- Extend the catalog schema with immutable acquisition descriptors for the two
  already approved artifacts.
- Add a typed Rust acquisition manager with catalog-only URLs, redirect-host
  validation, streaming download, cancellation, verification, and atomic install.
- Expose only fixed Tauri commands taking safe artifact/job IDs.
- Add a Settings → Models section with explicit confirmation, bounded progress,
  retry, connection, disconnection, and safe bootstrap-model removal.
- Replace the missing-model dead end with truthful setup guidance.

## Explicit exclusions

No arbitrary URL, generic HTTP/filesystem/process command, cloud inference,
browser authentication, token, telemetry, update check, startup download,
runtime removal, model marketplace, AssistantContext internet authority, Vault
access, or project-context work is in this phase.
