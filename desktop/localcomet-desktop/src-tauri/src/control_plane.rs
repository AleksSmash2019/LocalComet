use crate::ipc;
use crate::supervisor::{DesktopSidecarSupervisor, SidecarFrameRouter};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager, State};

pub const DESKTOP_STATUS_BRIDGE_VERSION: &str = "v6.84.5.1";
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

const _: () = assert!(HARD_MAX_IN_FLIGHT_REQUESTS >= MAX_IN_FLIGHT_REQUESTS);

const REQUEST_TIMEOUT: Duration = Duration::from_secs(5);
const MOCK_TURN_TIMEOUT: Duration = Duration::from_secs(10);
const CANCEL_TIMEOUT: Duration = Duration::from_secs(5);

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
        }
    }

    fn timeout(self) -> Duration {
        match self {
            Self::TurnStartMock => MOCK_TURN_TIMEOUT,
            Self::TurnCancel => CANCEL_TIMEOUT,
            Self::ModelGatewayProbe | Self::ModelModelsList => Duration::from_secs(8),
            Self::ModelTurnStart
            | Self::ModelTurnCancel
            | Self::ModelManagedAttach
            | Self::ModelManagedDetach
            | Self::KnowledgeTurnDecide
            | Self::KnowledgeReviewDecisionCreate => Duration::from_secs(5),
            Self::KnowledgeTurnPreview => Duration::from_secs(15),
            _ => REQUEST_TIMEOUT,
        }
    }
}

pub const CONTROL_PLANE_METHOD_COUNT: usize = 25;
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
    state: Mutex<PendingState>,
    ready: Condvar,
}

impl PendingRequest {
    fn new(reply_to: String) -> Self {
        Self {
            reply_to,
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
    fn insert(&mut self, request_id: String) -> Result<Arc<PendingRequest>, BridgeError> {
        if self.entries.len() >= MAX_IN_FLIGHT_REQUESTS {
            return Err(BridgeError::new("busy", "request registry is full"));
        }
        if self.entries.contains_key(&request_id) {
            return Err(BridgeError::new(
                "duplicate_message_id",
                "duplicate request id",
            ));
        }
        let pending = Arc::new(PendingRequest::new(request_id.clone()));
        self.entries.insert(request_id, Arc::clone(&pending));
        Ok(pending)
    }

    fn get(&self, request_id: &str) -> Option<Arc<PendingRequest>> {
        self.entries.get(request_id).cloned()
    }

    fn remove(&mut self, request_id: &str) {
        self.entries.remove(request_id);
    }

    fn fail_all(&mut self, error: BridgeError) {
        let pending: Vec<_> = self.entries.drain().map(|(_, pending)| pending).collect();
        for entry in pending {
            finish_pending(&entry, Err(error.clone()));
        }
    }
}

pub struct ControlPlaneBridge {
    supervisor: Arc<DesktopSidecarSupervisor>,
    app: AppHandle,
    registry: Mutex<RequestRegistry>,
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
            request_counter: AtomicU64::new(1),
            warnings: Mutex::new(Vec::new()),
        }
    }

