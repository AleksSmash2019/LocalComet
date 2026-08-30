use crate::approval::{
    canonical_input_digest, command_family_for_tool, ApprovalDecision, ApprovalDescriptor,
    ApprovalEnvelope, ApprovalError, ApprovalPrompt, ApprovalRegistry, ApprovalScope,
    ExecutionGrant, FrontendApprovalDispatcher, FrontendApprovalPrompt, IdempotencyOutcome,
    RiskLevel, ScriptedApprovalPrompt,
};
use crate::control_plane::{
    build_tool_call_request_with_correlation, AgentPermissions, BridgeError, ControlPlaneBridge,
};
use crate::managed_runtime::ManagedRuntimeSupervisor;
use crate::workspace::WorkspaceIdentity;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use tauri::State;

/// GLOBAL TOOL EXECUTION LOCK
///
/// This constant gates all tool calls. It is set to true after the successful
/// MVP-P0-C-A2 security audit.
const TOOL_EXECUTION_ACTIVATION_ENABLED: bool = true;

/// Pure activation gate - no State, no bridge, no env, no global mutable.
/// Production entry points must call this before touching State.
pub(crate) fn activation_gate(enabled: bool) -> Result<(), BridgeError> {
    if enabled {
        Ok(())
    } else {
        Err(BridgeError::new(
            "feature_disabled",
            "tool execution is disabled until execution binding is complete",
        ))
    }
}

fn is_tool_execution_enabled() -> bool {
    TOOL_EXECUTION_ACTIVATION_ENABLED
}

fn require_approval_fields(
    risk_level: RiskLevel,
    token: Option<String>,
    approval_id: Option<String>,
    call_id: Option<String>,
) -> Result<Option<(String, String, String)>, BridgeError> {
    match risk_level {
        RiskLevel::ReadOnly => Ok(None),
        RiskLevel::Guarded | RiskLevel::Dangerous => Ok(Some((
            token.ok_or_else(|| {
                BridgeError::new("approval_required", "tool execution requires approval")
            })?,
            approval_id.ok_or_else(|| {
                BridgeError::new("approval_required", "tool execution requires approval_id")
            })?,
            call_id.ok_or_else(|| {
                BridgeError::new("approval_required", "tool execution requires call_id")
            })?,
        ))),
    }
}

const NON_WORKSPACE_SENTINEL: &str = crate::approval::NON_WORKSPACE_APPROVAL_SCOPE;

fn is_non_workspace_operation(tool: &str) -> bool {
    matches!(
        tool,
        "artifact.download"
            | "artifact.remove"
            | "runtime.start"
            | "runtime.stop"
            | "model.binding.set"
            | "import_custom_model"
            | "computer_use"
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
    permissions: Mutex<AgentPermissions>,
    permission_context: Mutex<Option<crate::permission_context::PermissionContext>>,
    prompt: Arc<dyn ApprovalPrompt>,
    pub dispatcher: Option<Arc<FrontendApprovalDispatcher>>,
}

impl Default for ApprovalState {
    fn default() -> Self {
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            permissions: Mutex::new(disabled_agent_permissions()),
            permission_context: Mutex::new(None),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Reject,
            }), // Tests can override this
            dispatcher: None,
        }
    }
}

impl ApprovalState {
    pub fn new(app_handle: tauri::AppHandle) -> Self {
        let dispatcher = Arc::new(FrontendApprovalDispatcher::new(app_handle));
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            permissions: Mutex::new(disabled_agent_permissions()),
            permission_context: Mutex::new(None),
            prompt: Arc::new(FrontendApprovalPrompt {
                dispatcher: Arc::clone(&dispatcher),
            }),
            dispatcher: Some(dispatcher),
        }
    }

    /// Digest of the armed permission context, if any (typed evidence only).
    pub fn permission_context_digest(&self) -> String {
        let guard = self
            .permission_context
            .lock()
            .expect("permission context lock poisoned");
        guard
            .as_ref()
            .map(|c| c.context_digest.clone())
            .unwrap_or_default()
    }

    /// Read-only accessor for typed consumers (checkpoint commands): the
    /// confirmed workspace identity, if any.
    pub(crate) fn workspace_identity(&self) -> Option<(String, String)> {
        let guard = self
            .workspace
            .lock()
            .expect("approval workspace lock poisoned");
        guard
            .as_ref()
            .map(|identity| (identity.canonical_path.clone(), identity.digest.clone()))
    }

    /// Arm the typed permission context (F-03 isolated harness path).
    pub fn set_permission_context(&self, context: crate::permission_context::PermissionContext) {
        let mut guard = self
            .permission_context
            .lock()
            .expect("permission context lock poisoned");
        *guard = Some(context);
    }

    /// F-03 runtime gate: when an armed context exists it must still be
    /// valid (unexpired, unrevoked) before any guarded/dangerous dispatch.
    /// A normal session has `None` here and is governed purely by the
    /// backend-authoritative capability flags above.
    #[allow(dead_code)]
    pub(crate) fn permission_context_valid(&self) -> bool {
        let guard = self
            .permission_context
            .lock()
            .expect("permission context lock poisoned");
        match guard.as_ref() {
            None => true,
            Some(context) => {
                let now = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_millis() as u64)
                    .unwrap_or(0);
                now < context.expires_at_unix_ms && !context.revoked
            }
        }
    }

    pub(crate) fn require_permission_context_for_tool(
        &self,
        tool: &str,
    ) -> Result<(), BridgeError> {
        let (session_id, workspace_digest, desktop) = {
            let registry = self.registry.lock().expect("approval registry poisoned");
            let ws_guard = self
                .workspace
                .lock()
                .expect("approval workspace lock poisoned");
            let (workspace_digest, _) = match ws_guard.as_ref() {
                Some(identity) => (identity.digest.clone(), identity.canonical_path.clone()),
                None if is_non_workspace_operation(tool) => (
                    crate::approval::NON_WORKSPACE_APPROVAL_SCOPE.to_string(),
                    crate::approval::NON_WORKSPACE_APPROVAL_SCOPE.to_string(),
                ),
                None => {
                    // No workspace confirmed: only read_only tools allowed without context;
                    // guarded/dangerous will later fail on no_workspace.
                    return Ok(());
                }
            };
            let desktop = std::env::var("LC_HIDDEN_DESKTOP_NAME")
                .ok()
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty());
            (registry.session_id().to_owned(), workspace_digest, desktop)
        };
        let guard = self
            .permission_context
            .lock()
            .expect("permission context lock poisoned");
        let Some(context) = guard.as_ref() else {
            return Ok(());
        };
        if let Err(code) = context.verify_digest() {
            return Err(BridgeError::new(code, code));
        }
        let Some(capability_id) =
            crate::permission_context::PermissionContext::capability_for_tool(tool)
        else {
            // Unknown tool already denied elsewhere; no context check.
            return Ok(());
        };
        context
            .validate(
                &session_id,
                &workspace_digest,
                desktop.as_deref(),
                capability_id,
            )
            .map_err(|code| BridgeError::new(code, code))?;
        // Isolated context must be IsolatedHiddenTest; Normal sessions never arm a context.
        context
            .validate_mode(crate::permission_context::ExecutionMode::IsolatedHiddenTest)
            .map_err(|code| BridgeError::new(code, code))?;
        Ok(())
    }

    pub(crate) fn session_id(&self) -> String {
        self.registry
            .lock()
            .expect("approval registry poisoned")
            .session_id()
            .to_owned()
    }

    pub(crate) fn sync_isolated_workspace_digest(&self, new_digest: &str) {
        let mut guard = self
            .permission_context
            .lock()
            .expect("permission context lock poisoned");
        if let Some(ctx) = guard.as_mut() {
            if ctx.execution_mode == crate::permission_context::ExecutionMode::IsolatedHiddenTest {
                // Re-bind workspace scope for all capabilities and recompute digest.
                ctx.workspace_digest = new_digest.to_owned();
                for cap in &mut ctx.capabilities {
                    cap.workspace_scope = new_digest.to_owned();
                }
                ctx.context_digest = ctx.compute_digest();
            }
        }
    }

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

    /// Update the backend-authoritative capability state for the current model
    /// session. Any change revokes outstanding approval material.
    pub fn set_agent_permissions(&self, permissions: AgentPermissions) {
        let mut current = self
            .permissions
            .lock()
            .expect("approval permissions lock poisoned");
        if *current != permissions {
            *current = permissions;
            let mut registry = self.registry.lock().expect("approval registry poisoned");
            *registry = ApprovalRegistry::new();
        }
    }

    /// Test-only state for the deterministic intent→approval→broker e2e seam
    /// /// (live_e2e). Scripted Approve prompt, confirmed workspace, all caps on.
    #[cfg(test)]
    pub(crate) fn for_intent_e2e() -> Self {
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(Some(WorkspaceIdentity {
                canonical_path: r"C:\Windows".to_string(),
                digest: "intent-e2e-ws".to_string(),
            })),
            permission_context: Mutex::new(None),
            permissions: Mutex::new(AgentPermissions {
                files: true,
                shell: true,
                tools: true,
                computer_use: true,
                internet: true,
            }),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Approve,
            }),
            dispatcher: None,
        }
    }

    fn allows_tool(&self, tool: &str) -> bool {
        let permissions = self
            .permissions
            .lock()
            .expect("approval permissions lock poisoned");
        match tool {
            "files.read"
            | "files.list"
            | "files.write"
            | "files.create_folder"
            | "files.delete"
            | "files.rollback"
            | "files.rollback_undo"
            | "checkpoint.restore_files"
            | "checkpoint.restore_task" => permissions.files,
            "shell" => permissions.shell,
            "computer_use" => permissions.computer_use,
            "web.search" | "web.fetch" => permissions.internet,
            "skills.invoke" => permissions.tools,
            _ => true,
        }
    }
}

