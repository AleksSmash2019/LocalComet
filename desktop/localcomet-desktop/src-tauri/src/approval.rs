use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use subtle::ConstantTimeEq;

const TOKEN_ENTROPY_BYTES: usize = 32;
const TOKEN_PREFIX: &str = "lcap_";
const MAX_ACTIVE_TOKENS: usize = 64;
const DEFAULT_TTL: Duration = Duration::from_secs(300);
const GRANT_TTL: Duration = Duration::from_secs(30);

#[derive(Clone, Debug)]
pub struct ApprovalScope {
    pub tool: String,
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    /// Risk classification recorded at issue time (for UI/policy/audit). The
    /// authorization decision is enforced by scope matching in execute_approved;
    /// risk_level is descriptive metadata retained on the scope.
    #[allow(dead_code)]
    pub risk_level: RiskLevel,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RiskLevel {
    ReadOnly,
    Guarded,
    Dangerous,
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
    Expired,
    /// Reserved for a future soft-consume design that marks tokens consumed
    /// without removing them. The current implementation removes a token on
    /// consume, so a replay surfaces as TokenNotFound; this variant is retained
    /// to keep the error vocabulary stable.
    #[allow(dead_code)]
    AlreadyConsumed,
    InvalidToken,
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
            Self::Expired => write!(f, "approval token expired"),
            Self::AlreadyConsumed => write!(f, "approval token already consumed"),
            Self::InvalidToken => write!(f, "approval token is invalid"),
        }
    }
}

pub struct ApprovalRegistry {
    entries: HashMap<String, ApprovalEntry>,
    session_id: String,
}

impl ApprovalRegistry {
    pub fn new() -> Self {
        let mut session_bytes = [0u8; 16];
        getrandom::getrandom(&mut session_bytes)
            .expect("OS CSPRNG unavailable for session generation");
        Self {
            entries: HashMap::new(),
            session_id: hex_encode(&session_bytes),
        }
    }

    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    pub fn issue(&mut self, scope: ApprovalScope) -> Result<String, ApprovalError> {
        self.issue_with_ttl(scope, DEFAULT_TTL)
    }

    fn issue_with_ttl(
        &mut self,
        scope: ApprovalScope,
        ttl: Duration,
    ) -> Result<String, ApprovalError> {
        // Sweep already-expired entries before the capacity check so stale
        // tokens cannot permanently occupy registry slots. This only removes
        // tokens past their TTL; it never weakens validation (fail-closed).
        self.entries
            .retain(|_, entry| entry.issued_at.elapsed() <= entry.ttl);

        if self.entries.len() >= MAX_ACTIVE_TOKENS {
            return Err(ApprovalError::RegistryFull);
        }

        let mut token_bytes = [0u8; TOKEN_ENTROPY_BYTES];
        getrandom::getrandom(&mut token_bytes).expect("OS CSPRNG unavailable for token generation");

        let mut nonce = [0u8; 16];
        getrandom::getrandom(&mut nonce).expect("OS CSPRNG unavailable for nonce generation");

        let token_string = format!("{}{}", TOKEN_PREFIX, hex_encode(&token_bytes));

        self.entries.insert(
            token_string.clone(),
            ApprovalEntry {
                scope,
                nonce,
                issued_at: Instant::now(),
                ttl,
            },
        );

        Ok(token_string)
    }

    pub fn execute_approved(
        &mut self,
        token: &str,
        tool: &str,
        input_digest: &[u8; 32],
        workspace: &str,
    ) -> Result<ExecutionGrant, ApprovalError> {
        if !token.starts_with(TOKEN_PREFIX) {
            return Err(ApprovalError::InvalidToken);
        }

        let entry = self
            .entries
            .remove(token)
            .ok_or(ApprovalError::TokenNotFound)?;

        if entry.issued_at.elapsed() > entry.ttl {
            return Err(ApprovalError::Expired);
        }

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

        let mut grant_id = [0u8; 16];
        getrandom::getrandom(&mut grant_id).expect("OS CSPRNG unavailable for grant generation");

        Ok(ExecutionGrant {
            grant_id: hex_encode(&grant_id),
            tool: scope.tool.clone(),
            input_digest: *input_digest,
            workspace: workspace.to_owned(),
            session: self.session_id.clone(),
            nonce: entry.nonce,
            valid_until: Instant::now() + GRANT_TTL,
        })
    }

    pub fn invalidate_workspace(&mut self, old_workspace: &str) {
        self.entries
            .retain(|_, entry| entry.scope.workspace != old_workspace);
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
        let mut token_bytes = [0u8; TOKEN_ENTROPY_BYTES];
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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn test_scope(tool: &str, workspace: &str, session: &str) -> ApprovalScope {
        ApprovalScope {
            tool: tool.to_owned(),
            input_digest: canonical_input_digest(&json!({"path": "test.txt", "content": "hello"})),
            workspace: workspace.to_owned(),
            session: session.to_owned(),
            risk_level: RiskLevel::Guarded,
        }
    }

    #[test]
    fn issued_tokens_are_unique_and_256_bits() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let mut tokens = Vec::new();
        for _ in 0..MAX_ACTIVE_TOKENS {
            let scope = test_scope("files.patch", "/workspace", &session);
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
        let t1 = r1
            .issue(test_scope("files.patch", "/w", &s1_session))
            .unwrap();
        let t2 = r2
            .issue(test_scope("files.patch", "/w", &s2_session))
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
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(&token, "files.patch", &digest, "/workspace")
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
        };
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
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
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.delete", &digest, "/w")
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
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest_b, "/w")
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
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/workspace-b")
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
        };
        let scope_b = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-b".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token_a = registry.issue(scope_a).unwrap();
        let _token_b = registry.issue(scope_b).unwrap();
        assert_eq!(registry.active_count(), 2);
        registry.invalidate_workspace("/ws-a");
        assert_eq!(registry.active_count(), 1);
        let err = registry
            .execute_approved(&token_a, "files.patch", &digest, "/ws-a")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn invalid_prefix_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let digest = [0u8; 32];
        let err = registry
            .execute_approved("apt_fake_token", "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InvalidToken));
    }

    #[test]
    fn wrong_session_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        // Token is bound to a forged session that does not match the registry.
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: "00000000000000000000000000000000".to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::SessionMismatch));
    }

    #[test]
    fn expired_token_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let scope = test_scope("files.patch", "/w", &session);
        let digest = scope.input_digest;
        // Backdate the token so it is already expired (deterministic, no sleep).
        let token =
            registry.issue_backdated(scope, Duration::from_secs(1), Duration::from_secs(10));
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::Expired));
    }

    #[test]
    fn ttl_sweep_frees_expired_slots_before_capacity_check() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        // Fill the registry to capacity with tokens that are already expired
        // (backdated). This is deterministic and independent of wall-clock timing.
        for _ in 0..MAX_ACTIVE_TOKENS {
            registry.issue_backdated(
                test_scope("files.patch", "/w", &session),
                Duration::from_secs(1),
                Duration::from_secs(10),
            );
        }
        assert_eq!(registry.active_count(), MAX_ACTIVE_TOKENS);
        // Without the sweep this would fail with RegistryFull; the sweep clears
        // the expired entries first, so a fresh issue succeeds.
        let scope = test_scope("files.patch", "/w", &session);
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
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap();
        // A freshly minted grant must not be expired yet.
        assert!(!grant.is_expired());
        // A grant whose deadline is in the past must report expired.
        let stale = ExecutionGrant {
            valid_until: Instant::now() - Duration::from_secs(1),
            ..grant.clone()
        };
        assert!(stale.is_expired());
    }
}
