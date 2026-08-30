//! Typed Tauri transports over the checkpoint backend (Phase 3).
//! Authority stays in `checkpoint.rs`; these commands only re-validate
//! workspace ownership and marshal results for the timeline UI.

use crate::approval_commands::ApprovalState;
use crate::checkpoint::{self, CompareResult};
use crate::control_plane::BridgeError;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use tauri::State;

fn checkpoints_store_root(workspace_digest: &str) -> PathBuf {
    let base = std::env::var("LOCALAPPDATA")
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
    Path::new(&base)
        .join("LocalComet")
        .join("DevRuntime")
        .join("checkpoints")
        .join(workspace_digest)
}

fn workspace_digest_of(canonical_path: &str) -> String {
    let mut h = Sha256::new();
    h.update(canonical_path.as_bytes());
    format!("{:x}", h.finalize())
}

// Kept as the single derivation site for the storage layout contract; the
// manifest's own workspace_digest field is authoritative at read time.
#[allow(dead_code)]
fn _digest_contract_note() -> String {
    workspace_digest_of("canonical")
}

fn require_workspace(state: &ApprovalState) -> Result<(String, String), BridgeError> {
    state.workspace_identity().ok_or_else(|| {
        BridgeError::new(
            "no_workspace",
            "checkpoint operations require a confirmed workspace",
        )
    })
}

fn require_workspace_cmd(
    state: &State<'_, ApprovalState>,
) -> Result<(String, String), BridgeError> {
    require_workspace(state.inner())
}

/// Timeline source: every stored manifest for the confirmed workspace.
#[tauri::command]
pub fn checkpoint_list(state: State<'_, ApprovalState>) -> Result<Vec<Value>, BridgeError> {
    let (_canonical, digest) = require_workspace_cmd(&state)?;
    let manifests_dir = checkpoints_store_root(&digest).join("manifests");
    let mut items = Vec::new();
    let entries = std::fs::read_dir(&manifests_dir).map_err(|e| {
        BridgeError::new(
            "checkpoint_storage_unavailable",
            &format!("manifests directory unavailable: {e}"),
        )
    })?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let Ok(data) = std::fs::read(&path) else {
            continue;
        };
        let manifest: checkpoint::CheckpointManifest = match serde_json::from_slice(&data) {
            Ok(m) => m,
            Err(_) => continue, // interrupted write: skip, never crash timeline
        };
        // Workspace ownership check: a manifest from another workspace must
        // never surface here even if it landed in this directory.
        if manifest.workspace_digest != digest {
            continue;
        }
        items.push(json!({
            "checkpoint_id": manifest.checkpoint_id,
            "parent_checkpoint_id": manifest.parent_checkpoint_id,
            "patch_id": manifest.patch_id,
            "task_id": manifest.task_id,
            "step_id": manifest.step_id,
            "status": manifest.status,
            "trigger": manifest.trigger,
            "paths": manifest.paths,
            "operations": manifest.operations,
            "before_sha256": manifest.before_sha256,
            "after_sha256": manifest.after_sha256,
            "ownership": manifest.ownership,
        }));
    }
    Ok(items)
}

fn load_manifest_at(
    store_root: &Path,
    digest: &str,
    checkpoint_id: &str,
) -> Result<checkpoint::CheckpointManifest, BridgeError> {
    if !valid_checkpoint_id(checkpoint_id) {
        return Err(BridgeError::new(
            "invalid_payload",
            "checkpoint id is invalid",
        ));
    }
    let path = store_root
        .join("manifests")
        .join(format!("{checkpoint_id}.json"));
    let data = std::fs::read(&path)
        .map_err(|_| BridgeError::new("checkpoint_not_found", "checkpoint manifest not found"))?;
    let manifest: checkpoint::CheckpointManifest = serde_json::from_slice(&data)
        .map_err(|_| BridgeError::new("invalid_payload", "checkpoint manifest is malformed"))?;
    if manifest.workspace_digest != digest {
        return Err(BridgeError::new(
            "checkpoint_workspace_mismatch",
            "checkpoint belongs to a different workspace",
        ));
    }
    Ok(manifest)
}

fn load_manifest(
    digest: &str,
    checkpoint_id: &str,
) -> Result<checkpoint::CheckpointManifest, BridgeError> {
    load_manifest_at(&checkpoints_store_root(digest), digest, checkpoint_id)
}

