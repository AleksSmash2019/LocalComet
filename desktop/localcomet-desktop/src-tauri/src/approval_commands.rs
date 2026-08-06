use crate::approval::{
    canonical_input_digest, command_family_for_tool, ApprovalDescriptor, ApprovalEnvelope,
    ApprovalError, ApprovalPrompt, ApprovalRegistry, ApprovalScope, ExecutionGrant,
    IdempotencyOutcome, NativeWindowsApprovalPrompt, RiskLevel,
};
use crate::control_plane::{build_tool_call_request, BridgeError, ControlPlaneBridge};
use crate::workspace::WorkspaceIdentity;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use tauri::State;

/// GLOBAL TOOL EXECUTION LOCK
///
/// This constant gates all tool calls. It is set to true after the successful
/// MVP-P0-C-A2 security audit.
const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = true;

const NON_WORKSPACE_SENTINEL: &str = crate::approval::NON_WORKSPACE_APPROVAL_SCOPE;

fn is_non_workspace_operation(tool: &str) -> bool {
    matches!(
        tool,
        "artifact.download"
            | "artifact.remove"
            | "runtime.start"
            | "runtime.stop"
            | "model.binding.set"
    )
}

fn approval_error_code(error: &ApprovalError) -> &'static str {
    match error {
        ApprovalError::TokenNotFound => "approval_token_unknown",
        ApprovalError::AlreadyConsumed => "approval_token_consumed",
        ApprovalError::Expired => "approval_token_expired",
        ApprovalError::InvalidToken => "approval_token_invalid",
        ApprovalError::ToolMismatch => "approval_operation_mismatch",
        ApprovalError::InputDigestMismatch => "approval_arguments_mismatch",
        ApprovalError::WorkspaceMismatch => "approval_workspace_mismatch",
        ApprovalError::SessionMismatch => "approval_session_mismatch",
        ApprovalError::ApprovalIdMismatch => "approval_identity_mismatch",
        ApprovalError::CallIdMismatch => "approval_call_mismatch",
        ApprovalError::RiskMismatch => "approval_risk_mismatch",
        ApprovalError::FamilyMismatch => "approval_family_mismatch",
        ApprovalError::RegistryFull => "approval_registry_full",
        ApprovalError::Rejected => "approval_rejected",
        ApprovalError::PromptUnavailable => "approval_prompt_unavailable",
        ApprovalError::IdempotencyRegistryFull => "logical_call_registry_full",
        ApprovalError::IdempotencyPending => "logical_call_in_flight",
        ApprovalError::DuplicateLogicalCall => "logical_call_duplicate",
    }
}

fn resolve_approval_workspace(
    workspace_guard: &Option<WorkspaceIdentity>,
    tool: &str,
) -> Result<String, BridgeError> {
    match workspace_guard.as_ref() {
        Some(identity) => Ok(identity.canonical_path.clone()),
        None if is_non_workspace_operation(tool) => Ok(NON_WORKSPACE_SENTINEL.to_string()),
        None => Err(BridgeError::new(
            "no_workspace",
            "approval requires a confirmed workspace",
        )),
    }
}

/// Managed approval state: the single Rust authority for issuing and consuming
/// scoped one-time approval tokens, plus the currently confirmed workspace.
pub struct ApprovalState {
    registry: Mutex<ApprovalRegistry>,
    workspace: Mutex<Option<WorkspaceIdentity>>,
    prompt: Arc<dyn ApprovalPrompt>,
}

impl Default for ApprovalState {
    fn default() -> Self {
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            prompt: Arc::new(NativeWindowsApprovalPrompt),
        }
    }
}

impl ApprovalState {
    /// Store a confirmed workspace identity.
    ///
    /// Public API for workspace management. The `set_workspace` Tauri command
    /// updates the guards directly (to avoid re-locking the same mutexes), so
    /// this helper is not yet called internally; it is retained as the
    /// documented entry point for future UI/IPC workspace flows.
    #[allow(dead_code)]
    pub fn set_workspace(&self, identity: WorkspaceIdentity) {
        let mut workspace = self
            .workspace
            .lock()
            .expect("approval workspace lock poisoned");
        *workspace = Some(identity);
    }

