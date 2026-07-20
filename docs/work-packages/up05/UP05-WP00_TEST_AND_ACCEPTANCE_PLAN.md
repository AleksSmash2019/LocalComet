# UP05-WP00 Test and Acceptance Plan

<!-- Bounded acceptance plan for WP00 only. -->

## Static catalog validation

Test canonical UTF-8/LF serialization, exact schema version/catalog identity, duplicate JSON keys, unknown keys, sorted unique IDs, bounded ID grammar, required fields, lowercase SHA-256, positive bytes, platform/architecture/variant, internal distribution flags, safe filenames, relative paths, case-fold collisions, runtime file identities, and compatibility references.

## Live installed validation

Using isolated temporary roots:

- exact runtime package is valid;
- exact GGUF is valid;
- missing artifact is unavailable;
- unknown artifact is rejected;
- size mismatch is rejected before trust;
- hash mismatch is rejected;
- invalid GGUF magic is rejected;
- absolute, drive-relative, traversal, backslash, and reparse paths are rejected;
- runtime/model incompatibility is rejected;
- unapproved neighboring files never enter approved projections;
- mutable AppData cannot add approval.

Persistent installed inventory is intentionally omitted. Every status is derived from the embedded catalog and current bytes.

## Typed contract

Verify approved runtime/model lists, validated installed lists, one-ID status, and model readiness commands. Frontend validation must reconstruct safe metadata, reconcile catalog digest, reject malformed/extra/path-bearing fields, and expose no mutation method.

Managed runtime start accepts only a stable model ID and repeats the complete Rust validation chain immediately before launch.

## Bootstrap acquisition

Record exact official source/revision, final URL, bytes, SHA-256, UTC time, license, archive members, CRC, safe paths, collisions, links/reparse flags, executable, and required DLLs. Validate only the exact Q4_K_M GGUF and CPU runtime.

## Runtime acceptance

Run the approved executable only, loopback-only, with fixed LocalComet-compatible arguments. Require version identity, GGUF load, readiness, one real non-empty response, one terminal completion, clean shutdown, and zero owned orphan processes. Record load, first-token, total duration, chunk count, and bounded peak memory when available.

## Repository checks

Frontend:

- npm test
- npm run check
- npm run build
- rendered model setup trust/status flow through the Browser plugin

Rust/Tauri:

- cargo fmt --check
- cargo check
- cargo clippy --all-targets -- -D warnings
- cargo test
- focused catalog/inventory/typed command tests
- release build or bundle where repository-supported and bounded

Python/backend:

- py_compile for changed Python files, if any
- existing focused managed-runtime/model-gateway tests
- direct runtime/model acceptance

## Negative authority checks

Prove no generic raw IPC, shell, arbitrary file read, arbitrary process launch, approval mutation, runtime automatic download, telemetry, cloud inference, Vault access, installer model payload, or public/LAN binding was introduced.
