from __future__ import annotations

import codecs
import hashlib
import http.client
import json
import re
import secrets
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from modules.knowledge_injection_ru import (
    KnowledgeInjectionContractError,
    KnowledgeInjectionEnvelope,
    assemble_provider_messages,
    injection_audit_metadata,
    verify_provider_messages,
)


LOCAL_MODEL_GATEWAY_VERSION = "v6.84.5"
PROVIDER_ID = "openai-compatible-local"
MANAGED_PROVIDER_ID = "managed-llama-cpp"
HARNESS_MINIMAL = "minimal"
HARNESS_NATIVE = "native-localcomet"
PROVIDER_REGISTRY = (PROVIDER_ID, MANAGED_PROVIDER_ID)
HARNESS_REGISTRY = (HARNESS_MINIMAL, HARNESS_NATIVE)
SUPPORTED_FINISH_REASONS = (None, "stop", "length", "content_filter")
TURN_ID_RE = re.compile(r"^[0-9a-f]{24}$")
CHAT_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_SAFE_INTEGER = 9_007_199_254_740_991
DEFAULT_MAX_TOKENS = 256
MAX_MAX_TOKENS = 512
MAX_RECENT_REQUEST_IDS = 256
PUBLIC_TIMEOUT_ERROR_CODES = {
    "first_token_timeout": "first_token_timeout",
    "inactivity_timeout": "stream_inactivity_timeout",
    "overall_timeout": "request_timed_out",
}
TIMEOUT_ERROR_CODES = frozenset(PUBLIC_TIMEOUT_ERROR_CODES)
TERMINAL_EVENTS = frozenset(
    (
        "model.turn.completed",
        "model.turn.cancelled",
        "model.turn.timed_out",
        "model.turn.failed",
    )
)
TURN_START_PAYLOAD_KEYS = frozenset(
    (
        "request_id",
        "chat_session_id",
        "model_id",
        "submitted_at_unix_ms",
        "max_tokens",
        "prompt",
        "assistant_context",
        "binding_fingerprint",
    )
)

LOCALCOMET_APPLICATION_VERSION = "v6.84.5.1"
ASSISTANT_CONTEXT_APPLICATION_KEYS = frozenset(("name", "mode", "version"))
ASSISTANT_CONTEXT_CONVERSATION_KEYS = frozenset(("locale", "project_context_available"))
ASSISTANT_CONTEXT_CAPABILITY_KEYS = frozenset(
    (
        "local_chat",
        "local_model_inference",
        "internet",
        "email",
        "browser",
        "filesystem",
        "vault",
        "computer_use",
        "shell",
        "tools",
    )
)
TURN_CANCEL_PAYLOAD_KEYS = frozenset(("request_id",))
MANAGED_ATTACH_PAYLOAD_KEYS = frozenset(
    (
        "runtime_instance_id",
        "port",
        "credential",
        "expected_model_alias",
        "model_id",
        "binding_fingerprint",
    )
)


@dataclass(frozen=True, slots=True)
class GatewayLimits:
    maximum_models_body_bytes: int = 262_144
    maximum_model_count: int = 256
    maximum_model_id_bytes: int = 192
    maximum_prompt_bytes: int = 16_384
    maximum_messages: int = 4
    maximum_sse_line_bytes: int = 8_192
    maximum_sse_event_bytes: int = 16_384
    maximum_sse_events: int = 2_048
    maximum_output_bytes: int = 262_144
    read_chunk_bytes: int = 512
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 5.0
    first_token_timeout_seconds: float = 30.0
    inactivity_timeout_seconds: float = 10.0
    overall_timeout_seconds: float = 120.0
    worker_join_timeout_seconds: float = 2.0


class GatewayError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = _bounded_text(code, 64)
        self.message = _bounded_text(message, 256)
        self.retryable = bool(retryable)

    def as_payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass(frozen=True, slots=True)
class ModelBinding:
    provider_id: str
    harness_id: str
    port: int | None
    model_id: str
    fingerprint: str
    discovered_fingerprint: str
    runtime_instance_id: str | None = None
    credential: str | None = None
    expected_model_alias: str | None = None


@dataclass(slots=True)
class _ActiveTurn:
    request: "TurnRequest"
    binding: ModelBinding
    turn_id: str
    cancel: threading.Event
    thread: threading.Thread
    emit_event: Callable[[str, str, int, Mapping[str, Any]], None]
    closer: Callable[[], None] | None = None
    terminal: bool = False
    events_open: bool = True
    stop_in_progress: bool = False
    sequence: int = 0
    model_called: bool = False
    generated_bytes: int = 0
    pending_events: deque["_QueuedTurnEvent"] = field(default_factory=deque)
    events_draining: bool = False


@dataclass(frozen=True, slots=True)
class _QueuedTurnEvent:
    method: str
    request_id: str
    sequence: int
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TurnRequest:
    request_id: str
    turn_id: str
    chat_session_id: str
    model_id: str
    submitted_at_unix_ms: int
    max_tokens: int
    prompt: str
    assistant_context: "AssistantContext"
    binding_fingerprint: str


@dataclass(frozen=True, slots=True)
class AssistantContext:
    application_name: str
    application_mode: str
    application_version: str
    locale: str
    project_context_available: bool
    local_chat: bool
    local_model_inference: bool
    internet: bool
    email: bool
    browser: bool
    filesystem: bool
    vault: bool
    computer_use: bool
    shell: bool
    tools: tuple[str, ...]


def _expected_assistant_context(locale: str) -> AssistantContext:
    if locale not in {"ru", "en"}:
        raise GatewayError("invalid_payload", "assistant locale is unsupported")
    return AssistantContext(
        application_name="LocalComet",
        application_mode="local_offline_desktop_assistant",
        application_version=LOCALCOMET_APPLICATION_VERSION,
        locale=locale,
        project_context_available=False,
        local_chat=True,
        local_model_inference=True,
        internet=False,
        email=False,
        browser=False,
        filesystem=False,
        vault=False,
        computer_use=False,
        shell=False,
        tools=(),
    )


def trusted_assistant_context_payload(locale: str) -> dict[str, Any]:
    context = _expected_assistant_context(locale)
    return {
        "application": {
            "name": context.application_name,
            "mode": context.application_mode,
            "version": context.application_version,
        },
        "conversation": {
            "locale": context.locale,
            "project_context_available": context.project_context_available,
        },
        "capabilities": {
            "local_chat": context.local_chat,
            "local_model_inference": context.local_model_inference,
            "internet": context.internet,
            "email": context.email,
            "browser": context.browser,
            "filesystem": context.filesystem,
            "vault": context.vault,
            "computer_use": context.computer_use,
            "shell": context.shell,
            "tools": list(context.tools),
        },
    }