fn disabled_agent_permissions() -> AgentPermissions {
    AgentPermissions {
        files: false,
        shell: false,
        tools: false,
        computer_use: false,
        internet: false,
    }
}

fn require_tool_permission(state: &ApprovalState, tool: &str) -> Result<(), BridgeError> {
    if state.allows_tool(tool) {
        Ok(())
    } else {
        Err(BridgeError::new(
            "permission_denied",
            "the required capability is disabled for this session",
        ))
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
        | "checkpoint.restore_files"
        | "checkpoint.restore_task"
        | "web.search"
        | "web.fetch"
        | "artifact.download"
        | "runtime.start"
        | "runtime.stop"
        | "model.binding.set"
        | "import_custom_model" => Ok(RiskLevel::Guarded),
        "files.delete" | "artifact.remove" | "shell" | "computer_use" | "skills.invoke" => {
            Ok(RiskLevel::Dangerous)
        }
        _ => Err(BridgeError::new(
            "unknown_tool",
            "unknown tool is not registered in the risk policy",
        )),
    }
}

#[tauri::command(async)]
pub fn resolve_tool_approval(
    state: tauri::State<'_, ApprovalState>,
    request_id: String,
    decision: String,
) -> Result<(), BridgeError> {
    let decision_enum = match decision.as_str() {
        "approve" => ApprovalDecision::Approve,
        "reject" => ApprovalDecision::Reject,
        _ => {
            return Err(BridgeError::new(
                "invalid_decision",
                "Decision must be 'approve' or 'reject'",
            ))
        }
    };

    if let Some(dispatcher) = &state.dispatcher {
        dispatcher
            .resolve(&request_id, decision_enum)
            .map_err(|e| BridgeError::new("resolve_failed", &e))
    } else {
        Err(BridgeError::new(
            "no_dispatcher",
            "Frontend dispatcher not available",
        ))
    }
}

