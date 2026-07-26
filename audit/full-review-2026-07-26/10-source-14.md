# Полный исходный код (продолжение)

### ПУТЬ: modules/desktop_ipc_contract_ru.py (436 строк, 18914 байт)

````python
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
````

### ПУТЬ: modules/desktop_observer.py (338 строк, 10962 байт)

````python
import ctypes
import ctypes.wintypes
import json
import os
import struct
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "desktop_observer"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _window_text(hwnd):
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_class(hwnd):
    try:
        user32 = ctypes.windll.user32
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_rect(hwnd):
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
        }
    except Exception:
        return {}


def _active_window():
    if os.name != "nt":
        return {"title": "", "class": "", "rect": {}, "error": "desktop observer currently supports Windows"}

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return {
            "title": _window_text(hwnd),
            "class": _window_class(hwnd),
            "rect": _window_rect(hwnd),
            "hwnd": int(hwnd),
        }
    except Exception as exc:
        return {"title": "", "class": "", "rect": {}, "error": str(exc)}


def _visible_windows(limit=30):
    if os.name != "nt":
        return []

    user32 = ctypes.windll.user32
    windows = []

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            title = _window_text(hwnd)
            if not title:
                return True

            rect = _window_rect(hwnd)
            if rect and (rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0):
                return True

            windows.append({
                "title": title,
                "class": _window_class(hwnd),
                "rect": rect,
                "hwnd": int(hwnd),
            })

            return len(windows) < limit
        except Exception:
            return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(callback)
    user32.EnumWindows(enum_proc, 0)
    return windows


def _capture_screenshot():
    _ensure_dirs()
    png_path = SCREENSHOTS_DIR / f"desktop_{_stamp()}.png"

    try:
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        image.save(png_path)
        return str(png_path), ""
    except Exception as exc:
        bmp_path, bmp_error = _capture_screenshot_bmp()
        if bmp_path:
            return bmp_path, f"PIL unavailable, used BMP fallback: {exc}"
        return "", f"{exc}; BMP fallback failed: {bmp_error}"


def _capture_screenshot_bmp():
    if os.name != "nt":
        return "", "BMP fallback currently supports Windows only"

    path = SCREENSHOTS_DIR / f"desktop_{_stamp()}.bmp"
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hdc_screen = None
    hdc_mem = None
    hbmp = None
    old_obj = None

    try:
        x = user32.GetSystemMetrics(76)
        y = user32.GetSystemMetrics(77)
        width = user32.GetSystemMetrics(78)
        height = user32.GetSystemMetrics(79)

        if width <= 0 or height <= 0:
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            x = 0
            y = 0

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        old_obj = gdi32.SelectObject(hdc_mem, hbmp)

        srccopy = 0x00CC0020
        captureblt = 0x40000000
        if not gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x, y, srccopy | captureblt):
            return "", "BitBlt failed"

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.wintypes.DWORD),
                ("biWidth", ctypes.wintypes.LONG),
                ("biHeight", ctypes.wintypes.LONG),
                ("biPlanes", ctypes.wintypes.WORD),
                ("biBitCount", ctypes.wintypes.WORD),
                ("biCompression", ctypes.wintypes.DWORD),
                ("biSizeImage", ctypes.wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.wintypes.LONG),
                ("biYPelsPerMeter", ctypes.wintypes.LONG),
                ("biClrUsed", ctypes.wintypes.DWORD),
                ("biClrImportant", ctypes.wintypes.DWORD),
            ]

        class BitmapInfo(ctypes.Structure):
            _fields_ = [
                ("bmiHeader", BitmapInfoHeader),
                ("bmiColors", ctypes.wintypes.DWORD * 3),
            ]

        bitmap_info = BitmapInfo()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BitmapInfoHeader)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = 0
        bitmap_info.bmiHeader.biSizeImage = width * height * 4

        buffer = ctypes.create_string_buffer(bitmap_info.bmiHeader.biSizeImage)
        lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bitmap_info), 0)
        if lines == 0:
            return "", "GetDIBits failed"

        pixel_data = buffer.raw
        file_header_size = 14
        info_header_size = 40
        offset = file_header_size + info_header_size
        file_size = offset + len(pixel_data)

        with path.open("wb") as handle:
            handle.write(struct.pack("<2sIHHI", b"BM", file_size, 0, 0, offset))
            handle.write(struct.pack(
                "<IiiHHIIiiII",
                info_header_size,
                width,
                height,
                1,
                32,
                0,
                len(pixel_data),
                0,
                0,
                0,
                0,
            ))
            handle.write(pixel_data)

        return str(path), ""
    except Exception as exc:
        return "", str(exc)
    finally:
        try:
            if old_obj and hdc_mem:
                gdi32.SelectObject(hdc_mem, old_obj)
            if hbmp:
                gdi32.DeleteObject(hbmp)
            if hdc_mem:
                gdi32.DeleteDC(hdc_mem)
            if hdc_screen:
                user32.ReleaseDC(0, hdc_screen)
        except Exception:
            pass


def _write_report(result):
    _ensure_dirs()
    path = REPORTS_DIR / f"desktop_observe_{_stamp()}.md"
    active = result.get("active_window") or {}
    windows = result.get("windows") or []

    lines = [
        "# Desktop Observe Report",
        "",
        f"- created_at: {result.get('created_at')}",
        f"- screenshot_path: {result.get('screenshot_path') or 'нет'}",
        f"- screenshot_error: {result.get('screenshot_error') or 'нет'}",
        "",
        "## Active Window",
        "",
        f"- title: {active.get('title') or 'нет'}",
        f"- class: {active.get('class') or 'нет'}",
        f"- rect: `{json.dumps(active.get('rect') or {}, ensure_ascii=False)}`",
        "",
        "## Visible Windows",
        "",
    ]

    if windows:
        for index, window in enumerate(windows, start=1):
            title = window.get("title") or "нет"
            cls = window.get("class") or "нет"
            rect = json.dumps(window.get("rect") or {}, ensure_ascii=False)
            lines.append(f"{index}. `{title}` | class: `{cls}` | rect: `{rect}`")
    else:
        lines.append("- нет")

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def observe_desktop(write_report=True):
    _ensure_dirs()
    screenshot_path, screenshot_error = _capture_screenshot()
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "active_window": _active_window(),
        "windows": _visible_windows(),
        "screenshot_path": screenshot_path,
        "screenshot_error": screenshot_error,
        "report_path": "",
    }

    if write_report:
        result["report_path"] = _write_report(result)

    try:
        set_value("desktop_observer: да", "да")
        set_value("last_desktop_observation_report", result.get("report_path") or "")
        set_value("last_desktop_screenshot", result.get("screenshot_path") or "")
        set_value("last_desktop_active_window", (result.get("active_window") or {}).get("title") or "")
        set_value("last_desktop_observation", json.dumps(result, ensure_ascii=False)[:5000])
    except Exception:
        pass

    return result


def format_desktop_observation(result):
    active = result.get("active_window") or {}
    windows = result.get("windows") or []
    lines = [
        "Desktop Observe:",
        f"- created_at: {result.get('created_at')}",
        f"- active_window: {active.get('title') or 'нет'}",
        f"- active_class: {active.get('class') or 'нет'}",
        f"- visible_windows: {len(windows)}",
        f"- screenshot: {result.get('screenshot_path') or 'нет'}",
        f"- screenshot_error: {result.get('screenshot_error') or 'нет'}",
        f"- report: {result.get('report_path') or 'нет'}",
        "",
        "Visible windows:",
    ]

    if windows:
        for index, window in enumerate(windows[:12], start=1):
            lines.append(f"{index}. {window.get('title') or 'нет'}")
    else:
        lines.append("- нет")

    return "\n".join(lines)


def latest_desktop_observation_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("desktop_observe_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
````

### ПУТЬ: modules/desktop_sidecar_runtime_ru.py (444 строк, 17469 байт)

````python
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
    TIMEOUT_ERROR_CODES,
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

    def close(self) -> None:
        """Boundedly stop the model worker when the runner loses its IPC peer."""
        self._model_gateway.shutdown()

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
            if method == "model.managed.attach" and exc.code in TIMEOUT_ERROR_CODES:
                code = "timeout"
            else:
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
````

### ПУТЬ: modules/development_safety_orchestrator_ru.py (407 строк, 11849 байт)

````python
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

DEVELOPMENT_SAFETY_VERSION = "v6.77"

def _project_root() -> Path:
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        if env_name in os.environ:
            return Path(os.environ[env_name]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _project_root()

_SOURCE_SUFFIXES = {
    ".py",
    ".pyw",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
    ".md",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT_DIR),
        check=False,
    )


def _parse_status_line(line: str) -> Dict[str, Any]:
    if len(line) < 3:
        return {
            "raw": line,
            "xy": "",
            "path": line.strip(),
            "staged": False,
            "unstaged": False,
            "deleted": False,
        }

    xy = line[:2]
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()

    return {
        "raw": line,
        "xy": xy,
        "path": path,
        "staged": xy[0] not in {" ", "?"},
        "unstaged": xy[1] not in {" ", "?"},
        "deleted": "D" in xy,
    }


def _git_status_snapshot() -> Dict[str, Any]:
    try:
        result = _run_git("status", "--short", "--untracked-files=no")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "untracked_ignored_for_risk": True,
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": result.stderr.strip() or f"git status exited with {result.returncode}",
            "untracked_ignored_for_risk": True,
        }

    raw_lines = [line for line in result.stdout.splitlines() if line.strip()]
    entries = [_parse_status_line(line) for line in raw_lines]
    tracked_paths = [entry["path"] for entry in entries]
    source_paths = [
        path
        for path in tracked_paths
        if Path(path).suffix.lower() in _SOURCE_SUFFIXES
    ]
    deleted_files = [entry["path"] for entry in entries if entry["deleted"]]

    return {
        "ok": True,
        "total_changed": len(entries),
        "tracked_changed": len(entries),
        "staged_changed": sum(1 for entry in entries if entry["staged"]),
        "unstaged_changed": sum(1 for entry in entries if entry["unstaged"]),
        "untracked": None,
        "untracked_ignored_for_risk": True,
        "source_changed": len(source_paths),
        "source_paths": source_paths,
        "deleted": deleted_files,
        "lines": raw_lines,
        "entries": entries,
    }


def _gate_snapshot() -> Dict[str, Any]:
    result: Dict[str, Any] = {"contracts": {}, "strict": {}}

    try:
        from modules.computer_use_core_ru import dispatch as computer_use_dispatch

        response = computer_use_dispatch("pc computer contracts")
        summary = response.get("summary", {})
        result["contracts"] = {
            "passed": summary.get("passed"),
            "total": summary.get("total"),
            "ok": response.get("ok"),
        }
    except Exception as exc:
        result["contracts"] = {"error": f"{type(exc).__name__}: {exc}", "ok": False}

    try:
        from modules.strict_project_stability_ru import dispatch as stability_dispatch

        response = stability_dispatch("проверь проект")
        result["strict"] = {
            "ok": response.get("ok"),
            "hard_failures": response.get("hard_failures"),
            "warnings": response.get("warnings"),
        }
    except Exception as exc:
        result["strict"] = {"error": f"{type(exc).__name__}: {exc}", "ok": False}

    return result


def _normalize_allow_write(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("allow", False))
    return bool(value)


def _screenshot_policy_snapshot() -> Dict[str, Any]:
    try:
        from modules.screenshot_capture_policy_ru import (
            is_screenshot_capture_enabled,
            should_allow_screenshot_write,
        )

        raw_allow_write = should_allow_screenshot_write()
        return {
            "ok": True,
            "capture_enabled": bool(is_screenshot_capture_enabled()),
            "allow_write": _normalize_allow_write(raw_allow_write),
            "allow_write_raw": raw_allow_write,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _diff_risk_snapshot(git_data: Dict[str, Any]) -> Dict[str, Any]:
    if not git_data.get("ok"):
        return {
            "total_changed": 0,
            "source_changed": 0,
            "deleted_source_count": 0,
            "deleted_files": [],
            "risky_paths": [],
            "untracked_ignored_for_risk": True,
            "verdict": "HOLD_REVIEW_REQUIRED",
            "error": git_data.get("error", "Unable to read tracked Git status."),
        }

    total = int(git_data.get("tracked_changed", 0))
    source = int(git_data.get("source_changed", 0))
    deleted = list(git_data.get("deleted", []))
    risky_paths: list[str] = []

    keywords = {
        "screenshot",
        "backup",
        "venv",
        "node_modules",
        ".git",
        "credentials",
        ".env",
        "secret",
    }

    for path in (entry.get("path", "") for entry in git_data.get("entries", [])):
        lower_path = path.lower()
        if any(keyword in lower_path for keyword in keywords):
            risky_paths.append(path)

    verdict = "GREEN_TO_CONTINUE"
    if source >= 9 or total >= 16:
        verdict = "HOLD"
    if source > 15:
        verdict = "HOLD_REVIEW_REQUIRED"
    if total > 50:
        verdict = "REJECT_RECOVERY_REQUIRED"
    if deleted:
        verdict = "HOLD_REVIEW_REQUIRED"
    if risky_paths and verdict == "GREEN_TO_CONTINUE":
        verdict = "HOLD"

    return {
        "total_changed": total,
        "source_changed": source,
        "deleted_source_count": len(deleted),
        "deleted_files": deleted,
        "risky_paths": risky_paths,
        "untracked_ignored_for_risk": True,
        "verdict": verdict,
    }


def collect_git_status_snapshot() -> Dict[str, Any]:
    return _git_status_snapshot()


def collect_gate_snapshot() -> Dict[str, Any]:
    return _gate_snapshot()


def collect_screenshot_policy_snapshot() -> Dict[str, Any]:
    return _screenshot_policy_snapshot()


def collect_diff_risk_snapshot() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    result = _diff_risk_snapshot(git_data)
    result["mode"] = "development_safety_diff_snapshot"
    result["version"] = DEVELOPMENT_SAFETY_VERSION
    return result


def evaluate_development_safety() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    gates = _gate_snapshot()
    screenshot = _screenshot_policy_snapshot()
    diff = _diff_risk_snapshot(git_data)

    contracts_ok = gates.get("contracts", {}).get("ok") is True
    strict_ok = gates.get("strict", {}).get("ok") is True
    gates_ok = contracts_ok and strict_ok

    screenshot_ok = (
        screenshot.get("ok") is True
        and screenshot.get("capture_enabled") is False
        and screenshot.get("allow_write") is False
    )

    if not git_data.get("ok") or not screenshot.get("ok"):
        overall = "HOLD_REVIEW_REQUIRED"
    elif screenshot_ok and gates_ok and diff.get("verdict") == "GREEN_TO_CONTINUE":
        overall = "GREEN_TO_CONTINUE"
    elif not gates_ok:
        overall = "HOLD_REVIEW_REQUIRED"
    elif not screenshot_ok:
        overall = "REJECT_RECOVERY_REQUIRED"
    else:
        overall = diff.get("verdict", "HOLD")

    return {
        "ok": True,
        "mode": "development_safety_evaluation",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "git_status": git_data,
        "gates": gates,
        "screenshot_policy": screenshot,
        "diff_risk": diff,
        "overall_verdict": overall,
    }


def _lightweight_status() -> Dict[str, Any]:
    git_data = _git_status_snapshot()
    screenshot = _screenshot_policy_snapshot()
    diff = _diff_risk_snapshot(git_data)

    contracts_skip = {
        "ok": None,
        "executed": False,
        "reason": "not_run_in_lightweight_status",
    }
    strict_skip = {
        "ok": None,
        "executed": False,
        "reason": "not_run_in_lightweight_status",
    }

    if not git_data.get("ok") or not screenshot.get("ok"):
        overall = "HOLD_REVIEW_REQUIRED"
    elif screenshot.get("capture_enabled") or screenshot.get("allow_write"):
        overall = "REJECT_RECOVERY_REQUIRED"
    else:
        overall = diff.get("verdict", "HOLD")

    return {
        "ok": True,
        "mode": "development_safety_evaluation",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "lightweight": True,
        "git_status": git_data,
        "gates": {
            "contracts": contracts_skip,
            "strict": strict_skip,
        },
        "screenshot_policy": screenshot,
        "diff_risk": diff,
        "overall_verdict": overall,
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "development_safety_orchestrator_status",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "evaluation": _lightweight_status(),
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "development_safety_orchestrator_report",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "generated_at": _now(),
        "status": {
            "ok": True,
            "mode": "development_safety_orchestrator_status",
            "version": DEVELOPMENT_SAFETY_VERSION,
            "evaluation": evaluate_development_safety(),
        },
    }


def is_development_safety_command(command: str = "") -> bool:
    lower = str(command or "").strip().lower().replace("ё", "е")
    return lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
        "report",
        "pc dev safety report",
        "preflight audit",
        "pc preflight audit",
        "diff limit status",
        "pc diff limit status",
        "opencode recovery status",
        "pc opencode recovery status",
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")

    if lower in {
        "status",
        "development safety status",
        "dev safety status",
        "статус разработки",
        "pc dev safety status",
    }:
        return status()

    if lower in {"report", "pc dev safety report"}:
        return report()

    if lower in {"preflight audit", "pc preflight audit"}:
        return evaluate_development_safety()

    if lower in {"diff limit status", "pc diff limit status"}:
        return collect_diff_risk_snapshot()

    if lower in {"opencode recovery status", "pc opencode recovery status"}:
        return evaluate_development_safety()

    return {
        "ok": False,
        "mode": "development_safety_orchestrator_unrecognized",
        "version": DEVELOPMENT_SAFETY_VERSION,
        "result": (
            "Неизвестная команда. Используйте: статус разработки, "
            "development safety status, preflight audit, diff limit status, "
            "opencode recovery status"
        ),
    }
````

### ПУТЬ: modules/diagnostics.py (233 строк, 6516 байт)

````python
from pathlib import Path
from modules.project_paths import get_project_root
from datetime import datetime
import requests

from config import MODEL, LMSTUDIO_API
from core.state import load_state, get_value, STATE_FILE


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
NOTES_DIR = PROJECTS_DIR / "Notes"
FILES_DIR = PROJECTS_DIR / "Files"
WINDOWS_DIR = PROJECTS_DIR / "Windows"
MEMORY_DIR = ROOT_DIR / "memory"


def _models_url():
    return LMSTUDIO_API.replace("/chat/completions", "/models")


def _short_text(value, limit: int = 500):
    text = str(value)

    if len(text) > limit:
        return text[:limit] + "... [обрезано]"

    return text


def check_lmstudio():
    url = _models_url()

    lines = [
        "## Проверка LM Studio",
        "",
        f"- API chat: {LMSTUDIO_API}",
        f"- API models: {url}",
        f"- MODEL в config.py: {MODEL}",
        "",
    ]

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        models = data.get("data", [])

        ids = [m.get("id") for m in models if m.get("id")]

        lines.append("Статус: ✅ LM Studio API отвечает.")
        lines.append("")
        lines.append("Доступные модели:")

        if ids:
            for model_id in ids:
                mark = "✅" if model_id == MODEL else "-"
                lines.append(f"{mark} {model_id}")
        else:
            lines.append("- Модели не найдены.")

        if MODEL in ids:
            lines.append("")
            lines.append(f"Итог: ✅ текущая модель `{MODEL}` доступна.")
        else:
            lines.append("")
            lines.append(f"Итог: ⚠️ текущая модель `{MODEL}` НЕ найдена в списке /v1/models.")

    except Exception as e:
        lines.append("Статус: ❌ LM Studio API не отвечает.")
        lines.append("")
        lines.append(f"Ошибка: {e}")
        lines.append("")
        lines.append("Что проверить:")
        lines.append("1. Открыт ли LM Studio.")
        lines.append("2. Запущен ли Local Server.")
        lines.append("3. Загружена ли модель.")
        lines.append("4. Порт должен быть 1234.")

    return "\n".join(lines)


def check_workspace():
    dirs = [
        ("ROOT", ROOT_DIR),
        ("Projects", PROJECTS_DIR),
        ("Reports", REPORTS_DIR),
        ("Notes", NOTES_DIR),
        ("Files", FILES_DIR),
        ("Windows", WINDOWS_DIR),
        ("memory", MEMORY_DIR),
    ]

    lines = [
        "## Проверка папок LocalComet",
        "",
    ]

    for name, path in dirs:
        if path.exists():
            lines.append(f"✅ {name}: {path}")
        else:
            lines.append(f"❌ {name}: {path}")

    return "\n".join(lines)


def check_memory():
    state = load_state()

    lines = [
        "## Проверка памяти LocalComet",
        "",
        f"STATE_FILE: {STATE_FILE}",
        "",
    ]

    if STATE_FILE.exists():
        lines.append("Статус: ✅ state.json найден.")
    else:
        lines.append("Статус: ⚠️ state.json пока не создан.")

    if not state:
        lines.append("")
        lines.append("Память пустая.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Ключи памяти:")

    for key, value in state.items():
        value_text = _short_text(value, limit=500)
        lines.append(f"- {key}: {value_text}")

    return "\n".join(lines)


def check_reports():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = sorted(
        REPORTS_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    lines = [
        "## Проверка отчетов",
        "",
        f"Папка: {REPORTS_DIR}",
        f"Всего отчетов: {len(reports)}",
        "",
    ]

    if not reports:
        lines.append("Отчетов пока нет.")
        return "\n".join(lines)

    lines.append("Последние отчеты:")

    for report in reports[:10]:
        modified = datetime.fromtimestamp(report.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"- {report.name} — {modified}")

    lines.append("")
    lines.append(f"last_report в памяти: {get_value('last_report', 'нет')}")

    return "\n".join(lines)


def check_files():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)

    notes = list(NOTES_DIR.glob("*.md"))
    files = [p for p in FILES_DIR.rglob("*") if p.is_file()]
    windows_files = [p for p in WINDOWS_DIR.rglob("*") if p.is_file()]

    lines = [
        "## Проверка файлов Workspace",
        "",
        f"Заметок: {len(notes)}",
        f"Файлов в Projects/Files: {len(files)}",
        f"Файлов в Projects/Windows: {len(windows_files)}",
        "",
        f"last_workspace_file: {get_value('last_workspace_file', 'нет')}",
        f"last_windows_file: {get_value('last_windows_file', 'нет')}",
    ]

    if files:
        lines.append("")
        lines.append("Последние файлы:")

        sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

        for file in sorted_files[:10]:
            lines.append(f"- {file.relative_to(FILES_DIR)}")

    return "\n".join(lines)


def check_last_error():
    last_error = get_value("last_error")

    if not last_error:
        return "Последней ошибки нет."

    return "Последняя ошибка:\n" + str(last_error)


def full_diagnostics():
    sections = [
        "# Диагностика LocalComet",
        "",
        check_lmstudio(),
        "",
        check_workspace(),
        "",
        check_memory(),
        "",
        check_reports(),
        "",
        check_files(),
        "",
        "## Последняя ошибка",
        "",
        check_last_error(),
    ]

    return "\n".join(sections)
````

### ПУТЬ: modules/executor_adapter_registry_ru.py (236 строк, 9798 байт)

````python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional

EXECUTOR_ADAPTER_VERSION = "v6.76"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _registry() -> List[Dict[str, Any]]:
    return [
        {
            "id": "opencode_deepseek",
            "title": "OpenCode with DeepSeek v4",
            "type": "local_ai",
            "strength": "Fast inference, strong coding capability",
            "weaknesses": "Limited context window, no vision",
            "allowed_task_types": ["code_generation", "code_review", "refactoring", "test_writing", "patch_creation"],
            "forbidden_task_types": ["sensitive_data_handling", "browser_automation", "external_api_calls"],
            "max_recommended_diff_files": 8,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Default development agent for LocalComet tasks.",
        },
        {
            "id": "opencode_qwen",
            "title": "OpenCode with Qwen-Coder",
            "type": "local_ai",
            "strength": "Good for open-ended research, alternative code perspective",
            "weaknesses": "Slower inference, may need more guidance",
            "allowed_task_types": ["code_review", "research", "architecture_exploration", "test_writing"],
            "forbidden_task_types": ["sensitive_data_handling", "browser_automation", "external_api_calls", "rapid_iteration"],
            "max_recommended_diff_files": 5,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Alternative model for code review and exploration.",
        },
        {
            "id": "opencode_north",
            "title": "OpenCode with North AI",
            "type": "hosted_ai",
            "strength": "Strong reasoning, large context",
            "weaknesses": "Requires internet, potentially higher cost",
            "allowed_task_types": ["complex_architecture", "security_audit", "large_refactoring"],
            "forbidden_task_types": ["rapid_iteration", "simple_patches"],
            "max_recommended_diff_files": 15,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Hosted model for complex tasks.",
        },
        {
            "id": "manual_patch",
            "title": "Manual Patch by Developer",
            "type": "human",
            "strength": "Full control, best for sensitive changes",
            "weaknesses": "Slow, requires developer time",
            "allowed_task_types": ["sensitive_data_handling", "security_patches", "critical_infrastructure"],
            "forbidden_task_types": [],
            "max_recommended_diff_files": 100,
            "requires_human_review": False,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": True,
            "status": "available",
            "notes": "Human developer makes changes manually.",
        },
        {
            "id": "chatgpt_manual_reviewer",
            "title": "ChatGPT Manual Reviewer",
            "type": "human_ai_review",
            "strength": "Human-in-the-loop AI review, independent perspective",
            "weaknesses": "No code execution, no file modification",
            "allowed_task_types": ["code_review", "validation_check", "architecture_review"],
            "forbidden_task_types": ["code_execution", "file_modification", "external_api_calls"],
            "max_recommended_diff_files": 20,
            "requires_human_review": True,
            "requires_green_gates": False,
            "can_execute_code": False,
            "can_modify_files": False,
            "can_use_external_api": False,
            "status": "available",
            "notes": "Review-only adapter. Verdicts must be read via reviewer bridge.",
        },
        {
            "id": "local_ollama_future",
            "title": "Local Ollama Model (Future)",
            "type": "local_ai_future",
            "strength": "Fully offline, no API costs",
            "weaknesses": "Not yet configured, model TBD",
            "allowed_task_types": ["code_generation", "code_review"],
            "forbidden_task_types": ["sensitive_data_handling", "rapid_iteration"],
            "max_recommended_diff_files": 5,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "future",
            "notes": "Requires Ollama installation and model download.",
        },
        {
            "id": "internal_patch_engine_future",
            "title": "Internal Patch Engine (Future)",
            "type": "automated_future",
            "strength": "Fast automated patches for well-defined tasks",
            "weaknesses": "Not implemented, limited scope",
            "allowed_task_types": ["simple_patches", "test_writing"],
            "forbidden_task_types": ["sensitive_data_handling", "complex_architecture"],
            "max_recommended_diff_files": 3,
            "requires_human_review": True,
            "requires_green_gates": True,
            "can_execute_code": True,
            "can_modify_files": True,
            "can_use_external_api": False,
            "status": "future",
            "notes": "Future automated patch engine.",
        },
    ]


def get_executor_adapter_registry() -> List[Dict[str, Any]]:
    return _registry()


def get_executor_adapter(adapter_id: str) -> Optional[Dict[str, Any]]:
    for entry in _registry():
        if entry["id"] == adapter_id:
            return entry
    return None


def classify_executor_for_task(task_description: str) -> Dict[str, Any]:
    lower = task_description.lower().replace("ё", "е")
    recommendations = []
    for entry in _registry():
        for allowed in entry["allowed_task_types"]:
            if allowed.replace("_", " ") in lower:
                recommendations.append(entry["id"])
                break
    return {
        "ok": True,
        "task_description": task_description,
        "matched_adapters": recommendations,
    }


def recommend_executor(task_description: str = "") -> Dict[str, Any]:
    if not task_description:
        return {
            "ok": True,
            "mode": "executor_recommendation",
            "version": EXECUTOR_ADAPTER_VERSION,
            "recommendation": "opencode_deepseek",
            "reason": "Default adapter for general LocalComet development.",
        }
    classification = classify_executor_for_task(task_description)
    matched = classification.get("matched_adapters", [])
    if matched:
        return {
            "ok": True,
            "mode": "executor_recommendation",
            "version": EXECUTOR_ADAPTER_VERSION,
            "recommendation": matched[0],
            "all_matches": matched,
            "reason": f"Matched task description to adapter(s): {', '.join(matched)}",
        }
    return {
        "ok": True,
        "mode": "executor_recommendation",
        "version": EXECUTOR_ADAPTER_VERSION,
        "recommendation": "opencode_deepseek",
        "reason": "No specific match, defaulting to opencode_deepseek.",
    }


def status() -> Dict[str, Any]:
    registry = _registry()
    return {
        "ok": True,
        "mode": "executor_adapter_registry_status",
        "version": EXECUTOR_ADAPTER_VERSION,
        "total_adapters": len(registry),
        "available": [e["id"] for e in registry if e["status"] == "available"],
        "future": [e["id"] for e in registry if "future" in e["status"]],
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "executor_adapter_registry_report",
        "version": EXECUTOR_ADAPTER_VERSION,
        "generated_at": _now(),
        "registry": _registry(),
        "status": status(),
    }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"status", "executor adapter status", "pc executor adapter status"}:
        return status()
    if lower in {"report", "executor registry", "реестр исполнителей", "pc executor registry"}:
        return report()
    if lower in {"recommend executor", "какой исполнитель лучше", "pc recommend executor"}:
        return recommend_executor()
    if lower.startswith("recommend executor ") or lower.startswith("какой исполнитель лучше "):
        desc = lower.split(" ", 2)[-1] if len(lower.split(" ", 2)) > 2 else ""
        return recommend_executor(desc)
    return {
        "mode": "executor_adapter_registry_unrecognized",
        "version": EXECUTOR_ADAPTER_VERSION,
        "result": "Неизвестная команда. Используйте: executor registry, реестр исполнителей, executor adapter status, recommend executor, какой исполнитель лучше",
    }
````

### ПУТЬ: modules/feature_verification.py (759 строк, 24177 байт)

````python
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from time import perf_counter


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
FEATURE_ROOT = PROJECTS_DIR / "FeatureVerification"
REPORTS_FEATURE_DIR = REPORTS_DIR / "feature_verification"
INVENTORY_PATH = FEATURE_ROOT / "feature_inventory.json"
LAST_OK_INVENTORY_PATH = FEATURE_ROOT / "feature_inventory_last_ok.json"

SCAN_ROOTS = [
    "agents",
    "core",
    "modules",
    "next",
]

ALWAYS_INCLUDE = [
    "LocalComet_Control_Panel.py",
]

SKIP_DIR_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SAFE_SMOKE_MODULES = [
    "modules.feature_verification",
    "modules.russian_command_context",
    "modules.premium_task_panel_ru",
    "modules.auto_verification",
    "modules.project_health",
    "modules.regression_commands",
    "modules.patch_registry",
    "core.project_context",
]

COMMAND_KEYWORDS = (
    "dispatch",
    "status",
    "report",
    "command",
    "commands",
    "is_",
    "pc ",
)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    FEATURE_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit=2600):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except Exception:
        return path.as_posix().replace("\\", "/")


