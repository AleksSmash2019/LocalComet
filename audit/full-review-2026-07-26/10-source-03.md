# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/src-tauri/binaries/app/modules/local_model_gateway_ru.py (1928 строк, 79537 байт)

````python
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

LOCALCOMET_APPLICATION_VERSION = "v6.84.6"
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
            headers["Authorization"] = f"Bearer [REDACTED: secret in desktop/localcomet-desktop/src-tauri/binaries/app/modules/local_model_gateway_ru.py:1422]"
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
        "control_plane_version": "v6.84.6",
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
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/binaries/app/tools/run_localcomet_desktop_sidecar.py (145 строк, 4678 байт)

````python
from __future__ import annotations

import sys
import threading
from pathlib import Path


def _prepare_import_path() -> None:
    runner = Path(__file__)
    if runner.is_symlink():
        raise RuntimeError("sidecar runner symlink is not allowed")
    root = runner.resolve(strict=True).parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


_prepare_import_path()

from modules.desktop_ipc_contract_ru import FrameDecoder, IPCProtocolError  # noqa: E402
from modules.desktop_sidecar_runtime_ru import make_runtime  # noqa: E402


READ_CHUNK_BYTES = 8192
WRITE_LOCK = threading.RLock()
SERIALIZED_ACCEPTANCE_METHODS = frozenset(
    ("model.turn.start", "knowledge.turn.decide")
)


def _write_messages(runtime, messages) -> bool:
    try:
        payload = runtime.encode_messages(messages)
        if payload:
            with WRITE_LOCK:
                sys.stdout.buffer.write(payload)
                sys.stdout.buffer.flush()
        return True
    except BrokenPipeError:
        return False


class _AcceptanceWriteGate:
    """Keep acceptance ahead of async events without holding WRITE_LOCK in handlers."""

    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._active_token: object | None = None
        self._buffered: list[tuple[dict, ...]] = []

    def begin(self) -> object:
        token = object()
        with self._lock:
            if self._active_token is not None:
                raise RuntimeError("nested sidecar acceptance gate")
            self._active_token = token
            self._buffered.clear()
        return token

    def write_async(self, messages) -> bool:
        batch = tuple(messages)
        with self._lock:
            if self._active_token is not None:
                self._buffered.append(batch)
                return True
        return _write_messages(self._runtime, batch)

    def finish(self, token: object, response_messages=(), *, flush: bool) -> bool:
        # WRITE_LOCK is acquired only after the handler has released gateway
        # locks. It stays held while the gate opens and the acceptance response
        # plus buffered events are drained in that order.
        with WRITE_LOCK:
            with self._lock:
                if self._active_token is not token:
                    raise RuntimeError("sidecar acceptance gate token mismatch")
                buffered = tuple(self._buffered)
                self._buffered.clear()
                self._active_token = None
            if not flush:
                return False
            if not _write_messages(self._runtime, response_messages):
                return False
            for batch in buffered:
                if not _write_messages(self._runtime, batch):
                    return False
        return True


def _handle_and_write(runtime, message, acceptance_gate: _AcceptanceWriteGate) -> bool:
    def handle():
        try:
            return runtime.handle_message(message)
        except IPCProtocolError as exc:
            return runtime.protocol_error_messages(
                exc,
                reply_to=str(message.get("id", "unknown")),
            )

    if message.get("method") not in SERIALIZED_ACCEPTANCE_METHODS:
        return _write_messages(runtime, handle())

    token = acceptance_gate.begin()
    try:
        response_messages = handle()
    except BaseException:
        acceptance_gate.finish(token, flush=False)
        raise
    return acceptance_gate.finish(token, response_messages, flush=True)


def main() -> int:
    runtime = make_runtime()
    acceptance_gate = _AcceptanceWriteGate(runtime)
    runtime.set_async_message_writer(acceptance_gate.write_async)
    decoder = FrameDecoder()
    try:
        if not _write_messages(runtime, runtime.startup_messages()):
            return 0

        while not runtime.shutdown_requested:
            chunk = sys.stdin.buffer.read1(READ_CHUNK_BYTES)
            if not chunk:
                break
            try:
                messages = decoder.feed(chunk)
            except IPCProtocolError as exc:
                if not _write_messages(runtime, runtime.protocol_error_messages(exc)):
                    return 0
                continue
            for message in messages:
                if not _handle_and_write(runtime, message, acceptance_gate):
                    return 0

        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        sys.stderr.write("localcomet sidecar fatal\n")
        raise SystemExit(1)
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/binaries/app/tools/validate_localcomet_vault.py (1359 строк, 58943 байт)

````python
"""Deterministic, dependency-free, read-only validator for LocalComet Vault v2."""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


sys.dont_write_bytecode = True

MAX_NOTES = 2000
MAX_NOTE_BYTES = 1_048_576
MAX_TOTAL_SCAN_BYTES = 67_108_864
MAX_AUXILIARY_BYTES = 1_048_576
MAX_CANVAS_NODES = 512
MAX_CANVAS_EDGES = 1024
MAX_CANVAS_TEXT_CHARS = 65_536

DECLARED_CANVAS_ASSETS = frozenset(
    {"00 Канон/LocalComet — Архитектурная карта.canvas"}
)
HUB_PATH_PREFIXES = ("00 Канон/", "01 Архитектура/", "03 Решения/")
COMPONENT_PATH_PREFIXES = ("01 Архитектура/",)
DRAFT_PATH_PREFIXES = ("01 Архитектура/",)

REQUIRED_FIELDS = (
    "id",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "updated",
    "last_reviewed",
)
LIST_FIELDS = {
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "aliases",
    "tags",
}
ENUMS = {
    "type": {
        "canonical", "architecture", "release", "adr", "runbook", "incident",
        "roadmap", "security", "research", "prompt", "session", "evidence", "meta",
        "hub", "component",
    },
    "status": {
        "current", "active", "accepted", "planned", "research", "resolved",
        "historical", "superseded", "evidence-limited", "draft",
    },
    "knowledge_layer": {
        "current_source_truth", "verified_history", "founder_intent", "operational",
        "research", "roadmap", "forensic_evidence", "session_snapshot",
    },
    "evidence_class": {"A", "B", "C", "D", "E", "G"},
    "authority": {
        "source", "runtime", "test", "forensic_evidence", "founder",
        "architecture_decision", "research", "roadmap", "session",
    },
}
REQUIRED_CANONICAL_SCOPES = {
    "current-state",
    "version-matrix",
    "product-vision",
    "system-architecture",
    "source-map",
    "knowledge-schema",
    "security",
    "roadmap",
    "evidence",
    "incidents",
}
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".com", ".scr", ".msi",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".db", ".sqlite", ".sqlite3",
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".zsh",
    ".vbs", ".jar",
}
FORBIDDEN_AUXILIARY_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"PK\x03\x04",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07",
    b"\x1f\x8b",
    b"SQLite format 3\x00",
    b"#!",
)
LINK_BENEFIT_TYPES = {
    "canonical", "architecture", "adr", "runbook", "incident", "roadmap",
    "security", "research", "evidence", "hub",
}

ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
EVIDENCE_ID_RE = re.compile(r"^EV-[0-9]{3,}$")
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:[ ](.*))?$")
LIST_ITEM_RE = re.compile(r"^  -[ ](.+)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
WIKI_LINK_RE = re.compile(r"!?\[\[([^\[\]\r\n]+)\]\]")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ValidatorRuntimeError(RuntimeError):
    """The validator could not safely establish or read its configured roots."""


class FrontmatterError(ValueError):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.line = line


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    file: str = ""
    line: int = 0
    finding_type: str = ""
    redacted: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", 0)}


@dataclass
class Note:
    path: Path
    relative_path: str
    raw_bytes: bytes
    text: str
    metadata: dict[str, Any]
    body_lines: list[tuple[int, str]]
    headings: set[str] = field(default_factory=set)
    title: str = ""
    note_id: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    status: str
    vault_root: str
    project_root: str
    vault_revision: str
    markdown_note_count: int
    markdown_total_bytes: int
    obsidian_json_count: int
    obsidian_auxiliary_count: int
    obsidian_auxiliary_total_bytes: int
    obsidian_auxiliary_files: list[dict[str, Any]]
    stable_id_count: int
    canonical_scope_count: int
    wiki_link_count: int
    resolved_wiki_link_count: int
    broken_link_count: int
    ambiguous_link_count: int
    alias_collision_count: int
    evidence_record_count: int
    unresolved_evidence_ref_count: int
    canonical_ownership_conflict_count: int
    supersession_cycle_count: int
    missing_source_path_count: int
    unexpected_file_count: int
    binary_or_forbidden_file_count: int
    secret_finding_count: int
    error_count: int
    warning_count: int
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normal(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _lookup_key(value: str) -> str:
    return _normal(value).casefold()


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_path_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((os.fspath(path), os.fspath(root))) == os.fspath(root)
    except (ValueError, OSError):
        return False


def _stat_is_reparse(info: os.stat_result) -> bool:
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & marker)


def is_reparse_point(path: os.PathLike[str] | str) -> bool:
    """Return True for a symlink or Windows reparse point without following it."""
    info = os.lstat(path)
    return stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _path_components(path: Path) -> Iterable[Path]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    current = anchor
    if absolute == anchor:
        yield anchor
        return
    for part in absolute.parts[1:]:
        current = current / part
        yield current


def _safe_root(configured: os.PathLike[str] | str, label: str) -> Path:
    path = Path(os.path.abspath(os.fspath(configured)))
    try:
        for component in _path_components(path):
            if is_reparse_point(component):
                raise ValidatorRuntimeError(f"{label} contains a symlink or reparse point: {component}")
        if not path.exists() or not path.is_dir():
            raise ValidatorRuntimeError(f"{label} does not exist or is not a directory: {path}")
        resolved = path.resolve(strict=True)
    except ValidatorRuntimeError:
        raise
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot inspect {label}: {path}: {exc}") from exc
    return resolved


def _entry_is_link_or_reparse(entry: os.DirEntry[str], info: os.stat_result) -> bool:
    return entry.is_symlink() or stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _inspect_auxiliary_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_auxiliary",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_SIZE_LIMIT",
                f"Obsidian auxiliary file size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}",
                relative,
            )
        )
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Obsidian auxiliary file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Obsidian auxiliary file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(
            Issue(
                "error",
                "AUXILIARY_FORBIDDEN_CONTENT",
                "Obsidian auxiliary file contains executable, archive, or database content",
                relative,
            )
        )
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_BINARY_CONTENT",
                "Obsidian auxiliary file must be bounded UTF-8 text",
                relative,
            )
        )
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    return record, issues, False


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _bounded_canvas_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value) or abs(value) > 10_000_000:
        return False
    return not positive or value > 0


def _canvas_file_reference_problem(path_value: Any, vault_root: Path) -> str | None:
    if not isinstance(path_value, str) or not 1 <= len(path_value) <= 512:
        return "file node reference must be a bounded string"
    if URL_RE.match(path_value):
        return "URL file references are forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return "absolute, drive-qualified, or UNC file references are forbidden"
    if "\\" in path_value:
        return "Canvas file references must use forward slashes"
    parts = path_value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "Canvas file reference traversal is forbidden"
    if Path(path_value).suffix.casefold() != ".md":
        return "Canvas file nodes may reference Markdown notes only"
    candidate = vault_root.joinpath(*parts)
    current = vault_root
    try:
        for part in parts:
            current = current / part
            if current.exists() and is_reparse_point(current):
                return "Canvas file reference crosses a symlink or reparse point"
        if not candidate.exists() or not candidate.is_file():
            return "Canvas file reference does not resolve to a Vault note"
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return f"Canvas file reference inspection failed: {exc}"
    if not _is_path_within(resolved, vault_root):
        return "Canvas file reference resolves outside the Vault"
    return None


def _canvas_node_problem(node: Any, vault_root: Path) -> str | None:
    if not isinstance(node, dict):
        return "Canvas node must be an object"
    node_type = node.get("type")
    common = {"id", "type", "x", "y", "width", "height", "color"}
    allowed_by_type = {
        "group": common | {"label"},
        "file": common | {"file"},
        "text": common | {"text"},
    }
    required_by_type = {
        "group": {"id", "type", "x", "y", "width", "height", "label"},
        "file": {"id", "type", "x", "y", "width", "height", "file"},
        "text": {"id", "type", "x", "y", "width", "height", "text"},
    }
    if node_type not in allowed_by_type:
        return "Canvas node type must be group, file, or text"
    if not required_by_type[node_type].issubset(node) or not set(node).issubset(allowed_by_type[node_type]):
        return f"Canvas {node_type} node has missing or unknown fields"
    node_id = node.get("id")
    if not isinstance(node_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", node_id):
        return "Canvas node id is invalid"
    if not _bounded_canvas_number(node.get("x")) or not _bounded_canvas_number(node.get("y")):
        return "Canvas node coordinates are invalid"
    if not _bounded_canvas_number(node.get("width"), positive=True) or not _bounded_canvas_number(node.get("height"), positive=True):
        return "Canvas node dimensions are invalid"
    color = node.get("color")
    if color is not None and (not isinstance(color, str) or not 1 <= len(color) <= 64):
        return "Canvas node color is invalid"
    if node_type == "group":
        label = node.get("label")
        if not isinstance(label, str) or not 1 <= len(label) <= 512:
            return "Canvas group label is invalid"
    elif node_type == "file":
        return _canvas_file_reference_problem(node.get("file"), vault_root)
    else:
        text = node.get("text")
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_CANVAS_TEXT_CHARS:
            return "Canvas text node content is invalid"
        if re.search(r"(?i)\b(?:https?|file)://", text):
            return "Canvas text nodes may not declare external URL references"
    return None


def _canvas_edge_problem(edge: Any, node_ids: set[str]) -> str | None:
    if not isinstance(edge, dict):
        return "Canvas edge must be an object"
    allowed = {
        "id", "fromNode", "fromSide", "fromEnd", "toNode", "toSide",
        "toEnd", "color", "label",
    }
    if not {"id", "fromNode", "toNode"}.issubset(edge) or not set(edge).issubset(allowed):
        return "Canvas edge has missing or unknown fields"
    for field_name in ("id", "fromNode", "toNode"):
        value = edge.get(field_name)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            return f"Canvas edge {field_name} is invalid"
    if edge["fromNode"] not in node_ids or edge["toNode"] not in node_ids:
        return "Canvas edge references an unknown node"
    if edge["fromNode"] == edge["toNode"]:
        return "Canvas self-edges are forbidden"
    for field_name in ("fromSide", "toSide"):
        if field_name in edge and edge[field_name] not in {"top", "right", "bottom", "left"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name in ("fromEnd", "toEnd"):
        if field_name in edge and edge[field_name] not in {"none", "arrow"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name, limit in (("color", 64), ("label", 512)):
        if field_name in edge and (
            not isinstance(edge[field_name], str) or not 1 <= len(edge[field_name]) <= limit
        ):
            return f"Canvas edge {field_name} is invalid"
    return None


def _inspect_canvas_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
    vault_root: Path,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_canvas",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(Issue("error", "AUXILIARY_SIZE_LIMIT", f"Canvas size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}", relative))
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Canvas file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Canvas file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(Issue("error", "AUXILIARY_FORBIDDEN_CONTENT", "Canvas contains executable, archive, or database content", relative))
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(Issue("error", "AUXILIARY_BINARY_CONTENT", "Canvas must be bounded UTF-8 JSON", relative))
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON number: {value}")),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        issues.append(Issue("error", "CANVAS_JSON_INVALID", f"Canvas JSON is invalid: {exc}", relative))
        return record, issues, False
    if not isinstance(payload, dict) or set(payload) != {"nodes", "edges"}:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas root must contain exactly nodes and edges arrays", relative))
        return record, issues, False
    nodes = payload["nodes"]
    edges = payload["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas nodes must be a non-empty array and edges must be an array", relative))
        return record, issues, False
    if len(nodes) > MAX_CANVAS_NODES or len(edges) > MAX_CANVAS_EDGES:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas node or edge count exceeds the bounded policy", relative))
        return record, issues, False
    node_ids: set[str] = set()
    hard_stop_present = False
    for index, node in enumerate(nodes):
        problem = _canvas_node_problem(node, vault_root)
        if problem:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: {problem}", relative))
            continue
        node_id = node["id"]
        if node_id in node_ids:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: duplicate node id", relative))
        node_ids.add(node_id)
        if node.get("type") == "text" and "HARD STOP" in node.get("text", "") and "NO AUTOMATIC VAULT WRITE" in node.get("text", ""):
            hard_stop_present = True
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        problem = _canvas_edge_problem(edge, node_ids)
        if problem:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: {problem}", relative))
            continue
        edge_id = edge["id"]
        if edge_id in edge_ids:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: duplicate edge id", relative))
        edge_ids.add(edge_id)
    if not hard_stop_present:
        issues.append(Issue("error", "CANVAS_BOUNDARY_MISSING", "Declared architecture Canvas must retain the no-write HARD STOP boundary", relative))
    return record, issues, False


def _discover_files_detailed(
    vault_root: Path,
) -> tuple[
    list[tuple[Path, os.stat_result]],
    int,
    list[dict[str, Any]],
    list[Issue],
    int,
    int,
]:
    notes: list[tuple[Path, os.stat_result]] = []
    obsidian_json_count = 0
    auxiliary_files: list[dict[str, Any]] = []
    issues: list[Issue] = []
    unexpected_count = 0
    forbidden_count = 0

    def walk(directory: Path) -> None:
        nonlocal obsidian_json_count, unexpected_count, forbidden_count
        try:
            entries = sorted(os.scandir(directory), key=lambda item: _lookup_key(item.name))
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot enumerate Vault directory {directory}: {exc}") from exc
        try:
            for entry in entries:
                candidate = Path(entry.path)
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise ValidatorRuntimeError(f"cannot inspect Vault entry {candidate}: {exc}") from exc
                relative = _relative_posix(candidate, vault_root)
                if _entry_is_link_or_reparse(entry, info):
                    issues.append(Issue("error", "REPARSE_POINT", "symlink or reparse point is forbidden", relative))
                    continue
                if stat.S_ISDIR(info.st_mode):
                    walk(candidate)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    issues.append(Issue("error", "NON_REGULAR_FILE", "non-regular Vault entry is forbidden", relative))
                    continue
                resolved = candidate.resolve(strict=True)
                if not _is_path_within(resolved, vault_root):
                    issues.append(Issue("error", "PATH_ESCAPE", "Vault file resolves outside the configured root", relative))
                    continue
                in_obsidian = bool(Path(relative).parts and Path(relative).parts[0] == ".obsidian")
                suffix = candidate.suffix.casefold()
                if in_obsidian and suffix == ".json":
                    obsidian_json_count += 1
                elif not in_obsidian and suffix == ".md":
                    notes.append((candidate, info))
                elif suffix == ".base":
                    record, auxiliary_issues, forbidden_content = _inspect_auxiliary_file(
                        candidate,
                        info,
                        relative,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                elif suffix == ".canvas" and _normal(relative) in DECLARED_CANVAS_ASSETS:
                    record, auxiliary_issues, forbidden_content = _inspect_canvas_file(
                        candidate,
                        info,
                        relative,
                        vault_root,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                else:
                    unexpected_count += 1
                    if suffix in FORBIDDEN_EXTENSIONS:
                        forbidden_count += 1
                        issues.append(Issue("error", "FORBIDDEN_FILE", f"forbidden Vault file extension: {suffix}", relative))
                    else:
                        issues.append(Issue("error", "UNEXPECTED_FILE", "unexpected regular file outside the Vault file policy", relative))
        finally:
            for entry in entries:
                del entry

    walk(vault_root)
    notes.sort(key=lambda item: _lookup_key(_relative_posix(item[0], vault_root)))
    auxiliary_files.sort(key=lambda item: _normal(item["relative_path"]))
    return (
        notes,
        obsidian_json_count,
        auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    )


def _discover_files(
    vault_root: Path,
) -> tuple[list[tuple[Path, os.stat_result]], int, list[Issue], int, int]:
    """Compatibility wrapper used by the read-only KnowledgeAdapter."""
    notes, json_count, _auxiliary, issues, unexpected, forbidden = (
        _discover_files_detailed(vault_root)
    )
    return notes, json_count, issues, unexpected, forbidden


def _parse_scalar(value: str, line_number: int) -> Any:
    if value == "[]":
        return []
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if not value:
        raise FrontmatterError("empty scalar is unsupported; use [] for an empty list", line_number)
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise FrontmatterError(f"invalid quoted string: {exc.msg}", line_number) from exc
        if not isinstance(parsed, str):
            raise FrontmatterError("quoted frontmatter values must be strings", line_number)
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise FrontmatterError("invalid single-quoted string", line_number)
        return value[1:-1].replace("''", "'")
    if value[0] in "[{&*!>|%@`" or value.endswith(":") or " #" in value or "\t" in value:
        raise FrontmatterError("unsupported YAML-like scalar syntax", line_number)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], list[tuple[int, str]]]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterError("missing opening frontmatter delimiter", 1)
    closing = next((index for index in range(1, len(lines)) if lines[index] == "---"), None)
    if closing is None:
        raise FrontmatterError("missing closing frontmatter delimiter", 1)
    metadata: dict[str, Any] = {}
    index = 1
    while index < closing:
        line = lines[index]
        line_number = index + 1
        if not line.strip():
            index += 1
            continue
        if "\t" in line:
            raise FrontmatterError("tabs are unsupported in frontmatter", line_number)
        match = KEY_RE.fullmatch(line)
        if not match:
            raise FrontmatterError("unsupported frontmatter syntax", line_number)
        key, raw_value = match.group(1), match.group(2)
        if key in metadata:
            raise FrontmatterError(f"duplicate frontmatter key: {key}", line_number)
        if raw_value is None or raw_value == "":
            values: list[str] = []
            index += 1
            while index < closing:
                item_match = LIST_ITEM_RE.fullmatch(lines[index])
                if not item_match:
                    break
                item = _parse_scalar(item_match.group(1), index + 1)
                if not isinstance(item, str):
                    raise FrontmatterError("block list items must be scalar strings", index + 1)
                values.append(item)
                index += 1
            if not values:
                raise FrontmatterError(f"empty block list for {key}; use []", line_number)
            metadata[key] = values
            continue
        metadata[key] = _parse_scalar(raw_value, line_number)
        index += 1
    body = [(line_number + 1, line) for line_number, line in enumerate(lines[closing + 1 :], closing + 1)]
    return metadata, body


def _outside_fences(lines: list[tuple[int, str]]) -> Iterable[tuple[int, str]]:
    fence: str | None = None
    for line_number, line in lines:
        marker_match = re.match(r"^[ ]{0,3}(`{3,}|~{3,})", line)
        if marker_match:
            marker = marker_match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None:
            yield line_number, line


def _extract_headings(note: Note) -> None:
    headings: set[str] = set()
    first_h1 = ""
    for _line_number, line in _outside_fences(note.body_lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
        if heading:
            headings.add(_lookup_key(heading))
            if len(match.group(1)) == 1 and not first_h1:
                first_h1 = heading
    note.headings = headings
    configured_title = note.metadata.get("title")
    note.title = configured_title if isinstance(configured_title, str) else first_h1


def _issue(issues: list[Issue], severity: str, code: str, message: str, note: Note | None = None, line: int = 0) -> None:
    issues.append(Issue(severity, code, message, note.relative_path if note else "", line))


def _validate_date(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        _datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_timestamp(value: Any) -> bool:
    if _validate_date(value):
        return True
    if not isinstance(value, str):
        return False
    try:
        _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def _validate_note_schema(note: Note, issues: list[Issue]) -> None:
    metadata = note.metadata
    for field_name in REQUIRED_FIELDS:
        if field_name not in metadata:
            _issue(issues, "error", "MISSING_REQUIRED_FIELD", f"missing required field: {field_name}", note)
    for field_name, allowed in ENUMS.items():
        value = metadata.get(field_name)
        if field_name in metadata and (not isinstance(value, str) or value not in allowed):
            _issue(issues, "error", "INVALID_ENUM", f"invalid {field_name}: {value!r}", note)
    for field_name in LIST_FIELDS:
        if field_name not in metadata:
            continue
        value = metadata[field_name]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _issue(issues, "error", "INVALID_FIELD_TYPE", f"{field_name} must be a list of strings", note)
    canonical = metadata.get("canonical", False)
    if not isinstance(canonical, bool):
        _issue(issues, "error", "INVALID_CANONICAL_TYPE", "canonical must be a boolean", note)
    for field_name in ("updated", "last_reviewed"):
        if field_name in metadata and not _validate_date(metadata[field_name]):
            _issue(issues, "error", "INVALID_DATE", f"{field_name} must be a valid YYYY-MM-DD date", note)
    if "verified_at" in metadata and not _validate_timestamp(metadata["verified_at"]):
        _issue(issues, "error", "INVALID_TIMESTAMP", "verified_at must be an ISO date or ISO-8601 timestamp", note)
    note_id = metadata.get("id")
    if isinstance(note_id, str):
        note.note_id = note_id
        if not ID_RE.fullmatch(note_id):
            _issue(issues, "error", "INVALID_STABLE_ID", f"invalid stable ID: {note_id!r}", note)
    elif "id" in metadata:
        _issue(issues, "error", "INVALID_STABLE_ID", "stable ID must be a string", note)
    aliases = metadata.get("aliases", [])
    if isinstance(aliases, list) and all(isinstance(value, str) for value in aliases):
        note.aliases = aliases

    status = metadata.get("status")
    layer = metadata.get("knowledge_layer")
    note_type = metadata.get("type")
    if layer == "current_source_truth" and status in {"planned", "superseded"}:
        _issue(issues, "error", "CURRENT_TRUTH_STATUS", f"current source truth cannot be {status}", note)
    if canonical is True and status == "superseded":
        _issue(issues, "error", "SUPERSEDED_CANONICAL", "canonical note cannot be superseded", note)
    if status == "superseded" and not metadata.get("superseded_by"):
        _issue(issues, "error", "SUPERSEDED_WITHOUT_SUCCESSOR", "superseded note requires superseded_by", note)
    if layer == "founder_intent" and metadata.get("authority") != "founder":
        _issue(issues, "warning", "FOUNDER_INTENT_AUTHORITY", "founder_intent normally uses authority: founder", note)
    if note_type == "release" and not metadata.get("releases"):
        if not (isinstance(note_id, str) and re.fullmatch(r"release[._-]v?[0-9]+(?:[._-][0-9]+)*(?:[a-z][0-9]*)?", note_id)):
            _issue(issues, "error", "RELEASE_IDENTIFIER_MISSING", "release note requires releases or a release-compatible stable ID", note)
    if note_type == "hub":
        tags = metadata.get("tags", [])
        if not note.relative_path.startswith(HUB_PATH_PREFIXES) or not isinstance(tags, list) or "hub" not in tags:
            _issue(
                issues,
                "error",
                "HUB_ROLE_BOUNDARY",
                "hub is reserved for tagged navigation entry points under Canon, Architecture, or Decisions",
                note,
            )
    if note_type == "component":
        component_contract = (
            note.relative_path.startswith(COMPONENT_PATH_PREFIXES)
            and canonical is False
            and layer == "current_source_truth"
            and metadata.get("evidence_class") == "A"
            and metadata.get("authority") == "source"
            and bool(metadata.get("source_paths"))
        )
        if not component_contract:
            _issue(
                issues,
                "error",
                "COMPONENT_ROLE_BOUNDARY",
                "component is reserved for source-grounded, non-canonical software component notes under Architecture",
                note,
            )
    if status == "draft":
        draft_contract = (
            note.relative_path.startswith(DRAFT_PATH_PREFIXES)
            and canonical is False
            and layer == "founder_intent"
            and metadata.get("evidence_class") == "C"
            and metadata.get("authority") in {"founder", "architecture_decision"}
        )
        if not draft_contract:
            _issue(
                issues,
                "error",
                "DRAFT_AUTHORITY_BOUNDARY",
                "draft is non-canonical founder intent under Architecture and grants no current-source authority",
                note,
            )


def _validate_source_path(path_value: str, project_root: Path) -> tuple[Path | None, str | None]:
    if URL_RE.match(path_value):
        return None, "URL source path is forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return None, "absolute, drive-qualified, or UNC source path is forbidden"
    components = [part for part in re.split(r"[\\/]", path_value) if part not in ("", ".")]
    if not components or any(part == ".." for part in components):
        return None, "source path traversal is forbidden"
    candidate = project_root.joinpath(*components)
    current = project_root
    try:
        for component in components:
            current = current / component
            if current.exists() and is_reparse_point(current):
                return None, "source path traverses a symlink or reparse point"
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, f"source path inspection failed: {exc}"
    if not _is_path_within(resolved, project_root):
        return None, "source path resolves outside project root"
    return candidate, None


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}…{value[-4:]}"


def _looks_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in ("placeholder", "redacted", "example", "changeme", "your_", "your-", "xxxx", "<", ">", "..."))


def _scan_secret_text(text: str, relative_path: str) -> list[Issue]:
    findings: list[Issue] = []
    prefix_re = re.compile(
        r"\b(sk-(?:live-)?[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
        r"xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"
    )
    assignment_re = re.compile(
        r"(?i)\b(api[ _-]?key|access[ _-]?token|token|secret|password|passwd|client_secret)"
        r"\s*[:=]\s*[\"']?([A-Za-z0-9_./+\-=]{20,})"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        if "-----BEGIN " in line and "PRIVATE KEY-----" in line:
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "PEM_PRIVATE_KEY", "-----BEGIN … PRIVATE KEY-----"))
        for match in prefix_re.finditer(line):
            value = match.group(1)
            if not _looks_placeholder(value):
                findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "LIVE_TOKEN_PREFIX", _redact(value)))
        for match in assignment_re.finditer(line):
            value = match.group(2)
            if re.fullmatch(r"[0-9a-fA-F]{64}", value) or _looks_placeholder(value):
                continue
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence credential assignment", relative_path, line_number, "CREDENTIAL_ASSIGNMENT", _redact(value)))
    unique: dict[tuple[Any, ...], Issue] = {}
    for finding in findings:
        unique[(finding.file, finding.line, finding.finding_type, finding.redacted)] = finding
    return list(unique.values())