fn computer_use_risk_for_input(input: &Value) -> Result<(RiskLevel, String, bool), BridgeError> {
    let action = input
        .get("action")
        .and_then(Value::as_str)
        .map(str::trim)
        .map(str::to_ascii_lowercase)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| BridgeError::new("invalid_payload", "computer_use action is required"))?;
    // `text` is intentionally excluded. Typing a sentence that happens to
    // contain "delete" or "password" is not an external side effect. Semantic
    // escalation comes from the action target/control metadata instead.
    let semantic_context = [
        "target",
        "control",
        "field",
        "label",
        "window",
        "url",
        "destination",
        "button",
        "role",
        "title",
        "goal",
    ]
    .iter()
    .filter_map(|key| input.get(*key).and_then(Value::as_str))
    .map(|value| value.trim().to_ascii_lowercase())
    .filter(|value| !value.is_empty())
    .collect::<Vec<_>>()
    .join(" ");
    let path_context = [
        "target",
        "path",
        "file_path",
        "folder",
        "directory",
        "destination",
    ]
    .iter()
    .filter_map(|key| input.get(*key).and_then(Value::as_str))
    .map(|value| value.trim().to_ascii_lowercase())
    .filter(|value| !value.is_empty())
    .collect::<Vec<_>>()
    .join(" ");
    let target_is_path =
        path_context.contains('\\') || path_context.contains('/') || path_context.contains(':');
    let system_target = target_is_path
        || [
            "system32",
            "\\windows",
            "/windows",
            "program files",
            "programdata",
            "system volume information",
            "registry",
            "hkey_",
            "$recycle.bin",
            "boot",
        ]
        .iter()
        .any(|marker| path_context.contains(marker));
    let sensitive_or_external = [
        "password",
        "passcode",
        "otp",
        "verification code",
        "captcha",
        "login",
        "log in",
        "sign in",
        "send",
        "submit",
        "purchase",
        "checkout",
        "payment",
        "credit card",
        "delete",
        "remove",
        "format",
        "shutdown",
        "restart",
        "install",
        "uninstall",
        "administrator",
        "admin",
        "grant access",
        "allow access",
        "publish",
    ]
    .iter()
    .any(|marker| semantic_context.contains(marker));

    if system_target {
        return Ok((
            RiskLevel::Dangerous,
            "computer_use_system_or_unallowlisted_path".to_owned(),
            true,
        ));
    }
    if sensitive_or_external {
        return Ok((
            RiskLevel::Dangerous,
            "computer_use_sensitive_or_external_effect".to_owned(),
            false,
        ));
    }

    match action.as_str() {
        "screenshot" | "wait" | "wait_for_window" | "observe" | "cursor_position"
        | "mouse_move" | "scroll" => Ok((
            RiskLevel::ReadOnly,
            "computer_use_observation".to_owned(),
            false,
        )),
        "open_app" => Ok((
            RiskLevel::Guarded,
            "computer_use_application_launch".to_owned(),
            false,
        )),
        "open_folder" => Ok((
            RiskLevel::Guarded,
            "computer_use_folder_open".to_owned(),
            false,
        )),
        "open_url" => Ok((
            // External browser navigation is an observable side effect and must
            // always wait for the explicit frontend consent card.
            RiskLevel::Dangerous,
            "computer_use_browser_navigation".to_owned(),
            false,
        )),
        "click" | "double_click" | "type" | "type_element" | "paste" | "key" | "hotkey"
        | "drag" | "task" => Ok((
            RiskLevel::Guarded,
            "computer_use_ui_interaction".to_owned(),
            false,
        )),
        "close_owned" => Ok((
            RiskLevel::Dangerous,
            "computer_use_owned_lifecycle".to_owned(),
            false,
        )),
        _ => Err(BridgeError::new(
            "unsupported_action",
            "computer_use action is not registered in the risk policy",
        )),
    }
}

/// Validate the request and build the approval scope plus the descriptor the
/// consent card renders (tool, risk, target summary, side-effect category).
fn effective_risk_level(tool: &str, input: &Value) -> Result<RiskLevel, BridgeError> {
    if tool == "computer_use" {
        return computer_use_risk_for_input(input).map(|(risk, _, _)| risk);
    }
    risk_level_for_tool(tool)
}

fn build_approval_scope_and_descriptor(
    state: &ApprovalState,
    tool: &str,
    input: &Value,
    model_request_id: Option<String>,
    model_action_id: Option<String>,
) -> Result<(ApprovalScope, ApprovalDescriptor), BridgeError> {
    require_tool_permission(state, tool)?;
    let tool_risk_level = risk_level_for_tool(tool)?;
    let command_family = command_family_for_tool(tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let (risk_level, side_effect_category, destructive) = if tool == "computer_use" {
        computer_use_risk_for_input(input)?
    } else {
        (
            tool_risk_level,
            format!("{command_family:?}"),
            tool_risk_level == RiskLevel::Dangerous,
        )
    };
    let digest = canonical_input_digest(input);
    let session = {
        let registry = state.registry.lock().expect("approval registry poisoned");
        registry.session_id().to_owned()
    };
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = resolve_approval_workspace(&workspace_guard, tool)?;
    if tool == "computer_use" {
        if let Some(action) = crate::cu_broker::broker_action(input) {
            crate::cu_broker::validate_broker_action(action, input, Some(workspace.as_str()))
                .map_err(|reason| {
                    BridgeError::new(
                        "computer_use_blocked",
                        &format!("broker blocked action: {reason}"),
                    )
                })?;
        }
    }
    let scope = ApprovalScope {
        tool: tool.to_string(),
        input_digest: digest,
        workspace,
        session,
        risk_level,
        command_family,
        approval_id: String::new(),
        call_id: String::new(),
    };
    let descriptor = ApprovalDescriptor {
        tool: tool.to_string(),
        command_family,
        risk_level,
        input_digest: digest,
        model_request_id,
        model_action_id,
        target_summary: serde_json::to_string(input).unwrap_or_default(),
        side_effect_category,
        destructive,
    };
    Ok((scope, descriptor))
}

fn validate_model_request_id(value: Option<String>) -> Result<Option<String>, BridgeError> {
    match value {
        None => Ok(None),
        Some(id)
            if id.len() == 24
                && id
                    .bytes()
                    .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase()) =>
        {
            Ok(Some(id))
        }
        Some(_) => Err(BridgeError::new(
            "invalid_correlation",
            "model request id must be exactly 24 lowercase hexadecimal characters",
        )),
    }
}

fn validate_model_action_id(value: Option<String>) -> Result<Option<String>, BridgeError> {
    match value {
        None => Ok(None),
        Some(id)
            if !id.is_empty()
                && id.len() <= 256
                && !id.chars().any(|character| character.is_control()) =>
        {
            Ok(Some(id))
        }
        Some(_) => Err(BridgeError::new(
            "invalid_correlation",
            "model action id must be a bounded non-control string",
        )),
    }
}

fn issue_scoped_envelope(
    state: &ApprovalState,
    scope: ApprovalScope,
    descriptor: &ApprovalDescriptor,
) -> Result<ApprovalEnvelope, BridgeError> {
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    registry
        .issue_without_prompt(scope, descriptor)
        .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))
}

/// Issue a scoped one-time approval token bound to (tool, input digest,
/// workspace, session).
///
/// Guarded and read-only operations use the background boundary: the frontend
/// reaches this command only from an explicit user action for that exact
/// operation (button click) or a session capability the user granted, and the
/// token stays scoped, single-use, expiring and validated before execution.
/// Dangerous tools additionally require an explicit user decision: the
/// approval prompt emits a `request_tool_approval` card to the frontend, and
/// issuance happens only after an Approve decision; reject, prompt timeout
/// and frontend disconnect all deny issuance.
#[tauri::command(async)]
pub async fn request_approval(
    state: State<'_, ApprovalState>,
    _runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    tool: String,
    input: Value,
    request_id: Option<String>,
    action_id: Option<String>,
) -> Result<ApprovalEnvelope, BridgeError> {
    let request_id = validate_model_request_id(request_id)?;
    let action_id = validate_model_action_id(action_id)?;
    let (scope, descriptor) =
        build_approval_scope_and_descriptor(&state, &tool, &input, request_id, action_id)?;
    if descriptor.risk_level == RiskLevel::Dangerous {
        // The prompt blocks for up to PROMPT_TIMEOUT_SECS on a user decision;
        // run it on the blocking pool so no async worker is parked.
        let prompt = Arc::clone(&state.prompt);
        let prompt_descriptor = descriptor.clone();
        let decision =
            tauri::async_runtime::spawn_blocking(move || prompt.decide(&prompt_descriptor))
                .await
                .map_err(|_| {
                    BridgeError::new("approval_prompt_failed", "approval prompt task failed")
                })?
                .map_err(|_| {
                    BridgeError::new("approval_prompt_unavailable", "approval prompt unavailable")
                })?;
        match decision {
            ApprovalDecision::Approve => {}
            ApprovalDecision::Reject => {
                return Err(BridgeError::new(
                    "approval_rejected",
                    "the user rejected the requested tool action",
                ));
            }
        }
    }
    issue_scoped_envelope(&state, scope, &descriptor)
}

