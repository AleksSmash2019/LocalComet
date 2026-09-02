use crate::approval::canonical_input_digest;
use crate::approval_commands::ApprovalState;
use crate::files::SelectedFilesManager;
use crate::ipc;
use crate::managed_runtime::ManagedRuntimeSupervisor;
use crate::project_intelligence::{try_build_context_manifest_bound, ContextManifest};
use crate::supervisor::{DesktopSidecarSupervisor, SidecarFrameRouter};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager, State};

pub const DESKTOP_STATUS_BRIDGE_VERSION: &str = "v7.0.5";
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
pub const DEFAULT_MODEL_SEED: u32 = 42;
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
const TOOL_CALL_TIMEOUT: Duration = Duration::from_secs(30);
// Real Computer Use may spend tens of seconds in UIA/native readback before
// returning its verified envelope. Keep this aligned with the managed frontend
// first-token watchdog while retaining the shorter bound for ordinary tools.
const COMPUTER_USE_TOOL_CALL_TIMEOUT: Duration = Duration::from_secs(180);
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
    "skills.invoke",
    "system.time",
];

const _: () = assert!(REGISTERED_MODEL_TOOLS.len() == 11);

#[derive(Clone, Copy)]
struct ModelToolArgumentSchema {
    required_string_fields: &'static [&'static str],
    optional_string_fields: &'static [&'static str],
    required_array_fields: &'static [&'static str],
    optional_array_fields: &'static [&'static str],
    optional_json_fields: &'static [&'static str],
    // Bounded numeric fields: (name, inclusive min, inclusive max).
    optional_number_fields: &'static [(&'static str, f64, f64)],
    // Bounded integer fields: (name, inclusive min, inclusive max).
    optional_integer_fields: &'static [(&'static str, i64, i64)],
}

