# UP05-WP00 PR Body

<!-- Source-controlled WP00 review record. -->

## Summary

Implemented a source-controlled immutable Approved Artifact Catalog, strict Rust validation, live non-authoritative installed-state derivation, and typed read-only frontend projections. Pinned, provisioned, and validated one internal llama.cpp CPU runtime and one Qwen2.5 1.5B Q4_K_M bootstrap model without committing or bundling their bytes.

This file is the retrospective source-controlled review record. No remote pull request was opened.

## Trust decision

Approval is reviewed source authority. AppData cannot approve artifacts. Managed launch resolves stable model ID through catalog, exact model validation, compatibility, exact runtime validation, and fixed contained launch policy.

## Scope

- canonical catalog resource and digest
- Rust parser/schema/path/hash/compatibility validator
- live installed status and managed launch integration
- read-only Tauri/frontend contract
- focused security and consumer tests
- bounded official acquisition/provisioning
- direct real inference and cleanup evidence
- WP00 documentation and rollback

## Explicit exclusions

No automatic download, cloud provider, model library redesign, installer payload, public distribution, generic raw IPC, generic shell, arbitrary filesystem access, telemetry, Vault access, RAG, tools/agents, UP06–UP10, or UP05 chat lifecycle completion.

## Validation

Catalog schema 1 passed with exact digest `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`.

Pinned artifacts:

- runtime ID `llama-cpp-windows-x86-64-cpu-bootstrap`: llama.cpp `b10068`, revision `571d0d540df04f25298d0e159e520d9fc62ed121`, `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes, SHA-256 `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`, MIT;
- model ID `qwen2.5-1.5b-instruct-q4-k-m`: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, Apache-2.0.

Direct inference passed on loopback with output `AI`: 0.953 seconds load-to-listen, 114.378 milliseconds to first content, 123.099 milliseconds total, three JSON SSE chunks, one non-empty content chunk, exactly one `[DONE]`, and peak working set 1,749,966,848 bytes. Graceful Ctrl+C shutdown left no orphan process.

Frontend tests passed 211/211; Svelte check had zero errors and one pre-existing warning; production build passed. Rust fmt/check/clippy/all tests passed, including the 55.05-second installed-production test; the offline locked release build passed in 1 minute 10 seconds. Python compilation, v6.84.5.1 managed-runtime regression, and clean-room model-gateway regression passed. Negative authority tests and both source and physical managed-artifact rollback rehearsals passed.

The supplemental fast stability gate reported 17/19 because two legacy checks fail in untouched control-panel code. All WP00-affected checks passed. Evidence retains this limitation explicitly.

## Review notes

The bootstrap model is internal validation material only, not a public-distribution or installer payload and not a production performance baseline. Full LocalComet chat reliability resumes in UP05-WP01; WP00 does not claim it complete.