def _is_skipped(path):
    parts = {part for part in Path(path).parts}
    return bool(parts & SKIP_DIR_PARTS)


def _python_files():
    files = []

    for relative in ALWAYS_INCLUDE:
        path = ROOT_DIR / relative
        if path.exists() and path.is_file():
            files.append(path)

    for root_name in SCAN_ROOTS:
        root = ROOT_DIR / root_name
        if not root.exists() or not root.is_dir():
            continue

        for path in root.rglob("*.py"):
            if path.is_file() and not _is_skipped(path):
                files.append(path)

    seen = set()
    result = []
    for path in files:
        normalized = _rel(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(path)

    return result


def _read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _file_hash(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _node_name(node):
    return getattr(node, "name", "")


def _literal_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _extract_string_literals(tree, limit=120):
    values = []
    for node in ast.walk(tree):
        value = _literal_string(node)
        if value:
            stripped = value.strip()
            if stripped and len(stripped) <= 160:
                values.append(stripped)
        if len(values) >= limit:
            break
    return values


def _extract_symbols(path):
    text = _read_text(path)
    rel = _rel(path)
    payload = {
        "path": rel,
        "hash": _file_hash(text),
        "line_count": len(text.splitlines()),
        "functions": [],
        "async_functions": [],
        "classes": [],
        "command_functions": [],
        "dispatch_functions": [],
        "status_functions": [],
        "report_functions": [],
        "command_literals": [],
        "parse_ok": True,
        "parse_error": "",
    }

    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        payload["parse_ok"] = False
        payload["parse_error"] = str(exc)
        return payload

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            payload["functions"].append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            payload["async_functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            payload["classes"].append(node.name)

    all_functions = set(payload["functions"]) | set(payload["async_functions"])

    for name in sorted(all_functions):
        lower = name.lower()
        if lower == "dispatch":
            payload["dispatch_functions"].append(name)
        if lower == "status" or lower.endswith("_status"):
            payload["status_functions"].append(name)
        if lower == "report" or lower.endswith("_report"):
            payload["report_functions"].append(name)
        if lower.startswith("is_") and lower.endswith("_command"):
            payload["command_functions"].append(name)

    literals = _extract_string_literals(tree)
    payload["command_literals"] = [
        item
        for item in literals
        if any(keyword in item.lower().replace("ё", "е") for keyword in COMMAND_KEYWORDS)
    ][:80]

    return payload


def scan_feature_inventory():
    files = [_extract_symbols(path) for path in _python_files()]
    files.sort(key=lambda item: item["path"])

    totals = {
        "files": len(files),
        "functions": sum(len(item.get("functions", [])) for item in files),
        "async_functions": sum(len(item.get("async_functions", [])) for item in files),
        "classes": sum(len(item.get("classes", [])) for item in files),
        "command_modules": sum(1 for item in files if item.get("command_functions") or item.get("dispatch_functions")),
        "parse_errors": sum(1 for item in files if not item.get("parse_ok")),
    }

    return {
        "ok": totals["parse_errors"] == 0,
        "mode": "feature_inventory",
        "generated_at": _now(),
        "root": str(ROOT_DIR),
        "totals": totals,
        "files": files,
    }


def _load_inventory(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _save_inventory(data, path):
    _ensure_dirs()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _symbols_for(item):
    return {
        "functions": set(item.get("functions", [])),
        "async_functions": set(item.get("async_functions", [])),
        "classes": set(item.get("classes", [])),
        "command_functions": set(item.get("command_functions", [])),
        "dispatch_functions": set(item.get("dispatch_functions", [])),
        "status_functions": set(item.get("status_functions", [])),
        "report_functions": set(item.get("report_functions", [])),
    }


def diff_inventory(current, previous=None):
    previous = previous or {}
    previous_files = {item.get("path"): item for item in previous.get("files", []) if item.get("path")}
    current_files = {item.get("path"): item for item in current.get("files", []) if item.get("path")}

    new_files = []
    changed_files = []
    removed_files = []
    new_symbols = []

    for path, item in current_files.items():
        before = previous_files.get(path)
        if before is None:
            new_files.append(path)
            symbols = _symbols_for(item)
            for group, names in symbols.items():
                for name in sorted(names):
                    new_symbols.append({"path": path, "kind": group, "name": name})
            continue

        if before.get("hash") != item.get("hash"):
            changed_files.append(path)
            before_symbols = _symbols_for(before)
            after_symbols = _symbols_for(item)
            for group, after_names in after_symbols.items():
                before_names = before_symbols.get(group, set())
                for name in sorted(after_names - before_names):
                    new_symbols.append({"path": path, "kind": group, "name": name})

    for path in previous_files:
        if path not in current_files:
            removed_files.append(path)

    return {
        "new_files": sorted(new_files),
        "changed_files": sorted(changed_files),
        "removed_files": sorted(removed_files),
        "new_symbols": new_symbols,
        "changed_or_new_files": sorted(set(new_files + changed_files)),
    }


def _compile_targets(diff, current):
    candidates = diff.get("changed_or_new_files", [])
    safe_bootstrap_files = [
        "modules/feature_verification.py",
        "modules/russian_command_context.py",
        "modules/premium_task_panel_ru.py",
        "modules/auto_verification.py",
        "LocalComet_Control_Panel.py",
    ]

    if not candidates:
        candidates = list(safe_bootstrap_files)

    if len(candidates) > 40:
        candidates = [
            path
            for path in candidates
            if path in set(safe_bootstrap_files)
            or path.startswith("modules/feature_")
            or path.startswith("modules/russian_")
        ]

    existing = []
    for path in candidates:
        full = ROOT_DIR / path
        if full.exists() and full.suffix == ".py":
            existing.append(path)

    if not existing:
        existing = [
            item["path"]
            for item in current.get("files", [])
            if item.get("path") in {
                "modules/feature_verification.py",
                "modules/russian_command_context.py",
                "modules/premium_task_panel_ru.py",
                "modules/auto_verification.py",
                "LocalComet_Control_Panel.py",
            }
        ]

    return sorted(set(existing))


def _run_py_compile(files):
    if not files:
        return {
            "ok": True,
            "name": "py_compile changed/new feature files",
            "output": "Нет новых или изменённых Python-файлов для py_compile.",
            "files": [],
        }

    result = subprocess.run(
        ["python", "-m", "py_compile", *files],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )

    return {
        "ok": result.returncode == 0,
        "name": "py_compile changed/new feature files",
        "files": files,
        "output": (
            f"CODE: {result.returncode}\n"
            f"FILES: {len(files)}\n"
            + "\n".join(f"- {path}" for path in files)
            + f"\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ),
    }


def _safe_import(module_name):
    started = perf_counter()
    try:
        module = importlib.import_module(module_name)
        return {
            "module": module_name,
            "ok": True,
            "duration_sec": round(perf_counter() - started, 3),
            "error": "",
            "has_status": callable(getattr(module, "status", None)),
            "has_report": callable(getattr(module, "report", None)),
            "has_dispatch": callable(getattr(module, "dispatch", None)),
        }
    except Exception:
        return {
            "module": module_name,
            "ok": False,
            "duration_sec": round(perf_counter() - started, 3),
            "error": _short(traceback.format_exc(), 900),
            "has_status": False,
            "has_report": False,
            "has_dispatch": False,
        }


def _run_smoke_imports():
    results = [_safe_import(module_name) for module_name in SAFE_SMOKE_MODULES]
    return {
        "ok": all(item["ok"] for item in results),
        "name": "safe smoke imports",
        "results": results,
    }


def _run_command_contract_checks(current):
    problems = []
    checked = 0

    for item in current.get("files", []):
        path = item.get("path", "")
        if not path.startswith("modules/"):
            continue

        has_command_surface = bool(
            item.get("command_functions")
            or item.get("dispatch_functions")
            or item.get("command_literals")
        )
        if not has_command_surface:
            continue

        checked += 1

        if item.get("dispatch_functions") and not item.get("status_functions"):
            problems.append(f"{path}: dispatch есть, но status/status_* не найден.")

        if item.get("dispatch_functions") and not item.get("report_functions"):
            problems.append(f"{path}: dispatch есть, но report/report_* не найден.")

    return {
        "ok": not problems,
        "name": "command module contracts",
        "checked": checked,
        "problems": problems,
    }


def _run_russian_context_contract():
    try:
        from modules.russian_command_context import (
            build_russian_agent_context,
            explain_russian_intent,
            normalize_russian_agent_command,
            status as context_status,
        )

        normalized = normalize_russian_agent_command("проверь новые функции")
        context = build_russian_agent_context("проверь новые функции")
        explained = explain_russian_intent("проверь новые функции")
        payload = context_status()

        ok = (
            normalized == "pc verify features"
            and "Русский контекст" in context
            and explained.get("suggested_command") == "pc verify features"
            and payload.get("ok") is True
        )

        return {
            "ok": ok,
            "name": "russian command context contract",
            "normalized": normalized,
            "intent": explained,
            "status": payload,
            "context_preview": _short(context, 700),
        }
    except Exception:
        return {
            "ok": False,
            "name": "russian command context contract",
            "error": _short(traceback.format_exc(), 1200),
        }


def _run_feature_module_contract():
    try:
        own_status = status()
        ok = (
            own_status.get("ok") is True
            and "pc verify features" in own_status.get("commands", [])
            and own_status.get("browser_used") is False
        )
        return {
            "ok": ok,
            "name": "feature verification contract",
            "status": own_status,
        }
    except Exception:
        return {
            "ok": False,
            "name": "feature verification contract",
            "error": _short(traceback.format_exc(), 1200),
        }


def run_feature_verification(write_report=True, allow_browser=False):
    _ensure_dirs()
    previous = _load_inventory(LAST_OK_INVENTORY_PATH)
    current = scan_feature_inventory()
    diff = diff_inventory(current, previous)
    compile_files = _compile_targets(diff, current)

    steps = [
        {
            "ok": current.get("ok") is True,
            "name": "static feature inventory",
            "totals": current.get("totals", {}),
            "parse_errors": [
                {"path": item.get("path"), "error": item.get("parse_error")}
                for item in current.get("files", [])
                if not item.get("parse_ok")
            ],
        },
        _run_py_compile(compile_files),
        _run_smoke_imports(),
        _run_command_contract_checks(current),
        _run_russian_context_contract(),
        _run_feature_module_contract(),
    ]

    passed = sum(1 for step in steps if step.get("ok"))
    total = len(steps)
    result = {
        "ok": passed == total,
        "status": "ok" if passed == total else "failed",
        "mode": "feature_verification",
        "generated_at": _now(),
        "allow_browser": bool(allow_browser),
        "browser_used": False,
        "passed": passed,
        "total": total,
        "diff": diff,
        "compile_files": compile_files,
        "inventory_totals": current.get("totals", {}),
        "steps": steps,
        "report": "",
        "inventory": str(INVENTORY_PATH),
        "last_ok_inventory": str(LAST_OK_INVENTORY_PATH),
    }

    _save_inventory(current, INVENTORY_PATH)

    if result["ok"]:
        _save_inventory(current, LAST_OK_INVENTORY_PATH)

    if write_report:
        result["report"] = str(write_feature_verification_report(result, current))

    return result


def format_feature_verification(result=None):
    result = result or run_feature_verification(write_report=False)
    diff = result.get("diff", {})
    lines = [
        "Feature Verification:",
        f"- status: {result.get('status')}",
        f"- mode: {result.get('mode')}",
        f"- score: {result.get('passed')}/{result.get('total')}",
        f"- generated_at: {result.get('generated_at')}",
        f"- browser_used: {str(result.get('browser_used')).lower()}",
        f"- report: {result.get('report') or 'не записан'}",
        "",
        "Detected changes:",
        f"- new_files: {len(diff.get('new_files', []))}",
        f"- changed_files: {len(diff.get('changed_files', []))}",
        f"- removed_files: {len(diff.get('removed_files', []))}",
        f"- new_symbols: {len(diff.get('new_symbols', []))}",
        "",
        "Checks:",
    ]

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] {step.get('name')}")

    problems = [step for step in result.get("steps", []) if not step.get("ok")]
    lines.extend(["", "Problems:"])

    if problems:
        for step in problems:
            lines.append(f"- {step.get('name')}: {_short(step.get('error') or step.get('problems') or step.get('output'), 400)}")
    else:
        lines.append("- Не обнаружены.")

    return "\n".join(lines)


def write_feature_verification_report(result=None, inventory=None):
    _ensure_dirs()
    result = result or run_feature_verification(write_report=False)
    inventory = inventory or scan_feature_inventory()
    path = REPORTS_FEATURE_DIR / f"feature_verification_{_stamp()}.md"
    diff = result.get("diff", {})

    lines = [
        "# Feature Verification",
        "",
        format_feature_verification({**result, "report": str(path)}),
        "",
        "## Inventory totals",
        "",
    ]

    for key, value in result.get("inventory_totals", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Changed or new files", ""])

    changed_or_new = diff.get("changed_or_new_files", [])
    if changed_or_new:
        for item in changed_or_new[:120]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Нет новых или изменённых файлов относительно последнего успешного inventory.")

    lines.extend(["", "## New symbols", ""])

    new_symbols = diff.get("new_symbols", [])
    if new_symbols:
        for item in new_symbols[:160]:
            lines.append(f"- `{item.get('path')}` · {item.get('kind')} · `{item.get('name')}`")
    else:
        lines.append("- Новые функции/классы не обнаружены.")

    lines.extend(["", "## Step details", ""])

    for step in result.get("steps", []):
        mark = "OK" if step.get("ok") else "FAIL"
        lines.extend([
            f"### [{mark}] {step.get('name')}",
            "",
            "```json",
            json.dumps(step, ensure_ascii=False, indent=2),
            "```",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def latest_feature_verification_report():
    if not REPORTS_FEATURE_DIR.exists():
        return None
    reports = [
        path
        for path in REPORTS_FEATURE_DIR.glob("feature_verification_*.md")
        if path.is_file()
    ]
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def status():
    latest = latest_feature_verification_report()
    previous = _load_inventory(LAST_OK_INVENTORY_PATH)
    current = scan_feature_inventory()
    return {
        "ok": True,
        "mode": "feature_verification_status",
        "generated_at": _now(),
        "browser_used": False,
        "checks_new_functions": True,
        "detects_new_functions": True,
        "auto_verification_integration": True,
        "inventory": str(INVENTORY_PATH),
        "last_ok_inventory": str(LAST_OK_INVENTORY_PATH),
        "latest_report": str(latest) if latest else "",
        "has_baseline": bool(previous),
        "totals": current.get("totals", {}),
        "commands": [
            "pc verify features",
            "pc verify status",
            "pc verify report",
            "проверь новые функции",
            "автопроверка функций",
        ],
    }


def report():
    result = run_feature_verification(write_report=True, allow_browser=False)
    return {
        "ok": result.get("ok"),
        "mode": "feature_verification_report",
        "generated_at": _now(),
        "status": result.get("status"),
        "report": result.get("report"),
        "score": f"{result.get('passed')}/{result.get('total')}",
    }


def dispatch(command):
    text = str(command or "").strip()
    lower = text.lower().replace("ё", "е")

    if lower in {"pc verify", "pc verify status", "pc feature status", "pc features status", "статус проверки функций"}:
        return json.dumps(status(), ensure_ascii=False, indent=2)

    if lower in {
        "pc verify features",
        "pc feature verify",
        "pc features verify",
        "pc auto verify features",
        "проверь новые функции",
        "проверить новые функции",
        "автопроверка функций",
        "проверка функций",
    }:
        return json.dumps(run_feature_verification(write_report=True, allow_browser=False), ensure_ascii=False, indent=2)

    if lower in {"pc verify report", "pc feature report", "pc features report", "отчет проверки функций", "отчёт проверки функций"}:
        return json.dumps(report(), ensure_ascii=False, indent=2)

    return json.dumps(
        {
            "ok": False,
            "mode": "feature_verification_unknown_command",
            "generated_at": _now(),
            "error": "Неизвестная команда проверки функций.",
            "commands": status().get("commands", []),
        },
        ensure_ascii=False,
        indent=2,
    )


def is_feature_verification_command(command):
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower.startswith(("pc verify", "pc feature", "pc features", "pc auto verify")):
        return True
    return lower in {
        "проверь новые функции",
        "проверить новые функции",
        "автопроверка функций",
        "проверка функций",
        "статус проверки функций",
        "отчет проверки функций",
        "отчёт проверки функций",
    }
````

### ПУТЬ: modules/files.py (65 строк, 1668 байт)

````python
from pathlib import Path
from modules.project_paths import projects_dir
import shutil

BASE_DIR = projects_dir()
BASE_DIR.mkdir(parents=True, exist_ok=True)


def safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()

    if not str(target).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Запрещенный путь за пределами Projects.")

    return target


def create_folder(path: str):
    target = safe_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Папка создана: {target}"


def write_file(path: str, content: str):
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Файл создан: {target}"


def read_file(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Файл не найден: {target}"

    return target.read_text(encoding="utf-8")


def list_files(path: str = ""):
    target = safe_path(path)

    if not target.exists():
        return f"Папка не найдена: {target}"

    items = []
    for item in target.iterdir():
        kind = "DIR " if item.is_dir() else "FILE"
        items.append(f"{kind}: {item.name}")

    return "\n".join(items) if items else "Папка пустая."


def delete_path(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Не найдено: {target}"

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return f"Удалено: {target}"
````

### ПУТЬ: modules/first_failure_extractor_ru.py (262 строк, 8711 байт)

````python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List, Optional


FIRST_FAILURE_EXTRACTOR_VERSION = "v6.58"
FIRST_FAILURE_EXTRACTOR_NAME = "LocalComet First Failure Extractor RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _reports_dir() -> Path:
    return _root() / "Projects" / "Reports"


def _output_dir() -> Path:
    path = _reports_dir() / "developer_velocity"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_text(path: Path, limit: int = 250000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > limit:
        return text[: limit // 2] + "\n[... middle trimmed ...]\n" + text[-limit // 2 :]
    return text


def _candidate_logs() -> List[Path]:
    root = _root()
    bases = [
        root / "Projects" / "Reports" / "patch_panel_ux",
        root / "Projects" / "Reports" / "strict_project_stability",
        root / "Projects" / "Reports" / "localcomet_functional_tests",
        root / "Projects" / "Reports" / "computer_use_contracts",
        root / "Projects" / "ChatGPTRelay",
        root / "Projects" / "SelfEdit",
    ]
    patterns = ["latest*.md", "latest*.json", "*.md", "*.json", "*.txt", "*.log"]
    seen: Dict[str, Path] = {}
    for base in bases:
        if not base.exists():
            continue
        for pattern in patterns:
            for item in base.glob(pattern):
                if item.is_file():
                    try:
                        seen[str(item.resolve())] = item
                    except Exception:
                        seen[str(item)] = item
    return sorted(seen.values(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:80]


def _line_score(line: str) -> int:
    lower = line.lower().replace("ё", "е")
    score = 0
    high = [
        "traceback",
        "assertionerror",
        "filenotfounderror",
        "modulenotfounderror",
        "syntaxerror",
        "typeerror",
        "valueerror",
        "oserror",
        "exception",
        "code: 1",
        "code: 2",
        "code: 999",
        "rollback",
        "откачен",
        "тесты упали",
        "validation failed",
        "проверка не пройдена",
        "ошибка применения",
        "stop:",
    ]
    medium = ["fail", "failed", "hard_failures", "warnings", "blocked", "error", "ошибка", "упали"]
    for token in high:
        if token in lower:
            score += 100
    for token in medium:
        if token in lower:
            score += 20
    if re.search(r"\bCODE:\s*[1-9]\d*\b", line, re.IGNORECASE):
        score += 150
    return score


def _extract_from_text(text: str, source: str = "") -> Dict[str, Any]:
    lines = str(text or "").splitlines()
    best: Optional[Dict[str, Any]] = None
    for index, line in enumerate(lines):
        score = _line_score(line)
        if score <= 0:
            continue
        start = max(0, index - 3)
        end = min(len(lines), index + 8)
        context = "\n".join(lines[start:end]).strip()
        item = {
            "found": True,
            "source": source,
            "line_number": index + 1,
            "score": score,
            "first_error": line.strip()[:1000],
            "context": context[:5000],
        }
        if best is None or item["score"] > best["score"]:
            best = item
    if best:
        code_match = re.search(r"\bCODE:\s*([0-9]+)", best.get("context", ""), re.IGNORECASE)
        if code_match:
            best["code"] = int(code_match.group(1))
        return best
    return {
        "found": False,
        "source": source,
        "first_error": "",
        "context": "",
        "line_number": 0,
        "score": 0,
    }


def extract_first_failure_from_text(text: str, source: str = "text") -> Dict[str, Any]:
    payload = _extract_from_text(text, source=source)
    payload.update({
        "ok": True,
        "mode": "first_failure_from_text",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "generated_at": _now(),
    })
    return payload


def find_latest_failure(write_report: bool = True) -> Dict[str, Any]:
    candidates = _candidate_logs()
    best: Optional[Dict[str, Any]] = None
    inspected: List[str] = []
    for path in candidates:
        inspected.append(str(path))
        text = _read_text(path)
        item = _extract_from_text(text, source=str(path))
        if item.get("found") and (best is None or int(item.get("score", 0)) > int(best.get("score", 0))):
            best = item
    if best is None:
        best = {
            "found": False,
            "source": "",
            "first_error": "",
            "context": "",
            "line_number": 0,
            "score": 0,
        }
    payload: Dict[str, Any] = {
        "ok": True,
        "mode": "first_failure_extractor",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "generated_at": _now(),
        "failure": best,
        "inspected_count": len(inspected),
        "inspected": inspected[:25],
        "report": "",
        "json": "",
    }
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _output_dir()
    json_path = out / f"first_failure_{_stamp()}.json"
    md_path = out / f"first_failure_{_stamp()}.md"
    latest_json = out / "latest_first_failure.json"
    latest_md = out / "latest_first_failure.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    failure = payload.get("failure", {})
    lines = [
        "# LocalComet First Failure",
        "",
        f"- version: {payload.get('version')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- found: {failure.get('found')}",
        f"- source: {failure.get('source')}",
        f"- line: {failure.get('line_number')}",
        "",
        "## First error",
        "",
        "```text",
        str(failure.get("first_error", "")),
        "```",
        "",
        "## Context",
        "",
        "```text",
        str(failure.get("context", "")),
        "```",
    ]
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path, "latest_json": latest_json, "latest_md": latest_md}


def status(command: str = "status") -> Dict[str, Any]:
    latest = _output_dir() / "latest_first_failure.json"
    return {
        "ok": True,
        "mode": "first_failure_extractor_status",
        "version": FIRST_FAILURE_EXTRACTOR_VERSION,
        "latest_json": str(latest),
        "latest_exists": latest.exists(),
        "commands": ["последний сбой", "last failure", "first failure"],
    }


def report(command: str = "report") -> Dict[str, Any]:
    return find_latest_failure(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"последний сбой", "последняя ошибка", "first failure", "last failure", "latest failure"}:
        result = find_latest_failure(write_report=True)
        result["handled"] = True
        return result
    if lower in {"status", "статус", "first failure status"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет", "first failure report"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "first_failure_extractor", "reason": "unknown command"}
````

### ПУТЬ: modules/git_status.py (54 строк, 1360 байт)

````python
import subprocess
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()


def _run_git(args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=10,
    )

    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_status():
    code, stdout, stderr = _run_git(["rev-parse", "--is-inside-work-tree"])

    if code != 0 or stdout.lower() != "true":
        return {
            "state": "no repo",
            "branch": "",
            "last_commit": "",
            "dirty": False,
            "error": stderr or stdout or "not a git repository",
        }

    _, branch, _ = _run_git(["branch", "--show-current"])
    _, short_status, _ = _run_git(["status", "--short"])
    _, last_commit, _ = _run_git(["log", "-1", "--pretty=%h %s"])

    dirty = bool(short_status.strip())

    return {
        "state": "dirty" if dirty else "clean",
        "branch": branch or "unknown",
        "last_commit": last_commit or "unknown",
        "dirty": dirty,
        "error": "",
    }


def short_status():
    status = git_status()

    if status["state"] == "no repo":
        return "Git: no repo"

    return f"Git: {status['state']} | {status['branch']} | {status['last_commit']}"
````

### ПУТЬ: modules/global_update_center.py (355 строк, 12679 байт)

````python
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import subprocess
import traceback

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
GLOBAL_UPDATE_REPORTS_DIR = REPORTS_DIR / "global_update_center"
PATCH_REGISTRY_FILE = PROJECTS_DIR / "PatchRegistry" / "patches.json"
RELAY_RESPONSE_FILE = PROJECTS_DIR / "ChatGPTRelay" / "response.json"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _short(value, limit=2200):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[обрезано]"


def _safe_call(label, func):
    try:
        return {"ok": True, "label": label, "value": func(), "error": ""}
    except Exception:
        return {"ok": False, "label": label, "value": None, "error": traceback.format_exc()}


def _git_status_short():
    result = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=25,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _latest_file(folder: Path, patterns):
    if not folder.exists():
        return ""
    files = []
    for pattern in patterns:
        files.extend(folder.glob(pattern))
    files = [path for path in files if path.is_file()]
    if not files:
        return ""
    return str(max(files, key=lambda path: path.stat().st_mtime))


def _patch_registry_status():
    if not PATCH_REGISTRY_FILE.exists():
        return {"exists": False, "count": 0, "latest": None}

    try:
        data = json.loads(PATCH_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "count": 0, "latest": None, "error": str(exc)}

    patches = data if isinstance(data, list) else data.get("patches", []) if isinstance(data, dict) else []
    return {
        "exists": True,
        "count": len(patches),
        "latest": patches[-1] if patches else None,
    }


def _voice_status():
    try:
        from modules.voice_control import get_voice_status
        return get_voice_status()
    except Exception:
        return {"error": traceback.format_exc()}


def _pc_agent_health():
    try:
        from modules.pc_agent_core import pc_agent_health_snapshot
        return pc_agent_health_snapshot()
    except Exception:
        return {"error": traceback.format_exc()}


def _chatgpt_desktop_status():
    try:
        from modules.chatgpt_desktop_bridge import chatgpt_desktop_status, chatgpt_desktop_loop_status
        return {
            "status": chatgpt_desktop_status(),
            "loop": chatgpt_desktop_loop_status(),
        }
    except Exception:
        return {"error": traceback.format_exc()}


def build_global_update_plan():
    return {
        "title": "LocalComet Global Update Plan",
        "steps": [
            {
                "id": 1,
                "title": "Холодный безопасный режим",
                "command": "safe mode",
                "reason": "Выключить голос и известные циклы перед работой.",
            },
            {
                "id": 2,
                "title": "Проверка проекта",
                "command": "полная проверка",
                "reason": "Понять, что сломано до следующего patch.",
            },
            {
                "id": 3,
                "title": "Снимок релиза",
                "command": "снимок релиза",
                "reason": "Зафиксировать состояние перед крупными изменениями.",
            },
            {
                "id": 4,
                "title": "PC Agent next",
                "command": "что дальше",
                "reason": "Получить безопасные следующие шаги.",
            },
            {
                "id": 5,
                "title": "Коммит",
                "command": "статус git",
                "reason": "Коммитить только после зелёных проверок.",
            },
        ],
    }


def format_global_update_plan(plan=None):
    plan = plan or build_global_update_plan()
    lines = [plan.get("title", "Global Update Plan") + ":"]
    for step in plan.get("steps", []):
        lines.append("")
        lines.append(f"{step.get('id')}. {step.get('title')}")
        lines.append(f"   Команда: {step.get('command')}")
        lines.append(f"   Зачем: {step.get('reason')}")
    return "\n".join(lines)


def get_global_update_status():
    checks = {
        "git": _safe_call("git", _git_status_short),
        "patch_registry": _safe_call("patch_registry", _patch_registry_status),
        "voice": _safe_call("voice", _voice_status),
        "pc_agent": _safe_call("pc_agent", _pc_agent_health),
        "chatgpt_desktop": _safe_call("chatgpt_desktop", _chatgpt_desktop_status),
        "relay_response": {
            "ok": RELAY_RESPONSE_FILE.exists(),
            "path": str(RELAY_RESPONSE_FILE),
            "size": RELAY_RESPONSE_FILE.stat().st_size if RELAY_RESPONSE_FILE.exists() else 0,
        },
        "latest_reports": {
            "auto_verification": _latest_file(REPORTS_DIR / "auto_verification", ["*.md"]),
            "pc_agent": _latest_file(REPORTS_DIR / "pc_agent", ["*.md", "*.json"]),
            "voice": _latest_file(REPORTS_DIR / "voice_sessions", ["*.md", "*.json"]),
            "global_update_center": _latest_file(GLOBAL_UPDATE_REPORTS_DIR, ["*.md", "*.json"]),
        },
    }

    problems = []
    git_value = checks["git"].get("value") if checks["git"].get("ok") else {}
    git_text = ((git_value or {}).get("stdout") or "") + "\n" + ((git_value or {}).get("stderr") or "")
    if "??" in git_text or "\n M " in git_text or "\nM " in git_text or "\n D " in git_text:
        problems.append("Git содержит незакоммиченные изменения.")

    voice_value = checks["voice"].get("value") if checks["voice"].get("ok") else {}
    if isinstance(voice_value, dict) and voice_value.get("listening"):
        problems.append("Voice сейчас слушает микрофон.")
    if isinstance(voice_value, dict) and not voice_value.get("disabled", False):
        problems.append("Voice не заблокирован. Для холодного режима лучше держать Voice Kill включенным.")

    for name in ["pc_agent", "chatgpt_desktop"]:
        if not checks[name].get("ok"):
            problems.append(f"{name} не прочитан.")

    status = "attention" if problems else "ok"
    payload = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT_DIR),
        "checks": checks,
        "problems": problems,
        "recommended_next_steps": build_global_update_plan()["steps"],
    }
    set_value("last_global_update_status", payload)
    return payload


def format_global_update_status(payload):
    checks = payload.get("checks", {})
    problems = payload.get("problems", [])

    lines = [
        "Global Update Center:",
        f"- status: {payload.get('status')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- root: {payload.get('root')}",
        "",
        "Ключевые статусы:",
    ]

    git = checks.get("git", {})
    git_value = git.get("value") if isinstance(git, dict) else {}
    lines.append("- git: " + ("ok" if git.get("ok") else "fail"))
    if isinstance(git_value, dict) and git_value.get("stdout"):
        lines.append(_short(git_value.get("stdout"), 500))

    registry = checks.get("patch_registry", {})
    registry_value = registry.get("value") if isinstance(registry, dict) else {}
    if isinstance(registry_value, dict):
        lines.append(f"- patch_registry: {registry_value.get('count')} patches")

    voice = checks.get("voice", {})
    voice_value = voice.get("value") if isinstance(voice, dict) else {}
    if isinstance(voice_value, dict):
        lines.append(
            "- voice: "
            f"enabled={voice_value.get('enabled')} "
            f"disabled={voice_value.get('disabled')} "
            f"listening={voice_value.get('listening')} "
            f"muted={voice_value.get('muted')}"
        )

    relay = checks.get("relay_response", {})
    if isinstance(relay, dict):
        lines.append(f"- response.json: exists={relay.get('ok')} size={relay.get('size')}")

    lines.append("")
    lines.append("Проблемы:")
    if problems:
        lines.extend("- " + problem for problem in problems)
    else:
        lines.append("- Не обнаружены.")

    lines.append("")
    lines.append("Рекомендуемые следующие шаги:")
    for step in payload.get("recommended_next_steps", []):
        lines.append(f"{step.get('id')}. {step.get('title')} — {step.get('command')}")

    return "\n".join(lines)


def activate_safe_mode():
    actions = []

    try:
        from modules.voice_control import voice_kill_switch
        actions.append({"voice_kill_switch": voice_kill_switch(disable_voice=True)})
    except Exception:
        actions.append({"voice_kill_switch_error": traceback.format_exc()})

    try:
        from modules.pc_agent_core import pc_agent_loop_stop
        actions.append({"pc_agent_loop_stop": pc_agent_loop_stop()})
    except Exception:
        actions.append({"pc_agent_loop_stop_error": traceback.format_exc()})

    try:
        from modules.chatgpt_desktop_bridge import chatgpt_desktop_loop_stop
        actions.append({"chatgpt_desktop_loop_stop": chatgpt_desktop_loop_stop()})
    except Exception:
        actions.append({"chatgpt_desktop_loop_stop_error": "not available"})

    set_value("global_safe_mode", True)
    payload = {
        "ok": True,
        "safe_mode": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "actions": actions,
        "message": "Safe Mode enabled. Voice and known loops were asked to stop.",
    }
    set_value("last_global_safe_mode", payload)
    return payload


def create_release_snapshot(note=""):
    GLOBAL_UPDATE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    status = get_global_update_status()
    plan = build_global_update_plan()
    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note": str(note or "").strip(),
        "status": status,
        "plan": plan,
    }

    stamp = _stamp()
    json_path = GLOBAL_UPDATE_REPORTS_DIR / f"release_snapshot_{stamp}.json"
    md_path = GLOBAL_UPDATE_REPORTS_DIR / f"release_snapshot_{stamp}.md"

    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# LocalComet Release Snapshot",
        "",
        f"- generated_at: {snapshot['generated_at']}",
        f"- note: {snapshot['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_global_update_status(status),
        "```",
        "",
        "## Plan",
        "",
        "```text",
        format_global_update_plan(plan),
        "```",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    set_value("last_global_update_report", str(md_path))
    return {
        "ok": True,
        "json": str(json_path),
        "report": str(md_path),
        "status": status.get("status"),
        "problems": status.get("problems", []),
    }


def format_release_snapshot(payload):
    lines = [
        "Release Snapshot:",
        f"- ok: {payload.get('ok')}",
        f"- status: {payload.get('status')}",
        f"- report: {payload.get('report')}",
        f"- json: {payload.get('json')}",
        "",
        "Problems:",
    ]
    problems = payload.get("problems", [])
    if problems:
        lines.extend("- " + problem for problem in problems)
    else:
        lines.append("- Не обнаружены.")
    return "\n".join(lines)
````

### ПУТЬ: modules/gpt_browser_bridge.py (1288 строк, 41468 байт)

````python
import json
import os
import threading
import time
from pathlib import Path
from modules.project_paths import get_project_root

import pyperclip
from json_repair import repair_json
from playwright.sync_api import sync_playwright

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
PROFILE_DIR = PROJECTS_DIR / "BrowserProfile"
RELAY_DIR = PROJECTS_DIR / "ChatGPTRelay"
REQUEST_PATH = RELAY_DIR / "request.md"
RESPONSE_PATH = RELAY_DIR / "response.json"
RAW_ANSWER_PATH = RELAY_DIR / "gpt_browser_last_answer.txt"
RAW_RESPONSE_PATH = RELAY_DIR / "response_raw.md"
ERROR_REPORT_PATH = RELAY_DIR / "gpt_browser_response_error.md"
DOWNLOADS_DIR = RELAY_DIR / "Downloads"
BAD_RESPONSE_PATH = RELAY_DIR / "bad_response.json"

STRICT_JSON_INSTRUCTION = """
ВАЖНО ДЛЯ ОТВЕТА:
ГЛАВНЫЙ РЕЗУЛЬТАТ — создай скачиваемый файл response.json.
Файл response.json должен содержать строго валидный JSON с полями summary, operations, tests.
Не выводи большой JSON patch обычным текстом в чат, если можешь создать файл response.json.

Если создание файла response.json недоступно, верни ТОЛЬКО валидный JSON текстом:
- без markdown;
- без ```json;
- без объяснений до/после JSON;
- ответ должен начинаться с { и заканчиваться };
- JSON обязан содержать поля summary, operations, tests.

Не пиши вступление.
Не пиши "я вижу", "готово", "думал", пояснения или комментарии.
""".strip()

CHATGPT_URL = "https://chatgpt.com/"
GPT_BROWSER_CHAT_URL_KEY = "gpt_browser_chat_url"

_playwright = None
_context = None
_page = None
_owner_thread_id = None


def _remember_error(error):
    text = str(error or "")
    set_value("last_gpt_browser_error", text)
    return text


def _clear_error():
    set_value("last_gpt_browser_error", "")


def _saved_chat_url():
    return str(get_value(GPT_BROWSER_CHAT_URL_KEY, "") or "").strip()


def _target_chat_url():
    saved_chat_url = _saved_chat_url()
    return saved_chat_url if saved_chat_url else CHATGPT_URL


def set_chat_url(url):
    try:
        _clear_error()
        saved_chat_url = str(url or "").strip()

        if not saved_chat_url:
            raise ValueError("URL не указан.")

        if not saved_chat_url.startswith(("https://chatgpt.com/", "http://chatgpt.com/")):
            raise ValueError("Нужен URL chatgpt.com.")

        set_value(GPT_BROWSER_CHAT_URL_KEY, saved_chat_url)
        set_value("last_gpt_browser_action", "set_chat")
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)

        return (
            "GPT Browser Bridge: saved_chat_url сохранен.\n"
            f"saved_chat_url: {saved_chat_url}"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось сохранить saved_chat_url.\nОшибка: {e}"


def show_chat_url():
    saved_chat_url = _saved_chat_url()

    if not saved_chat_url:
        return "GPT Browser Bridge: saved_chat_url не задан."

    return f"GPT Browser Bridge saved_chat_url:\n{saved_chat_url}"


def clear_chat_url():
    set_value(GPT_BROWSER_CHAT_URL_KEY, "")
    set_value("last_gpt_browser_action", "clear_chat")
    set_value("last_gpt_browser_saved_chat_url", "")
    return "GPT Browser Bridge: saved_chat_url очищен."


def open_project_chat():
    saved_chat_url = _saved_chat_url()

    if not saved_chat_url:
        return "GPT Browser Bridge: saved_chat_url не задан. Сначала выполни: gpt browser set chat <url>"

    return open_chatgpt()


def _ensure_dirs():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    RELAY_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)



def _launch_persistent_context():
    """Launch visible browser with fixed downloads folder.

    Preference order:
    1. Installed Google Chrome
    2. Installed Microsoft Edge
    3. Playwright bundled Chromium
    """
    _ensure_dirs()

    base_kwargs = {
        "user_data_dir": str(PROFILE_DIR),
        "headless": False,
        "viewport": {"width": 1400, "height": 900},
        "accept_downloads": True,
        "downloads_path": str(DOWNLOADS_DIR),
        "args": [
            "--disable-blink-features=AutomationControlled",
        ],
    }

    last_error = None

    for channel, label in [
        ("chrome", "chrome"),
        ("msedge", "msedge"),
        (None, "chromium"),
    ]:
        try:
            kwargs = dict(base_kwargs)

            if channel:
                kwargs["channel"] = channel

            context = _playwright.chromium.launch_persistent_context(**kwargs)
            set_value("last_gpt_browser_engine", label)
            set_value("last_gpt_browser_downloads_dir", str(DOWNLOADS_DIR))
            return context

        except Exception as e:
            last_error = e
            set_value(f"last_gpt_browser_{label}_launch_error", str(e))

    raise RuntimeError(f"Не удалось открыть Chrome/Edge/Chromium: {last_error}")


def reset_bridge_state(reason=""):
    """Force reset Playwright globals without raising.

    Playwright sync objects are thread-affine. If a page/context/playwright was
    created in another thread, reusing it from the auto-cycle worker can fail
    with: cannot switch to a different thread.
    """
    global _playwright, _context, _page, _owner_thread_id

    errors = []

    try:
        if _page is not None:
            _page.close()
    except Exception as e:
        errors.append(f"page.close: {e}")

    try:
        if _context is not None:
            _context.close()
    except Exception as e:
        errors.append(f"context.close: {e}")

    try:
        if _playwright is not None:
            _playwright.stop()
    except Exception as e:
        errors.append(f"playwright.stop: {e}")

    _page = None
    _context = None
    _playwright = None
    _owner_thread_id = None

    set_value("last_gpt_browser_thread_reset_reason", str(reason or "manual_reset"))
    set_value("last_gpt_browser_thread_reset_errors", "\n".join(errors))
    set_value("last_gpt_browser_thread_reset_time", str(time.time()))

    if errors:
        return "GPT Browser Bridge: state reset выполнен с ошибками закрытия.\n" + "\n".join(errors)

    return "GPT Browser Bridge: state reset выполнен."


def _ensure_thread_owner():
    global _owner_thread_id

    current_thread_id = threading.get_ident()

    if _owner_thread_id is None:
        _owner_thread_id = current_thread_id
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))
        return

    if _owner_thread_id != current_thread_id:
        old_thread_id = _owner_thread_id
        reset_bridge_state(
            f"thread_changed old={old_thread_id} new={current_thread_id}"
        )
        _owner_thread_id = current_thread_id
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))


def _get_page(force_new: bool = False):
    global _playwright, _context, _page, _owner_thread_id

    _ensure_dirs()
    _ensure_thread_owner()

    if force_new:
        reset_bridge_state("force_new")
        _ensure_thread_owner()

    if _playwright is None:
        _playwright = sync_playwright().start()
        _owner_thread_id = threading.get_ident()
        set_value("last_gpt_browser_owner_thread_id", str(_owner_thread_id))

    if _context is None:
        _context = _launch_persistent_context()

    if _page is None or _page.is_closed():
        if _context.pages:
            _page = _context.pages[0]
        else:
            _page = _context.new_page()

    return _page


def close_bridge():
    global _playwright, _context, _page, _owner_thread_id

    closed = []
    errors = []

    try:
        if _page is not None and not _page.is_closed():
            _page.close()
            closed.append("page")
    except Exception as e:
        errors.append(f"page: {e}")

    try:
        if _context is not None:
            _context.close()
            closed.append("context")
    except Exception as e:
        errors.append(f"context: {e}")

    try:
        if _playwright is not None:
            _playwright.stop()
            closed.append("playwright")
    except Exception as e:
        errors.append(f"playwright: {e}")

    _page = None
    _context = None
    _playwright = None
    _owner_thread_id = None

    if closed:
        result = "GPT Browser Bridge: закрыт, BrowserProfile освобожден. Закрыто: " + ", ".join(closed)
    else:
        result = "GPT Browser Bridge: активный браузерный контекст не найден."

    if errors:
        result += "\nОшибки закрытия проигнорированы:\n" + "\n".join(errors)

    set_value("last_gpt_browser_action", "close")
    set_value("last_gpt_browser_close_result", result)
    set_value("last_gpt_browser_owner_thread_id", "")
    return result


def open_chatgpt():
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()
        page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_action", "open")
        set_value("last_gpt_browser_profile", str(PROFILE_DIR))
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)

        return (
            "GPT Browser Bridge: ChatGPT открыт.\n"
            f"URL: {page.url}\n"
            f"saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
            f"Profile: {PROFILE_DIR}\n\n"
            "Если видишь экран входа — войди вручную один раз. Профиль сохранится."
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось открыть ChatGPT.\nОшибка: {e}"


def _latest_request_path():
    candidates = [
        get_value("last_relay_dated_request", ""),
        get_value("last_relay_request", ""),
        get_value("last_relay_request_path", ""),
        get_value("last_request_path", ""),
        str(REQUEST_PATH),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        path = Path(str(candidate))

        if path.exists() and path.is_file():
            return path

    dated_dir = RELAY_DIR / "Requests"

    if dated_dir.exists():
        requests = list(dated_dir.glob("request_*.md"))

        if requests:
            return max(requests, key=lambda p: p.stat().st_mtime)

    return REQUEST_PATH


def _find_prompt_input(page):
    selectors = [
        "[data-testid='prompt-textarea']",
        "textarea[data-testid='prompt-textarea']",
        "div[contenteditable='true']",
        "textarea",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).last
            locator.wait_for(timeout=5000)
            return locator
        except Exception:
            continue

    raise RuntimeError("Не нашел поле ввода ChatGPT.")


def paste_text(text: str):
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()

        if "chatgpt.com" not in page.url:
            page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        elif saved_chat_url and not page.url.startswith(saved_chat_url):
            page.goto(saved_chat_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

        value = str(text or "").strip()

        if not value:
            return "GPT Browser Bridge: paste_text получил пустой текст."

        pyperclip.copy(value)
        prompt = _find_prompt_input(page)
        prompt.click(timeout=7000)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(1000)

        set_value("last_gpt_browser_action", "paste_text")
        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)
        set_value("last_gpt_browser_paste_text_len", str(len(value)))

        return (
            "GPT Browser Bridge: произвольный текст вставлен в ChatGPT.\n"
            f"URL: {page.url}\n"
            f"Символов: {len(value)}"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось вставить произвольный текст.\nОшибка: {e}"


def read_last_assistant_message(limit: int = 8000):
    try:
        _clear_error()
        page = _get_page()
        text = _last_assistant_text(page)
        text = str(text or "")

        if limit:
            text = text[:int(limit)]

        RAW_ANSWER_PATH.write_text(text, encoding="utf-8", errors="replace")
        set_value("last_gpt_browser_action", "read_last_assistant_message")
        set_value("last_gpt_browser_last_assistant_message", text[:4000])
        set_value("last_gpt_browser_last_answer_path", str(RAW_ANSWER_PATH))

        return text

    except Exception as e:
        _remember_error(e)
        return f"STOP: GPT Browser Bridge не смог прочитать последний assistant message.\nОшибка: {e}"


def clarify_task_prompt(text: str, timeout_sec: int = 300):
    from modules.task_clarifier import clarify_dev_task

    return clarify_dev_task(text, timeout_sec=timeout_sec)


def _active_cycle_instruction():
    cycle_id = str(get_value("last_true_auto_cycle_id", "") or "").strip()

    if not cycle_id:
        return ""

    goal_preview = str(get_value("last_true_auto_relay_goal", "") or "").strip()[:500]
    cycle_id_json = json.dumps(cycle_id, ensure_ascii=False)
    goal_preview_json = json.dumps(goal_preview, ensure_ascii=False)

    return f"""
FRESHNESS GUARD ДЛЯ АВТОЦИКЛА:
Это текущий auto-cycle request.
Обязательно добавь в корень JSON поле meta:

"meta": {{
  "cycle_id": {cycle_id_json},
  "goal_preview": {goal_preview_json}
}}

Правила:
- meta.cycle_id должен быть ровно: {cycle_id}
- meta.goal_preview должен кратко отражать текущую задачу.
- Не используй старые cycle_id из предыдущих сообщений.
- Не отдавай старый response_vXXX.json.
- Если создаешь файл, имя может быть response_{cycle_id}.json.
- JSON без правильного meta.cycle_id будет отклонен и patch не применится.
""".strip()

def paste_request():
    try:
        _clear_error()
        page = _get_page()
        saved_chat_url = _saved_chat_url()

        if "chatgpt.com" not in page.url:
            page.goto(_target_chat_url(), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        elif saved_chat_url and not page.url.startswith(saved_chat_url):
            page.goto(saved_chat_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

        request_path = _latest_request_path()

        if not request_path.exists():
            return f"GPT Browser Bridge: request.md не найден: {request_path}"

        original_text = request_path.read_text(encoding="utf-8", errors="replace")
        freshness_instruction = _active_cycle_instruction()
        parts = [original_text.rstrip(), STRICT_JSON_INSTRUCTION]

        if freshness_instruction:
            parts.append(freshness_instruction)

        text = "\n\n".join(parts) + "\n"
        pyperclip.copy(text)

        prompt = _find_prompt_input(page)
        prompt.click(timeout=7000)
        page.keyboard.press("Control+V")
        page.wait_for_timeout(1000)

        set_value("last_gpt_browser_request", str(request_path))
        set_value("last_gpt_browser_action", "paste_request")
        set_value("last_gpt_browser_url", page.url)
        set_value("last_gpt_browser_saved_chat_url", saved_chat_url)
        set_value("last_gpt_browser_strict_instruction", "true")
        set_value("last_gpt_browser_response_mode", "file_response_json_first")
        set_value("last_gpt_browser_active_cycle_id", str(get_value("last_true_auto_cycle_id", "") or ""))

        return (
            "GPT Browser Bridge: request вставлен в ChatGPT.\n"
            f"Файл: {request_path}\n"
            f"URL: {page.url}\n"
            f"saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
            f"Символов исходно: {len(original_text)}\n"
            f"Символов вставлено: {len(text)}\n"
            "Добавлена инструкция: главный результат — скачиваемый файл response.json; fallback — JSON-only текст.\n"
            "Добавлен Response Freshness Guard: meta.cycle_id для текущего автоцикла, если cycle_id активен.\n"
            "Автоскачивание файла пока не выполняется.\n\n"
            "Дальше: gpt browser send"
        )

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось вставить request.\nОшибка: {e}"


def send_prompt():
    try:
        _clear_error()
        page = _get_page()

        selectors = [
            "button[data-testid='send-button']",
            "button[aria-label*='Send']",
            "button[aria-label*='Отправить']",
            "button:has-text('Send')",
            "button:has-text('Отправить')",
        ]

        for selector in selectors:
            try:
                button = page.locator(selector).last
                button.click(timeout=3000)
                set_value("last_gpt_browser_action", "send")
                set_value("last_gpt_browser_send_time_epoch", str(time.time()))
                return "GPT Browser Bridge: запрос отправлен."
            except Exception:
                continue

        page.keyboard.press("Enter")
        set_value("last_gpt_browser_action", "send_enter")
        set_value("last_gpt_browser_send_time_epoch", str(time.time()))
        return "GPT Browser Bridge: запрос отправлен через Enter."

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось отправить запрос.\nОшибка: {e}"


def _main_text(page):
    try:
        return page.locator("main").inner_text(timeout=10000)
    except Exception:
        return page.locator("body").inner_text(timeout=10000)


def wait_response(timeout_sec: int = 600, stable_rounds: int = 5):
    try:
        _clear_error()
        page = _get_page()

        last_text = ""
        stable = 0
        started = time.time()

        while time.time() - started < timeout_sec:
            text = _main_text(page)

            if text == last_text:
                stable += 1
            else:
                stable = 0
                last_text = text

            stop_visible = False

            for selector in [
                "button[aria-label*='Stop']",
                "button[aria-label*='Остановить']",
                "button:has-text('Stop')",
                "button:has-text('Остановить')",
            ]:
                try:
                    if page.locator(selector).last.is_visible(timeout=500):
                        stop_visible = True
                        break
                except Exception:
                    pass

            if stable >= stable_rounds and not stop_visible:
                set_value("last_gpt_browser_action", "wait_done")
                set_value("last_gpt_browser_wait_seconds", str(int(time.time() - started)))
                set_value("last_gpt_browser_wait_timeout", str(timeout_sec))
                return (
                    "GPT Browser Bridge: ответ выглядит завершенным.\n"
                    f"Ожидание: {int(time.time() - started)} сек.\n"
                    f"Лимит: {timeout_sec} сек."
                )

            time.sleep(2)

        raise TimeoutError(f"Ответ не стабилизировался за {timeout_sec} сек.")

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: ожидание ответа завершилось ошибкой.\nОшибка: {e}"


def _last_assistant_text(page):
    selectors = [
        "[data-message-author-role='assistant']",
        "article",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()

            if count:
                text = locator.nth(count - 1).inner_text(timeout=10000)

                if text.strip():
                    return text
        except Exception:
            continue

    return _main_text(page)


def _json_candidates_by_balance(raw: str):
    source = str(raw or "")
    starts = [i for i, ch in enumerate(source) if ch == "{"]

    for start in reversed(starts):
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(source)):
            ch = source[index]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1

                if depth == 0:
                    yield source[start:index + 1]
                    break


def _json_candidates_from_fences(raw: str):
    text = str(raw or "")
    parts = text.split("```")

    for part in reversed(parts):
        clean = part.strip()

        if clean.lower().startswith("json"):
            clean = clean[4:].strip()

        if clean.startswith("{") and clean.endswith("}"):
            yield clean


def _looks_like_patch(data):
    return (
        isinstance(data, dict)
        and "summary" in data
        and "operations" in data
        and "tests" in data
        and isinstance(data.get("operations"), list)
        and isinstance(data.get("tests"), list)
    )


def _try_parse_patch(candidate: str):
    errors = []

    for payload in [candidate, repair_json(candidate)]:
        try:
            data = json.loads(payload)

            if _looks_like_patch(data):
                return data, ""
        except Exception as e:
            errors.append(str(e))

    return None, " | ".join(errors[-3:])


def _extract_json_patch(text: str):
    raw = str(text or "").strip()
    raw = raw.replace("```json", "```").replace("```JSON", "```")

    errors = []
    candidates = []

    candidates.extend(_json_candidates_from_fences(raw))
    candidates.extend(_json_candidates_by_balance(raw))

    # Последняя попытка: весь текст через json_repair.
    candidates.append(raw)

    seen = set()

    for candidate in candidates:
        candidate = str(candidate or "").strip()

        if not candidate or candidate in seen:
            continue

        seen.add(candidate)

        if "summary" not in candidate and "operations" not in candidate:
            continue

        data, error = _try_parse_patch(candidate)

        if data is not None:
            return data

        if error:
            errors.append(error)

    raise ValueError(
        "В ответе не найден валидный JSON patch с summary/operations/tests. "
        + ("Ошибки парсинга: " + " || ".join(errors[-5:]) if errors else "")
    )


def _save_error_report(source: str, error):
    _ensure_dirs()

    lines = [
        "# GPT Browser Response Parse Error",
        "",
        f"- Ошибка: {error}",
        f"- raw_answer: {RAW_ANSWER_PATH}",
        f"- response_raw: {RAW_RESPONSE_PATH}",
        f"- response_json: {RESPONSE_PATH}",
        "",
        "## Что делать",
        "- Выполни: gpt browser repair response",
        "- Если снова ошибка — открой raw файл и проверь, есть ли там JSON.",
        "",
        "## Начало сырого ответа",
        "```text",
        str(source or "")[:5000],
        "```",
    ]

    ERROR_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_gpt_browser_error_report", str(ERROR_REPORT_PATH))
    return ERROR_REPORT_PATH



CONFIRMATION_SUMMARY_MARKERS = [
    "принято",
    "готово",
    "буду делать",
    "буду создавать",
    "буду по возможности",
    "дальше для localcomet",
    "дальше для localagent",
    "создавать скачиваемый файл",
    "не выводить большой json",
    "acknowledged",
    "accepted",
]


def _summary_looks_like_confirmation(summary):
    text = str(summary or "").lower()
    return any(marker in text for marker in CONFIRMATION_SUMMARY_MARKERS)


def _is_empty_confirmation_patch(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("operations"), list)
        and not data.get("operations")
        and _summary_looks_like_confirmation(data.get("summary", ""))
    )


def _write_bad_response(reason, data):
    _ensure_dirs()

    payload = {
        "reason": str(reason),
        "patch": data,
    }

    BAD_RESPONSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_gpt_browser_bad_response", str(BAD_RESPONSE_PATH))
    set_value("last_gpt_browser_bad_response_reason", str(reason))

    return BAD_RESPONSE_PATH


def _schema_errors(data):
    errors = []

    if not isinstance(data, dict):
        return ["patch должен быть JSON object"]

    if not isinstance(data.get("summary"), str):
        errors.append("summary должен быть строкой")

    if not isinstance(data.get("operations"), list):
        errors.append("operations должен быть списком")

    if not isinstance(data.get("tests"), list):
        errors.append("tests должен быть списком")

    if _is_empty_confirmation_patch(data):
        errors.append(
            "operations пустой, а summary похож на подтверждение вместо patch. "
            "Такой response.json считается bad_response."
        )

    for index, operation in enumerate(data.get("operations", []), start=1):
        if not isinstance(operation, dict):
            errors.append(f"операция #{index} не является объектом")
            continue

        op_type = operation.get("type")
        path = operation.get("path")

        if not isinstance(op_type, str) or not op_type:
            errors.append(f"операция #{index}: нет type")

        if not isinstance(path, str) or not path:
            errors.append(f"операция #{index}: нет path")

        if op_type == "replace":
            if "old" not in operation:
                errors.append(f"операция #{index}: replace без old")
            if "new" not in operation:
                errors.append(f"операция #{index}: replace без new")

        if op_type in ["create", "write"]:
            if "content" not in operation:
                errors.append(f"операция #{index}: {op_type} без content")

    return errors


def _load_patch_from_text(text):
    last_error = None

    for payload in [text, repair_json(text)]:
        try:
            data = json.loads(payload)
            errors = _schema_errors(data)

            if not errors:
                return data, []

            last_error = "; ".join(errors)

        except Exception as e:
            last_error = str(e)

    return None, [last_error or "не удалось распарсить JSON"]


def _download_files():
    _ensure_dirs()

    if not DOWNLOADS_DIR.exists():
        return []

    return sorted(
        [path for path in DOWNLOADS_DIR.rglob("*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _download_file_is_fresh(path):
    try:
        send_time = float(get_value("last_gpt_browser_send_time_epoch", "0") or "0")
    except Exception:
        send_time = 0.0

    if send_time <= 0:
        return True

    try:
        return path.stat().st_mtime >= send_time - 5
    except Exception:
        return True


def _import_downloaded_response_data():
    _ensure_dirs()

    files = _download_files()

    if not files:
        raise FileNotFoundError(f"В папке загрузок нет файлов: {DOWNLOADS_DIR}")

    invalid_reports = []

    for path in files[:20]:
        if not _download_file_is_fresh(path):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            invalid_reports.append(f"{path.name}: не удалось прочитать: {e}")
            continue

        data, errors = _load_patch_from_text(text)

        if data is not None:
            return data, path

        invalid_reports.append(f"{path.name}: {'; '.join(errors)}")

    BAD_RESPONSE_PATH.write_text(
        "\\n".join(invalid_reports) if invalid_reports else "Нет свежего валидного response.json",
        encoding="utf-8",
    )

    raise ValueError(
        "Не найден свежий валидный downloaded response.json. "
        f"bad_response: {BAD_RESPONSE_PATH}"
    )


def import_downloaded_response():
    try:
        _clear_error()
        data, source_path = _import_downloaded_response_data()

        set_value("last_gpt_browser_action", "import_downloaded_response")
        set_value("last_gpt_browser_downloaded_response", str(source_path))

        result = _save_patch_data(data)

        return (
            "GPT Browser Bridge: downloaded response импортирован.\\n"
            f"Источник: {source_path}\\n"
            f"Скопировано в: {RESPONSE_PATH}\\n\\n"
            + result
        )

    except Exception as e:
        _remember_error(e)
        return (
            "GPT Browser Bridge: не удалось импортировать downloaded response.\\n"
            f"Ошибка: {e}\\n"
            f"Папка загрузок: {DOWNLOADS_DIR}\\n"
            f"bad_response: {BAD_RESPONSE_PATH if BAD_RESPONSE_PATH.exists() else 'нет'}"
        )


def downloads_status():
    _ensure_dirs()
    files = _download_files()

    lines = [
        "GPT Browser downloads:",
        f"- downloads_dir: {DOWNLOADS_DIR}",
        f"- exists: {DOWNLOADS_DIR.exists()}",
        f"- files: {len(files)}",
    ]

    for path in files[:10]:
        try:
            rel = path.relative_to(DOWNLOADS_DIR)
        except Exception:
            rel = path.name

        lines.append(
            f"- {rel} | {path.stat().st_size} bytes | {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))}"
        )

    return "\\n".join(lines)


def open_downloads():
    _ensure_dirs()

    try:
        if hasattr(os, "startfile"):
            os.startfile(str(DOWNLOADS_DIR))
            return f"GPT Browser Bridge: открыта папка загрузок: {DOWNLOADS_DIR}"

        return f"GPT Browser Bridge downloads folder: {DOWNLOADS_DIR}"

    except Exception as e:
        _remember_error(e)
        return f"GPT Browser Bridge: не удалось открыть папку загрузок.\\nОшибка: {e}"


def _save_patch_data(data):
    errors = _schema_errors(data)

    if errors:
        bad_path = _write_bad_response("; ".join(errors), data)
        raise ValueError(
            "JSON patch не прошел schema guard: "
            + "; ".join(errors)
            + f" | bad_response: {bad_path}"
        )

    RESPONSE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_value("last_gpt_browser_response", str(RESPONSE_PATH))
    set_value("last_relay_response", str(RESPONSE_PATH))

    return (
        "GPT Browser Bridge: response.json сохранен.\n"
        f"Файл: {RESPONSE_PATH}\n"
        f"Summary: {data.get('summary', 'нет')}\n"
        f"Операций: {len(data.get('operations', []))}\n\n"
        "Дальше: relay проверь ответ"
    )


def save_response():
    try:
        _clear_error()

        try:
            data, source_path = _import_downloaded_response_data()
            set_value("last_gpt_browser_action", "save_response_from_download")
            set_value("last_gpt_browser_downloaded_response", str(source_path))

            result = _save_patch_data(data)

            return (
                "GPT Browser Bridge: response.json сохранен из скачанного файла.\n"
                f"Источник: {source_path}\n\n"
                + result
            )
        except Exception as download_error:
            set_value("last_gpt_browser_download_import_error", str(download_error))

        page = _get_page()

        answer_text = _last_assistant_text(page)
        RAW_ANSWER_PATH.write_text(answer_text, encoding="utf-8")
        RAW_RESPONSE_PATH.write_text(answer_text, encoding="utf-8")

        data = _extract_json_patch(answer_text)

        set_value("last_gpt_browser_action", "save_response")
        set_value("last_gpt_browser_raw_answer", str(RAW_ANSWER_PATH))

        return _save_patch_data(data)

    except Exception as e:
        _remember_error(e)

        source = ""

        try:
            if RAW_ANSWER_PATH.exists():
                source = RAW_ANSWER_PATH.read_text(encoding="utf-8", errors="replace")
        except Exception:
            source = ""

        report = _save_error_report(source, e)

        return (
            "GPT Browser Bridge: не удалось сохранить response.json.\n"
            f"Ошибка: {e}\n"
            f"Сырой ответ сохранен: {RAW_ANSWER_PATH if RAW_ANSWER_PATH.exists() else 'нет'}\n"
            f"Error report: {report}\n\n"
            "Попробуй: gpt browser repair response"
        )


def repair_response():
    try:
        _clear_error()
        _ensure_dirs()

        sources = [
            RAW_ANSWER_PATH,
            RAW_RESPONSE_PATH,
        ]

        last_error = None

        for path in sources:
            if not path.exists() or not path.is_file():
                continue

            text = path.read_text(encoding="utf-8", errors="replace")

            try:
                data = _extract_json_patch(text)
                set_value("last_gpt_browser_action", "repair_response")
                set_value("last_gpt_browser_raw_answer", str(path))
                return (
                    "GPT Browser Bridge: response.json восстановлен из сырого ответа.\n"
                    f"Источник: {path}\n"
                    + _save_patch_data(data)
                )
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error

        raise FileNotFoundError(
            f"Не найден сырой ответ: {RAW_ANSWER_PATH} или {RAW_RESPONSE_PATH}"
        )

    except Exception as e:
        _remember_error(e)
        report = _save_error_report("", e)

        return (
            "GPT Browser Bridge: repair response не смог восстановить JSON.\n"
            f"Ошибка: {e}\n"
            f"Error report: {report}"
        )


def status():
    page_url = "нет"
    page_state = "нет"
    saved_chat_url = _saved_chat_url()

    try:
        if _page is not None and not _page.is_closed():
            page_url = _page.url
            page_state = "открыта"
        else:
            page_state = "закрыта"
    except Exception as e:
        page_state = f"ошибка: {e}"

    return (
        "GPT Browser Bridge status:\n"
        f"- profile: {PROFILE_DIR}\n"
        f"- engine: {get_value('last_gpt_browser_engine', 'нет')}\n"
        f"- downloads_dir: {DOWNLOADS_DIR}\n"
        f"- downloads_exists: {DOWNLOADS_DIR.exists()}\n"
        f"- saved_chat_url: {saved_chat_url if saved_chat_url else 'нет'}\n"
        f"- request: {_latest_request_path()}\n"
        f"- response: {RESPONSE_PATH}\n"
        f"- response_exists: {RESPONSE_PATH.exists()}\n"
        f"- raw_answer: {RAW_ANSWER_PATH}\n"
        f"- error_report: {ERROR_REPORT_PATH}\n"
        f"- page: {page_state}\n"
        f"- url: {page_url}\n"
        f"- default_wait_timeout: 600\n"
        f"- response_mode: {get_value('last_gpt_browser_response_mode', 'file_response_json_first')}\n"
        f"- auto_download_response_json: fixed_downloads_import\n"
        f"- last_download_import_error: {get_value('last_gpt_browser_download_import_error', 'нет')}\n"
        f"- last_action: {get_value('last_gpt_browser_action', 'нет')}\n"
        f"- last_error: {get_value('last_gpt_browser_error', 'нет')}"
    )


def download_latest_response_artifact(timeout_sec: int = 900):
    from modules.true_auto_relay import download_latest_response_artifact as _download

    return _download(timeout_sec=timeout_sec)


def true_auto_relay_cycle(goal: str = "", timeout_sec: int = 900):
    from modules.true_auto_relay import true_auto_relay_cycle as _cycle

    return _cycle(goal=goal, timeout_sec=timeout_sec)


def full_cycle(timeout_sec: int = 600):
    from agents import chatgpt_relay_agent

    parts = [
        "--- OPEN ---",
        open_chatgpt(),
        "",
        "--- PASTE REQUEST ---",
        paste_request(),
        "",
        "--- SEND ---",
        send_prompt(),
        "",
        "--- WAIT ---",
        wait_response(timeout_sec=timeout_sec),
        "",
        "--- SAVE RESPONSE ---",
        save_response(),
        "",
        "--- RELAY VALIDATE ---",
        chatgpt_relay_agent.handle("validate_response", {}),
    ]

    return "\n".join(str(part) for part in parts)


def full_apply(timeout_sec: int = 600):
    from agents import chatgpt_relay_agent
    from agents import automation_agent

    cycle_result = full_cycle(timeout_sec=timeout_sec)
    validate_result = chatgpt_relay_agent.handle("validate_response", {})

    parts = [
        "--- FULL CYCLE ---",
        cycle_result,
        "",
        "--- VALIDATE AGAIN ---",
        validate_result,
    ]

    if "✅" not in str(validate_result) and "проверка пройдена" not in str(validate_result).lower():
        parts.extend([
            "",
            "FULL APPLY остановлен: relay validate не прошел.",
        ])
        return "\n".join(parts)

    close_result = close_bridge()
    apply_result = chatgpt_relay_agent.handle("apply_response", {})
    after_result = automation_agent.handle("after_patch", {})

    parts.extend([
        "",
        "--- GPT BROWSER CLOSE ---",
        close_result,
        "",
        "--- RELAY APPLY ---",
        apply_result,
        "",
        "--- AFTER PATCH ---",
        after_result,
    ])

    return "\n".join(str(part) for part in parts)
````

### ПУТЬ: modules/gpt_client.py (134 строк, 3609 байт)

````python
import os
import json
import requests

from config import OPENAI_MODEL, OPENAI_RESPONSES_API


def _get_api_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()

    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY не найден.\n"
            "Проверь, что ты выполнил:\n"
            'setx OPENAI_API_KEY "твой_ключ"\n'
            "После setx нужно полностью закрыть PowerShell и открыть заново."
        )

    return key


def _extract_output_text(data: dict):
    if not isinstance(data, dict):
        return str(data)

    direct = data.get("output_text")

    if direct:
        return str(direct)

    output = data.get("output", [])

    parts = []

    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content", [])

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    block_type = block.get("type")

                    if block_type in ["output_text", "text"]:
                        text = block.get("text", "")

                        if text:
                            parts.append(str(text))

            text = item.get("text")

            if text:
                parts.append(str(text))

    if parts:
        return "\n".join(parts)

    return json.dumps(data, ensure_ascii=False, indent=2)


def ask_gpt(
    prompt: str,
    system: str = None,
    model: str = None,
    max_output_tokens: int = 3000,
):
    prompt = str(prompt or "").strip()

    if not prompt:
        return "GPT: пустой prompt."

    api_key = _get_api_key()
    selected_model = model or OPENAI_MODEL

    instructions = system or (
        "Ты GPT-мозг для локального Python-агента LocalComet. "
        "Отвечай по-русски, практично, без воды. "
        "Если речь про код — давай точные действия и безопасные решения."
    )

    payload = {
        "model": selected_model,
        "instructions": instructions,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }

    headers = {
        "Authorization": f"Bearer [REDACTED: secret in modules/gpt_client.py:94]",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_API,
            headers=headers,
            json=payload,
            timeout=300,
        )

        if response.status_code >= 400:
            return (
                "GPT API ошибка.\n"
                f"HTTP: {response.status_code}\n"
                f"Ответ: {response.text[:3000]}"
            )

        data = response.json()
        return _extract_output_text(data)

    except Exception as e:
        return f"GPT request error: {e}"


def gpt_status():
    key = os.getenv("OPENAI_API_KEY", "").strip()

    if key:
        safe_key = key[:10] + "..." + key[-4:] if len(key) > 18 else "ключ найден"
        key_status = f"✅ OPENAI_API_KEY найден: {safe_key}"
    else:
        key_status = "❌ OPENAI_API_KEY не найден"

    return (
        "GPT Bridge status:\n"
        f"- {key_status}\n"
        f"- OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"- API: {OPENAI_RESPONSES_API}"
    )
````

### ПУТЬ: modules/green_gate_status_ru.py (151 строк, 5664 байт)

````python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict


GREEN_GATE_STATUS_VERSION = "v6.58"
GREEN_GATE_STATUS_NAME = "LocalComet Green Gate Status RU"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "AGENTS.md").exists() or (candidate / "LocalComet_Control_Panel.py").exists():
            return candidate
    return get_project_root()


def _reports_dir() -> Path:
    path = _root() / "Projects" / "Reports" / "green_gate_status"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"ok": False, "mode": "unexpected_result", "value": str(value)[:2000]}


def _run_strict() -> Dict[str, Any]:
    try:
        from modules.strict_project_stability_ru import dispatch
        return _safe_payload(dispatch("проверь проект"))
    except Exception as exc:
        return {"ok": False, "mode": "strict_project_stability_error", "error": str(exc)}


def _latest_report(folder: str, pattern: str = "*.json") -> str:
    base = _root() / "Projects" / "Reports" / folder
    if not base.exists():
        return ""
    items = [p for p in base.glob(pattern) if p.is_file()]
    if not items:
        return ""
    try:
        return str(max(items, key=lambda p: p.stat().st_mtime))
    except Exception:
        return str(items[-1])


def get_green_gate_status(write_report: bool = True) -> Dict[str, Any]:
    strict = _run_strict()
    summary = strict.get("summary", {}) if isinstance(strict, dict) else {}
    hard_failures = int(summary.get("hard_failures", 999) or 0)
    warnings = int(summary.get("warnings", 999) or 0)
    clean_green = bool(strict.get("ok")) and hard_failures == 0 and warnings == 0
    payload: Dict[str, Any] = {
        "ok": clean_green,
        "mode": "green_gate_status",
        "version": GREEN_GATE_STATUS_VERSION,
        "generated_at": _now(),
        "clean_green": clean_green,
        "strict": {
            "ok": bool(strict.get("ok")),
            "score": strict.get("score", ""),
            "summary": summary,
            "report": strict.get("report", ""),
        },
        "latest_reports": {
            "functional": _latest_report("localcomet_functional_tests"),
            "contracts": _latest_report("computer_use_contracts"),
            "patch_ux": str(_root() / "Projects" / "Reports" / "patch_panel_ux" / "latest_patch_panel_ux_report.md"),
            "first_failure": str(_root() / "Projects" / "Reports" / "developer_velocity" / "latest_first_failure.md"),
        },
        "recommendation": "READY_FOR_NEXT_PATCH" if clean_green else "REPAIR_BEFORE_NEXT_PATCH",
        "report": "",
        "json": "",
    }
    if write_report:
        paths = _write_reports(payload)
        payload["report"] = str(paths["md"])
        payload["json"] = str(paths["json"])
    return payload


def _write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    out = _reports_dir()
    json_path = out / f"green_gate_status_{_stamp()}.json"
    md_path = out / f"green_gate_status_{_stamp()}.md"
    latest_json = out / "latest_green_gate_status.json"
    latest_md = out / "latest_green_gate_status.md"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    json_path.write_text(text, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    strict_summary = payload.get("strict", {}).get("summary", {})
    lines = [
        "# LocalComet Green Gate Status",
        "",
        f"- version: {payload.get('version')}",
        f"- clean_green: {payload.get('clean_green')}",
        f"- recommendation: {payload.get('recommendation')}",
        f"- hard_failures: {strict_summary.get('hard_failures')}",
        f"- warnings: {strict_summary.get('warnings')}",
        f"- score: {payload.get('strict', {}).get('score')}",
        "",
        "## Latest reports",
        "",
    ]
    for key, value in payload.get("latest_reports", {}).items():
        lines.append(f"- {key}: {value}")
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def status(command: str = "status") -> Dict[str, Any]:
    return get_green_gate_status(write_report=True)


def report(command: str = "report") -> Dict[str, Any]:
    return get_green_gate_status(write_report=True)


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = str(command or "").strip().lower().replace("ё", "е")
    if lower in {"статус разработки", "green gate", "green gate status", "dev status", "статус проекта"}:
        payload = get_green_gate_status(write_report=True)
        payload["handled"] = True
        return payload
    if lower in {"status", "статус"}:
        payload = status(command)
        payload["handled"] = True
        return payload
    if lower in {"report", "отчет"}:
        payload = report(command)
        payload["handled"] = True
        return payload
    return {"ok": False, "handled": False, "mode": "green_gate_status", "reason": "unknown command"}
````

### ПУТЬ: modules/history_log.py (168 строк, 4185 байт)

````python
import json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
LOGS_DIR = PROJECTS_DIR / "Logs"
ACTIONS_LOG = LOGS_DIR / "actions.jsonl"


def _ensure_logs_dir():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _short(value, limit: int = 1200):
    text = str(value or "")

    if len(text) > limit:
        return text[:limit] + "... [обрезано]"

    return text


def append_log(user_text: str, plan=None, result=None, status: str = "ok", error=None):
    _ensure_logs_dir()

    tool = None
    action = None

    if isinstance(plan, dict):
        tool = plan.get("tool")
        action = plan.get("action")

        if "actions" in plan:
            tool = "multi"
            action = "actions"

    elif isinstance(plan, list):
        tool = "multi"
        action = "list"

    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "user_text": str(user_text or ""),
        "tool": tool,
        "action": action,
        "status": status,
        "plan": plan,
        "result": _short(result),
        "error": _short(error),
    }

    with ACTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def _read_records():
    _ensure_logs_dir()

    if not ACTIONS_LOG.exists():
        return []

    records = []

    for line in ACTIONS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            records.append(json.loads(line))
        except Exception:
            records.append({
                "time": "unknown",
                "user_text": "bad log line",
                "tool": "unknown",
                "action": "unknown",
                "status": "error",
                "result": line,
                "error": "Не удалось разобрать строку JSONL",
            })

    return records


def show_history(limit: int = 20):
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    recent = records[-limit:]
    lines = [f"Последние действия ({len(recent)}):"]

    for i, item in enumerate(recent, start=1):
        time = item.get("time", "unknown")
        user_text = item.get("user_text", "")
        tool = item.get("tool", "unknown")
        action = item.get("action", "unknown")
        status = item.get("status", "unknown")

        lines.append(
            f"{i}. [{time}] {status} | {tool}.{action} | {user_text}"
        )

    return "\n".join(lines)


def show_last_log():
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    item = records[-1]

    return (
        "Последняя запись истории:\n"
        + json.dumps(item, ensure_ascii=False, indent=2)
    )


def show_history_stats():
    records = _read_records()

    if not records:
        return "История действий пока пустая."

    total = len(records)
    errors = len([r for r in records if r.get("status") == "error"])

    by_tool = {}

    for item in records:
        tool = item.get("tool") or "unknown"
        by_tool[tool] = by_tool.get(tool, 0) + 1

    lines = [
        "Статистика истории:",
        f"- Всего записей: {total}",
        f"- Ошибок: {errors}",
        "",
        "По инструментам:",
    ]

    for tool, count in sorted(by_tool.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {tool}: {count}")

    return "\n".join(lines)


def clear_history():
    _ensure_logs_dir()

    if ACTIONS_LOG.exists():
        ACTIONS_LOG.unlink()

    return f"История очищена: {ACTIONS_LOG}"


def get_log_path():
    _ensure_logs_dir()
    return str(ACTIONS_LOG)
````

### ПУТЬ: modules/knowledge_adapter_ru.py (859 строк, 38491 байт)

````python
"""Read-only, deterministic, in-memory LocalComet KnowledgeAdapter prototype."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import unicodedata
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping

from modules.knowledge_contract_ru import (
    AdapterState,
    HARD_MAX_CONTEXT_CHARS,
    HARD_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeConfig,
    KnowledgeErrorCode,
    KnowledgeNote,
    MatchedSection,
    MAX_EXCERPT_CHARS,
    MAX_MATCHED_SECTIONS,
    MAX_QUERY_CHARS,
    NoteHeading,
    QueryIntent,
)
from tools import validate_localcomet_vault as vault_validator


sys.dont_write_bytecode = True

DiagnosticLogger = Callable[[str, Mapping[str, Any]], None]
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class _KnowledgeIndex:
    notes: tuple[KnowledgeNote, ...]
    by_id: Mapping[str, KnowledgeNote]
    vault_revision: str
    canonical_scope_count: int
    validation_status: str
    validation_error_count: int
    validation_warning_count: int


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize(value: str) -> str:
    return " ".join(_nfc(value).casefold().split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(_normalize(value)))


def _list_of_strings(metadata: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = metadata.get(name, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise KnowledgeAdapterError(
            KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID,
            f"Validated note has an invalid {name} field.",
        )
    return tuple(value)


def _safe_error_from_validation(result: Any) -> KnowledgeAdapterError:
    codes = {item.get("code") for item in result.errors}
    if "NOTE_SIZE_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_NOTE_TOO_LARGE
    elif "TOTAL_SCAN_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_VAULT_TOO_LARGE
    elif "NOTE_COUNT_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_TOO_MANY_NOTES
    elif "FRONTMATTER_ERROR" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID
    elif codes & {"DUPLICATE_STABLE_ID", "NORMALIZED_DUPLICATE_ID"}:
        code = KnowledgeErrorCode.KNOWLEDGE_DUPLICATE_ID
    elif "CANONICAL_SCOPE_CONFLICT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_CANONICAL_CONFLICT
    elif codes & {"REPARSE_POINT", "NON_REGULAR_FILE"}:
        code = KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT
    elif "PATH_ESCAPE" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE
    else:
        code = KnowledgeErrorCode.KNOWLEDGE_VALIDATION_FAILED
    return KnowledgeAdapterError(
        code,
        "Knowledge Vault validation failed.",
        details={"validation_error_count": result.error_count},
    )


def _runtime_error(error: BaseException) -> KnowledgeAdapterError:
    message = str(error).casefold()
    if "reparse" in message or "symlink" in message or "junction" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT
        safe_message = "Knowledge Vault contains an unsafe reparse boundary."
    elif "outside" in message or "escape" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE
        safe_message = "Knowledge Vault path boundary is unsafe."
    elif "does not exist" in message or "not a directory" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_VAULT_NOT_FOUND
        safe_message = "Configured Knowledge Vault was not found."
    else:
        code = KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR
        safe_message = "Knowledge Vault could not be read safely."
    return KnowledgeAdapterError(code, safe_message)


class KnowledgeAdapter:
    """Validated, read-only knowledge retrieval with process-memory state only."""

    def __init__(
        self,
        config: KnowledgeConfig | None,
        *,
        diagnostic_logger: DiagnosticLogger | None = None,
    ) -> None:
        self._config = config
        self._logger = diagnostic_logger
        self._index: _KnowledgeIndex | None = None
        self._last_validation: dict[str, Any] | None = None
        self._state = AdapterState.NOT_CONFIGURED if config is None else AdapterState.NOT_CONFIGURED
        self._last_error_code: str | None = None
        self._lock = threading.RLock()

    def _log(self, event: str, **fields: Any) -> None:
        if self._logger is not None:
            bounded = {key: value for key, value in fields.items() if key != "query"}
            self._logger(event, MappingProxyType(bounded))

    def _require_config(self) -> KnowledgeConfig:
        if self._config is None:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                "KnowledgeAdapter is not configured.",
            )
        return self._config

    def _require_index(self) -> _KnowledgeIndex:
        if self._index is None:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                "Knowledge index is not initialized.",
            )
        return self._index

    def status(self) -> dict[str, Any]:
        with self._lock:
            index = self._index
            observed = self._last_validation or {}
            return {
                "state": self._state.value,
                "vault_revision": index.vault_revision if index else observed.get("vault_revision"),
                "note_count": len(index.notes) if index else observed.get("note_count", 0),
                "indexed_note_count": len(index.notes) if index else 0,
                "canonical_scope_count": (
                    index.canonical_scope_count
                    if index
                    else observed.get("canonical_scope_count", 0)
                ),
                "validation_status": (
                    index.validation_status if index else observed.get("status")
                ),
                "validation_error_count": (
                    index.validation_error_count
                    if index
                    else observed.get("error_count", 0)
                ),
                "validation_warning_count": (
                    index.validation_warning_count
                    if index
                    else observed.get("warning_count", 0)
                ),
                "read_only": True,
                "last_refresh_revision": index.vault_revision if index else None,
                "observed_vault_revision": observed.get("vault_revision"),
                "last_validation_status": observed.get("status"),
                "last_validation_error_count": observed.get("error_count", 0),
                "last_validation_warning_count": observed.get("warning_count", 0),
                "last_error_code": self._last_error_code,
            }

    def initialize(self) -> dict[str, Any]:
        return self.refresh()

    def refresh(self) -> dict[str, Any]:
        config = self._require_config()
        with self._lock:
            previous = self._index
            previous_state = self._state
            previous_revision = previous.vault_revision if previous else None
            self._state = AdapterState.SCANNING
            self._last_error_code = None
            started = time.monotonic()
            self._log("scan_started")
            try:
                candidate = self._build_index(config)
            except KnowledgeAdapterError as exc:
                self._last_error_code = exc.code.value
                if previous is not None:
                    self._index = previous
                    self._state = previous_state
                    self._log("scan_failed", error_code=exc.code.value)
                    raise KnowledgeAdapterError(
                        KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                        "Knowledge refresh failed; the previous validated index remains active.",
                        details={
                            "cause_code": exc.code.value,
                            "previous_revision": previous_revision,
                        },
                    ) from exc
                self._state = AdapterState.ERROR
                self._log("scan_failed", error_code=exc.code.value)
                raise
            except Exception as exc:
                mapped = _runtime_error(exc)
                self._last_error_code = mapped.code.value
                if previous is not None:
                    self._index = previous
                    self._state = previous_state
                    self._log("scan_failed", error_code=mapped.code.value)
                    raise KnowledgeAdapterError(
                        KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                        "Knowledge refresh failed; the previous validated index remains active.",
                        details={
                            "cause_code": mapped.code.value,
                            "previous_revision": previous_revision,
                        },
                    ) from exc
                self._state = AdapterState.ERROR
                self._log("scan_failed", error_code=mapped.code.value)
                raise mapped from exc
            self._index = candidate
            self._state = (
                AdapterState.DEGRADED
                if candidate.validation_warning_count
                else AdapterState.READY
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log(
                "scan_completed",
                note_count=len(candidate.notes),
                duration_ms=duration_ms,
                vault_revision=candidate.vault_revision,
            )
            return {
                "state": self._state.value,
                "previous_revision": previous_revision,
                "current_revision": candidate.vault_revision,
                "note_count": len(candidate.notes),
                "changed": previous_revision != candidate.vault_revision,
                "validation_warning_count": candidate.validation_warning_count,
            }

    def _build_index(self, config: KnowledgeConfig) -> _KnowledgeIndex:
        try:
            validation = vault_validator.validate_vault(
                config.vault_root,
                config.project_root,
                max_notes=config.max_notes,
                max_note_bytes=config.max_note_bytes,
                max_total_scan_bytes=config.max_total_scan_bytes,
            )
        except vault_validator.ValidatorRuntimeError as exc:
            raise _runtime_error(exc) from exc
        self._last_validation = {
            "status": validation.status,
            "vault_revision": validation.vault_revision,
            "note_count": validation.markdown_note_count,
            "canonical_scope_count": validation.canonical_scope_count,
            "error_count": validation.error_count,
            "warning_count": validation.warning_count,
        }
        if validation.status == "FAIL" or validation.error_count:
            raise _safe_error_from_validation(validation)
        try:
            vault_root = vault_validator._safe_root(config.vault_root, "Vault root")
            discovered, _obsidian_count, discovery_issues, _unexpected, _forbidden = (
                vault_validator._discover_files(vault_root)
            )
        except vault_validator.ValidatorRuntimeError as exc:
            raise _runtime_error(exc) from exc
        if any(issue.severity == "error" for issue in discovery_issues):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge Vault discovery crossed an unsafe boundary.",
            )
        if len(discovered) != validation.markdown_note_count:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Knowledge Vault changed during index construction.",
            )
        notes: list[KnowledgeNote] = []
        for path, info in discovered:
            notes.append(self._read_note(path, info, vault_root, config))
        notes.sort(key=lambda note: (_nfc(note.note_id), _nfc(note.relative_path)))
        by_id = {note.note_id: note for note in notes}
        if len(by_id) != len(notes):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_DUPLICATE_ID,
                "Knowledge Vault contains duplicate stable IDs.",
            )
        return _KnowledgeIndex(
            notes=tuple(notes),
            by_id=MappingProxyType(by_id),
            vault_revision=validation.vault_revision,
            canonical_scope_count=validation.canonical_scope_count,
            validation_status=validation.status,
            validation_error_count=validation.error_count,
            validation_warning_count=validation.warning_count,
        )

    def _read_note(
        self,
        path: Path,
        info: os.stat_result,
        vault_root: Path,
        config: KnowledgeConfig,
    ) -> KnowledgeNote:
        relative = path.relative_to(vault_root).as_posix()
        if path.suffix.casefold() != ".md" or not stat.S_ISREG(info.st_mode):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge index encountered an invalid note entry.",
            )
        if info.st_size > config.max_note_bytes:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOTE_TOO_LARGE,
                "Knowledge note exceeds the configured size limit.",
            )
        resolved = path.resolve(strict=True)
        if not vault_validator._is_path_within(resolved, vault_root):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge note resolves outside the configured Vault.",
            )
        if vault_validator.is_reparse_point(path):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT,
                "Knowledge note crosses an unsafe reparse boundary.",
            )
        raw = path.read_bytes()
        if len(raw) != info.st_size:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Knowledge note changed during index construction.",
            )
        try:
            text = raw.decode("utf-8")
            metadata, body_lines = vault_validator.parse_frontmatter(text)
        except (UnicodeDecodeError, vault_validator.FrontmatterError) as exc:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID,
                "Knowledge note frontmatter is invalid.",
            ) from exc
        text_lines = tuple(text.splitlines())
        headings = self._headings(body_lines, len(text_lines))
        configured_title = metadata.get("title")
        title = configured_title if isinstance(configured_title, str) and configured_title else ""
        if not title:
            title = next((heading.title for heading in headings if heading.level == 1), path.stem)
        body_start_line = body_lines[0][0] if body_lines else len(text_lines) + 1
        body_text = "\n".join(line for _line_number, line in body_lines)
        return KnowledgeNote(
            note_id=str(metadata["id"]),
            title=title,
            relative_path=relative,
            type=str(metadata["type"]),
            status=str(metadata["status"]),
            knowledge_layer=str(metadata["knowledge_layer"]),
            evidence_class=str(metadata["evidence_class"]),
            authority=str(metadata["authority"]),
            canonical=metadata.get("canonical", False) is True,
            canonical_scope=(
                str(metadata["canonical_scope"])
                if isinstance(metadata.get("canonical_scope"), str)
                else None
            ),
            aliases=_list_of_strings(metadata, "aliases"),
            releases=_list_of_strings(metadata, "releases"),
            source_paths=_list_of_strings(metadata, "source_paths"),
            evidence_refs=_list_of_strings(metadata, "evidence_refs"),
            supersedes=_list_of_strings(metadata, "supersedes"),
            superseded_by=_list_of_strings(metadata, "superseded_by"),
            updated=str(metadata["updated"]),
            last_reviewed=str(metadata["last_reviewed"]),
            verified_at=(
                str(metadata["verified_at"])
                if isinstance(metadata.get("verified_at"), str)
                else None
            ),
            headings=headings,
            body_text=body_text,
            text_lines=text_lines,
            body_start_line=body_start_line,
            note_sha256=hashlib.sha256(raw).hexdigest(),
            file_size=len(raw),
        )

    @staticmethod
    def _headings(
        body_lines: list[tuple[int, str]],
        total_lines: int,
    ) -> tuple[NoteHeading, ...]:
        raw_headings: list[tuple[str, int, int]] = []
        for line_number, line in vault_validator._outside_fences(body_lines):
            match = HEADING_RE.match(line)
            if match:
                title = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
                raw_headings.append((title, len(match.group(1)), line_number))
        headings = []
        for index, (title, level, line_start) in enumerate(raw_headings):
            line_end = raw_headings[index + 1][2] - 1 if index + 1 < len(raw_headings) else total_lines
            headings.append(NoteHeading(title, level, line_start, max(line_start, line_end)))
        return tuple(headings)

    @staticmethod
    def resolve_intent(query: str, intent: QueryIntent | str) -> QueryIntent:
        try:
            requested = intent if isinstance(intent, QueryIntent) else QueryIntent(str(intent).upper())
        except ValueError as exc:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Unknown knowledge query intent.",
            ) from exc
        if requested is not QueryIntent.AUTO:
            return requested
        normalized = _normalize(query)
        hints: tuple[tuple[QueryIntent, tuple[str, ...]], ...] = (
            (QueryIntent.CURRENT_STATE, ("current", "сейчас", "текущ", "работает")),
            (QueryIntent.ARCHITECTURE, ("architecture", "архитектур", "почему устроено")),
            (QueryIntent.SECURITY, ("security", "безопасност")),
            (QueryIntent.HISTORY, ("history", "истори", "релиз", "раньше")),
            (QueryIntent.FOUNDER_INTENT, ("vision", "цель", "видение", "founder intent")),
            (QueryIntent.ROADMAP, ("roadmap", "план", "дальше", "будет")),
            (QueryIntent.RESEARCH, ("research", "исследован")),
            (QueryIntent.INCIDENT, ("incident", "ошибк", "инцидент", "сломалось")),
            (QueryIntent.OPERATIONAL, ("runbook", "инструкц", "диагностик", "запуск")),
        )
        matches = [resolved for resolved, words in hints if any(word in normalized for word in words)]
        return matches[0] if len(matches) == 1 else QueryIntent.AUTO

    def _validated_query(self, query: Any) -> tuple[str, str, tuple[str, ...]]:
        if not isinstance(query, str) or not _normalize(query):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_QUERY_EMPTY,
                "Knowledge query must be a non-empty string.",
            )
        if len(query) > MAX_QUERY_CHARS:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_QUERY_TOO_LARGE,
                "Knowledge query exceeds the hard character limit.",
            )
        normalized = _normalize(query)
        return query, normalized, _tokens(normalized)

    def _result_limit(self, value: Any) -> int:
        config = self._require_config()
        limit = config.default_max_results if value is None else value
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= config.hard_max_results:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_RESULT_LIMIT,
                "max_results is outside the configured bounds.",
            )
        return limit

    @staticmethod
    def _lexical_score(note: KnowledgeNote, normalized: str, query_tokens: tuple[str, ...]) -> int:
        score = 0
        if normalized == _normalize(note.note_id):
            score += 100_000
        if normalized == _normalize(note.title):
            score += 80_000
        if any(normalized == _normalize(alias) for alias in note.aliases):
            score += 70_000
        title_tokens = set(_tokens(note.title))
        heading_tokens = set(_tokens(" ".join(heading.title for heading in note.headings)))
        body_tokens = set(_tokens(note.body_text))
        query_set = set(query_tokens)
        score += len(query_set & title_tokens) * 1_000
        score += len(query_set & heading_tokens) * 500
        score += len(query_set & body_tokens) * 20
        return score

    @staticmethod
    def _intent_boost(note: KnowledgeNote, intent: QueryIntent) -> int:
        boost = 0
        if intent is QueryIntent.CURRENT_STATE:
            boost += 8_000 if note.note_id == "canonical.current-state" else 0
            boost += 6_000 if note.note_id == "canonical.version-matrix" else 0
            boost += 2_500 if note.knowledge_layer == "current_source_truth" else 0
            boost += 700 if note.evidence_class == "A" else 0
            boost += 500 if note.status == "current" else 0
            boost -= 1_500 if note.knowledge_layer in {"research", "roadmap", "session_snapshot"} else 0
            boost -= 1_000 if note.type == "release" or note.status == "historical" else 0
        elif intent is QueryIntent.FOUNDER_INTENT:
            boost += 8_000 if note.note_id == "vision.product" else 0
            boost += 3_000 if note.knowledge_layer == "founder_intent" else 0
            boost += 700 if note.authority == "founder" else 0
        elif intent is QueryIntent.ROADMAP:
            boost += 8_000 if note.note_id == "roadmap.localcomet" else 0
            boost += 3_000 if note.knowledge_layer == "roadmap" else 0
            boost += 600 if note.knowledge_layer == "founder_intent" else 0
        elif intent is QueryIntent.HISTORY:
            boost += 3_000 if note.type in {"release", "incident"} else 0
            boost += 2_000 if note.knowledge_layer == "verified_history" else 0
            boost += 800 if note.knowledge_layer == "forensic_evidence" else 0
        elif intent is QueryIntent.SECURITY:
            boost += 8_000 if note.canonical_scope == "security" else 0
            boost += 3_000 if note.type == "security" else 0
            boost += 1_500 if note.type == "adr" and "security" in _normalize(note.body_text) else 0
            boost += 800 if note.knowledge_layer == "current_source_truth" else 0
        elif intent is QueryIntent.ARCHITECTURE:
            boost += 8_000 if note.note_id == "canonical.system-architecture" else 0
            boost += 3_000 if note.type == "architecture" else 0
            boost += 2_000 if note.type == "adr" else 0
            boost += 800 if note.knowledge_layer == "current_source_truth" else 0
        elif intent is QueryIntent.OPERATIONAL:
            boost += 4_000 if note.type == "runbook" else 0
            boost += 2_000 if note.knowledge_layer == "operational" else 0
        elif intent is QueryIntent.INCIDENT:
            boost += 8_000 if note.note_id == "incident.index" else 0
            boost += 3_500 if note.type == "incident" else 0
            boost += 1_500 if note.knowledge_layer == "verified_history" else 0
        elif intent is QueryIntent.RESEARCH:
            boost += 4_000 if note.type == "research" else 0
            boost += 2_500 if note.knowledge_layer == "research" else 0
        return boost

    def search(
        self,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_results: int | None = None,
        include_superseded: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            original, normalized, query_tokens = self._validated_query(query)
            resolved = self.resolve_intent(original, intent)
            limit = self._result_limit(max_results)
            if not isinstance(include_superseded, bool):
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                    "include_superseded must be boolean.",
                )
            ranked: list[tuple[int, KnowledgeNote]] = []
            for note in index.notes:
                if note.status == "superseded" and not include_superseded:
                    continue
                if resolved is QueryIntent.CURRENT_STATE and note.evidence_class in {"D", "E", "G"}:
                    continue
                lexical = self._lexical_score(note, normalized, query_tokens)
                if lexical <= 0:
                    continue
                ranked.append((lexical + self._intent_boost(note, resolved), note))
            ranked.sort(key=lambda item: (-item[0], _nfc(item[1].note_id), _nfc(item[1].relative_path)))
            results = [
                self._search_result(note, score, query_tokens)
                for score, note in ranked[:limit]
            ]
            self._log("search_completed", resolved_intent=resolved.value, result_count=len(results))
            return {
                "query": original,
                "resolved_intent": resolved.value,
                "vault_revision": index.vault_revision,
                "result_count": len(results),
                "results": results,
            }

    def _search_result(
        self,
        note: KnowledgeNote,
        score: int,
        query_tokens: tuple[str, ...],
    ) -> dict[str, Any]:
        result = {
            "note_id": note.note_id,
            "title": note.title,
            "relative_path": note.relative_path,
            "type": note.type,
            "status": note.status,
            "knowledge_layer": note.knowledge_layer,
            "evidence_class": note.evidence_class,
            "authority": note.authority,
            "canonical": note.canonical,
            "score": score,
            "matched_sections": [
                section.to_dict() for section in self._matched_sections(note, query_tokens)
            ],
            "note_sha256": note.note_sha256,
        }
        if note.canonical_scope is not None:
            result["canonical_scope"] = note.canonical_scope
        return result

    @staticmethod
    def _heading_for_line(note: KnowledgeNote, line_number: int) -> NoteHeading | None:
        containing = [
            heading
            for heading in note.headings
            if heading.line_start <= line_number <= heading.line_end
        ]
        return containing[-1] if containing else None

    def _matched_sections(
        self,
        note: KnowledgeNote,
        query_tokens: tuple[str, ...],
    ) -> tuple[MatchedSection, ...]:
        matches: list[int] = []
        query_set = set(query_tokens)
        for line_number in range(note.body_start_line, len(note.text_lines) + 1):
            line_tokens = set(_tokens(note.text_lines[line_number - 1]))
            if query_set & line_tokens:
                matches.append(line_number)
        if not matches and note.headings:
            matches.append(note.headings[0].line_start)
        sections: list[MatchedSection] = []
        used_ranges: set[tuple[int, int]] = set()
        for line_number in matches:
            heading = self._heading_for_line(note, line_number)
            section_start = heading.line_start if heading else max(note.body_start_line, line_number - 1)
            section_end = min(
                heading.line_end if heading else len(note.text_lines),
                line_number + 2,
            )
            section_start = max(section_start, line_number - 2, note.body_start_line)
            key = (section_start, section_end)
            if key in used_ranges:
                continue
            used_ranges.add(key)
            excerpt = "\n".join(note.text_lines[section_start - 1 : section_end])
            if len(excerpt) > MAX_EXCERPT_CHARS:
                excerpt = excerpt[: MAX_EXCERPT_CHARS - 1] + "…"
            sections.append(
                MatchedSection(
                    heading=heading.title if heading else "",
                    line_start=section_start,
                    line_end=section_end,
                    excerpt=excerpt,
                )
            )
            if len(sections) >= MAX_MATCHED_SECTIONS:
                break
        return tuple(sections)

    def note_get(self, note_id: str, max_chars: int | None = None) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            if not isinstance(note_id, str) or not vault_validator.ID_RE.fullmatch(note_id):
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND,
                    "Knowledge note was not found by stable ID.",
                )
            note = index.by_id.get(note_id)
            if note is None:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND,
                    "Knowledge note was not found by stable ID.",
                )
            limit = self._context_limit(max_chars)
            truncated = len(note.body_text) > limit
            return {
                "note_id": note.note_id,
                "title": note.title,
                "relative_path": note.relative_path,
                "metadata": note.metadata_dict(),
                "content": note.body_text[:limit],
                "truncated": truncated,
                "note_sha256": note.note_sha256,
                "vault_revision": index.vault_revision,
            }

    def _context_limit(self, value: Any) -> int:
        config = self._require_config()
        limit = config.default_context_chars if value is None else value
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= config.hard_max_context_chars:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_CONTEXT_LIMIT,
                "Context character limit is outside the configured bounds.",
            )
        return limit

    def context_preview(
        self,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int | None = None,
        max_results: int | None = None,
        include_superseded: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            limit = self._context_limit(max_context_chars)
            search_response = self.search(
                query,
                intent,
                max_results=max_results,
                include_superseded=include_superseded,
            )
            sources: list[dict[str, Any]] = []
            total_chars = 0
            truncated = False
            bundle_parts: list[bytes] = [
                index.vault_revision.encode("utf-8"),
                _normalize(query).encode("utf-8"),
                search_response["resolved_intent"].encode("ascii"),
            ]
            for result in search_response["results"]:
                note = index.by_id[result["note_id"]]
                selected_sections: list[dict[str, Any]] = []
                for section in result["matched_sections"]:
                    content = section["excerpt"]
                    remaining = limit - total_chars
                    if remaining <= 0:
                        truncated = True
                        break
                    if len(content) > remaining:
                        content = content[:remaining]
                        truncated = True
                    selected = {
                        "heading": section["heading"],
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                        "content": content,
                    }
                    selected_sections.append(selected)
                    total_chars += len(content)
                    bundle_parts.extend(
                        (
                            note.note_id.encode("utf-8"),
                            f"{selected['line_start']}:{selected['line_end']}".encode("ascii"),
                            hashlib.sha256(content.encode("utf-8")).hexdigest().encode("ascii"),
                        )
                    )
                    if len(content) < len(section["excerpt"]):
                        break
                if selected_sections:
                    sources.append(
                        {
                            "note_id": note.note_id,
                            "title": note.title,
                            "relative_path": note.relative_path,
                            "knowledge_layer": note.knowledge_layer,
                            "evidence_class": note.evidence_class,
                            "authority": note.authority,
                            "status": note.status,
                            "canonical": note.canonical,
                            "selected_sections": selected_sections,
                            "note_sha256": note.note_sha256,
                        }
                    )
                if total_chars >= limit:
                    if any(
                        candidate["note_id"] != result["note_id"]
                        for candidate in search_response["results"]
                        if candidate not in search_response["results"][: len(sources)]
                    ):
                        truncated = True
                    break
            digest = hashlib.sha256()
            for part in bundle_parts:
                digest.update(part)
                digest.update(b"\0")
            warnings = []
            if index.validation_warning_count:
                warnings.append(f"VALIDATION_WARNINGS:{index.validation_warning_count}")
            if truncated:
                warnings.append("CONTEXT_TRUNCATED")
            response = {
                "bundle_id": "kb:" + digest.hexdigest(),
                "vault_revision": index.vault_revision,
                "query": query,
                "resolved_intent": search_response["resolved_intent"],
                "total_chars": total_chars,
                "truncated": truncated,
                "sources": sources,
                "context_relations": self._relations(sources, index),
                "warnings": warnings,
            }
            self._log(
                "context_preview_completed",
                resolved_intent=search_response["resolved_intent"],
                result_count=len(sources),
                context_character_count=total_chars,
            )
            return response

    @staticmethod
    def _relations(sources: list[dict[str, Any]], index: _KnowledgeIndex) -> list[dict[str, Any]]:
        relations: list[dict[str, Any]] = []
        current = [source["note_id"] for source in sources if source["knowledge_layer"] == "current_source_truth"]
        historical = [
            source["note_id"]
            for source in sources
            if source["knowledge_layer"] in {"verified_history", "forensic_evidence", "session_snapshot"}
        ]
        founders = [source["note_id"] for source in sources if source["knowledge_layer"] == "founder_intent"]
        research = [source["note_id"] for source in sources if source["knowledge_layer"] == "research"]
        if current and historical:
            relations.append({"type": "CURRENT_VS_HISTORICAL", "note_ids": [current[0], historical[0]]})
        if current and founders:
            relations.append({"type": "FOUNDER_INTENT_VS_IMPLEMENTATION", "note_ids": [founders[0], current[0]]})
        if current and research:
            relations.append({"type": "RESEARCH_VS_CURRENT", "note_ids": [research[0], current[0]]})
        for source in sources:
            note = index.by_id[source["note_id"]]
            if note.status == "superseded" and note.superseded_by:
                relations.append({"type": "SUPERSEDED", "note_ids": [note.note_id, note.superseded_by[0]]})
        return relations

    def dispatch(self, operation: str, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(request or {})
        if operation == "knowledge.status":
            return self.status()
        if operation == "knowledge.refresh":
            return self.refresh()
        if operation == "knowledge.search":
            return self.search(
                payload.get("query"),
                payload.get("intent", QueryIntent.AUTO.value),
                payload.get("max_results"),
                payload.get("include_superseded", False),
            )
        if operation == "knowledge.note.get":
            return self.note_get(payload.get("note_id"), payload.get("max_chars"))
        if operation == "knowledge.context.preview":
            return self.context_preview(
                payload.get("query"),
                payload.get("intent", QueryIntent.AUTO.value),
                payload.get("max_context_chars"),
                payload.get("max_results"),
                payload.get("include_superseded", False),
            )
        raise KnowledgeAdapterError(
            KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
            "Unknown knowledge operation.",
        )


__all__ = [
    "KnowledgeAdapter",
    "KnowledgeAdapterError",
    "KnowledgeConfig",
    "KnowledgeErrorCode",
    "QueryIntent",
]
````

### ПУТЬ: modules/knowledge_change_proposal_ru.py (783 строк, 37175 байт)

````python
"""Knowledge Change Proposal Contract — v6.84.5.1e9a.

Model-independent, deterministic, proposal-only contract for untrusted agents to
propose changes to durable LocalComet knowledge without authority to modify the
canonical Vault.

This module implements:
- KnowledgeChangeProposal: versioned, bounded, canonicalized proposal structure
- ProposalValidator: deterministic validation against current Vault revision
- ValidationResult: immutable structured outcome (VALID/INVALID/STALE)
- No Vault writes, no publication path, no approval path, no persistent store.

Contract version: localcomet.knowledge-change-proposal / 1.0
Proposal identity prefix: kprop:
Supported operations: UPDATE_EXISTING, CREATE_NEW
Rejected operations: DELETE, MOVE, RENAME, SUPERSEDE (reserved, non-validating)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from modules.knowledge_contract_ru import (
    KnowledgeAdapterError,
    KnowledgeErrorCode,
    _SHA256_RE,
    _VAULT_REVISION_RE,
    _bounded_integer,
    _contains_absolute_path,
    _freeze,
    _thaw,
)
from tools.validate_localcomet_vault import ID_RE, ValidationResult as VaultValidationResult

sys.dont_write_bytecode = True

CONTRACT_VERSION = "localcomet.knowledge-change-proposal/1.0"
PROPOSAL_ID_PREFIX = "kprop:"
PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
_STABLE_ID_MAXLEN = 128
_PROPOSER_METADATA_MAXLEN = 512
_REASON_MAXLEN = 2048
_CONTENT_MAXLEN = 1_048_576
_EVIDENCE_REF_MAXLEN = 256
_MAX_EVIDENCE_REFS = 32
_MAX_TOTAL_PROPOSAL_BYTES = 2_097_152
_SUPERSEDE_RESERVED = "SUPERSEDE_RESERVED"


class ProposalOperation(str, Enum):
    UPDATE_EXISTING = "UPDATE_EXISTING"
    CREATE_NEW = "CREATE_NEW"
    DELETE = "DELETE"
    MOVE = "MOVE"
    RENAME = "RENAME"
    SUPERSEDE = "SUPERSEDE"


class ValidationOutcome(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    STALE = "STALE"


class ProposalValidationCode(str, Enum):
    OK = "OK"
    MISSING_CONTRACT_VERSION = "MISSING_CONTRACT_VERSION"
    UNSUPPORTED_CONTRACT_VERSION = "UNSUPPORTED_CONTRACT_VERSION"
    EMPTY_PROPOSAL_ID = "EMPTY_PROPOSAL_ID"
    MALFORMED_PROPOSAL_ID = "MALFORMED_PROPOSAL_ID"
    EMPTY_STABLE_ID = "EMPTY_STABLE_ID"
    MALFORMED_STABLE_ID = "MALFORMED_STABLE_ID"
    STABLE_ID_TOO_LONG = "STABLE_ID_TOO_LONG"
    MISSING_OPERATION = "MISSING_OPERATION"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    UPDATE_TARGET_MISSING = "UPDATE_TARGET_MISSING"
    CREATE_STABLE_ID_COLLISION = "CREATE_STABLE_ID_COLLISION"
    MALFORMED_EXPECTED_VAULT_REVISION = "MALFORMED_EXPECTED_VAULT_REVISION"
    STALE_BASE_REVISION = "STALE_BASE_REVISION"
    ABSOLUTE_PATH_ATTEMPT = "ABSOLUTE_PATH_ATTEMPT"
    PARENT_TRAVERSAL_ATTEMPT = "PARENT_TRAVERSAL_ATTEMPT"
    DESTRUCTIVE_OPERATION_REJECTED = "DESTRUCTIVE_OPERATION_REJECTED"
    SUPERSEDE_RESERVED_NON_VALIDATING = "SUPERSEDE_RESERVED_NON_VALIDATING"
    PROPOSER_AUTHORITY_SPOOFING = "PROPOSER_AUTHORITY_SPOOFING"
    PROPOSER_LIFECYCLE_SPOOFING = "PROPOSER_LIFECYCLE_SPOOFING"
    MALFORMED_EVIDENCE_REFERENCE = "MALFORMED_EVIDENCE_REFERENCE"
    TOO_MANY_EVIDENCE_REFERENCES = "TOO_MANY_EVIDENCE_REFERENCES"
    EVIDENCE_REFERENCE_TOO_LONG = "EVIDENCE_REFERENCE_TOO_LONG"
    OVERSIZED_CONTENT = "OVERSIZED_CONTENT"
    OVERSIZED_TOTAL_PROPOSAL = "OVERSIZED_TOTAL_PROPOSAL"
    SECRET_DETECTED = "SECRET_DETECTED"
    PROPOSER_METADATA_TOO_LONG = "PROPOSER_METADATA_TOO_LONG"
    REASON_TOO_LONG = "REASON_TOO_LONG"
    HASH_AMBIGUITY = "HASH_AMBIGUITY"
    CANONICALIZATION_AMBIGUITY = "CANONICALIZATION_AMBIGUITY"
    MUTATION_DURING_VALIDATION = "MUTATION_DURING_VALIDATION"
    INTERNAL_VALIDATION_ERROR = "INTERNAL_VALIDATION_ERROR"


@dataclass(frozen=True, slots=True)
class ProposerMetadata:
    agent_type: str = ""
    agent_instance_id: str = ""
    model_identifier: str = ""
    source_workflow: str = ""

    def __post_init__(self) -> None:
        for name, value in (("agent_type", self.agent_type), ("agent_instance_id", self.agent_instance_id),
                            ("model_identifier", self.model_identifier), ("source_workflow", self.source_workflow)):
            if not isinstance(value, str):
                raise ValueError(f"proposer metadata {name} must be string")
            if len(value) > _PROPOSER_METADATA_MAXLEN:
                raise ValueError(f"proposer metadata {name} exceeds {_PROPOSER_METADATA_MAXLEN} chars")
        if _contains_absolute_path((self.agent_type, self.agent_instance_id, self.model_identifier, self.source_workflow)):
            raise ValueError("proposer metadata contains absolute path")

    def to_dict(self) -> dict[str, str]:
        return {
            "agent_type": self.agent_type,
            "agent_instance_id": self.agent_instance_id,
            "model_identifier": self.model_identifier,
            "source_workflow": self.source_workflow,
        }


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    reference: str
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reference, str) or not self.reference:
            raise ValueError("evidence reference must be non-empty string")
        if len(self.reference) > _EVIDENCE_REF_MAXLEN:
            raise ValueError(f"evidence reference exceeds {_EVIDENCE_REF_MAXLEN} chars")
        if not isinstance(self.description, str):
            raise ValueError("evidence description must be string")
        if len(self.description) > _EVIDENCE_REF_MAXLEN:
            raise ValueError(f"evidence description exceeds {_EVIDENCE_REF_MAXLEN} chars")
        if _contains_absolute_path(self.reference) or _contains_absolute_path(self.description):
            raise ValueError("evidence reference contains absolute path")

    def to_dict(self) -> dict[str, str]:
        return {"reference": self.reference, "description": self.description}


@dataclass(frozen=True, slots=True)
class ProposedNoteContent:
    title: str
    body_text: str
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool = False
    canonical_scope: str | None = None
    aliases: tuple[str, ...] = ()
    releases: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    superseded_by: tuple[str, ...] = ()
    updated: str = ""
    last_reviewed: str = ""
    verified_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise ValueError("proposed title must be string")
        if not isinstance(self.body_text, str):
            raise ValueError("proposed body_text must be string")
        if len(self.body_text) > _CONTENT_MAXLEN:
            raise ValueError(f"proposed content exceeds {_CONTENT_MAXLEN} chars")
        if not isinstance(self.type, str) or not self.type:
            raise ValueError("proposed type must be non-empty string")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("proposed status must be non-empty string")
        if not isinstance(self.knowledge_layer, str) or not self.knowledge_layer:
            raise ValueError("proposed knowledge_layer must be non-empty string")
        if not isinstance(self.evidence_class, str) or not self.evidence_class:
            raise ValueError("proposed evidence_class must be non-empty string")
        if not isinstance(self.authority, str) or not self.authority:
            raise ValueError("proposed authority must be non-empty string")
        if not isinstance(self.canonical, bool):
            raise ValueError("proposed canonical must be boolean")
        if self.canonical_scope is not None and (not isinstance(self.canonical_scope, str) or not self.canonical_scope):
            raise ValueError("proposed canonical_scope must be non-empty string when set")
        for seq_name, seq_val in (("aliases", self.aliases), ("releases", self.releases),
                                   ("source_paths", self.source_paths), ("evidence_refs", self.evidence_refs),
                                   ("supersedes", self.supersedes), ("superseded_by", self.superseded_by)):
            if not isinstance(seq_val, tuple):
                raise ValueError(f"proposed {seq_name} must be tuple")
            for item in seq_val:
                if not isinstance(item, str):
                    raise ValueError(f"proposed {seq_name} item must be string")
                if _contains_absolute_path(item):
                    raise ValueError(f"proposed {seq_name} contains absolute path")
        if self.updated and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.updated):
            raise ValueError("proposed updated must be YYYY-MM-DD")
        if self.last_reviewed and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.last_reviewed):
            raise ValueError("proposed last_reviewed must be YYYY-MM-DD")
        if self.verified_at is not None:
            if not isinstance(self.verified_at, str):
                raise ValueError("proposed verified_at must be string or None")
            try:
                from datetime import datetime
                datetime.fromisoformat(self.verified_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("proposed verified_at must be ISO timestamp") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body_text": self.body_text,
            "type": self.type,
            "status": self.status,
            "knowledge_layer": self.knowledge_layer,
            "evidence_class": self.evidence_class,
            "authority": self.authority,
            "canonical": self.canonical,
            "canonical_scope": self.canonical_scope,
            "aliases": list(self.aliases),
            "releases": list(self.releases),
            "source_paths": list(self.source_paths),
            "evidence_refs": list(self.evidence_refs),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "updated": self.updated,
            "last_reviewed": self.last_reviewed,
            "verified_at": self.verified_at,
        }


@dataclass(frozen=True, slots=True)
class CanonicalLocationHint:
    relative_path: str
    parent_stable_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str) or not self.relative_path:
            raise ValueError("canonical location hint relative_path must be non-empty string")
        if PurePosixPath(self.relative_path).is_absolute() or PureWindowsPath(self.relative_path).is_absolute():
            raise ValueError("canonical location hint must not be absolute path")
        parts = [p for p in re.split(r"[\\/]", self.relative_path) if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise ValueError("canonical location hint parent traversal forbidden")
        if self.parent_stable_id is not None:
            if not isinstance(self.parent_stable_id, str) or not ID_RE.fullmatch(self.parent_stable_id):
                raise ValueError("canonical location hint parent_stable_id must be valid stable ID")

    def to_dict(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "parent_stable_id": self.parent_stable_id}


@dataclass(frozen=True, slots=True)
class Provenance:
    reason: str
    source_observation: str = ""
    related_stable_ids: tuple[str, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()
    workflow_origin: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("provenance reason must be non-empty string")
        if len(self.reason) > _REASON_MAXLEN:
            raise ValueError(f"provenance reason exceeds {_REASON_MAXLEN} chars")
        if not isinstance(self.source_observation, str):
            raise ValueError("provenance source_observation must be string")
        if len(self.source_observation) > _REASON_MAXLEN:
            raise ValueError(f"provenance source_observation exceeds {_REASON_MAXLEN} chars")
        if not isinstance(self.workflow_origin, str):
            raise ValueError("provenance workflow_origin must be string")
        if len(self.workflow_origin) > _REASON_MAXLEN:
            raise ValueError(f"provenance workflow_origin exceeds {_REASON_MAXLEN} chars")
        for sid in self.related_stable_ids:
            if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
                raise ValueError("provenance related_stable_ids must be valid stable IDs")
        if len(self.evidence_references) > _MAX_EVIDENCE_REFS:
            raise ValueError(f"evidence references exceed {_MAX_EVIDENCE_REFS}")
        for ref in self.evidence_references:
            if not isinstance(ref, EvidenceReference):
                raise ValueError("provenance evidence_references must be EvidenceReference objects")
        if _contains_absolute_path((self.reason, self.source_observation, self.workflow_origin,
                                     self.related_stable_ids, self.evidence_references)):
            raise ValueError("provenance contains absolute path")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "source_observation": self.source_observation,
            "related_stable_ids": list(self.related_stable_ids),
            "evidence_references": [ref.to_dict() for ref in self.evidence_references],
            "workflow_origin": self.workflow_origin,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeChangeProposal:
    proposal_id: str
    contract_version: str
    operation: ProposalOperation
    target_stable_id: str
    expected_vault_revision: str
    proposer: ProposerMetadata
    provenance: Provenance
    proposed_content: ProposedNoteContent | None = None
    canonical_location_hint: CanonicalLocationHint | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("proposal_id must match kprop:<sha256>")
        if not isinstance(self.contract_version, str) or self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        if not isinstance(self.operation, ProposalOperation):
            try:
                object.__setattr__(self, "operation", ProposalOperation(self.operation))
            except (TypeError, ValueError) as exc:
                raise ValueError("operation must be valid ProposalOperation") from exc
        if not isinstance(self.target_stable_id, str) or not self.target_stable_id:
            raise ValueError("target_stable_id must be non-empty string")
        if len(self.target_stable_id) > _STABLE_ID_MAXLEN:
            raise ValueError(f"target_stable_id exceeds {_STABLE_ID_MAXLEN} chars")
        if not ID_RE.fullmatch(self.target_stable_id):
            raise ValueError("target_stable_id must be valid stable ID pattern")
        if not isinstance(self.expected_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.expected_vault_revision):
            raise ValueError("expected_vault_revision must be sha256:<64-hex>")
        if not isinstance(self.proposer, ProposerMetadata):
            raise ValueError("proposer must be ProposerMetadata")
        if not isinstance(self.provenance, Provenance):
            raise ValueError("provenance must be Provenance")
        if self.proposed_content is not None and not isinstance(self.proposed_content, ProposedNoteContent):
            raise ValueError("proposed_content must be ProposedNoteContent or None")
        if self.canonical_location_hint is not None and not isinstance(self.canonical_location_hint, CanonicalLocationHint):
            raise ValueError("canonical_location_hint must be CanonicalLocationHint or None")
        if self.operation in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW):
            if self.proposed_content is None:
                raise ValueError(f"operation {self.operation.value} requires proposed_content")
        if self.operation is ProposalOperation.CREATE_NEW:
            if self.canonical_location_hint is None:
                raise ValueError("CREATE_NEW requires canonical_location_hint")
        if self.operation is ProposalOperation.UPDATE_EXISTING:
            if self.canonical_location_hint is not None:
                raise ValueError("UPDATE_EXISTING must not provide canonical_location_hint")
        if _contains_absolute_path(self):
            raise ValueError("proposal contains absolute path")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "contract_version": self.contract_version,
            "operation": self.operation.value,
            "target_stable_id": self.target_stable_id,
            "expected_vault_revision": self.expected_vault_revision,
            "proposer": self.proposer.to_dict(),
            "provenance": self.provenance.to_dict(),
            "proposed_content": self.proposed_content.to_dict() if self.proposed_content else None,
            "canonical_location_hint": self.canonical_location_hint.to_dict() if self.canonical_location_hint else None,
        }


def _canonical_proposal_bytes(proposal: KnowledgeChangeProposal) -> bytes:
    payload = {
        "proposal_id": proposal.proposal_id,
        "contract_version": proposal.contract_version,
        "operation": proposal.operation.value,
        "target_stable_id": proposal.target_stable_id,
        "expected_vault_revision": proposal.expected_vault_revision,
        "proposer": proposal.proposer.to_dict(),
        "provenance": proposal.provenance.to_dict(),
        "proposed_content": proposal.proposed_content.to_dict() if proposal.proposed_content else None,
        "canonical_location_hint": proposal.canonical_location_hint.to_dict() if proposal.canonical_location_hint else None,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_proposal_content_hash(proposal: KnowledgeChangeProposal) -> str:
    return "sha256:" + hashlib.sha256(_canonical_proposal_bytes(proposal)).hexdigest()


def compute_proposal_instance_id(proposal: KnowledgeChangeProposal) -> str:
    return PROPOSAL_ID_PREFIX + hashlib.sha256(_canonical_proposal_bytes(proposal)).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    outcome: ValidationOutcome
    proposal_id: str
    proposal_content_hash: str
    contract_version: str
    operation: str
    target_stable_id: str
    expected_vault_revision: str
    validated_vault_revision: str
    findings: tuple[ValidationFinding, ...] = ()
    provenance_summary: dict[str, Any] | None = None
    evidence_reference_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ValidationOutcome):
            try:
                object.__setattr__(self, "outcome", ValidationOutcome(self.outcome))
            except (TypeError, ValueError) as exc:
                raise ValueError("outcome must be ValidationOutcome") from exc
        if not isinstance(self.proposal_id, str) or not PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("validation result proposal_id invalid")
        if not isinstance(self.proposal_content_hash, str):
            raise ValueError("validation result proposal_content_hash invalid")
        # Accept both "sha256:" prefix and raw 64-hex
        if self.proposal_content_hash.startswith("sha256:"):
            if not _SHA256_RE.fullmatch(self.proposal_content_hash[7:]):
                raise ValueError("validation result proposal_content_hash invalid")
        elif not _SHA256_RE.fullmatch(self.proposal_content_hash):
            raise ValueError("validation result proposal_content_hash invalid")
        if not isinstance(self.contract_version, str) or self.contract_version != CONTRACT_VERSION:
            raise ValueError("validation result contract_version invalid")
        if not isinstance(self.operation, str):
            raise ValueError("validation result operation invalid")
        if not isinstance(self.target_stable_id, str):
            raise ValueError("validation result target_stable_id invalid")
        if not isinstance(self.expected_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.expected_vault_revision):
            raise ValueError("validation result expected_vault_revision invalid")
        if not isinstance(self.validated_vault_revision, str) or not _VAULT_REVISION_RE.fullmatch(self.validated_vault_revision):
            raise ValueError("validation result validated_vault_revision invalid")
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        for f in self.findings:
            if not isinstance(f, ValidationFinding):
                raise ValueError("findings must be ValidationFinding objects")
        if self.provenance_summary is not None and not isinstance(self.provenance_summary, dict):
            raise ValueError("provenance_summary must be dict or None")
        if not isinstance(self.evidence_reference_count, int) or self.evidence_reference_count < 0:
            raise ValueError("evidence_reference_count must be non-negative int")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "proposal_id": self.proposal_id,
            "proposal_content_hash": self.proposal_content_hash,
            "contract_version": self.contract_version,
            "operation": self.operation,
            "target_stable_id": self.target_stable_id,
            "expected_vault_revision": self.expected_vault_revision,
            "validated_vault_revision": self.validated_vault_revision,
            "findings": [f.to_dict() for f in self.findings],
            "provenance_summary": self.provenance_summary,
            "evidence_reference_count": self.evidence_reference_count,
        }


class ProposalValidator:
    def __init__(
        self,
        vault_revision: str,
        stable_ids: frozenset[str] | set[str] | None = None,
        *,
        vault_root: Path | None = None,
        project_root: Path | None = None,
        max_notes: int = 2000,
        max_note_bytes: int = 1_048_576,
        max_total_scan_bytes: int = 67_108_864,
    ) -> None:
        self._provided_revision = vault_revision
        self._provided_stable_ids = frozenset(stable_ids) if stable_ids is not None else None
        self._vault_root = Path(os.fspath(vault_root)) if vault_root else None
        self._project_root = Path(os.fspath(project_root)) if project_root else None
        self._max_notes = max_notes
        self._max_note_bytes = max_note_bytes
        self._max_total_scan_bytes = max_total_scan_bytes
        self._cached_validation: VaultValidationResult | None = None
        self._cached_stable_ids: frozenset[str] | None = None

    def _get_current_vault_revision(self) -> str:
        if self._provided_revision:
            return self._provided_revision
        if self._cached_validation is None:
            if not self._vault_root or not self._project_root:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                    "ProposalValidator requires either vault_revision or vault_root+project_root",
                )
            self._cached_validation = vault_validator.validate_vault(
                self._vault_root,
                self._project_root,
                max_notes=self._max_notes,
                max_note_bytes=self._max_note_bytes,
                max_total_scan_bytes=self._max_total_scan_bytes,
            )
            if self._cached_validation.status == "FAIL" or self._cached_validation.error_count > 0:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_VALIDATION_FAILED,
                    "Current Vault validation failed; cannot validate proposals against invalid baseline.",
                )
        return self._cached_validation.vault_revision

    def _get_stable_ids(self) -> frozenset[str]:
        if self._provided_stable_ids is not None:
            return self._provided_stable_ids
        if self._cached_stable_ids is None:
            self._get_current_vault_revision()
            if self._cached_validation:
                stable_ids = set()
                for note in self._cached_validation.__dict__.get("notes", []):
                    if hasattr(note, "note_id") and note.note_id and ID_RE.fullmatch(note.note_id):
                        stable_ids.add(note.note_id)
                self._cached_stable_ids = frozenset(stable_ids)
        return self._cached_stable_ids or frozenset()

    def validate(self, proposal: KnowledgeChangeProposal) -> ValidationResult:
        current_revision = self._get_current_vault_revision()
        stable_ids = self._get_stable_ids()

        findings: list[ValidationFinding] = []

        if proposal.contract_version != CONTRACT_VERSION:
            findings.append(ValidationFinding(
                ProposalValidationCode.UNSUPPORTED_CONTRACT_VERSION.value,
                f"Unsupported contract version: {proposal.contract_version}",
            ))

        if proposal.operation in (ProposalOperation.DELETE, ProposalOperation.MOVE, ProposalOperation.RENAME):
            findings.append(ValidationFinding(
                ProposalValidationCode.DESTRUCTIVE_OPERATION_REJECTED.value,
                f"Operation {proposal.operation.value} is not supported in this contract version",
            ))
        elif proposal.operation is ProposalOperation.SUPERSEDE:
            findings.append(ValidationFinding(
                ProposalValidationCode.SUPERSEDE_RESERVED_NON_VALIDATING.value,
                "SUPERSEDE is reserved for future use and cannot validate in this release",
            ))

        if proposal.operation is ProposalOperation.UPDATE_EXISTING:
            if proposal.target_stable_id not in stable_ids:
                findings.append(ValidationFinding(
                    ProposalValidationCode.UPDATE_TARGET_MISSING.value,
                    f"UPDATE_EXISTING target stable ID not found in current Vault: {proposal.target_stable_id}",
                ))
        elif proposal.operation is ProposalOperation.CREATE_NEW:
            if proposal.target_stable_id in stable_ids:
                findings.append(ValidationFinding(
                    ProposalValidationCode.CREATE_STABLE_ID_COLLISION.value,
                    f"CREATE_NEW target stable ID collides with existing: {proposal.target_stable_id}",
                ))

        if proposal.expected_vault_revision != current_revision:
            findings.append(ValidationFinding(
                ProposalValidationCode.STALE_BASE_REVISION.value,
                f"Proposal expected Vault revision {proposal.expected_vault_revision} but current is {current_revision}",
            ))

        proposer_dict = proposal.proposer.to_dict()
        reserved_keys = {"VALIDATED", "APPROVED", "PUBLISHED", "USER_APPROVAL", "CANONICAL", "VERIFIED_BY_LOCALCOMET"}
        for key, value in proposer_dict.items():
            if key in reserved_keys or value in reserved_keys:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_AUTHORITY_SPOOFING.value,
                    f"Proposer metadata contains reserved authority term: {key}={value}",
                ))

        prov_dict = proposal.provenance.to_dict()
        # Check provenance fields for reserved lifecycle terms
        for field in ("source_observation", "workflow_origin"):
            val = prov_dict.get(field, "")
            if val in reserved_keys:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_LIFECYCLE_SPOOFING.value,
                    f"Provenance {field} contains reserved lifecycle term: {val}",
                ))
        for ref in prov_dict.get("evidence_references", []):
            if isinstance(ref, dict) and ref.get("verified") is True:
                findings.append(ValidationFinding(
                    ProposalValidationCode.PROPOSER_LIFECYCLE_SPOOFING.value,
                    "Evidence reference claims verified status not granted by this contract",
                ))

        if proposal.proposed_content:
            content_bytes = proposal.proposed_content.body_text.encode("utf-8")
            if len(content_bytes) > _CONTENT_MAXLEN:
                findings.append(ValidationFinding(
                    ProposalValidationCode.OVERSIZED_CONTENT.value,
                    f"Proposed content exceeds {_CONTENT_MAXLEN} bytes",
                ))
            if self._detect_secrets(proposal.proposed_content.body_text):
                findings.append(ValidationFinding(
                    ProposalValidationCode.SECRET_DETECTED.value,
                    "Proposed content contains detected secret pattern",
                ))

        total_bytes = len(_canonical_proposal_bytes(proposal))
        if total_bytes > _MAX_TOTAL_PROPOSAL_BYTES:
            findings.append(ValidationFinding(
                ProposalValidationCode.OVERSIZED_TOTAL_PROPOSAL.value,
                f"Total proposal size {total_bytes} exceeds {_MAX_TOTAL_PROPOSAL_BYTES} bytes",
            ))

        if proposal.provenance and len(proposal.provenance.evidence_references) > _MAX_EVIDENCE_REFS:
            findings.append(ValidationFinding(
                ProposalValidationCode.TOO_MANY_EVIDENCE_REFERENCES.value,
                f"Evidence references exceed {_MAX_EVIDENCE_REFS}",
            ))

        for ref in proposal.provenance.evidence_references:
            if len(ref.reference) > _EVIDENCE_REF_MAXLEN:
                findings.append(ValidationFinding(
                    ProposalValidationCode.EVIDENCE_REFERENCE_TOO_LONG.value,
                    f"Evidence reference exceeds {_EVIDENCE_REF_MAXLEN} chars",
                ))

        if findings:
            outcome = ValidationOutcome.INVALID
            for f in findings:
                if f.code == ProposalValidationCode.STALE_BASE_REVISION.value:
                    outcome = ValidationOutcome.STALE
                    break
        else:
            outcome = ValidationOutcome.VALID

        content_hash = compute_proposal_content_hash(proposal)
        provenance_summary = {
            "reason": proposal.provenance.reason[:200],
            "source_observation": proposal.provenance.source_observation[:200] if proposal.provenance.source_observation else "",
            "related_stable_ids": list(proposal.provenance.related_stable_ids),
            "workflow_origin": proposal.provenance.workflow_origin[:200] if proposal.provenance.workflow_origin else "",
        }

        return ValidationResult(
            outcome=outcome,
            proposal_id=proposal.proposal_id,
            proposal_content_hash=content_hash,
            contract_version=CONTRACT_VERSION,
            operation=proposal.operation.value,
            target_stable_id=proposal.target_stable_id,
            expected_vault_revision=proposal.expected_vault_revision,
            validated_vault_revision=current_revision,
            findings=tuple(findings),
            provenance_summary=provenance_summary,
            evidence_reference_count=len(proposal.provenance.evidence_references),
        )

    def _detect_secrets(self, text: str) -> bool:
        patterns = [
            re.compile(r"\bsk-(?:live-)?[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
            re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|passwd|client_secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{20,}"),
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
        ]
        for pattern in patterns:
            if pattern.search(text):
                return True
        return False


def create_proposal_from_untrusted(
    *,
    operation: str,
    target_stable_id: str,
    expected_vault_revision: str,
    proposer: dict[str, str] | None = None,
    provenance: dict[str, Any] | None = None,
    proposed_content: dict[str, Any] | None = None,
    canonical_location_hint: dict[str, Any] | None = None,
) -> KnowledgeChangeProposal:
    proposer_obj = ProposerMetadata(
        agent_type=(proposer or {}).get("agent_type", ""),
        agent_instance_id=(proposer or {}).get("agent_instance_id", ""),
        model_identifier=(proposer or {}).get("model_identifier", ""),
        source_workflow=(proposer or {}).get("source_workflow", ""),
    )

    evidence_refs = []
    for ref in (provenance or {}).get("evidence_references", []):
        evidence_refs.append(EvidenceReference(
            reference=ref.get("reference", ""),
            description=ref.get("description", ""),
        ))

    provenance_obj = Provenance(
        reason=(provenance or {}).get("reason", ""),
        source_observation=(provenance or {}).get("source_observation", ""),
        related_stable_ids=tuple((provenance or {}).get("related_stable_ids", [])),
        evidence_references=tuple(evidence_refs),
        workflow_origin=(provenance or {}).get("workflow_origin", ""),
    )

    content_obj = None
    if proposed_content:
        content_obj = ProposedNoteContent(
            title=proposed_content.get("title", ""),
            body_text=proposed_content.get("body_text", ""),
            type=proposed_content.get("type", ""),
            status=proposed_content.get("status", ""),
            knowledge_layer=proposed_content.get("knowledge_layer", ""),
            evidence_class=proposed_content.get("evidence_class", ""),
            authority=proposed_content.get("authority", ""),
            canonical=proposed_content.get("canonical", False),
            canonical_scope=proposed_content.get("canonical_scope"),
            aliases=tuple(proposed_content.get("aliases", [])),
            releases=tuple(proposed_content.get("releases", [])),
            source_paths=tuple(proposed_content.get("source_paths", [])),
            evidence_refs=tuple(proposed_content.get("evidence_refs", [])),
            supersedes=tuple(proposed_content.get("supersedes", [])),
            superseded_by=tuple(proposed_content.get("superseded_by", [])),
            updated=proposed_content.get("updated", ""),
            last_reviewed=proposed_content.get("last_reviewed", ""),
            verified_at=proposed_content.get("verified_at"),
        )

    hint_obj = None
    if canonical_location_hint:
        hint_obj = CanonicalLocationHint(
            relative_path=canonical_location_hint.get("relative_path", ""),
            parent_stable_id=canonical_location_hint.get("parent_stable_id"),
        )

    temp_proposal = KnowledgeChangeProposal(
        proposal_id="kprop:" + "0" * 64,
        contract_version=CONTRACT_VERSION,
        operation=operation,
        target_stable_id=target_stable_id,
        expected_vault_revision=expected_vault_revision,
        proposer=proposer_obj,
        provenance=provenance_obj,
        proposed_content=content_obj,
        canonical_location_hint=hint_obj,
    )

    instance_id = compute_proposal_instance_id(temp_proposal)

    return KnowledgeChangeProposal(
        proposal_id=instance_id,
        contract_version=CONTRACT_VERSION,
        operation=operation,
        target_stable_id=target_stable_id,
        expected_vault_revision=expected_vault_revision,
        proposer=proposer_obj,
        provenance=provenance_obj,
        proposed_content=content_obj,
        canonical_location_hint=hint_obj,
    )


__all__ = [
    "CONTRACT_VERSION",
    "PROPOSAL_ID_PREFIX",
    "PROPOSAL_ID_RE",
    "ProposalOperation",
    "ValidationOutcome",
    "ProposalValidationCode",
    "ProposerMetadata",
    "EvidenceReference",
    "ProposedNoteContent",
    "CanonicalLocationHint",
    "Provenance",
    "KnowledgeChangeProposal",
    "ValidationFinding",
    "ValidationResult",
    "ProposalValidator",
    "compute_proposal_content_hash",
    "compute_proposal_instance_id",
    "create_proposal_from_untrusted",
]
````

### ПУТЬ: modules/knowledge_change_review_decision_ru.py (569 строк, 23759 байт)

````python
"""Human Review Decision Contract — LocalComet v6.84.5.1e9c.

Create one immutable, deterministic human-review decision bound to one exact
e9b ``KnowledgeChangeReviewArtifact``.  The result records review evidence and
then stops.  It has no persistence, Vault-write, publication, merge, rebase,
execution, model, network, subprocess, Tauri, frontend, registry, or consumer
authority.

Contract: localcomet.knowledge-change-review-decision/1.0
Lifecycle: exact e9b artifact -> exact decision binding -> decision -> HARD STOP
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Final

from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as REVIEW_CONTRACT_VERSION,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
)


CONTRACT_VERSION: Final[str] = "localcomet.knowledge-change-review-decision/1.0"
IDENTITY_VERSION: Final[str] = "1.0"
IDENTITY_DOMAIN: Final[str] = "HUMAN_REVIEW_DECISION_IDENTITY"
DECISION_ID_PREFIX: Final[str] = "kdecision:"

MAX_COMMENT_CHARS: Final[int] = 2_000
MAX_COMMENT_UTF8_BYTES: Final[int] = 4_096
MAX_ACTOR_IDENTIFIER_CHARS: Final[int] = 256
MAX_ACTOR_IDENTIFIER_UTF8_BYTES: Final[int] = 512
MAX_ACTOR_DISPLAY_NAME_CHARS: Final[int] = 256
MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES: Final[int] = 512
MAX_ACTOR_SOURCE_CHARS: Final[int] = 128
MAX_ACTOR_SOURCE_UTF8_BYTES: Final[int] = 256

HARD_STOP: Final[bool] = True
REVIEW_DECISION_ONLY: Final[bool] = True
ACTOR_METADATA_EVIDENCE_ONLY: Final[bool] = True
HUMAN_IDENTITY_AUTHENTICATED: Final[bool] = False
GRANTS_WRITE_AUTHORITY: Final[bool] = False
GRANTS_VAULT_WRITE_AUTHORITY: Final[bool] = False
GRANTS_PERSISTENCE_AUTHORITY: Final[bool] = False
GRANTS_PUBLICATION_AUTHORITY: Final[bool] = False
GRANTS_MERGE_AUTHORITY: Final[bool] = False
GRANTS_REBASE_AUTHORITY: Final[bool] = False
GRANTS_EXECUTION_AUTHORITY: Final[bool] = False
GRANTS_POLICY_AUTHORITY: Final[bool] = False
GRANTS_MODEL_GATEWAY_AUTHORITY: Final[bool] = False
GRANTS_TAURI_FRONTEND_AUTHORITY: Final[bool] = False
GRANTS_AUTOMATIC_APPROVAL_AUTHORITY: Final[bool] = False

_PROPOSAL_ID_RE = re.compile(r"^kprop:[0-9a-f]{64}$")
_REVIEW_ID_RE = re.compile(r"^kreview:[0-9a-f]{64}$")
_CHANGE_ID_RE = re.compile(r"^kchange:[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DECISION_ID_RE = re.compile(r"^kdecision:[0-9a-f]{64}$")


class HumanReviewDecisionValue(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class HumanReviewDecisionRejectionCode(str, Enum):
    WRONG_REVIEW_ARTIFACT_TYPE = "WRONG_REVIEW_ARTIFACT_TYPE"
    INVALID_REVIEW_ARTIFACT = "INVALID_REVIEW_ARTIFACT"
    UNSUPPORTED_REVIEW_CONTRACT = "UNSUPPORTED_REVIEW_CONTRACT"
    INVALID_BINDING_VALUE = "INVALID_BINDING_VALUE"
    PROPOSAL_ID_MISMATCH = "PROPOSAL_ID_MISMATCH"
    REVIEW_ARTIFACT_IDENTITY_MISMATCH = "REVIEW_ARTIFACT_IDENTITY_MISMATCH"
    CHANGE_IDENTITY_MISMATCH = "CHANGE_IDENTITY_MISMATCH"
    OBSERVED_VAULT_REVISION_MISMATCH = "OBSERVED_VAULT_REVISION_MISMATCH"
    STALE_CURRENT_VAULT_REVISION = "STALE_CURRENT_VAULT_REVISION"
    UNSUPPORTED_DECISION = "UNSUPPORTED_DECISION"
    BLOCKED_APPROVAL_FORBIDDEN = "BLOCKED_APPROVAL_FORBIDDEN"
    APPROVAL_REQUIRES_CHANGE_IDENTITY = "APPROVAL_REQUIRES_CHANGE_IDENTITY"
    COMMENT_TYPE_INVALID = "COMMENT_TYPE_INVALID"
    COMMENT_REQUIRED = "COMMENT_REQUIRED"
    COMMENT_CHARACTER_LIMIT_EXCEEDED = "COMMENT_CHARACTER_LIMIT_EXCEEDED"
    COMMENT_UTF8_ENCODING_INVALID = "COMMENT_UTF8_ENCODING_INVALID"
    COMMENT_UTF8_BYTE_LIMIT_EXCEEDED = "COMMENT_UTF8_BYTE_LIMIT_EXCEEDED"
    ACTOR_TYPE_INVALID = "ACTOR_TYPE_INVALID"


class HumanReviewDecisionRejected(ValueError):
    """Deterministic typed rejection from the e9c decision boundary."""

    def __init__(self, code: HumanReviewDecisionRejectionCode) -> None:
        if type(code) is not HumanReviewDecisionRejectionCode:
            raise TypeError("code must be HumanReviewDecisionRejectionCode")
        self.code = code
        super().__init__(code.value)


def _validate_actor_text(
    name: str,
    value: str,
    *,
    max_chars: int,
    max_utf8_bytes: int,
) -> None:
    if type(value) is not str:
        raise ValueError(f"{name} must be an exact string")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")
    if "\x00" in value:
        raise ValueError(f"{name} must not contain NUL")
    if len(value) > max_chars:
        raise ValueError(f"{name} exceeds {max_chars} characters")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"{name} must be valid UTF-8") from None
    if len(encoded) > max_utf8_bytes:
        raise ValueError(f"{name} exceeds {max_utf8_bytes} UTF-8 bytes")


@dataclass(frozen=True, slots=True)
class HumanReviewerMetadata:
    """Bounded descriptive reviewer evidence; never an authority credential."""

    actor_identifier: str
    display_name: str
    source: str

    def __post_init__(self) -> None:
        _validate_actor_text(
            "actor_identifier",
            self.actor_identifier,
            max_chars=MAX_ACTOR_IDENTIFIER_CHARS,
            max_utf8_bytes=MAX_ACTOR_IDENTIFIER_UTF8_BYTES,
        )
        _validate_actor_text(
            "display_name",
            self.display_name,
            max_chars=MAX_ACTOR_DISPLAY_NAME_CHARS,
            max_utf8_bytes=MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES,
        )
        _validate_actor_text(
            "source",
            self.source,
            max_chars=MAX_ACTOR_SOURCE_CHARS,
            max_utf8_bytes=MAX_ACTOR_SOURCE_UTF8_BYTES,
        )


def _decision_rule_error(
    review_status: ReviewStatus,
    change_identity: str | None,
    decision: HumanReviewDecisionValue,
) -> HumanReviewDecisionRejectionCode | None:
    if review_status is ReviewStatus.BLOCKED and decision is HumanReviewDecisionValue.APPROVE:
        return HumanReviewDecisionRejectionCode.BLOCKED_APPROVAL_FORBIDDEN
    if decision is HumanReviewDecisionValue.APPROVE and change_identity is None:
        return HumanReviewDecisionRejectionCode.APPROVAL_REQUIRES_CHANGE_IDENTITY
    return None


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    contract_version: str
    review_contract_version: str
    review_status: ReviewStatus
    proposal_id: str
    review_artifact_identity: str
    change_identity: str | None
    observed_vault_revision: str
    decision: HumanReviewDecisionValue
    comment: str
    actor: HumanReviewerMetadata
    decision_identity: str
    hard_stop: bool
    review_decision_only: bool
    actor_metadata_evidence_only: bool
    human_identity_authenticated: bool
    grants_write_authority: bool
    grants_vault_write_authority: bool
    grants_persistence_authority: bool
    grants_publication_authority: bool
    grants_merge_authority: bool
    grants_rebase_authority: bool
    grants_execution_authority: bool
    grants_policy_authority: bool
    grants_model_gateway_authority: bool
    grants_tauri_frontend_authority: bool
    grants_automatic_approval_authority: bool

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("decision contract version mismatch")
        if self.review_contract_version != REVIEW_CONTRACT_VERSION:
            raise ValueError("review contract version mismatch")
        if type(self.review_status) is not ReviewStatus:
            raise ValueError("review_status must be ReviewStatus")
        if type(self.proposal_id) is not str or not _PROPOSAL_ID_RE.fullmatch(self.proposal_id):
            raise ValueError("proposal_id is invalid")
        if (
            type(self.review_artifact_identity) is not str
            or not _REVIEW_ID_RE.fullmatch(self.review_artifact_identity)
        ):
            raise ValueError("review_artifact_identity is invalid")
        if self.change_identity is not None and (
            type(self.change_identity) is not str
            or not _CHANGE_ID_RE.fullmatch(self.change_identity)
        ):
            raise ValueError("change_identity is invalid")
        if (
            type(self.observed_vault_revision) is not str
            or not _REVISION_RE.fullmatch(self.observed_vault_revision)
        ):
            raise ValueError("observed_vault_revision is invalid")
        if type(self.decision) is not HumanReviewDecisionValue:
            raise ValueError("decision must be HumanReviewDecisionValue")
        decision_error = _decision_rule_error(
            self.review_status,
            self.change_identity,
            self.decision,
        )
        if decision_error is not None:
            raise ValueError(decision_error.value)
        comment_error = _comment_error(self.comment, self.decision)
        if comment_error is not None:
            raise ValueError(comment_error.value)
        if type(self.actor) is not HumanReviewerMetadata:
            raise ValueError("actor must be HumanReviewerMetadata")
        expected_boundary = _authority_boundary_values()
        actual_boundary = _authority_boundary_values(self)
        if actual_boundary != expected_boundary:
            raise ValueError("HARD STOP/no-authority boundary mismatch")
        if type(self.decision_identity) is not str or not _DECISION_ID_RE.fullmatch(
            self.decision_identity
        ):
            raise ValueError("decision_identity is invalid")
        expected_identity = _compute_decision_identity(
            contract_version=self.contract_version,
            review_contract_version=self.review_contract_version,
            review_status=self.review_status,
            proposal_id=self.proposal_id,
            review_artifact_identity=self.review_artifact_identity,
            change_identity=self.change_identity,
            observed_vault_revision=self.observed_vault_revision,
            decision=self.decision,
            comment=self.comment,
            actor=self.actor,
            boundary=actual_boundary,
        )
        if self.decision_identity != expected_identity:
            raise ValueError("decision_identity does not bind the complete artifact")

def _authority_boundary_values(
    decision: HumanReviewDecision | None = None,
) -> tuple[tuple[str, bool], ...]:
    if decision is not None:
        return (
            ("hard_stop", decision.hard_stop),
            ("review_decision_only", decision.review_decision_only),
            ("actor_metadata_evidence_only", decision.actor_metadata_evidence_only),
            ("human_identity_authenticated", decision.human_identity_authenticated),
            ("grants_write_authority", decision.grants_write_authority),
            ("grants_vault_write_authority", decision.grants_vault_write_authority),
            ("grants_persistence_authority", decision.grants_persistence_authority),
            ("grants_publication_authority", decision.grants_publication_authority),
            ("grants_merge_authority", decision.grants_merge_authority),
            ("grants_rebase_authority", decision.grants_rebase_authority),
            ("grants_execution_authority", decision.grants_execution_authority),
            ("grants_policy_authority", decision.grants_policy_authority),
            ("grants_model_gateway_authority", decision.grants_model_gateway_authority),
            ("grants_tauri_frontend_authority", decision.grants_tauri_frontend_authority),
            (
                "grants_automatic_approval_authority",
                decision.grants_automatic_approval_authority,
            ),
        )
    return (
        ("hard_stop", HARD_STOP),
        ("review_decision_only", REVIEW_DECISION_ONLY),
        ("actor_metadata_evidence_only", ACTOR_METADATA_EVIDENCE_ONLY),
        ("human_identity_authenticated", HUMAN_IDENTITY_AUTHENTICATED),
        ("grants_write_authority", GRANTS_WRITE_AUTHORITY),
        ("grants_vault_write_authority", GRANTS_VAULT_WRITE_AUTHORITY),
        ("grants_persistence_authority", GRANTS_PERSISTENCE_AUTHORITY),
        ("grants_publication_authority", GRANTS_PUBLICATION_AUTHORITY),
        ("grants_merge_authority", GRANTS_MERGE_AUTHORITY),
        ("grants_rebase_authority", GRANTS_REBASE_AUTHORITY),
        ("grants_execution_authority", GRANTS_EXECUTION_AUTHORITY),
        ("grants_policy_authority", GRANTS_POLICY_AUTHORITY),
        ("grants_model_gateway_authority", GRANTS_MODEL_GATEWAY_AUTHORITY),
        ("grants_tauri_frontend_authority", GRANTS_TAURI_FRONTEND_AUTHORITY),
        ("grants_automatic_approval_authority", GRANTS_AUTOMATIC_APPROVAL_AUTHORITY),
    )


def _decision_identity_payload(
    *,
    contract_version: str,
    review_contract_version: str,
    review_status: ReviewStatus,
    proposal_id: str,
    review_artifact_identity: str,
    change_identity: str | None,
    observed_vault_revision: str,
    decision: HumanReviewDecisionValue,
    comment: str,
    actor: HumanReviewerMetadata,
    boundary: tuple[tuple[str, bool], ...],
) -> dict[str, Any]:
    return {
        "decision_contract_version": contract_version,
        "review_contract_version": review_contract_version,
        "review_status": review_status.value,
        "proposal_id": proposal_id,
        "review_artifact_identity": review_artifact_identity,
        "change_identity": change_identity,
        "observed_vault_revision": observed_vault_revision,
        "decision": decision.value,
        "comment": comment,
        "actor": _actor_identity_payload(actor),
        "semantics": {key: value for key, value in boundary},
    }


def _actor_identity_payload(actor: HumanReviewerMetadata) -> dict[str, str]:
    return {
        "actor_identifier": actor.actor_identifier,
        "display_name": actor.display_name,
        "source": actor.source,
    }


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _compute_decision_identity(
    *,
    contract_version: str,
    review_contract_version: str,
    review_status: ReviewStatus,
    proposal_id: str,
    review_artifact_identity: str,
    change_identity: str | None,
    observed_vault_revision: str,
    decision: HumanReviewDecisionValue,
    comment: str,
    actor: HumanReviewerMetadata,
    boundary: tuple[tuple[str, bool], ...],
) -> str:
    payload = _decision_identity_payload(
        contract_version=contract_version,
        review_contract_version=review_contract_version,
        review_status=review_status,
        proposal_id=proposal_id,
        review_artifact_identity=review_artifact_identity,
        change_identity=change_identity,
        observed_vault_revision=observed_vault_revision,
        decision=decision,
        comment=comment,
        actor=actor,
        boundary=boundary,
    )
    envelope = {
        "domain": IDENTITY_DOMAIN,
        "version": IDENTITY_VERSION,
        "payload": payload,
    }
    return DECISION_ID_PREFIX + hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()


def _comment_error(
    comment: Any,
    decision: HumanReviewDecisionValue,
) -> HumanReviewDecisionRejectionCode | None:
    if type(comment) is not str:
        return HumanReviewDecisionRejectionCode.COMMENT_TYPE_INVALID
    if len(comment) > MAX_COMMENT_CHARS:
        return HumanReviewDecisionRejectionCode.COMMENT_CHARACTER_LIMIT_EXCEEDED
    try:
        encoded = comment.encode("utf-8")
    except UnicodeEncodeError:
        return HumanReviewDecisionRejectionCode.COMMENT_UTF8_ENCODING_INVALID
    if len(encoded) > MAX_COMMENT_UTF8_BYTES:
        return HumanReviewDecisionRejectionCode.COMMENT_UTF8_BYTE_LIMIT_EXCEEDED
    if decision is HumanReviewDecisionValue.REQUEST_CHANGES and not comment.strip():
        return HumanReviewDecisionRejectionCode.COMMENT_REQUIRED
    return None


def _reject(code: HumanReviewDecisionRejectionCode) -> None:
    raise HumanReviewDecisionRejected(code)


def _validate_review_artifact(review_artifact: KnowledgeChangeReviewArtifact) -> None:
    if type(review_artifact.contract_version) is not str:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.contract_version != REVIEW_CONTRACT_VERSION:
        _reject(HumanReviewDecisionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT)
    if type(review_artifact.status) is not ReviewStatus:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if type(review_artifact.proposal_id) is not str or not _PROPOSAL_ID_RE.fullmatch(
        review_artifact.proposal_id
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if (
        type(review_artifact.review_artifact_identity) is not str
        or not _REVIEW_ID_RE.fullmatch(review_artifact.review_artifact_identity)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.change_identity is not None and (
        type(review_artifact.change_identity) is not str
        or not _CHANGE_ID_RE.fullmatch(review_artifact.change_identity)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if review_artifact.status is ReviewStatus.BLOCKED and review_artifact.change_identity is not None:
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)
    if (
        type(review_artifact.observed_vault_revision) is not str
        or not _REVISION_RE.fullmatch(review_artifact.observed_vault_revision)
    ):
        _reject(HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT)


def _validate_binding_text(value: Any, pattern: re.Pattern[str]) -> None:
    if type(value) is not str or not pattern.fullmatch(value):
        _reject(HumanReviewDecisionRejectionCode.INVALID_BINDING_VALUE)


def _coerce_decision(value: HumanReviewDecisionValue | str) -> HumanReviewDecisionValue:
    if type(value) is HumanReviewDecisionValue:
        return value
    if type(value) is str:
        try:
            return HumanReviewDecisionValue(value)
        except ValueError:
            pass
    _reject(HumanReviewDecisionRejectionCode.UNSUPPORTED_DECISION)
    raise AssertionError("unreachable")


def create_human_review_decision(
    review_artifact: KnowledgeChangeReviewArtifact,
    *,
    expected_proposal_id: str,
    expected_review_artifact_identity: str,
    expected_change_identity: str | None,
    expected_observed_vault_revision: str,
    current_observed_vault_revision: str,
    decision: HumanReviewDecisionValue | str,
    comment: str,
    actor: HumanReviewerMetadata,
) -> HumanReviewDecision:
    """Validate exact e9b binding and return an immutable HARD STOP artifact."""
    if type(review_artifact) is not KnowledgeChangeReviewArtifact:
        _reject(HumanReviewDecisionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)
    _validate_review_artifact(review_artifact)

    _validate_binding_text(expected_proposal_id, _PROPOSAL_ID_RE)
    _validate_binding_text(expected_review_artifact_identity, _REVIEW_ID_RE)
    if expected_change_identity is not None:
        _validate_binding_text(expected_change_identity, _CHANGE_ID_RE)
    _validate_binding_text(expected_observed_vault_revision, _REVISION_RE)
    _validate_binding_text(current_observed_vault_revision, _REVISION_RE)

    if expected_proposal_id != review_artifact.proposal_id:
        _reject(HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH)
    if expected_review_artifact_identity != review_artifact.review_artifact_identity:
        _reject(HumanReviewDecisionRejectionCode.REVIEW_ARTIFACT_IDENTITY_MISMATCH)
    if expected_change_identity != review_artifact.change_identity:
        _reject(HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH)
    if expected_observed_vault_revision != review_artifact.observed_vault_revision:
        _reject(HumanReviewDecisionRejectionCode.OBSERVED_VAULT_REVISION_MISMATCH)
    if current_observed_vault_revision != review_artifact.observed_vault_revision:
        _reject(HumanReviewDecisionRejectionCode.STALE_CURRENT_VAULT_REVISION)

    selected_decision = _coerce_decision(decision)
    decision_error = _decision_rule_error(
        review_artifact.status,
        review_artifact.change_identity,
        selected_decision,
    )
    if decision_error is not None:
        _reject(decision_error)

    comment_error = _comment_error(comment, selected_decision)
    if comment_error is not None:
        _reject(comment_error)
    if type(actor) is not HumanReviewerMetadata:
        _reject(HumanReviewDecisionRejectionCode.ACTOR_TYPE_INVALID)

    boundary = _authority_boundary_values()
    decision_identity = _compute_decision_identity(
        contract_version=CONTRACT_VERSION,
        review_contract_version=REVIEW_CONTRACT_VERSION,
        review_status=review_artifact.status,
        proposal_id=review_artifact.proposal_id,
        review_artifact_identity=review_artifact.review_artifact_identity,
        change_identity=review_artifact.change_identity,
        observed_vault_revision=review_artifact.observed_vault_revision,
        decision=selected_decision,
        comment=comment,
        actor=actor,
        boundary=boundary,
    )
    boundary_values = dict(boundary)
    return HumanReviewDecision(
        contract_version=CONTRACT_VERSION,
        review_contract_version=REVIEW_CONTRACT_VERSION,
        review_status=review_artifact.status,
        proposal_id=review_artifact.proposal_id,
        review_artifact_identity=review_artifact.review_artifact_identity,
        change_identity=review_artifact.change_identity,
        observed_vault_revision=review_artifact.observed_vault_revision,
        decision=selected_decision,
        comment=comment,
        actor=actor,
        decision_identity=decision_identity,
        hard_stop=boundary_values["hard_stop"],
        review_decision_only=boundary_values["review_decision_only"],
        actor_metadata_evidence_only=boundary_values["actor_metadata_evidence_only"],
        human_identity_authenticated=boundary_values["human_identity_authenticated"],
        grants_write_authority=boundary_values["grants_write_authority"],
        grants_vault_write_authority=boundary_values["grants_vault_write_authority"],
        grants_persistence_authority=boundary_values["grants_persistence_authority"],
        grants_publication_authority=boundary_values["grants_publication_authority"],
        grants_merge_authority=boundary_values["grants_merge_authority"],
        grants_rebase_authority=boundary_values["grants_rebase_authority"],
        grants_execution_authority=boundary_values["grants_execution_authority"],
        grants_policy_authority=boundary_values["grants_policy_authority"],
        grants_model_gateway_authority=boundary_values["grants_model_gateway_authority"],
        grants_tauri_frontend_authority=boundary_values["grants_tauri_frontend_authority"],
        grants_automatic_approval_authority=boundary_values[
            "grants_automatic_approval_authority"
        ],
    )


__all__ = [
    "CONTRACT_VERSION",
    "REVIEW_CONTRACT_VERSION",
    "IDENTITY_VERSION",
    "IDENTITY_DOMAIN",
    "DECISION_ID_PREFIX",
    "MAX_COMMENT_CHARS",
    "MAX_COMMENT_UTF8_BYTES",
    "MAX_ACTOR_IDENTIFIER_CHARS",
    "MAX_ACTOR_IDENTIFIER_UTF8_BYTES",
    "MAX_ACTOR_DISPLAY_NAME_CHARS",
    "MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES",
    "MAX_ACTOR_SOURCE_CHARS",
    "MAX_ACTOR_SOURCE_UTF8_BYTES",
    "HumanReviewDecisionValue",
    "HumanReviewDecisionRejectionCode",
    "HumanReviewDecisionRejected",
    "HumanReviewerMetadata",
    "HumanReviewDecision",
    "create_human_review_decision",
]
````

### ПУТЬ: modules/knowledge_change_review_ru.py (1647 строк, 65372 байт)

````python
"""Knowledge Review Layer — v6.84.5.1e9b.

Deterministically binds one e9a KnowledgeChangeProposal to its exact
ValidationResult, verifies caller-supplied in-memory target snapshots, performs
bounded operation-specific conflict analysis, and returns an immutable review
artifact. The module has no write, approval, publication, persistence, model,
network, subprocess, shell, browser, Tauri, or frontend path.

Contract: localcomet.knowledge-change-review/1.0
Lifecycle: proposal -> exact validation binding -> review artifact -> hard stop
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import difflib
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

from modules.knowledge_change_proposal_ru import (
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposedNoteContent,
    ValidationOutcome,
    ValidationResult,
    compute_proposal_content_hash,
    compute_proposal_instance_id,
    create_proposal_from_untrusted,
)


CONTRACT_VERSION: Final[str] = "localcomet.knowledge-change-review/1.0"
SEMANTIC_NORMALIZATION_VERSION: Final[str] = "semantic-normalization/v1"
IDENTITY_VERSION: Final[str] = "1.0"
CHANGE_ID_PREFIX: Final[str] = "kchange:"
REVIEW_ID_PREFIX: Final[str] = "kreview:"
TRUNCATION_MARKER: Final[str] = "... REVIEW_DIFF_PREVIEW_TRUNCATED ..."

MAX_SOURCE_BYTES: Final[int] = 1_048_576
MAX_TRUSTED_TEXT_CHARS: Final[int] = 1_048_576
MAX_PROPOSED_CONTENT_BYTES: Final[int] = 1_048_576
MAX_STABLE_IDS: Final[int] = 4_096
MAX_EVIDENCE_REFERENCES: Final[int] = 32
MAX_PROVENANCE_ENTRIES: Final[int] = 128
MAX_FINDINGS: Final[int] = 16
MAX_FINDING_MESSAGE_CHARS: Final[int] = 1_024
MAX_FINDING_DETAIL_ITEMS: Final[int] = 16
MAX_FINDING_DETAIL_CHARS: Final[int] = 512
MAX_FULL_DIFF_BYTES: Final[int] = 4_194_304
MAX_PREVIEW_BYTES: Final[int] = 32_768
MAX_PREVIEW_LINES: Final[int] = 400
MAX_PATH_LENGTH: Final[int] = 512
MAX_STABLE_ID_LENGTH: Final[int] = 128
MAX_PROPOSED_SNAPSHOT_BYTES: Final[int] = 1_048_576
MAX_METADATA_PREVIEW_VALUE_BYTES: Final[int] = 1_024
MAX_VALIDATION_SNAPSHOT_DEPTH: Final[int] = 24
MAX_VALIDATION_SNAPSHOT_NODES: Final[int] = 4_096
MAX_VALIDATION_MAPPING_ENTRIES: Final[int] = 256
MAX_VALIDATION_SEQUENCE_ENTRIES: Final[int] = 256
MAX_VALIDATION_KEY_LENGTH: Final[int] = 256
MAX_VALIDATION_STRING_LENGTH: Final[int] = 8_192

_SHA256_VALUE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REVISION_RE = _SHA256_VALUE_RE
_STABLE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class ReviewStatus(str, Enum):
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ConflictSeverity(str, Enum):
    BLOCKING = "BLOCKING"
    REVIEW = "REVIEW"


class ConflictCode(str, Enum):
    VALIDATION_RESULT_PROPOSAL_MISMATCH = "VALIDATION_RESULT_PROPOSAL_MISMATCH"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    STALE_VAULT_REVISION = "STALE_VAULT_REVISION"
    TARGET_MISSING = "TARGET_MISSING"
    TARGET_CHANGED_SINCE_PROPOSAL = "TARGET_CHANGED_SINCE_PROPOSAL"
    TARGET_STATE_COMPARISON_UNAVAILABLE = "TARGET_STATE_COMPARISON_UNAVAILABLE"
    TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL = "TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL"
    UNVERIFIED_TEXT_INPUT = "UNVERIFIED_TEXT_INPUT"
    STABLE_ID_COLLISION = "STABLE_ID_COLLISION"
    PROPOSED_CONTENT_ALREADY_IDENTICAL = "PROPOSED_CONTENT_ALREADY_IDENTICAL"
    PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT = "PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT"


_FINDING_ORDER: Final[Mapping[ConflictCode, int]] = MappingProxyType({
    ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH: 0,
    ConflictCode.UNSUPPORTED_OPERATION: 1,
    ConflictCode.STALE_VAULT_REVISION: 2,
    ConflictCode.TARGET_MISSING: 3,
    ConflictCode.UNVERIFIED_TEXT_INPUT: 4,
    ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL: 5,
    ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL: 6,
    ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE: 7,
    ConflictCode.STABLE_ID_COLLISION: 8,
    ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL: 9,
    ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT: 10,
})


_CANONICAL_VALUE_TAGS: Final[frozenset[str]] = frozenset({
    "null",
    "bool",
    "int",
    "string",
    "mapping",
    "sequence",
})

_PROPOSED_CONTENT_FIELD_ORDER: Final[tuple[str, ...]] = (
    "title",
    "body_text",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "canonical",
    "canonical_scope",
    "aliases",
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "updated",
    "last_reviewed",
    "verified_at",
)


@dataclass(frozen=True, slots=True)
class FrozenCanonicalValue:
    """Type-tagged immutable canonical value used for validation snapshots."""

    type_tag: str
    scalar_value: str | int | bool | None = None
    mapping_items: tuple[tuple[str, "FrozenCanonicalValue"], ...] = ()
    sequence_items: tuple["FrozenCanonicalValue", ...] = ()

    def __post_init__(self) -> None:
        if self.type_tag not in _CANONICAL_VALUE_TAGS:
            raise ValueError("unsupported canonical value type tag")
        if not isinstance(self.mapping_items, tuple) or not isinstance(self.sequence_items, tuple):
            raise ValueError("canonical value collections must be immutable tuples")

        if self.type_tag == "mapping":
            if self.scalar_value is not None or self.sequence_items:
                raise ValueError("mapping canonical value has invalid payload channels")
            previous_key: str | None = None
            for item in self.mapping_items:
                if not isinstance(item, tuple) or len(item) != 2:
                    raise ValueError("mapping canonical items must be key/value tuples")
                key, child = item
                if not isinstance(key, str) or not isinstance(child, FrozenCanonicalValue):
                    raise ValueError("mapping canonical item has invalid type")
                if previous_key is not None and key <= previous_key:
                    raise ValueError("mapping canonical keys must be unique and sorted")
                previous_key = key
            return

        if self.type_tag == "sequence":
            if self.scalar_value is not None or self.mapping_items:
                raise ValueError("sequence canonical value has invalid payload channels")
            if not all(isinstance(item, FrozenCanonicalValue) for item in self.sequence_items):
                raise ValueError("sequence canonical items must be canonical values")
            return

        if self.mapping_items or self.sequence_items:
            raise ValueError("scalar canonical value must not contain child items")
        if self.type_tag == "null" and self.scalar_value is not None:
            raise ValueError("null canonical value must contain None")
        if self.type_tag == "bool" and type(self.scalar_value) is not bool:
            raise ValueError("bool canonical value must contain bool")
        if self.type_tag == "int" and type(self.scalar_value) is not int:
            raise ValueError("int canonical value must contain int")
        if self.type_tag == "string" and type(self.scalar_value) is not str:
            raise ValueError("string canonical value must contain string")

    def identity_payload(self) -> dict[str, Any]:
        if self.type_tag == "mapping":
            return {
                "type": "mapping",
                "items": [
                    [key, child.identity_payload()]
                    for key, child in self.mapping_items
                ],
            }
        if self.type_tag == "sequence":
            return {
                "type": "sequence",
                "items": [child.identity_payload() for child in self.sequence_items],
            }
        if self.type_tag == "null":
            return {"type": "null"}
        return {"type": self.type_tag, "value": self.scalar_value}


@dataclass(frozen=True, slots=True)
class ProposedContentSnapshot:
    """Frozen review projection of every real e9a ProposedNoteContent field."""

    title: str
    body_text: str
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool
    canonical_scope: str | None
    aliases: tuple[str, ...]
    releases: tuple[str, ...]
    source_paths: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    updated: str
    last_reviewed: str
    verified_at: str | None

    def __post_init__(self) -> None:
        string_fields = (
            "title",
            "body_text",
            "type",
            "status",
            "knowledge_layer",
            "evidence_class",
            "authority",
            "updated",
            "last_reviewed",
        )
        for name in string_fields:
            if type(getattr(self, name)) is not str:
                raise ValueError(f"proposed content snapshot {name} must be string")
        if type(self.canonical) is not bool:
            raise ValueError("proposed content snapshot canonical must be bool")
        for name in ("canonical_scope", "verified_at"):
            value = getattr(self, name)
            if value is not None and type(value) is not str:
                raise ValueError(f"proposed content snapshot {name} must be string or None")
        for name in (
            "aliases",
            "releases",
            "source_paths",
            "evidence_refs",
            "supersedes",
            "superseded_by",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(type(item) is str for item in value):
                raise ValueError(f"proposed content snapshot {name} must be tuple[str, ...]")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body_text": self.body_text,
            "type": self.type,
            "status": self.status,
            "knowledge_layer": self.knowledge_layer,
            "evidence_class": self.evidence_class,
            "authority": self.authority,
            "canonical": self.canonical,
            "canonical_scope": self.canonical_scope,
            "aliases": list(self.aliases),
            "releases": list(self.releases),
            "source_paths": list(self.source_paths),
            "evidence_refs": list(self.evidence_refs),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "updated": self.updated,
            "last_reviewed": self.last_reviewed,
            "verified_at": self.verified_at,
        }

    def metadata_items(self) -> tuple[tuple[str, Any], ...]:
        payload = self.identity_payload()
        return tuple(
            (name, payload[name])
            for name in _PROPOSED_CONTENT_FIELD_ORDER
            if name != "body_text"
        )


@dataclass(frozen=True, slots=True)
class ConflictFinding:
    code: ConflictCode
    severity: ConflictSeverity
    message: str
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, ConflictCode):
            object.__setattr__(self, "code", ConflictCode(self.code))
        if not isinstance(self.severity, ConflictSeverity):
            object.__setattr__(self, "severity", ConflictSeverity(self.severity))
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("finding message must be a non-empty string")
        if len(self.message) > MAX_FINDING_MESSAGE_CHARS:
            raise ValueError("finding message exceeds bound")
        normalized_details = tuple(self.details)
        if len(normalized_details) > MAX_FINDING_DETAIL_ITEMS:
            raise ValueError("finding details exceed bound")
        checked: list[tuple[str, str]] = []
        for item in normalized_details:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("finding details must be key/value tuples")
            key, value = item
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("finding detail key and value must be strings")
            if not key or len(key) > MAX_FINDING_DETAIL_CHARS or len(value) > MAX_FINDING_DETAIL_CHARS:
                raise ValueError("finding detail exceeds bound")
            checked.append((key, value))
        object.__setattr__(self, "details", tuple(sorted(checked)))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "details": [[key, value] for key, value in self.details],
        }


