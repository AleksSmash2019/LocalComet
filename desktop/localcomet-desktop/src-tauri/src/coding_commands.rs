//! Typed Tauri seam over the coding orchestrator (Phase 1 production wiring).
//!
//! Authority stays in Rust: the handler re-validates workspace containment,
//! permission-context validity and path policy, then drives the existing
//! orchestrator → checkpoint → terminal-runner → ledger chain. The frontend
//! never picks risk, never runs processes, never accepts Completed.

use crate::approval_commands::ApprovalState;
use crate::coding_orchestrator::{self};
use crate::task_ledger::{LedgerStore, TaskEvent, TaskState};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, VecDeque};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use tauri::State;

/// Hard size bound on one coding patch body (frontend-supplied newContent).
const MAX_PATCH_BYTES: usize = 512 * 1024;

/// Bounded task→roots registry. Replaces the former global LAST_TASK_ROOT:
/// every task owns its ledger/store roots and correlation never leaks
/// across tasks. Oldest entries are evicted beyond the cap.
const MAX_TRACKED_TASKS: usize = 64;
struct TaskRoots {
    ledger_root: PathBuf,
    store_root: PathBuf,
}

type TaskRegistry = (VecDeque<String>, HashMap<String, TaskRoots>);

fn task_registry() -> &'static Mutex<TaskRegistry> {
    static TASKS: OnceLock<Mutex<TaskRegistry>> = OnceLock::new();
    TASKS.get_or_init(|| Mutex::new((VecDeque::new(), HashMap::new())))
}

fn register_task_roots(task_id: &str, roots: TaskRoots) {
    let mut guard = task_registry().lock().expect("task registry poisoned");
    if guard.1.len() >= MAX_TRACKED_TASKS && !guard.1.contains_key(task_id) {
        if let Some(oldest) = guard.0.pop_front() {
            guard.1.remove(&oldest);
        }
    }
    if !guard.1.contains_key(task_id) {
        guard.0.push_back(task_id.to_string());
    }
    guard.1.insert(task_id.to_string(), roots);
}

fn lookup_task_roots(task_id: &str) -> Option<TaskRoots> {
    let guard = task_registry().lock().expect("task registry poisoned");
    guard.1.get(task_id).map(|r| TaskRoots {
        ledger_root: r.ledger_root.clone(),
        store_root: r.store_root.clone(),
    })
}

/// Per-task cancellation flags for bounded cancel semantics.
fn task_flags() -> &'static Mutex<HashMap<String, Arc<AtomicBool>>> {
    static FLAGS: OnceLock<Mutex<HashMap<String, Arc<AtomicBool>>>> = OnceLock::new();
    FLAGS.get_or_init(|| Mutex::new(HashMap::new()))
}

pub(crate) fn dev_tasks_root(workspace_digest: &str) -> PathBuf {
    let base = std::env::var("LOCALAPPDATA")
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
    Path::new(&base)
        .join("LocalComet")
        .join("DevRuntime")
        .join("tasks")
        .join(workspace_digest)
}

/// Validate a workspace directory without following reparse points.
fn validate_workspace(path: &str) -> Result<PathBuf, String> {
    let p = PathBuf::from(path);
    if !p.is_absolute() || !p.is_dir() {
        return Err("invalid_workspace".into());
    }
    if let Ok(md) = std::fs::symlink_metadata(&p) {
        if md.file_type().is_symlink() {
            return Err("workspace_reparse".into());
        }
    }
    Ok(p)
}

/// Compute base hashes for every touched op from CURRENT disk state so a
/// stale caller-side hash can never bypass conflict detection.
fn compute_base_hashes(
    workspace_root: &Path,
    ops: &[crate::checkpoint::FileOp],
) -> HashMap<String, String> {
    ops.iter()
        .map(|op| {
            let abs = workspace_root.join(&op.path);
            let hash = match std::fs::read(&abs) {
                Ok(bytes) => {
                    let mut h = Sha256::new();
                    h.update(&bytes);
                    format!("{:x}", h.finalize())
                }
                Err(_) => "missing".to_string(),
            };
            (op.path.clone(), hash)
        })
        .collect()
}

/// Typed request payload for `coding_start`.
#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CodingStartRequest {
    #[allow(dead_code)]
    pub session_id: String,
    pub workspace_path: String,
    pub rel_path: String,
    pub new_content: String,
    pub task_id: String,
    pub patch_id: String,
    pub step_id: String,
    /// One-time approval material minted by `coding_start_approval`.
    /// Required: without it the guarded mutation is rejected before any I/O.
    pub token: Option<String>,
    pub approval_id: Option<String>,
    pub call_id: Option<String>,
}

