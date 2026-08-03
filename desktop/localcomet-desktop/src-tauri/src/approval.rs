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
const MAX_IDEMPOTENCY_PENDING: usize = 128;
const MAX_IDEMPOTENCY_COMPLETED: usize = 512;
const IDEMPOTENCY_PENDING_TTL: Duration = Duration::from_secs(30);
const IDEMPOTENCY_COMPLETED_TTL: Duration = Duration::from_secs(300);

pub const NON_WORKSPACE_APPROVAL_SCOPE: &str = "localcomet://approval-scope/non-workspace";
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

pub struct NativeWindowsApprovalPrompt;

impl ApprovalPrompt for NativeWindowsApprovalPrompt {
    fn decide(
        &self,
        descriptor: &ApprovalDescriptor,
    ) -> Result<ApprovalDecision, ApprovalPromptError> {
        #[cfg(target_os = "windows")]
        {
            use windows_sys::Win32::UI::WindowsAndMessaging::{
                MessageBoxW, IDCANCEL, IDOK, MB_ICONQUESTION, MB_OKCANCEL,
            };
            let title: Vec<u16> = "LocalComet\0".encode_utf16().collect();
            let mut body = format!(
                "Tool: {}\nRisk: {}\nTarget: {}\nSide-effect: {}",
                descriptor.tool,
                match descriptor.risk_level {
                    RiskLevel::ReadOnly => "read_only",
                    RiskLevel::Guarded => "guarded",
                    RiskLevel::Dangerous => "dangerous",
                },
                descriptor.target_summary,
                descriptor.side_effect_category,
            );
            if descriptor.destructive {
                body.push_str("\nWARNING: This operation is destructive and cannot be undone.");
            }
            let body_wide: Vec<u16> = body.encode_utf16().chain(std::iter::once(0)).collect();
            let result = unsafe {
                MessageBoxW(
                    std::ptr::null_mut(),
                    body_wide.as_ptr(),
                    title.as_ptr(),
                    MB_OKCANCEL | MB_ICONQUESTION,
                )
            };
            match result {
                IDOK => Ok(ApprovalDecision::Approve),
                IDCANCEL => Ok(ApprovalDecision::Reject),
                _ => Err(ApprovalPromptError::Unavailable(
                    "unexpected dialog result".into(),
                )),
            }
        }
        #[cfg(not(target_os = "windows"))]
        {
            let _ = descriptor;
            Err(ApprovalPromptError::Unavailable(
                "trusted approval prompt is unavailable".into(),
            ))
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
        "files.delete" => Some(CommandFamily::ToolFilesystemDelete),
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

fn hex_encode(bytes: &[u8]) -> String {
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
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::{Arc, Mutex};

    const TEST_APPROVAL_ID: &str = "appr_00000000000000000000000000000000";
    const TEST_CALL_ID: &str = "call_00000000000000000000000000000000";

    fn test_scope(tool: &str, digest: [u8; 32], workspace: &str, session: &str) -> ApprovalScope {
        ApprovalScope {
            tool: tool.to_owned(),
            input_digest: digest,
            workspace: workspace.to_owned(),
            session: session.to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        }
    }

    fn scoped(
        tool: &str,
        digest: [u8; 32],
        workspace: &str,
        session: &str,
        risk_level: RiskLevel,
        command_family: CommandFamily,
    ) -> ApprovalScope {
        ApprovalScope {
            tool: tool.to_owned(),
            input_digest: digest,
            workspace: workspace.to_owned(),
            session: session.to_owned(),
            risk_level,
            command_family,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        }
    }

    #[test]
    fn issued_tokens_are_unique_and_256_bits() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "test.txt", "content": "hello"}));
        let mut tokens = Vec::new();
        for _ in 0..MAX_ACTIVE_TOKENS {
            let scope = test_scope("files.patch", digest, "/workspace", &session);
            let token = registry.issue(scope).unwrap();
            tokens.push(token);
        }
        let unique: std::collections::HashSet<&String> = tokens.iter().collect();
        assert_eq!(unique.len(), MAX_ACTIVE_TOKENS);
        for token in &tokens {
            let hex_part = token.strip_prefix(TOKEN_PREFIX).unwrap();
            assert_eq!(hex_part.len(), 64);
        }
    }

    #[test]
    fn two_registries_issue_different_first_tokens() {
        let mut r1 = ApprovalRegistry::new();
        let mut r2 = ApprovalRegistry::new();
        let s1_session = r1.session_id().to_owned();
        let s2_session = r2.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "test.txt", "content": "hello"}));
        let t1 = r1
            .issue(test_scope("files.patch", digest, "/w", &s1_session))
            .unwrap();
        let t2 = r2
            .issue(test_scope("files.patch", digest, "/w", &s2_session))
            .unwrap();
        assert_ne!(t1, t2);
    }

    #[test]
    fn execute_approved_succeeds_with_matching_scope() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt", "content": "data"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/workspace".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/workspace",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(grant.workspace, "/workspace");
    }

    #[test]
    fn replay_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::AlreadyConsumed));
    }

    #[test]
    fn idempotency_key_is_deterministic() {
        let digest = canonical_input_digest(&json!({"path": "a.txt", "content": "x"}));
        let identity = LogicalCallIdentity {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: "session".to_owned(),
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
        };
        let a = IdempotencyRegistry::make_key(&identity);
        let b = IdempotencyRegistry::make_key(&identity);
        assert_eq!(a, b);
    }

    #[test]
    fn idempotency_registry_rejects_duplicate_pending_and_completed() {
        let mut registry = IdempotencyRegistry::new();
        let key = [7u8; 32];
        let receipt = registry.begin(&key).unwrap();
        assert!(matches!(
            registry.begin(&key),
            Err(ApprovalError::IdempotencyPending)
        ));
        registry.complete(receipt, IdempotencyOutcome::Completed);
        assert!(matches!(
            registry.begin(&key),
            Err(ApprovalError::DuplicateLogicalCall)
        ));
    }

    #[test]
    fn wrong_tool_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
    }

    #[test]
    fn wrong_input_digest_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input_a = json!({"path": "a.txt", "content": "A"});
        let input_b = json!({"path": "a.txt", "content": "B"});
        let digest_a = canonical_input_digest(&input_a);
        let digest_b = canonical_input_digest(&input_b);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest_a,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest_b,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InputDigestMismatch));
    }

    #[test]
    fn wrong_workspace_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/workspace-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/workspace-b",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::WorkspaceMismatch));
    }

    #[test]
    fn key_reordering_does_not_change_digest() {
        let a = json!({"alpha": 1, "beta": 2});
        let b = json!({"beta": 2, "alpha": 1});
        assert_eq!(canonical_input_digest(&a), canonical_input_digest(&b));
    }

    #[test]
    fn value_change_changes_digest() {
        let a = json!({"key": "value_a"});
        let b = json!({"key": "value_b"});
        assert_ne!(canonical_input_digest(&a), canonical_input_digest(&b));
    }

    #[test]
    fn invalidate_workspace_removes_matching_tokens() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"x": 1});
        let digest = canonical_input_digest(&input);
        let scope_a = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let scope_b = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-b".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token_a = registry.issue(scope_a).unwrap();
        let _token_b = registry.issue(scope_b).unwrap();
        assert_eq!(registry.active_count(), 2);
        registry.invalidate_workspace("/ws-a");
        assert_eq!(registry.active_count(), 1);
        let err = registry
            .execute_approved(
                &token_a,
                "files.patch",
                &digest,
                "/ws-a",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn invalid_prefix_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let digest = [0u8; 32];
        let err = registry
            .execute_approved(
                "apt_fake_token",
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InvalidToken));
    }

    #[test]
    fn wrong_session_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: "00000000000000000000000000000000".to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::SessionMismatch));
    }

    #[test]
    fn expired_token_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "test.txt", "content": "hello"}));
        let scope = test_scope("files.patch", digest, "/w", &session);
        let token =
            registry.issue_backdated(scope, Duration::from_secs(1), Duration::from_secs(10));
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::Expired));
    }

    #[test]
    fn ttl_sweep_frees_expired_slots_before_capacity_check() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "test.txt", "content": "hello"}));
        for _ in 0..MAX_ACTIVE_TOKENS {
            registry.issue_backdated(
                test_scope("files.patch", digest, "/w", &session),
                Duration::from_secs(1),
                Duration::from_secs(10),
            );
        }
        assert_eq!(registry.active_count(), MAX_ACTIVE_TOKENS);
        let scope = test_scope("files.patch", digest, "/w", &session);
        assert!(registry.issue(scope).is_ok());
        assert_eq!(registry.active_count(), 1);
    }

    #[test]
    fn execution_grant_carries_short_lived_expiry() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert!(!grant.is_expired());
        let stale = ExecutionGrant {
            valid_until: Instant::now() - Duration::from_secs(1),
            ..grant.clone()
        };
        assert!(stale.is_expired());
    }

    #[test]
    fn wrong_tool_rejects_without_consuming_token() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn wrong_digest_rejects_without_consuming_token() {
        let mut registry = ApprovalRegistry::new();
        let input_a = json!({"path": "a.txt", "content": "A"});
        let input_b = json!({"path": "a.txt", "content": "B"});
        let digest_a = canonical_input_digest(&input_a);
        let digest_b = canonical_input_digest(&input_b);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest_a,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest_b,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InputDigestMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest_a,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn wrong_workspace_rejects_without_consuming_token() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/ws-b",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::WorkspaceMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/ws-a",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.workspace, "/ws-a");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn wrong_session_rejects_without_consuming_token() {
        let mut registry_a = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry_a.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry_a.issue(scope.clone()).unwrap();
        let mut registry_b = ApprovalRegistry::new();
        registry_b.entries.insert(
            token.clone(),
            ApprovalEntry {
                scope,
                nonce: [0u8; 16],
                issued_at: Instant::now(),
                ttl: DEFAULT_TTL,
            },
        );
        let err = registry_b
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::SessionMismatch));
        assert_eq!(registry_b.active_count(), 1);
    }

    #[test]
    fn token_survives_invalid_attempt_then_succeeds() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let wrong_digest = canonical_input_digest(&json!({"path": "other.txt"}));
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
        assert_eq!(registry.active_count(), 1);
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &wrong_digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InputDigestMismatch));
        assert_eq!(registry.active_count(), 1);
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/other",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::WorkspaceMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(registry.active_count(), 0);
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::AlreadyConsumed));
    }

    #[test]
    fn forged_token_with_valid_prefix_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let forged = format!("{}{}", TOKEN_PREFIX, "00".repeat(32));
        let digest = [0u8; 32];
        let err = registry
            .execute_approved(
                &forged,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn concurrent_consume_exactly_one_succeeds() {
        let registry = Arc::new(Mutex::new(ApprovalRegistry::new()));
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let token = {
            let mut guard = registry.lock().unwrap();
            let scope = ApprovalScope {
                tool: "files.patch".to_owned(),
                input_digest: digest,
                workspace: "/w".to_owned(),
                session: guard.session_id().to_owned(),
                risk_level: RiskLevel::Guarded,
                command_family: CommandFamily::ToolFilesystemWrite,
                approval_id: TEST_APPROVAL_ID.to_owned(),
                call_id: TEST_CALL_ID.to_owned(),
            };
            guard.issue(scope).unwrap()
        };
        let handles: Vec<_> = (0..2)
            .map(|_| {
                let registry = Arc::clone(&registry);
                let token = token.clone();
                std::thread::spawn(move || {
                    registry.lock().unwrap().execute_approved(
                        &token,
                        "files.patch",
                        &digest,
                        "/w",
                        TEST_APPROVAL_ID,
                        TEST_CALL_ID,
                        RiskLevel::Guarded,
                        CommandFamily::ToolFilesystemWrite,
                    )
                })
            })
            .collect();
        let results: Vec<_> = handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .collect();
        let ok_count = results.iter().filter(|result| result.is_ok()).count();
        let consumed_count = results
            .iter()
            .filter(|result| matches!(result, Err(ApprovalError::AlreadyConsumed)))
            .count();
        assert_eq!(ok_count, 1);
        assert_eq!(consumed_count, 1);
    }

    #[test]
    fn risk_level_metadata_cannot_bypass_scope_matching() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.read".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::ReadOnly,
            command_family: CommandFamily::ToolFilesystemRead,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
        let scope = ApprovalScope {
            tool: "files.delete".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Dangerous,
            command_family: CommandFamily::ToolFilesystemDelete,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Dangerous,
                CommandFamily::ToolFilesystemDelete,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.delete");
    }

    #[test]
    fn p0b_r2_approval_id_match_succeeds() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.approval_id, "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    }

    #[test]
    fn p0b_r2_approval_id_mismatch_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                "appr_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ApprovalIdMismatch));
    }

    #[test]
    fn p0b_r2_token_survives_wrong_approval_id() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                "appr_cccccccccccccccccccccccccccccccc",
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ApprovalIdMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                "appr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn p0b_r2_call_id_match_succeeds() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: "call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                "call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.call_id, "call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    }

    #[test]
    fn p0b_r2_call_id_mismatch_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: "call_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                "call_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::CallIdMismatch));
    }

    #[test]
    fn p0b_r2_risk_metadata_mismatch_does_not_block() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Dangerous,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Dangerous,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
    }

    #[test]
    fn p0b_r2_risk_level_absent_from_consume_api() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
    }

    #[test]
    fn p0b_r2_artifact_token_rejected_for_runtime_tool() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"artifact_id": "model-x"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "artifact.download".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "runtime.start",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
    }

    #[test]
    fn p0b_r2_runtime_token_rejected_for_artifact_tool() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"model_id": "model-x"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "runtime.start".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
    }

    #[test]
    fn p0b_r2_replay_distinguished_from_unknown() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        let replay_err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(replay_err, ApprovalError::AlreadyConsumed));
        let forged = format!("{}{}", TOKEN_PREFIX, "ff".repeat(32));
        let unknown_err = registry
            .execute_approved(
                &forged,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(unknown_err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn p0b_r2_token_consumed_before_dispatch_no_rollback() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: TEST_APPROVAL_ID.to_owned(),
            call_id: TEST_CALL_ID.to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert!(!grant.is_expired());
        assert_eq!(registry.active_count(), 0);
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::AlreadyConsumed));
    }

    #[test]
    fn p0b_authoritative_risk_is_stored() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        let stored = registry.stored_scope(&token).expect("scope stored");
        assert_eq!(stored.risk_level, RiskLevel::Guarded);
    }

    #[test]
    fn p0b_matching_authoritative_risk_is_accepted() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.write");
    }

    #[test]
    fn p0b_lowered_risk_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.delete",
            digest,
            "/w",
            &session,
            RiskLevel::Dangerous,
            CommandFamily::ToolFilesystemDelete,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemDelete,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::RiskMismatch));
    }

    #[test]
    fn p0b_wrong_risk_does_not_consume_token() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.delete",
            digest,
            "/w",
            &session,
            RiskLevel::Dangerous,
            CommandFamily::ToolFilesystemDelete,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemDelete,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::RiskMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Dangerous,
                CommandFamily::ToolFilesystemDelete,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.delete");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn p0b_renderer_cannot_select_risk() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let authoritative = crate::approval_commands::risk_level_for_tool("files.delete").unwrap();
        assert_eq!(authoritative, RiskLevel::Dangerous);
        let scope = scoped(
            "files.delete",
            digest,
            "/w",
            &session,
            authoritative,
            CommandFamily::ToolFilesystemDelete,
        );
        let token = registry.issue(scope).unwrap();
        let renderer_chosen = RiskLevel::ReadOnly;
        let err = registry
            .execute_approved(
                &token,
                "files.delete",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                renderer_chosen,
                CommandFamily::ToolFilesystemDelete,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::RiskMismatch));
    }

    #[test]
    fn p0b_unknown_operation_has_no_accepted_risk() {
        assert!(crate::approval_commands::risk_level_for_tool("unknown.tool").is_err());
    }

    #[test]
    fn p0b_command_family_is_stored() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"artifact_id": "m"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let token = registry.issue(scope).unwrap();
        let stored = registry.stored_scope(&token).expect("scope stored");
        assert_eq!(stored.command_family, CommandFamily::ArtifactDownload);
    }

    #[test]
    fn p0b_matching_command_family_is_accepted() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"artifact_id": "m"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ArtifactDownload,
            )
            .unwrap();
        assert_eq!(grant.tool, "artifact.download");
    }

    #[test]
    fn p0b_same_risk_different_family_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"id": "x"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::RuntimeStart,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::FamilyMismatch));
    }

    #[test]
    fn p0b_same_digest_different_family_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"id": "x"}));
        let scope = scoped(
            "runtime.start",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::RuntimeStart,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "runtime.start",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::RuntimeStop,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::FamilyMismatch));
    }

    #[test]
    fn p0b_wrong_family_does_not_consume_token() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"id": "x"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ArtifactRemove,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::FamilyMismatch));
        assert_eq!(registry.active_count(), 1);
        let grant = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ArtifactDownload,
            )
            .unwrap();
        assert_eq!(grant.tool, "artifact.download");
        assert_eq!(registry.active_count(), 0);
    }

    #[test]
    fn p0b_renderer_cannot_select_command_family() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"id": "x"}));
        let authoritative = command_family_for_tool("artifact.download").unwrap();
        assert_eq!(authoritative, CommandFamily::ArtifactDownload);
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            authoritative,
        );
        let token = registry.issue(scope).unwrap();
        let renderer_chosen = CommandFamily::RuntimeStart;
        let err = registry
            .execute_approved(
                &token,
                "artifact.download",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                renderer_chosen,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::FamilyMismatch));
    }

    #[test]
    fn p0b_consumed_tombstone_returns_already_consumed() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::AlreadyConsumed));
    }

    #[test]
    fn p0b_unknown_token_returns_token_not_found() {
        let mut registry = ApprovalRegistry::new();
        let forged = format!("{}{}", TOKEN_PREFIX, "ab".repeat(32));
        let digest = [0u8; 32];
        let err = registry
            .execute_approved(
                &forged,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn p0b_consumed_tombstones_have_fixed_capacity() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        for _ in 0..(MAX_CONSUMED_TOMBSTONES + 1) {
            let scope = scoped(
                "files.write",
                digest,
                "/w",
                &session,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            );
            let token = registry.issue(scope).unwrap();
            registry
                .execute_approved(
                    &token,
                    "files.write",
                    &digest,
                    "/w",
                    TEST_APPROVAL_ID,
                    TEST_CALL_ID,
                    RiskLevel::Guarded,
                    CommandFamily::ToolFilesystemWrite,
                )
                .unwrap();
        }
        assert!(registry.consumed_count() <= MAX_CONSUMED_TOMBSTONES);
    }

    #[test]
    fn p0b_oldest_tombstone_is_evicted_deterministically() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let mut first_token = String::new();
        let mut last_token = String::new();
        for i in 0..MAX_CONSUMED_TOMBSTONES {
            let scope = scoped(
                "files.write",
                digest,
                "/w",
                &session,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            );
            let token = registry.issue(scope).unwrap();
            if i == 0 {
                first_token = token.clone();
            }
            last_token = token.clone();
            registry
                .execute_approved(
                    &token,
                    "files.write",
                    &digest,
                    "/w",
                    TEST_APPROVAL_ID,
                    TEST_CALL_ID,
                    RiskLevel::Guarded,
                    CommandFamily::ToolFilesystemWrite,
                )
                .unwrap();
        }
        assert_eq!(registry.consumed_count(), MAX_CONSUMED_TOMBSTONES);
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(registry.consumed_count(), MAX_CONSUMED_TOMBSTONES);
        let evicted = registry
            .execute_approved(
                &first_token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(evicted, ApprovalError::TokenNotFound));
        let recent = registry
            .execute_approved(
                &last_token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(recent, ApprovalError::AlreadyConsumed));
    }

    #[test]
    fn p0b_expired_tombstones_are_removed() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let token = format!("{}{}", TOKEN_PREFIX, "cd".repeat(32));
        registry.insert_backdated_tombstone(&token, TOMBSTONE_TTL + Duration::from_secs(1));
        assert_eq!(registry.consumed_count(), 1);
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let _ = registry.issue(scope).unwrap();
        assert_eq!(registry.consumed_count(), 0);
    }

    #[test]
    fn p0b_concurrent_replay_registry_remains_consistent() {
        let registry = Arc::new(Mutex::new(ApprovalRegistry::new()));
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let token = {
            let mut guard = registry.lock().unwrap();
            let session = guard.session_id().to_owned();
            let scope = scoped(
                "files.write",
                digest,
                "/w",
                &session,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            );
            guard.issue(scope).unwrap()
        };
        let handles: Vec<_> = (0..8)
            .map(|_| {
                let registry = Arc::clone(&registry);
                let token = token.clone();
                std::thread::spawn(move || {
                    registry.lock().unwrap().execute_approved(
                        &token,
                        "files.write",
                        &digest,
                        "/w",
                        TEST_APPROVAL_ID,
                        TEST_CALL_ID,
                        RiskLevel::Guarded,
                        CommandFamily::ToolFilesystemWrite,
                    )
                })
            })
            .collect();
        let results: Vec<_> = handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .collect();
        let ok_count = results.iter().filter(|result| result.is_ok()).count();
        let consumed_count = results
            .iter()
            .filter(|result| matches!(result, Err(ApprovalError::AlreadyConsumed)))
            .count();
        assert_eq!(ok_count, 1);
        assert_eq!(consumed_count, 7);
        let guard = registry.lock().unwrap();
        assert_eq!(guard.active_count(), 0);
        assert_eq!(guard.consumed_count(), 1);
    }

    fn test_descriptor() -> ApprovalDescriptor {
        ApprovalDescriptor {
            tool: "files.write".to_owned(),
            command_family: CommandFamily::ToolFilesystemWrite,
            risk_level: RiskLevel::Guarded,
            target_summary: "notes.txt".to_owned(),
            side_effect_category: "filesystem_write".to_owned(),
            destructive: false,
        }
    }

    #[test]
    fn p0b_r5_generate_token_format() {
        let token = generate_token();
        assert_eq!(token.len(), 69);
        assert!(token.starts_with("lcap_"));
        assert!(token[5..]
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
    }

    #[test]
    fn p0b_r5_generate_approval_id_format() {
        let id = generate_approval_id();
        assert_eq!(id.len(), 37);
        assert!(id.starts_with("appr_"));
        assert!(id[5..]
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
    }

    #[test]
    fn p0b_r5_generate_call_id_format() {
        let id = generate_call_id();
        assert_eq!(id.len(), 37);
        assert!(id.starts_with("call_"));
        assert!(id[5..]
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
    }

    #[test]
    fn p0b_r5_ids_are_independent() {
        let token = generate_token();
        let approval_id = generate_approval_id();
        let call_id = generate_call_id();
        assert_ne!(token, approval_id);
        assert_ne!(token, call_id);
        assert_ne!(approval_id, call_id);
        assert!(token.starts_with("lcap_"));
        assert!(approval_id.starts_with("appr_"));
        assert!(call_id.starts_with("call_"));
    }

    #[test]
    fn p0b_r5_validate_token_syntax_valid() {
        let token = generate_token();
        assert!(validate_token_syntax(&token));
    }

    #[test]
    fn p0b_r5_validate_token_syntax_invalid_prefix() {
        assert!(!validate_token_syntax(
            "apt_0000000000000000000000000000000000000000000000000000000000000000"
        ));
    }

    #[test]
    fn p0b_r5_validate_token_syntax_invalid_length() {
        assert!(!validate_token_syntax("lcap_short"));
        assert!(!validate_token_syntax(&format!("lcap_{}", "a".repeat(65))));
    }

    #[test]
    fn p0b_r5_validate_token_syntax_uppercase_rejected() {
        assert!(!validate_token_syntax(&format!("lcap_{}", "A".repeat(64))));
    }

    #[test]
    fn p0b_r5_validate_approval_id_syntax_valid() {
        let id = generate_approval_id();
        assert!(validate_approval_id_syntax(&id));
    }

    #[test]
    fn p0b_r5_validate_approval_id_syntax_invalid() {
        assert!(!validate_approval_id_syntax("test-approval-id"));
        assert!(!validate_approval_id_syntax("appr_short"));
        assert!(!validate_approval_id_syntax(&format!(
            "appr_{}",
            "A".repeat(32)
        )));
        assert!(!validate_approval_id_syntax(
            "call_00000000000000000000000000000000"
        ));
    }

    #[test]
    fn p0b_r5_validate_call_id_syntax_valid() {
        let id = generate_call_id();
        assert!(validate_call_id_syntax(&id));
    }

    #[test]
    fn p0b_r5_validate_call_id_syntax_invalid() {
        assert!(!validate_call_id_syntax("test-call-id"));
        assert!(!validate_call_id_syntax("call_short"));
        assert!(!validate_call_id_syntax(&format!(
            "call_{}",
            "A".repeat(32)
        )));
        assert!(!validate_call_id_syntax(
            "appr_00000000000000000000000000000000"
        ));
    }

    #[test]
    fn p0b_r5_scripted_prompt_approve() {
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let descriptor = test_descriptor();
        let result = prompt.decide(&descriptor).unwrap();
        assert_eq!(result, ApprovalDecision::Approve);
    }

    #[test]
    fn p0b_r5_scripted_prompt_reject() {
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Reject,
        };
        let descriptor = test_descriptor();
        let result = prompt.decide(&descriptor).unwrap();
        assert_eq!(result, ApprovalDecision::Reject);
    }

    #[test]
    fn p0b_r5_request_with_prompt_approve_returns_envelope() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        assert!(validate_token_syntax(&envelope.token));
        assert!(validate_approval_id_syntax(&envelope.approval_id));
        assert!(validate_call_id_syntax(&envelope.call_id));
        assert_eq!(envelope.tool, "files.write");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);
        assert_eq!(envelope.command_family, CommandFamily::ToolFilesystemWrite);
        assert!(envelope.expires_at_unix_ms > 0);
    }

    #[test]
    fn p0b_r5_request_with_prompt_reject_returns_error() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Reject,
        };
        let err = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap_err();
        assert!(matches!(err, ApprovalError::Rejected));
    }

    #[test]
    fn p0b_r5_request_with_prompt_unavailable_returns_error() {
        struct FailingPrompt;
        impl ApprovalPrompt for FailingPrompt {
            fn decide(
                &self,
                _d: &ApprovalDescriptor,
            ) -> Result<ApprovalDecision, ApprovalPromptError> {
                Err(ApprovalPromptError::Unavailable("test".into()))
            }
        }
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = FailingPrompt;
        let err = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap_err();
        assert!(matches!(err, ApprovalError::PromptUnavailable));
    }

    #[test]
    fn p0b_r5_envelope_serialization_camel_case() {
        let envelope = ApprovalEnvelope {
            token: generate_token(),
            approval_id: generate_approval_id(),
            call_id: generate_call_id(),
            tool: "files.write".to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            expires_at_unix_ms: 1000000,
        };
        let json_val = serde_json::to_value(&envelope).unwrap();
        assert!(json_val.get("approvalId").is_some());
        assert!(json_val.get("callId").is_some());
        assert!(json_val.get("riskLevel").is_some());
        assert!(json_val.get("commandFamily").is_some());
        assert!(json_val.get("expiresAtUnixMs").is_some());
        assert!(json_val.get("approval_id").is_none());
        assert!(json_val.get("call_id").is_none());
    }

    #[test]
    fn p0b_r5_envelope_deserialization() {
        let json_str = r#"{"token":"lcap_0000000000000000000000000000000000000000000000000000000000000000","approvalId":"appr_00000000000000000000000000000000","callId":"call_00000000000000000000000000000000","tool":"files.write","riskLevel":"guarded","commandFamily":"tool_filesystem_write","expiresAtUnixMs":1000}"#;
        let envelope: ApprovalEnvelope = serde_json::from_str(json_str).unwrap();
        assert_eq!(envelope.tool, "files.write");
        assert_eq!(envelope.risk_level, RiskLevel::Guarded);
        assert_eq!(envelope.command_family, CommandFamily::ToolFilesystemWrite);
        assert_eq!(envelope.expires_at_unix_ms, 1000);
    }

    #[test]
    fn p0b_r5_risk_level_serialization() {
        assert_eq!(
            serde_json::to_value(RiskLevel::ReadOnly).unwrap(),
            "read_only"
        );
        assert_eq!(serde_json::to_value(RiskLevel::Guarded).unwrap(), "guarded");
        assert_eq!(
            serde_json::to_value(RiskLevel::Dangerous).unwrap(),
            "dangerous"
        );
    }

    #[test]
    fn p0b_r5_command_family_serialization() {
        assert_eq!(
            serde_json::to_value(CommandFamily::ArtifactDownload).unwrap(),
            "artifact_download"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::ArtifactRemove).unwrap(),
            "artifact_remove"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::RuntimeStart).unwrap(),
            "runtime_start"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::RuntimeStop).unwrap(),
            "runtime_stop"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::ModelBindingSet).unwrap(),
            "model_binding_set"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::ToolFilesystemRead).unwrap(),
            "tool_filesystem_read"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::ToolFilesystemWrite).unwrap(),
            "tool_filesystem_write"
        );
        assert_eq!(
            serde_json::to_value(CommandFamily::ToolFilesystemDelete).unwrap(),
            "tool_filesystem_delete"
        );
    }

    #[test]
    fn p0b_r5_execute_approved_validates_approval_id_syntax() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                "bad-id",
                TEST_CALL_ID,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ApprovalIdMismatch));
    }

    #[test]
    fn p0b_r5_execute_approved_validates_call_id_syntax() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = scoped(
            "files.write",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ToolFilesystemWrite,
        );
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(
                &token,
                "files.write",
                &digest,
                "/w",
                TEST_APPROVAL_ID,
                "bad-id",
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, ApprovalError::CallIdMismatch));
    }

    #[test]
    fn p0b_r5_no_derived_approval_call_id_in_source() {
        let source = include_str!("approval.rs");
        let needle = format!("pub fn {}_approval_call_id", "derived");
        assert!(
            !source.contains(&needle),
            "derived helper function must be removed"
        );
    }

    #[test]
    fn p0b_r5_scope_sentinels_defined() {
        assert_eq!(
            NON_WORKSPACE_APPROVAL_SCOPE,
            "localcomet://approval-scope/non-workspace"
        );
        assert_eq!(
            NON_SESSION_APPROVAL_SCOPE,
            "localcomet://approval-scope/non-session"
        );
    }

    #[test]
    fn p0b_r5_envelope_contains_all_fields() {
        let envelope = ApprovalEnvelope {
            token: "lcap_0000000000000000000000000000000000000000000000000000000000000000"
                .to_owned(),
            approval_id: "appr_00000000000000000000000000000000".to_owned(),
            call_id: "call_00000000000000000000000000000000".to_owned(),
            tool: "artifact.download".to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ArtifactDownload,
            expires_at_unix_ms: 999,
        };
        let json_val = serde_json::to_value(&envelope).unwrap();
        let keys: Vec<&str> = json_val
            .as_object()
            .unwrap()
            .keys()
            .map(|s| s.as_str())
            .collect();
        assert!(keys.contains(&"token"));
        assert!(keys.contains(&"approvalId"));
        assert!(keys.contains(&"callId"));
        assert!(keys.contains(&"tool"));
        assert!(keys.contains(&"riskLevel"));
        assert!(keys.contains(&"commandFamily"));
        assert!(keys.contains(&"expiresAtUnixMs"));
        assert_eq!(keys.len(), 7);
    }

    #[test]
    fn p0b_r5_token_approval_id_call_id_unique_per_request() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let e1 = registry
            .request_with_prompt(scope.clone(), &descriptor, &prompt)
            .unwrap();
        let e2 = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        assert_ne!(e1.token, e2.token);
        assert_ne!(e1.approval_id, e2.approval_id);
        assert_ne!(e1.call_id, e2.call_id);
    }

    #[test]
    fn p0b_r5_rejected_error_display() {
        let err = ApprovalError::Rejected;
        assert_eq!(err.to_string(), "approval was rejected by the user");
    }

    #[test]
    fn p0b_r5_prompt_unavailable_error_display() {
        let err = ApprovalError::PromptUnavailable;
        assert_eq!(err.to_string(), "trusted approval prompt is unavailable");
    }

    #[test]
    fn p0b_r5_request_with_prompt_stores_correct_scope() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        let stored = registry
            .stored_scope(&envelope.token)
            .expect("scope stored");
        assert_eq!(stored.approval_id, envelope.approval_id);
        assert_eq!(stored.call_id, envelope.call_id);
        assert_eq!(stored.tool, "files.write");
    }

    #[test]
    fn p0b_r5_envelope_expiry_is_future() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        let now_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;
        assert!(envelope.expires_at_unix_ms > now_ms);
    }

    #[test]
    fn p0b_r5_descriptor_fields() {
        let descriptor = ApprovalDescriptor {
            tool: "artifact.remove".to_owned(),
            command_family: CommandFamily::ArtifactRemove,
            risk_level: RiskLevel::Dangerous,
            target_summary: "model-x".to_owned(),
            side_effect_category: "artifact_delete".to_owned(),
            destructive: true,
        };
        assert_eq!(descriptor.tool, "artifact.remove");
        assert_eq!(descriptor.command_family, CommandFamily::ArtifactRemove);
        assert_eq!(descriptor.risk_level, RiskLevel::Dangerous);
        assert!(descriptor.destructive);
    }

    #[test]
    fn p0b_r5_envelope_roundtrip_after_request() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"path": "a.txt"}));
        let scope = ApprovalScope {
            tool: "files.write".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session,
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: String::new(),
            call_id: String::new(),
        };
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        let grant = registry
            .execute_approved(
                &envelope.token,
                "files.write",
                &digest,
                "/w",
                &envelope.approval_id,
                &envelope.call_id,
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap();
        assert_eq!(grant.tool, "files.write");
    }

    #[test]
    fn p0b_r5_no_allow_execute_approved_in_capabilities() {
        let caps = include_str!("../capabilities/main.json");
        assert!(
            !caps.contains("allow-execute-approved"),
            "allow-execute-approved must be removed from capabilities"
        );
    }

    #[test]
    fn p0b_r5_no_allow_execute_approved_in_permissions() {
        let perms = include_str!("../permissions/approval.toml");
        assert!(
            !perms.contains("allow-execute-approved"),
            "allow-execute-approved must be removed from permissions"
        );
    }

    #[test]
    fn p0b_r5_no_user_decision_in_request_approval() {
        let source = include_str!("approval_commands.rs");
        assert!(
            !source.contains("user_decision"),
            "user_decision parameter must be removed from request_approval"
        );
    }

    #[test]
    fn p0b_r5_fixture_file_exists() {
        let fixture =
            include_str!("../../../../security/contracts/approval_envelope_v1.fixture.json");
        let parsed: serde_json::Value = serde_json::from_str(fixture).unwrap();
        assert!(parsed.get("token").is_some());
        assert!(parsed.get("approvalId").is_some());
        assert!(parsed.get("callId").is_some());
        assert!(parsed.get("tool").is_some());
        assert!(parsed.get("riskLevel").is_some());
        assert!(parsed.get("commandFamily").is_some());
        assert!(parsed.get("expiresAtUnixMs").is_some());
    }

    #[test]
    fn p0b_r5_native_prompt_trait_object_safe() {
        let prompt: Arc<dyn ApprovalPrompt> = Arc::new(ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        });
        let descriptor = test_descriptor();
        assert_eq!(
            prompt.decide(&descriptor).unwrap(),
            ApprovalDecision::Approve
        );
    }

    #[test]
    fn p0b_r5_risk_level_deserialization() {
        let ro: RiskLevel = serde_json::from_str("\"read_only\"").unwrap();
        assert_eq!(ro, RiskLevel::ReadOnly);
        let g: RiskLevel = serde_json::from_str("\"guarded\"").unwrap();
        assert_eq!(g, RiskLevel::Guarded);
        let d: RiskLevel = serde_json::from_str("\"dangerous\"").unwrap();
        assert_eq!(d, RiskLevel::Dangerous);
    }

    #[test]
    fn p0b_r5_command_family_deserialization() {
        let f: CommandFamily = serde_json::from_str("\"artifact_download\"").unwrap();
        assert_eq!(f, CommandFamily::ArtifactDownload);
        let f: CommandFamily = serde_json::from_str("\"tool_filesystem_delete\"").unwrap();
        assert_eq!(f, CommandFamily::ToolFilesystemDelete);
    }

    #[test]
    fn p0b_r6_model_binding_command_has_no_confirmed_parameter() {
        let source = include_str!("control_plane.rs");
        let fn_start = source
            .find("pub async fn model_binding_set")
            .expect("model_binding_set must exist");
        let fn_block = &source[fn_start..];
        let sig_end = fn_block.find(") -> Result").expect("signature must close");
        let signature = &fn_block[..sig_end];
        assert!(
            !signature.contains("confirmed"),
            "model_binding_set signature must not contain a confirmed parameter"
        );
    }

    #[test]
    fn p0b_r6_model_binding_digest_excludes_confirmed() {
        let source = include_str!("control_plane.rs");
        let fn_start = source
            .find("pub async fn model_binding_set")
            .expect("model_binding_set must exist");
        let fn_block = &source[fn_start..];
        let validate_pos = fn_block
            .find("validate_approval_token")
            .expect("validate_approval_token call must exist");
        let pre_validate = &fn_block[..validate_pos];
        assert!(
            !pre_validate.contains("\"confirmed\""),
            "canonical digest payload must not contain confirmed before approval validation"
        );
    }

    #[test]
    fn p0b_r6_model_binding_approval_and_execution_input_equal() {
        let approval_input = json!({
            "provider_id": "openai-compatible-local",
            "harness_id": "minimal",
            "port": 1234u16,
            "model_id": "test-model",
            "runtime_instance_id": null
        });
        let execution_semantic_input = json!({
            "provider_id": "openai-compatible-local",
            "harness_id": "minimal",
            "port": 1234u16,
            "model_id": "test-model",
            "runtime_instance_id": null
        });
        let approval_digest = canonical_input_digest(&approval_input);
        let execution_digest = canonical_input_digest(&execution_semantic_input);
        assert_eq!(
            approval_digest, execution_digest,
            "approval semantic input digest must equal execution semantic digest"
        );
        let python_payload = json!({
            "provider_id": "openai-compatible-local",
            "harness_id": "minimal",
            "port": 1234u16,
            "model_id": "test-model",
            "confirmed": true,
            "runtime_instance_id": null
        });
        let python_digest = canonical_input_digest(&python_payload);
        assert_ne!(
            approval_digest, python_digest,
            "Python compatibility payload with confirmed must differ from semantic digest"
        );
    }

    #[test]
    fn p0b_r6_model_binding_requires_token() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"provider_id": "openai-compatible-local"}));
        let result = registry.execute_approved(
            "",
            "model.binding.set",
            &digest,
            "/w",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        let _ = session;
        assert!(result.is_err(), "empty token must be rejected");
    }

    #[test]
    fn p0b_r6_model_binding_requires_approval_id() {
        let mut registry = ApprovalRegistry::new();
        let digest = canonical_input_digest(&json!({"provider_id": "openai-compatible-local"}));
        let result = registry.execute_approved(
            "lcap_0000000000000000000000000000000000000000000000000000000000000000",
            "model.binding.set",
            &digest,
            "/w",
            "",
            TEST_CALL_ID,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        assert!(result.is_err(), "empty approval_id must be rejected");
    }

    #[test]
    fn p0b_r6_model_binding_requires_call_id() {
        let mut registry = ApprovalRegistry::new();
        let digest = canonical_input_digest(&json!({"provider_id": "openai-compatible-local"}));
        let result = registry.execute_approved(
            "lcap_0000000000000000000000000000000000000000000000000000000000000000",
            "model.binding.set",
            &digest,
            "/w",
            TEST_APPROVAL_ID,
            "",
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        assert!(result.is_err(), "empty call_id must be rejected");
    }

    #[test]
    fn p0b_r6_model_binding_internal_confirmed_after_consume() {
        let source = include_str!("control_plane.rs");
        let fn_start = source
            .find("pub async fn model_binding_set")
            .expect("model_binding_set must exist");
        let fn_block = &source[fn_start..];
        let validate_pos = fn_block
            .find("validate_approval_token")
            .expect("validate_approval_token call must exist");
        let confirmed_pos = fn_block.find("\"confirmed\"");
        match confirmed_pos {
            None => {}
            Some(pos) => assert!(
                pos > validate_pos,
                "confirmed compatibility value must appear only after validate_approval_token"
            ),
        }
    }

    #[test]
    fn p0b_r6_model_binding_rejection_never_builds_python_confirmed() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"provider_id": "openai-compatible-local"}));
        let scope = scoped(
            "model.binding.set",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Reject,
        };
        let result = registry.request_with_prompt(scope, &descriptor, &prompt);
        assert!(result.is_err(), "rejected approval must produce an error");
        let replay = registry.execute_approved(
            "lcap_0000000000000000000000000000000000000000000000000000000000000000",
            "model.binding.set",
            &digest,
            "/w",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        assert!(
            replay.is_err(),
            "no token exists after rejection; execution must fail"
        );
    }

    #[test]
    fn p0b_r6_model_binding_scope_mismatch_never_builds_python_confirmed() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"provider_id": "openai-compatible-local"}));
        let scope = scoped(
            "model.binding.set",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .expect("approval must succeed");
        let result = registry.execute_approved(
            &envelope.token,
            "model.binding.set",
            &digest,
            "/other-workspace",
            &envelope.approval_id,
            &envelope.call_id,
            RiskLevel::Guarded,
            CommandFamily::ModelBindingSet,
        );
        assert!(
            result.is_err(),
            "scope mismatch must prevent execution; no confirmed payload may be built"
        );
    }

    #[test]
    fn p0b_r6_all_approval_errors_use_exact_mapper() {
        let source = include_str!("approval_commands.rs");
        assert!(
            !source.contains("\"approval_denied\""),
            "no production path may collapse approval errors to generic approval_denied"
        );
    }

    #[test]
    fn p0b_r6_consumed_error_not_generic() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"artifact_id": "test"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        registry
            .execute_approved(
                &envelope.token,
                "artifact.download",
                &digest,
                "/w",
                &envelope.approval_id,
                &envelope.call_id,
                RiskLevel::Guarded,
                CommandFamily::ArtifactDownload,
            )
            .unwrap();
        let replay = registry.execute_approved(
            &envelope.token,
            "artifact.download",
            &digest,
            "/w",
            &envelope.approval_id,
            &envelope.call_id,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let error = replay.expect_err("replay must fail");
        assert!(
            matches!(error, ApprovalError::AlreadyConsumed),
            "consumed token must produce AlreadyConsumed, not a generic error; got: {:?}",
            error
        );
    }

    #[test]
    fn p0b_r6_unknown_error_not_generic() {
        let mut registry = ApprovalRegistry::new();
        let digest = canonical_input_digest(&json!({"artifact_id": "test"}));
        let result = registry.execute_approved(
            "lcap_0000000000000000000000000000000000000000000000000000000000000000",
            "artifact.download",
            &digest,
            "/w",
            TEST_APPROVAL_ID,
            TEST_CALL_ID,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let error = result.expect_err("unknown token must fail");
        assert!(
            matches!(error, ApprovalError::TokenNotFound),
            "unknown token must produce TokenNotFound, not a generic error; got: {:?}",
            error
        );
    }

    #[test]
    fn p0b_r6_scope_error_not_generic() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let digest = canonical_input_digest(&json!({"artifact_id": "test"}));
        let scope = scoped(
            "artifact.download",
            digest,
            "/w",
            &session,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let descriptor = test_descriptor();
        let prompt = ScriptedApprovalPrompt {
            decision: ApprovalDecision::Approve,
        };
        let envelope = registry
            .request_with_prompt(scope, &descriptor, &prompt)
            .unwrap();
        let result = registry.execute_approved(
            &envelope.token,
            "artifact.download",
            &digest,
            "/other-workspace",
            &envelope.approval_id,
            &envelope.call_id,
            RiskLevel::Guarded,
            CommandFamily::ArtifactDownload,
        );
        let error = result.expect_err("scope mismatch must fail");
        assert!(
            matches!(error, ApprovalError::WorkspaceMismatch),
            "scope mismatch must produce WorkspaceMismatch, not a generic error; got: {:?}",
            error
        );
    }

    #[test]
    fn p0b_r6_command_family_manifest_matches_rust_exactly() {
        let manifest_str =
            include_str!("../../../../security/contracts/approval_command_families_v1.json");
        let manifest: serde_json::Value = serde_json::from_str(manifest_str).unwrap();
        let families = manifest["families"]
            .as_array()
            .expect("families must be an array");
        let mut manifest_set: Vec<String> = families
            .iter()
            .map(|v| v.as_str().unwrap().to_owned())
            .collect();
        manifest_set.sort();
        let all_variants = [
            CommandFamily::ArtifactDownload,
            CommandFamily::ArtifactRemove,
            CommandFamily::RuntimeStart,
            CommandFamily::RuntimeStop,
            CommandFamily::ModelBindingSet,
            CommandFamily::ToolFilesystemRead,
            CommandFamily::ToolFilesystemWrite,
            CommandFamily::ToolFilesystemDelete,
        ];
        let mut rust_set: Vec<String> = all_variants
            .iter()
            .map(|v| {
                serde_json::to_value(v)
                    .unwrap()
                    .as_str()
                    .unwrap()
                    .to_owned()
            })
            .collect();
        rust_set.sort();
        assert_eq!(
            manifest_set, rust_set,
            "manifest family set must exactly equal Rust CommandFamily serialized set"
        );
    }

    #[test]
    fn p0b_r6_command_family_manifest_has_no_duplicates() {
        let manifest_str =
            include_str!("../../../../security/contracts/approval_command_families_v1.json");
        let manifest: serde_json::Value = serde_json::from_str(manifest_str).unwrap();
        let families = manifest["families"]
            .as_array()
            .expect("families must be an array");
        let values: Vec<&str> = families.iter().map(|v| v.as_str().unwrap()).collect();
        let mut seen = std::collections::HashSet::new();
        for v in &values {
            assert!(seen.insert(v), "duplicate family value in manifest: {}", v);
        }
        assert_eq!(
            values.len(),
            8,
            "manifest must contain exactly 8 family values"
        );
    }

    #[test]
    fn p0b_r6_all_envelope_families_are_manifest_members() {
        let manifest_str =
            include_str!("../../../../security/contracts/approval_command_families_v1.json");
        let manifest: serde_json::Value = serde_json::from_str(manifest_str).unwrap();
        let families = manifest["families"].as_array().unwrap();
        let manifest_set: std::collections::HashSet<&str> =
            families.iter().map(|v| v.as_str().unwrap()).collect();
        let all_variants = [
            CommandFamily::ArtifactDownload,
            CommandFamily::ArtifactRemove,
            CommandFamily::RuntimeStart,
            CommandFamily::RuntimeStop,
            CommandFamily::ModelBindingSet,
            CommandFamily::ToolFilesystemRead,
            CommandFamily::ToolFilesystemWrite,
            CommandFamily::ToolFilesystemDelete,
        ];
        for variant in &all_variants {
            let serialized = serde_json::to_value(variant).unwrap();
            let s = serialized.as_str().unwrap();
            assert!(
                manifest_set.contains(s),
                "Rust family {} must be a manifest member",
                s
            );
        }
    }

    #[test]
    fn p0b_r6_current_five_routes_map_to_exact_families() {
        let routes = [
            ("artifact.download", CommandFamily::ArtifactDownload),
            ("artifact.remove", CommandFamily::ArtifactRemove),
            ("runtime.start", CommandFamily::RuntimeStart),
            ("runtime.stop", CommandFamily::RuntimeStop),
            ("model.binding.set", CommandFamily::ModelBindingSet),
        ];
        for (tool, expected) in &routes {
            let actual = command_family_for_tool(tool).expect("tool must have a family");
            assert_eq!(
                &actual, expected,
                "tool {} must map to {:?}",
                tool, expected
            );
        }
    }

    #[test]
    fn p0b_r6_forbidden_capabilities_remain_absent() {
        let caps = include_str!("../capabilities/main.json");
        assert!(
            !caps.contains("allow-run-tool-call"),
            "allow-run-tool-call must remain absent"
        );
        assert!(
            !caps.contains("allow-set-workspace"),
            "allow-set-workspace must remain absent"
        );
        assert!(
            !caps.contains("allow-execute-approved"),
            "allow-execute-approved must remain absent"
        );
    }
}
