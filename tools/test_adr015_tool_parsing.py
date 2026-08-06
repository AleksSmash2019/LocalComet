#!/usr/bin/env python
"""ADR-015 Block 1 [TDD]: приём и валидация tool calls моделью.

Покрывает: реестр/схемы инструментов (5 files.*), инкрементальную сборку
tool_calls из SSE-дельт (включая разрез посреди JSON-escape и UTF-8 — правка [5]),
валидацию имени и схемы tool call ДО эмиссии ([ОБЯЗ-2]: вне реестра/невалидная
схема -> ошибка, не событие).
"""
from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.local_model_gateway_ru import (  # noqa: E402
    GatewayError,
    GatewayLimits,
    LocalModelGateway,
    ProviderAdapter,
    TOOL_REGISTRY,
    ToolCallAccumulator,
    build_system_instruction,
    build_tool_schemas,
    check_model_response_markers,
    trusted_assistant_context_payload,
    validate_tool_call,
    _reject_tool_markers,
    _validate_assistant_context,
)


def _raises(fn, code: str) -> None:
    try:
        fn()
    except GatewayError as exc:
        assert exc.code == code, f"expected {code}, got {exc.code}"
        return
    raise AssertionError(f"expected GatewayError({code}), none raised")


class ToolRegistryTests(unittest.TestCase):
    def test_registry_has_exactly_five_files_tools(self) -> None:
        self.assertEqual(
            set(TOOL_REGISTRY),
            {"files.read", "files.list", "files.write", "files.create_folder", "files.delete", "shell", "computer_use"},
        )

    def test_build_tool_schemas_is_openai_function_format(self) -> None:
        schemas = build_tool_schemas()
        self.assertEqual(len(schemas), 7)
        for schema in schemas:
            self.assertEqual(schema["type"], "function")
            fn = schema["function"]
            self.assertIn(fn["name"], TOOL_REGISTRY)
            self.assertIsInstance(fn["description"], str)
            params = fn["parameters"]
            self.assertEqual(params["type"], "object")
            self.assertIn("properties", params)
            self.assertIn("required", params)

    def test_files_write_schema_requires_path_and_content(self) -> None:
        schemas = {s["function"]["name"]: s for s in build_tool_schemas()}
        write_required = schemas["files.write"]["function"]["parameters"]["required"]
        self.assertEqual(set(write_required), {"path", "content"})


class ToolCallAccumulatorTests(unittest.TestCase):
    def test_accumulates_a_single_tool_call_across_deltas(self) -> None:
        acc = ToolCallAccumulator()
        acc.feed([{"index": 0, "id": "call_1", "type": "function", "function": {"name": "files.read", "arguments": ""}}])
        acc.feed([{"index": 0, "function": {"arguments": '{"path":'}}])
        acc.feed([{"index": 0, "function": {"arguments": ' "a.txt"}'}}])
        calls = acc.build()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["id"], "call_1")
        self.assertEqual(calls[0]["name"], "files.read")
        self.assertEqual(calls[0]["arguments"], {"path": "a.txt"})

    def test_assembles_arguments_split_mid_escape(self) -> None:
        # Разрез посреди JSON-escape последовательности \" (правая кавычка имени файла).
        acc = ToolCallAccumulator()
        acc.feed([{"index": 0, "id": "c", "type": "function", "function": {"name": "files.write", "arguments": ""}}])
        acc.feed([{"index": 0, "function": {"arguments": '{"path": "a\\"'}}])
        acc.feed([{"index": 0, "function": {"arguments": 'txt", "content": "x"}'}}])
        calls = acc.build()
        self.assertEqual(calls[0]["arguments"], {"path": 'a"txt', "content": "x"})

    def test_assembles_arguments_split_mid_utf8(self) -> None:
        # Аргументы собираются как строка, затем парсятся; UTF-8 декодируется
        # инкрементально в SSE-потоке. Проверяем целостность multi-byte символа.
        acc = ToolCallAccumulator()
        acc.feed([{"index": 0, "id": "c", "type": "function", "function": {"name": "files.write", "arguments": ""}}])
        full = '{"path": "файл.txt", "content": "привет"}'
        mid = len(full) // 2
        acc.feed([{"index": 0, "function": {"arguments": full[:mid]}}])
        acc.feed([{"index": 0, "function": {"arguments": full[mid:]}}])
        calls = acc.build()
        self.assertEqual(calls[0]["arguments"], {"path": "файл.txt", "content": "привет"})

    def test_accumulates_multiple_tool_calls_by_index(self) -> None:
        acc = ToolCallAccumulator()
        acc.feed([
            {"index": 0, "id": "c0", "type": "function", "function": {"name": "files.read", "arguments": ""}},
            {"index": 1, "id": "c1", "type": "function", "function": {"name": "files.list", "arguments": ""}},
        ])
        acc.feed([{"index": 0, "function": {"arguments": '{"path": "a"}'}}])
        acc.feed([{"index": 1, "function": {"arguments": '{"path": "b"}'}}])
        calls = acc.build()
        self.assertEqual(len(calls), 2)
        by_id = {c["id"]: c for c in calls}
        self.assertEqual(by_id["c0"]["arguments"], {"path": "a"})
        self.assertEqual(by_id["c1"]["arguments"], {"path": "b"})

    def test_malformed_stream_tool_call_scalars_are_rejected(self) -> None:
        for delta in (
            [{"index": True, "function": {}}],
            [{"index": 0, "id": 42, "function": {}}],
            [{"index": 0, "function": {"name": 42}}],
            [{"index": 0, "function": {"arguments": {}}}],
        ):
            with self.subTest(delta=delta):
                with self.assertRaisesRegex(GatewayError, "invalid"):
                    ToolCallAccumulator().feed(delta)

    def test_build_with_no_calls_is_empty(self) -> None:
        self.assertEqual(ToolCallAccumulator().build(), [])