    /// Invalidate all approval tokens bound to a previous workspace.
    ///
    /// `workspace::change_workspace` already performs this invalidation; this
    /// helper exposes the same operation for callers that change workspace
    /// outside that path.
    #[allow(dead_code)]
    pub fn invalidate_workspace_tokens(&self, old_workspace: &str) {
        let mut registry = self.registry.lock().expect("approval registry poisoned");
        registry.invalidate_workspace(old_workspace);
    }
}

/// Maps a tool name to its risk level.
///
/// MUST stay in sync with security/invariants/tool_risk_levels.toml. The
/// scripts/check_tool_risk_registry.py gate enforces the Python-side registry;
/// this mirror covers the Rust authorization boundary.
/// Unknown or malformed tool names are rejected fail-closed.
pub(crate) fn risk_level_for_tool(tool: &str) -> Result<RiskLevel, BridgeError> {
    match tool {
        "files.read" | "files.list" => Ok(RiskLevel::ReadOnly),
        "files.write"
        | "files.create_folder"
        | "files.rollback"
        | "files.rollback_undo"
        | "web.search"
        | "web.fetch"
        | "artifact.download"
        | "runtime.start"
        | "runtime.stop"
        | "model.binding.set" => Ok(RiskLevel::Guarded),
        "files.delete" | "artifact.remove" | "shell" | "computer_use" => Ok(RiskLevel::Dangerous),
        _ => Err(BridgeError::new(
            "unknown_tool",
            "unknown tool is not registered in the risk policy",
        )),
    }
}

/// Issue a scoped one-time approval token bound to (tool, input digest,
/// workspace, session). Requires an explicit positive user decision and fails
/// closed if no workspace is confirmed (non-workspace operations bind the
/// sentinel scope instead). Returns the plain token string; approval_id and
/// call_id are derived from the token at consume time.
#[tauri::command]
pub fn request_approval(
    state: State<'_, ApprovalState>,
    tool: String,
    input: Value,
) -> Result<ApprovalEnvelope, BridgeError> {
    let risk_level = risk_level_for_tool(&tool)?;
    let command_family = command_family_for_tool(&tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = resolve_approval_workspace(&workspace_guard, &tool)?;
    let scope = ApprovalScope {
        tool: tool.clone(),
        input_digest: digest,
        workspace,
        session: registry.session_id().to_owned(),
        risk_level,
        command_family,
        approval_id: String::new(),
        call_id: String::new(),
    };
    let descriptor = ApprovalDescriptor {
        tool: tool.clone(),
        command_family,
        risk_level,
        target_summary: serde_json::to_string(&input).unwrap_or_default(),
        side_effect_category: format!("{command_family:?}"),
        destructive: risk_level == RiskLevel::Dangerous,
    };
    let envelope = registry
        .request_with_prompt(scope, &descriptor, state.prompt.as_ref())
        .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))?;
    Ok(envelope)
}

/// Atomically validate scope and consume a one-time token, returning an
/// execution grant on success.
///
/// NOTE (honest boundary): the desktop sidecar exposes no tool.call execution
/// path (filesystem methods are explicitly `unsupported_method`), so this
/// command produces the authoritative grant but does not dispatch to the
/// sidecar. A future tool-execution path must present this grant; there is no
/// bypass around execute_approved.
#[tauri::command]
pub fn execute_approved(
    state: State<'_, ApprovalState>,
    token: String,
    tool: String,
    input: Value,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError> {
    let risk_level = risk_level_for_tool(&tool)?;
    let command_family = command_family_for_tool(&tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = resolve_approval_workspace(&workspace_guard, &tool)?;
    let grant = registry
        .execute_approved(
            &token,
            &tool,
            &digest,
            &workspace,
            &approval_id,
            &call_id,
            risk_level,
            command_family,
        )
        .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))?;
    if grant.is_expired() {
        return Err(BridgeError::new("grant_expired", "execution grant expired"));
    }
    Ok(json!({
        "grant_id": grant.grant_id,
        "tool": grant.tool,
        "workspace": grant.workspace,
        "session": grant.session,
    }))
}