@dataclass(frozen=True, slots=True)
class LineEndingProfile:
    crlf_count: int
    lf_count: int
    cr_count: int
    terminal_newline: bool

    def __post_init__(self) -> None:
        for value in (self.crlf_count, self.lf_count, self.cr_count):
            if not isinstance(value, int) or value < 0:
                raise ValueError("line-ending counts must be non-negative integers")
        if not isinstance(self.terminal_newline, bool):
            raise ValueError("terminal_newline must be bool")

    @property
    def label(self) -> str:
        present = []
        if self.crlf_count:
            present.append("CRLF")
        if self.lf_count:
            present.append("LF")
        if self.cr_count:
            present.append("CR")
        if not present:
            present.append("NONE")
        return "+".join(present)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "crlf_count": self.crlf_count,
            "lf_count": self.lf_count,
            "cr_count": self.cr_count,
            "terminal_newline": self.terminal_newline,
        }


@dataclass(frozen=True, slots=True)
class RepresentationDelta:
    before_present: bool
    after_present: bool
    before_line_endings: LineEndingProfile | None
    after_line_endings: LineEndingProfile
    terminal_newline_changed: bool
    after_source_bytes_known: bool
    source_bytes_changed_text_identical: bool
    raw_text_changed_semantic_equal: bool
    semantic_content_changed: bool
    identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.before_present, bool) or not isinstance(self.after_present, bool):
            raise ValueError("representation presence flags must be bool")
        if self.before_present and not isinstance(self.before_line_endings, LineEndingProfile):
            raise ValueError("before line-ending profile required when before is present")
        if not self.before_present and self.before_line_endings is not None:
            raise ValueError("before line-ending profile forbidden when before is absent")
        if not isinstance(self.after_line_endings, LineEndingProfile):
            raise ValueError("after line-ending profile required")
        if not isinstance(self.after_source_bytes_known, bool):
            raise ValueError("after_source_bytes_known must be bool")
        if not _SHA256_VALUE_RE.fullmatch(self.identity):
            raise ValueError("representation identity must be sha256:<64-hex>")


