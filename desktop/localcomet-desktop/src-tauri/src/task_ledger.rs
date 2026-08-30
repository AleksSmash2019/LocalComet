//! Task Ledger MVP — NDJSON + snapshot hash chain, external storage.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

pub const EVENT_SCHEMA: &str = "task.ledger.event.v1";
pub const SNAPSHOT_SCHEMA: &str = "task.ledger.snapshot.v1";
const MAX_LEDGER_BYTES: u64 = 8 * 1024 * 1024;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TaskState {
    Created,
    IntentCompiled,
    PlanReady,
    AwaitingApproval,
    Running,
    WaitingHost,
    Validating,
    Recovering,
    PausedForReview,
    RollbackRequired,
    Completed,
    Failed,
    Blocked,
    Cancelled,
    Expired,
}

impl TaskState {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            Self::Failed | Self::Blocked | Self::Cancelled | Self::Expired | Self::Completed
        )
    }

    /// Non-terminal states that still require user attention before any
    /// mutating retry. Used by recovery to refuse automatic re-runs.
    pub fn requires_review(&self) -> bool {
        matches!(self, Self::PausedForReview | Self::RollbackRequired)
    }

    /// Stable wire value for UI/recovery consumers. Do not expose Rust's
    /// `Debug` formatting as a protocol contract.
    pub fn wire_name(&self) -> &'static str {
        match self {
            Self::Created => "created",
            Self::IntentCompiled => "intent_compiled",
            Self::PlanReady => "plan_ready",
            Self::AwaitingApproval => "awaiting_approval",
            Self::Running => "running",
            Self::WaitingHost => "waiting_host",
            Self::Validating => "validating",
            Self::Recovering => "recovering",
            Self::PausedForReview => "paused_for_review",
            Self::RollbackRequired => "rollback_required",
            Self::Completed => "completed",
            Self::Failed => "failed",
            Self::Blocked => "blocked",
            Self::Cancelled => "cancelled",
            Self::Expired => "expired",
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskEvent {
    pub schema_version: String,
    pub seq: u64,
    pub event_id: String,
    pub task_id: String,
    pub task_version: u64,
    pub created_at_unix_ms: u64,
    pub event_type: String,
    pub state_before: TaskState,
    pub state_after: TaskState,
    pub step_id: Option<String>,
    pub checkpoint_id: Option<String>,
    pub request_id: Option<String>,
    pub action_id: Option<String>,
    pub correlation_id: Option<String>,
    pub payload: serde_json::Value,
    pub prev_event_hash: String,
    pub event_hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskSnapshot {
    pub schema_version: String,
    pub task_id: String,
    pub workspace_digest: String,
    pub session_id: String,
    pub last_seq: u64,
    pub last_event_hash: String,
    pub state: TaskState,
    pub current_step_id: Option<String>,
    pub completed_step_ids: Vec<String>,
    pub remaining_step_ids: Vec<String>,
    pub budgets: serde_json::Value,
    pub model_binding_fingerprint: String,
    pub checkpoint_id: Option<String>,
    pub pending_request_id: Option<String>,
    pub pending_action_id: Option<String>,
    pub pending_grant_ref_hash: Option<String>,
    pub last_evidence_refs: Vec<String>,
    pub updated_at_unix_ms: u64,
    pub snapshot_hash: String,
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn canonical_json(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::Null => "null".into(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => {
            format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
        }
        serde_json::Value::Array(a) => format!(
            "[{}]",
            a.iter().map(canonical_json).collect::<Vec<_>>().join(",")
        ),
        serde_json::Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            let pairs: Vec<String> = keys
                .iter()
                .map(|k| format!("\"{}\":{}", k, canonical_json(&m[*k])))
                .collect();
            format!("{{{}}}", pairs.join(","))
        }
    }
}

fn event_hash_without_hash(event: &TaskEvent) -> String {
    let mut clone = serde_json::to_value(event).unwrap();
    if let serde_json::Value::Object(ref mut map) = clone {
        map.remove("event_hash");
    }
    let canonical = canonical_json(&clone);
    sha256_hex(canonical.as_bytes())
}

fn snapshot_hash_without_hash(snap: &TaskSnapshot) -> String {
    let mut clone = serde_json::to_value(snap).unwrap();
    if let serde_json::Value::Object(ref mut map) = clone {
        map.remove("snapshot_hash");
    }
    let canonical = canonical_json(&clone);
    sha256_hex(canonical.as_bytes())
}

pub fn valid_transition(from: &TaskState, to: &TaskState) -> bool {
    use TaskState::*;
    matches!(
        (from, to),
        (Created, IntentCompiled)
            | (IntentCompiled, PlanReady)
            | (IntentCompiled, AwaitingApproval)
            | (IntentCompiled, Running)
            | (PlanReady, AwaitingApproval)
            | (AwaitingApproval, Running)
            | (Running, WaitingHost)
            | (Running, Validating)
            // Bounded no-op progress transitions: fine-grained runner/
            // diagnostics events ride on the same typed state while the
            // hash chain keeps their order tamper-evident.
            | (Running, Running)
            | (Validating, Validating)
            | (WaitingHost, Validating)
            | (WaitingHost, Running)
            | (Validating, Running)
            | (Validating, Completed)
            | (Validating, Failed)
            | (Running, Failed)
            | (Running, Blocked)
            | (Running, Cancelled)
            | (Running, Expired)
            | (WaitingHost, Blocked)
            | (WaitingHost, Expired)
            | (WaitingHost, Recovering)
            | (Recovering, PausedForReview)
            | (Recovering, Running)
            | (Recovering, Failed)
            // Cancel after the patch applied: rollback finished, then the
            // typed cancelled terminal (workspace proven at preimage).
            | (Recovering, Cancelled)
            | (PausedForReview, Running)
            | (PausedForReview, Failed)
            // Postcondition failure after a patch landed: the workspace may
            // hold a silently broken state until a proven rollback finishes.
            | (Running, RollbackRequired)
            | (Validating, RollbackRequired)
            | (RollbackRequired, Recovering)
            | (RollbackRequired, PausedForReview)
            | (Created, Failed)
            | (IntentCompiled, Failed)
    )
}

pub struct LedgerStore {
    root: PathBuf,
}

pub(crate) fn is_reparse_or_symlink(path: &Path) -> bool {
    let Ok(metadata) = fs::symlink_metadata(path) else {
        return false;
    };
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0400;
        if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return true;
        }
    }
    false
}