#[cfg(test)]
pub(crate) fn request_approval_inner(
    state: &ApprovalState,
    tool: String,
    input: Value,
) -> Result<ApprovalEnvelope, BridgeError> {
    let (scope, descriptor) =
        build_approval_scope_and_descriptor(state, &tool, &input, None, None)?;
    if descriptor.risk_level == RiskLevel::Dangerous {
        match state.prompt.decide(&descriptor) {
            Ok(ApprovalDecision::Approve) => {}
            Ok(ApprovalDecision::Reject) => {
                return Err(BridgeError::new(
                    "approval_rejected",
                    "the user rejected the requested tool action",
                ));
            }
            Err(_) => {
                return Err(BridgeError::new(
                    "approval_prompt_unavailable",
                    "approval prompt unavailable",
                ));
            }
        }
    }
    issue_scoped_envelope(state, scope, &descriptor)
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
    require_tool_permission(&state, &tool)?;
    let risk_level = effective_risk_level(&tool, &input)?;
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

/// Issue a scoped one-time approval envelope for a GUARDED tool input on
/// behalf of a Rust-internal typed command (e.g. `coding_start_approval`).
///
/// Guarded tools use the documented background boundary: the frontend reaches
/// this only through an explicit per-operation user action, and the resulting
/// token stays scoped to (tool, input digest, workspace, session), single-use,
/// expiring. Dangerous tools must NEVER route through this helper — they
/// always require the interactive prompt path in `request_approval`.
pub(crate) fn issue_guarded_approval_for_input(
    state: &ApprovalState,
    tool: &str,
    input: &Value,
) -> Result<ApprovalEnvelope, BridgeError> {
    if risk_level_for_tool(tool)? != RiskLevel::Guarded {
        return Err(BridgeError::new(
            "invalid_tool_risk_path",
            "guarded-only issuance helper refused a non-guarded tool",
        ));
    }
    require_tool_permission(state, tool)?;
    let (scope, descriptor) = build_approval_scope_and_descriptor(state, tool, input, None, None)?;
    issue_scoped_envelope(state, scope, &descriptor)
}

#[cfg(test)]
fn execute_approved_inner(
    state: &ApprovalState,
    token: String,
    tool: String,
    input: Value,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError> {
    require_tool_permission(state, &tool)?;
    let risk_level = effective_risk_level(&tool, &input)?;
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
    require_tool_permission(state, tool)?;
    let risk_level = effective_risk_level(tool, input)?;
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
///
/// The explicit metadata parameters keep model-turn correlation out of the
/// schema-validated input object. This command already has six authorization
/// fields, so the clippy exception is intentionally local to this Tauri seam.
#[allow(clippy::too_many_arguments)]
#[tauri::command]
pub fn run_tool_call(
    state: State<'_, ApprovalState>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    tool: String,
    input: Value,
    token: Option<String>,
    approval_id: Option<String>,
    call_id: Option<String>,
    request_id: Option<String>,
    action_id: Option<String>,
) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    let tool_for_detail = tool.clone();
    run_tool_call_inner(
        &state,
        Some(&bridge),
        tool,
        input,
        token,
        approval_id,
        call_id,
        request_id.clone(),
        action_id.clone(),
    )
    .map_err(|error| {
        // INV-ERR-001: dispatch-stage rejections carry the versioned envelope
        // with model-turn correlation so the UI can show a diagnostic id
        // instead of an opaque failure.
        error
            .with_phase("tool_dispatch")
            .with_correlation(request_id.as_deref().or(action_id.as_deref()))
            .with_detail("tool", &Value::String(tool_for_detail))
    })
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn run_tool_call_inner(
    state: &ApprovalState,
    bridge: Option<&ControlPlaneBridge>,
    tool: String,
    input: Value,
    token: Option<String>,
    approval_id: Option<String>,
    call_id: Option<String>,
    request_id: Option<String>,
    action_id: Option<String>,
) -> Result<Value, BridgeError> {
    require_tool_permission(state, &tool)?;
    // F-03 full binding gate: when an armed context exists it must match
    // session/workspace/desktop/capability/digest/expiry/mode before ANY
    // guarded/dangerous dispatch. Normal sessions (None) pass through.
    state.require_permission_context_for_tool(&tool)?;
    let risk_level = effective_risk_level(&tool, &input)?;
    let command_family = command_family_for_tool(&tool)
        .ok_or_else(|| BridgeError::new("unknown_tool", "unknown tool has no command family"))?;
    let digest = canonical_input_digest(&input);
    // Every guarded/dangerous operation, including Computer Use, consumes a
    // scoped one-time approval before sidecar dispatch.
    let approval_fields = require_approval_fields(risk_level, token, approval_id, call_id)?;
    let (grant, session, workspace_path, workspace_digest, idempotency_receipt) = {
        let mut registry = state.registry.lock().expect("approval registry poisoned");
        let workspace_guard = state
            .workspace
            .lock()
            .expect("approval workspace lock poisoned");
        let (workspace_path, workspace_digest) = match workspace_guard.as_ref() {
            Some(identity) => (identity.canonical_path.clone(), identity.digest.clone()),
            None if is_non_workspace_operation(&tool) => (
                NON_WORKSPACE_SENTINEL.to_owned(),
                NON_WORKSPACE_SENTINEL.to_owned(),
            ),
            None => {
                return Err(BridgeError::new(
                    "no_workspace",
                    "tool execution requires a confirmed workspace",
                ));
            }
        };
        let approval_id_ref = approval_fields
            .as_ref()
            .map(|(_, approval_id, _)| approval_id.as_str())
            .unwrap_or("");
        let call_id_ref = approval_fields
            .as_ref()
            .map(|(_, _, call_id)| call_id.as_str())
            .unwrap_or("");
        let idempotency_key =
            crate::approval::IdempotencyRegistry::make_key(&crate::approval::LogicalCallIdentity {
                tool: tool.clone(),
                input_digest: digest,
                workspace: workspace_path.clone(),
                session: registry.session_id().to_owned(),
                approval_id: approval_id_ref.to_owned(),
                call_id: call_id_ref.to_owned(),
                risk_level,
                command_family,
            });
        let idempotency_receipt = registry
            .begin_idempotent_call(&idempotency_key)
            .map_err(|error| BridgeError::new(approval_error_code(&error), &error.to_string()))?;
        let grant: Option<ExecutionGrant> = match risk_level {
            RiskLevel::ReadOnly => None,
            RiskLevel::Guarded | RiskLevel::Dangerous => {
                let (token, approval_id, call_id) = approval_fields
                    .as_ref()
                    .expect("guarded risk requires prevalidated approval fields");
                match registry.execute_approved(
                    token,
                    &tool,
                    &digest,
                    &workspace_path,
                    approval_id,
                    call_id,
                    risk_level,
                    command_family,
                ) {
                    Ok(grant) if grant.is_expired() => {
                        registry.complete_idempotent_call(
                            idempotency_receipt,
                            IdempotencyOutcome::Failed,
                        );
                        return Err(BridgeError::new("grant_expired", "execution grant expired"));
                    }
                    Ok(grant) => Some(grant),
                    Err(error) => {
                        registry.complete_idempotent_call(
                            idempotency_receipt,
                            IdempotencyOutcome::Failed,
                        );
                        return Err(BridgeError::new(
                            approval_error_code(&error),
                            &error.to_string(),
                        ));
                    }
                }
            }
        };
        let session = registry.session_id().to_owned();
        (
            grant,
            session,
            workspace_path,
            workspace_digest,
            Some(idempotency_receipt),
        )
    };
    // Computer Use spawn-class actions (open_app/open_folder) execute in this
    // host process, OUTSIDE the sidecar's single-process containment job — the
    // sidecar job forbids any child spawn (WinError 1816). The grant consumed
    // above is re-verified inside the broker against the exact input bytes.
    // Hidden-desktop binding comes from the harness environment: when present,
    // every spawn is desktop-bound BEFORE process creation.
    if tool == "computer_use" {
        if let Some(action) = crate::cu_broker::broker_action(&input) {
            // Runtime telemetry is intentionally reduced to a fixed stage,
            // status and broker action. Never log raw tool input, grants,
            // tokens, request ids or digests at this boundary.
            crate::startup::record_runtime("broker_dispatch", "start", action);
            let hidden_desktop = std::env::var("LC_HIDDEN_DESKTOP_NAME")
                .ok()
                .map(|value| value.trim().to_owned())
                .filter(|value| !value.is_empty());
            let envelope = crate::cu_broker::execute_broker_action(
                action,
                &input,
                grant.as_ref(),
                request_id.as_deref(),
                action_id.as_deref(),
                Some(workspace_path.as_str()),
                hidden_desktop.as_deref(),
            );
            let outcome = envelope
                .get("status")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown");
            crate::startup::record_runtime("broker_dispatch", "return", outcome);
            if let Some(receipt) = idempotency_receipt {
                state
                    .registry
                    .lock()
                    .expect("approval registry poisoned")
                    .complete_idempotent_call(receipt, IdempotencyOutcome::Completed);
            }
            return Ok(envelope);
        }
    }
    let (method, payload) = match build_tool_call_request_with_correlation(
        &tool,
        &input,
        &workspace_path,
        &workspace_digest,
        &session,
        grant.as_ref(),
        request_id.as_deref(),
        action_id.as_deref(),
    ) {
        Ok(request) => request,
        Err(error) => {
            if let Some(receipt) = idempotency_receipt {
                state
                    .registry
                    .lock()
                    .expect("approval registry poisoned")
                    .complete_idempotent_call(receipt, IdempotencyOutcome::Failed);
            }
            return Err(error);
        }
    };
    let Some(bridge) = bridge else {
        if let Some(receipt) = idempotency_receipt {
            state
                .registry
                .lock()
                .expect("approval registry poisoned")
                .complete_idempotent_call(receipt, IdempotencyOutcome::Failed);
        }
        return Err(BridgeError::new(
            "bridge_unavailable",
            "sidecar bridge is required for non-broker tool execution",
        ));
    };
    let result = bridge.request(method, payload);
    if let Some(receipt) = idempotency_receipt {
        let outcome = if result.is_ok() {
            IdempotencyOutcome::Completed
        } else {
            IdempotencyOutcome::Failed
        };
        state
            .registry
            .lock()
            .expect("approval registry poisoned")
            .complete_idempotent_call(receipt, outcome);
    }
    result
}

/// Continuation observation for a broker-spawned launch. Observation-only:
/// never spawns, never consumes grants; identified purely by request_id and
/// bounded by the broker's continuation TTL.
#[tauri::command]
pub fn cu_broker_observe(request_id: String) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    if !crate::cu_broker::valid_request_id(&request_id) {
        return Err(BridgeError::new(
            "invalid_payload",
            "broker continuation request_id is invalid",
        ));
    }
    match crate::cu_broker::observe_broker_action(&request_id) {
        Some(envelope) => Ok(json!({ "found": true, "envelope": envelope })),
        None => Ok(json!({ "found": false })),
    }
}

// ---------------------------------------------------------------------------
// Broker-owned continuation grant commands (master prompt Part I). These are
// thin typed transports: all authority lives in the Rust continuation
// registry; the frontend can only carry opaque refs back and never mints,
// extends or reinterprets a grant.
// ---------------------------------------------------------------------------

fn continuation_session_workspace(
    state: &ApprovalState,
) -> Result<(String, String, String), BridgeError> {
    let registry = state
        .registry
        .lock()
        .map_err(|_| BridgeError::new("internal_error", "approval registry poisoned"))?;
    let workspace_guard = state
        .workspace
        .lock()
        .map_err(|_| BridgeError::new("internal_error", "workspace lock poisoned"))?;
    let identity = workspace_guard.as_ref().ok_or_else(|| {
        BridgeError::new(
            "no_workspace",
            "continuation requires a confirmed workspace",
        )
    })?;
    Ok((
        registry.session_id().to_owned(),
        identity.canonical_path.clone(),
        identity.digest.clone(),
    ))
}

#[allow(clippy::too_many_arguments)]
#[tauri::command]
pub fn cu_broker_continuation_consume(
    state: State<'_, ApprovalState>,
    grant_ref: String,
    task_id: String,
    step_id: String,
    request_id: String,
    action_kind: String,
    input: Value,
    expected_step_index: u16,
) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    let (session, _workspace_path, workspace_digest) = continuation_session_workspace(&state)?;
    // Authority recomputes the canonical digest from the exact input bytes;
    // a caller-supplied hex is never trusted (master prompt section 4.2).
    let input_digest = crate::approval::canonical_input_digest(&input);
    let hidden_desktop = std::env::var("LC_HIDDEN_DESKTOP_NAME")
        .ok()
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty());
    match crate::cu_continuation::consume_continuation_grant(
        &grant_ref,
        &task_id,
        &step_id,
        &request_id,
        &action_kind,
        &input_digest,
        &session,
        &workspace_digest,
        hidden_desktop.as_deref(),
        expected_step_index,
    ) {
        Ok(mut lease) => {
            // Echo the authoritative digest so evidence can correlate without
            // exposing any capability material.
            lease.canonical_input_digest_hex = crate::cu_broker::hex_digest(&input_digest);
            serde_json::to_value(lease)
                .map_err(|error| BridgeError::new("internal_error", &error.to_string()))
        }
        Err(code) => Err(BridgeError::new(code, code)),
    }
}