class ValidateToolCallTests(unittest.TestCase):
    def test_every_registered_tool_accepts_exact_valid_arguments(self) -> None:
        valid_arguments = {
            "files.read": {"path": "a.txt"},
            "files.list": {"path": "."},
            "files.write": {"path": "a.txt", "content": "data"},
            "files.create_folder": {"path": "new-folder"},
            "files.delete": {"path": "old.txt"},
            "shell": {"command": "ls"},
            "computer_use": {"action": "click", "coordinate": [100, 100], "text": "hello"},
        }
        self.assertEqual(set(valid_arguments), set(TOOL_REGISTRY))
        for name, arguments in valid_arguments.items():
            with self.subTest(tool=name):
                validate_tool_call(name, arguments)

    def test_unknown_tool_is_rejected(self) -> None:
        _raises(lambda: validate_tool_call("files.rename", {"path": "a"}), "invalid_payload")
        _raises(lambda: validate_tool_call("shell.exec", {"cmd": "ls"}), "invalid_payload")

    def test_missing_required_field_is_rejected(self) -> None:
        _raises(lambda: validate_tool_call("files.write", {"path": "a.txt"}), "invalid_payload")
        _raises(lambda: validate_tool_call("files.read", {}), "invalid_payload")

    def test_wrong_type_field_is_rejected(self) -> None:
        _raises(lambda: validate_tool_call("files.read", {"path": 123}), "invalid_payload")
        _raises(lambda: validate_tool_call("files.write", {"path": "a", "content": 42}), "invalid_payload")

    def test_extra_unknown_field_is_rejected(self) -> None:
        _raises(lambda: validate_tool_call("files.read", {"path": "a", "extra": "x"}), "invalid_payload")

    def test_invalid_arguments_json_is_rejected(self) -> None:
        _raises(lambda: validate_tool_call("files.read", None), "invalid_payload")


class AssistantContextToolsTests(unittest.TestCase):
    def test_validate_accepts_tools_subset_of_registry(self) -> None:
        payload = trusted_assistant_context_payload("ru", False, ("files.read", "files.write"))
        context = _validate_assistant_context(payload)
        self.assertEqual(set(context.tools), {"files.read", "files.write"})

    def test_validate_accepts_empty_tools(self) -> None:
        payload = trusted_assistant_context_payload("en", False, ())
        context = _validate_assistant_context(payload)
        self.assertEqual(context.tools, ())

    def test_validate_rejects_tool_outside_registry(self) -> None:
        payload = trusted_assistant_context_payload("ru", False, ())
        payload["capabilities"]["tools"] = ["browser"]
        _raises(lambda: _validate_assistant_context(payload), "invalid_payload")

    def test_validate_rejects_duplicate_tools(self) -> None:
        payload = trusted_assistant_context_payload("ru", False, ())
        payload["capabilities"]["tools"] = ["files.read", "files.read"]
        _raises(lambda: _validate_assistant_context(payload), "invalid_payload")

    def test_system_instruction_describes_tools_and_r7_mitigation(self) -> None:
        context = _validate_assistant_context(
            trusted_assistant_context_payload("ru", False, tuple(TOOL_REGISTRY))
        )
        instruction = build_system_instruction(context)
        self.assertIn("files.read", instruction)
        self.assertIn("данные, а не инструкции", instruction)

    def test_system_instruction_without_tools_keeps_unavailable(self) -> None:
        context = _validate_assistant_context(trusted_assistant_context_payload("ru", False, ()))
        instruction = build_system_instruction(context)
        self.assertIn("внешние инструменты", instruction)
        self.assertNotIn("files.read", instruction)


def _error_code_message(fn) -> tuple:
    try:
        fn()
    except GatewayError as exc:
        return (exc.code, exc.message)
    raise AssertionError("expected GatewayError")