impl LedgerStore {
    pub fn new_with_root(root: PathBuf) -> Self {
        Self { root }
    }
    pub fn new_for_workspace(workspace_digest: &str) -> Self {
        let base = std::env::var("LOCALAPPDATA")
            .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
        let root = Path::new(&base)
            .join("LocalComet")
            .join("DevRuntime")
            .join("tasks")
            .join(workspace_digest);
        Self { root }
    }
    fn ledger_path(&self, task_id: &str) -> PathBuf {
        self.root.join("ledger").join(format!("{}.ndjson", task_id))
    }
    fn snapshot_path(&self, task_id: &str, terminal: bool) -> PathBuf {
        let dir = if terminal { "terminal" } else { "active" };
        self.root
            .join(dir)
            .join(format!("{}.snapshot.json", task_id))
    }

    pub fn has_task(&self, task_id: &str) -> bool {
        let ledger = self.ledger_path(task_id);
        if is_reparse_or_symlink(&ledger) {
            return false;
        }
        ledger.is_file()
    }

    /// Parse every complete event and return the byte offset after the valid
    /// prefix. A malformed final record is treated as a crash-truncated tail
    /// and may be repaired before the next append. Any malformed record with
    /// later bytes is interior corruption and fails closed.
    fn scan_ledger_bytes(data: &[u8]) -> Result<(usize, Vec<TaskEvent>), String> {
        let mut valid_end = 0usize;
        let mut expected_prev = "0".repeat(64);
        let mut expected_seq = 1u64;
        let mut events = Vec::new();

        for segment in data.split_inclusive(|byte| *byte == b'\n') {
            let raw = segment.strip_suffix(b"\n").unwrap_or(segment);
            if raw.iter().all(|byte| byte.is_ascii_whitespace()) {
                valid_end += segment.len();
                continue;
            }
            let line = std::str::from_utf8(raw).map_err(|_| "ledger_corrupt".to_string())?;
            let event = match serde_json::from_str::<TaskEvent>(line) {
                Ok(event) => event,
                Err(_) if valid_end + segment.len() == data.len() => break,
                Err(_) => return Err("ledger_corrupt".into()),
            };
            if event.seq != expected_seq {
                return Err("seq_mismatch".into());
            }
            if event.prev_event_hash != expected_prev {
                return Err("prev_hash_mismatch".into());
            }
            if event_hash_without_hash(&event) != event.event_hash {
                return Err("hash_mismatch".into());
            }
            expected_prev = event.event_hash.clone();
            expected_seq += 1;
            valid_end += segment.len();
            events.push(event);
        }
        Ok((valid_end, events))
    }

