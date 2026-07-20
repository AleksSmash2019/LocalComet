#!/usr/bin/env python
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import DESKTOP_CONTROL_PLANE_VERSION  # noqa: E402
from modules.desktop_ipc_contract_ru import IPC_PROTOCOL, IPC_PROTOCOL_VERSION  # noqa: E402
from modules.desktop_sidecar_runtime_ru import DESKTOP_SIDECAR_RUNTIME_VERSION  # noqa: E402
from modules.local_model_gateway_ru import (  # noqa: E402
    HARNESS_REGISTRY,
    LOCAL_MODEL_GATEWAY_VERSION,
    MODEL_GATEWAY_METHODS,
    PROVIDER_REGISTRY,
    GatewayError,
    GatewayLimits,
    HarnessAdapter,
    LocalModelGateway,
    MANAGED_PROVIDER_ID,
    ModelBinding,
    ProviderAdapter,
    TurnRequest,
    _validate_assistant_context,
    _turn_payload,
    trusted_assistant_context_payload,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _raises(fn, code: str | None = None) -> None:
    try:
        fn()
    except GatewayError as exc:
        if code is not None:
            _assert(exc.code == code, f"Expected {code}, got {exc.code}")
        return
    raise AssertionError("Expected GatewayError")


class FakeProvider(BaseHTTPRequestHandler):
    mode = "ok"
    seen_posts = 0

    def log_message(self, *_: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/models":
            self.send_response(404)
            self.end_headers()
            return
        if type(self).mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/v1/models")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if type(self).mode == "duplicate_json":
            self.wfile.write(b'{"data":[{"id":"one"}],"data":[]}')
        elif type(self).mode == "oversized":
            self.wfile.write(json.dumps({"data": [{"id": f"m{i}"} for i in range(300)]}).encode("utf-8"))
        elif type(self).mode == "malformed_model":
            self.wfile.write(b'{"data":[{"id":""}]}')
        else:
            self.wfile.write(b'{"data":[{"id":"local-model"}]}')

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        type(self).seen_posts += 1
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if (
            set(body) != {"max_tokens", "messages", "model", "stream", "temperature"}
            or body["stream"] is not True
            or body["temperature"] != 0
            or not 1 <= body["max_tokens"] <= 512
        ):
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if type(self).mode == "tool_calls":
            self.wfile.write(b'data: {"choices":[{"index":0,"delta":{"tool_calls":[]},"finish_reason":null}]}\n\n')
            self.wfile.flush()
            return
        if type(self).mode == "function_call":
            self.wfile.write(b'data: {"choices":[{"index":0,"delta":{"function_call":{"name":"run","arguments":"{}"}},"finish_reason":null}]}\n\n')
            self.wfile.flush()
            return
        if type(self).mode == "multi_choice":
            self.wfile.write(b'data: {"choices":[{"index":0,"delta":{"content":"a"}},{"index":1,"delta":{"content":"b"}}]}\n\n')
            self.wfile.flush()
            return
        if type(self).mode == "slow":
            if not self._write_sse(b": comment\n\n"):
                return
            time.sleep(0.2)
        if not self._write_sse(b'data: {"choices":[{"index":0,"delta":{"content":"he"},"finish_reason":null}]}\n\n'):
            return
        if not self._write_sse(b'data: {"choices":[{"index":0,"delta":{"content":"llo"},"finish_reason":null}]}\n\n'):
            return
        self._write_sse(b"data: [DONE]\n\n")

    def _write_sse(self, chunk: bytes) -> bool:
        try:
            self.wfile.write(chunk)
            self.wfile.flush()
            return True
        except ConnectionError:
            return False


class FakeServer:
    def __init__(self, mode: str = "ok") -> None:
        FakeProvider.mode = mode
        FakeProvider.seen_posts = 0
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeProvider)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def __enter__(self) -> "FakeServer":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2)


def test_registries_and_validation() -> None:
    _assert(PROVIDER_REGISTRY == ("openai-compatible-local", "managed-llama-cpp"), "provider registry changed")
    _assert(HARNESS_REGISTRY == ("minimal", "native-localcomet"), "harness registry changed")
    _assert(len(MODEL_GATEWAY_METHODS) == 8, "gateway method count changed")
    gateway = LocalModelGateway()
    _raises(lambda: gateway.probe({"port": "1234"}), "invalid_payload")
    _raises(lambda: gateway.probe({"port": 80}), "invalid_payload")
    _raises(lambda: gateway.set_binding({"provider_id": "http://127.0.0.1:1/v1", "harness_id": "minimal", "port": 1234, "model_id": "x", "confirmed": True}), "invalid_payload")
    _raises(lambda: gateway.set_binding({"provider_id": "openai-compatible-local", "harness_id": "dynamic", "port": 1234, "model_id": "x", "confirmed": True}), "invalid_payload")