@dataclass(frozen=True, slots=True)
class TrustedTargetSnapshot:
    source_bytes: bytes
    trusted_text: str
    source_relative_path: str
    target_stable_id: str
    captured_vault_revision: str
    source_byte_hash: str
    text_raw_hash: str
    semantic_text_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_bytes, bytes):
            raise ValueError("source_bytes must be immutable bytes")
        if not isinstance(self.trusted_text, str):
            raise ValueError("trusted_text must be string")
        for name in (
            "source_relative_path",
            "target_stable_id",
            "captured_vault_revision",
            "source_byte_hash",
            "text_raw_hash",
            "semantic_text_hash",
        ):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be string")


@dataclass(frozen=True, slots=True)
class CurrentKnowledgeState:
    observed_vault_revision: str
    current_stable_ids: frozenset[str] | set[str] | tuple[str, ...] | list[str]
    current_target: TrustedTargetSnapshot | None = None
    baseline_target: TrustedTargetSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.observed_vault_revision, str) or not _REVISION_RE.fullmatch(
            self.observed_vault_revision
        ):
            raise ValueError("observed_vault_revision must be sha256:<64-hex>")
        if type(self.current_stable_ids) not in (frozenset, set, tuple, list):
            raise ValueError(
                "current_stable_ids must be list, tuple, set, or frozenset of strings"
            )
        try:
            stable_ids = frozenset(self.current_stable_ids)
        except TypeError as exc:
            raise ValueError("current_stable_ids entries must be strings") from exc
        if len(stable_ids) > MAX_STABLE_IDS:
            raise ValueError("current_stable_ids exceeds hard bound")
        for stable_id in stable_ids:
            if type(stable_id) is not str:
                raise ValueError("current_stable_ids entries must be strings")
            _validate_stable_id(stable_id)
        object.__setattr__(self, "current_stable_ids", stable_ids)
        if self.current_target is not None and not isinstance(self.current_target, TrustedTargetSnapshot):
            raise ValueError("current_target must be TrustedTargetSnapshot or None")
        if self.baseline_target is not None and not isinstance(self.baseline_target, TrustedTargetSnapshot):
            raise ValueError("baseline_target must be TrustedTargetSnapshot or None")