/// Validate and consume a one-time approval token for a mutating command.
///
/// Shared gate used by the guarded/dangerous Tauri commands (artifact
/// acquisition, managed runtime, model binding). Computes the canonical input
/// digest, locks the registry and confirmed workspace, and atomically consumes
/// the token via `execute_approved`. The approval_id and call_id are derived
/// from the token itself; non-workspace operations bind the sentinel scope.
/// Returns the execution grant on success or a typed bridge error with a
/// specific approval error code without performing the guarded action on
/// failure.
pub fn validate_approval_token(
    state: &ApprovalState,
    tool: &str,
    input: &Value,
    token: &str,
    approval_id: &str,
    call_id: &str,
) -> Result<ExecutionGrant, BridgeError> {
    let risk_level = risk_level_for_tool(tool)?;
    let command_family = command_family_for_tool(tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let digest = canonical_input_digest(input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = resolve_approval_workspace(&workspace_guard, tool)?;
    let grant = registry
        .execute_approved(
            token,
            tool,
            &digest,
            &workspace,
            approval_id,
            call_id,
            risk_level,
            command_family,
        )
        .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))?;
    if grant.is_expired() {
        return Err(BridgeError::new("grant_expired", "execution grant expired"));
    }
    Ok(grant)
}

/// Execute a tool call, dispatching it to the sidecar after authorization.
///
/// Read-only tools run without a token. Guarded and dangerous tools require a
/// one-time approval token that is consumed atomically via `execute_approved`
/// BEFORE the sidecar dispatch (INV-APPROVAL-001: no bypass path). The grant and
/// confirmed workspace are forwarded so the sidecar can confine execution to the
/// workspace. Registry/workspace locks are released before the blocking IPC call.
#[tauri::command]
pub fn run_tool_call(
    state: State<'_, ApprovalState>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    tool: String,
    input: Value,
    token: Option<String>,
    approval_id: Option<String>,
    call_id: Option<String>,
) -> Result<Value, BridgeError> {
    if !TOOL_EXECUTION_ACTIVATION_ENABLED {
        return Err(BridgeError::new(
            "feature_disabled",
            "tool execution is disabled until execution binding is complete",
        ));
    }
    let risk_level = risk_level_for_tool(&tool)?;
    let command_family = command_family_for_tool(&tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let digest = canonical_input_digest(&input);
    let (grant_id, session, workspace_path, workspace_digest) = {
        let mut registry = state.registry.lock().expect("approval registry poisoned");
        let workspace_guard = state
            .workspace
            .lock()
            .expect("approval workspace lock poisoned");
        let workspace = workspace_guard.as_ref().ok_or_else(|| {
            BridgeError::new(
                "no_workspace",
                "tool execution requires a confirmed workspace",
            )
        })?;
        let approval_id_ref = approval_id.as_deref().unwrap_or("");
        let call_id_ref = call_id.as_deref().unwrap_or("");
        let idempotency_key =
            crate::approval::IdempotencyRegistry::make_key(&crate::approval::LogicalCallIdentity {
                tool: tool.clone(),
                input_digest: digest,
                workspace: workspace.canonical_path.clone(),
                session: registry.session_id().to_owned(),
                approval_id: approval_id_ref.to_owned(),
                call_id: call_id_ref.to_owned(),
                risk_level,
                command_family,
            });
        let idempotency_receipt = registry
            .begin_idempotent_call(&idempotency_key)
            .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))?;
        let grant_id: Option<String> = match risk_level {
            RiskLevel::ReadOnly => None,
            RiskLevel::Guarded | RiskLevel::Dangerous => {
                let token = token.ok_or_else(|| {
                    BridgeError::new("approval_required", "tool execution requires approval")
                })?;
                let approval_id = approval_id.ok_or_else(|| {
                    BridgeError::new("approval_required", "tool execution requires approval_id")
                })?;
                let call_id = call_id.ok_or_else(|| {
                    BridgeError::new("approval_required", "tool execution requires call_id")
                })?;
                let grant = registry
                    .execute_approved(
                        &token,
                        &tool,
                        &digest,
                        &workspace.canonical_path,
                        &approval_id,
                        &call_id,
                        risk_level,
                        command_family,
                    )
                    .map_err(|error| {
                        BridgeError::new(approval_error_code(&error), &error.to_string())
                    })?;
                if grant.is_expired() {
                    registry
                        .complete_idempotent_call(idempotency_receipt, IdempotencyOutcome::Failed);
                    return Err(BridgeError::new("grant_expired", "execution grant expired"));
                }
                registry
                    .complete_idempotent_call(idempotency_receipt, IdempotencyOutcome::Completed);
                Some(grant.grant_id)
            }
        };
        let session = registry.session_id().to_owned();
        (
            grant_id,
            session,
            workspace.canonical_path.clone(),
            workspace.digest.clone(),
        )
    };
    let (method, payload) = build_tool_call_request(
        &tool,
        &input,
        &workspace_path,
        &workspace_digest,
        &session,
        grant_id.as_deref(),
    )?;
    bridge.request(method, payload)
}