def _scan_secrets(note: Note) -> list[Issue]:
    return _scan_secret_text(note.text, note.relative_path)


def _compute_revision(notes: list[Note]) -> str:
    canonical = hashlib.sha256()
    for note in sorted(notes, key=lambda item: _normal(item.relative_path)):
        canonical.update(_normal(note.relative_path).encode("utf-8"))
        canonical.update(b"\0")
        canonical.update(hashlib.sha256(note.raw_bytes).hexdigest().encode("ascii"))
        canonical.update(b"\0")
    return f"sha256:{canonical.hexdigest()}"


def _cycle_count(edges: dict[str, set[str]]) -> int:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycle_keys: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, set())):
            if state.get(target, 0) == 0:
                visit(target)
            elif state.get(target) == 1:
                start = stack.index(target)
                cycle = stack[start:]
                rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
                cycle_keys.add(min(rotations))
        stack.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            visit(node)
    return len(cycle_keys)


def _result(
    *, vault_root: Path, project_root: Path, notes: list[Note], markdown_note_count: int,
    markdown_total_bytes: int, obsidian_json_count: int,
    obsidian_auxiliary_files: list[dict[str, Any]], issues: list[Issue],
    canonical_scope_count: int, wiki_count: int, resolved_count: int, broken_count: int,
    ambiguous_count: int, alias_collision_count: int, evidence_count: int,
    unresolved_evidence_count: int, ownership_conflicts: int, cycle_count: int,
    missing_source_count: int, unexpected_count: int, forbidden_count: int,
    secret_count: int,
) -> ValidationResult:
    issues.sort(key=lambda item: (_lookup_key(item.file), item.line, item.severity, item.code, item.message))
    errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
    warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    stable_ids = {note.note_id for note in notes if note.note_id and ID_RE.fullmatch(note.note_id)}
    return ValidationResult(
        status=status,
        vault_root=os.fspath(vault_root),
        project_root=os.fspath(project_root),
        vault_revision=_compute_revision(notes),
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_count=len(obsidian_auxiliary_files),
        obsidian_auxiliary_total_bytes=sum(
            int(item["size"]) for item in obsidian_auxiliary_files
        ),
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        stable_id_count=len(stable_ids),
        canonical_scope_count=canonical_scope_count,
        wiki_link_count=wiki_count,
        resolved_wiki_link_count=resolved_count,
        broken_link_count=broken_count,
        ambiguous_link_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_record_count=evidence_count,
        unresolved_evidence_ref_count=unresolved_evidence_count,
        canonical_ownership_conflict_count=ownership_conflicts,
        supersession_cycle_count=cycle_count,
        missing_source_path_count=missing_source_count,
        unexpected_file_count=unexpected_count,
        binary_or_forbidden_file_count=forbidden_count,
        secret_finding_count=secret_count,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
    )


