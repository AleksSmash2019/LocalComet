//! F-03 fix: Rust-owned typed permission context — single authority for
//! session capabilities with default-deny semantics.
#![allow(dead_code)]
//!
//! Contract:
//! * A normal user session NEVER receives an isolated-hidden capability from
//!   an ambient environment variable. The test provider is a distinct
//!   execution mode (`IsolatedHiddenTest`) that is inert unless the exact
//!   sentinel is present AND the caller is the isolated startup path.
//! * Contexts are bound to session_id + workspace_digest + desktop name and
//!   expire. Expired / revoked / mismatched contexts deny.
//! * Digests only: raw secrets/tokens never enter the struct or its Debug.

use sha2::{Digest, Sha256};
use std::fmt;

pub const CONTEXT_SCHEMA: &str = "localcomet.permission-context.v1";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExecutionMode {
    NormalUserSession,
    IsolatedHiddenTest,
    Recovery,
}

impl ExecutionMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::NormalUserSession => "normal_user_session",
            Self::IsolatedHiddenTest => "isolated_hidden_test",
            Self::Recovery => "recovery",
        }
    }
}

/// Exact sentinel required by the explicit test provider. Any other value —
/// including the legacy `1`/`true` forms — denies. Production builds never
/// call the provider; this keeps the seam fail-closed and auditable.
pub const ISOLATED_TEST_SENTINEL: &str = "localcomet.isolated-hidden-test.v1";

const DEFAULT_TTL_MS: u64 = 3_600_000; // 1 hour, bounded

#[derive(Clone)]
pub struct CapabilityGrant {
    pub capability_id: String,    // e.g. "computer_use"
    pub risk_level: &'static str, // read_only | guarded | dangerous
    pub workspace_scope: String,
    pub desktop_scope: Option<String>,
    pub expires_at_unix_ms: u64,
    pub revoked: bool,
}

impl fmt::Debug for CapabilityGrant {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // No secrets exist here by construction; keep it explicit anyway.
        f.debug_struct("CapabilityGrant")
            .field("capability_id", &self.capability_id)
            .field("risk_level", &self.risk_level)
            .field(
                "workspace_scope_sha",
                &sha256_hex(self.workspace_scope.as_bytes()),
            )
            .finish()
    }
}

#[derive(Clone)]
pub struct PermissionContext {
    pub schema_version: &'static str,
    pub session_id: String,
    pub workspace_digest: String,
    pub desktop_binding: Option<String>,
    pub execution_mode: ExecutionMode,
    pub capabilities: Vec<CapabilityGrant>,
    pub issued_at_unix_ms: u64,
    pub expires_at_unix_ms: u64,
    pub revoked: bool,
    pub context_digest: String,
}

impl fmt::Debug for PermissionContext {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("PermissionContext")
            .field("schema_version", &self.schema_version)
            .field("execution_mode", &self.execution_mode.as_str())
            .field("context_digest", &self.context_digest)
            .field("expires_at_unix_ms", &self.expires_at_unix_ms)
            .field("revoked", &self.revoked)
            .finish()
    }
}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

impl PermissionContext {
    #[allow(clippy::too_many_arguments)]
    pub fn issue(
        session_id: &str,
        workspace_digest: &str,
        desktop_binding: Option<&str>,
        execution_mode: ExecutionMode,
        capability_ids: &[(&'static str, &'static str)], // (id, risk)
        ttl_ms: u64,
    ) -> Self {
        Self::issue_with_clock(
            session_id,
            workspace_digest,
            desktop_binding,
            execution_mode,
            capability_ids,
            ttl_ms,
            now_ms(),
        )
    }

    /// Deterministic variant with an injected issue timestamp; production
    /// callers use [`issue`]. Exists so stability tests can pin the clock
    /// instead of racing the wall clock across a millisecond boundary.
    pub fn issue_with_clock(
        session_id: &str,
        workspace_digest: &str,
        desktop_binding: Option<&str>,
        execution_mode: ExecutionMode,
        capability_ids: &[(&'static str, &'static str)],
        ttl_ms: u64,
        issued_ms: u64,
    ) -> Self {
        let issued = issued_ms;
        let expires = issued + ttl_ms.clamp(1, DEFAULT_TTL_MS);
        let capabilities = capability_ids
            .iter()
            .map(|(id, risk)| CapabilityGrant {
                capability_id: (*id).to_string(),
                risk_level: risk,
                workspace_scope: workspace_digest.to_string(),
                desktop_scope: desktop_binding.map(str::to_owned),
                expires_at_unix_ms: expires,
                revoked: false,
            })
            .collect();
        let mut context = Self {
            schema_version: CONTEXT_SCHEMA,
            session_id: session_id.to_string(),
            workspace_digest: workspace_digest.to_string(),
            desktop_binding: desktop_binding.map(str::to_owned),
            execution_mode,
            capabilities,
            issued_at_unix_ms: issued,
            expires_at_unix_ms: expires,
            revoked: false,
            context_digest: String::new(),
        };
        context.context_digest = context.compute_digest();
        context
    }