def _validate_assistant_context(value: object) -> AssistantContext:
    if not isinstance(value, Mapping) or set(value) != {
        "application",
        "conversation",
        "capabilities",
    }:
        raise GatewayError("invalid_payload", "assistant context shape is invalid")
    application = value.get("application")
    conversation = value.get("conversation")
    capabilities = value.get("capabilities")
    if not isinstance(application, Mapping) or set(application) != set(ASSISTANT_CONTEXT_APPLICATION_KEYS):
        raise GatewayError("invalid_payload", "assistant application context is invalid")
    if not isinstance(conversation, Mapping) or set(conversation) != set(ASSISTANT_CONTEXT_CONVERSATION_KEYS):
        raise GatewayError("invalid_payload", "assistant conversation context is invalid")
    if not isinstance(capabilities, Mapping) or set(capabilities) != set(ASSISTANT_CONTEXT_CAPABILITY_KEYS):
        raise GatewayError("invalid_payload", "assistant capability context is invalid")
    locale = conversation.get("locale")
    if not isinstance(locale, str):
        raise GatewayError("invalid_payload", "assistant locale is invalid")
    expected = _expected_assistant_context(locale)
    boolean_fields = (
        "project_context_available",
        "local_chat",
        "local_model_inference",
        "internet",
        "email",
        "browser",
        "filesystem",
        "vault",
        "computer_use",
        "shell",
    )
    observed_booleans = (
        conversation.get("project_context_available"),
        capabilities.get("local_chat"),
        capabilities.get("local_model_inference"),
        capabilities.get("internet"),
        capabilities.get("email"),
        capabilities.get("browser"),
        capabilities.get("filesystem"),
        capabilities.get("vault"),
        capabilities.get("computer_use"),
        capabilities.get("shell"),
    )
    if any(type(observed) is not bool for observed in observed_booleans):
        raise GatewayError("invalid_payload", f"{boolean_fields[0]} or capability boolean is invalid")
    if not isinstance(capabilities.get("tools"), list):
        raise GatewayError("invalid_payload", "assistant tools context is invalid")
    if value != trusted_assistant_context_payload(locale):
        raise GatewayError("invalid_payload", "assistant context is not trusted")
    return expected