/// `compare_only`: never mutates; reports per-path drift vs postimage.
#[tauri::command]
pub fn checkpoint_compare(
    state: State<'_, ApprovalState>,
    checkpoint_id: String,
) -> Result<Value, BridgeError> {
    let (canonical, digest) = require_workspace(&state)?;
    let manifest = load_manifest(&digest, &checkpoint_id)?;
    let results = checkpoint::compare_only(Path::new(&canonical), &manifest);
    let map: serde_json::Map<String, Value> = results
        .iter()
        .map(|(path, result)| {
            let value = match result {
                CompareResult::Identical => json!("identical"),
                CompareResult::Modified { current_sha256 } => {
                    json!({ "modified": true, "current_sha256": current_sha256 })
                }
                CompareResult::Missing => json!("missing"),
            };
            (path.clone(), value)
        })
        .collect();
    Ok(json!({ "checkpoint_id": checkpoint_id, "compare": Value::Object(map) }))
}

/// `restore_files`: guarded mutating operation. Requires a one-time scoped
/// grant minted by `checkpoint_restore_approval`; the backend rebuilds the
/// canonical approval input itself (confirmed workspace digest, authoritative
/// session id, canonical ordered checkpoint ids, current manifest digests,
/// operation kind) and consumes the token atomically BEFORE any file changes.
#[tauri::command]
pub fn checkpoint_restore_files(
    state: State<'_, ApprovalState>,
    checkpoint_id: String,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError> {
    let plan = resolve_restore_plan(state.inner(), "restore_files", &[checkpoint_id])?;
    consume_restore_grant(state.inner(), &plan, &token, &approval_id, &call_id)?;
    execute_restore_plan(state.inner(), &plan)
}

/// `restore_task`: unwind every checkpoint of one task, newest→oldest input
/// order enforced by the store's chronological index (never caller order).
/// Same conflict rule per checkpoint; the error names the offending one.
/// Guarded mutating operation: same one-time grant contract, bound to the
/// exact ordered checkpoint id set of ONE task.
#[tauri::command]
pub fn checkpoint_restore_task(
    state: State<'_, ApprovalState>,
    checkpoint_ids: Vec<String>,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError> {
    let plan = resolve_restore_plan(state.inner(), "restore_task", &checkpoint_ids)?;
    consume_restore_grant(state.inner(), &plan, &token, &approval_id, &call_id)?;
    execute_restore_plan(state.inner(), &plan)
}

// ---------------------------------------------------------------------------
// Restore authorization (P0): every mutating restore goes through the Rust
// approval authority. The frontend may only ask FOR an envelope; it can never
// choose risk level, workspace digest or arbitrary descriptor fields.
// ---------------------------------------------------------------------------

/// Typed restore request carried to both issuance and consumption. The ids
/// themselves are normalized server-side before entering the approval input.
#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckpointRestoreApprovalRequest {
    /// "restore_files" | "restore_task"
    pub operation: String,
    pub checkpoint_ids: Vec<String>,
}

const RESTORE_FILES_TOOL: &str = "checkpoint.restore_files";
const RESTORE_TASK_TOOL: &str = "checkpoint.restore_task";

fn tool_for_operation(operation: &str) -> Result<&'static str, BridgeError> {
    match operation {
        "restore_files" => Ok(RESTORE_FILES_TOOL),
        "restore_task" => Ok(RESTORE_TASK_TOOL),
        _ => Err(BridgeError::new(
            "invalid_payload",
            "restore operation must be restore_files or restore_task",
        )),
    }
}

