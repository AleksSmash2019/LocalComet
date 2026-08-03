# MVP Remediation Master Plan

## Program Identity

- Repository: C:\Users\DNS\Documents\LocalComet-build-week-clean
- Branch: feature/donor-ui-compatible-port
- HEAD: 8af1c89c7d7c1d8e43265c99e6dd3f33abd03364
- Tree digest: 06c557d94665494205a839bf0ec168113d1fb41cf50a60272ebfe0c2ef3f8a73
- Baseline verified: 2026-07-30
- Baseline verdict: CONFIRMED

## Product Boundary

Svelte frontend -> Tauri/Rust desktop -> bounded local IPC -> Python sidecar/model gateway -> authoritative validation -> approval -> workspace-bound execution -> result event -> frontend.

Legacy execution architecture (next/app_v5.py -> planner -> agents -> legacy modules -> arbitrary shell/filesystem/process execution) is NOT part of MVP.

## Findings Index

| ID | Severity | Finding | Cycle | State |
|----|----------|---------|-------|-------|
| F-001 | CRITICAL | Legacy arbitrary shell execution reachable | MVP-P0-A | NOT_STARTED |
| F-002 | CRITICAL | Approval authority not unified | MVP-P0-B | NOT_STARTED |
| F-003 | HIGH | Sidecar health correlation prefix-only | MVP-P0-C | NOT_STARTED |
| F-004 | HIGH | Bundle parity stale | MVP-P0-D | NOT_STARTED |
| F-005 | MEDIUM | Command/test authority ambiguity | MVP-P0-E | NOT_STARTED |
| F-006 | HIGH | B5LP Python resource limits absent | MVP-P1-A | NOT_STARTED |
| F-007 | HIGH | IPC pre-parse depth safety absent | MVP-P1-B | NOT_STARTED |
| F-008 | HIGH | Frontend approval double execution | MVP-P1-C | NOT_STARTED |
| F-009 | MEDIUM | Uninformed approval UI | MVP-P1-D | NOT_STARTED |
| F-010 | CRITICAL | Workspace/session/grant binding incomplete | MVP-P1-E | NOT_STARTED |
| F-011 | CRITICAL | Workspace TOCTOU | MVP-P1-F | NOT_STARTED |
| F-012 | HIGH | B6 cross-event provenance absent | MVP-P1-G | NOT_STARTED |
| F-013 | HIGH | Asymmetric IPC validation | MVP-P1-H | NOT_STARTED |
| F-014 | HIGH | Incomplete execution bounds | MVP-P1-I | NOT_STARTED |
| F-015 | LOW | Source-tree node_modules invariant | MVP-P4-B | NOT_STARTED |

## Milestone Dependencies

### M1 UI Demo MVP
Requires: P0-A, P0-D, P0-E, P2-A through P2-G

### M2 Safe Local MVP
Requires: M1 + all P0 + all P1

### M3 Release MVP
Requires: M2 + all P3 + all P4

## Execution Order

1. MVP-P0-A: Legacy Execution Quarantine
2. MVP-P0-B: Authoritative Approval Unification
3. MVP-P0-C: Exact Sidecar Health Correlation
4. MVP-P0-D: Source/Bundle/Deployed Parity
5. MVP-P0-E: Command/Test Authority
6. MVP-P1-A: B5LP GREEN
7. MVP-P1-B: IPC Pre-parse Depth Safety
8. MVP-P1-C: Frontend Single-flight / Backend Idempotency
9. MVP-P1-D: Informed Approval UI
10. MVP-P1-E: Workspace/Session/Grant Binding
11. MVP-P1-F: Workspace Confinement / TOCTOU
12. MVP-P1-G: B6 Cross-event Provenance
13. MVP-P1-H: Symmetric Rust/Python IPC
14. MVP-P1-I: Bounded Filesystem Execution
15. MVP-P1-J: End-to-end Adversarial Tool Tests
16. P2 tasks (parallelizable after P0)
17. P3 tasks (after M2)
18. P4 tasks (after M2)

## Safety Invariants

- Production tools: DISABLED until all P1 complete
- Strict Rust placeholder: ACTIVE until B6 + all P1 complete
- Legacy routes: must be UNREACHABLE from MVP runtime after P0-A
- No shell=True for model-controlled values
- No trust of renderer confirmed:true as authorization
- No trust of caller-provided workspace/session digests
