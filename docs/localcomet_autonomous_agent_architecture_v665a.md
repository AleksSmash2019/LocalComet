# LocalComet Autonomous Agent Architecture - v6.65a

## Core Vision

LocalComet is a local autonomous agentic OS for development and computer control. It is not intended to remain a wrapper around OpenCode. OpenCode, Aider, Codex, and Computer Use are inspirations and adapters, not the final core.

OpenCode is replaceable. LocalComet is the system.

## Role Separation

- **User** = goal owner and final approval
- **LocalComet** = orchestrator, memory, risk controller, gatekeeper
- **OpenCode** = temporary code executor adapter
- **Aider/Codex-style engines** = replaceable coding backends
- **Computer Use** = desktop/UI operator
- **Internal Agent Runtime** = future core

## Target Architecture

### Core Layers

#### 1. LocalComet Control Panel
Central Tkinter-based UI for command input, status display, and human interaction. Manages routes to adapters and internal modules.

#### 2. Intent Router
Receives natural language commands and routes to appropriate adapters or internal systems based on command analysis.

#### 3. Context Pack Builder
Collects and structures project context, memory, and knowledge for agents to reference during execution.

#### 4. Plan Contract Generator
Creates execution contracts with safety checks, risk classifications, and approval requirements before action execution.

#### 5. Risk Classifier
Evaluates command risk levels (low, medium, high, blocked) and determines approval requirements.

#### 6. Policy Engine
Enforces GREEN-only workflow rules, including backups, manifest checks, and approval requirements.

#### 7. Task Queue
Manages ordered execution of validated tasks with status tracking and rollback capabilities.

#### 8. Tool Router
Directs validated commands to appropriate adapters (OpenCode, Aider, Computer Use, Terminal, etc.).

#### 9. Adapter Layer
Collection of replaceable adapters for different execution engines:

- **OpenCodeAdapter** - Interfaces with OpenCode for temporary code execution
- **AiderAdapter** - Interfaces with Aider coding engine  
- **CodexAdapter** - Interfaces with Codex engine
- **InternalPatchAdapter** - Manages internal codebase patches
- **ComputerUseAdapter** - Controls desktop and GUI operations
- **BrowserAdapter** - Browser automation interface
- **TerminalAdapter** - Command-line execution
- **FileSystemAdapter** - File and directory operations
- **TestRunnerAdapter** - Test execution and validation

#### 10. Internal Patch Engine
Manages codebase changes with diff control, manifest generation, and rollback capabilities.

#### 11. Terminal Executor
Sandboxed command execution with safety checks and audit logging.

#### 12. Computer Use Operator
GUI automation with vision, grounding, and safety controls.

#### 13. Browser Harness
Browser automation with profile isolation and safety controls.

#### 14. Test Runner
Automated testing with functional, contract, and stability validation.

#### 15. Backup/Manifest Manager
Creates pre-change backups and manifests for all modifications.

#### 16. Recovery Manager
Manages rollback operations and system recovery.

#### 17. Reviewer/Gate System
Provides human-review interface with ACCEPT/HOLD/REJECT verdicts.

#### 18. Memory/Project Knowledge Base
Persistent storage of learned patterns, successful strategies, and project context.

## Adapter Strategy

### Replaceable Adapters

LocalComet supports multiple coding and execution backends through a standardized adapter interface:

- **OpenCodeAdapter**: Current temporary adapter for OpenCode-based execution
- **AiderAdapter**: Alternative adapter for Aider-based coding
- **CodexAdapter**: Alternative adapter for Codex-based coding  
- **InternalPatchAdapter**: Adapter for internal codebase modifications
- **ComputerUseAdapter**: Adapter for desktop GUI automation
- **BrowserAdapter**: Adapter for browser automation
- **TerminalAdapter**: Adapter for command-line execution
- **FileSystemAdapter**: Adapter for file system operations
- **TestRunnerAdapter**: Adapter for test execution and validation

### Key Principles

1. **OpenCode is replaceable** - Current adapter can be swapped out
2. **LocalComet is the system** - Core functionality remains independent of adapters
3. **AdapterInterface** - Standardized interface for all adapters
4. **Route selection** - Intent router chooses appropriate adapter at runtime
5. **Safety consistent** - All adapters must follow LocalComet's safety policies

## Safety and Governance

### GREEN-Only Workflow

1. **Backup before changes**: Mandatory pre-change snapshot creation
2. **Manifest before changes**: Complete change manifest generation
3. **Diff limits**: Maximum change size restrictions
4. **Risk class**: Automatic risk classification for all operations
5. **Approval requirements**: Different approval levels for different risk levels
6. **Contracts gate**: All changes require contract validation
7. **Functional gate**: All changes require functional test validation
8. **Strict stability gate**: All changes require strict project stability validation
9. **Reviewer verdict**: Final review with ACCEPT/HOLD/REJECT options
10. **Rollback path**: Guaranteed rollback capability for all changes

### Risk Classification

- **Low**: Safe UI automation, read operations
- **Medium**: File modifications, typing actions
- **High**: Code compilation, file replacements
- **Blocked**: Destructive operations, admin actions, secrets access

### Approval Requirements

- **Low risk**: No approval needed (auto-execute with observation)
- **Medium risk**: Requires confirmation before execution
- **High risk**: Requires explicit reviewer approval
- **Blocked**: Always blocked, cannot be overridden

### Gate System

