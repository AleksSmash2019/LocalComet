//! Patch/Checkpoint MVP — DevRuntime external storage, touched-files-only blobs.
//! Authority: Rust, workspace-relative canonical paths, SHA-256 blobs, atomic manifests.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

pub const SCHEMA_VERSION: &str = "checkpoint.manifest.v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CheckpointManifest {
    pub schema_version: String,
    pub checkpoint_id: String,
    pub parent_checkpoint_id: Option<String>,
    pub patch_id: String,
    pub task_id: String,
    pub step_id: String,
    pub workspace_digest: String,
    pub base_workspace_state_digest: String,
    pub trigger: String,
    pub paths: Vec<String>,
    pub operations: Vec<String>,
    pub before_sha256: HashMap<String, String>,
    pub after_sha256: HashMap<String, String>,
    pub before_blob_refs: HashMap<String, String>,
    pub after_blob_refs: HashMap<String, String>,
    pub ownership: String,
    pub evidence_refs: Vec<String>,
    pub status: String,
}

#[derive(Clone, Debug)]
pub struct FileOp {
    pub path: String,
    pub content: Option<Vec<u8>>, // None = delete
}

#[derive(Clone, Debug)]
pub struct Patch {
    pub patch_id: String,
    pub ops: Vec<FileOp>,
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn sha256_file(path: &Path) -> std::io::Result<String> {
    let data = fs::read(path)?;
    Ok(sha256_hex(&data))
}

fn is_reparse_or_symlink(p: &Path) -> bool {
    if let Ok(md) = fs::symlink_metadata(p) {
        md.file_type().is_symlink()
    } else {
        false
    }
}

fn canonical_relative(workspace_root: &Path, rel: &str) -> Result<PathBuf, String> {
    if rel.is_empty() || rel.len() > 240 {
        return Err("path length".into());
    }
    if rel.contains('\0') {
        return Err("null byte".into());
    }
    // forbid absolute, traversal, encoded traversal, separators that escape
    let lower = rel.to_ascii_lowercase();
    if lower.contains("..") || lower.contains("%2e") || lower.contains("%252e") {
        return Err("traversal".into());
    }
    if rel.contains(':') || rel.starts_with('/') || rel.starts_with('\\') {
        return Err("absolute".into());
    }
    let p = Path::new(rel);
    if p.is_absolute() {
        return Err("absolute".into());
    }
    for comp in p.components() {
        match comp {
            std::path::Component::ParentDir => return Err("parent".into()),
            std::path::Component::RootDir | std::path::Component::Prefix(_) => {
                return Err("prefix".into())
            }
            _ => {}
        }
    }
    let abs = workspace_root.join(rel);
    // reparse/symlink check on any prefix
    let mut cur = workspace_root.to_path_buf();
    for part in p.iter() {
        cur = cur.join(part);
        if is_reparse_or_symlink(&cur) {
            return Err("reparse".into());
        }
    }
    // also check final target if exists and is symlink
    if abs.exists() && is_reparse_or_symlink(&abs) {
        return Err("reparse target".into());
    }
    Ok(abs)
}

fn check_case_collision(paths: &[String]) -> Result<(), String> {
    let mut seen = HashSet::new();
    for p in paths {
        let lower = p.to_ascii_lowercase();
        if !seen.insert(lower) {
            return Err("case collision".into());
        }
    }
    Ok(())
}

fn checkpoints_root(workspace_digest: &str) -> PathBuf {
    let base = std::env::var("LOCALAPPDATA")
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
    Path::new(&base)
        .join("LocalComet")
        .join("DevRuntime")
        .join("checkpoints")
        .join(workspace_digest)
}

fn blobs_dir(root: &Path) -> PathBuf {
    root.join("blobs").join("sha256")
}
fn manifests_dir(root: &Path) -> PathBuf {
    root.join("manifests")
}

fn write_atomic(path: &Path, data: &[u8]) -> std::io::Result<()> {
    let tmp = path.with_extension("tmp");
    if let Some(parent) = tmp.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut f = fs::File::create(&tmp)?;
    f.write_all(data)?;
    f.sync_all()?;
    fs::rename(&tmp, path)?;
    // ensure dir sync not needed for test
    Ok(())
}

// ---------------------------------------------------------------------------
// Multi-file apply protection: a write-ahead recovery journal records every
// planned mutation BEFORE the first rename and is advanced after each file.
// Any failure between files triggers a proven rollback to the captured
// preimage blobs; a hard crash between files is recoverable from disk via
// `recover_unfinished_apply`. Sequential renames are therefore NOT presented
// as an atomic transaction — they are journaled and reversible.
// ---------------------------------------------------------------------------

pub const RECOVERY_JOURNAL_SCHEMA: &str = "checkpoint.recovery-journal.v1";

#[derive(Clone, Debug, Serialize, Deserialize)]
struct JournalOp {
    path: String,
    /// "replace" (tmp → final) or "delete".
    kind: String,
    /// Staged temp file for replace ops (absolute).
    #[serde(default)]
    tmp: Option<PathBuf>,
    final_path: PathBuf,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct RecoveryJournal {
    schema_version: String,
    task_id: String,
    patch_id: String,
    workspace_root: PathBuf,
    applied: Vec<String>,
    ops: Vec<JournalOp>,
    /// Captured preimage state for every touched path; the rollback authority.
    before_sha256: HashMap<String, String>,
    before_blob_refs: HashMap<String, String>,
}

fn journal_path(store_root: &Path, task_id: &str, patch_id: &str) -> PathBuf {
    let safe = |s: &str| {
        s.chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '_' || c == '-' {
                    c
                } else {
                    '_'
                }
            })
            .take(64)
            .collect::<String>()
    };
    store_root
        .join("journal")
        .join(format!("{}_{}.journal.json", safe(task_id), safe(patch_id)))
}

