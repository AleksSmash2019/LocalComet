# MVP-P0-B-R6 — COMMAND FAMILY CONTRACT (FROZEN)

Status: FROZEN before GREEN implementation
Cycle: MVP-P0-B-R6
Date: 2026-07-30

## Canonical Manifest

security/contracts/approval_command_families_v1.json

## Exact Eight Family Values

| # | Serialized value | Rust variant |
|---|---|---|
| 1 | artifact_download | ArtifactDownload |
| 2 | artifact_remove | ArtifactRemove |
| 3 | runtime_start | RuntimeStart |
| 4 | runtime_stop | RuntimeStop |
| 5 | model_binding_set | ModelBindingSet |
| 6 | tool_filesystem_read | ToolFilesystemRead |
| 7 | tool_filesystem_write | ToolFilesystemWrite |
| 8 | tool_filesystem_delete | ToolFilesystemDelete |

## Parity Requirements

- Rust CommandFamily enum serialized set == manifest exactly
- TypeScript ApprovalCommandFamily type == manifest exactly
- TypeScript COMMAND_FAMILIES runtime array == manifest exactly
- No duplicates in manifest
- No arbitrary string widening in TypeScript validator
- Frontend envelope parser accepts all eight Rust values

## Current UI Route Mappings (five active tools)

| Tool | Family |
|---|---|
| artifact.download | artifact_download |
| artifact.remove | artifact_remove |
| runtime.start | runtime_start |
| runtime.stop | runtime_stop |
| model.binding.set | model_binding_set |

Filesystem tools (files.read, files.list, files.write, files.create_folder, files.delete)
map to tool_filesystem_read/write/delete but are not exposed in the current UI.

## Error-Mapping Policy

Every ApprovalError variant maps through approval_error_code() to a distinct stable code.
No branch may collapse errors into generic "approval_denied" or "approval_error".

| ApprovalError variant | Bridge code |
|---|---|
| TokenNotFound | approval_token_unknown |
| AlreadyConsumed | approval_token_consumed |
| Expired | approval_token_expired |
| InvalidToken | approval_token_invalid |
| ToolMismatch | approval_operation_mismatch |
| InputDigestMismatch | approval_arguments_mismatch |
| WorkspaceMismatch | approval_workspace_mismatch |
| SessionMismatch | approval_session_mismatch |
| ApprovalIdMismatch | approval_identity_mismatch |
| CallIdMismatch | approval_call_mismatch |
| RiskMismatch | approval_risk_mismatch |
| FamilyMismatch | approval_family_mismatch |
| RegistryFull | approval_registry_full |
| Rejected | approval_rejected |
| PromptUnavailable | approval_prompt_unavailable |
