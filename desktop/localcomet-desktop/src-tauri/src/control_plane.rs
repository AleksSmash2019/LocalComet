use crate::approval::canonical_input_digest;
use crate::artifact_trust::ArtifactTrustService;
use crate::files::SelectedFilesManager;
use crate::ipc;
use crate::managed_runtime::ManagedRuntimeSupervisor;
use crate::supervisor::{DesktopSidecarSupervisor, SidecarFrameRouter};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager, State};

pub const DESKTOP_STATUS_BRIDGE_VERSION: &str = "v6.84.6";
const LOCALCOMET_PACKAGE_METADATA: &str = include_str!("../../package.json");
pub const CONTROL_PLANE_EVENT_CHANNEL: &str = "localcomet://control-plane-event";
pub const MAX_IN_FLIGHT_REQUESTS: usize = 32;
pub const HARD_MAX_IN_FLIGHT_REQUESTS: usize = 64;
pub const MAX_EVENTS_PER_REQUEST: usize = 64;
pub const MAX_EVENT_TEXT_PER_REQUEST: usize = 1_048_576;
pub const MAX_TITLE_CHARS: usize = 120;
pub const MAX_PROMPT_CHARS: usize = 8192;
pub const MAX_DELTA_CHARS: usize = 65_536;
pub const MIN_MODEL_PORT: u16 = 1024;
pub const MAX_MODEL_PROMPT_CHARS: usize = 16_384;
pub const MAX_MODEL_EVENTS_PER_REQUEST: usize = 2_048;
pub const MAX_MODEL_EVENT_TEXT_PER_REQUEST: usize = 262_144;
pub const MAX_KNOWLEDGE_REVIEW_OFFSET: u16 = 128;
pub const MAX_KNOWLEDGE_REVIEW_LIMIT: u16 = 50;
pub const MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES: usize = 1_048_576;
pub const MAX_REVIEW_COMMENT_CHARS: usize = 2_000;
pub const MAX_REVIEW_COMMENT_BYTES: usize = 4_096;
pub const MAX_REVIEW_ACTOR_IDENTIFIER_CHARS: usize = 256;
pub const MAX_REVIEW_ACTOR_IDENTIFIER_BYTES: usize = 512;
pub const MAX_REVIEW_ACTOR_DISPLAY_NAME_CHARS: usize = 256;
pub const MAX_REVIEW_ACTOR_DISPLAY_NAME_BYTES: usize = 512;
pub const MAX_REVIEW_ACTOR_SOURCE_CHARS: usize = 128;
pub const MAX_REVIEW_ACTOR_SOURCE_BYTES: usize = 256;
pub const KNOWLEDGE_CHANGE_REVIEW_CONTRACT: &str = "localcomet.knowledge-change-review/1.0";
pub const KNOWLEDGE_REVIEW_ACTOR_SOURCE: &str = "LOCALCOMET_REVIEW_CENTER";
pub const MAX_ARGUMENT_BYTES: usize = 65_536;
pub const MAX_ARGUMENT_DEPTH: usize = 32;
pub const MAX_ARGUMENT_OBJECT_KEYS: usize = 512;
pub const MAX_ARGUMENT_NODES: usize = 4_096;

const _: () = assert!(HARD_MAX_IN_FLIGHT_REQUESTS >= MAX_IN_FLIGHT_REQUESTS);

const REQUEST_TIMEOUT: Duration = Duration::from_secs(5);
const MOCK_TURN_TIMEOUT: Duration = Duration::from_secs(10);
const CANCEL_TIMEOUT: Duration = Duration::from_secs(5);
const MODEL_ATTACH_TIMEOUT: Duration = Duration::from_secs(300);
const MODEL_DETACH_TIMEOUT: Duration = Duration::from_secs(2);
const MODEL_REQUEST_WATCHDOG_TIMEOUT: Duration = Duration::from_secs(125);

pub(crate) const REGISTERED_MODEL_TOOLS: &[&str] = &[
    "files.read",
    "files.list",
    "files.write",
    "files.create_folder",
    "files.delete",
    "shell",
    "computer_use",
    "web.search",
    "web.fetch",
];

const _: () = assert!(REGISTERED_MODEL_TOOLS.len() == 9);

#[derive(Clone, Copy)]
struct ModelToolArgumentSchema {
    required_string_fields: &'static [&'static str],
    optional_string_fields: &'static [&'static str],
    optional_array_fields: &'static [&'static str],
}

fn model_tool_argument_schema(name: &str) -> Option<ModelToolArgumentSchema> {
    match name {
        "files.read" | "files.list" | "files.create_folder" | "files.delete" => {
            Some(ModelToolArgumentSchema {
                required_string_fields: &["path"],
                optional_string_fields: &[],
                optional_array_fields: &[],
            })
        }
        "files.write" => Some(ModelToolArgumentSchema {
            required_string_fields: &["path", "content"],
            optional_string_fields: &[],
            optional_array_fields: &[],
        }),
        "shell" => Some(ModelToolArgumentSchema {
            required_string_fields: &["command"],
            optional_string_fields: &[],
            optional_array_fields: &[],
        }),
        "computer_use" => Some(ModelToolArgumentSchema {
            required_string_fields: &["action"],
            optional_string_fields: &["text"],
            optional_array_fields: &["coordinate"],
        }),
        "web.search" => Some(ModelToolArgumentSchema {
            required_string_fields: &["query"],
            optional_string_fields: &[],
            optional_array_fields: &[],
        }),
        "web.fetch" => Some(ModelToolArgumentSchema {
            required_string_fields: &["url"],
            optional_string_fields: &[],
            optional_array_fields: &[],
        }),
        _ => None,
    }
}

