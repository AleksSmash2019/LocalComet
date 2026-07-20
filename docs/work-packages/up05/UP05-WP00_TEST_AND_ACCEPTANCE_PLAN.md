# UP05-WP00 Test and Acceptance Plan

<!-- Bounded acceptance plan and completed result for WP00 only. -->

Status: WP00-affected acceptance checks passed. The broader fast stability gate reported 17/19 because of two legacy checks in untouched control-panel code; those results are retained rather than misreported as WP00 regressions.

Catalog under test: schema 1, digest `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`.

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

Result: PASS in isolated roots and against the provisioned production artifacts. The production discovery test completed in 55.05 seconds and found the approved runtime/model installed, byte-valid, hash-valid, contained, compatible, and launchable. Unknown, tampered, path-escaping, incompatible, and AppData-claimed artifacts failed closed.

## Typed contract

Verify approved runtime/model lists, validated installed lists, one-ID status, and model readiness commands. Frontend validation must reconstruct safe metadata, reconcile catalog digest, reject malformed/extra/path-bearing fields, and expose no mutation method.

Managed runtime start accepts only a stable model ID and repeats the complete Rust validation chain immediately before launch.

Result: PASS. The frontend consumes five fixed read-only trust commands, reconstructs closed safe objects, reconciles the catalog digest, derives installation state separately from approval, and obtains fresh readiness before stable-ID start. No approval/catalog/inventory mutation command is exposed.

## Bootstrap acquisition

Record exact official source/revision, final URL, bytes, SHA-256, UTC time, license, archive members, CRC, safe paths, collisions, links/reparse flags, executable, and required DLLs. Validate only the exact Q4_K_M GGUF and CPU runtime.

Result: PASS.

- Runtime: `ggml-org/llama.cpp`, `b10068`, revision `571d0d540df04f25298d0e159e520d9fc62ed121`, `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes, SHA-256 `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`, MIT, acquired `2026-07-20T11:42:55.7121149Z`.
- Model: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, Apache-2.0, acquired `2026-07-20T11:43:27.1950378Z`.

The runtime archive passed CRC and member-safety checks and yielded exactly 31 catalog-required files. The model passed exact-size, SHA-256, GGUF magic, source, and Q4_K_M identity checks. Both were provisioned to their catalog-declared managed locations without collision; no acquired bytes entered Git or installer resources.

## Runtime acceptance

Run the approved executable only, loopback-only, with fixed LocalComet-compatible arguments. Require version identity, GGUF load, readiness, one real non-empty response, one terminal completion, clean shutdown, and zero owned orphan processes. Record load, first-token, total duration, chunk count, and bounded peak memory when available.

Result: PASS. Load-to-listen was 0.953 seconds. First non-empty content arrived at 114.378 milliseconds and total inference completed in 123.099 milliseconds. The observed output was `AI`; the stream contained three JSON SSE chunks, one non-empty content chunk, and exactly one `[DONE]`. Peak working set was 1,749,966,848 bytes. Graceful Ctrl+C shutdown left no owned or orphan `llama-server` process.

## Repository checks

Frontend:

- `npm test`: PASS, 211/211 tests
- `npm run check`: PASS, zero errors and one pre-existing warning
- `npm run build`: PASS
- typed managed-artifact and model-gateway consumer/component tests: PASS

Rust/Tauri:

- `cargo fmt --check`: PASS
- `cargo check`: PASS
- `cargo clippy --all-targets -- -D warnings`: PASS
- all Rust tests and focused catalog/inventory/typed-command tests: PASS
- owner-provisioned production discovery test: PASS in 55.05 seconds
- offline locked release build: PASS in 1 minute 10 seconds

Python/backend:

- `py_compile` for the changed Python test: PASS
- v6.84.5.1 managed-runtime regression: PASS
- clean-room model-gateway regression: PASS
- direct runtime/model acceptance and cleanup: PASS

Repository-wide supplemental gate:

- fast stability: 17/19; two failures are legacy checks in untouched `LocalComet_Control_Panel.py` code, while every WP00-affected check passed

## Negative authority checks

Prove no generic raw IPC, shell, arbitrary file read, arbitrary process launch, approval mutation, runtime automatic download, telemetry, cloud inference, Vault access, installer model payload, or public/LAN binding was introduced.

Result: PASS. Tests also covered unknown IDs, byte/hash mismatch, incompatibility, absolute/drive-relative/traversal/reparse paths, corrupt/stale/traversal inventory claims, unexpected runtime files, bad GGUF magic, source-only approval, fresh readiness, loopback listener ownership, and held launch identities. The Obsidian Vault was neither read nor modified.

## Rollback acceptance

Source reverse-apply checks against exact base `0467cf71e1cf0e0400d687c1829e7bd0de91eebc` passed. The catalog diff reversed cleanly. The exact managed runtime and model destinations were moved aside on the same volume, observed absent, and restored; unrelated managed content and user data were preserved. Live state reconstructed after restoration and exact validation returned to the successful feature state.

UP05-WP00 establishes the trust/provisioning bootstrap only. UP05-WP01 chat reliability remains incomplete and is the next work package.
