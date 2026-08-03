# MVP-P0-B Approval Command Inventory

## Discovery Date: 2026-07-30
## Agents: 6 read-only (risk-registry, rust-approval, tauri-command, frontend-invoke, token-state-machine, test-matrix)

## Critical Findings

### CAP-1: Approval commands unreachable from renderer
The 4 approval commands (request_approval, execute_approved, run_tool_call, set_workspace) are registered in lib.rs invoke_handler but have NO permission entry in capabilities/main.json. The renderer cannot call them.

### GAP-1: Remove-before-validate destroys tokens
approval.rs execute_approved() removes the token from the HashMap BEFORE validating scope. A mismatched attempt permanently destroys a valid token.

### GAP-2: 5 mutating commands bypass token system
start_approved_artifact_download, remove_managed_model, managed_runtime_start, managed_runtime_stop, model_binding_set do not require approval tokens. Three use only `confirmed: bool` from renderer; two have no authorization at all.

## Command Authorization Inventory

| Command | Risk | Mutates | Current Authorization | Capability Exposed | Required P0-B Action |
|---------|------|---------|----------------------|-------------------|---------------------|
| request_approval | n/a | issues token | workspace confirmed | **NO (CAP-1)** | Add capability |
| execute_approved | n/a | consumes token | token validation | **NO (CAP-1)** | Add capability |
| run_tool_call | n/a | token-gated dispatch | risk-level token | **NO (CAP-1)** | Add capability |
| set_workspace | n/a | trust anchor | path validation | **NO (CAP-1)** | Add capability |
| start_approved_artifact_download | guarded | download+install | `confirmed: bool` | YES | Require token |
| remove_managed_model | dangerous | delete file | `confirmed: bool` | YES | Require token |
| managed_runtime_start | guarded | spawn process | NONE | YES | Require token |
| managed_runtime_stop | guarded | kill process | NONE | YES | Require token |
| model_binding_set | guarded | mutate binding | token (R6: confirmed removed) | YES | COMPLETE (R6) |
| files.write | guarded | write file | token via run_tool_call | via run_tool_call | Already correct |
| files.create_folder | guarded | create dir | token via run_tool_call | via run_tool_call | Already correct |
| files.delete | dangerous | delete | token via run_tool_call | via run_tool_call | Already correct |
| files.read | read_only | no | none needed | via run_tool_call | Already correct |
| files.list | read_only | no | none needed | via run_tool_call | Already correct |

## Token Binding (Current)

| Field | Bound at Issue | Validated at Consume |
|-------|---------------|---------------------|
| tool | YES | YES (ct_eq) |
| input_digest | YES (SHA-256 canonical JSON) | YES (ct_eq) |
| workspace | YES | YES (ct_eq) |
| session | YES | YES (ct_eq) |
| risk_level | YES (metadata) | NO |
| call/request ID | NO | NO |
| expiration | YES (Instant + TTL) | YES |
| one-time | YES (HashMap::remove) | YES |

## Existing Tests (approval.rs): 15 tests
## Existing Tests (approval_commands.rs): 8 tests (risk classification only)
## Required New Tests: 8 (5 will FAIL against current code = RED)
