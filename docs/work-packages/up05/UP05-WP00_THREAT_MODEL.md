# LocalComet Repository Threat Model

<!-- Generated under the repository-scoped Codex Security threat-model contract. -->

## Overview

LocalComet is a local Windows agent application with a Tauri/Rust desktop trust boundary, a contained Python sidecar/control plane, local model runtime integration, bounded project workflows, and user-facing Svelte UI. Primary assets are the integrity of executable code and approved model/runtime artifacts, user project and application data, local credentials and process boundaries, typed request/event identity, and the owner's source-reviewed architecture authority.

Primary runtime surfaces include desktop/localcomet-desktop/src-tauri, desktop/localcomet-desktop/src, modules, core, agents, and the packaged Python runtime. Tests, docs, reports, and developer tools inform assurance but do not independently grant production authority.

## Threat Model, Trust Boundaries, and Assumptions

Trust boundaries:

1. Source review and build boundary: repository-controlled source, lockfiles, resources, and build configuration become a packaged desktop application. Unreviewed binaries and mutable AppData are outside this approval boundary.
2. Desktop frontend to Tauri boundary: Svelte is less trusted than Rust. Only typed, permissioned commands may cross; frontend input must not become raw paths, commands, environment, or approval state.
3. Tauri to Python sidecar boundary: framed typed control-plane messages cross a contained local process boundary. Request identity, schema, sequence, bounds, cancellation, and shutdown must fail closed.
4. Tauri to managed model runtime boundary: an external executable processes complex GGUF data and exposes loopback HTTP/SSE. Exact binary/model identity, contained paths, loopback binding, fixed arguments, credentials, readiness, resource bounds, and process cleanup matter.
5. Application to per-user AppData boundary: AppData is mutable by the user and other same-user processes. It may contain installed bytes and derived state but cannot create trust or override source approval.
6. LocalComet to project/Vault boundary: project files and the Obsidian Vault are user assets. Access must remain explicitly scoped; this work package grants none.
7. Acquisition boundary: official upstream pages and asset CDNs are network-controlled inputs until exact source identity, archive safety, bytes, format, license, and SHA-256 are verified and reviewed into source.
8. Installer/runtime boundary: packaged resources and per-user processes must not create persistent terminals, global PATH changes, firewall exposure, startup persistence, or unrestricted process authority.

Developer-controlled inputs include reviewed source catalogs, schemas, command registration, permissions, lockfiles, and build scripts. Operator-controlled inputs include prompts, explicit UI actions, bounded project choices, and installation of exact approved artifacts. Attacker-controlled inputs may include malformed frontend payloads, tampered AppData files, unapproved executables/models, malicious archive members, hostile model outputs, malformed local HTTP/SSE responses, and compromised same-user files.

Assumptions:

- The packaged application and reviewed commit are trusted roots for this local threat model.
- Windows same-user compromise can tamper with AppData, so exact revalidation is required; AppData secrecy or integrity is not assumed.
- Local model output is untrusted text and cannot authorize tools, files, commands, or approval.
- Loopback reduces remote exposure but does not prove process or model identity.
- Administrator/kernel compromise and malicious replacement of the packaged application itself are outside the guarantees of a user-mode source catalog.

Security invariants:

- Only source-reviewed catalog entries can approve runtime/model artifacts.
- Every executable/model is resolved from a stable ID through exact hash, size, type, compatibility, and path containment checks.
- No raw frontend/AppData path or mutable cache grants trust.
- Typed IPC cannot expand into generic shell, filesystem, process, or network authority.
- One request/event identity and terminal lifecycle remains isolated.
- Secrets, full private paths, environment dumps, and unrelated logs do not cross safe projections.
- Shutdown and failure do not leave owned privileged processes alive.

## Attack Surface, Mitigations, and Attacker Stories

Artifact acquisition and extraction face supply-chain substitution, malicious redirects, traversal, drive-relative members, duplicate/case-colliding entries, symlink/reparse members, unexpected installers/scripts, and archive bombs. Mitigations are strict official-source allowlists, one pinned asset, exact raw SHA-256, bounded extraction, member validation, and no execution before review.

Managed AppData faces unknown or tampered models/runtimes, filename spoofing, stale caches, path traversal, junction/reparse escape, time-of-check/time-of-use changes, and compatibility confusion. Mitigations are source-only approval, exact revalidation, safe relative paths, canonical descendant checks, reparse rejection, held model identity, stable IDs, and runtime/model compatibility references.

Frontend/Tauri IPC faces malformed data, extra-field smuggling, ID/path confusion, unauthorized commands, and stale readiness. Mitigations are strict Rust ownership, Tauri permission allowlists, reconstructed safe TypeScript projections, stable-ID-only start commands, no mutation API, and fail-closed digest/schema matching.

Sidecar and model runtime protocols face spoofed readiness, duplicate/late/cross-request events, zero-token success, indefinite streams, cancellation races, oversized output, and credential leakage. Existing controls include bounded loopback transport, typed methods, per-turn IDs, output limits, contained processes, and sanitized logs. UP05-WP01 remains responsible for completing the chat lifecycle repairs.

Realistic attacker stories include a same-user process replacing a GGUF after provisioning, a crafted archive attempting path escape, a frontend payload containing traversal-like IDs, an AppData file claiming an unknown artifact is approved, or an unapproved executable placed under a plausible runtime filename. All must fail closed.

Out-of-scope stories include cloud multi-tenant isolation, remote account takeover, kernel-level process injection, administrator compromise, and physical attacks. Localhost-only exposure does not make malformed local protocol input irrelevant, but it generally lowers unauthenticated remote reachability.

## Severity Calibration (Critical, High, Medium, Low)

Critical:

- Generic command/process authority reachable from model output or untrusted frontend input.
- A source/installer supply-chain bypass that silently executes an unapproved binary across installations.
- Vault or broad user-file destruction reachable without explicit bounded authority.

High:

- AppData or inventory content authorizes an unknown executable/model.
- Traversal/reparse escape launches a binary outside the managed root.
- Hash/compatibility bypass executes tampered runtime bytes.
- Remote/LAN binding exposes an unauthenticated privileged model/control endpoint.

Medium:

- Typed event confusion contaminates another local request without broader code execution.
- A stale readiness state causes local user actions against the wrong approved model.
- Bounded local denial of service through malformed catalog/runtime responses with restart recovery.

Low:

- Safe metadata inconsistency that cannot grant approval or launch.
- Sanitized diagnostic inaccuracies without secret/path disclosure.
- Cosmetic UI state issues with no authority, integrity, or data-loss effect.

Severity falls when exploitation requires prior administrator/kernel control or replacement of the trusted packaged application. It rises when a same-user mutable input crosses into executable approval, arbitrary filesystem access, generic process authority, secret disclosure, or irreversible user-data impact.

Repository: git-remote-sha256:344e82ae9595cf6d13c8b89d3e77f32a310fd1a1c57eb9c4af39126e2086e2ba
Version: 0467cf71e1cf0e0400d687c1829e7bd0de91eebc