def test_version_alignment_and_turn_payload_shape() -> None:
    binding = ModelBinding(
        provider_id="openai-compatible-local",
        harness_id="minimal",
        port=1234,
        model_id="local-model",
        fingerprint="a" * 64,
        discovered_fingerprint="b" * 64,
    )
    request = TurnRequest(
        request_id="c" * 24,
        turn_id="c" * 24,
        chat_session_id="chat-test",
        model_id="local-model",
        submitted_at_unix_ms=1,
        max_tokens=64,
        prompt="hello",
        assistant_context=_validate_assistant_context(trusted_assistant_context_payload("ru")),
        binding_fingerprint="a" * 64,
    )
    payload = _turn_payload(
        request,
        "Generating",
        binding,
        model_called=True,
        text="hello",
        generated_bytes=5,
    )
    _assert(
        set(payload)
        == {
            "control_plane_version",
            "model_gateway_version",
            "request_id",
            "turn_id",
            "chat_session_id",
            "session_id",
            "thread_id",
            "item_id",
            "kind",
            "state",
            "provider_id",
            "harness_id",
            "model_id",
            "submitted_at_unix_ms",
            "max_tokens",
            "binding_fingerprint",
            "text",
            "model_called",
            "tools_executed",
            "persistence",
            "generated_bytes",
            "metadata",
        },
        "turn payload shape changed",
    )
    _assert(
        set(payload["metadata"])
        == {
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
        },
        "turn payload metadata shape changed",
    )
    _assert(payload["control_plane_version"] == DESKTOP_CONTROL_PLANE_VERSION == "v6.84.5.1", "Control Plane version not aligned")
    _assert(payload["control_plane_version"] != "v6.84.4", "stale Control Plane version still emitted")
    _assert(payload["model_gateway_version"] == LOCAL_MODEL_GATEWAY_VERSION == "v6.84.5", "Model Gateway release changed")
    _assert(IPC_PROTOCOL == "localcomet.ipc" and IPC_PROTOCOL_VERSION == "1.0", "IPC protocol changed")
    _assert(DESKTOP_SIDECAR_RUNTIME_VERSION == "v6.84.3", "Sidecar runtime version changed")

    bridge_text = (ROOT / "desktop" / "localcomet-desktop" / "src" / "lib" / "bridge" / "controlPlane.ts").read_text(encoding="utf-8")
    bridge_test_text = (ROOT / "desktop" / "localcomet-desktop" / "tests" / "control-plane.test.ts").read_text(encoding="utf-8")
    _assert("object.control_plane_version !== 'v6.84.5.1'" in bridge_text, "exact Control Plane validation changed")
    _assert("rejects the stale v6.84.4 bootstrap version" in bridge_test_text, "stale-version rejection test missing")


def test_probe_list_and_binding() -> None:
    with FakeServer() as server:
        gateway = LocalModelGateway()
        probe = gateway.probe({"port": server.port})
        _assert(probe["host"] == "127.0.0.1" and probe["base_path"] == "/v1", "endpoint boundary changed")
        listed = gateway.list_models({"port": server.port})
        _assert(listed["models"] == [{"model_id": "local-model"}], "model listing failed")
        _raises(lambda: gateway.set_binding({"provider_id": "openai-compatible-local", "harness_id": "minimal", "port": server.port, "model_id": "other", "confirmed": True}), "invalid_payload")
        _raises(lambda: gateway.set_binding({"provider_id": "openai-compatible-local", "harness_id": "minimal", "port": server.port, "model_id": "local-model", "confirmed": False}), "invalid_payload")
        binding = gateway.set_binding({"provider_id": "openai-compatible-local", "harness_id": "minimal", "port": server.port, "model_id": "local-model", "confirmed": True})
        _assert(len(binding["binding_fingerprint"]) == 64, "binding fingerprint missing")


def test_managed_attach_binding_and_detach() -> None:
    with FakeServer() as server:
        gateway = LocalModelGateway()
        attach = gateway.managed_attach(
            {
                "runtime_instance_id": "a" * 32,
                "port": server.port,
                "credential": "b" * 64,
                "expected_model_alias": "local-model",
                "model_id": "managed-model",
                "binding_fingerprint": "c" * 64,
            }
        )
        _assert(attach["provider_id"] == MANAGED_PROVIDER_ID, "managed provider attach failed")
        _assert(attach["model_state"] == "Ready" and attach["inference_ready"] is True, "managed readiness missing")
        binding = gateway.set_binding(
            {
                "provider_id": MANAGED_PROVIDER_ID,
                "harness_id": "minimal",
                "port": None,
                "model_id": "managed-model",
                "confirmed": True,
                "runtime_instance_id": "a" * 32,
            }
        )
        _assert(binding["provider_id"] == MANAGED_PROVIDER_ID, "managed binding provider wrong")
        _assert("port" not in binding and "runtime_instance_id" in binding, "managed binding exposed port")
        detached = gateway.managed_detach()
        _assert(detached["detached"] is True, "managed detach failed")


