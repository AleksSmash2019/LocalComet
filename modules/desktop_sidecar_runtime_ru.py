from __future__ import annotations

import os
from pathlib import Path
import secrets
import time
from collections import deque
from typing import Any, Callable, Iterable, Mapping

from modules.desktop_ipc_contract_ru import (
    ERROR_CODES,
    IPC_PROTOCOL_VERSION,
    IPCProtocolError,
    encode_frame,
    make_error,
    make_event,
    make_goodbye,
    make_hello,
    make_response,
    sanitize_ipc_for_log,
    validate_envelope,
)
from modules.desktop_control_plane_ru import (
    CONTROL_PLANE_METHODS,
    DESKTOP_CONTROL_PLANE_VERSION,
    ControlPlaneError,
    DesktopControlPlane,
)
from modules.knowledge_adapter_ru import KnowledgeAdapter
from modules.knowledge_contract_ru import KnowledgeAdapterError, KnowledgeConfig
from modules.knowledge_change_review_ru import KnowledgeChangeReviewArtifact
from modules.local_model_gateway_ru import (
    LOCAL_MODEL_GATEWAY_VERSION,
    MODEL_GATEWAY_METHODS,
    GatewayError,
    LocalModelGateway,
    validate_gateway_payload,
)


DESKTOP_SIDECAR_RUNTIME_VERSION = "v6.84.3"
PYTHON_CORE_ROLE = "python_core"
LIFECYCLE_CAPABILITIES = ("lifecycle",)
CONTROL_PLANE_CAPABILITIES = tuple(CONTROL_PLANE_METHODS)
MODEL_GATEWAY_CAPABILITIES = tuple(MODEL_GATEWAY_METHODS)
DESKTOP_KNOWLEDGE_CAPABILITIES = ("knowledge.turn.decide", "knowledge.turn.preview")
ALLOWED_REQUEST_METHODS = frozenset(
    (
        "app.health",
        "app.shutdown",
        *CONTROL_PLANE_CAPABILITIES,
        *MODEL_GATEWAY_CAPABILITIES,
        *DESKTOP_KNOWLEDGE_CAPABILITIES,
    )
)
MAX_SEEN_MESSAGE_IDS = 256


class DuplicateMessageIdCache:
    def __init__(self, limit: int = MAX_SEEN_MESSAGE_IDS) -> None:
        if limit < 1:
            raise ValueError("duplicate id cache limit must be positive")
        self._limit = limit
        self._order: deque[str] = deque()
        self._seen: set[str] = set()

    def remember(self, message_id: str) -> bool:
        if message_id in self._seen:
            return False
        self._seen.add(message_id)
        self._order.append(message_id)
        while len(self._order) > self._limit:
            expired = self._order.popleft()
            self._seen.discard(expired)
        return True

    def __len__(self) -> int:
        return len(self._seen)