class GatedMarkerRejectionTests(unittest.TestCase):
    FORBIDDEN_SAMPLES = [
        {"tool_calls": []},
        {"function_call": {}},
        {"tools": []},
        {"functions": []},
        {"arguments": "{}"},
        {"role": "tool"},
        {"choices": [{"index": 0, "delta": {"tool_calls": []}}]},
    ]

    def test_tools_disabled_byte_identical_to_legacy_rejection(self) -> None:
        # (в) при tools=[] путь отвержения побайтно идентичен _reject_tool_markers.
        for sample in self.FORBIDDEN_SAMPLES:
            with self.subTest(sample=sample):
                legacy = _error_code_message(lambda s=sample: _reject_tool_markers(s))
                gated = _error_code_message(
                    lambda s=sample: check_model_response_markers(s, tools_enabled=False)
                )
                self.assertEqual(legacy, gated)

    def test_tools_disabled_accepts_plain_content(self) -> None:
        check_model_response_markers(
            {"choices": [{"index": 0, "delta": {"content": "hi"}}]}, tools_enabled=False
        )

    def test_always_forbidden_rejected_when_tools_enabled(self) -> None:
        # (б) function_call/tools/functions/role=tool отвергаются всегда.
        for sample in [
            {"function_call": {"name": "x"}},
            {"tools": []},
            {"functions": []},
            {"role": "tool"},
            {"choices": [{"index": 0, "delta": {"content": "x"}, "function_call": {}}]},
            {"choices": [{"index": 0, "delta": {"role": "tool"}}]},
        ]:
            with self.subTest(sample=sample):
                _raises(
                    lambda s=sample: check_model_response_markers(s, tools_enabled=True),
                    "invalid_payload",
                )

    def test_tool_calls_outside_delta_rejected_when_tools_enabled(self) -> None:
        # (а) tool_calls/arguments в любой позиции кроме choices[].delta.tool_calls.
        for sample in [
            {"tool_calls": []},
            {"arguments": "{}"},
            {"choices": [{"index": 0, "tool_calls": [], "delta": {}}]},
            {"choices": [{"index": 0, "delta": {"arguments": "{}"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "arguments": "{}"}]}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 0, "function": {"name": "f", "tool_calls": []}}
            ]}}]},
        ]:
            with self.subTest(sample=sample):
                _raises(
                    lambda s=sample: check_model_response_markers(s, tools_enabled=True),
                    "invalid_payload",
                )

    def test_wellformed_tool_calls_accepted_when_tools_enabled(self) -> None:
        check_model_response_markers(
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 0, "id": "c1", "type": "function",
                 "function": {"name": "files.read", "arguments": ""}}
            ]}}]},
            tools_enabled=True,
        )

    def test_content_delta_accepted_when_tools_enabled(self) -> None:
        check_model_response_markers(
            {"choices": [{"index": 0, "delta": {"content": "hi"}}]}, tools_enabled=True
        )

    def test_arguments_inside_function_accepted(self) -> None:
        check_model_response_markers(
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": "{\"path\":"}}
            ]}}]},
            tools_enabled=True,
        )


class _ToolFakeProvider(BaseHTTPRequestHandler):
    mode = "content"
    last_body: dict = {}

    def log_message(self, *args):  # silence request logging
        pass

    def do_POST(self):  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_body = json.loads(self.rfile.read(length).decode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if type(self).mode == "tool_calls_stream":
            self.wfile.write(
                b'data: {"choices":[{"index":0,"delta":{"tool_calls":['
                b'{"index":0,"id":"call_1","type":"function","function":{"name":"files.read","arguments":""}}'
                b']},"finish_reason":null}]}\n\n'
            )
            self.wfile.write(
                b'data: {"choices":[{"index":0,"delta":{"tool_calls":['
                b'{"index":0,"function":{"arguments":"{\\"path\\": \\"a.txt\\"}"}}'
                b']},"finish_reason":null}]}\n\n'
            )
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self.wfile.write(b'data: {"choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":null}]}\n\n')
            self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class _ToolFakeServer:
    def __init__(self, mode: str) -> None:
        _ToolFakeProvider.mode = mode
        _ToolFakeProvider.last_body = {}
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _ToolFakeProvider)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def __enter__(self) -> "_ToolFakeServer":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        return False


class MultiTurnMessagesTests(unittest.TestCase):
    def _limits(self):
        from modules.local_model_gateway_ru import GatewayLimits

        return GatewayLimits()

    def _validate(self, messages, tools_enabled):
        from modules.local_model_gateway_ru import _validate_messages

        return _validate_messages(messages, self._limits(), tools_enabled=tools_enabled)

    def test_tools_disabled_only_system_user(self) -> None:
        self._validate(
            ({"role": "system", "content": "s"}, {"role": "user", "content": "u"}),
            tools_enabled=False,
        )
        _raises(
            lambda: self._validate(({"role": "assistant", "content": "a"},), tools_enabled=False),
            "invalid_payload",
        )
        _raises(
            lambda: self._validate(
                ({"role": "tool", "content": "t", "tool_call_id": "c1"},), tools_enabled=False
            ),
            "invalid_payload",
        )

    def test_tools_enabled_allows_assistant_and_tool_roles(self) -> None:
        messages = (
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "files.read", "arguments": "{}"}}
            ]},
            {"role": "tool", "content": "result", "tool_call_id": "c1"},
        )
        self._validate(messages, tools_enabled=True)

    def test_tools_enabled_tool_requires_tool_call_id(self) -> None:
        _raises(
            lambda: self._validate(({"role": "tool", "content": "t"},), tools_enabled=True),
            "invalid_payload",
        )

    def test_tools_enabled_assistant_rejects_unknown_keys(self) -> None:
        _raises(
            lambda: self._validate(
                ({"role": "assistant", "content": "a", "extra": 1},), tools_enabled=True
            ),
            "invalid_payload",
        )


class StreamChatToolCallsTests(unittest.TestCase):
    MESSAGES = ({"role": "user", "content": "hi"},)

    def test_tools_disabled_yields_only_content_strings(self) -> None:
        with _ToolFakeServer("content") as server:
            adapter = ProviderAdapter(server.port, GatewayLimits())
            events = list(
                adapter.stream_chat("local-model", self.MESSAGES, threading.Event(), lambda: None)
            )
        self.assertEqual(events, ["hello"])
        self.assertNotIn("tools", _ToolFakeProvider.last_body)

    def test_tools_enabled_sends_tools_and_yields_tool_call_events(self) -> None:
        accumulator = ToolCallAccumulator()
        with _ToolFakeServer("tool_calls_stream") as server:
            adapter = ProviderAdapter(server.port, GatewayLimits())
            events = list(
                adapter.stream_chat(
                    "local-model",
                    self.MESSAGES,
                    threading.Event(),
                    lambda: None,
                    tools=build_tool_schemas(),
                    tool_call_accumulator=accumulator,
                )
            )
        self.assertIn("tools", _ToolFakeProvider.last_body)
        self.assertEqual(_ToolFakeProvider.last_body["tool_choice"], "auto")
        tool_events = [e for e in events if isinstance(e, dict) and "tool_calls" in e]
        self.assertGreaterEqual(len(tool_events), 1)
        calls = accumulator.build()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "files.read")
        self.assertEqual(calls[0]["arguments"], {"path": "a.txt"})


