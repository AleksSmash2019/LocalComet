from __future__ import annotations

import copy
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Mapping

DESKTOP_IPC_CONTRACT_VERSION = "v6.84.1"
IPC_PROTOCOL = "localcomet.ipc"
IPC_PROTOCOL_VERSION = "1.0"
MAX_FRAME_BYTES = 4_194_304
MAX_NESTING_DEPTH = 16
MAX_OBJECT_KEYS = 256
MAX_ARRAY_LENGTH = 10_000
MAX_STRING_CHARS = 1_048_576
MAX_LOG_STRING_CHARS = 4_096
MAX_DELTA_TEXT_CHARS = 65_536
FRAME_PREFIX_BYTES = 4
ENVELOPE_TYPES = ("cancel", "error", "event", "goodbye", "hello", "request", "response")
ERROR_CODES = (
    "approval_required", "budget_exceeded", "busy", "duplicate_message_id",
    "frame_too_large", "internal_error", "invalid_envelope", "invalid_frame",
    "invalid_json", "invalid_payload", "invalid_sequence", "kill_switch_active",
    "payload_too_large", "policy_blocked", "request_cancelled",
    "request_not_found", "sidecar_shutdown", "sidecar_unavailable", "timeout",
    "unsupported_method", "unsupported_type", "unsupported_version",
)
CANCEL_REASONS = ("shutdown", "timeout", "user_requested", "window_closing")
APPROVAL_SCOPES = ("SINGLE_ACTION",)
APPROVAL_DECISIONS = ("approve", "deny")
STREAM_CHANNELS = ("content", "reasoning")
DOCUMENT_EVENTS = (
    "document.artifact.created", "document.confirmation.required",
    "document.failed", "document.fields.extracted", "document.fields.required",
    "document.ingestion.completed", "document.ingestion.started",
    "document.rendering.started", "document.verification.completed",
)
METHOD_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){0,7}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RUN_ID_RE = re.compile(r"^[0-9a-f]{24}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(
    "|".join((
        r"sk" + r"-[A-Za-z0-9_\-]{8,}",
        r"ghp" + r"_[A-Za-z0-9_]{8,}",
        r"(?i:bearer\s+[A-Za-z0-9._\-]{8,})",
        r"(?i:(authorization\s*:\s*)[^\r\n]+)",
        r"(?i:((?:api[_-]?key|token|sec" + r"ret)\s*[:=]\s*)[^\s'\";]{8,})",
        r"(?i:((?:pass" + r"word|passwd)\s*[:=]\s*)[^\s'\";]{6,})",
        r"-----BEGIN [A-Z ]*PRIVATE " + r"KEY-----.*?-----END [A-Z ]*PRIVATE " + r"KEY-----",
        r"Traceback \(most recent call last\):.*",
    )),
    re.DOTALL,
)
USER_PATH_RE = re.compile(
    r"(?i)([A-Z]:\\Us" + r"ers\\[^\\\s]+|/ho" + r"me/[^/\s]+|/Us" + r"ers/[^/\s]+|\\\\[^\\\s]+\\[^\\\s]+)"
)
TEXT_KEYS = {"content", "text", "message", "summary", "source", "stdout", "stderr"}
SECRET_KEYS = {"password", "token", "api_key", "authorization", "secret"}
PATH_KEYS = {"absolute_path", "attachment_path", "path"}
WRITE_KEYS = {"content", "new_text", "old_text", "raw_content", "write_content"}
ENVELOPE_KEYS = ("protocol", "version", "type", "id", "method", "run_id", "sequence", "reply_to", "payload")


class IPCProtocolError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(code)
        self.code = code
        self.message = message or code


def canonical_json_bytes(message: Mapping[str, Any]) -> bytes:
    _ensure_supported_json(message)
    findings = validate_payload(dict(message))
    if findings:
        raise IPCProtocolError("invalid_payload", findings[0])
    try:
        return json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IPCProtocolError("invalid_json", "serialization_failed") from exc


def encode_frame(message: Mapping[str, Any]) -> bytes:
    body = canonical_json_bytes(message)
    if len(body) == 0:
        raise IPCProtocolError("invalid_frame", "zero_length_frame")
    if len(body) > MAX_FRAME_BYTES:
        raise IPCProtocolError("frame_too_large", "frame_too_large")
    return struct.pack(">I", len(body)) + body