#[tauri::command]
pub fn cu_broker_continuation_complete(
    state: State<'_, ApprovalState>,
    lease_id: String,
    status: String,
    postcondition_verified: bool,
) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    let _session = continuation_session_workspace(&state)?;
    match crate::cu_continuation::complete_continuation_grant(
        &lease_id,
        &status,
        postcondition_verified,
    ) {
        Ok((completed_status, grant_state)) => Ok(json!({
            "schema_version": crate::cu_continuation::CONTINUATION_GRANT_SCHEMA,
            "status": completed_status,
            "grant_state": grant_state,
        })),
        Err(code) => Err(BridgeError::new(code, code)),
    }
}

#[tauri::command]
pub fn cu_broker_continuation_revoke(
    state: State<'_, ApprovalState>,
    grant_ref: String,
    reason: String,
) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    let _ = continuation_session_workspace(&state)?;
    if reason.trim().is_empty() {
        return Err(BridgeError::new(
            "invalid_payload",
            "revoke requires a non-empty reason",
        ));
    }
    match crate::cu_continuation::revoke_continuation_grants(&grant_ref) {
        Ok(revoked) => Ok(json!({ "revoked": revoked })),
        Err(code) => Err(BridgeError::new(code, code)),
    }
}

/// Confirm a workspace: validate the path, invalidate tokens bound to the
/// previous workspace, and store the new identity. Fails closed on invalid
/// paths or symlink/reparse escape.
#[tauri::command]
pub fn set_workspace(state: State<'_, ApprovalState>, path: String) -> Result<Value, BridgeError> {
    activation_gate(is_tool_execution_enabled())?;
    set_workspace_inner(&state, path)
}