# ---------------------------------------------------------------------------
# ADR-015 Block 2 [TDD]: интеграция _run_turn — RED-тесты A1–A5.
#
# Эти тесты перехватывают события ИСКЛЮЧИТЕЛЬНО через публичный event stream
# (gateway.start_turn(request, emit_event)); приватные буферы/аккумуляторы не
# читаются. Сравнение сложных структур — через канонический JSON.
#
# Транспорт: локальный FakeServer пишет ответ байтовыми фрагментами
# (wfile.write(bytes) + flush). Gateway использует read_chunk_bytes=1, что
# ГАРАНТИРУЕТ byte-level чтение (в том числе разрез внутри multi-byte UTF-8
# символа) на уровне инкрементального декодера — детерминированно, без привязки
# к таймингам TCP. Для A1 дополнительно режем транспортный фрагмент посередине
# UTF-8 символа. Транспортная слепая зона НЕ фиксируется: byte-level фрагментация
# реализуема локально и покрыта.
#
# RED: текущая реализация эмитит model.tool.request на КАЖДУЮ непустую дельту
# (partial emission), не валидирует batch атомарно и не имеет лимита 10 calls.
# GREEN-контракт: ровно один model.tool.request на валидный call, эмитируется
# ПОСЛЕ атомарной валидации всего batch; при ошибке/превышении лимита —
# model.turn.failed и НОЛЬ model.tool.request.
# ---------------------------------------------------------------------------

_TERMINAL_METHODS = frozenset(
    (
        "model.turn.completed",
        "model.turn.tool_calls",
        "model.turn.cancelled",
        "model.turn.timed_out",
        "model.turn.failed",
    )
)


def _sse_tool_delta(*tool_call_deltas: dict) -> bytes:
    obj = {
        "choices": [
            {"index": 0, "delta": {"tool_calls": list(tool_call_deltas)}, "finish_reason": None}
        ]
    }
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _sse_content(text: str) -> bytes:
    obj = {"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]}
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n\n"


_SSE_DONE = b"data: [DONE]\n\n"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _mid_utf8_cuts(data: bytes, chars: str) -> list:
    """Byte offsets that split `data` between the two bytes of a multi-byte char."""
    cuts = []
    for ch in chars:
        raw = ch.encode("utf-8")
        if len(raw) < 2:
            continue
        start = 0
        while True:
            idx = data.find(raw, start)
            if idx == -1:
                break
            cuts.append(idx + 1)
            start = idx + len(raw)
    return cuts


def _fragment(data: bytes, cuts) -> list:
    bounds = sorted({0, len(data), *(c for c in cuts if 0 < c < len(data))})
    return [data[a:b] for a, b in zip(bounds, bounds[1:])]


class _IntegrationProvider(BaseHTTPRequestHandler):
    fragments: list = []
    fragment_delay: float = 0.0
    last_body: dict = {}

    def log_message(self, *args: Any) -> None:  # silence request logging
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/models":
            self.send_response(404)
            self.end_headers()
            return
        body = b'{"data":[{"id":"local-model"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_body = json.loads(self.rfile.read(length).decode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for fragment in type(self).fragments:
            try:
                self.wfile.write(fragment)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionError, OSError):
                return
            if type(self).fragment_delay:
                time.sleep(type(self).fragment_delay)


class _IntegrationFakeServer:
    def __init__(self, fragments: list, fragment_delay: float = 0.0) -> None:
        _IntegrationProvider.fragments = list(fragments)
        _IntegrationProvider.fragment_delay = fragment_delay
        _IntegrationProvider.last_body = {}
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _IntegrationProvider)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def __enter__(self) -> "_IntegrationFakeServer":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2)
        return False