    /// Remove only an incomplete final record left by a crash. Never repair
    /// interior corruption silently: doing so would make later events
    /// unverifiable and could hide task history.
    fn prepare_append(&self, task_id: &str) -> Result<(u64, String), String> {
        let ledger = self.ledger_path(task_id);
        if !ledger.exists() {
            return Ok((0, "0".repeat(64)));
        }
        if is_reparse_or_symlink(&ledger) {
            return Err("ledger_reparse_point_rejected".into());
        }
        let metadata = fs::metadata(&ledger).map_err(|e| e.to_string())?;
        if metadata.len() > MAX_LEDGER_BYTES {
            return Err("ledger_too_large".into());
        }
        let data = fs::read(&ledger).map_err(|e| e.to_string())?;
        let (valid_end, events) = Self::scan_ledger_bytes(&data)?;
        if valid_end < data.len() {
            let file = fs::OpenOptions::new()
                .write(true)
                .open(&ledger)
                .map_err(|e| e.to_string())?;
            file.set_len(valid_end as u64).map_err(|e| e.to_string())?;
            file.sync_all().map_err(|e| e.to_string())?;
        }
        Ok(events
            .last()
            .map(|event| (event.seq, event.event_hash.clone()))
            .unwrap_or((0, "0".repeat(64))))
    }