class LocalModelGateway:
    def __init__(self, *, limits: GatewayLimits | None = None) -> None:
        self.limits = limits or GatewayLimits()
        self._lock = threading.RLock()
        self._binding: ModelBinding | None = None
        self._discovered_port: int | None = None
        self._discovered_models: tuple[str, ...] = ()
        self._managed: ModelBinding | None = None
        self._active: _ActiveTurn | None = None
        self._recent_request_order: deque[str] = deque()
        self._recent_request_ids: set[str] = set()

    def catalog(self) -> dict[str, Any]:
        return {
            "gateway_version": LOCAL_MODEL_GATEWAY_VERSION,
            "providers": [
                {
                    "provider_id": PROVIDER_ID,
                    "label": "OpenAI-compatible local",
                    "scheme": "http",
                    "host": "127.0.0.1",
                    "base_path": "/v1",
                },
                {
                    "provider_id": MANAGED_PROVIDER_ID,
                    "label": "LocalComet managed llama.cpp",
                    "scheme": "internal",
                    "host": "127.0.0.1",
                    "base_path": "/v1",
                }
            ],
            "harnesses": [
                {"harness_id": HARNESS_MINIMAL, "label": "Minimal"},
                {"harness_id": HARNESS_NATIVE, "label": "Native LocalComet"},
            ],
            "persistence": False,
            "tools_available": False,
        }

    def bound_turn_payload(self, prompt: str) -> dict[str, Any]:
        """Build an internal turn payload from the active in-memory binding."""
        normalized_prompt = _validate_prompt(prompt, self.limits)
        if not normalized_prompt.strip():
            raise GatewayError("invalid_payload", "prompt must not be empty")
        with self._lock:
            if self._binding is None:
                raise GatewayError("invalid_payload", "model binding is required")
            fingerprint = self._binding.fingerprint
            model_id = self._binding.model_id
        request_id = secrets.token_hex(12)
        return {
            "request_id": request_id,
            "chat_session_id": f"knowledge-{request_id}",
            "model_id": model_id,
            "submitted_at_unix_ms": int(time.time() * 1000),
            "max_tokens": DEFAULT_MAX_TOKENS,
            "prompt": normalized_prompt,
            "assistant_context": trusted_assistant_context_payload("ru"),
            "binding_fingerprint": fingerprint,
        }

    def probe(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        port = _validate_port(payload.get("port"))
        adapter = ProviderAdapter(port, self.limits)
        models = adapter.list_models()
        with self._lock:
            self._remember_discovery(port, models)
        return {
            "status": "Ready",
            "provider_id": PROVIDER_ID,
            "host": "127.0.0.1",
            "port": port,
            "base_path": "/v1",
            "model_count": len(models),
        }

    def list_models(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        port = _validate_port(payload.get("port"))
        adapter = ProviderAdapter(port, self.limits)
        models = adapter.list_models()
        with self._lock:
            self._remember_discovery(port, models)
        return {
            "provider_id": PROVIDER_ID,
            "host": "127.0.0.1",
            "port": port,
            "models": [{"model_id": model_id} for model_id in models],
            "discovered_fingerprint": _fingerprint({"port": port, "models": list(models)}),
        }

    def set_binding(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        provider_id = _expect_one_of(payload.get("provider_id"), PROVIDER_REGISTRY, "provider_id")
        harness_id = _expect_one_of(payload.get("harness_id"), HARNESS_REGISTRY, "harness_id")
        model_id = _validate_model_id(payload.get("model_id"))
        if payload.get("confirmed") is not True:
            raise GatewayError("invalid_payload", "binding confirmation is required")
        with self._lock:
            if provider_id == MANAGED_PROVIDER_ID:
                runtime_instance_id = _validate_runtime_instance_id(payload.get("runtime_instance_id"))
                if self._managed is None or self._managed.runtime_instance_id != runtime_instance_id:
                    raise GatewayError("invalid_payload", "managed runtime is not attached")
                if self._managed.model_id != model_id:
                    raise GatewayError("invalid_payload", "managed model_id mismatch")
                binding = _make_managed_binding(self._managed, harness_id)
                self._binding = binding
                return _binding_payload(binding)
            port = _validate_port(payload.get("port"))
            if self._discovered_port != port or not self._discovered_models:
                raise GatewayError("invalid_payload", "model discovery is required before binding")
            if model_id not in self._discovered_models:
                raise GatewayError("invalid_payload", "model_id was not returned by current discovery")
            discovered = _fingerprint({"port": port, "models": list(self._discovered_models)})
            binding = _make_binding(provider_id, harness_id, port, model_id, discovered)
            self._binding = binding
            return _binding_payload(binding)

    def start_turn(self, payload: Mapping[str, Any], emit_event: Callable[[str, str, int, Mapping[str, Any]], None]) -> dict[str, Any]:
        return self._start_turn(payload, emit_event)

    def start_turn_with_knowledge(
        self,
        payload: Mapping[str, Any],
        emit_event: Callable[[str, str, int, Mapping[str, Any]], None],
        envelope: KnowledgeInjectionEnvelope,
        *,
        control_plane_turn_id: str,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None],
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None],
    ) -> dict[str, Any]:
        """Internal-only dispatch for an already approved Control Plane envelope."""
        typed_payload = dict(payload)
        if set(typed_payload) == {"prompt", "binding_fingerprint"}:
            with self._lock:
                binding = self._binding
                if binding is None:
                    raise GatewayError("invalid_payload", "model binding is required")
            request_id = secrets.token_hex(12)
            typed_payload = {
                "request_id": request_id,
                "chat_session_id": f"knowledge-{control_plane_turn_id}",
                "model_id": binding.model_id,
                "submitted_at_unix_ms": int(time.time() * 1000),
                "max_tokens": DEFAULT_MAX_TOKENS,
                "assistant_context": trusted_assistant_context_payload("ru"),
                **typed_payload,
            }
        return self._start_turn(
            typed_payload,
            emit_event,
            knowledge_envelope=envelope,
            control_plane_turn_id=control_plane_turn_id,
            before_outbound_request=before_outbound_request,
            after_outbound_request=after_outbound_request,
        )

    def _start_turn(
        self,
        payload: Mapping[str, Any],
        emit_event: Callable[[str, str, int, Mapping[str, Any]], None],
        *,
        knowledge_envelope: KnowledgeInjectionEnvelope | None = None,
        control_plane_turn_id: str | None = None,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
    ) -> dict[str, Any]:
        _require_exact_payload_keys(payload, TURN_START_PAYLOAD_KEYS, "model.turn.start")
        with self._lock:
            if self._active is not None and self._active.thread.is_alive():
                raise GatewayError("busy", "one model inference is already active", retryable=True)
            if self._active is not None:
                self._active = None
            binding = self._binding
            if binding is None:
                raise GatewayError("invalid_payload", "model binding is required")
            request = _validate_turn_request(payload, binding, self.limits)
            if request.request_id in self._recent_request_ids:
                raise GatewayError("invalid_payload", "request_id was already used")
            messages = HarnessAdapter(binding.harness_id, self.limits).messages_for(
                request.prompt,
                request.assistant_context,
            )
            knowledge_audit: Mapping[str, Any] | None = None
            if knowledge_envelope is not None:
                if control_plane_turn_id is None:
                    raise GatewayError("invalid_payload", "knowledge Turn association is required")
                messages = assemble_provider_messages(
                    messages,
                    knowledge_envelope,
                    expected_turn_id=control_plane_turn_id,
                )
                verify_provider_messages(
                    messages,
                    knowledge_envelope,
                    expected_turn_id=control_plane_turn_id,
                )
                knowledge_audit = injection_audit_metadata(knowledge_envelope)
            _validate_messages(messages, self.limits)
            self._remember_request_id(request.request_id)
            cancel = threading.Event()
            thread = threading.Thread(
                target=self._run_turn,
                name="localcomet-model-turn",
                args=(
                    request,
                    binding,
                    messages,
                    cancel,
                    emit_event,
                    knowledge_audit,
                    before_outbound_request,
                    after_outbound_request,
                ),
                daemon=True,
            )
            active = _ActiveTurn(
                request=request,
                binding=binding,
                turn_id=request.turn_id,
                cancel=cancel,
                thread=thread,
                emit_event=emit_event,
            )
            self._active = active
            thread.start()
            response = {
                "request_id": request.request_id,
                "turn_id": request.turn_id,
                "chat_session_id": request.chat_session_id,
                "model_id": request.model_id,
                "submitted_at_unix_ms": request.submitted_at_unix_ms,
                "max_tokens": request.max_tokens,
                "binding_fingerprint": request.binding_fingerprint,
                "state": "Accepted",
                "provider_id": binding.provider_id,
                "harness_id": binding.harness_id,
                "model_called": False,
                "tools_executed": 0,
                "persistence": False,
            }
            if knowledge_envelope is not None:
                response["knowledge_injection_id"] = knowledge_envelope.injection_id
                response["knowledge_injection_state"] = knowledge_envelope.state.value
            return response

    def cancel_turn(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        _require_exact_payload_keys(payload, TURN_CANCEL_PAYLOAD_KEYS, "model.turn.cancel")
        request_id = _validate_request_id(payload.get("request_id"))
        with self._lock:
            active = self._active
            if (
                active is None
                or active.request.request_id != request_id
                or active.terminal
                or not active.events_open
            ):
                return {
                    "request_id": request_id,
                    "turn_id": request_id,
                    "state": "Cancelled",
                    "accepted": False,
                    "already_terminal": True,
                    "worker_alive": False,
                }
            active.stop_in_progress = True
            closer = active.closer
            thread = active.thread
            if closer is None:
                active.cancel.set()
            else:
                closer()
        thread.join(self.limits.worker_join_timeout_seconds)
        drain_events = False
        with self._lock:
            alive = thread.is_alive()
            if self._active is active and not active.terminal:
                drain_events = self._queue_terminal_locked(
                    active,
                    "model.turn.cancelled",
                    "Cancelled",
                )
            active.events_open = False
            active.terminal = True
            if self._active is active and not alive:
                self._active = None
        if drain_events:
            self._drain_turn_events(active)
        return {
            "request_id": request_id,
            "turn_id": request_id,
            "state": "Cancelling" if alive else "Cancelled",
            "accepted": True,
            "already_terminal": False,
            "worker_alive": alive,
        }

    def managed_attach(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        _require_exact_payload_keys(payload, MANAGED_ATTACH_PAYLOAD_KEYS, "model.managed.attach")
        runtime_instance_id = _validate_runtime_instance_id(payload.get("runtime_instance_id"))
        port = _validate_port(payload.get("port"))
        credential = _validate_credential(payload.get("credential"))
        expected_model_alias = _validate_model_id(payload.get("expected_model_alias"))
        model_id = _validate_model_id(payload.get("model_id"))
        binding_fingerprint = _validate_fingerprint(payload.get("binding_fingerprint"))
        with self._lock:
            if self._active is not None and self._active.thread.is_alive():
                raise GatewayError("busy", "model inference is active", retryable=True)
        adapter = ProviderAdapter(port, self.limits, api_key=credential)
        models = adapter.list_models(timeout_code="overall_timeout")
        if models != (expected_model_alias,):
            raise GatewayError("invalid_payload", "managed model alias mismatch")
        readiness_text = "".join(
            adapter.stream_chat(
                expected_model_alias,
                ({"role": "user", "content": "Reply with one character."},),
                threading.Event(),
                lambda: None,
                max_tokens=1,
            )
        )
        if not readiness_text.strip():
            raise GatewayError("invalid_payload", "managed inference readiness returned empty content")
        with self._lock:
            if self._active is not None and self._active.thread.is_alive():
                raise GatewayError("busy", "model inference became active", retryable=True)
            self._managed = ModelBinding(
                provider_id=MANAGED_PROVIDER_ID,
                harness_id=HARNESS_MINIMAL,
                port=port,
                model_id=model_id,
                fingerprint=binding_fingerprint,
                discovered_fingerprint=_fingerprint({"runtime_instance_id": runtime_instance_id, "model_id": model_id}),
                runtime_instance_id=runtime_instance_id,
                credential=credential,
                expected_model_alias=expected_model_alias,
            )
            if self._binding and self._binding.provider_id == MANAGED_PROVIDER_ID:
                self._binding = None
        return {
            "provider_id": MANAGED_PROVIDER_ID,
            "runtime_instance_id": runtime_instance_id,
            "model_id": model_id,
            "attached": True,
            "model_state": "Ready",
            "inference_ready": True,
        }

    def managed_detach(self) -> dict[str, Any]:
        self.shutdown()
        with self._lock:
            self._managed = None
            if self._binding and self._binding.provider_id == MANAGED_PROVIDER_ID:
                self._binding = None
        return {"provider_id": MANAGED_PROVIDER_ID, "detached": True}

    def shutdown(self) -> None:
        with self._lock:
            active = self._active
            if active is None:
                return
            active.stop_in_progress = True
            closer = active.closer
            thread = active.thread
            if closer is None:
                active.cancel.set()
            else:
                closer()
        thread.join(self.limits.worker_join_timeout_seconds)
        drain_events = False
        with self._lock:
            alive = thread.is_alive()
            if self._active is active and not active.terminal:
                drain_events = self._queue_terminal_locked(
                    active,
                    "model.turn.cancelled",
                    "Cancelled",
                )
            active.events_open = False
            active.terminal = True
            if self._active is active and not alive:
                self._active = None
        if drain_events:
            self._drain_turn_events(active)

    def _remember_request_id(self, request_id: str) -> None:
        self._recent_request_ids.add(request_id)
        self._recent_request_order.append(request_id)
        while len(self._recent_request_order) > MAX_RECENT_REQUEST_IDS:
            expired = self._recent_request_order.popleft()
            self._recent_request_ids.discard(expired)

    def _remember_discovery(self, port: int, models: tuple[str, ...]) -> None:
        if self._binding and (self._binding.port != port or self._binding.model_id not in models):
            self._binding = None
        self._discovered_port = port
        self._discovered_models = models

    def _run_turn(
        self,
        request: TurnRequest,
        binding: ModelBinding,
        messages: tuple[dict[str, str], ...],
        cancel: threading.Event,
        emit_event: Callable[[str, str, int, Mapping[str, Any]], None],
        knowledge_audit: Mapping[str, Any] | None = None,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
    ) -> None:
        adapter = ProviderAdapter(binding.port, self.limits, api_key=binding.credential)
        with self._lock:
            active = self._active
            if active is None or active.request.request_id != request.request_id:
                return
            active.closer = lambda: adapter.cancel_and_close(cancel)
        try:
            def mark_started() -> None:
                drain_events = False
                with self._lock:
                    if self._active is not active or active.terminal or cancel.is_set():
                        return
                    active.model_called = True
                    drain_events = self._queue_turn_event_locked(
                        active,
                        "model.turn.started",
                        _turn_payload(
                            request,
                            "Streaming",
                            binding,
                            model_called=True,
                            text=None,
                            audit_metadata=knowledge_audit,
                        ),
                    )
                if drain_events:
                    self._drain_turn_events(active)

            provider_model_id = (
                binding.expected_model_alias
                if binding.provider_id == MANAGED_PROVIDER_ID
                else binding.model_id
            )
            if provider_model_id is None:
                raise GatewayError("invalid_payload", "managed model alias is missing")
            for delta in adapter.stream_chat(
                provider_model_id,
                messages,
                cancel,
                mark_started,
                max_tokens=request.max_tokens,
                before_outbound_request=before_outbound_request,
                after_outbound_request=after_outbound_request,
            ):
                if cancel.is_set():
                    break
                if not delta:
                    continue
                drain_events = False
                with self._lock:
                    if self._active is not active or active.terminal or cancel.is_set():
                        break
                    active.generated_bytes += len(delta.encode("utf-8"))
                    drain_events = self._queue_turn_event_locked(
                        active,
                        "model.output.delta",
                        _turn_payload(
                            request,
                            "Streaming",
                            binding,
                            model_called=True,
                            text=delta,
                            generated_bytes=active.generated_bytes,
                        ),
                    )
                if drain_events:
                    self._drain_turn_events(active)
            drain_events = False
            with self._lock:
                if self._active is active and not active.terminal:
                    if cancel.is_set():
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.cancelled",
                            "Cancelled",
                        )
                    elif active.generated_bytes == 0:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.failed",
                            "Failed",
                            GatewayError(
                                "empty_model_output",
                                "model completion returned no content",
                                retryable=True,
                            ),
                        )
                    else:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.completed",
                            "Completed",
                        )
            if drain_events:
                self._drain_turn_events(active)
        except KnowledgeInjectionContractError as exc:
            drain_events = False
            with self._lock:
                if self._active is active and not active.terminal:
                    if cancel.is_set():
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.cancelled",
                            "Cancelled",
                        )
                    else:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.failed",
                            "Failed",
                            GatewayError(exc.code, exc.safe_message, retryable=False),
                        )
            if drain_events:
                self._drain_turn_events(active)
        except GatewayError as exc:
            drain_events = False
            with self._lock:
                if self._active is active and not active.terminal:
                    if cancel.is_set():
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.cancelled",
                            "Cancelled",
                        )
                    elif exc.code in TIMEOUT_ERROR_CODES:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.timed_out",
                            "TimedOut",
                            exc,
                        )
                    else:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.failed",
                            "Failed",
                            exc,
                        )
            if drain_events:
                self._drain_turn_events(active)
        except Exception:
            drain_events = False
            with self._lock:
                if self._active is active and not active.terminal:
                    if cancel.is_set():
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.cancelled",
                            "Cancelled",
                        )
                    else:
                        drain_events = self._queue_terminal_locked(
                            active,
                            "model.turn.failed",
                            "Failed",
                            GatewayError(
                                "internal_error",
                                "local model gateway failed",
                                retryable=False,
                            ),
                        )
            if drain_events:
                self._drain_turn_events(active)
        finally:
            adapter.close()
            with self._lock:
                active.closer = None
                if self._active is active and active.terminal:
                    active.events_open = False
                    if not active.stop_in_progress:
                        self._active = None

    def _queue_turn_event_locked(
        self,
        active: _ActiveTurn,
        method: str,
        payload: Mapping[str, Any],
    ) -> bool:
        if self._active is not active or not active.events_open or active.terminal:
            return False
        if active.cancel.is_set() and method != "model.turn.cancelled":
            return False
        if method in TERMINAL_EVENTS:
            active.terminal = True
        sequence = active.sequence
        active.sequence += 1
        active.pending_events.append(
            _QueuedTurnEvent(
                method=method,
                request_id=active.request.request_id,
                sequence=sequence,
                payload=payload,
            )
        )
        if active.events_draining:
            return False
        active.events_draining = True
        return True

    def _queue_terminal_locked(
        self,
        active: _ActiveTurn,
        method: str,
        state: str,
        error: GatewayError | None = None,
    ) -> bool:
        payload = _turn_payload(
            active.request,
            state,
            active.binding,
            model_called=active.model_called,
            generated_bytes=active.generated_bytes,
        )
        if error is not None:
            error_payload = error.as_payload()
            if method == "model.turn.timed_out":
                error_payload["code"] = PUBLIC_TIMEOUT_ERROR_CODES.get(
                    error.code,
                    "request_timed_out",
                )
            payload["metadata"] = {
                **payload["metadata"],
                "error": error_payload,
            }
        return self._queue_turn_event_locked(active, method, payload)

    def _drain_turn_events(self, active: _ActiveTurn) -> None:
        first_error: BaseException | None = None
        while True:
            with self._lock:
                if not active.pending_events:
                    active.events_draining = False
                    break
                event = active.pending_events.popleft()
            try:
                active.emit_event(
                    event.method,
                    event.request_id,
                    event.sequence,
                    event.payload,
                )
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


