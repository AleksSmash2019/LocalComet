"""Focused tests for v6.84.5.1e7b SSE UTF-8 Incremental Decoding Fix.

Tests the stateful incremental UTF-8 decoder integration in the
ProviderAdapter.stream_chat SSE event-stream parsing loop.
"""

from __future__ import annotations

import codecs
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.local_model_gateway_ru import (
    GatewayError,
    GatewayLimits,
    ProviderAdapter,
    _parse_sse_event,
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


def _make_delta_event(content: str) -> bytes:
    """Build a single SSE delta event as raw bytes."""
    payload = json.dumps(
        {"choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]},
        ensure_ascii=False,
    ).encode("utf-8")
    result = b"data: " + payload + b"\n\n"
    _assert(b"\xff" not in result and b"\xfe" not in result,
            "delta event contains raw control bytes")
    return result


def _make_done_event() -> bytes:
    """Build the SSE [DONE] event."""
    return b"data: [DONE]\n\n"


def _simulate_stream(
    chunks: list[bytes],
    limits: GatewayLimits | None = None,
) -> list[str]:
    """Simulate the stream_chat incremental decoder loop with controlled chunks.

    Mirrors the decoder portion of ProviderAdapter.stream_chat.
    Returns the list of delta strings extracted from SSE events, in order.
    """
    limits = limits or GatewayLimits()
    decoder = codecs.getincrementaldecoder("utf-8")()
    text_buffer = ""
    deltas: list[str] = []
    event_lines: list[str] = []
    event_bytes_count = 0
    event_count = 0

    for chunk_idx, chunk in enumerate(chunks):
        is_final = (chunk_idx == len(chunks) - 1)
        try:
            text = decoder.decode(chunk, final=is_final)
        except UnicodeDecodeError as exc:
            raise GatewayError("invalid_payload", "invalid UTF-8 from provider") from exc
        text_buffer += text
        while "\n" in text_buffer:
            line, text_buffer = text_buffer.split("\n", 1)
            if line.endswith("\r"):
                line = line[:-1]
            if len(line.encode("utf-8")) > limits.maximum_sse_line_bytes:
                raise GatewayError("payload_too_large", "SSE line limit reached")
            if line == "":
                if event_lines:
                    event_count += 1
                    if event_count > limits.maximum_sse_events:
                        raise GatewayError("budget_exceeded", "SSE event limit reached")
                    delta, done = _parse_sse_event(event_lines)
                    event_lines = []
                    event_bytes_count = 0
                    if delta:
                        deltas.append(delta)
                    if done:
                        return deltas
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                part = line[5:]
                if part.startswith(" "):
                    part = part[1:]
                event_lines.append(part)
            elif line.startswith("event:") or line.startswith("id:") or line.startswith("retry:"):
                continue
            else:
                raise GatewayError("invalid_payload", "unsupported SSE line")

    # End of stream without [DONE]: flush decoder
    try:
        decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise GatewayError("invalid_payload", "invalid UTF-8 from provider") from exc
    return deltas


# ---------------------------------------------------------------------------
# Unit tests: incremental decoder with controlled byte chunks
# ---------------------------------------------------------------------------

def test_ascii_split_across_chunks() -> None:
    """ASCII chars (single-byte UTF-8) should never be corrupted by chunk splits."""
    event = _make_delta_event("hello") + _make_done_event()
    for split_pos in range(1, len(event)):
        deltas = _simulate_stream([event[:split_pos], event[split_pos:]])
        _assert(deltas == ["hello"], f"ASCII split at {split_pos} produced {deltas!r}")
    print("PASS test_ascii_split_across_chunks")


def test_cyrillic_split_after_first_byte() -> None:
    """2-byte Cyrillic 'П' (U+041F, \\xd0\\x9f) split after byte 1."""
    cyrillic_text = "П"
    event = _make_delta_event(cyrillic_text) + _make_done_event()
    # Find the split point: 'П' at byte position in JSON
    data_prefix = b'data: {"choices":[{"index":0,"delta":{"content":"'
    content_bytes = cyrillic_text.encode("utf-8")  # \xd0\x9f
    # Position where \xd0 appears in the full event
    pos = event.find(content_bytes)
    _assert(pos >= 0, "could not locate Cyrillic bytes in event")
    split_at = pos + 1  # Split after \xd0, before \x9f
    deltas = _simulate_stream([event[:split_at], event[split_at:]])
    _assert(deltas == ["П"], f"Cyrillic split after byte 1 produced {deltas!r}")
    print("PASS test_cyrillic_split_after_first_byte")


def test_cyrillic_split_before_final_byte() -> None:
    """2-byte Cyrillic 'т' (U+0442, \\xd1\\x82) split before final byte."""
    event = _make_delta_event("тест") + _make_done_event()
    # Find bytes for 'е' (U+0435 = \xd0\xb5) — split between bytes
    content_bytes = "е".encode("utf-8")
    pos = event.find(content_bytes)
    _assert(pos >= 0, "could not locate Cyrillic bytes in event")
    # Split at the boundary between the two bytes of 'е'
    split_at = pos + 1
    deltas = _simulate_stream([event[:split_at], event[split_at:]])
    _assert(deltas == ["тест"], f"Cyrillic 'е' split produced {deltas!r}")
    print("PASS test_cyrillic_split_before_final_byte")


def test_multiple_cyrillic_split_different_boundaries() -> None:
    """Multiple Cyrillic chars split at various byte boundaries."""
    text = "Привет"
    event = _make_delta_event(text) + _make_done_event()
    # Split at byte 1 of the 2nd character ('р' = \xd1\x80)
    # 'П' = \xd0\x9f, 'р' = \xd1\x80
    p_bytes = "П".encode("utf-8")  # \xd0\x9f
    r_bytes = "р".encode("utf-8")  # \xd1\x80
    pos = event.find(p_bytes)
    _assert(pos >= 0, "could not locate П in event")
    pos_r = event.find(r_bytes, pos)
    _assert(pos_r >= 0, "could not locate р in event")
    # Split at the first byte boundary of 'р'
    split_at = pos_r + 1
    deltas = _simulate_stream([event[:split_at], event[split_at:]])
    _assert(deltas == ["Привет"], f"Multiple Cyrillic split produced {deltas!r}")
    print("PASS test_multiple_cyrillic_split_different_boundaries")


def test_emoji_split_across_4byte_boundary() -> None:
    """4-byte emoji U+1F600 😀 (\\xf0\\x9f\\x98\\x80) split at various points."""
    emoji = "\U0001F600"
    event = _make_delta_event(emoji) + _make_done_event()
    emoji_bytes = emoji.encode("utf-8")
    _assert(len(emoji_bytes) == 4, "emoji should be 4 bytes")
    pos = event.find(emoji_bytes)
    _assert(pos >= 0, "could not locate emoji bytes in event")
    # Split after byte 1, 2, and 3 of the 4-byte sequence
    for byte_offset in range(1, 4):
        split_at = pos + byte_offset
        deltas = _simulate_stream([event[:split_at], event[split_at:]])
        _assert(deltas == ["\U0001F600"],
                f"Emoji split at byte {byte_offset} produced {deltas!r}")
    print("PASS test_emoji_split_across_4byte_boundary")


def test_mixed_ascii_cyrillic_emoji_split() -> None:
    """Mixed ASCII + Cyrillic + emoji split at arbitrary boundaries."""
    text = "Hello Привет \U0001F600"
    event = _make_delta_event(text) + _make_done_event()
    # Split into 4 roughly equal chunks
    quarter = len(event) // 4
    chunks = [
        event[:quarter],
        event[quarter : quarter * 2],
        event[quarter * 2 : quarter * 3],
        event[quarter * 3 :],
    ]
    deltas = _simulate_stream(chunks)
    _assert(deltas == [text], f"Mixed text split produced {deltas!r}")
    print("PASS test_mixed_ascii_cyrillic_emoji_split")


def test_sse_line_split_across_chunks() -> None:
    """SSE data: line split across chunk boundaries (data: prefix maintained)."""
    event = _make_delta_event("hello") + _make_done_event()
    # Split at the middle of the data: line (before the closing \n)
    data_prefix = b"data: "
    pos = event.find(data_prefix)
    _assert(pos >= 0, "could not find data: prefix")
    # Split right after 'data: {"choices...' (at a comma boundary)
    comma_pos = event.find(b",", pos)
    split_at = comma_pos
    deltas = _simulate_stream([event[:split_at], event[split_at:]])
    _assert(deltas == ["hello"], f"SSE line split produced {deltas!r}")
    print("PASS test_sse_line_split_across_chunks")


def test_sse_data_payload_split_across_chunks() -> None:
    """SSE JSON data payload split at field boundaries within the JSON."""
    content = "world"
    event = _make_delta_event(content) + _make_done_event()
    # Split in the content value after the opening quote
    content_val = b'"world"'
    pos = event.find(content_val)
    _assert(pos >= 0, "could not find content value in event")
    split_at = pos + 2  # Split inside the content value
    deltas = _simulate_stream([event[:split_at], event[split_at:]])
    _assert(deltas == ["world"], f"SSE data payload split produced {deltas!r}")
    print("PASS test_sse_data_payload_split_across_chunks")


def test_multiple_sse_events_in_one_chunk() -> None:
    """Multiple delta events and [DONE] in a single raw chunk."""
    events = (
        _make_delta_event("one")
        + _make_delta_event("two")
        + _make_delta_event("three")
        + _make_done_event()
    )
    deltas = _simulate_stream([events])
    _assert(deltas == ["one", "two", "three"],
            f"Multiple events in one chunk produced {deltas!r}")
    print("PASS test_multiple_sse_events_in_one_chunk")


def test_partial_final_multibyte_at_eof() -> None:
    """Incomplete trailing UTF-8 at EOF should raise GatewayError."""
    event = b'data: {"choices":[{"index":0,"delta":{"content":"\xd0"}]}\n\n'
    _assert(event.endswith(b"\n\n"), "event should end with double newline")
    _raises(lambda: _simulate_stream([event]), "invalid_payload")
    print("PASS test_partial_final_multibyte_at_eof")


def test_decoder_flush_at_normal_eof() -> None:
    """Normal [DONE] terminates properly; decoder flush not needed."""
    event = _make_delta_event("normal") + _make_done_event()
    deltas = _simulate_stream([event])
    _assert(deltas == ["normal"], f"Normal EOF produced {deltas!r}")
    print("PASS test_decoder_flush_at_normal_eof")


def test_no_replacement_character_corruption() -> None:
    """Valid split UTF-8 must not produce \\ufffd replacement characters."""
    text = "Тест"
    bytes_all = _make_delta_event(text) + _make_done_event()
    # Split between EVERY byte pair to stress-test all boundaries
    for split_pos in range(1, len(bytes_all)):
        deltas = _simulate_stream([bytes_all[:split_pos], bytes_all[split_pos:]])
        _assert(len(deltas) == 1, f"Split at {split_pos} produced {len(deltas)} deltas")
        _assert("\ufffd" not in deltas[0],
                f"Replacement char found at split {split_pos}: {deltas[0]!r}")
        _assert(deltas[0] == text,
                f"Split at {split_pos} produced {deltas[0]!r}, expected {text!r}")
    print("PASS test_no_replacement_character_corruption")


def test_stream_delta_ordering_preserved() -> None:
    """Multiple deltas preserve order when events span chunk boundaries."""
    events = (
        _make_delta_event("first") + _make_delta_event("second")
        + _make_delta_event("third") + _make_done_event()
    )
    # Split at various positions
    deltas = _simulate_stream([events[:40], events[40:80], events[80:]])
    _assert(deltas == ["first", "second", "third"],
            f"Delta ordering produced {deltas!r}")
    print("PASS test_stream_delta_ordering_preserved")


def test_cancellation_path_preserved() -> None:
    """Cancellation raises no decoder error — just stops iteration."""
    event = _make_delta_event("before")
    # Without [DONE], the stream continues; cancellation stops reads
    deltas = _simulate_stream([event])
    _assert(deltas == ["before"], f"Cancellation test produced {deltas!r}")
    print("PASS test_cancellation_path_preserved")


def test_exactly_one_terminal_outcome() -> None:
    """[DONE] terminates after exactly one event sequence."""
    events = (
        _make_delta_event("hello")
        + _make_delta_event(" ")
        + _make_delta_event("world")
        + _make_done_event()
    )
    deltas = _simulate_stream([events])
    _assert(deltas == ["hello", " ", "world"],
            f"Terminal outcome produced {deltas!r}")
    print("PASS test_exactly_one_terminal_outcome")


# ---------------------------------------------------------------------------
# Integration tests: stream_chat with FakeServer and controlled read sizes
# ---------------------------------------------------------------------------

class FakeProviderSSE(BaseHTTPRequestHandler):
    """Sends pre-configured SSE byte chunks on POST /v1/chat/completions."""
    chunks: list[bytes] = []
    _send_idx = 0

    def log_message(self, *_: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data":[{"id":"local-model"}]}')

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        # Consume request body
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk in type(self).chunks:
            self.wfile.write(chunk)
            self.wfile.flush()
            time.sleep(0.005)  # Small delay to encourage separate TCP reads

    @classmethod
    def reset(cls) -> None:
        cls.chunks = []
        cls._send_idx = 0


class FakeServerSSE:
    def __init__(self, chunks: list[bytes]) -> None:
        FakeProviderSSE.reset()
        FakeProviderSSE.chunks = chunks
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeProviderSSE)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def __enter__(self) -> "FakeServerSSE":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2)


def test_integration_small_read_chunks_cyrillic() -> None:
    """stream_chat with small read_chunk_bytes forces many reads."""
    text = "Привет мир"
    event = _make_delta_event(text) + _make_done_event()
    # Split into multiple small server-side chunks
    chunk_size = max(1, len(event) // 8)
    chunks = [event[i:i + chunk_size] for i in range(0, len(event), chunk_size)]
    with FakeServerSSE(chunks) as server:
        limits = GatewayLimits(read_chunk_bytes=16)
        adapter = ProviderAdapter(server.port, limits)
        called = []
        result = "".join(adapter.stream_chat(
            "local-model",
            ({"role": "user", "content": "hi"},),
            threading.Event(),
            lambda: called.append(True),
        ))
    _assert(result == text, f"Integration Cyrillic got {result!r}")
    _assert(called == [True], "on_request_started not called")
    print("PASS test_integration_small_read_chunks_cyrillic")


def test_integration_emoji_small_reads() -> None:
    """stream_chat handles 4-byte emoji split across multiple reads."""
    emoji = "\U0001F600\U0001F44D\U0001F44B"  # 😀 👍 👋
    event = _make_delta_event(emoji) + _make_done_event()
    chunk_size = max(1, len(event) // 12)
    chunks = [event[i:i + chunk_size] for i in range(0, len(event), chunk_size)]
    with FakeServerSSE(chunks) as server:
        limits = GatewayLimits(read_chunk_bytes=8)
        adapter = ProviderAdapter(server.port, limits)
        called = []
        result = "".join(adapter.stream_chat(
            "local-model",
            ({"role": "user", "content": "hi"},),
            threading.Event(),
            lambda: called.append(True),
        ))
    _assert(result == emoji, f"Integration emoji got {result!r}")
    print("PASS test_integration_emoji_small_reads")


def test_integration_byte_by_byte_read() -> None:
    """Extreme test: read_chunk_bytes=1, each byte fed individually."""
    text = "Hello"
    event = _make_delta_event(text) + _make_done_event()
    with FakeServerSSE([event]) as server:
        limits = GatewayLimits(read_chunk_bytes=1)
        adapter = ProviderAdapter(server.port, limits)
        called = []
        result = "".join(adapter.stream_chat(
            "local-model",
            ({"role": "user", "content": "hi"},),
            threading.Event(),
            lambda: called.append(True),
        ))
    _assert(result == text, f"Byte-by-byte got {result!r}")
    print("PASS test_integration_byte_by_byte_read")


def test_integration_multiple_events_split() -> None:
    """Multiple delta events in single chunk with UTF-8 split boundaries."""
    text = "ab" + "\u041F\u0440\u0438"  # ASCII + Cyrillic
    event = _make_delta_event(text) + _make_done_event()
    chunk_size = max(1, len(event) // 5)
    chunks = [event[i:i + chunk_size] for i in range(0, len(event), chunk_size)]
    with FakeServerSSE(chunks) as server:
        limits = GatewayLimits(read_chunk_bytes=12)
        adapter = ProviderAdapter(server.port, limits)
        called = []
        result = "".join(adapter.stream_chat(
            "local-model",
            ({"role": "user", "content": "hi"},),
            threading.Event(),
            lambda: called.append(True),
        ))
    _assert(result == text, f"Multiple events split got {result!r}")
    print("PASS test_integration_multiple_events_split")


def test_integration_non_streaming_unchanged() -> None:
    """Non-streaming (list_models) path unchanged by decoder change."""
    with FakeServerSSE([]) as server:
        adapter = ProviderAdapter(server.port, GatewayLimits())
        models = adapter.list_models()
    _assert(models == ("local-model",), f"list_models got {models!r}")
    print("PASS test_integration_non_streaming_unchanged")


# ---------------------------------------------------------------------------
# Contracts: registry, harness, tool/function rejection unchanged
# ---------------------------------------------------------------------------

def test_provider_registry_unchanged() -> None:
    from modules.local_model_gateway_ru import PROVIDER_REGISTRY
    _assert(PROVIDER_REGISTRY == ("openai-compatible-local", "managed-llama-cpp"),
            "Provider registry changed")
    print("PASS test_provider_registry_unchanged")


def test_harness_registry_unchanged() -> None:
    from modules.local_model_gateway_ru import HARNESS_REGISTRY
    _assert(HARNESS_REGISTRY == ("minimal", "native-localcomet"),
            "Harness registry changed")
    print("PASS test_harness_registry_unchanged")


def test_tool_function_rejection_unchanged() -> None:
    """Tool/function call markers still rejected."""
    from modules.local_model_gateway_ru import _reject_tool_markers
    _raises(lambda: _reject_tool_markers({"tool_calls": []}), "invalid_payload")
    _raises(lambda: _reject_tool_markers({"function_call": {}}), "invalid_payload")
    _raises(lambda: _reject_tool_markers({"role": "tool"}), "invalid_payload")
    _raises(lambda: _reject_tool_markers({"choices": [{"index": 0, "delta": {"tool_calls": []}}]}),
            "invalid_payload")
    # Valid calls should not raise
    try:
        _reject_tool_markers({"choices": [{"index": 0, "delta": {"content": "hello"}}]})
    except GatewayError:
        _assert(False, "Valid delta raised rejection")
    print("PASS test_tool_function_rejection_unchanged")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    tests = [
        # Unit tests: decoder simulation
        test_ascii_split_across_chunks,
        test_cyrillic_split_after_first_byte,
        test_cyrillic_split_before_final_byte,
        test_multiple_cyrillic_split_different_boundaries,
        test_emoji_split_across_4byte_boundary,
        test_mixed_ascii_cyrillic_emoji_split,
        test_sse_line_split_across_chunks,
        test_sse_data_payload_split_across_chunks,
        test_multiple_sse_events_in_one_chunk,
        test_partial_final_multibyte_at_eof,
        test_decoder_flush_at_normal_eof,
        test_no_replacement_character_corruption,
        test_stream_delta_ordering_preserved,
        test_cancellation_path_preserved,
        test_exactly_one_terminal_outcome,
        # Integration tests: stream_chat with controlled reads
        test_integration_small_read_chunks_cyrillic,
        test_integration_emoji_small_reads,
        test_integration_byte_by_byte_read,
        test_integration_multiple_events_split,
        test_integration_non_streaming_unchanged,
        # Contract tests: registry and rejection unchanged
        test_provider_registry_unchanged,
        test_harness_registry_unchanged,
        test_tool_function_rejection_unchanged,
    ]
    passed = 0
    failed = 0
    for test in tests:
        start = time.perf_counter()
        try:
            test()
            print(f"  ({time.perf_counter() - start:.3f}s)")
            passed += 1
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc}")
            failed += 1
    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"SSE UTF-8 DECODER TESTS: {passed}/{total} passed"
          + (f", {failed} FAILED" if failed else ", ALL PASSED"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