fn write_journal_atomically(journal: &RecoveryJournal, path: &Path) -> Result<(), String> {
    let data = serde_json::to_vec(journal).map_err(|e| e.to_string())?;
    write_atomic(path, &data).map_err(|e| e.to_string())
}

/// Restore every path in `applied` (reverse order) to its captured preimage.
/// Preimage "missing" means the file must not exist afterwards; otherwise the
/// preimage blob is verified against its hash before being written back.
fn rollback_to_preimage(
    store_root: &Path,
    workspace_root: &Path,
    before_sha256: &HashMap<String, String>,
    before_blob_refs: &HashMap<String, String>,
    applied: &[String],
) -> Result<(), String> {
    for rel in applied.iter().rev() {
        let abs = workspace_root.join(rel);
        match before_sha256.get(rel).map(String::as_str) {
            Some("missing") | None => {
                if abs.exists() {
                    fs::remove_file(&abs).map_err(|e| format!("rollback remove {rel}: {e}"))?;
                }
            }
            Some(pre_hash) => {
                let blob_hash = before_blob_refs
                    .get(rel)
                    .ok_or_else(|| format!("rollback missing blob ref for {rel}"))?;
                let data = fs::read(blobs_dir(store_root).join(blob_hash))
                    .map_err(|e| format!("rollback read blob {rel}: {e}"))?;
                if sha256_hex(&data) != *blob_hash || sha256_hex(&data) != pre_hash {
                    return Err(format!("rollback blob hash mismatch for {rel}"));
                }
                let tmp = abs.with_extension("tmp_rb");
                if let Some(parent) = tmp.parent() {
                    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                fs::write(&tmp, &data).map_err(|e| format!("rollback write {rel}: {e}"))?;
                if abs.exists() {
                    fs::remove_file(&abs).map_err(|e| format!("rollback unlink {rel}: {e}"))?;
                }
                fs::rename(&tmp, &abs).map_err(|e| format!("rollback rename {rel}: {e}"))?;
            }
        }
    }
    Ok(())
}

/// Crash-recovery entry point: scans the journal directory and rolls any
/// unfinished apply back to its recorded preimage. Returns the number of
/// journals recovered. Never mutates anything when no journal exists.
pub fn recover_unfinished_apply(
    store_root: &Path,
    expected_workspace_root: &Path,
) -> Result<usize, String> {
    let dir = store_root.join("journal");
    if !dir.exists() {
        return Ok(0);
    }
    let mut recovered = 0usize;
    let entries = fs::read_dir(&dir).map_err(|e| e.to_string())?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let Ok(data) = fs::read(&path) else {
            continue;
        };
        let Ok(journal) = serde_json::from_slice::<RecoveryJournal>(&data) else {
            continue; // malformed journal: skip, never widen the blast radius
        };
        if journal.workspace_root != expected_workspace_root.to_path_buf() {
            continue; // ownership check: another workspace's journal is untouchable
        }
        let applied: Vec<String> = journal.applied.clone();
        rollback_to_preimage(
            store_root,
            expected_workspace_root,
            &journal.before_sha256,
            &journal.before_blob_refs,
            &applied,
        )?;
        let _ = fs::remove_file(&path);
        recovered += 1;
    }
    Ok(recovered)
}

fn store_blob(root: &Path, data: &[u8]) -> std::io::Result<String> {
    let hash = sha256_hex(data);
    let blob_path = blobs_dir(root).join(&hash);
    if !blob_path.exists() {
        if let Some(parent) = blob_path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&blob_path, data)?;
    }
    Ok(hash)
}

/// Create a checkpoint capturing before/after for touched files (MVP: writes manifest and blobs).
pub fn create_checkpoint(
    store_root: &Path,
    workspace_root: &Path,
    manifest: CheckpointManifest,
    blobs: HashMap<String, Vec<u8>>,
) -> Result<PathBuf, String> {
    for rel in &manifest.paths {
        canonical_relative(workspace_root, rel)?;
    }
    check_case_collision(&manifest.paths)?;
    fs::create_dir_all(manifests_dir(store_root)).map_err(|e| e.to_string())?;
    fs::create_dir_all(blobs_dir(store_root)).map_err(|e| e.to_string())?;
    for (rel, data) in blobs {
        store_blob(store_root, &data).map_err(|e| e.to_string())?;
        let _ = rel;
    }
    let manifest_path = manifests_dir(store_root).join(format!("{}.json", manifest.checkpoint_id));
    let data = serde_json::to_vec_pretty(&manifest).map_err(|e| e.to_string())?;
    write_atomic(&manifest_path, &data).map_err(|e| e.to_string())?;
    // index.json atomic append
    let index_path = store_root.join("index.json");
    let mut index: Vec<String> = if index_path.exists() {
        serde_json::from_slice(&fs::read(&index_path).unwrap_or_default()).unwrap_or_default()
    } else {
        Vec::new()
    };
    index.push(manifest.checkpoint_id.clone());
    let idx_data = serde_json::to_vec_pretty(&index).map_err(|e| e.to_string())?;
    write_atomic(&index_path, &idx_data).map_err(|e| e.to_string())?;
    Ok(manifest_path)
}

