#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import math
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _raises(fn, code: str | None = None) -> None:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    try:
        fn()
    except ipc.IPCProtocolError as exc:
        if code is not None:
            _assert(exc.code == code, "Unexpected IPC error code.")
        return
    except Exception:
        if code is None:
            return
        raise
    raise AssertionError("Expected failure did not occur.")


def _paths_under(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for path in root.rglob("*"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _import_ipc():
    sys.modules.pop("modules.desktop_ipc_contract_ru", None)
    return importlib.import_module("modules.desktop_ipc_contract_ru")


def _request(**updates: Any) -> dict[str, Any]:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    msg = ipc.make_request("req_001", "models.list", {})
    msg.update(updates)
    return msg


def test_import_safety() -> None:
    before = _paths_under(ROOT)
    env_before = dict(os.environ)
    threads_before = {t.ident for t in threading.enumerate()}
    calls: list[str] = []
    originals = (subprocess.Popen, socket.socket, urllib.request.urlopen)

    def forbidden(name: str):
        def inner(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError("external effect")
        return inner

    try:
        subprocess.Popen = forbidden("popen")
        socket.socket = forbidden("socket")
        urllib.request.urlopen = forbidden("urlopen")
        ipc = _import_ipc()
    finally:
        subprocess.Popen, socket.socket, urllib.request.urlopen = originals
    _assert(ipc.DESKTOP_IPC_CONTRACT_VERSION == "v6.84.1", "IPC version changed.")
    _assert(before == _paths_under(ROOT), "Import created or modified files.")
    _assert(env_before == dict(os.environ), "Import mutated environment.")
    _assert(calls == [], "Import used subprocess or network.")
    _assert({t.ident for t in threading.enumerate()} == threads_before, "Import started threads.")


def test_canonical_json_and_framing() -> None:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    a = ipc.make_request("req_001", "models.list", {"text": "Привет"})
    b = {"payload": {"text": "Привет"}, "reply_to": None, "sequence": 0, "run_id": None, "method": "models.list", "id": "req_001", "type": "request", "version": "1.0", "protocol": "localcomet.ipc"}
    before = json.dumps(a, ensure_ascii=False, sort_keys=True)
    _assert(ipc.canonical_json_bytes(a) == ipc.canonical_json_bytes(b), "Canonical bytes depend on key order.")
    _assert("Привет".encode("utf-8") in ipc.canonical_json_bytes(a), "UTF-8 text not preserved.")
    _assert(before == json.dumps(a, ensure_ascii=False, sort_keys=True), "Canonical serialization mutated input.")
    _raises(lambda: ipc.canonical_json_bytes({"x": float("nan")}), "invalid_json")
    _raises(lambda: ipc.canonical_json_bytes({"x": math.inf}), "invalid_json")
    _raises(lambda: ipc.canonical_json_bytes({"x": Path("x")}), "invalid_payload")
    frame = ipc.encode_frame(a)
    length = struct.unpack(">I", frame[:4])[0]
    _assert(length == len(frame) - 4, "Frame length prefix mismatch.")
    _assert(ipc.decode_frame(frame) == a, "One complete frame did not decode.")
    decoder = ipc.FrameDecoder()
    _assert(decoder.feed(b"") == (), "Empty feed produced messages.")
    joined = ipc.encode_frame(a) + ipc.encode_frame(ipc.make_goodbye("bye_001"))
    _assert(len(decoder.feed(joined)) == 2, "Concatenated frames did not decode.")
    decoder.reset()
    out = []
    for byte in ipc.encode_frame(a):
        out.extend(decoder.feed(bytes([byte])))
    _assert(out == [a], "One-byte feed failed.")
    decoder.reset()
    split = ipc.encode_frame(a)
    _assert(decoder.feed(split[:2]) == (), "Incomplete prefix produced message.")
    _assert(decoder.feed(split[2:6]) == (), "Incomplete body produced message.")
    _assert(decoder.feed(split[6:]) == (a,), "Split body did not decode.")
    _raises(lambda: ipc.decode_frame(b"\x00\x00\x00\x00"), "invalid_frame")
    _raises(lambda: decoder.feed(struct.pack(">I", ipc.MAX_FRAME_BYTES + 1)), "frame_too_large")
    _raises(lambda: ipc.decode_frame(struct.pack(">I", ipc.MAX_FRAME_BYTES + 1) + b"{}"), "frame_too_large")
    _raises(lambda: ipc.decode_frame(b"\x00\x00\x00\x02\xff\xff"), "invalid_json")
    _raises(lambda: ipc.decode_frame(b"\x00\x00\x00\x01{"), "invalid_json")
    dup = b'{"protocol":"localcomet.ipc","protocol":"localcomet.ipc"}'
    _raises(lambda: ipc.decode_frame(struct.pack(">I", len(dup)) + dup), "invalid_json")
    _raises(lambda: ipc.decode_frame(ipc.encode_frame(a) + b"x"), "invalid_frame")
    decoder.reset()
    _assert(decoder.feed(ipc.encode_frame(a)) == (a,), "Decoder reset failed.")


def test_envelope_payload_and_constructors() -> None:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    valid = [
        ipc.make_hello("hello_001", session_nonce="nonce_001"),
        ipc.make_request("req_001", "models.list", {}),
        ipc.make_response("res_001", "req_001", {}),
        ipc.make_event("evt_001", "chat.started", {}, reply_to="req_001"),
        ipc.make_error("err_001", "req_001", "busy", "busy", retryable=True),
        ipc.make_cancel("can_001", "req_001", "user_requested"),
        ipc.make_goodbye("bye_001"),
    ]
    for msg in valid:
        _assert(ipc.validate_envelope(msg) == (), "Valid constructor output did not validate.")
    invalids = [
        (_request(protocol="wrong"), "invalid_protocol"),
        (_request(version="2.0"), "unsupported_version"),
        (_request(type="weird"), "unsupported_type"),
        (_request(id=""), "invalid_id"),
        (_request(id="../x"), "invalid_id"),
        (_request(method="bad..name"), "invalid_method"),
        (_request(run_id="abc"), "invalid_run_id"),
        (_request(sequence=True), "invalid_sequence"),
        (_request(sequence=-1), "invalid_sequence"),
        (dict(ipc.make_response("res_001", "req_001", {}), reply_to=None), "missing_reply_to"),
        (dict(ipc.make_error("err_001", "req_001", "busy", "busy"), reply_to=None), "missing_reply_to"),
        (_request(payload=[]), "payload_not_object"),
        (dict(_request(), extra=1), "unknown_extra"),
    ]
    for msg, expected in invalids:
        _assert(expected in ipc.validate_envelope(msg), "Invalid envelope was not rejected.")
    _assert("max_depth_exceeded" in ipc.validate_payload({"x": [[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]}), "Depth limit missing.")
    _assert("object_too_large" in ipc.validate_payload({str(i): i for i in range(ipc.MAX_OBJECT_KEYS + 1)}), "Object key limit missing.")
    _assert("array_too_large" in ipc.validate_payload(list(range(ipc.MAX_ARRAY_LENGTH + 1))), "Array limit missing.")
    _assert("string_too_large" in ipc.validate_payload("x" * (ipc.MAX_STRING_CHARS + 1)), "String limit missing.")
    _assert("non_finite_number" in ipc.validate_payload({"x": float("nan")}), "Nested NaN accepted.")
    _assert("unsupported_payload_type" in ipc.validate_payload({"x": b"bytes"}), "Bytes accepted.")
    _assert("unsupported_payload_type" in ipc.validate_payload({"x": Path("x")}), "Path accepted.")
    _assert("unsupported_payload_type" in ipc.validate_payload({"x": lambda: None}), "Callable accepted.")
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    _assert("cyclic_payload" in ipc.validate_payload(cyclic), "Cycle not detected.")
    _raises(lambda: ipc.make_request("../bad", "models.list", {}), "invalid_envelope")
    _raises(lambda: ipc.make_request("req_001", "bad..method", {}), "invalid_envelope")
    _raises(lambda: ipc.make_request("req_001", "models.list", {}, sequence=True), "invalid_envelope")
    _assert(ipc.make_request("req_001", "models.list", {}) == ipc.make_request("req_001", "models.list", {}), "Constructor output not deterministic.")


def test_streaming_errors_cancel_approval_and_sanitization() -> None:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    delta = ipc.make_event("evt_001", "chat.delta", {"channel": "content", "text": "hello", "finish_reason": None}, reply_to="req_001", sequence=0)
    _assert(ipc.validate_envelope(delta) == (), "chat.delta did not validate.")
    bad_delta = dict(delta)
    bad_delta["id"] = "evt_002"
    bad_delta["payload"] = {"channel": "other", "text": "x", "finish_reason": None}
    _assert("invalid_delta_channel" in ipc.validate_envelope(bad_delta), "Delta channel vocabulary not enforced.")
    too_big = dict(delta)
    too_big["id"] = "evt_003"
    too_big["payload"] = {"channel": "content", "text": "x" * (ipc.MAX_DELTA_TEXT_CHARS + 1), "finish_reason": None}
    _assert("invalid_delta_text" in ipc.validate_envelope(too_big), "Delta text limit missing.")
    err = ipc.make_error("err_001", "req_001", "busy", "Traceback (most recent call last): secret", details={"path": "C:" + "\\Users\\Name\\x"})
    _assert(ipc.validate_envelope(err) == (), "Bounded error code did not validate.")
    bad_err = ipc.make_error("err_002", "req_001", "busy", "x")
    bad_err["payload"]["code"] = "unknown"
    _assert("invalid_error_code" in ipc.validate_envelope(bad_err), "Unknown error code accepted.")
    cancel = ipc.make_cancel("can_001", "req_001", "timeout")
    _assert(ipc.validate_envelope(cancel) == (), "Valid cancel failed.")
    bad_cancel = ipc.make_cancel("can_002", "req_001", "timeout")
    bad_cancel["payload"]["reason"] = "approve"
    _assert("invalid_cancel_reason" in ipc.validate_envelope(bad_cancel), "Unknown cancel reason accepted.")
    bad_cancel["payload"]["decision"] = "approve"
    _assert("cancel_contains_approval" in ipc.validate_envelope(bad_cancel), "Cancel accepted approval data.")
    approval = ipc.make_request("req_approval", "approval.submit", {"action_id": "action_01", "action_fingerprint": "a" * 64, "decision": "approve", "scope": "SINGLE_ACTION"})
    _assert(ipc.validate_envelope(approval) == (), "Approval submit failed.")
    for key, value, finding in (("action_fingerprint", "bad", "invalid_action_fingerprint"), ("decision", "maybe", "invalid_approval_decision"), ("scope", "GLOBAL", "invalid_approval_scope"), ("autonomy_level", "LEVEL_4", "approval_changes_policy"), ("content", "write", "approval_contains_write_content")):
        bad = ipc.make_request("req_approval", "approval.submit", {"action_id": "action_01", "action_fingerprint": "a" * 64, "decision": "approve", "scope": "SINGLE_ACTION"})
        bad["payload"][key] = value
        _assert(finding in ipc.validate_envelope(bad), "Approval invalid field accepted.")
    secret = "sk" + "-" + "A" * 16
    private = "-----BEGIN PRIVATE " + "KEY-----\nabc\n-----END PRIVATE " + "KEY-----"
    msg = ipc.make_request("req_001", "chat.send", {"text": "hello " + secret, "password": "pass" + "word123", "authorization": "Bearer " + "B" * 16, "content": "raw write", "old_text": "old", "new_text": "new", "path": "C:" + "\\Users\\Name\\secret.txt", "private": private})
    original = json.loads(json.dumps(msg))
    sanitized = ipc.sanitize_ipc_for_log(msg)
    text = json.dumps(sanitized, ensure_ascii=False)
    _assert(msg == original, "Sanitizer mutated input.")
    _assert(secret not in text and "password123" not in text and "Bearer" not in text and ("PRIVATE " + "KEY") not in text, "Sanitizer leaked sensitive values.")
    _assert("<REDACTED_TEXT>" in text and "<REDACTED_TOKEN>" in text and "<USER_PATH>" in text, "Sanitizer markers missing.")
    _assert(sanitized["protocol"] == "localcomet.ipc" and sanitized["method"] == "chat.send" and sanitized["id"] == "req_001", "Safe metadata was not preserved.")
    long = ipc.sanitize_ipc_for_log(ipc.make_request("req_002", "chat.send", {"text": "x" * (ipc.MAX_LOG_STRING_CHARS + 10)}))
    _assert("<TRUNCATED>" in json.dumps(long), "Long text was not truncated.")


def test_schema_document_manifest_and_regression_invariants() -> None:
    ipc = importlib.import_module("modules.desktop_ipc_contract_ru")
    schema_path = ROOT / "desktop" / "contracts" / "localcomet_ipc_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _assert(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "Wrong schema draft.")
    _assert(schema["$id"] == "localcomet://schemas/ipc/v1", "Wrong schema ID.")
    _assert(schema["properties"]["protocol"]["const"] == ipc.IPC_PROTOCOL, "Schema protocol mismatch.")
    _assert(schema["properties"]["version"]["const"] == ipc.IPC_PROTOCOL_VERSION, "Schema version mismatch.")
    _assert(tuple(schema["$defs"]["envelopeType"]["enum"]) == ipc.ENVELOPE_TYPES, "Type vocabulary mismatch.")
    _assert(tuple(schema["$defs"]["errorCode"]["enum"]) == ipc.ERROR_CODES, "Error vocabulary mismatch.")
    _assert(tuple(schema["$defs"]["cancelReason"]["enum"]) == ipc.CANCEL_REASONS, "Cancel vocabulary mismatch.")
    _assert(tuple(schema["$defs"]["approvalScope"]["enum"]) == ipc.APPROVAL_SCOPES, "Approval scope mismatch.")
    schema_text = schema_path.read_text(encoding="utf-8")
    _assert(("C:" + "\\Users") not in schema_text and "/home/" not in schema_text and "Open WebUI" not in schema_text, "Schema contains forbidden path or branding.")
    doc = (ROOT / "docs" / "desktop_architecture_v6841.md").read_text(encoding="utf-8")
    required = ["Tauri 2", "SvelteKit", "TypeScript", "Rust", "Python sidecar", "no exposed production localhost", "length-prefixed JSON", "CSP", "Windows Job Object", "Tkinter", "Navigation rail", "Agent inspector", "light theme", "dark theme", "source ingestion", "DocumentWorkflowCard", "ArtifactVerificationBadge"]
    for phrase in required:
        _assert(phrase in doc, "Architecture document is missing a required phrase.")
    _assert("source-code fork" in doc and "not implemented in v6.84.1" in doc, "Architecture document boundaries missing.")
    manifest = json.loads((ROOT / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    if "modules/desktop_ipc_contract_ru.py" in manifest.get("lazy_runtime", []) or "tools/test_v6841_desktop_ipc.py" in manifest.get("tests", []):
        _assert("modules/desktop_ipc_contract_ru.py" in manifest.get("lazy_runtime", []), "IPC module missing from manifest.")
        _assert("tools/test_v6841_desktop_ipc.py" in manifest.get("tests", []), "IPC test missing from manifest.")
    seen: set[str] = set()
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        values = manifest.get(key, [])
        _assert(values == sorted(values, key=str.lower), f"Manifest list not sorted: {key}")
        _assert(len(values) == len(set(values)), f"Manifest duplicates: {key}")
        _assert(not (seen & set(values)), f"Manifest cross-category duplicate: {key}")
        seen.update(values)
    panel = importlib.import_module("LocalComet_Control_Panel")
    source = (ROOT / "LocalComet_Control_Panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    _assert(type(panel.LOCALCOMET_VERSION) is str and panel.LOCALCOMET_VERSION == "v6.82", "Panel version changed.")
    _assert(sum(isinstance(n, ast.FunctionDef) and n.name == "run_panel_chat_command" for n in ast.walk(tree)) == 1, "Dispatcher count changed.")
    executor = (ROOT / "modules" / "autonomous_action_executor_ru.py").read_text(encoding="utf-8")
    _assert('AUTONOMOUS_ACTION_EXECUTOR_VERSION = "v6.84"' in executor, "v6.84 executor marker changed.")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files present.")


def main() -> None:
    tests = [
        test_import_safety,
        test_canonical_json_and_framing,
        test_envelope_payload_and_constructors,
        test_streaming_errors_cancel_approval_and_sanitization,
        test_schema_document_manifest_and_regression_invariants,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.84.1 DESKTOP IPC TESTS PASSED")


if __name__ == "__main__":
    main()