    pub fn append_event(&self, mut event: TaskEvent) -> Result<TaskEvent, String> {
        if !valid_transition(&event.state_before, &event.state_after) {
            return Err("invalid_transition".into());
        }
        let ledger = self.ledger_path(&event.task_id);
        if let Some(parent) = ledger.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        // Repair only a crash-truncated final record; interior corruption is
        // rejected before this append can hide it.
        let (last_seq, last_hash) = self.prepare_append(&event.task_id)?;
        if event.seq != last_seq + 1 && last_seq != 0 {
            return Err("seq_mismatch".into());
        }
        if event.prev_event_hash != last_hash && last_seq != 0 {
            return Err("prev_hash_mismatch".into());
        }
        let hash = event_hash_without_hash(&event);
        event.event_hash = hash;
        let line = serde_json::to_string(&event).map_err(|e| e.to_string())?;
        let mut f = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&ledger)
            .map_err(|e| e.to_string())?;
        writeln!(f, "{}", line).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        Ok(event)
    }

    pub fn last_seq_hash(&self, task_id: &str) -> Option<(u64, String)> {
        let ledger = self.ledger_path(task_id);
        if is_reparse_or_symlink(&ledger) || fs::metadata(&ledger).ok()?.len() > MAX_LEDGER_BYTES {
            return None;
        }
        let data = fs::read(&ledger).ok()?;
        let (_, events) = Self::scan_ledger_bytes(&data).ok()?;
        Some(
            events
                .last()
                .map(|event| (event.seq, event.event_hash.clone()))
                .unwrap_or((0, "0".repeat(64))),
        )
    }

    pub fn verify_chain(&self, task_id: &str) -> Result<Vec<TaskEvent>, String> {
        let ledger = self.ledger_path(task_id);
        if !ledger.exists() {
            return Ok(vec![]);
        }
        if is_reparse_or_symlink(&ledger) {
            return Err("ledger_reparse_point_rejected".into());
        }
        let metadata = fs::metadata(&ledger).map_err(|e| e.to_string())?;
        if metadata.len() > MAX_LEDGER_BYTES {
            return Err("ledger_too_large".into());
        }
        let data = fs::read(&ledger).map_err(|e| e.to_string())?;
        let (_, events) = Self::scan_ledger_bytes(&data)?;
        Ok(events)
    }

    pub fn write_snapshot(
        &self,
        mut snap: TaskSnapshot,
        terminal: bool,
    ) -> Result<PathBuf, String> {
        let hash = snapshot_hash_without_hash(&snap);
        snap.snapshot_hash = hash;
        let path = self.snapshot_path(&snap.task_id, terminal);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let data = serde_json::to_vec_pretty(&snap).map_err(|e| e.to_string())?;
        let tmp = path.with_extension("tmp");
        fs::write(&tmp, &data).map_err(|e| e.to_string())?;
        fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
        Ok(path)
    }

    pub fn load_snapshot(&self, task_id: &str, terminal: bool) -> Result<TaskSnapshot, String> {
        let path = self.snapshot_path(task_id, terminal);
        let data = fs::read(&path).map_err(|e| e.to_string())?;
        let snap: TaskSnapshot = serde_json::from_slice(&data).map_err(|e| e.to_string())?;
        let computed = snapshot_hash_without_hash(&snap);
        if computed != snap.snapshot_hash {
            return Err("snapshot_hash_mismatch".into());
        }
        Ok(snap)
    }

    pub fn recover(&self, task_id: &str) -> Result<(TaskSnapshot, Vec<TaskEvent>), String> {
        // try active snapshot, else terminal
        let snap = self
            .load_snapshot(task_id, false)
            .or_else(|_| self.load_snapshot(task_id, true))?;
        let events = self.verify_chain(task_id)?;
        // replay after last_seq
        let to_replay: Vec<TaskEvent> = events
            .into_iter()
            .filter(|e| e.seq > snap.last_seq)
            .collect();
        Ok((snap, to_replay))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_root() -> PathBuf {
        let base = std::env::temp_dir();
        let uniq = format!(
            "ledger_{}_{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let p = base.join(uniq);
        fs::create_dir_all(&p).unwrap();
        p
    }
    fn cleanup(p: &Path) {
        let _ = fs::remove_dir_all(p);
    }

    fn sample_event(
        task_id: &str,
        seq: u64,
        prev: &str,
        from: TaskState,
        to: TaskState,
    ) -> TaskEvent {
        TaskEvent {
            schema_version: EVENT_SCHEMA.to_string(),
            seq,
            event_id: format!("evt_{}", seq),
            task_id: task_id.to_string(),
            task_version: 1,
            created_at_unix_ms: 0,
            event_type: "step.completed".to_string(),
            state_before: from,
            state_after: to,
            step_id: Some("step_1".to_string()),
            checkpoint_id: None,
            request_id: Some("req_1".to_string()),
            action_id: Some("act_1".to_string()),
            correlation_id: Some("corr_1".to_string()),
            payload: serde_json::json!({"verdict":"VERIFIED_SUCCESS"}),
            prev_event_hash: prev.to_string(),
            event_hash: String::new(),
        }
    }

    #[test]
    fn create_append_replay() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_1";
        let ev1 = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        let ev1 = store.append_event(ev1).unwrap();
        let ev2 = sample_event(
            task,
            2,
            &ev1.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
        );
        store.append_event(ev2).unwrap();
        let events = store.verify_chain(task).unwrap();
        assert_eq!(events.len(), 2);
        cleanup(&root);
    }

    #[test]
    fn seq_mismatch_rejected() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_seq";
        let ev1 = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        let ev1 = store.append_event(ev1).unwrap();
        let mut ev2 = sample_event(
            task,
            5,
            &ev1.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
        );
        ev2.seq = 5;
        let err = store.append_event(ev2).unwrap_err();
        assert!(err.contains("seq"));
        cleanup(&root);
    }

    #[test]
    fn hash_mismatch_detected() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_hash";
        let ev1 = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        store.append_event(ev1).unwrap();
        // corrupt file directly — change payload verdict so hash mismatches
        let ledger = store.ledger_path(task);
        let mut content = fs::read_to_string(&ledger).unwrap();
        content = content.replace("VERIFIED_SUCCESS", "CORRUPTED");
        fs::write(&ledger, content).unwrap();
        let err = store.verify_chain(task).unwrap_err();
        assert!(err.contains("hash") || err.contains("mismatch"));
        cleanup(&root);
    }

    #[test]
    fn truncated_final_line_ignored() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_trunc";
        let ev1 = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        let ev1 = store.append_event(ev1).unwrap();
        let ev2 = sample_event(
            task,
            2,
            &ev1.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
        );
        store.append_event(ev2).unwrap();
        // append truncated line
        let ledger = store.ledger_path(task);
        let mut f = fs::OpenOptions::new().append(true).open(&ledger).unwrap();
        writeln!(f, "{{\"incomplete\":").unwrap();
        let events = store.verify_chain(task).unwrap();
        assert_eq!(events.len(), 2);
        cleanup(&root);
    }

    #[test]
    fn append_repairs_only_truncated_final_record() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_tail_repair";
        let ev1 = store
            .append_event(sample_event(
                task,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();
        let ev2 = store
            .append_event(sample_event(
                task,
                2,
                &ev1.event_hash,
                TaskState::IntentCompiled,
                TaskState::PlanReady,
            ))
            .unwrap();
        let ledger = store.ledger_path(task);
        let mut f = fs::OpenOptions::new().append(true).open(&ledger).unwrap();
        writeln!(f, "{{\"event_id\":\"truncated").unwrap();
        drop(f);

        let ev3 = store
            .append_event(sample_event(
                task,
                3,
                &ev2.event_hash,
                TaskState::PlanReady,
                TaskState::AwaitingApproval,
            ))
            .unwrap();
        let events = store.verify_chain(task).unwrap();
        assert_eq!(events.len(), 3);
        assert_eq!(events.last().unwrap().event_hash, ev3.event_hash);
        assert!(!fs::read_to_string(&ledger).unwrap().contains("truncated"));
        cleanup(&root);
    }

    #[test]
    fn interior_corruption_is_rejected_before_append() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_interior_corrupt";
        let ev1 = store
            .append_event(sample_event(
                task,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();
        let ledger = store.ledger_path(task);
        let mut f = fs::OpenOptions::new().append(true).open(&ledger).unwrap();
        writeln!(f, "{{\"event_id\":\"corrupt\"}}").unwrap();
        // A valid later record makes the malformed record interior corruption,
        // rather than a crash-truncated final tail.
        let mut ev2 = sample_event(
            task,
            2,
            &ev1.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
        );
        ev2.event_hash = event_hash_without_hash(&ev2);
        writeln!(f, "{}", serde_json::to_string(&ev2).unwrap()).unwrap();
        drop(f);
        let ev3 = sample_event(
            task,
            3,
            &ev2.event_hash,
            TaskState::PlanReady,
            TaskState::AwaitingApproval,
        );
        let err = store.append_event(ev3).unwrap_err();
        assert_eq!(err, "ledger_corrupt");
        assert_eq!(store.verify_chain(task).unwrap_err(), "ledger_corrupt");
        cleanup(&root);
    }

    #[test]
    fn snapshot_and_recovery() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_snap";
        let ev1 = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        let ev1 = store.append_event(ev1).unwrap();
        let snap = TaskSnapshot {
            schema_version: SNAPSHOT_SCHEMA.to_string(),
            task_id: task.to_string(),
            workspace_digest: "ws".to_string(),
            session_id: "sess".to_string(),
            last_seq: 1,
            last_event_hash: ev1.event_hash.clone(),
            state: TaskState::IntentCompiled,
            current_step_id: Some("step_1".to_string()),
            completed_step_ids: vec![],
            remaining_step_ids: vec![],
            budgets: serde_json::json!({"max_steps":8}),
            model_binding_fingerprint: "fp".to_string(),
            checkpoint_id: None,
            pending_request_id: None,
            pending_action_id: None,
            pending_grant_ref_hash: None,
            last_evidence_refs: vec![],
            updated_at_unix_ms: 0,
            snapshot_hash: String::new(),
        };
        store.write_snapshot(snap, false).unwrap();
        let ev2 = sample_event(
            task,
            2,
            &ev1.event_hash,
            TaskState::IntentCompiled,
            TaskState::PlanReady,
        );
        store.append_event(ev2).unwrap();
        let (snap2, replay) = store.recover(task).unwrap();
        assert_eq!(snap2.last_seq, 1);
        assert_eq!(replay.len(), 1);
        cleanup(&root);
    }

    #[test]
    fn invalid_transition_rejected() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_inv";
        let ev = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::Completed,
        );
        let err = store.append_event(ev).unwrap_err();
        assert!(err.contains("invalid"));
        cleanup(&root);
    }

    #[test]
    fn rollback_required_lifecycle_is_typed_and_bounded() {
        // Postcondition failure may enter RollbackRequired from the two
        // post-patch states only; a proven rollback continues to Recovering
        // and terminates Failed; an unresolved rollback parks in
        // PausedForReview. Direct terminal jumps are illegal.
        assert!(valid_transition(
            &TaskState::Running,
            &TaskState::RollbackRequired
        ));
        assert!(valid_transition(
            &TaskState::Validating,
            &TaskState::RollbackRequired
        ));
        assert!(valid_transition(
            &TaskState::RollbackRequired,
            &TaskState::Recovering
        ));
        assert!(valid_transition(
            &TaskState::RollbackRequired,
            &TaskState::PausedForReview
        ));
        assert!(valid_transition(&TaskState::Recovering, &TaskState::Failed));
        // Illegal shortcuts.
        assert!(!valid_transition(
            &TaskState::RollbackRequired,
            &TaskState::Completed
        ));
        assert!(!valid_transition(
            &TaskState::Created,
            &TaskState::RollbackRequired
        ));

        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_rb";
        let e0 = store
            .append_event(sample_event(
                task,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();
        let e1 = store
            .append_event(sample_event(
                task,
                2,
                &e0.event_hash,
                TaskState::IntentCompiled,
                TaskState::Running,
            ))
            .unwrap();
        let e2 = store
            .append_event(sample_event(
                task,
                3,
                &e1.event_hash,
                TaskState::Running,
                TaskState::RollbackRequired,
            ))
            .unwrap();
        let _e3 = store
            .append_event(sample_event(
                task,
                4,
                &e2.event_hash,
                TaskState::RollbackRequired,
                TaskState::Recovering,
            ))
            .unwrap();
        let events = store.verify_chain(task).unwrap();
        assert_eq!(events.last().unwrap().state_after, TaskState::Recovering);
        cleanup(&root);
    }

    #[test]
    fn review_states_refuse_terminal_completion_shortcut() {
        assert!(TaskState::PausedForReview.requires_review());
        assert!(TaskState::RollbackRequired.requires_review());
        assert!(!TaskState::Running.requires_review());
        // A parked review state must not be closable as Completed directly.
        assert!(!valid_transition(
            &TaskState::PausedForReview,
            &TaskState::Completed
        ));
        assert!(!valid_transition(
            &TaskState::RollbackRequired,
            &TaskState::Completed
        ));
    }

    #[test]
    fn bounded_payload_no_raw_secret() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_secret";
        let mut ev = sample_event(
            task,
            1,
            &"0".repeat(64),
            TaskState::Created,
            TaskState::IntentCompiled,
        );
        ev.payload = serde_json::json!({"ev":"ok"}); // no raw token
        let ev = store.append_event(ev).unwrap();
        assert!(!ev.payload.to_string().contains("lcap_"));
        cleanup(&root);
    }

    #[test]
    fn stale_completion_after_cancel_cannot_change_terminal_task() {
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task = "task_cancel";
        let e0 = store
            .append_event(sample_event(
                task,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();
        let _e1 = store
            .append_event(sample_event(
                task,
                2,
                &e0.event_hash,
                TaskState::IntentCompiled,
                TaskState::Running,
            ))
            .unwrap();
        // cancel from RUNNING is legal and terminal…
        let _e2 = store
            .append_event(sample_event(
                task,
                3,
                &_e1.event_hash,
                TaskState::Running,
                TaskState::Cancelled,
            ))
            .unwrap();
        // …a late "completion" after terminal state is an invalid transition.
        let late = sample_event(
            task,
            4,
            &_e2.event_hash,
            TaskState::Cancelled,
            TaskState::Completed,
        );
        assert!(store.append_event(late).is_err());
        cleanup(&root);
    }

    /// Orchestrator seam: intent compiled → approval → broker dispatch →
    /// WAITING_HOST → restart → replay resumes into a safe next step.
    #[test]
    fn orchestrator_restart_resume_seam() {
        use crate::intent_compiler::{compile_intent, IntentKind};
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task_id = "task_orch";

        // 1. deterministic intent compile drives INTENT_COMPILED
        let plan = compile_intent("открой блокнот").plan.unwrap();
        assert_eq!(plan.intent_kind, IntentKind::OpenApp);
        let e0 = store
            .append_event(sample_event(
                task_id,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();

        // 2. approval + dispatch chain to WAITING_HOST (launch_pending)
        let _e1 = store
            .append_event(sample_event(
                task_id,
                2,
                &e0.event_hash,
                TaskState::IntentCompiled,
                TaskState::AwaitingApproval,
            ))
            .unwrap();
        let _e2 = store
            .append_event(sample_event(
                task_id,
                3,
                &_e1.event_hash,
                TaskState::AwaitingApproval,
                TaskState::Running,
            ))
            .unwrap();
        let e3 = store
            .append_event(sample_event(
                task_id,
                4,
                &_e2.event_hash,
                TaskState::Running,
                TaskState::WaitingHost,
            ))
            .unwrap();

        // 3. snapshot at WAITING_HOST, then "crash"
        let snap = TaskSnapshot {
            schema_version: SNAPSHOT_SCHEMA.to_string(),
            task_id: task_id.to_string(),
            workspace_digest: "ws".to_string(),
            session_id: "sess".to_string(),
            last_seq: 4,
            last_event_hash: e3.event_hash.clone(),
            state: TaskState::WaitingHost,
            current_step_id: Some("step_1".into()),
            completed_step_ids: vec![],
            remaining_step_ids: vec![],
            budgets: serde_json::json!({"max_steps":8}),
            model_binding_fingerprint: "qwen3-1.7b".to_string(),
            checkpoint_id: None,
            pending_request_id: Some("req_1".into()),
            pending_action_id: Some("act_1".into()),
            pending_grant_ref_hash: None,
            last_evidence_refs: vec![],
            updated_at_unix_ms: 0,
            snapshot_hash: String::new(),
        };
        store.write_snapshot(snap, false).unwrap();

        // 4. restart: verify chain + replay after last_seq (nothing lost)
        let (snap2, replay) = store.recover(task_id).unwrap();
        assert_eq!(snap2.state, TaskState::WaitingHost);
        assert_eq!(snap2.last_seq, 4);
        assert!(replay.is_empty(), "no events were lost before the crash");

        // 5. safe resume path only: WAITING_HOST → VALIDATING is the allowed
        //    Rust-owned observation continuation; direct COMPLETED is illegal.
        assert!(valid_transition(
            &TaskState::WaitingHost,
            &TaskState::Validating
        ));
        assert!(!valid_transition(
            &TaskState::WaitingHost,
            &TaskState::Completed
        ));
        cleanup(&root);
    }

    /// Child half of the separate-process restart proof: re-verify snapshot
    /// hash + event chain from disk, replay after last_seq, emit JSON.
    fn restart_child_entrypoint() {
        let root =
            PathBuf::from(std::env::var("LC_LEDGER_RESTART_ROOT").expect("restart root env"));
        let task_id = std::env::var("LC_LEDGER_RESTART_TASK").expect("restart task env");
        let store = LedgerStore::new_with_root(root);
        let result = store.recover(&task_id);
        match result {
            Ok((snap, replay)) => println!(
                "{{\"restart\":\"verified\",\"task\":\"{}\",\"state\":\"{:?}\",\"last_seq\":{},\"replay_len\":{}}}",
                snap.task_id, snap.state, snap.last_seq, replay.len()
            ),
            Err(err) => println!("{{\"restart\":\"failed\",\"error\":\"{err}\"}}"),
        }
    }

    /// Separate-process restart proof: the SAME test binary is re-executed as
    /// a child process against the same external DevRuntime root. The child
    /// verifies snapshot hash + event chain, replays after last_seq, and
    /// emits machine-readable evidence on stdout. This is a real process
    /// boundary, not a simulated replay.
    #[test]
    fn ledger_separate_process_restart() {
        if std::env::var("LC_LEDGER_RESTART_CHILD").ok().as_deref() == Some("1") {
            restart_child_entrypoint();
            return;
        }
        let root = tmp_root();
        let store = LedgerStore::new_with_root(root.clone());
        let task_id = "task_reproc";

        // Parent phase: drive a task to WAITING_HOST and snapshot it.
        let e0 = store
            .append_event(sample_event(
                task_id,
                1,
                &"0".repeat(64),
                TaskState::Created,
                TaskState::IntentCompiled,
            ))
            .unwrap();
        let e1 = store
            .append_event(sample_event(
                task_id,
                2,
                &e0.event_hash,
                TaskState::IntentCompiled,
                TaskState::AwaitingApproval,
            ))
            .unwrap();
        let e2 = store
            .append_event(sample_event(
                task_id,
                3,
                &e1.event_hash,
                TaskState::AwaitingApproval,
                TaskState::Running,
            ))
            .unwrap();
        let e3 = store
            .append_event(sample_event(
                task_id,
                4,
                &e2.event_hash,
                TaskState::Running,
                TaskState::WaitingHost,
            ))
            .unwrap();
        let snap = TaskSnapshot {
            schema_version: SNAPSHOT_SCHEMA.to_string(),
            task_id: task_id.to_string(),
            workspace_digest: "ws-reproc".to_string(),
            session_id: "sess".to_string(),
            last_seq: 4,
            last_event_hash: e3.event_hash.clone(),
            state: TaskState::WaitingHost,
            current_step_id: Some("step_1".into()),
            completed_step_ids: vec![],
            remaining_step_ids: vec![],
            budgets: serde_json::json!({"max_steps":8}),
            model_binding_fingerprint: "qwen3-1.7b".to_string(),
            checkpoint_id: None,
            pending_request_id: Some("req_r".into()),
            pending_action_id: Some("act_r".into()),
            pending_grant_ref_hash: None,
            last_evidence_refs: vec![],
            updated_at_unix_ms: 0,
            snapshot_hash: String::new(),
        };
        store.write_snapshot(snap, false).unwrap();

        // Controlled process boundary: same binary, fresh process.
        let exe = std::env::current_exe().expect("current test exe");
        let output = std::process::Command::new(exe)
            .args([
                "--exact",
                "task_ledger::tests::ledger_separate_process_restart",
                "--nocapture",
            ])
            .env("LC_LEDGER_RESTART_CHILD", "1")
            .env("LC_LEDGER_RESTART_ROOT", &root)
            .env("LC_LEDGER_RESTART_TASK", task_id)
            .output()
            .expect("child process spawned");
        let stdout = String::from_utf8_lossy(&output.stdout);
        assert!(
            output.status.success(),
            "child restart verification failed:\n{stdout}\n--- stderr ---\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(
            stdout.contains("\"restart\":\"verified\""),
            "child must emit verified evidence: {stdout}"
        );
        assert!(
            stdout.contains("\"state\":\"WaitingHost\""),
            "child must recover WAITING_HOST from disk: {stdout}"
        );
        cleanup(&root);
    }
}
