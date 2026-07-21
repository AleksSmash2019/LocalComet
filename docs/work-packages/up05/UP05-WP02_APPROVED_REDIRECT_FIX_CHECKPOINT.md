# UP05-WP02 approved redirect correction checkpoint

Status: `CHECKPOINT_PHASE_A_APPROVED_REDIRECT_FIX_UI_SMOKE_PENDING`

## Source correction

The approved Qwen model URL returned an HTTPS `302` redirect to the exact host
`us.aws.cdn.hf.co`. The prior immutable allowlist did not contain that host, so
the backend correctly rejected the redirect before creating a payload.

Commit `38e64b3a9349a27d9b0df108bf1e4beda23ca3de` adds only
`us.aws.cdn.hf.co` to the entry-specific redirect-host allowlist for
`qwen2.5-1.5b-instruct-q4-k-m`. The runtime artifact does not inherit that
host.

The correction preserves the existing backend-owned contract: exact
case-normalized host equality, HTTPS-only URLs, no explicit port, no userinfo,
and no wildcard, suffix, dynamic, or frontend-provided redirect trust.

The following immutable model fields did not change:

- ID: `qwen2.5-1.5b-instruct-q4-k-m`
- URL: `https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Filename: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Expected bytes: `1117320736`
- Expected SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`

## Redirect evidence and tests

One header-only request to the exact committed model URL returned `302`, with
Location host `us.aws.cdn.hf.co` and HTTPS preserved. No response body or
model payload was saved, and no credentials were sent.

The focused regression tests passed:

- `model_redirect_authority_requires_exact_https_host` accepts the original
  host, each pre-existing exact host, and `us.aws.cdn.hf.co`.
- It rejects HTTP, an explicit port, userinfo, the exact-host suffix and prefix
  attacks, sibling/lookalike hosts, a trailing-dot variant, and an IP literal.
- `embedded_catalog_is_canonical_and_exactly_pinned` verifies the canonical
  catalog digest, the immutable model fields, the exact host list, and that
  the unrelated runtime entry does not inherit the model CDN host.

## Completed verification

- Focused Rust tests: passed.
- Complete Rust suite: `93 passed`, `2 expected ignored`, `0 failed`.
- Frontend suite: `17 files`, `265 passed`.
- Svelte check: `0 errors`; the one pre-existing `LanguageSwitcher` listbox
  tabindex warning remains unchanged.
- Production frontend build: passed.
- `cargo check --locked --offline`: passed.
- `cargo clippy --locked --offline --all-targets -- -D warnings`: passed.
- Normal offline NSIS build with the restored real sidecar: passed.

Generated NSIS artifact (not committed):

- `desktop/localcomet-desktop/src-tauri/target/release/bundle/nsis/LocalComet_0.0.0_x64-setup.exe`
- Bytes: `13864492`
- SHA-256: `77f0af06c5c28010d8899f45d9c7e9bcc5d0671fbf5090f01318fe9dc2c6e4ed`

## Packaged smoke status

`NOT STARTED`

Classification: `BLOCKED_PHASE_A_ACCEPTANCE_AUTOMATION_ENVIRONMENT`.

The Windows UI-control system could not attest the active browser/UI context;
policy therefore prohibited packaged interaction. This is an automation
environment blocker, not an installer, downloader, redirect-integrity, or
LocalComet product failure. No packaged redirect-acceptance result is claimed.

No model payload was downloaded. The normal-profile model was not accessed or
changed. Phase A remains open, and Phase B remains prohibited pending a new
authorized packaged smoke run.