def decode_frame(frame: bytes) -> dict[str, Any]:
    if not isinstance(frame, (bytes, bytearray)):
        raise IPCProtocolError("invalid_frame", "frame_must_be_bytes")
    data = bytes(frame)
    if len(data) < FRAME_PREFIX_BYTES:
        raise IPCProtocolError("invalid_frame", "missing_length_prefix")
    length = struct.unpack(">I", data[:FRAME_PREFIX_BYTES])[0]
    if length == 0:
        raise IPCProtocolError("invalid_frame", "zero_length_frame")
    if length > MAX_FRAME_BYTES:
        raise IPCProtocolError("frame_too_large", "frame_too_large")
    body = data[FRAME_PREFIX_BYTES:]
    if len(body) != length:
        raise IPCProtocolError("invalid_frame", "frame_length_mismatch")
    return _loads_json(body)


class FrameDecoder:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> tuple[dict[str, Any], ...]:
        if not isinstance(data, (bytes, bytearray)):
            raise IPCProtocolError("invalid_frame", "feed_requires_bytes")
        if not data:
            return ()
        self._buffer.extend(data)
        if len(self._buffer) > MAX_FRAME_BYTES + FRAME_PREFIX_BYTES:
            self.reset()
            raise IPCProtocolError("frame_too_large", "buffer_too_large")
        messages: list[dict[str, Any]] = []
        try:
            while True:
                if len(self._buffer) < FRAME_PREFIX_BYTES:
                    break
                length = struct.unpack(">I", self._buffer[:FRAME_PREFIX_BYTES])[0]
                if length == 0:
                    raise IPCProtocolError("invalid_frame", "zero_length_frame")
                if length > MAX_FRAME_BYTES:
                    raise IPCProtocolError("frame_too_large", "frame_too_large")
                total = FRAME_PREFIX_BYTES + length
                if len(self._buffer) < total:
                    break
                body = bytes(self._buffer[FRAME_PREFIX_BYTES:total])
                del self._buffer[:total]
                messages.append(_loads_json(body))
            return tuple(messages)
        except IPCProtocolError:
            self.reset()
            raise

    def reset(self) -> None:
        self._buffer.clear()