fn validate_model_tool_arguments(name: &str, arguments: &Value) -> Result<(), BridgeError> {
    let schema = model_tool_argument_schema(name)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "tool is not registered"))?;
    let object = arguments.as_object().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "tool call arguments must be an object")
    })?;
    for key in object.keys() {
        if !schema.required_string_fields.contains(&key.as_str())
            && !schema.optional_string_fields.contains(&key.as_str())
            && !schema.optional_array_fields.contains(&key.as_str())
        {
            let message = format!("tool {name} has unknown argument field {key}");
            return Err(BridgeError::new("protocol_mismatch", &message));
        }
    }
    for field in schema.required_string_fields {
        match object.get(*field) {
            None => {
                let message = format!("tool {name} missing required argument field {field}");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
            Some(Value::String(_)) => {}
            Some(_) => {
                let message = format!("tool {name} argument field {field} must be a string");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    for field in schema.optional_string_fields {
        if let Some(val) = object.get(*field) {
            if !val.is_string() {
                let message = format!("tool {name} argument field {field} must be a string");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    for field in schema.optional_array_fields {
        if let Some(val) = object.get(*field) {
            if !val.is_array() {
                let message = format!("tool {name} argument field {field} must be an array");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum ControlPlaneMethod {
    AppBootstrap,
    AppStatus,
    SessionCreate,
    SessionGet,
    SessionClose,
    ThreadCreate,
    ThreadGet,
    TurnStartMock,
    TurnStatus,
    TurnCancel,
    ModelCatalogGet,
    ModelGatewayProbe,
    ModelModelsList,
    ModelBindingSet,
    ModelTurnStart,
    ModelTurnCancel,
    ModelManagedAttach,
    ModelManagedDetach,
    KnowledgeTurnPreview,
    KnowledgeTurnDecide,
    KnowledgeReviewList,
    KnowledgeReviewGet,
    KnowledgeReviewSnapshot,
    KnowledgeReviewRefresh,
    KnowledgeReviewDecisionCreate,
    ToolCall,
}

impl ControlPlaneMethod {
    pub fn as_wire(self) -> &'static str {
        match self {
            Self::AppBootstrap => "app.bootstrap",
            Self::AppStatus => "app.status",
            Self::SessionCreate => "session.create",
            Self::SessionGet => "session.get",
            Self::SessionClose => "session.close",
            Self::ThreadCreate => "thread.create",
            Self::ThreadGet => "thread.get",
            Self::TurnStartMock => "turn.start_mock",
            Self::TurnStatus => "turn.status",
            Self::TurnCancel => "turn.cancel",
            Self::ModelCatalogGet => "model.catalog.get",
            Self::ModelGatewayProbe => "model.gateway.probe",
            Self::ModelModelsList => "model.models.list",
            Self::ModelBindingSet => "model.binding.set",
            Self::ModelTurnStart => "model.turn.start",
            Self::ModelTurnCancel => "model.turn.cancel",
            Self::ModelManagedAttach => "model.managed.attach",
            Self::ModelManagedDetach => "model.managed.detach",
            Self::KnowledgeTurnPreview => "knowledge.turn.preview",
            Self::KnowledgeTurnDecide => "knowledge.turn.decide",
            Self::KnowledgeReviewList => "knowledge.review.list",
            Self::KnowledgeReviewGet => "knowledge.review.get",
            Self::KnowledgeReviewSnapshot => "knowledge.review.snapshot",
            Self::KnowledgeReviewRefresh => "knowledge.review.refresh",
            Self::KnowledgeReviewDecisionCreate => "knowledge.review.decision.create",
            Self::ToolCall => "tool.call",
        }
    }

    fn timeout(self) -> Duration {
        match self {
            Self::TurnStartMock => MOCK_TURN_TIMEOUT,
            Self::TurnCancel => CANCEL_TIMEOUT,
            Self::ModelGatewayProbe | Self::ModelModelsList => Duration::from_secs(8),
            Self::ModelTurnStart
            | Self::ModelTurnCancel
            | Self::KnowledgeTurnDecide
            | Self::KnowledgeReviewDecisionCreate
            | Self::ToolCall => Duration::from_secs(5),
            Self::ModelManagedAttach => MODEL_ATTACH_TIMEOUT,
            Self::ModelManagedDetach => MODEL_DETACH_TIMEOUT,
            Self::KnowledgeTurnPreview => Duration::from_secs(15),
            _ => REQUEST_TIMEOUT,
        }
    }
}

pub const CONTROL_PLANE_METHOD_COUNT: usize = 26;
pub const CONTROL_PLANE_METHOD_VOCABULARY: [(&str, ControlPlaneMethod);
    CONTROL_PLANE_METHOD_COUNT] = [
    ("app.bootstrap", ControlPlaneMethod::AppBootstrap),
    ("app.status", ControlPlaneMethod::AppStatus),
    ("session.create", ControlPlaneMethod::SessionCreate),
    ("session.get", ControlPlaneMethod::SessionGet),
    ("session.close", ControlPlaneMethod::SessionClose),
    ("thread.create", ControlPlaneMethod::ThreadCreate),
    ("thread.get", ControlPlaneMethod::ThreadGet),
    ("turn.start_mock", ControlPlaneMethod::TurnStartMock),
    ("turn.status", ControlPlaneMethod::TurnStatus),
    ("turn.cancel", ControlPlaneMethod::TurnCancel),
    ("model.catalog.get", ControlPlaneMethod::ModelCatalogGet),
    ("model.gateway.probe", ControlPlaneMethod::ModelGatewayProbe),
    ("model.models.list", ControlPlaneMethod::ModelModelsList),
    ("model.binding.set", ControlPlaneMethod::ModelBindingSet),
    ("model.turn.start", ControlPlaneMethod::ModelTurnStart),
    ("model.turn.cancel", ControlPlaneMethod::ModelTurnCancel),
    (
        "model.managed.attach",
        ControlPlaneMethod::ModelManagedAttach,
    ),
    (
        "model.managed.detach",
        ControlPlaneMethod::ModelManagedDetach,
    ),
    (
        "knowledge.turn.preview",
        ControlPlaneMethod::KnowledgeTurnPreview,
    ),
    (
        "knowledge.turn.decide",
        ControlPlaneMethod::KnowledgeTurnDecide,
    ),
    (
        "knowledge.review.list",
        ControlPlaneMethod::KnowledgeReviewList,
    ),
    (
        "knowledge.review.get",
        ControlPlaneMethod::KnowledgeReviewGet,
    ),
    (
        "knowledge.review.snapshot",
        ControlPlaneMethod::KnowledgeReviewSnapshot,
    ),
    (
        "knowledge.review.refresh",
        ControlPlaneMethod::KnowledgeReviewRefresh,
    ),
    (
        "knowledge.review.decision.create",
        ControlPlaneMethod::KnowledgeReviewDecisionCreate,
    ),
    ("tool.call", ControlPlaneMethod::ToolCall),
];

#[derive(Clone, Debug, Serialize)]
pub struct BridgeError {
    pub code: String,
    pub message: String,
}

impl BridgeError {
    pub(crate) fn new(code: &str, message: &str) -> Self {
        Self {
            code: sanitize_text(code, 64),
            message: sanitize_text(message, 256),
        }
    }

    fn unavailable(message: &str) -> Self {
        Self::new("sidecar_unavailable", message)
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UiControlPlaneEvent {
    pub method: String,
    pub sequence: u64,
    pub reply_to: String,
    pub request_id: Option<String>,
    pub chat_session_id: Option<String>,
    pub model_id: Option<String>,
    pub control_plane_version: String,
    pub session_id: Option<String>,
    pub thread_id: Option<String>,
    pub turn_id: Option<String>,
    pub item_id: Option<String>,
    pub state: String,
    pub kind: Option<String>,
    pub text: Option<String>,
    pub metadata: Value,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct AssistantApplicationContext {
    name: &'static str,
    mode: &'static str,
    version: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct AssistantConversationContext {
    locale: String,
    project_context_available: bool,
    selected_files_context_available: bool,
    messages: Vec<Value>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct AssistantCapabilities {
    local_chat: bool,
    local_model_inference: bool,
    internet: bool,
    email: bool,
    browser: bool,
    filesystem: bool,
    vault: bool,
    computer_use: bool,
    shell: bool,
    tools: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentPermissions {
    pub files: bool,
    pub shell: bool,
    pub tools: bool,
    #[serde(rename = "computerUse")]
    pub computer_use: bool,
    #[serde(default)]
    pub internet: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct AssistantContext {
    application: AssistantApplicationContext,
    conversation: AssistantConversationContext,
    capabilities: AssistantCapabilities,
}

impl AssistantContext {
    fn trusted(
        locale: &str,
        selected_files_context_available: bool,
        permissions: Option<&AgentPermissions>,
        messages: Vec<Value>,
    ) -> Result<Self, BridgeError> {
        if !matches!(locale, "ru" | "en") {
            return Err(BridgeError::new(
                "invalid_payload",
                "assistant locale is unsupported",
            ));
        }
        Ok(Self {
            application: AssistantApplicationContext {
                name: "LocalComet",
                mode: "local_offline_desktop_assistant",
                version: application_version_from_package_metadata()?,
            },
            conversation: AssistantConversationContext {
                locale: locale.to_owned(),
                project_context_available: false,
                selected_files_context_available,
                messages,
            },
            capabilities: AssistantCapabilities {
                local_chat: true,
                local_model_inference: true,
                internet: permissions.map(|p| p.internet).unwrap_or(false),
                email: false,
                browser: permissions.map(|p| p.internet).unwrap_or(false),
                filesystem: permissions.map(|p| p.files).unwrap_or(false),
                vault: false,
                computer_use: permissions.map(|p| p.computer_use).unwrap_or(false),
                shell: permissions.map(|p| p.shell).unwrap_or(false),
                tools: {
                    let mut t = Vec::new();
                    if permissions.map(|p| p.files).unwrap_or(false) {
                        t.push("files.read".into());
                        t.push("files.list".into());
                        t.push("files.write".into());
                        t.push("files.create_folder".into());
                        t.push("files.delete".into());
                    }
                    if permissions.map(|p| p.shell).unwrap_or(false) {
                        t.push("shell".into());
                    }
                    if permissions.map(|p| p.computer_use).unwrap_or(false) {
                        t.push("computer_use".into());
                    }
                    if permissions.map(|p| p.internet).unwrap_or(false) {
                        t.push("web.search".into());
                        t.push("web.fetch".into());
                    }
                    if permissions.map(|p| p.tools).unwrap_or(false) {
                        // In future, sidecar tools could be added here
                    }
                    t
                },
            },
        })
    }
}

fn application_version_from_package_metadata() -> Result<String, BridgeError> {
    let metadata: Value = serde_json::from_str(LOCALCOMET_PACKAGE_METADATA)
        .map_err(|_| BridgeError::new("invalid_payload", "application metadata is invalid"))?;
    let raw = metadata
        .get("version")
        .and_then(Value::as_str)
        .ok_or_else(|| BridgeError::new("invalid_payload", "application version is missing"))?;
    let version = raw.strip_prefix("0.0.0-").unwrap_or(raw);
    if version != DESKTOP_STATUS_BRIDGE_VERSION {
        return Err(BridgeError::new(
            "invalid_payload",
            "application version metadata is inconsistent",
        ));
    }
    Ok(version.to_owned())
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ModelRequestIdentity {
    request_id: String,
    chat_session_id: String,
    model_id: String,
    submitted_at_unix_ms: u64,
    max_tokens: u16,
    binding_fingerprint: String,
}

#[derive(Debug, Default)]
struct ModelRequestWatchdog {
    cancelled: Mutex<bool>,
    wake: Condvar,
}

impl ModelRequestWatchdog {
    fn cancel(&self) {
        let mut cancelled = self
            .cancelled
            .lock()
            .expect("model request watchdog poisoned");
        *cancelled = true;
        self.wake.notify_all();
    }

    fn wait_for_timeout(&self, timeout: Duration) -> bool {
        let cancelled = self
            .cancelled
            .lock()
            .expect("model request watchdog poisoned");
        let (cancelled, result) = self
            .wake
            .wait_timeout_while(cancelled, timeout, |cancelled| !*cancelled)
            .expect("model request watchdog wait poisoned");
        !*cancelled && result.timed_out()
    }
}

#[derive(Debug)]
struct ModelRequestEntry {
    identity: ModelRequestIdentity,
    provider_id: Option<String>,
    harness_id: Option<String>,
    knowledge_model: bool,
    knowledge_acceptance_seen: bool,
    knowledge_injection_id: Option<String>,
    knowledge_included: bool,
    watchdog: Arc<ModelRequestWatchdog>,
    accepted: bool,
    cancel_pending: bool,
    cancel_accepted: bool,
    cancel_requested_before_acceptance: bool,
    cancel_after_synthetic_release: bool,
    releasing_events: bool,
    remove_after_release: bool,
    started_seen: bool,
    terminal_seen: bool,
    next_sequence: u64,
    event_count: usize,
    event_text: usize,
    model_called: bool,
    generated_bytes: u64,
    buffered_events: Vec<UiControlPlaneEvent>,
    tools_enabled: bool,
    permitted_tool_names: Vec<String>,
    intermediate_tool_calls: Vec<Value>,
    /// Digest of the canonical `model.turn.start` wire payload this reservation
    /// authorizes, including `assistant_context`. `None` until the reservation is
    /// bound (knowledge turns are registered post-dispatch and stay unbound, so
    /// they can never satisfy the dispatch check).
    reserved_wire_digest: Option<[u8; 32]>,
}

impl ModelRequestEntry {
    fn new(identity: ModelRequestIdentity, permitted_tool_names: Vec<String>) -> Self {
        let tools_enabled = !permitted_tool_names.is_empty();
        Self {
            identity,
            provider_id: None,
            harness_id: None,
            knowledge_model: false,
            knowledge_acceptance_seen: false,
            knowledge_injection_id: None,
            knowledge_included: false,
            watchdog: Arc::new(ModelRequestWatchdog::default()),
            accepted: false,
            cancel_pending: false,
            cancel_accepted: false,
            cancel_requested_before_acceptance: false,
            cancel_after_synthetic_release: false,
            releasing_events: false,
            remove_after_release: false,
            started_seen: false,
            terminal_seen: false,
            next_sequence: 0,
            event_count: 0,
            event_text: 0,
            model_called: false,
            generated_bytes: 0,
            buffered_events: Vec::new(),
            tools_enabled,
            permitted_tool_names,
            intermediate_tool_calls: Vec::new(),
            reserved_wire_digest: None,
        }
    }

    fn tools_are_enabled(&self) -> bool {
        debug_assert_eq!(self.tools_enabled, !self.permitted_tool_names.is_empty());
        self.tools_enabled
    }
}

impl Drop for ModelRequestEntry {
    fn drop(&mut self) {
        self.watchdog.cancel();
    }
}

#[derive(Default)]
struct ModelRequestRegistry {
    entries: HashMap<String, ModelRequestEntry>,
}

impl ModelRequestRegistry {
    fn insert(
        &mut self,
        identity: ModelRequestIdentity,
        permitted_tool_names: Vec<String>,
    ) -> Result<Arc<ModelRequestWatchdog>, BridgeError> {
        if self.entries.len() >= MAX_IN_FLIGHT_REQUESTS {
            return Err(BridgeError::new("busy", "model request registry is full"));
        }
        if self.entries.contains_key(&identity.request_id) {
            return Err(BridgeError::new(
                "duplicate_message_id",
                "duplicate model request id",
            ));
        }
        let entry = ModelRequestEntry::new(identity.clone(), permitted_tool_names);
        let watchdog = Arc::clone(&entry.watchdog);
        self.entries.insert(identity.request_id, entry);
        Ok(watchdog)
    }

    fn bind_reserved_wire_digest(
        &mut self,
        request_id: &str,
        wire_digest: [u8; 32],
    ) -> Result<(), BridgeError> {
        let entry = self.entries.get_mut(request_id).ok_or_else(|| {
            BridgeError::new("request_not_found", "model request reservation is missing")
        })?;
        if entry.reserved_wire_digest.is_some() {
            return Err(BridgeError::new(
                "protocol_mismatch",
                "model request reservation is already bound",
            ));
        }
        entry.reserved_wire_digest = Some(wire_digest);
        Ok(())
    }

    fn remove(&mut self, request_id: &str) -> Option<ModelRequestEntry> {
        self.entries.remove(request_id)
    }

    fn take_release_batch(&mut self, request_id: &str) -> Option<Vec<UiControlPlaneEvent>> {
        let remove_entry;
        let events;
        {
            let entry = self.entries.get_mut(request_id)?;
            if !entry.buffered_events.is_empty() {
                events = Some(std::mem::take(&mut entry.buffered_events));
                if entry.terminal_seen {
                    entry.remove_after_release = true;
                }
                remove_entry = false;
            } else {
                entry.releasing_events = false;
                remove_entry = entry.terminal_seen || entry.remove_after_release;
                events = None;
            }
        }
        if remove_entry {
            self.remove(request_id);
        }
        events
    }

    fn remove_or_queue_synthetic_terminal(
        &mut self,
        request_id: &str,
        method: &str,
        state: &str,
        code: &str,
        message: &str,
    ) -> Option<ModelRequestEntry> {
        let entry = self.entries.get_mut(request_id)?;
        if entry.releasing_events {
            if !entry.terminal_seen {
                let terminal = model_terminal_event(entry, method, state, code, message);
                entry.buffered_events.push(terminal);
                entry.next_sequence = entry.next_sequence.saturating_add(1);
                entry.event_count = entry.event_count.saturating_add(1);
                entry.terminal_seen = true;
                entry.cancel_after_synthetic_release = true;
            }
            return None;
        }
        self.remove(request_id)
    }
}

fn model_request_reservation_exists(
    registry: &Mutex<ModelRequestRegistry>,
    request_id: &str,
) -> bool {
    registry
        .lock()
        .expect("model request registry poisoned")
        .entries
        .contains_key(request_id)
}

/// Canonical `model.turn.start` wire payload. Single construction site so the
/// digest that authorizes a turn and the bytes that are framed cannot drift.
fn model_turn_wire_payload(
    identity: &ModelRequestIdentity,
    prompt: &str,
    assistant_context: &AssistantContext,
) -> Value {
    json!({
        "request_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "prompt": prompt,
        "assistant_context": assistant_context,
        "binding_fingerprint": identity.binding_fingerprint,
    })
}

/// Digest over every dispatched `model.turn.start` field, `assistant_context`
/// (application, conversation and the capability/tool grant) included.
fn model_turn_wire_digest(payload: &Value) -> [u8; 32] {
    canonical_input_digest(payload)
}

/// Fail-closed dispatch guard: the framed payload must hash to the digest the
/// reservation was created with. A reservation that is missing, unbound, or bound
/// to different bytes (including a different `assistant_context`) cannot dispatch.
fn model_request_reservation_authorizes_wire(
    registry: &Mutex<ModelRequestRegistry>,
    request_id: &str,
    wire_digest: &[u8; 32],
) -> Result<(), BridgeError> {
    if !model_request_reservation_exists(registry, request_id) {
        return Err(BridgeError::new(
            "request_not_found",
            "model request reservation expired before dispatch",
        ));
    }
    let registry = registry.lock().expect("model request registry poisoned");
    let Some(entry) = registry.entries.get(request_id) else {
        return Err(BridgeError::new(
            "request_not_found",
            "model request reservation expired before dispatch",
        ));
    };
    match entry.reserved_wire_digest {
        Some(reserved) if reserved == *wire_digest => Ok(()),
        _ => Err(BridgeError::new(
            "protocol_mismatch",
            "model turn payload does not match the reserved turn",
        )),
    }
}

#[derive(Default)]
struct PendingState {
    terminal: Option<Result<Value, BridgeError>>,
    next_sequence: u64,
    event_count: usize,
    event_text: usize,
    terminal_seen: bool,
}

struct PendingRequest {
    reply_to: String,
    knowledge_model: Option<PendingKnowledgeModel>,
    state: Mutex<PendingState>,
    ready: Condvar,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct PendingKnowledgeModel {
    turn_id: String,
    injection_id: String,
    preview_hash: String,
    include_knowledge: bool,
}

#[derive(Debug)]
struct KnowledgeAdmission {
    context: PendingKnowledgeModel,
    watchdog: Arc<ModelRequestWatchdog>,
}

impl KnowledgeAdmission {
    fn new(context: PendingKnowledgeModel) -> Self {
        Self {
            context,
            watchdog: Arc::new(ModelRequestWatchdog::default()),
        }
    }
}

impl Drop for KnowledgeAdmission {
    fn drop(&mut self) {
        self.watchdog.cancel();
    }
}

impl PendingRequest {
    fn new(reply_to: String, knowledge_model: Option<PendingKnowledgeModel>) -> Self {
        Self {
            reply_to,
            knowledge_model,
            state: Mutex::new(PendingState::default()),
            ready: Condvar::new(),
        }
    }
}

#[derive(Default)]
struct RequestRegistry {
    entries: HashMap<String, Arc<PendingRequest>>,
}

impl RequestRegistry {
    fn insert(
        &mut self,
        request_id: String,
        knowledge_model: Option<PendingKnowledgeModel>,
    ) -> Result<Arc<PendingRequest>, BridgeError> {
        if self.entries.len() >= MAX_IN_FLIGHT_REQUESTS {
            return Err(BridgeError::new("busy", "request registry is full"));
        }
        if self.entries.contains_key(&request_id) {
            return Err(BridgeError::new(
                "duplicate_message_id",
                "duplicate request id",
            ));
        }
        let pending = Arc::new(PendingRequest::new(request_id.clone(), knowledge_model));
        self.entries.insert(request_id, Arc::clone(&pending));
        Ok(pending)
    }

    fn get(&self, request_id: &str) -> Option<Arc<PendingRequest>> {
        self.entries.get(request_id).cloned()
    }

    fn remove(&mut self, request_id: &str) {
        self.entries.remove(request_id);
    }

    fn drain_all(&mut self) -> Vec<Arc<PendingRequest>> {
        self.entries.drain().map(|(_, pending)| pending).collect()
    }
}

pub struct ControlPlaneBridge {
    supervisor: Arc<DesktopSidecarSupervisor>,
    app: AppHandle,
    registry: Mutex<RequestRegistry>,
    model_requests: Arc<Mutex<ModelRequestRegistry>>,
    knowledge_admissions: Arc<Mutex<HashMap<String, KnowledgeAdmission>>>,
    request_counter: AtomicU64,
    warnings: Mutex<Vec<String>>,
}

impl ControlPlaneBridge {
    pub fn new(supervisor: Arc<DesktopSidecarSupervisor>, app: AppHandle) -> Self {
        validate_bridge_contract();
        Self {
            supervisor,
            app,
            registry: Mutex::new(RequestRegistry::default()),
            model_requests: Arc::new(Mutex::new(ModelRequestRegistry::default())),
            knowledge_admissions: Arc::new(Mutex::new(HashMap::new())),
            request_counter: AtomicU64::new(1),
            warnings: Mutex::new(Vec::new()),
        }
    }

    pub fn request(
        &self,
        method: ControlPlaneMethod,
        payload: Value,
    ) -> Result<Value, BridgeError> {
        self.request_with_timeout(method, payload, method.timeout())
    }

    pub(crate) fn request_with_timeout(
        &self,
        method: ControlPlaneMethod,
        payload: Value,
        timeout: Duration,
    ) -> Result<Value, BridgeError> {
        if timeout.is_zero() {
            return Err(BridgeError::new(
                "timeout",
                "control-plane request timed out",
            ));
        }
        self.ensure_ready()?;
        validate_payload_for_method(method, &payload)?;
        let knowledge_model = pending_knowledge_model(method, &payload);
        let request_id = self.next_request_id();
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .insert(request_id.clone(), knowledge_model.clone())?;
        let envelope = json!({
            "protocol": ipc::IPC_PROTOCOL,
            "version": ipc::IPC_PROTOCOL_VERSION,
            "type": "request",
            "id": request_id,
            "method": method.as_wire(),
            "run_id": null,
            "sequence": 0,
            "reply_to": null,
            "payload": payload,
        });
        let body = serde_json::to_string(&envelope)
            .map_err(|_| BridgeError::new("invalid_json", "request serialization failed"))?;
        let frame = ipc::json_frame(&body)
            .map_err(|_| BridgeError::new("invalid_frame", "request frame serialization failed"))?;
        if let Err(error) = self.supervisor.send_ipc_frame(frame) {
            self.registry
                .lock()
                .expect("control-plane registry poisoned")
                .remove(&request_id);
            return Err(BridgeError::unavailable(&error.to_string()));
        }
        let response = self.wait_for_terminal(&request_id, pending, timeout)?;
        if let Some(knowledge_model) = knowledge_model {
            let admission =
                if response.get("model_dispatched").and_then(Value::as_bool) == Some(true) {
                    self.register_knowledge_model_acceptance(&response, &knowledge_model)
                } else {
                    Ok(())
                };
            self.registry
                .lock()
                .expect("control-plane registry poisoned")
                .remove(&request_id);
            if let Err(error) = admission {
                if let Some(model_request_id) =
                    response.get("model_turn_id").and_then(Value::as_str)
                {
                    self.send_model_cancel_best_effort(model_request_id);
                }
                return Err(error);
            }
        }
        if matches!(
            method,
            ControlPlaneMethod::KnowledgeReviewList
                | ControlPlaneMethod::KnowledgeReviewGet
                | ControlPlaneMethod::KnowledgeReviewSnapshot
                | ControlPlaneMethod::KnowledgeReviewRefresh
                | ControlPlaneMethod::KnowledgeReviewDecisionCreate
        ) {
            ensure_knowledge_review_response_bound(&response)?;
        }
        Ok(response)
    }

    fn reserve_model_turn(
        self: &Arc<Self>,
        identity: &ModelRequestIdentity,
        permitted_tool_names: Vec<String>,
        wire_digest: [u8; 32],
    ) -> Result<(), BridgeError> {
        let watchdog = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let watchdog = registry.insert(identity.clone(), permitted_tool_names)?;
            if let Err(error) =
                registry.bind_reserved_wire_digest(&identity.request_id, wire_digest)
            {
                registry.remove(&identity.request_id);
                return Err(error);
            }
            watchdog
        };
        if let Err(error) = self.spawn_model_request_watchdog(identity.request_id.clone(), watchdog)
        {
            self.model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&identity.request_id);
            return Err(error);
        }
        Ok(())
    }

    fn request_model_turn_reserved(
        self: &Arc<Self>,
        identity: ModelRequestIdentity,
        prompt: String,
        assistant_context: AssistantContext,
    ) -> Result<Value, BridgeError> {
        let payload = model_turn_wire_payload(&identity, &prompt, &assistant_context);
        let response = match self.request_reserved_model_start(&identity.request_id, payload) {
            Ok(response) => response,
            Err(error) => {
                self.discard_unaccepted_model_request(&identity.request_id);
                return Err(error);
            }
        };
        let (provider_id, harness_id) = match validate_model_acceptance(&response, &identity) {
            Ok(binding) => binding,
            Err(error) => {
                self.discard_unaccepted_model_request(&identity.request_id);
                return Err(error);
            }
        };

        let release_events = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let Some(entry) = registry.entries.get_mut(&identity.request_id) else {
                drop(registry);
                self.discard_unaccepted_model_request(&identity.request_id);
                return Err(BridgeError::new(
                    "request_not_found",
                    "model request registry entry missing",
                ));
            };
            if entry
                .provider_id
                .as_deref()
                .is_some_and(|observed| observed != provider_id)
                || entry
                    .harness_id
                    .as_deref()
                    .is_some_and(|observed| observed != harness_id)
            {
                drop(registry);
                self.discard_unaccepted_model_request(&identity.request_id);
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "model acceptance provider or harness mismatch",
                ));
            }
            entry.provider_id = Some(provider_id.clone());
            entry.harness_id = Some(harness_id.clone());
            record_model_acceptance(entry)
        };
        if release_events.0 {
            self.release_model_events(&identity.request_id);
        }
        if release_events.1 {
            let _ = self.request_model_cancel(&identity.request_id);
        }
        Ok(project_model_acceptance(
            &identity,
            &provider_id,
            &harness_id,
        ))
    }

    fn request_reserved_model_start(
        &self,
        model_request_id: &str,
        payload: Value,
    ) -> Result<Value, BridgeError> {
        self.ensure_ready()?;
        validate_payload_for_method(ControlPlaneMethod::ModelTurnStart, &payload)?;
        let wire_digest = model_turn_wire_digest(&payload);
        let transport_id = self.next_request_id();
        let envelope = json!({
            "protocol": ipc::IPC_PROTOCOL,
            "version": ipc::IPC_PROTOCOL_VERSION,
            "type": "request",
            "id": transport_id,
            "method": ControlPlaneMethod::ModelTurnStart.as_wire(),
            "run_id": null,
            "sequence": 0,
            "reply_to": null,
            "payload": payload,
        });
        let body = serde_json::to_string(&envelope)
            .map_err(|_| BridgeError::new("invalid_json", "request serialization failed"))?;
        let frame = ipc::json_frame(&body)
            .map_err(|_| BridgeError::new("invalid_frame", "request frame serialization failed"))?;
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .insert(transport_id.clone(), None)?;
        let reservation_authorized = model_request_reservation_authorizes_wire(
            &self.model_requests,
            model_request_id,
            &wire_digest,
        );
        let send_result = match reservation_authorized {
            Ok(()) => self
                .supervisor
                .send_ipc_frame(frame)
                .map_err(|error| BridgeError::unavailable(&error.to_string())),
            Err(error) => Err(error),
        };
        if let Err(error) = send_result {
            self.registry
                .lock()
                .expect("control-plane registry poisoned")
                .remove(&transport_id);
            return Err(error);
        }
        self.wait_for_terminal(
            &transport_id,
            pending,
            ControlPlaneMethod::ModelTurnStart.timeout(),
        )
    }

    fn register_knowledge_model_acceptance(
        &self,
        response: &Value,
        context: &PendingKnowledgeModel,
    ) -> Result<(), BridgeError> {
        let request_id = validate_knowledge_model_receipt(response, context)?;
        let mut new_admission = None;
        let release_events = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let expected_chat_session_id = format!("knowledge-{}", context.turn_id);
            let conflicting_ids: Vec<_> = registry
                .entries
                .iter()
                .filter(|(_, entry)| {
                    entry.knowledge_model
                        && !entry.knowledge_acceptance_seen
                        && entry.knowledge_included == context.include_knowledge
                        && entry.knowledge_injection_id.as_deref()
                            == context
                                .include_knowledge
                                .then_some(context.injection_id.as_str())
                        && entry.identity.chat_session_id == expected_chat_session_id
                        && entry.identity.request_id != request_id
                })
                .map(|(request_id, _)| request_id.clone())
                .collect();
            if !conflicting_ids.is_empty() {
                for conflicting_id in &conflicting_ids {
                    registry.remove(conflicting_id);
                }
                drop(registry);
                for conflicting_id in conflicting_ids {
                    self.send_model_cancel_best_effort(&conflicting_id);
                }
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "knowledge model receipt request mismatch",
                ));
            }
            if let Some(entry) = registry.entries.get_mut(&request_id) {
                if !entry.knowledge_model
                    || entry.knowledge_included != context.include_knowledge
                    || entry.knowledge_injection_id.as_deref()
                        != context
                            .include_knowledge
                            .then_some(context.injection_id.as_str())
                {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "knowledge model acceptance identity mismatch",
                    ));
                }
                entry.accepted = true;
                entry.knowledge_acceptance_seen = true;
                begin_model_event_release(entry)
            } else {
                drop(registry);
                let mut admissions = self
                    .knowledge_admissions
                    .lock()
                    .expect("knowledge admission registry poisoned");
                if let Some(existing) = admissions.get(&request_id) {
                    if existing.context != *context {
                        return Err(BridgeError::new(
                            "protocol_mismatch",
                            "knowledge model receipt association mismatch",
                        ));
                    }
                } else {
                    if admissions.len() >= MAX_IN_FLIGHT_REQUESTS {
                        return Err(BridgeError::new(
                            "busy",
                            "knowledge model admission registry is full",
                        ));
                    }
                    let admission = KnowledgeAdmission::new(context.clone());
                    new_admission = Some(Arc::clone(&admission.watchdog));
                    admissions.insert(request_id.clone(), admission);
                }
                false
            }
        };
        if release_events {
            self.release_model_events(&request_id);
        } else if let Some(watchdog) = new_admission {
            self.spawn_knowledge_admission_watchdog(request_id, watchdog)?;
        }
        Ok(())
    }

    fn admit_pending_knowledge_model_event(
        &self,
        event: &UiControlPlaneEvent,
        method: &str,
        sequence: u64,
    ) -> Result<bool, BridgeError> {
        if method != "model.turn.started" || sequence != 0 {
            return Err(BridgeError::new(
                "request_not_found",
                "foreign or late model event",
            ));
        }
        let (identity, provider_id, harness_id) = knowledge_model_identity_from_event(event)?;
        let request_id = identity.request_id.clone();
        let metadata = event.metadata.as_object().ok_or_else(|| {
            BridgeError::new("protocol_mismatch", "model event metadata is not an object")
        })?;
        let chat_session_id = event.chat_session_id.as_deref().ok_or_else(|| {
            BridgeError::new("protocol_mismatch", "model chat_session_id missing")
        })?;
        let admissions = self
            .knowledge_admissions
            .lock()
            .expect("knowledge admission registry poisoned");
        if let Some(admission) = admissions.get(&request_id) {
            let context = admission.context.clone();
            let watchdog = self.insert_knowledge_model_event_entry(
                identity,
                provider_id,
                harness_id,
                &context,
                true,
            )?;
            drop(admissions);
            self.spawn_detached_model_request_watchdog(request_id, watchdog)?;
            return Ok(true);
        }
        drop(admissions);

        let matches: Vec<_> = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .entries
            .values()
            .filter_map(|pending| pending.knowledge_model.clone())
            .filter(|pending| {
                let injection_matches = if pending.include_knowledge {
                    metadata
                        .get("knowledge_injection_id")
                        .and_then(Value::as_str)
                        == Some(pending.injection_id.as_str())
                } else {
                    !metadata.contains_key("knowledge_injection_id")
                };
                injection_matches && chat_session_id == format!("knowledge-{}", pending.turn_id)
            })
            .collect();
        if matches.len() != 1 {
            return Err(BridgeError::new(
                "request_not_found",
                "model event knowledge association is ambiguous or missing",
            ));
        }
        let watchdog = self.insert_knowledge_model_event_entry(
            identity,
            provider_id,
            harness_id,
            &matches[0],
            false,
        )?;
        self.spawn_detached_model_request_watchdog(request_id, watchdog)?;
        Ok(false)
    }

    fn insert_knowledge_model_event_entry(
        &self,
        identity: ModelRequestIdentity,
        provider_id: String,
        harness_id: String,
        context: &PendingKnowledgeModel,
        acceptance_seen: bool,
    ) -> Result<Arc<ModelRequestWatchdog>, BridgeError> {
        let request_id = identity.request_id.clone();
        let mut registry = self
            .model_requests
            .lock()
            .expect("model request registry poisoned");
        let watchdog = registry.insert(identity, Vec::new())?;
        let entry = registry.entries.get_mut(&request_id).ok_or_else(|| {
            BridgeError::new(
                "request_not_found",
                "knowledge model entry disappeared while locked",
            )
        })?;
        entry.provider_id = Some(provider_id);
        entry.harness_id = Some(harness_id);
        entry.knowledge_model = true;
        entry.knowledge_acceptance_seen = acceptance_seen;
        entry.knowledge_injection_id = context
            .include_knowledge
            .then_some(context.injection_id.clone());
        entry.knowledge_included = context.include_knowledge;
        entry.accepted = true;
        Ok(watchdog)
    }

    fn discard_unaccepted_model_request(&self, request_id: &str) {
        let _ = self.request(
            ControlPlaneMethod::ModelTurnCancel,
            model_cancel_payload(request_id),
        );
        self.model_requests
            .lock()
            .expect("model request registry poisoned")
            .remove(request_id);
    }

    fn request_model_cancel(&self, request_id: &str) -> Result<Value, BridgeError> {
        let already_terminal = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            if !registry.entries.contains_key(request_id) {
                true
            } else {
                let entry = registry.entries.get_mut(request_id).ok_or_else(|| {
                    BridgeError::new(
                        "request_not_found",
                        "model request entry disappeared while locked",
                    )
                })?;
                if entry.terminal_seen {
                    entry.remove_after_release = true;
                    true
                } else if entry.cancel_pending || entry.cancel_accepted {
                    return Err(BridgeError::new(
                        "busy",
                        "model cancellation is already active",
                    ));
                } else {
                    entry.cancel_pending = true;
                    if !entry.accepted {
                        entry.cancel_requested_before_acceptance = true;
                    }
                    false
                }
            }
        };
        if already_terminal {
            return Ok(terminal_model_cancel_ack(request_id));
        }

        let response = match self.request(
            ControlPlaneMethod::ModelTurnCancel,
            model_cancel_payload(request_id),
        ) {
            Ok(response) => response,
            Err(error) => {
                self.release_cancel_buffer(request_id, false);
                return Err(error);
            }
        };
        let acknowledgement = match validate_model_cancel_ack(&response, request_id) {
            Ok(acknowledgement) => acknowledgement,
            Err(error) => {
                self.model_requests
                    .lock()
                    .expect("model request registry poisoned")
                    .remove(request_id);
                self.send_model_cancel_best_effort(request_id);
                return Err(error);
            }
        };

        let release_events = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let entry = registry.entries.get_mut(request_id).ok_or_else(|| {
                BridgeError::new("request_not_found", "active model request not found")
            })?;
            entry.cancel_pending = false;
            if entry.accepted {
                entry.cancel_requested_before_acceptance = false;
            }
            if acknowledgement.accepted {
                entry.cancel_accepted = true;
                if entry
                    .buffered_events
                    .iter()
                    .any(|event| is_model_terminal_method(&event.method))
                {
                    registry.remove(request_id);
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "natural terminal event conflicts with accepted cancellation",
                    ));
                }
            }
            begin_model_event_release(entry)
        };
        if release_events {
            self.release_model_events(request_id);
        }
        Ok(response)
    }

    fn release_cancel_buffer(&self, request_id: &str, cancellation_accepted: bool) {
        let release_events = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let Some(entry) = registry.entries.get_mut(request_id) else {
                return;
            };
            entry.cancel_pending = false;
            entry.cancel_accepted |= cancellation_accepted;
            begin_model_event_release(entry)
        };
        if release_events {
            self.release_model_events(request_id);
        }
    }

    fn release_model_events(&self, request_id: &str) {
        loop {
            let events = self
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .take_release_batch(request_id);
            let Some(events) = events else {
                return;
            };
            let terminal_emitted = events
                .iter()
                .any(|event| is_model_terminal_method(&event.method));
            for event in events {
                self.emit_event(event);
            }
            if terminal_emitted {
                let cancel_after_release = {
                    let mut registry = self
                        .model_requests
                        .lock()
                        .expect("model request registry poisoned");
                    registry.entries.get_mut(request_id).is_some_and(|entry| {
                        std::mem::take(&mut entry.cancel_after_synthetic_release)
                    })
                };
                if cancel_after_release {
                    self.send_model_cancel_best_effort(request_id);
                }
            }
        }
    }

    fn spawn_model_request_watchdog(
        self: &Arc<Self>,
        request_id: String,
        watchdog: Arc<ModelRequestWatchdog>,
    ) -> Result<(), BridgeError> {
        let weak = Arc::downgrade(self);
        thread::Builder::new()
            .name("localcomet-model-request-watchdog".into())
            .spawn(move || {
                if !watchdog.wait_for_timeout(MODEL_REQUEST_WATCHDOG_TIMEOUT) {
                    return;
                }
                if let Some(bridge) = weak.upgrade() {
                    bridge.timeout_model_request(&request_id);
                }
            })
            .map(|_| ())
            .map_err(|_| {
                BridgeError::new(
                    "runtime_unavailable",
                    "model request watchdog could not start",
                )
            })
    }

    fn spawn_detached_model_request_watchdog(
        &self,
        request_id: String,
        watchdog: Arc<ModelRequestWatchdog>,
    ) -> Result<(), BridgeError> {
        let registry = Arc::clone(&self.model_requests);
        let app = self.app.clone();
        let supervisor = Arc::clone(&self.supervisor);
        thread::Builder::new()
            .name("localcomet-knowledge-model-watchdog".into())
            .spawn(move || {
                if !watchdog.wait_for_timeout(MODEL_REQUEST_WATCHDOG_TIMEOUT) {
                    return;
                }
                let entry = registry
                    .lock()
                    .expect("model request registry poisoned")
                    .remove_or_queue_synthetic_terminal(
                        &request_id,
                        "model.turn.timed_out",
                        "TimedOut",
                        "request_timed_out",
                        "knowledge model request exceeded the bounded lifetime",
                    );
                let Some(mut entry) = entry else {
                    return;
                };
                if let Some(events) = take_authoritative_buffered_terminal(&mut entry) {
                    if let Some(window) = app.get_webview_window("main") {
                        for event in events {
                            let _ = window.emit(CONTROL_PLANE_EVENT_CHANNEL, event);
                        }
                    }
                } else {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.emit(
                            CONTROL_PLANE_EVENT_CHANNEL,
                            model_terminal_event(
                                &entry,
                                "model.turn.timed_out",
                                "TimedOut",
                                "request_timed_out",
                                "knowledge model request exceeded the bounded lifetime",
                            ),
                        );
                    }
                    let transport_id = format!("deskcp-kcancel-{}", entry.identity.request_id);
                    let envelope =
                        model_cancel_request_envelope(&transport_id, &entry.identity.request_id);
                    if let Ok(body) = serde_json::to_string(&envelope) {
                        if let Ok(frame) = ipc::json_frame(&body) {
                            let _ = supervisor.send_ipc_frame(frame);
                        }
                    }
                }
            })
            .map(|_| ())
            .map_err(|_| {
                BridgeError::new(
                    "runtime_unavailable",
                    "knowledge model watchdog could not start",
                )
            })
    }

    fn spawn_knowledge_admission_watchdog(
        &self,
        request_id: String,
        watchdog: Arc<ModelRequestWatchdog>,
    ) -> Result<(), BridgeError> {
        let admissions = Arc::clone(&self.knowledge_admissions);
        let supervisor = Arc::clone(&self.supervisor);
        let timeout_request_id = request_id.clone();
        let spawn = thread::Builder::new()
            .name("localcomet-knowledge-admission-watchdog".into())
            .spawn(move || {
                if !watchdog.wait_for_timeout(MODEL_REQUEST_WATCHDOG_TIMEOUT) {
                    return;
                }
                let expired = admissions
                    .lock()
                    .expect("knowledge admission registry poisoned")
                    .remove(&timeout_request_id)
                    .is_some();
                if expired {
                    let transport_id = format!("deskcp-kcancel-{timeout_request_id}");
                    let envelope =
                        model_cancel_request_envelope(&transport_id, &timeout_request_id);
                    if let Ok(body) = serde_json::to_string(&envelope) {
                        if let Ok(frame) = ipc::json_frame(&body) {
                            let _ = supervisor.send_ipc_frame(frame);
                        }
                    }
                }
            });
        if spawn.is_err() {
            self.knowledge_admissions
                .lock()
                .expect("knowledge admission registry poisoned")
                .remove(&request_id);
            self.send_model_cancel_best_effort(&request_id);
            return Err(BridgeError::new(
                "runtime_unavailable",
                "knowledge admission watchdog could not start",
            ));
        }
        Ok(())
    }

    fn timeout_model_request(&self, request_id: &str) {
        let entry = self
            .model_requests
            .lock()
            .expect("model request registry poisoned")
            .remove_or_queue_synthetic_terminal(
                request_id,
                "model.turn.timed_out",
                "TimedOut",
                "request_timed_out",
                "model request exceeded the bounded lifetime",
            );
        let Some(mut entry) = entry else {
            return;
        };
        if let Some(events) = take_authoritative_buffered_terminal(&mut entry) {
            for event in events {
                self.emit_event(event);
            }
            return;
        }
        self.emit_event(model_terminal_event(
            &entry,
            "model.turn.timed_out",
            "TimedOut",
            "request_timed_out",
            "model request exceeded the bounded lifetime",
        ));
        let _ = self.request(
            ControlPlaneMethod::ModelTurnCancel,
            model_cancel_payload(request_id),
        );
    }

    fn fail_model_requests(&self, code: &str, message: &str) {
        let request_ids: Vec<_> = self
            .model_requests
            .lock()
            .expect("model request registry poisoned")
            .entries
            .keys()
            .cloned()
            .collect();
        for request_id in request_ids {
            let entry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove_or_queue_synthetic_terminal(
                    &request_id,
                    "model.turn.failed",
                    "Failed",
                    code,
                    message,
                );
            let Some(mut entry) = entry else {
                continue;
            };
            if let Some(events) = take_authoritative_buffered_terminal(&mut entry) {
                for event in events {
                    self.emit_event(event);
                }
                continue;
            }
            self.emit_event(model_terminal_event(
                &entry,
                "model.turn.failed",
                "Failed",
                code,
                message,
            ));
        }
    }

    pub fn emit_sidecar_status(&self) {
        let snapshot = self.supervisor.snapshot();
        let event = UiControlPlaneEvent {
            method: "sidecar.status".into(),
            sequence: 0,
            reply_to: "startup".into(),
            request_id: None,
            chat_session_id: None,
            model_id: None,
            control_plane_version: DESKTOP_STATUS_BRIDGE_VERSION.into(),
            session_id: None,
            thread_id: None,
            turn_id: None,
            item_id: None,
            state: if snapshot.running {
                "READY"
            } else {
                "UNAVAILABLE"
            }
            .into(),
            kind: None,
            text: None,
            metadata: json!({
                "saw_python_hello": snapshot.saw_python_hello,
                "saw_goodbye": snapshot.saw_goodbye,
            }),
        };
        self.emit_event(event);
    }

    fn wait_for_terminal(
        &self,
        request_id: &str,
        pending: Arc<PendingRequest>,
        timeout: Duration,
    ) -> Result<Value, BridgeError> {
        let deadline = Instant::now() + timeout;
        let mut guard = pending.state.lock().expect("pending request poisoned");
        loop {
            if let Some(result) = guard.terminal.take() {
                drop(guard);
                if result.is_err() || pending.knowledge_model.is_none() {
                    self.registry
                        .lock()
                        .expect("control-plane registry poisoned")
                        .remove(request_id);
                }
                return result;
            }
            let now = Instant::now();
            if now >= deadline {
                drop(guard);
                self.registry
                    .lock()
                    .expect("control-plane registry poisoned")
                    .remove(request_id);
                return Err(BridgeError::new(
                    "timeout",
                    "control-plane request timed out",
                ));
            }
            let wait = deadline.saturating_duration_since(now);
            let (next_guard, _) = pending
                .ready
                .wait_timeout(guard, wait)
                .expect("pending request wait poisoned");
            guard = next_guard;
        }
    }

    fn next_request_id(&self) -> String {
        let value = self.request_counter.fetch_add(1, Ordering::SeqCst);
        format!("deskcp-{value:010}")
    }

    fn ensure_ready(&self) -> Result<(), BridgeError> {
        let snapshot = self.supervisor.snapshot();
        if snapshot.running && snapshot.saw_python_hello {
            Ok(())
        } else {
            Err(BridgeError::unavailable("sidecar is not ready"))
        }
    }

    fn emit_event(&self, event: UiControlPlaneEvent) {
        if let Some(window) = self.app.get_webview_window("main") {
            if window.emit(CONTROL_PLANE_EVENT_CHANNEL, &event).is_err() {
                self.record_warning("main window event emission failed");
            }
        } else {
            self.record_warning("main window unavailable");
        }
    }

    fn record_warning(&self, warning: &str) {
        let mut warnings = self
            .warnings
            .lock()
            .expect("control-plane warning lock poisoned");
        warnings.push(sanitize_text(warning, 128));
        if warnings.len() > 16 {
            warnings.remove(0);
        }
    }
}

impl SidecarFrameRouter for ControlPlaneBridge {
    fn route_frame(&self, frame: Vec<u8>) {
        if let Err(error) = self.route_frame_inner(&frame) {
            self.record_warning(&error.message);
        }
    }

    fn fail_pending(&self, code: &str, message: &str) {
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .drain_all();
        let error = BridgeError::new(code, message);
        for entry in pending {
            finish_pending(&entry, Err(error.clone()));
        }
        self.knowledge_admissions
            .lock()
            .expect("knowledge admission registry poisoned")
            .clear();
        self.fail_model_requests(code, message);
    }
}

impl ControlPlaneBridge {
    fn route_frame_inner(&self, frame: &[u8]) -> Result<(), BridgeError> {
        let envelope = ipc::parse_semantic_json(frame)
            .map_err(|_| BridgeError::new("invalid_json", "sidecar frame was not JSON"))?;
        let msg_type = envelope.get("type").and_then(Value::as_str).unwrap_or("");
        match msg_type {
            "event" => self.route_event(&envelope),
            "response" => self.route_terminal(&envelope, false),
            "error" => self.route_terminal(&envelope, true),
            "hello" | "goodbye" => Ok(()),
            _ => Err(BridgeError::new(
                "unsupported_type",
                "unsupported sidecar frame type",
            )),
        }
    }

    fn route_event(&self, envelope: &Value) -> Result<(), BridgeError> {
        let sequence = envelope
            .get("sequence")
            .and_then(Value::as_u64)
            .ok_or_else(|| BridgeError::new("invalid_sequence", "event sequence missing"))?;
        let method = string_field(envelope, "method")?;
        if !allowed_event_method(&method) {
            return Err(BridgeError::new(
                "unsupported_method",
                "unsupported event method",
            ));
        }
        if allowed_model_event_method(&method) {
            return self.route_model_event(envelope, &method, sequence);
        }
        let reply_to = string_field(envelope, "reply_to")?;
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .get(&reply_to)
            .ok_or_else(|| BridgeError::new("request_not_found", "unknown event reply_to"))?;
        let event = ui_event_from_envelope(envelope)?;
        {
            let mut state = pending.state.lock().expect("pending request poisoned");
            if state.terminal_seen {
                return Err(BridgeError::new(
                    "invalid_sequence",
                    "event after terminal response",
                ));
            }
            if sequence != state.next_sequence {
                return Err(BridgeError::new(
                    "invalid_sequence",
                    "event sequence is not strictly increasing",
                ));
            }
            let text_len = event.text.as_deref().unwrap_or("").len();
            if event.text.as_deref().unwrap_or("").len() > MAX_DELTA_CHARS {
                finish_pending(
                    &pending,
                    Err(BridgeError::new(
                        "payload_too_large",
                        "event text too large",
                    )),
                );
                return Ok(());
            }
            if state.event_count + 1 > MAX_EVENTS_PER_REQUEST {
                finish_pending(
                    &pending,
                    Err(BridgeError::new("budget_exceeded", "event limit reached")),
                );
                return Ok(());
            }
            if state.event_text + text_len > MAX_EVENT_TEXT_PER_REQUEST {
                finish_pending(
                    &pending,
                    Err(BridgeError::new(
                        "payload_too_large",
                        "event text limit reached",
                    )),
                );
                return Ok(());
            }
            state.next_sequence += 1;
            state.event_count += 1;
            state.event_text += text_len;
        }
        self.emit_event(event);
        Ok(())
    }

    fn route_model_event(
        &self,
        envelope: &Value,
        method: &str,
        sequence: u64,
    ) -> Result<(), BridgeError> {
        let run_id = string_field(envelope, "run_id")?;
        ensure_request_id(&run_id)?;
        match self.route_validated_model_event(envelope, method, sequence, &run_id) {
            Ok(()) => Ok(()),
            Err(error) => {
                let (known_request, entry) = {
                    let mut registry = self
                        .model_requests
                        .lock()
                        .expect("model request registry poisoned");
                    let known_request = registry.entries.contains_key(&run_id);
                    let entry = registry.remove_or_queue_synthetic_terminal(
                        &run_id,
                        "model.turn.failed",
                        "Failed",
                        &error.code,
                        &error.message,
                    );
                    (known_request, entry)
                };
                let admission = self
                    .knowledge_admissions
                    .lock()
                    .expect("knowledge admission registry poisoned")
                    .remove(&run_id);
                drop(admission);
                if let Some(mut entry) = entry {
                    if let Some(events) = take_authoritative_buffered_terminal(&mut entry) {
                        for event in events {
                            self.emit_event(event);
                        }
                    } else {
                        self.emit_event(model_terminal_event(
                            &entry,
                            "model.turn.failed",
                            "Failed",
                            &error.code,
                            &error.message,
                        ));
                    }
                }
                self.send_model_cancel_best_effort(&run_id);
                if known_request {
                    Ok(())
                } else {
                    Err(error)
                }
            }
        }
    }

    fn send_model_cancel_best_effort(&self, request_id: &str) {
        if self.ensure_ready().is_err() || ensure_request_id(request_id).is_err() {
            return;
        }
        let transport_id = self.next_request_id();
        let envelope = model_cancel_request_envelope(&transport_id, request_id);
        let Ok(body) = serde_json::to_string(&envelope) else {
            return;
        };
        let Ok(frame) = ipc::json_frame(&body) else {
            return;
        };
        let _ = self.supervisor.send_ipc_frame(frame);
    }

    fn route_validated_model_event(
        &self,
        envelope: &Value,
        method: &str,
        sequence: u64,
        run_id: &str,
    ) -> Result<(), BridgeError> {
        let mut event = ui_event_from_envelope(envelope)?;
        let request_id = event
            .request_id
            .clone()
            .ok_or_else(|| BridgeError::new("invalid_payload", "model event request_id missing"))?;
        if request_id.as_str() != run_id
            || event.turn_id.as_deref() != Some(request_id.as_str())
            || event.reply_to != request_id
        {
            return Err(BridgeError::new(
                "protocol_mismatch",
                "model request, run, reply, and turn IDs differ",
            ));
        }
        let request_known = self
            .model_requests
            .lock()
            .expect("model request registry poisoned")
            .entries
            .contains_key(&request_id);
        let admitted_from_receipt = if request_known {
            false
        } else {
            self.admit_pending_knowledge_model_event(&event, method, sequence)?
        };

        let emit = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let (emit, terminal) = {
                let entry = registry.entries.get_mut(&request_id).ok_or_else(|| {
                    BridgeError::new("request_not_found", "foreign or late model event")
                })?;
                let forward = validate_and_record_model_event(entry, &event, method, sequence)?;
                event.metadata = project_model_event_metadata(&event)?;
                let buffered = model_event_is_gated(entry)
                    || (entry.knowledge_model
                        && !entry.knowledge_acceptance_seen
                        && entry.terminal_seen);
                if buffered {
                    if forward {
                        entry.buffered_events.push(event);
                    }
                    (None, false)
                } else if !forward {
                    (None, false)
                } else {
                    let terminal = entry.terminal_seen;
                    (Some(event), terminal)
                }
            };
            if terminal {
                registry.remove(&request_id);
            }
            emit
        };
        if let Some(event) = emit {
            self.emit_event(event);
        }
        if admitted_from_receipt {
            let admission = self
                .knowledge_admissions
                .lock()
                .expect("knowledge admission registry poisoned")
                .remove(&request_id);
            drop(admission);
        }
        Ok(())
    }

    fn route_terminal(&self, envelope: &Value, is_error: bool) -> Result<(), BridgeError> {
        let reply_to = string_field(envelope, "reply_to")?;
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .get(&reply_to)
            .ok_or_else(|| BridgeError::new("request_not_found", "unknown terminal reply_to"))?;
        let result = if is_error {
            let payload = envelope
                .get("payload")
                .cloned()
                .unwrap_or_else(|| json!({}));
            Err(BridgeError::new(
                payload
                    .get("code")
                    .and_then(Value::as_str)
                    .unwrap_or("internal_error"),
                payload
                    .get("message")
                    .and_then(Value::as_str)
                    .unwrap_or("sidecar error"),
            ))
        } else {
            Ok(envelope
                .get("payload")
                .cloned()
                .unwrap_or_else(|| json!({})))
        };
        {
            let mut state = pending.state.lock().expect("pending request poisoned");
            if state.terminal_seen {
                return Err(BridgeError::new(
                    "invalid_sequence",
                    "duplicate terminal response",
                ));
            }
            state.terminal_seen = true;
        }
        finish_pending(&pending, result);
        Ok(())
    }
}

fn validate_control_plane_method_count(actual: usize) {
    debug_assert_eq!(
        actual, CONTROL_PLANE_METHOD_COUNT,
        "control-plane method vocabulary count mismatch"
    );
}

fn validate_bridge_contract() {
    validate_control_plane_method_count(CONTROL_PLANE_METHOD_VOCABULARY.len());
    for (wire, method) in CONTROL_PLANE_METHOD_VOCABULARY {
        debug_assert_eq!(wire, method.as_wire());
    }
}

#[tauri::command]
pub fn control_plane_bootstrap(
    state: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<Value, BridgeError> {
    let response = state.request(ControlPlaneMethod::AppBootstrap, json!({}))?;
    state.emit_sidecar_status();
    Ok(response)
}

#[tauri::command]
pub fn control_plane_create_session(
    state: State<'_, Arc<ControlPlaneBridge>>,
    title: String,
) -> Result<Value, BridgeError> {
    ensure_len("title", &title, MAX_TITLE_CHARS)?;
    state.request(ControlPlaneMethod::SessionCreate, json!({ "title": title }))
}

#[tauri::command]
pub fn control_plane_close_session(
    state: State<'_, Arc<ControlPlaneBridge>>,
    session_id: String,
) -> Result<Value, BridgeError> {
    ensure_id("session_id", &session_id)?;
    state.request(
        ControlPlaneMethod::SessionClose,
        json!({ "session_id": session_id }),
    )
}

#[tauri::command]
pub fn control_plane_create_thread(
    state: State<'_, Arc<ControlPlaneBridge>>,
    session_id: String,
    title: String,
) -> Result<Value, BridgeError> {
    ensure_id("session_id", &session_id)?;
    ensure_len("title", &title, MAX_TITLE_CHARS)?;
    state.request(
        ControlPlaneMethod::ThreadCreate,
        json!({ "session_id": session_id, "title": title }),
    )
}

#[tauri::command]
pub fn control_plane_start_mock_turn(
    state: State<'_, Arc<ControlPlaneBridge>>,
    thread_id: String,
    prompt: String,
    behavior: String,
) -> Result<Value, BridgeError> {
    ensure_id("thread_id", &thread_id)?;
    ensure_len("prompt", &prompt, MAX_PROMPT_CHARS)?;
    if !matches!(
        behavior.as_str(),
        "complete" | "pending_model" | "wait_for_cancel"
    ) {
        return Err(BridgeError::new("invalid_payload", "invalid behavior"));
    }
    state.request(
        ControlPlaneMethod::TurnStartMock,
        json!({ "thread_id": thread_id, "prompt": prompt, "behavior": behavior }),
    )
}

#[tauri::command]
pub fn control_plane_get_turn_status(
    state: State<'_, Arc<ControlPlaneBridge>>,
    turn_id: String,
) -> Result<Value, BridgeError> {
    ensure_id("turn_id", &turn_id)?;
    state.request(
        ControlPlaneMethod::TurnStatus,
        json!({ "turn_id": turn_id }),
    )
}

#[tauri::command]
pub fn control_plane_cancel_turn(
    state: State<'_, Arc<ControlPlaneBridge>>,
    turn_id: String,
    reason: String,
) -> Result<Value, BridgeError> {
    ensure_id("turn_id", &turn_id)?;
    if !matches!(
        reason.as_str(),
        "user_requested" | "window_closing" | "timeout"
    ) {
        return Err(BridgeError::new(
            "invalid_payload",
            "invalid cancellation reason",
        ));
    }
    state.request(
        ControlPlaneMethod::TurnCancel,
        json!({ "turn_id": turn_id, "reason": reason }),
    )
}

#[tauri::command]
pub async fn model_gateway_catalog(
    state: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<Value, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        state.request(ControlPlaneMethod::ModelCatalogGet, json!({}))
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model catalog worker failed"))?
}

#[tauri::command]
pub async fn model_gateway_probe(
    state: State<'_, Arc<ControlPlaneBridge>>,
    port: u16,
) -> Result<Value, BridgeError> {
    ensure_model_port(port)?;
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        state.request(
            ControlPlaneMethod::ModelGatewayProbe,
            json!({ "port": port }),
        )
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model probe worker failed"))?
}

#[tauri::command]
pub async fn model_gateway_list_models(
    state: State<'_, Arc<ControlPlaneBridge>>,
    port: u16,
) -> Result<Value, BridgeError> {
    ensure_model_port(port)?;
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        state.request(ControlPlaneMethod::ModelModelsList, json!({ "port": port }))
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model list worker failed"))?
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn model_binding_set(
    state: State<'_, Arc<ControlPlaneBridge>>,
    artifacts: State<'_, Arc<ArtifactTrustService>>,
    approval: State<'_, crate::approval_commands::ApprovalState>,
    provider_id: String,
    harness_id: String,
    port: Option<u16>,
    model_id: String,
    runtime_instance_id: Option<String>,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError> {
    ensure_provider(&provider_id)?;
    ensure_harness(&harness_id)?;
    ensure_model_id(&model_id)?;
    if provider_id == "openai-compatible-local" {
        ensure_model_port(port.unwrap_or(0))?;
    } else if let Some(instance_id) = &runtime_instance_id {
        ensure_runtime_instance_id(instance_id)?;
    } else {
        return Err(BridgeError::new(
            "invalid_payload",
            "runtime instance is required",
        ));
    }
    let semantic_payload = json!({
        "provider_id": provider_id,
        "harness_id": harness_id,
        "port": port,
        "model_id": model_id,
        "runtime_instance_id": runtime_instance_id
    });
    crate::approval_commands::validate_approval_token(
        &approval,
        "model.binding.set",
        &semantic_payload,
        &token,
        &approval_id,
        &call_id,
    )?;
    let mut python_payload = semantic_payload;
    python_payload["confirmed"] = json!(true);
    let state = Arc::clone(&state);
    let artifacts = Arc::clone(&artifacts);
    let bound_model_id = model_id.clone();
    tauri::async_runtime::spawn_blocking(move || {
        state
            .request(ControlPlaneMethod::ModelBindingSet, python_payload)
            .inspect(|_| artifacts.invalidate_validation_cache_for_artifact(&bound_model_id))
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model binding worker failed"))?
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn model_turn_start(
    state: State<'_, Arc<ControlPlaneBridge>>,
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    files: State<'_, SelectedFilesManager>,
    request_id: String,
    chat_session_id: String,
    model_id: String,
    submitted_at_unix_ms: u64,
    max_tokens: u16,
    prompt: String,
    file_ids: Vec<String>,
    locale: String,
    binding_fingerprint: String,
    agent_permissions: AgentPermissions,
    messages: Vec<Value>,
) -> Result<Value, BridgeError> {
    ensure_request_id(&request_id)?;
    ensure_chat_session_id(&chat_session_id)?;
    ensure_model_id(&model_id)?;
    if submitted_at_unix_ms == 0 || submitted_at_unix_ms > 9_007_199_254_740_991 {
        return Err(BridgeError::new(
            "invalid_payload",
            "submitted_at_unix_ms is invalid",
        ));
    }
    if !(1..=512).contains(&max_tokens) {
        return Err(BridgeError::new(
            "invalid_payload",
            "max_tokens is outside the allowed range",
        ));
    }
    ensure_model_prompt(&prompt)?;
    let (prompt, file_context_report) = if file_ids.is_empty() {
        (prompt, None)
    } else {
        let separator = "\n\n";
        let context_budget = MAX_MODEL_PROMPT_CHARS
            .checked_sub(prompt.len())
            .and_then(|remaining| remaining.checked_sub(separator.len()))
            .ok_or_else(|| {
                BridgeError::new(
                    crate::files::LC_FILE_CONTEXT_LIMIT,
                    "Selected file context does not fit in this request",
                )
            })?;
        let bundle = files
            .build_context(&file_ids, context_budget)
            .map_err(|error| BridgeError::new(error.code(), error.message()))?;
        debug_assert!(bundle.included_bytes as u64 <= bundle.source_bytes);
        debug_assert!(bundle.included_characters <= bundle.source_characters);
        debug_assert_eq!(
            bundle.truncated,
            bundle.included_bytes as u64 != bundle.source_bytes
        );
        let report = json!({
            "source_bytes": bundle.source_bytes,
            "source_characters": bundle.source_characters,
            "included_bytes": bundle.included_bytes,
            "included_characters": bundle.included_characters,
            "truncated": bundle.truncated,
            "files": bundle.inclusions,
        });
        (
            format!("{prompt}{separator}{}", bundle.context),
            Some(report),
        )
    };
    ensure_model_prompt(&prompt)?;
    let assistant_context = AssistantContext::trusted(
        &locale,
        file_context_report.is_some(),
        Some(&agent_permissions),
        messages,
    )?;
    ensure_fingerprint(&binding_fingerprint)?;
    let identity = ModelRequestIdentity {
        request_id,
        chat_session_id,
        model_id,
        submitted_at_unix_ms,
        max_tokens,
        binding_fingerprint,
    };
    // The reservation is bound to the digest of the exact wire payload it
    // authorizes, assistant_context (and therefore the capability/tool grant that
    // drives permitted_tool_names) included. Dispatch re-derives this digest.
    let wire_digest = model_turn_wire_digest(&model_turn_wire_payload(
        &identity,
        &prompt,
        &assistant_context,
    ));
    state.reserve_model_turn(
        &identity,
        assistant_context.capabilities.tools.clone(),
        wire_digest,
    )?;
    let cleanup_state = Arc::clone(&state);
    let cleanup_request_id = identity.request_id.clone();
    let worker_state = Arc::clone(&state);
    let worker_runtime = Arc::clone(&runtime);
    let mut response = match tauri::async_runtime::spawn_blocking(move || {
        if let Err(error) = worker_runtime.ensure_model_ready(&identity.model_id) {
            worker_state
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&identity.request_id);
            return Err(error);
        }
        worker_state.request_model_turn_reserved(identity, prompt, assistant_context)
    })
    .await
    {
        Ok(result) => result?,
        Err(_) => {
            cleanup_state
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&cleanup_request_id);
            cleanup_state.send_model_cancel_best_effort(&cleanup_request_id);
            return Err(BridgeError::new(
                "runtime_unavailable",
                "model start worker failed",
            ));
        }
    };
    if let (Some(report), Value::Object(response)) = (file_context_report, &mut response) {
        response.insert("file_context".to_owned(), report);
    }
    Ok(response)
}

#[tauri::command]
pub async fn model_turn_cancel(
    state: State<'_, Arc<ControlPlaneBridge>>,
    request_id: String,
) -> Result<Value, BridgeError> {
    ensure_request_id(&request_id)?;
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || state.request_model_cancel(&request_id))
        .await
        .map_err(|_| BridgeError::new("runtime_unavailable", "model cancel worker failed"))?
}

#[tauri::command]
pub fn knowledge_review_list(
    state: State<'_, Arc<ControlPlaneBridge>>,
    offset: u16,
    limit: u16,
) -> Result<Value, BridgeError> {
    let (method, payload) = build_knowledge_review_list_request(offset, limit)?;
    state.request(method, payload)
}

#[tauri::command]
pub fn knowledge_review_get(
    state: State<'_, Arc<ControlPlaneBridge>>,
    review_artifact_identity: String,
) -> Result<Value, BridgeError> {
    let (method, payload) = build_knowledge_review_get_request(&review_artifact_identity)?;
    state.request(method, payload)
}

#[tauri::command]
pub fn knowledge_review_snapshot(
    state: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<Value, BridgeError> {
    state.request(ControlPlaneMethod::KnowledgeReviewSnapshot, json!({}))
}

#[tauri::command]
pub fn knowledge_review_refresh(
    state: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<Value, BridgeError> {
    state.request(ControlPlaneMethod::KnowledgeReviewRefresh, json!({}))
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub fn knowledge_review_decision_create(
    state: State<'_, Arc<ControlPlaneBridge>>,
    review_contract_version: String,
    proposal_id: String,
    review_artifact_identity: String,
    change_identity: Option<String>,
    observed_vault_revision: String,
    decision: String,
    comment: String,
    actor_identifier: String,
    actor_display_name: String,
    actor_source: String,
) -> Result<Value, BridgeError> {
    let (method, payload) = build_knowledge_review_decision_create_request(
        &review_contract_version,
        &proposal_id,
        &review_artifact_identity,
        change_identity.as_deref(),
        &observed_vault_revision,
        &decision,
        &comment,
        &actor_identifier,
        &actor_display_name,
        &actor_source,
    )?;
    state.request(method, payload)
}

fn build_knowledge_review_list_request(
    offset: u16,
    limit: u16,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    ensure_knowledge_review_page(offset, limit)?;
    Ok((
        ControlPlaneMethod::KnowledgeReviewList,
        json!({ "offset": offset, "limit": limit }),
    ))
}

fn build_knowledge_review_get_request(
    review_artifact_identity: &str,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    ensure_review_artifact_identity(review_artifact_identity)?;
    Ok((
        ControlPlaneMethod::KnowledgeReviewGet,
        json!({ "review_artifact_identity": review_artifact_identity }),
    ))
}

#[allow(clippy::too_many_arguments)]
fn build_knowledge_review_decision_create_request(
    review_contract_version: &str,
    proposal_id: &str,
    review_artifact_identity: &str,
    change_identity: Option<&str>,
    observed_vault_revision: &str,
    decision: &str,
    comment: &str,
    actor_identifier: &str,
    actor_display_name: &str,
    actor_source: &str,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    ensure_exact_contract(
        "review_contract_version",
        review_contract_version,
        KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
    )?;
    ensure_prefixed_identity("proposal_id", proposal_id, "kprop:")?;
    ensure_review_artifact_identity(review_artifact_identity)?;
    if let Some(identity) = change_identity {
        ensure_prefixed_identity("change_identity", identity, "kchange:")?;
    }
    ensure_prefixed_identity(
        "observed_vault_revision",
        observed_vault_revision,
        "sha256:",
    )?;
    ensure_review_decision(decision)?;
    ensure_bounded_text(
        "comment",
        comment,
        MAX_REVIEW_COMMENT_CHARS,
        MAX_REVIEW_COMMENT_BYTES,
        true,
    )?;
    if decision == "REQUEST_CHANGES" && comment.trim().is_empty() {
        return Err(BridgeError::new(
            "invalid_payload",
            "REQUEST_CHANGES requires a meaningful comment",
        ));
    }
    ensure_bounded_text(
        "actor_identifier",
        actor_identifier,
        MAX_REVIEW_ACTOR_IDENTIFIER_CHARS,
        MAX_REVIEW_ACTOR_IDENTIFIER_BYTES,
        false,
    )?;
    ensure_bounded_text(
        "actor_display_name",
        actor_display_name,
        MAX_REVIEW_ACTOR_DISPLAY_NAME_CHARS,
        MAX_REVIEW_ACTOR_DISPLAY_NAME_BYTES,
        false,
    )?;
    ensure_bounded_text(
        "actor_source",
        actor_source,
        MAX_REVIEW_ACTOR_SOURCE_CHARS,
        MAX_REVIEW_ACTOR_SOURCE_BYTES,
        false,
    )?;
    if actor_source != KNOWLEDGE_REVIEW_ACTOR_SOURCE {
        return Err(BridgeError::new(
            "invalid_payload",
            "actor_source is not the fixed Review Center source",
        ));
    }
    Ok((
        ControlPlaneMethod::KnowledgeReviewDecisionCreate,
        json!({
            "review_contract_version": review_contract_version,
            "proposal_id": proposal_id,
            "review_artifact_identity": review_artifact_identity,
            "change_identity": change_identity,
            "observed_vault_revision": observed_vault_revision,
            "decision": decision,
            "comment": comment,
            "actor_identifier": actor_identifier,
            "actor_display_name": actor_display_name,
            "actor_source": actor_source
        }),
    ))
}

fn finish_pending(pending: &PendingRequest, result: Result<Value, BridgeError>) {
    let _reply_to = &pending.reply_to;
    let mut state = pending.state.lock().expect("pending request poisoned");
    state.terminal = Some(result);
    pending.ready.notify_all();
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ModelCancelAcknowledgement {
    accepted: bool,
    already_terminal: bool,
}

fn validate_model_acceptance(
    response: &Value,
    expected: &ModelRequestIdentity,
) -> Result<(String, String), BridgeError> {
    let object = response.as_object().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "model acceptance is not an object")
    })?;
    const ACCEPTANCE_KEYS: &[&str] = &[
        "request_id",
        "turn_id",
        "chat_session_id",
        "model_id",
        "submitted_at_unix_ms",
        "max_tokens",
        "binding_fingerprint",
        "state",
        "provider_id",
        "harness_id",
        "model_called",
        "tools_executed",
        "persistence",
    ];
    if object.len() != ACCEPTANCE_KEYS.len()
        || object
            .keys()
            .any(|key| !ACCEPTANCE_KEYS.contains(&key.as_str()))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model acceptance shape mismatch",
        ));
    }
    let string = |key: &str| {
        object
            .get(key)
            .and_then(Value::as_str)
            .ok_or_else(|| BridgeError::new("protocol_mismatch", "model acceptance field missing"))
    };
    if string("request_id")? != expected.request_id
        || string("turn_id")? != expected.request_id
        || string("chat_session_id")? != expected.chat_session_id
        || string("model_id")? != expected.model_id
        || string("binding_fingerprint")? != expected.binding_fingerprint
        || string("state")? != "Accepted"
        || object.get("submitted_at_unix_ms").and_then(Value::as_u64)
            != Some(expected.submitted_at_unix_ms)
        || object.get("max_tokens").and_then(Value::as_u64) != Some(u64::from(expected.max_tokens))
        || object.get("model_called").and_then(Value::as_bool) != Some(false)
        || object.get("tools_executed").and_then(Value::as_u64) != Some(0)
        || object.get("persistence").and_then(Value::as_bool) != Some(false)
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model acceptance identity mismatch",
        ));
    }
    let provider_id = string("provider_id")?;
    let harness_id = string("harness_id")?;
    if ensure_provider(provider_id).is_err() || ensure_harness(harness_id).is_err() {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model acceptance provider or harness mismatch",
        ));
    }
    Ok((provider_id.into(), harness_id.into()))
}