/// Apply patch atomically. Returns manifest path on success or Err(CONFLICT/ROLLBACK_REQUIRED).
pub fn apply_patch(
    store_root: &Path,
    workspace_root: &Path,
    patch: &Patch,
    base_hashes: &HashMap<String, String>,
    task_id: &str,
    step_id: &str,
) -> Result<CheckpointManifest, String> {
    journaled_apply(
        store_root,
        workspace_root,
        patch,
        base_hashes,
        task_id,
        step_id,
        None,
    )
}

fn journaled_apply(
    store_root: &Path,
    workspace_root: &Path,
    patch: &Patch,
    base_hashes: &HashMap<String, String>,
    task_id: &str,
    step_id: &str,
    // Test-only fault injection: fail the journaled pass AT this op index
    // (after earlier ops really applied), modelling an IO failure or crash
    // between files. Production always passes None.
    inject_failure_at: Option<usize>,
) -> Result<CheckpointManifest, String> {
    // 1. canonical + collision checks
    let rels: Vec<String> = patch.ops.iter().map(|op| op.path.clone()).collect();
    for rel in &rels {
        canonical_relative(workspace_root, rel)?;
    }
    check_case_collision(&rels)?;

    // 1b. A directory sitting at a patch target must never be overwritten.
    for rel in &rels {
        let abs = workspace_root.join(rel);
        if abs.is_dir() {
            return Err("target_is_directory".into());
        }
    }

    // 2. base hash check — any mismatch => CONFLICT, touch nothing
    for op in &patch.ops {
        let abs = workspace_root.join(&op.path);
        if let Some(expected) = base_hashes.get(&op.path) {
            if abs.exists() {
                let actual = sha256_file(&abs).map_err(|_| "read base".to_string())?;
                if &actual != expected {
                    return Err("CONFLICT".into());
                }
            } else if expected != "missing" {
                return Err("CONFLICT".into());
            }
        }
    }

    // 3. preimage capture + blob store
    let mut before_map = HashMap::new();
    let mut before_blobs = HashMap::new();
    for op in &patch.ops {
        let abs = workspace_root.join(&op.path);
        if abs.exists() {
            let data = fs::read(&abs).map_err(|e| e.to_string())?;
            let h = sha256_hex(&data);
            before_map.insert(op.path.clone(), h.clone());
            store_blob(store_root, &data).map_err(|e| e.to_string())?;
            before_blobs.insert(op.path.clone(), h);
        } else {
            before_map.insert(op.path.clone(), "missing".to_string());
        }
    }

    // 4. apply to temp files, check encoding/size; build the journal ops
    let mut after_map = HashMap::new();
    let mut after_blobs = HashMap::new();
    let mut journal_ops: Vec<JournalOp> = Vec::new(); // (tmp, final)
    for op in &patch.ops {
        let abs = workspace_root.join(&op.path);
        if let Some(data) = &op.content {
            if data.len() > 5 * 1024 * 1024 {
                return Err("too_large".into());
            }
            // check valid utf8 or binary allowed? For now allow any bytes but check not null
            let tmp = abs.with_extension("tmp_patch");
            if let Some(parent) = tmp.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            fs::write(&tmp, data).map_err(|e| e.to_string())?;
            // verify expected hash
            let h = sha256_hex(data);
            after_map.insert(op.path.clone(), h.clone());
            store_blob(store_root, data).map_err(|e| e.to_string())?;
            after_blobs.insert(op.path.clone(), h);
            journal_ops.push(JournalOp {
                path: op.path.clone(),
                kind: "replace".to_string(),
                tmp: Some(tmp),
                final_path: abs,
            });
        } else {
            // delete
            after_map.insert(op.path.clone(), "missing".to_string());
            journal_ops.push(JournalOp {
                path: op.path.clone(),
                kind: "delete".to_string(),
                tmp: None,
                final_path: abs,
            });
        }
    }

    // 4b. Write-ahead journal BEFORE the first mutation so a crash or failure
    // between files is recoverable from disk (never a silent half-apply).
    let jpath = journal_path(store_root, task_id, &patch.patch_id);
    let mut journal = RecoveryJournal {
        schema_version: RECOVERY_JOURNAL_SCHEMA.to_string(),
        task_id: task_id.to_string(),
        patch_id: patch.patch_id.clone(),
        workspace_root: workspace_root.to_path_buf(),
        applied: Vec::new(),
        ops: journal_ops.clone(),
        before_sha256: before_map.clone(),
        before_blob_refs: before_blobs.clone(),
    };
    write_journal_atomically(&journal, &jpath)?;

    // 5. journaled replace/delete pass with rollback-on-failure between files.
    for (op_index, op) in journal_ops.iter().enumerate() {
        let step_result: Result<(), String> = if inject_failure_at == Some(op_index) {
            Err("injected_failure_between_files".to_string())
        } else {
            (|| match (op.kind.as_str(), &op.tmp) {
                ("replace", Some(tmp)) => {
                    if op.final_path.exists() {
                        let _ = fs::remove_file(&op.final_path);
                    }
                    fs::rename(tmp, &op.final_path).map_err(|e| format!("atomic: {e}"))
                }
                ("delete", _) => {
                    if op.final_path.exists() {
                        fs::remove_file(&op.final_path).map_err(|e| format!("delete: {e}"))?;
                    }
                    Ok(())
                }
                _ => Err("journal op malformed".into()),
            })()
        };
        if let Err(e) = step_result {
            let rollback = rollback_to_preimage(
                store_root,
                workspace_root,
                &before_map,
                &before_blobs,
                &journal.applied,
            );
            let _ = fs::remove_file(&jpath);
            return Err(match rollback {
                Ok(()) => format!("rolled_back_after_failure:{e}"),
                Err(rb) => format!("ROLLBACK_REQUIRED:{e};rollback_error:{rb}"),
            });
        }
        journal.applied.push(op.path.clone());
        write_journal_atomically(&journal, &jpath)?;
    }

    // 6. postimage verification; mismatch → proven auto-rollback to preimage.
    for op in &patch.ops {
        let abs = workspace_root.join(&op.path);
        let expected = after_map.get(&op.path).unwrap();
        let verified = if expected == "missing" {
            !abs.exists()
        } else {
            matches!(
                sha256_file(&abs),
                Ok(actual) if &actual == expected
            )
        };
        if !verified {
            let rollback = rollback_to_preimage(
                store_root,
                workspace_root,
                &before_map,
                &before_blobs,
                &patch.ops.iter().map(|o| o.path.clone()).collect::<Vec<_>>(),
            );
            let _ = fs::remove_file(&jpath);
            return Err(match rollback {
                Ok(()) => "rolled_back_after_postimage_failure".into(),
                Err(rb) => format!("ROLLBACK_REQUIRED;rollback_error:{rb}"),
            });
        }
    }

    // 7. Success: journal is consumed and removed before the manifest lands.
    let _ = fs::remove_file(&jpath);

    let manifest = CheckpointManifest {
        schema_version: SCHEMA_VERSION.to_string(),
        checkpoint_id: format!(
            "cp_{}",
            &sha256_hex(format!("{:?}{:?}", task_id, patch.patch_id).as_bytes())[..16]
        ),
        parent_checkpoint_id: None,
        patch_id: patch.patch_id.clone(),
        task_id: task_id.to_string(),
        step_id: step_id.to_string(),
        workspace_digest: sha256_hex(workspace_root.to_string_lossy().as_bytes()),
        base_workspace_state_digest: base_hashes.values().cloned().collect::<Vec<_>>().join(","),
        trigger: "patch_apply".to_string(),
        paths: rels.clone(),
        operations: patch
            .ops
            .iter()
            .map(|op| {
                if op.content.is_some() {
                    "modify".to_string()
                } else {
                    "delete".to_string()
                }
            })
            .collect(),
        before_sha256: before_map.clone(),
        after_sha256: after_map.clone(),
        before_blob_refs: before_blobs,
        after_blob_refs: after_blobs,
        ownership: "user".to_string(),
        evidence_refs: vec![],
        status: "applied".to_string(),
    };
    let _ = create_checkpoint(store_root, workspace_root, manifest.clone(), HashMap::new())?;
    Ok(manifest)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CompareResult {
    Identical,
    Modified { current_sha256: String },
    Missing,
}

/// `compare_only` restore mode: never mutates anything. Reports whether the
/// current file still matches the checkpoint postimage.
pub fn compare_only(
    workspace_root: &Path,
    manifest: &CheckpointManifest,
) -> HashMap<String, CompareResult> {
    let mut out = HashMap::new();
    for rel in &manifest.paths {
        let abs = workspace_root.join(rel);
        if !abs.exists() {
            out.insert(rel.clone(), CompareResult::Missing);
            continue;
        }
        match sha256_file(&abs) {
            Ok(current) => {
                if manifest.after_sha256.get(rel).map(String::as_str) == Some(&current) {
                    out.insert(rel.clone(), CompareResult::Identical);
                } else {
                    out.insert(
                        rel.clone(),
                        CompareResult::Modified {
                            current_sha256: current,
                        },
                    );
                }
            }
            Err(_) => {
                out.insert(rel.clone(), CompareResult::Missing);
            }
        }
    }
    out
}

/// `restore_files` backend contract: only when the current bytes equal the
/// checkpoint postimage (no user/foreign edit wins over), the preimage blob is
/// restored. Any drift => `restore_conflict`, touch nothing. No git reset/clean.
///
/// Multi-file restores are journaled like patch applies: the rollback
/// authority is the verified postimage captured before the first rename, so a
/// failure between files either proves a byte-exact rollback or reports
/// `ROLLBACK_REQUIRED` — never a silent partial restore.
pub fn restore_files(
    store_root: &Path,
    workspace_root: &Path,
    manifest: &CheckpointManifest,
) -> Result<usize, String> {
    restore_files_inner(store_root, workspace_root, manifest, None)
}

fn restore_files_inner(
    store_root: &Path,
    workspace_root: &Path,
    manifest: &CheckpointManifest,
    // Test-only fault injection: fail the journaled pass AT this op index
    // (after earlier files really restored), modelling an IO failure or
    // crash between files. Production always passes None.
    inject_failure_at: Option<usize>,
) -> Result<usize, String> {
    // Precondition pass first — conflict means nothing is touched.
    for rel in &manifest.paths {
        let abs = workspace_root.join(rel);
        match manifest.after_sha256.get(rel).map(String::as_str) {
            None => return Err("restore_conflict: no postimage".into()),
            Some(post_hash) => {
                if abs.exists() {
                    let current = sha256_file(&abs).map_err(|_| "read".to_string())?;
                    if current != *post_hash {
                        return Err("restore_conflict".into());
                    }
                } else if post_hash != "missing" {
                    return Err("restore_conflict".into());
                }
            }
        }
    }

    // Rollback authority: capture the verified postimage bytes for every
    // touched path BEFORE mutating anything.
    let mut post_map = HashMap::new();
    let mut post_blobs = HashMap::new();
    for rel in &manifest.paths {
        let abs = workspace_root.join(rel);
        if abs.exists() {
            let data = fs::read(&abs).map_err(|e| e.to_string())?;
            let h = sha256_hex(&data);
            store_blob(store_root, &data).map_err(|e| e.to_string())?;
            post_blobs.insert(rel.clone(), h.clone());
            post_map.insert(rel.clone(), h);
        } else {
            post_map.insert(rel.clone(), "missing".to_string());
        }
    }

    // Journal ops: stage preimage bytes, replace atomically.
    let mut journal_ops: Vec<JournalOp> = Vec::new();
    for rel in &manifest.paths {
        let abs = workspace_root.join(rel);
        match manifest.before_sha256.get(rel).map(String::as_str) {
            Some("missing") | None => {
                journal_ops.push(JournalOp {
                    path: rel.clone(),
                    kind: "delete".to_string(),
                    tmp: None,
                    final_path: abs,
                });
            }
            Some(_pre_hash) => {
                let blob_hash = manifest
                    .before_blob_refs
                    .get(rel)
                    .ok_or_else(|| "missing preimage blob ref".to_string())?;
                let data =
                    fs::read(blobs_dir(store_root).join(blob_hash)).map_err(|e| e.to_string())?;
                if sha256_hex(&data) != *blob_hash {
                    return Err("blob hash mismatch".into());
                }
                let tmp = abs.with_extension("tmp_restore");
                if let Some(parent) = tmp.parent() {
                    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                fs::write(&tmp, &data).map_err(|e| e.to_string())?;
                journal_ops.push(JournalOp {
                    path: rel.clone(),
                    kind: "replace".to_string(),
                    tmp: Some(tmp),
                    final_path: abs,
                });
            }
        }
    }

    // Write-ahead journal BEFORE the first mutation.
    let jpath = journal_path(
        store_root,
        &manifest.task_id,
        &format!("restore_{}", manifest.checkpoint_id),
    );
    let mut journal = RecoveryJournal {
        schema_version: RECOVERY_JOURNAL_SCHEMA.to_string(),
        task_id: manifest.task_id.clone(),
        patch_id: format!("restore_{}", manifest.checkpoint_id),
        workspace_root: workspace_root.to_path_buf(),
        applied: Vec::new(),
        ops: journal_ops.clone(),
        before_sha256: post_map.clone(),
        before_blob_refs: post_blobs,
    };
    write_journal_atomically(&journal, &jpath)?;

    // Journaled pass with proven rollback on any between-file failure.
    for (op_index, op) in journal_ops.iter().enumerate() {
        let step_result: Result<(), String> = if inject_failure_at == Some(op_index) {
            Err("injected_failure_between_files".to_string())
        } else {
            (|| match (op.kind.as_str(), &op.tmp) {
                ("replace", Some(tmp)) => {
                    if op.final_path.exists() {
                        let _ = fs::remove_file(&op.final_path);
                    }
                    fs::rename(tmp, &op.final_path).map_err(|e| format!("atomic: {e}"))
                }
                ("delete", _) => {
                    if op.final_path.exists() {
                        fs::remove_file(&op.final_path)
                            .map_err(|e| format!("restore delete: {e}"))?;
                    }
                    Ok(())
                }
                _ => Err("journal op malformed".into()),
            })()
        };
        if let Err(e) = step_result {
            let rollback = rollback_to_preimage(
                store_root,
                workspace_root,
                &post_map,
                &manifest.after_blob_refs,
                &journal.applied,
            );
            let _ = fs::remove_file(&jpath);
            return Err(match rollback {
                Ok(()) => format!("restore_rolled_back_after_failure:{e}"),
                Err(rb) => format!("ROLLBACK_REQUIRED:{e};rollback_error:{rb}"),
            });
        }
        journal.applied.push(op.path.clone());
        write_journal_atomically(&journal, &jpath)?;
    }

    // Postcondition verification: every file must now match its recorded
    // PREIMAGE; mismatch → proven auto-rollback to the postimage.
    for op in &journal_ops {
        let abs = workspace_root.join(&op.path);
        let expected = manifest
            .before_sha256
            .get(&op.path)
            .cloned()
            .unwrap_or_else(|| "missing".into());
        let verified = if expected == "missing" {
            !abs.exists()
        } else {
            matches!(
                sha256_file(&abs),
                Ok(actual) if actual == expected
            )
        };
        if !verified {
            let rollback = rollback_to_preimage(
                store_root,
                workspace_root,
                &post_map,
                &manifest.after_blob_refs,
                &journal_ops
                    .iter()
                    .map(|o| o.path.clone())
                    .collect::<Vec<_>>(),
            );
            let _ = fs::remove_file(&jpath);
            return Err(match rollback {
                Ok(()) => "restore_rolled_back_after_postimage_failure".into(),
                Err(rb) => format!("ROLLBACK_REQUIRED;rollback_error:{rb}"),
            });
        }
    }

    let _ = fs::remove_file(&jpath);
    Ok(journal_ops.len())
}

/// `restore_task` mode: undo every checkpoint of ONE task in reverse
/// chronological order (newest patch undone first), so intermediate states
/// line up and each per-checkpoint conflict rule stays meaningful. Any
/// conflict aborts before touching that checkpoint; earlier (already
/// restored newer) files keep their rolled-back state and the error names
/// the offending checkpoint.
pub fn restore_task(
    store_root: &Path,
    workspace_root: &Path,
    // Must be in chronological order (oldest first), single task only.
    manifests_chronological: &[CheckpointManifest],
) -> Result<(String, usize), String> {
    let mut task_id: Option<&str> = None;
    for m in manifests_chronological {
        match task_id {
            None => task_id = Some(m.task_id.as_str()),
            Some(t) if t != m.task_id => {
                return Err("restore_task_mixed_tasks".into());
            }
            _ => {}
        }
    }
    let task = task_id.ok_or("restore_task_empty")?;
    let mut restored = 0usize;
    for manifest in manifests_chronological.iter().rev() {
        match restore_files(store_root, workspace_root, manifest) {
            Ok(n) => restored += n,
            Err(reason) => {
                return Err(format!(
                    "restore_conflict@{}:{reason}",
                    manifest.checkpoint_id
                ))
            }
        }
    }
    Ok((task.to_string(), restored))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_dirs(prefix: &str) -> (PathBuf, PathBuf) {
        let base = std::env::temp_dir();
        let uniq = format!(
            "{}_{}_{}",
            prefix,
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let ws = base.join(format!("ws_{}", uniq));
        let store = base.join(format!("store_{}", uniq));
        fs::create_dir_all(&ws).unwrap();
        fs::create_dir_all(&store).unwrap();
        (ws, store)
    }
    fn cleanup(p: &Path) {
        let _ = fs::remove_dir_all(p);
    }

    /// restore_task: two sequential patches over the same file unwind in
    /// reverse order; a foreign edit on an intermediate state conflicts and
    /// names the offending checkpoint; mixed-task input is rejected.
    #[test]
    fn restore_task_unwinds_in_reverse_order_and_conflicts_honestly() {
        let (ws, store) = tmp_dirs("rt");
        fs::write(ws.join("a.txt"), b"v0").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"v0"));
        let m1 = apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "rt1".into(),
                ops: vec![FileOp {
                    path: "a.txt".into(),
                    content: Some(b"v1".to_vec()),
                }],
            },
            &base,
            "task_rt",
            "s1",
        )
        .unwrap();
        let base2 = HashMap::from([("a.txt".to_string(), sha256_hex(b"v1"))]);
        let m2 = apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "rt2".into(),
                ops: vec![FileOp {
                    path: "a.txt".into(),
                    content: Some(b"v2".to_vec()),
                }],
            },
            &base2,
            "task_rt",
            "s1",
        )
        .unwrap();
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"v2");

        // Mixed tasks rejected before touching anything.
        let mut mixed = m2.clone();
        mixed.task_id = "other".into();
        let err = restore_task(&store, &ws, &[m1.clone(), mixed]).unwrap_err();
        assert!(err.contains("mixed"));

        // Full unwind: newest first → back to v0.
        let (task, n) = restore_task(&store, &ws, &[m1.clone(), m2.clone()]).unwrap();
        assert_eq!(task, "task_rt");
        assert_eq!(n, 2);
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"v0");

        // Re-apply v1/v2 then introduce a foreign edit: conflict must name
        // the checkpoint whose postimage no longer matches, and leave the
        // already-unwound newer file in its rolled-back state.
        let base2b = HashMap::from([("a.txt".to_string(), sha256_hex(b"v0"))]);
        let m1b = apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "rt3".into(),
                ops: vec![FileOp {
                    path: "a.txt".into(),
                    content: Some(b"v1".to_vec()),
                }],
            },
            &base2b,
            "task_rt",
            "s1",
        )
        .unwrap();
        // user edit wins → m1b postimage no longer on disk
        fs::write(ws.join("a.txt"), b"user-edit").unwrap();
        let err = restore_task(&store, &ws, &[m1b]).unwrap_err();
        assert!(err.starts_with("restore_conflict@cp_"), "got: {err}");
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"user-edit");

        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn create_and_modify() {
        let (ws, store) = tmp_dirs("cm");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"hello"));
        let patch = Patch {
            patch_id: "p1".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"world".to_vec()),
            }],
        };
        let m = apply_patch(&store, &ws, &patch, &base, "t1", "s1").expect("apply");
        assert_eq!(m.status, "applied");
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"world");
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn base_conflict_touch_nothing() {
        let (ws, store) = tmp_dirs("bc");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"other"));
        let patch = Patch {
            patch_id: "p2".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"world".to_vec()),
            }],
        };
        let err = apply_patch(&store, &ws, &patch, &base, "t1", "s1").unwrap_err();
        assert_eq!(err, "CONFLICT");
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"hello");
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn traversal_rejected() {
        let (ws, store) = tmp_dirs("tr");
        let patch = Patch {
            patch_id: "p3".into(),
            ops: vec![FileOp {
                path: "../evil.txt".into(),
                content: Some(b"x".to_vec()),
            }],
        };
        let err = apply_patch(&store, &ws, &patch, &HashMap::new(), "t1", "s1").unwrap_err();
        assert!(err.contains("traversal") || err.contains("parent"));
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn encoded_traversal_rejected() {
        let (ws, store) = tmp_dirs("etr");
        let patch = Patch {
            patch_id: "p4".into(),
            ops: vec![FileOp {
                path: "%2e%2e/evil.txt".into(),
                content: Some(b"x".to_vec()),
            }],
        };
        let err = apply_patch(&store, &ws, &patch, &HashMap::new(), "t1", "s1").unwrap_err();
        assert!(err.contains("traversal"));
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn delete_and_create() {
        let (ws, store) = tmp_dirs("dc");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"hello"));
        let patch = Patch {
            patch_id: "p5".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: None,
            }],
        };
        apply_patch(&store, &ws, &patch, &base, "t1", "s1").unwrap();
        assert!(!ws.join("a.txt").exists());
        let patch2 = Patch {
            patch_id: "p6".into(),
            ops: vec![FileOp {
                path: "b.txt".into(),
                content: Some(b"new".to_vec()),
            }],
        };
        apply_patch(&store, &ws, &patch2, &HashMap::new(), "t1", "s1").unwrap();
        assert_eq!(fs::read(ws.join("b.txt")).unwrap(), b"new");
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn external_storage() {
        let (ws, store) = tmp_dirs("es");
        let patch = Patch {
            patch_id: "p7".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"x".to_vec()),
            }],
        };
        apply_patch(&store, &ws, &patch, &HashMap::new(), "t1", "s1").unwrap();
        assert!(store.join("manifests").exists());
        assert!(store.join("blobs").exists());
        assert!(!ws.join("manifests").exists());
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn case_collision_rejected() {
        let (ws, store) = tmp_dirs("cc");
        let patch = Patch {
            patch_id: "p8".into(),
            ops: vec![
                FileOp {
                    path: "A.txt".into(),
                    content: Some(b"x".to_vec()),
                },
                FileOp {
                    path: "a.txt".into(),
                    content: Some(b"y".to_vec()),
                },
            ],
        };
        let err = apply_patch(&store, &ws, &patch, &HashMap::new(), "t1", "s1").unwrap_err();
        assert!(err.contains("case"));
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn compare_only_reports_identical_modified_missing_without_mutation() {
        let (ws, store) = tmp_dirs("cmp");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"hello"));
        let patch = Patch {
            patch_id: "cp1".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"world".to_vec()),
            }],
        };
        let m = apply_patch(&store, &ws, &patch, &base, "t1", "s1").unwrap();
        let r1 = compare_only(&ws, &m);
        assert!(matches!(r1.get("a.txt"), Some(CompareResult::Identical)));
        fs::write(ws.join("a.txt"), b"user-edit").unwrap();
        let r2 = compare_only(&ws, &m);
        assert!(matches!(
            r2.get("a.txt"),
            Some(CompareResult::Modified { .. })
        ));
        fs::remove_file(ws.join("a.txt")).unwrap();
        let r3 = compare_only(&ws, &m);
        assert!(matches!(r3.get("a.txt"), Some(CompareResult::Missing)));
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn restore_files_safe_and_conflict_wins() {
        let (ws, store) = tmp_dirs("rst");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"hello"));
        let patch = Patch {
            patch_id: "rs1".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"world".to_vec()),
            }],
        };
        let m = apply_patch(&store, &ws, &patch, &base, "t1", "s1").unwrap();
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"world");
        let n = restore_files(&store, &ws, &m).expect("restore");
        assert_eq!(n, 1);
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"hello");
        cleanup(&ws);
        cleanup(&store);
    }

    #[test]
    fn restore_conflicts_on_user_edit_and_touches_nothing() {
        let (ws, store) = tmp_dirs("rsc");
        fs::write(ws.join("a.txt"), b"hello").unwrap();
        let mut base = HashMap::new();
        base.insert("a.txt".to_string(), sha256_hex(b"hello"));
        let patch = Patch {
            patch_id: "rs2".into(),
            ops: vec![FileOp {
                path: "a.txt".into(),
                content: Some(b"world".to_vec()),
            }],
        };
        let m = apply_patch(&store, &ws, &patch, &base, "t1", "s1").unwrap();
        // user edits after checkpoint — their change wins
        fs::write(ws.join("a.txt"), b"user-precious").unwrap();
        let err = restore_files(&store, &ws, &m).unwrap_err();
        assert_eq!(err, "restore_conflict");
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"user-precious");
        cleanup(&ws);
        cleanup(&store);
    }

    /// Failure BETWEEN files of one multi-file restore: already-restored
    /// files must be proven rolled back to their verified postimage and no
    /// journal may remain. A silent partial restore is forbidden.
    #[test]
    fn partial_restore_failure_rolls_back_between_files() {
        let (ws, store) = tmp_dirs("rjf");
        fs::write(ws.join("first.txt"), b"orig-first").unwrap();
        fs::write(ws.join("second.txt"), b"orig-second").unwrap();
        let mut base = HashMap::new();
        base.insert("first.txt".to_string(), sha256_hex(b"orig-first"));
        base.insert("second.txt".to_string(), sha256_hex(b"orig-second"));
        let m = apply_patch(
            &store,
            &ws,
            &Patch {
                patch_id: "rj1".into(),
                ops: vec![
                    FileOp {
                        path: "first.txt".into(),
                        content: Some(b"patched-first".to_vec()),
                    },
                    FileOp {
                        path: "second.txt".into(),
                        content: Some(b"patched-second".to_vec()),
                    },
                ],
            },
            &base,
            "t_rj",
            "s1",
        )
        .unwrap();
        assert_eq!(fs::read(ws.join("first.txt")).unwrap(), b"patched-first");

        let err = restore_files_inner(&store, &ws, &m, Some(1)).unwrap_err();
        assert!(
            err.starts_with("restore_rolled_back_after_failure"),
            "expected proven rollback, got: {err}"
        );
        // Byte-exact postimage on both files; second never half-restored.
        assert_eq!(fs::read(ws.join("first.txt")).unwrap(), b"patched-first");
        assert_eq!(fs::read(ws.join("second.txt")).unwrap(), b"patched-second");
        // Journal consumed: no unfinished restore left behind.
        let journal_dir = store.join("journal");
        assert!(
            !journal_dir.exists()
                || journal_dir
                    .read_dir()
                    .map(|mut d| d.next().is_none())
                    .unwrap_or(true)
        );
        cleanup(&ws);
        cleanup(&store);
    }

    /// Failure BETWEEN files of one multi-file patch: the earlier applied
    /// file must be rolled back to its preimage and no journal may remain.
    /// The injected fault exercises the same error path a real IO failure
    /// takes at the journaled step (op 0 really applied, op 1 fails).
    #[test]
    fn partial_apply_failure_rolls_back_between_files() {
        let (ws, store) = tmp_dirs("pjf");
        fs::write(ws.join("first.txt"), b"original-first").unwrap();

        let mut base = HashMap::new();
        base.insert("first.txt".to_string(), sha256_hex(b"original-first"));
        let patch = Patch {
            patch_id: "pj1".into(),
            ops: vec![
                FileOp {
                    path: "first.txt".into(),
                    content: Some(b"patched-first".to_vec()),
                },
                FileOp {
                    path: "second.txt".into(),
                    content: Some(b"patched-second".to_vec()),
                },
            ],
        };
        let err = journaled_apply(
            &store,
            &ws,
            &patch,
            &base,
            "t_pj",
            "s1",
            Some(1), // fail at second op, after the first truly applied
        )
        .unwrap_err();
        assert!(
            err.starts_with("rolled_back_after_failure"),
            "expected proven rollback, got: {err}"
        );
        // First file restored byte-for-byte; second never created.
        assert_eq!(fs::read(ws.join("first.txt")).unwrap(), b"original-first");
        assert!(!ws.join("second.txt").exists());
        // Journal consumed: no unfinished apply left behind.
        assert!(!store.join("journal").join("t_pj_pj1.journal.json").exists());
        cleanup(&ws);
        cleanup(&store);
    }

    /// A directory parked on a patch target is rejected before ANY mutation,
    /// including before the journal and the first file's rename.
    #[test]
    fn directory_on_target_rejected_before_mutation() {
        let (ws, store) = tmp_dirs("pjd");
        fs::write(ws.join("first.txt"), b"original-first").unwrap();
        fs::create_dir_all(ws.join("second.txt")).unwrap();
        let mut base = HashMap::new();
        base.insert("first.txt".to_string(), sha256_hex(b"original-first"));
        let patch = Patch {
            patch_id: "pj2".into(),
            ops: vec![
                FileOp {
                    path: "first.txt".into(),
                    content: Some(b"patched-first".to_vec()),
                },
                FileOp {
                    path: "second.txt".into(),
                    content: Some(b"x".to_vec()),
                },
            ],
        };
        let err = apply_patch(&store, &ws, &patch, &base, "t_pjd", "s1").unwrap_err();
        assert!(err.contains("directory"), "got: {err}");
        assert_eq!(fs::read(ws.join("first.txt")).unwrap(), b"original-first");
        assert!(ws.join("second.txt").is_dir());
        assert!(
            !store.join("journal").exists()
                || store
                    .join("journal")
                    .read_dir()
                    .map(|mut d| d.next().is_none())
                    .unwrap_or(true)
        );
        cleanup(&ws);
        cleanup(&store);
    }

    /// Hard-crash equivalent: a journal survives on disk with one file already
    /// replaced. `recover_unfinished_apply` must restore the preimage from
    /// blobs, consume the journal, and refuse foreign-workspace journals.
    #[test]
    fn crash_between_files_is_recoverable_from_journal() {
        let (ws, store) = tmp_dirs("pjc");
        let (other_ws, _other_store) = tmp_dirs("pjc_other");
        fs::create_dir_all(&other_ws).unwrap();

        fs::write(ws.join("a.txt"), b"preimage-a").unwrap();
        let blob_hash = store_blob(&store, b"preimage-a").unwrap();
        let pre_hash = sha256_hex(b"preimage-a");

        // Simulated crash state: a.txt already replaced, journal says so.
        fs::write(ws.join("a.txt"), b"half-applied-patch").unwrap();
        let journal = RecoveryJournal {
            schema_version: RECOVERY_JOURNAL_SCHEMA.to_string(),
            task_id: "t_crash".into(),
            patch_id: "pc1".into(),
            workspace_root: ws.clone(),
            applied: vec!["a.txt".into()],
            ops: vec![JournalOp {
                path: "a.txt".into(),
                kind: "replace".into(),
                tmp: None,
                final_path: ws.join("a.txt"),
            }],
            before_sha256: HashMap::from([("a.txt".to_string(), pre_hash.clone())]),
            before_blob_refs: HashMap::from([("a.txt".to_string(), blob_hash)]),
        };
        let jp = journal_path(&store, "t_crash", "pc1");
        write_journal_atomically(&journal, &jp).unwrap();

        // Foreign workspace journal must be skipped entirely.
        let foreign = RecoveryJournal {
            workspace_root: other_ws.clone(),
            task_id: "t_foreign".into(),
            ..journal.clone()
        };
        write_journal_atomically(&foreign, &journal_path(&store, "t_foreign", "pf1")).unwrap();
        fs::write(other_ws.join("f.txt"), b"foreign-intact").unwrap();

        let n = recover_unfinished_apply(&store, &ws).expect("recovery runs");
        assert_eq!(n, 1, "only the owned journal is recovered");
        assert_eq!(fs::read(ws.join("a.txt")).unwrap(), b"preimage-a");
        assert!(!jp.exists(), "consumed journal removed");
        // Untouched foreign journal and its workspace stay intact.
        assert!(journal_path(&store, "t_foreign", "pf1").exists());
        assert_eq!(fs::read(other_ws.join("f.txt")).unwrap(), b"foreign-intact");

        cleanup(&ws);
        cleanup(&store);
        cleanup(&other_ws);
        cleanup(&_other_store);
    }
}