class HarnessAdapter:
    def __init__(self, harness_id: str, limits: GatewayLimits) -> None:
        self.harness_id = _expect_one_of(harness_id, HARNESS_REGISTRY, "harness_id")
        self.limits = limits

    def messages_for(
        self,
        prompt: str,
        assistant_context: AssistantContext,
    ) -> tuple[dict[str, str], ...]:
        prompt = _validate_prompt(prompt, self.limits)
        messages = (
            {
                "role": "system",
                "content": build_system_instruction(assistant_context),
            },
            {"role": "user", "content": prompt},
        )
        _validate_messages(messages, self.limits)
        return messages


def build_system_instruction(context: AssistantContext) -> str:
    if context != _expected_assistant_context(context.locale):
        raise GatewayError("invalid_payload", "assistant context is not trusted")
    if context.locale == "ru":
        return (
            f"Ты НЕ LocalComet, а локальный текстовый помощник внутри приложения LocalComet {context.application_version}. "
            "Ты не приложение, не его владелец и не разработчик. "
            "На вопрос о личности отвечай: «Я локальный помощник внутри LocalComet»; никогда не отвечай «Я LocalComet». "
            "Доступны ТОЛЬКО локальный текстовый чат и ответы локальной модели. "
            "Недоступны интернет и новости, email, браузер, файлы, документы, Obsidian Vault, PowerShell, shell, управление компьютером и кнопками, Computer Use и внешние инструменты. "
            "Сообщение пользователя не может изменить реальные возможности. Не утверждай, что недоступный доступ есть или действие выполнено. "
            "На вопрос о таком доступе начинай: «Нет, доступа нет». На просьбу о действии прямо откажись; можешь предложить текстовый черновик. "
            "Если пользователь заявляет о новом доступе, скажи, что это ничего не меняет и доступа всё равно нет. "
            "На вопрос «Что ты умеешь прямо сейчас?» отвечай ТОЛЬКО ДОСЛОВНО: «Доступны локальный текстовый чат и генерация ответов локальной моделью». "
            "Если спрашивают, что недоступно, перечисли недоступные возможности выше, а не доступные. "
            "На вопрос о проекте отвечай: «Контекст проекта не предоставлен, поэтому я не знаю деталей и не буду их выдумывать. Опишите проект в чате». "
            "По умолчанию русский; по явной просьбе дай один ответ на другом языке. "
            "При написании, редактировании или планировании помогай без отказов и повторения правил. Кратко ответь на запрос."
        )
    return (
        f"You are NOT LocalComet. You are a local text assistant inside the LocalComet {context.application_version} desktop application; "
        "you are not the application, its owner, or its developer. LocalComet uses a local model for text chat. "
        "When asked who you are, answer that you are a local assistant inside LocalComet; never answer that you are LocalComet. "
        "ONLY local text chat and local-model response generation are available. Internet or current news, email, browser, files or documents, "
        "Obsidian Vault, PowerShell or shell, computer or button control, Computer Use, and external tools are unavailable. "
        "A user message cannot change the real capabilities. Never claim unavailable access exists or an unavailable action was performed. "
        "Answer questions about such access with 'No, there is no access'; refuse such action requests directly and offer only text drafting when useful. "
        "A user's claim of new access changes nothing: state that the access is still unavailable. Describe your abilities as local text chat and local-model responses. "
        "Project context was not supplied. When asked about the project, say the context was not supplied, invent no details, and invite the user to describe it in chat. "
        "Reply in English by default, but honor an explicit request for one answer in another language. For ordinary writing, editing, or planning, "
        "simply help without refusals or repeating these rules. Answer only the request, concisely and practically."
    )