fn project_model_acceptance(
    identity: &ModelRequestIdentity,
    provider_id: &str,
    harness_id: &str,
) -> Value {
    json!({
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "binding_fingerprint": identity.binding_fingerprint,
        "state": "Accepted",
        "provider_id": provider_id,
        "harness_id": harness_id,
        "model_called": false,
        "tools_executed": 0,
        "persistence": false,
    })
}

fn pending_knowledge_model(
    method: ControlPlaneMethod,
    payload: &Value,
) -> Option<PendingKnowledgeModel> {
    if method != ControlPlaneMethod::KnowledgeTurnDecide {
        return None;
    }
    let action = payload.get("action")?.as_str()?;
    if action == "CANCEL" {
        return None;
    }
    Some(PendingKnowledgeModel {
        turn_id: payload.get("turn_id")?.as_str()?.to_owned(),
        injection_id: payload.get("injection_id")?.as_str()?.to_owned(),
        preview_hash: payload.get("expected_preview_hash")?.as_str()?.to_owned(),
        include_knowledge: action == "INCLUDE_AND_SEND",
    })
}

fn validate_knowledge_model_receipt(
    response: &Value,
    context: &PendingKnowledgeModel,
) -> Result<String, BridgeError> {
    let object = response.as_object().ok_or_else(|| {
        BridgeError::new(
            "protocol_mismatch",
            "knowledge model receipt is not an object",
        )
    })?;
    const RECEIPT_KEYS: &[&str] = &[
        "injection_id",
        "turn_id",
        "action",
        "preview_hash",
        "state",
        "decision_source",
        "model_turn_id",
        "model_dispatched",
        "knowledge_included",
        "duplicate",
    ];
    if object.len() != RECEIPT_KEYS.len()
        || object
            .keys()
            .any(|key| !RECEIPT_KEYS.contains(&key.as_str()))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "knowledge model receipt shape mismatch",
        ));
    }
    let string = |key: &str| {
        object.get(key).and_then(Value::as_str).ok_or_else(|| {
            BridgeError::new("protocol_mismatch", "knowledge model receipt field missing")
        })
    };
    let request_id = string("model_turn_id")?;
    let expected_action = if context.include_knowledge {
        "INCLUDE_AND_SEND"
    } else {
        "REJECT_AND_SEND_WITHOUT_KNOWLEDGE"
    };
    let valid_state = if context.include_knowledge {
        matches!(string("state")?, "DISPATCHING" | "INJECTED")
    } else {
        string("state")? == "REJECTED"
    };
    if string("turn_id")? != context.turn_id
        || string("injection_id")? != context.injection_id
        || string("preview_hash")? != context.preview_hash
        || string("action")? != expected_action
        || string("decision_source")? != "USER_APPROVAL"
        || !valid_state
        || object.get("model_dispatched").and_then(Value::as_bool) != Some(true)
        || object.get("knowledge_included").and_then(Value::as_bool)
            != Some(context.include_knowledge)
        || object.get("duplicate").and_then(Value::as_bool).is_none()
        || ensure_request_id(request_id).is_err()
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "knowledge model receipt identity mismatch",
        ));
    }
    Ok(request_id.into())
}

fn knowledge_model_identity_from_event(
    event: &UiControlPlaneEvent,
) -> Result<(ModelRequestIdentity, String, String), BridgeError> {
    let metadata = event.metadata.as_object().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "model event metadata is not an object")
    })?;
    let string = |key: &str| {
        metadata.get(key).and_then(Value::as_str).ok_or_else(|| {
            BridgeError::new("protocol_mismatch", "model event metadata field missing")
        })
    };
    let request_id = event
        .request_id
        .as_deref()
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model event request_id missing"))?;
    let chat_session_id = event.chat_session_id.as_deref().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "model event chat_session_id missing")
    })?;
    let model_id = event
        .model_id
        .as_deref()
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model event model_id missing"))?;
    let submitted_at_unix_ms = metadata
        .get("submitted_at_unix_ms")
        .and_then(Value::as_u64)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model event time missing"))?;
    let max_tokens = metadata
        .get("max_tokens")
        .and_then(Value::as_u64)
        .and_then(|value| u16::try_from(value).ok())
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model event budget missing"))?;
    let binding_fingerprint = string("binding_fingerprint")?;
    let provider_id = string("provider_id")?;
    let harness_id = string("harness_id")?;
    if ensure_request_id(request_id).is_err()
        || ensure_chat_session_id(chat_session_id).is_err()
        || ensure_model_id(model_id).is_err()
        || ensure_fingerprint(binding_fingerprint).is_err()
        || submitted_at_unix_ms == 0
        || submitted_at_unix_ms > 9_007_199_254_740_991
        || !(1..=512).contains(&max_tokens)
        || ensure_provider(provider_id).is_err()
        || ensure_harness(harness_id).is_err()
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "knowledge model event identity mismatch",
        ));
    }
    Ok((
        ModelRequestIdentity {
            request_id: request_id.into(),
            chat_session_id: chat_session_id.into(),
            model_id: model_id.into(),
            submitted_at_unix_ms,
            max_tokens,
            binding_fingerprint: binding_fingerprint.into(),
        },
        provider_id.into(),
        harness_id.into(),
    ))
}

fn validate_model_cancel_ack(
    response: &Value,
    request_id: &str,
) -> Result<ModelCancelAcknowledgement, BridgeError> {
    let object = response.as_object().ok_or_else(|| {
        BridgeError::new(
            "protocol_mismatch",
            "model cancellation acknowledgement is not an object",
        )
    })?;
    let accepted = object
        .get("accepted")
        .and_then(Value::as_bool)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "cancel accepted flag missing"))?;
    let already_terminal = object
        .get("already_terminal")
        .and_then(Value::as_bool)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "cancel terminal flag missing"))?;
    let worker_alive = object
        .get("worker_alive")
        .and_then(Value::as_bool)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "cancel worker flag missing"))?;
    let matching_identity = object.get("request_id").and_then(Value::as_str) == Some(request_id)
        && object.get("turn_id").and_then(Value::as_str) == Some(request_id);
    let state = object.get("state").and_then(Value::as_str);
    let active_shape = accepted
        && !already_terminal
        && matches!(
            (state, worker_alive),
            (Some("Cancelling"), true) | (Some("Cancelled"), false)
        );
    let terminal_shape =
        !accepted && already_terminal && !worker_alive && state == Some("Cancelled");
    if !matching_identity || !(active_shape || terminal_shape) {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model cancellation acknowledgement mismatch",
        ));
    }
    Ok(ModelCancelAcknowledgement {
        accepted,
        already_terminal,
    })
}

fn terminal_model_cancel_ack(request_id: &str) -> Value {
    json!({
        "request_id": request_id,
        "turn_id": request_id,
        "state": "Cancelled",
        "accepted": false,
        "already_terminal": true,
        "worker_alive": false,
    })
}

fn model_cancel_payload(request_id: &str) -> Value {
    json!({ "request_id": request_id })
}

fn model_cancel_request_envelope(transport_id: &str, request_id: &str) -> Value {
    json!({
        "protocol": ipc::IPC_PROTOCOL,
        "version": ipc::IPC_PROTOCOL_VERSION,
        "type": "request",
        "id": transport_id,
        "method": ControlPlaneMethod::ModelTurnCancel.as_wire(),
        "run_id": null,
        "sequence": 0,
        "reply_to": null,
        "payload": model_cancel_payload(request_id),
    })
}

struct ArgumentMetrics {
    max_depth: usize,
    object_key_count: usize,
    node_count: usize,
}

fn measure_arguments(root: &Value) -> ArgumentMetrics {
    let mut stack: Vec<(&Value, usize)> = vec![(root, 1)];
    let mut max_depth: usize = 0;
    let mut object_key_count: usize = 0;
    let mut node_count: usize = 0;
    while let Some((value, depth)) = stack.pop() {
        node_count = node_count.saturating_add(1);
        match value {
            Value::Object(map) => {
                if depth > max_depth {
                    max_depth = depth;
                }
                object_key_count = object_key_count.saturating_add(map.len());
                for child in map.values() {
                    stack.push((child, depth.saturating_add(1)));
                }
            }
            Value::Array(items) => {
                if depth > max_depth {
                    max_depth = depth;
                }
                for child in items {
                    stack.push((child, depth.saturating_add(1)));
                }
            }
            _ => {}
        }
    }
    ArgumentMetrics {
        max_depth,
        object_key_count,
        node_count,
    }
}

fn validate_and_record_model_event(
    entry: &mut ModelRequestEntry,
    event: &UiControlPlaneEvent,
    method: &str,
    sequence: u64,
) -> Result<bool, BridgeError> {
    if event.method != method
        || event.request_id.as_deref() != Some(entry.identity.request_id.as_str())
        || event.chat_session_id.as_deref() != Some(entry.identity.chat_session_id.as_str())
        || event.model_id.as_deref() != Some(entry.identity.model_id.as_str())
        || event.turn_id.as_deref() != Some(entry.identity.request_id.as_str())
        || event.control_plane_version != DESKTOP_STATUS_BRIDGE_VERSION
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model event identity mismatch",
        ));
    }
    let telemetry = validate_model_event_metadata(entry, event, method)?;
    if entry.terminal_seen {
        return Err(BridgeError::new(
            "invalid_sequence",
            "model event followed a terminal event",
        ));
    }
    if sequence != entry.next_sequence || event.sequence != sequence {
        return Err(BridgeError::new(
            "invalid_sequence",
            "model event sequence is not strictly increasing",
        ));
    }
    if entry.cancel_accepted && method != "model.turn.cancelled" {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "non-cancellation event followed accepted cancellation",
        ));
    }

    let terminal = match method {
        "model.turn.started" => {
            if entry.started_seen || event.state != "Streaming" || event.text.is_some() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model start transition",
                ));
            }
            false
        }
        "model.output.delta" => {
            if !entry.started_seen || event.state != "Streaming" || event.text.is_none() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model content transition",
                ));
            }
            false
        }
        "model.turn.completed" => {
            if !entry.started_seen || event.state != "Completed" || event.text.is_some() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model completion transition",
                ));
            }
            true
        }
        "model.turn.cancelled" => {
            if event.state != "Cancelled" || event.text.is_some() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model cancellation transition",
                ));
            }
            true
        }
        "model.turn.timed_out" => {
            if event.state != "TimedOut" || event.text.is_some() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model timeout transition",
                ));
            }
            true
        }
        "model.turn.failed" => {
            if event.state != "Failed" || event.text.is_some() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid model failure transition",
                ));
            }
            true
        }
        "model.tool.request" | "model.turn.tool_calls" => {
            let expected_state = if method == "model.tool.request" {
                "Streaming"
            } else {
                "ToolCalls"
            };
            if event.state != expected_state
                || (method == "model.tool.request" && event.text.is_some())
            {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "invalid tool event transition",
                ));
            }
            if !entry.tools_are_enabled() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "tool events are not permitted when assistant_context.tools is empty",
                ));
            }
            let tool_calls = event
                .metadata
                .get("tool_calls")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    BridgeError::new(
                        "protocol_mismatch",
                        "structured tool_calls metadata is required",
                    )
                })?;
            if tool_calls.is_empty() {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "structured tool_calls metadata is required",
                ));
            }
            if method == "model.tool.request" && tool_calls.len() != 1 {
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "model.tool.request must contain exactly one tool call",
                ));
            }
            let mut seen_ids: HashSet<&str> = HashSet::new();
            for call in tool_calls {
                let envelope = call.as_object().ok_or_else(|| {
                    BridgeError::new(
                        "protocol_mismatch",
                        "structured tool_calls metadata is required",
                    )
                })?;
                if envelope
                    .keys()
                    .any(|key| !matches!(key.as_str(), "id" | "name" | "arguments"))
                {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call envelope contains unknown fields",
                    ));
                }
                let name = call.get("name").and_then(Value::as_str).ok_or_else(|| {
                    BridgeError::new(
                        "protocol_mismatch",
                        "structured tool_calls metadata is required",
                    )
                })?;
                if !entry
                    .permitted_tool_names
                    .iter()
                    .any(|permitted| permitted == name)
                {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool is not permitted for this request",
                    ));
                }
                let id = match call.get("id") {
                    None => {
                        return Err(BridgeError::new(
                            "protocol_mismatch",
                            "tool call id is required",
                        ));
                    }
                    Some(Value::String(s)) => s.as_str(),
                    Some(_) => {
                        return Err(BridgeError::new(
                            "protocol_mismatch",
                            "tool call id must be a string",
                        ));
                    }
                };
                if id.is_empty() || id.chars().all(char::is_whitespace) {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call id is required",
                    ));
                }
                if !seen_ids.insert(id) {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "duplicate tool call id",
                    ));
                }
                let arguments = call.get("arguments").ok_or_else(|| {
                    BridgeError::new("protocol_mismatch", "tool call arguments are required")
                })?;
                if !arguments.is_object() {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments must be an object",
                    ));
                }
                let serialized = serde_json::to_string(arguments).map_err(|_| {
                    BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments exceed maximum size",
                    )
                })?;
                if serialized.len() > MAX_ARGUMENT_BYTES {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments exceed maximum size",
                    ));
                }
                let metrics = measure_arguments(arguments);
                if metrics.max_depth > MAX_ARGUMENT_DEPTH {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments exceed maximum nesting depth",
                    ));
                }
                if metrics.object_key_count > MAX_ARGUMENT_OBJECT_KEYS {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments exceed maximum object key count",
                    ));
                }
                if metrics.node_count > MAX_ARGUMENT_NODES {
                    return Err(BridgeError::new(
                        "protocol_mismatch",
                        "tool call arguments exceed maximum node count",
                    ));
                }
                if let Err(e) = validate_model_tool_arguments(name, arguments) {
                    eprintln!("validate_model_tool_arguments failed: {}", e.message);
                    return Err(e);
                }
            }
            if method == "model.tool.request"
                && telemetry.tools_executed != entry.intermediate_tool_calls.len() as u64 + 1
            {
                eprintln!("model.tool.request tools_executed is not cumulative");
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "model.tool.request tools_executed is not cumulative",
                ));
            }
            if method == "model.turn.tool_calls"
                && tool_calls.as_slice() != entry.intermediate_tool_calls.as_slice()
            {
                eprintln!("tool call provenance mismatch");
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "tool call provenance mismatch",
                ));
            }
            if method == "model.turn.tool_calls"
                && (telemetry.tools_executed != tool_calls.len() as u64
                    || telemetry.tools_executed != entry.intermediate_tool_calls.len() as u64)
            {
                eprintln!("model.turn.tool_calls tools_executed mismatch");
                return Err(BridgeError::new(
                    "protocol_mismatch",
                    "model.turn.tool_calls tools_executed mismatch",
                ));
            }
            if entry.event_count + 1 > MAX_MODEL_EVENTS_PER_REQUEST {
                eprintln!("model event limit reached");
                return Err(BridgeError::new(
                    "budget_exceeded",
                    "model event limit reached",
                ));
            }
            if method == "model.tool.request" {
                entry.intermediate_tool_calls.push(tool_calls[0].clone());
            }
            entry.next_sequence += 1;
            entry.event_count += 1;
            entry.terminal_seen = method == "model.turn.tool_calls";
            entry.provider_id = Some(telemetry.provider_id);
            entry.harness_id = Some(telemetry.harness_id);
            entry.model_called = telemetry.model_called;
            entry.generated_bytes = telemetry.generated_bytes;
            return Ok(true);
        }
        _ => {
            return Err(BridgeError::new(
                "unsupported_method",
                "unsupported model event method",
            ))
        }
    };

    let text_len = event.text.as_deref().unwrap_or("").len();
    if entry.event_count + 1 > MAX_MODEL_EVENTS_PER_REQUEST {
        return Err(BridgeError::new(
            "budget_exceeded",
            "model event limit reached",
        ));
    }
    if entry.event_text + text_len > MAX_MODEL_EVENT_TEXT_PER_REQUEST {
        return Err(BridgeError::new(
            "payload_too_large",
            "model event text limit reached",
        ));
    }
    entry.next_sequence += 1;
    entry.event_count += 1;
    entry.event_text += text_len;
    entry.started_seen |= method == "model.turn.started";
    entry.terminal_seen = terminal;
    entry.provider_id = Some(telemetry.provider_id);
    entry.harness_id = Some(telemetry.harness_id);
    entry.model_called = telemetry.model_called;
    entry.generated_bytes = telemetry.generated_bytes;
    Ok(true)
}