/// Typed descriptor for the coding patch the user is asked to approve.
/// The workspace digest is injected server-side from Rust-owned state —
/// the frontend cannot claim a workspace it was never confirmed.
#[derive(serde::Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CodingPatchDescriptor {
    pub rel_path: String,
    pub content_sha256: String,
    pub task_id: String,
    pub patch_id: String,
    pub step_id: String,
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn valid_task_shape(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 64
        && id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

fn valid_rel_path(rel: &str) -> Result<(), String> {
    if rel.is_empty()
        || rel.contains("..")
        || rel.starts_with('/')
        || rel.starts_with('\\')
        || rel.contains(':')
        || !rel.ends_with(".rs")
    {
        return Err("invalid_patch_path".into());
    }
    Ok(())
}

fn valid_sha256_field(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
}

impl CodingPatchDescriptor {
    fn validate(&self) -> Result<(), String> {
        valid_rel_path(&self.rel_path)?;
        for id in [&self.task_id, &self.patch_id, &self.step_id] {
            if !valid_task_shape(id) {
                return Err("invalid_task_id".into());
            }
        }
        if !valid_sha256_field(&self.content_sha256) {
            return Err("invalid_content_digest".into());
        }
        Ok(())
    }
}

/// Canonical approval input binding THIS exact patch to THIS confirmed
/// workspace. Issuance and consumption must build byte-identical JSON.
fn coding_approval_input(workspace_digest: &str, d: &CodingPatchDescriptor) -> Value {
    json!({
        "kind": "coding_patch",
        "workspace_digest": workspace_digest,
        "rel_path": d.rel_path,
        "content_sha256": d.content_sha256,
        "task_id": d.task_id,
        "patch_id": d.patch_id,
        "step_id": d.step_id,
    })
}

/// Persist the typed plan boundary before issuing the one-time grant. This is
/// the production restart seam: if the app dies while the grant is awaiting
/// the explicit coding start, a fresh process can surface the task for review
/// instead of silently losing the intent or resuming it.
#[cfg(not(test))]
fn persist_coding_approval_plan(
    workspace_digest: &str,
    descriptor: &CodingPatchDescriptor,
) -> Result<(), crate::control_plane::BridgeError> {
    let ledger_root = dev_tasks_root(workspace_digest);
    if crate::task_ledger::is_reparse_or_symlink(&ledger_root) {
        return Err(crate::control_plane::BridgeError::new(
            "task_ledger_reparse_point_rejected",
            "coding task ledger root is a reparse point",
        ));
    }
    let ledger = LedgerStore::new_with_root(ledger_root);
    if ledger.has_task(&descriptor.task_id) {
        return Err(crate::control_plane::BridgeError::new(
            "task_exists",
            "coding task already has a persisted ledger",
        ));
    }
    let first = ledger
        .append_event(TaskEvent {
            schema_version: crate::task_ledger::EVENT_SCHEMA.to_string(),
            seq: 1,
            event_id: format!("approval_plan_{}_1", descriptor.task_id),
            task_id: descriptor.task_id.clone(),
            task_version: 1,
            created_at_unix_ms: 0,
            event_type: "coding_approval_plan_compiled".to_string(),
            state_before: TaskState::Created,
            state_after: TaskState::IntentCompiled,
            step_id: Some(descriptor.step_id.clone()),
            checkpoint_id: None,
            request_id: None,
            action_id: None,
            correlation_id: Some(descriptor.patch_id.clone()),
            payload: json!({
                "workspace_digest": workspace_digest,
                "rel_path": descriptor.rel_path,
                "content_sha256": descriptor.content_sha256,
                "patch_id": descriptor.patch_id,
            }),
            prev_event_hash: "0".repeat(64),
            event_hash: String::new(),
        })
        .map_err(|error| {
            crate::control_plane::BridgeError::new(
                "task_ledger_unavailable",
                &format!("unable to persist coding approval plan: {error}"),
            )
        })?;
    ledger
        .append_event(TaskEvent {
            schema_version: crate::task_ledger::EVENT_SCHEMA.to_string(),
            seq: 2,
            event_id: format!("approval_plan_{}_2", descriptor.task_id),
            task_id: descriptor.task_id.clone(),
            task_version: 1,
            created_at_unix_ms: 0,
            event_type: "coding_approval_awaiting_explicit_start".to_string(),
            state_before: TaskState::IntentCompiled,
            state_after: TaskState::AwaitingApproval,
            step_id: Some(descriptor.step_id.clone()),
            checkpoint_id: None,
            request_id: None,
            action_id: None,
            correlation_id: Some(descriptor.patch_id.clone()),
            payload: json!({
                "workspace_digest": workspace_digest,
                "rel_path": descriptor.rel_path,
                "content_sha256": descriptor.content_sha256,
                "patch_id": descriptor.patch_id,
                "awaiting_explicit_start": true,
            }),
            prev_event_hash: first.event_hash,
            event_hash: String::new(),
        })
        .map_err(|error| {
            crate::control_plane::BridgeError::new(
                "task_ledger_unavailable",
                &format!("unable to persist coding approval boundary: {error}"),
            )
        })?;
    Ok(())
}

/// Mint the one-time scoped approval grant for one exact coding patch.
///
/// Production path (task P0): frontend coding task → typed descriptor →
/// Rust validates shape + confirmed workspace → scoped single-use envelope
/// bound to files.write × input-digest × workspace × session.
#[tauri::command(async)]
pub async fn coding_start_approval(
    state: State<'_, ApprovalState>,
    descriptor: CodingPatchDescriptor,
) -> Result<crate::approval::ApprovalEnvelope, String> {
    coding_start_approval_inner(&state, descriptor).map_err(|e| e.code.clone())
}

fn coding_start_approval_inner(
    state: &ApprovalState,
    descriptor: CodingPatchDescriptor,
) -> Result<crate::approval::ApprovalEnvelope, crate::control_plane::BridgeError> {
    descriptor
        .validate()
        .map_err(|code| crate::control_plane::BridgeError::new(&code, &code))?;
    let (_, ws_digest) = state.workspace_identity().ok_or_else(|| {
        crate::control_plane::BridgeError::new("no_workspace", "no confirmed workspace")
    })?;
    let input = coding_approval_input(&ws_digest, &descriptor);
    // The real app persists the approval boundary before issuing the grant.
    // Keep the lower-level unit-test helper free of app-data side effects; the
    // native restart harness exercises this production (non-test) path.
    #[cfg(not(test))]
    persist_coding_approval_plan(&ws_digest, &descriptor)?;
    crate::approval_commands::issue_guarded_approval_for_input(state, "files.write", &input)
}

/// Start one bounded coding task. Synchronous by design: the orchestrator is
/// bounded (timeout + output budgets inside the runner), so no orphan state.
///
/// Authorization chain (P0): context gate → confirmed-workspace/session
/// binding → strict shape validation → ONE-TIME scoped grant consumed
/// atomically BEFORE any filesystem mutation → orchestrator.
#[tauri::command]
pub fn coding_start(
    approval: State<'_, ApprovalState>,
    request: CodingStartRequest,
) -> Result<Value, String> {
    coding_start_inner(&approval, request)
}

fn coding_start_inner(
    approval: &ApprovalState,
    request: CodingStartRequest,
) -> Result<Value, String> {
    // F-03 full gate: session/workspace/desktop/capability/digest/expiry/mode.
    // coding_start is a guarded mutating operation (files.write) and never
    // trusts caller-supplied risk/capability. Context validity is necessary
    // but NOT sufficient — the one-time grant below authorizes THIS patch.
    approval
        .require_permission_context_for_tool("files.write")
        .map_err(|e| e.code.clone())?;

    // B2: caller-supplied workspace_path/session_id are untrusted. Use the
    // confirmed Rust workspace identity and validate caller values strictly.
    let (confirmed_canonical, confirmed_digest) = approval
        .workspace_identity()
        .ok_or_else(|| "no_workspace".to_string())?;
    let expected_session = approval.session_id();
    if !request.session_id.is_empty() && request.session_id != expected_session {
        return Err("session_mismatch".into());
    }
    let supplied_root = validate_workspace(&request.workspace_path)?;
    let confirmed_root = PathBuf::from(&confirmed_canonical);
    if supplied_root != confirmed_root {
        return Err("workspace_mismatch".into());
    }
    for id in [&request.task_id, &request.patch_id, &request.step_id] {
        if !valid_task_shape(id) {
            return Err("invalid_task_id".into());
        }
    }
    valid_rel_path(&request.rel_path)?;
    if request.new_content.len() > MAX_PATCH_BYTES {
        return Err("patch_too_large".into());
    }

    // One-time grant consumption — BEFORE any disk I/O. The descriptor is
    // rebuilt server-side from validated fields; a token minted for any
    // other patch/workspace/session fails here without touching the file.
    let (token, approval_id, call_id) =
        match (&request.token, &request.approval_id, &request.call_id) {
            (Some(t), Some(a), Some(c)) if !t.is_empty() => (t.clone(), a.clone(), c.clone()),
            _ => return Err("approval_required".into()),
        };
    let consume_input = coding_approval_input(
        &confirmed_digest,
        &CodingPatchDescriptor {
            rel_path: request.rel_path.clone(),
            content_sha256: sha256_hex(request.new_content.as_bytes()),
            task_id: request.task_id.clone(),
            patch_id: request.patch_id.clone(),
            step_id: request.step_id.clone(),
        },
    );
    let grant = crate::approval_commands::validate_approval_token(
        approval,
        "files.write",
        &consume_input,
        &token,
        &approval_id,
        &call_id,
    )
    .map_err(|e| e.code.clone())?;

    let workspace_root = confirmed_root;
    let ws_digest = confirmed_digest;
    let ledger_root = dev_tasks_root(&ws_digest);
    let store_root = store_root_for(&ws_digest);
    register_task_roots(
        &request.task_id,
        TaskRoots {
            ledger_root: ledger_root.clone(),
            store_root: store_root.clone(),
        },
    );

    let ops = vec![crate::checkpoint::FileOp {
        path: request.rel_path.clone(),
        content: Some(request.new_content.into_bytes()),
    }];
    let base_hashes = compute_base_hashes(&workspace_root, &ops);

    // Register cancellation flag BEFORE running so coding_cancel can race us.
    let flag = Arc::new(AtomicBool::new(false));
    task_flags()
        .lock()
        .expect("task flags poisoned")
        .insert(request.task_id.clone(), flag.clone());

    // Task-scoped doom-loop budget: failures of one task never exhaust or
    // reset another task's budget (per-task guard instance).
    //
    // PRODUCTION CALLER QUALIFICATION (deliberate Variant B — compile-only):
    // `require_focus_test = false` is an explicit, documented choice, not an
    // omission. Auto-creating a focus harness would mutate the user's
    // workspace OUTSIDE the approved patch scope, and executing any
    // workspace-matching binary on every task would widen the attack surface
    // (prompt injection -> planted harness -> arbitrary code execution).
    // Therefore the standard production flow can only ever claim
    // `compile_verified_only`; `behavior_verified` is reserved for the
    // opt-in/fixture path that passes `true` with a task-scoped harness
    // (see coding_orchestrator tests and the hidden E2E fixture). The
    // backend labels the outcome machine-readably via `verification_level`
    // and the UI renders it as visibly weaker than full success.
    let result = coding_orchestrator::run_coding_task(
        &store_root,
        &workspace_root,
        &ledger_root,
        &request.task_id,
        &request.patch_id,
        &request.step_id,
        &base_hashes,
        ops,
        &approval.permission_context_digest(),
        &|| flag.load(Ordering::Relaxed),
        &crate::terminal_runner::ExecutionGuard::new(),
        false, // PRODUCTION: compile-only by design; see block comment above.
    );

    task_flags()
        .lock()
        .expect("task flags poisoned")
        .remove(&request.task_id);

    let result = result?;
    // P1 truthfulness: the backend reports exactly how strongly the change
    // was verified. `compile_verified_only` is NOT success — the frontend
    // must render it as a visibly weaker outcome than behavior_verified.
    Ok(json!({
        "schema_version": coding_orchestrator::ORCHESTRATOR_SCHEMA,
        "task_id": request.task_id,
        "status": result.status,
        "verification_level": result.verification_level,
        "applied_paths": result.applied_paths,
        "error_diagnostics": result.error_diagnostics,
        "generation_hash": result.generation_hash,
        "test_exit_code": result.test_exit_code,
        "reason": result.reason,
        "events_task_id": request.task_id,
        "workspace_digest": ws_digest,
        "grant_id": grant.grant_id,
        "approval_consumed": true,
    }))
}

fn store_root_for(ws_digest: &str) -> PathBuf {
    let base = std::env::var("LOCALAPPDATA")
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
    Path::new(&base)
        .join("LocalComet")
        .join("DevRuntime")
        .join("checkpoints")
        .join(ws_digest)
}

fn event_json(event: &TaskEvent) -> Value {
    json!({
        "seq": event.seq,
        "event_type": event.event_type,
        "state_before": event.state_before.wire_name(),
        "state_after": event.state_after.wire_name(),
        "payload": event.payload,
        "event_hash": event.event_hash,
    })
}

fn recovery_status(state: &TaskState, event: &TaskEvent) -> (&'static str, &'static str) {
    match state {
        TaskState::Completed => match event
            .payload
            .get("verification_level")
            .and_then(|value| value.as_str())
        {
            Some("behavior_verified") => ("completed", "behavior_verified"),
            _ => ("compile_verified_only", "compile_verified_only"),
        },
        TaskState::Blocked => ("blocked", "none"),
        TaskState::Cancelled => ("cancelled", "none"),
        TaskState::Failed | TaskState::Expired => ("failed", "none"),
        // A restart never auto-resumes a mutating/non-terminal task. It is
        // surfaced for explicit review instead of replaying host actions.
        _ => ("paused_for_review", "none"),
    }
}

fn current_workspace_ledger(state: &ApprovalState, task_id: &str) -> Result<LedgerStore, String> {
    let (_, workspace_digest) = state
        .workspace_identity()
        .ok_or_else(|| "no_workspace".to_string())?;
    let ledger = LedgerStore::new_with_root(dev_tasks_root(&workspace_digest));
    if !ledger.has_task(task_id) {
        return Err("task_not_found".to_string());
    }
    Ok(ledger)
}

/// Bounded event poll: full verified chain for one task. Roots normally come
/// from the live task registry; after restart they are derived only from the
/// confirmed workspace identity, never from a caller-supplied filesystem path.
#[tauri::command]
pub fn coding_events(approval: State<'_, ApprovalState>, task_id: String) -> Result<Value, String> {
    if !valid_task_shape(&task_id) {
        return Err("invalid_task_id".to_string());
    }
    let ledger = if let Some(roots) = lookup_task_roots(&task_id) {
        let (_, workspace_digest) = approval
            .inner()
            .workspace_identity()
            .ok_or_else(|| "no_workspace".to_string())?;
        let expected_root = dev_tasks_root(&workspace_digest);
        if roots.ledger_root != expected_root {
            return Err("workspace_mismatch".to_string());
        }
        LedgerStore::new_with_root(roots.ledger_root)
    } else {
        current_workspace_ledger(approval.inner(), &task_id)?
    };
    let events = ledger.verify_chain(&task_id).map_err(|e| e.to_string())?;
    let events_json: Vec<Value> = events.iter().map(event_json).collect();
    Ok(json!({ "task_id": task_id, "events": events_json }))
}

/// List persisted task ledgers for the confirmed workspace. Corrupt ledgers
/// remain visible as `corrupt` rows instead of disappearing from recovery UI.
fn coding_list_tasks_inner(approval: &ApprovalState) -> Result<Value, String> {
    let (_, workspace_digest) = approval
        .workspace_identity()
        .ok_or_else(|| "no_workspace".to_string())?;
    let ledger_root = dev_tasks_root(&workspace_digest);
    let ledger_dir = ledger_root.join("ledger");
    if crate::task_ledger::is_reparse_or_symlink(&ledger_dir) {
        return Err("task_ledger_reparse_point_rejected".to_string());
    }
    let entries = match std::fs::read_dir(&ledger_dir) {
        Ok(entries) => entries,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(json!({ "workspace_digest": workspace_digest, "tasks": [] }));
        }
        Err(error) => return Err(format!("task_ledger_unavailable:{error}")),
    };
    let mut tasks = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|ext| ext.to_str()) != Some("ndjson") {
            continue;
        }
        let Some(task_id) = path.file_stem().and_then(|stem| stem.to_str()) else {
            continue;
        };
        if !valid_task_shape(task_id) {
            continue;
        }
        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        match ledger.verify_chain(task_id) {
            Ok(events) if events.is_empty() => tasks.push(json!({
                "task_id": task_id,
                "status": "corrupt",
                "reason": "task ledger has no complete events",
            })),
            Ok(events) => {
                let last = events.last().expect("non-empty events");
                let (status, verification_level) = recovery_status(&last.state_after, last);
                tasks.push(json!({
                    "task_id": task_id,
                    "status": status,
                    "verification_level": verification_level,
                    "state": last.state_after.wire_name(),
                    "last_seq": last.seq,
                    "terminal": last.state_after.is_terminal(),
                    "requires_review": !last.state_after.is_terminal(),
                    "reason": if last.state_after.is_terminal() { "persisted terminal result" } else { "restart requires explicit review; no automatic resume" },
                }));
            }
            Err(error) => tasks.push(json!({
                "task_id": task_id,
                "status": "corrupt",
                "reason": error,
            })),
        }
    }
    tasks.sort_by(|left, right| left["task_id"].as_str().cmp(&right["task_id"].as_str()));
    Ok(json!({ "workspace_digest": workspace_digest, "tasks": tasks }))
}