class DesktopSidecarRuntime:
    def __init__(
        self,
        *,
        session_nonce: str | None = None,
        monotonic: Any = time.monotonic,
        knowledge_adapter: Any | None = None,
        knowledge_reviews: (
            list[KnowledgeChangeReviewArtifact]
            | tuple[KnowledgeChangeReviewArtifact, ...]
            | None
        ) = None,
    ) -> None:
        self.session_nonce = session_nonce or secrets.token_hex(12)
        self.started_at = float(monotonic())
        self._monotonic = monotonic
        self._outgoing_sequence = 0
        self._outgoing_counter = 0
        self._seen_ids = DuplicateMessageIdCache()
        self._shutdown_requested = False
        self._desktop_hello_seen = False
        self._control_plane = DesktopControlPlane(
            knowledge_adapter=knowledge_adapter,
            knowledge_reviews=knowledge_reviews,
        )
        self._model_gateway = LocalModelGateway()
        self._async_message_writer: Callable[[tuple[dict[str, Any], ...]], None] | None = None

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    @property
    def seen_id_count(self) -> int:
        return len(self._seen_ids)

    def startup_messages(self) -> tuple[dict[str, Any], ...]:
        return (self._hello(),)

    def set_async_message_writer(self, writer: Callable[[tuple[dict[str, Any], ...]], None]) -> None:
        self._async_message_writer = writer

    def handle_message(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        findings = validate_envelope(message)
        if findings:
            raise IPCProtocolError("invalid_envelope", findings[0])

        message_id = str(message["id"])
        if not self._seen_ids.remember(message_id):
            return (self._error(message_id, "duplicate_message_id", "duplicate message id"),)

        msg_type = message["type"]
        if msg_type == "hello":
            self._desktop_hello_seen = True
            return (self._hello(),)
        if msg_type == "goodbye":
            self._shutdown_requested = True
            return ()
        if msg_type != "request":
            return (self._error(message_id, "unsupported_type", "unsupported lifecycle message type"),)

        method = message.get("method")
        if not self._desktop_hello_seen:
            return (self._error(message_id, "sidecar_unavailable", "desktop hello required"),)
        if method == "app.health":
            return (self._health_response(message_id),)
        if method == "app.shutdown":
            self._shutdown_requested = True
            self._model_gateway.shutdown()
            return (
                make_response(
                    self._next_message_id("response"),
                    message_id,
                    {"status": "shutting_down", "runtime_version": DESKTOP_SIDECAR_RUNTIME_VERSION},
                    sequence=self._next_sequence(),
                ),
                make_goodbye(self._next_message_id("goodbye"), reason="shutdown", sequence=self._next_sequence()),
            )
        if method in CONTROL_PLANE_CAPABILITIES:
            return self._control_plane_messages(message)
        if method in DESKTOP_KNOWLEDGE_CAPABILITIES:
            return self._desktop_knowledge_messages(message)
        if method in MODEL_GATEWAY_CAPABILITIES:
            return self._model_gateway_messages(message)
        return (self._error(message_id, "unsupported_method", f"unsupported lifecycle method: {method}"),)

    def protocol_error_messages(self, error: IPCProtocolError, *, reply_to: str = "unknown") -> tuple[dict[str, Any], ...]:
        code = error.code if error.code in ERROR_CODES else "invalid_frame"
        return (self._error(reply_to, code, error.message),)

    def encode_messages(self, messages: Iterable[Mapping[str, Any]]) -> bytes:
        return b"".join(encode_frame(message) for message in messages)

    def sanitized_for_log(self, message: Mapping[str, Any]) -> dict[str, Any]:
        return sanitize_ipc_for_log(message)

    def _hello(self) -> dict[str, Any]:
        payload = {
            "role": PYTHON_CORE_ROLE,
            "selected_version": IPC_PROTOCOL_VERSION,
            "supported_versions": [IPC_PROTOCOL_VERSION],
            "session_nonce": self.session_nonce,
            "runtime_version": DESKTOP_SIDECAR_RUNTIME_VERSION,
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "model_gateway_version": LOCAL_MODEL_GATEWAY_VERSION,
            "capabilities": sorted(
                (
                    *LIFECYCLE_CAPABILITIES,
                    *CONTROL_PLANE_CAPABILITIES,
                    *MODEL_GATEWAY_CAPABILITIES,
                    *DESKTOP_KNOWLEDGE_CAPABILITIES,
                )
            ),
        }
        return {
            "protocol": "localcomet.ipc",
            "version": IPC_PROTOCOL_VERSION,
            "type": "hello",
            "id": self._next_message_id("hello"),
            "method": None,
            "run_id": None,
            "sequence": self._next_sequence(),
            "reply_to": None,
            "payload": payload,
        }

    def _health_response(self, reply_to: str) -> dict[str, Any]:
        uptime_ms = max(0, int((float(self._monotonic()) - self.started_at) * 1000))
        payload = {
            "status": "ok",
            "runtime_version": DESKTOP_SIDECAR_RUNTIME_VERSION,
            "control_plane_version": DESKTOP_CONTROL_PLANE_VERSION,
            "model_gateway_version": LOCAL_MODEL_GATEWAY_VERSION,
            "protocol_version": IPC_PROTOCOL_VERSION,
            "uptime_ms": uptime_ms,
            "seen_message_ids": self.seen_id_count,
            "capabilities": sorted(
                (
                    *LIFECYCLE_CAPABILITIES,
                    *CONTROL_PLANE_CAPABILITIES,
                    *MODEL_GATEWAY_CAPABILITIES,
                    *DESKTOP_KNOWLEDGE_CAPABILITIES,
                )
            ),
        }
        return make_response(
            self._next_message_id("response"),
            reply_to,
            payload,
            sequence=self._next_sequence(),
        )

    def _control_plane_messages(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        request_id = str(message["id"])
        method = str(message["method"])
        try:
            result = self._control_plane.dispatch(method, message["payload"], request_id=request_id)
        except ControlPlaneError as exc:
            return (self._error(request_id, exc.code if exc.code in ERROR_CODES else "invalid_payload", exc.message),)
        messages: list[dict[str, Any]] = []
        for event in result.events:
            messages.append(
                make_event(
                    self._next_message_id("event"),
                    event.method,
                    event.payload,
                    reply_to=request_id,
                    sequence=event.sequence,
                )
            )
        messages.append(
            make_response(
                self._next_message_id("response"),
                request_id,
                result.response,
                sequence=len(result.events),
            )
        )
        return tuple(messages)

    def _model_gateway_messages(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        request_id = str(message["id"])
        method = str(message["method"])
        findings = validate_gateway_payload(method, message["payload"])
        if findings:
            return (self._error(request_id, "invalid_payload", findings[0]),)
        try:
            if method == "model.catalog.get":
                response = self._model_gateway.catalog()
            elif method == "model.gateway.probe":
                response = self._model_gateway.probe(message["payload"])
            elif method == "model.models.list":
                response = self._model_gateway.list_models(message["payload"])
            elif method == "model.binding.set":
                response = self._model_gateway.set_binding(message["payload"])
            elif method == "model.turn.start":
                response = self._model_gateway.start_turn(message["payload"], self._emit_model_event)
            elif method == "model.turn.cancel":
                response = self._model_gateway.cancel_turn(message["payload"])
            elif method == "model.managed.attach":
                response = self._model_gateway.managed_attach(message["payload"])
            elif method == "model.managed.detach":
                response = self._model_gateway.managed_detach()
            else:
                return (self._error(request_id, "unsupported_method", "unsupported model gateway method"),)
        except GatewayError as exc:
            code = exc.code if exc.code in ERROR_CODES else "invalid_payload"
            return (self._error(request_id, code, exc.message),)
        return (
            make_response(
                self._next_message_id("response"),
                request_id,
                response,
                sequence=self._next_sequence(),
            ),
        )

    def _desktop_knowledge_messages(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        request_id = str(message["id"])
        method = str(message["method"])
        payload = message["payload"]
        finding = _validate_desktop_knowledge_payload(method, payload)
        if finding is not None:
            return (self._error(request_id, "invalid_payload", finding),)
        try:
            if method == "knowledge.turn.preview":
                response = self._control_plane.desktop_knowledge_preview(
                    turn_id=str(payload["turn_id"]),
                    intent=str(payload["intent"]),
                    max_context_chars=int(payload["max_context_chars"]),
                    max_results=int(payload["max_results"]),
                )
            else:
                response = self._control_plane.desktop_knowledge_decide(
                    turn_id=str(payload["turn_id"]),
                    injection_id=str(payload["injection_id"]),
                    expected_preview_hash=str(payload["expected_preview_hash"]),
                    action=str(payload["action"]),
                    model_gateway=self._model_gateway,
                    emit_model_event=self._emit_model_event,
                )
        except ControlPlaneError as exc:
            return (self._error(request_id, "invalid_payload", exc.message),)
        except GatewayError as exc:
            return (self._error(request_id, exc.code if exc.code in ERROR_CODES else "invalid_payload", exc.message),)
        return (
            make_response(
                self._next_message_id("response"),
                request_id,
                response,
                sequence=self._next_sequence(),
            ),
        )

    def _emit_model_event(self, method: str, turn_id: str, sequence: int, payload: Mapping[str, Any]) -> None:
        writer = self._async_message_writer
        if writer is None:
            return
        event = make_event(
            self._next_message_id("event"),
            method,
            payload,
            reply_to=None,
            run_id=turn_id,
            sequence=sequence,
        )
        writer((event,))

    def _error(self, reply_to: str, code: str, message: str) -> dict[str, Any]:
        return make_error(
            self._next_message_id("error"),
            reply_to,
            code,
            message,
            retryable=False,
            details={"runtime_version": DESKTOP_SIDECAR_RUNTIME_VERSION},
            sequence=self._next_sequence(),
        )

    def _next_message_id(self, prefix: str) -> str:
        self._outgoing_counter += 1
        return f"py-{prefix}-{self._outgoing_counter:06d}"

    def _next_sequence(self) -> int:
        value = self._outgoing_sequence
        self._outgoing_sequence += 1
        return value


def _validate_desktop_knowledge_payload(method: str, payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return "knowledge payload must be an object"
    expected = (
        {"turn_id", "intent", "max_context_chars", "max_results"}
        if method == "knowledge.turn.preview"
        else {"turn_id", "injection_id", "expected_preview_hash", "action"}
    )
    if set(payload) != expected:
        return "unexpected knowledge payload shape"
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or len(turn_id) != 24 or any(ch not in "0123456789abcdef" for ch in turn_id):
        return "turn_id is invalid"
    if method == "knowledge.turn.preview":
        if payload.get("intent") not in {
            "AUTO", "CURRENT_STATE", "ARCHITECTURE", "SECURITY", "HISTORY",
            "FOUNDER_INTENT", "ROADMAP", "RESEARCH", "OPERATIONAL", "INCIDENT",
        }:
            return "knowledge intent is invalid"
        context_chars = payload.get("max_context_chars")
        max_results = payload.get("max_results")
        if isinstance(context_chars, bool) or not isinstance(context_chars, int) or not 1 <= context_chars <= 12_000:
            return "knowledge context limit is invalid"
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 8:
            return "knowledge result limit is invalid"
        return None
    injection_id = payload.get("injection_id")
    if not isinstance(injection_id, str) or not injection_id.startswith("kinj:") or not 6 <= len(injection_id) <= 128:
        return "injection_id is invalid"
    preview_hash = payload.get("expected_preview_hash")
    if (
        not isinstance(preview_hash, str)
        or len(preview_hash) != 71
        or not preview_hash.startswith("sha256:")
        or any(ch not in "0123456789abcdef" for ch in preview_hash[7:])
    ):
        return "preview hash is invalid"
    if payload.get("action") not in {
        "INCLUDE_AND_SEND",
        "REJECT_AND_SEND_WITHOUT_KNOWLEDGE",
        "CANCEL",
    }:
        return "knowledge action is invalid"
    return None


def _production_knowledge_adapter() -> KnowledgeAdapter | None:
    vault_text = os.environ.get("LOCALCOMET_KNOWLEDGE_VAULT", "")
    if not vault_text:
        return None
    project_text = os.environ.get("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT", "")
    project_root = Path(project_text) if project_text else Path(__file__).resolve().parents[1]
    adapter = KnowledgeAdapter(
        KnowledgeConfig(
            vault_root=Path(vault_text),
            project_root=project_root,
        )
    )
    try:
        adapter.initialize()
    except KnowledgeAdapterError:
        pass
    return adapter


def make_runtime() -> DesktopSidecarRuntime:
    return DesktopSidecarRuntime(knowledge_adapter=_production_knowledge_adapter())