1. **GREEN** - All checks pass, change approved
2. **YELLOW** - Warnings present, requires attention but can proceed
3. **RED** - Critical failures, change blocked
4. **HOLD** - Manual review required
5. **REJECT** - Change rejected, rollback initiated

## Autonomous Agent Loop

### Future Internal Loop

1. **Observe**: Scan environment, screen, and context
2. **Understand**: Analyze current state and requirements
3. **Plan**: Create execution plan with risk classification
4. **Risk Classify**: Determine required approvals and safety checks
5. **Backup**: Create system backup and change manifest
6. **Edit**: Execute changes through appropriate adapters
7. **Test**: Run functional, contract, and stability tests
8. **Repair**: Fix any test failures or issues
9. **Report**: Generate comprehensive execution report
10. **Accept/Rollback**: Final decision based on all checks

### Loop Characteristics

- **One-action-per-observation**: No blind multi-step execution
- **Grounded actions required**: All GUI actions must be visually grounded
- **Visual guard decisions**: Screen changes trigger decision points
- **Continuous observation**: System constantly monitors state

## Roadmap from v6.65 to v7.0

### Development Phases

#### v6.65: Architecture and Working Directory Guard
- Complete architecture documentation
- Implement working directory isolation
- Create base safety guardrails
- Establish foundation for internal agent runtime

#### v6.66: Capability Map v2, Read-Only and Accurate
- Develop accurate internal capability map
- Implement read-only mode for critical operations
- Enhance route selection accuracy
- Improve safety check precision

#### v6.67: Task Contract Registry
- Create immutable task contract registry
- Implement contract lifecycle management
- Add contract validation and enforcement
- Establish contract lineage tracking

#### v6.68: Tool Adapter Interface
- Standardize adapter interface
- Implement adapter registration system
- Add adapter testing framework
- Create adapter lifecycle management

#### v6.69: Internal Patch Engine Prototype
- Develop internal patch creation system
- Implement diff-based patching
- Create rollback infrastructure
- Add patch validation framework

#### v6.70: Diff Control and Rollback Manager
- Implement diff tracking and validation
- Create automated rollback capabilities
- Add rollback testing framework
- Improve patch safety mechanisms

#### v6.80: Internal Coding Loop
- Implement self-contained coding cycle
- Add internal modification capabilities
- Implement code review integration
- Create quality assurance integration

#### v6.90: Computer Use Supervised Operator
- Enhance GUI automation with supervision
- Add human-in-the-loop controls
- Implement safety-verified automation
- Create user approval workflow

#### v7.0: Autonomous Local Agent Runtime MVP
- Launch fully autonomous local agent runtime
- Implement complete self-governance
- Add comprehensive logging and reporting
- Launch production-ready system

## Non-Goals

### Explicit Exclusions

- **Not uncontrolled full desktop automation**: All automation requires grounding and approval
- **Not blind self-modification**: All changes require explicit safety checks and approvals
- **Not one giant system doctor patch**: Changes are incremental and reversible
- **Not dependent on OpenCode forever**: OpenCode is a temporary adapter
- **Not deleting backups/screenshots without approval**: All deletions require explicit confirmation
- **Not weakening safety for convenience**: Safety rules are non-negotiable
- **Not bypassing human oversight**: All significant changes require human approval
- **Not running without audit trails**: Every action is logged and auditable

## Next Implementation Candidates

### 5 Small Safe Next Patches

1. **Working Directory Guard**: Implement directory isolation and protection
2. **Accurate Capability Map v2**: Create comprehensive internal capability registry
3. **Task Contract Registry**: Establish immutable contract storage and validation
4. **Adapter Interface Skeleton**: Create base adapter interface with registration
5. **Diff Limit Guard**: Implement change size and impact restrictions

### Rationale

- **Incremental approach**: Each patch builds on previous work
- **Safety-first**: All changes maintain or improve safety
- **Backwards compatible**: No breaking changes to existing functionality
- **Testable**: Each change has clear acceptance criteria
- **Documented**: Complete documentation for each change

## Acceptance Criteria

### Validation Requirements

The architecture document is accepted only if:

- [ ] No Python source was edited (only docs/report files created)
- [ ] Docs/report files created only (not Python source)
- [ ] Current baseline remains GREEN (all tests passing)
- [ ] Architecture clearly states OpenCode is temporary
- [ ] Roadmap is concrete and incremental with clear milestones
- [ ] Safety policies are preserved and documented
- [ ] Adapter strategy is fully specified
- [ ] Non-goals are clearly stated

### Quality Gates

1. **Architectural completeness**: All major components documented
2. **Safety preservation**: No weakening of existing safety measures
3. **Incremental roadmap**: Path from v6.65 to v7.0 is feasible
4. **Documentation quality**: Clear, actionable, well-structured
5. **Implementation readiness**: Concrete next steps identified

## Final Architecture Summary

LocalComet evolves from a wrapper system into a fully autonomous local agent runtime. The core system orchestrates multiple replaceable adapters while maintaining strict safety controls. The architecture emphasizes:

- **Safety above all**: GREEN-only workflow with multiple gates
- **Replaceability**: Adapters can be swapped without changing core
- **Incremental development**: Clear roadmap with achievable milestones
- **Human oversight**: User retains final approval authority
- **Auditable operations**: Complete audit trails for all actions

The system will mature through well-defined phases, maintaining reliability and safety throughout the evolution from v6.65 to v7.0.