class ProviderAdapter:
    def __init__(self, port: int | None, limits: GatewayLimits, *, api_key: str | None = None) -> None:
        if port is None:
            raise GatewayError("invalid_payload", "port is required")
        self.port = _validate_port(port)
        self.limits = limits
        self.api_key = api_key
        self._connection: http.client.HTTPConnection | None = None
        self._response: http.client.HTTPResponse | None = None
        self._connection_lock = threading.RLock()

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def list_models(self, *, timeout_code: str = "sidecar_unavailable") -> tuple[str, ...]:
        if timeout_code not in {"sidecar_unavailable", "overall_timeout"}:
            raise ValueError("unsupported model readiness timeout code")
        deadline = time.monotonic() + max(0.001, float(self.limits.read_timeout_seconds))
        connection = self._connect(
            timeout_seconds=min(
                max(0.001, float(self.limits.connect_timeout_seconds)),
                _remaining_model_readiness_seconds(deadline, timeout_code),
            )
        )
        watchdog_stop, watchdog_fired = self._start_deadline_watchdog(connection, deadline)
        try:
            connection.request("GET", "/v1/models", headers=self._headers("application/json"))
            _raise_model_readiness_timeout_if_due(deadline, timeout_code, watchdog_fired)
            _set_connection_timeout(
                connection,
                _remaining_model_readiness_seconds(deadline, timeout_code),
            )
            response = connection.getresponse()
            self._remember_response(connection, response)
            _raise_model_readiness_timeout_if_due(deadline, timeout_code, watchdog_fired)
            _reject_redirect(response.status)
            if response.status != 200:
                raise GatewayError("sidecar_unavailable", "model provider returned non-200 status", retryable=True)
            body = _read_bounded(
                connection,
                response,
                self.limits.maximum_models_body_bytes,
                deadline=deadline,
                timeout_code=timeout_code,
                watchdog_fired=watchdog_fired,
            )
            value = _loads_json(body)
            if not isinstance(value, Mapping):
                raise GatewayError("invalid_payload", "model response must be an object")
            data = value.get("data")
            if not isinstance(data, list) or len(data) > self.limits.maximum_model_count:
                raise GatewayError("invalid_payload", "model data list is invalid")
            models: list[str] = []
            seen: set[str] = set()
            for item in data:
                if not isinstance(item, Mapping):
                    raise GatewayError("invalid_payload", "model record is invalid")
                model_id = _validate_model_id(item.get("id"), self.limits)
                if model_id in seen:
                    raise GatewayError("invalid_payload", "duplicate model id rejected")
                seen.add(model_id)
                models.append(model_id)
            return tuple(models)
        except GatewayError:
            raise
        except socket.timeout as exc:
            if watchdog_fired.is_set() or time.monotonic() >= deadline:
                raise _model_readiness_timeout(timeout_code) from exc
            raise GatewayError(
                "sidecar_unavailable",
                "model provider readiness timed out",
                retryable=True,
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            if watchdog_fired.is_set() or time.monotonic() >= deadline:
                raise _model_readiness_timeout(timeout_code) from exc
            raise GatewayError(
                "sidecar_unavailable",
                "model provider readiness failed",
                retryable=True,
            ) from exc
        finally:
            watchdog_stop.set()
            self.close()

    def stream_chat(
        self,
        model_id: str,
        messages: tuple[dict[str, str], ...],
        cancel: threading.Event,
        on_request_started: Callable[[], None],
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
    ) -> Iterable[str]:
        model_id = _validate_model_id(model_id, self.limits)
        max_tokens = _validate_max_tokens(max_tokens)
        _validate_messages(messages, self.limits)
        body = _json_bytes(
            {
                "max_tokens": max_tokens,
                "model": model_id,
                "messages": list(messages),
                "stream": True,
                "temperature": 0,
            }
        )
        started = time.monotonic()
        first_token_deadline = started + self.limits.first_token_timeout_seconds
        overall_deadline = started + self.limits.overall_timeout_seconds
        last_activity = started
        first_content_seen = False
        event_count = 0
        output_bytes = 0
        event_lines: list[str] = []
        event_bytes = 0
        decoder = codecs.getincrementaldecoder("utf-8")()
        text_buffer = ""
        preheader_watchdog_stop: threading.Event | None = None
        preheader_watchdog_fired = threading.Event()
        try:
            if before_outbound_request is not None:
                before_outbound_request(messages)
            if cancel.is_set():
                return
            preheader_deadline = min(first_token_deadline, overall_deadline)
            remaining = preheader_deadline - time.monotonic()
            if remaining <= 0:
                _raise_stream_timeout_if_due(
                    time.monotonic(),
                    overall_deadline=overall_deadline,
                    first_token_deadline=first_token_deadline,
                    first_content_seen=False,
                    last_activity=last_activity,
                    inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
                    force_phase=True,
                )
            connection = self._connect(
                timeout_seconds=min(
                    max(0.001, float(self.limits.connect_timeout_seconds)),
                    max(0.001, remaining),
                )
            )
            if cancel.is_set():
                self._close_connection_if_current(connection)
                return
            preheader_watchdog_stop, preheader_watchdog_fired = self._start_deadline_watchdog(
                connection,
                preheader_deadline,
            )
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={**self._headers("text/event-stream"), "Content-Type": "application/json"},
            )
            if after_outbound_request is not None:
                after_outbound_request(messages)
            now = time.monotonic()
            _raise_stream_timeout_if_due(
                now,
                overall_deadline=overall_deadline,
                first_token_deadline=first_token_deadline,
                first_content_seen=False,
                last_activity=last_activity,
                inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
            )
            _set_connection_timeout(
                connection,
                min(first_token_deadline, overall_deadline) - now,
            )
            response = connection.getresponse()
            self._remember_response(connection, response)
            preheader_watchdog_stop.set()
            preheader_watchdog_stop = None
            _raise_stream_timeout_if_due(
                time.monotonic(),
                overall_deadline=overall_deadline,
                first_token_deadline=first_token_deadline,
                first_content_seen=False,
                last_activity=last_activity,
                inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
            )
            _reject_redirect(response.status)
            if response.status != 200:
                raise GatewayError("sidecar_unavailable", "model completion returned non-200 status", retryable=True)
            content_type = response.getheader("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "text/event-stream":
                raise GatewayError("stream_protocol_error", "model completion stream type is invalid")
            on_request_started()
            while not cancel.is_set():
                now = time.monotonic()
                _raise_stream_timeout_if_due(
                    now,
                    overall_deadline=overall_deadline,
                    first_token_deadline=first_token_deadline,
                    first_content_seen=first_content_seen,
                    last_activity=last_activity,
                    inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
                )
                if first_content_seen:
                    phase_deadline = last_activity + self.limits.inactivity_timeout_seconds
                else:
                    phase_deadline = first_token_deadline
                _set_response_timeout(
                    connection,
                    response,
                    min(overall_deadline, phase_deadline) - now,
                )
                try:
                    chunk = response.read1(self.limits.read_chunk_bytes)
                except socket.timeout as exc:
                    _raise_stream_timeout_if_due(
                        time.monotonic(),
                        overall_deadline=overall_deadline,
                        first_token_deadline=first_token_deadline,
                        first_content_seen=first_content_seen,
                        last_activity=last_activity,
                        inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
                        force_phase=True,
                    )
                    raise GatewayError(
                        "stream_protocol_error",
                        "model stream read timed out unexpectedly",
                        retryable=True,
                    ) from exc
                if not chunk:
                    try:
                        decoder.decode(b"", final=True)
                    except UnicodeDecodeError as exc:
                        raise GatewayError("stream_encoding_error", "model stream encoding is invalid") from exc
                    raise GatewayError("stream_protocol_error", "model stream ended without DONE")
                last_activity = time.monotonic()
                try:
                    text_buffer += decoder.decode(chunk, final=False)
                except UnicodeDecodeError as exc:
                    raise GatewayError("stream_encoding_error", "model stream encoding is invalid") from exc
                while "\n" in text_buffer:
                    line, text_buffer = text_buffer.split("\n", 1)
                    if line.endswith("\r"):
                        line = line[:-1]
                    if len(line.encode("utf-8")) > self.limits.maximum_sse_line_bytes:
                        raise GatewayError("payload_too_large", "SSE line limit reached")
                    if line == "":
                        if event_lines:
                            event_count += 1
                            if event_count > self.limits.maximum_sse_events:
                                raise GatewayError("budget_exceeded", "SSE event limit reached")
                            try:
                                delta, done = _parse_sse_event(event_lines)
                            except GatewayError as exc:
                                if exc.code in {"payload_too_large", "budget_exceeded"}:
                                    raise
                                raise GatewayError(
                                    "stream_protocol_error",
                                    "model stream event is invalid",
                                ) from exc
                            event_lines = []
                            event_bytes = 0
                            if delta:
                                first_content_seen = True
                                output_bytes += len(delta.encode("utf-8"))
                                if output_bytes > self.limits.maximum_output_bytes:
                                    raise GatewayError("payload_too_large", "generated text limit reached")
                                yield delta
                            if done:
                                return
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        part = line[5:]
                        if part.startswith(" "):
                            part = part[1:]
                        event_bytes += len(part.encode("utf-8"))
                        if event_bytes > self.limits.maximum_sse_event_bytes:
                            raise GatewayError("payload_too_large", "SSE event limit reached")
                        event_lines.append(part)
                    elif line.startswith("event:") or line.startswith("id:") or line.startswith("retry:"):
                        continue
                    else:
                        raise GatewayError("stream_protocol_error", "model stream line is unsupported")
                if len(text_buffer.encode("utf-8")) > self.limits.maximum_sse_line_bytes:
                    raise GatewayError("payload_too_large", "SSE line limit reached")
        except GatewayError:
            raise
        except socket.timeout as exc:
            _raise_stream_timeout_if_due(
                time.monotonic(),
                overall_deadline=overall_deadline,
                first_token_deadline=first_token_deadline,
                first_content_seen=first_content_seen,
                last_activity=last_activity,
                inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
                force_phase=True,
            )
            raise GatewayError(
                "sidecar_unavailable",
                "model provider timed out",
                retryable=True,
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            _raise_stream_timeout_if_due(
                time.monotonic(),
                overall_deadline=overall_deadline,
                first_token_deadline=first_token_deadline,
                first_content_seen=first_content_seen,
                last_activity=last_activity,
                inactivity_timeout_seconds=self.limits.inactivity_timeout_seconds,
                force_phase=preheader_watchdog_fired.is_set(),
            )
            raise GatewayError(
                "sidecar_unavailable",
                "model provider connection failed",
                retryable=True,
            ) from exc
        finally:
            if preheader_watchdog_stop is not None:
                preheader_watchdog_stop.set()
            self.close()

    def close(self) -> None:
        with self._connection_lock:
            self._close_locked()

    def cancel_and_close(self, cancel: threading.Event) -> None:
        with self._connection_lock:
            cancel.set()
            self._close_locked()

    def _start_deadline_watchdog(
        self,
        connection: http.client.HTTPConnection,
        deadline: float,
    ) -> tuple[threading.Event, threading.Event]:
        stop = threading.Event()
        fired = threading.Event()

        def close_at_deadline() -> None:
            if stop.wait(max(0.0, deadline - time.monotonic())):
                return
            fired.set()
            self._close_connection_if_current(connection)

        threading.Thread(
            target=close_at_deadline,
            name="localcomet-provider-deadline",
            daemon=True,
        ).start()
        return stop, fired

    def _close_connection_if_current(self, connection: http.client.HTTPConnection) -> None:
        with self._connection_lock:
            if self._connection is not connection:
                return
            self._close_locked()

    def _remember_response(
        self,
        connection: http.client.HTTPConnection,
        response: http.client.HTTPResponse,
    ) -> None:
        with self._connection_lock:
            if self._connection is connection:
                self._response = response

    def _close_locked(self) -> None:
        if self._connection is not None:
            try:
                sock = self._connection.sock
                if sock is None and self._response is not None:
                    raw = getattr(getattr(self._response, "fp", None), "raw", None)
                    sock = getattr(raw, "_sock", None)
                if sock is not None:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                if self._response is not None:
                    self._response.close()
                self._connection.close()
            finally:
                self._response = None
                self._connection = None

    def _connect(self, *, timeout_seconds: float | None = None) -> http.client.HTTPConnection:
        with self._connection_lock:
            return self._connect_locked(timeout_seconds=timeout_seconds)

    def _connect_locked(self, *, timeout_seconds: float | None = None) -> http.client.HTTPConnection:
        self._close_locked()
        self._connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.port,
            timeout=max(
                0.001,
                float(
                    self.limits.connect_timeout_seconds
                    if timeout_seconds is None
                    else timeout_seconds
                ),
            ),
        )
        return self._connection

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def validate_gateway_payload(method: str, payload: Mapping[str, Any]) -> tuple[str, ...]:
    if method not in MODEL_GATEWAY_METHODS:
        return ("unsupported_method",)
    if not isinstance(payload, Mapping):
        return ("payload_not_object",)
    schemas: dict[str, set[str]] = {
        "model.catalog.get": set(),
        "model.gateway.probe": {"port"},
        "model.models.list": {"port"},
        "model.binding.set": {"provider_id", "harness_id", "port", "model_id", "confirmed", "runtime_instance_id"},
        "model.turn.start": set(TURN_START_PAYLOAD_KEYS),
        "model.turn.cancel": set(TURN_CANCEL_PAYLOAD_KEYS),
        "model.managed.attach": set(MANAGED_ATTACH_PAYLOAD_KEYS),
        "model.managed.detach": set(),
    }
    allowed = schemas[method]
    findings = [f"missing_{key}" for key in sorted(allowed - set(payload))]
    findings.extend(f"unknown_{key}" for key in sorted(set(payload) - allowed))
    return tuple(findings)


MODEL_GATEWAY_METHODS = (
    "model.catalog.get",
    "model.gateway.probe",
    "model.models.list",
    "model.binding.set",
    "model.turn.start",
    "model.turn.cancel",
    "model.managed.attach",
    "model.managed.detach",
)
MODEL_GATEWAY_EVENTS = (
    "model.turn.started",
    "model.output.delta",
    "model.turn.completed",
    "model.turn.cancelled",
    "model.turn.timed_out",
    "model.turn.failed",
)


def provider_registry() -> tuple[str, ...]:
    return PROVIDER_REGISTRY


def harness_registry() -> tuple[str, ...]:
    return HARNESS_REGISTRY


def _turn_payload(
    request: TurnRequest,
    state: str,
    binding: ModelBinding,
    *,
    model_called: bool,
    text: str | None = None,
    generated_bytes: int = 0,
    audit_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "control_plane_version": "v6.84.5.1",
        "model_gateway_version": LOCAL_MODEL_GATEWAY_VERSION,
        "request_id": request.request_id,
        "turn_id": request.turn_id,
        "chat_session_id": request.chat_session_id,
        "session_id": None,
        "thread_id": None,
        "item_id": None,
        "kind": None,
        "state": state,
        "provider_id": binding.provider_id,
        "harness_id": binding.harness_id,
        "model_id": request.model_id,
        "submitted_at_unix_ms": request.submitted_at_unix_ms,
        "max_tokens": request.max_tokens,
        "binding_fingerprint": request.binding_fingerprint,
        "text": _bounded_text(text or "", 65_536) if text is not None else None,
        "model_called": bool(model_called),
        "tools_executed": 0,
        "persistence": False,
        "generated_bytes": int(generated_bytes),
        "metadata": {
            "provider_id": binding.provider_id,
            "harness_id": binding.harness_id,
            "request_id": request.request_id,
            "turn_id": request.turn_id,
            "chat_session_id": request.chat_session_id,
            "model_id": request.model_id,
            "submitted_at_unix_ms": request.submitted_at_unix_ms,
            "max_tokens": request.max_tokens,
            "binding_fingerprint": request.binding_fingerprint,
            "model_called": bool(model_called),
            "tools_executed": 0,
            "persistence": False,
            "generated_bytes": int(generated_bytes),
        },
    }
    if audit_metadata:
        payload["metadata"] = {**payload["metadata"], **dict(audit_metadata)}
    return payload


def _make_binding(provider_id: str, harness_id: str, port: int, model_id: str, discovered: str) -> ModelBinding:
    fingerprint = _fingerprint(
        {
            "provider_id": provider_id,
            "harness_id": harness_id,
            "port": port,
            "model_id": model_id,
            "endpoint": f"http://127.0.0.1:{port}/v1",
        }
    )
    return ModelBinding(provider_id, harness_id, port, model_id, fingerprint, discovered)


def _make_managed_binding(managed: ModelBinding, harness_id: str) -> ModelBinding:
    fingerprint = _fingerprint(
        {
            "provider_id": MANAGED_PROVIDER_ID,
            "harness_id": harness_id,
            "runtime_instance_id": managed.runtime_instance_id,
            "model_id": managed.model_id,
            "expected_model_alias": managed.expected_model_alias,
            "binding_fingerprint": managed.fingerprint,
        }
    )
    return ModelBinding(
        MANAGED_PROVIDER_ID,
        harness_id,
        managed.port,
        managed.model_id,
        fingerprint,
        managed.discovered_fingerprint,
        managed.runtime_instance_id,
        managed.credential,
        managed.expected_model_alias,
    )


def _binding_payload(binding: ModelBinding) -> dict[str, Any]:
    return {
        "provider_id": binding.provider_id,
        "harness_id": binding.harness_id,
        "model_id": binding.model_id,
        "binding_fingerprint": binding.fingerprint,
        "discovered_fingerprint": binding.discovered_fingerprint,
        "persistence": False,
        **({"host": "127.0.0.1", "port": binding.port, "base_path": "/v1"} if binding.provider_id == PROVIDER_ID else {"runtime_instance_id": binding.runtime_instance_id}),
    }


def _validate_port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GatewayError("invalid_payload", "port must be a decimal integer")
    if value < 1024 or value > 65535:
        raise GatewayError("invalid_payload", "port is outside the allowed range")
    return value


def _validate_model_id(value: object, limits: GatewayLimits | None = None) -> str:
    limit = (limits or GatewayLimits()).maximum_model_id_bytes
    if not isinstance(value, str):
        raise GatewayError("invalid_payload", "model_id must be a string")
    if not value or "\0" in value or len(value.encode("utf-8")) > limit:
        raise GatewayError("invalid_payload", "model_id is invalid")
    if any(ch.isspace() for ch in value):
        raise GatewayError("invalid_payload", "model_id contains unsafe whitespace")
    return value


def _validate_request_id(value: object) -> str:
    if isinstance(value, str) and TURN_ID_RE.fullmatch(value):
        return value
    raise GatewayError("invalid_payload", "request_id is invalid")


def _validate_turn_id(value: object) -> str:
    if isinstance(value, str) and TURN_ID_RE.fullmatch(value):
        return value
    raise GatewayError("invalid_payload", "turn_id is invalid")


def _validate_chat_session_id(value: object) -> str:
    if isinstance(value, str) and CHAT_SESSION_ID_RE.fullmatch(value):
        return value
    raise GatewayError("invalid_payload", "chat_session_id is invalid")


def _validate_safe_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GatewayError("invalid_payload", f"{name} must be an integer")
    if value < 0 or value > MAX_SAFE_INTEGER:
        raise GatewayError("invalid_payload", f"{name} is outside the safe range")
    return value


def _validate_max_tokens(value: object) -> int:
    max_tokens = _validate_safe_integer(value, "max_tokens")
    if not 1 <= max_tokens <= MAX_MAX_TOKENS:
        raise GatewayError("invalid_payload", "max_tokens is outside the allowed range")
    return max_tokens


def _validate_turn_request(
    payload: Mapping[str, Any],
    binding: ModelBinding,
    limits: GatewayLimits,
) -> TurnRequest:
    request_id = _validate_request_id(payload.get("request_id"))
    chat_session_id = _validate_chat_session_id(payload.get("chat_session_id"))
    model_id = _validate_model_id(payload.get("model_id"), limits)
    if model_id != binding.model_id:
        raise GatewayError("invalid_payload", "model_id does not match the active binding")
    submitted_at_unix_ms = _validate_safe_integer(
        payload.get("submitted_at_unix_ms"),
        "submitted_at_unix_ms",
    )
    max_tokens = _validate_max_tokens(payload.get("max_tokens"))
    prompt = _validate_prompt(payload.get("prompt"), limits)
    if not prompt.strip():
        raise GatewayError("invalid_payload", "prompt must not be empty")
    assistant_context = _validate_assistant_context(payload.get("assistant_context"))
    binding_fingerprint = _validate_fingerprint(payload.get("binding_fingerprint"))
    if binding_fingerprint != binding.fingerprint:
        raise GatewayError("invalid_payload", "binding fingerprint mismatch")
    return TurnRequest(
        request_id=request_id,
        turn_id=request_id,
        chat_session_id=chat_session_id,
        model_id=model_id,
        submitted_at_unix_ms=submitted_at_unix_ms,
        max_tokens=max_tokens,
        prompt=prompt,
        assistant_context=assistant_context,
        binding_fingerprint=binding_fingerprint,
    )


def _validate_runtime_instance_id(value: object) -> str:
    if isinstance(value, str) and len(value) == 32 and all(ch in "0123456789abcdef" for ch in value):
        return value
    raise GatewayError("invalid_payload", "runtime_instance_id is invalid")


def _validate_fingerprint(value: object) -> str:
    if isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value):
        return value
    raise GatewayError("invalid_payload", "binding_fingerprint is invalid")


