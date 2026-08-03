# MVP Program Decisions

## Owner-Ratified Decisions

### D-001: Legacy execution quarantine (not deletion)
- Date: Program start
- Decision: Legacy planner/agent shell execution must be quarantined from all shipped and reachable MVP entry points. Runtime quarantine required even if legacy source files remain present. Do not permanently delete ADR-011 files without separate explicit owner decision.
- Authority: Owner (program specification)

### D-002: Production tools remain disabled
- Date: Program start
- Decision: Production tools must remain disabled until every P1 activation blocker is complete. Tool activation is its own micro-cycle.
- Authority: Owner (program specification)

### D-003: No commits or pushes
- Date: Program start
- Decision: Do not commit or push. Preserve dirty worktree.
- Authority: Owner (program specification)

### D-004: First safe tool subset
- Date: Program start
- Decision: Initially enable only bounded workspace file read and bounded workspace file list. Do not initially enable delete, arbitrary process, shell, network, arbitrary application launch, self-edit, or recursive destructive operations.
- Authority: Owner (program specification)

## Pending Decisions

### PD-001: Signing and updater policy (P4-F)
- Required before: RELEASE_MVP_READY
- Options: signed/unsigned, updater enabled/disabled, trust root, rollback, artifact retention, release channel