fn model_tool_argument_schema(name: &str) -> Option<ModelToolArgumentSchema> {
    match name {
        "files.read" | "files.list" | "files.create_folder" | "files.delete" => {
            Some(ModelToolArgumentSchema {
                required_string_fields: &["path"],
                optional_string_fields: &[],
                required_array_fields: &[],
                optional_array_fields: &[],
                optional_json_fields: &[],
                optional_number_fields: &[],
                optional_integer_fields: &[],
            })
        }
        "files.write" => Some(ModelToolArgumentSchema {
            required_string_fields: &["path", "content"],
            optional_string_fields: &[],
            required_array_fields: &[],
            optional_array_fields: &[],
            optional_json_fields: &[],
            optional_number_fields: &[],
            optional_integer_fields: &[],
        }),
        "shell" => Some(ModelToolArgumentSchema {
            required_string_fields: &["command"],
            optional_string_fields: &[],
            required_array_fields: &[],
            optional_array_fields: &[],
            optional_json_fields: &[],
            optional_number_fields: &[],
            optional_integer_fields: &[],
        }),
        "computer_use" => Some(ModelToolArgumentSchema {
            required_string_fields: &["action"],
            optional_string_fields: &["text", "target", "url", "goal"],
            required_array_fields: &[],
            optional_array_fields: &["coordinate"],
            optional_json_fields: &[],
            // Canonical bounded wait: one format (seconds, 0.1..=30.0)
            // shared by the intent parser, this schema, and the executor.
            optional_number_fields: &[("seconds", 0.1, 30.0)],
            optional_integer_fields: &[("max_steps", 1, 8)],
        }),
        "skills.invoke" => Some(ModelToolArgumentSchema {
            required_string_fields: &["skill_id"],
            optional_string_fields: &[],
            required_array_fields: &["permissions"],
            optional_array_fields: &[],
            optional_json_fields: &["arguments"],
            optional_number_fields: &[],
            optional_integer_fields: &[],
        }),
        "web.search" => Some(ModelToolArgumentSchema {
            required_string_fields: &["query"],
            optional_string_fields: &[],
            required_array_fields: &[],
            optional_array_fields: &[],
            optional_json_fields: &[],
            optional_number_fields: &[],
            optional_integer_fields: &[],
        }),
        "web.fetch" => Some(ModelToolArgumentSchema {
            required_string_fields: &["url"],
            optional_string_fields: &[],
            required_array_fields: &[],
            optional_array_fields: &[],
            optional_json_fields: &[],
            optional_number_fields: &[],
            optional_integer_fields: &[],
        }),
        "system.time" => Some(ModelToolArgumentSchema {
            required_string_fields: &[],
            optional_string_fields: &[],
            required_array_fields: &[],
            optional_array_fields: &[],
            optional_json_fields: &[],
            optional_number_fields: &[],
            optional_integer_fields: &[],
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
            && !schema.optional_json_fields.contains(&key.as_str())
            && !schema
                .optional_number_fields
                .iter()
                .any(|(field, _, _)| *field == key.as_str())
            && !schema
                .optional_integer_fields
                .iter()
                .any(|(field, _, _)| *field == key.as_str())
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
    for field in schema.required_array_fields {
        match object.get(*field) {
            None => {
                let message = format!("tool {name} missing required argument field {field}");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
            Some(Value::Array(_)) => {}
            Some(_) => {
                let message = format!("tool {name} argument field {field} must be an array");
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
    for field in schema.optional_json_fields {
        if let Some(val) = object.get(*field) {
            if !val.is_object() && !val.is_array() {
                let message =
                    format!("tool {name} argument field {field} must be an object or array");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    for (field, min, max) in schema.optional_number_fields {
        if let Some(val) = object.get(*field) {
            let Some(number) = val.as_f64() else {
                let message = format!("tool {name} argument field {field} must be a number");
                return Err(BridgeError::new("protocol_mismatch", &message));
            };
            if !(*min..=*max).contains(&number) || number.is_nan() {
                let message =
                    format!("tool {name} argument field {field} must be within {min}..={max}");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    for (field, min, max) in schema.optional_integer_fields {
        if let Some(val) = object.get(*field) {
            let Some(integer) = val.as_i64() else {
                let message = format!("tool {name} argument field {field} must be an integer");
                return Err(BridgeError::new("protocol_mismatch", &message));
            };
            if !(*min..=*max).contains(&integer) {
                let message =
                    format!("tool {name} argument field {field} must be within {min}..={max}");
                return Err(BridgeError::new("protocol_mismatch", &message));
            }
        }
    }
    if name == "computer_use" && object.get("action").and_then(Value::as_str) == Some("task") {
        let valid_goal = object
            .get("goal")
            .and_then(Value::as_str)
            .is_some_and(|goal| !goal.trim().is_empty() && goal.chars().count() <= 1200);
        if !valid_goal {
            return Err(BridgeError::new(
                "protocol_mismatch",
                "tool computer_use task requires a non-empty goal of at most 1200 characters",
            ));
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
            | Self::KnowledgeReviewDecisionCreate => Duration::from_secs(5),
            Self::ToolCall => TOOL_CALL_TIMEOUT,
            Self::ModelManagedAttach => MODEL_ATTACH_TIMEOUT,
            Self::ModelManagedDetach => MODEL_DETACH_TIMEOUT,
            Self::KnowledgeTurnPreview => Duration::from_secs(15),
            _ => REQUEST_TIMEOUT,
        }
    }
}

fn request_timeout_for_payload(method: ControlPlaneMethod, payload: &Value) -> Duration {
    if method == ControlPlaneMethod::ToolCall
        && payload.get("tool").and_then(Value::as_str) == Some("computer_use")
    {
        COMPUTER_USE_TOOL_CALL_TIMEOUT
    } else {
        method.timeout()
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

/// Versioned wire schema for every Tauri command rejection (INV-ERR-001).
/// The frontend normalizes arbitrary rejection values into this shape; a
/// rejection must never degrade into `[object Object]` user-visible text.
pub const ERROR_ENVELOPE_SCHEMA: &str = "localcomet.error.v1";

/// Monotonic correlation suffix so every typed error carries a diagnostic id
/// without randomness or wall-clock-only ambiguity.
static ERROR_CORRELATION_COUNTER: AtomicU64 = AtomicU64::new(0);

fn next_error_correlation_id() -> String {
    let seq = ERROR_CORRELATION_COUNTER.fetch_add(1, Ordering::Relaxed);
    let millis = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|since| since.as_millis())
        .unwrap_or(0);
    format!("err_{millis:012x}_{seq:04x}")
}

#[derive(Clone, Debug, Serialize)]
pub struct BridgeError {
    /// Boxed so `Result<T, BridgeError>` stays under the clippy
    /// `result_large_err` budget; `serde(flatten)` keeps the wire shape flat.
    #[serde(flatten)]
    inner: Box<ErrorInner>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ErrorInner {
    pub schema: &'static str,
    pub code: String,
    pub message: String,
    pub retryable: bool,
    pub phase: &'static str,
    pub correlation_id: String,
    pub details: Value,
}

impl std::ops::Deref for BridgeError {
    type Target = ErrorInner;

    fn deref(&self) -> &Self::Target {
        &self.inner
    }
}

impl BridgeError {
    pub(crate) fn new(code: &str, message: &str) -> Self {
        Self {
            inner: Box::new(ErrorInner {
                schema: ERROR_ENVELOPE_SCHEMA,
                code: sanitize_text(code, 64),
                message: sanitize_text(message, 256),
                retryable: false,
                phase: "dispatch",
                correlation_id: next_error_correlation_id(),
                details: Value::Null,
            }),
        }
    }

    fn unavailable(message: &str) -> Self {
        Self::new("sidecar_unavailable", message).with_retryable(true)
    }

    /// Marks the failure as transient. Callers own retry policy; this flag is
    /// informational and never triggers an automatic retry loop.
    pub(crate) fn with_retryable(mut self, retryable: bool) -> Self {
        self.inner.retryable = retryable;
        self
    }

    /// Binds the envelope to the pipeline stage that produced it
    /// (e.g. `tool_dispatch`, `intent_dispatch`, `coding_dispatch`).
    pub(crate) fn with_phase(mut self, phase: &'static str) -> Self {
        self.inner.phase = phase;
        self
    }

    /// Prefers an explicit caller-supplied correlation id (request/action);
    /// falls back to the generated one when absent or empty.
    pub(crate) fn with_correlation(mut self, id: Option<&str>) -> Self {
        if let Some(id) = id {
            let bounded = sanitize_text(id, 64);
            if !bounded.is_empty() {
                self.inner.correlation_id = bounded;
            }
        }
        self
    }

    /// Attaches ONE bounded, redacted detail entry. Values are serialized and
    /// passed through `sanitize_text`, so secrets/tracebacks never survive and
    /// raw payloads cannot exceed the bounded size.
    pub(crate) fn with_detail(mut self, key: &str, value: &Value) -> Self {
        const MAX_DETAIL_JSON_CHARS: usize = 256;
        const MAX_DETAIL_ENTRIES: usize = 8;
        if !key.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') || key.len() > 32 {
            return self;
        }
        let existing = std::mem::take(&mut self.inner.details);
        let mut map = match existing {
            Value::Object(map) => map,
            _ => serde_json::Map::new(),
        };
        if !map.contains_key(key) && map.len() < MAX_DETAIL_ENTRIES {
            let serialized =
                serde_json::to_string(value).unwrap_or_else(|_| "<unserializable>".into());
            map.insert(
                key.to_owned(),
                Value::String(sanitize_text(&serialized, MAX_DETAIL_JSON_CHARS)),
            );
        }
        self.inner.details = Value::Object(map);
        self
    }
}

#[cfg(test)]
mod error_envelope_tests {
    use super::*;

    #[test]
    fn envelope_carries_versioned_schema_and_stable_fields() {
        let error = BridgeError::new("dispatch_failed", "tool dispatch rejected");
        assert_eq!(error.schema, "localcomet.error.v1");
        assert_eq!(error.code, "dispatch_failed");
        assert_eq!(error.message, "tool dispatch rejected");
        assert!(!error.retryable);
        assert_eq!(error.phase, "dispatch");
        assert!(error.correlation_id.starts_with("err_"));
        assert_eq!(error.details, Value::Null);
    }

    #[test]
    fn envelope_preserves_cyrillic_message_through_wire_roundtrip() {
        let error = BridgeError::new("dispatch_failed", "Открой блокнот: отказано");
        let wire = serde_json::to_string(&error).expect("envelope must serialize");
        assert!(
            wire.contains("Открой блокнот: отказано"),
            "cyrillic message lost on the wire: {wire}"
        );
        assert!(!wire.contains('\u{fffd}'), "replacement char in wire bytes");
        // serde_json never escapes to ANSI/CP1251 mojibake; non-ASCII stays UTF-8.
        let parsed: Value = serde_json::from_str(&wire).expect("wire must parse");
        assert_eq!(parsed["schema"], ERROR_ENVELOPE_SCHEMA);
        assert_eq!(parsed["message"], "Открой блокнот: отказано");
    }

    #[test]
    fn correlation_ids_differ_between_errors() {
        let first = BridgeError::new("a", "a").correlation_id.clone();
        let second = BridgeError::new("a", "a").correlation_id.clone();
        assert_ne!(first, second, "correlation ids must be unique per error");
    }

    #[test]
    fn with_correlation_prefers_request_id_and_bounds_input() {
        let error = BridgeError::new("x", "x")
            .with_correlation(Some("req_abcdef123456"))
            .with_phase("tool_dispatch");
        assert_eq!(error.correlation_id, "req_abcdef123456");
        assert_eq!(error.phase, "tool_dispatch");
        let long_id = "r".repeat(500);
        let bounded = BridgeError::new("x", "x").with_correlation(Some(&long_id));
        assert!(bounded.correlation_id.len() <= 64);
        // Empty correlation falls back to the generated id.
        let fallback = BridgeError::new("x", "x").with_correlation(Some(""));
        assert!(fallback.correlation_id.starts_with("err_"));
        // None also keeps the generated id.
        let none = BridgeError::new("x", "x").with_correlation(None);
        assert!(none.correlation_id.starts_with("err_"));
    }

    #[test]
    fn detail_is_bounded_and_redacts_secret_like_values() {
        let secret = json!("sk-AbCd1234567890");
        let huge = json!("П".repeat(4000));
        let error = BridgeError::new("x", "x")
            .with_detail("token", &secret)
            .with_detail("payload", &huge);
        let serialized = serde_json::to_string(&error.details).expect("details serialize");
        assert!(!serialized.contains("sk-AbCd1234567890"), "secret leaked");
        assert!(
            serialized.len() <= 512,
            "details not bounded: {}",
            serialized.len()
        );
        // Invalid keys are dropped.
        let dropped = BridgeError::new("x", "x").with_detail("bad key!", &json!("v"));
        assert_eq!(dropped.details, Value::Null);
    }

    #[test]
    fn sanitize_text_truncates_cyrillic_on_char_boundary() {
        let text = "Привет".repeat(100);
        let sanitized = sanitize_text(&text, 7);
        assert_eq!(sanitized, "При"); // cut at char boundary, never mid-codepoint
        assert!(!sanitized.contains('\u{fffd}'));
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
    #[serde(skip_serializing_if = "Option::is_none")]
    project_context_manifest: Option<ContextManifest>,
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

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
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
pub(crate) struct AssistantContext {
    application: AssistantApplicationContext,
    conversation: AssistantConversationContext,
    capabilities: AssistantCapabilities,
}

impl AssistantContext {
    #[allow(dead_code)]
    pub(crate) fn trusted(
        locale: &str,
        selected_files_context_available: bool,
        permissions: Option<&AgentPermissions>,
    ) -> Result<Self, BridgeError> {
        Self::trusted_with_project_context(
            locale,
            selected_files_context_available,
            permissions,
            None,
        )
    }

    pub(crate) fn trusted_with_project_context(
        locale: &str,
        selected_files_context_available: bool,
        permissions: Option<&AgentPermissions>,
        project_context_manifest: Option<ContextManifest>,
    ) -> Result<Self, BridgeError> {
        if !matches!(
            locale,
            "ru" | "en"
                | "es"
                | "de"
                | "fr"
                | "pt-BR"
                | "it"
                | "zh-CN"
                | "ja"
                | "ko"
                | "tr"
                | "uk"
                | "pl"
                | "ar"
        ) {
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
                project_context_available: project_context_manifest.is_some(),
                selected_files_context_available,
                project_context_manifest,
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
                        t.push("skills.invoke".into());
                    }
                    t
                },
            },
        })
    }
}

fn build_project_context_manifest(
    approval: &ApprovalState,
    request_id: &str,
    prompt: &str,
) -> Result<Option<ContextManifest>, BridgeError> {
    let Some((canonical_path, workspace_digest)) = approval.workspace_identity() else {
        return Ok(None);
    };
    let task_keywords: Vec<String> = prompt
        .split_whitespace()
        .filter(|word| {
            word.len() <= 128
                && word.chars().any(|character| character.is_alphanumeric())
                && !word.chars().any(|character| character.is_control())
        })
        .take(32)
        .map(|word| {
            word.trim_matches(|character: char| !character.is_alphanumeric())
                .to_string()
        })
        .filter(|word| !word.is_empty())
        .collect();
    let manifest = try_build_context_manifest_bound(
        std::path::Path::new(&canonical_path),
        &workspace_digest,
        request_id,
        None,
        &task_keywords,
        crate::project_intelligence::MAX_CONTEXT_BUDGET,
    )
    .map_err(|error| BridgeError::new("context_manifest_invalid", &error.to_string()))?;
    Ok(Some(manifest))
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
pub(crate) struct ModelRequestIdentity {
    pub(crate) request_id: String,
    pub(crate) chat_session_id: String,
    pub(crate) model_id: String,
    pub(crate) submitted_at_unix_ms: u64,
    pub(crate) max_tokens: u16,
    pub(crate) seed: u32,
    pub(crate) binding_fingerprint: String,
}

#[derive(Debug)]
struct WatchdogState {
    cancelled: bool,
    last_activity: Instant,
}

#[derive(Debug)]
struct ModelRequestWatchdog {
    state: Mutex<WatchdogState>,
    wake: Condvar,
}

impl ModelRequestWatchdog {
    fn new() -> Self {
        Self {
            state: Mutex::new(WatchdogState {
                cancelled: false,
                last_activity: Instant::now(),
            }),
            wake: Condvar::new(),
        }
    }

    /// BUG-4: every model event (streaming delta included) proves the request
    /// is alive, so the deadline slides forward. The watchdog fires only on
    /// genuine inactivity, not on total request lifetime — a legal long
    /// generation at ~15-20 tok/s with --n-predict 4096 (~205-270 s) is no
    /// longer killed by the fixed 125 s bound.
    fn touch(&self) {
        let mut state = self.state.lock().expect("model request watchdog poisoned");
        state.last_activity = Instant::now();
        self.wake.notify_all();
    }

    fn cancel(&self) {
        let mut state = self.state.lock().expect("model request watchdog poisoned");
        state.cancelled = true;
        self.wake.notify_all();
    }

    /// Returns true when the request must be failed: either cancelled
    /// (entry removed / terminal) or inactive for a full `timeout` since the
    /// last activity. `touch()` moves `last_activity` forward, so the waiter
    /// recomputes its remaining sleep on every wake-up.
    fn wait_for_timeout(&self, timeout: Duration) -> bool {
        let mut state = self.state.lock().expect("model request watchdog poisoned");
        loop {
            if state.cancelled {
                return false;
            }
            let idle = state.last_activity.elapsed();
            if idle >= timeout {
                return true;
            }
            let remaining = timeout - idle;
            let (guard, wait_result) = self
                .wake
                .wait_timeout(state, remaining)
                .expect("model request watchdog wait poisoned");
            state = guard;
            if state.cancelled {
                return false;
            }
            let _ = wait_result;
        }
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
    effort: String,
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
            watchdog: Arc::new(ModelRequestWatchdog::new()),
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
            effort: "off".to_owned(),
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
#[allow(dead_code)]
pub(crate) fn model_turn_wire_payload(
    identity: &ModelRequestIdentity,
    prompt: &str,
    assistant_context: &AssistantContext,
    messages: &[Value],
) -> Value {
    model_turn_wire_payload_with_effort(identity, prompt, assistant_context, messages, "off")
}

pub(crate) fn model_turn_wire_payload_with_effort(
    identity: &ModelRequestIdentity,
    prompt: &str,
    assistant_context: &AssistantContext,
    messages: &[Value],
    effort: &str,
) -> Value {
    json!({
        "request_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "seed": identity.seed,
        "effort": effort,
        "prompt": prompt,
        "assistant_context": assistant_context,
        "binding_fingerprint": identity.binding_fingerprint,
        "messages": messages,
    })
}

/// Digest over every dispatched `model.turn.start` field, `assistant_context`
/// (application, conversation and the capability/tool grant) included.
pub(crate) fn model_turn_wire_digest(payload: &Value) -> [u8; 32] {
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
            watchdog: Arc::new(ModelRequestWatchdog::new()),
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
    /// Confirmed managed bindings per runtime instance, most recent last
    /// (runtime_instance_id -> composed binding fingerprint the user
    /// confirmed through model.binding.set). Turns must present exactly this
    /// fingerprint for the active runtime instance (P0-3).
    confirmed_managed_bindings: Mutex<Vec<(String, String)>>,
    request_counter: AtomicU64,
    warnings: Mutex<Vec<String>>,
}

/// Bounded memory of confirmed managed bindings: a fresh instance after a
/// restart requires a fresh confirmation, so stale entries age out quickly.
const MAX_CONFIRMED_MANAGED_BINDINGS: usize = 8;

impl ControlPlaneBridge {
    pub fn new(supervisor: Arc<DesktopSidecarSupervisor>, app: AppHandle) -> Self {
        validate_bridge_contract();
        Self {
            supervisor,
            app,
            registry: Mutex::new(RequestRegistry::default()),
            model_requests: Arc::new(Mutex::new(ModelRequestRegistry::default())),
            knowledge_admissions: Arc::new(Mutex::new(HashMap::new())),
            confirmed_managed_bindings: Mutex::new(Vec::new()),
            request_counter: AtomicU64::new(1),
            warnings: Mutex::new(Vec::new()),
        }
    }

    /// Records the composed binding fingerprint confirmed for a managed
    /// runtime instance. Called by the model_binding_set command after the
    /// sidecar accepted the binding.
    pub(crate) fn record_managed_binding(
        &self,
        runtime_instance_id: &str,
        binding_fingerprint: &str,
    ) {
        let mut bindings = self
            .confirmed_managed_bindings
            .lock()
            .expect("confirmed managed bindings poisoned");
        bindings.retain(|(instance, _)| instance != runtime_instance_id);
        bindings.push((
            runtime_instance_id.to_owned(),
            binding_fingerprint.to_owned(),
        ));
        let excess = bindings
            .len()
            .saturating_sub(MAX_CONFIRMED_MANAGED_BINDINGS);
        bindings.drain(..excess);
    }

    /// Diagnostic snapshot of routing warnings (bounded, sanitized).
    #[cfg(test)]
    pub(crate) fn warnings_snapshot(&self) -> Vec<String> {
        self.warnings
            .lock()
            .expect("control-plane warning lock poisoned")
            .clone()
    }

    /// Returns the composed binding fingerprint the user confirmed for the
    /// given runtime instance, if any.
    pub(crate) fn confirmed_managed_binding(&self, runtime_instance_id: &str) -> Option<String> {
        self.confirmed_managed_bindings
            .lock()
            .expect("confirmed managed bindings poisoned")
            .iter()
            .rev()
            .find(|(instance, _)| instance == runtime_instance_id)
            .map(|(_, fingerprint)| fingerprint.clone())
    }

    pub fn request(
        &self,
        method: ControlPlaneMethod,
        payload: Value,
    ) -> Result<Value, BridgeError> {
        let timeout = request_timeout_for_payload(method, &payload);
        self.request_with_timeout(method, payload, timeout)
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

    pub(crate) fn reserve_model_turn(
        self: &Arc<Self>,
        identity: &ModelRequestIdentity,
        permitted_tool_names: Vec<String>,
        wire_digest: [u8; 32],
        effort: &str,
    ) -> Result<(), BridgeError> {
        let watchdog = {
            let mut registry = self
                .model_requests
                .lock()
                .expect("model request registry poisoned");
            let watchdog = registry.insert(identity.clone(), permitted_tool_names)?;
            if let Some(entry) = registry.entries.get_mut(&identity.request_id) {
                entry.effort = effort.to_owned();
            }
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

    pub(crate) fn request_model_turn_reserved(
        self: &Arc<Self>,
        identity: ModelRequestIdentity,
        prompt: String,
        assistant_context: AssistantContext,
        messages: Vec<Value>,
        effort: String,
    ) -> Result<Value, BridgeError> {
        let payload = model_turn_wire_payload_with_effort(
            &identity,
            &prompt,
            &assistant_context,
            &messages,
            &effort,
        );
        let response = match self.request_reserved_model_start(&identity.request_id, payload) {
            Ok(response) => response,
            Err(error) => {
                self.discard_unaccepted_model_request(&identity.request_id);
                return Err(error);
            }
        };
        let (provider_id, harness_id) =
            match validate_model_acceptance(&response, &identity, &effort) {
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
            &effort,
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
        if snapshot.running && snapshot.saw_python_hello && snapshot.saw_health_ok {
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
    assert_eq!(
        actual, CONTROL_PLANE_METHOD_COUNT,
        "control-plane method vocabulary count mismatch"
    );
}

/// Turn dispatch gate: the managed model must be Ready and the turn's
/// binding fingerprint must equal the composed fingerprint the user confirmed
/// through model.binding.set for the active runtime instance.
pub(crate) fn dispatch_gate_for_model_turn(
    runtime: &Arc<ManagedRuntimeSupervisor>,
    bridge: &ControlPlaneBridge,
    model_id: &str,
    binding_fingerprint: &str,
) -> Result<(), BridgeError> {
    let (runtime_instance_id, _attach_fingerprint) = runtime.active_runtime_identity(model_id)?;
    let confirmed = bridge
        .confirmed_managed_binding(&runtime_instance_id)
        .ok_or_else(|| {
            BridgeError::new(
                "binding_mismatch",
                "no confirmed binding for the active managed runtime",
            )
        })?;
    if confirmed != binding_fingerprint {
        return Err(BridgeError::new(
            "binding_mismatch",
            "turn binding fingerprint does not match the confirmed managed binding",
        ));
    }
    Ok(())
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
    tauri::async_runtime::spawn_blocking(move || {
        let response = state.request(ControlPlaneMethod::ModelBindingSet, python_payload)?;
        // Remember the composed fingerprint the user confirmed for this
        // runtime instance so turn dispatch can bind turns to it (P0-3).
        if response.get("provider_id").and_then(Value::as_str) == Some("managed-llama-cpp") {
            if let (Some(instance_id), Some(binding_fingerprint)) = (
                response.get("runtime_instance_id").and_then(Value::as_str),
                response.get("binding_fingerprint").and_then(Value::as_str),
            ) {
                state.record_managed_binding(instance_id, binding_fingerprint);
            }
        }
        Ok(response)
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
    approval: State<'_, ApprovalState>,
    request_id: String,
    chat_session_id: String,
    model_id: String,
    submitted_at_unix_ms: u64,
    max_tokens: u16,
    seed: u32,
    effort: String,
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
    ensure_effort(&effort)?;
    if submitted_at_unix_ms == 0 || submitted_at_unix_ms > 9_007_199_254_740_991 {
        return Err(BridgeError::new(
            "invalid_payload",
            "submitted_at_unix_ms is invalid",
        ));
    }
    // Raised from 512: the managed runtime now runs --n-predict 4096 and the
    // external OpenAI-compatible provider (LM Studio) has no such ceiling.
    if seed != DEFAULT_MODEL_SEED {
        return Err(BridgeError::new(
            "invalid_payload",
            "seed must equal the fixed model seed",
        ));
    }
    if seed > i32::MAX as u32 {
        return Err(BridgeError::new(
            "invalid_payload",
            "seed is outside the allowed range",
        ));
    }
    if !(1..=8192).contains(&max_tokens) {
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
    let project_context_manifest = build_project_context_manifest(&approval, &request_id, &prompt)?;
    let assistant_context = AssistantContext::trusted_with_project_context(
        &locale,
        file_context_report.is_some(),
        Some(&agent_permissions),
        project_context_manifest,
    )?;
    approval.set_agent_permissions(agent_permissions.clone());
    ensure_fingerprint(&binding_fingerprint)?;
    let identity = ModelRequestIdentity {
        request_id,
        chat_session_id,
        model_id,
        submitted_at_unix_ms,
        max_tokens,
        seed,
        binding_fingerprint,
    };
    // The reservation is bound to the digest of the exact wire payload it
    // authorizes, assistant_context (and therefore the capability/tool grant that
    // drives permitted_tool_names) included. Dispatch re-derives this digest.
    let wire_digest = model_turn_wire_digest(&model_turn_wire_payload_with_effort(
        &identity,
        &prompt,
        &assistant_context,
        &messages,
        &effort,
    ));
    state.reserve_model_turn(
        &identity,
        assistant_context.capabilities.tools.clone(),
        wire_digest,
        &effort,
    )?;
    let cleanup_state = Arc::clone(&state);
    let cleanup_request_id = identity.request_id.clone();
    let worker_state = Arc::clone(&state);
    let worker_runtime = Arc::clone(&runtime);
    let mut response = match tauri::async_runtime::spawn_blocking(move || {
        // The turn is only dispatched when the model is ready AND the turn's
        // binding fingerprint equals the composed fingerprint the user
        // confirmed for the ACTIVE runtime instance (P0-3). A stale
        // fingerprint from a previous instance or harness is rejected
        // Rust-side before reaching the sidecar.
        if let Err(error) = dispatch_gate_for_model_turn(
            &worker_runtime,
            &worker_state,
            &identity.model_id,
            &identity.binding_fingerprint,
        ) {
            worker_state
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&identity.request_id);
            return Err(error);
        }
        worker_state.request_model_turn_reserved(
            identity,
            prompt,
            assistant_context,
            messages,
            effort,
        )
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
    expected_effort: &str,
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
        "seed",
        "binding_fingerprint",
        "state",
        "effort",
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
        || string("effort")? != expected_effort
        || object.get("submitted_at_unix_ms").and_then(Value::as_u64)
            != Some(expected.submitted_at_unix_ms)
        || object.get("max_tokens").and_then(Value::as_u64) != Some(u64::from(expected.max_tokens))
        || object.get("seed").and_then(Value::as_u64) != Some(u64::from(expected.seed))
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
    effort: &str,
) -> Value {
    json!({
        "request_id": identity.request_id,
        "turn_id": identity.request_id,
        "chat_session_id": identity.chat_session_id,
        "model_id": identity.model_id,
        "submitted_at_unix_ms": identity.submitted_at_unix_ms,
        "max_tokens": identity.max_tokens,
        "seed": identity.seed,
        "binding_fingerprint": identity.binding_fingerprint,
        "state": "Accepted",
        "effort": effort,
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
    let seed = metadata
        .get("seed")
        .and_then(Value::as_u64)
        .and_then(|value| u32::try_from(value).ok())
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model event seed missing"))?;
    let binding_fingerprint = string("binding_fingerprint")?;
    let provider_id = string("provider_id")?;
    let harness_id = string("harness_id")?;
    if ensure_request_id(request_id).is_err()
        || ensure_chat_session_id(chat_session_id).is_err()
        || ensure_model_id(model_id).is_err()
        || ensure_fingerprint(binding_fingerprint).is_err()
        || submitted_at_unix_ms == 0
        || submitted_at_unix_ms > 9_007_199_254_740_991
        || !(1..=8192).contains(&max_tokens)
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
            seed,
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
    let telemetry = match validate_model_event_metadata(entry, event, method) {
        Ok(telemetry) => telemetry,
        Err(error) => {
            let trace_path = std::env::temp_dir().join("localcomet-rust-model-event-error.txt");
            let trace = format!(
                "method={method}\ncode={}\nmessage={}\nentry_generated_bytes={}\nevent_metadata={}\n",
                error.code,
                error.message,
                entry.generated_bytes,
                event.metadata,
            );
            let _ = std::fs::write(trace_path, trace);
            return Err(error);
        }
    };
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

    // BUG-4: streaming deltas and lifecycle events prove the request is alive;
    // slide the inactivity deadline forward on every event.
    entry.watchdog.touch();
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
        "seed",
        "effort",
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
            && key != "stream_channel"
            && !KNOWLEDGE_KEYS.contains(&key.as_str())
            && !(is_tool_event && key == "tool_calls")
    }) || BASE_KEYS.iter().any(|key| !metadata.contains_key(*key))
    {
        return Err(BridgeError::new(
            "protocol_mismatch",
            "model event metadata shape mismatch",
        ));
    }
    if let Some(channel) = metadata.get("stream_channel") {
        if !matches!(channel.as_str(), Some("content") | Some("reasoning")) {
            return Err(BridgeError::new(
                "protocol_mismatch",
                "model event stream channel mismatch",
            ));
        }
    }
    let effort = metadata
        .get("effort")
        .and_then(Value::as_str)
        .ok_or_else(|| BridgeError::new("protocol_mismatch", "model effort missing"))?;
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
        && metadata.get("seed").and_then(Value::as_u64) == Some(u64::from(entry.identity.seed))
        && metadata.get("binding_fingerprint").and_then(Value::as_str)
            == Some(entry.identity.binding_fingerprint.as_str());
    if !base_identity_matches
        || ensure_effort(effort).is_err()
        || effort != entry.effort
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
    if let Some(effort) = metadata.get("effort") {
        projected.insert("effort".into(), effort.clone());
    }
    if let Some(channel) = metadata.get("stream_channel") {
        projected.insert("stream_channel".into(), channel.clone());
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
                "seed",
                "effort",
                "prompt",
                "assistant_context",
                "binding_fingerprint",
                "messages",
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
    const OPTIONAL: [&str; 4] = ["grant_id", "grant", "request_id", "action_id"];
    const GRANT_KEYS: [&str; 6] = [
        "grant_id",
        "tool",
        "input_digest",
        "workspace",
        "session",
        "expires_at_unix_ms",
    ];
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
    if let Some(request_id) = object.get("request_id") {
        let Some(request_id) = request_id.as_str() else {
            return Err(BridgeError::new(
                "invalid_payload",
                "request_id must be a string",
            ));
        };
        ensure_request_id(request_id)?;
    }
    if let Some(action_id) = object.get("action_id") {
        let Some(action_id) = action_id.as_str() else {
            return Err(BridgeError::new(
                "invalid_payload",
                "action_id must be a string",
            ));
        };
        if !crate::cu_broker::valid_action_id(action_id) {
            return Err(BridgeError::new("invalid_payload", "action_id is invalid"));
        }
    }
    if let Some(grant) = object.get("grant") {
        let Some(grant_object) = grant.as_object() else {
            return Err(BridgeError::new(
                "invalid_payload",
                "grant must be an object",
            ));
        };
        if grant_object
            .keys()
            .any(|key| !GRANT_KEYS.contains(&key.as_str()))
        {
            return Err(BridgeError::new(
                "invalid_payload",
                "unexpected grant shape",
            ));
        }
        for key in &GRANT_KEYS[..5] {
            let present_nonempty = grant_object
                .get(*key)
                .and_then(Value::as_str)
                .is_some_and(|value| !value.is_empty());
            if !present_nonempty {
                return Err(BridgeError::new(
                    "invalid_payload",
                    &format!("grant.{key} must be a non-empty string"),
                ));
            }
        }
        let expires_valid = grant_object
            .get("expires_at_unix_ms")
            .and_then(Value::as_u64)
            .is_some_and(|value| value > 0);
        if !expires_valid {
            return Err(BridgeError::new(
                "invalid_payload",
                "grant.expires_at_unix_ms must be a positive integer",
            ));
        }
        if let (Some(outer), Some(inner)) = (
            payload.get("grant_id").and_then(Value::as_str),
            grant_object.get("grant_id").and_then(Value::as_str),
        ) {
            if outer != inner {
                return Err(BridgeError::new(
                    "invalid_payload",
                    "grant_id must match the grant envelope",
                ));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
pub(crate) fn build_tool_call_request(
    tool: &str,
    input: &Value,
    workspace: &str,
    workspace_digest: &str,
    session: &str,
    grant: Option<&crate::approval::ExecutionGrant>,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    build_tool_call_request_with_correlation(
        tool,
        input,
        workspace,
        workspace_digest,
        session,
        grant,
        None,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn build_tool_call_request_with_correlation(
    tool: &str,
    input: &Value,
    workspace: &str,
    workspace_digest: &str,
    session: &str,
    grant: Option<&crate::approval::ExecutionGrant>,
    request_id: Option<&str>,
    action_id: Option<&str>,
) -> Result<(ControlPlaneMethod, Value), BridgeError> {
    let mut payload = json!({
        "tool": tool,
        "input": input,
        "workspace": workspace,
        "workspace_digest": workspace_digest,
        "session": session,
    });
    if let Some(request_id) = request_id.filter(|value| !value.is_empty()) {
        payload["request_id"] = json!(request_id);
    }
    if let Some(action_id) = action_id.filter(|value| !value.is_empty()) {
        payload["action_id"] = json!(action_id);
    }
    if let Some(grant) = grant {
        payload["grant_id"] = json!(grant.grant_id);
        payload["grant"] = json!({
            "grant_id": grant.grant_id,
            "tool": grant.tool,
            "input_digest": grant.input_digest_hex(),
            "workspace": grant.workspace,
            "session": grant.session,
            "expires_at_unix_ms": grant.expires_at_unix_ms(),
        });
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

fn ensure_effort(value: &str) -> Result<(), BridgeError> {
    if matches!(value, "off" | "low" | "medium" | "high") {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "unsupported effort level",
        ))
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
#[path = "control_plane_tests.rs"]
mod tests;