struct ValidatedModelTelemetry {
    provider_id: String,
    harness_id: String,
    model_called: bool,
    generated_bytes: u64,
    tools_executed: u64,
}

fn validate_model_event_metadata(
    entry: &ModelRequestEntry,
    event: &UiControlPlaneEvent,
    method: &str,
) -> Result<ValidatedModelTelemetry, BridgeError> {
    let metadata = event.metadata.as_object().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "model event metadata is not an object")
    })?;
    const BASE_KEYS: &[&str] = &[
        "provider_id",
        "harness_id",
        "request_id",
        "turn_id",
        "chat_session_id",
        "model_id",
        "submitted_at_unix_ms",
        "max_tokens",
        "binding_fingerprint",
        "model_called",
        "tools_executed",
        "persistence",
        "generated_bytes",
    ];
    const KNOWLEDGE_KEYS: &[&str] = &[
        "knowledge_injection_id",
        "knowledge_request_id",
        "knowledge_bundle_id",
        "knowledge_vault_revision",
        "knowledge_preview_hash",
        "knowledge_context_sha256",
        "knowledge_source_count",
        "knowledge_serialization_format",
        "knowledge_decision_source",
        "knowledge_synthetic_message",
        "knowledge_context_reference_data",
    ];
    let is_tool_event = matches!(method, "model.tool.request" | "model.turn.tool_calls");
    if metadata.keys().any(|key| {
        !BASE_KEYS.contains(&key.as_str())
            && key != "error"
            && !KNOWLEDGE_KEYS.contains(&key.as_str())
            && !(is_tool_event && key == "tool_calls")
    }) || BASE_KEYS.iter().any(|key| !metadata.contains_key(*key))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model event metadata shape mismatch",
        ));
    }
    let provider_id = metadata
        .get("provider_id")
        .and_then(Value::as_str)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model provider missing"))?;
    let harness_id = metadata
        .get("harness_id")
        .and_then(Value::as_str)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model harness missing"))?;
    let model_called = metadata
        .get("model_called")
        .and_then(Value::as_bool)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model_called missing"))?;
    let tools_executed = metadata
        .get("tools_executed")
        .and_then(Value::as_u64)
        .filter(|value| *value <= 9_007_199_254_740_991)
        .ok_or_else(|| {
            BridgeError::new(
                "protocol_mismatch",
                "tools_executed must be a nonnegative safe integer",
            )
        })?;
    let persistence_is_disabled =
        metadata.get("persistence").and_then(Value::as_bool) == Some(false);
    let generated_bytes = metadata
        .get("generated_bytes")
        .and_then(Value::as_u64)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "generated_bytes missing"))?;
    let base_identity_matches = metadata.get("request_id").and_then(Value::as_str)
        == Some(entry.identity.request_id.as_str())
        && metadata.get("turn_id").and_then(Value::as_str)
            == Some(entry.identity.request_id.as_str())
        && metadata.get("chat_session_id").and_then(Value::as_str)
            == Some(entry.identity.chat_session_id.as_str())
        && metadata.get("model_id").and_then(Value::as_str)
            == Some(entry.identity.model_id.as_str())
        && metadata.get("submitted_at_unix_ms").and_then(Value::as_u64)
            == Some(entry.identity.submitted_at_unix_ms)
        && metadata.get("max_tokens").and_then(Value::as_u64)
            == Some(u64::from(entry.identity.max_tokens))
        && metadata.get("binding_fingerprint").and_then(Value::as_str)
            == Some(entry.identity.binding_fingerprint.as_str());
    if !base_identity_matches
        || ensure_provider(provider_id).is_err()
        || ensure_harness(harness_id).is_err()
        || entry
            .provider_id
            .as_deref()
            .is_some_and(|expected| expected != provider_id)
        || entry
            .harness_id
            .as_deref()
            .is_some_and(|expected| expected != harness_id)
        || (entry.model_called && !model_called)
        || (entry.tools_are_enabled()
            && !matches!(method, "model.tool.request" | "model.turn.tool_calls")
            && tools_executed != entry.intermediate_tool_calls.len() as u64)
        || (!entry.tools_are_enabled() && tools_executed != 0)
        || !persistence_is_disabled
        || generated_bytes < entry.generated_bytes
        || generated_bytes > MAX_MODEL_EVENT_TEXT_PER_REQUEST as u64
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model event telemetry mismatch",
        ));
    }
    let has_knowledge = KNOWLEDGE_KEYS.iter().any(|key| metadata.contains_key(*key));
    let knowledge_required =
        entry.knowledge_included && event.method.as_str() == "model.turn.started";
    if (knowledge_required && !has_knowledge)
        || (has_knowledge && !entry.knowledge_included)
        || (has_knowledge
            && KNOWLEDGE_KEYS
                .iter()
                .any(|key| !metadata.contains_key(*key)))
        || (has_knowledge && !validate_knowledge_event_metadata(entry, metadata))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model knowledge telemetry mismatch",
        ));
    }
    let error = metadata.get("error");
    if error.is_some()
        != matches!(
            event.method.as_str(),
            "model.turn.failed" | "model.turn.timed_out"
        )
        || error.is_some_and(|error| !valid_model_error(error))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model event error telemetry mismatch",
        ));
    }
    Ok(ValidatedModelTelemetry {
        provider_id: provider_id.into(),
        harness_id: harness_id.into(),
        model_called,
        generated_bytes,
        tools_executed,
    })
}

fn validate_knowledge_event_metadata(
    entry: &ModelRequestEntry,
    metadata: &serde_json::Map<String, Value>,
) -> bool {
    let safe_string = |key: &str, prefix: &str, max: usize| {
        metadata
            .get(key)
            .and_then(Value::as_str)
            .is_some_and(|value| {
                value.starts_with(prefix)
                    && value.len() <= max
                    && value
                        .chars()
                        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, ':' | '-' | '_' | '.'))
            })
    };
    let exact_hex = |key: &str, prefix: &str| {
        metadata
            .get(key)
            .and_then(Value::as_str)
            .is_some_and(|value| {
                value.len() == prefix.len() + 64
                    && value.starts_with(prefix)
                    && value[prefix.len()..]
                        .chars()
                        .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
            })
    };
    metadata
        .get("knowledge_injection_id")
        .and_then(Value::as_str)
        == entry.knowledge_injection_id.as_deref()
        && safe_string("knowledge_request_id", "kreq:", 128)
        && exact_hex("knowledge_bundle_id", "kb:")
        && exact_hex("knowledge_vault_revision", "sha256:")
        && exact_hex("knowledge_preview_hash", "sha256:")
        && exact_hex("knowledge_context_sha256", "sha256:")
        && metadata
            .get("knowledge_source_count")
            .and_then(Value::as_u64)
            .is_some_and(|value| value <= 8)
        && metadata
            .get("knowledge_serialization_format")
            .and_then(Value::as_str)
            == Some("localcomet.knowledge-context.v1")
        && metadata
            .get("knowledge_decision_source")
            .and_then(Value::as_str)
            == Some("USER_APPROVAL")
        && metadata
            .get("knowledge_synthetic_message")
            .and_then(Value::as_bool)
            == Some(true)
        && metadata
            .get("knowledge_context_reference_data")
            .and_then(Value::as_bool)
            == Some(true)
}

fn valid_model_error(value: &Value) -> bool {
    let Some(error) = value.as_object() else {
        return false;
    };
    if error.len() != 3
        || !error.contains_key("code")
        || !error.contains_key("message")
        || !error.contains_key("retryable")
    {
        return false;
    }
    let code_ok = error
        .get("code")
        .and_then(Value::as_str)
        .is_some_and(|code| {
            !code.is_empty()
                && code.len() <= 64
                && code
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
        });
    let message_ok = error
        .get("message")
        .and_then(Value::as_str)
        .is_some_and(|message| message.len() <= 256 && !message.chars().any(|ch| ch.is_control()));
    code_ok && message_ok && error.get("retryable").and_then(Value::as_bool).is_some()
}

fn project_model_event_metadata(event: &UiControlPlaneEvent) -> Result<Value, BridgeError> {
    let metadata = event.metadata.as_object().ok_or_else(|| {
        BridgeError::new("protocol_mismatch", "model event metadata is not an object")
    })?;
    let mut projected = serde_json::Map::new();
    for key in [
        "provider_id",
        "harness_id",
        "binding_fingerprint",
        "model_called",
        "tools_executed",
        "persistence",
        "generated_bytes",
    ] {
        projected.insert(
            key.into(),
            metadata
                .get(key)
                .cloned()
                .ok_or_else(|| BridgeError::new("protocol_mismatch", "model telemetry missing"))?,
        );
    }
    if matches!(
        event.method.as_str(),
        "model.tool.request" | "model.turn.tool_calls"
    ) {
        projected.insert(
            "tool_calls".into(),
            metadata
                .get("tool_calls")
                .cloned()
                .ok_or_else(|| BridgeError::new("protocol_mismatch", "tool telemetry missing"))?,
        );
    }
    if metadata.contains_key("knowledge_injection_id") {
        for key in [
            "knowledge_injection_id",
            "knowledge_request_id",
            "knowledge_bundle_id",
            "knowledge_vault_revision",
            "knowledge_preview_hash",
            "knowledge_context_sha256",
            "knowledge_source_count",
            "knowledge_serialization_format",
            "knowledge_decision_source",
            "knowledge_synthetic_message",
            "knowledge_context_reference_data",
        ] {
            projected.insert(
                key.into(),
                metadata.get(key).cloned().ok_or_else(|| {
                    BridgeError::new("protocol_mismatch", "knowledge telemetry missing")
                })?,
            );
        }
    }
    if let Some(error) = metadata.get("error").and_then(Value::as_object) {
        projected.insert(
            "error".into(),
            json!({
                "code": sanitize_text(
                    error.get("code").and_then(Value::as_str).unwrap_or("internal_error"),
                    64,
                ),
                "message": if event.method == "model.turn.timed_out" {
                    "model request timed out"
                } else {
                    "local model request failed"
                },
                "retryable": error.get("retryable").and_then(Value::as_bool).unwrap_or(false),
            }),
        );
    }
    Ok(Value::Object(projected))
}

fn model_event_is_gated(entry: &ModelRequestEntry) -> bool {
    !entry.accepted
        || entry.cancel_pending
        || entry.cancel_requested_before_acceptance
        || entry.releasing_events
}

fn record_model_acceptance(entry: &mut ModelRequestEntry) -> (bool, bool) {
    entry.accepted = true;
    let needs_recancel =
        entry.cancel_requested_before_acceptance && !entry.cancel_accepted && !entry.terminal_seen;
    if !needs_recancel {
        entry.cancel_requested_before_acceptance = false;
    }
    (begin_model_event_release(entry), needs_recancel)
}

fn take_authoritative_buffered_terminal(
    entry: &mut ModelRequestEntry,
) -> Option<Vec<UiControlPlaneEvent>> {
    if entry.terminal_seen {
        Some(std::mem::take(&mut entry.buffered_events))
    } else {
        None
    }
}

fn begin_model_event_release(entry: &mut ModelRequestEntry) -> bool {
    if entry.accepted
        && !entry.cancel_pending
        && !entry.cancel_requested_before_acceptance
        && !entry.releasing_events
    {
        entry.releasing_events = true;
        true
    } else {
        false
    }
}

fn model_terminal_event(
    entry: &ModelRequestEntry,
    method: &str,
    state: &str,
    code: &str,
    _message: &str,
) -> UiControlPlaneEvent {
    UiControlPlaneEvent {
        method: method.into(),
        sequence: entry.next_sequence,
        reply_to: entry.identity.request_id.clone(),
        request_id: Some(entry.identity.request_id.clone()),
        chat_session_id: Some(entry.identity.chat_session_id.clone()),
        model_id: Some(entry.identity.model_id.clone()),
        control_plane_version: DESKTOP_STATUS_BRIDGE_VERSION.into(),
        session_id: None,
        thread_id: None,
        turn_id: Some(entry.identity.request_id.clone()),
        item_id: None,
        state: state.into(),
        kind: None,
        text: None,
        metadata: json!({
            "provider_id": entry.provider_id.as_deref().unwrap_or("managed-llama-cpp"),
            "harness_id": entry.harness_id.as_deref().unwrap_or("minimal"),
            "binding_fingerprint": entry.identity.binding_fingerprint,
            "model_called": entry.model_called,
            "tools_executed": 0,
            "persistence": false,
            "generated_bytes": entry.generated_bytes,
            "error": {
                "code": sanitize_text(code, 64),
                "message": if method == "model.turn.timed_out" {
                    "model request timed out"
                } else {
                    "local model request failed"
                },
                "retryable": true,
            }
        }),
    }
}

fn validate_payload_for_method(
    method: ControlPlaneMethod,
    payload: &Value,
) -> Result<(), BridgeError> {
    match method {
        ControlPlaneMethod::SessionCreate => ensure_payload_keys(payload, &["title"]),
        ControlPlaneMethod::SessionClose => ensure_payload_keys(payload, &["session_id"]),
        ControlPlaneMethod::ThreadCreate => ensure_payload_keys(payload, &["session_id", "title"]),
        ControlPlaneMethod::TurnStartMock => {
            ensure_payload_keys(payload, &["thread_id", "prompt", "behavior"])
        }
        ControlPlaneMethod::TurnStatus => ensure_payload_keys(payload, &["turn_id"]),
        ControlPlaneMethod::TurnCancel => ensure_payload_keys(payload, &["turn_id", "reason"]),
        ControlPlaneMethod::ModelCatalogGet => ensure_payload_keys(payload, &[]),
        ControlPlaneMethod::ModelGatewayProbe => ensure_payload_keys(payload, &["port"]),
        ControlPlaneMethod::ModelModelsList => ensure_payload_keys(payload, &["port"]),
        ControlPlaneMethod::ModelBindingSet => ensure_payload_keys(
            payload,
            &[
                "provider_id",
                "harness_id",
                "port",
                "model_id",
                "confirmed",
                "runtime_instance_id",
            ],
        ),
        ControlPlaneMethod::ModelTurnStart => ensure_payload_keys(
            payload,
            &[
                "request_id",
                "chat_session_id",
                "model_id",
                "submitted_at_unix_ms",
                "max_tokens",
                "prompt",
                "assistant_context",
                "binding_fingerprint",
            ],
        ),
        ControlPlaneMethod::ModelTurnCancel => ensure_payload_keys(payload, &["request_id"]),
        ControlPlaneMethod::ModelManagedAttach => ensure_payload_keys(
            payload,
            &[
                "runtime_instance_id",
                "port",
                "credential",
                "expected_model_alias",
                "model_id",
                "binding_fingerprint",
            ],
        ),
        ControlPlaneMethod::ModelManagedDetach => ensure_payload_keys(payload, &[]),
        ControlPlaneMethod::KnowledgeTurnPreview => ensure_payload_keys(
            payload,
            &["turn_id", "intent", "max_context_chars", "max_results"],
        ),
        ControlPlaneMethod::KnowledgeTurnDecide => ensure_payload_keys(
            payload,
            &["turn_id", "injection_id", "expected_preview_hash", "action"],
        ),
        ControlPlaneMethod::KnowledgeReviewList => validate_knowledge_review_list_payload(payload),
        ControlPlaneMethod::KnowledgeReviewGet => validate_knowledge_review_get_payload(payload),
        ControlPlaneMethod::KnowledgeReviewSnapshot
        | ControlPlaneMethod::KnowledgeReviewRefresh => ensure_payload_keys(payload, &[]),
        ControlPlaneMethod::KnowledgeReviewDecisionCreate => {
            validate_knowledge_review_decision_create_payload(payload)
        }
        ControlPlaneMethod::ToolCall => validate_tool_call_payload(payload),
        _ => ensure_payload_keys(payload, &[]),
    }
}

fn validate_tool_call_payload(payload: &Value) -> Result<(), BridgeError> {
    const REQUIRED: [&str; 5] = ["tool", "input", "workspace", "workspace_digest", "session"];
    const OPTIONAL: [&str; 1] = ["grant_id"];
    let Some(object) = payload.as_object() else {
        return Err(BridgeError::new(
            "invalid_payload",
            "payload must be an object",
        ));
    };
    if REQUIRED.iter().any(|key| !object.contains_key(*key)) {
        return Err(BridgeError::new(
            "invalid_payload",
            "unexpected payload shape",
        ));
    }
    let is_allowed = |key: &str| -> bool { REQUIRED.contains(&key) || OPTIONAL.contains(&key) };
    if object.keys().any(|key| !is_allowed(key)) {
        return Err(BridgeError::new(
            "invalid_payload",
            "unexpected payload shape",
        ));
    }
    let nonempty_str = |key: &str| -> bool {
        payload
            .get(key)
            .and_then(Value::as_str)
            .is_some_and(|value| !value.is_empty())
    };
    if !nonempty_str("tool") {
        return Err(BridgeError::new("invalid_payload", "tool must be a string"));
    }
    for key in ["workspace", "workspace_digest", "session"] {
        if !nonempty_str(key) {
            return Err(BridgeError::new(
                "invalid_payload",
                &format!("{key} must be a string"),
            ));
        }
    }
    if object.contains_key("grant_id") && !nonempty_str("grant_id") {
        return Err(BridgeError::new(
            "invalid_payload",
            "grant_id must be a string",
        ));
    }
    Ok(())
}

pub(crate) fn build_tool_call_request(
    tool: &str,
    input: &Value,
    workspace: &str,
    workspace_digest: &str,
    session: &str,
    grant_id: Option<&str>,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    let mut payload = json!({
        "tool": tool,
        "input": input,
        "workspace": workspace,
        "workspace_digest": workspace_digest,
        "session": session,
    });
    if let Some(grant_id) = grant_id {
        payload["grant_id"] = json!(grant_id);
    }
    validate_tool_call_payload(&payload)?;
    Ok((ControlPlaneMethod::ToolCall, payload))
}

fn validate_knowledge_review_list_payload(payload: &Value) -> Result<(), BridgeError> {
    ensure_payload_keys(payload, &["offset", "limit"])?;
    let offset = payload
        .get("offset")
        .and_then(Value::as_u64)
        .and_then(|value| u16::try_from(value).ok())
        .ok_or_else(|| BridgeError::new("invalid_payload", "offset must be an integer"))?;
    let limit = payload
        .get("limit")
        .and_then(Value::as_u64)
        .and_then(|value| u16::try_from(value).ok())
        .ok_or_else(|| BridgeError::new("invalid_payload", "limit must be an integer"))?;
    ensure_knowledge_review_page(offset, limit)
}

fn validate_knowledge_review_get_payload(payload: &Value) -> Result<(), BridgeError> {
    ensure_payload_keys(payload, &["review_artifact_identity"])?;
    let identity = payload
        .get("review_artifact_identity")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            BridgeError::new(
                "invalid_payload",
                "review_artifact_identity must be a string",
            )
        })?;
    ensure_review_artifact_identity(identity)
}

fn validate_knowledge_review_decision_create_payload(payload: &Value) -> Result<(), BridgeError> {
    ensure_payload_keys(
        payload,
        &[
            "review_contract_version",
            "proposal_id",
            "review_artifact_identity",
            "change_identity",
            "observed_vault_revision",
            "decision",
            "comment",
            "actor_identifier",
            "actor_display_name",
            "actor_source",
        ],
    )?;
    let string_value = |key: &str| -> Result<&str, BridgeError> {
        payload
            .get(key)
            .and_then(Value::as_str)
            .ok_or_else(|| BridgeError::new("invalid_payload", &format!("{key} must be a string")))
    };
    ensure_exact_contract(
        "review_contract_version",
        string_value("review_contract_version")?,
        KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
    )?;
    ensure_prefixed_identity("proposal_id", string_value("proposal_id")?, "kprop:")?;
    ensure_review_artifact_identity(string_value("review_artifact_identity")?)?;
    match payload.get("change_identity") {
        Some(Value::Null) => {}
        Some(Value::String(identity)) => {
            ensure_prefixed_identity("change_identity", identity, "kchange:")?;
        }
        _ => {
            return Err(BridgeError::new(
                "invalid_payload",
                "change_identity must be null or a string",
            ));
        }
    }
    ensure_prefixed_identity(
        "observed_vault_revision",
        string_value("observed_vault_revision")?,
        "sha256:",
    )?;
    let decision = string_value("decision")?;
    ensure_review_decision(decision)?;
    let comment = string_value("comment")?;
    ensure_bounded_text(
        "comment",
        comment,
        MAX_REVIEW_COMMENT_CHARS,
        MAX_REVIEW_COMMENT_BYTES,
        true,
    )?;
    if decision == "REQUEST_CHANGES" && comment.trim().is_empty() {
        return Err(BridgeError::new(
            "invalid_payload",
            "REQUEST_CHANGES requires a meaningful comment",
        ));
    }
    ensure_bounded_text(
        "actor_identifier",
        string_value("actor_identifier")?,
        MAX_REVIEW_ACTOR_IDENTIFIER_CHARS,
        MAX_REVIEW_ACTOR_IDENTIFIER_BYTES,
        false,
    )?;
    ensure_bounded_text(
        "actor_display_name",
        string_value("actor_display_name")?,
        MAX_REVIEW_ACTOR_DISPLAY_NAME_CHARS,
        MAX_REVIEW_ACTOR_DISPLAY_NAME_BYTES,
        false,
    )?;
    let actor_source = string_value("actor_source")?;
    ensure_bounded_text(
        "actor_source",
        actor_source,
        MAX_REVIEW_ACTOR_SOURCE_CHARS,
        MAX_REVIEW_ACTOR_SOURCE_BYTES,
        false,
    )?;
    if actor_source != KNOWLEDGE_REVIEW_ACTOR_SOURCE {
        return Err(BridgeError::new(
            "invalid_payload",
            "actor_source is not the fixed Review Center source",
        ));
    }
    Ok(())
}

fn ensure_knowledge_review_page(offset: u16, limit: u16) -> Result<(), BridgeError> {
    if offset > MAX_KNOWLEDGE_REVIEW_OFFSET {
        return Err(BridgeError::new(
            "invalid_payload",
            "knowledge review offset is outside the allowed range",
        ));
    }
    if !(1..=MAX_KNOWLEDGE_REVIEW_LIMIT).contains(&limit) {
        return Err(BridgeError::new(
            "invalid_payload",
            "knowledge review limit is outside the allowed range",
        ));
    }
    Ok(())
}

fn ensure_review_artifact_identity(value: &str) -> Result<(), BridgeError> {
    let valid = value.strip_prefix("kreview:").is_some_and(|digest| {
        digest.len() == 64
            && digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    });
    if valid {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "review_artifact_identity is invalid",
        ))
    }
}

fn ensure_prefixed_identity(name: &str, value: &str, prefix: &str) -> Result<(), BridgeError> {
    let valid = value.strip_prefix(prefix).is_some_and(|digest| {
        digest.len() == 64
            && digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    });
    if valid {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            &format!("{name} is invalid"),
        ))
    }
}

fn ensure_exact_contract(name: &str, value: &str, expected: &str) -> Result<(), BridgeError> {
    if value == expected {
        Ok(())
    } else {
        Err(BridgeError::new(
            "unsupported_version",
            &format!("{name} is unsupported"),
        ))
    }
}

fn ensure_review_decision(value: &str) -> Result<(), BridgeError> {
    if matches!(value, "APPROVE" | "REJECT" | "REQUEST_CHANGES") {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "review decision is unsupported",
        ))
    }
}

fn ensure_bounded_text(
    name: &str,
    value: &str,
    max_chars: usize,
    max_bytes: usize,
    allow_empty: bool,
) -> Result<(), BridgeError> {
    if value.contains('\0')
        || value.chars().count() > max_chars
        || value.len() > max_bytes
        || (!allow_empty && value.trim().is_empty())
    {
        return Err(BridgeError::new(
            "invalid_payload",
            &format!("{name} is invalid"),
        ));
    }
    Ok(())
}

fn ensure_knowledge_review_response_bound(payload: &Value) -> Result<(), BridgeError> {
    let bytes = serde_json::to_vec(payload)
        .map_err(|_| BridgeError::new("invalid_json", "review response serialization failed"))?;
    if bytes.len() <= MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES {
        Ok(())
    } else {
        Err(BridgeError::new(
            "payload_too_large",
            "knowledge review response exceeds the allowed size",
        ))
    }
}

fn ensure_payload_keys(payload: &Value, expected: &[&str]) -> Result<(), BridgeError> {
    let Some(object) = payload.as_object() else {
        return Err(BridgeError::new(
            "invalid_payload",
            "payload must be an object",
        ));
    };
    if object.len() != expected.len() || expected.iter().any(|key| !object.contains_key(*key)) {
        return Err(BridgeError::new(
            "invalid_payload",
            "unexpected payload shape",
        ));
    }
    Ok(())
}

fn ensure_id(name: &str, value: &str) -> Result<(), BridgeError> {
    ensure_lower_hex_id(name, value, 24)
}

fn ensure_runtime_instance_id(value: &str) -> Result<(), BridgeError> {
    ensure_lower_hex_id("runtime_instance_id", value, 32)
}

fn ensure_lower_hex_id(name: &str, value: &str, expected_len: usize) -> Result<(), BridgeError> {
    if value.len() == expected_len
        && value
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            &format!("{name} is invalid"),
        ))
    }
}

fn ensure_request_id(value: &str) -> Result<(), BridgeError> {
    ensure_id("request_id", value)
}

fn ensure_chat_session_id(value: &str) -> Result<(), BridgeError> {
    if !value.is_empty()
        && value.len() <= 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
    {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "chat_session_id is invalid",
        ))
    }
}

fn ensure_len(name: &str, value: &str, limit: usize) -> Result<(), BridgeError> {
    if value.chars().count() <= limit {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            &format!("{name} is too long"),
        ))
    }
}

fn ensure_model_prompt(value: &str) -> Result<(), BridgeError> {
    if !value.trim().is_empty() && !value.contains('\0') && value.len() <= MAX_MODEL_PROMPT_CHARS {
        Ok(())
    } else {
        Err(BridgeError::new("invalid_payload", "prompt is invalid"))
    }
}

fn ensure_model_port(value: u16) -> Result<(), BridgeError> {
    if value >= MIN_MODEL_PORT {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "port is outside the allowed range",
        ))
    }
}

fn ensure_provider(value: &str) -> Result<(), BridgeError> {
    if matches!(value, "openai-compatible-local" | "managed-llama-cpp") {
        Ok(())
    } else {
        Err(BridgeError::new("invalid_payload", "unsupported provider"))
    }
}

fn ensure_harness(value: &str) -> Result<(), BridgeError> {
    if matches!(value, "minimal" | "native-localcomet") {
        Ok(())
    } else {
        Err(BridgeError::new("invalid_payload", "unsupported harness"))
    }
}

fn ensure_model_id(value: &str) -> Result<(), BridgeError> {
    if !value.is_empty()
        && value.len() <= 192
        && !value.contains('\0')
        && !value.chars().any(char::is_whitespace)
    {
        Ok(())
    } else {
        Err(BridgeError::new("invalid_payload", "invalid model id"))
    }
}

fn ensure_fingerprint(value: &str) -> Result<(), BridgeError> {
    if value.len() == 64
        && value
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "invalid binding fingerprint",
        ))
    }
}

fn allowed_event_method(method: &str) -> bool {
    matches!(
        method,
        "sidecar.status"
            | "session.created"
            | "session.closed"
            | "thread.created"
            | "turn.started"
            | "turn.completed"
            | "turn.cancelled"
            | "turn.failed"
            | "item.started"
            | "item.delta"
            | "item.completed"
            | "model.turn.started"
            | "model.output.delta"
            | "model.turn.completed"
            | "model.turn.cancelled"
            | "model.turn.timed_out"
            | "model.turn.failed"
            | "model.tool.request"
            | "model.turn.tool_calls"
    )
}

fn allowed_model_event_method(method: &str) -> bool {
    matches!(
        method,
        "model.turn.started"
            | "model.output.delta"
            | "model.turn.completed"
            | "model.turn.cancelled"
            | "model.turn.timed_out"
            | "model.turn.failed"
            | "model.tool.request"
            | "model.turn.tool_calls"
    )
}

fn is_model_terminal_method(method: &str) -> bool {
    matches!(
        method,
        "model.turn.completed"
            | "model.turn.cancelled"
            | "model.turn.timed_out"
            | "model.turn.failed"
            | "model.turn.tool_calls"
    )
}

fn ui_event_from_envelope(envelope: &Value) -> Result<UiControlPlaneEvent, BridgeError> {
    let payload = envelope
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| BridgeError::new("invalid_payload", "event payload missing"))?;
    Ok(UiControlPlaneEvent {
        method: string_field(envelope, "method")?,
        sequence: envelope
            .get("sequence")
            .and_then(Value::as_u64)
            .ok_or_else(|| BridgeError::new("invalid_sequence", "event sequence missing"))?,
        reply_to: string_field(envelope, "reply_to")
            .or_else(|_| string_field(envelope, "run_id"))?,
        request_id: optional_id_payload(payload, "request_id")?,
        chat_session_id: optional_chat_session_id_payload(payload)?,
        model_id: optional_model_id_payload(payload)?,
        control_plane_version: string_payload(payload, "control_plane_version")?,
        session_id: optional_id_payload(payload, "session_id")?,
        thread_id: optional_id_payload(payload, "thread_id")?,
        turn_id: optional_id_payload(payload, "turn_id")?,
        item_id: optional_id_payload(payload, "item_id")?,
        state: string_payload(payload, "state")?,
        kind: optional_string_payload(payload, "kind")?,
        text: optional_string_payload(payload, "text")?
            .map(|text| sanitize_text(&text, MAX_DELTA_CHARS)),
        metadata: payload
            .get("metadata")
            .cloned()
            .unwrap_or_else(|| json!({})),
    })
}