    pub fn request(
        &self,
        method: ControlPlaneMethod,
        payload: Value,
    ) -> Result<Value, BridgeError> {
        self.ensure_ready()?;
        validate_payload_for_method(method, &payload)?;
        let request_id = self.next_request_id();
        let pending = self
            .registry
            .lock()
            .expect("control-plane registry poisoned")
            .insert(request_id.clone())?;
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
        let response = self.wait_for_terminal(method, &request_id, pending)?;
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

    pub fn emit_sidecar_status(&self) {
        let snapshot = self.supervisor.snapshot();
        let event = UiControlPlaneEvent {
            method: "sidecar.status".into(),
            sequence: 0,
            reply_to: "startup".into(),
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
        method: ControlPlaneMethod,
        request_id: &str,
        pending: Arc<PendingRequest>,
    ) -> Result<Value, BridgeError> {
        let deadline = Instant::now() + method.timeout();
        let mut guard = pending.state.lock().expect("pending request poisoned");
        loop {
            if let Some(result) = guard.terminal.take() {
                self.registry
                    .lock()
                    .expect("control-plane registry poisoned")
                    .remove(request_id);
                return result;
            }
            let now = Instant::now();
            if now >= deadline {
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
        self.registry
            .lock()
            .expect("control-plane registry poisoned")
            .fail_all(BridgeError::new(code, message));
    }
}

impl ControlPlaneBridge {
    fn route_frame_inner(&self, frame: &[u8]) -> Result<(), BridgeError> {
        let envelope: Value = serde_json::from_slice(frame)
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
            let run_id = string_field(envelope, "run_id")?;
            ensure_id("run_id", &run_id)?;
            self.emit_event(ui_event_from_envelope(envelope)?);
            return Ok(());
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
pub fn model_gateway_catalog(
    state: State<'_, Arc<ControlPlaneBridge>>,
) -> Result<Value, BridgeError> {
    state.request(ControlPlaneMethod::ModelCatalogGet, json!({}))
}

#[tauri::command]
pub fn model_gateway_probe(
    state: State<'_, Arc<ControlPlaneBridge>>,
    port: u16,
) -> Result<Value, BridgeError> {
    ensure_model_port(port)?;
    state.request(
        ControlPlaneMethod::ModelGatewayProbe,
        json!({ "port": port }),
    )
}

#[tauri::command]
pub fn model_gateway_list_models(
    state: State<'_, Arc<ControlPlaneBridge>>,
    port: u16,
) -> Result<Value, BridgeError> {
    ensure_model_port(port)?;
    state.request(ControlPlaneMethod::ModelModelsList, json!({ "port": port }))
}

#[tauri::command]
pub fn model_binding_set(
    state: State<'_, Arc<ControlPlaneBridge>>,
    provider_id: String,
    harness_id: String,
    port: Option<u16>,
    model_id: String,
    confirmed: bool,
    runtime_instance_id: Option<String>,
) -> Result<Value, BridgeError> {
    ensure_provider(&provider_id)?;
    ensure_harness(&harness_id)?;
    ensure_model_id(&model_id)?;
    if provider_id == "openai-compatible-local" {
        ensure_model_port(port.unwrap_or(0))?;
    } else if let Some(instance_id) = &runtime_instance_id {
        ensure_id("runtime_instance_id", instance_id)?;
    } else {
        return Err(BridgeError::new(
            "invalid_payload",
            "runtime instance is required",
        ));
    }
    if !confirmed {
        return Err(BridgeError::new(
            "invalid_payload",
            "binding confirmation is required",
        ));
    }
    state.request(
        ControlPlaneMethod::ModelBindingSet,
        json!({
            "provider_id": provider_id,
            "harness_id": harness_id,
            "port": port,
            "model_id": model_id,
            "confirmed": true,
            "runtime_instance_id": runtime_instance_id
        }),
    )
}

#[tauri::command]
pub fn model_turn_start(
    state: State<'_, Arc<ControlPlaneBridge>>,
    prompt: String,
    binding_fingerprint: String,
) -> Result<Value, BridgeError> {
    ensure_len("prompt", &prompt, MAX_MODEL_PROMPT_CHARS)?;
    ensure_fingerprint(&binding_fingerprint)?;
    state.request(
        ControlPlaneMethod::ModelTurnStart,
        json!({ "prompt": prompt, "binding_fingerprint": binding_fingerprint }),
    )
}

#[tauri::command]
pub fn model_turn_cancel(
    state: State<'_, Arc<ControlPlaneBridge>>,
    turn_id: String,
) -> Result<Value, BridgeError> {
    ensure_id("turn_id", &turn_id)?;
    state.request(
        ControlPlaneMethod::ModelTurnCancel,
        json!({ "turn_id": turn_id }),
    )
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
        ControlPlaneMethod::ModelTurnStart => {
            ensure_payload_keys(payload, &["prompt", "binding_fingerprint"])
        }
        ControlPlaneMethod::ModelTurnCancel => ensure_payload_keys(payload, &["turn_id"]),
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
        _ => ensure_payload_keys(payload, &[]),
    }
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
    if value.len() == 24
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
            | "model.turn.failed"
    )
}

fn allowed_model_event_method(method: &str) -> bool {
    matches!(
        method,
        "model.turn.started"
            | "model.output.delta"
            | "model.turn.completed"
            | "model.turn.cancelled"
            | "model.turn.failed"
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
        Some(Value::String(value)) => Ok(Some(sanitize_text(value, MAX_DELTA_CHARS))),
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

fn sanitize_text(value: &str, limit: usize) -> String {
    let mut text = value.replace('\0', "");
    for marker in ["Traceback", "PRIVATE KEY", "sk-", "bearer ", "Bearer "] {
        if let Some(index) = text.find(marker) {
            text.replace_range(index.., "<REDACTED_TEXT>");
        }
    }
    if text.len() > limit {
        text.truncate(limit);
    }
    text
}

#[cfg(test)]
mod tests {
    use super::*;

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
        assert!(registry.insert("deskcp-0000000001".into()).is_ok());
        assert!(registry.insert("deskcp-0000000001".into()).is_err());
        for index in 2..=MAX_IN_FLIGHT_REQUESTS {
            registry.insert(format!("deskcp-{index:010}")).unwrap();
        }
        assert!(registry.insert("deskcp-9999999999".into()).is_err());
    }

    #[test]
    fn pending_terminal_wakes_and_records_result() {
        let pending = PendingRequest::new("deskcp-0000000001".into());
        finish_pending(&pending, Ok(json!({"state":"COMPLETED"})));
        let mut guard = pending.state.lock().unwrap();
        assert!(guard.terminal_seen || guard.terminal.is_some());
        assert_eq!(
            guard.terminal.take().unwrap().unwrap()["state"],
            "COMPLETED"
        );
    }

    #[test]
    fn command_input_validation_rejects_bad_values() {
        assert!(ensure_id("turn_id", "abcdefabcdefabcdefabcdef").is_ok());
        assert!(ensure_id("turn_id", "../bad").is_err());
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
}
