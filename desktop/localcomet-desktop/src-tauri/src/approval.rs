use sha2::{Digest, Sha256};
use std::collections::{HashMap, VecDeque};
use std::time::{Duration, Instant};
use subtle::ConstantTimeEq;

const TOKEN_PREFIX: &str = "lcap_";
const APPROVAL_ID_PREFIX: &str = "appr_";
const CALL_ID_PREFIX: &str = "call_";
const MAX_ACTIVE_TOKENS: usize = 64;
const DEFAULT_TTL: Duration = Duration::from_secs(300);
const GRANT_TTL: Duration = Duration::from_secs(30);
const MAX_CONSUMED_TOMBSTONES: usize = 4096;
const TOMBSTONE_TTL: Duration = Duration::from_secs(300);
const FRONTEND_APPROVAL_PROMPT_TTL: Duration = Duration::from_secs(120);
const MAX_IDEMPOTENCY_PENDING: usize = 128;
const MAX_IDEMPOTENCY_COMPLETED: usize = 512;
const IDEMPOTENCY_PENDING_TTL: Duration = Duration::from_secs(30);
const IDEMPOTENCY_COMPLETED_TTL: Duration = Duration::from_secs(300);

pub const NON_WORKSPACE_APPROVAL_SCOPE: &str = "localcomet://approval-scope/non-workspace";

fn approval_trace(message: &str) {
    if std::env::var("LOCALCOMET_APPROVAL_TRACE").ok().as_deref() == Some("1") {
        eprintln!("[localcomet.approval] {message}");
    }
}
#[allow(dead_code)]
pub const NON_SESSION_APPROVAL_SCOPE: &str = "localcomet://approval-scope/non-session";

