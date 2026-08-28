//! Broker-owned one-time continuation grants for Computer Use launches.
//!
//! Authority contract (master prompt Part I): a continuation grant is issued
//! only by the Rust broker after an eligible parent launch, is one-time,
//! short-TTL, task/step/session/workspace/desktop bound and action-allowlist
//! bound. Transport contract (F-03): the raw `cgr_` token is returned EXACTLY
//! ONCE over the typed Tauri response to the authorized caller; the registry
//! stores only its SHA-256 hash; duplicate issues never re-reveal it; no Rust
//! log, ledger or evidence writer serializes it. Consumers must scrub it from
//! any UI/evidence persistence. Python is never a capability authority.
//!
//! Action contract (F-02): EVERY advertised action gets its own canonical
//! input digest and subject binding at issue time; consume validates the
//! ACTUAL action against its own binding. Only actions with a real host-side
//! postcondition implementation may be advertised.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const CONTINUATION_GRANT_SCHEMA: &str = "cu.broker.continuation.grant.v1";
const DEFAULT_TTL_MS: u64 = 30_000;
const MAX_TTL_MS: u64 = 600_000;
const MAX_REMAINING_STEPS: u16 = 8;
/// Syntactic vocabulary of action kinds a continuation MAY name at all.
/// Membership here does NOT make an action advertisable.
const ALLOWED_NEXT_ACTION_KINDS: [&str; 5] = [
    "observe",
    "wait",
    "wait_for_window",
    "type_element",
    "press_key",
];
/// Actions with an ACTUAL host-side postcondition implementation. Only these
/// may be advertised in `allowed_next_actions`; anything else would promise a
/// capability the runtime cannot verify (F-02).
pub const HOST_IMPLEMENTED_NEXT_ACTIONS: [&str; 1] = ["observe"];

pub const ERR_NOT_FOUND: &str = "continuation_not_found";
pub const ERR_EXPIRED: &str = "continuation_expired";
pub const ERR_REPLAYED: &str = "continuation_replayed";
pub const ERR_TASK_MISMATCH: &str = "continuation_task_mismatch";
pub const ERR_STEP_MISMATCH: &str = "continuation_step_mismatch";
pub const ERR_ACTION_MISMATCH: &str = "continuation_action_mismatch";
pub const ERR_INPUT_DIGEST_MISMATCH: &str = "continuation_input_digest_mismatch";
pub const ERR_SESSION_MISMATCH: &str = "continuation_session_mismatch";
pub const ERR_WORKSPACE_MISMATCH: &str = "continuation_workspace_mismatch";
pub const ERR_DESKTOP_MISMATCH: &str = "continuation_desktop_mismatch";
pub const ERR_POSTCONDITION_MISMATCH: &str = "continuation_postcondition_mismatch";
pub const ERR_NOT_ISSUED_BY_BROKER: &str = "continuation_grant_not_issued_by_broker";
pub const ERR_IN_FLIGHT: &str = "continuation_in_flight";
#[allow(dead_code)]
pub const ERR_RECOVERY_REQUIRED: &str = "continuation_recovery_required";
pub const ERR_POLICY_DENIED: &str = "continuation_policy_denied";
pub const ERR_INVALID_PAYLOAD: &str = "invalid_payload";
pub const ERR_BUDGET_EXHAUSTED: &str = "continuation_budget_exhausted";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ContinuationState {
    Issued,
    InFlight,
    CompletedVerified,
    CompletedFailed,
    CompletedBlocked,
    Expired,
    Revoked,
    #[allow(dead_code)]
    RecoveryRequired,
}

impl ContinuationState {
    pub fn as_wire(self) -> &'static str {
        match self {
            Self::Issued => "issued",
            Self::InFlight => "in_flight",
            Self::CompletedVerified => "completed_verified",
            Self::CompletedFailed => "completed_failed",
            Self::CompletedBlocked => "completed_blocked",
            Self::Expired => "expired",
            Self::Revoked => "revoked",
            Self::RecoveryRequired => "recovery_required",
        }
    }
}

/// Per-action authority binding (F-02): each advertised action carries its
/// own canonical continuation-input digest AND its own subject digest, both
/// computed at issue time from authoritative fields only.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ContinuationActionBinding {
    pub action_kind: String,
    pub expected_input_digest: [u8; 32],
    pub expected_subject_digest: [u8; 32],
}