fn valid_checkpoint_id(id: &str) -> bool {
    !id.is_empty() && id.len() <= 64 && id.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// Raw-bytes digest over the exact manifests being restored, in canonical
/// order. Binds the grant to the manifest content: any manifest change between
/// issuance and consumption invalidates the token.
fn manifests_digest(store_root: &Path, ordered_ids: &[String]) -> Result<String, BridgeError> {
    let mut hasher = Sha256::new();
    for id in ordered_ids {
        let path = store_root.join("manifests").join(format!("{id}.json"));
        let data = std::fs::read(&path).map_err(|_| {
            BridgeError::new("checkpoint_not_found", "checkpoint manifest not found")
        })?;
        hasher.update(data);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

/// Everything needed to authorize and run one restore operation.
#[derive(Debug)]
struct RestorePlan {
    tool: &'static str,
    /// Store the manifests/blobs live in; resolved once from the confirmed
    /// workspace identity so execution cannot drift to another store.
    store_root: PathBuf,
    ordered_manifests: Vec<checkpoint::CheckpointManifest>,
    /// Canonical approval input; rebuilt identically at consumption time.
    approval_input: Value,
}

/// Build the canonical ordered plan for a restore operation. Shared by
/// issuance and consumption so both sides see byte-identical JSON.
///
/// Canonical ordering authority is index.json (chronological append-on-create):
/// caller order is ignored, duplicates and unknown ids are rejected, and a
/// task-level set spanning multiple tasks fails closed.
fn resolve_restore_plan(
    state: &ApprovalState,
    operation: &str,
    requested_ids: &[String],
) -> Result<RestorePlan, BridgeError> {
    let (_canonical, digest) = require_workspace(state)?;
    let store_root = checkpoints_store_root(&digest);
    resolve_restore_plan_at(
        &store_root,
        &digest,
        &state.session_id(),
        operation,
        requested_ids,
    )
}

fn resolve_restore_plan_at(
    store_root: &Path,
    workspace_digest: &str,
    session_id: &str,
    operation: &str,
    requested_ids: &[String],
) -> Result<RestorePlan, BridgeError> {
    let tool = tool_for_operation(operation)?;
    if requested_ids.is_empty() {
        return Err(BridgeError::new(
            "invalid_payload",
            "restore requires at least one checkpoint id",
        ));
    }
    let mut seen = std::collections::HashSet::new();
    for id in requested_ids {
        if !valid_checkpoint_id(id) {
            return Err(BridgeError::new(
                "invalid_payload",
                "checkpoint id is invalid",
            ));
        }
        if !seen.insert(id.as_str()) {
            return Err(BridgeError::new(
                "invalid_payload",
                "duplicate checkpoint ids are not allowed",
            ));
        }
    }
    if operation == "restore_files" && requested_ids.len() != 1 {
        return Err(BridgeError::new(
            "invalid_payload",
            "restore_files requires exactly one checkpoint id",
        ));
    }
    // Chronological authority is index.json (append-on-create), NOT the
    // caller's ordering.
    let index_path = store_root.join("index.json");
    let index: Vec<String> = std::fs::read(&index_path)
        .map(|data| serde_json::from_slice(&data).unwrap_or_default())
        .unwrap_or_default();
    let mut ordered: Vec<checkpoint::CheckpointManifest> = Vec::with_capacity(requested_ids.len());
    for id in &index {
        if requested_ids.iter().any(|req| req == id) {
            ordered.push(load_manifest_at(store_root, workspace_digest, id)?);
        }
    }
    if ordered.len() != requested_ids.len() {
        return Err(BridgeError::new(
            "checkpoint_not_found",
            "one or more requested checkpoints are missing from this workspace store",
        ));
    }
    let task_id = if operation == "restore_task" {
        let first = ordered[0].task_id.clone();
        for m in &ordered {
            if m.task_id != first {
                return Err(BridgeError::new(
                    "restore_task_mixed_tasks",
                    "a task restore must cover checkpoints of exactly one task",
                ));
            }
        }
        Some(first)
    } else {
        None
    };
    let manifests_sha256 = manifests_digest(store_root, &index_order(&ordered))?;
    let approval_input = restore_approval_input(
        workspace_digest,
        session_id,
        tool,
        &index_order(&ordered),
        task_id.as_deref(),
        &manifests_sha256,
    );
    let _ = task_id; // bound inside approval_input
    Ok(RestorePlan {
        tool,
        store_root: store_root.to_path_buf(),
        ordered_manifests: ordered,
        approval_input,
    })
}

fn index_order(manifests: &[checkpoint::CheckpointManifest]) -> Vec<String> {
    manifests.iter().map(|m| m.checkpoint_id.clone()).collect()
}

/// The single derivation site for the restore approval payload. Changing this
/// JSON shape invalidates every outstanding restore token — intended.
fn restore_approval_input(
    workspace_digest: &str,
    session_id: &str,
    tool: &str,
    ordered_checkpoint_ids: &[String],
    task_id: Option<&str>,
    manifests_sha256: &str,
) -> Value {
    json!({
        "kind": "checkpoint_restore",
        "operation": tool.strip_prefix("checkpoint.").unwrap_or(tool),
        "workspace_digest": workspace_digest,
        "session_id": session_id,
        "checkpoint_ids": ordered_checkpoint_ids,
        "task_id": task_id,
        "manifests_sha256": manifests_sha256,
    })
}

/// Mint the one-time scoped approval envelope for one exact restore set.
/// Production path: frontend confirm button → typed request → Rust validates
/// shape + confirmed workspace + single-task scope → guarded envelope bound
/// to checkpoint.restore_* × input-digest × workspace × session.
#[tauri::command]
pub fn checkpoint_restore_approval(
    state: State<'_, ApprovalState>,
    request: CheckpointRestoreApprovalRequest,
) -> Result<crate::approval::ApprovalEnvelope, BridgeError> {
    let plan = resolve_restore_plan(state.inner(), &request.operation, &request.checkpoint_ids)?;
    crate::approval_commands::issue_guarded_approval_for_input(
        state.inner(),
        plan.tool,
        &plan.approval_input,
    )
}

/// Atomically validate and consume the one-time grant BEFORE any mutation.
/// Replay, wrong workspace/session, reordered/substituted ids, tampered
/// manifests and expired tokens are all rejected here without touching files.
fn consume_restore_grant(
    state: &ApprovalState,
    plan: &RestorePlan,
    token: &str,
    approval_id: &str,
    call_id: &str,
) -> Result<(), BridgeError> {
    if token.is_empty() || approval_id.is_empty() || call_id.is_empty() {
        return Err(BridgeError::new(
            "approval_required",
            "restore requires a one-time approval grant",
        ));
    }
    crate::approval_commands::validate_approval_token(
        state,
        plan.tool,
        &plan.approval_input,
        token,
        approval_id,
        call_id,
    )?;
    Ok(())
}

fn execute_restore_plan(state: &ApprovalState, plan: &RestorePlan) -> Result<Value, BridgeError> {
    let (canonical, digest) = require_workspace(state)?;
    let store_root = plan.store_root.clone();
    if plan.tool == RESTORE_TASK_TOOL {
        match checkpoint::restore_task(&store_root, Path::new(&canonical), &plan.ordered_manifests)
        {
            Ok((task, restored)) => Ok(json!({
                "task_id": task,
                "restored": restored,
                "checkpoints": plan.ordered_manifests.len(),
                "status": "restored_task",
                "workspace_digest": digest,
                "approval_consumed": true,
            })),
            Err(reason) if reason.starts_with("restore_conflict@") => {
                Err(BridgeError::new("restore_conflict", &reason))
            }
            Err(reason) => Err(BridgeError::new("restore_failed", &reason)),
        }
    } else {
        let manifest = plan.ordered_manifests.first().ok_or_else(|| {
            BridgeError::new("invalid_payload", "file restore requires a checkpoint")
        })?;
        let checkpoint_id = manifest.checkpoint_id.clone();
        match checkpoint::restore_files(&store_root, Path::new(&canonical), manifest) {
            Ok(restored) => Ok(json!({
                "checkpoint_id": checkpoint_id,
                "restored": restored,
                "status": "restored",
                "workspace_digest": digest,
                "approval_consumed": true,
            })),
            Err(reason) if reason == "restore_conflict" => Err(BridgeError::new(
                "restore_conflict",
                "user or foreign changes detected; nothing was touched",
            )),
            Err(reason) => Err(BridgeError::new("restore_failed", &reason)),
        }
    }
}

// --- Rust tests: restore authorization seam (P0) ---
#[cfg(test)]
mod restore_approval_tests {
    use super::*;
    use crate::approval::ApprovalEnvelope;
    use crate::approval_commands::issue_guarded_approval_for_input;
    use crate::checkpoint::{FileOp, Patch};
    use crate::control_plane::AgentPermissions;
    use crate::workspace::WorkspaceIdentity;
    use std::collections::HashMap;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn sha_hex(data: &[u8]) -> String {
        let mut h = Sha256::new();
        h.update(data);
        format!("{:x}", h.finalize())
    }

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

    struct Fixture {
        ws: PathBuf,
        store: PathBuf,
        state: ApprovalState,
        digest: String,
        m1: checkpoint::CheckpointManifest,
        m2: checkpoint::CheckpointManifest,
        other_task: checkpoint::CheckpointManifest,
    }

    /// Isolated fixture workspace + external checkpoint store. The workspace
    /// digest mirrors apply_patch's own derivation (sha256 of the canonical
    /// path string) so manifests and the confirmed identity agree.
    ///
    /// Layout: calc.rs v0→v1 (task_r/m1), notes.txt n0→n1 (task_r/m2),
    /// third.txt t0→tx (task_other). Final disk state: v1/n1/tx, so every
    /// checkpoint's postimage matches the current bytes (restore-eligible).
    fn fixture(name: &str) -> Fixture {
        let ws = tmp(name);
        let store = tmp(&format!("{name}_store"));
        std::fs::write(ws.join("calc.rs"), b"v0").unwrap();
        std::fs::write(ws.join("notes.txt"), b"n0").unwrap();
        std::fs::write(ws.join("third.txt"), b"t0").unwrap();
        let base = HashMap::from([("calc.rs".to_string(), sha_hex(b"v0"))]);
        let m1 = checkpoint::apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "p1".into(),
                ops: vec![FileOp {
                    path: "calc.rs".into(),
                    content: Some(b"v1".to_vec()),
                }],
            },
            &base,
            "task_r",
            "s1",
        )
        .unwrap();
        let base2 = HashMap::from([("notes.txt".to_string(), sha_hex(b"n0"))]);
        let m2 = checkpoint::apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "p2".into(),
                ops: vec![FileOp {
                    path: "notes.txt".into(),
                    content: Some(b"n1".to_vec()),
                }],
            },
            &base2,
            "task_r",
            "s2",
        )
        .unwrap();
        let base3 = HashMap::from([("third.txt".to_string(), sha_hex(b"t0"))]);
        let other_task = checkpoint::apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "p3".into(),
                ops: vec![FileOp {
                    path: "third.txt".into(),
                    content: Some(b"tx".to_vec()),
                }],
            },
            &base3,
            "task_other",
            "s1",
        )
        .unwrap();
        let digest = sha_hex(ws.to_string_lossy().as_bytes());
        let state = ApprovalState::default();
        state.set_agent_permissions(AgentPermissions {
            files: true,
            shell: false,
            tools: false,
            computer_use: false,
            internet: false,
        });
        state.set_workspace(WorkspaceIdentity {
            canonical_path: ws.to_string_lossy().to_string(),
            digest: digest.clone(),
        });
        Fixture {
            ws,
            store,
            state,
            digest,
            m1,
            m2,
            other_task,
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.ws);
            let _ = std::fs::remove_dir_all(&self.store);
        }
    }

    fn mint(f: &Fixture, op: &str, ids: &[String]) -> (RestorePlan, ApprovalEnvelope) {
        let plan = resolve_restore_plan_at(&f.store, &f.digest, &f.state.session_id(), op, ids)
            .expect("resolve plan");
        let envelope = issue_guarded_approval_for_input(&f.state, plan.tool, &plan.approval_input)
            .expect("mint envelope");
        (plan, envelope)
    }

    #[test]
    fn restore_without_grant_is_blocked_before_disk_io() {
        let f = fixture("cra_no_grant");
        let plan = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_files",
            std::slice::from_ref(&f.m1.checkpoint_id),
        )
        .expect("plan");
        let err = consume_restore_grant(&f.state, &plan, "", "", "").unwrap_err();
        assert_eq!(err.code, "approval_required");
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
    }

    #[test]
    fn grant_for_another_checkpoint_is_rejected() {
        let f = fixture("cra_other_cp");
        // Envelope minted for m2 only.
        let (_m2_plan, env) = mint(
            &f,
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        );
        // Consumption attempt for m1: canonical input differs -> typed denial.
        let plan = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_files",
            std::slice::from_ref(&f.m1.checkpoint_id),
        )
        .expect("plan");
        let err =
            consume_restore_grant(&f.state, &plan, &env.token, &env.approval_id, &env.call_id)
                .unwrap_err();
        assert_eq!(err.code, "approval_arguments_mismatch");
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
    }

    #[test]
    fn replayed_grant_is_rejected_and_touches_nothing() {
        let f = fixture("cra_replay");
        let (plan, env) = mint(
            &f,
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        );
        consume_restore_grant(&f.state, &plan, &env.token, &env.approval_id, &env.call_id)
            .expect("first consumption");
        let out = execute_restore_plan(&f.state, &plan).expect("restore runs");
        assert_eq!(out["status"], json!("restored"));
        assert_eq!(std::fs::read(f.ws.join("notes.txt")).unwrap(), b"n0");
        // Untouched sibling keeps its checkpointed postimage.
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
        // Replay of the same one-time token: typed denial, no second mutation.
        let replay_plan = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        )
        .expect("replay plan");
        let err = consume_restore_grant(
            &f.state,
            &replay_plan,
            &env.token,
            &env.approval_id,
            &env.call_id,
        )
        .unwrap_err();
        assert_eq!(err.code, "approval_token_consumed");
        assert_eq!(std::fs::read(f.ws.join("notes.txt")).unwrap(), b"n0");
    }

    #[test]
    fn wrong_workspace_binding_is_rejected() {
        let f = fixture("cra_wrong_ws");
        let (_plan, env) = mint(
            &f,
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        );
        // A plan resolved against a DIFFERENT workspace digest must not accept
        // the token minted for the confirmed one.
        let other_digest = format!("other_{}", &f.digest[..12]);
        let plan = resolve_restore_plan_at(
            &f.store,
            &other_digest,
            &f.state.session_id(),
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        );
        // Manifest ownership check rejects the foreign digest outright.
        assert_eq!(plan.unwrap_err().code, "checkpoint_workspace_mismatch");
        // And even a forged matching-shape input fails at the registry because
        // the input digest differs from the approved scope.
        let forged_input = restore_approval_input(
            &other_digest,
            &f.state.session_id(),
            "checkpoint.restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
            None,
            "deadbeef",
        );
        let err = crate::approval_commands::validate_approval_token(
            &f.state,
            "checkpoint.restore_files",
            &forged_input,
            &env.token,
            &env.approval_id,
            &env.call_id,
        )
        .unwrap_err();
        assert_eq!(err.code, "approval_arguments_mismatch");
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
    }

    #[test]
    fn substituted_task_id_set_is_rejected() {
        let f = fixture("cra_sub_ids");
        // Grant minted for exactly [m1].
        let (_plan, env) = mint(
            &f,
            "restore_task",
            std::slice::from_ref(&f.m1.checkpoint_id),
        );
        // Consumption attempt with an enlarged/reordered set [m1, m2].
        let plan = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_task",
            &[f.m1.checkpoint_id.clone(), f.m2.checkpoint_id.clone()],
        )
        .expect("plan resolves; ordering authority is index.json");
        let err =
            consume_restore_grant(&f.state, &plan, &env.token, &env.approval_id, &env.call_id)
                .unwrap_err();
        assert_eq!(err.code, "approval_arguments_mismatch");
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
    }

    #[test]
    fn duplicate_and_mixed_task_sets_fail_closed() {
        let f = fixture("cra_dup_mixed");
        let dup = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_task",
            &[f.m1.checkpoint_id.clone(), f.m1.checkpoint_id.clone()],
        )
        .unwrap_err();
        assert_eq!(dup.code, "invalid_payload");

        let mixed = resolve_restore_plan_at(
            &f.store,
            &f.digest,
            &f.state.session_id(),
            "restore_task",
            &[
                f.m1.checkpoint_id.clone(),
                f.other_task.checkpoint_id.clone(),
            ],
        )
        .unwrap_err();
        assert_eq!(mixed.code, "restore_task_mixed_tasks");
    }

    #[test]
    fn conflict_with_valid_grant_leaves_user_bytes_intact() {
        let f = fixture("cra_conflict");
        let (plan, env) = mint(
            &f,
            "restore_files",
            std::slice::from_ref(&f.m2.checkpoint_id),
        );
        // The user edits AFTER the checkpoint was taken: their bytes win.
        std::fs::write(f.ws.join("notes.txt"), b"user-precious-edit").unwrap();
        consume_restore_grant(&f.state, &plan, &env.token, &env.approval_id, &env.call_id)
            .expect("grant itself is valid");
        let err = execute_restore_plan(&f.state, &plan).unwrap_err();
        assert_eq!(err.code, "restore_conflict");
        assert_eq!(
            std::fs::read(f.ws.join("notes.txt")).unwrap(),
            b"user-precious-edit"
        );
        // Sibling file untouched.
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v1");
    }

    #[test]
    fn task_restore_happy_path_unwinds_newest_first() {
        let f = fixture("cra_task_ok");
        let ids = vec![f.m1.checkpoint_id.clone(), f.m2.checkpoint_id.clone()];
        let (plan, env) = mint(&f, "restore_task", &ids);
        consume_restore_grant(&f.state, &plan, &env.token, &env.approval_id, &env.call_id)
            .expect("consume");
        let out = execute_restore_plan(&f.state, &plan).expect("task restore");
        assert_eq!(out["status"], json!("restored_task"));
        assert_eq!(out["task_id"], json!("task_r"));
        assert_eq!(out["checkpoints"], json!(2));
        // Both unwinds applied: back to the pre-task preimage.
        assert_eq!(std::fs::read(f.ws.join("calc.rs")).unwrap(), b"v0");
    }
}
