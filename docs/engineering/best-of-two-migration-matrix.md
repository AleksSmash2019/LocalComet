# Best-of-Two Migration Matrix

Donor: Local Agent Desktop (WP-1.45.4, React/Tauri/Python sidecar)
Target: LocalComet canonical (6.84.6+, Svelte/Tauri/Python monorepo)
Date: 2026-07-25
Branch: integration/best-of-two-local-agent

## Summary

LocalComet desktop already implements or exceeds many donor improvements:
- Windows Job Object with KILL_ON_JOB_CLOSE + ACTIVE_PROCESS_LIMIT=1
- Process supervisor with active health probe and readiness correlation
- Bounded stderr reader (4096 ring buffer)
- IPC framing with 4MB max frame, length-prefix
- Artifact trust with SHA-256, GGUF magic, catalog guard, reparse rejection
- Control plane bridge with request registry, timeouts, model lifecycle
- Bounded pipe writes with timeout and backpressure handling
- Sanitized sidecar environment (PYTHONNOUSERSITE, -I, -B)
- Python discovery filtering WindowsApps Store stubs

## Migration Matrix

| Donor improvement | Donor file | LocalComet analogue | Decision | Target file | Required adaptation | Tests | Status |
|---|---|---|---|---|---|---|---|
| Windows Job Object | windows_job.rs | src-tauri/src/windows_job.rs | ALREADY_PRESENT | — | — | 3 unit tests | DONE |
| Process supervisor | supervisor.rs | src-tauri/src/supervisor.rs | ALREADY_PRESENT | — | — | 6 unit tests | DONE |
| Active health probe | supervisor.rs | supervisor.rs:360-371 | ALREADY_PRESENT | — | — | lifecycle test | DONE |
| Bounded stderr reader | supervisor.rs | supervisor.rs:548-572 | ALREADY_PRESENT | — | — | — | DONE |
| IPC framing + max size | ipc.rs | src-tauri/src/ipc.rs | ALREADY_PRESENT | — | — | 2 unit tests | DONE |
| Artifact trust + SHA-256 | artifact_trust.rs | src-tauri/src/artifact_trust.rs | ALREADY_PRESENT | — | — | extensive | DONE |
| Catalog guard (embedded digest) | — | artifact_trust.rs:33-34 | ALREADY_PRESENT | — | — | canonical check | DONE |
| Reparse point rejection | — | artifact_trust.rs (reject_reparse_point) | ALREADY_PRESENT | — | — | — | DONE |
| Bounded pipe write | — | windows_job.rs:10-42 | ALREADY_PRESENT | — | — | 3 unit tests | DONE |
| Sanitized environment | — | supervisor.rs:646-679 | ALREADY_PRESENT | — | — | env test | DONE |
| Python discovery (Windows) | — | supervisor.rs:600-644 | ALREADY_PRESENT | — | — | — | DONE |
| Control plane bridge | — | src-tauri/src/control_plane.rs | ALREADY_PRESENT | — | — | — | DONE |
| Request registry + timeouts | — | control_plane.rs:556-591 | ALREADY_PRESENT | — | — | — | DONE |
| Model request lifecycle | — | control_plane.rs:349-486 | ALREADY_PRESENT | — | — | — | DONE |
| EOL/BOM invariant test | test_eol_invariant.py | — | PORT | tests/test_trust_chain_invariants.py | Adapt for LocalComet trust-chain files | new | PENDING |
| .gitattributes hardening | .gitattributes | .gitattributes | ADAPT | .gitattributes | Add trust-chain file rules | — | PENDING |
| Non-authorities registry | non_authorities.toml | — | PORT | security/invariants/non_authorities.toml | LocalComet-specific entries | new | PENDING |
| Security-negative taxonomy | security-negative-map.toml | — | PORT | security/invariants/security_negative.toml | Adapt to LocalComet test structure | new | PENDING |
| Invariant registry | invariants.toml | — | PORT | security/invariants/invariants.toml | LocalComet invariant IDs | new | PENDING |
| Response type validation | — | control_plane.rs (partial) | ADAPT | src-tauri/src/ipc.rs + control_plane.rs | Add expected response type map | new | PENDING |
| Scoped approval tokens | control_plane_core.rs | — | PORT | src-tauri/src/approval.rs | New module, CSPRNG, scoped, one-time | new | PENDING |
| Workspace propagation | — | — | PORT | src-tauri/src/workspace.rs + IPC | workspace.set protocol | new | PENDING |
| Evidence provenance | check_evidence_provenance.py | — | PORT | scripts/check_evidence_provenance.py | Adapt for LocalComet evidence | new | PENDING |
| Command parity gate | check_command_parity.py | — | PORT | scripts/check_command_parity.py | Svelte invokes == Tauri commands | new | PENDING |
| Streaming SHA-256 (product path) | — | artifact_trust.rs (sha256_file) | ADAPT | artifact_acquisition.rs | Verify streaming in download path | — | PENDING |
| Native smoke binary | lad_smoke.rs | — | DEFER_WITH_REASON | — | Requires sidecar protocol stability first | — | DEFERRED |
| AST async check | — | — | DEFER_WITH_REASON | — | LocalComet uses spawn_blocking already | — | DEFERRED |
| React/Zustand stores | src/lib/*.ts | — | REJECT | — | LocalComet uses Svelte 5 | — | REJECTED |
| Separate Python package layout | sidecar/ | modules/ | REJECT | — | LocalComet has monorepo modules | — | REJECTED |
| Second IPC client | ipc_client.rs | — | REJECT | — | LocalComet has single ipc.rs | — | REJECTED |

## Process ownership map (LocalComet)

```
Tauri main (lib.rs)
  → DesktopSidecarSupervisor (supervisor.rs)
    → ContainedSidecarProcess (windows_job.rs)
      → CreateProcessW (CREATE_SUSPENDED)
      → AssignProcessToJobObject (KILL_ON_JOB_CLOSE, ACTIVE_PROCESS=1)
      → ResumeThread
    → stdout reader thread → frame router → ControlPlaneBridge
    → stderr reader thread → ring buffer (4096)
    → health probe (desk-health-{seq}) → saw_health_ok
    → shutdown: app.shutdown request → wait 1500ms → terminate
  → ManagedRuntimeSupervisor (managed_runtime.rs)
    → ContainedManagedRuntimeProcess (windows_job.rs)
      → Same Job Object containment
```

## Approval map (LocalComet — TO BE IMPLEMENTED)

```
User confirms action in Svelte UI
  → Tauri command (approve_step)
  → Rust approval.rs: issue scoped token (CSPRNG 256-bit)
    scope = {tool, input_digest, workspace, session, expiry, nonce}
  → Frontend carries opaque token
  → Tauri command (run_tool_call) with token
  → Rust approval.rs: execute_approved()
    → validate scope (constant-time)
    → consume one-time
    → create execution grant
    → send authorized envelope to sidecar
  → Python sidecar: execute only with valid grant
```

## Workspace map (LocalComet — TO BE IMPLEMENTED)

```
User selects directory (native dialog)
  → Rust canonicalize + symlink/junction check
  → workspace.set.request → sidecar
  → Python creates new WorkspacePolicy
  → workspace.set.response with identity
  → Rust invalidates old approval tokens
  → UI confirmed state
```