#[derive(Clone, Debug)]
pub struct ContinuationGrantRecord {
    pub grant_ref_hash: [u8; 32],
    pub task_id: String,
    pub step_id: String,
    pub parent_request_id: String,
    /// Retained for task-ledger/evidence correlation (Phase 3 consumers).
    #[allow(dead_code)]
    pub parent_action_id: String,
    pub parent_input_digest: [u8; 32],
    pub session_id: String,
    pub workspace_digest: String,
    pub hidden_desktop: Option<String>,
    pub target: String,
    pub allowed_next_actions: Vec<String>,
    /// One binding per advertised action, same order as allowed_next_actions.
    pub action_bindings: Vec<ContinuationActionBinding>,
    pub expected_postcondition_kind: String,
    pub step_index: u16,
    pub remaining_steps: u16,
    /// Retained for task-ledger/evidence correlation (Phase 3 consumers).
    #[allow(dead_code)]
    pub issued_at_unix_ms: u64,
    pub expires_at_unix_ms: u64,
    deadline: Instant,
    pub state: ContinuationState,
    lease_id: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ContinuationIssueReceipt {
    pub schema_version: &'static str,
    pub status: &'static str,
    pub grant_ref: String,
    pub grant_state: &'static str,
    pub task_id: String,
    pub step_id: String,
    pub parent_request_id: String,
    pub allowed_next_actions: Vec<String>,
    pub target: String,
    pub step_index: u16,
    pub remaining_steps: u16,
    pub expires_at_unix_ms: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct ContinuationLeaseReceipt {
    pub schema_version: &'static str,
    pub status: &'static str,
    pub lease_id: String,
    pub grant_state: &'static str,
    pub grant_ref_hash_hex: String,
    pub task_id: String,
    pub step_id: String,
    pub request_id: String,
    pub action_kind: String,
    pub canonical_input_digest_hex: String,
    pub expires_at_unix_ms: u64,
    pub postcondition_contract_kind: String,
}

/// Issue parameters. Every field comes from Rust-owned state (SpawnRecord /
/// ApprovalState); nothing here is trusted from Python or model output.
#[derive(Clone, Debug)]
pub struct ContinuationIssueRequest<'a> {
    pub task_id: &'a str,
    pub step_id: &'a str,
    pub parent_request_id: &'a str,
    pub parent_action_id: &'a str,
    pub parent_input_digest: &'a [u8; 32],
    pub session_id: &'a str,
    pub workspace_digest: &'a str,
    pub hidden_desktop: Option<&'a str>,
    pub target: &'a str,
    pub allowed_next_actions: &'a [String],
    pub expected_postcondition_kind: &'a str,
    pub step_index: u16,
    pub remaining_steps: u16,
    pub ttl_ms: u64,
    pub idempotency_key: &'a str,
}

fn sha256_bytes(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn unix_now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_millis() as u64)
        .unwrap_or(0)
}

fn valid_id(value: &str) -> bool {
    !value.trim().is_empty() && value.len() <= 128
}

fn random_handle(prefix: &str) -> String {
    let mut bytes = [0u8; 16];
    getrandom::getrandom(&mut bytes).expect("CSPRNG unavailable");
    format!("{prefix}_{}", hex(&bytes))
}

/// Single authoritative construction site for the expected continuation subject.
/// Domain-separated from the parent exact input digest: parent digest is one
/// field inside the subject, while the continuation-step digest is the subject
/// hash itself. Caller-supplied hex is never trusted; authority recomputes.
#[allow(clippy::too_many_arguments)]
pub fn build_continuation_subject_digest(
    parent_request_id: &str,
    parent_action_id: &str,
    parent_input_digest_hex: &str,
    task_id: &str,
    step_id: &str,
    step_index: u16,
    action_kind: &str,
    workspace_digest: &str,
    session_id: &str,
    hidden_desktop: Option<&str>,
    postcondition_kind: &str,
    continuation_input_digest_hex: &str,
) -> [u8; 32] {
    // Canonical JSON with sorted keys and escaped strings, hashed via SHA-256.
    // Order is fixed; adding a field is a breaking schema change.
    let mut out = String::with_capacity(512);
    out.push('{');
    out.push_str("\"schema_version\":\"cu-continuation-subject.v1\"");
    out.push_str(",\"parent_request_id\":\"");
    out.push_str(&escape_json_val(parent_request_id));
    out.push_str("\",\"parent_action_id\":\"");
    out.push_str(&escape_json_val(parent_action_id));
    out.push_str("\",\"parent_input_digest\":\"");
    out.push_str(&escape_json_val(parent_input_digest_hex));
    out.push_str("\",\"task_id\":\"");
    out.push_str(&escape_json_val(task_id));
    out.push_str("\",\"step_id\":\"");
    out.push_str(&escape_json_val(step_id));
    out.push_str("\",\"step_index\":");
    out.push_str(&step_index.to_string());
    out.push_str(",\"action_kind\":\"");
    out.push_str(&escape_json_val(action_kind));
    out.push_str("\",\"workspace_digest\":\"");
    out.push_str(&escape_json_val(workspace_digest));
    out.push_str("\",\"session_id\":\"");
    out.push_str(&escape_json_val(session_id));
    out.push_str("\",\"hidden_desktop\":\"");
    out.push_str(&escape_json_val(hidden_desktop.unwrap_or("")));
    out.push_str("\",\"postcondition_contract\":{\"kind\":\"");
    out.push_str(&escape_json_val(postcondition_kind));
    out.push_str("\"},\"continuation_input_digest\":\"");
    out.push_str(&escape_json_val(continuation_input_digest_hex));
    out.push_str("\"}");
    sha256_bytes(out.as_bytes())
}

fn escape_json_val(raw: &str) -> String {
    let mut escaped = String::with_capacity(raw.len());
    for ch in raw.chars() {
        match ch {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            c if c.is_control() => escaped.push_str(&format!("\\u{:04x}", c as u32)),
            c => escaped.push(c),
        }
    }
    escaped
}