@dataclass(frozen=True, slots=True)
class KnowledgeChangeReviewArtifact:
    contract_version: str
    status: ReviewStatus
    proposal_id: str
    proposal_content_hash: str
    operation: str
    target_stable_id: str
    expected_vault_revision: str
    observed_vault_revision: str
    validation_outcome: str
    validation_snapshot: FrozenCanonicalValue
    source_validation_findings: tuple[tuple[str, str], ...]
    stable_id_set_hash: str
    proposed_content_snapshot: ProposedContentSnapshot
    findings: tuple[ConflictFinding, ...]
    before_source_byte_hash: str | None
    before_text_raw_hash: str | None
    before_semantic_text_hash: str | None
    proposed_text_raw_hash: str | None
    proposed_semantic_text_hash: str | None
    deterministic_text_diff: str | None
    deterministic_text_diff_hash: str | None
    representation_delta: RepresentationDelta | None
    change_identity: str | None
    review_artifact_identity: str
    human_review_preview: str

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("review artifact contract version mismatch")
        if not isinstance(self.status, ReviewStatus):
            object.__setattr__(self, "status", ReviewStatus(self.status))
        if not isinstance(self.findings, tuple):
            raise ValueError("findings must be immutable tuple")
        if not isinstance(self.source_validation_findings, tuple):
            raise ValueError("source_validation_findings must be immutable tuple")
        if not isinstance(self.validation_snapshot, FrozenCanonicalValue):
            raise ValueError("validation_snapshot must be FrozenCanonicalValue")
        if not isinstance(self.proposed_content_snapshot, ProposedContentSnapshot):
            raise ValueError("proposed_content_snapshot must be ProposedContentSnapshot")
        if not _SHA256_VALUE_RE.fullmatch(self.stable_id_set_hash):
            raise ValueError("stable_id_set_hash invalid")
        if not re.fullmatch(r"kreview:[0-9a-f]{64}", self.review_artifact_identity):
            raise ValueError("review_artifact_identity invalid")
        if self.change_identity is not None and not re.fullmatch(r"kchange:[0-9a-f]{64}", self.change_identity):
            raise ValueError("change_identity invalid")
        if any(
            finding.severity is ConflictSeverity.BLOCKING
            for finding in self.findings
        ) and any(
            value is not None
            for value in (
                self.deterministic_text_diff,
                self.deterministic_text_diff_hash,
                self.representation_delta,
                self.change_identity,
            )
        ):
            raise ValueError("blocking artifact must not expose normal change material")
        preview_bytes = self.human_review_preview.encode("utf-8")
        if len(preview_bytes) > MAX_PREVIEW_BYTES:
            raise ValueError("human_review_preview exceeds byte bound")
        if len(self.human_review_preview.splitlines()) > MAX_PREVIEW_LINES:
            raise ValueError("human_review_preview exceeds line bound")