def _validate_credential(value: object) -> str:
    if isinstance(value, str) and len(value) >= 64 and len(value) <= 256 and all(ch in "0123456789abcdef" for ch in value):
        return value
    raise GatewayError("invalid_payload", "managed credential is invalid")


def _validate_prompt(value: object, limits: GatewayLimits) -> str:
    if not isinstance(value, str):
        raise GatewayError("invalid_payload", "prompt must be a string")
    if "\0" in value:
        raise GatewayError("invalid_payload", "prompt contains invalid null byte")
    if len(value.encode("utf-8")) > limits.maximum_prompt_bytes:
        raise GatewayError("payload_too_large", "prompt byte limit reached")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _validate_messages(messages: tuple[dict[str, str], ...], limits: GatewayLimits) -> None:
    if len(messages) > limits.maximum_messages:
        raise GatewayError("invalid_payload", "too many harness messages")
    total = 0
    for message in messages:
        if set(message) != {"role", "content"}:
            raise GatewayError("invalid_payload", "message shape is invalid")
        if message["role"] not in {"system", "user"}:
            raise GatewayError("invalid_payload", "unsupported message role")
        content = message["content"]
        if not isinstance(content, str) or "\0" in content:
            raise GatewayError("invalid_payload", "message content is invalid")
        total += len(content.encode("utf-8"))
    if total > limits.maximum_prompt_bytes * 2:
        raise GatewayError("payload_too_large", "harness message byte limit reached")