/// Canonical minimal continuation input for one action kind. Single site so
/// issue-time and consume-time digests can never diverge per action.
fn canonical_continuation_input(action_kind: &str) -> [u8; 32] {
    sha256_bytes(format!("{{\"action\":\"{action_kind}\"}}").as_bytes())
}

/// Build the full per-action binding set (F-02). Every advertised action is
/// bound independently; there is no "primary action" shortcut.
#[allow(clippy::too_many_arguments)]
fn build_action_bindings(
    actions: &[String],
    parent_request_id: &str,
    parent_action_id: &str,
    parent_input_digest_hex: &str,
    task_id: &str,
    step_id: &str,
    next_step_index: u16,
    workspace_digest: &str,
    session_id: &str,
    hidden_desktop: Option<&str>,
    postcondition_kind: &str,
) -> Vec<ContinuationActionBinding> {
    actions
        .iter()
        .map(|action| {
            let input_digest = canonical_continuation_input(action);
            let subject = build_continuation_subject_digest(
                parent_request_id,
                parent_action_id,
                parent_input_digest_hex,
                task_id,
                step_id,
                next_step_index,
                action,
                workspace_digest,
                session_id,
                hidden_desktop,
                postcondition_kind,
                &hex(&input_digest),
            );
            ContinuationActionBinding {
                action_kind: action.clone(),
                expected_input_digest: input_digest,
                expected_subject_digest: subject,
            }
        })
        .collect()
}

struct ContinuationRegistryInner {
    grants: HashMap<[u8; 32], ContinuationGrantRecord>,
    /// idempotency_key -> grant_ref_hash
    idempotency: HashMap<String, [u8; 32]>,
}

static CONTINUATION_REGISTRY: Mutex<Option<ContinuationRegistryInner>> = Mutex::new(None);

fn with_registry<T>(
    f: impl FnOnce(&mut ContinuationRegistryInner) -> Result<T, &'static str>,
) -> Result<T, &'static str> {
    let mut guard = CONTINUATION_REGISTRY
        .lock()
        .map_err(|_| "continuation registry poisoned")?;
    let inner = guard.get_or_insert_with(|| ContinuationRegistryInner {
        grants: HashMap::new(),
        idempotency: HashMap::new(),
    });
    f(inner)
}

/// Issue a one-time continuation grant after a broker-owned parent launch.
/// Duplicate issue with the same idempotency key returns the same logical
/// receipt without creating a second capability.
pub fn issue_continuation_grant(
    request: &ContinuationIssueRequest<'_>,
) -> Result<ContinuationIssueReceipt, &'static str> {
    for value in [
        request.task_id,
        request.step_id,
        request.parent_request_id,
        request.parent_action_id,
        request.session_id,
        request.workspace_digest,
        request.target,
        request.idempotency_key,
    ] {
        if !valid_id(value) {
            return Err(ERR_INVALID_PAYLOAD);
        }
    }
    if request.allowed_next_actions.is_empty()
        || request
            .allowed_next_actions
            .iter()
            .any(|kind| !ALLOWED_NEXT_ACTION_KINDS.contains(&kind.as_str()))
    {
        return Err(ERR_POLICY_DENIED);
    }
    // F-02: never advertise a capability the host runtime cannot verify.
    if request
        .allowed_next_actions
        .iter()
        .any(|kind| !HOST_IMPLEMENTED_NEXT_ACTIONS.contains(&kind.as_str()))
    {
        return Err(ERR_POLICY_DENIED);
    }
    if request.ttl_ms == 0 || request.ttl_ms > MAX_TTL_MS {
        return Err(ERR_POLICY_DENIED);
    }
    if request.remaining_steps == 0 || request.remaining_steps > MAX_REMAINING_STEPS {
        return Err(ERR_POLICY_DENIED);
    }

    let token = random_handle("cgr");
    let grant_ref_hash = sha256_bytes(token.as_bytes());
    let deadline = Instant::now() + Duration::from_millis(request.ttl_ms);
    let now_unix = unix_now_ms();
    let expires_at_unix_ms = now_unix + request.ttl_ms;

    // F-02: independent binding per advertised action. Domain-separated.
    let parent_input_digest_hex = hex(request.parent_input_digest);
    let action_bindings = build_action_bindings(
        request.allowed_next_actions,
        request.parent_request_id,
        request.parent_action_id,
        &parent_input_digest_hex,
        request.task_id,
        request.step_id,
        request.step_index.wrapping_add(1),
        request.workspace_digest,
        request.session_id,
        request.hidden_desktop,
        request.expected_postcondition_kind,
    );

    with_registry(|inner| {
        if let Some(existing_hash) = inner.idempotency.get(request.idempotency_key) {
            let hash = *existing_hash;
            return match inner.grants.get(&hash) {
                Some(existing) => Ok(ContinuationIssueReceipt {
                    schema_version: CONTINUATION_GRANT_SCHEMA,
                    status: "issued",
                    // Duplicate issue: same logical receipt, raw token is NOT
                    // re-revealed (it was destroyed after first issuance).
                    grant_ref: String::new(),
                    grant_state: existing.state.as_wire(),
                    task_id: existing.task_id.clone(),
                    step_id: existing.step_id.clone(),
                    parent_request_id: existing.parent_request_id.clone(),
                    allowed_next_actions: existing.allowed_next_actions.clone(),
                    target: existing.target.clone(),
                    step_index: existing.step_index,
                    remaining_steps: existing.remaining_steps,
                    expires_at_unix_ms: existing.expires_at_unix_ms,
                }),
                None => Err(ERR_REPLAYED),
            };
        }
        inner
            .idempotency
            .insert(request.idempotency_key.to_owned(), grant_ref_hash);
        inner.grants.insert(
            grant_ref_hash,
            ContinuationGrantRecord {
                grant_ref_hash,
                task_id: request.task_id.to_owned(),
                step_id: request.step_id.to_owned(),
                parent_request_id: request.parent_request_id.to_owned(),
                parent_action_id: request.parent_action_id.to_owned(),
                parent_input_digest: *request.parent_input_digest,
                session_id: request.session_id.to_owned(),
                workspace_digest: request.workspace_digest.to_owned(),
                hidden_desktop: request.hidden_desktop.map(str::to_owned),
                target: request.target.to_owned(),
                allowed_next_actions: request.allowed_next_actions.to_vec(),
                expected_postcondition_kind: request.expected_postcondition_kind.to_owned(),
                step_index: request.step_index,
                remaining_steps: request.remaining_steps,
                action_bindings,
                issued_at_unix_ms: now_unix,
                expires_at_unix_ms,
                deadline,
                state: ContinuationState::Issued,
                lease_id: None,
            },
        );
        Ok(ContinuationIssueReceipt {
            schema_version: CONTINUATION_GRANT_SCHEMA,
            status: "issued",
            grant_ref: token,
            grant_state: ContinuationState::Issued.as_wire(),
            task_id: request.task_id.to_owned(),
            step_id: request.step_id.to_owned(),
            parent_request_id: request.parent_request_id.to_owned(),
            allowed_next_actions: request.allowed_next_actions.to_vec(),
            target: request.target.to_owned(),
            step_index: request.step_index,
            remaining_steps: request.remaining_steps,
            expires_at_unix_ms,
        })
    })
}