@dataclass(frozen=True, slots=True)
class _SnapshotVerification:
    valid: bool
    errors: tuple[str, ...]
    decoded_text: str | None


@dataclass(slots=True)
class _SnapshotBudget:
    nodes: int = 0


class _CanonicalSnapshotError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def semantic_normalize_v1(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("semantic_normalize_v1 requires string")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compute_source_byte_hash(source_bytes: bytes) -> str:
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    return _sha256(source_bytes)


def compute_text_raw_hash(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be string")
    return _sha256(text.encode("utf-8"))


def compute_semantic_text_hash(text: str) -> str:
    return _sha256(semantic_normalize_v1(text).encode("utf-8"))


def create_trusted_target_snapshot(
    *,
    source_bytes: bytes,
    source_relative_path: str,
    target_stable_id: str,
    captured_vault_revision: str,
) -> TrustedTargetSnapshot:
    if not isinstance(source_bytes, bytes):
        raise ValueError("source_bytes must be immutable bytes")
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise ValueError("source_bytes exceeds hard bound")
    try:
        trusted_text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("source_bytes are not strict UTF-8") from exc
    if len(trusted_text) > MAX_TRUSTED_TEXT_CHARS:
        raise ValueError("trusted_text exceeds hard bound")
    _validate_relative_path(source_relative_path)
    _validate_stable_id(target_stable_id)
    _validate_revision(captured_vault_revision)
    return TrustedTargetSnapshot(
        source_bytes=source_bytes,
        trusted_text=trusted_text,
        source_relative_path=source_relative_path,
        target_stable_id=target_stable_id,
        captured_vault_revision=captured_vault_revision,
        source_byte_hash=compute_source_byte_hash(source_bytes),
        text_raw_hash=compute_text_raw_hash(trusted_text),
        semantic_text_hash=compute_semantic_text_hash(trusted_text),
    )


def analyze_review(
    proposal: KnowledgeChangeProposal,
    validation_result: ValidationResult,
    current_state: CurrentKnowledgeState,
) -> KnowledgeChangeReviewArtifact:
    """Return an immutable deterministic review artifact and perform no side effects."""
    if not isinstance(proposal, KnowledgeChangeProposal):
        raise TypeError("proposal must be the real e9a KnowledgeChangeProposal")
    if not isinstance(validation_result, ValidationResult):
        raise TypeError("validation_result must be the real e9a ValidationResult")
    if not isinstance(current_state, CurrentKnowledgeState):
        raise TypeError("current_state must be CurrentKnowledgeState")
    if proposal.proposed_content is None:
        raise ValueError("supported e9b operations require proposed_content")

    proposed_snapshot = _snapshot_proposed_content(proposal.proposed_content)
    _validate_proposal_bounds(proposal, proposed_snapshot)
    proposed_text = proposed_snapshot.body_text
    proposed_raw_hash = compute_text_raw_hash(proposed_text)
    proposed_semantic_hash = compute_semantic_text_hash(proposed_text)
    proposal_content_hash = compute_proposal_content_hash(proposal)
    stable_id_set_hash = _stable_id_set_hash(current_state.current_stable_ids)

    findings: list[ConflictFinding] = []
    try:
        validation_snapshot = _snapshot_validation_result(validation_result)
    except _CanonicalSnapshotError as exc:
        validation_snapshot = _validation_snapshot_error_value(exc.code)
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The mutable e9a ValidationResult data could not be safely snapshotted.",
            ("validation_snapshot_error", exc.code),
        ))

    source_validation_findings = tuple(
        (finding.code, finding.severity) for finding in validation_result.findings
    )

    binding_errors = _validation_binding_errors(proposal, validation_result, proposal_content_hash)
    if binding_errors:
        findings.append(_finding(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            ConflictSeverity.BLOCKING,
            "The supplied e9a ValidationResult is not bound to the exact proposal.",
            ("mismatched_fields", ",".join(binding_errors)),
        ))

    if proposal.operation not in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW):
        findings.append(_finding(
            ConflictCode.UNSUPPORTED_OPERATION,
            ConflictSeverity.BLOCKING,
            "The proposal operation is outside the e9b review boundary.",
            ("operation", proposal.operation.value),
        ))

    observed_revision = current_state.observed_vault_revision
    if (
        validation_result.outcome is ValidationOutcome.STALE
        or proposal.expected_vault_revision != observed_revision
        or validation_result.validated_vault_revision != observed_revision
    ):
        findings.append(_finding(
            ConflictCode.STALE_VAULT_REVISION,
            ConflictSeverity.BLOCKING,
            "The proposal or validation result is stale relative to the observed Vault revision.",
            ("expected", proposal.expected_vault_revision),
            ("validated", validation_result.validated_vault_revision),
            ("observed", observed_revision),
        ))

    operation_analysis_allowed = (
        not binding_errors
        and validation_result.outcome is ValidationOutcome.VALID
        and proposal.operation in (ProposalOperation.UPDATE_EXISTING, ProposalOperation.CREATE_NEW)
    )

    before_snapshot: TrustedTargetSnapshot | None = None
    full_diff: str | None = None
    full_diff_hash: str | None = None
    representation_delta: RepresentationDelta | None = None
    change_identity: str | None = None
    before_source_hash: str | None = None
    before_raw_hash: str | None = None
    before_semantic_hash: str | None = None

    if operation_analysis_allowed and proposal.operation is ProposalOperation.UPDATE_EXISTING:
        before_snapshot, operation_findings = _analyze_update_state(proposal, current_state)
        findings.extend(operation_findings)
        if before_snapshot is not None:
            before_source_hash = before_snapshot.source_byte_hash
            before_raw_hash = before_snapshot.text_raw_hash
            before_semantic_hash = before_snapshot.semantic_text_hash
        if before_snapshot is not None and not _has_blocking_finding(findings):
            full_diff, full_diff_hash, representation_delta = _build_change_material(
                stable_id=proposal.target_stable_id,
                before_text=before_snapshot.trusted_text,
                before_source_bytes=before_snapshot.source_bytes,
                after_text=proposed_text,
                create_new=False,
            )
            change_identity = _compute_change_identity(
                proposal=proposal,
                proposal_content_hash=proposal_content_hash,
                proposed_content_snapshot=proposed_snapshot,
                observed_revision=observed_revision,
                stable_id_set_hash=stable_id_set_hash,
                before_snapshot=before_snapshot,
                proposed_raw_hash=proposed_raw_hash,
                proposed_semantic_hash=proposed_semantic_hash,
                full_diff_hash=full_diff_hash,
                representation_identity=representation_delta.identity,
            )

    elif operation_analysis_allowed and proposal.operation is ProposalOperation.CREATE_NEW:
        operation_findings = _analyze_create_state(proposal, current_state)
        findings.extend(operation_findings)
        if not _has_blocking_finding(findings):
            full_diff, full_diff_hash, representation_delta = _build_change_material(
                stable_id=proposal.target_stable_id,
                before_text=None,
                before_source_bytes=None,
                after_text=proposed_text,
                create_new=True,
            )
            change_identity = _compute_change_identity(
                proposal=proposal,
                proposal_content_hash=proposal_content_hash,
                proposed_content_snapshot=proposed_snapshot,
                observed_revision=observed_revision,
                stable_id_set_hash=stable_id_set_hash,
                before_snapshot=None,
                proposed_raw_hash=proposed_raw_hash,
                proposed_semantic_hash=proposed_semantic_hash,
                full_diff_hash=full_diff_hash,
                representation_identity=representation_delta.identity,
            )

    ordered_findings = _order_and_deduplicate_findings(findings)
    status = _derive_status(validation_result.outcome, ordered_findings)
    preview = _build_human_preview(
        proposal=proposal,
        proposed_content_snapshot=proposed_snapshot,
        validation_result=validation_result,
        status=status,
        findings=ordered_findings,
        representation_delta=representation_delta,
        full_diff=full_diff,
    )
    review_identity = _compute_review_identity(
        proposal=proposal,
        proposal_content_hash=proposal_content_hash,
        proposed_content_snapshot=proposed_snapshot,
        validation_snapshot=validation_snapshot,
        status=status,
        observed_revision=observed_revision,
        stable_id_set_hash=stable_id_set_hash,
        findings=ordered_findings,
        before_source_hash=before_source_hash,
        before_raw_hash=before_raw_hash,
        before_semantic_hash=before_semantic_hash,
        proposed_raw_hash=proposed_raw_hash,
        proposed_semantic_hash=proposed_semantic_hash,
        full_diff_hash=full_diff_hash,
        representation_identity=representation_delta.identity if representation_delta else None,
        change_identity=change_identity,
    )

    return KnowledgeChangeReviewArtifact(
        contract_version=CONTRACT_VERSION,
        status=status,
        proposal_id=proposal.proposal_id,
        proposal_content_hash=proposal_content_hash,
        operation=proposal.operation.value,
        target_stable_id=proposal.target_stable_id,
        expected_vault_revision=proposal.expected_vault_revision,
        observed_vault_revision=observed_revision,
        validation_outcome=validation_result.outcome.value,
        validation_snapshot=validation_snapshot,
        source_validation_findings=source_validation_findings,
        stable_id_set_hash=stable_id_set_hash,
        proposed_content_snapshot=proposed_snapshot,
        findings=ordered_findings,
        before_source_byte_hash=before_source_hash,
        before_text_raw_hash=before_raw_hash,
        before_semantic_text_hash=before_semantic_hash,
        proposed_text_raw_hash=proposed_raw_hash,
        proposed_semantic_text_hash=proposed_semantic_hash,
        deterministic_text_diff=full_diff,
        deterministic_text_diff_hash=full_diff_hash,
        representation_delta=representation_delta,
        change_identity=change_identity,
        review_artifact_identity=review_identity,
        human_review_preview=preview,
    )