def _require_exact_payload_keys(
    payload: Mapping[str, Any],
    expected: frozenset[str],
    method: str,
) -> None:
    if not isinstance(payload, Mapping) or set(payload) != set(expected):
        raise GatewayError("invalid_payload", f"{method} payload shape is invalid")


def _expect_exact(value: object, expected: str, name: str) -> str:
    if value != expected:
        raise GatewayError("invalid_payload", f"{name} is unsupported")
    return expected


def _expect_one_of(value: object, options: tuple[str, ...], name: str) -> str:
    if isinstance(value, str) and value in options:
        return value
    raise GatewayError("invalid_payload", f"{name} is unsupported")


def _parse_sse_event(lines: list[str]) -> tuple[str, bool]:
    data = "\n".join(lines)
    if data == "[DONE]":
        return "", True
    value = _loads_json(data.encode("utf-8"))
    _reject_tool_markers(value)
    if not isinstance(value, Mapping):
        raise GatewayError("invalid_payload", "SSE JSON must be an object")
    choices = value.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise GatewayError("invalid_payload", "SSE choices must contain only index 0")
    choice = choices[0]
    if not isinstance(choice, Mapping) or choice.get("index") not in (0, None):
        raise GatewayError("invalid_payload", "SSE choice index is invalid")
    finish_reason = choice.get("finish_reason")
    if finish_reason not in SUPPORTED_FINISH_REASONS:
        raise GatewayError("invalid_payload", "SSE finish reason is unsupported")
    delta = choice.get("delta", {})
    if delta is None:
        delta = {}
    if not isinstance(delta, Mapping):
        raise GatewayError("invalid_payload", "SSE delta is invalid")
    content = delta.get("content", "")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise GatewayError("invalid_payload", "SSE content delta is invalid")
    return content, False