/// Atomically validate and lease a grant before the next host-side action.
#[allow(clippy::too_many_arguments)]
pub fn consume_continuation_grant(
    grant_ref: &str,
    task_id: &str,
    step_id: &str,
    request_id: &str,
    action_kind: &str,
    canonical_input_digest: &[u8; 32],
    session_id: &str,
    workspace_digest: &str,
    hidden_desktop: Option<&str>,
    expected_step_index: u16,
) -> Result<ContinuationLeaseReceipt, &'static str> {
    if !grant_ref.starts_with("cgr_") || grant_ref.len() < 8 {
        return Err(ERR_NOT_ISSUED_BY_BROKER);
    }
    let grant_ref_hash = sha256_bytes(grant_ref.as_bytes());
    with_registry(|inner| {
        let record = inner.grants.get_mut(&grant_ref_hash).ok_or(ERR_NOT_FOUND)?;
        match record.state {
            ContinuationState::Issued => {}
            ContinuationState::InFlight => return Err(ERR_IN_FLIGHT),
            ContinuationState::Revoked => return Err(ERR_REPLAYED),
            ContinuationState::Expired => return Err(ERR_EXPIRED),
            _ => return Err(ERR_REPLAYED),
        }
        if Instant::now() >= record.deadline {
            record.state = ContinuationState::Expired;
            return Err(ERR_EXPIRED);
        }
        if record.task_id != task_id {
            return Err(ERR_TASK_MISMATCH);
        }
        if record.step_id != step_id {
            return Err(ERR_STEP_MISMATCH);
        }
        if record.session_id != session_id {
            return Err(ERR_SESSION_MISMATCH);
        }
        if record.workspace_digest != workspace_digest {
            return Err(ERR_WORKSPACE_MISMATCH);
        }
        if record.hidden_desktop.is_some() && record.hidden_desktop.as_deref() != hidden_desktop {
            return Err(ERR_DESKTOP_MISMATCH);
        }
        if expected_step_index != record.step_index.wrapping_add(1) {
            return Err(ERR_STEP_MISMATCH);
        }
        if !record.allowed_next_actions.iter().any(|k| k == action_kind) {
            return Err(ERR_ACTION_MISMATCH);
        }
        if record.remaining_steps == 0 {
            return Err(ERR_BUDGET_EXHAUSTED);
        }
        // --- F-02 per-action digest binding: the ACTUAL action is validated
        // --- against ITS OWN issued binding, never the first advertised one.
        let binding = record
            .action_bindings
            .iter()
            .find(|binding| binding.action_kind == action_kind)
            .ok_or(ERR_ACTION_MISMATCH)?;
        // 1. Canonical input digest must equal THIS action's expected input.
        let expected_input_for_action = canonical_continuation_input(action_kind);
        if expected_input_for_action != *canonical_input_digest {
            return Err(ERR_INPUT_DIGEST_MISMATCH);
        }
        if binding.expected_input_digest != *canonical_input_digest {
            return Err(ERR_INPUT_DIGEST_MISMATCH);
        }
        // 2. Domain-separated subject digest recomputed from authoritative
        // fields must equal THIS action's issued subject binding.
        let parent_hex = hex(&record.parent_input_digest);
        let continuation_hex = hex(canonical_input_digest);
        let recomputed_subject = build_continuation_subject_digest(
            &record.parent_request_id,
            &record.parent_action_id,
            &parent_hex,
            &record.task_id,
            &record.step_id,
            expected_step_index,
            action_kind,
            &record.workspace_digest,
            &record.session_id,
            record.hidden_desktop.as_deref(),
            &record.expected_postcondition_kind,
            &continuation_hex,
        );
        if recomputed_subject != binding.expected_subject_digest {
            return Err(ERR_INPUT_DIGEST_MISMATCH);
        }
        // Atomic issued -> in_flight transition under the registry lock.
        record.state = ContinuationState::InFlight;
        record.remaining_steps -= 1;
        let lease = ContinuationLeaseReceipt {
            schema_version: CONTINUATION_GRANT_SCHEMA,
            status: "leased",
            lease_id: random_handle("lease"),
            grant_state: record.state.as_wire(),
            grant_ref_hash_hex: hex(&record.grant_ref_hash),
            task_id: record.task_id.clone(),
            step_id: record.step_id.clone(),
            request_id: request_id.to_owned(),
            action_kind: action_kind.to_owned(),
            canonical_input_digest_hex: hex(canonical_input_digest),
            expires_at_unix_ms: record.expires_at_unix_ms,
            postcondition_contract_kind: record.expected_postcondition_kind.clone(),
        };
        record.lease_id = Some(lease.lease_id.clone());
        Ok(lease)
    })
}