#[derive(Clone, Debug)]
pub struct ApprovalScope {
    pub tool: String,
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    pub risk_level: RiskLevel,
    pub command_family: CommandFamily,
    pub approval_id: String,
    pub call_id: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RiskLevel {
    ReadOnly,
    Guarded,
    Dangerous,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CommandFamily {
    ArtifactDownload,
    ArtifactRemove,
    RuntimeStart,
    RuntimeStop,
    ModelBindingSet,
    ToolFilesystemRead,
    ToolFilesystemWrite,
    ToolFilesystemDelete,
    ComputerUse,
    SkillsInvoke,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApprovalDecision {
    Approve,
    Reject,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApprovalPromptError {
    Unavailable(String),
}

pub trait ApprovalPrompt: Send + Sync {
    fn decide(
        &self,
        descriptor: &ApprovalDescriptor,
    ) -> Result<ApprovalDecision, ApprovalPromptError>;
}

pub struct FrontendApprovalDispatcher {
    app: tauri::AppHandle,
    pending: std::sync::Mutex<
        std::collections::HashMap<String, std::sync::mpsc::Sender<ApprovalDecision>>,
    >,
}

impl FrontendApprovalDispatcher {
    pub fn new(app: tauri::AppHandle) -> Self {
        Self {
            app,
            pending: std::sync::Mutex::new(std::collections::HashMap::new()),
        }
    }

    pub fn resolve(&self, request_id: &str, decision: ApprovalDecision) -> Result<(), String> {
        let mut pending = self.pending.lock().map_err(|_| "poisoned")?;
        if let Some(tx) = pending.remove(request_id) {
            let _ = tx.send(decision);
            Ok(())
        } else {
            Err("request not found".into())
        }
    }
}

pub struct FrontendApprovalPrompt {
    pub dispatcher: std::sync::Arc<FrontendApprovalDispatcher>,
}

#[derive(Clone, serde::Serialize)]
struct ApprovalRequestPayload {
    pub request_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_request_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_action_id: Option<String>,
    pub input_digest: String,
    pub expires_at_unix_ms: u64,
    pub tool: String,
    pub risk_level: String,
    pub target_summary: String,
    pub side_effect_category: String,
    pub destructive: bool,
}

impl ApprovalPrompt for FrontendApprovalPrompt {
    fn decide(
        &self,
        descriptor: &ApprovalDescriptor,
    ) -> Result<ApprovalDecision, ApprovalPromptError> {
        let request_id = generate_approval_id();
        approval_trace(&format!(
            "prompt.begin tool={} risk={:?} request_id={}",
            descriptor.tool, descriptor.risk_level, request_id
        ));
        let (tx, rx) = std::sync::mpsc::channel();

        {
            let mut pending = self.dispatcher.pending.lock().expect("poisoned");
            pending.insert(request_id.clone(), tx);
        }

        let payload = ApprovalRequestPayload {
            request_id: request_id.clone(),
            model_request_id: descriptor.model_request_id.clone(),
            model_action_id: descriptor.model_action_id.clone(),
            input_digest: hex_encode(&descriptor.input_digest),
            expires_at_unix_ms: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .saturating_add(FRONTEND_APPROVAL_PROMPT_TTL)
                .as_millis() as u64,
            tool: descriptor.tool.clone(),
            risk_level: match descriptor.risk_level {
                RiskLevel::ReadOnly => "read_only",
                RiskLevel::Guarded => "guarded",
                RiskLevel::Dangerous => "dangerous",
            }
            .to_string(),
            target_summary: descriptor.target_summary.clone(),
            side_effect_category: descriptor.side_effect_category.clone(),
            destructive: descriptor.destructive,
        };

        use tauri::Emitter;
        if let Err(e) = self.dispatcher.app.emit("request_tool_approval", payload) {
            approval_trace(&format!(
                "prompt.emit_failed request_id={request_id} error={e}"
            ));
            return Err(ApprovalPromptError::Unavailable(format!(
                "Failed to emit to frontend: {e}"
            )));
        }
        approval_trace(&format!("prompt.emitted request_id={request_id}"));

        match rx.recv_timeout(FRONTEND_APPROVAL_PROMPT_TTL) {
            Ok(ApprovalDecision::Approve) => {
                approval_trace(&format!("prompt.decision=approve request_id={request_id}"));
                Ok(ApprovalDecision::Approve)
            }
            Ok(ApprovalDecision::Reject) => {
                approval_trace(&format!("prompt.decision=reject request_id={request_id}"));
                Ok(ApprovalDecision::Reject)
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                approval_trace(&format!("prompt.decision=timeout request_id={request_id}"));
                Ok(ApprovalDecision::Reject)
            }
            Err(_) => {
                approval_trace(&format!("prompt.disconnected request_id={request_id}"));
                Err(ApprovalPromptError::Unavailable(
                    "Frontend disconnected".into(),
                ))
            }
        }
    }
}

#[allow(dead_code)]
pub struct ScriptedApprovalPrompt {
    pub decision: ApprovalDecision,
}

impl ApprovalPrompt for ScriptedApprovalPrompt {
    fn decide(
        &self,
        _descriptor: &ApprovalDescriptor,
    ) -> Result<ApprovalDecision, ApprovalPromptError> {
        Ok(self.decision)
    }
}

#[derive(Debug, Clone)]
pub struct ApprovalDescriptor {
    pub tool: String,
    pub command_family: CommandFamily,
    pub risk_level: RiskLevel,
    pub input_digest: [u8; 32],
    pub model_request_id: Option<String>,
    pub model_action_id: Option<String>,
    pub target_summary: String,
    pub side_effect_category: String,
    pub destructive: bool,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ApprovalEnvelope {
    pub token: String,
    pub approval_id: String,
    pub call_id: String,
    pub tool: String,
    pub risk_level: RiskLevel,
    pub command_family: CommandFamily,
    pub expires_at_unix_ms: u64,
}

pub fn command_family_for_tool(tool: &str) -> Option<CommandFamily> {
    match tool {
        "artifact.download" => Some(CommandFamily::ArtifactDownload),
        "artifact.remove" => Some(CommandFamily::ArtifactRemove),
        "runtime.start" => Some(CommandFamily::RuntimeStart),
        "runtime.stop" => Some(CommandFamily::RuntimeStop),
        "model.binding.set" => Some(CommandFamily::ModelBindingSet),
        "files.read" | "files.list" => Some(CommandFamily::ToolFilesystemRead),
        "files.write" | "files.create_folder" => Some(CommandFamily::ToolFilesystemWrite),
        "checkpoint.restore_files" | "checkpoint.restore_task" => {
            Some(CommandFamily::ToolFilesystemWrite)
        }
        "files.delete" => Some(CommandFamily::ToolFilesystemDelete),
        "computer_use" => Some(CommandFamily::ComputerUse),
        "skills.invoke" => Some(CommandFamily::SkillsInvoke),
        "import_custom_model" => Some(CommandFamily::ArtifactDownload),
        _ => None,
    }
}

#[derive(Debug)]
struct ApprovalEntry {
    scope: ApprovalScope,
    nonce: [u8; 16],
    issued_at: Instant,
    ttl: Duration,
}

#[derive(Debug)]
pub enum ApprovalError {
    RegistryFull,
    TokenNotFound,
    ToolMismatch,
    InputDigestMismatch,
    WorkspaceMismatch,
    SessionMismatch,
    ApprovalIdMismatch,
    CallIdMismatch,
    RiskMismatch,
    FamilyMismatch,
    Expired,
    AlreadyConsumed,
    InvalidToken,
    Rejected,
    PromptUnavailable,
    IdempotencyRegistryFull,
    IdempotencyPending,
    DuplicateLogicalCall,
}

impl std::fmt::Display for ApprovalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::RegistryFull => write!(f, "approval registry is full"),
            Self::TokenNotFound => write!(f, "approval token not found"),
            Self::ToolMismatch => write!(f, "approval tool mismatch"),
            Self::InputDigestMismatch => write!(f, "approval input digest mismatch"),
            Self::WorkspaceMismatch => write!(f, "approval workspace mismatch"),
            Self::SessionMismatch => write!(f, "approval session mismatch"),
            Self::ApprovalIdMismatch => write!(f, "approval id mismatch"),
            Self::CallIdMismatch => write!(f, "approval call id mismatch"),
            Self::RiskMismatch => write!(f, "approval risk level mismatch"),
            Self::FamilyMismatch => write!(f, "approval command family mismatch"),
            Self::Expired => write!(f, "approval token expired"),
            Self::AlreadyConsumed => write!(f, "approval token already consumed"),
            Self::InvalidToken => write!(f, "approval token is invalid"),
            Self::Rejected => write!(f, "approval was rejected by the user"),
            Self::PromptUnavailable => write!(f, "trusted approval prompt is unavailable"),
            Self::IdempotencyRegistryFull => write!(f, "logical-call idempotency registry is full"),
            Self::IdempotencyPending => write!(f, "logical-call is already in flight"),
            Self::DuplicateLogicalCall => write!(f, "logical-call has already completed"),
        }
    }
}

pub struct ApprovalRegistry {
    entries: HashMap<String, ApprovalEntry>,
    consumed: HashMap<[u8; 32], Instant>,
    consumed_order: VecDeque<[u8; 32]>,
    idempotency: IdempotencyRegistry,
    session_id: String,
}

impl ApprovalRegistry {
    pub fn new() -> Self {
        let mut session_bytes = [0u8; 16];
        getrandom::getrandom(&mut session_bytes)
            .expect("OS CSPRNG unavailable for session generation");
        Self {
            entries: HashMap::new(),
            consumed: HashMap::new(),
            consumed_order: VecDeque::new(),
            idempotency: IdempotencyRegistry::new(),
            session_id: hex_encode(&session_bytes),
        }
    }

    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    /// Issue a token with a freshly generated random identity. Retained as the
    /// general issuance API; the command layer uses `issue_with_token` so that
    /// approval_id/call_id can be derived from the token itself.
    #[allow(dead_code)]
    pub fn issue(&mut self, scope: ApprovalScope) -> Result<String, ApprovalError> {
        self.issue_inner(generate_approval_token(), scope, DEFAULT_TTL)
    }

    #[allow(dead_code)]
    pub fn issue_with_token(
        &mut self,
        token: String,
        scope: ApprovalScope,
    ) -> Result<String, ApprovalError> {
        self.issue_inner(token, scope, DEFAULT_TTL)
    }

    /// Issue a scoped envelope for read-only/guarded operations whose explicit
    /// UI action already established the user intent. Dangerous operations
    /// must continue through `request_with_prompt` before reaching this path.
    pub fn issue_without_prompt(
        &mut self,
        scope: ApprovalScope,
        descriptor: &ApprovalDescriptor,
    ) -> Result<ApprovalEnvelope, ApprovalError> {
        let token = generate_token();
        let approval_id = generate_approval_id();
        let call_id = generate_call_id();
        let scope = ApprovalScope {
            approval_id: approval_id.clone(),
            call_id: call_id.clone(),
            ..scope
        };
        self.issue_with_token(token.clone(), scope)?;
        let expires_at_unix_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
            + DEFAULT_TTL.as_millis() as u64;
        Ok(ApprovalEnvelope {
            token,
            approval_id,
            call_id,
            tool: descriptor.tool.clone(),
            risk_level: descriptor.risk_level,
            command_family: descriptor.command_family,
            expires_at_unix_ms,
        })
    }

    #[allow(dead_code)]
    pub fn request_with_prompt(
        &mut self,
        scope: ApprovalScope,
        descriptor: &ApprovalDescriptor,
        prompt: &dyn ApprovalPrompt,
    ) -> Result<ApprovalEnvelope, ApprovalError> {
        match prompt.decide(descriptor) {
            Err(_) => Err(ApprovalError::PromptUnavailable),
            Ok(ApprovalDecision::Reject) => Err(ApprovalError::Rejected),
            Ok(ApprovalDecision::Approve) => {
                let token = generate_token();
                let approval_id = generate_approval_id();
                let call_id = generate_call_id();
                let scope = ApprovalScope {
                    approval_id: approval_id.clone(),
                    call_id: call_id.clone(),
                    ..scope
                };
                self.issue_inner(token.clone(), scope, DEFAULT_TTL)?;
                let expires_at_unix_ms = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as u64
                    + DEFAULT_TTL.as_millis() as u64;
                Ok(ApprovalEnvelope {
                    token,
                    approval_id,
                    call_id,
                    tool: descriptor.tool.clone(),
                    risk_level: descriptor.risk_level,
                    command_family: descriptor.command_family,
                    expires_at_unix_ms,
                })
            }
        }
    }

    fn issue_inner(
        &mut self,
        token: String,
        scope: ApprovalScope,
        ttl: Duration,
    ) -> Result<String, ApprovalError> {
        self.entries
            .retain(|_, entry| entry.issued_at.elapsed() <= entry.ttl);
        self.sweep_consumed();

        if self.entries.len() >= MAX_ACTIVE_TOKENS {
            return Err(ApprovalError::RegistryFull);
        }

        let mut nonce = [0u8; 16];
        getrandom::getrandom(&mut nonce).expect("OS CSPRNG unavailable for nonce generation");

        self.entries.insert(
            token.clone(),
            ApprovalEntry {
                scope,
                nonce,
                issued_at: Instant::now(),
                ttl,
            },
        );

        Ok(token)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn execute_approved(
        &mut self,
        token: &str,
        tool: &str,
        input_digest: &[u8; 32],
        workspace: &str,
        approval_id: &str,
        call_id: &str,
        risk_level: RiskLevel,
        command_family: CommandFamily,
    ) -> Result<ExecutionGrant, ApprovalError> {
        if !validate_token_syntax(token) {
            return Err(ApprovalError::InvalidToken);
        }

        if !validate_approval_id_syntax(approval_id) {
            return Err(ApprovalError::ApprovalIdMismatch);
        }

        if !validate_call_id_syntax(call_id) {
            return Err(ApprovalError::CallIdMismatch);
        }

        let token_digest = token_tombstone_digest(token);
        if let Some(consumed_at) = self.consumed.get(&token_digest) {
            if consumed_at.elapsed() <= TOMBSTONE_TTL {
                return Err(ApprovalError::AlreadyConsumed);
            }
            self.consumed.remove(&token_digest);
        }

        let expired = match self.entries.get(token) {
            None => return Err(ApprovalError::TokenNotFound),
            Some(entry) => entry.issued_at.elapsed() > entry.ttl,
        };
        if expired {
            self.entries.remove(token);
            return Err(ApprovalError::Expired);
        }

        let entry = self
            .entries
            .get(token)
            .expect("token presence checked above");
        let scope = &entry.scope;

        if scope.tool.as_bytes().ct_eq(tool.as_bytes()).unwrap_u8() != 1 {
            return Err(ApprovalError::ToolMismatch);
        }

        if scope.input_digest.ct_eq(input_digest).unwrap_u8() != 1 {
            return Err(ApprovalError::InputDigestMismatch);
        }

        if scope
            .workspace
            .as_bytes()
            .ct_eq(workspace.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::WorkspaceMismatch);
        }

        if scope
            .session
            .as_bytes()
            .ct_eq(self.session_id.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::SessionMismatch);
        }

        if scope
            .approval_id
            .as_bytes()
            .ct_eq(approval_id.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::ApprovalIdMismatch);
        }

        if scope
            .call_id
            .as_bytes()
            .ct_eq(call_id.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::CallIdMismatch);
        }