def validate_envelope(message: Mapping[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    if not isinstance(message, Mapping):
        return ("envelope_not_object",)
    keys = set(message)
    missing = [key for key in ENVELOPE_KEYS if key not in message]
    findings.extend(f"missing_{key}" for key in missing)
    extra = sorted(keys - set(ENVELOPE_KEYS))
    findings.extend(f"unknown_{key}" for key in extra)
    if missing:
        return tuple(sorted(set(findings)))
    if message.get("protocol") != IPC_PROTOCOL:
        findings.append("invalid_protocol")
    if message.get("version") != IPC_PROTOCOL_VERSION:
        findings.append("unsupported_version")
    msg_type = message.get("type")
    if msg_type not in ENVELOPE_TYPES:
        findings.append("unsupported_type")
    if not _valid_id(message.get("id")):
        findings.append("invalid_id")
    method = message.get("method")
    if method is not None and not _valid_method(method):
        findings.append("invalid_method")
    run_id = message.get("run_id")
    if run_id is not None and not (isinstance(run_id, str) and RUN_ID_RE.match(run_id)):
        findings.append("invalid_run_id")
    sequence = message.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        findings.append("invalid_sequence")
    reply_to = message.get("reply_to")
    if msg_type in {"response", "error"} and not _valid_id(reply_to):
        findings.append("missing_reply_to")
    if reply_to is not None and not _valid_id(reply_to):
        findings.append("invalid_reply_to")
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        findings.append("payload_not_object")
    else:
        findings.extend(validate_payload(payload))
        findings.extend(_validate_typed_payload(msg_type, method, payload))
    return tuple(sorted(set(findings)))


def validate_payload(value: Any) -> tuple[str, ...]:
    findings: list[str] = []
    seen: set[int] = set()

    def walk(item: Any, depth: int) -> None:
        if depth > MAX_NESTING_DEPTH:
            findings.append("max_depth_exceeded")
            return
        if isinstance(item, (Mapping, list, tuple)):
            marker = id(item)
            if marker in seen:
                findings.append("cyclic_payload")
                return
            seen.add(marker)
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                findings.append("non_finite_number")
            return
        if isinstance(item, str):
            if len(item) > MAX_STRING_CHARS:
                findings.append("string_too_large")
            return
        if isinstance(item, (bytes, bytearray, Path)) or callable(item):
            findings.append("unsupported_payload_type")
            return
        if isinstance(item, Mapping):
            if len(item) > MAX_OBJECT_KEYS:
                findings.append("object_too_large")
            for key, child in item.items():
                if not isinstance(key, str):
                    findings.append("non_string_key")
                elif len(key) > 128:
                    findings.append("key_too_large")
                walk(child, depth + 1)
            return
        if isinstance(item, (list, tuple)):
            if len(item) > MAX_ARRAY_LENGTH:
                findings.append("array_too_large")
            for child in item:
                walk(child, depth + 1)
            return
        findings.append("unsupported_payload_type")

    walk(value, 0)
    return tuple(sorted(set(findings)))


def make_hello(message_id: str, *, session_nonce: str, capabilities: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    return _make("hello", message_id, None, {"role": "desktop_bridge", "supported_versions": [IPC_PROTOCOL_VERSION], "session_nonce": session_nonce, "capabilities": sorted(capabilities)})


def make_request(message_id: str, method: str, payload: Mapping[str, Any], *, run_id: str | None = None, sequence: int = 0) -> dict[str, Any]:
    return _make("request", message_id, method, payload, run_id=run_id, sequence=sequence)


def make_response(message_id: str, reply_to: str, payload: Mapping[str, Any], *, run_id: str | None = None, sequence: int = 0) -> dict[str, Any]:
    return _make("response", message_id, None, payload, run_id=run_id, sequence=sequence, reply_to=reply_to)


def make_event(message_id: str, method: str, payload: Mapping[str, Any], *, reply_to: str | None = None, run_id: str | None = None, sequence: int = 0) -> dict[str, Any]:
    return _make("event", message_id, method, payload, run_id=run_id, sequence=sequence, reply_to=reply_to)


def make_error(message_id: str, reply_to: str, code: str, message: str, *, retryable: bool = False, details: Mapping[str, Any] | None = None, sequence: int = 0) -> dict[str, Any]:
    payload = {"code": code, "message": _bounded_text(message, 512), "retryable": bool(retryable), "details": dict(details or {})}
    return _make("error", message_id, None, payload, sequence=sequence, reply_to=reply_to)


def make_cancel(message_id: str, target_request_id: str, reason: str, *, sequence: int = 0) -> dict[str, Any]:
    return _make("cancel", message_id, None, {"target_request_id": target_request_id, "reason": reason}, sequence=sequence)


def make_goodbye(message_id: str, *, reason: str = "shutdown", sequence: int = 0) -> dict[str, Any]:
    return _make("goodbye", message_id, None, {"reason": _bounded_text(reason, 128)}, sequence=sequence)


def sanitize_ipc_for_log(message: Mapping[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(dict(message))
    return _sanitize_value(cloned, "")


def serialize_protocol_metadata() -> dict[str, Any]:
    return {
        "mode": "desktop_ipc_contract",
        "version": DESKTOP_IPC_CONTRACT_VERSION,
        "protocol": IPC_PROTOCOL,
        "protocol_version": IPC_PROTOCOL_VERSION,
        "max_frame_bytes": MAX_FRAME_BYTES,
        "max_nesting_depth": MAX_NESTING_DEPTH,
        "max_object_keys": MAX_OBJECT_KEYS,
        "max_array_length": MAX_ARRAY_LENGTH,
        "max_string_chars": MAX_STRING_CHARS,
        "envelope_types": list(ENVELOPE_TYPES),
        "error_codes": list(ERROR_CODES),
        "cancel_reasons": list(CANCEL_REASONS),
        "approval_scopes": list(APPROVAL_SCOPES),
        "stream_channels": list(STREAM_CHANNELS),
        "reserved_document_events": list(DOCUMENT_EVENTS),
    }


def _make(msg_type: str, message_id: str, method: str | None, payload: Mapping[str, Any], *, run_id: str | None = None, sequence: int = 0, reply_to: str | None = None) -> dict[str, Any]:
    message = {"protocol": IPC_PROTOCOL, "version": IPC_PROTOCOL_VERSION, "type": msg_type, "id": message_id, "method": method, "run_id": run_id, "sequence": sequence, "reply_to": reply_to, "payload": dict(payload)}
    findings = validate_envelope(message)
    if findings:
        raise IPCProtocolError("invalid_envelope", findings[0])
    return message


def _loads_json(body: bytes) -> dict[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IPCProtocolError("invalid_json", "malformed_utf8") from exc
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_json_constant)
    except IPCProtocolError:
        raise
    except json.JSONDecodeError as exc:
        raise IPCProtocolError("invalid_json", "malformed_json") from exc
    if not isinstance(value, dict):
        raise IPCProtocolError("invalid_envelope", "frame_json_not_object")
    findings = validate_envelope(value)
    if findings:
        raise IPCProtocolError("invalid_envelope", findings[0])
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IPCProtocolError("invalid_json", "duplicate_key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise IPCProtocolError("invalid_json", "non_finite_number")


def _ensure_supported_json(value: Any) -> None:
    if isinstance(value, Mapping):
        for child in value.values():
            _ensure_supported_json(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _ensure_supported_json(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise IPCProtocolError("invalid_json", "non_finite_number")
    elif isinstance(value, (bytes, bytearray, Path)) or callable(value):
        raise IPCProtocolError("invalid_payload", "unsupported_payload_type")


def _validate_typed_payload(msg_type: Any, method: Any, payload: Mapping[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    if msg_type == "hello":
        if payload.get("role") not in {"desktop_bridge", "python_core"}:
            findings.append("invalid_hello_role")
        versions = payload.get("supported_versions", payload.get("selected_version"))
        if not versions:
            findings.append("missing_version_selection")
    if msg_type == "error":
        if payload.get("code") not in ERROR_CODES:
            findings.append("invalid_error_code")
        if not isinstance(payload.get("message"), str) or len(payload.get("message", "")) > 512:
            findings.append("invalid_error_message")
        if not isinstance(payload.get("retryable"), bool):
            findings.append("invalid_retryable")
        if not isinstance(payload.get("details"), Mapping):
            findings.append("invalid_error_details")
    if msg_type == "cancel":
        if not _valid_id(payload.get("target_request_id")):
            findings.append("invalid_cancel_target")
        if payload.get("reason") not in CANCEL_REASONS:
            findings.append("invalid_cancel_reason")
        if "approval" in payload or "decision" in payload:
            findings.append("cancel_contains_approval")
    if method == "chat.delta":
        if payload.get("channel") not in STREAM_CHANNELS:
            findings.append("invalid_delta_channel")
        if not isinstance(payload.get("text"), str) or len(payload.get("text", "")) > MAX_DELTA_TEXT_CHARS:
            findings.append("invalid_delta_text")
    if method == "approval.submit":
        if payload.get("decision") not in APPROVAL_DECISIONS:
            findings.append("invalid_approval_decision")
        if payload.get("scope") not in APPROVAL_SCOPES:
            findings.append("invalid_approval_scope")
        if not isinstance(payload.get("action_fingerprint"), str) or not FINGERPRINT_RE.match(payload["action_fingerprint"]):
            findings.append("invalid_action_fingerprint")
        if "level" in payload or "autonomy_level" in payload:
            findings.append("approval_changes_policy")
        if any(key in payload for key in ("content", "old_text", "new_text", "write_content")):
            findings.append("approval_contains_write_content")
    if method == "approval.required":
        if not isinstance(payload.get("action_fingerprint"), str) or not FINGERPRINT_RE.match(payload["action_fingerprint"]):
            findings.append("invalid_action_fingerprint")
    return tuple(findings)


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value)) and "/" not in value and "\\" not in value


def _valid_method(value: Any) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 96 and bool(METHOD_RE.match(value))


def _sanitize_value(value: Any, key: str) -> Any:
    lowered = key.lower()
    if isinstance(value, str):
        if lowered in WRITE_KEYS:
            return "<REDACTED_TEXT>"
        if lowered in PATH_KEYS:
            return _sanitize_text(value)
        if lowered in SECRET_KEYS:
            return "<REDACTED_TOKEN>"
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(k): _sanitize_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v, key) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_value(v, key) for v in value]
    return value


def _sanitize_text(text: str) -> str:
    private_marker = "PRIVATE " + "KEY"
    value = TOKEN_RE.sub(lambda m: "<PRIVATE_KEY>" if private_marker in m.group(0).upper() else "<REDACTED_TOKEN>", text)
    value = USER_PATH_RE.sub("<USER_PATH>", value)
    if len(value) > MAX_LOG_STRING_CHARS:
        value = value[:MAX_LOG_STRING_CHARS] + "<TRUNCATED>"
    if "Traceback" in value:
        value = value.split("Traceback", 1)[0] + "<REDACTED_TEXT>"
    return value


def _bounded_text(text: str, limit: int) -> str:
    return str(text)[:limit]