/// Complete a leased continuation. `pending` returns the grant to `issued`
/// so the bounded observe loop can continue within the original TTL window.
pub fn complete_continuation_grant(
    lease_id: &str,
    status: &str,
    postcondition_verified: bool,
) -> Result<(&'static str, &'static str), &'static str> {
    if lease_id.is_empty() {
        return Err(ERR_NOT_FOUND);
    }
    let wire_status: &'static str = match status {
        "verified" => "verified",
        "failed" => "failed",
        "blocked" => "blocked",
        "pending" => "pending",
        _ => return Err(ERR_INVALID_PAYLOAD),
    };
    with_registry(|inner| {
        let record = inner
            .grants
            .values_mut()
            .find(|record| record.lease_id.as_deref() == Some(lease_id))
            .ok_or(ERR_NOT_FOUND)?;
        if record.state != ContinuationState::InFlight {
            return Err(ERR_REPLAYED);
        }
        match wire_status {
            "verified" => {
                if !postcondition_verified {
                    return Err(ERR_POSTCONDITION_MISMATCH);
                }
                record.state = ContinuationState::CompletedVerified;
            }
            "failed" => record.state = ContinuationState::CompletedFailed,
            "blocked" => record.state = ContinuationState::CompletedBlocked,
            "pending" => {
                record.state = ContinuationState::Issued;
                record.lease_id = None;
                return Ok(("pending", "issued"));
            }
            _ => return Err(ERR_INVALID_PAYLOAD),
        }
        Ok((wire_status, record.state.as_wire()))
    })
}

/// Revoke one grant (by opaque ref) or every live grant when empty.
pub fn revoke_continuation_grants(grant_ref: &str) -> Result<usize, &'static str> {
    let target_hash = if grant_ref.is_empty() {
        None
    } else {
        Some(sha256_bytes(grant_ref.as_bytes()))
    };
    with_registry(|inner| {
        let mut revoked = 0usize;
        for record in inner.grants.values_mut() {
            let matches = match target_hash {
                Some(hash) => record.grant_ref_hash == hash,
                None => true,
            };
            if matches
                && matches!(
                    record.state,
                    ContinuationState::Issued | ContinuationState::InFlight
                )
            {
                record.state = ContinuationState::Revoked;
                revoked += 1;
            }
        }
        Ok(revoked)
    })
}

/// Recovery classification after an `in_flight` crash (master prompt §8.4):
/// a crashed lease must NEVER auto-replay its mutating observation. The
/// authority classifies it `recovery_required`; the orchestrator then maps it
/// to RECOVERING/PAUSED_FOR_REVIEW/EXPIRED and needs a fresh decision.
#[allow(dead_code)]
pub fn classify_crashed_grant(grant_ref: &str) -> Result<&'static str, &'static str> {
    let grant_ref_hash = sha256_bytes(grant_ref.as_bytes());
    with_registry(|inner| {
        let record = inner.grants.get_mut(&grant_ref_hash).ok_or(ERR_NOT_FOUND)?;
        match record.state {
            ContinuationState::InFlight => {
                record.state = ContinuationState::RecoveryRequired;
                record.lease_id = None;
                Ok("recovery_required")
            }
            other => Ok(other.as_wire()),
        }
    })
}

