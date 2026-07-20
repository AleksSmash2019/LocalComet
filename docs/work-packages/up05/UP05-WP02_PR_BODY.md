# UP05-WP02 — Proposed Change Description

## Summary

Adds a deliberately narrow LocalComet bootstrap acquisition path and Settings
model manager for the already approved llama.cpp runtime and Qwen GGUF model.

## Security boundary

Catalog data, not the frontend, controls URLs, redirect hosts, expected bytes,
hashes, filenames, formats, and managed destinations. Downloads require a user
confirmation and do not grant the model, chat, or frontend internet authority.

## Validation

Run the focused Rust acquisition tests, frontend bridge/UI tests, full frontend
test/check/build, locked offline Rust checks, Clippy, release build, bundle, and
isolated acquisition acceptance. This branch is the dependency base for Phase B;
it is not based on `main` and is not pushed.
