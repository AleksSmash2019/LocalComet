#!/usr/bin/env python
from __future__ import annotations

import json
import os
import queue
import struct
import subprocess
import sys
import threading
import time
import unittest
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_ipc_contract_ru import (  # noqa: E402
    decode_frame,
    encode_frame,
    make_hello,
    make_request,
)
from modules.desktop_sidecar_runtime_ru import DesktopSidecarRuntime  # noqa: E402
from modules.local_model_gateway_ru import (  # noqa: E402
    HARNESS_MINIMAL,
    MANAGED_PROVIDER_ID,
    PROVIDER_ID,
    GatewayError,
    GatewayLimits,
    LocalModelGateway,
    ProviderAdapter,
    trusted_assistant_context_payload,
    validate_gateway_payload,
)
from tools import run_localcomet_desktop_sidecar as sidecar_runner  # noqa: E402


TERMINAL_METHODS = {
    "model.turn.completed",
    "model.turn.cancelled",
    "model.turn.timed_out",
    "model.turn.failed",
}


class ScenarioProvider(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        provider = self.server
        provider.get_paths.append(self.path)
        provider.authorization_headers.append(self.headers.get("Authorization"))
        if self.path != "/v1/models":
            self._send_body(404, b"not found", "text/plain")
            return
        body = json.dumps(
            {"data": [{"id": model_id} for model_id in provider.model_aliases]},
            separators=(",", ":"),
        ).encode("utf-8")
        with provider.slow_model_lock:
            slow_body = provider.slow_model_responses > 0
            if slow_body:
                provider.slow_model_responses -= 1
        if slow_body:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._write_slowly(body)
            return
        self._send_body(200, body, "application/json")

    def do_POST(self) -> None:  # noqa: N802
        provider = self.server
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        provider.post_paths.append(self.path)
        provider.authorization_headers.append(self.headers.get("Authorization"))
        provider.posts.append(json.loads(raw_body.decode("utf-8")))
        provider.post_event.set()
        if self.path != "/v1/chat/completions":
            self._send_body(404, b"not found", "text/plain")
            return

        scenario = provider.next_scenario()
        if scenario == "slow_headers":
            self._write_slowly(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/event-stream; charset=utf-8\r\n"
                b"Cache-Control: no-cache\r\n\r\n"
            )
            self._delta("late")
            self._done()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if scenario == "ready":
            self._delta("R")
            self._done()
            return
        if scenario == "empty":
            self._done()
            return
        if scenario == "first_timeout":
            time.sleep(0.15)
            self._done()
            return
        if scenario == "inactivity_timeout":
            self._delta("A")
            time.sleep(0.15)
            self._done()
            return
        if scenario == "overall_timeout":
            self._write(b": activity\n\n")
            time.sleep(0.15)
            self._done()
            return
        if scenario == "cancel":
            self._write(b": request accepted\n\n")
            time.sleep(0.25)
            self._write(b"data: malformed-json\n\n")
            self._done()
            return

        self._delta("")
        self._delta("A")
        self._write(b'data: {"choices":[{"index":0,"delta":{},"finish_reason":null}]}\n\n')
        self._delta("B", finish_reason="stop")
        self._done()

    def _delta(self, text: str, *, finish_reason: str | None = None) -> bool:
        body = json.dumps(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": text},
                        "finish_reason": finish_reason,
                    }
                ]
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return self._write(b"data: " + body + b"\n\n")

    def _done(self) -> bool:
        return self._write(b"data: [DONE]\n\n")

    def _write(self, body: bytes) -> bool:
        try:
            self.wfile.write(body)
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionError, OSError):
            return False

    def _write_slowly(self, body: bytes) -> None:
        for byte in body:
            if not self._write(bytes((byte,))):
                return
            time.sleep(self.server.slow_drip_interval)

    def _send_body(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write(body)


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, _request: Any, _client_address: Any) -> None:
        return


class ScenarioServer:
    def __init__(
        self,
        scenarios: list[str] | tuple[str, ...] = (),
        *,
        model_aliases: tuple[str, ...] = ("local-model",),
        slow_model_responses: int = 0,
        slow_drip_interval: float = 0.01,
    ) -> None:
        self.httpd = QuietThreadingHTTPServer(("127.0.0.1", 0), ScenarioProvider)
        self.httpd.model_aliases = model_aliases
        self.httpd.scenarios = deque(scenarios)
        self.httpd.scenario_lock = threading.Lock()
        self.httpd.slow_model_responses = slow_model_responses
        self.httpd.slow_model_lock = threading.Lock()
        self.httpd.slow_drip_interval = slow_drip_interval
        self.httpd.posts = []
        self.httpd.post_paths = []
        self.httpd.get_paths = []
        self.httpd.authorization_headers = []
        self.httpd.post_event = threading.Event()

        def next_scenario() -> str:
            with self.httpd.scenario_lock:
                return self.httpd.scenarios.popleft() if self.httpd.scenarios else "order"

        self.httpd.next_scenario = next_scenario
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    @property
    def posts(self) -> list[dict[str, Any]]:
        return self.httpd.posts

    @property
    def post_event(self) -> threading.Event:
        return self.httpd.post_event

    def enqueue(self, scenario: str) -> None:
        with self.httpd.scenario_lock:
            self.httpd.scenarios.append(scenario)

    def __enter__(self) -> "ScenarioServer":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2.0)