fn set_workspace_inner(state: &ApprovalState, path: String) -> Result<Value, BridgeError> {
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
    // Re-bind isolated-test context to the concrete workspace digest so B1
    // workspace binding stays verifiable after the workspace becomes known.
    drop(registry);
    drop(workspace_guard);
    state.sync_isolated_workspace_digest(&identity.digest);
    // Re-acquire for response (already stored)
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
    fn p0_approval_correlation_rejects_malformed_model_request_id() {
        let error = validate_model_request_id(Some("not-a-turn".to_owned())).unwrap_err();
        assert_eq!(error.code, "invalid_correlation");
        assert!(validate_model_request_id(Some("0123456789abcdef01234567".to_owned())).is_ok());
        assert!(validate_model_request_id(None).unwrap().is_none());
    }

    #[test]
    fn p0_approval_correlation_rejects_unbounded_or_control_action_id() {
        let error = validate_model_action_id(Some("\u{0}".to_owned())).unwrap_err();
        assert_eq!(error.code, "invalid_correlation");
        assert!(validate_model_action_id(Some(TEST_CALL_ID.to_owned())).is_ok());
        assert!(validate_model_action_id(None).unwrap().is_none());
    }

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
        test_approval_state_with_prompt(ApprovalDecision::Approve)
    }

    fn test_approval_state_with_prompt(decision: ApprovalDecision) -> ApprovalState {
        ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(Some(WorkspaceIdentity {
                canonical_path: "C:\\test-workspace".to_string(),
                digest: "abcd1234".to_string(),
            })),
            permission_context: Mutex::new(None),
            permissions: Mutex::new(AgentPermissions {
                files: true,
                shell: true,
                tools: true,
                computer_use: true,
                internet: true,
            }),
            prompt: Arc::new(ScriptedApprovalPrompt { decision }),
            dispatcher: None,
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
            risk_level: effective_risk_level(tool, input).expect("known tool/action"),
            command_family: command_family_for_tool(tool).expect("known tool"),
            approval_id: approval_id.clone(),
            call_id: call_id.clone(),
        };
        registry
            .issue_with_token(token.clone(), scope)
            .expect("issue token");
        (token, approval_id, call_id)
    }

    #[test]
    fn browser_navigation_requires_explicit_consent() {
        let input = json!({
            "action": "open_url",
            "target": "browser",
            "url": "https://www.youtube.com/"
        });
        let (risk, category, destructive) =
            computer_use_risk_for_input(&input).expect("open_url is a registered action");
        assert_eq!(risk, RiskLevel::Dangerous);
        assert_eq!(category, "computer_use_browser_navigation");
        assert!(!destructive);
    }

    #[test]
    fn disabled_capabilities_reject_before_approval_issuance() {
        let state = ApprovalState::default();
        for (tool, input) in [
            ("files.read", json!({"path": "notes.txt"})),
            ("shell", json!({"command": "echo blocked"})),
            ("computer_use", json!({"action": "screenshot"})),
            ("web.fetch", json!({"url": "https://example.invalid"})),
            ("skills.invoke", json!({"skill": "example"})),
        ] {
            let error = request_approval_inner(&state, tool.to_string(), input)
                .expect_err("disabled capability must reject before issuing a token");
            assert_eq!(error.code, "permission_denied", "{tool}");
        }
    }

    #[test]
    fn permission_revocation_invalidates_pending_computer_use_grant() {
        let state = test_approval_state_with_workspace();
        let input = json!({"action": "screenshot"});
        let (token, approval_id, call_id) = issue_test_token(&state, "computer_use", &input);
        state.set_agent_permissions(disabled_agent_permissions());
        let error = execute_approved_inner(
            &state,
            token,
            "computer_use".to_string(),
            input,
            approval_id,
            call_id,
        )
        .expect_err("revoked Computer Use capability must reject before grant consumption");
        assert_eq!(error.code, "permission_denied");
    }

    // Frozen-contract: disabled activation surfaces feature_disabled via
    // the pure gate. No State, no bridge, no UB.

    #[test]
    fn p0b_run_tool_call_rejected_when_disabled() {
        let err = activation_gate(false).expect_err("must be rejected when disabled");
        assert_eq!(err.code, "feature_disabled");
    }

    #[test]
    fn p0b_set_workspace_rejected_when_disabled() {
        let err = activation_gate(false).expect_err("must be rejected when disabled");
        assert_eq!(err.code, "feature_disabled");
    }

    #[test]
    fn p0b_activation_gate_enabled_allows() {
        assert!(activation_gate(true).is_ok());
        assert!(activation_gate(is_tool_execution_enabled()).is_ok());
    }

    #[test]
    fn p0b_execute_approved_cannot_dispatch() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"path": "notes.txt"});
        let (token, approval_id, call_id) =
            issue_test_token(&approval_state, "files.write", &input);
        let result = execute_approved_inner(
            &approval_state,
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
    fn p0b_run_tool_call_broker_evidence_echoes_transport_ids_without_spawn() {
        let state = test_approval_state_with_workspace();
        let input = json!({
            "action": "open_app",
            "target": "definitely-not-allowlisted",
            "text": "raw arguments remain unchanged"
        });
        let (token, approval_id, call_id) = issue_test_token(&state, "computer_use", &input);
        let request_id = "0123456789abcdef01234567";
        let action_id = "call_0123456789abcdef0123456789abcdef";
        let expected_digest = canonical_input_digest(&input);
        let expected_digest_hex: String = expected_digest
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect();

        let result = run_tool_call_inner(
            &state,
            None,
            "computer_use".to_owned(),
            input,
            Some(token),
            Some(approval_id.clone()),
            Some(call_id.clone()),
            Some(request_id.to_owned()),
            Some(action_id.to_owned()),
        )
        .expect("invalid allowlist target returns a truthful broker envelope");

        assert_eq!(result["schema_version"], crate::cu_broker::ENVELOPE_SCHEMA);
        assert_eq!(result["status"], "blocked");
        assert_eq!(result["request_id"], request_id);
        assert_eq!(result["action_id"], action_id);
        assert_eq!(result["execution"]["approval_id"], approval_id);
        assert_eq!(result["execution"]["approval_call_id"], call_id);
        assert_eq!(result["execution"]["input_digest"], expected_digest_hex);
    }

    #[test]
    fn p0b_confirmed_boolean_does_not_authorize() {
        let input = json!({"path": "notes.txt", "confirmed": true});
        assert_eq!(
            risk_level_for_tool("files.write").unwrap(),
            RiskLevel::Guarded
        );
        assert!(canonical_input_digest(&input).iter().any(|byte| *byte != 0));

        let err = require_approval_fields(RiskLevel::Guarded, None, None, None)
            .expect_err("confirmed=true without a token must be rejected");
        assert_eq!(err.code, "approval_required");

        let err = require_approval_fields(
            RiskLevel::Guarded,
            Some("not-authoritative".into()),
            None,
            None,
        )
        .expect_err("token alone still requires bound identifiers");
        assert_eq!(err.code, "approval_required");
    }

    /// Dangerous tools (files.delete, shell, computer_use) were only covered
    /// indirectly: require_approval_fields grouped them with Guarded, and the
    /// execution path relies on `.expect(...)` for the prevalidated tuple.
    /// Dropping Dangerous out of that arm therefore turned an approval bypass
    /// into a panic instead of a test failure, which no test caught. Assert the
    /// contract directly for every Dangerous tool so a regression is a red test.
    #[test]
    fn dangerous_tools_cannot_execute_without_full_approval_material() {
        for tool in ["files.delete", "shell", "computer_use"] {
            assert_eq!(
                risk_level_for_tool(tool).unwrap(),
                RiskLevel::Dangerous,
                "{tool} must stay Dangerous"
            );
        }

        let err = require_approval_fields(RiskLevel::Dangerous, None, None, None)
            .expect_err("a dangerous tool must never run without a token");
        assert_eq!(err.code, "approval_required");

        let err =
            require_approval_fields(RiskLevel::Dangerous, Some("token-only".into()), None, None)
                .expect_err("token alone must not authorize a dangerous tool");
        assert_eq!(err.code, "approval_required");

        let err = require_approval_fields(
            RiskLevel::Dangerous,
            Some("token".into()),
            Some("approval-1".into()),
            None,
        )
        .expect_err("call_id is part of the binding, not optional");
        assert_eq!(err.code, "approval_required");

        // Complete material resolves, so the arm below can never hit `.expect`.
        let ok = require_approval_fields(
            RiskLevel::Dangerous,
            Some("token".into()),
            Some("approval-1".into()),
            Some("call-1".into()),
        )
        .expect("complete approval material must resolve");
        assert!(ok.is_some(), "Dangerous must carry approval material");

        // Read-only stays free of approval material, or every read would prompt.
        assert!(
            require_approval_fields(RiskLevel::ReadOnly, None, None, None)
                .expect("read-only needs no approval")
                .is_none()
        );
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
        let envelope = request_approval_inner(
            &approval_state,
            "files.write".into(),
            json!({"path": "notes.txt"}),
        )
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
    fn p0b_r5_request_approval_is_background_and_scoped() {
        let approval_state = ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(Some(WorkspaceIdentity {
                canonical_path: "C:\\test-workspace".to_string(),
                digest: "abcd1234".to_string(),
            })),
            permission_context: Mutex::new(None),
            permissions: Mutex::new(AgentPermissions {
                files: true,
                shell: true,
                tools: true,
                computer_use: true,
                internet: true,
            }),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Reject,
            }),
            dispatcher: None,
        };
        let input = json!({"path": "notes.txt"});
        let envelope = request_approval_inner(&approval_state, "files.write".into(), input.clone())
            .expect("background issuance must not depend on frontend prompt");
        assert_eq!(envelope.tool, "files.write");
        let grant = validate_approval_token(
            &approval_state,
            "files.write",
            &input,
            &envelope.token,
            &envelope.approval_id,
            &envelope.call_id,
        )
        .expect("background token still validates atomically");
        assert_eq!(grant.tool, "files.write");
    }

    /// Dangerous tools must not receive a token until the approval prompt
    /// returns an Approve decision. The scripted prompt plays the user.
    #[test]
    fn dangerous_tool_prompt_approval_issues_envelope() {
        let approval_state = test_approval_state_with_workspace();
        let envelope = request_approval_inner(
            &approval_state,
            "computer_use".into(),
            json!({"action": "click", "target": "Submit payment"}),
        )
        .expect("scripted approve issues a dangerous envelope");
        assert_eq!(envelope.tool, "computer_use");
        assert_eq!(envelope.risk_level, RiskLevel::Dangerous);
        assert_eq!(envelope.command_family, CommandFamily::ComputerUse);
    }

    #[test]
    fn dangerous_tool_prompt_rejection_denies_issuance() {
        let approval_state = test_approval_state_with_prompt(ApprovalDecision::Reject);
        let error = request_approval_inner(
            &approval_state,
            "computer_use".into(),
            json!({"action": "click", "target": "Submit payment"}),
        )
        .expect_err("prompt rejection must deny token issuance");
        assert_eq!(error.code, "approval_rejected");
        let error = request_approval_inner(
            &approval_state,
            "files.delete".into(),
            json!({"path": "notes.txt"}),
        )
        .expect_err("every dangerous tool must consult the prompt");
        assert_eq!(error.code, "approval_rejected");
    }

    /// Guarded tools stay on the background boundary even when the prompt
    /// would reject: their consent is the explicit user action that triggered
    /// the request (UI button for that exact operation).
    #[test]
    fn guarded_tool_ignores_prompt_and_issues_in_background() {
        let approval_state = test_approval_state_with_prompt(ApprovalDecision::Reject);
        let envelope = request_approval_inner(
            &approval_state,
            "files.write".into(),
            json!({"path": "notes.txt"}),
        )
        .expect("guarded issuance must not depend on the dangerous-tool prompt");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);
    }

    #[test]
    fn p0b_r4_non_workspace_operations_use_sentinel() {
        let approval_state = ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            permissions: Mutex::new(disabled_agent_permissions()),
            permission_context: Mutex::new(None),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Approve,
            }),
            dispatcher: None,
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
    fn p0b_import_custom_model_binds_sentinel_workspace() {
        let approval_state = ApprovalState {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
            permissions: Mutex::new(disabled_agent_permissions()),
            permission_context: Mutex::new(None),
            prompt: Arc::new(ScriptedApprovalPrompt {
                decision: ApprovalDecision::Approve,
            }),
            dispatcher: None,
        };
        let input = json!({"source_path": "model.gguf", "filename": "model.gguf"});

        let envelope = request_approval_inner(
            &approval_state,
            "import_custom_model".to_string(),
            input.clone(),
        )
        .expect("request_approval should succeed with no workspace");

        assert_eq!(envelope.tool, "import_custom_model");
        assert_eq!(envelope.command_family, CommandFamily::ArtifactDownload);
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);

        let grant = validate_approval_token(
            &approval_state,
            "import_custom_model",
            &input,
            &envelope.token,
            &envelope.approval_id,
            &envelope.call_id,
        )
        .expect("validate_approval_token should succeed");

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

    #[test]
    fn computer_use_risk_is_action_aware() {
        let cases = [
            (
                json!({"action": "open_app", "target": "notepad"}),
                RiskLevel::Guarded,
                "computer_use_application_launch",
                false,
            ),
            (
                json!({"action": "screenshot"}),
                RiskLevel::ReadOnly,
                "computer_use_observation",
                false,
            ),
            (
                json!({"action": "open_folder", "target": "C:\\\\Windows\\\\System32"}),
                RiskLevel::Dangerous,
                "computer_use_system_or_unallowlisted_path",
                true,
            ),
            (
                json!({"action": "click", "target": "Submit payment"}),
                RiskLevel::Dangerous,
                "computer_use_sensitive_or_external_effect",
                false,
            ),
            (
                json!({"action": "type", "text": "hello in Notepad"}),
                RiskLevel::Guarded,
                "computer_use_ui_interaction",
                false,
            ),
            (
                json!({"action": "type", "text": "delete password later"}),
                RiskLevel::Guarded,
                "computer_use_ui_interaction",
                false,
            ),
            (
                json!({"action": "type", "text": "secret", "field": "Password"}),
                RiskLevel::Dangerous,
                "computer_use_sensitive_or_external_effect",
                false,
            ),
            (
                json!({"action": "open_app", "target": "chrome", "url": "https://example.com"}),
                RiskLevel::Guarded,
                "computer_use_application_launch",
                false,
            ),
            (
                json!({"action": "task", "goal": "кликни кнопку и введи текст"}),
                RiskLevel::Guarded,
                "computer_use_ui_interaction",
                false,
            ),
        ];

        for (input, expected_risk, expected_category, expected_destructive) in cases {
            let (risk, category, destructive) =
                computer_use_risk_for_input(&input).expect("known Computer Use action");
            assert_eq!(risk, expected_risk, "input={input}");
            assert_eq!(category, expected_category, "input={input}");
            assert_eq!(destructive, expected_destructive, "input={input}");
        }
    }

    #[test]
    fn unallowlisted_computer_use_launch_is_blocked_before_prompt() {
        let approval_state = test_approval_state_with_prompt(ApprovalDecision::Approve);
        for target in ["cmd.exe", "C:\\Windows\\System32\\notepad.exe"] {
            let error = request_approval_inner(
                &approval_state,
                "computer_use".into(),
                json!({"action": "open_app", "target": target}),
            )
            .expect_err("broker must block unallowlisted launch before approval");
            assert_eq!(error.code, "computer_use_blocked", "target={target}");
        }
    }

    #[test]
    fn routine_computer_use_actions_skip_dangerous_prompt() {
        let approval_state = test_approval_state_with_prompt(ApprovalDecision::Reject);
        let envelope = request_approval_inner(
            &approval_state,
            "computer_use".into(),
            json!({"action": "open_app", "target": "notepad"}),
        )
        .expect("allowlisted app launch must not depend on dangerous prompt");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);

        let screenshot = request_approval_inner(
            &approval_state,
            "computer_use".into(),
            json!({"action": "screenshot"}),
        )
        .expect("screenshot must not depend on dangerous prompt");
        assert_eq!(screenshot.risk_level, RiskLevel::ReadOnly);
    }

    #[test]
    fn effective_computer_use_risk_is_used_for_execution() {
        let approval_state = test_approval_state_with_workspace();
        let input = json!({"action": "open_app", "target": "notepad"});
        let envelope =
            request_approval_inner(&approval_state, "computer_use".into(), input.clone())
                .expect("allowlisted app launch must issue a guarded envelope");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);
        let grant = execute_approved_inner(
            &approval_state,
            envelope.token,
            "computer_use".into(),
            input,
            envelope.approval_id,
            envelope.call_id,
        )
        .expect("guarded Computer Use envelope must validate with the same effective risk");
        assert_eq!(grant["tool"], "computer_use");

        let screenshot = json!({"action": "screenshot"});
        assert_eq!(
            effective_risk_level("computer_use", &screenshot).expect("known action"),
            RiskLevel::ReadOnly
        );
        let task = json!({"action": "task", "goal": "кликни кнопку и введи текст"});
        assert_eq!(
            effective_risk_level("computer_use", &task).expect("known composite action"),
            RiskLevel::Guarded
        );
        assert!(require_approval_fields(
            effective_risk_level("computer_use", &screenshot).expect("known action"),
            None,
            None,
            None,
        )
        .expect("read-only Computer Use needs no approval")
        .is_none());
    }

    #[test]
    fn computer_use_unknown_action_fails_closed() {
        let error = computer_use_risk_for_input(&json!({"action": "run_shell"}))
            .expect_err("unknown Computer Use action must be rejected");
        assert_eq!(error.code, "unsupported_action");
    }
}