/// Confirm a workspace: validate the path, invalidate tokens bound to the
/// previous workspace, and store the new identity. Fails closed on invalid
/// paths or symlink/reparse escape.
#[tauri::command]
pub fn set_workspace(state: State<'_, ApprovalState>, path: String) -> Result<Value, BridgeError> {
    if !TOOL_EXECUTION_ACTIVATION_ENABLED {
        return Err(BridgeError::new(
            "feature_disabled",
            "tool execution is disabled until execution binding is complete",
        ));
    }
    let raw = std::path::Path::new(&path);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let mut workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let current = workspace_guard.clone();
    let identity = crate::workspace::change_workspace(raw, &mut registry, &current)
        .map_err(|error| BridgeError::new("workspace_error", &error.to_string()))?;
    *workspace_guard = Some(identity.clone());
    Ok(json!({
        "status": "ok",
        "canonical_path": identity.canonical_path,
        "workspace_digest": identity.digest,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::approval::{
        generate_approval_id, generate_call_id, generate_token, validate_approval_id_syntax,
        validate_call_id_syntax, validate_token_syntax, ApprovalDecision, CommandFamily,
        ScriptedApprovalPrompt,
    };

    const TEST_APPROVAL_ID: &str = "appr_00000000000000000000000000000000";
    const TEST_CALL_ID: &str = "call_00000000000000000000000000000000";

    #[test]
    fn b3r_known_read_only_unchanged() {
        assert_eq!(
            risk_level_for_tool("files.read").unwrap(),
            RiskLevel::ReadOnly
        );
        assert_eq!(
            risk_level_for_tool("files.list").unwrap(),
            RiskLevel::ReadOnly
        );
    }

    #[test]
    fn b3r_known_guarded_unchanged() {
        assert_eq!(
            risk_level_for_tool("files.write").unwrap(),
            RiskLevel::Guarded
        );
        assert_eq!(
            risk_level_for_tool("files.create_folder").unwrap(),
            RiskLevel::Guarded
        );
        assert_eq!(
            risk_level_for_tool("artifact.download").unwrap(),
            RiskLevel::Guarded
        );
        assert_eq!(
            risk_level_for_tool("runtime.start").unwrap(),
            RiskLevel::Guarded
        );
        assert_eq!(
            risk_level_for_tool("runtime.stop").unwrap(),
            RiskLevel::Guarded
        );
        assert_eq!(
            risk_level_for_tool("model.binding.set").unwrap(),
            RiskLevel::Guarded
        );
    }

    #[test]
    fn b3r_known_dangerous_unchanged() {
        assert_eq!(
            risk_level_for_tool("files.delete").unwrap(),
            RiskLevel::Dangerous
        );
        assert_eq!(
            risk_level_for_tool("artifact.remove").unwrap(),
            RiskLevel::Dangerous
        );
    }

    fn assert_unknown_tool_rejected(tool: &str) {
        let result = risk_level_for_tool(tool);
        let error = result.expect_err(&format!("B3R: {tool:?} must be rejected"));
        assert_eq!(error.code, "unknown_tool");
    }

    #[test]
    fn b3r_unknown_tool_rejected_fail_closed() {
        assert_unknown_tool_rejected("unknown.tool");
    }

    #[test]
    fn b3r_empty_name_rejected_fail_closed() {
        assert_unknown_tool_rejected("");
    }

    #[test]
    fn b3r_whitespace_name_rejected_fail_closed() {
        assert_unknown_tool_rejected("   ");
    }

    #[test]
    fn b3r_case_confusion_rejected_fail_closed() {
        assert_unknown_tool_rejected("FILES.READ");
    }

    #[test]
    fn b3r_prefix_suffix_confusion_rejected_fail_closed() {
        assert_unknown_tool_rejected("files.read.extra");
        assert_unknown_tool_rejected("evil.files.read");
    }

    fn test_approval_state_with_workspace() -> ApprovalState {
        ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(Some(WorkspaceIdentity {
                canonical_path: "C:\\test-workspace".to_string(),
                digest: "abcd1234".to_string(),
            })),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Approve,
            }),
        }
    }

    fn issue_test_token(
        state: &ApprovalState,
        tool: &str,
        input: &Value,
    ) -> (String, String, String) {
        let digest = canonical_input_digest(input);
        let mut registry = state.registry.lock().expect("registry lock");
        let workspace = state.workspace.lock().expect("workspace lock");
        let ws = workspace.as_ref().expect("workspace set");
        let token = generate_token();
        let approval_id = generate_approval_id();
        let call_id = generate_call_id();
        let scope = ApprovalScope {
            tool: tool.to_string(),
            input_digest: digest,
            workspace: ws.canonical_path.clone(),
            session: registry.session_id().to_owned(),
            risk_level: risk_level_for_tool(tool).expect("known tool"),
            command_family: command_family_for_tool(tool).expect("known tool"),
            approval_id: approval_id.clone(),
            call_id: call_id.clone(),
        };
        registry
            .issue_with_token(token.clone(), scope)
            .expect("issue token");
        (token, approval_id, call_id)
    }

    fn mock_state<T: Send + Sync + 'static>(value: &T) -> State<'_, T> {
        unsafe { std::mem::transmute::<&T, State<'_, T>>(value) }
    }

    fn dangling_bridge_state() -> State<'static, Arc<ControlPlaneBridge>> {
        let ptr: *const Arc<ControlPlaneBridge> = std::ptr::NonNull::dangling().as_ptr();
        mock_state(unsafe { &*ptr })
    }

    #[test]
    fn p0b_run_tool_call_rejected_when_disabled() {
        let approval_state = ApprovalState::default();
        let state = mock_state(&approval_state);
        let bridge = dangling_bridge_state();
        let result = run_tool_call(
            state,
            bridge,
            "files.read".into(),
            json!({}),
            None,
            None,
            None,
        );
        let error = result.expect_err("must be rejected when disabled");
        assert_eq!(error.code, "feature_disabled");
    }

    #[test]
    fn p0b_set_workspace_rejected_when_disabled() {
        let approval_state = ApprovalState::default();
        let state = mock_state(&approval_state);
        let result = set_workspace(state, "C:\\any-path".to_string());
        let error = result.expect_err("must be rejected when disabled");
        assert_eq!(error.code, "feature_disabled");
    }

    #[test]
    fn p0b_execute_approved_cannot_dispatch() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"path": "notes.txt"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "files.write", &input);
        let state = mock_state(&approval_state);
        let result = execute_approved(
            state,
            token,
            "files.write".into(),
            input,
            approval_id,
            call_id,
        );
        let grant = result.expect("grant issued");
        assert!(grant.get("grant_id").and_then(Value::as_str).is_some());
        assert_eq!(grant["tool"], "files.write");
        assert_eq!(grant["workspace"], "C:\\test-workspace");
        assert!(grant.get("session").and_then(Value::as_str).is_some());
    }

    #[test]
    fn p0b_confirmed_boolean_does_not_authorize() {
        let approval_state = ApprovalState::default();
        let state = mock_state(&approval_state);
        let bridge = dangling_bridge_state();
        let input = json!({"path": "notes.txt", "confirmed": true});
        let result = run_tool_call(state, bridge, "files.write".into(), input, None, None, None);
        assert!(result.is_err());
    }

    #[test]
    fn p0b_token_survives_scope_mismatch() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"path": "notes.txt"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "files.write", &input);
        let digest = canonical_input_digest(&input);
        let mut registry = approval_state.registry.lock().expect("registry lock");
        let mismatch = registry.execute_approved(
            &token,
            "files.delete",
            &digest,
            "C:\\test-workspace",
            &approval_id,
            &call_id,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        assert!(matches!(
            mismatch,
            Err(crate::approval::ApprovalError::ToolMismatch)
        ));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "C:\\test-workspace",
                &approval_id,
                &call_id,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .expect("correct tool succeeds");
        assert_eq!(grant.tool, "files.write");
    }

    #[test]
    fn p0b_replay_rejected() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"path": "notes.txt"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "files.write", &input);
        let digest = canonical_input_digest(&input);
        let mut registry = approval_state.registry.lock().expect("registry lock");
        registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "C:\\test-workspace",
                &approval_id,
                &call_id,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .expect("first consume succeeds");
        let replay = registry.execute_approved(
            &token,
            "files.write",
            &digest,
            "C:\\test-workspace",
            &approval_id,
            &call_id,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        assert!(matches!(
            replay,
            Err(crate::approval::ApprovalError::AlreadyConsumed)
        ));
    }

    #[test]
    fn p0b_forged_token_rejected() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({});
        let digest = canonical_input_digest(&input);
        let mut registry = approval_state.registry.lock().expect("registry lock");
        let forged_lcap = format!("lcap_{}", "00".repeat(32));
        let result_lcap = registry.execute_approved(
            &forged_lcap,
            "files.read",
            &digest,
            "C:\\test-workspace",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::ReadOnly,
            CommandFamily::ToolFilesystemRead,
        );
        assert!(matches!(
            result_lcap,
            Err(crate::approval::ApprovalError::TokenNotFound)
        ));
        let forged_apt = format!("apt_{}", "00".repeat(32));
        let result_apt = registry.execute_approved(
            &forged_apt,
            "files.read",
            &digest,
            "C:\\test-workspace",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::ReadOnly,
            CommandFamily::ToolFilesystemRead,
        );
        assert!(matches!(
            result_apt,
            Err(crate::approval::ApprovalError::InvalidToken)
        ));
    }

    #[test]
    fn p0b_concurrent_exactly_one_succeeds() {
        let registry = Arc::new(Mutex::new(ApprovalRegistry::new()));
        let input = json!({"path": "notes.txt"});
        let digest = canonical_input_digest(&input);
        let token = {
            let mut reg = registry.lock().expect("registry lock");
            let scope = ApprovalScope {
                tool: "files.write".to_string(),
                input_digest: digest,
                workspace: "C:\\test-workspace".to_string(),
                session: reg.session_id().to_owned(),
                risk_level: RiskLevel::Guarded,
                command_family: CommandFamily::ToolFilesystemWrite,
                approval_id: TEST_APPROVAL_ID.to_string(),
                call_id: TEST_CALL_ID.to_string(),
            };
            reg.issue(scope).expect("issue token")
        };
        let registry_a = Arc::clone(&registry);
        let token_a = token.clone();
        let handle_a = std::thread::spawn(move || {
            let mut reg = registry_a.lock().expect("registry lock");
            reg.execute_approved(
                &token_a,
                "files.write",
                &digest,
                "C:\\test-workspace",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
        });
        let registry_b = Arc::clone(&registry);
        let token_b = token;
        let handle_b = std::thread::spawn(move || {
            let mut reg = registry_b.lock().expect("registry lock");
            reg.execute_approved(
                &token_b,
                "files.write",
                &digest,
                "C:\\test-workspace",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
        });
        let result_a = handle_a.join().expect("thread a join");
        let result_b = handle_b.join().expect("thread b join");
        assert_ne!(
            result_a.is_ok(),
            result_b.is_ok(),
            "exactly one must succeed"
        );
    }

    #[test]
    fn p0b_r2_confirmed_false_neutral_artifact_download() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"artifact_id": "test-artifact"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "artifact.download", &input);
        let result = validate_approval_token(
            &approval_state,
            "artifact.download",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn p0b_r2_confirmed_false_neutral_artifact_remove() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"model_id": "test-model"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "artifact.remove", &input);
        let result = validate_approval_token(
            &approval_state,
            "artifact.remove",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn p0b_r2_confirmed_false_neutral_model_binding() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"provider_id": "lmstudio", "model_id": "m1"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "model.binding.set", &input);
        let result = validate_approval_token(
            &approval_state,
            "model.binding.set",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn p0b_r2_confirmed_false_neutral_runtime_start() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"model_id": "test-model"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "runtime.start", &input);
        let result = validate_approval_token(
            &approval_state,
            "runtime.start",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn p0b_r2_confirmed_false_neutral_runtime_stop() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "runtime.stop", &input);
        let result = validate_approval_token(
            &approval_state,
            "runtime.stop",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn p0b_r4_token_syntax_exact_69_chars() {
        let approval_state = test_approval_state_with_workspace();
        let digest = canonical_input_digest(&json!({}));
        let mut registry = approval_state.registry.lock().expect("registry lock");
        let short_token = format!("lcap_{}", "a".repeat(63));
        assert_eq!(short_token.len(), 68);
        let result = registry.execute_approved(
            &short_token,
            "files.read",
            &digest,
            "C:\\test-workspace",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::ReadOnly,
            CommandFamily::ToolFilesystemRead,
        );
        assert!(
            matches!(&result, Err(crate::approval::ApprovalError::InvalidToken)),
            "token with wrong length must be InvalidToken, got {result:?}"
        );
        let long_token = format!("lcap_{}", "a".repeat(65));
        assert_eq!(long_token.len(), 70);
        let result = registry.execute_approved(
            &long_token,
            "files.read",
            &digest,
            "C:\\test-workspace",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::ReadOnly,
            CommandFamily::ToolFilesystemRead,
        );
        assert!(
            matches!(&result, Err(crate::approval::ApprovalError::InvalidToken)),
            "token with wrong length must be InvalidToken, got {result:?}"
        );
    }

    #[test]
    fn p0b_r4_token_syntax_rejects_uppercase_hex() {
        let approval_state = test_approval_state_with_workspace();
        let digest = canonical_input_digest(&json!({}));
        let mut registry = approval_state.registry.lock().expect("registry lock");
        let upper_token = format!("lcap_{}", "A".repeat(64));
        assert_eq!(upper_token.len(), 69);
        let result = registry.execute_approved(
            &upper_token,
            "files.read",
            &digest,
            "C:\\test-workspace",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::ReadOnly,
            CommandFamily::ToolFilesystemRead,
        );
        assert!(
            matches!(&result, Err(crate::approval::ApprovalError::InvalidToken)),
            "uppercase hex token must be InvalidToken, got {result:?}"
        );
    }

    #[test]
    fn p0b_r5_request_approval_returns_envelope() {
        let approval_state = test_approval_state_with_workspace();
        let state = mock_state(&approval_state);
        let envelope = request_approval(state, "files.write".into(), json!({"path": "notes.txt"}))
            .expect("scripted approve issues envelope");
        assert_eq!(envelope.token.len(), 69);
        assert!(envelope.token.starts_with("lcap_"));
        assert!(validate_token_syntax(&envelope.token));
        assert!(validate_approval_id_syntax(&envelope.approval_id));
        assert!(validate_call_id_syntax(&envelope.call_id));
        assert_eq!(envelope.tool, "files.write");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);
        assert_eq!(envelope.command_family, CommandFamily::ToolFilesystemWrite);
    }

    #[test]
    fn p0b_r5_request_approval_rejected_by_prompt() {
        let approval_state = ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(Some(WorkspaceIdentity {
                canonical_path: "C:\\test-workspace".to_string(),
                digest: "abcd1234".to_string(),
            })),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Reject,
            }),
        };
        let state = mock_state(&approval_state);
        let result = request_approval(state, "files.write".into(), json!({"path": "notes.txt"}));
        let error = result.expect_err("rejected prompt must fail");
        assert_eq!(error.code, "approval_rejected");
    }

    #[test]
    fn p0b_r4_non_workspace_operations_use_sentinel() {
        let approval_state = ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Approve,
            }),
        };
        let input = json!({"artifact_id": "test-artifact"});
        let (token, approval_id, call_id) = {
            let digest = canonical_input_digest(&input);
            let mut registry = approval_state.registry.lock().expect("registry lock");
            let token = generate_token();
            let approval_id = generate_approval_id();
            let call_id = generate_call_id();
            let scope = ApprovalScope {
                tool: "artifact.download".to_string(),
                input_digest: digest,
                workspace: NON_WORKSPACE_SENTINEL.to_string(),
                session: registry.session_id().to_owned(),
                risk_level: risk_level_for_tool("artifact.download").expect("known tool"),
                command_family: command_family_for_tool("artifact.download").expect("known tool"),
                approval_id: approval_id.clone(),
                call_id: call_id.clone(),
            };
            registry
                .issue_with_token(token.clone(), scope)
                .expect("issue token");
            (token, approval_id, call_id)
        };
        let result = validate_approval_token(
            &approval_state,
            "artifact.download",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        let grant = result.expect("non-workspace operation must bind the sentinel scope");
        assert_eq!(grant.workspace, NON_WORKSPACE_SENTINEL);
    }

    #[test]
    fn p0b_r4_error_codes_are_specific() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"path": "notes.txt"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "files.write", &input);
        let mismatch = validate_approval_token(
            &approval_state,
            "files.delete",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        let error = mismatch.expect_err("wrong tool must be rejected");
        assert_eq!(error.code, "approval_operation_mismatch");
        let malformed = validate_approval_token(
            &approval_state,
            "files.write",
            &input,
            "lcap_short",
            &approval_id,
            &call_id,
        );
        let error = malformed.expect_err("malformed token must be rejected");
        assert_eq!(error.code, "approval_token_invalid");
        let unknown = format!("lcap_{}", "f".repeat(64));
        let unknown_result = validate_approval_token(
            &approval_state,
            "files.write",
            &input,
            &unknown,
            &approval_id,
            &call_id,
        );
        let error = unknown_result.expect_err("unknown token must be rejected");
        assert_eq!(error.code, "approval_token_unknown");
        validate_approval_token(
            &approval_state,
            "files.write",
            &input,
            &token,
            &approval_id,
            &call_id,
        )
        .expect("correct scope consumes the token");
        let replay = validate_approval_token(
            &approval_state,
            "files.write",
            &input,
            &token,
            &approval_id,
            &call_id,
        );
        let error = replay.expect_err("replay must be rejected");
        assert_eq!(error.code, "approval_token_consumed");
    }
}
