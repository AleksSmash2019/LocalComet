from __future__ import annotations

import codecs
import hashlib
import http.client
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass
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
    idle_timeout_seconds: float = 10.0
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
    turn_id: str
    cancel: threading.Event
    thread: threading.Thread
    closer: Callable[[], None] | None = None
    terminal: bool = False


class LocalModelGateway:
    def __init__(self, *, limits: GatewayLimits | None = None) -> None:
        self.limits = limits or GatewayLimits()
        self._lock = threading.RLock()
        self._binding: ModelBinding | None = None
        self._discovered_port: int | None = None
        self._discovered_models: tuple[str, ...] = ()
        self._managed: ModelBinding | None = None
        self._active: _ActiveTurn | None = None

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

    def bound_turn_payload(self, prompt: str) -> dict[str, str]:
        """Build an internal turn payload from the active in-memory binding."""
        normalized_prompt = _validate_prompt(prompt, self.limits)
        with self._lock:
            if self._binding is None:
                raise GatewayError("invalid_payload", "model binding is required")
            fingerprint = self._binding.fingerprint
        return {
            "prompt": normalized_prompt,
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
        return self._start_turn(
            payload,
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
        prompt = _validate_prompt(payload.get("prompt"), self.limits)
        binding_fingerprint = _bounded_text(str(payload.get("binding_fingerprint", "")), 64)
        with self._lock:
            if self._active is not None and self._active.thread.is_alive() and not self._active.terminal:
                raise GatewayError("busy", "one model inference is already active", retryable=True)
            binding = self._binding
            if binding is None:
                raise GatewayError("invalid_payload", "model binding is required")
            if binding.fingerprint != binding_fingerprint:
                raise GatewayError("invalid_payload", "binding fingerprint mismatch")
            messages = HarnessAdapter(binding.harness_id, self.limits).messages_for(prompt)
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
            turn_id = secrets.token_hex(12)
            cancel = threading.Event()
            thread = threading.Thread(
                target=self._run_turn,
                name="localcomet-model-turn",
                args=(
                    turn_id,
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
            active = _ActiveTurn(turn_id=turn_id, cancel=cancel, thread=thread)
            self._active = active
            thread.start()
            response = {
                "turn_id": turn_id,
                "state": "GENERATING",
                "provider_id": binding.provider_id,
                "harness_id": binding.harness_id,
                "model_id": binding.model_id,
                "binding_fingerprint": binding.fingerprint,
                "model_called": False,
                "tools_executed": 0,
                "persistence": False,
            }
            if knowledge_envelope is not None:
                response["knowledge_injection_id"] = knowledge_envelope.injection_id
                response["knowledge_injection_state"] = knowledge_envelope.state.value
            return response

    def cancel_turn(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        turn_id = _validate_turn_id(payload.get("turn_id"))
        with self._lock:
            active = self._active
            if active is None or active.turn_id != turn_id:
                return {"turn_id": turn_id, "state": "Cancelled", "already_terminal": True}
            active.cancel.set()
            if active.closer is not None:
                active.closer()
            thread = active.thread
        thread.join(self.limits.worker_join_timeout_seconds)
        with self._lock:
            alive = thread.is_alive()
            if not alive:
                active.terminal = True
                if self._active is active:
                    self._active = None
        return {"turn_id": turn_id, "state": "Cancelling" if alive else "Cancelled", "worker_alive": alive}

    def managed_attach(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        runtime_instance_id = _validate_runtime_instance_id(payload.get("runtime_instance_id"))
        port = _validate_port(payload.get("port"))
        credential = _validate_credential(payload.get("credential"))
        expected_model_alias = _validate_model_id(payload.get("expected_model_alias"))
        model_id = _validate_model_id(payload.get("model_id"))
        binding_fingerprint = _validate_fingerprint(payload.get("binding_fingerprint"))
        with self._lock:
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
            active.cancel.set()
            if active.closer is not None:
                active.closer()
            thread = active.thread
        thread.join(self.limits.worker_join_timeout_seconds)
        with self._lock:
            self._active = None

    def _remember_discovery(self, port: int, models: tuple[str, ...]) -> None:
        if self._binding and (self._binding.port != port or self._binding.model_id not in models):
            self._binding = None
        self._discovered_port = port
        self._discovered_models = models

    def _run_turn(
        self,
        turn_id: str,
        binding: ModelBinding,
        messages: tuple[dict[str, str], ...],
        cancel: threading.Event,
        emit_event: Callable[[str, str, int, Mapping[str, Any]], None],
        knowledge_audit: Mapping[str, Any] | None = None,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
    ) -> None:
        sequence = 0

        def emit(method: str, payload: Mapping[str, Any]) -> None:
            nonlocal sequence
            emit_event(method, turn_id, sequence, payload)
            sequence += 1

        adapter = ProviderAdapter(binding.port, self.limits, api_key=binding.credential)
        with self._lock:
            if self._active is not None and self._active.turn_id == turn_id:
                self._active.closer = adapter.close
        generated = 0
        terminal_sent = False
        try:
            def mark_started() -> None:
                emit(
                    "model.turn.started",
                    _turn_payload(
                        turn_id,
                        "Generating",
                        binding,
                        model_called=True,
                        text=None,
                        audit_metadata=knowledge_audit,
                    ),
                )

            for delta in adapter.stream_chat(
                binding.model_id,
                messages,
                cancel,
                mark_started,
                before_outbound_request=before_outbound_request,
                after_outbound_request=after_outbound_request,
            ):
                if cancel.is_set():
                    break
                generated += len(delta.encode("utf-8"))
                emit(
                    "model.output.delta",
                    _turn_payload(
                        turn_id,
                        "Generating",
                        binding,
                        model_called=True,
                        text=delta,
                        generated_bytes=generated,
                    ),
                )
            if cancel.is_set():
                emit("model.turn.cancelled", _turn_payload(turn_id, "Cancelled", binding, model_called=True))
            else:
                emit(
                    "model.turn.completed",
                    _turn_payload(turn_id, "Completed", binding, model_called=True, generated_bytes=generated),
                )
            terminal_sent = True
        except KnowledgeInjectionContractError as exc:
            failed_payload = _turn_payload(turn_id, "Failed", binding, model_called=False)
            failed_payload["metadata"] = {
                **failed_payload["metadata"],
                "error": {"code": exc.code, "message": exc.safe_message, "retryable": False},
            }
            emit("model.turn.failed", failed_payload)
            terminal_sent = True
        except GatewayError as exc:
            failed_payload = _turn_payload(turn_id, "Failed", binding, model_called=False)
            failed_payload["metadata"] = {**failed_payload["metadata"], "error": exc.as_payload()}
            emit("model.turn.failed", failed_payload)
            terminal_sent = True
        except Exception:
            if cancel.is_set():
                emit("model.turn.cancelled", _turn_payload(turn_id, "Cancelled", binding, model_called=True))
            else:
                failed_payload = _turn_payload(turn_id, "Failed", binding, model_called=False)
                failed_payload["metadata"] = {
                    **failed_payload["metadata"],
                    "error": {"code": "internal_error", "message": "local model gateway failed", "retryable": False},
                }
                emit("model.turn.failed", failed_payload)
            terminal_sent = True
        finally:
            adapter.close()
            with self._lock:
                active = self._active
                if active is not None and active.turn_id == turn_id:
                    active.terminal = terminal_sent
                    self._active = None


class HarnessAdapter:
    def __init__(self, harness_id: str, limits: GatewayLimits) -> None:
        self.harness_id = _expect_one_of(harness_id, HARNESS_REGISTRY, "harness_id")
        self.limits = limits

    def messages_for(self, prompt: str) -> tuple[dict[str, str], ...]:
        prompt = _validate_prompt(prompt, self.limits)
        if self.harness_id == HARNESS_MINIMAL:
            messages = ({"role": "user", "content": prompt},)
        else:
            messages = (
                {
                    "role": "system",
                    "content": (
                        "You are LocalComet running through a local text-only model gateway. "
                        "Return plain text only. No tools, files, shell commands, browser actions, "
                        "or project context are available. Do not claim that any tool or file operation was executed."
                    ),
                },
                {"role": "user", "content": prompt},
            )
        _validate_messages(messages, self.limits)
        return messages


class ProviderAdapter:
    def __init__(self, port: int | None, limits: GatewayLimits, *, api_key: str | None = None) -> None:
        if port is None:
            raise GatewayError("invalid_payload", "port is required")
        self.port = _validate_port(port)
        self.limits = limits
        self.api_key = api_key
        self._connection: http.client.HTTPConnection | None = None

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def list_models(self) -> tuple[str, ...]:
        connection = self._connect()
        try:
            connection.request("GET", "/v1/models", headers=self._headers("application/json"))
            response = connection.getresponse()
            _reject_redirect(response.status)
            if response.status != 200:
                raise GatewayError("sidecar_unavailable", "model provider returned non-200 status", retryable=True)
            body = _read_bounded(response, self.limits.maximum_models_body_bytes)
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
        finally:
            self.close()

    def stream_chat(
        self,
        model_id: str,
        messages: tuple[dict[str, str], ...],
        cancel: threading.Event,
        on_request_started: Callable[[], None],
        *,
        before_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
        after_outbound_request: Callable[[tuple[dict[str, str], ...]], None] | None = None,
    ) -> Iterable[str]:
        model_id = _validate_model_id(model_id, self.limits)
        _validate_messages(messages, self.limits)
        body = _json_bytes(
            {
                "model": model_id,
                "messages": list(messages),
                "stream": True,
            }
        )
        connection = self._connect()
        started = time.monotonic()
        last_read = started
        event_count = 0
        output_bytes = 0
        event_lines: list[str] = []
        event_bytes = 0
        decoder = codecs.getincrementaldecoder("utf-8")()
        text_buffer = ""
        try:
            if before_outbound_request is not None:
                before_outbound_request(messages)
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={**self._headers("text/event-stream"), "Content-Type": "application/json"},
            )
            if after_outbound_request is not None:
                after_outbound_request(messages)
            response = connection.getresponse()
            _reject_redirect(response.status)
            if response.status != 200:
                raise GatewayError("sidecar_unavailable", "model completion returned non-200 status", retryable=True)
            content_type = response.getheader("Content-Type", "")
            if "text/event-stream" not in content_type.lower().split(";")[0]:
                raise GatewayError("invalid_payload", "model completion did not return event-stream")
            on_request_started()
            while not cancel.is_set():
                now = time.monotonic()
                if now - started > self.limits.overall_timeout_seconds:
                    raise GatewayError("timeout", "model completion overall timeout", retryable=True)
                if now - last_read > self.limits.idle_timeout_seconds:
                    raise GatewayError("timeout", "model completion idle timeout", retryable=True)
                try:
                    chunk = response.read(self.limits.read_chunk_bytes)
                except socket.timeout as exc:
                    raise GatewayError("timeout", "model completion read timeout", retryable=True) from exc
                if not chunk:
                    try:
                        decoder.decode(b"", final=True)
                    except UnicodeDecodeError as exc:
                        raise GatewayError("invalid_payload", "invalid UTF-8 from provider") from exc
                    raise GatewayError("invalid_payload", "event stream ended without DONE")
                last_read = time.monotonic()
                text_buffer += decoder.decode(chunk, final=False)
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
                            delta, done = _parse_sse_event(event_lines)
                            event_lines = []
                            event_bytes = 0
                            if delta:
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
                        raise GatewayError("invalid_payload", "unsupported SSE line")
        finally:
            self.close()

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    def _connect(self) -> http.client.HTTPConnection:
        self.close()
        self._connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.port,
            timeout=self.limits.read_timeout_seconds,
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
        "model.turn.start": {"prompt", "binding_fingerprint"},
        "model.turn.cancel": {"turn_id"},
        "model.managed.attach": {"runtime_instance_id", "port", "credential", "expected_model_alias", "model_id", "binding_fingerprint"},
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
    "model.turn.failed",
)


def provider_registry() -> tuple[str, ...]:
    return PROVIDER_REGISTRY


def harness_registry() -> tuple[str, ...]:
    return HARNESS_REGISTRY


def _turn_payload(
    turn_id: str,
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
        "turn_id": turn_id,
        "session_id": None,
        "thread_id": None,
        "item_id": None,
        "kind": None,
        "state": state,
        "provider_id": binding.provider_id,
        "harness_id": binding.harness_id,
        "model_id": binding.model_id,
        "binding_fingerprint": binding.fingerprint,
        "text": _bounded_text(text or "", 65_536) if text is not None else None,
        "model_called": bool(model_called),
        "tools_executed": 0,
        "persistence": False,
        "generated_bytes": int(generated_bytes),
        "metadata": {
            "provider_id": binding.provider_id,
            "harness_id": binding.harness_id,
            "model_id": binding.model_id,
            "binding_fingerprint": binding.fingerprint,
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


def _validate_turn_id(value: object) -> str:
    if isinstance(value, str) and len(value) == 24 and all(ch in "0123456789abcdef" for ch in value):
        return value
    raise GatewayError("invalid_payload", "turn_id is invalid")


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
    return content, finish_reason is not None


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


def _read_bounded(response: http.client.HTTPResponse, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(8192)
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