        if scope.risk_level != risk_level {
            return Err(ApprovalError::RiskMismatch);
        }

        if scope.command_family != command_family {
            return Err(ApprovalError::FamilyMismatch);
        }

        let entry = self
            .entries
            .remove(token)
            .expect("token presence checked above");
        self.record_consumed(token_digest);

        let mut grant_id = [0u8; 16];
        getrandom::getrandom(&mut grant_id).expect("OS CSPRNG unavailable for grant generation");

        Ok(ExecutionGrant {
            grant_id: hex_encode(&grant_id),
            tool: entry.scope.tool.clone(),
            input_digest: *input_digest,
            workspace: workspace.to_owned(),
            session: self.session_id.clone(),
            nonce: entry.nonce,
            valid_until: Instant::now() + GRANT_TTL,
            approval_id: entry.scope.approval_id.clone(),
            call_id: entry.scope.call_id.clone(),
        })
    }

    pub fn invalidate_workspace(&mut self, old_workspace: &str) {
        self.entries
            .retain(|_, entry| entry.scope.workspace != old_workspace);
    }

    fn record_consumed(&mut self, token_digest: [u8; 32]) {
        self.consumed.insert(token_digest, Instant::now());
        self.consumed_order.push_back(token_digest);
        if self.consumed.len() > MAX_CONSUMED_TOMBSTONES {
            if let Some(oldest) = self.consumed_order.pop_front() {
                self.consumed.remove(&oldest);
            }
        }
    }

    fn sweep_consumed(&mut self) {
        self.consumed
            .retain(|_, consumed_at| consumed_at.elapsed() <= TOMBSTONE_TTL);
        self.consumed_order
            .retain(|digest| self.consumed.contains_key(digest));
    }

    pub fn begin_idempotent_call(
        &mut self,
        key: &[u8; 32],
    ) -> Result<IdempotencyReceipt, ApprovalError> {
        self.idempotency.begin(key)
    }

    pub fn complete_idempotent_call(
        &mut self,
        receipt: IdempotencyReceipt,
        outcome: IdempotencyOutcome,
    ) {
        self.idempotency.complete(receipt, outcome);
    }

    /// Invalidate every active token (e.g. on session reset / restart).
    /// Public API; not invoked internally yet.
    #[allow(dead_code)]
    pub fn invalidate_all(&mut self) {
        self.entries.clear();
    }

    /// Number of active (not yet consumed/expired) tokens. Used by tests and
    /// intended for monitoring/diagnostics.
    #[allow(dead_code)]
    pub fn active_count(&self) -> usize {
        self.entries.len()
    }

    #[cfg(test)]
    fn issue_backdated(
        &mut self,
        scope: ApprovalScope,
        ttl: Duration,
        backdate: Duration,
    ) -> String {
        let mut token_bytes = [0u8; 32];
        getrandom::getrandom(&mut token_bytes).expect("OS CSPRNG unavailable for token generation");
        let mut nonce = [0u8; 16];
        getrandom::getrandom(&mut nonce).expect("OS CSPRNG unavailable for nonce generation");
        let token_string = format!("{}{}", TOKEN_PREFIX, hex_encode(&token_bytes));
        self.entries.insert(
            token_string.clone(),
            ApprovalEntry {
                scope,
                nonce,
                issued_at: Instant::now() - backdate,
                ttl,
            },
        );
        token_string
    }

    #[cfg(test)]
    fn stored_scope(&self, token: &str) -> Option<&ApprovalScope> {
        self.entries.get(token).map(|entry| &entry.scope)
    }

    #[cfg(test)]
    fn consumed_count(&self) -> usize {
        self.consumed.len()
    }

    #[cfg(test)]
    fn insert_backdated_tombstone(&mut self, token: &str, age: Duration) {
        let digest = token_tombstone_digest(token);
        self.consumed.insert(digest, Instant::now() - age);
        self.consumed_order.push_back(digest);
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IdempotencyOutcome {
    Completed,
    Failed,
}

#[derive(Debug, Clone)]
pub struct IdempotencyReceipt {
    key: [u8; 32],
}

#[derive(Debug, Clone)]
pub struct LogicalCallIdentity {
    pub tool: String,
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    pub approval_id: String,
    pub call_id: String,
    pub risk_level: RiskLevel,
    pub command_family: CommandFamily,
}

#[derive(Debug)]
struct IdempotencyEntry {
    state: IdempotencyState,
    created_at: Instant,
    ttl: Duration,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum IdempotencyState {
    Pending,
    Completed,
}

#[derive(Debug)]
pub struct IdempotencyRegistry {
    entries: HashMap<[u8; 32], IdempotencyEntry>,
    order: VecDeque<[u8; 32]>,
}

impl IdempotencyRegistry {
    pub fn new() -> Self {
        Self {
            entries: HashMap::new(),
            order: VecDeque::new(),
        }
    }

    pub fn make_key(identity: &LogicalCallIdentity) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(identity.tool.as_bytes());
        hasher.update(identity.input_digest);
        hasher.update(identity.workspace.as_bytes());
        hasher.update(identity.session.as_bytes());
        hasher.update(identity.approval_id.as_bytes());
        hasher.update(identity.call_id.as_bytes());
        hasher.update([identity.risk_level as u8]);
        hasher.update([identity.command_family as u8]);
        hasher.finalize().into()
    }

    pub fn begin(&mut self, key: &[u8; 32]) -> Result<IdempotencyReceipt, ApprovalError> {
        self.sweep();
        if let Some(entry) = self.entries.get(key) {
            return match entry.state {
                IdempotencyState::Pending => Err(ApprovalError::IdempotencyPending),
                IdempotencyState::Completed => Err(ApprovalError::DuplicateLogicalCall),
            };
        }
        if self.entries.len() >= MAX_IDEMPOTENCY_PENDING {
            return Err(ApprovalError::IdempotencyRegistryFull);
        }
        self.entries.insert(
            *key,
            IdempotencyEntry {
                state: IdempotencyState::Pending,
                created_at: Instant::now(),
                ttl: IDEMPOTENCY_PENDING_TTL,
            },
        );
        self.order.push_back(*key);
        Ok(IdempotencyReceipt { key: *key })
    }

    pub fn complete(&mut self, receipt: IdempotencyReceipt, outcome: IdempotencyOutcome) {
        if let Some(entry) = self.entries.get_mut(&receipt.key) {
            entry.state = match outcome {
                IdempotencyOutcome::Completed => IdempotencyState::Completed,
                IdempotencyOutcome::Failed => IdempotencyState::Pending,
            };
            entry.created_at = Instant::now();
            entry.ttl = match outcome {
                IdempotencyOutcome::Completed => IDEMPOTENCY_COMPLETED_TTL,
                IdempotencyOutcome::Failed => IDEMPOTENCY_PENDING_TTL,
            };
            if matches!(outcome, IdempotencyOutcome::Completed)
                && self.completed_len() > MAX_IDEMPOTENCY_COMPLETED
            {
                self.trim_completed();
            }
        }
    }

    fn sweep(&mut self) {
        self.entries
            .retain(|_, entry| entry.created_at.elapsed() <= entry.ttl);
        self.order.retain(|key| self.entries.contains_key(key));
    }

    fn completed_len(&self) -> usize {
        self.entries
            .values()
            .filter(|entry| matches!(entry.state, IdempotencyState::Completed))
            .count()
    }

    fn trim_completed(&mut self) {
        self.order.retain(|key| match self.entries.get(key) {
            Some(entry)
                if matches!(entry.state, IdempotencyState::Completed)
                    && entry.created_at.elapsed() > IDEMPOTENCY_COMPLETED_TTL =>
            {
                false
            }
            Some(_) => true,
            None => false,
        });
    }
}

#[derive(Clone, Debug)]
pub struct ExecutionGrant {
    pub grant_id: String,
    pub tool: String,
    // input_digest and nonce are part of the grant's authorization material.
    // They are consumed by a downstream tool-execution path when one exists
    // (the desktop sidecar currently performs no filesystem tool execution);
    // retained so the grant is self-describing and verifiable at that boundary.
    #[allow(dead_code)]
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    #[allow(dead_code)]
    pub nonce: [u8; 16],
    pub valid_until: Instant,
    #[allow(dead_code)]
    pub approval_id: String,
    #[allow(dead_code)]
    pub call_id: String,
}

impl ExecutionGrant {
    pub fn is_expired(&self) -> bool {
        Instant::now() >= self.valid_until
    }

    pub fn input_digest_hex(&self) -> String {
        hex_encode(&self.input_digest)
    }

    pub fn expires_at_unix_ms(&self) -> u64 {
        let remaining = self.valid_until.saturating_duration_since(Instant::now());
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
            + remaining.as_millis() as u64
    }
}

pub fn canonical_input_digest(input: &serde_json::Value) -> [u8; 32] {
    let canonical = canonicalize_json(input);
    let mut hasher = Sha256::new();
    hasher.update(canonical.as_bytes());
    hasher.finalize().into()
}

fn token_tombstone_digest(token: &str) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(token.as_bytes());
    hasher.finalize().into()
}