def test_provider_rejects_malformed_responses() -> None:
    for mode in ("duplicate_json", "oversized", "malformed_model", "redirect"):
        with FakeServer(mode) as server:
            _raises(lambda: ProviderAdapter(server.port, GatewayLimits(maximum_model_count=4)).list_models())


def test_harnesses_are_deterministic_and_text_only() -> None:
    context = _validate_assistant_context(trusted_assistant_context_payload("en"))
    minimal = HarnessAdapter("minimal", GatewayLimits()).messages_for("hello", context)
    native = HarnessAdapter("native-localcomet", GatewayLimits()).messages_for("hello", context)
    _assert([message["role"] for message in minimal] == ["system", "user"], "trusted system message order changed")
    _assert(native == HarnessAdapter("native-localcomet", GatewayLimits()).messages_for("hello", context), "native harness not deterministic")
    _assert("external tools are unavailable" in native[0]["content"] and "Project context was not supplied" in native[0]["content"], "assistant safety context missing")


def test_sse_streaming_and_fail_closed() -> None:
    with FakeServer() as server:
        adapter = ProviderAdapter(server.port, GatewayLimits())
        called = []
        text = "".join(adapter.stream_chat("local-model", ({"role": "user", "content": "hi"},), threading.Event(), lambda: called.append(True)))
        _assert(text == "hello" and called == [True], "fragmented SSE did not parse")
    for mode in ("tool_calls", "function_call", "multi_choice"):
        with FakeServer(mode) as server:
            adapter = ProviderAdapter(server.port, GatewayLimits())
            _raises(lambda: list(adapter.stream_chat("local-model", ({"role": "user", "content": "hi"},), threading.Event(), lambda: None)), "stream_protocol_error")


def test_single_active_and_cancellation_cleanup() -> None:
    with FakeServer("slow") as server:
        gateway = LocalModelGateway(limits=GatewayLimits(worker_join_timeout_seconds=2.0, read_chunk_bytes=16))
        gateway.list_models({"port": server.port})
        binding = gateway.set_binding({"provider_id": "openai-compatible-local", "harness_id": "minimal", "port": server.port, "model_id": "local-model", "confirmed": True})
        events: list[tuple[str, str]] = []
        request_id = "d" * 24
        request = {
            "request_id": request_id,
            "chat_session_id": "chat-test",
            "model_id": "local-model",
            "submitted_at_unix_ms": 1,
            "max_tokens": 32,
            "prompt": "hello",
            "assistant_context": trusted_assistant_context_payload("en"),
            "binding_fingerprint": binding["binding_fingerprint"],
        }
        started = gateway.start_turn(request, lambda m, t, s, p: events.append((m, str(p.get("state")))))
        second = {**request, "request_id": "e" * 24, "prompt": "again"}
        _raises(lambda: gateway.start_turn(second, lambda *_: None), "busy")
        result = gateway.cancel_turn({"request_id": started["request_id"]})
        _assert(result["accepted"] is True and result["already_terminal"] is False, "cancel ack wrong")
        _assert(result["worker_alive"] is False, "worker remained alive after cancellation")
        gateway.shutdown()
        _assert(any(method == "model.turn.cancelled" for method, _ in events), "cancel event missing")


def test_source_build_artifacts_absent() -> None:
    desktop = ROOT / "desktop" / "localcomet-desktop"
    _assert(not (desktop / "node_modules").exists(), "source node_modules present")
    _assert(not (desktop / "src-tauri" / "target").exists(), "source src-tauri/target present")


def main() -> None:
    tests = [
        test_registries_and_validation,
        test_version_alignment_and_turn_payload_shape,
        test_probe_list_and_binding,
        test_managed_attach_binding_and_detach,
        test_provider_rejects_malformed_responses,
        test_harnesses_are_deterministic_and_text_only,
        test_sse_streaming_and_fail_closed,
        test_single_active_and_cancellation_cleanup,
        test_source_build_artifacts_absent,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.84.5 MODEL GATEWAY TESTS PASSED")


if __name__ == "__main__":
    main()