def _bound_gateway(
    server: ScenarioServer,
    *,
    limits: GatewayLimits | None = None,
) -> tuple[LocalModelGateway, dict[str, Any]]:
    gateway = LocalModelGateway(limits=limits)
    gateway.list_models({"port": server.port})
    binding = gateway.set_binding(
        {
            "provider_id": PROVIDER_ID,
            "harness_id": HARNESS_MINIMAL,
            "port": server.port,
            "model_id": "local-model",
            "confirmed": True,
            "runtime_instance_id": None,
        }
    )
    return gateway, binding


def _turn_request(
    binding: Mapping[str, Any],
    request_id: str,
    *,
    max_tokens: int = 64,
    prompt: str = "hello",
    chat_session_id: str = "local-chat",
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "chat_session_id": chat_session_id,
        "model_id": str(binding["model_id"]),
        "submitted_at_unix_ms": 1_700_000_000_000,
        "max_tokens": max_tokens,
        "prompt": prompt,
        "assistant_context": trusted_assistant_context_payload("ru"),
        "binding_fingerprint": str(binding["binding_fingerprint"]),
    }


def _wait_for_terminal(
    events: list[tuple[str, str, int, Mapping[str, Any]]],
    timeout: float = 3.0,
) -> tuple[str, str, int, Mapping[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        terminals = [event for event in events if event[0] in TERMINAL_METHODS]
        if terminals:
            return terminals[-1]
        time.sleep(0.005)
    raise AssertionError(f"model turn did not terminate: {[event[0] for event in events]}")


def _assert_gateway_error(test: unittest.TestCase, code: str, callback: Any) -> None:
    with test.assertRaises(GatewayError) as caught:
        callback()
    test.assertEqual(code, caught.exception.code)


def _read_exact(stream: BinaryIO, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("sidecar pipe closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class ProcessFrameReader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._queue: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                prefix = _read_exact(self._stream, 4)
                length = struct.unpack(">I", prefix)[0]
                body = _read_exact(self._stream, length)
                self._queue.put(decode_frame(prefix + body))
        except BaseException as exc:
            self._queue.put(exc)

    def get(self, timeout: float = 3.0) -> dict[str, Any]:
        item = self._queue.get(timeout=timeout)
        if isinstance(item, BaseException):
            raise item
        return item


def _send_process_message(process: subprocess.Popen[bytes], message: Mapping[str, Any]) -> None:
    if process.stdin is None:
        raise AssertionError("sidecar stdin is unavailable")
    process.stdin.write(encode_frame(message))
    process.stdin.flush()


class ModelChatBackendTests(unittest.TestCase):
    def test_exact_start_contract_and_identity_validation(self) -> None:
        with ScenarioServer(("order",)) as server:
            gateway, binding = _bound_gateway(server)
            request = _turn_request(binding, "a" * 24, max_tokens=17)
            self.assertEqual((), validate_gateway_payload("model.turn.start", request))
            self.assertEqual(
                ("unknown_turn_id",),
                validate_gateway_payload("model.turn.start", {**request, "turn_id": request["request_id"]}),
            )
            missing_prompt = dict(request)
            missing_prompt.pop("prompt")
            self.assertEqual(("missing_prompt",), validate_gateway_payload("model.turn.start", missing_prompt))

            invalid_requests = (
                {**request, "request_id": "A" * 24},
                {**request, "chat_session_id": "bad/session"},
                {**request, "model_id": "unknown-model"},
                {**request, "submitted_at_unix_ms": 9_007_199_254_740_992},
                {**request, "submitted_at_unix_ms": True},
                {**request, "max_tokens": 0},
                {**request, "max_tokens": 513},
                {**request, "max_tokens": True},
                {**request, "prompt": "  \n"},
                {**request, "binding_fingerprint": "0" * 64},
                {**request, "turn_id": request["request_id"]},
            )
            for invalid in invalid_requests:
                _assert_gateway_error(
                    self,
                    "invalid_payload",
                    lambda invalid=invalid: gateway.start_turn(invalid, lambda *_: None),
                )

            events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            accepted = gateway.start_turn(request, lambda *event: events.append(event))
            self.assertEqual(
                {
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
                },
                set(accepted),
            )
            self.assertNotIn("prompt", accepted)
            self.assertEqual("Accepted", accepted["state"])
            self.assertEqual(request["request_id"], accepted["turn_id"])
            self.assertEqual(17, accepted["max_tokens"])
            _wait_for_terminal(events)
            _assert_gateway_error(
                self,
                "invalid_payload",
                lambda: gateway.start_turn(request, lambda *_: None),
            )

            unknown = gateway.cancel_turn({"request_id": "b" * 24})
            self.assertEqual(
                {
                    "request_id": "b" * 24,
                    "turn_id": "b" * 24,
                    "state": "Cancelled",
                    "accepted": False,
                    "already_terminal": True,
                    "worker_alive": False,
                },
                unknown,
            )
            _assert_gateway_error(
                self,
                "invalid_payload",
                lambda: gateway.cancel_turn({"request_id": "b" * 24, "turn_id": "b" * 24}),
            )

    def test_stream_order_empty_chunks_done_and_second_request(self) -> None:
        with ScenarioServer(("order", "order")) as server:
            gateway, binding = _bound_gateway(server)
            for request_id in ("c" * 24, "d" * 24):
                events: list[tuple[str, str, int, Mapping[str, Any]]] = []
                request = _turn_request(binding, request_id, max_tokens=23)
                gateway.start_turn(request, lambda *event: events.append(event))
                _wait_for_terminal(events)
                self.assertEqual(
                    [
                        "model.turn.started",
                        "model.output.delta",
                        "model.output.delta",
                        "model.turn.completed",
                    ],
                    [event[0] for event in events],
                )
                self.assertEqual([0, 1, 2, 3], [event[2] for event in events])
                self.assertEqual(["A", "B"], [event[3]["text"] for event in events[1:3]])
                self.assertEqual(1, sum(event[0] in TERMINAL_METHODS for event in events))
                for method, emitted_request_id, _sequence, payload in events:
                    self.assertEqual(request_id, emitted_request_id, method)
                    self.assertEqual(request_id, payload["request_id"], method)
                    self.assertEqual(request_id, payload["turn_id"], method)
                    self.assertEqual("local-chat", payload["chat_session_id"], method)
                    self.assertIsNone(payload["session_id"], method)
                    self.assertEqual("local-model", payload["model_id"], method)
                    self.assertEqual(23, payload["max_tokens"], method)
            self.assertEqual([23, 23], [post["max_tokens"] for post in server.posts])
            for post in server.posts:
                self.assertEqual(["system", "user"], [message["role"] for message in post["messages"]])
                self.assertIn("LocalComet", post["messages"][0]["content"])
                self.assertEqual("hello", post["messages"][1]["content"])

    def test_managed_readiness_alias_and_stable_public_model(self) -> None:
        credential = "b" * 64
        runtime_instance_id = "c" * 32
        with ScenarioServer(("ready", "order"), model_aliases=("provider-alias",)) as server:
            gateway = LocalModelGateway()
            attached = gateway.managed_attach(
                {
                    "runtime_instance_id": runtime_instance_id,
                    "port": server.port,
                    "credential": credential,
                    "expected_model_alias": "provider-alias",
                    "model_id": "stable-model",
                    "binding_fingerprint": "d" * 64,
                }
            )
            self.assertEqual(
                {
                    "provider_id": MANAGED_PROVIDER_ID,
                    "runtime_instance_id": runtime_instance_id,
                    "model_id": "stable-model",
                    "attached": True,
                    "model_state": "Ready",
                    "inference_ready": True,
                },
                attached,
            )
            self.assertEqual(["/v1/models"], server.httpd.get_paths)
            self.assertEqual("provider-alias", server.posts[0]["model"])
            self.assertEqual(1, server.posts[0]["max_tokens"])
            self.assertEqual(f"Bearer {credential}", server.httpd.authorization_headers[0])
            self.assertEqual(f"Bearer {credential}", server.httpd.authorization_headers[1])

            binding = gateway.set_binding(
                {
                    "provider_id": MANAGED_PROVIDER_ID,
                    "harness_id": HARNESS_MINIMAL,
                    "port": None,
                    "model_id": "stable-model",
                    "confirmed": True,
                    "runtime_instance_id": runtime_instance_id,
                }
            )
            events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            gateway.start_turn(
                _turn_request(binding, "e" * 24, max_tokens=7),
                lambda *event: events.append(event),
            )
            _wait_for_terminal(events)
            self.assertEqual("provider-alias", server.posts[1]["model"])
            self.assertEqual(7, server.posts[1]["max_tokens"])
            self.assertTrue(all(event[3]["model_id"] == "stable-model" for event in events))
            self.assertTrue(all(event[3]["provider_id"] == MANAGED_PROVIDER_ID for event in events))

        with ScenarioServer(model_aliases=("wrong-alias",)) as wrong_server:
            wrong_gateway = LocalModelGateway()
            _assert_gateway_error(
                self,
                "invalid_payload",
                lambda: wrong_gateway.managed_attach(
                    {
                        "runtime_instance_id": runtime_instance_id,
                        "port": wrong_server.port,
                        "credential": credential,
                        "expected_model_alias": "provider-alias",
                        "model_id": "stable-model",
                        "binding_fingerprint": "d" * 64,
                    }
                ),
            )
            self.assertEqual([], wrong_server.posts)

        with ScenarioServer(("empty",), model_aliases=("provider-alias",)) as empty_server:
            empty_gateway = LocalModelGateway()
            _assert_gateway_error(
                self,
                "invalid_payload",
                lambda: empty_gateway.managed_attach(
                    {
                        "runtime_instance_id": runtime_instance_id,
                        "port": empty_server.port,
                        "credential": credential,
                        "expected_model_alias": "provider-alias",
                        "model_id": "stable-model",
                        "binding_fingerprint": "d" * 64,
                    }
                ),
            )

    def test_model_list_absolute_deadline_stops_slow_body_and_adapter_recovers(self) -> None:
        limits = GatewayLimits(
            connect_timeout_seconds=0.2,
            read_timeout_seconds=0.08,
        )
        with ScenarioServer(
            slow_model_responses=1,
            slow_drip_interval=0.02,
        ) as server:
            adapter = ProviderAdapter(server.port, limits)
            errors: list[BaseException] = []

            def list_slow_models() -> None:
                try:
                    adapter.list_models()
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=list_slow_models, daemon=True)
            worker.start()
            worker.join(0.5)
            self.assertFalse(worker.is_alive(), "slow model body exceeded its absolute deadline")
            self.assertEqual(1, len(errors))
            self.assertIsInstance(errors[0], GatewayError)
            self.assertEqual("sidecar_unavailable", errors[0].code)
            self.assertEqual(("local-model",), adapter.list_models())

    def test_managed_attach_header_deadline_keeps_sidecar_healthy_and_retryable(self) -> None:
        limits = GatewayLimits(
            connect_timeout_seconds=0.3,
            read_timeout_seconds=0.3,
            first_token_timeout_seconds=0.2,
            inactivity_timeout_seconds=0.2,
            overall_timeout_seconds=0.6,
            worker_join_timeout_seconds=0.3,
        )
        with ScenarioServer(
            ("slow_headers", "ready"),
            model_aliases=("provider-alias",),
            slow_drip_interval=0.05,
        ) as server:
            runtime = DesktopSidecarRuntime(session_nonce="a" * 24)
            runtime._model_gateway = LocalModelGateway(limits=limits)
            runtime.handle_message(make_hello("desktop-deadline-hello", session_nonce="b" * 24))
            payload = {
                "runtime_instance_id": "c" * 32,
                "port": server.port,
                "credential": "d" * 64,
                "expected_model_alias": "provider-alias",
                "model_id": "stable-model",
                "binding_fingerprint": "e" * 64,
            }
            result: list[tuple[dict[str, Any], ...]] = []

            def attach_slow_provider() -> None:
                result.append(
                    runtime.handle_message(
                        make_request("slow-attach", "model.managed.attach", payload)
                    )
                )

            worker = threading.Thread(target=attach_slow_provider, daemon=True)
            worker.start()
            worker.join(1.0)
            self.assertFalse(worker.is_alive(), "slow response headers wedged the sidecar request loop")
            self.assertEqual(1, len(result))
            self.assertEqual("error", result[0][0]["type"])
            self.assertEqual("timeout", result[0][0]["payload"]["code"])

            health_id = "hreq_" + "f" * 32
            health = runtime.handle_message(
                make_request(
                    health_id,
                    "app.health",
                    {
                        "type": "health.check",
                        "protocolVersion": 1,
                        "requestId": health_id,
                        "generationId": 1,
                        "startupNonce": "scn_" + "a" * 64,
                        "runtimeInstanceId": "rti_" + "b" * 32,
                        "sentAtUnixMs": 1_700_000_000_000,
                    },
                )
            )
            self.assertEqual("response", health[0]["type"])
            self.assertEqual("health.status", health[0]["payload"]["type"])
            self.assertEqual("ready", health[0]["payload"]["status"])
            self.assertIs(False, health[0]["payload"]["capabilities"]["toolExecution"])
            retry = runtime.handle_message(
                make_request("retry-attach", "model.managed.attach", payload)
            )
            self.assertEqual("response", retry[0]["type"])
            self.assertTrue(retry[0]["payload"]["attached"])
            runtime.close()

    def test_first_token_inactivity_and_overall_timeouts(self) -> None:
        cases = (
            ("first_timeout", "first_token_timeout", []),
            ("inactivity_timeout", "stream_inactivity_timeout", ["A"]),
            ("overall_timeout", "request_timed_out", []),
        )
        for index, (scenario, error_code, expected_deltas) in enumerate(cases):
            with self.subTest(scenario=scenario), ScenarioServer((scenario,)) as server:
                limits = GatewayLimits(
                    read_chunk_bytes=32,
                    connect_timeout_seconds=0.2,
                    first_token_timeout_seconds=0.05 if scenario != "overall_timeout" else 0.3,
                    inactivity_timeout_seconds=0.05 if scenario != "overall_timeout" else 0.3,
                    overall_timeout_seconds=0.05 if scenario == "overall_timeout" else 0.3,
                    worker_join_timeout_seconds=0.3,
                )
                gateway, binding = _bound_gateway(server, limits=limits)
                events: list[tuple[str, str, int, Mapping[str, Any]]] = []
                gateway.start_turn(
                    _turn_request(binding, format(index + 10, "024x")),
                    lambda *event: events.append(event),
                )
                terminal = _wait_for_terminal(events)
                self.assertEqual("model.turn.timed_out", terminal[0])
                self.assertEqual("TimedOut", terminal[3]["state"])
                self.assertEqual(error_code, terminal[3]["metadata"]["error"]["code"])
                self.assertEqual(
                    expected_deltas,
                    [event[3]["text"] for event in events if event[0] == "model.output.delta"],
                )
                self.assertEqual(1, sum(event[0] in TERMINAL_METHODS for event in events))

    def test_cancel_precedence_ack_second_request_and_shutdown_cleanup(self) -> None:
        limits = GatewayLimits(
            read_chunk_bytes=32,
            first_token_timeout_seconds=1.0,
            inactivity_timeout_seconds=1.0,
            overall_timeout_seconds=2.0,
            worker_join_timeout_seconds=0.05,
        )
        with ScenarioServer(("cancel", "order", "cancel")) as server:
            gateway, binding = _bound_gateway(server, limits=limits)
            first_events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            first_id = "f" * 24
            gateway.start_turn(
                _turn_request(binding, first_id),
                lambda *event: first_events.append(event),
            )
            self.assertTrue(server.post_event.wait(1.0))

            mismatch = gateway.cancel_turn({"request_id": "1" * 24})
            self.assertEqual(False, mismatch["accepted"])
            self.assertEqual(True, mismatch["already_terminal"])
            self.assertEqual(False, mismatch["worker_alive"])

            cancelled = gateway.cancel_turn({"request_id": first_id})
            self.assertEqual(
                {
                    "request_id",
                    "turn_id",
                    "state",
                    "accepted",
                    "already_terminal",
                    "worker_alive",
                },
                set(cancelled),
            )
            self.assertEqual(first_id, cancelled["turn_id"])
            self.assertTrue(cancelled["accepted"])
            self.assertFalse(cancelled["already_terminal"])
            self.assertEqual(
                "Cancelling" if cancelled["worker_alive"] else "Cancelled",
                cancelled["state"],
            )
            _wait_for_terminal(first_events)
            snapshot = list(first_events)
            time.sleep(0.35)
            self.assertEqual(snapshot, first_events)
            self.assertEqual(1, sum(event[0] == "model.turn.cancelled" for event in first_events))
            self.assertFalse(any(event[0] in TERMINAL_METHODS - {"model.turn.cancelled"} for event in first_events))

            second_events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            gateway.start_turn(
                _turn_request(binding, "2" * 24),
                lambda *event: second_events.append(event),
            )
            self.assertEqual("model.turn.completed", _wait_for_terminal(second_events)[0])
            self.assertTrue(all(event[1] == "2" * 24 for event in second_events))

            server.post_event.clear()
            shutdown_events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            gateway.start_turn(
                _turn_request(binding, "3" * 24),
                lambda *event: shutdown_events.append(event),
            )
            self.assertTrue(server.post_event.wait(1.0))
            gateway.shutdown()
            _wait_for_terminal(shutdown_events)
            shutdown_snapshot = list(shutdown_events)
            time.sleep(0.35)
            self.assertEqual(shutdown_snapshot, shutdown_events)
            self.assertEqual(1, sum(event[0] == "model.turn.cancelled" for event in shutdown_events))
            self.assertIsNone(gateway._active)

    def test_cancel_before_connect_sends_no_post_and_worker_is_quiescent(self) -> None:
        with ScenarioServer(("order",)) as server:
            gateway, binding = _bound_gateway(server)
            entered = threading.Event()
            release = threading.Event()
            original_stream_chat = ProviderAdapter.stream_chat

            def gated_stream_chat(adapter: ProviderAdapter, *args: Any, **kwargs: Any):
                entered.set()
                if not release.wait(1.0):
                    raise AssertionError("gated model worker was not released")
                yield from original_stream_chat(adapter, *args, **kwargs)

            events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            request_id = "6" * 24
            with mock.patch.object(ProviderAdapter, "stream_chat", gated_stream_chat):
                gateway.start_turn(
                    _turn_request(binding, request_id),
                    lambda *event: events.append(event),
                )
                self.assertTrue(entered.wait(1.0))
                with gateway._lock:
                    self.assertIsNotNone(gateway._active)
                    worker = gateway._active.thread
                    cancel_signal = gateway._active.cancel

                result: dict[str, Any] = {}
                cancel_error: list[BaseException] = []

                def cancel() -> None:
                    try:
                        result.update(gateway.cancel_turn({"request_id": request_id}))
                    except BaseException as exc:
                        cancel_error.append(exc)

                canceller = threading.Thread(target=cancel, daemon=True)
                canceller.start()
                self.assertTrue(cancel_signal.wait(1.0))
                release.set()
                canceller.join(2.0)
                self.assertFalse(canceller.is_alive())
                self.assertEqual([], cancel_error)

                self.assertEqual("Cancelled", result["state"])
                self.assertTrue(result["accepted"])
                self.assertFalse(result["already_terminal"])
                self.assertFalse(result["worker_alive"])
                self.assertFalse(worker.is_alive())
                self.assertEqual([], server.posts)
                self.assertEqual("model.turn.cancelled", _wait_for_terminal(events)[0])
                self.assertEqual(1, sum(event[0] in TERMINAL_METHODS for event in events))

                second_events: list[tuple[str, str, int, Mapping[str, Any]]] = []
                gateway.start_turn(
                    _turn_request(binding, "7" * 24),
                    lambda *event: second_events.append(event),
                )
                self.assertEqual("model.turn.completed", _wait_for_terminal(second_events)[0])
                self.assertEqual(1, len(server.posts))

    def test_shutdown_before_connect_sends_no_post_and_worker_is_quiescent(self) -> None:
        with ScenarioServer(("order",)) as server:
            gateway, binding = _bound_gateway(server)
            entered = threading.Event()
            release = threading.Event()
            original_stream_chat = ProviderAdapter.stream_chat

            def gated_stream_chat(adapter: ProviderAdapter, *args: Any, **kwargs: Any):
                entered.set()
                if not release.wait(1.0):
                    raise AssertionError("gated model worker was not released")
                yield from original_stream_chat(adapter, *args, **kwargs)

            events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            with mock.patch.object(ProviderAdapter, "stream_chat", gated_stream_chat):
                gateway.start_turn(
                    _turn_request(binding, "8" * 24),
                    lambda *event: events.append(event),
                )
                self.assertTrue(entered.wait(1.0))
                with gateway._lock:
                    self.assertIsNotNone(gateway._active)
                    worker = gateway._active.thread
                    cancel_signal = gateway._active.cancel

                shutdown_error: list[BaseException] = []

                def shutdown() -> None:
                    try:
                        gateway.shutdown()
                    except BaseException as exc:
                        shutdown_error.append(exc)

                stopper = threading.Thread(target=shutdown, daemon=True)
                stopper.start()
                self.assertTrue(cancel_signal.wait(1.0))
                release.set()
                stopper.join(2.0)
                self.assertFalse(stopper.is_alive())
                self.assertEqual([], shutdown_error)
                self.assertFalse(worker.is_alive())
                self.assertEqual([], server.posts)
                self.assertEqual("model.turn.cancelled", _wait_for_terminal(events)[0])
                self.assertEqual(1, sum(event[0] in TERMINAL_METHODS for event in events))
                self.assertIsNone(gateway._active)

    def test_managed_attach_timeout_uses_rust_facing_timeout_envelope(self) -> None:
        runtime = DesktopSidecarRuntime(session_nonce="8" * 24)
        runtime.handle_message(make_hello("desktop-timeout-hello", session_nonce="9" * 24))
        payload = {
            "runtime_instance_id": "a" * 32,
            "port": 12345,
            "credential": "b" * 64,
            "expected_model_alias": "provider-alias",
            "model_id": "stable-model",
            "binding_fingerprint": "c" * 64,
        }
        for index, internal_code in enumerate(
            ("first_token_timeout", "inactivity_timeout", "overall_timeout"),
            start=1,
        ):
            with self.subTest(internal_code=internal_code), mock.patch.object(
                runtime._model_gateway,
                "managed_attach",
                side_effect=GatewayError(internal_code, "managed readiness timed out", retryable=True),
            ):
                request_id = f"attach-timeout-{index}"
                messages = runtime.handle_message(
                    make_request(request_id, "model.managed.attach", payload)
                )
                self.assertEqual(1, len(messages))
                self.assertEqual("error", messages[0]["type"])
                self.assertEqual(request_id, messages[0]["reply_to"])
                self.assertEqual("timeout", messages[0]["payload"]["code"])
                self.assertNotEqual("invalid_payload", messages[0]["payload"]["code"])

    def test_runner_avoids_writer_gateway_lock_inversion_during_knowledge_cancel(self) -> None:
        class LockOrderRuntime:
            def __init__(self) -> None:
                self.gateway_lock = threading.RLock()
                self.knowledge_handler_entered = threading.Event()
                self.async_writer = None

            def set_async_message_writer(self, writer) -> None:
                self.async_writer = writer

            def handle_message(self, message: Mapping[str, Any]):
                if message["method"] == "model.turn.start":
                    return (
                        {
                            "type": "response",
                            "reply_to": message["id"],
                            "payload": {"state": "Accepted"},
                        },
                    )
                if message["method"] == "knowledge.turn.decide":
                    self.knowledge_handler_entered.set()
                    with self.gateway_lock:
                        return (
                            {
                                "type": "response",
                                "reply_to": message["id"],
                                "payload": {
                                    "state": "REJECTED",
                                    "action": "CANCEL",
                                    "model_dispatched": False,
                                },
                            },
                        )
                raise AssertionError("unexpected fake sidecar method")

        runtime = LockOrderRuntime()
        acceptance_gate = sidecar_runner._AcceptanceWriteGate(runtime)
        runtime.set_async_message_writer(acceptance_gate.write_async)
        writes: list[dict[str, Any]] = []

        def record_write(_runtime: Any, messages) -> bool:
            with sidecar_runner.WRITE_LOCK:
                writes.extend(tuple(messages))
            return True

        direct_start = {
            "id": "direct-start",
            "method": "model.turn.start",
            "payload": {"request_id": "d" * 24},
        }
        knowledge_cancel = {
            "id": "knowledge-cancel",
            "method": "knowledge.turn.decide",
            "payload": {"action": "CANCEL"},
        }
        event = {
            "type": "event",
            "method": "model.turn.cancelled",
            "run_id": "d" * 24,
        }
        worker_has_gateway_lock = threading.Event()
        release_worker = threading.Event()
        worker_errors: list[BaseException] = []

        def emit_from_direct_worker() -> None:
            try:
                with runtime.gateway_lock:
                    worker_has_gateway_lock.set()
                    if not release_worker.wait(1.0):
                        raise AssertionError("direct worker was not released")
                    if runtime.async_writer is None or not runtime.async_writer((event,)):
                        raise AssertionError("async event write failed")
            except BaseException as exc:
                worker_errors.append(exc)

        knowledge_results: list[bool] = []
        knowledge_errors: list[BaseException] = []

        def handle_knowledge_cancel() -> None:
            try:
                knowledge_results.append(
                    sidecar_runner._handle_and_write(
                        runtime,
                        knowledge_cancel,
                        acceptance_gate,
                    )
                )
            except BaseException as exc:
                knowledge_errors.append(exc)

        with mock.patch.object(sidecar_runner, "_write_messages", record_write):
            self.assertTrue(
                sidecar_runner._handle_and_write(runtime, direct_start, acceptance_gate)
            )
            worker = threading.Thread(target=emit_from_direct_worker, daemon=True)
            worker.start()
            self.assertTrue(worker_has_gateway_lock.wait(1.0))
            knowledge = threading.Thread(target=handle_knowledge_cancel, daemon=True)
            knowledge.start()
            self.assertTrue(runtime.knowledge_handler_entered.wait(1.0))
            release_worker.set()
            worker.join(1.0)
            knowledge.join(1.0)

        self.assertFalse(worker.is_alive())
        self.assertFalse(knowledge.is_alive())
        self.assertEqual([], worker_errors)
        self.assertEqual([], knowledge_errors)
        self.assertEqual([True], knowledge_results)
        self.assertEqual(
            ["direct-start", "knowledge-cancel", "model.turn.cancelled"],
            [message.get("reply_to", message.get("method")) for message in writes],
        )

    def test_gateway_emits_outside_lock_during_concurrent_knowledge_decision(self) -> None:
        with ScenarioServer(("order",)) as server:
            gateway, binding = _bound_gateway(server)
            knowledge_lock = threading.RLock()
            decision_holds_knowledge = threading.Event()
            worker_entered_emit = threading.Event()
            events: list[tuple[str, str, int, Mapping[str, Any]]] = []
            decision_errors: list[BaseException] = []
            busy_codes: list[str] = []

            def tracked_emit(*event: Any) -> None:
                worker_entered_emit.set()
                with knowledge_lock:
                    events.append(event)

            def controlled_stream_chat(
                _adapter: ProviderAdapter,
                _model_id: str,
                _messages: tuple[dict[str, str], ...],
                _cancel: threading.Event,
                on_request_started,
                **_kwargs: Any,
            ):
                if not decision_holds_knowledge.wait(1.0):
                    raise AssertionError("knowledge decision did not take its lock")
                on_request_started()
                yield "safe"

            def make_concurrent_knowledge_decision() -> None:
                try:
                    with knowledge_lock:
                        decision_holds_knowledge.set()
                        if not worker_entered_emit.wait(1.0):
                            raise AssertionError("model worker did not enter tracked emit")
                        payload = gateway.bound_turn_payload("knowledge decision prompt")
                        try:
                            gateway.start_turn(payload, lambda *_event: None)
                        except GatewayError as exc:
                            busy_codes.append(exc.code)
                except BaseException as exc:
                    decision_errors.append(exc)

            with mock.patch.object(
                ProviderAdapter,
                "stream_chat",
                controlled_stream_chat,
            ):
                gateway.start_turn(_turn_request(binding, "9" * 24), tracked_emit)
                with gateway._lock:
                    self.assertIsNotNone(gateway._active)
                    worker = gateway._active.thread
                decision = threading.Thread(
                    target=make_concurrent_knowledge_decision,
                    daemon=True,
                )
                decision.start()
                decision.join(1.0)
                self.assertFalse(decision.is_alive())
                self.assertEqual("model.turn.completed", _wait_for_terminal(events)[0])
                worker.join(1.0)

            self.assertFalse(worker.is_alive())
            self.assertEqual([], decision_errors)
            self.assertEqual(["busy"], busy_codes)
            self.assertEqual(
                list(range(len(events))),
                [event[2] for event in events],
            )
            self.assertEqual(1, sum(event[0] in TERMINAL_METHODS for event in events))

    def test_runner_serializes_acceptance_before_worker_event(self) -> None:
        with ScenarioServer(("order",)) as server:
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment.pop("LOCALCOMET_KNOWLEDGE_VAULT", None)
            environment.pop("LOCALCOMET_KNOWLEDGE_PROJECT_ROOT", None)
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "run_localcomet_desktop_sidecar.py")],
                cwd=str(ROOT),
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            if process.stdout is None:
                self.fail("sidecar stdout is unavailable")
            reader = ProcessFrameReader(process.stdout)
            try:
                self.assertEqual("hello", reader.get()["type"])
                _send_process_message(
                    process,
                    make_hello("desktop-hello", session_nonce="4" * 24),
                )
                self.assertEqual("hello", reader.get()["type"])

                _send_process_message(
                    process,
                    make_request("req-models", "model.models.list", {"port": server.port}),
                )
                models_response = reader.get()
                self.assertEqual("response", models_response["type"])
                self.assertEqual("req-models", models_response["reply_to"])

                _send_process_message(
                    process,
                    make_request(
                        "req-binding",
                        "model.binding.set",
                        {
                            "provider_id": PROVIDER_ID,
                            "harness_id": HARNESS_MINIMAL,
                            "port": server.port,
                            "model_id": "local-model",
                            "confirmed": True,
                            "runtime_instance_id": None,
                        },
                    ),
                )
                binding_response = reader.get()
                self.assertEqual("response", binding_response["type"])
                binding = binding_response["payload"]

                public_request_id = "5" * 24
                _send_process_message(
                    process,
                    make_request(
                        "req-start",
                        "model.turn.start",
                        _turn_request(binding, public_request_id, max_tokens=9),
                        run_id=public_request_id,
                    ),
                )
                first = reader.get()
                self.assertEqual("response", first["type"])
                self.assertEqual("req-start", first["reply_to"])
                self.assertEqual("Accepted", first["payload"]["state"])
                self.assertEqual(public_request_id, first["payload"]["turn_id"])
                self.assertNotIn("prompt", first["payload"])

                event_messages: list[dict[str, Any]] = []
                while not event_messages or event_messages[-1]["method"] not in TERMINAL_METHODS:
                    event_messages.append(reader.get())
                self.assertTrue(all(message["type"] == "event" for message in event_messages))
                self.assertEqual("model.turn.started", event_messages[0]["method"])
                self.assertEqual(
                    list(range(len(event_messages))),
                    [message["sequence"] for message in event_messages],
                )
                self.assertTrue(all(message["run_id"] == public_request_id for message in event_messages))
                self.assertTrue(all(message["payload"]["session_id"] is None for message in event_messages))

                _send_process_message(
                    process,
                    make_request("req-shutdown", "app.shutdown", {}),
                )
                shutdown_messages = (reader.get(), reader.get())
                self.assertEqual({"response", "goodbye"}, {message["type"] for message in shutdown_messages})
                process.wait(timeout=3.0)
                self.assertEqual(0, process.returncode)
            finally:
                if process.stdin is not None:
                    process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2.0)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