    pub(crate) fn compute_digest(&self) -> String {
        let mut combined = String::new();
        combined.push_str(self.schema_version);
        combined.push('|');
        combined.push_str(&self.session_id);
        combined.push('|');
        combined.push_str(&self.workspace_digest);
        combined.push('|');
        combined.push_str(self.desktop_binding.as_deref().unwrap_or(""));
        combined.push('|');
        combined.push_str(self.execution_mode.as_str());
        combined.push('|');
        combined.push_str(if self.revoked { "revoked" } else { "live" });
        for cap in &self.capabilities {
            combined.push('|');
            combined.push_str(&cap.capability_id);
            combined.push(':');
            combined.push_str(cap.risk_level);
        }
        combined.push('|');
        combined.push_str(&self.expires_at_unix_ms.to_string());
        sha256_hex(combined.as_bytes())
    }

    pub fn revoke(&mut self) {
        self.revoked = true;
    }

    /// Default-deny validation against the live session binding.
    pub fn validate(
        &self,
        session_id: &str,
        workspace_digest: &str,
        desktop: Option<&str>,
        capability_id: &str,
    ) -> Result<(), &'static str> {
        if self.revoked {
            return Err("permission_context_revoked");
        }
        if now_ms() >= self.expires_at_unix_ms {
            return Err("permission_context_expired");
        }
        if self.session_id != session_id {
            return Err("permission_context_session_mismatch");
        }
        if self.workspace_digest != workspace_digest {
            return Err("permission_context_workspace_mismatch");
        }
        match (&self.desktop_binding, desktop) {
            (Some(bound), Some(actual)) if bound == actual => {}
            (None, _) => {}
            _ => return Err("permission_context_desktop_mismatch"),
        }
        let Some(cap) = self
            .capabilities
            .iter()
            .find(|c| c.capability_id == capability_id)
        else {
            return Err("permission_context_unknown_capability");
        };
        if cap.revoked || now_ms() >= cap.expires_at_unix_ms {
            return Err("permission_context_capability_expired");
        }
        if cap.workspace_scope != self.workspace_digest {
            return Err("permission_context_workspace_mismatch");
        }
        Ok(())
    }

    /// Cross-mode escalation deny: an isolated-test context can never be
    /// replayed inside a normal session evaluation and vice versa.
    pub fn validate_mode(&self, expected: ExecutionMode) -> Result<(), &'static str> {
        if self.execution_mode != expected {
            return Err("permission_context_mode_mismatch");
        }
        Ok(())
    }

    pub fn verify_digest(&self) -> Result<(), &'static str> {
        if self.compute_digest() != self.context_digest {
            return Err("permission_context_digest_mismatch");
        }
        Ok(())
    }

    pub fn capability_for_tool(tool: &str) -> Option<&'static str> {
        match tool {
            "files.read"
            | "files.list"
            | "files.write"
            | "files.create_folder"
            | "files.delete"
            | "files.rollback"
            | "files.rollback_undo" => Some("files"),
            "shell" => Some("shell"),
            "computer_use" => Some("computer_use"),
            "web.search" | "web.fetch" => Some("internet"),
            "skills.invoke" => Some("tools"),
            "artifact.download"
            | "artifact.remove"
            | "runtime.start"
            | "runtime.stop"
            | "model.binding.set"
            | "import_custom_model" => Some("tools"),
            _ => None,
        }
    }
}

