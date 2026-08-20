# Verification of attached audit findings — 2026-08-21

## Verified so far

| Finding | Current source observation | Status |
|---|---|---|
| F-01, frontend permission enforcement | `approvalStore.ts` requests an approval envelope and calls `runToolCall` immediately in a background flow. The displayed permission settings are not an execution-deny check in this file. | **Confirmed at the frontend boundary; backend and all capability call sites still require verification.** |
| F-02, Computer Use approval bypass | `approval_commands.rs` sets `approval_fields=None` and `grant_id=None` for `auto_computer_use`; dangerous calls otherwise use `registry.execute_approved` before dispatch. | **Confirmed.** The source contradicts the stated no-bypass invariant and requires an explicit Rust-side remediation design. |

## F-01 follow-up

`setAgentPermissions()` updates a Svelte store and persisted UI preferences. In `modelGateway.ts`, disabled `computerUse` and disabled file access only choose the frontend's `requestApprovalForTool()` branch. That function immediately mints an approval envelope and dispatches `runToolCall`; it is not a deny boundary. **F-01 is confirmed for the inspected Computer Use and read-only files paths.** The remaining tool families and backend call sites still need an exhaustive mapping before remediation.

## Safety decision

No source modification has been made from the attached audit. Correcting F-01/F-02 requires a change in `src-tauri`, which is prohibited by the repository instructions unless the current request expressly authorizes it. The findings will be completed with source/tests verification, then submitted for explicit approval to modify the Rust approval boundary.

## F-03 passive hang diagnosis

The `tools/test_v6846_tool_execution.py` launch produced no test output and remained attached to the remote shell past two 120-second observation windows. Passive process inspection found **no active Python process whose command line contained that test**, so the test body itself is no longer executing. The unrelated `python.exe .\\server.py` process observed on the desktop was created on 2026-08-19 by a separate `anthology-ai-helper` PowerShell launcher; it is not a child of the F-03 command and is not evidence that the test started a sidecar.

The current evidence therefore points to an orphaned/blocked remote shell session after the child test ended, rather than an active test deadlock. No process was stopped. F-03's functional failure remains separately confirmed by the test source: it still expects enabled `files.create_folder` and `files.delete`, while the current security contract intentionally returns `feature_disabled`.

## F-04 verification

F-04 is **confirmed**. `DEFAULT_UI_PREFERENCES` freezes only its outer object; `defaultPreferences()` shallow-copies it and retains the shared nested `agentPermissions` object. `normalizePreferences()` then mutates individual keys of that nested object. A valid stored preference can therefore mutate what later calls treat as the default permission values. This is a frontend state-integrity defect; it can be repaired by constructing a fresh `agentPermissions` object in `defaultPreferences()` and adding a regression test.

## Remediation contract approved by the user

1. A typed `AgentPermissions` value will live in `ApprovalState` with conservative defaults (all capabilities disabled), be reset on workspace changes, and be set only through a validated Rust command.
2. `request_approval`, `execute_approved`, `validate_approval_token`, and `run_tool_call` will reject a disabled tool family with `permission_denied` before token issuance, consumption, or sidecar dispatch.
3. `computer_use` remains `dangerous`: all such calls will obtain and atomically consume a normal one-time token/grant. The native Windows shortcut is removed so it cannot bypass the control-plane/sidecar approval boundary.
4. The frontend will submit the intended session permissions once through the validated backend command before it starts a model turn. Its local toggles are no longer the sole authority.
5. `defaultPreferences()` will create fresh nested permissions, and F-03 will assert the intentional `feature_disabled` behavior of unimplemented reparse-sensitive file mutations.

## Implementation note

`model_turn_start` already receives the validated `agent_permissions` payload that is used to build the assistant context. The minimal trustworthy sync point is therefore immediately after that validation and before the model request is dispatched: it can update `ApprovalState` for the active Rust process without inventing a second frontend-only permissions protocol. A separate `set_agent_permissions` command remains useful for an immediate toggle update and is registered through `lib.rs`.