class ToolCallIntegrationTests(unittest.TestCase):
    """A1–A5: интеграция _run_turn через публичный event stream (RED)."""

    def _bound_gateway(self, port: int) -> tuple:
        # read_chunk_bytes=1 => byte-level чтение (детерминированная фрагментация).
        gateway = LocalModelGateway(limits=GatewayLimits(read_chunk_bytes=1))
        gateway.list_models({"port": port})
        binding = gateway.set_binding(
            {
                "provider_id": "openai-compatible-local",
                "harness_id": "minimal",
                "port": port,
                "model_id": "local-model",
                "confirmed": True,
            }
        )
        return gateway, binding

    def _turn_request(self, binding_fingerprint: str, request_id: str, tools: tuple) -> dict:
        return {
            "request_id": request_id,
            "chat_session_id": "adr015-chat",
            "model_id": "local-model",
            "submitted_at_unix_ms": 1_700_000_000_000,
            "max_tokens": 128,
            "prompt": "hello",
            "assistant_context": trusted_assistant_context_payload("ru", False, tools),
            "binding_fingerprint": binding_fingerprint,
        }

    def _run_turn(self, gateway: LocalModelGateway, request: dict, timeout: float = 6.0) -> list:
        events: list = []
        lock = threading.Lock()

        def emit_event(method: str, turn_id: str, sequence: int, payload: Any) -> None:
            with lock:
                events.append((method, payload))

        gateway.start_turn(request, emit_event)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with lock:
                if any(method in _TERMINAL_METHODS for method, _ in events):
                    return list(events)
            time.sleep(0.005)
        with lock:
            snapshot = [method for method, _ in events]
        raise AssertionError(f"turn did not terminate: {snapshot}")

    @staticmethod
    def _by_method(events: list, method: str) -> list:
        return [payload for seen, payload in events if seen == method]

    # -- A1 -----------------------------------------------------------------
    def test_a1_fragmented_interleaved_calls_atomic_emission(self) -> None:
        # call_0: files.read {"path":"файл.txt"}; call_1: files.write {"path":"out.txt","content":"привет"}.
        # Имена разрезаны, arguments разрезаны внутри JSON-строки, кириллица,
        # дельты двух calls перемежаются по index, byte-level разрез внутри UTF-8.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.", "arguments": ""}}),
            _sse_tool_delta({"index": 1, "id": "call_1", "type": "function", "function": {"name": "files.", "arguments": ""}}),
            _sse_tool_delta({"index": 0, "function": {"name": "read", "arguments": '{"path": "'}}),
            _sse_tool_delta({"index": 1, "function": {"name": "write", "arguments": '{"path": "out.txt", "content": "'}}),
            _sse_tool_delta({"index": 0, "function": {"arguments": "файл"}}),
            _sse_tool_delta({"index": 1, "function": {"arguments": "привет"}}),
            _sse_tool_delta({"index": 0, "function": {"arguments": '.txt"}'}}),
            _sse_tool_delta({"index": 1, "function": {"arguments": '"}'}}),
            _SSE_DONE,
        ]
        full = b"".join(event_chunks)
        cuts = list(_mid_utf8_cuts(full, "фп"))  # разрез посередине UTF-8 символа
        acc = 0
        for chunk in event_chunks[:-1]:  # границы SSE-событий
            acc += len(chunk)
            cuts.append(acc)
        fragments = _fragment(full, cuts)
        # sanity: фрагментация действительно режет multi-byte символ.
        self.assertGreater(len(fragments), len(event_chunks))

        expected_calls = [
            {"id": "call_0", "name": "files.read", "arguments": {"path": "файл.txt"}},
            {"id": "call_1", "name": "files.write", "arguments": {"path": "out.txt", "content": "привет"}},
        ]
        with _IntegrationFakeServer(fragments) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "a" * 24, ("files.read", "files.write"))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        tool_requests = self._by_method(events, "model.tool.request")
        terminals = self._by_method(events, "model.turn.tool_calls")
        # RED: GREEN эмитит ровно один model.tool.request на валидный call (после
        # валидации batch); текущая реализация эмитит по одному на каждую дельту.
        self.assertEqual(len(tool_requests), 2, "expected one model.tool.request per valid call")
        self.assertEqual(self._by_method(events, "model.turn.failed"), [])
        self.assertEqual(len(terminals), 1)
        self.assertEqual(_canon(terminals[0]["metadata"]["tool_calls"]), _canon(expected_calls))
        self.assertEqual(terminals[0]["tools_executed"], 2)

    # -- A2 -----------------------------------------------------------------
    def test_a2_content_and_tool_calls_coexist_atomically(self) -> None:
        event_chunks = [
            _sse_content("Hello, "),
            _sse_content("world!"),
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.read", "arguments": '{"path":'}}),
            _sse_tool_delta({"index": 0, "function": {"arguments": ' "a.txt"}'}}),
            _SSE_DONE,
        ]
        expected_calls = [{"id": "call_0", "name": "files.read", "arguments": {"path": "a.txt"}}]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "b" * 24, ("files.read", "files.write"))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        terminals = [p for m, p in events if m in _TERMINAL_METHODS]
        tool_calls_terminals = self._by_method(events, "model.turn.tool_calls")
        self.assertEqual(len(terminals), 1, "exactly one terminal event expected")
        self.assertEqual(len(tool_calls_terminals), 1)
        terminal = tool_calls_terminals[0]
        # accumulated content не теряется и НЕ дублируется.
        self.assertEqual(terminal["text"], "Hello, world!")
        self.assertEqual(_canon(terminal["metadata"]["tool_calls"]), _canon(expected_calls))
        self.assertEqual(terminal["tools_executed"], 1)
        # RED: один call => один model.tool.request (атомарно); текущая реализация
        # эмитит на каждую дельту (здесь 2 дельты arguments).
        self.assertEqual(len(self._by_method(events, "model.tool.request")), 1)

    def test_a2b_text_after_tool_fragments_stays_zero_until_requests_emit(self) -> None:
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.read", "arguments": '{"path": "a.txt"}'}}),
            _sse_content("explanation after the call"),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "c" * 24, ("files.read",))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        deltas = self._by_method(events, "model.output.delta")
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0]["tools_executed"], 0)
        self.assertEqual(deltas[0]["text"], "explanation after the call")
        requests = self._by_method(events, "model.tool.request")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["tools_executed"], 1)
        terminal = self._by_method(events, "model.turn.tool_calls")
        self.assertEqual(len(terminal), 1)
        self.assertEqual(terminal[0]["tools_executed"], 1)

    # -- A3 -----------------------------------------------------------------
    def test_a3_invalid_batch_is_atomic_no_partial_emission(self) -> None:
        # call_0 валиден, call_1 невалиден (имя вне реестра) => весь batch отвергается.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.read", "arguments": '{"path": "a.txt"}'}}),
            _sse_tool_delta({"index": 1, "id": "call_1", "type": "function", "function": {"name": "shell.exec", "arguments": '{"cmd": "ls"}'}}),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "c" * 24, ("files.read", "files.write"))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        failed = self._by_method(events, "model.turn.failed")
        # RED: при атомарной валидации batch model.tool.request НЕ эмитируется вовсе;
        # текущая реализация эмитит его для валидного call_0 ДО валидации batch.
        self.assertEqual(self._by_method(events, "model.tool.request"), [])
        self.assertEqual(self._by_method(events, "model.turn.tool_calls"), [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["metadata"]["error"]["code"], "invalid_payload")
        self.assertEqual(failed[0]["tools_executed"], 0)

    # -- A4 -----------------------------------------------------------------
    def test_a4a_tools_empty_rejects_model_tool_call_fail_closed(self) -> None:
        # tools=[] + tool_call в ответе модели => fail-closed.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.read", "arguments": '{"path": "a.txt"}'}}),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "d" * 24, ())
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        failed = self._by_method(events, "model.turn.failed")
        self.assertEqual(len(failed), 1, "tool_call with tools=[] must fail closed")
        self.assertEqual(self._by_method(events, "model.turn.tool_calls"), [])
        self.assertEqual(self._by_method(events, "model.tool.request"), [])
        self.assertIn(failed[0]["metadata"]["error"]["code"], {"stream_protocol_error", "invalid_payload"})

    def test_a4b_tools_empty_plain_content_completes(self) -> None:
        event_chunks = [_sse_content("hi "), _sse_content("there"), _SSE_DONE]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "e" * 24, ())
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        completed = self._by_method(events, "model.turn.completed")
        self.assertEqual(len(completed), 1)
        self.assertEqual(self._by_method(events, "model.turn.failed"), [])
        self.assertEqual(self._by_method(events, "model.turn.tool_calls"), [])
        streamed = "".join(p["text"] for p in self._by_method(events, "model.output.delta"))
        self.assertEqual(streamed, "hi there")
        self.assertEqual(completed[0]["tools_executed"], 0)

    # -- A5 -----------------------------------------------------------------
    def test_a5_ten_tool_calls_allowed_atomic(self) -> None:
        event_chunks = []
        expected_calls = []
        for i in range(10):
            event_chunks.append(
                _sse_tool_delta({"index": i, "id": f"call_{i}", "type": "function", "function": {"name": "files.read", "arguments": '{"path":'}})
            )
            event_chunks.append(_sse_tool_delta({"index": i, "function": {"arguments": f' "p{i}"}}'}}))
            expected_calls.append({"id": f"call_{i}", "name": "files.read", "arguments": {"path": f"p{i}"}})
        event_chunks.append(_SSE_DONE)
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "f" * 24, ("files.read", "files.write"))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        terminals = self._by_method(events, "model.turn.tool_calls")
        self.assertEqual(self._by_method(events, "model.turn.failed"), [])
        self.assertEqual(len(terminals), 1)
        self.assertEqual(_canon(terminals[0]["metadata"]["tool_calls"]), _canon(expected_calls))
        self.assertEqual(terminals[0]["tools_executed"], 10)
        # RED: ровно один model.tool.request на call (атомарно); текущая реализация
        # эмитит по одному на дельту (здесь 2 дельты на call => 20).
        self.assertEqual(len(self._by_method(events, "model.tool.request")), 10)

    def test_a5_eleven_tool_calls_rejected_atomically(self) -> None:
        event_chunks = []
        for i in range(11):
            event_chunks.append(
                _sse_tool_delta({"index": i, "id": f"call_{i}", "type": "function", "function": {"name": "files.read", "arguments": f'{{"path": "p{i}"}}'}})
            )
        event_chunks.append(_SSE_DONE)
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "1" * 24, ("files.read", "files.write"))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        failed = self._by_method(events, "model.turn.failed")
        # RED: лимит 10 calls отсутствует => текущая реализация успешно эмитит
        # model.turn.tool_calls с 11 calls вместо атомарного отказа.
        self.assertEqual(len(failed), 1, "11 tool calls must be rejected atomically")
        self.assertEqual(failed[0]["metadata"]["error"]["code"], "tool_call_limit_exceeded")
        self.assertEqual(self._by_method(events, "model.tool.request"), [])
        self.assertEqual(self._by_method(events, "model.turn.tool_calls"), [])
        self.assertEqual(failed[0]["tools_executed"], 0)

    def test_edge_duplicate_index_merges_into_single_call(self) -> None:
        # Протокольное нарушение: две дельты с одним index сливаются в один call
        # (ToolCallAccumulator.setdefault). Документирует текущее поведение:
        # name и arguments конкатенируются, id перезаписывается последним non-None.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.re", "arguments": ""}}),
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "ad", "arguments": '{"path":'}}),
            _sse_tool_delta({"index": 0, "function": {"arguments": ' "a.txt"}'}}),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "1" * 24, ("files.read",))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        terminals = self._by_method(events, "model.turn.tool_calls")
        self.assertEqual(len(terminals), 1)
        self.assertEqual(len(terminals[0]["metadata"]["tool_calls"]), 1, "duplicate index merges into one call")
        self.assertEqual(terminals[0]["metadata"]["tool_calls"][0]["name"], "files.read")
        self.assertEqual(terminals[0]["metadata"]["tool_calls"][0]["arguments"], {"path": "a.txt"})
        self.assertEqual(terminals[0]["tools_executed"], 1)

    def test_edge_duplicate_id_last_non_none_wins(self) -> None:
        # Две дельты одного index с разными id: побеждает последний non-None.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_first", "type": "function", "function": {"name": "files.read", "arguments": ""}}),
            _sse_tool_delta({"index": 0, "id": "call_second", "function": {"arguments": '{"path": "a.txt"}'}}),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "1" * 24, ("files.read",))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        terminals = self._by_method(events, "model.turn.tool_calls")
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0]["metadata"]["tool_calls"][0]["id"], "call_second", "last non-None id wins")

    def test_edge_broken_json_arguments_fails_atomically(self) -> None:
        # Битый JSON arguments → model.turn.failed (invalid_payload) атомарно:
        # ни model.tool.request, ни model.turn.tool_calls, tools_executed=0.
        event_chunks = [
            _sse_tool_delta({"index": 0, "id": "call_0", "type": "function", "function": {"name": "files.read", "arguments": '{"path": broken'}}),
            _SSE_DONE,
        ]
        with _IntegrationFakeServer(list(event_chunks)) as server:
            gateway, binding = self._bound_gateway(server.port)
            try:
                request = self._turn_request(binding["binding_fingerprint"], "1" * 24, ("files.read",))
                events = self._run_turn(gateway, request)
            finally:
                gateway.shutdown()

        failed = self._by_method(events, "model.turn.failed")
        self.assertEqual(len(failed), 1, "broken JSON arguments must fail atomically")
        self.assertEqual(failed[0]["metadata"]["error"]["code"], "invalid_payload")
        self.assertEqual(self._by_method(events, "model.tool.request"), [])
        self.assertEqual(self._by_method(events, "model.turn.tool_calls"), [])
        self.assertEqual(failed[0]["tools_executed"], 0)

    @unittest.skip(
        "iteration limit (5) — frontend orchestration (Block 3/4), not a _run_turn concern; "
        "unblock when Block 3/4 adds the client-side orchestration loop and its own test surface"
    )
    def test_a5_iteration_limit_is_frontend_orchestration(self) -> None:
        # Условие устранения: Block 3/4 реализует оркестрацию итераций на фронтенде
        # (лимит 5) — тогда тест переносится в соответствующий frontend-набор.
        self.fail("iteration limit is out of scope for _run_turn")