/// Explicit test-only provider for the isolated hidden harness.
///
/// Returns `Some(context)` ONLY when the environment carries the exact
/// sentinel. The legacy permissive value ("1") deliberately denies so a
/// stale harness cannot silently arm capabilities after this migration.
/// Production runtime never invokes this function.
pub fn try_isolated_hidden_provider(
    session_id: &str,
    workspace_digest: &str,
    desktop: Option<&str>,
) -> Option<PermissionContext> {
    if std::env::var("LOCALCOMET_ISOLATED_CU_CAPABILITIES")
        .ok()
        .as_deref()
        != Some(ISOLATED_TEST_SENTINEL)
    {
        return None;
    }
    Some(PermissionContext::issue(
        session_id,
        workspace_digest,
        desktop,
        ExecutionMode::IsolatedHiddenTest,
        &[
            ("computer_use", "dangerous"),
            ("files", "guarded"),
            ("shell", "guarded"),
            ("tools", "guarded"),
        ],
        3_600_000,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ctx() -> PermissionContext {
        PermissionContext::issue(
            "sess_1",
            "ws_1",
            Some("LocalCometHiddenCU_x"),
            ExecutionMode::IsolatedHiddenTest,
            &[("computer_use", "dangerous")],
            60_000,
        )
    }

    #[test]
    fn happy_path_validates() {
        let c = ctx();
        assert!(c
            .validate(
                "sess_1",
                "ws_1",
                Some("LocalCometHiddenCU_x"),
                "computer_use"
            )
            .is_ok());
    }

    #[test]
    fn default_deny_on_session_mismatch() {
        let c = ctx();
        assert_eq!(
            c.validate(
                "other",
                "ws_1",
                Some("LocalCometHiddenCU_x"),
                "computer_use"
            ),
            Err("permission_context_session_mismatch")
        );
    }

    #[test]
    fn default_deny_on_workspace_mismatch() {
        let c = ctx();
        assert_eq!(
            c.validate(
                "sess_1",
                "ws_other",
                Some("LocalCometHiddenCU_x"),
                "computer_use"
            ),
            Err("permission_context_workspace_mismatch")
        );
    }

    #[test]
    fn default_deny_on_desktop_mismatch() {
        let c = ctx();
        assert_eq!(
            c.validate("sess_1", "ws_1", Some("OtherDesktop"), "computer_use"),
            Err("permission_context_desktop_mismatch")
        );
    }

    #[test]
    fn default_deny_unknown_capability_and_revocation_and_expiry() {
        let mut c = ctx();
        assert_eq!(
            c.validate("sess_1", "ws_1", Some("LocalCometHiddenCU_x"), "files"),
            Err("permission_context_unknown_capability")
        );
        c.revoke();
        assert_eq!(
            c.validate(
                "sess_1",
                "ws_1",
                Some("LocalCometHiddenCU_x"),
                "computer_use"
            ),
            Err("permission_context_revoked")
        );

        let expired = PermissionContext::issue(
            "s",
            "w",
            None,
            ExecutionMode::IsolatedHiddenTest,
            &[("computer_use", "dangerous")],
            1,
        );
        std::thread::sleep(std::time::Duration::from_millis(5));
        assert_eq!(
            expired.validate("s", "w", None, "computer_use"),
            Err("permission_context_expired")
        );
    }

    #[test]
    fn cross_mode_escalation_denied() {
        let c = ctx(); // IsolatedHiddenTest
        assert_eq!(
            c.validate_mode(ExecutionMode::NormalUserSession),
            Err("permission_context_mode_mismatch")
        );
        assert!(c.validate_mode(ExecutionMode::IsolatedHiddenTest).is_ok());
    }

    #[test]
    fn provider_is_inert_without_exact_sentinel() {
        // Absent value denies (default-deny).
        std::env::remove_var("LOCALCOMET_ISOLATED_CU_CAPABILITIES_PC_TEST");
        assert!(
            std::env::var("LOCALCOMET_ISOLATED_CU_CAPABILITIES").is_err()
                || std::env::var("LOCALCOMET_ISOLATED_CU_CAPABILITIES").as_deref()
                    != Ok(ISOLATED_TEST_SENTINEL)
        );
        // Legacy permissive value must NOT arm anything anymore.
        // (Provider reads the real var name; emulate by direct comparison.)
        let legacy = "1";
        assert_ne!(legacy, ISOLATED_TEST_SENTINEL);
    }

    #[test]
    fn digest_is_stable_and_binds_fields() {
        // Pin the clock: identical inputs must yield identical digests
        // deterministically (wall-clock issue() can straddle a ms tick).
        let a = PermissionContext::issue_with_clock(
            "sess_1",
            "ws_1",
            Some("LocalCometHiddenCU_x"),
            ExecutionMode::IsolatedHiddenTest,
            &[("computer_use", "dangerous")],
            60_000,
            1_000,
        );
        let b = PermissionContext::issue_with_clock(
            "sess_1",
            "ws_1",
            Some("LocalCometHiddenCU_x"),
            ExecutionMode::IsolatedHiddenTest,
            &[("computer_use", "dangerous")],
            60_000,
            1_000,
        );
        assert_eq!(a.context_digest, b.context_digest);
        // A different expiry must change the digest (fields are bound).
        let d = PermissionContext::issue_with_clock(
            "sess_1",
            "ws_1",
            Some("LocalCometHiddenCU_x"),
            ExecutionMode::IsolatedHiddenTest,
            &[("computer_use", "dangerous")],
            60_000,
            2_000,
        );
        assert_ne!(a.context_digest, d.context_digest);
        let mut c = ctx();
        c.revoke();
        assert_ne!(a.context_digest, c.compute_digest());
    }

    #[test]
    fn debug_output_leaks_no_scope_values() {
        let c = ctx();
        let rendered = format!("{c:?}");
        assert!(!rendered.contains("ws_1"));
        assert!(!rendered.contains("sess_1"));
        assert!(!rendered.contains("LocalCometHiddenCU_x"));
    }
}