#[tauri::command]
pub fn coding_list_tasks(approval: State<'_, ApprovalState>) -> Result<Value, String> {
    coding_list_tasks_inner(approval.inner())
}

/// Recover one persisted task's verified event chain after a WebView/native
/// restart. This is read-only and deliberately refuses automatic continuation
/// of a task that may have pending host-side mutation.
fn coding_recover_task_inner(approval: &ApprovalState, task_id: String) -> Result<Value, String> {
    if !valid_task_shape(&task_id) {
        return Err("invalid_task_id".to_string());
    }
    let ledger = current_workspace_ledger(approval, &task_id)?;
    let events = ledger.verify_chain(&task_id).map_err(|e| e.to_string())?;
    let last = events
        .last()
        .ok_or_else(|| "task_ledger_empty".to_string())?;
    let (status, verification_level) = recovery_status(&last.state_after, last);
    Ok(json!({
        "task_id": task_id,
        "status": status,
        "verification_level": verification_level,
        "state": last.state_after.wire_name(),
        "terminal": last.state_after.is_terminal(),
        "requires_review": !last.state_after.is_terminal(),
        "reason": if last.state_after.is_terminal() { "persisted terminal result" } else { "restart requires explicit review; automatic resume is disabled" },
        "events": events.iter().map(event_json).collect::<Vec<_>>(),
    }))
}