class B5LPResourceLimitTests(unittest.TestCase):
    def _feed(self, acc: ToolCallAccumulator, raw: str, index: int = 0, call_id: str = "c1") -> None:
        acc.feed([{"index": index, "id": call_id, "type": "function", "function": {"name": "files.read", "arguments": raw}}])

    def test_b5lp_small_arguments_object_accepted(self) -> None:
        acc = ToolCallAccumulator()
        self._feed(acc, '{"path": "a.txt"}')
        calls = acc.build()
        self.assertEqual(calls[0]["arguments"], {"path": "a.txt"})

    def test_b5lp_exact_raw_byte_limit_accepted(self) -> None:
        raw = '{"k": "' + "x" * 65527 + '"}'
        self.assertEqual(len(raw.encode("utf-8")), 65536)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertIsInstance(calls[0]["arguments"], dict)
        self.assertIn("k", calls[0]["arguments"])

    def test_b5lp_exact_depth_limit_accepted(self) -> None:
        raw = "{"
        for i in range(31):
            raw += '"k%d":{' % i
        raw += '"leaf":1'
        raw += "}" * 32
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertIsNotNone(calls[0]["arguments"])

    def test_b5lp_exact_object_key_limit_accepted(self) -> None:
        raw = json.dumps({f"k{i}": "v" for i in range(512)})
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertEqual(len(calls[0]["arguments"]), 512)

    def test_b5lp_exact_node_limit_accepted(self) -> None:
        raw = json.dumps({"data": list(range(4094))})
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertIsNotNone(calls[0]["arguments"])

    def test_b5lp_duplicate_keys_still_rejected(self) -> None:
        acc = ToolCallAccumulator()
        self._feed(acc, '{"path": "a", "path": "b"}')
        calls = acc.build()
        self.assertIsNone(calls[0]["arguments"])
        _raises(lambda: validate_tool_call("files.read", None), "invalid_payload")

    def test_b5lp_malformed_json_still_rejected(self) -> None:
        acc = ToolCallAccumulator()
        self._feed(acc, '{"path": broken')
        calls = acc.build()
        self.assertIsNone(calls[0]["arguments"])
        _raises(lambda: validate_tool_call("files.read", None), "invalid_payload")

    def test_b5lp_non_object_still_rejected(self) -> None:
        acc = ToolCallAccumulator()
        self._feed(acc, "[1, 2, 3]")
        calls = acc.build()
        self.assertEqual(calls[0]["arguments"], [1, 2, 3])
        with self.assertRaises(GatewayError) as ctx:
            validate_tool_call("files.read", [1, 2, 3])
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments must be an object")

    def test_b5lp_raw_byte_limit_plus_one_rejected(self) -> None:
        raw = '{"k": "' + "x" * 65528 + '"}'
        self.assertEqual(len(raw.encode("utf-8")), 65537)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum size")

    def test_b5lp_unicode_byte_limit_plus_one_rejected(self) -> None:
        raw = '{"k": "' + "\u0444" * 32764 + '"}'
        self.assertEqual(len(raw.encode("utf-8")), 65537)
        self.assertLess(len(raw), 65537)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum size")

    def test_b5lp_depth_limit_plus_one_rejected(self) -> None:
        raw = "{"
        for i in range(32):
            raw += '"k%d":{' % i
        raw += '"leaf":1'
        raw += "}" * 33
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum nesting depth")

    def test_b5lp_object_key_limit_plus_one_rejected(self) -> None:
        raw = json.dumps({f"k{i}": "v" for i in range(513)})
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum object key count")

    def test_b5lp_node_limit_plus_one_rejected(self) -> None:
        raw = json.dumps({"data": list(range(4095))})
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum node count")

    def test_b5lp_size_error_precedes_json_parse_error(self) -> None:
        raw = "{" * 70000
        self.assertGreater(len(raw.encode("utf-8")), 65536)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum size")

    def test_b5lp_depth_error_precedes_json_parse_error(self) -> None:
        raw = "[" * 40 + "broken"
        self.assertLess(len(raw.encode("utf-8")), 65536)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum nesting depth")

    def test_b5lp_depth_scanner_ignores_braces_inside_strings(self) -> None:
        raw = '{"k": "{{{{[[[[[[[[[[[[[[[[[[[[[[[[[[[[}}}}]]]]]]]]]]]]]]]]]]]]]]]]]]]]"}'
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertEqual(calls[0]["arguments"], {"k": "{{{{[[[[[[[[[[[[[[[[[[[[[[[[[[[[}}}}]]]]]]]]]]]]]]]]]]]]]]]]]]]]"})

    def test_b5lp_depth_scanner_handles_escaped_quotes(self) -> None:
        raw = '{"k": "a\\"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[b"}'
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        calls = acc.build()
        self.assertIsInstance(calls[0]["arguments"], dict)
        self.assertIn("k", calls[0]["arguments"])

    def test_b5lp_invalid_second_call_emits_no_partial_batch(self) -> None:
        raw_over = '{"k": "' + "x" * 65528 + '"}'
        self.assertEqual(len(raw_over.encode("utf-8")), 65537)
        acc = ToolCallAccumulator()
        self._feed(acc, '{"path": "a.txt"}', index=0, call_id="c0")
        self._feed(acc, raw_over, index=1, call_id="c1")
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum size")

    def test_b5lp_limit_failure_preserves_accumulator_state(self) -> None:
        raw = '{"k": "' + "x" * 65528 + '"}'
        self.assertEqual(len(raw.encode("utf-8")), 65537)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx1:
            acc.build()
        self.assertEqual(ctx1.exception.code, "invalid_payload")
        self.assertEqual(ctx1.exception.message, "tool arguments exceed maximum size")
        with self.assertRaises(GatewayError) as ctx2:
            acc.build()
        self.assertEqual(ctx2.exception.code, "invalid_payload")
        self.assertEqual(ctx2.exception.message, "tool arguments exceed maximum size")

    def test_b5lp_fixed_precedence_for_multiple_limit_violations(self) -> None:
        raw = "[" * 40 + '"x"' * 22000 + "]" * 40
        self.assertGreater(len(raw.encode("utf-8")), 65536)
        acc = ToolCallAccumulator()
        self._feed(acc, raw)
        with self.assertRaises(GatewayError) as ctx:
            acc.build()
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertEqual(ctx.exception.message, "tool arguments exceed maximum size")