/// Domain-separated subject digest helper. Single construction site; used for
/// correlation/evidence only, never as authorization material by itself.
/// Phase 3 (task ledger) consumes this; kept public API until then.
#[allow(dead_code)]
pub fn continuation_subject_digest(parts: &[(&str, &str)]) -> [u8; 32] {
    let mut canonical = String::from("{\"schema_version\":\"cu-continuation-subject.v1\"");
    for (key, value) in parts {
        canonical.push_str(",\"");
        canonical.push_str(key);
        canonical.push_str("\":\"");
        canonical.push_str(value);
        canonical.push('"');
    }
    canonical.push('}');
    sha256_bytes(canonical.as_bytes())
}

/// Test/audit accessor: current wire state of a grant by opaque ref.
#[cfg(test)]
pub(crate) fn peek_state(grant_ref: &str) -> Option<&'static str> {
    let grant_ref_hash = sha256_bytes(grant_ref.as_bytes());
    with_registry(|inner| {
        Ok(inner
            .grants
            .get(&grant_ref_hash)
            .map(|record| record.state.as_wire()))
    })
    .ok()
    .flatten()
}

pub fn default_ttl_ms() -> u64 {
    DEFAULT_TTL_MS
}

#[cfg(test)]
mod tests {
    use super::*;

    const DIGEST: [u8; 32] = [7u8; 32];

    fn observe_input_digest() -> [u8; 32] {
        // Minimal valid continuation input for observe: {"action":"observe"}
        sha256_bytes(b"{\"action\":\"observe\"}")
    }
    fn wait_input_digest() -> [u8; 32] {
        sha256_bytes(b"{\"action\":\"wait\"}")
    }