#[tauri::command]
pub fn coding_recover_task(
    approval: State<'_, ApprovalState>,
    task_id: String,
) -> Result<Value, String> {
    coding_recover_task_inner(approval.inner(), task_id)
}

/// Bounded cancel: sets the flag consumed at the next runner poll tick.
#[tauri::command]
pub fn coding_cancel(task_id: String) -> Result<Value, String> {
    let flags = task_flags().lock().expect("task flags poisoned");
    match flags.get(&task_id) {
        Some(flag) => {
            flag.store(true, Ordering::Relaxed);
            Ok(json!({ "task_id": task_id, "cancel_requested": true }))
        }
        None => Ok(json!({
            "task_id": task_id,
            "cancel_requested": false,
            "reason": "task_not_running",
        })),
    }
}

// --- Rust tests (production seams, offline fixture workspaces) ---
#[cfg(test)]
mod tests {
    use super::*;
    use crate::control_plane::AgentPermissions;
    use crate::task_ledger::{TaskEvent, TaskState};
    use crate::terminal_runner::ExecutionGuard;
    use crate::workspace::WorkspaceIdentity;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp(prefix: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!(
            "{prefix}_{}_{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn rel_path_policy_rejects_escape_and_non_rs() {
        assert_eq!(valid_rel_path("../evil"), Err("invalid_patch_path".into()));
        assert_eq!(valid_rel_path("note.txt"), Err("invalid_patch_path".into()));
        assert_eq!(valid_rel_path("C:\\x.rs"), Err("invalid_patch_path".into()));
        assert_eq!(valid_rel_path("/abs.rs"), Err("invalid_patch_path".into()));
        assert!(valid_rel_path("src/lib.rs").is_ok());
    }

    #[test]
    fn cancel_unregistered_task_is_truthful() {
        let out = coding_cancel("never_started_cc".to_string()).unwrap();
        assert_eq!(out["cancel_requested"], json!(false));
        assert_eq!(out["reason"], json!("task_not_running"));
    }

    #[test]
    fn dev_tasks_root_is_under_devruntime() {
        let root = dev_tasks_root("abc");
        let s = root.to_string_lossy().to_lowercase();
        assert!(s.contains("localcomet") && s.contains("devruntime") && s.ends_with("abc"));
    }

    #[test]
    fn task_states_expose_terminal_flags() {
        assert!(TaskState::Completed.is_terminal());
        assert!(TaskState::Blocked.is_terminal());
        assert!(!TaskState::Running.is_terminal());
    }

    fn append_recovery_event(
        ledger: &LedgerStore,
        task_id: &str,
        seq: u64,
        previous_hash: &str,
        state_before: TaskState,
        state_after: TaskState,
        payload: Value,
    ) -> TaskEvent {
        ledger
            .append_event(TaskEvent {
                schema_version: crate::task_ledger::EVENT_SCHEMA.to_string(),
                seq,
                event_id: format!("recovery_evt_{task_id}_{seq}"),
                task_id: task_id.to_string(),
                task_version: 1,
                created_at_unix_ms: 0,
                event_type: "recovery.fixture".to_string(),
                state_before,
                state_after,
                step_id: Some("step_1".to_string()),
                checkpoint_id: Some("checkpoint_1".to_string()),
                request_id: Some("request_1".to_string()),
                action_id: Some("action_1".to_string()),
                correlation_id: Some("correlation_1".to_string()),
                payload,
                prev_event_hash: previous_hash.to_string(),
                event_hash: String::new(),
            })
            .expect("append recovery fixture event")
    }

    #[test]
    fn persisted_recovery_is_workspace_bound_and_never_auto_resumes() {
        let f = fixture("cc_recovery_direct");
        let (_, digest) = f.state.workspace_identity().expect("workspace identity");
        let ledger_root = dev_tasks_root(&digest);
        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let first = append_recovery_event(
            &ledger,
            "task_paused",
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
            json!({"verdict":"PENDING_TERMINAL"}),
        );
        append_recovery_event(
            &ledger,
            "task_paused",
            2,
            &first.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
            json!({"verdict":"PENDING_TERMINAL"}),
        );

        let listed = coding_list_tasks_inner(&f.state).expect("list persisted tasks");
        let paused = listed["tasks"]
            .as_array()
            .unwrap()
            .iter()
            .find(|task| task["task_id"] == json!("task_paused"))
            .expect("paused task listed");
        assert_eq!(paused["status"], json!("paused_for_review"));
        assert_eq!(paused["state"], json!("plan_ready"));
        assert_eq!(paused["terminal"], json!(false));
        assert_eq!(paused["requires_review"], json!(true));
        assert!(paused["reason"]
            .as_str()
            .unwrap()
            .contains("no automatic resume"));

        let recovered = coding_recover_task_inner(&f.state, "task_paused".to_string())
            .expect("recover persisted task");
        assert_eq!(recovered["status"], json!("paused_for_review"));
        assert_eq!(recovered["terminal"], json!(false));
        assert_eq!(recovered["requires_review"], json!(true));
        assert!(recovered["reason"]
            .as_str()
            .unwrap()
            .contains("automatic resume is disabled"));
        assert_eq!(recovered["events"].as_array().unwrap().len(), 2);
        assert_eq!(ledger.verify_chain("task_paused").unwrap().len(), 2);

        let other = fixture("cc_recovery_other_workspace");
        let err = coding_recover_task_inner(&other.state, "task_paused".to_string()).unwrap_err();
        assert_eq!(err, "task_not_found");

        let _ = std::fs::remove_dir_all(&f.ws);
        let _ = std::fs::remove_dir_all(&other.ws);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    #[test]
    fn persisted_recovery_reports_terminal_and_corrupt_rows_without_hiding_them() {
        let f = fixture("cc_recovery_terminal_corrupt");
        let (_, digest) = f.state.workspace_identity().expect("workspace identity");
        let ledger_root = dev_tasks_root(&digest);
        let ledger = LedgerStore::new_with_root(ledger_root.clone());
        let first = append_recovery_event(
            &ledger,
            "task_terminal",
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
            json!({"verification_level":"compile_verified_only"}),
        );
        append_recovery_event(
            &ledger,
            "task_terminal",
            2,
            &first.event_hash,
            TaskState::IntentCompiled,
            TaskState::Failed,
            json!({"verification_level":"none"}),
        );
        let corrupt_path = ledger_root.join("ledger").join("task_corrupt.ndjson");
        std::fs::create_dir_all(corrupt_path.parent().unwrap()).unwrap();
        // A malformed final line is intentionally treated as a crash-truncated
        // tail. Add later bytes so this fixture is interior corruption and
        // recovery must fail closed with the stronger ledger_corrupt verdict.
        std::fs::write(&corrupt_path, b"{not-json}\n{}\n").unwrap();

        let listed = coding_list_tasks_inner(&f.state).expect("list terminal and corrupt tasks");
        let tasks = listed["tasks"].as_array().unwrap();
        let terminal = tasks
            .iter()
            .find(|task| task["task_id"] == json!("task_terminal"))
            .expect("terminal task listed");
        assert_eq!(terminal["status"], json!("failed"));
        assert_eq!(terminal["terminal"], json!(true));
        assert_eq!(terminal["requires_review"], json!(false));
        let corrupt = tasks
            .iter()
            .find(|task| task["task_id"] == json!("task_corrupt"))
            .expect("corrupt task remains visible");
        assert_eq!(corrupt["status"], json!("corrupt"));

        let recovered = coding_recover_task_inner(&f.state, "task_terminal".to_string())
            .expect("recover terminal task");
        assert_eq!(recovered["status"], json!("failed"));
        assert_eq!(recovered["terminal"], json!(true));
        assert_eq!(recovered["requires_review"], json!(false));
        assert_eq!(recovered["events"].as_array().unwrap().len(), 2);
        assert_eq!(
            coding_recover_task_inner(&f.state, "task_corrupt".to_string()).unwrap_err(),
            "ledger_corrupt"
        );

        let _ = std::fs::remove_dir_all(&f.ws);
        let _ = std::fs::remove_dir_all(ledger_root);
    }

    // --- Grant boundary: production seam (issuance + consumption + disk) ---

    fn approval_state_for(ws: &Path) -> ApprovalState {
        let s = ApprovalState::default();
        s.set_agent_permissions(AgentPermissions {
            files: true,
            shell: false,
            tools: false,
            computer_use: false,
            internet: false,
        });
        s.set_workspace(WorkspaceIdentity {
            canonical_path: ws.to_string_lossy().to_string(),
            digest: format!(
                "digest_{}",
                &sha256_hex(ws.to_string_lossy().as_bytes())[..16]
            ),
        });
        s
    }

    struct Fixture {
        ws: PathBuf,
        state: ApprovalState,
        rel: String,
        content_a: String,
        content_b: String,
    }

    fn fixture(name: &str) -> Fixture {
        let ws = tmp(name);
        std::fs::write(
            ws.join("calc.rs"),
            "pub fn add(a: u32, b: u32) -> u32 { a }\n",
        )
        .unwrap();
        let state = approval_state_for(&ws);
        Fixture {
            ws,
            state,
            rel: "calc.rs".into(),
            content_a: "pub fn add(a: u32, b: u32) -> u32 { a + b }\n".into(),
            content_b: "pub fn add(a: u32, b: u32) -> u32 { a * 2 + b }\n".into(),
        }
    }

    fn start_request(f: &Fixture, content: &str) -> CodingStartRequest {
        CodingStartRequest {
            session_id: String::new(),
            workspace_path: f.ws.to_string_lossy().to_string(),
            rel_path: f.rel.clone(),
            new_content: content.to_string(),
            task_id: "task_grant".into(),
            patch_id: "patch_grant".into(),
            step_id: "step_1".into(),
            token: None,
            approval_id: None,
            call_id: None,
        }
    }

    fn mint(f: &Fixture, content_sha_hex: &str) -> crate::approval::ApprovalEnvelope {
        coding_start_approval_inner(
            &f.state,
            CodingPatchDescriptor {
                rel_path: f.rel.clone(),
                content_sha256: content_sha_hex.to_string(),
                task_id: "task_grant".into(),
                patch_id: "patch_grant".into(),
                step_id: "step_1".into(),
            },
        )
        .expect("mint envelope")
    }

    fn with_token(
        mut req: CodingStartRequest,
        env: &crate::approval::ApprovalEnvelope,
    ) -> CodingStartRequest {
        req.token = Some(env.token.clone());
        req.approval_id = Some(env.approval_id.clone());
        req.call_id = Some(env.call_id.clone());
        req
    }

    #[test]
    fn start_without_approval_is_rejected_before_disk_io() {
        let f = fixture("cc_no_grant");
        let before = std::fs::read(f.ws.join(&f.rel)).unwrap();
        let err = coding_start_inner(&f.state, start_request(&f, &f.content_a)).unwrap_err();
        assert_eq!(err, "approval_required");
        assert_eq!(
            std::fs::read(f.ws.join(&f.rel)).unwrap(),
            before,
            "file must be untouched when the grant is missing"
        );
        let _ = std::fs::remove_dir_all(&f.ws);
    }

    #[test]
    fn tampered_content_fails_digest_binding_without_disk_io() {
        let f = fixture("cc_tamper");
        let env = mint(&f, &sha256_hex(f.content_a.as_bytes()));
        // Consume-side content differs from the approved digest → deny.
        let req = with_token(start_request(&f, &f.content_b), &env);
        let before = std::fs::read(f.ws.join(&f.rel)).unwrap();
        let err = coding_start_inner(&f.state, req).unwrap_err();
        assert_eq!(err, "approval_arguments_mismatch");
        assert_eq!(std::fs::read(f.ws.join(&f.rel)).unwrap(), before);
        let _ = std::fs::remove_dir_all(&f.ws);
    }

    #[test]
    fn unknown_token_is_typed_denied_before_disk_io() {
        let f = fixture("cc_unknown_tok");
        let mut req = start_request(&f, &f.content_a);
        req.token = Some(format!("lcap_{}", "0".repeat(64)));
        req.approval_id = Some("apid_unknown".into());
        req.call_id = Some("cid_unknown".into());
        let before = std::fs::read(f.ws.join(&f.rel)).unwrap();
        // Registry validates approval identity fields first (fail-closed
        // ordering): garbage material yields the typed identity denial.
        let err = coding_start_inner(&f.state, req).unwrap_err();
        assert_eq!(err, "approval_identity_mismatch");
        assert_eq!(std::fs::read(f.ws.join(&f.rel)).unwrap(), before);
        let _ = std::fs::remove_dir_all(&f.ws);
    }

    #[test]
    fn wrong_workspace_after_issuance_is_denied() {
        let f = fixture("cc_ws_mismatch");
        let env = mint(&f, &sha256_hex(f.content_a.as_bytes()));
        // Re-point the confirmed workspace to another directory and address
        // THAT workspace in the request: the token stays bound to the
        // original workspace/digest and must fail closed at the registry.
        let other = tmp("cc_other_ws");
        f.state.set_workspace(WorkspaceIdentity {
            canonical_path: other.to_string_lossy().to_string(),
            digest: "other_digest".into(),
        });
        let mut req = start_request(&f, &f.content_a);
        req.workspace_path = other.to_string_lossy().to_string();
        let req = with_token(req, &env);
        let before = std::fs::read(f.ws.join(&f.rel)).unwrap();
        let err = coding_start_inner(&f.state, req).unwrap_err();
        assert!(
            matches!(
                err.as_str(),
                "approval_workspace_mismatch" | "approval_arguments_mismatch"
            ),
            "typed denial expected, got {err}"
        );
        assert_eq!(std::fs::read(f.ws.join(&f.rel)).unwrap(), before);
        let _ = std::fs::remove_dir_all(&f.ws);
        let _ = std::fs::remove_dir_all(other);
    }

    /// Full production chain on an isolated fixture workspace: grant minted
    /// for the exact bytes → orchestrator runs (real rustc via the runner) →
    /// file changed once → replay of the same one-time token is denied and
    /// does NOT touch the file again.
    #[test]
    fn grant_happy_path_runs_once_and_replay_is_denied() {
        let f = fixture("cc_full_flow");
        let env = mint(&f, &sha256_hex(f.content_a.as_bytes()));
        let req = with_token(start_request(&f, &f.content_a), &env);
        let result = coding_start_inner(&f.state, req).expect("full run");
        assert_eq!(result["status"], json!("compile_verified_only"));
        assert_eq!(result["verification_level"], json!("compile_verified_only"));
        assert_eq!(result["approval_consumed"], json!(true));
        let after_first = std::fs::read_to_string(f.ws.join(&f.rel)).unwrap();
        assert!(after_first.contains("a + b"));

        // Replay: same token must be consumed-once; no second write.
        let replay_req = with_token(start_request(&f, &f.content_a), &env);
        let err = coding_start_inner(&f.state, replay_req).unwrap_err();
        assert_eq!(err, "approval_token_consumed");
        assert_eq!(
            std::fs::read_to_string(f.ws.join(&f.rel)).unwrap(),
            after_first
        );

        // Task-scoped events remain retrievable through the registry. The
        // command itself is State-bound after restart support was added; this
        // unit seam verifies the same registry-selected ledger root.
        let roots = lookup_task_roots("task_grant").expect("task roots after completion");
        let events = LedgerStore::new_with_root(roots.ledger_root)
            .verify_chain("task_grant")
            .expect("events after completion");
        assert!(!events.is_empty());
        let _ = std::fs::remove_dir_all(&f.ws);
    }

    /// Real bounded user-flow integration: exercises the SAME code path as
    /// the Tauri `coding_start` command (minus the State wrapper) against a
    /// unique isolated project root with a real .rs file, real rustc through
    /// the terminal runner, a REAL executed focused test binary and a real
    /// ledger under DevRuntime-style root. Terminal outcome must be the
    /// strongest truthful one: behavior_verified with test exit code 0.
    #[test]
    fn coding_start_real_project_flow_completes() {
        let ws = tmp("coding_real_ws");
        // Unique per-run digest so the external ledger root never collides
        // with a previous integration run.
        let digest = format!(
            "integration-{}",
            &sha256_hex(ws.to_string_lossy().as_bytes())[..16]
        );
        // Pre-existing file so the patch is a real MODIFY with base hash.
        std::fs::write(
            ws.join("calc.rs"),
            "pub fn add(a: u32, b: u32) -> u32 { a }\n",
        )
        .unwrap();
        // Real focus harness: independent filesystem postcondition over the
        // patched file, compiled AND executed through the typed runner.
        std::fs::write(
            ws.join("__lc_focus_task_real_1.rs"),
            "fn main() {\n\
             \x20   let body = std::fs::read_to_string(\"calc.rs\").expect(\"patched file present\");\n\
             \x20   assert!(body.contains(\"a + b\"), \"postcondition content\");\n\
             }\n",
        )
        .unwrap();

        let new_content = "pub fn add(a: u32, b: u32) -> u32 { a + b }\n".to_string();
        let ops = vec![crate::checkpoint::FileOp {
            path: "calc.rs".into(),
            content: Some(new_content.clone().into_bytes()),
        }];
        let base_hashes = compute_base_hashes(&ws, &ops);
        assert_ne!(base_hashes["calc.rs"], "missing");

        let ledger_root = dev_tasks_root(&digest);
        let store_root = store_root_for(&digest);
        let guard = ExecutionGuard::new();
        let result = coding_orchestrator::run_coding_task(
            &store_root,
            &ws,
            &ledger_root,
            "task_real_1",
            "patch_real_1",
            "step_1",
            &base_hashes,
            ops,
            "",
            &|| false,
            &guard,
            true,
        )
        .expect("bounded run");

        // Independent filesystem postcondition: the file really changed.
        let on_disk = std::fs::read_to_string(ws.join("calc.rs")).unwrap();
        assert!(on_disk.contains("a + b"), "postcondition content");
        assert_eq!(
            result.status, "behavior_verified",
            "reason={}",
            result.reason
        );
        assert_eq!(result.verification_level, "behavior_verified");
        assert_eq!(result.test_exit_code, Some(0));
        assert_eq!(result.error_diagnostics, 0);

        // Ledger evidence: chain verifies, final state COMPLETED.
        let ledger = LedgerStore::new_with_root(ledger_root);
        let events = ledger.verify_chain("task_real_1").unwrap();
        assert_eq!(events.last().unwrap().state_after, TaskState::Completed);

        let _ = std::fs::remove_dir_all(ws);
    }

    /// Compile-only production slice: without a focus harness the task must
    /// terminate as compile_verified_only — machine-readably weaker than
    /// behavior_verified, with test_exit_code null and an honest reason.
    #[test]
    fn compile_only_run_is_visibly_weaker_than_behavior_verified() {
        let ws = tmp("coding_compile_only_ws");
        std::fs::write(
            ws.join("calc.rs"),
            "pub fn add(a: u32, b: u32) -> u32 { a }\n",
        )
        .unwrap();
        let new_content = "pub fn add(a: u32, b: u32) -> u32 { a + b }\n".to_string();
        let ops = vec![crate::checkpoint::FileOp {
            path: "calc.rs".into(),
            content: Some(new_content.into_bytes()),
        }];
        let base_hashes = compute_base_hashes(&ws, &ops);
        // Unique per-run digest: the external ledger root must never collide
        // with a previous integration run (seq_mismatch otherwise).
        let digest = format!(
            "compile-only-{}",
            &sha256_hex(ws.to_string_lossy().as_bytes())[..16]
        );
        let ledger_root = dev_tasks_root(&digest);
        let store_root = store_root_for(&digest);
        let guard = ExecutionGuard::new();
        let result = coding_orchestrator::run_coding_task(
            &store_root,
            &ws,
            &ledger_root,
            "task_compile_only",
            "patch_co",
            "step_1",
            &base_hashes,
            ops,
            "",
            &|| false,
            &guard,
            false,
        )
        .expect("bounded run");
        assert_eq!(result.status, "compile_verified_only");
        assert_eq!(result.verification_level, "compile_verified_only");
        assert_eq!(result.test_exit_code, None);
        assert!(
            result.reason.contains("NOT verified"),
            "reason must say behavior was not verified: {}",
            result.reason
        );

        let _ = std::fs::remove_dir_all(ws);
    }
}