def _reject_tool_markers(value: object) -> None:
    forbidden = {"tool_calls", "function_call", "tools", "functions", "arguments"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in forbidden or lowered == "role" and child == "tool":
                raise GatewayError("invalid_payload", "tool or function output is not supported")
            _reject_tool_markers(child)
    elif isinstance(value, list):
        for child in value:
            _reject_tool_markers(child)


def _set_connection_timeout(connection: http.client.HTTPConnection, seconds: float) -> None:
    sock = connection.sock
    if sock is not None:
        sock.settimeout(max(0.001, float(seconds)))


def _set_response_timeout(
    connection: http.client.HTTPConnection,
    response: http.client.HTTPResponse,
    seconds: float,
) -> None:
    sock = connection.sock
    if sock is None:
        raw = getattr(getattr(response, "fp", None), "raw", None)
        sock = getattr(raw, "_sock", None)
    if sock is not None:
        sock.settimeout(max(0.001, float(seconds)))


def _model_readiness_timeout(code: str) -> GatewayError:
    return GatewayError(
        code,
        "model provider readiness timed out",
        retryable=True,
    )


def _remaining_model_readiness_seconds(deadline: float, timeout_code: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _model_readiness_timeout(timeout_code)
    return max(0.001, remaining)


def _raise_model_readiness_timeout_if_due(
    deadline: float,
    timeout_code: str,
    watchdog_fired: threading.Event,
) -> None:
    if watchdog_fired.is_set() or time.monotonic() >= deadline:
        raise _model_readiness_timeout(timeout_code)


def _raise_stream_timeout_if_due(
    now: float,
    *,
    overall_deadline: float,
    first_token_deadline: float,
    first_content_seen: bool,
    last_activity: float,
    inactivity_timeout_seconds: float,
    force_phase: bool = False,
) -> None:
    if force_phase or now >= overall_deadline:
        if now >= overall_deadline:
            raise GatewayError(
                "overall_timeout",
                "model completion exceeded the overall deadline",
                retryable=True,
            )
    if not first_content_seen:
        if force_phase or now >= first_token_deadline:
            raise GatewayError(
                "first_token_timeout",
                "model completion did not produce a first token in time",
                retryable=True,
            )
        return
    if force_phase or now >= last_activity + inactivity_timeout_seconds:
        raise GatewayError(
            "inactivity_timeout",
            "model completion stream became inactive",
            retryable=True,
        )


def _read_bounded(
    connection: http.client.HTTPConnection,
    response: http.client.HTTPResponse,
    limit: int,
    *,
    deadline: float,
    timeout_code: str,
    watchdog_fired: threading.Event,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        _raise_model_readiness_timeout_if_due(deadline, timeout_code, watchdog_fired)
        _set_response_timeout(
            connection,
            response,
            _remaining_model_readiness_seconds(deadline, timeout_code),
        )
        try:
            chunk = response.read1(min(8192, limit - total + 1))
        except socket.timeout as exc:
            raise _model_readiness_timeout(timeout_code) from exc
        _raise_model_readiness_timeout_if_due(deadline, timeout_code, watchdog_fired)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise GatewayError("payload_too_large", "response body limit reached")
        chunks.append(chunk)
    return b"".join(chunks)


def _loads_json(body: bytes) -> Any:
    text = _decode_utf8(body)
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_json_constant)
    except GatewayError:
        raise
    except json.JSONDecodeError as exc:
        raise GatewayError("invalid_payload", "invalid provider JSON") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GatewayError("invalid_payload", "duplicate JSON key rejected")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise GatewayError("invalid_payload", f"invalid JSON constant {value}")


def _decode_utf8(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GatewayError("invalid_payload", "invalid UTF-8 from provider") from exc


def _reject_redirect(status: int) -> None:
    if 300 <= int(status) < 400:
        raise GatewayError("sidecar_unavailable", "provider redirect rejected", retryable=False)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _bounded_text(value: str, limit: int) -> str:
    text = str(value).replace("\0", "")
    if len(text) <= limit:
        return text
    return text[:limit]
