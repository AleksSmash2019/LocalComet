use crate::approval::{canonical_input_digest, ApprovalRegistry, ApprovalScope, RiskLevel};
use crate::control_plane::BridgeError;
use crate::workspace::WorkspaceIdentity;
use serde_json::{json, Value};
use std::sync::Mutex;
use tauri::State;

/// Managed approval state: the single Rust authority for issuing and consuming
/// scoped one-time approval tokens, plus the currently confirmed workspace.
pub struct ApprovalState {
    registry: Mutex<ApprovalRegistry>,
    workspace: Mutex<Option<WorkspaceIdentity>>,
}

impl Default for ApprovalState {
    fn default() -> Self {
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
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
fn risk_level_for_tool(tool: &str) -> RiskLevel {
    match tool {
        "files.delete" | "artifact.remove" => RiskLevel::Dangerous,
        "files.write"
        | "files.create_folder"
        | "artifact.download"
        | "runtime.start"
        | "runtime.stop"
        | "model.binding.set" => RiskLevel::Guarded,
        _ => RiskLevel::ReadOnly,
    }
}

/// Issue a scoped one-time approval token bound to (tool, input digest,
/// workspace, session). Fails closed if no workspace is confirmed.
#[tauri::command]
pub fn request_approval(
    state: State<'_, ApprovalState>,
    tool: String,
    input: Value,
) -> Result<String, BridgeError> {
    let risk_level = risk_level_for_tool(&tool);
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = workspace_guard.as_ref().ok_or_else(|| {
        BridgeError::new("no_workspace", "approval requires a confirmed workspace")
    })?;
    let scope = ApprovalScope {
        tool,
        input_digest: digest,
        workspace: workspace.canonical_path.clone(),
        session: registry.session_id().to_owned(),
        risk_level,
    };
    registry
        .issue(scope)
        .map_err(|error| BridgeError::new("approval_error", &error.to_string()))
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
) -> Result<Value, BridgeError> {
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = workspace_guard.as_ref().ok_or_else(|| {
        BridgeError::new("no_workspace", "approval requires a confirmed workspace")
    })?;
    let grant = registry
        .execute_approved(&token, &tool, &digest, &workspace.canonical_path)
        .map_err(|error| BridgeError::new("approval_denied", &error.to_string()))?;
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

/// Confirm a workspace: validate the path, invalidate tokens bound to the
/// previous workspace, and store the new identity. Fails closed on invalid
/// paths or symlink/reparse escape.
#[tauri::command]
pub fn set_workspace(state: State<'_, ApprovalState>, path: String) -> Result<Value, BridgeError> {
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