def _snapshot_proposed_content(content: ProposedNoteContent) -> ProposedContentSnapshot:
    if not isinstance(content, ProposedNoteContent):
        raise TypeError("proposed_content must be the real e9a ProposedNoteContent")
    return ProposedContentSnapshot(
        title=content.title,
        body_text=content.body_text,
        type=content.type,
        status=content.status,
        knowledge_layer=content.knowledge_layer,
        evidence_class=content.evidence_class,
        authority=content.authority,
        canonical=content.canonical,
        canonical_scope=content.canonical_scope,
        aliases=tuple(content.aliases),
        releases=tuple(content.releases),
        source_paths=tuple(content.source_paths),
        evidence_refs=tuple(content.evidence_refs),
        supersedes=tuple(content.supersedes),
        superseded_by=tuple(content.superseded_by),
        updated=content.updated,
        last_reviewed=content.last_reviewed,
        verified_at=content.verified_at,
    )


def _validate_proposal_bounds(
    proposal: KnowledgeChangeProposal,
    proposed_snapshot: ProposedContentSnapshot,
) -> None:
    _validate_stable_id(proposal.target_stable_id)
    _validate_revision(proposal.expected_vault_revision)
    proposed_bytes = proposed_snapshot.body_text.encode("utf-8")
    if len(proposed_bytes) > MAX_PROPOSED_CONTENT_BYTES:
        raise ValueError("proposed body content exceeds hard byte bound")
    snapshot_bytes = _canonical_json_bytes(proposed_snapshot.identity_payload())
    if len(snapshot_bytes) > MAX_PROPOSED_SNAPSHOT_BYTES:
        raise ValueError("proposed structured content exceeds hard byte bound")
    if len(proposal.provenance.evidence_references) > MAX_EVIDENCE_REFERENCES:
        raise ValueError("evidence references exceed hard bound")
    if _count_provenance_entries(proposal.provenance.to_dict()) > MAX_PROVENANCE_ENTRIES:
        raise ValueError("provenance entries exceed hard bound")


