use crate::ipc;
use crate::managed_runtime::ManagedRuntimeSupervisor;
use crate::supervisor::{DesktopSidecarSupervisor, SidecarFrameRouter};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
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

const _: () = assert!(HARD_MAX_IN_FLIGHT_REQUESTS >= MAX_IN_FLIGHT_REQUESTS);

const REQUEST_TIMEOUT: Duration = Duration::from_secs(5);
const MOCK_TURN_TIMEOUT: Duration = Duration::from_secs(10);
const CANCEL_TIMEOUT: Duration = Duration::from_secs(5);
const MODEL_ATTACH_TIMEOUT: Duration = Duration::from_secs(300);
const MODEL_DETACH_TIMEOUT: Duration = Duration::from_secs(2);
const MODEL_REQUEST_WATCHDOG_TIMEOUT: Duration = Duration::from_secs(125);

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
            | Self::KnowledgeTurnDecide
            | Self::KnowledgeReviewDecisionCreate => Duration::from_secs(5),
            Self::ModelManagedAttach => MODEL_ATTACH_TIMEOUT,
            Self::ModelManagedDetach => MODEL_DETACH_TIMEOUT,
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
}

impl ModelRequestEntry {
    fn new(identity: ModelRequestIdentity) -> Self {
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
        }
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
        let entry = ModelRequestEntry::new(identity.clone());
        let watchdog = Arc::clone(&entry.watchdog);
        self.entries.insert(identity.request_id, entry);
        Ok(watchdog)
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
    ) -> Result<(), BridgeError> {
        let watchdog = self
            .model_requests
            .lock()
            .expect("model request registry poisoned")
            .insert(identity.clone())?;
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
    ) -> Result<Value, BridgeError> {
        let payload = json!({
            "request_id": identity.request_id,
            "chat_session_id": identity.chat_session_id,
            "model_id": identity.model_id,
            "submitted_at_unix_ms": identity.submitted_at_unix_ms,
            "max_tokens": identity.max_tokens,
            "prompt": prompt,
            "binding_fingerprint": identity.binding_fingerprint,
        });
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
        let reservation_exists =
            model_request_reservation_exists(&self.model_requests, model_request_id);
        let send_result = if reservation_exists {
            self.supervisor
                .send_ipc_frame(frame)
                .map_err(|error| BridgeError::unavailable(&error.to_string()))
        } else {
            Err(BridgeError::new(
                "request_not_found",
                "model request reservation expired before dispatch",
            ))
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
        let watchdog = registry.insert(identity)?;
        let entry = registry
            .entries
            .get_mut(&request_id)
            .expect("knowledge model entry disappeared while locked");
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
                let entry = registry
                    .entries
                    .get_mut(request_id)
                    .expect("model request entry disappeared while locked");
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
                if entry.buffered_events.iter().any(|event| {
                    matches!(
                        event.method.as_str(),
                        "model.turn.completed" | "model.turn.failed" | "model.turn.timed_out"
                    )
                }) {
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
pub async fn model_binding_set(
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
        ensure_runtime_instance_id(instance_id)?;
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
    let payload = json!({
        "provider_id": provider_id,
        "harness_id": harness_id,
        "port": port,
        "model_id": model_id,
        "confirmed": true,
        "runtime_instance_id": runtime_instance_id
    });
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        state.request(ControlPlaneMethod::ModelBindingSet, payload)
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model binding worker failed"))?
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn model_turn_start(
    state: State<'_, Arc<ControlPlaneBridge>>,
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    request_id: String,
    chat_session_id: String,
    model_id: String,
    submitted_at_unix_ms: u64,
    max_tokens: u16,
    prompt: String,
    binding_fingerprint: String,
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
    ensure_fingerprint(&binding_fingerprint)?;
    let identity = ModelRequestIdentity {
        request_id,
        chat_session_id,
        model_id,
        submitted_at_unix_ms,
        max_tokens,
        binding_fingerprint,
    };
    state.reserve_model_turn(&identity)?;
    let cleanup_state = Arc::clone(&state);
    let cleanup_request_id = identity.request_id.clone();
    let worker_state = Arc::clone(&state);
    let worker_runtime = Arc::clone(&runtime);
    match tauri::async_runtime::spawn_blocking(move || {
        if let Err(error) = worker_runtime.ensure_model_ready(&identity.model_id) {
            worker_state
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&identity.request_id);
            return Err(error);
        }
        worker_state.request_model_turn_reserved(identity, prompt)
    })
    .await
    {
        Ok(result) => result,
        Err(_) => {
            cleanup_state
                .model_requests
                .lock()
                .expect("model request registry poisoned")
                .remove(&cleanup_request_id);
            cleanup_state.send_model_cancel_best_effort(&cleanup_request_id);
            Err(BridgeError::new(
                "runtime_unavailable",
                "model start worker failed",
            ))
        }
    }
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
    let telemetry = validate_model_event_metadata(entry, event)?;
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
}

fn validate_model_event_metadata(
    entry: &ModelRequestEntry,
    event: &UiControlPlaneEvent,
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
    if metadata.keys().any(|key| {
        !BASE_KEYS.contains(&key.as_str())
            && key != "error"
            && !KNOWLEDGE_KEYS.contains(&key.as_str())
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
    let tools_are_disabled = metadata.get("tools_executed").and_then(Value::as_u64) == Some(0);
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
        || !tools_are_disabled
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
    )
}

fn is_model_terminal_method(method: &str) -> bool {
    matches!(
        method,
        "model.turn.completed"
            | "model.turn.cancelled"
            | "model.turn.timed_out"
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
    for marker in ["Traceback", "PRIVATE KEY", "sk-", "bearer ", "Bearer "] {
        if let Some(index) = text.find(marker) {
            text.replace_range(index.., "<REDACTED_TEXT>");
        }
    }
    if text.len() > limit {
        let mut boundary = limit;
        while boundary > 0 && !text.is_char_boundary(boundary) {
            boundary -= 1;
        }
        text.truncate(boundary);
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
        registry.lock().unwrap().insert(identity).unwrap();

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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
    fn knowledge_audit_is_allowed_only_on_started_event_and_projected() {
        let identity = model_identity();
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let mut entry = ModelRequestEntry::new(identity);
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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let _watchdog = registry.insert(identity.clone()).unwrap();
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
        let _watchdog = registry.insert(identity.clone()).unwrap();
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
        let mut entry = ModelRequestEntry::new(identity);
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
        let _watchdog = registry.insert(identity.clone()).unwrap();
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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let _watchdog = registry.insert(identity.clone()).unwrap();
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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let mut entry = ModelRequestEntry::new(identity.clone());
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
        let _watchdog = registry.insert(identity.clone()).unwrap();
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
            &ModelRequestEntry::new(identity),
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
        let watchdog = registry.insert(identity.clone()).unwrap();
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
        let mut entry = ModelRequestEntry::new(identity.clone());
        let started = model_event(&identity, "model.turn.started", 0, "Streaming", None);
        validate_and_record_model_event(&mut entry, &started, "model.turn.started", 0).unwrap();
        let empty = model_event(&identity, "model.output.delta", 1, "Streaming", Some(""));
        assert!(
            validate_and_record_model_event(&mut entry, &empty, "model.output.delta", 1).unwrap()
        );
        assert_eq!(entry.next_sequence, 2);
    }
}