pub fn validate_token_syntax(token: &str) -> bool {
    if token.len() != 69 {
        return false;
    }
    if !token.starts_with(TOKEN_PREFIX) {
        return false;
    }
    let body = &token[TOKEN_PREFIX.len()..];
    body.chars()
        .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

pub fn validate_approval_id_syntax(id: &str) -> bool {
    id.len() == 37
        && id.starts_with(APPROVAL_ID_PREFIX)
        && id[5..]
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

pub fn validate_call_id_syntax(id: &str) -> bool {
    id.len() == 37
        && id.starts_with(CALL_ID_PREFIX)
        && id[5..]
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

fn canonicalize_json(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "null".to_owned(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => format!("\"{}\"", escape_json_string(s)),
        serde_json::Value::Array(arr) => {
            let items: Vec<String> = arr.iter().map(canonicalize_json).collect();
            format!("[{}]", items.join(","))
        }
        serde_json::Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let pairs: Vec<String> = keys
                .iter()
                .map(|k| {
                    format!(
                        "\"{}\":{}",
                        escape_json_string(k),
                        canonicalize_json(&map[*k])
                    )
                })
                .collect();
            format!("{{{}}}", pairs.join(","))
        }
    }
}

fn escape_json_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

pub(crate) fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes).expect("CSPRNG");
    format!("lcap_{}", hex_encode(&bytes))
}

pub fn generate_approval_id() -> String {
    let mut bytes = [0u8; 16];
    getrandom::getrandom(&mut bytes).expect("CSPRNG");
    format!("appr_{}", hex_encode(&bytes))
}

pub fn generate_call_id() -> String {
    let mut bytes = [0u8; 16];
    getrandom::getrandom(&mut bytes).expect("CSPRNG");
    format!("call_{}", hex_encode(&bytes))
}

pub fn generate_approval_token() -> String {
    generate_token()
}

#[cfg(test)]
#[path = "approval_tests.rs"]
mod tests;