fn string_field(envelope: &Value, key: &str) -> Result<String, BridgeError> {
    envelope
        .get(key)
        .and_then(Value::as_str)
        .map(|value| sanitize_text(value, 96))
        .ok_or_else(|| BridgeError::new("invalid_payload", "missing string field"))
}

fn string_payload(
    payload: &serde_json::Map<String, Value>,
    key: &str,
) -> Result<String, BridgeError> {
    payload
        .get(key)
        .and_then(Value::as_str)
        .map(|value| sanitize_text(value, 128))
        .ok_or_else(|| BridgeError::new("invalid_payload", "missing event payload field"))
}

fn optional_string_payload(
    payload: &serde_json::Map<String, Value>,
    key: &str,
) -> Result<Option<String>, BridgeError> {
    match payload.get(key) {
        Some(Value::Null) | None => Ok(None),
        Some(Value::String(value)) if value.len() <= MAX_DELTA_CHARS => {
            Ok(Some(sanitize_text(value, MAX_DELTA_CHARS)))
        }
        Some(Value::String(_)) => Err(BridgeError::new(
            "payload_too_large",
            "event text exceeds the allowed size",
        )),
        _ => Err(BridgeError::new(
            "invalid_payload",
            "invalid optional string field",
        )),
    }
}

fn optional_id_payload(
    payload: &serde_json::Map<String, Value>,
    key: &str,
) -> Result<Option<String>, BridgeError> {
    let value = optional_string_payload(payload, key)?;
    if let Some(id) = &value {
        ensure_id(key, id)?;
    }
    Ok(value)
}

fn optional_chat_session_id_payload(
    payload: &serde_json::Map<String, Value>,
) -> Result<Option<String>, BridgeError> {
    match payload.get("chat_session_id") {
        Some(Value::Null) | None => Ok(None),
        Some(Value::String(value)) => {
            ensure_chat_session_id(value)?;
            Ok(Some(value.clone()))
        }
        _ => Err(BridgeError::new(
            "invalid_payload",
            "invalid chat_session_id field",
        )),
    }
}

fn optional_model_id_payload(
    payload: &serde_json::Map<String, Value>,
) -> Result<Option<String>, BridgeError> {
    match payload.get("model_id") {
        Some(Value::Null) | None => Ok(None),
        Some(Value::String(value)) => {
            ensure_model_id(value)?;
            Ok(Some(value.clone()))
        }
        _ => Err(BridgeError::new(
            "invalid_payload",
            "invalid model_id field",
        )),
    }
}

fn sanitize_text(value: &str, limit: usize) -> String {
    let mut text = value.replace('\0', "");
    for marker in ["Traceback", "PRIVATE KEY", "bearer ", "Bearer "] {
        if let Some(index) = text.find(marker) {
            text.replace_range(index.., "<REDACTED_TEXT>");
        }
    }
    redact_sk_tokens(&mut text);
    if text.len() > limit {
        let mut boundary = limit;
        while boundary > 0 && !text.is_char_boundary(boundary) {
            boundary -= 1;
        }
        text.truncate(boundary);
    }
    text
}