class CrossLayerParityTests(unittest.TestCase):
    """Phase C: actual Python emission must match the shared three-layer contract."""

    def test_phase_c_python_emission_matches_shared_tool_event_contract(self) -> None:
        corpus = json.loads(
            (ROOT / "security" / "contracts" / "adr015_tool_event_parity_v1.json").read_text(
                encoding="utf-8"
            )
        )
        identity = corpus["identity"]
        enabled = corpus["enabled"]
        calls = enabled["events"][-1]["toolCalls"]
        chunks = [
            _sse_tool_delta(
                {
                    "index": index,
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], separators=(",", ":")),
                    },
                }
            )
            for index, call in enumerate(calls)
        ] + [_SSE_DONE]

        with _IntegrationFakeServer(chunks) as server:
            gateway = LocalModelGateway(limits=GatewayLimits(read_chunk_bytes=1))
            gateway.list_models({"port": server.port})
            binding = gateway.set_binding(
                {
                    "provider_id": "openai-compatible-local",
                    "harness_id": "minimal",
                    "port": server.port,
                    "model_id": identity["modelId"],
                    "confirmed": True,
                }
            )
            request = {
                "request_id": identity["requestId"],
                "chat_session_id": identity["chatSessionId"],
                "model_id": identity["modelId"],
                "submitted_at_unix_ms": identity["submittedAtUnixMs"],
                "max_tokens": identity["maxTokens"],
                "prompt": "hello",
                "assistant_context": trusted_assistant_context_payload(
                    "ru", False, tuple(enabled["permittedTools"])
                ),
                "binding_fingerprint": binding["binding_fingerprint"],
            }
            try:
                events = ToolCallIntegrationTests._run_turn(self, gateway, request)
            finally:
                gateway.shutdown()

        observed = [
            {
                "method": method,
                "toolsExecuted": payload["tools_executed"],
                "toolCalls": payload["metadata"]["tool_calls"],
            }
            for method, payload in events
            if method in {"model.tool.request", "model.turn.tool_calls"}
        ]
        expected = [
            {
                "method": event["method"],
                "toolsExecuted": event["toolsExecuted"],
                "toolCalls": event["toolCalls"],
            }
            for event in enabled["events"]
        ]
        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