    fn issue_request<'a>(
        task: &'a str,
        idem: &'a str,
        actions: &'a [String],
    ) -> ContinuationIssueRequest<'a> {
        ContinuationIssueRequest {
            task_id: task,
            step_id: "step_0000000000000001",
            parent_request_id: "0123456789abcdef01234567",
            parent_action_id: "call_0123456789abcdef0123456789ab",
            parent_input_digest: &DIGEST,
            session_id: "sess",
            workspace_digest: "ws",
            hidden_desktop: None,
            target: "chrome",
            allowed_next_actions: actions,
            expected_postcondition_kind: "browser_readiness",
            step_index: 0,
            remaining_steps: 2,
            ttl_ms: default_ttl_ms(),
            idempotency_key: idem,
        }
    }

    fn consume_ok(ref_: &str, task: &str) -> Result<ContinuationLeaseReceipt, &'static str> {
        let digest = observe_input_digest();
        consume_continuation_grant(
            ref_,
            task,
            "step_0000000000000001",
            "req_c",
            "observe",
            &digest,
            "sess",
            "ws",
            None,
            1,
        )
    }
    #[allow(dead_code)]
    fn consume_wait(ref_: &str, task: &str) -> Result<ContinuationLeaseReceipt, &'static str> {
        let digest = wait_input_digest();
        consume_continuation_grant(
            ref_,
            task,
            "step_0000000000000001",
            "req_c",
            "wait",
            &digest,
            "sess",
            "ws",
            None,
            1,
        )
    }

    #[test]
    fn issue_and_consume_happy_path_once() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_a", "idem_a", &actions)).expect("issue");
        assert!(receipt.grant_ref.starts_with("cgr_"));
        assert_eq!(peek_state(&receipt.grant_ref), Some("issued"));
        let lease = consume_ok(&receipt.grant_ref, "task_a").expect("consume");
        assert_eq!(lease.status, "leased");
        // One-time semantics: second consume while leased is typed in_flight.
        let replay = consume_ok(&receipt.grant_ref, "task_a");
        assert_eq!(replay.unwrap_err(), ERR_IN_FLIGHT);
        let (status, state) =
            complete_continuation_grant(&lease.lease_id, "verified", true).expect("complete");
        assert_eq!((status, state), ("verified", "completed_verified"));
    }

    #[test]
    fn issue_duplicate_idempotency_returns_same_logical_receipt() {
        let actions = vec!["observe".to_string()];
        let first =
            issue_continuation_grant(&issue_request("task_b", "idem_b", &actions)).expect("first");
        let second =
            issue_continuation_grant(&issue_request("task_b", "idem_b", &actions)).expect("dupe");
        assert!(
            second.grant_ref.is_empty(),
            "raw token must not be re-revealed"
        );
        assert_eq!(first.task_id, second.task_id);
    }

    #[test]
    fn consume_mismatches_are_typed_fail_closed() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_c", "idem_c", &actions)).expect("issue");
        let od = observe_input_digest();
        let wrong_task = consume_continuation_grant(
            &receipt.grant_ref,
            "other",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "ws",
            None,
            1,
        );
        assert_eq!(wrong_task.unwrap_err(), ERR_TASK_MISMATCH);
        let wrong_action = consume_continuation_grant(
            &receipt.grant_ref,
            "task_c",
            "step_0000000000000001",
            "r",
            "type_element",
            &od,
            "sess",
            "ws",
            None,
            1,
        );
        assert_eq!(wrong_action.unwrap_err(), ERR_ACTION_MISMATCH);
        let wrong_step = consume_continuation_grant(
            &receipt.grant_ref,
            "task_c",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "ws",
            None,
            5,
        );
        assert_eq!(wrong_step.unwrap_err(), ERR_STEP_MISMATCH);
        let wrong_session = consume_continuation_grant(
            &receipt.grant_ref,
            "task_c",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "other",
            "ws",
            None,
            1,
        );
        assert_eq!(wrong_session.unwrap_err(), ERR_SESSION_MISMATCH);
        let wrong_workspace = consume_continuation_grant(
            &receipt.grant_ref,
            "task_c",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "other",
            None,
            1,
        );
        assert_eq!(wrong_workspace.unwrap_err(), ERR_WORKSPACE_MISMATCH);
    }

    #[test]
    fn revoke_blocks_consume() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_d", "idem_d", &actions)).expect("issue");
        assert_eq!(
            revoke_continuation_grants(&receipt.grant_ref).unwrap_or(0),
            1
        );
        let consumed = consume_ok(&receipt.grant_ref, "task_d");
        assert_eq!(consumed.unwrap_err(), ERR_REPLAYED);
    }

    #[test]
    fn complete_requires_postcondition_and_is_terminal_once() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_e", "idem_e", &actions)).expect("issue");
        let lease = consume_ok(&receipt.grant_ref, "task_e").expect("consume");
        let optimistic = complete_continuation_grant(&lease.lease_id, "verified", false);
        assert_eq!(optimistic.unwrap_err(), ERR_POSTCONDITION_MISMATCH);
        // Pending completion returns the grant to issued for the observe loop.
        let (status, state) =
            complete_continuation_grant(&lease.lease_id, "pending", false).expect("pending");
        assert_eq!((status, state), ("pending", "issued"));
        let lease2 = consume_ok(&receipt.grant_ref, "task_e").expect("re-consume");
        let (_, state2) =
            complete_continuation_grant(&lease2.lease_id, "failed", false).expect("failed");
        assert_eq!(state2, "completed_failed");
        let stale = complete_continuation_grant(&lease2.lease_id, "verified", true);
        assert_eq!(stale.unwrap_err(), ERR_REPLAYED);
    }

    #[test]
    fn foreign_token_shapes_are_rejected() {
        let actions = vec!["observe".to_string()];
        let _ = issue_continuation_grant(&issue_request("task_f", "idem_f", &actions));
        let od = observe_input_digest();
        let bogus = consume_continuation_grant(
            "not_aGrant",
            "task_f",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "ws",
            None,
            1,
        );
        assert_eq!(bogus.unwrap_err(), ERR_NOT_ISSUED_BY_BROKER);
    }

    #[test]
    fn policy_denies_unallowlisted_next_actions_and_bad_ttl() {
        let denied_actions = vec!["open_url".to_string()];
        let denied = issue_continuation_grant(&issue_request("task_g", "idem_g", &denied_actions));
        assert_eq!(denied.unwrap_err(), ERR_POLICY_DENIED);
        let ok_actions = vec!["observe".to_string()];
        let mut request = issue_request("task_g", "idem_g2", &ok_actions);
        request.ttl_ms = 0;
        assert_eq!(
            issue_continuation_grant(&request).unwrap_err(),
            ERR_POLICY_DENIED
        );
    }

    /// F-02: actions without a host-side postcondition implementation must
    /// never be advertised — issuing a grant that names them is policy-denied.
    #[test]
    fn unsupported_actions_are_not_advertisable() {
        for kind in ["wait", "wait_for_window", "type_element", "press_key"] {
            let actions = vec![kind.to_string()];
            let denied = issue_continuation_grant(&issue_request("task_f02", "idem_f02", &actions));
            assert_eq!(
                denied.unwrap_err(),
                ERR_POLICY_DENIED,
                "{kind} has no host postcondition implementation"
            );
        }
    }

    /// F-02 positive test: the advertised action set consumes through its OWN
    /// binding. Each supported action gets an independent issue→consume round.
    #[test]
    fn every_host_implemented_action_consumes_through_its_own_binding() {
        for kind in HOST_IMPLEMENTED_NEXT_ACTIONS {
            let actions = vec![kind.to_string()];
            let receipt = issue_continuation_grant(&issue_request(
                "task_f02p",
                &format!("idem_f02p_{kind}"),
                &actions,
            ))
            .expect("issue for supported action");
            assert_eq!(receipt.allowed_next_actions, vec![kind.to_string()]);
            let digest = canonical_continuation_input(kind);
            let lease = consume_continuation_grant(
                &receipt.grant_ref,
                "task_f02p",
                "step_0000000000000001",
                "req_f02p",
                kind,
                &digest,
                "sess",
                "ws",
                None,
                1,
            )
            .expect("consume through own binding");
            complete_continuation_grant(&lease.lease_id, "verified", true).expect("complete");
        }
    }

    /// F-02 mechanism: bindings are per-action even when several actions are
    /// bound together — digests and subjects never collide across actions.
    #[test]
    fn action_bindings_are_independent_per_action() {
        let actions = vec!["observe".to_string(), "wait".to_string()];
        let parent_hex = hex(&DIGEST);
        let bindings = build_action_bindings(
            &actions,
            "req",
            "call",
            &parent_hex,
            "task_bind",
            "step_1",
            1,
            "ws",
            "sess",
            None,
            "browser_readiness",
        );
        assert_eq!(bindings.len(), 2);
        assert_ne!(
            bindings[0].expected_input_digest,
            bindings[1].expected_input_digest
        );
        assert_ne!(
            bindings[0].expected_subject_digest,
            bindings[1].expected_subject_digest
        );
        // Deterministic rebuild matches byte-for-byte.
        let again = build_action_bindings(
            &actions,
            "req",
            "call",
            &parent_hex,
            "task_bind",
            "step_1",
            1,
            "ws",
            "sess",
            None,
            "browser_readiness",
        );
        assert_eq!(bindings, again);
    }

    #[test]
    fn subject_digest_is_deterministic_and_domain_separated() {
        let a = continuation_subject_digest(&[("k", "v")]);
        let b = continuation_subject_digest(&[("k", "v")]);
        let c = continuation_subject_digest(&[("k", "other")]);
        assert_eq!(a, b);
        assert_ne!(a, c);
    }

    #[test]
    fn altered_continuation_input_digest_is_rejected() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_h", "idem_h", &actions)).expect("issue");
        // Tampered payload: extra field changes canonical digest
        let tampered = sha256_bytes(b"{\"action\":\"observe\",\"extra\":\"evil\"}");
        let res = consume_continuation_grant(
            &receipt.grant_ref,
            "task_h",
            "step_0000000000000001",
            "req_t",
            "observe",
            &tampered,
            "sess",
            "ws",
            None,
            1,
        );
        assert_eq!(res.unwrap_err(), ERR_INPUT_DIGEST_MISMATCH);
    }

    #[test]
    fn altered_subject_binding_is_rejected() {
        // Different workspace must fail even if input digest is correct
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_i", "idem_i", &actions)).expect("issue");
        let od = observe_input_digest();
        // Workspace mismatch already typed, but also subject would mismatch if we bypass direct check.
        // Ensure digest path also fails when we use wrong hidden desktop.
        let mut req = issue_request("task_j", "idem_j", &actions);
        req.hidden_desktop = Some("hiddenA");
        let receipt2 = issue_continuation_grant(&req).expect("issue hidden");
        let res = consume_continuation_grant(
            &receipt2.grant_ref,
            "task_j",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "ws",
            Some("hiddenB"),
            1,
        );
        assert_eq!(res.unwrap_err(), ERR_DESKTOP_MISMATCH);
        // Ensure correct hidden still requires correct input digest
        let res2 = consume_continuation_grant(
            &receipt.grant_ref,
            "task_i",
            "step_0000000000000001",
            "r",
            "observe",
            &od,
            "sess",
            "ws",
            None,
            1,
        );
        assert!(res2.is_ok());
    }

    #[test]
    fn continuation_subject_is_single_construction_site() {
        let parent_hex = hex(&DIGEST);
        let od_hex = hex(&observe_input_digest());
        let s1 = build_continuation_subject_digest(
            "req1",
            "call1",
            &parent_hex,
            "task1",
            "step1",
            1,
            "observe",
            "ws1",
            "sess1",
            None,
            "browser_readiness",
            &od_hex,
        );
        let s2 = build_continuation_subject_digest(
            "req1",
            "call1",
            &parent_hex,
            "task1",
            "step1",
            1,
            "observe",
            "ws1",
            "sess1",
            None,
            "browser_readiness",
            &od_hex,
        );
        assert_eq!(s1, s2);
        let s3 = build_continuation_subject_digest(
            "req1",
            "call1",
            &parent_hex,
            "task1",
            "step1",
            1,
            "wait",
            "ws1",
            "sess1",
            None,
            "browser_readiness",
            &od_hex,
        );
        assert_ne!(s1, s3);
    }

    #[test]
    fn input_digest_mismatch_is_typed() {
        let actions = vec!["observe".to_string()];
        let receipt =
            issue_continuation_grant(&issue_request("task_k", "idem_k", &actions)).expect("issue");
        // Use wait digest with observe action -> mismatch (action allows observe only)
        let wd = wait_input_digest();
        let res = consume_continuation_grant(
            &receipt.grant_ref,
            "task_k",
            "step_0000000000000001",
            "r",
            "observe",
            &wd,
            "sess",
            "ws",
            None,
            1,
        );
        assert_eq!(res.unwrap_err(), ERR_INPUT_DIGEST_MISMATCH);
    }

    #[test]
    fn in_flight_crash_never_auto_replays() {
        let actions = vec!["observe".to_string()];
        let receipt = issue_continuation_grant(&issue_request("task_rec", "idem_rec", &actions))
            .expect("issue");
        let lease = consume_ok(&receipt.grant_ref, "task_rec").expect("consume");
        // Crash while leased: classification moves to recovery_required…
        assert_eq!(
            classify_crashed_grant(&receipt.grant_ref).unwrap(),
            "recovery_required"
        );
        // …and the stale lease is destroyed: late complete can never replay.
        let stale = complete_continuation_grant(&lease.lease_id, "verified", true);
        assert_eq!(stale.unwrap_err(), ERR_NOT_FOUND);
        // Recovery state is terminal for consume as well.
        let reconsume = consume_ok(&receipt.grant_ref, "task_rec");
        assert_eq!(reconsume.unwrap_err(), ERR_REPLAYED);
    }
}