/// Masks only tokens matching `sk-[A-Za-z0-9_-]{8,}` (parity with the frontend
/// sanitizer), so legitimate output like `task-1`, `disk-usage` or `flask-app`
/// is preserved instead of truncating everything after the first "sk-".
fn redact_sk_tokens(text: &mut String) {
    let mut output = String::with_capacity(text.len());
    let mut rest = text.as_str();
    while let Some(offset) = rest.find("sk-") {
        output.push_str(&rest[..offset]);
        let tail = &rest[offset + "sk-".len()..];
        let run = tail
            .bytes()
            .take_while(|byte| byte.is_ascii_alphanumeric() || *byte == b'_' || *byte == b'-')
            .count();
        if run >= 8 {
            output.push_str("<REDACTED_TEXT>");
        } else {
            output.push_str(&rest[offset..offset + "sk-".len() + run]);
        }
        rest = &tail[run..];
    }
    output.push_str(rest);
    *text = output;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_text_masks_real_sk_secret_token() {
        assert_eq!(
            sanitize_text("token: sk-AbCd1234567890 done", 1024),
            "token: <REDACTED_TEXT> done"
        );
    }

    #[test]
    fn sanitize_text_keeps_legit_sk_substrings() {
        assert_eq!(
            sanitize_text("task-1, disk-usage, flask-app", 1024),
            "task-1, disk-usage, flask-app"
        );
    }

    #[test]
    fn sanitize_text_keeps_sk_prefix_without_long_tail() {
        assert_eq!(sanitize_text("sk-short stays", 1024), "sk-short stays");
        assert_eq!(
            sanitize_text("edge sk-1234567 stays", 1024),
            "edge sk-1234567 stays"
        );
    }

    #[test]
    fn method_enum_maps_to_exact_wire_vocabulary() {
        let wires: Vec<&str> = CONTROL_PLANE_METHOD_VOCABULARY
            .iter()
            .map(|(wire, method)| {
                assert_eq!(*wire, method.as_wire());
                *wire
            })
            .collect();
        assert_eq!(
            wires.len(),
            CONTROL_PLANE_METHOD_COUNT,
            "control-plane method vocabulary count mismatch"
        );
        assert!(wires.contains(&"turn.start_mock"));
        assert!(wires.contains(&"model.turn.start"));
        assert!(wires.contains(&"model.managed.attach"));
        assert!(wires.contains(&"model.managed.detach"));
        assert!(wires.contains(&"knowledge.turn.preview"));
        assert!(wires.contains(&"knowledge.turn.decide"));
        let review_wires: Vec<&str> = wires
            .iter()
            .copied()
            .filter(|wire| wire.starts_with("knowledge.review."))
            .collect();
        assert_eq!(
            review_wires,
            vec![
                "knowledge.review.list",
                "knowledge.review.get",
                "knowledge.review.snapshot",
                "knowledge.review.refresh",
                "knowledge.review.decision.create",
            ]
        );
        assert_eq!(
            ControlPlaneMethod::KnowledgeReviewList.timeout(),
            REQUEST_TIMEOUT
        );
        assert_eq!(
            ControlPlaneMethod::KnowledgeReviewGet.timeout(),
            REQUEST_TIMEOUT
        );
        assert_eq!(
            ControlPlaneMethod::KnowledgeReviewDecisionCreate.timeout(),
            Duration::from_secs(5)
        );
        assert_eq!(
            ControlPlaneMethod::ModelManagedAttach.timeout(),
            Duration::from_secs(300)
        );
        assert_eq!(
            ControlPlaneMethod::ModelManagedDetach.timeout(),
            Duration::from_secs(2)
        );
        assert!(!wires.contains(&"turn.start"));
        assert!(!wires.iter().any(|wire| wire.contains("register")));
        assert!(!wires.iter().any(|wire| wire.contains("publish")));
        assert!(!wires.iter().any(|wire| wire.contains("write")));
    }

    #[test]
    #[should_panic(expected = "control-plane method vocabulary count mismatch")]
    fn method_vocabulary_count_mismatch_fails_clearly() {
        validate_control_plane_method_count(CONTROL_PLANE_METHOD_COUNT - 1);
    }

    #[test]
    fn tool_call_method_maps_wire_and_timeout() {
        assert_eq!(ControlPlaneMethod::ToolCall.as_wire(), "tool.call");
        assert_eq!(
            ControlPlaneMethod::ToolCall.timeout(),
            Duration::from_secs(5)
        );
        assert!(CONTROL_PLANE_METHOD_VOCABULARY
            .iter()
            .any(|(wire, method)| *wire == "tool.call" && *method == ControlPlaneMethod::ToolCall));
    }

    #[test]
    fn build_tool_call_request_builds_exact_payloads() {
        let input = json!({"path": "notes.txt"});
        let (method, payload) = build_tool_call_request(
            "files.read",
            &input,
            "/workspace",
            "digest",
            "session-1",
            None,
        )
        .unwrap();
        assert_eq!(method, ControlPlaneMethod::ToolCall);
        assert_eq!(
            payload,
            json!({
                "tool": "files.read",
                "input": {"path": "notes.txt"},
                "workspace": "/workspace",
                "workspace_digest": "digest",
                "session": "session-1",
            })
        );
        assert!(validate_payload_for_method(method, &payload).is_ok());

        let (grant_method, grant_payload) = build_tool_call_request(
            "files.write",
            &input,
            "/workspace",
            "digest",
            "session-1",
            Some("grant-abc"),
        )
        .unwrap();
        assert_eq!(grant_method, ControlPlaneMethod::ToolCall);
        assert_eq!(
            grant_payload,
            json!({
                "tool": "files.write",
                "input": {"path": "notes.txt"},
                "workspace": "/workspace",
                "workspace_digest": "digest",
                "session": "session-1",
                "grant_id": "grant-abc",
            })
        );
        assert!(validate_payload_for_method(grant_method, &grant_payload).is_ok());
    }

    #[test]
    fn tool_call_payload_validation_rejects_extras_missing_and_blank() {
        let valid = json!({
            "tool": "files.read",
            "input": {},
            "workspace": "/w",
            "workspace_digest": "d",
            "session": "s",
        });
        assert!(validate_payload_for_method(ControlPlaneMethod::ToolCall, &valid).is_ok());

        let mut extra = valid.as_object().unwrap().clone();
        extra.insert("surprise".to_owned(), json!(true));
        assert!(
            validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(extra))
                .is_err()
        );

        let mut missing = valid.as_object().unwrap().clone();
        missing.remove("workspace_digest");
        assert!(
            validate_payload_for_method(ControlPlaneMethod::ToolCall, &Value::Object(missing))
                .is_err()
        );

        let mut blank_tool = valid.as_object().unwrap().clone();
        blank_tool.insert("tool".to_owned(), json!(""));
        assert!(validate_payload_for_method(
            ControlPlaneMethod::ToolCall,
            &Value::Object(blank_tool)
        )
        .is_err());

        let mut blank_grant = valid.as_object().unwrap().clone();
        blank_grant.insert("grant_id".to_owned(), json!(""));
        assert!(validate_payload_for_method(
            ControlPlaneMethod::ToolCall,
            &Value::Object(blank_grant)
        )
        .is_err());

        assert!(validate_payload_for_method(ControlPlaneMethod::ToolCall, &json!([])).is_err());
    }

    #[test]
    fn knowledge_review_request_helpers_build_exact_forwarding_payloads() {
        let identity = format!("kreview:{}", "a".repeat(64));
        let proposal_id = format!("kprop:{}", "b".repeat(64));
        let change_identity = format!("kchange:{}", "c".repeat(64));
        let revision = format!("sha256:{}", "d".repeat(64));
        let (list_method, list_payload) = build_knowledge_review_list_request(7, 25).unwrap();
        assert_eq!(list_method, ControlPlaneMethod::KnowledgeReviewList);
        assert_eq!(list_payload, json!({"offset":7,"limit":25}));
        assert!(validate_payload_for_method(list_method, &list_payload).is_ok());

        let (get_method, get_payload) = build_knowledge_review_get_request(&identity).unwrap();
        assert_eq!(get_method, ControlPlaneMethod::KnowledgeReviewGet);
        assert_eq!(get_payload, json!({"review_artifact_identity":identity}));
        assert!(validate_payload_for_method(get_method, &get_payload).is_ok());

        for method in [
            ControlPlaneMethod::KnowledgeReviewSnapshot,
            ControlPlaneMethod::KnowledgeReviewRefresh,
        ] {
            assert!(validate_payload_for_method(method, &json!({})).is_ok());
            assert!(validate_payload_for_method(method, &json!({"extra": true})).is_err());
        }

        let (decision_method, decision_payload) = build_knowledge_review_decision_create_request(
            KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
            &proposal_id,
            &identity,
            Some(&change_identity),
            &revision,
            "REQUEST_CHANGES",
            "Please provide stronger evidence.",
            "local-user",
            "Local user",
            KNOWLEDGE_REVIEW_ACTOR_SOURCE,
        )
        .unwrap();
        assert_eq!(
            decision_method,
            ControlPlaneMethod::KnowledgeReviewDecisionCreate
        );
        assert_eq!(
            decision_payload,
            json!({
                "review_contract_version": KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
                "proposal_id": proposal_id,
                "review_artifact_identity": identity,
                "change_identity": change_identity,
                "observed_vault_revision": revision,
                "decision": "REQUEST_CHANGES",
                "comment": "Please provide stronger evidence.",
                "actor_identifier": "local-user",
                "actor_display_name": "Local user",
                "actor_source": KNOWLEDGE_REVIEW_ACTOR_SOURCE,
            })
        );
        assert!(validate_payload_for_method(decision_method, &decision_payload).is_ok());
    }

    #[test]
    fn knowledge_review_payload_validation_rejects_extras_limits_and_bad_identity() {
        assert!(build_knowledge_review_list_request(0, 1).is_ok());
        assert!(build_knowledge_review_list_request(MAX_KNOWLEDGE_REVIEW_OFFSET, 50).is_ok());
        assert!(build_knowledge_review_list_request(MAX_KNOWLEDGE_REVIEW_OFFSET + 1, 1).is_err());
        assert!(build_knowledge_review_list_request(0, 0).is_err());
        assert!(build_knowledge_review_list_request(0, MAX_KNOWLEDGE_REVIEW_LIMIT + 1).is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::KnowledgeReviewList,
            &json!({"offset":0,"limit":10,"extra":true})
        )
        .is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::KnowledgeReviewList,
            &json!({"offset":0,"limit":"10"})
        )
        .is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::KnowledgeReviewList,
            &json!({"offset":0})
        )
        .is_err());

        let valid = format!("kreview:{}", "0123456789abcdef".repeat(4));
        assert!(ensure_review_artifact_identity(&valid).is_ok());
        assert!(ensure_review_artifact_identity(&valid.to_ascii_uppercase()).is_err());
        assert!(ensure_review_artifact_identity("kreview:abc").is_err());
        assert!(ensure_review_artifact_identity("../kreview:bad").is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::KnowledgeReviewGet,
            &json!({"review_artifact_identity":valid,"extra":true})
        )
        .is_err());
    }

    #[test]
    fn knowledge_review_decision_payload_is_exact_bounded_and_deny_by_default() {
        let review_id = format!("kreview:{}", "a".repeat(64));
        let proposal_id = format!("kprop:{}", "b".repeat(64));
        let change_identity = format!("kchange:{}", "c".repeat(64));
        let revision = format!("sha256:{}", "d".repeat(64));

        let build = |decision: &str, change: Option<&str>, comment: &str| {
            build_knowledge_review_decision_create_request(
                KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
                &proposal_id,
                &review_id,
                change,
                &revision,
                decision,
                comment,
                "local-user",
                "Local user",
                KNOWLEDGE_REVIEW_ACTOR_SOURCE,
            )
        };
        assert!(build("APPROVE", Some(&change_identity), "").is_ok());
        assert!(build("APPROVE", None, "").is_ok());
        assert!(build("REQUEST_CHANGES", Some(&change_identity), "   ").is_err());
        assert!(build("REJECT", None, "").is_ok());
        assert!(build("AUTO_APPROVE", Some(&change_identity), "").is_err());
        assert!(build("REJECT", None, &"x".repeat(MAX_REVIEW_COMMENT_CHARS + 1)).is_err());
        assert!(build("REJECT", None, &"😀".repeat(1_025)).is_err());

        let (_, valid_payload) = build("REJECT", None, "").unwrap();
        let mut with_extra = valid_payload.clone();
        with_extra
            .as_object_mut()
            .unwrap()
            .insert("write_vault".into(), Value::Bool(true));
        assert!(validate_payload_for_method(
            ControlPlaneMethod::KnowledgeReviewDecisionCreate,
            &with_extra
        )
        .is_err());
    }

    #[test]
    fn knowledge_review_response_guard_enforces_one_megabyte_limit() {
        assert!(ensure_knowledge_review_response_bound(&json!({"items":[]})).is_ok());
        let empty_envelope_bytes = serde_json::to_vec(&json!({"payload":""})).unwrap().len();
        let at_limit = json!({
            "payload": "x".repeat(MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES - empty_envelope_bytes)
        });
        assert_eq!(
            serde_json::to_vec(&at_limit).unwrap().len(),
            MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES
        );
        assert!(ensure_knowledge_review_response_bound(&at_limit).is_ok());

        let over_limit = json!({
            "payload": "x".repeat(
                MAX_KNOWLEDGE_REVIEW_RESPONSE_JSON_BYTES - empty_envelope_bytes + 1
            )
        });
        assert!(ensure_knowledge_review_response_bound(&over_limit).is_err());
    }

    #[test]
    fn knowledge_review_commands_permissions_and_capability_are_static_and_narrow() {
        let lib_source = include_str!("lib.rs");
        let permissions = include_str!("../permissions/knowledge-review-command-center.toml");
        let capability = include_str!("../capabilities/main.json");

        for command in [
            "knowledge_review_list",
            "knowledge_review_get",
            "knowledge_review_snapshot",
            "knowledge_review_refresh",
            "knowledge_review_decision_create",
        ] {
            assert_eq!(lib_source.matches(command).count(), 2);
        }
        for permission in [
            "allow-knowledge-review-list",
            "allow-knowledge-review-get",
            "allow-knowledge-review-snapshot",
            "allow-knowledge-review-refresh",
            "allow-knowledge-review-decision-create",
        ] {
            assert_eq!(capability.matches(permission).count(), 1);
        }
        for command in [
            "knowledge_review_snapshot",
            "knowledge_review_refresh",
            "knowledge_review_decision_create",
        ] {
            assert_eq!(permissions.matches(&format!("\"{command}\"")).count(), 1);
        }
        assert!(permissions.contains("bounded in-memory human review decision artifact"));
        assert!(!permissions.contains('*'));
        assert!(!capability.contains('*'));
        for source in [lib_source, permissions, capability] {
            assert!(!source.contains("knowledge_review_register"));
            assert!(!source.contains("knowledge_review_raw"));
            assert!(!source.contains("knowledge_review_publish"));
            assert!(!source.contains("knowledge_review_write"));
        }
    }

    #[test]
    fn registry_enforces_size_and_duplicate_ids() {
        let mut registry = RequestRegistry::default();
        assert!(registry.insert("deskcp-0000000001".into(), None).is_ok());
        assert!(registry.insert("deskcp-0000000001".into(), None).is_err());
        for index in 2..=MAX_IN_FLIGHT_REQUESTS {
            registry
                .insert(format!("deskcp-{index:010}"), None)
                .unwrap();
        }
        assert!(registry.insert("deskcp-9999999999".into(), None).is_err());
    }

    #[test]
    fn pending_terminal_wakes_and_records_result() {
        let pending = PendingRequest::new("deskcp-0000000001".into(), None);
        finish_pending(&pending, Ok(json!({"state":"COMPLETED"})));
        let mut guard = pending.state.lock().unwrap();
        assert!(guard.terminal_seen || guard.terminal.is_some());
        assert_eq!(
            guard.terminal.take().unwrap().unwrap()["state"],
            "COMPLETED"
        );
    }

    #[test]
    fn registry_failure_drains_before_pending_state_is_finished() {
        let mut registry = RequestRegistry::default();
        let pending = registry.insert("deskcp-0000000001".into(), None).unwrap();
        let drained = registry.drain_all();
        assert!(registry.entries.is_empty());
        assert_eq!(drained.len(), 1);

        finish_pending(
            &drained[0],
            Err(BridgeError::new("sidecar_stopped", "sidecar stopped")),
        );
        let mut state = pending.state.lock().unwrap();
        let error = state.terminal.take().unwrap().unwrap_err();
        assert_eq!(error.code, "sidecar_stopped");
    }

    #[test]
    fn command_input_validation_rejects_bad_values() {
        assert!(ensure_id("turn_id", "abcdefabcdefabcdefabcdef").is_ok());
        assert!(ensure_id("turn_id", "../bad").is_err());
        assert!(ensure_runtime_instance_id("abcdefabcdefabcdefabcdefabcdefab").is_ok());
        assert!(ensure_runtime_instance_id("abcdefabcdefabcdefabcdef").is_err());
        assert!(ensure_runtime_instance_id("ABCDEFABCDEFABCDEFABCDEFABCDEFAB").is_err());
        assert!(ensure_len(
            "prompt",
            &"x".repeat(MAX_PROMPT_CHARS + 1),
            MAX_PROMPT_CHARS
        )
        .is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::TurnCancel,
            &json!({"turn_id":"abcdefabcdefabcdefabcdef","reason":"user_requested"})
        )
        .is_ok());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::TurnCancel,
            &json!({"turn_id":"abcdefabcdefabcdefabcdef","reason":"user_requested","extra":true})
        )
        .is_err());
        assert!(ensure_model_port(1024).is_ok());
        assert!(ensure_model_port(1023).is_err());
        assert!(ensure_provider("openai-compatible-local").is_ok());
        assert!(ensure_provider("https://example.test").is_err());
        assert!(ensure_harness("minimal").is_ok());
        assert!(ensure_harness("dynamic").is_err());
    }

    #[test]
    fn event_validation_rejects_unknown_method_and_bad_id() {
        assert!(allowed_event_method("item.delta"));
        assert!(allowed_event_method("model.output.delta"));
        assert!(!allowed_event_method("provider.ready"));
        let event = json!({
            "method":"item.delta",
            "reply_to":"deskcp-0000000001",
            "sequence":0,
            "payload":{
                "control_plane_version":"v6.84.4",
                "session_id":"abcdefabcdefabcdefabcdef",
                "thread_id":null,
                "turn_id":null,
                "item_id":null,
                "state":"STREAMING",
                "kind":"assistant_message",
                "text":"hello",
                "metadata":{}
            }
        });
        assert!(ui_event_from_envelope(&event).is_ok());
    }

    fn model_identity() -> ModelRequestIdentity {
        ModelRequestIdentity {
            request_id: "0123456789abcdef01234567".into(),
            chat_session_id: "chat_session_1".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_000,
            max_tokens: 128,
            binding_fingerprint: "a".repeat(64),
        }
    }

    #[test]
    fn reservation_check_releases_request_registry_before_writer_wait() {
        let identity = model_identity();
        let request_id = identity.request_id.clone();
        let registry = Arc::new(Mutex::new(ModelRequestRegistry::default()));
        registry
            .lock()
            .unwrap()
            .insert(identity, Vec::new())
            .unwrap();

        let worker_registry = Arc::clone(&registry);
        let (checked_tx, checked_rx) = std::sync::mpsc::channel();
        let (release_tx, release_rx) = std::sync::mpsc::channel();
        let worker = thread::spawn(move || {
            assert!(model_request_reservation_exists(
                &worker_registry,
                &request_id
            ));
            checked_tx.send(()).unwrap();
            release_rx.recv().unwrap();
        });

        checked_rx.recv_timeout(Duration::from_secs(1)).unwrap();
        assert!(registry.try_lock().is_ok());
        release_tx.send(()).unwrap();
        worker.join().unwrap();
    }

    #[test]
    fn model_turn_wire_digest_covers_assistant_context() {
        let identity = model_identity();
        let neutral =
            AssistantContext::trusted("ru", false, None, vec![]).expect("trusted context");
        let baseline =
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral));
        assert_eq!(
            baseline,
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral)),
            "the digest must be stable for identical inputs"
        );

        let mut with_tools = neutral.clone();
        with_tools.capabilities.tools = vec!["files.read".to_string()];
        assert_ne!(
            baseline,
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &with_tools)),
            "a capability/tool grant change must change the wire digest"
        );

        let mut with_filesystem = neutral.clone();
        with_filesystem.capabilities.filesystem = true;
        assert_ne!(
            baseline,
            model_turn_wire_digest(&model_turn_wire_payload(
                &identity,
                "prompt",
                &with_filesystem
            )),
            "a capability flag change must change the wire digest"
        );

        let mut with_locale = neutral.clone();
        with_locale.conversation.locale = "en".to_string();
        assert_ne!(
            baseline,
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &with_locale)),
            "a conversation context change must change the wire digest"
        );

        assert_ne!(
            baseline,
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "other", &neutral)),
            "a prompt change must change the wire digest"
        );
    }

    #[test]
    fn model_turn_dispatch_requires_the_reserved_wire_digest() {
        let identity = model_identity();
        let request_id = identity.request_id.clone();
        let neutral =
            AssistantContext::trusted("ru", false, None, vec![]).expect("trusted context");
        let reserved =
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &neutral));
        let registry = Mutex::new(ModelRequestRegistry::default());

        // Missing reservation.
        assert_eq!(
            model_request_reservation_authorizes_wire(&registry, &request_id, &reserved)
                .unwrap_err()
                .code,
            "request_not_found"
        );

        registry
            .lock()
            .unwrap()
            .insert(identity.clone(), Vec::new())
            .unwrap();

        // Reserved but unbound: fail closed.
        assert_eq!(
            model_request_reservation_authorizes_wire(&registry, &request_id, &reserved)
                .unwrap_err()
                .code,
            "protocol_mismatch"
        );

        registry
            .lock()
            .unwrap()
            .bind_reserved_wire_digest(&request_id, reserved)
            .expect("bind reserved wire digest");
        assert!(
            model_request_reservation_authorizes_wire(&registry, &request_id, &reserved).is_ok()
        );

        // A payload whose assistant_context escalates capabilities cannot dispatch
        // on a reservation authorized for the capability-neutral context.
        let mut escalated = neutral.clone();
        escalated.capabilities.tools = vec!["files.read".to_string()];
        let escalated_digest =
            model_turn_wire_digest(&model_turn_wire_payload(&identity, "prompt", &escalated));
        assert_eq!(
            model_request_reservation_authorizes_wire(&registry, &request_id, &escalated_digest)
                .unwrap_err()
                .code,
            "protocol_mismatch"
        );

        // Rebinding an already bound reservation is refused.
        assert_eq!(
            registry
                .lock()
                .unwrap()
                .bind_reserved_wire_digest(&request_id, escalated_digest)
                .unwrap_err()
                .code,
            "protocol_mismatch"
        );
    }

    fn model_event(
        identity: &ModelRequestIdentity,
        method: &str,
        sequence: u64,
        state: &str,
        text: Option<&str>,
    ) -> UiControlPlaneEvent {
        let model_called = matches!(
            method,
            "model.turn.started" | "model.output.delta" | "model.turn.completed"
        ) || sequence > 0;
        let generated_bytes = text.map(str::len).unwrap_or_else(|| {
            if sequence > 0 {
                MAX_MODEL_EVENT_TEXT_PER_REQUEST
            } else {
                0
            }
        });
        let error = matches!(method, "model.turn.failed" | "model.turn.timed_out").then(|| {
            json!({
                "code": "model_request_failed",
                "message": "local model request failed",
                "retryable": true,
            })
        });
        let mut metadata = json!({
            "provider_id": "managed-llama-cpp",
            "harness_id": "minimal",
            "request_id": identity.request_id,
            "turn_id": identity.request_id,
            "chat_session_id": identity.chat_session_id,
            "model_id": identity.model_id,
            "submitted_at_unix_ms": identity.submitted_at_unix_ms,
            "max_tokens": identity.max_tokens,
            "binding_fingerprint": identity.binding_fingerprint,
            "model_called": model_called,
            "tools_executed": 0,
            "persistence": false,
            "generated_bytes": generated_bytes,
        });
        if let Some(error) = error {
            metadata["error"] = error;
        }
        UiControlPlaneEvent {
            method: method.into(),
            sequence,
            reply_to: identity.request_id.clone(),
            request_id: Some(identity.request_id.clone()),
            chat_session_id: Some(identity.chat_session_id.clone()),
            model_id: Some(identity.model_id.clone()),
            control_plane_version: DESKTOP_STATUS_BRIDGE_VERSION.into(),
            session_id: None,
            thread_id: None,
            turn_id: Some(identity.request_id.clone()),
            item_id: None,
            state: state.into(),
            kind: None,
            text: text.map(str::to_owned),
            metadata,
        }
    }

    #[test]
    fn typed_model_command_payloads_are_exact() {
        let identity = model_identity();
        let payload = json!({
            "request_id": identity.request_id,
            "chat_session_id": identity.chat_session_id,
            "model_id": identity.model_id,
            "submitted_at_unix_ms": identity.submitted_at_unix_ms,
            "max_tokens": identity.max_tokens,
            "prompt": "hello",
            "assistant_context": AssistantContext::trusted("ru", false, None, vec![]).unwrap(),
            "binding_fingerprint": identity.binding_fingerprint,
        });
        assert!(validate_payload_for_method(ControlPlaneMethod::ModelTurnStart, &payload).is_ok());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::ModelTurnStart,
            &json!({"prompt":"hello","binding_fingerprint":"a".repeat(64)})
        )
        .is_err());
        assert!(validate_payload_for_method(
            ControlPlaneMethod::ModelTurnCancel,
            &model_cancel_payload("0123456789abcdef01234567")
        )
        .is_ok());
        assert_eq!(
            model_cancel_payload("0123456789abcdef01234567"),
            json!({"request_id":"0123456789abcdef01234567"})
        );
        assert_eq!(
            model_cancel_request_envelope("deskcp-0000000001", "0123456789abcdef01234567"),
            json!({
                "protocol": ipc::IPC_PROTOCOL,
                "version": ipc::IPC_PROTOCOL_VERSION,
                "type": "request",
                "id": "deskcp-0000000001",
                "method": "model.turn.cancel",
                "run_id": null,
                "sequence": 0,
                "reply_to": null,
                "payload": {"request_id":"0123456789abcdef01234567"},
            })
        );
        assert!(validate_payload_for_method(
            ControlPlaneMethod::ModelTurnCancel,
            &json!({"turn_id":"0123456789abcdef01234567"})
        )
        .is_err());
    }

    #[test]
    fn model_acceptance_requires_all_immutable_fields() {
        let identity = model_identity();
        let response = json!({
            "request_id": identity.request_id,
            "turn_id": identity.request_id,
            "chat_session_id": identity.chat_session_id,
            "model_id": identity.model_id,
            "submitted_at_unix_ms": identity.submitted_at_unix_ms,
            "max_tokens": identity.max_tokens,
            "binding_fingerprint": identity.binding_fingerprint,
            "state": "Accepted",
            "provider_id": "managed-llama-cpp",
            "harness_id": "minimal",
            "model_called": false,
            "tools_executed": 0,
            "persistence": false,
        });
        assert!(validate_model_acceptance(&response, &identity).is_ok());
        let mut wrong = response;
        wrong["model_id"] = json!("foreign-model");
        assert!(validate_model_acceptance(&wrong, &identity).is_err());
        let mut extra = project_model_acceptance(&identity, "managed-llama-cpp", "minimal");
        extra["untrusted"] = json!("cross-webview");
        assert!(validate_model_acceptance(&extra, &identity).is_err());
    }

    #[test]
    fn knowledge_model_receipts_cover_include_and_reject_dispatch() {
        let hash = format!("sha256:{}", "a".repeat(64));
        let include_payload = json!({
            "turn_id": "0123456789abcdef01234567",
            "injection_id": "kinj:approved-1",
            "expected_preview_hash": hash,
            "action": "INCLUDE_AND_SEND",
        });
        let include =
            pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &include_payload)
                .unwrap();
        assert!(include.include_knowledge);
        let include_receipt = json!({
            "injection_id": include.injection_id,
            "turn_id": include.turn_id,
            "action": "INCLUDE_AND_SEND",
            "preview_hash": include.preview_hash,
            "state": "DISPATCHING",
            "decision_source": "USER_APPROVAL",
            "model_turn_id": "fedcba9876543210fedcba98",
            "model_dispatched": true,
            "knowledge_included": true,
            "duplicate": false,
        });
        assert_eq!(
            validate_knowledge_model_receipt(&include_receipt, &include).unwrap(),
            "fedcba9876543210fedcba98"
        );

        let reject_payload = json!({
            "turn_id": "0123456789abcdef01234567",
            "injection_id": "kinj:approved-1",
            "expected_preview_hash": format!("sha256:{}", "a".repeat(64)),
            "action": "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
        });
        let reject =
            pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &reject_payload)
                .unwrap();
        assert!(!reject.include_knowledge);
        let mut reject_receipt = include_receipt;
        reject_receipt["action"] = json!("REJECT_AND_SEND_WITHOUT_KNOWLEDGE");
        reject_receipt["state"] = json!("REJECTED");
        reject_receipt["knowledge_included"] = json!(false);
        assert!(validate_knowledge_model_receipt(&reject_receipt, &reject).is_ok());
        let mut cancel_payload = reject_payload;
        cancel_payload["action"] = json!("CANCEL");
        assert!(
            pending_knowledge_model(ControlPlaneMethod::KnowledgeTurnDecide, &cancel_payload)
                .is_none()
        );
    }

    #[test]
    fn assistant_context_is_trusted_typed_and_fail_closed() {
        let russian = AssistantContext::trusted("ru", false, None, vec![]).unwrap();
        let english = AssistantContext::trusted("en", false, None, vec![]).unwrap();
        let with_files = AssistantContext::trusted("ru", true, None, vec![]).unwrap();
        assert_eq!(russian.application.name, "LocalComet");
        assert_eq!(russian.application.mode, "local_offline_desktop_assistant");
        assert_eq!(russian.application.version, DESKTOP_STATUS_BRIDGE_VERSION);
        assert_eq!(russian.conversation.locale, "ru");
        assert_eq!(english.conversation.locale, "en");
        assert!(!russian.conversation.project_context_available);
        assert!(!russian.conversation.selected_files_context_available);
        assert!(with_files.conversation.selected_files_context_available);
        assert!(!with_files.capabilities.filesystem);
        assert!(russian.capabilities.local_chat);
        assert!(russian.capabilities.local_model_inference);
        assert!(!russian.capabilities.internet);
        assert!(!russian.capabilities.email);
        assert!(!russian.capabilities.browser);
        // internet toggle is opt-in — when granted, both internet and browser reflect it
        let with_internet = AssistantContext::trusted(
            "ru",
            false,
            Some(&AgentPermissions {
                files: false,
                shell: false,
                tools: false,
                computer_use: false,
                internet: true,
            }),
            vec![],
        )
        .unwrap();
        assert!(with_internet.capabilities.internet);
        assert!(with_internet.capabilities.browser);
        assert!(with_internet
            .capabilities
            .tools
            .iter()
            .any(|t| t == "web.search"));
        assert!(with_internet
            .capabilities
            .tools
            .iter()
            .any(|t| t == "web.fetch"));
        assert!(!russian.capabilities.filesystem);
        assert!(!russian.capabilities.vault);
        assert!(!russian.capabilities.computer_use);
        assert!(!russian.capabilities.shell);
        assert!(russian.capabilities.tools.is_empty());
        assert!(AssistantContext::trusted("fr", false, None, vec![]).is_err());

        let serialized = serde_json::to_string(&russian).unwrap();
        assert!(!serialized.contains("C:\\"));
        assert!(!serialized.contains("/home/"));
        assert!(!serialized.to_ascii_lowercase().contains("secret"));
    }

    #[test]
    fn removing_knowledge_admission_wakes_its_watchdog_immediately() {
        let context = PendingKnowledgeModel {
            turn_id: "0123456789abcdef01234567".into(),
            injection_id: "kinj:approved-1".into(),
            preview_hash: format!("sha256:{}", "a".repeat(64)),
            include_knowledge: true,
        };
        let admission = KnowledgeAdmission::new(context);
        let watchdog = Arc::clone(&admission.watchdog);
        let mut admissions = HashMap::new();
        admissions.insert("fedcba9876543210fedcba98".to_owned(), admission);
        let (finished_tx, finished_rx) = std::sync::mpsc::channel();
        let waiter = thread::spawn(move || {
            finished_tx
                .send(watchdog.wait_for_timeout(Duration::from_secs(5)))
                .unwrap();
        });

        let removed = admissions.remove("fedcba9876543210fedcba98");
        drop(removed);
        assert!(!finished_rx
            .recv_timeout(Duration::from_millis(500))
            .expect("removed admission should wake watchdog"));
        waiter.join().unwrap();
    }

    #[test]
    fn model_event_metadata_is_transactional_exact_and_projected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let mut invalid = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        invalid.metadata["untrusted"] = json!({"raw": "sidecar"});
        assert!(
            validate_and_record_model_event(&mut entry, &invalid, "model.turn.started", 0).is_err()
        );
        assert!(entry.provider_id.is_none());
        assert!(!entry.started_seen);
        assert_eq!(entry.next_sequence, 0);

        let valid = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &valid, "model.turn.started", 0).unwrap();
        let projected = project_model_event_metadata(&valid).unwrap();
        assert_eq!(projected["provider_id"], "managed-llama-cpp");
        assert_eq!(projected["harness_id"], "minimal");
        assert!(projected.get("request_id").is_none());
        assert!(projected.get("untrusted").is_none());
    }

    #[test]
    fn projected_tool_event_preserves_validated_tool_calls() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".into()]);
        let event = structured_tool_event(
            &identity,
            "model.tool.request",
            vec![("files.read", valid_tool_arguments_json("files.read"))],
        );
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0).unwrap();
        let projected = project_model_event_metadata(&event).unwrap();
        assert_eq!(projected["tool_calls"], event.metadata["tool_calls"]);
    }

    #[test]
    fn knowledge_audit_is_allowed_only_on_started_event_and_projected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        entry.accepted = true;
        entry.knowledge_model = true;
        entry.knowledge_included = true;
        entry.knowledge_injection_id = Some("kinj:approved-1".into());
        let mut started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        let hash = format!("sha256:{}", "b".repeat(64));
        let metadata = started.metadata.as_object_mut().unwrap();
        metadata.insert("knowledge_injection_id".into(), json!("kinj:approved-1"));
        metadata.insert("knowledge_request_id".into(), json!("kreq:request-1"));
        metadata.insert(
            "knowledge_bundle_id".into(),
            json!(format!("kb:{}", "c".repeat(64))),
        );
        for key in [
            "knowledge_vault_revision",
            "knowledge_preview_hash",
            "knowledge_context_sha256",
        ] {
            metadata.insert(key.into(), json!(hash));
        }
        metadata.insert("knowledge_source_count".into(), json!(1));
        metadata.insert(
            "knowledge_serialization_format".into(),
            json!("localcomet.knowledge-context.v1"),
        );
        metadata.insert("knowledge_decision_source".into(), json!("USER_APPROVAL"));
        metadata.insert("knowledge_synthetic_message".into(), json!(true));
        metadata.insert("knowledge_context_reference_data".into(), json!(true));
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        let projected = project_model_event_metadata(&started).unwrap();
        assert_eq!(projected["knowledge_injection_id"], "kinj:approved-1");

        let delta = model_event(&identity, "model.output.delta", 1, "Streaming", Some("x"));
        validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap();
        let projected_delta = project_model_event_metadata(&delta).unwrap();
        assert!(projected_delta.get("knowledge_injection_id").is_none());
    }

    #[test]
    fn buffered_terminal_is_owned_when_registry_cleanup_wins() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let terminal = model_event(&identity, "model.turn.cancelled", 0, "Cancelled", None);
        validate_and_record_model_event(&mut entry, &terminal, "model.turn.cancelled", 0).unwrap();
        entry.buffered_events.push(terminal);
        let owned = take_authoritative_buffered_terminal(&mut entry).unwrap();
        assert_eq!(owned.len(), 1);
        assert_eq!(owned[0].method, "model.turn.cancelled");
        assert!(entry.buffered_events.is_empty());
    }

    #[test]
    fn synthetic_terminal_matches_frontend_metadata_shape_and_metrics() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity, Vec::new());
        entry.provider_id = Some("managed-llama-cpp".into());
        entry.harness_id = Some("native-localcomet".into());
        entry.model_called = true;
        entry.generated_bytes = 42;
        let event = model_terminal_event(
            &entry,
            "model.turn.timed_out",
            "TimedOut",
            "request_timed_out",
            "untrusted detail",
        );
        assert_eq!(event.metadata["provider_id"], "managed-llama-cpp");
        assert_eq!(event.metadata["harness_id"], "native-localcomet");
        assert_eq!(event.metadata["model_called"], true);
        assert_eq!(event.metadata["generated_bytes"], 42);
        assert_eq!(event.metadata["error"]["code"], "request_timed_out");
        assert_eq!(
            event.metadata["error"]["message"],
            "model request timed out"
        );
    }

    #[test]
    fn model_event_sequence_is_strict_and_terminal_is_unique() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        entry.accepted = true;
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        assert!(
            validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap()
        );
        let delta = model_event(
            &identity,
            "model.output.delta",
            1,
            "Streaming",
            Some("hello"),
        );
        assert!(
            validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap()
        );
        let completed = model_event(&identity, "model.turn.completed", 2, "Completed", None);
        assert!(
            validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 2)
                .unwrap()
        );
        assert!(
            validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 2)
                .is_err()
        );
        let late = model_event(
            &identity,
            "model.output.delta",
            3,
            "Streaming",
            Some("late"),
        );
        assert!(
            validate_and_record_model_event(&mut entry, &late, "model.output.delta", 3).is_err()
        );
    }

    #[test]
    fn acceptance_release_gate_preserves_buffered_event_order() {
        let identity = model_identity();
        let mut registry = ModelRequestRegistry::default();
        let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
            assert!(
                validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap()
            );
            assert!(model_event_is_gated(entry));
            entry.buffered_events.push(started);
            entry.accepted = true;
            assert!(begin_model_event_release(entry));
        }

        let first_batch = registry
            .take_release_batch(&identity.request_id)
            .expect("accepted event batch");
        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            let delta = model_event(
                &identity,
                "model.output.delta",
                1,
                "Streaming",
                Some("next"),
            );
            assert!(
                validate_and_record_model_event(entry, &delta, "model.output.delta", 1).unwrap()
            );
            assert!(model_event_is_gated(entry));
            entry.buffered_events.push(delta);
        }
        let second_batch = registry
            .take_release_batch(&identity.request_id)
            .expect("event received while releasing");
        assert!(registry.take_release_batch(&identity.request_id).is_none());
        assert!(!model_event_is_gated(
            registry.entries.get(&identity.request_id).unwrap()
        ));

        let sequences: Vec<u64> = first_batch
            .into_iter()
            .chain(second_batch)
            .map(|event| event.sequence)
            .collect();
        assert_eq!(sequences, vec![0, 1]);
    }

    #[test]
    fn synthetic_terminal_waits_behind_an_owned_release_batch() {
        let identity = model_identity();
        let mut registry = ModelRequestRegistry::default();
        let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            entry.accepted = true;
            let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
            validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap();
            entry.buffered_events.push(started);
            assert!(begin_model_event_release(entry));
        }
        let first_batch = registry
            .take_release_batch(&identity.request_id)
            .expect("release owner should take the started event");
        assert!(registry
            .remove_or_queue_synthetic_terminal(
                &identity.request_id,
                "model.turn.timed_out",
                "TimedOut",
                "request_timed_out",
                "model request exceeded the bounded lifetime",
            )
            .is_none());
        assert!(registry.entries.contains_key(&identity.request_id));
        let terminal_batch = registry
            .take_release_batch(&identity.request_id)
            .expect("release owner should take the queued terminal");

        let methods: Vec<_> = first_batch
            .iter()
            .chain(terminal_batch.iter())
            .map(|event| (event.sequence, event.method.as_str()))
            .collect();
        assert_eq!(
            methods,
            vec![(0, "model.turn.started"), (1, "model.turn.timed_out")]
        );
        assert!(registry.entries[&identity.request_id].cancel_after_synthetic_release);
        assert!(registry.take_release_batch(&identity.request_id).is_none());
        assert!(!registry.entries.contains_key(&identity.request_id));
    }

    #[test]
    fn cancellation_reserved_before_acceptance_forces_a_second_cancel() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity, Vec::new());
        entry.cancel_requested_before_acceptance = true;
        entry.cancel_pending = false;

        let (release, needs_recancel) = record_model_acceptance(&mut entry);
        assert!(!release);
        assert!(needs_recancel);
        assert!(entry.cancel_requested_before_acceptance);
        assert!(model_event_is_gated(&entry));

        entry.cancel_pending = true;
        assert!(model_event_is_gated(&entry));
        entry.cancel_pending = false;
        entry.cancel_accepted = true;
        entry.cancel_requested_before_acceptance = false;
        assert!(begin_model_event_release(&mut entry));
    }

    #[test]
    fn cancellation_terminal_before_acceptance_keeps_entry_until_acceptance() {
        let identity = model_identity();
        let mut registry = ModelRequestRegistry::default();
        let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            entry.cancel_pending = true;
            let cancelled = model_event(&identity, "model.turn.cancelled", 0, "Cancelled", None);
            assert!(
                validate_and_record_model_event(entry, &cancelled, "model.turn.cancelled", 0)
                    .unwrap()
            );
            assert!(model_event_is_gated(entry));
            entry.buffered_events.push(cancelled);

            entry.cancel_pending = false;
            entry.cancel_accepted = true;
            assert!(!begin_model_event_release(entry));
        }
        assert!(registry.entries.contains_key(&identity.request_id));

        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            entry.accepted = true;
            assert!(begin_model_event_release(entry));
        }
        let terminal_batch = registry
            .take_release_batch(&identity.request_id)
            .expect("cancel terminal remains buffered until acceptance");
        assert_eq!(terminal_batch.len(), 1);
        assert_eq!(terminal_batch[0].method, "model.turn.cancelled");
        assert!(registry.entries.contains_key(&identity.request_id));
        assert!(registry.take_release_batch(&identity.request_id).is_none());
        assert!(!registry.entries.contains_key(&identity.request_id));
    }

    #[test]
    fn accepted_request_does_not_release_events_during_cancel_round_trip() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        entry.cancel_pending = true;
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        assert!(
            validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap()
        );
        entry.buffered_events.push(started);
        entry.accepted = true;
        assert!(!begin_model_event_release(&mut entry));
        assert_eq!(entry.buffered_events.len(), 1);

        entry.cancel_pending = false;
        assert!(begin_model_event_release(&mut entry));
    }

    #[test]
    fn pre_ack_delta_releases_before_cancelled_terminal() {
        let identity = model_identity();
        let mut registry = ModelRequestRegistry::default();
        let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        {
            let entry = registry.entries.get_mut(&identity.request_id).unwrap();
            entry.accepted = true;
            let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
            validate_and_record_model_event(entry, &started, "model.turn.started", 0).unwrap();
            entry.cancel_pending = true;
            let delta = model_event(
                &identity,
                "model.output.delta",
                1,
                "Streaming",
                Some("raced delta"),
            );
            validate_and_record_model_event(entry, &delta, "model.output.delta", 1).unwrap();
            assert!(model_event_is_gated(entry));
            entry.buffered_events.push(delta);

            entry.cancel_pending = false;
            entry.cancel_accepted = true;
            assert!(begin_model_event_release(entry));
        }
        let batch = registry
            .take_release_batch(&identity.request_id)
            .expect("pre-ack delta batch");
        assert_eq!(batch.len(), 1);
        assert_eq!(batch[0].method, "model.output.delta");
        assert!(registry.take_release_batch(&identity.request_id).is_none());

        let entry = registry.entries.get_mut(&identity.request_id).unwrap();
        let cancelled = model_event(&identity, "model.turn.cancelled", 2, "Cancelled", None);
        assert!(
            validate_and_record_model_event(entry, &cancelled, "model.turn.cancelled", 2).unwrap()
        );
    }

    #[test]
    fn model_event_rejects_foreign_identity_and_out_of_order_sequence() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let out_of_order = model_event(&identity, "model.turn.started", 1, "Streaming", None);
        assert!(validate_and_record_model_event(
            &mut entry,
            &out_of_order,
            "model.turn.started",
            1
        )
        .is_err());
        let mut foreign = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        foreign.request_id = Some("fedcba9876543210fedcba98".into());
        assert!(
            validate_and_record_model_event(&mut entry, &foreign, "model.turn.started", 0).is_err()
        );
        let mut wrong_binding = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        wrong_binding.metadata["binding_fingerprint"] = json!("b".repeat(64));
        assert!(validate_and_record_model_event(
            &mut entry,
            &wrong_binding,
            "model.turn.started",
            0
        )
        .is_err());
    }

    #[test]
    fn model_event_envelope_uses_run_id_fallback_and_typed_top_level_identity() {
        let identity = model_identity();
        let envelope = json!({
            "method": "model.turn.started",
            "sequence": 0,
            "reply_to": null,
            "run_id": identity.request_id,
            "payload": {
                "control_plane_version": DESKTOP_STATUS_BRIDGE_VERSION,
                "request_id": identity.request_id,
                "chat_session_id": identity.chat_session_id,
                "model_id": identity.model_id,
                "session_id": null,
                "thread_id": null,
                "turn_id": identity.request_id,
                "item_id": null,
                "state": "Streaming",
                "kind": null,
                "text": null,
                "metadata": {},
            }
        });
        let event = ui_event_from_envelope(&envelope).expect("typed model event envelope");
        assert_eq!(event.reply_to, identity.request_id);
        assert_eq!(
            event.request_id.as_deref(),
            Some(identity.request_id.as_str())
        );
        assert_eq!(
            event.chat_session_id.as_deref(),
            Some(identity.chat_session_id.as_str())
        );
        assert_eq!(event.model_id.as_deref(), Some(identity.model_id.as_str()));
        assert!(event.session_id.is_none());
    }

    #[test]
    fn accepted_cancellation_rejects_content_and_completion() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        entry.accepted = true;
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        entry.cancel_accepted = true;
        let late = model_event(
            &identity,
            "model.output.delta",
            1,
            "Streaming",
            Some("late"),
        );
        assert!(
            validate_and_record_model_event(&mut entry, &late, "model.output.delta", 1).is_err()
        );
        let completed = model_event(&identity, "model.turn.completed", 1, "Completed", None);
        assert!(
            validate_and_record_model_event(&mut entry, &completed, "model.turn.completed", 1)
                .is_err()
        );
        let failed = model_event(&identity, "model.turn.failed", 1, "Failed", None);
        assert!(
            validate_and_record_model_event(&mut entry, &failed, "model.turn.failed", 1).is_err()
        );
        let timed_out = model_event(&identity, "model.turn.timed_out", 1, "TimedOut", None);
        assert!(
            validate_and_record_model_event(&mut entry, &timed_out, "model.turn.timed_out", 1)
                .is_err()
        );
        let cancelled = model_event(&identity, "model.turn.cancelled", 1, "Cancelled", None);
        assert!(
            validate_and_record_model_event(&mut entry, &cancelled, "model.turn.cancelled", 1)
                .unwrap()
        );
    }

    #[test]
    fn cancel_ack_and_registry_cleanup_are_bounded() {
        let identity = model_identity();
        let active = json!({
            "request_id": identity.request_id,
            "turn_id": identity.request_id,
            "state": "Cancelling",
            "accepted": true,
            "already_terminal": false,
            "worker_alive": true,
        });
        assert_eq!(
            validate_model_cancel_ack(&active, &identity.request_id).unwrap(),
            ModelCancelAcknowledgement {
                accepted: true,
                already_terminal: false
            }
        );
        let mut incoherent = active.clone();
        incoherent["worker_alive"] = json!(false);
        assert!(validate_model_cancel_ack(&incoherent, &identity.request_id).is_err());
        let stopped = json!({
            "request_id": identity.request_id,
            "turn_id": identity.request_id,
            "state": "Cancelled",
            "accepted": true,
            "already_terminal": false,
            "worker_alive": false,
        });
        assert!(validate_model_cancel_ack(&stopped, &identity.request_id).is_ok());
        let mut registry = ModelRequestRegistry::default();
        let _watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        assert_eq!(registry.entries.len(), 1);
        registry.remove(&identity.request_id);
        assert!(registry.entries.is_empty());
        assert_eq!(
            terminal_model_cancel_ack(&identity.request_id),
            json!({
                "request_id": identity.request_id,
                "turn_id": identity.request_id,
                "state": "Cancelled",
                "accepted": false,
                "already_terminal": true,
                "worker_alive": false,
            })
        );
        let terminal = model_terminal_event(
            &ModelRequestEntry::new(identity, Vec::new()),
            "model.turn.failed",
            "Failed",
            "protocol_mismatch",
            "invalid event",
        );
        assert_eq!(terminal.metadata["model_called"], false);
        assert_eq!(terminal.metadata["tools_executed"], 0);
        assert_eq!(terminal.metadata["persistence"], false);
        assert_eq!(terminal.metadata["generated_bytes"], 0);
        assert_eq!(
            terminal.metadata["binding_fingerprint"],
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        );
    }

    #[test]
    fn removing_model_request_wakes_watchdog_without_full_timeout() {
        let identity = model_identity();
        let mut registry = ModelRequestRegistry::default();
        let watchdog = registry.insert(identity.clone(), Vec::new()).unwrap();
        let (finished_tx, finished_rx) = std::sync::mpsc::channel();
        let waiter = thread::spawn(move || {
            let timed_out = watchdog.wait_for_timeout(Duration::from_secs(5));
            finished_tx.send(timed_out).unwrap();
        });

        registry.remove(&identity.request_id);
        assert!(!finished_rx
            .recv_timeout(Duration::from_millis(500))
            .expect("removed request should wake watchdog"));
        waiter.join().unwrap();
    }

    #[test]
    fn empty_model_delta_advances_sequence_and_is_forwarded_for_ordering() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        let empty = model_event(&identity, "model.output.delta", 1, "Streaming", Some(""));
        assert!(
            validate_and_record_model_event(&mut entry, &empty, "model.output.delta", 1).unwrap()
        );
        assert_eq!(entry.next_sequence, 2);
    }

    #[test]
    fn t0_unknown_model_event_method_is_rejected() {
        assert!(!allowed_model_event_method("provider.unknown"));
        assert!(!allowed_model_event_method("model.tool.unknown"));
        assert!(!allowed_model_event_method(""));
    }

    #[test]
    fn t1_model_tool_request_is_allowed_model_event() {
        assert!(allowed_model_event_method("model.tool.request"));
        assert!(allowed_event_method("model.tool.request"));
    }

    #[test]
    fn t2_model_turn_tool_calls_is_allowed_model_event() {
        assert!(allowed_model_event_method("model.turn.tool_calls"));
        assert!(allowed_event_method("model.turn.tool_calls"));
    }

    #[test]
    fn tool_events_reach_specialized_branch_and_are_denied_without_permissive_acceptance() {
        let identity = model_identity();
        for method in ["model.tool.request", "model.turn.tool_calls"] {
            let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
            let event = model_event(&identity, method, 0, "Streaming", None);
            let result = validate_and_record_model_event(&mut entry, &event, method, 0);
            let error = result.expect_err("tool event must be denied before B2");
            assert_ne!(
                error.code, "unsupported_method",
                "{method} must not be unsupported_method"
            );
            assert_eq!(error.code, "protocol_mismatch");
            assert_eq!(entry.next_sequence, 0);
            assert_eq!(entry.event_count, 0);
        }
    }

    #[test]
    fn unknown_method_in_validator_remains_unsupported_method() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, "model.turn.unknown", 0, "Streaming", None);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.unknown", 0)
            .expect_err("unknown method must be rejected");
        assert_eq!(error.code, "unsupported_method");
    }

    #[test]
    fn b2_content_event_remains_valid_when_tools_are_disabled() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        let delta = model_event(
            &identity,
            "model.output.delta",
            1,
            "Streaming",
            Some("hello"),
        );
        assert!(
            validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1).unwrap()
        );
        assert_eq!(entry.next_sequence, 2);
        assert_eq!(entry.event_count, 2);
    }

    #[test]
    fn b2_model_tool_request_is_rejected_when_request_tools_are_disabled() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, "model.tool.request", 0, "Streaming", None);
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("tool event must be rejected when tools are disabled");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(entry.next_sequence, 0, "state must not advance");
        assert_eq!(entry.event_count, 0, "event must not be recorded");
        assert_eq!(entry.generated_bytes, 0, "generated_bytes must not advance");
        assert!(
            error.message.contains("not permitted")
                || error.message.contains("not enabled")
                || error.message.contains("disabled"),
            "B2 RED: expected tools-disabled reason, got: {}",
            error.message
        );
    }

    #[test]
    fn b2_terminal_tool_calls_are_rejected_when_request_tools_are_disabled() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, "model.turn.tool_calls", 0, "ToolCalls", None);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("terminal tool event must be rejected when tools are disabled");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(!entry.terminal_seen, "terminal must not be accepted");
        assert_eq!(entry.next_sequence, 0, "state must not advance");
        assert_eq!(entry.event_count, 0, "event must not be recorded");
        assert!(
            error.message.contains("not permitted")
                || error.message.contains("not enabled")
                || error.message.contains("disabled"),
            "B2 RED: expected tools-disabled reason, got: {}",
            error.message
        );
    }

    #[test]
    fn b2_tool_permissions_do_not_leak_between_adjacent_requests() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_001,
            max_tokens: 128,
            binding_fingerprint: "b".repeat(64),
        };
        let entry_a = ModelRequestEntry::new(identity_a.clone(), vec!["files.read".to_string()]);
        let mut entry_b = ModelRequestEntry::new(identity_b.clone(), Vec::new());
        assert!(entry_a.tools_are_enabled());
        assert!(!entry_b.tools_are_enabled());
        assert!(entry_b.permitted_tool_names.is_empty());
        let event_b = model_event(&identity_b, "model.tool.request", 0, "Streaming", None);
        let error =
            validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
                .expect_err("tool event on disabled request B must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(entry_b.next_sequence, 0);
        assert_eq!(entry_b.event_count, 0);
        assert_eq!(entry_a.next_sequence, 0, "entry A state must be unaffected");
        assert_eq!(entry_a.event_count, 0, "entry A state must be unaffected");
        assert!(
            error.message.contains("not permitted"),
            "B2: expected tools-disabled reason for B, got: {}",
            error.message
        );
    }

    #[test]
    fn b2_tool_event_cannot_enable_tools_for_a_disabled_request() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, "model.tool.request", 0, "Streaming", None);
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("tool event must not enable tools for a disabled request");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(
            error.message.contains("not permitted")
                || error.message.contains("not enabled")
                || error.message.contains("disabled"),
            "B2 RED: expected tools-disabled reason, got: {}",
            error.message
        );
    }

    #[test]
    fn b2_unknown_method_remains_unsupported_after_b2() {
        assert!(!allowed_model_event_method("model.tool.unknown"));
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = model_event(&identity, "model.turn.unknown", 0, "Streaming", None);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.unknown", 0)
            .expect_err("unknown method must be rejected");
        assert_eq!(error.code, "unsupported_method");
    }

    #[test]
    fn b2_tool_methods_remain_registered_after_b2() {
        assert!(allowed_model_event_method("model.tool.request"));
        assert!(allowed_model_event_method("model.turn.tool_calls"));
        assert!(allowed_event_method("model.tool.request"));
        assert!(allowed_event_method("model.turn.tool_calls"));
    }

    #[test]
    fn b2_enabled_request_records_valid_tool_request() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        assert!(entry.tools_are_enabled());
        let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect("enabled valid tool request must be recorded");
        assert_eq!(entry.next_sequence, 1);
        assert_eq!(entry.event_count, 1);
        assert_eq!(
            entry.intermediate_tool_calls,
            event.metadata["tool_calls"].as_array().unwrap().clone()
        );
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b2_request_entry_snapshots_empty_tool_context() {
        let identity = model_identity();
        let entry = ModelRequestEntry::new(identity, Vec::new());
        assert!(!entry.tools_are_enabled());
        assert!(entry.permitted_tool_names.is_empty());
    }

    #[test]
    fn b2_request_entry_snapshots_enabled_tool_context() {
        let identity = model_identity();
        let entry = ModelRequestEntry::new(
            identity,
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        assert!(entry.tools_are_enabled());
        assert_eq!(entry.permitted_tool_names, vec!["files.read", "files.list"]);
    }

    #[test]
    fn b2_request_entry_owns_tool_snapshot() {
        let identity = model_identity();
        let mut tools = vec!["files.read".to_string()];
        let entry = ModelRequestEntry::new(identity, tools.clone());
        tools.clear();
        assert!(entry.tools_are_enabled());
        assert_eq!(entry.permitted_tool_names, vec!["files.read"]);
    }

    #[test]
    fn b3f_registered_model_tools_is_closed_deterministic_and_bounded() {
        assert_eq!(REGISTERED_MODEL_TOOLS.len(), 9);
        assert_eq!(
            REGISTERED_MODEL_TOOLS,
            &[
                "files.read",
                "files.list",
                "files.write",
                "files.create_folder",
                "files.delete",
                "shell",
                "computer_use",
                "web.search",
                "web.fetch",
            ]
        );
        let as_set: std::collections::HashSet<&&str> = REGISTERED_MODEL_TOOLS.iter().collect();
        assert_eq!(as_set.len(), 9, "no duplicates");
    }

    fn tool_event_with_name(
        identity: &ModelRequestIdentity,
        method: &str,
        tool_name: &str,
    ) -> UiControlPlaneEvent {
        structured_tool_event(
            identity,
            method,
            vec![(tool_name, valid_tool_arguments_json(tool_name))],
        )
    }

    fn valid_tool_arguments_json(tool_name: &str) -> &'static str {
        match tool_name {
            "files.write" => r#"{"path":"notes.txt","content":"hello"}"#,
            "files.read" | "files.list" | "files.create_folder" | "files.delete" => {
                r#"{"path":"notes.txt"}"#
            }
            _ => "{}",
        }
    }

    #[test]
    fn b3m_disabled_request_rejects_tool_event() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("disabled request must reject");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
    }

    #[test]
    fn b3m_permitted_tool_request_is_recorded() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = tool_event_with_name(&identity, "model.tool.request", "files.read");
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect("permitted tool request must be recorded");
        assert_eq!(entry.next_sequence, 1);
        assert_eq!(entry.event_count, 1);
        assert_eq!(
            entry.intermediate_tool_calls,
            event.metadata["tool_calls"].as_array().unwrap().clone()
        );
    }

    #[test]
    fn b3m_registered_but_not_permitted_tool_is_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = tool_event_with_name(&identity, "model.tool.request", "files.delete");
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("non-permitted tool must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: expected membership rejection, got: {}",
            error.message
        );
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
    }

    #[test]
    fn b3m_unknown_tool_is_rejected_by_membership() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = tool_event_with_name(&identity, "model.tool.request", "unknown.tool");
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("unknown tool must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: expected membership rejection, got: {}",
            error.message
        );
        assert_eq!(entry.next_sequence, 0);
    }

    #[test]
    fn b3m_case_confusion_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = tool_event_with_name(&identity, "model.tool.request", "FILES.READ");
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("case-confused name must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: expected exact-match rejection, got: {}",
            error.message
        );
    }

    #[test]
    fn b3m_whitespace_and_prefix_confusion_rejected() {
        let identity = model_identity();
        for name in [
            " files.read",
            "files.read ",
            "files.read.extra",
            "evil.files.read",
        ] {
            let mut entry =
                ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
            let event = tool_event_with_name(&identity, "model.tool.request", name);
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                    .expect_err(&format!("{name:?} must be rejected"));
            assert_eq!(error.code, "protocol_mismatch");
            assert!(
                error.message.contains("not permitted for this request"),
                "B3M RED: {name:?} expected membership rejection, got: {}",
                error.message
            );
        }
    }
    #[test]
    fn b3m_terminal_batch_all_permitted_is_recorded() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = structured_tool_event(
            &identity,
            "model.turn.tool_calls",
            vec![
                ("files.read", valid_tool_arguments_json("files.read")),
                ("files.list", valid_tool_arguments_json("files.list")),
            ],
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect("matching intermediate request must be recorded");
        }
        let mut terminal = event;
        terminal.sequence = calls.len() as u64;
        validate_and_record_model_event(
            &mut entry,
            &terminal,
            "model.turn.tool_calls",
            calls.len() as u64,
        )
        .expect("matching terminal must be recorded");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
        assert_eq!(entry.event_count, calls.len() + 1);
        assert_eq!(entry.intermediate_tool_calls, calls);
    }

    #[test]
    fn b3m_terminal_batch_with_forbidden_name_rejected_atomically() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = structured_tool_event(
            &identity,
            "model.turn.tool_calls",
            vec![
                ("files.read", valid_tool_arguments_json("files.read")),
                ("files.delete", valid_tool_arguments_json("files.delete")),
            ],
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("batch with forbidden name must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: expected atomic membership rejection, got: {}",
            error.message
        );
        assert!(!entry.terminal_seen, "terminal must not be accepted");
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
    }

    #[test]
    fn b3m_terminal_batch_with_unknown_name_rejected_atomically() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = structured_tool_event(
            &identity,
            "model.turn.tool_calls",
            vec![
                ("files.read", valid_tool_arguments_json("files.read")),
                ("unknown.tool", "{}"),
            ],
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("batch with unknown name must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: expected atomic rejection, got: {}",
            error.message
        );
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b3m_adjacent_request_isolation() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_001,
            max_tokens: 128,
            binding_fingerprint: "b".repeat(64),
        };
        let entry_a = ModelRequestEntry::new(
            identity_a.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let mut entry_b =
            ModelRequestEntry::new(identity_b.clone(), vec!["files.read".to_string()]);
        let event_b = tool_event_with_name(&identity_b, "model.tool.request", "files.list");
        let error =
            validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
                .expect_err("files.list not permitted for B");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("not permitted for this request"),
            "B3M RED: B must reject files.list, got: {}",
            error.message
        );
        assert_eq!(entry_a.next_sequence, 0, "A state unchanged");
        assert_eq!(entry_b.next_sequence, 0, "B state unchanged");
    }

    fn structured_tool_event(
        identity: &ModelRequestIdentity,
        method: &str,
        calls: Vec<(&str, &str)>,
    ) -> UiControlPlaneEvent {
        let state = if method == "model.turn.tool_calls" {
            "ToolCalls"
        } else {
            "Streaming"
        };
        let mut event = model_event(identity, method, 0, state, None);
        let tool_calls: Vec<serde_json::Value> = calls
            .iter()
            .enumerate()
            .map(|(i, (name, args))| {
                json!({
                    "id": format!("call_{:03}", i + 1),
                    "name": name,
                    "arguments": serde_json::from_str::<serde_json::Value>(args)
                        .expect("test fixture arguments must be valid JSON"),
                })
            })
            .collect();
        event.metadata["tool_calls"] = json!(tool_calls);
        event.metadata["tools_executed"] =
            json!(event.metadata["tool_calls"].as_array().map_or(0, Vec::len));
        event
    }
    #[test]
    fn b4c_text_only_tool_event_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = model_event(
            &identity,
            "model.tool.request",
            0,
            "Streaming",
            Some("files.read"),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("text-only tool event must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("invalid tool event transition"),
            "text-bearing tool event must be rejected before metadata parsing, got: {}",
            error.message
        );
    }

    #[test]
    fn b4c_structured_single_call_is_recorded() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = structured_tool_event(
            &identity,
            "model.tool.request",
            vec![("files.read", "{\"path\":\"a.txt\"}")],
        );
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect("structured tool request must be admitted and recorded");
        assert_eq!(entry.next_sequence, 1);
        assert_eq!(entry.event_count, 1);
        assert_eq!(
            entry.intermediate_tool_calls,
            event.metadata["tool_calls"].as_array().unwrap().clone()
        );
    }

    #[test]
    fn b4c_structured_terminal_batch_admitted_past_metadata() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = structured_tool_event(
            &identity,
            "model.turn.tool_calls",
            vec![
                ("files.read", "{\"path\":\"a.txt\"}"),
                ("files.list", "{\"path\":\".\"}"),
            ],
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("must be rejected");
        assert!(
            !error.message.contains("metadata shape mismatch"),
            "B4C RED: structured batch should be admitted, got: {}",
            error.message
        );
    }

    #[test]
    fn b4c_structured_name_is_membership_authority_over_text() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let mut event = structured_tool_event(
            &identity,
            "model.tool.request",
            vec![("files.delete", "{\"path\":\"x\"}")],
        );
        event.text = Some("files.read".to_string());
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("must be rejected");
        assert!(
            !error.message.contains("metadata shape mismatch"),
            "B4C RED: structured event should pass metadata, got: {}",
            error.message
        );
    }

    #[test]
    fn b4c_non_tool_event_cannot_carry_tool_calls() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        let mut delta = model_event(&identity, "model.output.delta", 1, "Streaming", Some("hi"));
        delta.metadata["tool_calls"] =
            json!([{"id":"call_001","name":"files.read","arguments":{}}]);
        let error = validate_and_record_model_event(&mut entry, &delta, "model.output.delta", 1)
            .expect_err("content event with tool_calls must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(error.message.contains("metadata shape mismatch"));
    }

    #[test]
    fn b4c_structured_batch_forbidden_name_atomic() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = structured_tool_event(
            &identity,
            "model.turn.tool_calls",
            vec![
                ("files.read", "{\"path\":\"a.txt\"}"),
                ("files.delete", "{\"path\":\"x\"}"),
            ],
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("must be rejected");
        assert!(
            !error.message.contains("metadata shape mismatch"),
            "B4C RED: structured batch should pass metadata, got: {}",
            error.message
        );
        assert!(!entry.terminal_seen);
        assert_eq!(entry.next_sequence, 0);
    }

    fn raw_tool_event(
        identity: &ModelRequestIdentity,
        method: &str,
        tool_calls: serde_json::Value,
    ) -> UiControlPlaneEvent {
        let state = if method == "model.turn.tool_calls" {
            "ToolCalls"
        } else {
            "Streaming"
        };
        let mut event = model_event(identity, method, 0, state, None);
        event.metadata["tool_calls"] = tool_calls;
        event.metadata["tools_executed"] = if method == "model.tool.request" {
            json!(1)
        } else {
            json!(event.metadata["tool_calls"].as_array().map_or(0, Vec::len))
        };
        event
    }

    #[test]
    fn b4a_valid_single_id_is_recorded() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
        );
        validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect("valid single id must be recorded");
        assert_eq!(entry.next_sequence, 1);
        assert_eq!(entry.event_count, 1);
        assert_eq!(
            entry.intermediate_tool_calls,
            event.metadata["tool_calls"].as_array().unwrap().clone()
        );
    }

    #[test]
    fn b4a_missing_id_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"name":"files.read","arguments":"{\"path\":\"a.txt\"}"}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("missing id must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool call id"),
            "B4A RED: expected id-required error, got: {}",
            error.message
        );
        assert_eq!(entry.next_sequence, 0);
    }

    #[test]
    fn b4a_null_id_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"id":null,"name":"files.read","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("null id must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool call id"),
            "B4A RED: expected id-type error, got: {}",
            error.message
        );
    }

    #[test]
    fn b4a_numeric_id_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"id":123,"name":"files.read","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("numeric id must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool call id"),
            "B4A RED: expected id-type error, got: {}",
            error.message
        );
    }

    #[test]
    fn b4a_empty_id_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.tool.request",
            json!([{"id":"","name":"files.read","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("empty id must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("tool call id"),
            "B4A RED: expected id-required error, got: {}",
            error.message
        );
    }

    #[test]
    fn b4a_whitespace_id_rejected() {
        let identity = model_identity();
        for ws in [" ", "\t", "\n"] {
            let mut entry =
                ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
            let event = raw_tool_event(
                &identity,
                "model.tool.request",
                json!([{"id":ws,"name":"files.read","arguments":{}}]),
            );
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                    .expect_err(&format!("whitespace id {ws:?} must be rejected"));
            assert_eq!(error.code, "protocol_mismatch");
            assert!(
                error.message.contains("tool call id"),
                "B4A RED: expected id-required error for {ws:?}, got: {}",
                error.message
            );
        }
    }

    #[test]
    fn b4a_distinct_terminal_ids_are_recorded() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.list","arguments":{"path":"."}}
            ]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect("matching intermediate request must be recorded");
        }
        let mut terminal = event;
        terminal.sequence = calls.len() as u64;
        validate_and_record_model_event(
            &mut entry,
            &terminal,
            "model.turn.tool_calls",
            calls.len() as u64,
        )
        .expect("matching terminal must be recorded");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
        assert_eq!(entry.event_count, calls.len() + 1);
        assert_eq!(entry.intermediate_tool_calls, calls);
    }

    #[test]
    fn b4a_duplicate_terminal_id_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        );
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_001","name":"files.list","arguments":{"path":"."}}
            ]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("duplicate id must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("duplicate tool call id"),
            "B4A RED: expected duplicate-id error, got: {}",
            error.message
        );
        assert!(!entry.terminal_seen);
        assert_eq!(entry.next_sequence, 0);
    }

    #[test]
    fn b4a_duplicate_id_same_tool_rejected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()]);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}
            ]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("duplicate id same tool must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(
            error.message.contains("duplicate tool call id"),
            "B4A RED: expected duplicate-id error, got: {}",
            error.message
        );
    }

    #[test]
    fn b4a_adjacent_request_id_scope_is_independent() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_001,
            max_tokens: 128,
            binding_fingerprint: "b".repeat(64),
        };
        let mut entry_a =
            ModelRequestEntry::new(identity_a.clone(), vec!["files.read".to_string()]);
        let mut entry_b =
            ModelRequestEntry::new(identity_b.clone(), vec!["files.read".to_string()]);
        let event_a = raw_tool_event(
            &identity_a,
            "model.tool.request",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
        );
        let event_b = raw_tool_event(
            &identity_b,
            "model.tool.request",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}]),
        );
        validate_and_record_model_event(&mut entry_a, &event_a, "model.tool.request", 0)
            .expect("request A must record its id");
        validate_and_record_model_event(&mut entry_b, &event_b, "model.tool.request", 0)
            .expect("request B must independently record the same id");
        assert_eq!(
            entry_a.intermediate_tool_calls,
            event_a.metadata["tool_calls"].as_array().unwrap().clone()
        );
        assert_eq!(
            entry_b.intermediate_tool_calls,
            event_b.metadata["tool_calls"].as_array().unwrap().clone()
        );
        assert_eq!(entry_a.next_sequence, 1);
        assert_eq!(entry_b.next_sequence, 1);
    }

    fn b5_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
        ModelRequestEntry::new(identity.clone(), vec!["files.read".to_string()])
    }

    #[test]
    fn b5_valid_path_object_is_recorded() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect("matching intermediate request must be recorded");
        }
        let mut terminal = event;
        terminal.sequence = calls.len() as u64;
        validate_and_record_model_event(
            &mut entry,
            &terminal,
            "model.turn.tool_calls",
            calls.len() as u64,
        )
        .expect("matching terminal must be recorded");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
        assert_eq!(entry.event_count, calls.len() + 1);
        assert_eq!(entry.intermediate_tool_calls, calls);
    }

    #[test]
    fn b5_valid_batch_is_recorded() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.read","arguments":{"path":"b.txt"}}
            ]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect("matching intermediate request must be recorded");
        }
        let mut terminal = event;
        terminal.sequence = calls.len() as u64;
        validate_and_record_model_event(
            &mut entry,
            &terminal,
            "model.turn.tool_calls",
            calls.len() as u64,
        )
        .expect("matching terminal must be recorded");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, (calls.len() + 1) as u64);
        assert_eq!(entry.event_count, calls.len() + 1);
        assert_eq!(entry.intermediate_tool_calls, calls);
    }

    #[test]
    fn b5_missing_arguments_required() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read"}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("missing arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments are required");
    }

    #[test]
    fn b5_null_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":null}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("null arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_string_scalar_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":"hello"}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("string scalar arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_stringified_object_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":"{\"path\":\"a.txt\"}"}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("stringified object arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_empty_string_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":""}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("empty string arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_whitespace_string_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":"   "}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("whitespace string arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_array_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":[1,2]}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("array arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_number_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":5}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("number arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_boolean_arguments_must_be_object() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":true}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("boolean arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
    }

    #[test]
    fn b5_missing_arguments_leaves_entry_unchanged() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read"}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("missing arguments must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments are required");
        assert_eq!(entry.next_sequence, 0);
        assert!(!entry.terminal_seen);
        assert_eq!(entry.event_count, 0);
    }

    #[test]
    fn b5_unknown_tool_precedes_arguments() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.unknown","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("unknown tool must be rejected before arguments");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool is not permitted for this request");
    }

    #[test]
    fn b5_missing_id_precedes_arguments() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"name":"files.read","arguments":{}}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("missing id must be rejected before arguments");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call id is required");
    }

    #[test]
    fn b5_duplicate_id_precedes_arguments() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}
            ]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("duplicate id must be rejected before arguments");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "duplicate tool call id");
    }

    #[test]
    fn b5_adjacent_requests_independent() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_001,
            max_tokens: 128,
            binding_fingerprint: "b".repeat(64),
        };
        let mut entry_a = b5_entry(&identity_a);
        let mut entry_b = b5_entry(&identity_b);
        let event_a = raw_tool_event(
            &identity_a,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}]),
        );
        let event_b = raw_tool_event(
            &identity_b,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}}]),
        );
        for (entry, event) in [(&mut entry_a, event_a), (&mut entry_b, event_b)] {
            let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
            let request = raw_tool_event(
                &entry.identity,
                "model.tool.request",
                json!([calls[0].clone()]),
            );
            validate_and_record_model_event(entry, &request, "model.tool.request", 0)
                .expect("adjacent request prefix must be recorded independently");
            let mut terminal = event;
            terminal.sequence = 1;
            validate_and_record_model_event(entry, &terminal, "model.turn.tool_calls", 1)
                .expect("adjacent terminal must match only its own prefix");
            assert!(entry.terminal_seen);
            assert_eq!(entry.next_sequence, 2);
            assert_eq!(entry.intermediate_tool_calls, calls);
        }
    }

    #[test]
    fn b5_batch_second_call_invalid_arguments_atomic() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.read","arguments":"{\"path\":\"b.txt\"}"}
            ]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("invalid second call must be rejected atomically");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments must be an object");
        assert_eq!(entry.next_sequence, 0);
        assert!(!entry.terminal_seen);
        assert_eq!(entry.event_count, 0);
    }

    // ---- B5L resource-limit test helpers (test-only; deterministic counters) ----

    fn count_bytes(v: &Value) -> usize {
        serde_json::to_string(v).unwrap().len()
    }

    fn count_depth(v: &Value) -> usize {
        match v {
            Value::Object(map) => 1 + map.values().map(count_depth).max().unwrap_or(0),
            Value::Array(items) => 1 + items.iter().map(count_depth).max().unwrap_or(0),
            _ => 0,
        }
    }

    fn count_keys(v: &Value) -> usize {
        match v {
            Value::Object(map) => map.len() + map.values().map(count_keys).sum::<usize>(),
            Value::Array(items) => items.iter().map(count_keys).sum::<usize>(),
            _ => 0,
        }
    }

    fn count_nodes(v: &Value) -> usize {
        match v {
            Value::Object(map) => 1 + map.values().map(count_nodes).sum::<usize>(),
            Value::Array(items) => 1 + items.iter().map(count_nodes).sum::<usize>(),
            _ => 1,
        }
    }

    fn args_with_bytes(target: usize) -> Value {
        assert!(target >= 8, "target must cover the object overhead");
        let value = json!({ "p": "A".repeat(target - 8) });
        assert_eq!(
            count_bytes(&value),
            target,
            "args_with_bytes must hit exact byte target"
        );
        value
    }

    fn args_with_depth(depth: usize) -> Value {
        assert!(depth >= 1, "depth must be at least the root object");
        let mut value = json!({});
        for _ in 1..depth {
            value = json!({ "a": value });
        }
        assert_eq!(
            count_depth(&value),
            depth,
            "args_with_depth must hit exact depth target"
        );
        value
    }

    fn args_with_keys(keys: usize) -> Value {
        let mut map = serde_json::Map::new();
        for index in 0..keys {
            map.insert(format!("k{index}"), json!(1));
        }
        let value = Value::Object(map);
        assert_eq!(
            count_keys(&value),
            keys,
            "args_with_keys must hit exact key target"
        );
        value
    }

    fn args_with_nodes(nodes: usize) -> Value {
        assert!(nodes >= 2, "nodes must cover root object and array");
        let elements = nodes - 2;
        let value = json!({ "arr": vec![json!(1); elements] });
        assert_eq!(
            count_nodes(&value),
            nodes,
            "args_with_nodes must hit exact node target"
        );
        value
    }

    fn args_with_unicode_bytes(target: usize) -> Value {
        assert!(target >= 8, "target must cover the object overhead");
        let body = target - 8;
        let mut text = "é".repeat(body / 2);
        if body % 2 == 1 {
            text.push('A');
        }
        let value = json!({ "p": text });
        assert_eq!(
            count_bytes(&value),
            target,
            "args_with_unicode_bytes must hit exact byte target"
        );
        value
    }

    fn args_depth_and_keys_violation() -> Value {
        let mut inner = json!({});
        for level in 0..32 {
            let mut map = serde_json::Map::new();
            for k in 0..16 {
                map.insert(format!("k{level}_{k}"), json!(1));
            }
            map.insert("n".to_string(), inner);
            inner = Value::Object(map);
        }
        assert!(count_depth(&inner) > 32, "must exceed depth limit");
        assert!(count_keys(&inner) > 512, "must exceed key limit");
        assert!(count_bytes(&inner) <= 65_536, "must not exceed byte limit");
        assert!(count_nodes(&inner) <= 4_096, "must not exceed node limit");
        inner
    }

    // ---- B5L RED tests ----

    #[test]
    fn b5l_exact_byte_limit_reaches_schema_validation() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_bytes(65_536);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect_err("exact resource limit must pass bounds and reach schema validation");
        }
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b5l_exact_depth_limit_reaches_schema_validation() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_depth(32);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect_err("exact resource limit must pass bounds and reach schema validation");
        }
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b5l_exact_key_limit_reaches_schema_validation() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_keys(512);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect_err("exact resource limit must pass bounds and reach schema validation");
        }
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b5l_exact_node_limit_reaches_schema_validation() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_nodes(4_096);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect_err("exact resource limit must pass bounds and reach schema validation");
        }
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b5l_unicode_within_byte_limit_reaches_schema_validation() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_unicode_bytes(65_536);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let calls = event.metadata["tool_calls"].as_array().unwrap().clone();
        for (sequence, call) in calls.iter().enumerate() {
            let mut request =
                raw_tool_event(&identity, "model.tool.request", json!([call.clone()]));
            request.sequence = sequence as u64;
            request.metadata["tools_executed"] = json!(sequence + 1);
            validate_and_record_model_event(
                &mut entry,
                &request,
                "model.tool.request",
                sequence as u64,
            )
            .expect_err("exact resource limit must pass bounds and reach schema validation");
        }
        assert_eq!(entry.next_sequence, 0);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.terminal_seen);
    }

    #[test]
    fn b5l_byte_limit_plus_one_rejected() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_bytes(65_537);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("byte limit + 1 must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments exceed maximum size");
    }

    #[test]
    fn b5l_depth_limit_plus_one_rejected() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_depth(33);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("depth limit + 1 must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(
            error.message,
            "tool call arguments exceed maximum nesting depth"
        );
    }

    #[test]
    fn b5l_key_limit_plus_one_rejected() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_keys(513);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("key limit + 1 must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(
            error.message,
            "tool call arguments exceed maximum object key count"
        );
    }

    #[test]
    fn b5l_node_limit_plus_one_rejected() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_nodes(4_097);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("node limit + 1 must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(
            error.message,
            "tool call arguments exceed maximum node count"
        );
    }

    #[test]
    fn b5l_unicode_byte_limit_plus_one_rejected() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_unicode_bytes(65_537);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("unicode byte limit + 1 must be rejected");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments exceed maximum size");
    }

    #[test]
    fn b5l_multiple_violations_follow_fixed_precedence() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_depth_and_keys_violation();
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("multiple violations must follow fixed precedence");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(
            error.message,
            "tool call arguments exceed maximum nesting depth"
        );
    }

    #[test]
    fn b5l_invalid_second_call_rejects_batch_atomically() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let oversized = args_with_bytes(65_537);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([
                {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                {"id":"call_002","name":"files.read","arguments": oversized}
            ]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("invalid second call must be rejected atomically");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments exceed maximum size");
        assert_eq!(entry.next_sequence, 0);
        assert!(!entry.terminal_seen);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.started_seen);
        assert_eq!(entry.generated_bytes, 0);
        assert!(entry.provider_id.is_none());
        assert!(entry.harness_id.is_none());
    }

    #[test]
    fn b5l_failure_does_not_mutate_entry() {
        let identity = model_identity();
        let mut entry = b5_entry(&identity);
        let arguments = args_with_bytes(65_537);
        let event = raw_tool_event(
            &identity,
            "model.turn.tool_calls",
            json!([{"id":"call_001","name":"files.read","arguments": arguments}]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("failure must not mutate entry");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(error.message, "tool call arguments exceed maximum size");
        assert_eq!(entry.next_sequence, 0);
        assert!(!entry.terminal_seen);
        assert_eq!(entry.event_count, 0);
        assert!(!entry.started_seen);
        assert_eq!(entry.generated_bytes, 0);
        assert!(entry.provider_id.is_none());
        assert!(entry.harness_id.is_none());
    }

    #[test]
    fn adr015_phase_c_shared_tool_event_contract_is_accepted_only_when_tools_are_enabled() {
        let corpus: Value = serde_json::from_str(include_str!(
            "../../../../security/contracts/adr015_tool_event_parity_v1.json"
        ))
        .expect("Phase C parity corpus must be valid JSON");
        let identity_value = corpus["identity"]
            .as_object()
            .expect("Phase C identity must be an object");
        let identity = ModelRequestIdentity {
            request_id: identity_value["requestId"]
                .as_str()
                .expect("requestId must be a string")
                .into(),
            chat_session_id: identity_value["chatSessionId"]
                .as_str()
                .expect("chatSessionId must be a string")
                .into(),
            model_id: identity_value["modelId"]
                .as_str()
                .expect("modelId must be a string")
                .into(),
            submitted_at_unix_ms: identity_value["submittedAtUnixMs"]
                .as_u64()
                .expect("submittedAtUnixMs must be an unsigned integer"),
            max_tokens: identity_value["maxTokens"]
                .as_u64()
                .expect("maxTokens must be an unsigned integer") as u16,
            binding_fingerprint: identity_value["bindingFingerprint"]
                .as_str()
                .expect("bindingFingerprint must be a string")
                .into(),
        };
        let enabled = corpus["enabled"]
            .as_object()
            .expect("enabled contract must be an object");
        let permitted_tools = enabled["permittedTools"]
            .as_array()
            .expect("permittedTools must be an array")
            .iter()
            .map(|tool| tool.as_str().expect("tool must be a string").to_owned())
            .collect();
        let mut entry = ModelRequestEntry::new(identity.clone(), permitted_tools);
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0)
            .expect("tool-event contract requires an accepted started event");
        for case in enabled["events"]
            .as_array()
            .expect("enabled events must be an array")
        {
            let method = case["method"].as_str().expect("method must be a string");
            let sequence = case["sequence"]
                .as_u64()
                .expect("sequence must be an integer");
            let mut event = raw_tool_event(&identity, method, case["toolCalls"].clone());
            event.sequence = sequence;
            event.state = case["state"]
                .as_str()
                .expect("state must be a string")
                .to_owned();
            event.metadata["tools_executed"] = case["toolsExecuted"].clone();
            // The Python gateway emits a started event first, then a pure tool-call stream.
            event.metadata["model_called"] = json!(true);
            event.metadata["generated_bytes"] = json!(0);
            validate_and_record_model_event(&mut entry, &event, method, sequence)
                .expect("Python-emitted Phase C contract event must pass Rust validation");
        }
        assert!(entry.terminal_seen);
        assert_eq!(entry.intermediate_tool_calls.len(), 2);

        let disabled = corpus["disabled"]
            .as_object()
            .expect("disabled contract must be an object");
        let method = disabled["method"]
            .as_str()
            .expect("method must be a string");
        let sequence = disabled["sequence"]
            .as_u64()
            .expect("sequence must be an integer");
        let mut disabled_entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut disabled_entry, &started, "model.turn.started", 0)
            .expect("disabled contract still requires a valid started event");
        let mut event = raw_tool_event(&identity, method, disabled["toolCalls"].clone());
        event.sequence = sequence;
        event.state = disabled["state"]
            .as_str()
            .expect("state must be a string")
            .to_owned();
        event.metadata["tools_executed"] = disabled["toolsExecuted"].clone();
        event.metadata["model_called"] = json!(true);
        event.metadata["generated_bytes"] = json!(0);
        let error = validate_and_record_model_event(&mut disabled_entry, &event, method, sequence)
            .expect_err("tools=[] must reject the shared tool event contract");
        assert_eq!(error.code, "protocol_mismatch");
        assert_eq!(disabled_entry.next_sequence, 1);
        assert!(disabled_entry.intermediate_tool_calls.is_empty());
    }

    // ---- B6 cross-event provenance RED helpers and tests ----

    #[derive(Debug, PartialEq)]
    struct B6EntrySnapshot {
        identity: ModelRequestIdentity,
        provider_id: Option<String>,
        harness_id: Option<String>,
        knowledge_model: bool,
        knowledge_acceptance_seen: bool,
        knowledge_injection_id: Option<String>,
        knowledge_included: bool,
        accepted: bool,
        cancel_pending: bool,
        cancel_accepted: bool,
        cancel_requested_before_acceptance: bool,
        cancel_after_synthetic_release: bool,
        releasing_events: bool,
        remove_after_release: bool,
        started_seen: bool,
        terminal_seen: bool,
        next_sequence: u64,
        event_count: usize,
        event_text: usize,
        model_called: bool,
        generated_bytes: u64,
        buffered_events: Vec<String>,
        tools_enabled: bool,
        permitted_tool_names: Vec<String>,
        intermediate_tool_calls: Vec<Value>,
    }

    fn b6_snapshot(entry: &ModelRequestEntry) -> B6EntrySnapshot {
        B6EntrySnapshot {
            identity: entry.identity.clone(),
            provider_id: entry.provider_id.clone(),
            harness_id: entry.harness_id.clone(),
            knowledge_model: entry.knowledge_model,
            knowledge_acceptance_seen: entry.knowledge_acceptance_seen,
            knowledge_injection_id: entry.knowledge_injection_id.clone(),
            knowledge_included: entry.knowledge_included,
            accepted: entry.accepted,
            cancel_pending: entry.cancel_pending,
            cancel_accepted: entry.cancel_accepted,
            cancel_requested_before_acceptance: entry.cancel_requested_before_acceptance,
            cancel_after_synthetic_release: entry.cancel_after_synthetic_release,
            releasing_events: entry.releasing_events,
            remove_after_release: entry.remove_after_release,
            started_seen: entry.started_seen,
            terminal_seen: entry.terminal_seen,
            next_sequence: entry.next_sequence,
            event_count: entry.event_count,
            event_text: entry.event_text,
            model_called: entry.model_called,
            generated_bytes: entry.generated_bytes,
            buffered_events: entry
                .buffered_events
                .iter()
                .map(|event| serde_json::to_string(event).expect("buffered event must serialize"))
                .collect(),
            tools_enabled: entry.tools_enabled,
            permitted_tool_names: entry.permitted_tool_names.clone(),
            intermediate_tool_calls: entry.intermediate_tool_calls.clone(),
        }
    }

    fn b6_calls() -> Value {
        json!([
            {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
            {"id":"call_002","name":"files.list","arguments":{"path":"."}}
        ])
    }

    fn b6_tool_event(
        identity: &ModelRequestIdentity,
        method: &str,
        sequence: u64,
        tool_calls: Value,
    ) -> UiControlPlaneEvent {
        let mut event = raw_tool_event(identity, method, tool_calls);
        event.sequence = sequence;
        if method == "model.tool.request" {
            event.metadata["tools_executed"] = json!(sequence + 1);
        }
        event
    }

    fn b6_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
        ModelRequestEntry::new(
            identity.clone(),
            vec!["files.read".to_string(), "files.list".to_string()],
        )
    }

    fn b6_submit_prefix(entry: &mut ModelRequestEntry, calls: &Value) {
        // Use the production validator; failing at its current placeholder is the earliest B6 RED,
        // because accepting and accumulating intermediate requests is itself missing B6 behavior.
        for (sequence, call) in calls
            .as_array()
            .expect("B6 fixture calls must be an array")
            .iter()
            .enumerate()
        {
            let event = b6_tool_event(
                &entry.identity,
                "model.tool.request",
                sequence as u64,
                json!([call.clone()]),
            );
            validate_and_record_model_event(entry, &event, "model.tool.request", sequence as u64)
                .expect("intermediate tool request must be accepted and accumulated");
        }
    }

    fn b6_assert_provenance_rejection(error: &BridgeError) {
        assert_eq!(error.code, "protocol_mismatch");
        // This seam receives serde_json::Value, so lexical and key-order wire-byte assertions are invalid.
        // Exact wording is intentionally not frozen by ADR-015.
        assert!(
            error.message.contains("tool call provenance mismatch"),
            "expected provenance mismatch, got: {}",
            error.message
        );
    }

    #[test]
    fn b6_terminal_without_intermediate_request_is_rejected_atomically() {
        let identity = model_identity();
        let mut entry = b6_entry(&identity);
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 0, b6_calls());
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 0)
            .expect_err("terminal without an intermediate request must be rejected");
        b6_assert_provenance_rejection(&error);
        assert_eq!(b6_snapshot(&entry), before);
    }

    #[test]
    fn b6_exact_ordered_two_call_prefix_then_identical_terminal_is_recorded() {
        let identity = model_identity();
        let mut entry = b6_entry(&identity);
        let calls = b6_calls();
        b6_submit_prefix(&mut entry, &calls);
        let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, calls);
        // A mixed OpenAI response keeps its accumulated assistant text on the
        // terminal tool batch so the frontend can preserve it in history.
        event.text = Some("explanation before tool execution".into());
        validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
            .expect("matching mixed-content terminal must be accepted and recorded");
        assert!(entry.terminal_seen);
        assert_eq!(entry.next_sequence, 3);
        assert_eq!(entry.event_count, 3);
    }

    #[test]
    fn b6_terminal_mismatch_cases_are_rejected_atomically() {
        let identity = model_identity();
        let prefix = b6_calls();
        let cases = [
            (
                "missing",
                json!([
                    {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}
                ]),
            ),
            (
                "extra",
                json!([
                    {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}},
                    {"id":"call_002","name":"files.list","arguments":{"path":"."}},
                    {"id":"call_003","name":"files.read","arguments":{"path":"b.txt"}}
                ]),
            ),
            (
                "reordered",
                json!([
                    {"id":"call_002","name":"files.list","arguments":{"path":"."}},
                    {"id":"call_001","name":"files.read","arguments":{"path":"a.txt"}}
                ]),
            ),
            (
                "changed id",
                json!([
                    {"id":"call_009","name":"files.read","arguments":{"path":"a.txt"}},
                    {"id":"call_002","name":"files.list","arguments":{"path":"."}}
                ]),
            ),
            (
                "changed permitted name",
                json!([
                    {"id":"call_001","name":"files.list","arguments":{"path":"a.txt"}},
                    {"id":"call_002","name":"files.list","arguments":{"path":"."}}
                ]),
            ),
            (
                "changed argument value",
                json!([
                    {"id":"call_001","name":"files.read","arguments":{"path":"b.txt"}},
                    {"id":"call_002","name":"files.list","arguments":{"path":"."}}
                ]),
            ),
        ];

        for (label, terminal_calls) in cases {
            let mut entry = b6_entry(&identity);
            b6_submit_prefix(&mut entry, &prefix);
            let before = b6_snapshot(&entry);
            let event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
                    .expect_err(&format!("{label} mismatch must be rejected"));
            b6_assert_provenance_rejection(&error);
            assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
        }
    }

    #[test]
    fn b6_object_key_order_is_insignificant_after_parsing() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), vec!["files.write".to_string()]);
        let prefix = json!([{
            "id":"call_001",
            "name":"files.write",
            "arguments":{"path":"a.txt","content":"hello"}
        }]);
        b6_submit_prefix(&mut entry, &prefix);
        let terminal: Value = serde_json::from_str(
            r#"[{"arguments":{"content":"hello","path":"a.txt"},"name":"files.write","id":"call_001"}]"#,
        )
        .expect("reordered object fixture must parse");
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 1, terminal);
        validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 1)
            .expect("object member order must not affect parsed structural equality");
        assert!(entry.terminal_seen);
    }

    #[test]
    fn b6_missing_argument_field_differs_from_null() {
        let identity = model_identity();
        let prefix = json!([{
            "id":"call_001","name":"files.read","arguments":{"path":"a.txt"}
        }]);
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &prefix);
        let before = b6_snapshot(&entry);
        let terminal = json!([{
            "id":"call_001","name":"files.read","arguments":{"path":null}
        }]);
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 1, terminal);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 1)
            .expect_err("missing must differ from explicit null");
        assert!(error
            .message
            .contains("argument field path must be a string"));
        assert_eq!(b6_snapshot(&entry), before);
    }

    #[test]
    fn b6_unknown_tool_call_envelope_field_is_rejected_atomically() {
        let identity = model_identity();
        let mut entry = b6_entry(&identity);
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([{
                "id":"call_001","name":"files.read","arguments":{},"unexpected":true
            }]),
        );
        let error = validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
            .expect_err("closed tool-call envelope must reject unknown fields");
        assert_eq!(error.code, "protocol_mismatch");
        assert!(error.message.contains("unknown fields"));
        assert_eq!(b6_snapshot(&entry), before);
    }

    fn b7_tool_event(
        identity: &ModelRequestIdentity,
        method: &str,
        sequence: u64,
        calls: Value,
        tools_executed: Value,
    ) -> UiControlPlaneEvent {
        let mut event = if calls.is_null() {
            model_event(identity, method, sequence, "Streaming", None)
        } else {
            b6_tool_event(identity, method, sequence, calls)
        };
        event.metadata["tools_executed"] = tools_executed;
        event
    }

    fn b7_snapshot(entry: &ModelRequestEntry) -> (u64, usize, bool, bool, u64, usize) {
        (
            entry.next_sequence,
            entry.event_count,
            entry.started_seen,
            entry.terminal_seen,
            entry.generated_bytes,
            entry.intermediate_tool_calls.len(),
        )
    }

    #[test]
    fn b7_cumulative_tools_executed_is_sequence_consistent_and_atomic() {
        let identity = model_identity();
        let calls = b6_calls();
        let mut entry = b6_entry(&identity);

        let first = b7_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([calls[0].clone()]),
            json!(1),
        );
        validate_and_record_model_event(&mut entry, &first, "model.tool.request", 0)
            .expect("first request count must be one");

        for invalid in [
            json!(0),
            json!(1),
            json!(3),
            json!(-1),
            json!(1.5),
            json!("2"),
            json!(9_007_199_254_740_992_u64),
        ] {
            let before = b7_snapshot(&entry);
            let event = b7_tool_event(
                &identity,
                "model.tool.request",
                1,
                json!([calls[1].clone()]),
                invalid,
            );
            validate_and_record_model_event(&mut entry, &event, "model.tool.request", 1)
                .expect_err("invalid cumulative count must be rejected");
            assert_eq!(b7_snapshot(&entry), before, "rejection must be atomic");
        }

        let second = b7_tool_event(
            &identity,
            "model.tool.request",
            1,
            json!([calls[1].clone()]),
            json!(2),
        );
        validate_and_record_model_event(&mut entry, &second, "model.tool.request", 1)
            .expect("second request count must be two");

        let before = b7_snapshot(&entry);
        let bad_terminal = b7_tool_event(
            &identity,
            "model.turn.tool_calls",
            2,
            calls.clone(),
            json!(1),
        );
        validate_and_record_model_event(&mut entry, &bad_terminal, "model.turn.tool_calls", 2)
            .expect_err("terminal count must match accumulated calls");
        assert_eq!(b7_snapshot(&entry), before);

        let terminal = b7_tool_event(&identity, "model.turn.tool_calls", 2, calls, json!(2));
        validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 2)
            .expect("matching terminal count must be accepted");
        assert!(entry.terminal_seen);
    }

    #[test]
    fn b7_tools_disabled_rejects_nonzero_count_atomically() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone(), Vec::new());
        let before = b7_snapshot(&entry);
        let event = b7_tool_event(&identity, "model.turn.started", 0, Value::Null, json!(1));
        validate_and_record_model_event(&mut entry, &event, "model.turn.started", 0)
            .expect_err("tools-disabled context must require zero");
        assert_eq!(b7_snapshot(&entry), before);
    }

    #[test]
    fn b8_invalid_terminal_batches_preserve_complete_entry_snapshot() {
        let identity = model_identity();
        let valid_calls = b6_calls();
        let cases = vec![
            (
                "unknown later tool",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_002","name":"files.unknown","arguments":{}}
                ]),
                None,
            ),
            (
                "deep later arguments",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_002","name":"files.list","arguments":args_with_depth(33)}
                ]),
                None,
            ),
            (
                "oversized later arguments",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_002","name":"files.list","arguments":args_with_bytes(65_537)}
                ]),
                None,
            ),
            (
                "missing later id",
                json!([
                    valid_calls[0].clone(),
                    {"name":"files.list","arguments":{"path":"."}}
                ]),
                None,
            ),
            (
                "duplicate later id",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_001","name":"files.list","arguments":{"path":"."}}
                ]),
                None,
            ),
            (
                "unknown later envelope field",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_002","name":"files.list","arguments":{"path":"."},"unexpected":true}
                ]),
                None,
            ),
            (
                "provenance mismatch",
                json!([
                    valid_calls[0].clone(),
                    {"id":"call_002","name":"files.list","arguments":{"path":"elsewhere"}}
                ]),
                None,
            ),
            (
                "terminal counter mismatch",
                valid_calls.clone(),
                Some(json!(1)),
            ),
        ];

        for (label, terminal_calls, tools_executed) in cases {
            let mut entry = b6_entry(&identity);
            b6_submit_prefix(&mut entry, &valid_calls);
            entry.accepted = true;
            entry.cancel_pending = true;
            entry.buffered_events.push(model_event(
                &identity,
                "model.output.delta",
                99,
                "Streaming",
                Some("buffered sentinel"),
            ));
            let before = b6_snapshot(&entry);
            let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
            if let Some(value) = tools_executed {
                event.metadata["tools_executed"] = value;
            }
            validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
                .expect_err(&format!("{label} must reject the whole terminal batch"));
            assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
        }
    }

    #[test]
    fn b8_event_budget_failure_after_valid_terminal_batch_is_atomic() {
        let identity = model_identity();
        let calls = b6_calls();
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &calls);
        entry.event_count = MAX_MODEL_EVENTS_PER_REQUEST;
        let before = b6_snapshot(&entry);
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 2, calls);
        let error = validate_and_record_model_event(&mut entry, &event, "model.turn.tool_calls", 2)
            .expect_err("event budget failure must reject before terminal commit");
        assert_eq!(error.code, "budget_exceeded");
        assert_eq!(b6_snapshot(&entry), before);
    }

    #[test]
    fn b8_valid_terminal_commits_once_and_adjacent_request_stays_unchanged() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: identity_a.model_id.clone(),
            submitted_at_unix_ms: identity_a.submitted_at_unix_ms + 1,
            max_tokens: identity_a.max_tokens,
            binding_fingerprint: "b".repeat(64),
        };
        let calls = b6_calls();
        let mut entry_a = b6_entry(&identity_a);
        let entry_b = b6_entry(&identity_b);
        b6_submit_prefix(&mut entry_a, &calls);
        let before_b = b6_snapshot(&entry_b);
        let event = b6_tool_event(&identity_a, "model.turn.tool_calls", 2, calls.clone());
        validate_and_record_model_event(&mut entry_a, &event, "model.turn.tool_calls", 2)
            .expect("valid matching terminal must commit");
        assert!(entry_a.terminal_seen);
        assert_eq!(entry_a.next_sequence, 3);
        assert_eq!(entry_a.event_count, 3);
        assert_eq!(
            entry_a.intermediate_tool_calls,
            calls
                .as_array()
                .expect("calls fixture must be an array")
                .clone()
        );
        let after_first_commit = b6_snapshot(&entry_a);
        validate_and_record_model_event(&mut entry_a, &event, "model.turn.tool_calls", 2)
            .expect_err("terminal batch must not commit twice");
        assert_eq!(b6_snapshot(&entry_a), after_first_commit);
        assert_eq!(b6_snapshot(&entry_b), before_b);
    }

    fn b9_call(id: &str, name: &str, arguments: Value) -> Value {
        json!({"id": id, "name": name, "arguments": arguments})
    }

    fn b9_entry(identity: &ModelRequestIdentity, name: &str) -> ModelRequestEntry {
        ModelRequestEntry::new(identity.clone(), vec![name.to_string()])
    }

    #[test]
    fn b9_accepts_exact_argument_schema_for_every_registered_file_tool() {
        let identity = model_identity();
        let cases = [
            ("files.read", json!({"path":"notes.txt"})),
            ("files.list", json!({"path":"."})),
            ("files.write", json!({"path":"notes.txt","content":"hello"})),
            ("files.create_folder", json!({"path":"drafts"})),
            ("files.delete", json!({"path":"old.txt"})),
        ];

        for (name, arguments) in cases {
            let mut entry = b9_entry(&identity, name);
            let call = b9_call("call_001", name, arguments);
            let request = b6_tool_event(&identity, "model.tool.request", 0, json!([call.clone()]));
            validate_and_record_model_event(&mut entry, &request, "model.tool.request", 0)
                .expect("exact registered tool schema must be accepted");
            let terminal = b6_tool_event(&identity, "model.turn.tool_calls", 1, json!([call]));
            validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 1)
                .expect("matching terminal must be accepted");
        }
    }

    #[test]
    fn b9_rejects_malformed_intermediate_arguments_atomically() {
        let identity = model_identity();
        let cases = [
            ("missing required", "files.read", json!({})),
            ("null required", "files.read", json!({"path":null})),
            ("wrong type", "files.read", json!({"path":7})),
            (
                "extra key",
                "files.read",
                json!({"path":"notes.txt","recursive":true}),
            ),
            (
                "nested wrong type",
                "files.write",
                json!({"path":"notes.txt","content":{"text":"hello"}}),
            ),
            (
                "write missing content",
                "files.write",
                json!({"path":"notes.txt"}),
            ),
        ];

        for (label, name, arguments) in cases {
            let mut entry = b9_entry(&identity, name);
            let before = b6_snapshot(&entry);
            let event = b6_tool_event(
                &identity,
                "model.tool.request",
                0,
                json!([b9_call("call_001", name, arguments)]),
            );
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                    .expect_err(&format!("{label} must be rejected"));
            assert_eq!(error.code, "protocol_mismatch");
            assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry");
        }
    }

    #[test]
    fn b9_terminal_schema_validation_precedes_provenance_and_is_atomic() {
        let identity = model_identity();
        let valid = b9_call(
            "call_001",
            "files.write",
            json!({"path":"notes.txt","content":"hello"}),
        );
        let malformed = [
            json!({"path":"notes.txt"}),
            json!({"path":"notes.txt","content":null}),
            json!({"path":"notes.txt","content":9}),
            json!({"path":"notes.txt","content":"hello","mode":"append"}),
            json!({"path":{"nested":"notes.txt"},"content":"hello"}),
        ];

        for arguments in malformed {
            let mut entry = b9_entry(&identity, "files.write");
            let request = b6_tool_event(&identity, "model.tool.request", 0, json!([valid.clone()]));
            validate_and_record_model_event(&mut entry, &request, "model.tool.request", 0)
                .expect("valid prefix must be accepted");
            let before = b6_snapshot(&entry);
            let terminal = b6_tool_event(
                &identity,
                "model.turn.tool_calls",
                1,
                json!([b9_call("call_001", "files.write", arguments)]),
            );
            let error =
                validate_and_record_model_event(&mut entry, &terminal, "model.turn.tool_calls", 1)
                    .expect_err("malformed terminal arguments must be rejected");
            assert_eq!(error.code, "protocol_mismatch");
            assert!(
                error.message.contains("tool files.write"),
                "schema error must precede provenance comparison: {}",
                error.message
            );
            assert_eq!(b6_snapshot(&entry), before);
        }
    }

    #[test]
    fn b6_adjacent_model_request_entries_are_isolated() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "fedcba9876543210fedcba98".into(),
            chat_session_id: "chat_session_2".into(),
            model_id: "qwen2.5-1.5b-instruct-q4-k-m".into(),
            submitted_at_unix_ms: 1_750_000_000_001,
            max_tokens: 128,
            binding_fingerprint: "b".repeat(64),
        };
        let calls = b6_calls();
        let mut entry_a = b6_entry(&identity_a);
        let mut entry_b = b6_entry(&identity_b);
        b6_submit_prefix(&mut entry_a, &calls);
        let before_a = b6_snapshot(&entry_a);
        let before_b = b6_snapshot(&entry_b);
        let event_b = b6_tool_event(&identity_b, "model.turn.tool_calls", 0, calls);
        let error =
            validate_and_record_model_event(&mut entry_b, &event_b, "model.turn.tool_calls", 0)
                .expect_err("entry B cannot use entry A's intermediate requests");
        b6_assert_provenance_rejection(&error);
        assert_eq!(b6_snapshot(&entry_a), before_a);
        assert_eq!(b6_snapshot(&entry_b), before_b);
    }

    // ---- B10 malicious-sidecar defense-in-depth (deterministic adversarial corpus) ----
    //
    // Bounding chain for tool-call `id` length and intermediate_tool_calls growth
    // (settled by inspection, no redundant Rust check added):
    //   * every sidecar event arrives as one IPC frame bounded by
    //     `ipc::MAX_FRAME_BYTES` (4 MiB), so a single `id` cannot exceed that frame;
    //   * `entry.intermediate_tool_calls` only grows on an accepted
    //     `model.tool.request`, and each acceptance consumes one event of the
    //     `MAX_MODEL_EVENTS_PER_REQUEST` (2048) budget, which is checked before
    //     mutation, so growth is bounded by 2048 frames;
    //   * the Python gateway is the upstream authority and additionally caps a turn
    //     at `MAX_TOOL_CALLS_PER_TURN` (10).
    // Bound = frame size * event budget, both enforced before mutation.

    /// Deterministic LCG: no external crates, no entropy, reproducible corpus.
    struct B10Rng(u64);

    impl B10Rng {
        fn new(seed: u64) -> Self {
            Self(seed)
        }

        fn next_u32(&mut self) -> u32 {
            self.0 = self
                .0
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            (self.0 >> 33) as u32
        }

        fn pick<'a, T>(&mut self, items: &'a [T]) -> &'a T {
            let index = self.next_u32() as usize % items.len();
            &items[index]
        }
    }

    fn b10_entry(identity: &ModelRequestIdentity) -> ModelRequestEntry {
        ModelRequestEntry::new(
            identity.clone(),
            REGISTERED_MODEL_TOOLS
                .iter()
                .map(|name| (*name).to_string())
                .collect(),
        )
    }

    fn b10_read_call(id: &str, arguments: Value) -> Value {
        json!({"id": id, "name": "files.read", "arguments": arguments})
    }

    fn b10_reject(entry: &mut ModelRequestEntry, event: &UiControlPlaneEvent, label: &str) {
        let before = b6_snapshot(entry);
        let method = event.method.clone();
        let sequence = event.sequence;
        let error = validate_and_record_model_event(entry, event, &method, sequence)
            .expect_err(&format!("{label} must be rejected"));
        assert!(
            matches!(
                error.code.as_str(),
                "protocol_mismatch" | "budget_exceeded" | "invalid_sequence"
            ),
            "{label} produced unstable error code {}",
            error.code
        );
        assert!(!error.message.is_empty(), "{label} lost its error message");
        assert_eq!(b6_snapshot(entry), before, "{label} mutated entry state");
    }

    #[test]
    fn b10_boundary_limits_accept_at_limit_and_reject_beyond() {
        let identity = model_identity();

        // At-limit payloads must be accepted by the boundary.
        // args_with_bytes/keys/nodes build non-schema fields, so accept-side cases
        // use schema-valid arguments that still sit exactly on a structural limit.
        let at_depth = args_with_depth(MAX_ARGUMENT_DEPTH);
        assert_eq!(count_depth(&at_depth), MAX_ARGUMENT_DEPTH);

        let accepted = [
            ("bytes at limit", args_with_bytes(MAX_ARGUMENT_BYTES)),
            ("depth at limit", at_depth),
            ("keys at limit", args_with_keys(MAX_ARGUMENT_OBJECT_KEYS)),
            ("nodes at limit", args_with_nodes(MAX_ARGUMENT_NODES)),
        ];
        for (label, arguments) in accepted {
            let mut entry = b10_entry(&identity);
            let event = b6_tool_event(
                &identity,
                "model.tool.request",
                0,
                json!([b10_read_call("call_001", arguments)]),
            );
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                    .expect_err("non-schema structural payloads still fail per-tool schema");
            assert_eq!(
                error.code, "protocol_mismatch",
                "{label} must fail on schema, not on a resource limit"
            );
            assert!(
                error.message.contains("tool files.read"),
                "{label} must reach per-tool schema validation, got: {}",
                error.message
            );
        }

        // Beyond-limit payloads must fail earlier, on the resource-limit checks.
        let over_limit = [
            (
                "bytes over limit",
                args_with_bytes(MAX_ARGUMENT_BYTES + 1),
                "maximum size",
            ),
            (
                "depth over limit",
                args_with_depth(MAX_ARGUMENT_DEPTH + 1),
                "maximum nesting depth",
            ),
            (
                "keys over limit",
                args_with_keys(MAX_ARGUMENT_OBJECT_KEYS + 1),
                "maximum object key count",
            ),
            (
                "nodes over limit",
                args_with_nodes(MAX_ARGUMENT_NODES + 1),
                "maximum node count",
            ),
            (
                "unicode bytes over limit",
                args_with_unicode_bytes(MAX_ARGUMENT_BYTES + 1),
                "maximum size",
            ),
        ];
        for (label, arguments, expected) in over_limit {
            let mut entry = b10_entry(&identity);
            let before = b6_snapshot(&entry);
            let event = b6_tool_event(
                &identity,
                "model.tool.request",
                0,
                json!([b10_read_call("call_001", arguments)]),
            );
            let error =
                validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                    .expect_err(&format!("{label} must be rejected"));
            assert_eq!(error.code, "protocol_mismatch", "{label}");
            assert!(
                error.message.contains(expected),
                "{label} produced unstable message: {}",
                error.message
            );
            assert_eq!(b6_snapshot(&entry), before, "{label} mutated entry state");
        }
    }

    #[test]
    fn b10_hostile_envelopes_are_rejected_atomically() {
        let identity = model_identity();
        let huge_id = "i".repeat(200_000);
        let cases: Vec<(&str, Value)> = vec![
            (
                "unknown envelope field",
                json!({"id":"c1","name":"files.read","arguments":{"path":"a"},"x":1}),
            ),
            (
                "missing id",
                json!({"name":"files.read","arguments":{"path":"a"}}),
            ),
            (
                "id wrong type",
                json!({"id":7,"name":"files.read","arguments":{"path":"a"}}),
            ),
            (
                "empty id",
                json!({"id":"","name":"files.read","arguments":{"path":"a"}}),
            ),
            (
                "whitespace id",
                json!({"id":"   ","name":"files.read","arguments":{"path":"a"}}),
            ),
            (
                "name wrong type",
                json!({"id":"c1","name":42,"arguments":{"path":"a"}}),
            ),
            (
                "unregistered tool",
                json!({"id":"c1","name":"files.exec","arguments":{"path":"a"}}),
            ),
            (
                "arguments not an object",
                json!({"id":"c1","name":"files.read","arguments":"{\"path\":\"a\"}"}),
            ),
            (
                "arguments null",
                json!({"id":"c1","name":"files.read","arguments":null}),
            ),
            (
                "arguments array",
                json!({"id":"c1","name":"files.read","arguments":[]}),
            ),
            (
                "NUL byte in path",
                json!({"id":"c1","name":"files.read","arguments":{"path":"a\u{0000}b","extra":1}}),
            ),
            (
                "control chars with extra key",
                json!({"id":"c1","name":"files.read","arguments":{"path":"a\u{0007}\u{001b}b","x":1}}),
            ),
            (
                "unicode replacement path with extra key",
                json!({"id":"c1","name":"files.read","arguments":{"path":"\u{fffd}\u{202e}evil","x":1}}),
            ),
            ("envelope not an object", json!("call_001")),
        ];

        for (label, call) in cases {
            let mut entry = b10_entry(&identity);
            let event = b6_tool_event(&identity, "model.tool.request", 0, json!([call]));
            b10_reject(&mut entry, &event, label);
        }

        // Huge id is not covered by MAX_ARGUMENT_BYTES; it is bounded upstream by
        // ipc::MAX_FRAME_BYTES. At the validator seam it must not panic and must
        // still be classified deterministically by the remaining rules.
        let mut entry = b10_entry(&identity);
        let duplicate = json!([
            {"id": huge_id.clone(), "name":"files.read","arguments":{"path":"a"}},
            {"id": huge_id, "name":"files.list","arguments":{"path":"."}}
        ]);
        let event = b6_tool_event(&identity, "model.turn.tool_calls", 0, duplicate);
        b10_reject(&mut entry, &event, "duplicate huge ids");

        // Empty and non-array tool_calls metadata.
        for (label, calls) in [
            ("empty tool_calls", json!([])),
            ("tool_calls not an array", json!({"id":"c1"})),
        ] {
            let mut entry = b10_entry(&identity);
            let event = b6_tool_event(&identity, "model.tool.request", 0, calls);
            b10_reject(&mut entry, &event, label);
        }

        // model.tool.request must carry exactly one call.
        let mut entry = b10_entry(&identity);
        let event = b6_tool_event(
            &identity,
            "model.tool.request",
            0,
            json!([
                {"id":"c1","name":"files.read","arguments":{"path":"a"}},
                {"id":"c2","name":"files.list","arguments":{"path":"."}}
            ]),
        );
        b10_reject(&mut entry, &event, "batched intermediate request");
    }

    #[test]
    fn b10_hostile_terminal_batches_are_rejected_atomically() {
        let identity = model_identity();
        let calls = b6_calls();

        let cases: Vec<(&str, Value, Option<Value>)> = vec![
            (
                "provenance reordered",
                json!([calls[1].clone(), calls[0].clone()]),
                None,
            ),
            (
                "provenance truncated",
                json!([calls[0].clone()]),
                Some(json!(1)),
            ),
            (
                "provenance extended",
                json!([
                    calls[0].clone(),
                    calls[1].clone(),
                    {"id":"call_003","name":"files.read","arguments":{"path":"c.txt"}}
                ]),
                Some(json!(3)),
            ),
            ("count near u64 max", calls.clone(), Some(json!(u64::MAX))),
            (
                "count at unsafe integer",
                calls.clone(),
                Some(json!(9_007_199_254_740_992_u64)),
            ),
            ("count zero", calls.clone(), Some(json!(0))),
            ("count negative", calls.clone(), Some(json!(-1))),
            ("count fractional", calls.clone(), Some(json!(2.5))),
            ("count as string", calls.clone(), Some(json!("2"))),
        ];

        for (label, terminal_calls, tools_executed) in cases {
            let mut entry = b6_entry(&identity);
            b6_submit_prefix(&mut entry, &calls);
            let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, terminal_calls);
            if let Some(value) = tools_executed {
                event.metadata["tools_executed"] = value;
            }
            b10_reject(&mut entry, &event, label);
        }

        // A huge hostile batch must be rejected without unbounded work.
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &calls);
        let huge: Vec<Value> = (0..2_000)
            .map(|index| json!({"id": format!("c{index}"), "name":"files.read", "arguments":{"path":"a.txt"}}))
            .collect();
        let mut event = b6_tool_event(&identity, "model.turn.tool_calls", 2, json!(huge));
        event.metadata["tools_executed"] = json!(2_000);
        let started = std::time::Instant::now();
        b10_reject(&mut entry, &event, "huge hostile terminal batch");
        assert!(
            started.elapsed() < std::time::Duration::from_secs(5),
            "huge hostile batch validation must stay bounded"
        );
    }

    #[test]
    fn b10_repeated_hostile_events_are_atomic_under_seeded_corpus() {
        let identity = model_identity();
        let calls = b6_calls();
        let mut entry = b6_entry(&identity);
        b6_submit_prefix(&mut entry, &calls);
        entry.accepted = true;
        let before = b6_snapshot(&entry);

        let names = ["files.read", "files.list", "files.exec", "", "FILES.READ"];
        let ids = [
            "",
            " ",
            "call_001",
            "call_002",
            "\u{0000}",
            "x".repeat(4096).leak() as &str,
        ];
        let arg_shapes = [
            json!({}),
            json!({"path":null}),
            json!({"path":1}),
            json!({"path":"a.txt","extra":true}),
            json!({"path":{"nested":"a"}}),
            // Control/NUL characters are schema-valid `path` strings under the frozen
            // ADR-015 contract, so they are paired with a structural violation here and
            // covered on their own in b10_control_characters_in_path_are_schema_valid.
            json!({"path":"\u{0000}\u{001b}","extra":1}),
            json!([]),
            json!("string"),
        ];
        let methods = ["model.tool.request", "model.turn.tool_calls"];
        let counts = [
            json!(0),
            json!(1),
            json!(2),
            json!(3),
            json!(-1),
            json!(u64::MAX),
        ];

        let mut rng = B10Rng::new(0x05EE_DB10_u64);
        let started = std::time::Instant::now();
        for iteration in 0..512 {
            let method = *rng.pick(&methods);
            let call = json!({
                "id": rng.pick(&ids),
                "name": rng.pick(&names),
                "arguments": rng.pick(&arg_shapes).clone(),
            });
            let mut event = b6_tool_event(&identity, method, 2, json!([call]));
            event.metadata["tools_executed"] = rng.pick(&counts).clone();
            b10_reject(
                &mut entry,
                &event,
                &format!("seeded hostile event {iteration}"),
            );
        }
        assert!(
            started.elapsed() < std::time::Duration::from_secs(20),
            "seeded hostile corpus must stay bounded"
        );
        assert_eq!(
            b6_snapshot(&entry),
            before,
            "hostile corpus must leave the entry untouched"
        );
    }

    #[test]
    fn b10_valid_control_commits_once_and_adjacent_request_is_isolated() {
        let identity_a = model_identity();
        let identity_b = ModelRequestIdentity {
            request_id: "0f0f0f0f0f0f0f0f0f0f0f0f".into(),
            chat_session_id: "chat_session_b10".into(),
            model_id: identity_a.model_id.clone(),
            submitted_at_unix_ms: identity_a.submitted_at_unix_ms + 7,
            max_tokens: identity_a.max_tokens,
            binding_fingerprint: "c".repeat(64),
        };
        let calls = b6_calls();
        let mut entry_a = b6_entry(&identity_a);
        let mut entry_b = b6_entry(&identity_b);
        b6_submit_prefix(&mut entry_a, &calls);
        let before_b = b6_snapshot(&entry_b);

        // Hostile traffic against A must not touch B.
        let hostile = b6_tool_event(
            &identity_a,
            "model.turn.tool_calls",
            2,
            json!([calls[1].clone(), calls[0].clone()]),
        );
        b10_reject(
            &mut entry_a,
            &hostile,
            "reordered provenance before valid commit",
        );
        assert_eq!(b6_snapshot(&entry_b), before_b);

        let terminal = b6_tool_event(&identity_a, "model.turn.tool_calls", 2, calls.clone());
        validate_and_record_model_event(&mut entry_a, &terminal, "model.turn.tool_calls", 2)
            .expect("valid terminal must commit exactly once");
        assert!(entry_a.terminal_seen);
        let after_commit = b6_snapshot(&entry_a);

        // Replay of the same accepted terminal must be rejected without mutation.
        b10_reject(&mut entry_a, &terminal, "terminal replay");
        assert_eq!(b6_snapshot(&entry_a), after_commit);
        assert_eq!(b6_snapshot(&entry_b), before_b, "adjacent request mutated");

        // B still rejects A's provenance.
        let stolen = b6_tool_event(&identity_b, "model.turn.tool_calls", 0, calls);
        b10_reject(&mut entry_b, &stolen, "cross-request provenance theft");
    }

    #[test]
    fn b10_control_characters_in_path_are_schema_valid_at_the_rust_boundary() {
        // ADR-015 freezes the per-tool schema as "path is a string"; the control plane
        // deliberately does not sanitize path contents, because workspace containment is
        // enforced downstream. This test pins that boundary so a future change is explicit.
        // The downstream NUL handling gap found by the B10 corpus is fixed in
        // modules/tool_execution_ru.py, not here.
        let identity = model_identity();
        for path in ["a\u{0000}b.txt", "a\u{001b}[31m.txt", "\u{202e}txt.exe"] {
            let mut entry = b10_entry(&identity);
            let call = b10_read_call("call_001", json!({ "path": path }));
            let event = b6_tool_event(&identity, "model.tool.request", 0, json!([call.clone()]));
            validate_and_record_model_event(&mut entry, &event, "model.tool.request", 0)
                .expect("path strings are schema-valid regardless of control characters");
            assert_eq!(entry.intermediate_tool_calls, vec![call]);
        }
    }
}