def _validation_binding_errors(
    proposal: KnowledgeChangeProposal,
    result: ValidationResult,
    expected_content_hash: str,
) -> tuple[str, ...]:
    comparisons = (
        ("proposal_id", result.proposal_id, proposal.proposal_id, str),
        ("proposal_content_hash", result.proposal_content_hash, expected_content_hash, str),
        ("contract_version", result.contract_version, proposal.contract_version, str),
        ("operation", result.operation, proposal.operation.value, str),
        ("target_stable_id", result.target_stable_id, proposal.target_stable_id, str),
        (
            "expected_vault_revision",
            result.expected_vault_revision,
            proposal.expected_vault_revision,
            str,
        ),
    )
    mismatches = []
    for field_name, actual, expected, expected_type in comparisons:
        if type(actual) is not expected_type or actual != expected:
            mismatches.append(field_name)
    return tuple(mismatches)


def _analyze_update_state(
    proposal: KnowledgeChangeProposal,
    state: CurrentKnowledgeState,
) -> tuple[TrustedTargetSnapshot | None, list[ConflictFinding]]:
    findings: list[ConflictFinding] = []
    if proposal.target_stable_id not in state.current_stable_ids or state.current_target is None:
        findings.append(_finding(
            ConflictCode.TARGET_MISSING,
            ConflictSeverity.BLOCKING,
            "The current target snapshot is missing.",
            ("target_stable_id", proposal.target_stable_id),
        ))
        return None, findings

    current = state.current_target
    current_verification = _verify_snapshot(current)
    current_context_errors = []
    if current.target_stable_id != proposal.target_stable_id:
        current_context_errors.append("current_target_stable_id")
    if current.captured_vault_revision != state.observed_vault_revision:
        current_context_errors.append("current_captured_vault_revision")
    if not current_verification.valid or current_context_errors:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The current target snapshot failed verification.",
            ("errors", ",".join(current_verification.errors + tuple(current_context_errors))),
        ))
        return None, findings

    baseline = state.baseline_target
    if baseline is None:
        findings.append(_finding(
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            ConflictSeverity.REVIEW,
            "No trusted baseline snapshot was supplied; historical target drift is not claimed.",
            ("expected_vault_revision", proposal.expected_vault_revision),
        ))
        return current, findings

    baseline_verification = _verify_snapshot(baseline)
    baseline_context_errors = []
    if baseline.target_stable_id != proposal.target_stable_id:
        baseline_context_errors.append("baseline_target_stable_id")
    if baseline.captured_vault_revision != proposal.expected_vault_revision:
        baseline_context_errors.append("baseline_captured_vault_revision")
    if not baseline_verification.valid or baseline_context_errors:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "The baseline target snapshot failed verification.",
            ("errors", ",".join(baseline_verification.errors + tuple(baseline_context_errors))),
        ))
        return current, findings

    if baseline.source_bytes != current.source_bytes:
        if baseline.trusted_text == current.trusted_text:
            findings.append(_finding(
                ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
                ConflictSeverity.REVIEW,
                "Target source bytes changed while decoded text remained identical.",
                ("baseline_source_byte_hash", baseline.source_byte_hash),
                ("current_source_byte_hash", current.source_byte_hash),
            ))
        else:
            findings.append(_finding(
                ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL,
                ConflictSeverity.BLOCKING,
                "The verified target changed since the proposal baseline.",
                ("baseline_text_raw_hash", baseline.text_raw_hash),
                ("current_text_raw_hash", current.text_raw_hash),
            ))
    return current, findings


def _analyze_create_state(
    proposal: KnowledgeChangeProposal,
    state: CurrentKnowledgeState,
) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    if state.current_target is not None or state.baseline_target is not None:
        findings.append(_finding(
            ConflictCode.UNVERIFIED_TEXT_INPUT,
            ConflictSeverity.BLOCKING,
            "CREATE_NEW must not receive a target preimage or baseline snapshot.",
            ("operation", proposal.operation.value),
        ))
    if proposal.target_stable_id in state.current_stable_ids:
        findings.append(_finding(
            ConflictCode.STABLE_ID_COLLISION,
            ConflictSeverity.BLOCKING,
            "The proposed stable ID already exists in the bounded current state.",
            ("target_stable_id", proposal.target_stable_id),
        ))
    return findings


def _verify_snapshot(snapshot: TrustedTargetSnapshot) -> _SnapshotVerification:
    errors: list[str] = []
    if len(snapshot.source_bytes) > MAX_SOURCE_BYTES:
        errors.append("source_bytes_oversized")
    if len(snapshot.trusted_text) > MAX_TRUSTED_TEXT_CHARS:
        errors.append("trusted_text_oversized")
    try:
        _validate_relative_path(snapshot.source_relative_path)
    except ValueError:
        errors.append("invalid_relative_path")
    try:
        _validate_stable_id(snapshot.target_stable_id)
    except ValueError:
        errors.append("invalid_stable_id")
    try:
        _validate_revision(snapshot.captured_vault_revision)
    except ValueError:
        errors.append("invalid_revision")

    decoded_text: str | None = None
    try:
        decoded_text = snapshot.source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        errors.append("utf8_decode_failure")
    if decoded_text is not None and decoded_text != snapshot.trusted_text:
        errors.append("bytes_text_mismatch")
    if snapshot.source_byte_hash != compute_source_byte_hash(snapshot.source_bytes):
        errors.append("source_byte_hash_mismatch")
    if snapshot.text_raw_hash != compute_text_raw_hash(snapshot.trusted_text):
        errors.append("text_raw_hash_mismatch")
    if snapshot.semantic_text_hash != compute_semantic_text_hash(snapshot.trusted_text):
        errors.append("semantic_text_hash_mismatch")
    for value, label in (
        (snapshot.source_byte_hash, "source_byte_hash_format"),
        (snapshot.text_raw_hash, "text_raw_hash_format"),
        (snapshot.semantic_text_hash, "semantic_text_hash_format"),
    ):
        if not _SHA256_VALUE_RE.fullmatch(value):
            errors.append(label)
    return _SnapshotVerification(not errors, tuple(sorted(set(errors))), decoded_text)


def _build_change_material(
    *,
    stable_id: str,
    before_text: str | None,
    before_source_bytes: bytes | None,
    after_text: str,
    create_new: bool,
) -> tuple[str, str, RepresentationDelta]:
    full_diff = _deterministic_text_diff(
        stable_id,
        before_text,
        after_text,
        create_new=create_new,
    )
    if len(full_diff.encode("utf-8")) > MAX_FULL_DIFF_BYTES:
        raise ValueError("deterministic full diff exceeds hard bound")
    full_diff_hash = _domain_hash(
        "DETERMINISTIC_TEXT_DIFF_HASH",
        IDENTITY_VERSION,
        {"diff": full_diff},
    )
    representation_delta = _representation_delta(
        before_text=before_text,
        before_source_bytes=before_source_bytes,
        after_text=after_text,
        after_source_bytes=None,
    )
    return full_diff, full_diff_hash, representation_delta

def _deterministic_text_diff(
    stable_id: str,
    before_text: str | None,
    after_text: str,
    *,
    create_new: bool,
) -> str:
    before_normalized = semantic_normalize_v1(before_text) if before_text is not None else ""
    after_normalized = semantic_normalize_v1(after_text)
    before_lines = before_normalized.splitlines(keepends=True)
    after_lines = after_normalized.splitlines(keepends=True)
    from_label = "/dev/null" if create_new else f"before-body/{stable_id}"
    to_label = f"after-body/{stable_id}"
    return "".join(difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=from_label,
        tofile=to_label,
        n=3,
        lineterm="\n",
    ))


def _representation_delta(
    *,
    before_text: str | None,
    before_source_bytes: bytes | None,
    after_text: str,
    after_source_bytes: bytes | None,
) -> RepresentationDelta:
    before_profile = _line_ending_profile(before_text) if before_text is not None else None
    after_profile = _line_ending_profile(after_text)
    before_present = before_text is not None
    terminal_changed = (
        before_profile.terminal_newline != after_profile.terminal_newline
        if before_profile is not None
        else False
    )
    after_source_bytes_known = after_source_bytes is not None
    source_bytes_changed_text_identical = (
        before_present
        and before_source_bytes is not None
        and after_source_bytes is not None
        and before_source_bytes != after_source_bytes
        and before_text == after_text
    )
    raw_changed_semantic_equal = (
        before_present
        and before_text != after_text
        and semantic_normalize_v1(before_text or "") == semantic_normalize_v1(after_text)
    )
    semantic_changed = (
        not before_present
        or semantic_normalize_v1(before_text or "") != semantic_normalize_v1(after_text)
    )
    identity_payload = {
        "before_present": before_present,
        "after_present": True,
        "before_line_endings": before_profile.identity_payload() if before_profile else None,
        "after_line_endings": after_profile.identity_payload(),
        "terminal_newline_changed": terminal_changed,
        "after_source_bytes_known": after_source_bytes_known,
        "source_bytes_changed_text_identical": source_bytes_changed_text_identical,
        "raw_text_changed_semantic_equal": raw_changed_semantic_equal,
        "semantic_content_changed": semantic_changed,
    }
    identity = _domain_hash(
        "REPRESENTATION_DELTA_IDENTITY",
        IDENTITY_VERSION,
        identity_payload,
    )
    return RepresentationDelta(
        before_present=before_present,
        after_present=True,
        before_line_endings=before_profile,
        after_line_endings=after_profile,
        terminal_newline_changed=terminal_changed,
        after_source_bytes_known=after_source_bytes_known,
        source_bytes_changed_text_identical=source_bytes_changed_text_identical,
        raw_text_changed_semantic_equal=raw_changed_semantic_equal,
        semantic_content_changed=semantic_changed,
        identity=identity,
    )


def _line_ending_profile(text: str) -> LineEndingProfile:
    crlf_count = text.count("\r\n")
    without_crlf = text.replace("\r\n", "")
    lf_count = without_crlf.count("\n")
    cr_count = without_crlf.count("\r")
    return LineEndingProfile(
        crlf_count=crlf_count,
        lf_count=lf_count,
        cr_count=cr_count,
        terminal_newline=text.endswith("\n") or text.endswith("\r"),
    )


def _compute_change_identity(
    *,
    proposal: KnowledgeChangeProposal,
    proposal_content_hash: str,
    proposed_content_snapshot: ProposedContentSnapshot,
    observed_revision: str,
    stable_id_set_hash: str,
    before_snapshot: TrustedTargetSnapshot | None,
    proposed_raw_hash: str | None,
    proposed_semantic_hash: str | None,
    full_diff_hash: str,
    representation_identity: str,
) -> str:
    payload = {
        "proposal_id": proposal.proposal_id,
        "proposal_content_hash": proposal_content_hash,
        "proposed_content_snapshot": proposed_content_snapshot.identity_payload(),
        "operation": proposal.operation.value,
        "target_stable_id": proposal.target_stable_id,
        "expected_vault_revision": proposal.expected_vault_revision,
        "observed_vault_revision": observed_revision,
        "stable_id_set_hash": stable_id_set_hash,
        "before": {
            "source_relative_path": before_snapshot.source_relative_path,
            "source_byte_hash": before_snapshot.source_byte_hash,
            "text_raw_hash": before_snapshot.text_raw_hash,
            "semantic_text_hash": before_snapshot.semantic_text_hash,
            "captured_vault_revision": before_snapshot.captured_vault_revision,
        } if before_snapshot else None,
        "after": {
            "text_raw_hash": proposed_raw_hash,
            "semantic_text_hash": proposed_semantic_hash,
        },
        "deterministic_text_diff_hash": full_diff_hash,
        "representation_delta_identity": representation_identity,
    }
    return CHANGE_ID_PREFIX + _domain_digest("CHANGE_IDENTITY", IDENTITY_VERSION, payload)


def _compute_review_identity(
    *,
    proposal: KnowledgeChangeProposal,
    proposal_content_hash: str,
    proposed_content_snapshot: ProposedContentSnapshot,
    validation_snapshot: FrozenCanonicalValue,
    status: ReviewStatus,
    observed_revision: str,
    stable_id_set_hash: str,
    findings: tuple[ConflictFinding, ...],
    before_source_hash: str | None,
    before_raw_hash: str | None,
    before_semantic_hash: str | None,
    proposed_raw_hash: str | None,
    proposed_semantic_hash: str | None,
    full_diff_hash: str | None,
    representation_identity: str | None,
    change_identity: str | None,
) -> str:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": status.value,
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "proposal_content_hash": proposal_content_hash,
            "proposed_content_snapshot": proposed_content_snapshot.identity_payload(),
            "operation": proposal.operation.value,
            "target_stable_id": proposal.target_stable_id,
            "expected_vault_revision": proposal.expected_vault_revision,
        },
        "validation_snapshot": validation_snapshot.identity_payload(),
        "observed_vault_revision": observed_revision,
        "stable_id_set_hash": stable_id_set_hash,
        "findings": [finding.identity_payload() for finding in findings],
        "before": {
            "source_byte_hash": before_source_hash,
            "text_raw_hash": before_raw_hash,
            "semantic_text_hash": before_semantic_hash,
        },
        "proposed": {
            "text_raw_hash": proposed_raw_hash,
            "semantic_text_hash": proposed_semantic_hash,
        },
        "deterministic_text_diff_hash": full_diff_hash,
        "representation_delta_identity": representation_identity,
        "change_identity": change_identity,
    }
    return REVIEW_ID_PREFIX + _domain_digest("REVIEW_ARTIFACT_IDENTITY", IDENTITY_VERSION, payload)


def _snapshot_validation_result(result: ValidationResult) -> FrozenCanonicalValue:
    payload = {
        "outcome": result.outcome.value,
        "proposal_id": result.proposal_id,
        "proposal_content_hash": result.proposal_content_hash,
        "contract_version": result.contract_version,
        "operation": result.operation,
        "target_stable_id": result.target_stable_id,
        "expected_vault_revision": result.expected_vault_revision,
        "validated_vault_revision": result.validated_vault_revision,
        "findings": [
            {"code": item.code, "severity": item.severity}
            for item in result.findings
        ],
        "provenance_summary": result.provenance_summary,
        "evidence_reference_count": result.evidence_reference_count,
    }
    return _freeze_canonical_value(payload)


def _validation_snapshot_error_value(error_code: str) -> FrozenCanonicalValue:
    return FrozenCanonicalValue(
        type_tag="mapping",
        mapping_items=(
            (
                "snapshot_error",
                FrozenCanonicalValue(type_tag="string", scalar_value=error_code),
            ),
            (
                "snapshot_valid",
                FrozenCanonicalValue(type_tag="bool", scalar_value=False),
            ),
        ),
    )


def _freeze_canonical_value(
    value: Any,
    *,
    depth: int = 0,
    active_container_ids: set[int] | None = None,
    budget: _SnapshotBudget | None = None,
) -> FrozenCanonicalValue:
    if active_container_ids is None:
        active_container_ids = set()
    if budget is None:
        budget = _SnapshotBudget()
    if depth > MAX_VALIDATION_SNAPSHOT_DEPTH:
        raise _CanonicalSnapshotError("maximum_depth_exceeded")

    budget.nodes += 1
    if budget.nodes > MAX_VALIDATION_SNAPSHOT_NODES:
        raise _CanonicalSnapshotError("maximum_total_nodes_exceeded")

    if value is None:
        return FrozenCanonicalValue(type_tag="null")
    if type(value) is bool:
        return FrozenCanonicalValue(type_tag="bool", scalar_value=value)
    if type(value) is int:
        return FrozenCanonicalValue(type_tag="int", scalar_value=value)
    if type(value) is str:
        if len(value) > MAX_VALIDATION_STRING_LENGTH:
            raise _CanonicalSnapshotError("maximum_string_value_length_exceeded")
        return FrozenCanonicalValue(type_tag="string", scalar_value=value)

    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_container_ids:
            raise _CanonicalSnapshotError("cycle_detected")
        try:
            entry_count = len(value)
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        if entry_count > MAX_VALIDATION_MAPPING_ENTRIES:
            raise _CanonicalSnapshotError("maximum_mapping_entries_exceeded")
        try:
            keys = list(value.keys())
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        for key in keys:
            if type(key) is not str:
                raise _CanonicalSnapshotError("mapping_key_not_string")
            if len(key) > MAX_VALIDATION_KEY_LENGTH:
                raise _CanonicalSnapshotError("maximum_mapping_key_length_exceeded")
        keys.sort()
        active_container_ids.add(container_id)
        try:
            items = tuple(
                (
                    key,
                    _freeze_canonical_value(
                        value[key],
                        depth=depth + 1,
                        active_container_ids=active_container_ids,
                        budget=budget,
                    ),
                )
                for key in keys
            )
        except _CanonicalSnapshotError:
            raise
        except Exception as exc:
            raise _CanonicalSnapshotError("mapping_access_failure") from exc
        finally:
            active_container_ids.remove(container_id)
        return FrozenCanonicalValue(type_tag="mapping", mapping_items=items)

    if type(value) in (list, tuple):
        container_id = id(value)
        if container_id in active_container_ids:
            raise _CanonicalSnapshotError("cycle_detected")
        if len(value) > MAX_VALIDATION_SEQUENCE_ENTRIES:
            raise _CanonicalSnapshotError("maximum_sequence_entries_exceeded")
        active_container_ids.add(container_id)
        try:
            items = tuple(
                _freeze_canonical_value(
                    item,
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    budget=budget,
                )
                for item in value
            )
        finally:
            active_container_ids.remove(container_id)
        return FrozenCanonicalValue(type_tag="sequence", sequence_items=items)

    raise _CanonicalSnapshotError("unsupported_value_type")


def _has_blocking_finding(findings: Sequence[ConflictFinding]) -> bool:
    return any(
        finding.severity is ConflictSeverity.BLOCKING
        for finding in findings
    )

def _derive_status(
    validation_outcome: ValidationOutcome,
    findings: tuple[ConflictFinding, ...],
) -> ReviewStatus:
    if validation_outcome is not ValidationOutcome.VALID:
        return ReviewStatus.BLOCKED
    if any(finding.severity is ConflictSeverity.BLOCKING for finding in findings):
        return ReviewStatus.BLOCKED
    if findings:
        return ReviewStatus.REVIEW_REQUIRED
    return ReviewStatus.CLEAR


def _order_and_deduplicate_findings(
    findings: Sequence[ConflictFinding],
) -> tuple[ConflictFinding, ...]:
    by_code: dict[ConflictCode, ConflictFinding] = {}
    for finding in findings:
        existing = by_code.get(finding.code)
        if existing is None:
            by_code[finding.code] = finding
            continue
        if (
            finding.severity is ConflictSeverity.BLOCKING
            and existing.severity is not ConflictSeverity.BLOCKING
        ):
            by_code[finding.code] = finding
        elif finding.severity is existing.severity and finding.details < existing.details:
            by_code[finding.code] = finding
    ordered = tuple(sorted(by_code.values(), key=lambda item: _FINDING_ORDER[item.code]))
    if len(ordered) > MAX_FINDINGS:
        raise ValueError("findings exceed hard bound")
    return ordered


def _build_human_preview(
    *,
    proposal: KnowledgeChangeProposal,
    proposed_content_snapshot: ProposedContentSnapshot,
    validation_result: ValidationResult,
    status: ReviewStatus,
    findings: tuple[ConflictFinding, ...],
    representation_delta: RepresentationDelta | None,
    full_diff: str | None,
) -> str:
    lines = [
        f"LocalComet Knowledge Review {CONTRACT_VERSION}",
        f"Status: {status.value}",
        f"Proposal: {proposal.proposal_id}",
        f"Operation: {proposal.operation.value}",
        f"Target: {proposal.target_stable_id}",
        f"Validation outcome: {validation_result.outcome.value}",
        "Findings:",
    ]
    if findings:
        for finding in findings:
            lines.append(f"- {finding.code.value} [{finding.severity.value}]: {finding.message}")
    else:
        lines.append("- none")

    lines.extend([
        "Proposed content review projection:",
        "- publication-byte claim: unavailable by contract",
        "- current structured metadata comparison: unavailable from the trusted text-only target snapshot",
    ])
    proposed_payload = proposed_content_snapshot.identity_payload()
    for field_name in _PROPOSED_CONTENT_FIELD_ORDER:
        lines.append(
            f"- {field_name}: {_bounded_preview_value(proposed_payload[field_name])}"
        )

    lines.append("Body-text representation:")
    if representation_delta is None:
        lines.append("- unavailable")
    else:
        before_label = (
            representation_delta.before_line_endings.label
            if representation_delta.before_line_endings
            else "ABSENT"
        )
        after_label = representation_delta.after_line_endings.label
        lines.extend([
            f"- line endings: {before_label} -> {after_label}",
            f"- terminal newline changed: {str(representation_delta.terminal_newline_changed).lower()}",
            f"- proposed publication source bytes known: "
            f"{str(representation_delta.after_source_bytes_known).lower()}",
            f"- source bytes changed, decoded text identical: "
            f"{str(representation_delta.source_bytes_changed_text_identical).lower()}",
            f"- raw text changed, semantic text equal: "
            f"{str(representation_delta.raw_text_changed_semantic_equal).lower()}",
            f"- semantic body content changed: "
            f"{str(representation_delta.semantic_content_changed).lower()}",
        ])
    lines.append("Deterministic semantic body diff:")
    if full_diff:
        lines.extend(full_diff.splitlines())
    else:
        lines.append("(empty)")
    return _truncate_preview(lines)


def _bounded_preview_value(value: Any) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    encoded = serialized.encode("utf-8")
    if len(encoded) <= MAX_METADATA_PREVIEW_VALUE_BYTES:
        return serialized
    prefix_budget = max(1, MAX_METADATA_PREVIEW_VALUE_BYTES // 2)
    prefix = encoded[:prefix_budget].decode("utf-8", errors="ignore")
    summary = {
        "preview_prefix": prefix,
        "sha256": _sha256(encoded),
        "truncated": True,
        "utf8_bytes": len(encoded),
    }
    bounded = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(bounded.encode("utf-8")) > MAX_METADATA_PREVIEW_VALUE_BYTES:
        raise AssertionError("metadata preview bound invariant violated")
    return bounded

def _truncate_preview(lines: Sequence[str]) -> str:
    if not lines:
        return ""
    output: list[str] = []
    byte_count = 0
    truncated = False
    marker_bytes = len((TRUNCATION_MARKER + "\n").encode("utf-8"))
    line_limit = max(1, MAX_PREVIEW_LINES - 1)
    byte_limit = max(1, MAX_PREVIEW_BYTES - marker_bytes)
    for line in lines:
        normalized = line.replace("\r\n", "\n").replace("\r", "\n")
        for physical_line in normalized.split("\n"):
            candidate = physical_line + "\n"
            candidate_bytes = len(candidate.encode("utf-8"))
            if len(output) >= line_limit or byte_count + candidate_bytes > byte_limit:
                truncated = True
                break
            output.append(candidate)
            byte_count += candidate_bytes
        if truncated:
            break
    if truncated:
        output.append(TRUNCATION_MARKER + "\n")
    result = "".join(output)
    if len(result.encode("utf-8")) > MAX_PREVIEW_BYTES:
        raise AssertionError("preview byte bound invariant violated")
    if len(result.splitlines()) > MAX_PREVIEW_LINES:
        raise AssertionError("preview line bound invariant violated")
    return result


def _finding(
    code: ConflictCode,
    severity: ConflictSeverity,
    message: str,
    *details: tuple[str, str],
) -> ConflictFinding:
    return ConflictFinding(code=code, severity=severity, message=message, details=tuple(details))


def _stable_id_set_hash(stable_ids: frozenset[str]) -> str:
    return _domain_hash(
        "CURRENT_STABLE_ID_SET",
        IDENTITY_VERSION,
        {"stable_ids": sorted(stable_ids)},
    )


def _count_provenance_entries(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value) + sum(_count_provenance_entries(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) + sum(_count_provenance_entries(item) for item in value)
    return 1


def _validate_relative_path(path: str) -> None:
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH or "\x00" in path:
        raise ValueError("invalid relative path")
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    if posix_path.root or windows_path.drive or windows_path.root:
        raise ValueError("absolute, rooted, or drive-qualified path forbidden")
    parts = tuple(part for part in re.split(r"[\\/]", path) if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path traversal forbidden")


def _validate_stable_id(stable_id: str) -> None:
    if (
        not isinstance(stable_id, str)
        or not stable_id
        or len(stable_id) > MAX_STABLE_ID_LENGTH
        or not _STABLE_ID_RE.fullmatch(stable_id)
    ):
        raise ValueError("invalid stable ID")


def _validate_revision(revision: str) -> None:
    if not isinstance(revision, str) or not _REVISION_RE.fullmatch(revision):
        raise ValueError("invalid Vault revision")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _domain_digest(domain: str, version: str, payload: Any) -> str:
    envelope = {"domain": domain, "version": version, "payload": payload}
    return hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()


def _domain_hash(domain: str, version: str, payload: Any) -> str:
    return "sha256:" + _domain_digest(domain, version, payload)


E9A_API_BINDINGS: Final[Mapping[str, Any]] = MappingProxyType({
    "KnowledgeChangeProposal": KnowledgeChangeProposal,
    "ValidationResult": ValidationResult,
    "ProposalOperation": ProposalOperation,
    "ValidationOutcome": ValidationOutcome,
    "ProposalValidator": ProposalValidator,
    "ProposedNoteContent": ProposedNoteContent,
    "compute_proposal_content_hash": compute_proposal_content_hash,
    "compute_proposal_instance_id": compute_proposal_instance_id,
    "create_proposal_from_untrusted": create_proposal_from_untrusted,
})


__all__ = [
    "CONTRACT_VERSION",
    "SEMANTIC_NORMALIZATION_VERSION",
    "MAX_SOURCE_BYTES",
    "MAX_TRUSTED_TEXT_CHARS",
    "MAX_PROPOSED_CONTENT_BYTES",
    "MAX_STABLE_IDS",
    "MAX_EVIDENCE_REFERENCES",
    "MAX_PROVENANCE_ENTRIES",
    "MAX_FINDINGS",
    "MAX_FULL_DIFF_BYTES",
    "MAX_PREVIEW_BYTES",
    "MAX_PREVIEW_LINES",
    "MAX_PATH_LENGTH",
    "MAX_STABLE_ID_LENGTH",
    "MAX_PROPOSED_SNAPSHOT_BYTES",
    "MAX_METADATA_PREVIEW_VALUE_BYTES",
    "MAX_VALIDATION_SNAPSHOT_DEPTH",
    "MAX_VALIDATION_SNAPSHOT_NODES",
    "MAX_VALIDATION_MAPPING_ENTRIES",
    "MAX_VALIDATION_SEQUENCE_ENTRIES",
    "MAX_VALIDATION_KEY_LENGTH",
    "MAX_VALIDATION_STRING_LENGTH",
    "TRUNCATION_MARKER",
    "ReviewStatus",
    "ConflictSeverity",
    "ConflictCode",
    "FrozenCanonicalValue",
    "ProposedContentSnapshot",
    "ConflictFinding",
    "LineEndingProfile",
    "RepresentationDelta",
    "TrustedTargetSnapshot",
    "CurrentKnowledgeState",
    "KnowledgeChangeReviewArtifact",
    "semantic_normalize_v1",
    "compute_source_byte_hash",
    "compute_text_raw_hash",
    "compute_semantic_text_hash",
    "create_trusted_target_snapshot",
    "analyze_review",
    "E9A_API_BINDINGS",
]
````