def validate_vault(
    vault: os.PathLike[str] | str,
    project: os.PathLike[str] | str,
    *,
    require_canonical_scopes: bool = True,
    max_notes: int = MAX_NOTES,
    max_note_bytes: int = MAX_NOTE_BYTES,
    max_total_scan_bytes: int = MAX_TOTAL_SCAN_BYTES,
) -> ValidationResult:
    """Validate without writing to the Vault or project tree."""
    vault_root = _safe_root(vault, "Vault root")
    project_root = _safe_root(project, "project root")
    (
        discovered,
        obsidian_json_count,
        obsidian_auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    ) = _discover_files_detailed(vault_root)
    markdown_note_count = len(discovered)
    markdown_total_bytes = sum(info.st_size for _path, info in discovered)
    if markdown_note_count > max_notes:
        issues.append(Issue("error", "NOTE_COUNT_LIMIT", f"Markdown note count {markdown_note_count} exceeds limit {max_notes}"))
    if markdown_total_bytes > max_total_scan_bytes:
        issues.append(Issue("error", "TOTAL_SCAN_LIMIT", f"Markdown bytes {markdown_total_bytes} exceed limit {max_total_scan_bytes}"))

    notes: list[Note] = []
    for path, info in discovered:
        relative = _relative_posix(path, vault_root)
        if info.st_size > max_note_bytes:
            issues.append(Issue("error", "NOTE_SIZE_LIMIT", f"note size {info.st_size} exceeds limit {max_note_bytes}", relative))
            continue
        try:
            raw_bytes = path.read_bytes()
            if len(raw_bytes) != info.st_size:
                raise ValidatorRuntimeError(f"Vault note changed during validation: {relative}")
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(Issue("error", "INVALID_UTF8", f"note is not valid UTF-8: {exc}", relative))
            continue
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot read Vault note {relative}: {exc}") from exc
        try:
            metadata, body_lines = parse_frontmatter(text)
        except FrontmatterError as exc:
            issues.append(Issue("error", "FRONTMATTER_ERROR", str(exc), relative, exc.line))
            continue
        note = Note(path, relative, raw_bytes, text, metadata, body_lines)
        _extract_headings(note)
        _validate_note_schema(note, issues)
        issues.extend(_scan_secrets(note))
        notes.append(note)

    by_id: dict[str, list[Note]] = {}
    normalized_ids: dict[str, list[Note]] = {}
    for note in notes:
        if not note.note_id:
            continue
        by_id.setdefault(note.note_id, []).append(note)
        normalized_ids.setdefault(_lookup_key(note.note_id), []).append(note)
    for note_id, owners in sorted(by_id.items()):
        if len(owners) > 1:
            for note in owners:
                _issue(issues, "error", "DUPLICATE_STABLE_ID", f"duplicate stable ID: {note_id}", note)
    for normalized_id, owners in sorted(normalized_ids.items()):
        raw_values = {note.note_id for note in owners}
        if len(owners) > 1 and (len(raw_values) > 1 or len(by_id.get(next(iter(raw_values)), [])) > 1):
            for note in owners:
                _issue(issues, "error", "NORMALIZED_DUPLICATE_ID", f"normalized/case duplicate stable ID: {normalized_id}", note)

    canonical_owners: dict[str, list[Note]] = {}
    for note in notes:
        canonical = note.metadata.get("canonical", False)
        scope = note.metadata.get("canonical_scope")
        if canonical is True:
            if not isinstance(scope, str) or not scope:
                _issue(issues, "error", "CANONICAL_SCOPE_MISSING", "canonical note requires canonical_scope", note)
            else:
                canonical_owners.setdefault(scope, []).append(note)
    ownership_conflicts = 0
    for scope, owners in sorted(canonical_owners.items()):
        if len(owners) > 1:
            ownership_conflicts += 1
            for note in owners:
                _issue(issues, "error", "CANONICAL_SCOPE_CONFLICT", f"multiple canonical owners for scope: {scope}", note)
    if require_canonical_scopes:
        for scope in sorted(REQUIRED_CANONICAL_SCOPES - set(canonical_owners)):
            issues.append(Issue("error", "MISSING_CANONICAL_SCOPE", f"missing canonical scope: {scope}"))

    missing_source_count = 0
    for note in notes:
        paths = note.metadata.get("source_paths", [])
        if not isinstance(paths, list):
            continue
        for source_path in paths:
            if not isinstance(source_path, str):
                continue
            candidate, problem = _validate_source_path(source_path, project_root)
            if problem:
                _issue(issues, "error", "INVALID_SOURCE_PATH", f"{source_path!r}: {problem}", note)
                continue
            assert candidate is not None
            if not candidate.exists():
                if note.metadata.get("knowledge_layer") == "current_source_truth":
                    missing_source_count += 1
                    _issue(issues, "error", "MISSING_CURRENT_SOURCE", f"current source path does not exist: {source_path}", note)
                elif not note.metadata.get("evidence_refs"):
                    _issue(issues, "error", "MISSING_HISTORICAL_SOURCE", f"missing historical source path lacks evidence_refs: {source_path}", note)

    evidence_records: dict[str, list[tuple[Note, int]]] = {}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            heading = HEADING_RE.match(line)
            if not heading:
                continue
            heading_text = heading.group(2).strip()
            match = re.match(r"^(EV-[0-9]{3,})(?:\b|\s|—|-)", heading_text)
            if match:
                evidence_records.setdefault(match.group(1), []).append((note, line_number))
            elif heading_text.startswith("EV-"):
                _issue(issues, "error", "MALFORMED_EVIDENCE_ID", "malformed evidence record ID", note, line_number)
    for evidence_id, records in sorted(evidence_records.items()):
        if len(records) > 1:
            for note, line_number in records:
                _issue(issues, "error", "DUPLICATE_EVIDENCE_ID", f"duplicate evidence record ID: {evidence_id}", note, line_number)
    unresolved_evidence_count = 0
    for note in notes:
        references = note.metadata.get("evidence_refs", [])
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, str) or not EVIDENCE_ID_RE.fullmatch(reference):
                unresolved_evidence_count += 1
                _issue(issues, "error", "MALFORMED_EVIDENCE_REF", f"malformed evidence reference: {reference!r}", note)
            elif reference not in evidence_records:
                unresolved_evidence_count += 1
                _issue(issues, "error", "UNRESOLVED_EVIDENCE_REF", f"unresolved evidence reference: {reference}", note)

    id_to_note = {note.note_id: note for note in notes if note.note_id and len(by_id.get(note.note_id, [])) == 1}
    edges: dict[str, set[str]] = {note_id: set() for note_id in id_to_note}
    for note_id, note in id_to_note.items():
        supersedes = note.metadata.get("supersedes", [])
        superseded_by = note.metadata.get("superseded_by", [])
        for relation_name, references in (("supersedes", supersedes), ("superseded_by", superseded_by)):
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, str) or not ID_RE.fullmatch(reference):
                    _issue(issues, "error", "MALFORMED_SUPERSESSION_REF", f"malformed {relation_name} reference: {reference!r}", note)
                    continue
                if reference == note_id:
                    _issue(issues, "error", "SELF_SUPERSESSION", "self-supersession is forbidden", note)
                    continue
                if reference not in id_to_note:
                    _issue(issues, "error", "UNRESOLVED_SUPERSESSION_REF", f"unresolved {relation_name} reference: {reference}", note)
                    continue
                if relation_name == "supersedes":
                    edges[note_id].add(reference)
                    reciprocal = id_to_note[reference].metadata.get("superseded_by", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different superseded_by relation", note)
                else:
                    edges[reference].add(note_id)
                    reciprocal = id_to_note[reference].metadata.get("supersedes", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different supersedes relation", note)
    cycle_count = _cycle_count(edges)
    if cycle_count:
        issues.append(Issue("error", "SUPERSESSION_CYCLE", f"supersession graph contains {cycle_count} cycle(s)"))

    path_index: dict[str, list[Note]] = {}
    label_index: dict[str, list[Note]] = {}
    label_raw: dict[str, set[str]] = {}
    for note in notes:
        without_suffix = note.relative_path[:-3] if note.relative_path.casefold().endswith(".md") else note.relative_path
        path_index.setdefault(_lookup_key(without_suffix), []).append(note)
        labels = [Path(note.relative_path).stem]
        if note.title:
            labels.append(note.title)
        labels.extend(note.aliases)
        seen_in_note: set[str] = set()
        for label in labels:
            key = _lookup_key(label.strip())
            if not key or key in seen_in_note:
                continue
            seen_in_note.add(key)
            label_index.setdefault(key, []).append(note)
            label_raw.setdefault(key, set()).add(label)
    alias_collision_count = 0
    for key, owners in sorted(label_index.items()):
        unique_owners = {note.relative_path: note for note in owners}
        if len(unique_owners) > 1:
            alias_collision_count += 1
            raw = ", ".join(sorted(label_raw[key], key=_lookup_key))
            for note in unique_owners.values():
                _issue(issues, "error", "ALIAS_TITLE_COLLISION", f"ambiguous title/basename/alias after NFC and case normalization: {raw}", note)

    wiki_count = 0
    resolved_count = 0
    broken_count = 0
    ambiguous_count = 0
    incoming: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    outgoing: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            for match in WIKI_LINK_RE.finditer(line):
                wiki_count += 1
                content = match.group(1)
                target_part = content.split("|", 1)[0].strip()
                target_text, separator, heading_text = target_part.partition("#")
                target_text = target_text.strip().replace("\\", "/")
                heading_text = heading_text.strip() if separator else ""
                if not target_text:
                    candidates = [note] if separator else []
                else:
                    parts = target_text.split("/")
                    unsafe = URL_RE.match(target_text) or target_text.startswith("/") or PureWindowsPath(target_text).drive or any(part in ("", ".", "..") for part in parts)
                    if unsafe:
                        candidates = []
                    elif "/" in target_text:
                        normalized_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = path_index.get(_lookup_key(normalized_target), [])
                    else:
                        plain_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = label_index.get(_lookup_key(plain_target), [])
                unique_candidates = {candidate.relative_path: candidate for candidate in candidates}
                if not unique_candidates:
                    broken_count += 1
                    _issue(issues, "error", "BROKEN_WIKI_LINK", f"unresolved wiki link target: {target_text or target_part}", note, line_number)
                elif len(unique_candidates) > 1:
                    ambiguous_count += 1
                    _issue(issues, "error", "AMBIGUOUS_WIKI_LINK", f"ambiguous wiki link target: {target_text}", note, line_number)
                else:
                    target_note = next(iter(unique_candidates.values()))
                    resolved_count += 1
                    outgoing[note.relative_path].add(target_note.relative_path)
                    incoming[target_note.relative_path].add(note.relative_path)
                    if heading_text and _lookup_key(heading_text) not in target_note.headings:
                        _issue(issues, "warning", "MISSING_HEADING_FRAGMENT", f"wiki link heading not found: {heading_text}", note, line_number)

    for note in notes:
        if not incoming[note.relative_path]:
            code = "CANONICAL_NO_INCOMING" if note.metadata.get("canonical") is True else "NO_INCOMING_LINKS"
            _issue(issues, "warning", code, "note has no incoming wiki links", note)
        if note.metadata.get("type") in LINK_BENEFIT_TYPES and not outgoing[note.relative_path]:
            _issue(issues, "warning", "NO_OUTGOING_LINKS", "note type normally benefits from outgoing wiki links", note)
    hub_threshold = max(50, int(len(notes) * 0.60))
    for relative, targets in outgoing.items():
        if len(targets) > hub_threshold:
            note = next(item for item in notes if item.relative_path == relative)
            _issue(issues, "warning", "EXTREME_NAVIGATION_HUB", f"navigation note links to {len(targets)} distinct notes", note)

    secret_count = sum(1 for issue in issues if issue.code == "SECRET_FINDING")
    return _result(
        vault_root=vault_root,
        project_root=project_root,
        notes=notes,
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        issues=issues,
        canonical_scope_count=len(canonical_owners),
        wiki_count=wiki_count,
        resolved_count=resolved_count,
        broken_count=broken_count,
        ambiguous_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_count=len(evidence_records),
        unresolved_evidence_count=unresolved_evidence_count,
        ownership_conflicts=ownership_conflicts,
        cycle_count=cycle_count,
        missing_source_count=missing_source_count,
        unexpected_count=unexpected_count,
        forbidden_count=forbidden_count,
        secret_count=secret_count,
    )


def _human_report(result: ValidationResult) -> str:
    evidence_status = "PASS" if result.unresolved_evidence_ref_count == 0 else "FAIL"
    supersession_status = "PASS" if result.supersession_cycle_count == 0 else "FAIL"
    source_status = "PASS" if result.missing_source_path_count == 0 else "FAIL"
    return "\n".join(
        (
            "LocalComet Vault Validation",
            "",
            f"Status:\n{result.status}",
            "",
            f"Vault:\n{result.vault_root}",
            "",
            f"Vault revision:\n{result.vault_revision}",
            "",
            f"Markdown notes:\n{result.markdown_note_count}",
            "",
            f"Stable IDs:\n{result.stable_id_count}",
            "",
            f"Canonical scopes:\n{result.canonical_scope_count}",
            "",
            f"Obsidian auxiliary files:\n{result.obsidian_auxiliary_count}",
            "",
            f"Wiki links:\n{result.resolved_wiki_link_count} resolved\n{result.broken_link_count} broken\n{result.ambiguous_link_count} ambiguous",
            "",
            f"Evidence references:\n{evidence_status}",
            "",
            f"Supersession graph:\n{supersession_status}",
            "",
            f"Source paths:\n{source_status}",
            "",
            f"Unexpected files:\n{result.unexpected_file_count}",
            "",
            f"Secret findings:\n{result.secret_finding_count}",
            "",
            f"Errors:\n{result.error_count}",
            "",
            f"Warnings:\n{result.warning_count}",
            "",
            "Read only:\nYES",
        )
    )


def _runtime_payload(vault: str, project: str, exc: BaseException) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "vault_root": os.path.abspath(vault),
        "project_root": os.path.abspath(project),
        "error_count": 1,
        "warning_count": 0,
        "errors": [{"severity": "error", "code": "RUNTIME_FAILURE", "message": str(exc)}],
        "warnings": [],
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_vault(args.vault, args.project)
    except Exception as exc:  # Boundary: runtime failures use the exact CLI code 2.
        if args.json_output:
            print(json.dumps(_runtime_payload(args.vault, args.project, exc), ensure_ascii=False, sort_keys=True))
        else:
            print(f"LocalComet Vault Validation\n\nStatus:\nRUNTIME FAILURE\n\nError:\n{exc}\n\nRead only:\nYES")
        return 2
    if args.json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(_human_report(result))
    if result.status == "FAIL" or (args.fail_on_warnings and result.warning_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/binaries/up00-runtime-manifest.json (37 строк, 1080 байт)

````json
{
  "schemaVersion": 1,
  "workPackage": "UP00-WP01",
  "targetTriple": "x86_64-pc-windows-msvc",
  "sidecarBaseName": "localcomet-core",
  "entrypoint": "tools/run_localcomet_desktop_sidecar.py",
  "python": {
    "implementation": "CPython",
    "major": 3,
    "minor": 14,
    "licenseFile": "LICENSE.txt",
    "excludedTopLevel": [
      "__pycache__",
      "ensurepip",
      "idlelib",
      "site-packages",
      "tkinter",
      "turtledemo",
      "venv"
    ]
  },
  "sourceFiles": [
    "modules/desktop_control_plane_ru.py",
    "modules/desktop_ipc_contract_ru.py",
    "modules/desktop_sidecar_runtime_ru.py",
    "modules/knowledge_adapter_ru.py",
    "modules/knowledge_change_proposal_ru.py",
    "modules/knowledge_change_review_decision_ru.py",
    "modules/knowledge_change_review_ru.py",
    "modules/knowledge_contract_ru.py",
    "modules/knowledge_injection_ru.py",
    "modules/knowledge_review_ui_projection_ru.py",
    "modules/local_model_gateway_ru.py",
    "tools/run_localcomet_desktop_sidecar.py",
    "tools/validate_localcomet_vault.py"
  ]
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/build.rs (3 строк, 40 байт)

````rust
fn main() {
    tauri_build::build();
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/capabilities/main.json (51 строк, 1798 байт)

````json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main",
  "description": "LocalComet v6.84.6 main window with fixed bounded Control Plane, Knowledge Operations, and managed artifact commands only.",
  "windows": [
    "main"
  ],
  "permissions": [
    "allow-control-plane-bootstrap",
    "allow-control-plane-cancel-turn",
    "allow-control-plane-close-session",
    "allow-control-plane-create-session",
    "allow-control-plane-create-thread",
    "allow-control-plane-get-turn-status",
    "allow-control-plane-start-mock-turn",
    "allow-files-capability-status",
    "allow-forget-selected-file",
    "allow-knowledge-review-decision-create",
    "allow-knowledge-review-get",
    "allow-knowledge-review-list",
    "allow-knowledge-review-refresh",
    "allow-knowledge-review-snapshot",
    "allow-knowledge-turn-decide",
    "allow-knowledge-turn-preview",
    "allow-list-selected-files",
    "allow-managed-artifact-validation-status",
    "allow-managed-installed-artifacts",
    "allow-managed-model-catalog",
    "allow-managed-model-readiness",
    "allow-list-approved-downloadable-artifacts",
    "allow-start-approved-artifact-download",
    "allow-get-artifact-download-state",
    "allow-cancel-artifact-download",
    "allow-remove-managed-model",
    "allow-managed-runtime-catalog",
    "allow-managed-runtime-logs",
    "allow-managed-runtime-start",
    "allow-managed-runtime-status",
    "allow-managed-runtime-stop",
    "allow-model-binding-set",
    "allow-model-gateway-catalog",
    "allow-model-gateway-list-models",
    "allow-model-gateway-probe",
    "allow-model-turn-cancel",
    "allow-model-turn-start",
    "allow-preview-selected-file",
    "allow-select-files",
    "core:event:allow-listen",
    "core:event:allow-unlisten"
  ]
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/Cargo.toml (36 строк, 1073 байт)

````toml
[package]
name = "localcomet-desktop"
version = "6.84.6"
description = "LocalComet desktop visual shell"
edition = "2021"

[lib]
name = "localcomet_desktop_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2.6.3", features = [] }

[dependencies]
getrandom = "0.2"
serde = { version = "1.0.228", features = ["derive"] }
serde_json = "1.0.150"
sha2 = "0.10.9"
subtle = "2.6"
tauri = { version = "2.11.5", features = [] }
reqwest = { version = "0.13.4", default-features = false, features = ["blocking", "rustls"] }
zip = { version = "2.4.2", default-features = false, features = ["deflate"] }
windows-sys = { version = "0.61.2", features = [
    "Win32_Foundation",
    "Win32_NetworkManagement_IpHelper",
    "Win32_Networking_WinSock",
    "Win32_Security_Cryptography",
    "Win32_Storage_FileSystem",
    "Win32_Security",
    "Win32_System_JobObjects",
    "Win32_System_Pipes",
    "Win32_System_Threading",
    "Win32_System_WindowsProgramming",
    "Win32_UI_WindowsAndMessaging",
    "Win32_UI_Controls_Dialogs",
] }
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/gen/schemas/acl-manifests.json (1 строк, 74714 байт)

````json
{"__app-acl__":{"default_permission":null,"permissions":{"allow-cancel-artifact-download":{"identifier":"allow-cancel-artifact-download","description":"Allow cancelling one bounded LocalComet artifact download.","commands":{"allow":["cancel_artifact_download"],"deny":[]}},"allow-control-plane-bootstrap":{"identifier":"allow-control-plane-bootstrap","description":"Allow LocalComet control-plane bootstrap.","commands":{"allow":["control_plane_bootstrap"],"deny":[]}},"allow-control-plane-cancel-turn":{"identifier":"allow-control-plane-cancel-turn","description":"Allow cancelling a LocalComet control-plane turn.","commands":{"allow":["control_plane_cancel_turn"],"deny":[]}},"allow-control-plane-close-session":{"identifier":"allow-control-plane-close-session","description":"Allow closing a LocalComet control-plane session.","commands":{"allow":["control_plane_close_session"],"deny":[]}},"allow-control-plane-create-session":{"identifier":"allow-control-plane-create-session","description":"Allow creating a LocalComet control-plane session.","commands":{"allow":["control_plane_create_session"],"deny":[]}},"allow-control-plane-create-thread":{"identifier":"allow-control-plane-create-thread","description":"Allow creating a LocalComet control-plane thread.","commands":{"allow":["control_plane_create_thread"],"deny":[]}},"allow-control-plane-get-turn-status":{"identifier":"allow-control-plane-get-turn-status","description":"Allow reading LocalComet control-plane turn status.","commands":{"allow":["control_plane_get_turn_status"],"deny":[]}},"allow-control-plane-start-mock-turn":{"identifier":"allow-control-plane-start-mock-turn","description":"Allow starting a mock LocalComet control-plane turn.","commands":{"allow":["control_plane_start_mock_turn"],"deny":[]}},"allow-files-capability-status":{"identifier":"allow-files-capability-status","description":"Allow reading the fixed read-only Files capability contract.","commands":{"allow":["files_capability_status"],"deny":[]}},"allow-forget-selected-file":{"identifier":"allow-forget-selected-file","description":"Allow revoking one backend-issued opaque file identity from the current process.","commands":{"allow":["forget_selected_file"],"deny":[]}},"allow-get-artifact-download-state":{"identifier":"allow-get-artifact-download-state","description":"Allow reading one bounded LocalComet artifact download state.","commands":{"allow":["get_artifact_download_state"],"deny":[]}},"allow-knowledge-review-decision-create":{"identifier":"allow-knowledge-review-decision-create","description":"Allow creating one bounded in-memory human review decision artifact.","commands":{"allow":["knowledge_review_decision_create"],"deny":[]}},"allow-knowledge-review-get":{"identifier":"allow-knowledge-review-get","description":"Allow reading one exact bounded knowledge review projection.","commands":{"allow":["knowledge_review_get"],"deny":[]}},"allow-knowledge-review-list":{"identifier":"allow-knowledge-review-list","description":"Allow listing bounded read-only knowledge review summaries.","commands":{"allow":["knowledge_review_list"],"deny":[]}},"allow-knowledge-review-refresh":{"identifier":"allow-knowledge-review-refresh","description":"Allow refreshing read-only LocalComet knowledge review freshness state.","commands":{"allow":["knowledge_review_refresh"],"deny":[]}},"allow-knowledge-review-snapshot":{"identifier":"allow-knowledge-review-snapshot","description":"Allow reading the bounded LocalComet knowledge review inbox snapshot.","commands":{"allow":["knowledge_review_snapshot"],"deny":[]}},"allow-knowledge-turn-decide":{"identifier":"allow-knowledge-turn-decide","description":"Allow one bounded user decision for an exact project-knowledge preview.","commands":{"allow":["knowledge_turn_decide"],"deny":[]}},"allow-knowledge-turn-preview":{"identifier":"allow-knowledge-turn-preview","description":"Allow preparing one bounded project-knowledge preview for an existing Turn.","commands":{"allow":["knowledge_turn_preview"],"deny":[]}},"allow-list-approved-downloadable-artifacts":{"identifier":"allow-list-approved-downloadable-artifacts","description":"Allow reading the fixed approved LocalComet acquisition catalog projection.","commands":{"allow":["list_approved_downloadable_artifacts"],"deny":[]}},"allow-list-selected-files":{"identifier":"allow-list-selected-files","description":"Allow listing sanitized metadata for the current in-memory selected-file registry.","commands":{"allow":["list_selected_files"],"deny":[]}},"allow-managed-artifact-validation-status":{"identifier":"allow-managed-artifact-validation-status","description":"Allow reading live validation status for one LocalComet catalog artifact ID.","commands":{"allow":["managed_artifact_validation_status"],"deny":[]}},"allow-managed-installed-artifacts":{"identifier":"allow-managed-installed-artifacts","description":"Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog.","commands":{"allow":["managed_installed_artifacts"],"deny":[]}},"allow-managed-model-catalog":{"identifier":"allow-managed-model-catalog","description":"Allow reading safe approved model metadata from the immutable LocalComet artifact catalog.","commands":{"allow":["managed_model_catalog"],"deny":[]}},"allow-managed-model-readiness":{"identifier":"allow-managed-model-readiness","description":"Allow reading runtime compatibility and readiness for one LocalComet catalog model ID.","commands":{"allow":["managed_model_readiness"],"deny":[]}},"allow-managed-runtime-catalog":{"identifier":"allow-managed-runtime-catalog","description":"Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog.","commands":{"allow":["managed_runtime_catalog"],"deny":[]}},"allow-managed-runtime-logs":{"identifier":"allow-managed-runtime-logs","description":"Allow reading bounded sanitized managed runtime log tails.","commands":{"allow":["managed_runtime_logs"],"deny":[]}},"allow-managed-runtime-start":{"identifier":"allow-managed-runtime-start","description":"Allow starting the fixed LocalComet managed llama.cpp runtime.","commands":{"allow":["managed_runtime_start"],"deny":[]}},"allow-managed-runtime-status":{"identifier":"allow-managed-runtime-status","description":"Allow reading sanitized LocalComet managed runtime status.","commands":{"allow":["managed_runtime_status"],"deny":[]}},"allow-managed-runtime-stop":{"identifier":"allow-managed-runtime-stop","description":"Allow stopping the active LocalComet managed llama.cpp runtime.","commands":{"allow":["managed_runtime_stop"],"deny":[]}},"allow-model-binding-set":{"identifier":"allow-model-binding-set","description":"Allow confirming an in-memory LocalComet model binding.","commands":{"allow":["model_binding_set"],"deny":[]}},"allow-model-gateway-catalog":{"identifier":"allow-model-gateway-catalog","description":"Allow reading the fixed LocalComet model gateway catalog.","commands":{"allow":["model_gateway_catalog"],"deny":[]}},"allow-model-gateway-list-models":{"identifier":"allow-model-gateway-list-models","description":"Allow listing models from the fixed loopback-only local model gateway.","commands":{"allow":["model_gateway_list_models"],"deny":[]}},"allow-model-gateway-probe":{"identifier":"allow-model-gateway-probe","description":"Allow probing the fixed loopback-only local model gateway.","commands":{"allow":["model_gateway_probe"],"deny":[]}},"allow-model-turn-cancel":{"identifier":"allow-model-turn-cancel","description":"Allow cancelling the active local text model turn.","commands":{"allow":["model_turn_cancel"],"deny":[]}},"allow-model-turn-start":{"identifier":"allow-model-turn-start","description":"Allow starting one bounded local text model turn.","commands":{"allow":["model_turn_start"],"deny":[]}},"allow-preview-selected-file":{"identifier":"allow-preview-selected-file","description":"Allow a bounded preview reread through one backend-issued opaque file identity.","commands":{"allow":["preview_selected_file"],"deny":[]}},"allow-remove-managed-model":{"identifier":"allow-remove-managed-model","description":"Allow explicitly confirmed removal of one inactive approved managed model.","commands":{"allow":["remove_managed_model"],"deny":[]}},"allow-select-files":{"identifier":"allow-select-files","description":"Allow opening the native picker and registering explicitly selected read-only text files.","commands":{"allow":["select_files"],"deny":[]}},"allow-start-approved-artifact-download":{"identifier":"allow-start-approved-artifact-download","description":"Allow an explicitly confirmed download of one catalog-approved LocalComet artifact.","commands":{"allow":["start_approved_artifact_download"],"deny":[]}}},"permission_sets":{},"global_scope_schema":null},"core":{"default_permission":{"identifier":"default","description":"Default core plugins set.","permissions":["core:path:default","core:event:default","core:window:default","core:webview:default","core:app:default","core:image:default","core:resources:default","core:menu:default","core:tray:default"]},"permissions":{},"permission_sets":{},"global_scope_schema":null},"core:app":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin.","permissions":["allow-version","allow-name","allow-tauri-version","allow-identifier","allow-bundle-type","allow-register-listener","allow-remove-listener","allow-supports-multiple-windows"]},"permissions":{"allow-app-hide":{"identifier":"allow-app-hide","description":"Enables the app_hide command without any pre-configured scope.","commands":{"allow":["app_hide"],"deny":[]}},"allow-app-show":{"identifier":"allow-app-show","description":"Enables the app_show command without any pre-configured scope.","commands":{"allow":["app_show"],"deny":[]}},"allow-bundle-type":{"identifier":"allow-bundle-type","description":"Enables the bundle_type command without any pre-configured scope.","commands":{"allow":["bundle_type"],"deny":[]}},"allow-default-window-icon":{"identifier":"allow-default-window-icon","description":"Enables the default_window_icon command without any pre-configured scope.","commands":{"allow":["default_window_icon"],"deny":[]}},"allow-fetch-data-store-identifiers":{"identifier":"allow-fetch-data-store-identifiers","description":"Enables the fetch_data_store_identifiers command without any pre-configured scope.","commands":{"allow":["fetch_data_store_identifiers"],"deny":[]}},"allow-identifier":{"identifier":"allow-identifier","description":"Enables the identifier command without any pre-configured scope.","commands":{"allow":["identifier"],"deny":[]}},"allow-name":{"identifier":"allow-name","description":"Enables the name command without any pre-configured scope.","commands":{"allow":["name"],"deny":[]}},"allow-register-listener":{"identifier":"allow-register-listener","description":"Enables the register_listener command without any pre-configured scope.","commands":{"allow":["register_listener"],"deny":[]}},"allow-remove-data-store":{"identifier":"allow-remove-data-store","description":"Enables the remove_data_store command without any pre-configured scope.","commands":{"allow":["remove_data_store"],"deny":[]}},"allow-remove-listener":{"identifier":"allow-remove-listener","description":"Enables the remove_listener command without any pre-configured scope.","commands":{"allow":["remove_listener"],"deny":[]}},"allow-set-app-theme":{"identifier":"allow-set-app-theme","description":"Enables the set_app_theme command without any pre-configured scope.","commands":{"allow":["set_app_theme"],"deny":[]}},"allow-set-dock-visibility":{"identifier":"allow-set-dock-visibility","description":"Enables the set_dock_visibility command without any pre-configured scope.","commands":{"allow":["set_dock_visibility"],"deny":[]}},"allow-supports-multiple-windows":{"identifier":"allow-supports-multiple-windows","description":"Enables the supports_multiple_windows command without any pre-configured scope.","commands":{"allow":["supports_multiple_windows"],"deny":[]}},"allow-tauri-version":{"identifier":"allow-tauri-version","description":"Enables the tauri_version command without any pre-configured scope.","commands":{"allow":["tauri_version"],"deny":[]}},"allow-version":{"identifier":"allow-version","description":"Enables the version command without any pre-configured scope.","commands":{"allow":["version"],"deny":[]}},"deny-app-hide":{"identifier":"deny-app-hide","description":"Denies the app_hide command without any pre-configured scope.","commands":{"allow":[],"deny":["app_hide"]}},"deny-app-show":{"identifier":"deny-app-show","description":"Denies the app_show command without any pre-configured scope.","commands":{"allow":[],"deny":["app_show"]}},"deny-bundle-type":{"identifier":"deny-bundle-type","description":"Denies the bundle_type command without any pre-configured scope.","commands":{"allow":[],"deny":["bundle_type"]}},"deny-default-window-icon":{"identifier":"deny-default-window-icon","description":"Denies the default_window_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["default_window_icon"]}},"deny-fetch-data-store-identifiers":{"identifier":"deny-fetch-data-store-identifiers","description":"Denies the fetch_data_store_identifiers command without any pre-configured scope.","commands":{"allow":[],"deny":["fetch_data_store_identifiers"]}},"deny-identifier":{"identifier":"deny-identifier","description":"Denies the identifier command without any pre-configured scope.","commands":{"allow":[],"deny":["identifier"]}},"deny-name":{"identifier":"deny-name","description":"Denies the name command without any pre-configured scope.","commands":{"allow":[],"deny":["name"]}},"deny-register-listener":{"identifier":"deny-register-listener","description":"Denies the register_listener command without any pre-configured scope.","commands":{"allow":[],"deny":["register_listener"]}},"deny-remove-data-store":{"identifier":"deny-remove-data-store","description":"Denies the remove_data_store command without any pre-configured scope.","commands":{"allow":[],"deny":["remove_data_store"]}},"deny-remove-listener":{"identifier":"deny-remove-listener","description":"Denies the remove_listener command without any pre-configured scope.","commands":{"allow":[],"deny":["remove_listener"]}},"deny-set-app-theme":{"identifier":"deny-set-app-theme","description":"Denies the set_app_theme command without any pre-configured scope.","commands":{"allow":[],"deny":["set_app_theme"]}},"deny-set-dock-visibility":{"identifier":"deny-set-dock-visibility","description":"Denies the set_dock_visibility command without any pre-configured scope.","commands":{"allow":[],"deny":["set_dock_visibility"]}},"deny-supports-multiple-windows":{"identifier":"deny-supports-multiple-windows","description":"Denies the supports_multiple_windows command without any pre-configured scope.","commands":{"allow":[],"deny":["supports_multiple_windows"]}},"deny-tauri-version":{"identifier":"deny-tauri-version","description":"Denies the tauri_version command without any pre-configured scope.","commands":{"allow":[],"deny":["tauri_version"]}},"deny-version":{"identifier":"deny-version","description":"Denies the version command without any pre-configured scope.","commands":{"allow":[],"deny":["version"]}}},"permission_sets":{},"global_scope_schema":null},"core:event":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-listen","allow-unlisten","allow-emit","allow-emit-to"]},"permissions":{"allow-emit":{"identifier":"allow-emit","description":"Enables the emit command without any pre-configured scope.","commands":{"allow":["emit"],"deny":[]}},"allow-emit-to":{"identifier":"allow-emit-to","description":"Enables the emit_to command without any pre-configured scope.","commands":{"allow":["emit_to"],"deny":[]}},"allow-listen":{"identifier":"allow-listen","description":"Enables the listen command without any pre-configured scope.","commands":{"allow":["listen"],"deny":[]}},"allow-unlisten":{"identifier":"allow-unlisten","description":"Enables the unlisten command without any pre-configured scope.","commands":{"allow":["unlisten"],"deny":[]}},"deny-emit":{"identifier":"deny-emit","description":"Denies the emit command without any pre-configured scope.","commands":{"allow":[],"deny":["emit"]}},"deny-emit-to":{"identifier":"deny-emit-to","description":"Denies the emit_to command without any pre-configured scope.","commands":{"allow":[],"deny":["emit_to"]}},"deny-listen":{"identifier":"deny-listen","description":"Denies the listen command without any pre-configured scope.","commands":{"allow":[],"deny":["listen"]}},"deny-unlisten":{"identifier":"deny-unlisten","description":"Denies the unlisten command without any pre-configured scope.","commands":{"allow":[],"deny":["unlisten"]}}},"permission_sets":{},"global_scope_schema":null},"core:image":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-new","allow-from-bytes","allow-from-path","allow-rgba","allow-size"]},"permissions":{"allow-from-bytes":{"identifier":"allow-from-bytes","description":"Enables the from_bytes command without any pre-configured scope.","commands":{"allow":["from_bytes"],"deny":[]}},"allow-from-path":{"identifier":"allow-from-path","description":"Enables the from_path command without any pre-configured scope.","commands":{"allow":["from_path"],"deny":[]}},"allow-new":{"identifier":"allow-new","description":"Enables the new command without any pre-configured scope.","commands":{"allow":["new"],"deny":[]}},"allow-rgba":{"identifier":"allow-rgba","description":"Enables the rgba command without any pre-configured scope.","commands":{"allow":["rgba"],"deny":[]}},"allow-size":{"identifier":"allow-size","description":"Enables the size command without any pre-configured scope.","commands":{"allow":["size"],"deny":[]}},"deny-from-bytes":{"identifier":"deny-from-bytes","description":"Denies the from_bytes command without any pre-configured scope.","commands":{"allow":[],"deny":["from_bytes"]}},"deny-from-path":{"identifier":"deny-from-path","description":"Denies the from_path command without any pre-configured scope.","commands":{"allow":[],"deny":["from_path"]}},"deny-new":{"identifier":"deny-new","description":"Denies the new command without any pre-configured scope.","commands":{"allow":[],"deny":["new"]}},"deny-rgba":{"identifier":"deny-rgba","description":"Denies the rgba command without any pre-configured scope.","commands":{"allow":[],"deny":["rgba"]}},"deny-size":{"identifier":"deny-size","description":"Denies the size command without any pre-configured scope.","commands":{"allow":[],"deny":["size"]}}},"permission_sets":{},"global_scope_schema":null},"core:menu":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-new","allow-append","allow-prepend","allow-insert","allow-remove","allow-remove-at","allow-items","allow-get","allow-popup","allow-create-default","allow-set-as-app-menu","allow-set-as-window-menu","allow-text","allow-set-text","allow-is-enabled","allow-set-enabled","allow-set-accelerator","allow-set-as-windows-menu-for-nsapp","allow-set-as-help-menu-for-nsapp","allow-is-checked","allow-set-checked","allow-set-icon"]},"permissions":{"allow-append":{"identifier":"allow-append","description":"Enables the append command without any pre-configured scope.","commands":{"allow":["append"],"deny":[]}},"allow-create-default":{"identifier":"allow-create-default","description":"Enables the create_default command without any pre-configured scope.","commands":{"allow":["create_default"],"deny":[]}},"allow-get":{"identifier":"allow-get","description":"Enables the get command without any pre-configured scope.","commands":{"allow":["get"],"deny":[]}},"allow-insert":{"identifier":"allow-insert","description":"Enables the insert command without any pre-configured scope.","commands":{"allow":["insert"],"deny":[]}},"allow-is-checked":{"identifier":"allow-is-checked","description":"Enables the is_checked command without any pre-configured scope.","commands":{"allow":["is_checked"],"deny":[]}},"allow-is-enabled":{"identifier":"allow-is-enabled","description":"Enables the is_enabled command without any pre-configured scope.","commands":{"allow":["is_enabled"],"deny":[]}},"allow-items":{"identifier":"allow-items","description":"Enables the items command without any pre-configured scope.","commands":{"allow":["items"],"deny":[]}},"allow-new":{"identifier":"allow-new","description":"Enables the new command without any pre-configured scope.","commands":{"allow":["new"],"deny":[]}},"allow-popup":{"identifier":"allow-popup","description":"Enables the popup command without any pre-configured scope.","commands":{"allow":["popup"],"deny":[]}},"allow-prepend":{"identifier":"allow-prepend","description":"Enables the prepend command without any pre-configured scope.","commands":{"allow":["prepend"],"deny":[]}},"allow-remove":{"identifier":"allow-remove","description":"Enables the remove command without any pre-configured scope.","commands":{"allow":["remove"],"deny":[]}},"allow-remove-at":{"identifier":"allow-remove-at","description":"Enables the remove_at command without any pre-configured scope.","commands":{"allow":["remove_at"],"deny":[]}},"allow-set-accelerator":{"identifier":"allow-set-accelerator","description":"Enables the set_accelerator command without any pre-configured scope.","commands":{"allow":["set_accelerator"],"deny":[]}},"allow-set-as-app-menu":{"identifier":"allow-set-as-app-menu","description":"Enables the set_as_app_menu command without any pre-configured scope.","commands":{"allow":["set_as_app_menu"],"deny":[]}},"allow-set-as-help-menu-for-nsapp":{"identifier":"allow-set-as-help-menu-for-nsapp","description":"Enables the set_as_help_menu_for_nsapp command without any pre-configured scope.","commands":{"allow":["set_as_help_menu_for_nsapp"],"deny":[]}},"allow-set-as-window-menu":{"identifier":"allow-set-as-window-menu","description":"Enables the set_as_window_menu command without any pre-configured scope.","commands":{"allow":["set_as_window_menu"],"deny":[]}},"allow-set-as-windows-menu-for-nsapp":{"identifier":"allow-set-as-windows-menu-for-nsapp","description":"Enables the set_as_windows_menu_for_nsapp command without any pre-configured scope.","commands":{"allow":["set_as_windows_menu_for_nsapp"],"deny":[]}},"allow-set-checked":{"identifier":"allow-set-checked","description":"Enables the set_checked command without any pre-configured scope.","commands":{"allow":["set_checked"],"deny":[]}},"allow-set-enabled":{"identifier":"allow-set-enabled","description":"Enables the set_enabled command without any pre-configured scope.","commands":{"allow":["set_enabled"],"deny":[]}},"allow-set-icon":{"identifier":"allow-set-icon","description":"Enables the set_icon command without any pre-configured scope.","commands":{"allow":["set_icon"],"deny":[]}},"allow-set-text":{"identifier":"allow-set-text","description":"Enables the set_text command without any pre-configured scope.","commands":{"allow":["set_text"],"deny":[]}},"allow-text":{"identifier":"allow-text","description":"Enables the text command without any pre-configured scope.","commands":{"allow":["text"],"deny":[]}},"deny-append":{"identifier":"deny-append","description":"Denies the append command without any pre-configured scope.","commands":{"allow":[],"deny":["append"]}},"deny-create-default":{"identifier":"deny-create-default","description":"Denies the create_default command without any pre-configured scope.","commands":{"allow":[],"deny":["create_default"]}},"deny-get":{"identifier":"deny-get","description":"Denies the get command without any pre-configured scope.","commands":{"allow":[],"deny":["get"]}},"deny-insert":{"identifier":"deny-insert","description":"Denies the insert command without any pre-configured scope.","commands":{"allow":[],"deny":["insert"]}},"deny-is-checked":{"identifier":"deny-is-checked","description":"Denies the is_checked command without any pre-configured scope.","commands":{"allow":[],"deny":["is_checked"]}},"deny-is-enabled":{"identifier":"deny-is-enabled","description":"Denies the is_enabled command without any pre-configured scope.","commands":{"allow":[],"deny":["is_enabled"]}},"deny-items":{"identifier":"deny-items","description":"Denies the items command without any pre-configured scope.","commands":{"allow":[],"deny":["items"]}},"deny-new":{"identifier":"deny-new","description":"Denies the new command without any pre-configured scope.","commands":{"allow":[],"deny":["new"]}},"deny-popup":{"identifier":"deny-popup","description":"Denies the popup command without any pre-configured scope.","commands":{"allow":[],"deny":["popup"]}},"deny-prepend":{"identifier":"deny-prepend","description":"Denies the prepend command without any pre-configured scope.","commands":{"allow":[],"deny":["prepend"]}},"deny-remove":{"identifier":"deny-remove","description":"Denies the remove command without any pre-configured scope.","commands":{"allow":[],"deny":["remove"]}},"deny-remove-at":{"identifier":"deny-remove-at","description":"Denies the remove_at command without any pre-configured scope.","commands":{"allow":[],"deny":["remove_at"]}},"deny-set-accelerator":{"identifier":"deny-set-accelerator","description":"Denies the set_accelerator command without any pre-configured scope.","commands":{"allow":[],"deny":["set_accelerator"]}},"deny-set-as-app-menu":{"identifier":"deny-set-as-app-menu","description":"Denies the set_as_app_menu command without any pre-configured scope.","commands":{"allow":[],"deny":["set_as_app_menu"]}},"deny-set-as-help-menu-for-nsapp":{"identifier":"deny-set-as-help-menu-for-nsapp","description":"Denies the set_as_help_menu_for_nsapp command without any pre-configured scope.","commands":{"allow":[],"deny":["set_as_help_menu_for_nsapp"]}},"deny-set-as-window-menu":{"identifier":"deny-set-as-window-menu","description":"Denies the set_as_window_menu command without any pre-configured scope.","commands":{"allow":[],"deny":["set_as_window_menu"]}},"deny-set-as-windows-menu-for-nsapp":{"identifier":"deny-set-as-windows-menu-for-nsapp","description":"Denies the set_as_windows_menu_for_nsapp command without any pre-configured scope.","commands":{"allow":[],"deny":["set_as_windows_menu_for_nsapp"]}},"deny-set-checked":{"identifier":"deny-set-checked","description":"Denies the set_checked command without any pre-configured scope.","commands":{"allow":[],"deny":["set_checked"]}},"deny-set-enabled":{"identifier":"deny-set-enabled","description":"Denies the set_enabled command without any pre-configured scope.","commands":{"allow":[],"deny":["set_enabled"]}},"deny-set-icon":{"identifier":"deny-set-icon","description":"Denies the set_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["set_icon"]}},"deny-set-text":{"identifier":"deny-set-text","description":"Denies the set_text command without any pre-configured scope.","commands":{"allow":[],"deny":["set_text"]}},"deny-text":{"identifier":"deny-text","description":"Denies the text command without any pre-configured scope.","commands":{"allow":[],"deny":["text"]}}},"permission_sets":{},"global_scope_schema":null},"core:path":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-resolve-directory","allow-resolve","allow-normalize","allow-join","allow-dirname","allow-extname","allow-basename","allow-is-absolute"]},"permissions":{"allow-basename":{"identifier":"allow-basename","description":"Enables the basename command without any pre-configured scope.","commands":{"allow":["basename"],"deny":[]}},"allow-dirname":{"identifier":"allow-dirname","description":"Enables the dirname command without any pre-configured scope.","commands":{"allow":["dirname"],"deny":[]}},"allow-extname":{"identifier":"allow-extname","description":"Enables the extname command without any pre-configured scope.","commands":{"allow":["extname"],"deny":[]}},"allow-is-absolute":{"identifier":"allow-is-absolute","description":"Enables the is_absolute command without any pre-configured scope.","commands":{"allow":["is_absolute"],"deny":[]}},"allow-join":{"identifier":"allow-join","description":"Enables the join command without any pre-configured scope.","commands":{"allow":["join"],"deny":[]}},"allow-normalize":{"identifier":"allow-normalize","description":"Enables the normalize command without any pre-configured scope.","commands":{"allow":["normalize"],"deny":[]}},"allow-resolve":{"identifier":"allow-resolve","description":"Enables the resolve command without any pre-configured scope.","commands":{"allow":["resolve"],"deny":[]}},"allow-resolve-directory":{"identifier":"allow-resolve-directory","description":"Enables the resolve_directory command without any pre-configured scope.","commands":{"allow":["resolve_directory"],"deny":[]}},"deny-basename":{"identifier":"deny-basename","description":"Denies the basename command without any pre-configured scope.","commands":{"allow":[],"deny":["basename"]}},"deny-dirname":{"identifier":"deny-dirname","description":"Denies the dirname command without any pre-configured scope.","commands":{"allow":[],"deny":["dirname"]}},"deny-extname":{"identifier":"deny-extname","description":"Denies the extname command without any pre-configured scope.","commands":{"allow":[],"deny":["extname"]}},"deny-is-absolute":{"identifier":"deny-is-absolute","description":"Denies the is_absolute command without any pre-configured scope.","commands":{"allow":[],"deny":["is_absolute"]}},"deny-join":{"identifier":"deny-join","description":"Denies the join command without any pre-configured scope.","commands":{"allow":[],"deny":["join"]}},"deny-normalize":{"identifier":"deny-normalize","description":"Denies the normalize command without any pre-configured scope.","commands":{"allow":[],"deny":["normalize"]}},"deny-resolve":{"identifier":"deny-resolve","description":"Denies the resolve command without any pre-configured scope.","commands":{"allow":[],"deny":["resolve"]}},"deny-resolve-directory":{"identifier":"deny-resolve-directory","description":"Denies the resolve_directory command without any pre-configured scope.","commands":{"allow":[],"deny":["resolve_directory"]}}},"permission_sets":{},"global_scope_schema":null},"core:resources":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-close"]},"permissions":{"allow-close":{"identifier":"allow-close","description":"Enables the close command without any pre-configured scope.","commands":{"allow":["close"],"deny":[]}},"deny-close":{"identifier":"deny-close","description":"Denies the close command without any pre-configured scope.","commands":{"allow":[],"deny":["close"]}}},"permission_sets":{},"global_scope_schema":null},"core:tray":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin, which enables all commands.","permissions":["allow-new","allow-get-by-id","allow-remove-by-id","allow-set-icon","allow-set-menu","allow-set-tooltip","allow-set-title","allow-set-visible","allow-set-temp-dir-path","allow-set-icon-as-template","allow-set-icon-with-as-template","allow-set-show-menu-on-left-click"]},"permissions":{"allow-get-by-id":{"identifier":"allow-get-by-id","description":"Enables the get_by_id command without any pre-configured scope.","commands":{"allow":["get_by_id"],"deny":[]}},"allow-new":{"identifier":"allow-new","description":"Enables the new command without any pre-configured scope.","commands":{"allow":["new"],"deny":[]}},"allow-remove-by-id":{"identifier":"allow-remove-by-id","description":"Enables the remove_by_id command without any pre-configured scope.","commands":{"allow":["remove_by_id"],"deny":[]}},"allow-set-icon":{"identifier":"allow-set-icon","description":"Enables the set_icon command without any pre-configured scope.","commands":{"allow":["set_icon"],"deny":[]}},"allow-set-icon-as-template":{"identifier":"allow-set-icon-as-template","description":"Enables the set_icon_as_template command without any pre-configured scope.","commands":{"allow":["set_icon_as_template"],"deny":[]}},"allow-set-icon-with-as-template":{"identifier":"allow-set-icon-with-as-template","description":"Enables the set_icon_with_as_template command without any pre-configured scope.","commands":{"allow":["set_icon_with_as_template"],"deny":[]}},"allow-set-menu":{"identifier":"allow-set-menu","description":"Enables the set_menu command without any pre-configured scope.","commands":{"allow":["set_menu"],"deny":[]}},"allow-set-show-menu-on-left-click":{"identifier":"allow-set-show-menu-on-left-click","description":"Enables the set_show_menu_on_left_click command without any pre-configured scope.","commands":{"allow":["set_show_menu_on_left_click"],"deny":[]}},"allow-set-temp-dir-path":{"identifier":"allow-set-temp-dir-path","description":"Enables the set_temp_dir_path command without any pre-configured scope.","commands":{"allow":["set_temp_dir_path"],"deny":[]}},"allow-set-title":{"identifier":"allow-set-title","description":"Enables the set_title command without any pre-configured scope.","commands":{"allow":["set_title"],"deny":[]}},"allow-set-tooltip":{"identifier":"allow-set-tooltip","description":"Enables the set_tooltip command without any pre-configured scope.","commands":{"allow":["set_tooltip"],"deny":[]}},"allow-set-visible":{"identifier":"allow-set-visible","description":"Enables the set_visible command without any pre-configured scope.","commands":{"allow":["set_visible"],"deny":[]}},"deny-get-by-id":{"identifier":"deny-get-by-id","description":"Denies the get_by_id command without any pre-configured scope.","commands":{"allow":[],"deny":["get_by_id"]}},"deny-new":{"identifier":"deny-new","description":"Denies the new command without any pre-configured scope.","commands":{"allow":[],"deny":["new"]}},"deny-remove-by-id":{"identifier":"deny-remove-by-id","description":"Denies the remove_by_id command without any pre-configured scope.","commands":{"allow":[],"deny":["remove_by_id"]}},"deny-set-icon":{"identifier":"deny-set-icon","description":"Denies the set_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["set_icon"]}},"deny-set-icon-as-template":{"identifier":"deny-set-icon-as-template","description":"Denies the set_icon_as_template command without any pre-configured scope.","commands":{"allow":[],"deny":["set_icon_as_template"]}},"deny-set-icon-with-as-template":{"identifier":"deny-set-icon-with-as-template","description":"Denies the set_icon_with_as_template command without any pre-configured scope.","commands":{"allow":[],"deny":["set_icon_with_as_template"]}},"deny-set-menu":{"identifier":"deny-set-menu","description":"Denies the set_menu command without any pre-configured scope.","commands":{"allow":[],"deny":["set_menu"]}},"deny-set-show-menu-on-left-click":{"identifier":"deny-set-show-menu-on-left-click","description":"Denies the set_show_menu_on_left_click command without any pre-configured scope.","commands":{"allow":[],"deny":["set_show_menu_on_left_click"]}},"deny-set-temp-dir-path":{"identifier":"deny-set-temp-dir-path","description":"Denies the set_temp_dir_path command without any pre-configured scope.","commands":{"allow":[],"deny":["set_temp_dir_path"]}},"deny-set-title":{"identifier":"deny-set-title","description":"Denies the set_title command without any pre-configured scope.","commands":{"allow":[],"deny":["set_title"]}},"deny-set-tooltip":{"identifier":"deny-set-tooltip","description":"Denies the set_tooltip command without any pre-configured scope.","commands":{"allow":[],"deny":["set_tooltip"]}},"deny-set-visible":{"identifier":"deny-set-visible","description":"Denies the set_visible command without any pre-configured scope.","commands":{"allow":[],"deny":["set_visible"]}}},"permission_sets":{},"global_scope_schema":null},"core:webview":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin.","permissions":["allow-get-all-webviews","allow-webview-position","allow-webview-size","allow-internal-toggle-devtools"]},"permissions":{"allow-clear-all-browsing-data":{"identifier":"allow-clear-all-browsing-data","description":"Enables the clear_all_browsing_data command without any pre-configured scope.","commands":{"allow":["clear_all_browsing_data"],"deny":[]}},"allow-create-webview":{"identifier":"allow-create-webview","description":"Enables the create_webview command without any pre-configured scope.","commands":{"allow":["create_webview"],"deny":[]}},"allow-create-webview-window":{"identifier":"allow-create-webview-window","description":"Enables the create_webview_window command without any pre-configured scope.","commands":{"allow":["create_webview_window"],"deny":[]}},"allow-get-all-webviews":{"identifier":"allow-get-all-webviews","description":"Enables the get_all_webviews command without any pre-configured scope.","commands":{"allow":["get_all_webviews"],"deny":[]}},"allow-internal-toggle-devtools":{"identifier":"allow-internal-toggle-devtools","description":"Enables the internal_toggle_devtools command without any pre-configured scope.","commands":{"allow":["internal_toggle_devtools"],"deny":[]}},"allow-print":{"identifier":"allow-print","description":"Enables the print command without any pre-configured scope.","commands":{"allow":["print"],"deny":[]}},"allow-reparent":{"identifier":"allow-reparent","description":"Enables the reparent command without any pre-configured scope.","commands":{"allow":["reparent"],"deny":[]}},"allow-set-webview-auto-resize":{"identifier":"allow-set-webview-auto-resize","description":"Enables the set_webview_auto_resize command without any pre-configured scope.","commands":{"allow":["set_webview_auto_resize"],"deny":[]}},"allow-set-webview-background-color":{"identifier":"allow-set-webview-background-color","description":"Enables the set_webview_background_color command without any pre-configured scope.","commands":{"allow":["set_webview_background_color"],"deny":[]}},"allow-set-webview-focus":{"identifier":"allow-set-webview-focus","description":"Enables the set_webview_focus command without any pre-configured scope.","commands":{"allow":["set_webview_focus"],"deny":[]}},"allow-set-webview-position":{"identifier":"allow-set-webview-position","description":"Enables the set_webview_position command without any pre-configured scope.","commands":{"allow":["set_webview_position"],"deny":[]}},"allow-set-webview-size":{"identifier":"allow-set-webview-size","description":"Enables the set_webview_size command without any pre-configured scope.","commands":{"allow":["set_webview_size"],"deny":[]}},"allow-set-webview-zoom":{"identifier":"allow-set-webview-zoom","description":"Enables the set_webview_zoom command without any pre-configured scope.","commands":{"allow":["set_webview_zoom"],"deny":[]}},"allow-webview-close":{"identifier":"allow-webview-close","description":"Enables the webview_close command without any pre-configured scope.","commands":{"allow":["webview_close"],"deny":[]}},"allow-webview-hide":{"identifier":"allow-webview-hide","description":"Enables the webview_hide command without any pre-configured scope.","commands":{"allow":["webview_hide"],"deny":[]}},"allow-webview-position":{"identifier":"allow-webview-position","description":"Enables the webview_position command without any pre-configured scope.","commands":{"allow":["webview_position"],"deny":[]}},"allow-webview-show":{"identifier":"allow-webview-show","description":"Enables the webview_show command without any pre-configured scope.","commands":{"allow":["webview_show"],"deny":[]}},"allow-webview-size":{"identifier":"allow-webview-size","description":"Enables the webview_size command without any pre-configured scope.","commands":{"allow":["webview_size"],"deny":[]}},"deny-clear-all-browsing-data":{"identifier":"deny-clear-all-browsing-data","description":"Denies the clear_all_browsing_data command without any pre-configured scope.","commands":{"allow":[],"deny":["clear_all_browsing_data"]}},"deny-create-webview":{"identifier":"deny-create-webview","description":"Denies the create_webview command without any pre-configured scope.","commands":{"allow":[],"deny":["create_webview"]}},"deny-create-webview-window":{"identifier":"deny-create-webview-window","description":"Denies the create_webview_window command without any pre-configured scope.","commands":{"allow":[],"deny":["create_webview_window"]}},"deny-get-all-webviews":{"identifier":"deny-get-all-webviews","description":"Denies the get_all_webviews command without any pre-configured scope.","commands":{"allow":[],"deny":["get_all_webviews"]}},"deny-internal-toggle-devtools":{"identifier":"deny-internal-toggle-devtools","description":"Denies the internal_toggle_devtools command without any pre-configured scope.","commands":{"allow":[],"deny":["internal_toggle_devtools"]}},"deny-print":{"identifier":"deny-print","description":"Denies the print command without any pre-configured scope.","commands":{"allow":[],"deny":["print"]}},"deny-reparent":{"identifier":"deny-reparent","description":"Denies the reparent command without any pre-configured scope.","commands":{"allow":[],"deny":["reparent"]}},"deny-set-webview-auto-resize":{"identifier":"deny-set-webview-auto-resize","description":"Denies the set_webview_auto_resize command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_auto_resize"]}},"deny-set-webview-background-color":{"identifier":"deny-set-webview-background-color","description":"Denies the set_webview_background_color command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_background_color"]}},"deny-set-webview-focus":{"identifier":"deny-set-webview-focus","description":"Denies the set_webview_focus command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_focus"]}},"deny-set-webview-position":{"identifier":"deny-set-webview-position","description":"Denies the set_webview_position command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_position"]}},"deny-set-webview-size":{"identifier":"deny-set-webview-size","description":"Denies the set_webview_size command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_size"]}},"deny-set-webview-zoom":{"identifier":"deny-set-webview-zoom","description":"Denies the set_webview_zoom command without any pre-configured scope.","commands":{"allow":[],"deny":["set_webview_zoom"]}},"deny-webview-close":{"identifier":"deny-webview-close","description":"Denies the webview_close command without any pre-configured scope.","commands":{"allow":[],"deny":["webview_close"]}},"deny-webview-hide":{"identifier":"deny-webview-hide","description":"Denies the webview_hide command without any pre-configured scope.","commands":{"allow":[],"deny":["webview_hide"]}},"deny-webview-position":{"identifier":"deny-webview-position","description":"Denies the webview_position command without any pre-configured scope.","commands":{"allow":[],"deny":["webview_position"]}},"deny-webview-show":{"identifier":"deny-webview-show","description":"Denies the webview_show command without any pre-configured scope.","commands":{"allow":[],"deny":["webview_show"]}},"deny-webview-size":{"identifier":"deny-webview-size","description":"Denies the webview_size command without any pre-configured scope.","commands":{"allow":[],"deny":["webview_size"]}}},"permission_sets":{},"global_scope_schema":null},"core:window":{"default_permission":{"identifier":"default","description":"Default permissions for the plugin.","permissions":["allow-get-all-windows","allow-scale-factor","allow-inner-position","allow-outer-position","allow-inner-size","allow-outer-size","allow-is-fullscreen","allow-is-minimized","allow-is-maximized","allow-is-focused","allow-is-decorated","allow-is-resizable","allow-is-maximizable","allow-is-minimizable","allow-is-closable","allow-is-visible","allow-is-enabled","allow-title","allow-current-monitor","allow-primary-monitor","allow-monitor-from-point","allow-available-monitors","allow-cursor-position","allow-theme","allow-is-always-on-top","allow-activity-name","allow-scene-identifier","allow-internal-toggle-maximize"]},"permissions":{"allow-activity-name":{"identifier":"allow-activity-name","description":"Enables the activity_name command without any pre-configured scope.","commands":{"allow":["activity_name"],"deny":[]}},"allow-available-monitors":{"identifier":"allow-available-monitors","description":"Enables the available_monitors command without any pre-configured scope.","commands":{"allow":["available_monitors"],"deny":[]}},"allow-center":{"identifier":"allow-center","description":"Enables the center command without any pre-configured scope.","commands":{"allow":["center"],"deny":[]}},"allow-close":{"identifier":"allow-close","description":"Enables the close command without any pre-configured scope.","commands":{"allow":["close"],"deny":[]}},"allow-create":{"identifier":"allow-create","description":"Enables the create command without any pre-configured scope.","commands":{"allow":["create"],"deny":[]}},"allow-current-monitor":{"identifier":"allow-current-monitor","description":"Enables the current_monitor command without any pre-configured scope.","commands":{"allow":["current_monitor"],"deny":[]}},"allow-cursor-position":{"identifier":"allow-cursor-position","description":"Enables the cursor_position command without any pre-configured scope.","commands":{"allow":["cursor_position"],"deny":[]}},"allow-destroy":{"identifier":"allow-destroy","description":"Enables the destroy command without any pre-configured scope.","commands":{"allow":["destroy"],"deny":[]}},"allow-get-all-windows":{"identifier":"allow-get-all-windows","description":"Enables the get_all_windows command without any pre-configured scope.","commands":{"allow":["get_all_windows"],"deny":[]}},"allow-hide":{"identifier":"allow-hide","description":"Enables the hide command without any pre-configured scope.","commands":{"allow":["hide"],"deny":[]}},"allow-inner-position":{"identifier":"allow-inner-position","description":"Enables the inner_position command without any pre-configured scope.","commands":{"allow":["inner_position"],"deny":[]}},"allow-inner-size":{"identifier":"allow-inner-size","description":"Enables the inner_size command without any pre-configured scope.","commands":{"allow":["inner_size"],"deny":[]}},"allow-internal-toggle-maximize":{"identifier":"allow-internal-toggle-maximize","description":"Enables the internal_toggle_maximize command without any pre-configured scope.","commands":{"allow":["internal_toggle_maximize"],"deny":[]}},"allow-is-always-on-top":{"identifier":"allow-is-always-on-top","description":"Enables the is_always_on_top command without any pre-configured scope.","commands":{"allow":["is_always_on_top"],"deny":[]}},"allow-is-closable":{"identifier":"allow-is-closable","description":"Enables the is_closable command without any pre-configured scope.","commands":{"allow":["is_closable"],"deny":[]}},"allow-is-decorated":{"identifier":"allow-is-decorated","description":"Enables the is_decorated command without any pre-configured scope.","commands":{"allow":["is_decorated"],"deny":[]}},"allow-is-enabled":{"identifier":"allow-is-enabled","description":"Enables the is_enabled command without any pre-configured scope.","commands":{"allow":["is_enabled"],"deny":[]}},"allow-is-focused":{"identifier":"allow-is-focused","description":"Enables the is_focused command without any pre-configured scope.","commands":{"allow":["is_focused"],"deny":[]}},"allow-is-fullscreen":{"identifier":"allow-is-fullscreen","description":"Enables the is_fullscreen command without any pre-configured scope.","commands":{"allow":["is_fullscreen"],"deny":[]}},"allow-is-maximizable":{"identifier":"allow-is-maximizable","description":"Enables the is_maximizable command without any pre-configured scope.","commands":{"allow":["is_maximizable"],"deny":[]}},"allow-is-maximized":{"identifier":"allow-is-maximized","description":"Enables the is_maximized command without any pre-configured scope.","commands":{"allow":["is_maximized"],"deny":[]}},"allow-is-minimizable":{"identifier":"allow-is-minimizable","description":"Enables the is_minimizable command without any pre-configured scope.","commands":{"allow":["is_minimizable"],"deny":[]}},"allow-is-minimized":{"identifier":"allow-is-minimized","description":"Enables the is_minimized command without any pre-configured scope.","commands":{"allow":["is_minimized"],"deny":[]}},"allow-is-resizable":{"identifier":"allow-is-resizable","description":"Enables the is_resizable command without any pre-configured scope.","commands":{"allow":["is_resizable"],"deny":[]}},"allow-is-visible":{"identifier":"allow-is-visible","description":"Enables the is_visible command without any pre-configured scope.","commands":{"allow":["is_visible"],"deny":[]}},"allow-maximize":{"identifier":"allow-maximize","description":"Enables the maximize command without any pre-configured scope.","commands":{"allow":["maximize"],"deny":[]}},"allow-minimize":{"identifier":"allow-minimize","description":"Enables the minimize command without any pre-configured scope.","commands":{"allow":["minimize"],"deny":[]}},"allow-monitor-from-point":{"identifier":"allow-monitor-from-point","description":"Enables the monitor_from_point command without any pre-configured scope.","commands":{"allow":["monitor_from_point"],"deny":[]}},"allow-outer-position":{"identifier":"allow-outer-position","description":"Enables the outer_position command without any pre-configured scope.","commands":{"allow":["outer_position"],"deny":[]}},"allow-outer-size":{"identifier":"allow-outer-size","description":"Enables the outer_size command without any pre-configured scope.","commands":{"allow":["outer_size"],"deny":[]}},"allow-primary-monitor":{"identifier":"allow-primary-monitor","description":"Enables the primary_monitor command without any pre-configured scope.","commands":{"allow":["primary_monitor"],"deny":[]}},"allow-request-user-attention":{"identifier":"allow-request-user-attention","description":"Enables the request_user_attention command without any pre-configured scope.","commands":{"allow":["request_user_attention"],"deny":[]}},"allow-scale-factor":{"identifier":"allow-scale-factor","description":"Enables the scale_factor command without any pre-configured scope.","commands":{"allow":["scale_factor"],"deny":[]}},"allow-scene-identifier":{"identifier":"allow-scene-identifier","description":"Enables the scene_identifier command without any pre-configured scope.","commands":{"allow":["scene_identifier"],"deny":[]}},"allow-set-always-on-bottom":{"identifier":"allow-set-always-on-bottom","description":"Enables the set_always_on_bottom command without any pre-configured scope.","commands":{"allow":["set_always_on_bottom"],"deny":[]}},"allow-set-always-on-top":{"identifier":"allow-set-always-on-top","description":"Enables the set_always_on_top command without any pre-configured scope.","commands":{"allow":["set_always_on_top"],"deny":[]}},"allow-set-background-color":{"identifier":"allow-set-background-color","description":"Enables the set_background_color command without any pre-configured scope.","commands":{"allow":["set_background_color"],"deny":[]}},"allow-set-badge-count":{"identifier":"allow-set-badge-count","description":"Enables the set_badge_count command without any pre-configured scope.","commands":{"allow":["set_badge_count"],"deny":[]}},"allow-set-badge-label":{"identifier":"allow-set-badge-label","description":"Enables the set_badge_label command without any pre-configured scope.","commands":{"allow":["set_badge_label"],"deny":[]}},"allow-set-closable":{"identifier":"allow-set-closable","description":"Enables the set_closable command without any pre-configured scope.","commands":{"allow":["set_closable"],"deny":[]}},"allow-set-content-protected":{"identifier":"allow-set-content-protected","description":"Enables the set_content_protected command without any pre-configured scope.","commands":{"allow":["set_content_protected"],"deny":[]}},"allow-set-cursor-grab":{"identifier":"allow-set-cursor-grab","description":"Enables the set_cursor_grab command without any pre-configured scope.","commands":{"allow":["set_cursor_grab"],"deny":[]}},"allow-set-cursor-icon":{"identifier":"allow-set-cursor-icon","description":"Enables the set_cursor_icon command without any pre-configured scope.","commands":{"allow":["set_cursor_icon"],"deny":[]}},"allow-set-cursor-position":{"identifier":"allow-set-cursor-position","description":"Enables the set_cursor_position command without any pre-configured scope.","commands":{"allow":["set_cursor_position"],"deny":[]}},"allow-set-cursor-visible":{"identifier":"allow-set-cursor-visible","description":"Enables the set_cursor_visible command without any pre-configured scope.","commands":{"allow":["set_cursor_visible"],"deny":[]}},"allow-set-decorations":{"identifier":"allow-set-decorations","description":"Enables the set_decorations command without any pre-configured scope.","commands":{"allow":["set_decorations"],"deny":[]}},"allow-set-effects":{"identifier":"allow-set-effects","description":"Enables the set_effects command without any pre-configured scope.","commands":{"allow":["set_effects"],"deny":[]}},"allow-set-enabled":{"identifier":"allow-set-enabled","description":"Enables the set_enabled command without any pre-configured scope.","commands":{"allow":["set_enabled"],"deny":[]}},"allow-set-focus":{"identifier":"allow-set-focus","description":"Enables the set_focus command without any pre-configured scope.","commands":{"allow":["set_focus"],"deny":[]}},"allow-set-focusable":{"identifier":"allow-set-focusable","description":"Enables the set_focusable command without any pre-configured scope.","commands":{"allow":["set_focusable"],"deny":[]}},"allow-set-fullscreen":{"identifier":"allow-set-fullscreen","description":"Enables the set_fullscreen command without any pre-configured scope.","commands":{"allow":["set_fullscreen"],"deny":[]}},"allow-set-icon":{"identifier":"allow-set-icon","description":"Enables the set_icon command without any pre-configured scope.","commands":{"allow":["set_icon"],"deny":[]}},"allow-set-ignore-cursor-events":{"identifier":"allow-set-ignore-cursor-events","description":"Enables the set_ignore_cursor_events command without any pre-configured scope.","commands":{"allow":["set_ignore_cursor_events"],"deny":[]}},"allow-set-max-size":{"identifier":"allow-set-max-size","description":"Enables the set_max_size command without any pre-configured scope.","commands":{"allow":["set_max_size"],"deny":[]}},"allow-set-maximizable":{"identifier":"allow-set-maximizable","description":"Enables the set_maximizable command without any pre-configured scope.","commands":{"allow":["set_maximizable"],"deny":[]}},"allow-set-min-size":{"identifier":"allow-set-min-size","description":"Enables the set_min_size command without any pre-configured scope.","commands":{"allow":["set_min_size"],"deny":[]}},"allow-set-minimizable":{"identifier":"allow-set-minimizable","description":"Enables the set_minimizable command without any pre-configured scope.","commands":{"allow":["set_minimizable"],"deny":[]}},"allow-set-overlay-icon":{"identifier":"allow-set-overlay-icon","description":"Enables the set_overlay_icon command without any pre-configured scope.","commands":{"allow":["set_overlay_icon"],"deny":[]}},"allow-set-position":{"identifier":"allow-set-position","description":"Enables the set_position command without any pre-configured scope.","commands":{"allow":["set_position"],"deny":[]}},"allow-set-progress-bar":{"identifier":"allow-set-progress-bar","description":"Enables the set_progress_bar command without any pre-configured scope.","commands":{"allow":["set_progress_bar"],"deny":[]}},"allow-set-resizable":{"identifier":"allow-set-resizable","description":"Enables the set_resizable command without any pre-configured scope.","commands":{"allow":["set_resizable"],"deny":[]}},"allow-set-shadow":{"identifier":"allow-set-shadow","description":"Enables the set_shadow command without any pre-configured scope.","commands":{"allow":["set_shadow"],"deny":[]}},"allow-set-simple-fullscreen":{"identifier":"allow-set-simple-fullscreen","description":"Enables the set_simple_fullscreen command without any pre-configured scope.","commands":{"allow":["set_simple_fullscreen"],"deny":[]}},"allow-set-size":{"identifier":"allow-set-size","description":"Enables the set_size command without any pre-configured scope.","commands":{"allow":["set_size"],"deny":[]}},"allow-set-size-constraints":{"identifier":"allow-set-size-constraints","description":"Enables the set_size_constraints command without any pre-configured scope.","commands":{"allow":["set_size_constraints"],"deny":[]}},"allow-set-skip-taskbar":{"identifier":"allow-set-skip-taskbar","description":"Enables the set_skip_taskbar command without any pre-configured scope.","commands":{"allow":["set_skip_taskbar"],"deny":[]}},"allow-set-theme":{"identifier":"allow-set-theme","description":"Enables the set_theme command without any pre-configured scope.","commands":{"allow":["set_theme"],"deny":[]}},"allow-set-title":{"identifier":"allow-set-title","description":"Enables the set_title command without any pre-configured scope.","commands":{"allow":["set_title"],"deny":[]}},"allow-set-title-bar-style":{"identifier":"allow-set-title-bar-style","description":"Enables the set_title_bar_style command without any pre-configured scope.","commands":{"allow":["set_title_bar_style"],"deny":[]}},"allow-set-visible-on-all-workspaces":{"identifier":"allow-set-visible-on-all-workspaces","description":"Enables the set_visible_on_all_workspaces command without any pre-configured scope.","commands":{"allow":["set_visible_on_all_workspaces"],"deny":[]}},"allow-show":{"identifier":"allow-show","description":"Enables the show command without any pre-configured scope.","commands":{"allow":["show"],"deny":[]}},"allow-start-dragging":{"identifier":"allow-start-dragging","description":"Enables the start_dragging command without any pre-configured scope.","commands":{"allow":["start_dragging"],"deny":[]}},"allow-start-resize-dragging":{"identifier":"allow-start-resize-dragging","description":"Enables the start_resize_dragging command without any pre-configured scope.","commands":{"allow":["start_resize_dragging"],"deny":[]}},"allow-theme":{"identifier":"allow-theme","description":"Enables the theme command without any pre-configured scope.","commands":{"allow":["theme"],"deny":[]}},"allow-title":{"identifier":"allow-title","description":"Enables the title command without any pre-configured scope.","commands":{"allow":["title"],"deny":[]}},"allow-toggle-maximize":{"identifier":"allow-toggle-maximize","description":"Enables the toggle_maximize command without any pre-configured scope.","commands":{"allow":["toggle_maximize"],"deny":[]}},"allow-unmaximize":{"identifier":"allow-unmaximize","description":"Enables the unmaximize command without any pre-configured scope.","commands":{"allow":["unmaximize"],"deny":[]}},"allow-unminimize":{"identifier":"allow-unminimize","description":"Enables the unminimize command without any pre-configured scope.","commands":{"allow":["unminimize"],"deny":[]}},"deny-activity-name":{"identifier":"deny-activity-name","description":"Denies the activity_name command without any pre-configured scope.","commands":{"allow":[],"deny":["activity_name"]}},"deny-available-monitors":{"identifier":"deny-available-monitors","description":"Denies the available_monitors command without any pre-configured scope.","commands":{"allow":[],"deny":["available_monitors"]}},"deny-center":{"identifier":"deny-center","description":"Denies the center command without any pre-configured scope.","commands":{"allow":[],"deny":["center"]}},"deny-close":{"identifier":"deny-close","description":"Denies the close command without any pre-configured scope.","commands":{"allow":[],"deny":["close"]}},"deny-create":{"identifier":"deny-create","description":"Denies the create command without any pre-configured scope.","commands":{"allow":[],"deny":["create"]}},"deny-current-monitor":{"identifier":"deny-current-monitor","description":"Denies the current_monitor command without any pre-configured scope.","commands":{"allow":[],"deny":["current_monitor"]}},"deny-cursor-position":{"identifier":"deny-cursor-position","description":"Denies the cursor_position command without any pre-configured scope.","commands":{"allow":[],"deny":["cursor_position"]}},"deny-destroy":{"identifier":"deny-destroy","description":"Denies the destroy command without any pre-configured scope.","commands":{"allow":[],"deny":["destroy"]}},"deny-get-all-windows":{"identifier":"deny-get-all-windows","description":"Denies the get_all_windows command without any pre-configured scope.","commands":{"allow":[],"deny":["get_all_windows"]}},"deny-hide":{"identifier":"deny-hide","description":"Denies the hide command without any pre-configured scope.","commands":{"allow":[],"deny":["hide"]}},"deny-inner-position":{"identifier":"deny-inner-position","description":"Denies the inner_position command without any pre-configured scope.","commands":{"allow":[],"deny":["inner_position"]}},"deny-inner-size":{"identifier":"deny-inner-size","description":"Denies the inner_size command without any pre-configured scope.","commands":{"allow":[],"deny":["inner_size"]}},"deny-internal-toggle-maximize":{"identifier":"deny-internal-toggle-maximize","description":"Denies the internal_toggle_maximize command without any pre-configured scope.","commands":{"allow":[],"deny":["internal_toggle_maximize"]}},"deny-is-always-on-top":{"identifier":"deny-is-always-on-top","description":"Denies the is_always_on_top command without any pre-configured scope.","commands":{"allow":[],"deny":["is_always_on_top"]}},"deny-is-closable":{"identifier":"deny-is-closable","description":"Denies the is_closable command without any pre-configured scope.","commands":{"allow":[],"deny":["is_closable"]}},"deny-is-decorated":{"identifier":"deny-is-decorated","description":"Denies the is_decorated command without any pre-configured scope.","commands":{"allow":[],"deny":["is_decorated"]}},"deny-is-enabled":{"identifier":"deny-is-enabled","description":"Denies the is_enabled command without any pre-configured scope.","commands":{"allow":[],"deny":["is_enabled"]}},"deny-is-focused":{"identifier":"deny-is-focused","description":"Denies the is_focused command without any pre-configured scope.","commands":{"allow":[],"deny":["is_focused"]}},"deny-is-fullscreen":{"identifier":"deny-is-fullscreen","description":"Denies the is_fullscreen command without any pre-configured scope.","commands":{"allow":[],"deny":["is_fullscreen"]}},"deny-is-maximizable":{"identifier":"deny-is-maximizable","description":"Denies the is_maximizable command without any pre-configured scope.","commands":{"allow":[],"deny":["is_maximizable"]}},"deny-is-maximized":{"identifier":"deny-is-maximized","description":"Denies the is_maximized command without any pre-configured scope.","commands":{"allow":[],"deny":["is_maximized"]}},"deny-is-minimizable":{"identifier":"deny-is-minimizable","description":"Denies the is_minimizable command without any pre-configured scope.","commands":{"allow":[],"deny":["is_minimizable"]}},"deny-is-minimized":{"identifier":"deny-is-minimized","description":"Denies the is_minimized command without any pre-configured scope.","commands":{"allow":[],"deny":["is_minimized"]}},"deny-is-resizable":{"identifier":"deny-is-resizable","description":"Denies the is_resizable command without any pre-configured scope.","commands":{"allow":[],"deny":["is_resizable"]}},"deny-is-visible":{"identifier":"deny-is-visible","description":"Denies the is_visible command without any pre-configured scope.","commands":{"allow":[],"deny":["is_visible"]}},"deny-maximize":{"identifier":"deny-maximize","description":"Denies the maximize command without any pre-configured scope.","commands":{"allow":[],"deny":["maximize"]}},"deny-minimize":{"identifier":"deny-minimize","description":"Denies the minimize command without any pre-configured scope.","commands":{"allow":[],"deny":["minimize"]}},"deny-monitor-from-point":{"identifier":"deny-monitor-from-point","description":"Denies the monitor_from_point command without any pre-configured scope.","commands":{"allow":[],"deny":["monitor_from_point"]}},"deny-outer-position":{"identifier":"deny-outer-position","description":"Denies the outer_position command without any pre-configured scope.","commands":{"allow":[],"deny":["outer_position"]}},"deny-outer-size":{"identifier":"deny-outer-size","description":"Denies the outer_size command without any pre-configured scope.","commands":{"allow":[],"deny":["outer_size"]}},"deny-primary-monitor":{"identifier":"deny-primary-monitor","description":"Denies the primary_monitor command without any pre-configured scope.","commands":{"allow":[],"deny":["primary_monitor"]}},"deny-request-user-attention":{"identifier":"deny-request-user-attention","description":"Denies the request_user_attention command without any pre-configured scope.","commands":{"allow":[],"deny":["request_user_attention"]}},"deny-scale-factor":{"identifier":"deny-scale-factor","description":"Denies the scale_factor command without any pre-configured scope.","commands":{"allow":[],"deny":["scale_factor"]}},"deny-scene-identifier":{"identifier":"deny-scene-identifier","description":"Denies the scene_identifier command without any pre-configured scope.","commands":{"allow":[],"deny":["scene_identifier"]}},"deny-set-always-on-bottom":{"identifier":"deny-set-always-on-bottom","description":"Denies the set_always_on_bottom command without any pre-configured scope.","commands":{"allow":[],"deny":["set_always_on_bottom"]}},"deny-set-always-on-top":{"identifier":"deny-set-always-on-top","description":"Denies the set_always_on_top command without any pre-configured scope.","commands":{"allow":[],"deny":["set_always_on_top"]}},"deny-set-background-color":{"identifier":"deny-set-background-color","description":"Denies the set_background_color command without any pre-configured scope.","commands":{"allow":[],"deny":["set_background_color"]}},"deny-set-badge-count":{"identifier":"deny-set-badge-count","description":"Denies the set_badge_count command without any pre-configured scope.","commands":{"allow":[],"deny":["set_badge_count"]}},"deny-set-badge-label":{"identifier":"deny-set-badge-label","description":"Denies the set_badge_label command without any pre-configured scope.","commands":{"allow":[],"deny":["set_badge_label"]}},"deny-set-closable":{"identifier":"deny-set-closable","description":"Denies the set_closable command without any pre-configured scope.","commands":{"allow":[],"deny":["set_closable"]}},"deny-set-content-protected":{"identifier":"deny-set-content-protected","description":"Denies the set_content_protected command without any pre-configured scope.","commands":{"allow":[],"deny":["set_content_protected"]}},"deny-set-cursor-grab":{"identifier":"deny-set-cursor-grab","description":"Denies the set_cursor_grab command without any pre-configured scope.","commands":{"allow":[],"deny":["set_cursor_grab"]}},"deny-set-cursor-icon":{"identifier":"deny-set-cursor-icon","description":"Denies the set_cursor_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["set_cursor_icon"]}},"deny-set-cursor-position":{"identifier":"deny-set-cursor-position","description":"Denies the set_cursor_position command without any pre-configured scope.","commands":{"allow":[],"deny":["set_cursor_position"]}},"deny-set-cursor-visible":{"identifier":"deny-set-cursor-visible","description":"Denies the set_cursor_visible command without any pre-configured scope.","commands":{"allow":[],"deny":["set_cursor_visible"]}},"deny-set-decorations":{"identifier":"deny-set-decorations","description":"Denies the set_decorations command without any pre-configured scope.","commands":{"allow":[],"deny":["set_decorations"]}},"deny-set-effects":{"identifier":"deny-set-effects","description":"Denies the set_effects command without any pre-configured scope.","commands":{"allow":[],"deny":["set_effects"]}},"deny-set-enabled":{"identifier":"deny-set-enabled","description":"Denies the set_enabled command without any pre-configured scope.","commands":{"allow":[],"deny":["set_enabled"]}},"deny-set-focus":{"identifier":"deny-set-focus","description":"Denies the set_focus command without any pre-configured scope.","commands":{"allow":[],"deny":["set_focus"]}},"deny-set-focusable":{"identifier":"deny-set-focusable","description":"Denies the set_focusable command without any pre-configured scope.","commands":{"allow":[],"deny":["set_focusable"]}},"deny-set-fullscreen":{"identifier":"deny-set-fullscreen","description":"Denies the set_fullscreen command without any pre-configured scope.","commands":{"allow":[],"deny":["set_fullscreen"]}},"deny-set-icon":{"identifier":"deny-set-icon","description":"Denies the set_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["set_icon"]}},"deny-set-ignore-cursor-events":{"identifier":"deny-set-ignore-cursor-events","description":"Denies the set_ignore_cursor_events command without any pre-configured scope.","commands":{"allow":[],"deny":["set_ignore_cursor_events"]}},"deny-set-max-size":{"identifier":"deny-set-max-size","description":"Denies the set_max_size command without any pre-configured scope.","commands":{"allow":[],"deny":["set_max_size"]}},"deny-set-maximizable":{"identifier":"deny-set-maximizable","description":"Denies the set_maximizable command without any pre-configured scope.","commands":{"allow":[],"deny":["set_maximizable"]}},"deny-set-min-size":{"identifier":"deny-set-min-size","description":"Denies the set_min_size command without any pre-configured scope.","commands":{"allow":[],"deny":["set_min_size"]}},"deny-set-minimizable":{"identifier":"deny-set-minimizable","description":"Denies the set_minimizable command without any pre-configured scope.","commands":{"allow":[],"deny":["set_minimizable"]}},"deny-set-overlay-icon":{"identifier":"deny-set-overlay-icon","description":"Denies the set_overlay_icon command without any pre-configured scope.","commands":{"allow":[],"deny":["set_overlay_icon"]}},"deny-set-position":{"identifier":"deny-set-position","description":"Denies the set_position command without any pre-configured scope.","commands":{"allow":[],"deny":["set_position"]}},"deny-set-progress-bar":{"identifier":"deny-set-progress-bar","description":"Denies the set_progress_bar command without any pre-configured scope.","commands":{"allow":[],"deny":["set_progress_bar"]}},"deny-set-resizable":{"identifier":"deny-set-resizable","description":"Denies the set_resizable command without any pre-configured scope.","commands":{"allow":[],"deny":["set_resizable"]}},"deny-set-shadow":{"identifier":"deny-set-shadow","description":"Denies the set_shadow command without any pre-configured scope.","commands":{"allow":[],"deny":["set_shadow"]}},"deny-set-simple-fullscreen":{"identifier":"deny-set-simple-fullscreen","description":"Denies the set_simple_fullscreen command without any pre-configured scope.","commands":{"allow":[],"deny":["set_simple_fullscreen"]}},"deny-set-size":{"identifier":"deny-set-size","description":"Denies the set_size command without any pre-configured scope.","commands":{"allow":[],"deny":["set_size"]}},"deny-set-size-constraints":{"identifier":"deny-set-size-constraints","description":"Denies the set_size_constraints command without any pre-configured scope.","commands":{"allow":[],"deny":["set_size_constraints"]}},"deny-set-skip-taskbar":{"identifier":"deny-set-skip-taskbar","description":"Denies the set_skip_taskbar command without any pre-configured scope.","commands":{"allow":[],"deny":["set_skip_taskbar"]}},"deny-set-theme":{"identifier":"deny-set-theme","description":"Denies the set_theme command without any pre-configured scope.","commands":{"allow":[],"deny":["set_theme"]}},"deny-set-title":{"identifier":"deny-set-title","description":"Denies the set_title command without any pre-configured scope.","commands":{"allow":[],"deny":["set_title"]}},"deny-set-title-bar-style":{"identifier":"deny-set-title-bar-style","description":"Denies the set_title_bar_style command without any pre-configured scope.","commands":{"allow":[],"deny":["set_title_bar_style"]}},"deny-set-visible-on-all-workspaces":{"identifier":"deny-set-visible-on-all-workspaces","description":"Denies the set_visible_on_all_workspaces command without any pre-configured scope.","commands":{"allow":[],"deny":["set_visible_on_all_workspaces"]}},"deny-show":{"identifier":"deny-show","description":"Denies the show command without any pre-configured scope.","commands":{"allow":[],"deny":["show"]}},"deny-start-dragging":{"identifier":"deny-start-dragging","description":"Denies the start_dragging command without any pre-configured scope.","commands":{"allow":[],"deny":["start_dragging"]}},"deny-start-resize-dragging":{"identifier":"deny-start-resize-dragging","description":"Denies the start_resize_dragging command without any pre-configured scope.","commands":{"allow":[],"deny":["start_resize_dragging"]}},"deny-theme":{"identifier":"deny-theme","description":"Denies the theme command without any pre-configured scope.","commands":{"allow":[],"deny":["theme"]}},"deny-title":{"identifier":"deny-title","description":"Denies the title command without any pre-configured scope.","commands":{"allow":[],"deny":["title"]}},"deny-toggle-maximize":{"identifier":"deny-toggle-maximize","description":"Denies the toggle_maximize command without any pre-configured scope.","commands":{"allow":[],"deny":["toggle_maximize"]}},"deny-unmaximize":{"identifier":"deny-unmaximize","description":"Denies the unmaximize command without any pre-configured scope.","commands":{"allow":[],"deny":["unmaximize"]}},"deny-unminimize":{"identifier":"deny-unminimize","description":"Denies the unminimize command without any pre-configured scope.","commands":{"allow":[],"deny":["unminimize"]}}},"permission_sets":{},"global_scope_schema":null}}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/gen/schemas/capabilities.json (1 строк, 1535 байт)

````json
{"main":{"identifier":"main","description":"LocalComet v6.84.6 main window with fixed bounded Control Plane, Knowledge Operations, and managed artifact commands only.","local":true,"windows":["main"],"permissions":["allow-control-plane-bootstrap","allow-control-plane-cancel-turn","allow-control-plane-close-session","allow-control-plane-create-session","allow-control-plane-create-thread","allow-control-plane-get-turn-status","allow-control-plane-start-mock-turn","allow-files-capability-status","allow-forget-selected-file","allow-knowledge-review-decision-create","allow-knowledge-review-get","allow-knowledge-review-list","allow-knowledge-review-refresh","allow-knowledge-review-snapshot","allow-knowledge-turn-decide","allow-knowledge-turn-preview","allow-list-selected-files","allow-managed-artifact-validation-status","allow-managed-installed-artifacts","allow-managed-model-catalog","allow-managed-model-readiness","allow-list-approved-downloadable-artifacts","allow-start-approved-artifact-download","allow-get-artifact-download-state","allow-cancel-artifact-download","allow-remove-managed-model","allow-managed-runtime-catalog","allow-managed-runtime-logs","allow-managed-runtime-start","allow-managed-runtime-status","allow-managed-runtime-stop","allow-model-binding-set","allow-model-gateway-catalog","allow-model-gateway-list-models","allow-model-gateway-probe","allow-model-turn-cancel","allow-model-turn-start","allow-preview-selected-file","allow-select-files","core:event:allow-listen","core:event:allow-unlisten"]}}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/gen/schemas/desktop-schema.json (2526 строк, 127701 байт)

````json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CapabilityFile",
  "description": "Capability formats accepted in a capability file.",
  "anyOf": [
    {
      "description": "A single capability.",
      "allOf": [
        {
          "$ref": "#/definitions/Capability"
        }
      ]
    },
    {
      "description": "A list of capabilities.",
      "type": "array",
      "items": {
        "$ref": "#/definitions/Capability"
      }
    },
    {
      "description": "A list of capabilities.",
      "type": "object",
      "required": [
        "capabilities"
      ],
      "properties": {
        "capabilities": {
          "description": "The list of capabilities.",
          "type": "array",
          "items": {
            "$ref": "#/definitions/Capability"
          }
        }
      }
    }
  ],
  "definitions": {
    "Capability": {
      "description": "A grouping and boundary mechanism developers can use to isolate access to the IPC layer.\n\nIt controls application windows' and webviews' fine grained access to the Tauri core, application, or plugin commands. If a webview or its window is not matching any capability then it has no access to the IPC layer at all.\n\nThis can be done to create groups of windows, based on their required system access, which can reduce impact of frontend vulnerabilities in less privileged windows. Windows can be added to a capability by exact name (e.g. `main-window`) or glob patterns like `*` or `admin-*`. A Window can have none, one, or multiple associated capabilities.\n\n## Example\n\n```json { \"identifier\": \"main-user-files-write\", \"description\": \"This capability allows the `main` window on macOS and Windows access to `filesystem` write related commands and `dialog` commands to enable programmatic access to files selected by the user.\", \"windows\": [ \"main\" ], \"permissions\": [ \"core:default\", \"dialog:open\", { \"identifier\": \"fs:allow-write-text-file\", \"allow\": [{ \"path\": \"$HOME/test.txt\" }] }, ], \"platforms\": [\"macOS\",\"windows\"] } ```",
      "type": "object",
      "required": [
        "identifier",
        "permissions"
      ],
      "properties": {
        "identifier": {
          "description": "Identifier of the capability.\n\n## Example\n\n`main-user-files-write`",
          "type": "string"
        },
        "description": {
          "description": "Description of what the capability is intended to allow on associated windows.\n\nIt should contain a description of what the grouped permissions should allow.\n\n## Example\n\nThis capability allows the `main` window access to `filesystem` write related commands and `dialog` commands to enable programmatic access to files selected by the user.",
          "default": "",
          "type": "string"
        },
        "remote": {
          "description": "Configure remote URLs that can use the capability permissions.\n\nThis setting is optional and defaults to not being set, as our default use case is that the content is served from our local application.\n\n:::caution Make sure you understand the security implications of providing remote sources with local system access. :::\n\n## Example\n\n```json { \"urls\": [\"https://*.mydomain.dev\"] } ```",
          "anyOf": [
            {
              "$ref": "#/definitions/CapabilityRemote"
            },
            {
              "type": "null"
            }
          ]
        },
        "local": {
          "description": "Whether this capability is enabled for local app URLs or not. Defaults to `true`.",
          "default": true,
          "type": "boolean"
        },
        "windows": {
          "description": "List of windows that are affected by this capability. Can be a glob pattern.\n\nIf a window label matches any of the patterns in this list, the capability will be enabled on all the webviews of that window, regardless of the value of [`Self::webviews`].\n\nOn multiwebview windows, prefer specifying [`Self::webviews`] and omitting [`Self::windows`] for a fine grained access control.\n\n## Example\n\n`[\"main\"]`",
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "webviews": {
          "description": "List of webviews that are affected by this capability. Can be a glob pattern.\n\nThe capability will be enabled on all the webviews whose label matches any of the patterns in this list, regardless of whether the webview's window label matches a pattern in [`Self::windows`].\n\n## Example\n\n`[\"sub-webview-one\", \"sub-webview-two\"]`",
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "permissions": {
          "description": "List of permissions attached to this capability.\n\nMust include the plugin name as prefix in the form of `${plugin-name}:${permission-name}`. For commands directly implemented in the application itself only `${permission-name}` is required.\n\n## Example\n\n```json [ \"core:default\", \"shell:allow-open\", \"dialog:open\", { \"identifier\": \"fs:allow-write-text-file\", \"allow\": [{ \"path\": \"$HOME/test.txt\" }] } ] ```",
          "type": "array",
          "items": {
            "$ref": "#/definitions/PermissionEntry"
          },
          "uniqueItems": true
        },
        "platforms": {
          "description": "Limit which target platforms this capability applies to.\n\nBy default all platforms are targeted.\n\n## Example\n\n`[\"macOS\",\"windows\"]`",
          "type": [
            "array",
            "null"
          ],
          "items": {
            "$ref": "#/definitions/Target"
          }
        }
      }
    },
    "CapabilityRemote": {
      "description": "Configuration for remote URLs that are associated with the capability.",
      "type": "object",
      "required": [
        "urls"
      ],
      "properties": {
        "urls": {
          "description": "Remote domains this capability refers to using the [URLPattern standard](https://urlpattern.spec.whatwg.org/).\n\n## Examples\n\n- \"https://*.mydomain.dev\": allows subdomains of mydomain.dev - \"https://mydomain.dev/api/*\": allows any subpath of mydomain.dev/api",
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "PermissionEntry": {
      "description": "An entry for a permission value in a [`Capability`] can be either a raw permission [`Identifier`] or an object that references a permission and extends its scope.",
      "anyOf": [
        {
          "description": "Reference a permission or permission set by identifier.",
          "allOf": [
            {
              "$ref": "#/definitions/Identifier"
            }
          ]
        },
        {
          "description": "Reference a permission or permission set by identifier and extends its scope.",
          "type": "object",
          "allOf": [
            {
              "properties": {
                "identifier": {
                  "description": "Identifier of the permission or permission set.",
                  "allOf": [
                    {
                      "$ref": "#/definitions/Identifier"
                    }
                  ]
                },
                "allow": {
                  "description": "Data that defines what is allowed by the scope.",
                  "type": [
                    "array",
                    "null"
                  ],
                  "items": {
                    "$ref": "#/definitions/Value"
                  }
                },
                "deny": {
                  "description": "Data that defines what is denied by the scope. This should be prioritized by validation logic.",
                  "type": [
                    "array",
                    "null"
                  ],
                  "items": {
                    "$ref": "#/definitions/Value"
                  }
                }
              }
            }
          ],
          "required": [
            "identifier"
          ]
        }
      ]
    },
    "Identifier": {
      "description": "Permission identifier",
      "oneOf": [
        {
          "description": "Allow cancelling one bounded LocalComet artifact download.",
          "type": "string",
          "const": "allow-cancel-artifact-download",
          "markdownDescription": "Allow cancelling one bounded LocalComet artifact download."
        },
        {
          "description": "Allow LocalComet control-plane bootstrap.",
          "type": "string",
          "const": "allow-control-plane-bootstrap",
          "markdownDescription": "Allow LocalComet control-plane bootstrap."
        },
        {
          "description": "Allow cancelling a LocalComet control-plane turn.",
          "type": "string",
          "const": "allow-control-plane-cancel-turn",
          "markdownDescription": "Allow cancelling a LocalComet control-plane turn."
        },
        {
          "description": "Allow closing a LocalComet control-plane session.",
          "type": "string",
          "const": "allow-control-plane-close-session",
          "markdownDescription": "Allow closing a LocalComet control-plane session."
        },
        {
          "description": "Allow creating a LocalComet control-plane session.",
          "type": "string",
          "const": "allow-control-plane-create-session",
          "markdownDescription": "Allow creating a LocalComet control-plane session."
        },
        {
          "description": "Allow creating a LocalComet control-plane thread.",
          "type": "string",
          "const": "allow-control-plane-create-thread",
          "markdownDescription": "Allow creating a LocalComet control-plane thread."
        },
        {
          "description": "Allow reading LocalComet control-plane turn status.",
          "type": "string",
          "const": "allow-control-plane-get-turn-status",
          "markdownDescription": "Allow reading LocalComet control-plane turn status."
        },
        {
          "description": "Allow starting a mock LocalComet control-plane turn.",
          "type": "string",
          "const": "allow-control-plane-start-mock-turn",
          "markdownDescription": "Allow starting a mock LocalComet control-plane turn."
        },
        {
          "description": "Allow reading the fixed read-only Files capability contract.",
          "type": "string",
          "const": "allow-files-capability-status",
          "markdownDescription": "Allow reading the fixed read-only Files capability contract."
        },
        {
          "description": "Allow revoking one backend-issued opaque file identity from the current process.",
          "type": "string",
          "const": "allow-forget-selected-file",
          "markdownDescription": "Allow revoking one backend-issued opaque file identity from the current process."
        },
        {
          "description": "Allow reading one bounded LocalComet artifact download state.",
          "type": "string",
          "const": "allow-get-artifact-download-state",
          "markdownDescription": "Allow reading one bounded LocalComet artifact download state."
        },
        {
          "description": "Allow creating one bounded in-memory human review decision artifact.",
          "type": "string",
          "const": "allow-knowledge-review-decision-create",
          "markdownDescription": "Allow creating one bounded in-memory human review decision artifact."
        },
        {
          "description": "Allow reading one exact bounded knowledge review projection.",
          "type": "string",
          "const": "allow-knowledge-review-get",
          "markdownDescription": "Allow reading one exact bounded knowledge review projection."
        },
        {
          "description": "Allow listing bounded read-only knowledge review summaries.",
          "type": "string",
          "const": "allow-knowledge-review-list",
          "markdownDescription": "Allow listing bounded read-only knowledge review summaries."
        },
        {
          "description": "Allow refreshing read-only LocalComet knowledge review freshness state.",
          "type": "string",
          "const": "allow-knowledge-review-refresh",
          "markdownDescription": "Allow refreshing read-only LocalComet knowledge review freshness state."
        },
        {
          "description": "Allow reading the bounded LocalComet knowledge review inbox snapshot.",
          "type": "string",
          "const": "allow-knowledge-review-snapshot",
          "markdownDescription": "Allow reading the bounded LocalComet knowledge review inbox snapshot."
        },
        {
          "description": "Allow one bounded user decision for an exact project-knowledge preview.",
          "type": "string",
          "const": "allow-knowledge-turn-decide",
          "markdownDescription": "Allow one bounded user decision for an exact project-knowledge preview."
        },
        {
          "description": "Allow preparing one bounded project-knowledge preview for an existing Turn.",
          "type": "string",
          "const": "allow-knowledge-turn-preview",
          "markdownDescription": "Allow preparing one bounded project-knowledge preview for an existing Turn."
        },
        {
          "description": "Allow reading the fixed approved LocalComet acquisition catalog projection.",
          "type": "string",
          "const": "allow-list-approved-downloadable-artifacts",
          "markdownDescription": "Allow reading the fixed approved LocalComet acquisition catalog projection."
        },
        {
          "description": "Allow listing sanitized metadata for the current in-memory selected-file registry.",
          "type": "string",
          "const": "allow-list-selected-files",
          "markdownDescription": "Allow listing sanitized metadata for the current in-memory selected-file registry."
        },
        {
          "description": "Allow reading live validation status for one LocalComet catalog artifact ID.",
          "type": "string",
          "const": "allow-managed-artifact-validation-status",
          "markdownDescription": "Allow reading live validation status for one LocalComet catalog artifact ID."
        },
        {
          "description": "Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-installed-artifacts",
          "markdownDescription": "Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog."
        },
        {
          "description": "Allow reading safe approved model metadata from the immutable LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-model-catalog",
          "markdownDescription": "Allow reading safe approved model metadata from the immutable LocalComet artifact catalog."
        },
        {
          "description": "Allow reading runtime compatibility and readiness for one LocalComet catalog model ID.",
          "type": "string",
          "const": "allow-managed-model-readiness",
          "markdownDescription": "Allow reading runtime compatibility and readiness for one LocalComet catalog model ID."
        },
        {
          "description": "Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-runtime-catalog",
          "markdownDescription": "Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog."
        },
        {
          "description": "Allow reading bounded sanitized managed runtime log tails.",
          "type": "string",
          "const": "allow-managed-runtime-logs",
          "markdownDescription": "Allow reading bounded sanitized managed runtime log tails."
        },
        {
          "description": "Allow starting the fixed LocalComet managed llama.cpp runtime.",
          "type": "string",
          "const": "allow-managed-runtime-start",
          "markdownDescription": "Allow starting the fixed LocalComet managed llama.cpp runtime."
        },
        {
          "description": "Allow reading sanitized LocalComet managed runtime status.",
          "type": "string",
          "const": "allow-managed-runtime-status",
          "markdownDescription": "Allow reading sanitized LocalComet managed runtime status."
        },
        {
          "description": "Allow stopping the active LocalComet managed llama.cpp runtime.",
          "type": "string",
          "const": "allow-managed-runtime-stop",
          "markdownDescription": "Allow stopping the active LocalComet managed llama.cpp runtime."
        },
        {
          "description": "Allow confirming an in-memory LocalComet model binding.",
          "type": "string",
          "const": "allow-model-binding-set",
          "markdownDescription": "Allow confirming an in-memory LocalComet model binding."
        },
        {
          "description": "Allow reading the fixed LocalComet model gateway catalog.",
          "type": "string",
          "const": "allow-model-gateway-catalog",
          "markdownDescription": "Allow reading the fixed LocalComet model gateway catalog."
        },
        {
          "description": "Allow listing models from the fixed loopback-only local model gateway.",
          "type": "string",
          "const": "allow-model-gateway-list-models",
          "markdownDescription": "Allow listing models from the fixed loopback-only local model gateway."
        },
        {
          "description": "Allow probing the fixed loopback-only local model gateway.",
          "type": "string",
          "const": "allow-model-gateway-probe",
          "markdownDescription": "Allow probing the fixed loopback-only local model gateway."
        },
        {
          "description": "Allow cancelling the active local text model turn.",
          "type": "string",
          "const": "allow-model-turn-cancel",
          "markdownDescription": "Allow cancelling the active local text model turn."
        },
        {
          "description": "Allow starting one bounded local text model turn.",
          "type": "string",
          "const": "allow-model-turn-start",
          "markdownDescription": "Allow starting one bounded local text model turn."
        },
        {
          "description": "Allow a bounded preview reread through one backend-issued opaque file identity.",
          "type": "string",
          "const": "allow-preview-selected-file",
          "markdownDescription": "Allow a bounded preview reread through one backend-issued opaque file identity."
        },
        {
          "description": "Allow explicitly confirmed removal of one inactive approved managed model.",
          "type": "string",
          "const": "allow-remove-managed-model",
          "markdownDescription": "Allow explicitly confirmed removal of one inactive approved managed model."
        },
        {
          "description": "Allow opening the native picker and registering explicitly selected read-only text files.",
          "type": "string",
          "const": "allow-select-files",
          "markdownDescription": "Allow opening the native picker and registering explicitly selected read-only text files."
        },
        {
          "description": "Allow an explicitly confirmed download of one catalog-approved LocalComet artifact.",
          "type": "string",
          "const": "allow-start-approved-artifact-download",
          "markdownDescription": "Allow an explicitly confirmed download of one catalog-approved LocalComet artifact."
        },
        {
          "description": "Default core plugins set.\n#### This default permission set includes:\n\n- `core:path:default`\n- `core:event:default`\n- `core:window:default`\n- `core:webview:default`\n- `core:app:default`\n- `core:image:default`\n- `core:resources:default`\n- `core:menu:default`\n- `core:tray:default`",
          "type": "string",
          "const": "core:default",
          "markdownDescription": "Default core plugins set.\n#### This default permission set includes:\n\n- `core:path:default`\n- `core:event:default`\n- `core:window:default`\n- `core:webview:default`\n- `core:app:default`\n- `core:image:default`\n- `core:resources:default`\n- `core:menu:default`\n- `core:tray:default`"
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-version`\n- `allow-name`\n- `allow-tauri-version`\n- `allow-identifier`\n- `allow-bundle-type`\n- `allow-register-listener`\n- `allow-remove-listener`\n- `allow-supports-multiple-windows`",
          "type": "string",
          "const": "core:app:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-version`\n- `allow-name`\n- `allow-tauri-version`\n- `allow-identifier`\n- `allow-bundle-type`\n- `allow-register-listener`\n- `allow-remove-listener`\n- `allow-supports-multiple-windows`"
        },
        {
          "description": "Enables the app_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-app-hide",
          "markdownDescription": "Enables the app_hide command without any pre-configured scope."
        },
        {
          "description": "Enables the app_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-app-show",
          "markdownDescription": "Enables the app_show command without any pre-configured scope."
        },
        {
          "description": "Enables the bundle_type command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-bundle-type",
          "markdownDescription": "Enables the bundle_type command without any pre-configured scope."
        },
        {
          "description": "Enables the default_window_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-default-window-icon",
          "markdownDescription": "Enables the default_window_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the fetch_data_store_identifiers command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-fetch-data-store-identifiers",
          "markdownDescription": "Enables the fetch_data_store_identifiers command without any pre-configured scope."
        },
        {
          "description": "Enables the identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-identifier",
          "markdownDescription": "Enables the identifier command without any pre-configured scope."
        },
        {
          "description": "Enables the name command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-name",
          "markdownDescription": "Enables the name command without any pre-configured scope."
        },
        {
          "description": "Enables the register_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-register-listener",
          "markdownDescription": "Enables the register_listener command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_data_store command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-remove-data-store",
          "markdownDescription": "Enables the remove_data_store command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-remove-listener",
          "markdownDescription": "Enables the remove_listener command without any pre-configured scope."
        },
        {
          "description": "Enables the set_app_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-set-app-theme",
          "markdownDescription": "Enables the set_app_theme command without any pre-configured scope."
        },
        {
          "description": "Enables the set_dock_visibility command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-set-dock-visibility",
          "markdownDescription": "Enables the set_dock_visibility command without any pre-configured scope."
        },
        {
          "description": "Enables the supports_multiple_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-supports-multiple-windows",
          "markdownDescription": "Enables the supports_multiple_windows command without any pre-configured scope."
        },
        {
          "description": "Enables the tauri_version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-tauri-version",
          "markdownDescription": "Enables the tauri_version command without any pre-configured scope."
        },
        {
          "description": "Enables the version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-version",
          "markdownDescription": "Enables the version command without any pre-configured scope."
        },
        {
          "description": "Denies the app_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-app-hide",
          "markdownDescription": "Denies the app_hide command without any pre-configured scope."
        },
        {
          "description": "Denies the app_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-app-show",
          "markdownDescription": "Denies the app_show command without any pre-configured scope."
        },
        {
          "description": "Denies the bundle_type command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-bundle-type",
          "markdownDescription": "Denies the bundle_type command without any pre-configured scope."
        },
        {
          "description": "Denies the default_window_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-default-window-icon",
          "markdownDescription": "Denies the default_window_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the fetch_data_store_identifiers command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-fetch-data-store-identifiers",
          "markdownDescription": "Denies the fetch_data_store_identifiers command without any pre-configured scope."
        },
        {
          "description": "Denies the identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-identifier",
          "markdownDescription": "Denies the identifier command without any pre-configured scope."
        },
        {
          "description": "Denies the name command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-name",
          "markdownDescription": "Denies the name command without any pre-configured scope."
        },
        {
          "description": "Denies the register_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-register-listener",
          "markdownDescription": "Denies the register_listener command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_data_store command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-remove-data-store",
          "markdownDescription": "Denies the remove_data_store command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-remove-listener",
          "markdownDescription": "Denies the remove_listener command without any pre-configured scope."
        },
        {
          "description": "Denies the set_app_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-set-app-theme",
          "markdownDescription": "Denies the set_app_theme command without any pre-configured scope."
        },
        {
          "description": "Denies the set_dock_visibility command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-set-dock-visibility",
          "markdownDescription": "Denies the set_dock_visibility command without any pre-configured scope."
        },
        {
          "description": "Denies the supports_multiple_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-supports-multiple-windows",
          "markdownDescription": "Denies the supports_multiple_windows command without any pre-configured scope."
        },
        {
          "description": "Denies the tauri_version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-tauri-version",
          "markdownDescription": "Denies the tauri_version command without any pre-configured scope."
        },
        {
          "description": "Denies the version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-version",
          "markdownDescription": "Denies the version command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-listen`\n- `allow-unlisten`\n- `allow-emit`\n- `allow-emit-to`",
          "type": "string",
          "const": "core:event:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-listen`\n- `allow-unlisten`\n- `allow-emit`\n- `allow-emit-to`"
        },
        {
          "description": "Enables the emit command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-emit",
          "markdownDescription": "Enables the emit command without any pre-configured scope."
        },
        {
          "description": "Enables the emit_to command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-emit-to",
          "markdownDescription": "Enables the emit_to command without any pre-configured scope."
        },
        {
          "description": "Enables the listen command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-listen",
          "markdownDescription": "Enables the listen command without any pre-configured scope."
        },
        {
          "description": "Enables the unlisten command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-unlisten",
          "markdownDescription": "Enables the unlisten command without any pre-configured scope."
        },
        {
          "description": "Denies the emit command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-emit",
          "markdownDescription": "Denies the emit command without any pre-configured scope."
        },
        {
          "description": "Denies the emit_to command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-emit-to",
          "markdownDescription": "Denies the emit_to command without any pre-configured scope."
        },
        {
          "description": "Denies the listen command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-listen",
          "markdownDescription": "Denies the listen command without any pre-configured scope."
        },
        {
          "description": "Denies the unlisten command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-unlisten",
          "markdownDescription": "Denies the unlisten command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-from-bytes`\n- `allow-from-path`\n- `allow-rgba`\n- `allow-size`",
          "type": "string",
          "const": "core:image:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-from-bytes`\n- `allow-from-path`\n- `allow-rgba`\n- `allow-size`"
        },
        {
          "description": "Enables the from_bytes command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-from-bytes",
          "markdownDescription": "Enables the from_bytes command without any pre-configured scope."
        },
        {
          "description": "Enables the from_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-from-path",
          "markdownDescription": "Enables the from_path command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the rgba command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-rgba",
          "markdownDescription": "Enables the rgba command without any pre-configured scope."
        },
        {
          "description": "Enables the size command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-size",
          "markdownDescription": "Enables the size command without any pre-configured scope."
        },
        {
          "description": "Denies the from_bytes command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-from-bytes",
          "markdownDescription": "Denies the from_bytes command without any pre-configured scope."
        },
        {
          "description": "Denies the from_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-from-path",
          "markdownDescription": "Denies the from_path command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the rgba command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-rgba",
          "markdownDescription": "Denies the rgba command without any pre-configured scope."
        },
        {
          "description": "Denies the size command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-size",
          "markdownDescription": "Denies the size command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-append`\n- `allow-prepend`\n- `allow-insert`\n- `allow-remove`\n- `allow-remove-at`\n- `allow-items`\n- `allow-get`\n- `allow-popup`\n- `allow-create-default`\n- `allow-set-as-app-menu`\n- `allow-set-as-window-menu`\n- `allow-text`\n- `allow-set-text`\n- `allow-is-enabled`\n- `allow-set-enabled`\n- `allow-set-accelerator`\n- `allow-set-as-windows-menu-for-nsapp`\n- `allow-set-as-help-menu-for-nsapp`\n- `allow-is-checked`\n- `allow-set-checked`\n- `allow-set-icon`",
          "type": "string",
          "const": "core:menu:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-append`\n- `allow-prepend`\n- `allow-insert`\n- `allow-remove`\n- `allow-remove-at`\n- `allow-items`\n- `allow-get`\n- `allow-popup`\n- `allow-create-default`\n- `allow-set-as-app-menu`\n- `allow-set-as-window-menu`\n- `allow-text`\n- `allow-set-text`\n- `allow-is-enabled`\n- `allow-set-enabled`\n- `allow-set-accelerator`\n- `allow-set-as-windows-menu-for-nsapp`\n- `allow-set-as-help-menu-for-nsapp`\n- `allow-is-checked`\n- `allow-set-checked`\n- `allow-set-icon`"
        },
        {
          "description": "Enables the append command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-append",
          "markdownDescription": "Enables the append command without any pre-configured scope."
        },
        {
          "description": "Enables the create_default command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-create-default",
          "markdownDescription": "Enables the create_default command without any pre-configured scope."
        },
        {
          "description": "Enables the get command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-get",
          "markdownDescription": "Enables the get command without any pre-configured scope."
        },
        {
          "description": "Enables the insert command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-insert",
          "markdownDescription": "Enables the insert command without any pre-configured scope."
        },
        {
          "description": "Enables the is_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-is-checked",
          "markdownDescription": "Enables the is_checked command without any pre-configured scope."
        },
        {
          "description": "Enables the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-is-enabled",
          "markdownDescription": "Enables the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the items command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-items",
          "markdownDescription": "Enables the items command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the popup command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-popup",
          "markdownDescription": "Enables the popup command without any pre-configured scope."
        },
        {
          "description": "Enables the prepend command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-prepend",
          "markdownDescription": "Enables the prepend command without any pre-configured scope."
        },
        {
          "description": "Enables the remove command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-remove",
          "markdownDescription": "Enables the remove command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_at command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-remove-at",
          "markdownDescription": "Enables the remove_at command without any pre-configured scope."
        },
        {
          "description": "Enables the set_accelerator command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-accelerator",
          "markdownDescription": "Enables the set_accelerator command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_app_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-app-menu",
          "markdownDescription": "Enables the set_as_app_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_help_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-help-menu-for-nsapp",
          "markdownDescription": "Enables the set_as_help_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_window_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-window-menu",
          "markdownDescription": "Enables the set_as_window_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_windows_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-windows-menu-for-nsapp",
          "markdownDescription": "Enables the set_as_windows_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Enables the set_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-checked",
          "markdownDescription": "Enables the set_checked command without any pre-configured scope."
        },
        {
          "description": "Enables the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-enabled",
          "markdownDescription": "Enables the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-text",
          "markdownDescription": "Enables the set_text command without any pre-configured scope."
        },
        {
          "description": "Enables the text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-text",
          "markdownDescription": "Enables the text command without any pre-configured scope."
        },
        {
          "description": "Denies the append command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-append",
          "markdownDescription": "Denies the append command without any pre-configured scope."
        },
        {
          "description": "Denies the create_default command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-create-default",
          "markdownDescription": "Denies the create_default command without any pre-configured scope."
        },
        {
          "description": "Denies the get command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-get",
          "markdownDescription": "Denies the get command without any pre-configured scope."
        },
        {
          "description": "Denies the insert command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-insert",
          "markdownDescription": "Denies the insert command without any pre-configured scope."
        },
        {
          "description": "Denies the is_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-is-checked",
          "markdownDescription": "Denies the is_checked command without any pre-configured scope."
        },
        {
          "description": "Denies the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-is-enabled",
          "markdownDescription": "Denies the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the items command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-items",
          "markdownDescription": "Denies the items command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the popup command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-popup",
          "markdownDescription": "Denies the popup command without any pre-configured scope."
        },
        {
          "description": "Denies the prepend command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-prepend",
          "markdownDescription": "Denies the prepend command without any pre-configured scope."
        },
        {
          "description": "Denies the remove command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-remove",
          "markdownDescription": "Denies the remove command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_at command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-remove-at",
          "markdownDescription": "Denies the remove_at command without any pre-configured scope."
        },
        {
          "description": "Denies the set_accelerator command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-accelerator",
          "markdownDescription": "Denies the set_accelerator command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_app_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-app-menu",
          "markdownDescription": "Denies the set_as_app_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_help_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-help-menu-for-nsapp",
          "markdownDescription": "Denies the set_as_help_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_window_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-window-menu",
          "markdownDescription": "Denies the set_as_window_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_windows_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-windows-menu-for-nsapp",
          "markdownDescription": "Denies the set_as_windows_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Denies the set_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-checked",
          "markdownDescription": "Denies the set_checked command without any pre-configured scope."
        },
        {
          "description": "Denies the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-enabled",
          "markdownDescription": "Denies the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-text",
          "markdownDescription": "Denies the set_text command without any pre-configured scope."
        },
        {
          "description": "Denies the text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-text",
          "markdownDescription": "Denies the text command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-resolve-directory`\n- `allow-resolve`\n- `allow-normalize`\n- `allow-join`\n- `allow-dirname`\n- `allow-extname`\n- `allow-basename`\n- `allow-is-absolute`",
          "type": "string",
          "const": "core:path:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-resolve-directory`\n- `allow-resolve`\n- `allow-normalize`\n- `allow-join`\n- `allow-dirname`\n- `allow-extname`\n- `allow-basename`\n- `allow-is-absolute`"
        },
        {
          "description": "Enables the basename command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-basename",
          "markdownDescription": "Enables the basename command without any pre-configured scope."
        },
        {
          "description": "Enables the dirname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-dirname",
          "markdownDescription": "Enables the dirname command without any pre-configured scope."
        },
        {
          "description": "Enables the extname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-extname",
          "markdownDescription": "Enables the extname command without any pre-configured scope."
        },
        {
          "description": "Enables the is_absolute command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-is-absolute",
          "markdownDescription": "Enables the is_absolute command without any pre-configured scope."
        },
        {
          "description": "Enables the join command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-join",
          "markdownDescription": "Enables the join command without any pre-configured scope."
        },
        {
          "description": "Enables the normalize command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-normalize",
          "markdownDescription": "Enables the normalize command without any pre-configured scope."
        },
        {
          "description": "Enables the resolve command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-resolve",
          "markdownDescription": "Enables the resolve command without any pre-configured scope."
        },
        {
          "description": "Enables the resolve_directory command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-resolve-directory",
          "markdownDescription": "Enables the resolve_directory command without any pre-configured scope."
        },
        {
          "description": "Denies the basename command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-basename",
          "markdownDescription": "Denies the basename command without any pre-configured scope."
        },
        {
          "description": "Denies the dirname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-dirname",
          "markdownDescription": "Denies the dirname command without any pre-configured scope."
        },
        {
          "description": "Denies the extname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-extname",
          "markdownDescription": "Denies the extname command without any pre-configured scope."
        },
        {
          "description": "Denies the is_absolute command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-is-absolute",
          "markdownDescription": "Denies the is_absolute command without any pre-configured scope."
        },
        {
          "description": "Denies the join command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-join",
          "markdownDescription": "Denies the join command without any pre-configured scope."
        },
        {
          "description": "Denies the normalize command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-normalize",
          "markdownDescription": "Denies the normalize command without any pre-configured scope."
        },
        {
          "description": "Denies the resolve command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-resolve",
          "markdownDescription": "Denies the resolve command without any pre-configured scope."
        },
        {
          "description": "Denies the resolve_directory command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-resolve-directory",
          "markdownDescription": "Denies the resolve_directory command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-close`",
          "type": "string",
          "const": "core:resources:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-close`"
        },
        {
          "description": "Enables the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:resources:allow-close",
          "markdownDescription": "Enables the close command without any pre-configured scope."
        },
        {
          "description": "Denies the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:resources:deny-close",
          "markdownDescription": "Denies the close command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-get-by-id`\n- `allow-remove-by-id`\n- `allow-set-icon`\n- `allow-set-menu`\n- `allow-set-tooltip`\n- `allow-set-title`\n- `allow-set-visible`\n- `allow-set-temp-dir-path`\n- `allow-set-icon-as-template`\n- `allow-set-icon-with-as-template`\n- `allow-set-show-menu-on-left-click`",
          "type": "string",
          "const": "core:tray:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-get-by-id`\n- `allow-remove-by-id`\n- `allow-set-icon`\n- `allow-set-menu`\n- `allow-set-tooltip`\n- `allow-set-title`\n- `allow-set-visible`\n- `allow-set-temp-dir-path`\n- `allow-set-icon-as-template`\n- `allow-set-icon-with-as-template`\n- `allow-set-show-menu-on-left-click`"
        },
        {
          "description": "Enables the get_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-get-by-id",
          "markdownDescription": "Enables the get_by_id command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-remove-by-id",
          "markdownDescription": "Enables the remove_by_id command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon-as-template",
          "markdownDescription": "Enables the set_icon_as_template command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon_with_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon-with-as-template",
          "markdownDescription": "Enables the set_icon_with_as_template command without any pre-configured scope."
        },
        {
          "description": "Enables the set_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-menu",
          "markdownDescription": "Enables the set_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_show_menu_on_left_click command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-show-menu-on-left-click",
          "markdownDescription": "Enables the set_show_menu_on_left_click command without any pre-configured scope."
        },
        {
          "description": "Enables the set_temp_dir_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-temp-dir-path",
          "markdownDescription": "Enables the set_temp_dir_path command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-title",
          "markdownDescription": "Enables the set_title command without any pre-configured scope."
        },
        {
          "description": "Enables the set_tooltip command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-tooltip",
          "markdownDescription": "Enables the set_tooltip command without any pre-configured scope."
        },
        {
          "description": "Enables the set_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-visible",
          "markdownDescription": "Enables the set_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the get_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-get-by-id",
          "markdownDescription": "Denies the get_by_id command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-remove-by-id",
          "markdownDescription": "Denies the remove_by_id command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon-as-template",
          "markdownDescription": "Denies the set_icon_as_template command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon_with_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon-with-as-template",
          "markdownDescription": "Denies the set_icon_with_as_template command without any pre-configured scope."
        },
        {
          "description": "Denies the set_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-menu",
          "markdownDescription": "Denies the set_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_show_menu_on_left_click command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-show-menu-on-left-click",
          "markdownDescription": "Denies the set_show_menu_on_left_click command without any pre-configured scope."
        },
        {
          "description": "Denies the set_temp_dir_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-temp-dir-path",
          "markdownDescription": "Denies the set_temp_dir_path command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-title",
          "markdownDescription": "Denies the set_title command without any pre-configured scope."
        },
        {
          "description": "Denies the set_tooltip command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-tooltip",
          "markdownDescription": "Denies the set_tooltip command without any pre-configured scope."
        },
        {
          "description": "Denies the set_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-visible",
          "markdownDescription": "Denies the set_visible command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-webviews`\n- `allow-webview-position`\n- `allow-webview-size`\n- `allow-internal-toggle-devtools`",
          "type": "string",
          "const": "core:webview:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-webviews`\n- `allow-webview-position`\n- `allow-webview-size`\n- `allow-internal-toggle-devtools`"
        },
        {
          "description": "Enables the clear_all_browsing_data command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-clear-all-browsing-data",
          "markdownDescription": "Enables the clear_all_browsing_data command without any pre-configured scope."
        },
        {
          "description": "Enables the create_webview command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-create-webview",
          "markdownDescription": "Enables the create_webview command without any pre-configured scope."
        },
        {
          "description": "Enables the create_webview_window command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-create-webview-window",
          "markdownDescription": "Enables the create_webview_window command without any pre-configured scope."
        },
        {
          "description": "Enables the get_all_webviews command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-get-all-webviews",
          "markdownDescription": "Enables the get_all_webviews command without any pre-configured scope."
        },
        {
          "description": "Enables the internal_toggle_devtools command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-internal-toggle-devtools",
          "markdownDescription": "Enables the internal_toggle_devtools command without any pre-configured scope."
        },
        {
          "description": "Enables the print command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-print",
          "markdownDescription": "Enables the print command without any pre-configured scope."
        },
        {
          "description": "Enables the reparent command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-reparent",
          "markdownDescription": "Enables the reparent command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_auto_resize command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-auto-resize",
          "markdownDescription": "Enables the set_webview_auto_resize command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-background-color",
          "markdownDescription": "Enables the set_webview_background_color command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-focus",
          "markdownDescription": "Enables the set_webview_focus command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-position",
          "markdownDescription": "Enables the set_webview_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-size",
          "markdownDescription": "Enables the set_webview_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_zoom command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-zoom",
          "markdownDescription": "Enables the set_webview_zoom command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_close command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-close",
          "markdownDescription": "Enables the webview_close command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-hide",
          "markdownDescription": "Enables the webview_hide command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-position",
          "markdownDescription": "Enables the webview_position command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-show",
          "markdownDescription": "Enables the webview_show command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-size",
          "markdownDescription": "Enables the webview_size command without any pre-configured scope."
        },
        {
          "description": "Denies the clear_all_browsing_data command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-clear-all-browsing-data",
          "markdownDescription": "Denies the clear_all_browsing_data command without any pre-configured scope."
        },
        {
          "description": "Denies the create_webview command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-create-webview",
          "markdownDescription": "Denies the create_webview command without any pre-configured scope."
        },
        {
          "description": "Denies the create_webview_window command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-create-webview-window",
          "markdownDescription": "Denies the create_webview_window command without any pre-configured scope."
        },
        {
          "description": "Denies the get_all_webviews command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-get-all-webviews",
          "markdownDescription": "Denies the get_all_webviews command without any pre-configured scope."
        },
        {
          "description": "Denies the internal_toggle_devtools command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-internal-toggle-devtools",
          "markdownDescription": "Denies the internal_toggle_devtools command without any pre-configured scope."
        },
        {
          "description": "Denies the print command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-print",
          "markdownDescription": "Denies the print command without any pre-configured scope."
        },
        {
          "description": "Denies the reparent command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-reparent",
          "markdownDescription": "Denies the reparent command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_auto_resize command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-auto-resize",
          "markdownDescription": "Denies the set_webview_auto_resize command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-background-color",
          "markdownDescription": "Denies the set_webview_background_color command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-focus",
          "markdownDescription": "Denies the set_webview_focus command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-position",
          "markdownDescription": "Denies the set_webview_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-size",
          "markdownDescription": "Denies the set_webview_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_zoom command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-zoom",
          "markdownDescription": "Denies the set_webview_zoom command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_close command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-close",
          "markdownDescription": "Denies the webview_close command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-hide",
          "markdownDescription": "Denies the webview_hide command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-position",
          "markdownDescription": "Denies the webview_position command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-show",
          "markdownDescription": "Denies the webview_show command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-size",
          "markdownDescription": "Denies the webview_size command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-windows`\n- `allow-scale-factor`\n- `allow-inner-position`\n- `allow-outer-position`\n- `allow-inner-size`\n- `allow-outer-size`\n- `allow-is-fullscreen`\n- `allow-is-minimized`\n- `allow-is-maximized`\n- `allow-is-focused`\n- `allow-is-decorated`\n- `allow-is-resizable`\n- `allow-is-maximizable`\n- `allow-is-minimizable`\n- `allow-is-closable`\n- `allow-is-visible`\n- `allow-is-enabled`\n- `allow-title`\n- `allow-current-monitor`\n- `allow-primary-monitor`\n- `allow-monitor-from-point`\n- `allow-available-monitors`\n- `allow-cursor-position`\n- `allow-theme`\n- `allow-is-always-on-top`\n- `allow-activity-name`\n- `allow-scene-identifier`\n- `allow-internal-toggle-maximize`",
          "type": "string",
          "const": "core:window:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-windows`\n- `allow-scale-factor`\n- `allow-inner-position`\n- `allow-outer-position`\n- `allow-inner-size`\n- `allow-outer-size`\n- `allow-is-fullscreen`\n- `allow-is-minimized`\n- `allow-is-maximized`\n- `allow-is-focused`\n- `allow-is-decorated`\n- `allow-is-resizable`\n- `allow-is-maximizable`\n- `allow-is-minimizable`\n- `allow-is-closable`\n- `allow-is-visible`\n- `allow-is-enabled`\n- `allow-title`\n- `allow-current-monitor`\n- `allow-primary-monitor`\n- `allow-monitor-from-point`\n- `allow-available-monitors`\n- `allow-cursor-position`\n- `allow-theme`\n- `allow-is-always-on-top`\n- `allow-activity-name`\n- `allow-scene-identifier`\n- `allow-internal-toggle-maximize`"
        },
        {
          "description": "Enables the activity_name command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-activity-name",
          "markdownDescription": "Enables the activity_name command without any pre-configured scope."
        },
        {
          "description": "Enables the available_monitors command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-available-monitors",
          "markdownDescription": "Enables the available_monitors command without any pre-configured scope."
        },
        {
          "description": "Enables the center command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-center",
          "markdownDescription": "Enables the center command without any pre-configured scope."
        },
        {
          "description": "Enables the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-close",
          "markdownDescription": "Enables the close command without any pre-configured scope."
        },
        {
          "description": "Enables the create command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-create",
          "markdownDescription": "Enables the create command without any pre-configured scope."
        },
        {
          "description": "Enables the current_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-current-monitor",
          "markdownDescription": "Enables the current_monitor command without any pre-configured scope."
        },
        {
          "description": "Enables the cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-cursor-position",
          "markdownDescription": "Enables the cursor_position command without any pre-configured scope."
        },
        {
          "description": "Enables the destroy command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-destroy",
          "markdownDescription": "Enables the destroy command without any pre-configured scope."
        },
        {
          "description": "Enables the get_all_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-get-all-windows",
          "markdownDescription": "Enables the get_all_windows command without any pre-configured scope."
        },
        {
          "description": "Enables the hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-hide",
          "markdownDescription": "Enables the hide command without any pre-configured scope."
        },
        {
          "description": "Enables the inner_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-inner-position",
          "markdownDescription": "Enables the inner_position command without any pre-configured scope."
        },
        {
          "description": "Enables the inner_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-inner-size",
          "markdownDescription": "Enables the inner_size command without any pre-configured scope."
        },
        {
          "description": "Enables the internal_toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-internal-toggle-maximize",
          "markdownDescription": "Enables the internal_toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the is_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-always-on-top",
          "markdownDescription": "Enables the is_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Enables the is_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-closable",
          "markdownDescription": "Enables the is_closable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_decorated command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-decorated",
          "markdownDescription": "Enables the is_decorated command without any pre-configured scope."
        },
        {
          "description": "Enables the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-enabled",
          "markdownDescription": "Enables the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the is_focused command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-focused",
          "markdownDescription": "Enables the is_focused command without any pre-configured scope."
        },
        {
          "description": "Enables the is_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-fullscreen",
          "markdownDescription": "Enables the is_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the is_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-maximizable",
          "markdownDescription": "Enables the is_maximizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_maximized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-maximized",
          "markdownDescription": "Enables the is_maximized command without any pre-configured scope."
        },
        {
          "description": "Enables the is_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-minimizable",
          "markdownDescription": "Enables the is_minimizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_minimized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-minimized",
          "markdownDescription": "Enables the is_minimized command without any pre-configured scope."
        },
        {
          "description": "Enables the is_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-resizable",
          "markdownDescription": "Enables the is_resizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-visible",
          "markdownDescription": "Enables the is_visible command without any pre-configured scope."
        },
        {
          "description": "Enables the maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-maximize",
          "markdownDescription": "Enables the maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the minimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-minimize",
          "markdownDescription": "Enables the minimize command without any pre-configured scope."
        },
        {
          "description": "Enables the monitor_from_point command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-monitor-from-point",
          "markdownDescription": "Enables the monitor_from_point command without any pre-configured scope."
        },
        {
          "description": "Enables the outer_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-outer-position",
          "markdownDescription": "Enables the outer_position command without any pre-configured scope."
        },
        {
          "description": "Enables the outer_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-outer-size",
          "markdownDescription": "Enables the outer_size command without any pre-configured scope."
        },
        {
          "description": "Enables the primary_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-primary-monitor",
          "markdownDescription": "Enables the primary_monitor command without any pre-configured scope."
        },
        {
          "description": "Enables the request_user_attention command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-request-user-attention",
          "markdownDescription": "Enables the request_user_attention command without any pre-configured scope."
        },
        {
          "description": "Enables the scale_factor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-scale-factor",
          "markdownDescription": "Enables the scale_factor command without any pre-configured scope."
        },
        {
          "description": "Enables the scene_identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-scene-identifier",
          "markdownDescription": "Enables the scene_identifier command without any pre-configured scope."
        },
        {
          "description": "Enables the set_always_on_bottom command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-always-on-bottom",
          "markdownDescription": "Enables the set_always_on_bottom command without any pre-configured scope."
        },
        {
          "description": "Enables the set_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-always-on-top",
          "markdownDescription": "Enables the set_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Enables the set_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-background-color",
          "markdownDescription": "Enables the set_background_color command without any pre-configured scope."
        },
        {
          "description": "Enables the set_badge_count command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-badge-count",
          "markdownDescription": "Enables the set_badge_count command without any pre-configured scope."
        },
        {
          "description": "Enables the set_badge_label command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-badge-label",
          "markdownDescription": "Enables the set_badge_label command without any pre-configured scope."
        },
        {
          "description": "Enables the set_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-closable",
          "markdownDescription": "Enables the set_closable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_content_protected command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-content-protected",
          "markdownDescription": "Enables the set_content_protected command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_grab command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-grab",
          "markdownDescription": "Enables the set_cursor_grab command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-icon",
          "markdownDescription": "Enables the set_cursor_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-position",
          "markdownDescription": "Enables the set_cursor_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-visible",
          "markdownDescription": "Enables the set_cursor_visible command without any pre-configured scope."
        },
        {
          "description": "Enables the set_decorations command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-decorations",
          "markdownDescription": "Enables the set_decorations command without any pre-configured scope."
        },
        {
          "description": "Enables the set_effects command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-effects",
          "markdownDescription": "Enables the set_effects command without any pre-configured scope."
        },
        {
          "description": "Enables the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-enabled",
          "markdownDescription": "Enables the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the set_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-focus",
          "markdownDescription": "Enables the set_focus command without any pre-configured scope."
        },
        {
          "description": "Enables the set_focusable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-focusable",
          "markdownDescription": "Enables the set_focusable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-fullscreen",
          "markdownDescription": "Enables the set_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_ignore_cursor_events command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-ignore-cursor-events",
          "markdownDescription": "Enables the set_ignore_cursor_events command without any pre-configured scope."
        },
        {
          "description": "Enables the set_max_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-max-size",
          "markdownDescription": "Enables the set_max_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-maximizable",
          "markdownDescription": "Enables the set_maximizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_min_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-min-size",
          "markdownDescription": "Enables the set_min_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-minimizable",
          "markdownDescription": "Enables the set_minimizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_overlay_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-overlay-icon",
          "markdownDescription": "Enables the set_overlay_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-position",
          "markdownDescription": "Enables the set_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_progress_bar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-progress-bar",
          "markdownDescription": "Enables the set_progress_bar command without any pre-configured scope."
        },
        {
          "description": "Enables the set_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-resizable",
          "markdownDescription": "Enables the set_resizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_shadow command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-shadow",
          "markdownDescription": "Enables the set_shadow command without any pre-configured scope."
        },
        {
          "description": "Enables the set_simple_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-simple-fullscreen",
          "markdownDescription": "Enables the set_simple_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the set_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-size",
          "markdownDescription": "Enables the set_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_size_constraints command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-size-constraints",
          "markdownDescription": "Enables the set_size_constraints command without any pre-configured scope."
        },
        {
          "description": "Enables the set_skip_taskbar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-skip-taskbar",
          "markdownDescription": "Enables the set_skip_taskbar command without any pre-configured scope."
        },
        {
          "description": "Enables the set_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-theme",
          "markdownDescription": "Enables the set_theme command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-title",
          "markdownDescription": "Enables the set_title command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title_bar_style command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-title-bar-style",
          "markdownDescription": "Enables the set_title_bar_style command without any pre-configured scope."
        },
        {
          "description": "Enables the set_visible_on_all_workspaces command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-visible-on-all-workspaces",
          "markdownDescription": "Enables the set_visible_on_all_workspaces command without any pre-configured scope."
        },
        {
          "description": "Enables the show command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-show",
          "markdownDescription": "Enables the show command without any pre-configured scope."
        },
        {
          "description": "Enables the start_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-start-dragging",
          "markdownDescription": "Enables the start_dragging command without any pre-configured scope."
        },
        {
          "description": "Enables the start_resize_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-start-resize-dragging",
          "markdownDescription": "Enables the start_resize_dragging command without any pre-configured scope."
        },
        {
          "description": "Enables the theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-theme",
          "markdownDescription": "Enables the theme command without any pre-configured scope."
        },
        {
          "description": "Enables the title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-title",
          "markdownDescription": "Enables the title command without any pre-configured scope."
        },
        {
          "description": "Enables the toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-toggle-maximize",
          "markdownDescription": "Enables the toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the unmaximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-unmaximize",
          "markdownDescription": "Enables the unmaximize command without any pre-configured scope."
        },
        {
          "description": "Enables the unminimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-unminimize",
          "markdownDescription": "Enables the unminimize command without any pre-configured scope."
        },
        {
          "description": "Denies the activity_name command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-activity-name",
          "markdownDescription": "Denies the activity_name command without any pre-configured scope."
        },
        {
          "description": "Denies the available_monitors command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-available-monitors",
          "markdownDescription": "Denies the available_monitors command without any pre-configured scope."
        },
        {
          "description": "Denies the center command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-center",
          "markdownDescription": "Denies the center command without any pre-configured scope."
        },
        {
          "description": "Denies the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-close",
          "markdownDescription": "Denies the close command without any pre-configured scope."
        },
        {
          "description": "Denies the create command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-create",
          "markdownDescription": "Denies the create command without any pre-configured scope."
        },
        {
          "description": "Denies the current_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-current-monitor",
          "markdownDescription": "Denies the current_monitor command without any pre-configured scope."
        },
        {
          "description": "Denies the cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-cursor-position",
          "markdownDescription": "Denies the cursor_position command without any pre-configured scope."
        },
        {
          "description": "Denies the destroy command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-destroy",
          "markdownDescription": "Denies the destroy command without any pre-configured scope."
        },
        {
          "description": "Denies the get_all_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-get-all-windows",
          "markdownDescription": "Denies the get_all_windows command without any pre-configured scope."
        },
        {
          "description": "Denies the hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-hide",
          "markdownDescription": "Denies the hide command without any pre-configured scope."
        },
        {
          "description": "Denies the inner_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-inner-position",
          "markdownDescription": "Denies the inner_position command without any pre-configured scope."
        },
        {
          "description": "Denies the inner_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-inner-size",
          "markdownDescription": "Denies the inner_size command without any pre-configured scope."
        },
        {
          "description": "Denies the internal_toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-internal-toggle-maximize",
          "markdownDescription": "Denies the internal_toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the is_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-always-on-top",
          "markdownDescription": "Denies the is_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Denies the is_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-closable",
          "markdownDescription": "Denies the is_closable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_decorated command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-decorated",
          "markdownDescription": "Denies the is_decorated command without any pre-configured scope."
        },
        {
          "description": "Denies the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-enabled",
          "markdownDescription": "Denies the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the is_focused command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-focused",
          "markdownDescription": "Denies the is_focused command without any pre-configured scope."
        },
        {
          "description": "Denies the is_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-fullscreen",
          "markdownDescription": "Denies the is_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the is_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-maximizable",
          "markdownDescription": "Denies the is_maximizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_maximized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-maximized",
          "markdownDescription": "Denies the is_maximized command without any pre-configured scope."
        },
        {
          "description": "Denies the is_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-minimizable",
          "markdownDescription": "Denies the is_minimizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_minimized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-minimized",
          "markdownDescription": "Denies the is_minimized command without any pre-configured scope."
        },
        {
          "description": "Denies the is_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-resizable",
          "markdownDescription": "Denies the is_resizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-visible",
          "markdownDescription": "Denies the is_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-maximize",
          "markdownDescription": "Denies the maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the minimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-minimize",
          "markdownDescription": "Denies the minimize command without any pre-configured scope."
        },
        {
          "description": "Denies the monitor_from_point command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-monitor-from-point",
          "markdownDescription": "Denies the monitor_from_point command without any pre-configured scope."
        },
        {
          "description": "Denies the outer_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-outer-position",
          "markdownDescription": "Denies the outer_position command without any pre-configured scope."
        },
        {
          "description": "Denies the outer_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-outer-size",
          "markdownDescription": "Denies the outer_size command without any pre-configured scope."
        },
        {
          "description": "Denies the primary_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-primary-monitor",
          "markdownDescription": "Denies the primary_monitor command without any pre-configured scope."
        },
        {
          "description": "Denies the request_user_attention command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-request-user-attention",
          "markdownDescription": "Denies the request_user_attention command without any pre-configured scope."
        },
        {
          "description": "Denies the scale_factor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-scale-factor",
          "markdownDescription": "Denies the scale_factor command without any pre-configured scope."
        },
        {
          "description": "Denies the scene_identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-scene-identifier",
          "markdownDescription": "Denies the scene_identifier command without any pre-configured scope."
        },
        {
          "description": "Denies the set_always_on_bottom command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-always-on-bottom",
          "markdownDescription": "Denies the set_always_on_bottom command without any pre-configured scope."
        },
        {
          "description": "Denies the set_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-always-on-top",
          "markdownDescription": "Denies the set_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Denies the set_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-background-color",
          "markdownDescription": "Denies the set_background_color command without any pre-configured scope."
        },
        {
          "description": "Denies the set_badge_count command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-badge-count",
          "markdownDescription": "Denies the set_badge_count command without any pre-configured scope."
        },
        {
          "description": "Denies the set_badge_label command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-badge-label",
          "markdownDescription": "Denies the set_badge_label command without any pre-configured scope."
        },
        {
          "description": "Denies the set_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-closable",
          "markdownDescription": "Denies the set_closable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_content_protected command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-content-protected",
          "markdownDescription": "Denies the set_content_protected command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_grab command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-grab",
          "markdownDescription": "Denies the set_cursor_grab command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-icon",
          "markdownDescription": "Denies the set_cursor_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-position",
          "markdownDescription": "Denies the set_cursor_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-visible",
          "markdownDescription": "Denies the set_cursor_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the set_decorations command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-decorations",
          "markdownDescription": "Denies the set_decorations command without any pre-configured scope."
        },
        {
          "description": "Denies the set_effects command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-effects",
          "markdownDescription": "Denies the set_effects command without any pre-configured scope."
        },
        {
          "description": "Denies the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-enabled",
          "markdownDescription": "Denies the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the set_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-focus",
          "markdownDescription": "Denies the set_focus command without any pre-configured scope."
        },
        {
          "description": "Denies the set_focusable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-focusable",
          "markdownDescription": "Denies the set_focusable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-fullscreen",
          "markdownDescription": "Denies the set_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_ignore_cursor_events command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-ignore-cursor-events",
          "markdownDescription": "Denies the set_ignore_cursor_events command without any pre-configured scope."
        },
        {
          "description": "Denies the set_max_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-max-size",
          "markdownDescription": "Denies the set_max_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-maximizable",
          "markdownDescription": "Denies the set_maximizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_min_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-min-size",
          "markdownDescription": "Denies the set_min_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-minimizable",
          "markdownDescription": "Denies the set_minimizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_overlay_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-overlay-icon",
          "markdownDescription": "Denies the set_overlay_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-position",
          "markdownDescription": "Denies the set_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_progress_bar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-progress-bar",
          "markdownDescription": "Denies the set_progress_bar command without any pre-configured scope."
        },
        {
          "description": "Denies the set_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-resizable",
          "markdownDescription": "Denies the set_resizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_shadow command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-shadow",
          "markdownDescription": "Denies the set_shadow command without any pre-configured scope."
        },
        {
          "description": "Denies the set_simple_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-simple-fullscreen",
          "markdownDescription": "Denies the set_simple_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the set_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-size",
          "markdownDescription": "Denies the set_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_size_constraints command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-size-constraints",
          "markdownDescription": "Denies the set_size_constraints command without any pre-configured scope."
        },
        {
          "description": "Denies the set_skip_taskbar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-skip-taskbar",
          "markdownDescription": "Denies the set_skip_taskbar command without any pre-configured scope."
        },
        {
          "description": "Denies the set_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-theme",
          "markdownDescription": "Denies the set_theme command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-title",
          "markdownDescription": "Denies the set_title command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title_bar_style command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-title-bar-style",
          "markdownDescription": "Denies the set_title_bar_style command without any pre-configured scope."
        },
        {
          "description": "Denies the set_visible_on_all_workspaces command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-visible-on-all-workspaces",
          "markdownDescription": "Denies the set_visible_on_all_workspaces command without any pre-configured scope."
        },
        {
          "description": "Denies the show command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-show",
          "markdownDescription": "Denies the show command without any pre-configured scope."
        },
        {
          "description": "Denies the start_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-start-dragging",
          "markdownDescription": "Denies the start_dragging command without any pre-configured scope."
        },
        {
          "description": "Denies the start_resize_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-start-resize-dragging",
          "markdownDescription": "Denies the start_resize_dragging command without any pre-configured scope."
        },
        {
          "description": "Denies the theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-theme",
          "markdownDescription": "Denies the theme command without any pre-configured scope."
        },
        {
          "description": "Denies the title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-title",
          "markdownDescription": "Denies the title command without any pre-configured scope."
        },
        {
          "description": "Denies the toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-toggle-maximize",
          "markdownDescription": "Denies the toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the unmaximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-unmaximize",
          "markdownDescription": "Denies the unmaximize command without any pre-configured scope."
        },
        {
          "description": "Denies the unminimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-unminimize",
          "markdownDescription": "Denies the unminimize command without any pre-configured scope."
        }
      ]
    },
    "Value": {
      "description": "All supported ACL values.",
      "anyOf": [
        {
          "description": "Represents a null JSON value.",
          "type": "null"
        },
        {
          "description": "Represents a [`bool`].",
          "type": "boolean"
        },
        {
          "description": "Represents a valid ACL [`Number`].",
          "allOf": [
            {
              "$ref": "#/definitions/Number"
            }
          ]
        },
        {
          "description": "Represents a [`String`].",
          "type": "string"
        },
        {
          "description": "Represents a list of other [`Value`]s.",
          "type": "array",
          "items": {
            "$ref": "#/definitions/Value"
          }
        },
        {
          "description": "Represents a map of [`String`] keys to [`Value`]s.",
          "type": "object",
          "additionalProperties": {
            "$ref": "#/definitions/Value"
          }
        }
      ]
    },
    "Number": {
      "description": "A valid ACL number.",
      "anyOf": [
        {
          "description": "Represents an [`i64`].",
          "type": "integer",
          "format": "int64"
        },
        {
          "description": "Represents a [`f64`].",
          "type": "number",
          "format": "double"
        }
      ]
    },
    "Target": {
      "description": "Platform target.",
      "oneOf": [
        {
          "description": "MacOS.",
          "type": "string",
          "enum": [
            "macOS"
          ]
        },
        {
          "description": "Windows.",
          "type": "string",
          "enum": [
            "windows"
          ]
        },
        {
          "description": "Linux.",
          "type": "string",
          "enum": [
            "linux"
          ]
        },
        {
          "description": "Android.",
          "type": "string",
          "enum": [
            "android"
          ]
        },
        {
          "description": "iOS.",
          "type": "string",
          "enum": [
            "iOS"
          ]
        }
      ]
    }
  }
}
````

