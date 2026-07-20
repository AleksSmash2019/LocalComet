# UP05-WP00 PR Body

<!-- Source-controlled WP00 review record. -->

## Summary

Introduce a source-controlled immutable Approved Artifact Catalog, strict Rust validation, live non-authoritative installed-state derivation, and typed read-only frontend projections. Pin and validate one internal llama.cpp CPU runtime and one Qwen2.5 1.5B Q4_K_M bootstrap model without committing or bundling their bytes.

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

Final PR evidence will list exact frontend, Rust/Tauri, backend/runtime, negative-security, direct inference, process cleanup, and rollback results together with the catalog digest and upstream pins.

## Review notes

The bootstrap model is internal validation material only. Full LocalComet chat reliability resumes in UP05-WP01 after this trust/provisioning package is accepted.
