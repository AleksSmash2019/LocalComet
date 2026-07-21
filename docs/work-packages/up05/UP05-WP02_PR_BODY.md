# UP05-WP02 — Proposed Change Description

## Summary

Adds a deliberately narrow LocalComet bootstrap acquisition path and Settings
model manager for the already approved llama.cpp runtime and Qwen GGUF model.

## Security boundary

Catalog data, not the frontend, controls URLs, redirect hosts, expected bytes,
hashes, filenames, formats, and managed destinations. Downloads require a user
confirmation and do not grant the model, chat, or frontend internet authority.

## Validation

The source checkpoint passes focused Rust acquisition tests, frontend
bridge/UI tests, the full frontend test/check/build sequence, isolated locked
offline Rust checks, and warnings-denied Clippy. Normal Rust packaging checks,
release build, bundle, and isolated acquisition acceptance remain blocked by
the missing baseline sidecar resource
`binaries/localcomet-core-x86_64-pc-windows-msvc.exe`.

This branch is the dependency base for Phase B only after the Phase A gate is
unblocked and passes; it is not based on `main` and is not pushed.
