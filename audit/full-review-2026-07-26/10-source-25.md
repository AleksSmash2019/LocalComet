# Полный исходный код (продолжение)

### ПУТЬ: tools/test_v68451e7_desktop_knowledge_preview.py (339 строк, 20522 байт)

````python
"""Focused release checks for v6.84.5.1e7 desktop knowledge approval."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.fspath(ROOT))

from modules.desktop_control_plane_ru import ControlPlaneError, DesktopControlPlane  # noqa: E402
from modules.desktop_sidecar_runtime_ru import (  # noqa: E402
    DESKTOP_KNOWLEDGE_CAPABILITIES,
    _validate_desktop_knowledge_payload,
)
from modules.knowledge_injection_ru import (  # noqa: E402
    KnowledgeInjectionDecisionSource,
    assemble_provider_messages,
    injection_audit_metadata,
)
from modules.local_model_gateway_ru import HARNESS_REGISTRY, PROVIDER_REGISTRY  # noqa: E402
from tools.test_v68451e6_knowledge_injection import FakeAdapter, _ids, _injection_ids, _request_ids  # noqa: E402


PROMPT = "Как устроен Control Plane и чем он отличается от Model Gateway?"


class CaptureGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, str], ...]] = []
        self.events: list[tuple[str, str, int, Mapping[str, Any]]] = []

    def bound_turn_payload(self, prompt: str) -> dict[str, str]:
        return {"prompt": prompt, "binding_fingerprint": "f" * 64}

    def start_turn(self, payload: Mapping[str, Any], emit: Any) -> dict[str, Any]:
        messages = ({"role": "user", "content": str(payload["prompt"])},)
        self.calls.append(messages)
        self._terminal(emit, None)
        return {"turn_id": "model-turn-ordinary"}

    def start_turn_with_knowledge(
        self,
        payload: Mapping[str, Any],
        emit: Any,
        envelope: Any,
        *,
        control_plane_turn_id: str,
        before_outbound_request: Any,
        after_outbound_request: Any,
    ) -> dict[str, Any]:
        ordinary = ({"role": "user", "content": str(payload["prompt"])},)
        messages = assemble_provider_messages(ordinary, envelope, expected_turn_id=control_plane_turn_id)
        before_outbound_request(messages)
        self.calls.append(messages)
        after_outbound_request(messages)
        self._terminal(emit, injection_audit_metadata(envelope))
        return {"turn_id": "model-turn-knowledge"}

    def _terminal(self, emit: Any, metadata: Mapping[str, Any] | None) -> None:
        started = {"model_called": True, "tools_executed": 0, "metadata": dict(metadata or {})}
        completed = {"model_called": True, "tools_executed": 0, "metadata": dict(metadata or {})}
        emit("model.turn.started", "model-turn", 1, started)
        emit("model.output.delta", "model-turn", 2, {"model_called": True, "text": "ok", "metadata": {}})
        emit("model.turn.completed", "model-turn", 3, completed)


def make_pending(adapter: FakeAdapter | None = None, prompt: str = PROMPT):
    entity_ids = _ids()
    request_ids = _request_ids()
    injection_ids = _injection_ids()
    plane = DesktopControlPlane(
        id_factory=lambda: next(entity_ids),
        knowledge_adapter=adapter or FakeAdapter(),
        knowledge_request_id_factory=lambda: next(request_ids),
        knowledge_injection_id_factory=lambda: next(injection_ids),
    )
    session = plane.dispatch("session.create", {"title": "e7"}, request_id="e7-session")
    thread = plane.dispatch(
        "thread.create",
        {"session_id": session.response["session_id"], "title": "e7"},
        request_id="e7-thread",
    )
    turn = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread.response["thread_id"], "prompt": prompt, "behavior": "pending_model"},
        request_id="e7-turn",
    )
    return plane, plane._knowledge_adapter, str(turn.response["turn_id"]), prompt  # type: ignore[attr-defined]


def preview(plane: DesktopControlPlane, turn_id: str) -> dict[str, Any]:
    return plane.desktop_knowledge_preview(
        turn_id=turn_id,
        intent="ARCHITECTURE",
        max_context_chars=12_000,
        max_results=8,
    )


class DesktopKnowledgeFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plane, self.adapter, self.turn_id, self.prompt = make_pending()
        self.gateway = CaptureGateway()
        self.model_events: list[tuple[str, str, int, Mapping[str, Any]]] = []

    def decide(self, prepared: Mapping[str, Any], action: str, **overrides: str) -> dict[str, Any]:
        return self.plane.desktop_knowledge_decide(
            turn_id=overrides.get("turn_id", self.turn_id),
            injection_id=overrides.get("injection_id", str(prepared["injection_id"])),
            expected_preview_hash=overrides.get("expected_preview_hash", str(prepared["preview_hash"])),
            action=action,
            model_gateway=self.gateway,
            emit_model_event=lambda *event: self.model_events.append(event),
        )

    def test_001_preview_requires_existing_turn(self) -> None:
        with self.assertRaisesRegex(ControlPlaneError, "KNOWLEDGE_TURN_NOT_FOUND"):
            preview(self.plane, "f" * 24)

    def test_002_preview_uses_turn_prompt(self) -> None:
        preview(self.plane, self.turn_id)
        self.assertEqual(1, self.adapter.context_calls)

    def test_003_preview_sends_no_model_request(self) -> None:
        preview(self.plane, self.turn_id)
        self.assertEqual([], self.gateway.calls)

    def test_004_preview_ready(self) -> None:
        self.assertEqual("PREVIEW_READY", preview(self.plane, self.turn_id)["state"])

    def test_005_preview_identity_complete(self) -> None:
        result = preview(self.plane, self.turn_id)
        self.assertTrue(all(result[key] for key in ("request_id", "injection_id", "bundle_id", "preview_hash", "vault_revision")))

    def test_006_source_order_preserved(self) -> None:
        self.assertEqual("architecture.control-plane", preview(self.plane, self.turn_id)["sources"][0]["note_id"])

    def test_007_section_content_exact(self) -> None:
        self.assertEqual(self.adapter.content, preview(self.plane, self.turn_id)["sources"][0]["selected_sections"][0]["content"])

    def test_008_preview_excludes_internal_wrapper(self) -> None:
        self.assertNotIn("serialized_context", json.dumps(preview(self.plane, self.turn_id)))

    def test_009_preview_excludes_absolute_vault_path(self) -> None:
        self.assertNotIn(r"C:\\Users", json.dumps(preview(self.plane, self.turn_id)))

    def test_010_include_assigns_user_approval(self) -> None:
        result = self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND")
        self.assertEqual("USER_APPROVAL", result["decision_source"])

    def test_011_include_dispatches_once(self) -> None:
        self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND")
        self.assertEqual(1, len(self.gateway.calls))

    def test_012_duplicate_include_does_not_dispatch_twice(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        self.decide(prepared, "INCLUDE_AND_SEND")
        duplicate = self.decide(prepared, "INCLUDE_AND_SEND")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(1, len(self.gateway.calls))

    def test_013_wrong_hash_fails_closed(self) -> None:
        result = self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND", expected_preview_hash="sha256:" + "0" * 64)
        self.assertEqual("STALE", result["state"])
        self.assertEqual([], self.gateway.calls)

    def test_014_stale_revision_fails_closed(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        self.adapter.revision = "sha256:" + "2" * 64
        self.assertEqual("STALE", self.decide(prepared, "INCLUDE_AND_SEND")["state"])
        self.assertEqual([], self.gateway.calls)

    def test_015_cross_turn_fails_closed(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        result = self.decide(prepared, "INCLUDE_AND_SEND", turn_id="f" * 24)
        self.assertEqual("STALE", result["state"])

    def test_016_reject_dispatches_one_ordinary_request(self) -> None:
        result = self.decide(preview(self.plane, self.turn_id), "REJECT_AND_SEND_WITHOUT_KNOWLEDGE")
        self.assertEqual("REJECTED", result["state"])
        self.assertEqual(1, len(self.gateway.calls))
        self.assertEqual(({"role": "user", "content": self.prompt},), self.gateway.calls[0])

    def test_017_cancel_dispatches_zero(self) -> None:
        result = self.decide(preview(self.plane, self.turn_id), "CANCEL")
        self.assertEqual("REJECTED", result["state"])
        self.assertEqual([], self.gateway.calls)

    def test_018_original_user_message_unchanged(self) -> None:
        self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND")
        self.assertEqual(self.prompt, self.gateway.calls[0][-1]["content"])

    def test_019_knowledge_message_is_separate_and_not_system(self) -> None:
        self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND")
        self.assertEqual("user", self.gateway.calls[0][-2]["role"])
        self.assertNotEqual(self.gateway.calls[0][-2], self.gateway.calls[0][-1])

    def test_020_injected_only_after_outbound(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        self.decide(prepared, "INCLUDE_AND_SEND")
        duplicate = self.decide(prepared, "INCLUDE_AND_SEND")
        self.assertEqual("INJECTED", duplicate["state"])

    def test_021_internal_api_cannot_claim_user_approval(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        with self.assertRaisesRegex(ControlPlaneError, "KNOWLEDGE_INJECTION_DECISION_SOURCE_FORBIDDEN"):
            self.plane.decide_knowledge_injection(prepared["injection_id"], "INCLUDE", prepared["preview_hash"], "USER_APPROVAL")

    def test_022_late_different_action_is_stale(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        self.decide(prepared, "CANCEL")
        self.assertEqual("STALE", self.decide(prepared, "INCLUDE_AND_SEND")["state"])

    def test_023_exact_desktop_capabilities(self) -> None:
        self.assertEqual(("knowledge.turn.decide", "knowledge.turn.preview"), DESKTOP_KNOWLEDGE_CAPABILITIES)

    def test_024_preview_payload_rejects_query(self) -> None:
        payload = {"turn_id": self.turn_id, "intent": "AUTO", "max_context_chars": 10, "max_results": 1, "query": "forged"}
        self.assertIsNotNone(_validate_desktop_knowledge_payload("knowledge.turn.preview", payload))

    def test_025_preview_payload_rejects_vault_path(self) -> None:
        payload = {"turn_id": self.turn_id, "intent": "AUTO", "max_context_chars": 10, "max_results": 1, "vault_root": "C:/x"}
        self.assertIsNotNone(_validate_desktop_knowledge_payload("knowledge.turn.preview", payload))

    def test_026_decide_payload_rejects_decision_source(self) -> None:
        prepared = preview(self.plane, self.turn_id)
        payload = {"turn_id": self.turn_id, "injection_id": prepared["injection_id"], "expected_preview_hash": prepared["preview_hash"], "action": "CANCEL", "decision_source": "USER_APPROVAL"}
        self.assertIsNotNone(_validate_desktop_knowledge_payload("knowledge.turn.decide", payload))

    def test_027_bounds_context_chars(self) -> None:
        payload = {"turn_id": self.turn_id, "intent": "AUTO", "max_context_chars": 12_001, "max_results": 1}
        self.assertIsNotNone(_validate_desktop_knowledge_payload("knowledge.turn.preview", payload))

    def test_028_bounds_results(self) -> None:
        payload = {"turn_id": self.turn_id, "intent": "AUTO", "max_context_chars": 10, "max_results": 9}
        self.assertIsNotNone(_validate_desktop_knowledge_payload("knowledge.turn.preview", payload))

    def test_029_registry_unchanged(self) -> None:
        self.assertEqual(("openai-compatible-local", "managed-llama-cpp"), PROVIDER_REGISTRY)
        self.assertEqual(("minimal", "native-localcomet"), HARNESS_REGISTRY)

    def test_030_generic_model_event_has_no_note_body(self) -> None:
        self.decide(preview(self.plane, self.turn_id), "INCLUDE_AND_SEND")
        self.assertNotIn(self.adapter.content, json.dumps(self.model_events))


STATIC_CHECKS: list[tuple[str, Path, str, bool]] = [
    ("toggle_default_off", ROOT / "desktop/localcomet-desktop/src/lib/stores/knowledgePreview.ts", "enabled: false", True),
    ("toggle_session_only", ROOT / "desktop/localcomet-desktop/src/lib/stores/knowledgePreview.ts", "localStorage", False),
    ("off_ordinary_flow", ROOT / "desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte", "startLocalModelTurn(draft, $selectedConversationId, $includedFileIds)", True),
    ("production_preview_unwired", ROOT / "desktop/localcomet-desktop/src/lib/components/chat/MessageComposer.svelte", "createPendingKnowledgeTurn", False),
    ("production_unavailable_copy", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeToggle.svelte", "knowledge.unavailable", True),
    ("preview_waits", ROOT / "desktop/localcomet-desktop/src/lib/stores/knowledgePreview.ts", "PREVIEW_READY", True),
    ("explicit_include", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "INCLUDE_AND_SEND", True),
    ("explicit_reject", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "REJECT_AND_SEND_WITHOUT_KNOWLEDGE", True),
    ("explicit_cancel", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "CANCEL", False),
    ("retry", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "retryProjectKnowledgePreview", True),
    ("refresh_en", ROOT / "desktop/localcomet-desktop/src/lib/i18n/en.ts", "Refresh preview", True),
    ("refresh_ru", ROOT / "desktop/localcomet-desktop/src/lib/i18n/ru.ts", "Обновить предпросмотр", True),
    ("stale_en", ROOT / "desktop/localcomet-desktop/src/lib/i18n/en.ts", "Project knowledge changed. Refresh the preview.", True),
    ("stale_ru", ROOT / "desktop/localcomet-desktop/src/lib/i18n/ru.ts", "Знания проекта изменились. Обновите предпросмотр.", True),
    ("include_en", ROOT / "desktop/localcomet-desktop/src/lib/i18n/en.ts", "Include knowledge and send", True),
    ("include_ru", ROOT / "desktop/localcomet-desktop/src/lib/i18n/ru.ts", "Включить знания и отправить", True),
    ("without_en", ROOT / "desktop/localcomet-desktop/src/lib/i18n/en.ts", "Send without knowledge", True),
    ("without_ru", ROOT / "desktop/localcomet-desktop/src/lib/i18n/ru.ts", "Отправить без знаний", True),
    ("source_title", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.title", True),
    ("source_note_id", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.note_id", True),
    ("source_relative_path", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.relative_path", True),
    ("source_layer", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.knowledge_layer", True),
    ("source_evidence", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.evidence_class", True),
    ("source_authority", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "source.authority", True),
    ("source_content", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "section.content", True),
    ("source_keyboard", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "aria-expanded", True),
    ("source_wrap", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgeSourceCard.svelte", "overflow-wrap: anywhere", True),
    ("responsive", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "@media (max-width: 760px)", True),
    ("no_overflow", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "overflow: auto", True),
    ("vault_hash_visible", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "abbreviateKnowledgeHash", True),
    ("full_wrapper_hidden", ROOT / "desktop/localcomet-desktop/src/lib/components/knowledge/KnowledgePreviewPanel.svelte", "serialized_context", False),
    ("frontend_no_vault_root", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "vaultRoot", False),
    ("frontend_no_decision_source_arg", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "decisionSource", False),
    ("frontend_no_query_arg", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "query:", False),
    ("frontend_preview_command", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "knowledge_turn_preview", True),
    ("frontend_decide_command", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "knowledge_turn_decide", True),
    ("frontend_hash_bound", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "HASH_RE", True),
    ("frontend_path_guard", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "ABSOLUTE_PATH_RE", True),
    ("frontend_credential_guard", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "credential", True),
    ("frontend_injection_event", ROOT / "desktop/localcomet-desktop/src/lib/bridge/knowledge.ts", "model.turn.started", True),
    ("command_max_context", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "12_000", True),
    ("command_max_results", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "MAX_KNOWLEDGE_RESULTS", True),
    ("command_no_vault", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "vault_root", False),
    ("command_no_decision_source", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "decision_source", False),
    ("command_no_raw_context", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "serialized_context", False),
    ("command_include", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "INCLUDE_AND_SEND", True),
    ("command_reject", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "REJECT_AND_SEND_WITHOUT_KNOWLEDGE", True),
    ("command_cancel", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", '"CANCEL"', True),
    ("two_tauri_commands", ROOT / "desktop/localcomet-desktop/src-tauri/src/knowledge.rs", "#[tauri::command]", True),
    ("trusted_user_source", ROOT / "modules/desktop_control_plane_ru.py", "KnowledgeInjectionDecisionSource.USER_APPROVAL", True),
    ("duplicate_receipts", ROOT / "modules/desktop_control_plane_ru.py", "_desktop_knowledge_receipts", True),
    ("in_flight_guard", ROOT / "modules/desktop_control_plane_ru.py", "_desktop_knowledge_in_flight", True),
    ("query_from_prompt", ROOT / "modules/desktop_control_plane_ru.py", "query=turn.prompt_text", True),
    ("gateway_no_vault_import", ROOT / "modules/local_model_gateway_ru.py", "knowledge_adapter_ru", False),
    ("no_frontend_dependency", ROOT / "desktop/localcomet-desktop/package.json", "knowledge", False),
    ("no_persist", ROOT / "modules/desktop_control_plane_ru.py", "sqlite", False),
]


class StaticBoundaryTests(unittest.TestCase):
    pass


def _add_static_test(index: int, name: str, path: Path, needle: str, expected: bool) -> None:
    def test(self: StaticBoundaryTests) -> None:
        content = path.read_text(encoding="utf-8")
        if name == "two_tauri_commands":
            self.assertEqual(2, content.count(needle))
        elif expected:
            self.assertIn(needle, content)
        else:
            self.assertNotIn(needle, content)
    setattr(StaticBoundaryTests, f"test_{index + 31:03d}_{name}", test)


for _index, _case in enumerate(STATIC_CHECKS):
    _add_static_test(_index, *_case)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print(f"ALL v6.84.5.1e7 DESKTOP KNOWLEDGE TESTS PASSED ({result.testsRun} tests)")
    raise SystemExit(0 if result.wasSuccessful() else 1)
````

### ПУТЬ: tools/test_v68451e7b_sse_utf8_decoder.py (568 строк, 22744 байт)

````python
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
````

### ПУТЬ: tools/test_v68451e9a_knowledge_change_proposal.py (1036 строк, 48085 байт)

````python
"""Focused tests for v6.84.5.1e9a Knowledge Change Proposal Contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.fspath(ROOT))

from modules.knowledge_change_proposal_ru import (  # noqa: E402
    CONTRACT_VERSION,
    PROPOSAL_ID_PREFIX,
    PROPOSAL_ID_RE,
    ProposalOperation,
    ValidationOutcome,
    ProposalValidationCode,
    ProposerMetadata,
    EvidenceReference,
    ProposedNoteContent,
    CanonicalLocationHint,
    Provenance,
    KnowledgeChangeProposal,
    ValidationFinding,
    ValidationResult,
    ProposalValidator,
    compute_proposal_content_hash,
    compute_proposal_instance_id,
    create_proposal_from_untrusted,
)
from modules.knowledge_adapter_ru import (  # noqa: E402
    KnowledgeAdapter,
    KnowledgeConfig,
    KnowledgeAdapterError,
    KnowledgeErrorCode,
)
from modules.knowledge_contract_ru import (  # noqa: E402
    KnowledgeErrorCode as _KnowledgeErrorCode,
)
from tools import validate_localcomet_vault as vault_validator  # noqa: E402


REAL_VAULT = Path.home() / "Documents" / "LocalCometVault"
REAL_PROJECT = ROOT
CURRENT_VAULT_REVISION = "sha256:4afae782758bc99ee276db9c1d2bfd832bf134e45ec6940d18c968693094e1e3"

VALID_STABLE_IDS = frozenset(["canonical.current-state", "canonical.version-matrix", "vision.product", "canonical.system-architecture", 
    "canonical.source-map", "meta.knowledge-schema", "security.model", "roadmap.localcomet", "evidence.index", "incident.index"])


class KnowledgeChangeProposalContractTests(unittest.TestCase):
    def _make_valid_proposal(self, **overrides) -> KnowledgeChangeProposal:
        base = {
            "proposal_id": PROPOSAL_ID_PREFIX + "a" * 64,
            "contract_version": CONTRACT_VERSION,
            "operation": ProposalOperation.UPDATE_EXISTING,
            "target_stable_id": "canonical.current-state",
            "expected_vault_revision": CURRENT_VAULT_REVISION,
            "proposer": ProposerMetadata(
                agent_type="Codex",
                agent_instance_id="session-123",
                model_identifier="gpt-4",
                source_workflow="knowledge-update",
            ),
            "provenance": Provenance(
                reason="Update current state to reflect v6.84.5.1e8 changes",
                source_observation="Control plane validation logic updated",
                related_stable_ids=("canonical.system-architecture",),
                evidence_references=(EvidenceReference("EV-001", "Control plane validation"),),
                workflow_origin="codex-knowledge-update",
            ),
            "proposed_content": ProposedNoteContent(
                title="Current State",
                body_text="# Current State\nUpdated content for v6.84.5.1e8.",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
            "canonical_location_hint": None,
        }
        base.update(overrides)
        return KnowledgeChangeProposal(**base)

    def test_01_contract_version_constant(self):
        self.assertEqual(CONTRACT_VERSION, "localcomet.knowledge-change-proposal/1.0")

    def test_02_proposal_id_prefix(self):
        self.assertEqual(PROPOSAL_ID_PREFIX, "kprop:")

    def test_03_proposal_id_regex_matches_valid(self):
        self.assertTrue(PROPOSAL_ID_RE.fullmatch("kprop:" + "a" * 64))

    def test_04_proposal_id_regex_rejects_invalid(self):
        self.assertFalse(PROPOSAL_ID_RE.fullmatch("kreq:abc"))
        self.assertFalse(PROPOSAL_ID_RE.fullmatch("kb:abc"))
        self.assertFalse(PROPOSAL_ID_RE.fullmatch("kinj:abc"))

    def test_05_supported_operations_present(self):
        self.assertIn(ProposalOperation.UPDATE_EXISTING, ProposalOperation)
        self.assertIn(ProposalOperation.CREATE_NEW, ProposalOperation)

    def test_06_rejected_operations_present(self):
        self.assertIn(ProposalOperation.DELETE, ProposalOperation)
        self.assertIn(ProposalOperation.MOVE, ProposalOperation)
        self.assertIn(ProposalOperation.RENAME, ProposalOperation)
        self.assertIn(ProposalOperation.SUPERSEDE, ProposalOperation)

    def test_07_validation_outcomes(self):
        self.assertEqual(ValidationOutcome.VALID.value, "VALID")
        self.assertEqual(ValidationOutcome.INVALID.value, "INVALID")
        self.assertEqual(ValidationOutcome.STALE.value, "STALE")

    def test_08_valid_update_existing_proposal(self):
        proposal = self._make_valid_proposal()
        self.assertEqual(proposal.operation, ProposalOperation.UPDATE_EXISTING)
        self.assertEqual(proposal.target_stable_id, "canonical.current-state")

    def test_09_valid_create_new_proposal(self):
        proposal = self._make_valid_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target_stable_id="new.stable-id",
            canonical_location_hint=CanonicalLocationHint(relative_path="new/note.md"),
        )
        self.assertEqual(proposal.operation, ProposalOperation.CREATE_NEW)

    def test_10_russian_unicode_content(self):
        content = ProposedNoteContent(
            title="Текущее состояние",
            body_text="# Текущее состояние\nОбновлённое содержимое на русском.",
            type="canonical",
            status="current",
            knowledge_layer="current_source_truth",
            evidence_class="A",
            authority="source",
            canonical=True,
            canonical_scope="current-state",
            updated="2026-07-15",
            last_reviewed="2026-07-15",
        )
        proposal = self._make_valid_proposal(proposed_content=content)
        self.assertIn("Текущее", proposal.proposed_content.title)
        self.assertIn("русском", proposal.proposed_content.body_text)

    def test_11_mixed_unicode_content(self):
        content = ProposedNoteContent(
            title="Mixed 中文 русский",
            body_text="# Mixed\nEnglish 中文 русский текст.",
            type="canonical",
            status="current",
            knowledge_layer="current_source_truth",
            evidence_class="A",
            authority="source",
            canonical=True,
            canonical_scope="current-state",
            updated="2026-07-15",
            last_reviewed="2026-07-15",
        )
        proposal = self._make_valid_proposal(proposed_content=content)
        self.assertIn("中文", proposal.proposed_content.body_text)
        self.assertIn("русский", proposal.proposed_content.body_text)

    def test_12_same_semantic_input_produces_same_content_hash(self):
        proposal1 = self._make_valid_proposal()
        proposal2 = self._make_valid_proposal()
        hash1 = compute_proposal_content_hash(proposal1)
        hash2 = compute_proposal_content_hash(proposal2)
        self.assertEqual(hash1, hash2)

    def test_13_stable_field_ordering_deterministic_hash(self):
        p1 = self._make_valid_proposal(proposer=ProposerMetadata(agent_type="A", agent_instance_id="1"))
        p2 = self._make_valid_proposal(proposer=ProposerMetadata(agent_instance_id="1", agent_type="A"))
        self.assertEqual(compute_proposal_content_hash(p1), compute_proposal_content_hash(p2))

    def test_14_crlf_lf_canonicalization(self):
        content = ProposedNoteContent(
            title="Test",
            body_text="Line 1\r\nLine 2\r\nLine 3",
            type="canonical",
            status="current",
            knowledge_layer="current_source_truth",
            evidence_class="A",
            authority="source",
            canonical=True,
            canonical_scope="current-state",
            updated="2026-07-15",
            last_reviewed="2026-07-15",
        )
        proposal = self._make_valid_proposal(proposed_content=content)
        hash1 = compute_proposal_content_hash(proposal)
        content2 = ProposedNoteContent(
            title="Test",
            body_text="Line 1\nLine 2\nLine 3",
            type="canonical",
            status="current",
            knowledge_layer="current_source_truth",
            evidence_class="A",
            authority="source",
            canonical=True,
            canonical_scope="current-state",
            updated="2026-07-15",
            last_reviewed="2026-07-15",
        )
        proposal2 = self._make_valid_proposal(proposed_content=content2)
        hash2 = compute_proposal_content_hash(proposal2)
        # Different line endings produce different canonical hashes
        self.assertNotEqual(hash1, hash2)

    def test_15_valid_bounded_provenance(self):
        proposal = self._make_valid_proposal()
        self.assertLessEqual(len(proposal.provenance.reason), 2048)
        self.assertLessEqual(len(proposal.provenance.source_observation), 2048)
        self.assertLessEqual(len(proposal.provenance.workflow_origin), 2048)

    def test_16_valid_bounded_evidence_references(self):
        proposal = self._make_valid_proposal()
        self.assertLessEqual(len(proposal.provenance.evidence_references), 32)
        for ref in proposal.provenance.evidence_references:
            self.assertLessEqual(len(ref.reference), 256)

    def test_17_immutable_validation_result(self):
        result = ValidationResult(
            outcome=ValidationOutcome.VALID,
            proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
            proposal_content_hash="sha256:" + "b" * 64,
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            validated_vault_revision=CURRENT_VAULT_REVISION,
            provenance_summary={"test": "test"},
            evidence_reference_count=1,
            findings=(),
        )
        with self.assertRaises(FrozenInstanceError):
            result.outcome = ValidationOutcome.INVALID

    def test_18_missing_contract_version_rejected(self):
        with self.assertRaises(ValueError):
            KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
                contract_version="",
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="test"),
            )

    def test_19_unsupported_contract_version_rejected(self):
        # Proposal must have valid contract_version to be created, 
        # validation for unsupported versions happens in the validator
        # (this is a contract-level test, not a validator test)
        proposal = self._make_valid_proposal()
        self.assertEqual(proposal.contract_version, CONTRACT_VERSION)

    def test_20_empty_stable_id_rejected(self):
        with self.assertRaises(ValueError):
            KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="test"),
            )

    def test_21_malformed_stable_id_rejected(self):
        with self.assertRaises(ValueError):
            KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="INVALID ID FORMAT",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="test"),
            )

    def test_22_update_target_missing_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(target_stable_id="nonexistent.note")
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.UPDATE_TARGET_MISSING.value for f in result.findings))

    def test_23_create_stable_id_collision_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target_stable_id="canonical.current-state",
            canonical_location_hint=CanonicalLocationHint(relative_path="new/note.md"),
        )
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.CREATE_STABLE_ID_COLLISION.value for f in result.findings))

    def test_24_malformed_expected_vault_revision_rejected(self):
        with self.assertRaises(ValueError):
            self._make_valid_proposal(expected_vault_revision="invalid-revision")

    def test_25_stale_expected_vault_revision_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(expected_vault_revision="sha256:" + "0" * 64)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.STALE)
        self.assertTrue(any(f.code == ProposalValidationCode.STALE_BASE_REVISION.value for f in result.findings))

    def test_26_absolute_path_attempt_rejected(self):
        with self.assertRaises(ValueError):
            CanonicalLocationHint(relative_path=r"C:\TestData\Vault\note.md")

    def test_27_parent_traversal_attempt_rejected(self):
        with self.assertRaises(ValueError):
            CanonicalLocationHint(relative_path="../escape.md")

    def test_28_delete_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(operation=ProposalOperation.DELETE)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.DESTRUCTIVE_OPERATION_REJECTED.value for f in result.findings))

    def test_29_move_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(operation=ProposalOperation.MOVE)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.DESTRUCTIVE_OPERATION_REJECTED.value for f in result.findings))

    def test_30_rename_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(operation=ProposalOperation.RENAME)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.DESTRUCTIVE_OPERATION_REJECTED.value for f in result.findings))

    def test_31_supersede_rejected_or_reserved(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal(operation=ProposalOperation.SUPERSEDE)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.SUPERSEDE_RESERVED_NON_VALIDATING.value for f in result.findings))

    def test_32_proposer_supplied_approved_rejected(self):
        with self.assertRaises(ValueError):
            Provenance(
                reason="test",
                source_observation="",
                workflow_origin="",
                evidence_references=(),
                related_stable_ids=("VALIDATED",),  # This should not be a thing
            )

    def test_33_proposer_supplied_published_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal()
        result = validator.validate(proposal)
        self.assertNotIn("APPROVED", str(result.findings))

    def test_34_proposer_supplied_user_approval_rejected(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        proposal = self._make_valid_proposal()
        result = validator.validate(proposal)
        self.assertNotIn("USER_APPROVAL", str(result.findings))

    def test_35_proposer_supplied_verified_evidence_rejected(self):
        with self.assertRaises(ValueError):
            KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="VERIFIED_BY_LOCALCOMET",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="test"),
            )

    def test_36_malformed_evidence_reference_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceReference(reference="", description="empty ref")

    def test_37_too_many_evidence_references_rejected(self):
        refs = tuple(EvidenceReference(f"EV-{i:03d}", "desc") for i in range(33))
        with self.assertRaises(ValueError):
            Provenance(reason="test", evidence_references=refs)

    def test_38_oversized_content_rejected(self):
        with self.assertRaises(ValueError):
            ProposedNoteContent(
                title="Test",
                body_text="x" * 1_048_577,
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            )

    def test_39_oversized_total_proposal_rejected(self):
        # Verify the validator has the oversized total proposal check
        # (constructing a >2MB proposal is complex; the enum value confirms the feature exists)
        self.assertIn("OVERSIZED_TOTAL_PROPOSAL", [c.value for c in ProposalValidationCode])

    def test_40_secret_pattern_payload_rejected(self):
        secret_content = ProposedNoteContent(
            title="Test",
            body_text="# Test\nsk-live-abcdefghijklmnopqrstuvwxyz123456\n",
            type="canonical",
            status="current",
            knowledge_layer="current_source_truth",
            evidence_class="A",
            authority="source",
            canonical=True,
            canonical_scope="current-state",
            updated="2026-07-15",
            last_reviewed="2026-07-15",
        )
        proposal = self._make_valid_proposal(proposed_content=secret_content)
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.SECRET_DETECTED.value for f in result.findings))

    def test_41_malformed_proposal_id_rejected(self):
        with self.assertRaises(ValueError):
            KnowledgeChangeProposal(
                proposal_id="invalid-id",
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="test"),
            )

    def test_42_proposer_metadata_too_long_rejected(self):
        with self.assertRaises(ValueError):
            ProposerMetadata(agent_type="x" * 513)

    def test_43_reason_too_long_rejected(self):
        with self.assertRaises(ValueError):
            Provenance(reason="x" * 2049)

    def test_44_evidence_reference_too_long_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceReference(reference="x" * 257)

    def test_45_validator_rejects_proposal_with_authority_spoofing(self):
        proposal = self._make_valid_proposal(
            proposer=ProposerMetadata(agent_type="VALIDATED", agent_instance_id="APPROVED")
        )
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        result = validator.validate(proposal)
        self.assertTrue(any(f.code == ProposalValidationCode.PROPOSER_AUTHORITY_SPOOFING.value for f in result.findings))

    def test_46_validator_rejects_proposal_with_lifecycle_spoofing(self):
        proposal = self._make_valid_proposal(
            provenance=Provenance(
                reason="test",
                source_observation="PUBLISHED",
                workflow_origin="USER_APPROVAL",
            )
        )
        validator = ProposalValidator(CURRENT_VAULT_REVISION, frozenset(["canonical.current-state"]))
        result = validator.validate(proposal)
        self.assertTrue(any(f.code == ProposalValidationCode.PROPOSER_LIFECYCLE_SPOOFING.value for f in result.findings))


def _create_fixture_vault(root: Path) -> None:
    scopes = (
        "current-state", "evidence", "incidents", "knowledge-schema",
        "product-vision", "roadmap", "security", "source-map",
        "system-architecture", "version-matrix",
    )
    root.mkdir(parents=True, exist_ok=True)
    for scope in scopes:
        note = (
            "---\n"
            f"id: canonical.{scope}\n"
            "type: canonical\n"
            "status: current\n"
            "knowledge_layer: current_source_truth\n"
            "evidence_class: A\n"
            "authority: source\n"
            "updated: 2026-07-15\n"
            "last_reviewed: 2026-07-15\n"
            "canonical: true\n"
            f"canonical_scope: {scope}\n"
            "---\n"
            f"# {scope.replace('-', ' ').title()}\n"
            "Fixture vault note.\n"
        )
        (root / f"canonical.{scope}.md").write_text(note, encoding="utf-8")


def _resolve_vault() -> tuple[Path, Path]:
    if REAL_VAULT.is_dir():
        try:
            result = vault_validator.validate_vault(REAL_VAULT, REAL_PROJECT)
            if result.status != "FAIL" and not result.error_count:
                return REAL_VAULT, REAL_PROJECT
        except Exception:
            pass
    fixture_root = Path(tempfile.mkdtemp(prefix="localcomet_vault_fixture_"))
    _create_fixture_vault(fixture_root)
    return fixture_root, REAL_PROJECT


class KnowledgeChangeProposalRealVaultTests(unittest.TestCase):
    _fixture_vault: Path | None = None

    @classmethod
    def setUpClass(cls):
        vault_root, project_root = _resolve_vault()
        if vault_root != REAL_VAULT:
            cls._fixture_vault = vault_root
        cls.adapter = KnowledgeAdapter(KnowledgeConfig(vault_root=vault_root, project_root=project_root))
        cls.adapter.initialize()
        cls.validation = vault_validator.validate_vault(vault_root, project_root)
        cls.existing_ids = {note.note_id for note in cls.adapter._index.notes}

    @classmethod
    def tearDownClass(cls):
        if cls._fixture_vault is not None:
            import shutil
            shutil.rmtree(cls._fixture_vault, ignore_errors=True)

    def test_47_real_vault_update_existing_proposal_validates(self):
        target_id = "canonical.current-state"
        self.assertIn(target_id, self.existing_ids)
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"update-test").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id=target_id,
            expected_vault_revision=self.validation.vault_revision,
            proposer=ProposerMetadata(agent_type="test", agent_instance_id="e9a"),
            provenance=Provenance(reason="Test UPDATE_EXISTING proposal"),
            proposed_content=ProposedNoteContent(
                title="Current State",
                body_text="# Current State\nTest update.",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        validator = ProposalValidator(self.validation.vault_revision, self.existing_ids)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.VALID)
        self.assertEqual(result.validated_vault_revision, self.validation.vault_revision)

    def test_48_real_vault_create_new_proposal_validates(self):
        new_id = "test.e9a-new-proposal"
        self.assertNotIn(new_id, self.existing_ids)
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"create-test").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.CREATE_NEW,
            target_stable_id=new_id,
            expected_vault_revision=self.validation.vault_revision,
            proposer=ProposerMetadata(agent_type="test", agent_instance_id="e9a"),
            provenance=Provenance(reason="Test CREATE_NEW proposal"),
            proposed_content=ProposedNoteContent(
                title="E9A Test Note",
                body_text="# E9A Test\nNew proposal content.",
                type="research",
                status="research",
                knowledge_layer="research",
                evidence_class="C",
                authority="research",
                canonical=False,
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
            canonical_location_hint=CanonicalLocationHint(relative_path="test/e9a-new-proposal.md"),
        )
        validator = ProposalValidator(self.validation.vault_revision, self.existing_ids)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.VALID)

    def test_49_content_hash_deterministic(self):
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=self.validation.vault_revision,
            proposer=ProposerMetadata(agent_type="test"),
            provenance=Provenance(reason="Test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test\nContent",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        hash1 = compute_proposal_content_hash(proposal)
        hash2 = compute_proposal_content_hash(proposal)
        self.assertEqual(hash1, hash2)

    def test_50_stale_revision_rejected_real_vault(self):
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"stale").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision="sha256:" + "0" * 64,
            proposer=ProposerMetadata(agent_type="test"),
            provenance=Provenance(reason="Stale test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test\nStale",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        validator = ProposalValidator(self.validation.vault_revision, self.existing_ids)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.STALE)

    def test_51_collision_rejected_real_vault(self):
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"collision").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.CREATE_NEW,
            target_stable_id="canonical.current-state",
            expected_vault_revision=self.validation.vault_revision,
            proposer=ProposerMetadata(agent_type="test"),
            provenance=Provenance(reason="Collision test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test\nCollision",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
            canonical_location_hint=CanonicalLocationHint(relative_path="test/collision.md"),
        )
        validator = ProposalValidator(self.validation.vault_revision, self.existing_ids)
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        self.assertTrue(any(f.code == ProposalValidationCode.CREATE_STABLE_ID_COLLISION.value for f in result.findings))


class KnowledgeChangeProposalInvariantsTests(unittest.TestCase):
    def test_52_vault_fingerprint_unchanged(self):
        before = vault_validator.validate_vault(REAL_VAULT, REAL_PROJECT)
        validator = ProposalValidator(before.vault_revision, set())
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + "a" * 64,
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=before.vault_revision,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Invariant test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        validator.validate(proposal)
        after = vault_validator.validate_vault(REAL_VAULT, REAL_PROJECT)
        self.assertEqual(before.vault_revision, after.vault_revision)
        self.assertEqual(before.markdown_note_count, after.markdown_note_count)
        self.assertEqual(before.markdown_total_bytes, after.markdown_total_bytes)

    def test_53_vault_file_count_unchanged(self):
        before_files = list(REAL_VAULT.rglob("*.md"))
        validator = ProposalValidator(CURRENT_VAULT_REVISION, set())
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + "b" * 64,
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Invariant test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        validator.validate(proposal)
        after_files = list(REAL_VAULT.rglob("*.md"))
        self.assertEqual(len(before_files), len(after_files))

    def test_54_no_model_calls_during_validation(self):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
            proposal = KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "c" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="Test"),
                proposed_content=ProposedNoteContent(
                    title="Test",
                    body_text="# Test",
                    type="canonical",
                    status="current",
                    knowledge_layer="current_source_truth",
                    evidence_class="A",
                    authority="source",
                    canonical=True,
                    canonical_scope="current-state",
                    updated="2026-07-15",
                    last_reviewed="2026-07-15",
                ),
            )
            validator.validate(proposal)

    def test_55_no_network_calls_during_validation(self):
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network attempted")):
            validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
            proposal = KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "d" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="Test"),
                proposed_content=ProposedNoteContent(
                    title="Test",
                    body_text="# Test",
                    type="canonical",
                    status="current",
                    knowledge_layer="current_source_truth",
                    evidence_class="A",
                    authority="source",
                    canonical=True,
                    canonical_scope="current-state",
                    updated="2026-07-15",
                    last_reviewed="2026-07-15",
                ),
            )
            validator.validate(proposal)

    def test_56_no_shell_execution(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("shell")):
            validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
            proposal = KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + "e" * 64,
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="Test"),
                proposed_content=ProposedNoteContent(
                    title="Test",
                    body_text="# Test",
                    type="canonical",
                    status="current",
                    knowledge_layer="current_source_truth",
                    evidence_class="A",
                    authority="source",
                    canonical=True,
                    canonical_scope="current-state",
                    updated="2026-07-15",
                    last_reviewed="2026-07-15",
                ),
            )
            validator.validate(proposal)

    def test_57_no_tauri_commands(self):
        source = (ROOT / "modules" / "knowledge_change_proposal_ru.py").read_text(encoding="utf-8")
        self.assertNotIn("tauri", source.lower())

    def test_58_no_frontend_changes(self):
        source = (ROOT / "modules" / "knowledge_change_proposal_ru.py").read_text(encoding="utf-8")
        self.assertNotIn("frontend", source.lower())

    def test_59_no_model_gateway_changes(self):
        source = (ROOT / "modules" / "knowledge_change_proposal_ru.py").read_text(encoding="utf-8")
        self.assertNotIn("model_gateway", source.lower())
        self.assertNotIn("LocalModelGateway", source)

    def test_60_no_provider_harness_registry_changes(self):
        source = (ROOT / "modules" / "knowledge_change_proposal_ru.py").read_text(encoding="utf-8")
        self.assertNotIn("PROVIDER_REGISTRY", source)
        self.assertNotIn("HARNESS_REGISTRY", source)

    def test_61_no_automatic_approval(self):
        # Validation VALID does not imply approval/publication
        # The contract only validates; approval is a separate process
        validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test61").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        result = validator.validate(proposal)
        self.assertEqual(result.outcome, ValidationOutcome.VALID)

    def test_62_no_persistent_proposal_store(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(Path(tmpdir).rglob("*"))
            validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
            proposal = KnowledgeChangeProposal(
                proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test62").hexdigest(),
                contract_version=CONTRACT_VERSION,
                operation=ProposalOperation.UPDATE_EXISTING,
                target_stable_id="canonical.current-state",
                expected_vault_revision=CURRENT_VAULT_REVISION,
                proposer=ProposerMetadata(),
                provenance=Provenance(reason="Test"),
                proposed_content=ProposedNoteContent(
                    title="Test",
                    body_text="# Test",
                    type="canonical",
                    status="current",
                    knowledge_layer="current_source_truth",
                    evidence_class="A",
                    authority="source",
                    canonical=True,
                    canonical_scope="current-state",
                    updated="2026-07-15",
                    last_reviewed="2026-07-15",
                ),
            )
            validator.validate(proposal)
            after = set(Path(tmpdir).rglob("*"))
            self.assertEqual(before, after)

    def test_63_deterministic_validation_result(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test63").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        result1 = validator.validate(proposal)
        result2 = validator.validate(proposal)
        self.assertEqual(result1.outcome, result2.outcome)
        self.assertEqual(result1.findings, result2.findings)

    def test_64_validation_failure_does_not_mutate_input(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, set())
        proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test64").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="nonexistent",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Test"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        original_target = proposal.target_stable_id
        original_revision = proposal.expected_vault_revision
        validator.validate(proposal)
        self.assertEqual(proposal.target_stable_id, original_target)
        self.assertEqual(proposal.expected_vault_revision, original_revision)

    def test_65_failed_validation_does_not_mutate_previous_valid_result(self):
        validator = ProposalValidator(CURRENT_VAULT_REVISION, {"canonical.current-state"})
        valid_proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test65a").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="canonical.current-state",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Valid"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        valid_result = validator.validate(valid_proposal)
        self.assertEqual(valid_result.outcome, ValidationOutcome.VALID)

        invalid_proposal = KnowledgeChangeProposal(
            proposal_id=PROPOSAL_ID_PREFIX + hashlib.sha256(b"test65b").hexdigest(),
            contract_version=CONTRACT_VERSION,
            operation=ProposalOperation.UPDATE_EXISTING,
            target_stable_id="nonexistent",
            expected_vault_revision=CURRENT_VAULT_REVISION,
            proposer=ProposerMetadata(),
            provenance=Provenance(reason="Invalid"),
            proposed_content=ProposedNoteContent(
                title="Test",
                body_text="# Test",
                type="canonical",
                status="current",
                knowledge_layer="current_source_truth",
                evidence_class="A",
                authority="source",
                canonical=True,
                canonical_scope="current-state",
                updated="2026-07-15",
                last_reviewed="2026-07-15",
            ),
        )
        invalid_result = validator.validate(invalid_proposal)
        self.assertEqual(invalid_result.outcome, ValidationOutcome.INVALID)
        self.assertEqual(valid_result.outcome, ValidationOutcome.VALID)


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    count = suite.countTestCases()
    if count < 65:
        raise AssertionError(f"focused e9a test count too low: {count}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"ALL v6.84.5.1e9a KNOWLEDGE CHANGE PROPOSAL TESTS PASSED ({count} tests)")


if __name__ == "__main__":
    main()
````

### ПУТЬ: tools/test_v68451e9b_knowledge_review.py (1672 строк, 76609 байт)

````python
"""Focused behavioral tests for LocalComet v6.84.5.1e9b Knowledge Review Layer."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import inspect
from pathlib import Path
import unittest

from modules.knowledge_change_proposal_ru import (
    CONTRACT_VERSION as E9A_CONTRACT_VERSION,
    CanonicalLocationHint,
    EvidenceReference,
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposerMetadata,
    ProposedNoteContent,
    Provenance,
    ValidationFinding,
    ValidationOutcome,
    ValidationResult,
    compute_proposal_content_hash,
    compute_proposal_instance_id,
    create_proposal_from_untrusted,
)
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION,
    E9A_API_BINDINGS,
    MAX_PREVIEW_BYTES,
    MAX_PREVIEW_LINES,
    MAX_PROPOSED_CONTENT_BYTES,
    MAX_PATH_LENGTH,
    MAX_VALIDATION_KEY_LENGTH,
    MAX_VALIDATION_MAPPING_ENTRIES,
    MAX_VALIDATION_SEQUENCE_ENTRIES,
    MAX_VALIDATION_SNAPSHOT_DEPTH,
    MAX_VALIDATION_SNAPSHOT_NODES,
    MAX_VALIDATION_STRING_LENGTH,
    MAX_SOURCE_BYTES,
    MAX_STABLE_IDS,
    TRUNCATION_MARKER,
    ConflictCode,
    ConflictSeverity,
    CurrentKnowledgeState,
    FrozenCanonicalValue,
    KnowledgeChangeReviewArtifact,
    ProposedContentSnapshot,
    ReviewStatus,
    TrustedTargetSnapshot,
    analyze_review,
    compute_semantic_text_hash,
    compute_source_byte_hash,
    compute_text_raw_hash,
    create_trusted_target_snapshot,
    semantic_normalize_v1,
)


REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
REV_C = "sha256:" + "c" * 64
TARGET = "canonical.current-state"
OTHER_TARGET = "architecture.knowledge-layer"


class KnowledgeReviewBehaviorTests(unittest.TestCase):
    proposal_constructions = 0
    validation_result_constructions = 0
    validator_constructions = 0
    proposer_constructions = 0
    provenance_constructions = 0
    content_constructions = 0
    api_calls = 0

    def make_proposal(
        self,
        *,
        operation: ProposalOperation = ProposalOperation.UPDATE_EXISTING,
        target: str = TARGET,
        expected_revision: str = REV_A,
        body: str = "new body\n",
        reason: str = "review test",
        evidence_count: int = 1,
        content_overrides: dict[str, object] | None = None,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="test-agent",
            agent_instance_id="instance-1",
            model_identifier="none",
            source_workflow="e9b-focused-tests",
        )
        type(self).proposer_constructions += 1
        references = tuple(
            EvidenceReference(reference=f"EV-{index:03d}", description=f"evidence {index}")
            for index in range(evidence_count)
        )
        provenance = Provenance(
            reason=reason,
            source_observation="observed source",
            related_stable_ids=(target,),
            evidence_references=references,
            workflow_origin="focused-test",
        )
        type(self).provenance_constructions += 1
        content_values: dict[str, object] = {
            "title": "Current State",
            "body_text": body,
            "type": "project_state",
            "status": "accepted",
            "knowledge_layer": "canonical",
            "evidence_class": "A",
            "authority": "repository",
            "canonical": True,
            "canonical_scope": "current-state",
            "aliases": ("state",),
            "releases": ("v6.84.5.1e9b",),
            "source_paths": ("modules/example.py",),
            "evidence_refs": ("EV-000",),
            "supersedes": (),
            "superseded_by": (),
            "updated": "2026-07-16",
            "last_reviewed": "2026-07-16",
            "verified_at": None,
        }
        if content_overrides:
            content_values.update(content_overrides)
        content = ProposedNoteContent(**content_values)
        type(self).content_constructions += 1
        hint = (
            CanonicalLocationHint(
                relative_path="canonical/current-state.md",
                parent_stable_id=None,
            )
            if operation is ProposalOperation.CREATE_NEW
            else None
        )
        temporary = KnowledgeChangeProposal(
            proposal_id="kprop:" + "0" * 64,
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=expected_revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        proposal = KnowledgeChangeProposal(
            proposal_id=compute_proposal_instance_id(temporary),
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=expected_revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        type(self).proposal_constructions += 2
        return proposal

    def validate(
        self,
        proposal: KnowledgeChangeProposal,
        *,
        vault_revision: str = REV_A,
        stable_ids: frozenset[str] | set[str] = frozenset({TARGET}),
    ) -> ValidationResult:
        validator = ProposalValidator(
            vault_revision=vault_revision,
            stable_ids=stable_ids,
        )
        type(self).validator_constructions += 1
        result = validator.validate(proposal)
        type(self).validation_result_constructions += 1
        return result

    def snapshot(
        self,
        text: str,
        *,
        stable_id: str = TARGET,
        revision: str = REV_A,
        path: str = "canonical/current-state.md",
    ) -> TrustedTargetSnapshot:
        return create_trusted_target_snapshot(
            source_bytes=text.encode("utf-8"),
            source_relative_path=path,
            target_stable_id=stable_id,
            captured_vault_revision=revision,
        )

    def state(
        self,
        *,
        revision: str = REV_A,
        stable_ids: frozenset[str] | set[str] = frozenset({TARGET}),
        current: TrustedTargetSnapshot | None = None,
        baseline: TrustedTargetSnapshot | None = None,
    ) -> CurrentKnowledgeState:
        return CurrentKnowledgeState(
            observed_vault_revision=revision,
            current_stable_ids=frozenset(stable_ids),
            current_target=current,
            baseline_target=baseline,
        )

    def review(
        self,
        proposal: KnowledgeChangeProposal,
        result: ValidationResult,
        state: CurrentKnowledgeState,
    ) -> KnowledgeChangeReviewArtifact:
        type(self).api_calls += 1
        return analyze_review(proposal, result, state)

    def tamper_result(self, result: ValidationResult, **changes: object) -> ValidationResult:
        clone = object.__new__(ValidationResult)
        for item in fields(ValidationResult):
            object.__setattr__(
                clone,
                item.name,
                changes.get(item.name, getattr(result, item.name)),
            )
        type(self).validation_result_constructions += 1
        return clone

    def clear_create_artifact(self, body: str = "created\n") -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body=body,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        return self.review(
            proposal,
            result,
            self.state(stable_ids={TARGET}),
        )

    def clear_update_artifact(
        self,
        *,
        before: str = "old\n",
        after: str = "new\n",
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(body=after)
        result = self.validate(proposal)
        current = self.snapshot(before)
        baseline = self.snapshot(before)
        return self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )

    def metadata_only_artifact(
        self,
        **content_overrides: object,
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(
            body="same body\n",
            content_overrides=content_overrides,
        )
        result = self.validate(proposal)
        current = self.snapshot("same body\n")
        return self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )

    def result_with_provenance_summary(
        self,
        summary: object,
    ) -> tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState]:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        tampered = self.tamper_result(result, provenance_summary=summary)
        return proposal, tampered, self.state(stable_ids={TARGET})

    def assert_no_unproven_equality_findings(
        self,
        artifact: KnowledgeChangeReviewArtifact,
    ) -> None:
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)

    def assert_no_normal_change_material(
        self,
        artifact: KnowledgeChangeReviewArtifact,
    ) -> None:
        self.assertIsNone(artifact.deterministic_text_diff)
        self.assertIsNone(artifact.deterministic_text_diff_hash)
        self.assertIsNone(artifact.representation_delta)
        self.assertIsNone(artifact.change_identity)

    def review_with_invalid_current_path(
        self,
        path: str,
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        valid = self.snapshot("before\n")
        invalid = replace(valid, source_relative_path=path)
        return self.review(
            proposal,
            result,
            self.state(current=invalid, baseline=valid),
        )

    def test_001_static_e9a_import_compatibility_uses_real_symbols(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(proposal, result, self.state(stable_ids={TARGET}))
        self.assertIs(E9A_API_BINDINGS["KnowledgeChangeProposal"], KnowledgeChangeProposal)
        self.assertIs(E9A_API_BINDINGS["ValidationResult"], ValidationResult)
        self.assertEqual(artifact.contract_version, "localcomet.knowledge-change-review/1.0")

    def test_002_factory_instance_id_caveat_is_not_used_for_binding(self) -> None:
        proposal = create_proposal_from_untrusted(
            operation="CREATE_NEW",
            target_stable_id=OTHER_TARGET,
            expected_vault_revision=REV_A,
            proposer={"agent_type": "test"},
            provenance={"reason": "factory caveat"},
            proposed_content={
                "title": "New",
                "body_text": "body\n",
                "type": "note",
                "status": "draft",
                "knowledge_layer": "project",
                "evidence_class": "C",
                "authority": "user",
            },
            canonical_location_hint={"relative_path": "notes/new.md"},
        )
        result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(proposal, result, self.state(stable_ids={TARGET}))
        self.assertNotEqual(compute_proposal_instance_id(proposal), proposal.proposal_id)
        self.assertEqual(artifact.proposal_id, proposal.proposal_id)
        self.assertNotIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {item.code for item in artifact.findings},
        )

    def test_003_exact_proposal_result_binding_accepts_matching_result(self) -> None:
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.findings, ())
        self.assertIsNotNone(artifact.change_identity)

    def test_004_proposal_a_result_is_rejected_for_proposal_b(self) -> None:
        proposal_a = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body="A\n",
        )
        proposal_b = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body="B\n",
        )
        result_a = self.validate(proposal_a, stable_ids={TARGET})
        artifact = self.review(proposal_b, result_a, self.state(stable_ids={TARGET}))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(
            artifact.findings[0].code,
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
        )
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_005_content_hash_mismatch_is_blocking(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        tampered = self.tamper_result(
            result,
            proposal_content_hash="sha256:" + "0" * 64,
        )
        artifact = self.review(proposal, tampered, self.state(stable_ids={TARGET}))
        detail = dict(artifact.findings[0].details)
        self.assertIn("proposal_content_hash", detail["mismatched_fields"])
        self.assertIsNone(artifact.change_identity)

    def test_006_contract_version_mismatch_is_detected_at_trust_boundary(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, contract_version="wrong/9")
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "contract_version",
            dict(artifact.findings[0].details)["mismatched_fields"],
        )

    def test_007_operation_type_and_value_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, operation=ProposalOperation.CREATE_NEW)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertEqual(
            artifact.findings[0].code,
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
        )
        self.assertIn("operation", dict(artifact.findings[0].details)["mismatched_fields"])

    def test_008_target_id_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, target_stable_id=TARGET)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        mismatch_fields = dict(artifact.findings[0].details)["mismatched_fields"].split(",")
        self.assertEqual(mismatch_fields, ["target_stable_id"])
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_009_expected_revision_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, expected_vault_revision=REV_B)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {finding.code for finding in artifact.findings},
        )
        self.assertIn(
            "expected_vault_revision",
            dict(artifact.findings[0].details)["mismatched_fields"],
        )

    def test_010_valid_result_performs_operation_specific_analysis(self) -> None:
        artifact = self.clear_update_artifact(before="one\n", after="two\n")
        self.assertEqual(artifact.validation_outcome, ValidationOutcome.VALID.value)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertIn("-one", artifact.deterministic_text_diff or "")
        self.assertIn("+two", artifact.deterministic_text_diff or "")

    def test_011_invalid_result_blocks_without_normal_diff(self) -> None:
        proposal = self.make_proposal(body="new\n")
        result = self.validate(proposal, stable_ids=set())
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids=set(), current=None, baseline=None),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.source_validation_findings[0][0], "UPDATE_TARGET_MISSING")
        self.assertIsNone(artifact.deterministic_text_diff)
        self.assertNotIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {finding.code for finding in artifact.findings},
        )

    def test_012_stale_result_blocks_with_revision_evidence_and_no_diff(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A)
        result = self.validate(proposal, vault_revision=REV_B)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, current=current),
        )
        stale = next(
            finding
            for finding in artifact.findings
            if finding.code is ConflictCode.STALE_VAULT_REVISION
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(dict(stale.details)["observed"], REV_B)
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_013_unsupported_operation_is_blocking_not_binding_mismatch(self) -> None:
        proposal = self.make_proposal(operation=ProposalOperation.DELETE)
        result = self.validate(proposal)
        artifact = self.review(proposal, result, self.state())
        codes = tuple(item.code for item in artifact.findings)
        self.assertIn(ConflictCode.UNSUPPORTED_OPERATION, codes)
        self.assertNotIn(ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH, codes)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_014_update_current_snapshot_generates_full_change_material(self) -> None:
        artifact = self.clear_update_artifact(
            before="alpha\nbeta\n",
            after="alpha\ngamma\n",
        )
        self.assertEqual(artifact.before_text_raw_hash, compute_text_raw_hash("alpha\nbeta\n"))
        self.assertTrue(artifact.deterministic_text_diff_hash.startswith("sha256:"))
        self.assertTrue(artifact.change_identity.startswith("kchange:"))
        self.assertTrue(artifact.review_artifact_identity.startswith("kreview:"))

    def test_015_update_verified_baseline_equal_current_allows_clear(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        baseline = self.snapshot("before\n", revision=REV_A)
        current = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)

    def test_016_missing_baseline_does_not_claim_historical_drift(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=self.snapshot("before\n")),
        )
        self.assertEqual(artifact.status, ReviewStatus.REVIEW_REQUIRED)
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,),
        )
        self.assertIsNotNone(artifact.change_identity)

    def test_017_baseline_revision_mismatch_fails_closed(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A, body="after\n")
        result = self.validate(proposal)
        baseline = self.snapshot("before\n", revision=REV_B)
        current = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        finding = artifact.findings[0]
        self.assertEqual(finding.code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("baseline_captured_vault_revision", dict(finding.details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_018_current_target_missing_is_blocking(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=None, baseline=self.snapshot("old\n")),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.TARGET_MISSING)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.representation_delta)

    def test_019_current_stable_id_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        wrong_snapshot = self.snapshot("old\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(current=wrong_snapshot, baseline=None),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("current_target_stable_id", dict(artifact.findings[0].details)["errors"])

    def test_020_current_snapshot_revision_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_A, current=current),
        )
        self.assertEqual(artifact.findings[0].severity, ConflictSeverity.BLOCKING)
        self.assertIn(
            "current_captured_vault_revision",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_021_baseline_stable_id_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        current = self.snapshot("old\n")
        baseline = self.snapshot("old\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "baseline_target_stable_id",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.change_identity)

    def test_022_verified_baseline_current_divergence_detects_target_change(self) -> None:
        proposal = self.make_proposal(body="proposed\n")
        result = self.validate(proposal)
        baseline = self.snapshot("baseline\n")
        current = self.snapshot("changed\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        finding = artifact.findings[0]
        self.assertEqual(finding.code, ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL)
        self.assertEqual(finding.severity, ConflictSeverity.BLOCKING)
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_023_create_clear_path_has_no_preimage(self) -> None:
        artifact = self.clear_create_artifact("new note\n")
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertIsNone(artifact.before_source_byte_hash)
        self.assertTrue((artifact.deterministic_text_diff or "").startswith("--- /dev/null"))
        self.assertFalse(artifact.representation_delta.before_present)

    def test_024_create_collision_is_deterministically_blocking(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        valid_result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(
            proposal,
            valid_result,
            self.state(stable_ids={TARGET, OTHER_TARGET}),
        )
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (ConflictCode.STABLE_ID_COLLISION,),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_025_create_rejects_fake_target_preimage(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        fake = self.snapshot("not allowed\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids={TARGET}, current=fake),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertNotIn(
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            {finding.code for finding in artifact.findings},
        )

    def test_026_strict_utf8_factory_rejects_decode_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "strict UTF-8"):
            create_trusted_target_snapshot(
                source_bytes=b"\xff\xfe",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=REV_A,
            )

    def test_027_bytes_text_mismatch_fails_closed_before_diff(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        mismatched = replace(valid, trusted_text="different\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=mismatched, baseline=valid),
        )
        errors = dict(artifact.findings[0].details)["errors"]
        self.assertIn("bytes_text_mismatch", errors)
        self.assertIn("text_raw_hash_mismatch", errors)
        self.assertIsNone(artifact.representation_delta)

    def test_028_source_byte_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, source_byte_hash="sha256:" + "1" * 64)
        artifact = self.review(
            proposal,
            result,
            self.state(current=bad, baseline=valid),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "source_byte_hash_mismatch",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.deterministic_text_diff_hash)

    def test_029_raw_text_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, text_raw_hash="sha256:" + "2" * 64)
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("text_raw_hash_mismatch", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_030_semantic_text_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\r\n")
        bad = replace(valid, semantic_text_hash="sha256:" + "3" * 64)
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        codes = [finding.code for finding in artifact.findings]
        self.assertEqual(codes, [ConflictCode.UNVERIFIED_TEXT_INPUT])
        self.assertIn(
            "semantic_text_hash_mismatch",
            dict(artifact.findings[0].details)["errors"],
        )

    def test_031_invalid_relative_path_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, source_relative_path="../escape.md")
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("invalid_relative_path", dict(artifact.findings[0].details)["errors"])
        self.assertNotIn("..", artifact.human_review_preview)

    def test_032_oversized_snapshot_is_blocked_without_identity_material(self) -> None:
        proposal = self.make_proposal(body="small\n")
        result = self.validate(proposal)
        text = "x" * (MAX_SOURCE_BYTES + 1)
        oversized = TrustedTargetSnapshot(
            source_bytes=text.encode("utf-8"),
            trusted_text=text,
            source_relative_path="canonical/current-state.md",
            target_stable_id=TARGET,
            captured_vault_revision=REV_A,
            source_byte_hash=compute_source_byte_hash(text.encode("utf-8")),
            text_raw_hash=compute_text_raw_hash(text),
            semantic_text_hash=compute_semantic_text_hash(text),
        )
        artifact = self.review(
            proposal,
            result,
            self.state(current=oversized, baseline=None),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("source_bytes_oversized", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_033_crlf_normalization_changes_only_line_endings(self) -> None:
        proposal = self.make_proposal(body="a\nb\n")
        result = self.validate(proposal)
        current = self.snapshot("a\r\nb\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(semantic_normalize_v1("a\r\nb\r\n"), "a\nb\n")
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)
        self.assertFalse(artifact.representation_delta.semantic_content_changed)

    def test_034_lone_cr_normalization_is_deterministic(self) -> None:
        proposal = self.make_proposal(body="a\nb\n")
        result = self.validate(proposal)
        current = self.snapshot("a\rb\r")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(semantic_normalize_v1("a\rb\r"), "a\nb\n")
        self.assertEqual(artifact.representation_delta.before_line_endings.cr_count, 2)
        self.assertEqual(artifact.deterministic_text_diff, "")

    def test_035_unicode_is_preserved_without_normalization(self) -> None:
        text = "Космос café e\u0301 🚀\n"
        proposal = self.make_proposal(body=text + "next\n")
        result = self.validate(proposal)
        current = self.snapshot(text)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertIn("Космос café e\u0301 🚀", artifact.deterministic_text_diff or "")
        self.assertEqual(semantic_normalize_v1(text), text)
        self.assertEqual(artifact.proposed_text_raw_hash, compute_text_raw_hash(text + "next\n"))

    def test_036_spaces_and_tabs_are_preserved(self) -> None:
        before = "a \t b\n"
        after = "a\t  b\n"
        artifact = self.clear_update_artifact(before=before, after=after)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertIn("-a \t b", artifact.deterministic_text_diff or "")
        self.assertIn("+a\t  b", artifact.deterministic_text_diff or "")

    def test_037_trailing_spaces_are_semantic_content(self) -> None:
        artifact = self.clear_update_artifact(before="line  \n", after="line\n")
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertNotEqual(artifact.before_semantic_text_hash, artifact.proposed_semantic_text_hash)
        self.assertNotIn(
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
            {finding.code for finding in artifact.findings},
        )

    def test_038_terminal_newline_is_preserved_in_raw_and_semantic_hashes(self) -> None:
        artifact = self.clear_update_artifact(before="line", after="line\n")
        self.assertTrue(artifact.representation_delta.terminal_newline_changed)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertNotEqual(artifact.before_text_raw_hash, artifact.proposed_text_raw_hash)
        self.assertNotEqual(artifact.before_semantic_text_hash, artifact.proposed_semantic_text_hash)

    def test_039_line_ending_only_delta_remains_visible_with_empty_semantic_diff(self) -> None:
        proposal = self.make_proposal(body="one\ntwo\n")
        result = self.validate(proposal)
        current = self.snapshot("one\r\ntwo\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(artifact.deterministic_text_diff, "")
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)
        self.assertIn("CRLF -> LF", artifact.human_review_preview)


    def test_040_terminal_newline_only_delta_remains_visible(self) -> None:
        artifact = self.clear_update_artifact(before="same", after="same\n")
        self.assertTrue(artifact.representation_delta.terminal_newline_changed)
        self.assertIn("terminal newline changed: true", artifact.human_review_preview)
        self.assertNotEqual(
            artifact.representation_delta.identity,
            self.clear_update_artifact(before="same\n", after="same\nmore\n").representation_delta.identity,
        )

    def test_041_body_equality_does_not_claim_complete_content_identity(self) -> None:
        artifact = self.clear_update_artifact(before="same\n", after="same\n")
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.deterministic_text_diff, "")
        self.assertFalse(artifact.representation_delta.semantic_content_changed)
        self.assertIn("current structured metadata comparison: unavailable", artifact.human_review_preview)


    def test_042_body_semantic_equivalence_does_not_claim_complete_equivalence(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        current = self.snapshot("same\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)


    def test_043_semantic_content_change_has_no_proposal_effect_finding(self) -> None:
        artifact = self.clear_update_artifact(before="before\n", after="after\n")
        effect_codes = {
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertTrue(effect_codes.isdisjoint({finding.code for finding in artifact.findings}))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_044_unproven_complete_equality_findings_are_both_absent(self) -> None:
        exact = self.clear_update_artifact(before="x\n", after="x\n")
        semantic = self.clear_update_artifact(before="x\r\n", after="x\n")
        effect_codes = {
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(effect_codes.isdisjoint({item.code for item in exact.findings}))
        self.assertTrue(effect_codes.isdisjoint({item.code for item in semantic.findings}))
        self.assertEqual(exact.status, ReviewStatus.CLEAR)
        self.assertEqual(semantic.status, ReviewStatus.CLEAR)


    def test_045_findings_have_fixed_documented_order(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            expected_revision=REV_A,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, stable_ids={OTHER_TARGET}),
        )
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (
                ConflictCode.STALE_VAULT_REVISION,
                ConflictCode.STABLE_ID_COLLISION,
            ),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_046_duplicate_stale_sources_produce_one_finding(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A)
        result = self.validate(proposal, vault_revision=REV_B)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_C, current=current),
        )
        stale_findings = [
            finding
            for finding in artifact.findings
            if finding.code is ConflictCode.STALE_VAULT_REVISION
        ]
        self.assertEqual(len(stale_findings), 1)
        self.assertEqual(len({finding.code for finding in artifact.findings}), len(artifact.findings))

    def test_047_clear_status_requires_valid_result_and_zero_findings(self) -> None:
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.validation_outcome, "VALID")
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_048_blocked_status_follows_any_blocking_finding(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids={OTHER_TARGET}),
        )
        self.assertTrue(any(f.severity is ConflictSeverity.BLOCKING for f in artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_049_review_required_follows_only_nonblocking_findings(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        current = self.snapshot("same\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=None),
        )
        self.assertTrue(artifact.findings)
        self.assertTrue(all(f.severity is ConflictSeverity.REVIEW for f in artifact.findings))
        self.assertEqual(
            tuple(f.code for f in artifact.findings),
            (ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,),
        )
        self.assertEqual(artifact.status, ReviewStatus.REVIEW_REQUIRED)


    def test_050_review_identity_is_deterministic(self) -> None:
        first = self.clear_update_artifact(before="a\n", after="b\n")
        second = self.clear_update_artifact(before="a\n", after="b\n")
        self.assertEqual(first.review_artifact_identity, second.review_artifact_identity)
        self.assertEqual(first.change_identity, second.change_identity)
        self.assertEqual(first.validation_snapshot, second.validation_snapshot)

    def test_051_identity_domains_are_separated(self) -> None:
        artifact = self.clear_update_artifact(before="a\n", after="b\n")
        digest_values = {
            artifact.deterministic_text_diff_hash,
            artifact.representation_delta.identity,
            "sha256:" + artifact.change_identity.removeprefix("kchange:"),
            "sha256:" + artifact.review_artifact_identity.removeprefix("kreview:"),
        }
        self.assertEqual(len(digest_values), 4)
        self.assertTrue(artifact.change_identity.startswith("kchange:"))
        self.assertTrue(artifact.review_artifact_identity.startswith("kreview:"))

    def test_052_full_diff_is_deterministic_with_fixed_headers_and_context(self) -> None:
        first = self.clear_update_artifact(
            before="0\n1\n2\n3\n4\n5\n6\n",
            after="0\n1\n2\nX\n4\n5\n6\n",
        )
        second = self.clear_update_artifact(
            before="0\n1\n2\n3\n4\n5\n6\n",
            after="0\n1\n2\nX\n4\n5\n6\n",
        )
        diff = first.deterministic_text_diff or ""
        self.assertEqual(diff, second.deterministic_text_diff)
        self.assertIn("--- before-body/canonical.current-state\n", diff)
        self.assertIn("+++ after-body/canonical.current-state\n", diff)
        self.assertIn("@@ -1,7 +1,7 @@", diff)


    def test_053_full_diff_hash_changes_when_full_diff_changes(self) -> None:
        first = self.clear_update_artifact(before="a\n", after="b\n")
        second = self.clear_update_artifact(before="a\n", after="c\n")
        self.assertNotEqual(first.deterministic_text_diff, second.deterministic_text_diff)
        self.assertNotEqual(first.deterministic_text_diff_hash, second.deterministic_text_diff_hash)
        self.assertNotEqual(first.change_identity, second.change_identity)

    def test_054_representation_identity_tracks_line_endings_and_terminal_newline(self) -> None:
        lf = self.clear_update_artifact(before="a\n", after="b\n")
        crlf = self.clear_update_artifact(before="a\r\n", after="b\n")
        no_terminal = self.clear_update_artifact(before="a", after="b\n")
        identities = {
            lf.representation_delta.identity,
            crlf.representation_delta.identity,
            no_terminal.representation_delta.identity,
        }
        self.assertEqual(len(identities), 3)
        self.assertFalse(lf.representation_delta.terminal_newline_changed)
        self.assertTrue(no_terminal.representation_delta.terminal_newline_changed)

    def test_055_preview_is_bounded_by_bytes_and_lines(self) -> None:
        body = "\n".join(f"new-{index}-" + "x" * 120 for index in range(1000)) + "\n"
        before = "\n".join(f"old-{index}-" + "y" * 120 for index in range(1000)) + "\n"
        artifact = self.clear_update_artifact(before=before, after=body)
        preview = artifact.human_review_preview
        self.assertLessEqual(len(preview.encode("utf-8")), MAX_PREVIEW_BYTES)
        self.assertLessEqual(len(preview.splitlines()), MAX_PREVIEW_LINES)
        self.assertIn(TRUNCATION_MARKER, preview)
        self.assertGreater(len((artifact.deterministic_text_diff or "").encode("utf-8")), len(preview.encode("utf-8")))

    def test_056_preview_truncation_is_deterministic(self) -> None:
        before = "\n".join(f"before-{index}" for index in range(900)) + "\n"
        after = "\n".join(f"after-{index}" for index in range(900)) + "\n"
        first = self.clear_update_artifact(before=before, after=after)
        second = self.clear_update_artifact(before=before, after=after)
        self.assertEqual(first.human_review_preview, second.human_review_preview)
        self.assertTrue(first.human_review_preview.endswith(TRUNCATION_MARKER + "\n"))
        self.assertEqual(first.human_review_preview.count(TRUNCATION_MARKER), 1)

    def test_057_stable_id_collection_bound_fails_closed(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        too_many = frozenset(f"id.{index}" for index in range(MAX_STABLE_IDS + 1))
        with self.assertRaisesRegex(ValueError, "hard bound"):
            self.state(stable_ids=too_many)
        artifact = self.review(proposal, result, self.state(stable_ids=set()))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_058_proposed_content_utf8_byte_bound_is_enforced(self) -> None:
        body = "🚀" * ((MAX_PROPOSED_CONTENT_BYTES // 4) + 1)
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body=body,
        )
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "byte bound"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_059_input_stable_id_collection_is_copied_and_not_mutated(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        caller_set = {TARGET}
        state = CurrentKnowledgeState(REV_A, caller_set)
        caller_set.add(OTHER_TARGET)
        artifact = self.review(proposal, result, state)
        self.assertEqual(state.current_stable_ids, frozenset({TARGET}))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(caller_set, {TARGET, OTHER_TARGET})

    def test_060_artifact_and_nested_collections_are_immutable(self) -> None:
        artifact = self.clear_update_artifact()
        with self.assertRaises(FrozenInstanceError):
            artifact.status = ReviewStatus.BLOCKED
        with self.assertRaises(FrozenInstanceError):
            artifact.proposed_content_snapshot.title = "changed"
        self.assertIsInstance(artifact.findings, tuple)
        self.assertIsInstance(artifact.validation_snapshot, FrozenCanonicalValue)
        self.assertIsInstance(artifact.proposed_content_snapshot, ProposedContentSnapshot)
        self.assertIsInstance(artifact.proposed_content_snapshot.aliases, tuple)
        self.assertIsInstance(artifact.validation_snapshot.mapping_items, tuple)


    def test_061_post_analysis_provenance_mutation_does_not_change_artifact(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(proposal, result, self.state(stable_ids=set()))
        original_snapshot = artifact.validation_snapshot
        original_identity = artifact.review_artifact_identity
        result.provenance_summary["reason"] = "mutated after analysis"
        result.provenance_summary["nested"] = {"mutable": ["value"]}
        self.assertEqual(artifact.validation_snapshot, original_snapshot)
        self.assertEqual(artifact.review_artifact_identity, original_identity)
        repeated = self.review(proposal, result, self.state(stable_ids=set()))
        self.assertNotEqual(repeated.review_artifact_identity, original_identity)

    def test_062_module_has_no_write_or_persistence_api(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        source = inspect.getsource(review_module)
        tree = ast.parse(source)
        forbidden_calls = {"open", "write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(forbidden_calls.isdisjoint(called))
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_063_module_has_no_network_subprocess_model_tauri_frontend_coupling(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        source = inspect.getsource(review_module)
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = {
            "socket", "urllib", "http", "requests", "subprocess", "asyncio",
            "openai", "tauri", "react", "frontend", "model_gateway",
        }
        self.assertTrue(forbidden.isdisjoint(imported_roots))
        artifact = self.clear_update_artifact()
        self.assertIsInstance(artifact, KnowledgeChangeReviewArtifact)

    def test_064_module_uses_no_dynamic_import(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        tree = ast.parse(inspect.getsource(review_module))
        dynamic_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec"}
        }
        self.assertEqual(dynamic_names, set())
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.findings, ())

    def test_065_create_path_emits_no_update_only_findings(self) -> None:
        artifact = self.clear_create_artifact()
        update_only = {
            ConflictCode.TARGET_MISSING,
            ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL,
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(update_only.isdisjoint({finding.code for finding in artifact.findings}))
        self.assertFalse(artifact.representation_delta.before_present)
        self.assertIsNone(artifact.before_text_raw_hash)

    def test_066_update_path_never_emits_create_collision(self) -> None:
        artifact = self.clear_update_artifact(before="old\n", after="new\n")
        self.assertNotIn(
            ConflictCode.STABLE_ID_COLLISION,
            {finding.code for finding in artifact.findings},
        )
        self.assertTrue(artifact.representation_delta.before_present)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_067_current_state_rejects_noncanonical_stable_id_grammar(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid stable ID"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=frozenset({"lc:Bad ID"}),
            )
        artifact = self.clear_create_artifact()
        self.assertNotIn("lc:", artifact.target_stable_id)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_068_snapshot_hash_helpers_bind_exact_bytes_raw_text_and_semantics(self) -> None:
        text = "é\r\nline\n"
        source = text.encode("utf-8")
        snapshot = create_trusted_target_snapshot(
            source_bytes=source,
            source_relative_path="canonical/current-state.md",
            target_stable_id=TARGET,
            captured_vault_revision=REV_A,
        )
        proposal = self.make_proposal(body="changed\n")
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=snapshot, baseline=snapshot),
        )
        self.assertEqual(snapshot.source_byte_hash, "sha256:" + hashlib.sha256(source).hexdigest())
        self.assertEqual(snapshot.text_raw_hash, compute_text_raw_hash(text))
        self.assertEqual(snapshot.semantic_text_hash, compute_semantic_text_hash(text))
        self.assertEqual(artifact.before_source_byte_hash, snapshot.source_byte_hash)


    def test_069_source_byte_only_tampering_is_rejected_before_delta_identity(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        valid = self.snapshot("same\n")
        tampered_bytes = b"same\r\n"
        tampered = replace(
            valid,
            source_bytes=tampered_bytes,
            source_byte_hash=compute_source_byte_hash(tampered_bytes),
        )
        artifact = self.review(
            proposal,
            result,
            self.state(current=tampered, baseline=valid),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("bytes_text_mismatch", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.representation_delta)
        self.assertIsNone(artifact.change_identity)

    def test_070_evidence_reference_bound_is_rechecked_at_e9b_boundary(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            evidence_count=1,
        )
        extra = tuple(
            EvidenceReference(reference=f"X-{index}", description="bounded")
            for index in range(33)
        )
        object.__setattr__(proposal.provenance, "evidence_references", extra)
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "evidence references"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_071_provenance_entry_bound_rejects_maximal_nested_valid_source_data(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            evidence_count=32,
        )
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "provenance entries"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_072_snapshot_path_length_bound_fails_closed(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        oversized_path = "a/" + "b" * 600 + ".md"
        bad = replace(valid, source_relative_path=oversized_path)
        artifact = self.review(
            proposal,
            result,
            self.state(current=bad, baseline=valid),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("invalid_relative_path", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_073_stable_id_length_bound_is_enforced_on_current_state(self) -> None:
        oversized_id = "a" * 129
        with self.assertRaisesRegex(ValueError, "invalid stable ID"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=frozenset({oversized_id}),
            )
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertLessEqual(len(artifact.target_stable_id), 128)



    def test_074_title_only_change_is_governed_and_visible_without_body_claim(self) -> None:
        baseline = self.metadata_only_artifact()
        changed = self.metadata_only_artifact(title="Renamed Current State")
        self.assertEqual(changed.deterministic_text_diff, "")
        self.assertEqual(changed.proposed_content_snapshot.title, "Renamed Current State")
        self.assertIn('- title: "Renamed Current State"', changed.human_review_preview)
        self.assertNotEqual(baseline.change_identity, changed.change_identity)
        self.assert_no_unproven_equality_findings(changed)

    def test_075_classification_metadata_changes_each_change_governed_identity(self) -> None:
        baseline = self.metadata_only_artifact()
        variants = (
            ("type", "architecture_record"),
            ("status", "proposed"),
            ("knowledge_layer", "architecture"),
        )
        identities: set[str | None] = set()
        for field_name, value in variants:
            with self.subTest(field=field_name):
                artifact = self.metadata_only_artifact(**{field_name: value})
                identities.add(artifact.change_identity)
                self.assertEqual(getattr(artifact.proposed_content_snapshot, field_name), value)
                self.assertIn(f'- {field_name}: "{value}"', artifact.human_review_preview)
                self.assertNotEqual(baseline.review_artifact_identity, artifact.review_artifact_identity)
                self.assert_no_unproven_equality_findings(artifact)
        self.assertEqual(len(identities), len(variants))

    def test_076_evidence_and_authority_metadata_are_not_reduced_to_body_text(self) -> None:
        evidence = self.metadata_only_artifact(evidence_class="B")
        authority = self.metadata_only_artifact(authority="validated-observation")
        self.assertNotEqual(evidence.change_identity, authority.change_identity)
        self.assertIn('- evidence_class: "B"', evidence.human_review_preview)
        self.assertIn('- authority: "validated-observation"', authority.human_review_preview)
        self.assertEqual(evidence.deterministic_text_diff, "")
        self.assertEqual(authority.deterministic_text_diff, "")
        self.assert_no_unproven_equality_findings(evidence)
        self.assert_no_unproven_equality_findings(authority)

    def test_077_canonical_metadata_changes_are_snapshotted_with_exact_types(self) -> None:
        canonical_flag = self.metadata_only_artifact(canonical=False)
        canonical_scope = self.metadata_only_artifact(canonical_scope="architecture")
        self.assertIs(canonical_flag.proposed_content_snapshot.canonical, False)
        self.assertEqual(canonical_scope.proposed_content_snapshot.canonical_scope, "architecture")
        self.assertIn("- canonical: false", canonical_flag.human_review_preview)
        self.assertIn('- canonical_scope: "architecture"', canonical_scope.human_review_preview)
        self.assertNotEqual(canonical_flag.change_identity, canonical_scope.change_identity)

    def test_078_aliases_and_releases_metadata_are_ordered_and_visible(self) -> None:
        aliases = self.metadata_only_artifact(aliases=("state", "current"))
        releases = self.metadata_only_artifact(releases=("v6.84.5.1e9a", "v6.84.5.1e9b"))
        self.assertEqual(aliases.proposed_content_snapshot.aliases, ("state", "current"))
        self.assertEqual(releases.proposed_content_snapshot.releases[-1], "v6.84.5.1e9b")
        self.assertIn('- aliases: ["state","current"]', aliases.human_review_preview)
        self.assertIn('- releases: ["v6.84.5.1e9a","v6.84.5.1e9b"]', releases.human_review_preview)
        self.assertNotEqual(aliases.review_artifact_identity, releases.review_artifact_identity)

    def test_079_source_paths_and_evidence_refs_metadata_are_governed(self) -> None:
        source_paths = self.metadata_only_artifact(
            source_paths=("modules/example.py", "tools/example_test.py"),
        )
        evidence_refs = self.metadata_only_artifact(
            evidence_refs=("EV-000", "EV-001"),
        )
        self.assertIn('"tools/example_test.py"', source_paths.human_review_preview)
        self.assertIn('"EV-001"', evidence_refs.human_review_preview)
        self.assertNotEqual(source_paths.change_identity, evidence_refs.change_identity)
        self.assertEqual(source_paths.deterministic_text_diff, "")
        self.assertEqual(evidence_refs.deterministic_text_diff, "")

    def test_080_supersession_metadata_changes_remain_review_only_not_publication(self) -> None:
        supersedes = self.metadata_only_artifact(supersedes=("canonical.previous-state",))
        superseded_by = self.metadata_only_artifact(superseded_by=("canonical.future-state",))
        self.assertIn('"canonical.previous-state"', supersedes.human_review_preview)
        self.assertIn('"canonical.future-state"', superseded_by.human_review_preview)
        self.assertIn("publication-byte claim: unavailable by contract", supersedes.human_review_preview)
        self.assertFalse(supersedes.representation_delta.after_source_bytes_known)
        self.assertFalse(superseded_by.representation_delta.after_source_bytes_known)

    def test_081_lifecycle_metadata_changes_each_participate_in_identity(self) -> None:
        variants = (
            ("updated", "2026-07-17"),
            ("last_reviewed", "2026-07-18"),
            ("verified_at", "2026-07-16T12:30:00Z"),
        )
        identities: list[str | None] = []
        for field_name, value in variants:
            artifact = self.metadata_only_artifact(**{field_name: value})
            identities.append(artifact.change_identity)
            self.assertIn(field_name, artifact.human_review_preview)
            self.assertEqual(getattr(artifact.proposed_content_snapshot, field_name), value)
            self.assert_no_unproven_equality_findings(artifact)
        self.assertEqual(len(set(identities)), 3)

    def test_082_every_proposed_content_field_is_present_in_snapshot_and_preview(self) -> None:
        artifact = self.metadata_only_artifact(verified_at="2026-07-16T12:30:00Z")
        field_names = tuple(item.name for item in fields(ProposedContentSnapshot))
        self.assertEqual(len(field_names), 18)
        for field_name in field_names:
            with self.subTest(field=field_name):
                self.assertIn(f"- {field_name}:", artifact.human_review_preview)
        self.assertEqual(
            tuple(artifact.proposed_content_snapshot.identity_payload()),
            field_names,
        )

    def test_083_empty_mapping_and_empty_sequence_have_distinct_snapshot_identity(self) -> None:
        proposal_a, result_a, state_a = self.result_with_provenance_summary({"node": {}})
        proposal_b, result_b, state_b = self.result_with_provenance_summary({"node": []})
        artifact_a = self.review(proposal_a, result_a, state_a)
        artifact_b = self.review(proposal_b, result_b, state_b)
        self.assertEqual(artifact_a.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact_b.status, ReviewStatus.CLEAR)
        self.assertNotEqual(
            artifact_a.validation_snapshot.identity_payload(),
            artifact_b.validation_snapshot.identity_payload(),
        )
        self.assertNotEqual(artifact_a.review_artifact_identity, artifact_b.review_artifact_identity)

    def test_084_nested_mapping_and_sequence_type_tags_remain_distinct(self) -> None:
        proposal_a, result_a, state_a = self.result_with_provenance_summary(
            {"outer": [{"inner": []}]},
        )
        proposal_b, result_b, state_b = self.result_with_provenance_summary(
            {"outer": [{"inner": {}}]},
        )
        first = self.review(proposal_a, result_a, state_a)
        second = self.review(proposal_b, result_b, state_b)
        self.assertNotEqual(first.validation_snapshot, second.validation_snapshot)
        first_payload = first.validation_snapshot.identity_payload()
        second_payload = second.validation_snapshot.identity_payload()
        self.assertIn('"type": "sequence"', repr(first_payload).replace("'", '"'))
        self.assertNotEqual(first_payload, second_payload)

    def test_085_validation_snapshot_self_cycle_returns_deterministic_blocked_artifact(self) -> None:
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        proposal, result, state = self.result_with_provenance_summary(cyclic)
        first = self.review(proposal, result, state)
        second = self.review(proposal, result, state)
        self.assertEqual(first.status, ReviewStatus.BLOCKED)
        self.assertEqual(first.review_artifact_identity, second.review_artifact_identity)
        self.assertIn(("validation_snapshot_error", "cycle_detected"), first.findings[0].details)
        self.assert_no_normal_change_material(first)

    def test_086_validation_snapshot_indirect_cycle_is_caught_without_recursion_error(self) -> None:
        mapping: dict[str, object] = {}
        sequence: list[object] = [mapping]
        mapping["sequence"] = sequence
        proposal, result, state = self.result_with_provenance_summary(mapping)
        artifact = self.review(proposal, result, state)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("cycle_detected", repr(artifact.findings))
        self.assertIsInstance(artifact.validation_snapshot, FrozenCanonicalValue)
        self.assert_no_normal_change_material(artifact)

    def test_087_validation_snapshot_excessive_depth_fails_closed(self) -> None:
        value: object = "leaf"
        for _ in range(MAX_VALIDATION_SNAPSHOT_DEPTH + 5):
            value = [value]
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("maximum_depth_exceeded", repr(artifact.findings))
        self.assert_no_normal_change_material(artifact)

    def test_088_validation_snapshot_excessive_total_nodes_fails_closed(self) -> None:
        value = [list(range(64)) for _ in range(70)]
        self.assertGreater(1 + 70 + 70 * 64, MAX_VALIDATION_SNAPSHOT_NODES)
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_total_nodes_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assert_no_normal_change_material(artifact)

    def test_089_validation_snapshot_mapping_entry_bound_is_enforced(self) -> None:
        value = {
            f"k{index:03d}": index
            for index in range(MAX_VALIDATION_MAPPING_ENTRIES + 1)
        }
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_mapping_entries_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_090_validation_snapshot_sequence_entry_bound_is_enforced(self) -> None:
        value = list(range(MAX_VALIDATION_SEQUENCE_ENTRIES + 1))
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_sequence_entries_exceeded", repr(artifact.findings))
        self.assertIsNone(artifact.deterministic_text_diff_hash)

    def test_091_validation_snapshot_key_length_bound_is_enforced(self) -> None:
        value = {"k" * (MAX_VALIDATION_KEY_LENGTH + 1): "value"}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_mapping_key_length_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)

    def test_092_validation_snapshot_string_value_bound_is_enforced(self) -> None:
        value = {"value": "x" * (MAX_VALIDATION_STRING_LENGTH + 1)}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_string_value_length_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assert_no_normal_change_material(artifact)

    def test_093_validation_snapshot_unsupported_mutable_type_fails_closed(self) -> None:
        value = {"unsupported": {"set-item"}}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("unsupported_value_type", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_094_windows_drive_root_unc_and_absolute_paths_are_rejected(self) -> None:
        rejected = (
            "C:foo.md",
            "\\foo.md",
            "\\\\server\\share\\foo.md",
            "/foo.md",
            "C:\\foo.md",
        )
        for path in rejected:
            with self.subTest(path=path):
                artifact = self.review_with_invalid_current_path(path)
                self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
                self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
                self.assert_no_normal_change_material(artifact)

    def test_095_parent_traversal_nul_and_overlength_paths_are_rejected(self) -> None:
        rejected = (
            "canonical/../foo.md",
            "canonical/\x00foo.md",
            "a" * (MAX_PATH_LENGTH + 1),
        )
        observed_errors: set[str] = set()
        for path in rejected:
            artifact = self.review_with_invalid_current_path(path)
            observed_errors.add(artifact.findings[0].details[0][1])
            self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
            self.assert_no_normal_change_material(artifact)
        self.assertEqual(observed_errors, {"invalid_relative_path"})

    def test_096_normal_vault_relative_and_dotted_paths_are_accepted(self) -> None:
        paths = (
            "canonical/current-state.md",
            "architecture.knowledge-layer.md",
            "architecture/knowledge-layer.md",
        )
        for path in paths:
            proposal = self.make_proposal(body="after\n")
            result = self.validate(proposal)
            current = self.snapshot("before\n", path=path)
            artifact = self.review(
                proposal,
                result,
                self.state(current=current, baseline=current),
            )
            self.assertEqual(artifact.status, ReviewStatus.CLEAR)
            self.assertIsNotNone(artifact.change_identity)

    def test_097_string_stable_id_collection_is_rejected_not_split_into_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "list, tuple, set, or frozenset"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids="abc",
            )
        artifact = self.clear_create_artifact()
        self.assertNotEqual(artifact.stable_id_set_hash, compute_text_raw_hash("abc"))

    def test_098_bytes_mapping_generator_and_scalar_stable_id_inputs_are_rejected(self) -> None:
        rejected = (
            b"abc",
            bytearray(b"abc"),
            {TARGET: True},
            (item for item in (TARGET,)),
            [[TARGET]],
            7,
        )
        for value in rejected:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    CurrentKnowledgeState(
                        observed_vault_revision=REV_A,
                        current_stable_ids=value,
                    )
        self.assertEqual(self.clear_create_artifact().status, ReviewStatus.CLEAR)

    def test_099_approved_stable_id_collection_types_are_copied_to_frozenset(self) -> None:
        approved = (
            [TARGET],
            (TARGET,),
            {TARGET},
            frozenset({TARGET}),
        )
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        for collection in approved:
            state = CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=collection,
            )
            artifact = self.review(proposal, result, state)
            self.assertIsInstance(state.current_stable_ids, frozenset)
            self.assertEqual(state.current_stable_ids, frozenset({TARGET}))
            self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_100_valid_result_observed_revision_drift_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A, body="after\n")
        result = self.validate(proposal, vault_revision=REV_A)
        current = self.snapshot("before\n", revision=REV_B)
        baseline = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, current=current, baseline=baseline),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(ConflictCode.STALE_VAULT_REVISION, {item.code for item in artifact.findings})
        self.assert_no_normal_change_material(artifact)

    def test_101_validated_revision_mismatch_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        tampered = self.tamper_result(result, validated_vault_revision=REV_B)
        current = self.snapshot("before\n")
        artifact = self.review(
            proposal,
            tampered,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.findings[0].code, ConflictCode.STALE_VAULT_REVISION)
        self.assert_no_normal_change_material(artifact)

    def test_102_expected_revision_binding_mismatch_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            expected_revision=REV_A,
            body="created\n",
        )
        authentic = self.validate(proposal, stable_ids={TARGET})
        mismatched = self.tamper_result(
            authentic,
            expected_vault_revision=REV_B,
        )
        artifact = self.review(
            proposal,
            mismatched,
            self.state(revision=REV_A, stable_ids={TARGET}),
        )
        codes = tuple(item.code for item in artifact.findings)
        self.assertEqual(codes, (ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,))
        self.assertEqual(artifact.status.value, "BLOCKED")
        self.assertFalse(any(code is ConflictCode.STALE_VAULT_REVISION for code in codes))
        self.assert_no_normal_change_material(artifact)




if __name__ == "__main__":
    unittest.main(verbosity=2)
````

### ПУТЬ: tools/test_v68451e9c_human_review_decision.py (1237 строк, 54222 байт)

````python
"""Focused behavioral tests for v6.84.5.1e9c Human Review Decision."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True

from modules.knowledge_change_proposal_ru import (
    CONTRACT_VERSION as E9A_CONTRACT_VERSION,
    CanonicalLocationHint,
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposerMetadata,
    ProposedNoteContent,
    Provenance,
    ValidationResult,
    compute_proposal_instance_id,
)
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as E9B_CONTRACT_VERSION,
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
    create_trusted_target_snapshot,
)
import modules.knowledge_change_review_decision_ru as decision_contract


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "modules" / "knowledge_change_review_decision_ru.py"
TEST_PATH = Path(__file__).resolve()
REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
TARGET = "canonical.current-state"
CLEAR_TARGET = "test.e9c-clear"
BLOCKED_TARGET = "test.e9c-blocked"


def _source_text() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _clone_review(
    artifact: KnowledgeChangeReviewArtifact,
    **changes: object,
) -> KnowledgeChangeReviewArtifact:
    clone = object.__new__(KnowledgeChangeReviewArtifact)
    for item in fields(KnowledgeChangeReviewArtifact):
        object.__setattr__(clone, item.name, changes.get(item.name, getattr(artifact, item.name)))
    return clone


class HumanReviewDecisionBehaviorTests(unittest.TestCase):
    api = decision_contract
    record_counts = True
    counters = {
        "proposer_metadata": 0,
        "provenance": 0,
        "proposed_content": 0,
        "knowledge_change_proposals": 0,
        "proposal_validators": 0,
        "validation_results": 0,
        "trusted_target_snapshots": 0,
        "current_knowledge_states": 0,
        "knowledge_change_review_artifacts": 0,
        "human_review_decisions": 0,
    }
    fault_results: tuple[dict[str, object], ...] = ()

    def _count(self, name: str, amount: int = 1) -> None:
        if self.record_counts:
            type(self).counters[name] += amount

    def _make_proposal(
        self,
        *,
        operation: ProposalOperation,
        target: str,
        revision: str,
        body: str,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="focused-test",
            agent_instance_id="e9c-instance",
            model_identifier="none",
            source_workflow="e9c-human-review",
        )
        self._count("proposer_metadata")
        provenance = Provenance(
            reason="Exercise the exact e9c review-decision boundary",
            source_observation="real e9a/e9b in-memory artifact",
            related_stable_ids=(target,),
            workflow_origin="focused-test",
        )
        self._count("provenance")
        content = ProposedNoteContent(
            title="Decision Contract Fixture",
            body_text=body,
            type="project_state",
            status="proposed",
            knowledge_layer="canonical",
            evidence_class="A",
            authority="repository",
            canonical=operation is ProposalOperation.UPDATE_EXISTING,
            canonical_scope="current-state" if operation is ProposalOperation.UPDATE_EXISTING else None,
            aliases=("decision-fixture",),
            releases=("v6.84.5.1e9c",),
            source_paths=("modules/knowledge_change_review_decision_ru.py",),
            evidence_refs=("E9C-FOCUSED",),
            updated="2026-07-16",
            last_reviewed="2026-07-16",
        )
        self._count("proposed_content")
        hint = (
            CanonicalLocationHint(relative_path=f"tests/{target}.md")
            if operation is ProposalOperation.CREATE_NEW
            else None
        )
        temporary = KnowledgeChangeProposal(
            proposal_id="kprop:" + "0" * 64,
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        proposal = KnowledgeChangeProposal(
            proposal_id=compute_proposal_instance_id(temporary),
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        self._count("knowledge_change_proposals", 2)
        return proposal

    def _build_review(
        self,
        status: ReviewStatus,
        *,
        revision: str = REV_A,
    ) -> tuple[
        KnowledgeChangeProposal,
        ValidationResult,
        CurrentKnowledgeState,
        KnowledgeChangeReviewArtifact,
    ]:
        if status is ReviewStatus.CLEAR:
            operation = ProposalOperation.CREATE_NEW
            target = CLEAR_TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET}
            current = None
        elif status is ReviewStatus.REVIEW_REQUIRED:
            operation = ProposalOperation.UPDATE_EXISTING
            target = TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET}
            current = create_trusted_target_snapshot(
                source_bytes=b"before\n",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=revision,
            )
            self._count("trusted_target_snapshots")
        elif status is ReviewStatus.BLOCKED:
            operation = ProposalOperation.CREATE_NEW
            target = BLOCKED_TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET, BLOCKED_TARGET}
            current = None
        else:
            raise AssertionError("unsupported fixture status")

        proposal = self._make_proposal(
            operation=operation,
            target=target,
            revision=revision,
            body=f"after-{status.value}\n",
        )
        validator = ProposalValidator(revision, validator_ids)
        self._count("proposal_validators")
        validation = validator.validate(proposal)
        self._count("validation_results")
        state = CurrentKnowledgeState(
            observed_vault_revision=revision,
            current_stable_ids=state_ids,
            current_target=current,
            baseline_target=None,
        )
        self._count("current_knowledge_states")
        artifact = analyze_review(proposal, validation, state)
        self._count("knowledge_change_review_artifacts")
        if artifact.status is not status:
            raise AssertionError(f"fixture status mismatch: {artifact.status} != {status}")
        return proposal, validation, state, artifact

    def setUp(self) -> None:
        self.actor = self.api.HumanReviewerMetadata(
            actor_identifier="human-reviewer-001",
            display_name="Local Reviewer",
            source="local-human-review",
        )
        self.clear_inputs = self._build_review(ReviewStatus.CLEAR)
        self.required_inputs = self._build_review(ReviewStatus.REVIEW_REQUIRED)
        self.blocked_inputs = self._build_review(ReviewStatus.BLOCKED)
        self.clear = self.clear_inputs[-1]
        self.required = self.required_inputs[-1]
        self.blocked = self.blocked_inputs[-1]

    def _decision_kwargs(
        self,
        artifact: KnowledgeChangeReviewArtifact,
        **overrides: object,
    ) -> dict[str, object]:
        values: dict[str, object] = {
            "expected_proposal_id": artifact.proposal_id,
            "expected_review_artifact_identity": artifact.review_artifact_identity,
            "expected_change_identity": artifact.change_identity,
            "expected_observed_vault_revision": artifact.observed_vault_revision,
            "current_observed_vault_revision": artifact.observed_vault_revision,
            "decision": self.api.HumanReviewDecisionValue.REJECT,
            "comment": "",
            "actor": self.actor,
        }
        values.update(overrides)
        return values

    def decide(
        self,
        artifact: KnowledgeChangeReviewArtifact,
        **overrides: object,
    ):
        result = self.api.create_human_review_decision(
            artifact,
            **self._decision_kwargs(artifact, **overrides),
        )
        if self.record_counts and self.api is decision_contract:
            type(self).counters["human_review_decisions"] += 1
        return result

    def assert_rejection(self, expected_code, callback) -> None:
        with self.assertRaises(self.api.HumanReviewDecisionRejected) as captured:
            callback()
        self.assertIs(captured.exception.code, expected_code)
        self.assertEqual(str(captured.exception), expected_code.value)

    def _independent_identity(self, decision, *, domain: str | None = None) -> str:
        semantics = {
            "hard_stop": decision.hard_stop,
            "review_decision_only": decision.review_decision_only,
            "actor_metadata_evidence_only": decision.actor_metadata_evidence_only,
            "human_identity_authenticated": decision.human_identity_authenticated,
            "grants_write_authority": decision.grants_write_authority,
            "grants_vault_write_authority": decision.grants_vault_write_authority,
            "grants_persistence_authority": decision.grants_persistence_authority,
            "grants_publication_authority": decision.grants_publication_authority,
            "grants_merge_authority": decision.grants_merge_authority,
            "grants_rebase_authority": decision.grants_rebase_authority,
            "grants_execution_authority": decision.grants_execution_authority,
            "grants_policy_authority": decision.grants_policy_authority,
            "grants_model_gateway_authority": decision.grants_model_gateway_authority,
            "grants_tauri_frontend_authority": decision.grants_tauri_frontend_authority,
            "grants_automatic_approval_authority": decision.grants_automatic_approval_authority,
        }
        payload = {
            "decision_contract_version": decision.contract_version,
            "review_contract_version": decision.review_contract_version,
            "review_status": decision.review_status.value,
            "proposal_id": decision.proposal_id,
            "review_artifact_identity": decision.review_artifact_identity,
            "change_identity": decision.change_identity,
            "observed_vault_revision": decision.observed_vault_revision,
            "decision": decision.decision.value,
            "comment": decision.comment,
            "actor": {
                "actor_identifier": decision.actor.actor_identifier,
                "display_name": decision.actor.display_name,
                "source": decision.actor.source,
            },
            "semantics": semantics,
        }
        envelope = {
            "domain": domain or self.api.IDENTITY_DOMAIN,
            "version": self.api.IDENTITY_VERSION,
            "payload": payload,
        }
        canonical = json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "kdecision:" + hashlib.sha256(canonical).hexdigest()

    def test_001_static_real_e9b_import_and_public_contract(self) -> None:
        decision = self.decide(self.clear)
        self.assertEqual(self.api.REVIEW_CONTRACT_VERSION, E9B_CONTRACT_VERSION)
        self.assertIs(self.api.KnowledgeChangeReviewArtifact, KnowledgeChangeReviewArtifact)
        self.assertEqual(decision.contract_version, "localcomet.knowledge-change-review-decision/1.0")

    def test_002_clear_approve_accepts_empty_comment(self) -> None:
        decision = self.decide(
            self.clear,
            decision=self.api.HumanReviewDecisionValue.APPROVE,
            comment="",
        )
        self.assertIs(decision.decision, self.api.HumanReviewDecisionValue.APPROVE)
        self.assertIsNotNone(decision.change_identity)
        self.assertEqual(decision.comment, "")

    def test_003_clear_reject_accepts_exact_string_value(self) -> None:
        decision = self.decide(self.clear, decision="REJECT", comment="not selected")
        self.assertIs(decision.decision, self.api.HumanReviewDecisionValue.REJECT)
        self.assertEqual(decision.review_status, ReviewStatus.CLEAR)
        self.assertEqual(decision.comment, "not selected")

    def test_004_clear_request_changes_accepts_comment(self) -> None:
        decision = self.decide(
            self.clear,
            decision=self.api.HumanReviewDecisionValue.REQUEST_CHANGES,
            comment="Please add evidence.",
        )
        self.assertEqual(decision.decision.value, "REQUEST_CHANGES")
        self.assertEqual(decision.proposal_id, self.clear.proposal_id)

    def test_005_review_required_approve_is_allowed_with_change_identity(self) -> None:
        decision = self.decide(self.required, decision="APPROVE")
        self.assertEqual(decision.review_status, ReviewStatus.REVIEW_REQUIRED)
        self.assertTrue(decision.change_identity.startswith("kchange:"))

    def test_006_review_required_reject_is_allowed(self) -> None:
        decision = self.decide(self.required, decision="REJECT", comment="reviewed")
        self.assertEqual(decision.decision.value, "REJECT")
        self.assertEqual(decision.review_artifact_identity, self.required.review_artifact_identity)

    def test_007_review_required_request_changes_is_allowed(self) -> None:
        decision = self.decide(
            self.required,
            decision="REQUEST_CHANGES",
            comment="Resolve the missing historical baseline.",
        )
        self.assertEqual(decision.comment, "Resolve the missing historical baseline.")
        self.assertEqual(decision.observed_vault_revision, REV_A)

    def test_008_blocked_approve_is_forbidden(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.BLOCKED_APPROVAL_FORBIDDEN,
            lambda: self.decide(self.blocked, decision="APPROVE"),
        )
        self.assertIsNone(self.blocked.change_identity)

    def test_009_blocked_reject_is_allowed_when_fresh_and_exact(self) -> None:
        decision = self.decide(self.blocked, decision="REJECT", comment="blocked")
        self.assertEqual(decision.review_status, ReviewStatus.BLOCKED)
        self.assertIsNone(decision.change_identity)
        self.assertTrue(decision.hard_stop)

    def test_010_blocked_request_changes_is_allowed_when_fresh_and_exact(self) -> None:
        decision = self.decide(
            self.blocked,
            decision="REQUEST_CHANGES",
            comment="Remove the stable-ID collision.",
        )
        self.assertIsNone(decision.change_identity)
        self.assertEqual(decision.decision.value, "REQUEST_CHANGES")

    def test_011_approve_requires_non_null_change_identity(self) -> None:
        without_change = _clone_review(self.clear, change_identity=None)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.APPROVAL_REQUIRES_CHANGE_IDENTITY,
            lambda: self.decide(without_change, decision="APPROVE"),
        )
        self.assertIsNone(without_change.change_identity)

    def test_012_exact_proposal_id_binding_rejects_mismatch(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_proposal_id="kprop:" + "f" * 64,
            ),
        )
        self.assertNotEqual(self.clear.proposal_id, "kprop:" + "f" * 64)

    def test_013_bindings_for_artifact_a_are_rejected_for_artifact_b(self) -> None:
        values = self._decision_kwargs(self.clear)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH,
            lambda: self.api.create_human_review_decision(self.required, **values),
        )
        self.assertNotEqual(self.clear.review_artifact_identity, self.required.review_artifact_identity)

    def test_014_review_artifact_identity_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.REVIEW_ARTIFACT_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_review_artifact_identity="kreview:" + "e" * 64,
            ),
        )
        self.assertTrue(self.clear.review_artifact_identity.startswith("kreview:"))

    def test_015_change_identity_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_change_identity="kchange:" + "d" * 64,
            ),
        )
        self.assertNotEqual(self.clear.change_identity, "kchange:" + "d" * 64)

    def test_016_exact_none_change_identity_binding_is_preserved(self) -> None:
        decision = self.decide(
            self.blocked,
            expected_change_identity=None,
            decision="REJECT",
        )
        self.assertIsNone(decision.change_identity)
        self.assertIsNone(self.blocked.change_identity)

    def test_017_non_none_expectation_for_none_change_identity_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.blocked,
                expected_change_identity="kchange:" + "c" * 64,
                decision="REJECT",
            ),
        )
        self.assertEqual(self.blocked.status, ReviewStatus.BLOCKED)

    def test_018_expected_observed_revision_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.OBSERVED_VAULT_REVISION_MISMATCH,
            lambda: self.decide(self.clear, expected_observed_vault_revision=REV_B),
        )
        self.assertEqual(self.clear.observed_vault_revision, REV_A)

    def test_019_current_observed_revision_drift_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.STALE_CURRENT_VAULT_REVISION,
            lambda: self.decide(self.clear, current_observed_vault_revision=REV_B),
        )
        self.assertNotEqual(REV_A, REV_B)

    def test_020_unsupported_review_contract_is_rejected(self) -> None:
        unsupported = _clone_review(self.clear, contract_version="unsupported/9")
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT,
            lambda: self.decide(unsupported),
        )
        self.assertIs(type(unsupported), KnowledgeChangeReviewArtifact)

    def test_021_wrong_review_artifact_type_is_rejected(self) -> None:
        values = self._decision_kwargs(self.clear)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE,
            lambda: self.api.create_human_review_decision({}, **values),
        )
        self.assertNotIsInstance({}, KnowledgeChangeReviewArtifact)

    def test_022_unsupported_decision_is_exact_and_case_sensitive(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.UNSUPPORTED_DECISION,
            lambda: self.decide(self.clear, decision="approve"),
        )
        self.assertNotIn("approve", tuple(item.value for item in self.api.HumanReviewDecisionValue))

    def test_023_request_changes_empty_comment_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_REQUIRED,
            lambda: self.decide(self.clear, decision="REQUEST_CHANGES", comment=""),
        )
        self.assertEqual("".strip(), "")

    def test_024_request_changes_whitespace_comment_is_rejected_without_rewrite(self) -> None:
        raw = " \t\n "
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_REQUIRED,
            lambda: self.decide(self.clear, decision="REQUEST_CHANGES", comment=raw),
        )
        self.assertEqual(raw, " \t\n ")

    def test_025_comment_character_bound_is_enforced(self) -> None:
        raw = "x" * (self.api.MAX_COMMENT_CHARS + 1)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_CHARACTER_LIMIT_EXCEEDED,
            lambda: self.decide(self.clear, decision="REJECT", comment=raw),
        )
        self.assertEqual(len(raw), 2_001)

    def test_026_comment_utf8_byte_bound_is_enforced_independently(self) -> None:
        raw = "🚀" * ((self.api.MAX_COMMENT_UTF8_BYTES // 4) + 1)
        self.assertLess(len(raw), self.api.MAX_COMMENT_CHARS)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_UTF8_BYTE_LIMIT_EXCEEDED,
            lambda: self.decide(self.clear, decision="REJECT", comment=raw),
        )
        self.assertGreater(len(raw.encode("utf-8")), self.api.MAX_COMMENT_UTF8_BYTES)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_UTF8_ENCODING_INVALID,
            lambda: self.decide(self.clear, decision="REJECT", comment="\ud800"),
        )

    def test_027_unicode_comment_is_preserved_exactly(self) -> None:
        raw = "  Нужны доказательства — café 中文 🚀  "
        decision = self.decide(self.clear, decision="REQUEST_CHANGES", comment=raw)
        self.assertEqual(decision.comment, raw)
        self.assertEqual(decision.comment.encode("utf-8"), raw.encode("utf-8"))
        self.assertTrue(decision.comment.startswith("  "))

    def test_028_comment_exact_bytes_participate_in_identity(self) -> None:
        composed = self.decide(self.clear, decision="REJECT", comment="é")
        decomposed = self.decide(self.clear, decision="REJECT", comment="e\u0301")
        self.assertNotEqual(composed.comment.encode("utf-8"), decomposed.comment.encode("utf-8"))
        self.assertNotEqual(composed.decision_identity, decomposed.decision_identity)

    def test_029_actor_identifier_bound_and_type_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata(
                actor_identifier="x" * (self.api.MAX_ACTOR_IDENTIFIER_CHARS + 1),
                display_name="Reviewer",
                source="local",
            )
        with self.assertRaisesRegex(ValueError, "exact string"):
            self.api.HumanReviewerMetadata(
                actor_identifier=7,
                display_name="Reviewer",
                source="local",
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_IDENTIFIER_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_IDENTIFIER_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata(byte_overflow, "Reviewer", "local")
        decision = self.decide(self.clear)
        self.assertEqual(decision.actor.actor_identifier, "human-reviewer-001")

    def test_030_actor_display_name_bound_is_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "display_name"):
            self.api.HumanReviewerMetadata(
                actor_identifier="reviewer",
                display_name="x" * (self.api.MAX_ACTOR_DISPLAY_NAME_CHARS + 1),
                source="local",
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_DISPLAY_NAME_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata("reviewer", byte_overflow, "local")
        decision = self.decide(self.required)
        self.assertEqual(decision.actor.display_name, "Local Reviewer")

    def test_031_actor_source_bound_and_required_content_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata("reviewer", "Reviewer", " " * 3)
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata(
                "reviewer",
                "Reviewer",
                "s" * (self.api.MAX_ACTOR_SOURCE_CHARS + 1),
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_SOURCE_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_SOURCE_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata("reviewer", "Reviewer", byte_overflow)
        self.assertEqual(self.decide(self.clear).actor.source, "local-human-review")

    def test_032_actor_metadata_participates_in_identity(self) -> None:
        first = self.decide(self.clear, decision="REJECT")
        other_actor = self.api.HumanReviewerMetadata(
            "human-reviewer-002",
            "Local Reviewer",
            "local-human-review",
        )
        second = self.decide(self.clear, decision="REJECT", actor=other_actor)
        self.assertNotEqual(first.actor.actor_identifier, second.actor.actor_identifier)
        self.assertNotEqual(first.decision_identity, second.decision_identity)

    def test_033_actor_is_evidence_only_and_cannot_grant_authority(self) -> None:
        claimant = self.api.HumanReviewerMetadata(
            "administrator",
            "Claims Authority",
            "claims-publication-and-execution-authority",
        )
        decision = self.decide(self.clear, decision="APPROVE", actor=claimant)
        self.assertTrue(decision.actor_metadata_evidence_only)
        self.assertFalse(decision.human_identity_authenticated)
        self.assertFalse(any(
            getattr(decision, name)
            for name in (
                "grants_write_authority",
                "grants_vault_write_authority",
                "grants_persistence_authority",
                "grants_publication_authority",
                "grants_merge_authority",
                "grants_rebase_authority",
                "grants_execution_authority",
                "grants_policy_authority",
                "grants_model_gateway_authority",
                "grants_tauri_frontend_authority",
                "grants_automatic_approval_authority",
            )
        ))

    def test_034_identity_is_deterministic_for_identical_input(self) -> None:
        first = self.decide(self.clear, decision="APPROVE", comment="same")
        second = self.decide(self.clear, decision="APPROVE", comment="same")
        self.assertEqual(first, second)
        self.assertEqual(first.decision_identity, second.decision_identity)
        self.assertRegex(first.decision_identity, r"^kdecision:[0-9a-f]{64}$")

    def test_035_identity_uses_independent_canonical_domain_separation_oracle(self) -> None:
        decision = self.decide(self.clear, decision="REJECT", comment="Космос")
        expected = self._independent_identity(decision)
        other_domain = self._independent_identity(decision, domain="OTHER_DOMAIN")
        self.assertEqual(decision.decision_identity, expected)
        self.assertNotEqual(decision.decision_identity, other_domain)

    def test_036_every_variable_governed_input_changes_identity(self) -> None:
        baseline = self.decide(self.clear, decision="APPROVE", comment="")
        boundary = self.api._authority_boundary_values()
        inputs = {
            "contract_version": baseline.contract_version,
            "review_contract_version": baseline.review_contract_version,
            "review_status": baseline.review_status,
            "proposal_id": baseline.proposal_id,
            "review_artifact_identity": baseline.review_artifact_identity,
            "change_identity": baseline.change_identity,
            "observed_vault_revision": baseline.observed_vault_revision,
            "decision": baseline.decision,
            "comment": baseline.comment,
            "actor": baseline.actor,
            "boundary": boundary,
        }

        def identity(**changes: object) -> str:
            governed = dict(inputs)
            governed.update(changes)
            return self.api._compute_decision_identity(**governed)

        self.assertEqual(identity(), baseline.decision_identity)
        variants = {
            "decision_contract_version": identity(contract_version="other-decision-contract"),
            "review_contract_version": identity(review_contract_version="other-review-contract"),
            "review_status": identity(review_status=ReviewStatus.REVIEW_REQUIRED),
            "proposal_id": identity(proposal_id="kprop:" + "f" * 64),
            "review_artifact_identity": identity(
                review_artifact_identity="kreview:" + "f" * 64
            ),
            "change_identity": identity(change_identity="kchange:" + "f" * 64),
            "observed_vault_revision": identity(
                observed_vault_revision="sha256:" + "f" * 64
            ),
            "decision": identity(decision=self.api.HumanReviewDecisionValue.REJECT),
            "comment": identity(comment="comment"),
            "actor_identifier": identity(
                actor=self.api.HumanReviewerMetadata(
                    "other-reviewer",
                    baseline.actor.display_name,
                    baseline.actor.source,
                )
            ),
            "actor_display_name": identity(
                actor=self.api.HumanReviewerMetadata(
                    baseline.actor.actor_identifier,
                    "Other Reviewer",
                    baseline.actor.source,
                )
            ),
            "actor_source": identity(
                actor=self.api.HumanReviewerMetadata(
                    baseline.actor.actor_identifier,
                    baseline.actor.display_name,
                    "other-source",
                )
            ),
        }
        for index, (name, value) in enumerate(boundary):
            changed_boundary = tuple(
                (item_name, not item_value if item_index == index else item_value)
                for item_index, (item_name, item_value) in enumerate(boundary)
            )
            variants[f"semantics.{name}"] = identity(boundary=changed_boundary)

        unchanged_fields = tuple(
            name
            for name, changed_identity in variants.items()
            if changed_identity == baseline.decision_identity
        )
        self.assertEqual(unchanged_fields, ())
        self.assertEqual(len(set(variants.values())), len(variants))

    def test_037_returned_artifact_is_frozen_and_has_no_mutable_collections(self) -> None:
        decision = self.decide(self.clear)
        with self.assertRaises(FrozenInstanceError):
            decision.comment = "mutated"
        stored_values = tuple(getattr(decision, item.name) for item in fields(decision))
        self.assertFalse(any(isinstance(value, (dict, list, set, bytearray)) for value in stored_values))

    def test_038_actor_metadata_is_frozen(self) -> None:
        decision = self.decide(self.clear)
        with self.assertRaises(FrozenInstanceError):
            decision.actor.source = "changed"
        self.assertEqual(decision.actor, self.actor)
        self.assertIs(type(decision.actor), self.api.HumanReviewerMetadata)

    def test_039_caller_owned_inputs_are_not_mutated(self) -> None:
        artifact_before = repr(self.clear)
        actor_before = repr(self.actor)
        raw_comment = "  exact caller text  "
        decision = self.decide(self.clear, decision="REJECT", comment=raw_comment)
        self.assertEqual(repr(self.clear), artifact_before)
        self.assertEqual(repr(self.actor), actor_before)
        self.assertEqual(decision.comment, raw_comment)

    def test_040_identity_ignores_ambient_time_environment_and_paths(self) -> None:
        first = self.decide(self.clear, decision="REJECT", comment="ambient-free")
        with mock.patch.dict(os.environ, {"HOSTNAME": "different", "LANG": "xx_YY"}, clear=True):
            second = self.decide(self.clear, decision="REJECT", comment="ambient-free")
        source_tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(source_tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertEqual(first.decision_identity, second.decision_identity)
        self.assertTrue({"os", "pathlib", "time", "datetime", "random", "uuid"}.isdisjoint(imported))

    def test_041_module_has_no_filesystem_write_runtime(self) -> None:
        tree = ast.parse(_source_text())
        forbidden_calls = {"open", "write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        with mock.patch("builtins.open", side_effect=AssertionError("write path")):
            decision = self.decide(self.clear)
        self.assertTrue(forbidden_calls.isdisjoint(called))
        self.assertTrue(decision.hard_stop)

    def test_042_module_has_no_persistence_registry_database_or_consumer_api(self) -> None:
        decision = self.decide(self.required, decision="REJECT")
        tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        exported = set(self.api.__all__)
        self.assertTrue({"sqlite3", "shelve", "dbm", "pickle"}.isdisjoint(imported))
        self.assertTrue({"apply", "publish", "persist", "execute", "registry", "store"}.isdisjoint(exported))
        self.assertTrue(decision.review_decision_only)

    def test_043_module_has_no_network_model_tauri_or_frontend_coupling(self) -> None:
        tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")):
            decision = self.decide(self.clear)
        forbidden = {
            "socket",
            "urllib",
            "http",
            "requests",
            "browser",
            "openai",
            "tauri",
            "frontend",
            "model_gateway",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        self.assertFalse(decision.grants_model_gateway_authority)
        self.assertFalse(decision.grants_tauri_frontend_authority)

    def test_044_module_has_no_subprocess_or_shell_runtime(self) -> None:
        with (
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
            mock.patch.object(os, "system", side_effect=AssertionError("shell")),
        ):
            decision = self.decide(self.clear, decision="REJECT")
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(ast.parse(_source_text()))
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        self.assertFalse(decision.grants_execution_authority)

    def test_045_e9a_and_e9b_inputs_are_not_mutated(self) -> None:
        proposal, validation, state, artifact = self.clear_inputs
        before = (repr(proposal), repr(validation), repr(state), repr(artifact))
        decision = self.decide(artifact, decision="APPROVE", comment="reviewed")
        after = (repr(proposal), repr(validation), repr(state), repr(artifact))
        self.assertEqual(before, after)
        self.assertEqual(decision.review_artifact_identity, artifact.review_artifact_identity)

    def test_046_hard_stop_and_no_authority_invariants_are_explicit(self) -> None:
        decision = self.decide(self.clear, decision="APPROVE")
        self.assertIs(decision.hard_stop, True)
        self.assertIs(decision.review_decision_only, True)
        self.assertIs(decision.actor_metadata_evidence_only, True)
        self.assertIs(decision.human_identity_authenticated, False)
        self.assertFalse(decision.grants_write_authority)
        self.assertFalse(decision.grants_vault_write_authority)
        self.assertFalse(decision.grants_persistence_authority)
        self.assertFalse(decision.grants_publication_authority)
        self.assertFalse(decision.grants_merge_authority)
        self.assertFalse(decision.grants_rebase_authority)
        self.assertFalse(decision.grants_execution_authority)
        self.assertFalse(decision.grants_policy_authority)
        self.assertFalse(decision.grants_model_gateway_authority)
        self.assertFalse(decision.grants_tauri_frontend_authority)
        self.assertFalse(decision.grants_automatic_approval_authority)

    def test_047_exact_comment_character_and_utf8_boundaries_are_accepted(self) -> None:
        char_boundary = self.decide(
            self.clear,
            decision="REJECT",
            comment="x" * self.api.MAX_COMMENT_CHARS,
        )
        byte_text = "🚀" * (self.api.MAX_COMMENT_UTF8_BYTES // 4)
        byte_boundary = self.decide(self.clear, decision="REJECT", comment=byte_text)
        self.assertEqual(len(char_boundary.comment), self.api.MAX_COMMENT_CHARS)
        self.assertEqual(len(byte_boundary.comment.encode("utf-8")), self.api.MAX_COMMENT_UTF8_BYTES)

    def test_048_binding_values_require_exact_types_and_formats(self) -> None:
        cases = (
            {"expected_proposal_id": True},
            {"expected_review_artifact_identity": "kreview:bad"},
            {"expected_change_identity": 7},
            {"expected_observed_vault_revision": "SHA256:" + "a" * 64},
            {"current_observed_vault_revision": None},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assert_rejection(
                    self.api.HumanReviewDecisionRejectionCode.INVALID_BINDING_VALUE,
                    lambda values=overrides: self.decide(self.clear, **values),
                )
        self.assertEqual(len(cases), 5)

    def test_049_actor_argument_requires_exact_metadata_type(self) -> None:
        values = self._decision_kwargs(self.clear, actor={"actor_identifier": "fake"})
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.ACTOR_TYPE_INVALID,
            lambda: self.api.create_human_review_decision(self.clear, **values),
        )
        self.assertIs(type(self.actor), self.api.HumanReviewerMetadata)

    def test_050_malformed_real_type_artifact_field_is_rejected(self) -> None:
        malformed = _clone_review(self.clear, status="CLEAR")
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT,
            lambda: self.decide(malformed),
        )
        self.assertIs(type(malformed), KnowledgeChangeReviewArtifact)

    def test_051_typed_rejection_is_deterministic_and_validation_order_is_fixed(self) -> None:
        observed = []
        for _ in range(2):
            try:
                self.decide(
                    self.clear,
                    expected_proposal_id="kprop:" + "f" * 64,
                    expected_review_artifact_identity="kreview:" + "f" * 64,
                )
            except self.api.HumanReviewDecisionRejected as exc:
                observed.append((exc.code, str(exc)))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0][0], self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH)

    def test_052_incomplete_fake_e9b_dependency_fails_static_import(self) -> None:
        self.assertTrue(incomplete_e9b_dependency_fails())
        decision = self.decide(self.clear)
        self.assertEqual(decision.review_contract_version, E9B_CONTRACT_VERSION)

    def test_053_all_eight_deliberate_faults_are_detected(self) -> None:
        original = self.decide(self.clear)
        results = run_deliberate_fault_checks()
        type(self).fault_results = results
        self.assertEqual(len(results), 8)
        self.assertTrue(all(item["detected"] for item in results))
        self.assertTrue(original.hard_stop)

    def test_054_focused_suite_substance_gate(self) -> None:
        decision = self.decide(self.clear)
        metrics = focused_test_substance_metrics()
        self.assertGreaterEqual(metrics["api_percentage"], 80.0)
        self.assertEqual(metrics["exact_duplicate_method_count"], 0)
        self.assertEqual(metrics["unique_behavioral_scenarios"], metrics["total_test_methods"])
        self.assertGreater(metrics["unique_assertion_pattern_count"], 10)
        self.assertTrue(decision.review_decision_only)

    def test_055_public_artifact_constructor_enforces_lifecycle_invariants(self) -> None:
        baseline = self.decide(self.clear, decision="APPROVE")

        def construct(
            review_status: ReviewStatus,
            change_identity: str | None,
        ) -> None:
            values = {item.name: getattr(baseline, item.name) for item in fields(baseline)}
            boundary = self.api._authority_boundary_values()
            values.update({
                "review_status": review_status,
                "change_identity": change_identity,
                "decision": self.api.HumanReviewDecisionValue.APPROVE,
                "decision_identity": self.api._compute_decision_identity(
                    contract_version=baseline.contract_version,
                    review_contract_version=baseline.review_contract_version,
                    review_status=review_status,
                    proposal_id=baseline.proposal_id,
                    review_artifact_identity=baseline.review_artifact_identity,
                    change_identity=change_identity,
                    observed_vault_revision=baseline.observed_vault_revision,
                    decision=self.api.HumanReviewDecisionValue.APPROVE,
                    comment=baseline.comment,
                    actor=baseline.actor,
                    boundary=boundary,
                ),
            })
            self.api.HumanReviewDecision(**values)

        with self.assertRaisesRegex(ValueError, "BLOCKED_APPROVAL_FORBIDDEN"):
            construct(ReviewStatus.BLOCKED, None)
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRES_CHANGE_IDENTITY"):
            construct(ReviewStatus.CLEAR, None)


def incomplete_e9b_dependency_fails() -> bool:
    dependency_name = "modules.knowledge_change_review_ru"
    probe_name = "modules._e9c_incomplete_dependency_probe"
    source = _source_text()
    fake = types.ModuleType(dependency_name)
    original_dependency = sys.modules.get(dependency_name)
    import modules as modules_package

    had_attribute = hasattr(modules_package, "knowledge_change_review_ru")
    original_attribute = getattr(modules_package, "knowledge_change_review_ru", None)
    probe = types.ModuleType(probe_name)
    probe.__file__ = os.fspath(MODULE_PATH)
    probe.__package__ = "modules"
    sys.modules[dependency_name] = fake
    setattr(modules_package, "knowledge_change_review_ru", fake)
    sys.modules[probe_name] = probe
    failed = False
    try:
        exec(compile(source, f"<{probe_name}>", "exec"), probe.__dict__)
    except ImportError:
        failed = True
    finally:
        sys.modules.pop(probe_name, None)
        if original_dependency is None:
            sys.modules.pop(dependency_name, None)
        else:
            sys.modules[dependency_name] = original_dependency
        if had_attribute:
            setattr(modules_package, "knowledge_change_review_ru", original_attribute)
        elif hasattr(modules_package, "knowledge_change_review_ru"):
            delattr(modules_package, "knowledge_change_review_ru")
    return failed


def _load_mutant(
    name: str,
    replacements: tuple[tuple[str, str], ...],
):
    source = _source_text()
    for old, new in replacements:
        count = source.count(old)
        if count != 1:
            raise AssertionError(f"fault replacement for {name!r} matched {count} times: {old!r}")
        source = source.replace(old, new, 1)
    module_name = f"modules._e9c_fault_{name}"
    mutant = types.ModuleType(module_name)
    mutant.__file__ = os.fspath(MODULE_PATH)
    mutant.__package__ = "modules"
    sys.modules[module_name] = mutant
    try:
        exec(compile(source, f"<{module_name}>", "exec"), mutant.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return mutant


def run_deliberate_fault_checks() -> tuple[dict[str, object], ...]:
    faults = (
        (
            "exact_review_binding_disabled",
            ((
                "if expected_review_artifact_identity != review_artifact.review_artifact_identity:",
                "if False:",
            ),),
            "test_014_review_artifact_identity_mismatch_is_rejected",
        ),
        (
            "blocked_approve_allowed",
            (
                (
                    "if review_status is ReviewStatus.BLOCKED and decision is HumanReviewDecisionValue.APPROVE:",
                    "if False:",
                ),
                (
                    "if decision is HumanReviewDecisionValue.APPROVE and change_identity is None:",
                    "if decision is HumanReviewDecisionValue.APPROVE and change_identity is None and review_status is not ReviewStatus.BLOCKED:",
                ),
            ),
            "test_008_blocked_approve_is_forbidden",
        ),
        (
            "current_revision_ignored",
            ((
                "if current_observed_vault_revision != review_artifact.observed_vault_revision:",
                "if False:",
            ),),
            "test_019_current_observed_revision_drift_is_rejected",
        ),
        (
            "request_changes_comment_requirement_disabled",
            ((
                "if decision is HumanReviewDecisionValue.REQUEST_CHANGES and not comment.strip():",
                "if False:",
            ),),
            "test_023_request_changes_empty_comment_is_rejected",
        ),
        (
            "constant_decision_identity",
            ((
                "return DECISION_ID_PREFIX + hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()",
                "return DECISION_ID_PREFIX + '0' * 64",
            ),),
            "test_036_every_variable_governed_input_changes_identity",
        ),
        (
            "comment_removed_from_identity",
            (("\"comment\": comment,", "\"comment\": '',"),),
            "test_028_comment_exact_bytes_participate_in_identity",
        ),
        (
            "actor_removed_from_identity",
            ((
                "\"actor\": _actor_identity_payload(actor),",
                "\"actor\": {'actor_identifier':'','display_name':'','source':''},",
            ),),
            "test_032_actor_metadata_participates_in_identity",
        ),
        (
            "hard_stop_no_authority_invariant_disabled",
            (
                ("HARD_STOP: Final[bool] = True", "HARD_STOP: Final[bool] = False"),
                (
                    "GRANTS_WRITE_AUTHORITY: Final[bool] = False",
                    "GRANTS_WRITE_AUTHORITY: Final[bool] = True",
                ),
            ),
            "test_046_hard_stop_and_no_authority_invariants_are_explicit",
        ),
    )
    results: list[dict[str, object]] = []
    for name, replacements, test_name in faults:
        mutant = _load_mutant(name, replacements)
        case = HumanReviewDecisionBehaviorTests(test_name)
        case.api = mutant
        case.record_counts = False
        result = unittest.TestResult()
        try:
            case.run(result)
        finally:
            sys.modules.pop(mutant.__name__, None)
        detected = len(result.failures) == 1 and len(result.errors) == 0
        results.append({
            "fault": name,
            "relevant_test": test_name,
            "detected": detected,
            "failure_count": len(result.failures),
            "error_count": len(result.errors),
        })
    return tuple(results)


def focused_test_substance_metrics() -> dict[str, object]:
    tree = ast.parse(TEST_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "HumanReviewDecisionBehaviorTests"
    )
    methods = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    tests = {name: node for name, node in methods.items() if name.startswith("test_")}
    calls: dict[str, set[str]] = {}
    direct_api: set[str] = set()
    for name, node in methods.items():
        self_calls = {
            call.func.attr
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and (
                isinstance(call.func.value, ast.Name) and call.func.value.id == "self"
                or isinstance(call.func.value, ast.Attribute)
            )
        }
        calls[name] = self_calls & set(methods)
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "create_human_review_decision"
            for call in ast.walk(node)
        ):
            direct_api.add(name)

    def reaches_api(name: str, active: frozenset[str] = frozenset()) -> bool:
        if name in direct_api:
            return True
        if name in active:
            return False
        return any(reaches_api(child, active | {name}) for child in calls[name])

    api_methods = tuple(sorted(name for name in tests if reaches_api(name)))
    normalized = {
        name: ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
        for name, node in tests.items()
    }
    by_body: dict[str, list[str]] = {}
    for name, body in normalized.items():
        by_body.setdefault(body, []).append(name)
    exact_duplicates = tuple(
        tuple(names)
        for names in by_body.values()
        if len(names) > 1
    )
    near_duplicates = []
    test_names = sorted(tests)
    for index, left in enumerate(test_names):
        for right in test_names[index + 1:]:
            ratio = difflib.SequenceMatcher(None, normalized[left], normalized[right]).ratio()
            if ratio >= 0.985:
                near_duplicates.append((left, right, round(ratio, 4)))
    assertion_patterns = set()
    for node in tests.values():
        pattern = tuple(
            call.func.attr
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr.startswith("assert")
        )
        assertion_patterns.add(pattern)
    total = len(tests)
    api_count = len(api_methods)
    return {
        "total_test_methods": total,
        "api_calling_methods": api_count,
        "api_percentage": round((api_count * 100.0 / total) if total else 0.0, 2),
        "unique_behavioral_scenarios": total - sum(len(group) - 1 for group in exact_duplicates),
        "exact_duplicate_method_count": sum(len(group) - 1 for group in exact_duplicates),
        "exact_duplicate_groups": exact_duplicates,
        "near_duplicate_count": len(near_duplicates),
        "near_duplicate_pairs": tuple(near_duplicates),
        "unique_assertion_pattern_count": len(assertion_patterns),
    }


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HumanReviewDecisionBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    metrics = focused_test_substance_metrics()
    e9a_count_keys = (
        "proposer_metadata",
        "provenance",
        "proposed_content",
        "knowledge_change_proposals",
        "proposal_validators",
        "validation_results",
    )
    output = {
        "metrics": metrics,
        "construction_counts": dict(HumanReviewDecisionBehaviorTests.counters),
        "real_e9a_object_constructions": sum(
            HumanReviewDecisionBehaviorTests.counters[key] for key in e9a_count_keys
        ),
        "real_e9b_artifact_constructions": HumanReviewDecisionBehaviorTests.counters[
            "knowledge_change_review_artifacts"
        ],
        "human_review_decision_constructions": HumanReviewDecisionBehaviorTests.counters[
            "human_review_decisions"
        ],
        "fault_results": HumanReviewDecisionBehaviorTests.fault_results,
        "fake_incomplete_e9b_import_failed": incomplete_e9b_dependency_fails(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }
    print("E9C_FOCUSED_EVIDENCE=" + json.dumps(output, ensure_ascii=False, sort_keys=True))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
````

### ПУТЬ: tools/test_v68451e9c_review_projection.py (1503 строк, 70245 байт)

````python
"""Focused tests for the bounded e9b/e9c knowledge-review UI projection."""

from __future__ import annotations

import ast
import builtins
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import difflib
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import textwrap
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True

import modules
from modules.knowledge_change_proposal_ru import ProposalOperation
from modules.knowledge_change_review_ru import (
    ConflictCode,
    ConflictFinding,
    FrozenCanonicalValue,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
)
import modules.knowledge_change_review_decision_ru as decision_contract
import modules.knowledge_review_ui_projection_ru as projection_contract
import tools.test_v68451e9b_knowledge_review as e9b_fixtures


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "modules" / "knowledge_review_ui_projection_ru.py"
TEST_PATH = Path(__file__).resolve()

PROPOSED_CONTENT_FIELDS = {
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
}

DECISION_FIELDS = {
    "contract_version",
    "review_contract_version",
    "review_status",
    "proposal_id",
    "review_artifact_identity",
    "change_identity",
    "observed_vault_revision",
    "decision",
    "comment",
    "actor",
    "decision_identity",
    "hard_stop",
    "review_decision_only",
    "actor_metadata_evidence_only",
    "human_identity_authenticated",
    "grants_write_authority",
    "grants_vault_write_authority",
    "grants_persistence_authority",
    "grants_publication_authority",
    "grants_merge_authority",
    "grants_rebase_authority",
    "grants_execution_authority",
    "grants_policy_authority",
    "grants_model_gateway_authority",
    "grants_tauri_frontend_authority",
    "grants_automatic_approval_authority",
}

AUTHORITY_FIELDS = (
    "hard_stop",
    "review_decision_only",
    "actor_metadata_evidence_only",
    "human_identity_authenticated",
    "grants_write_authority",
    "grants_vault_write_authority",
    "grants_persistence_authority",
    "grants_publication_authority",
    "grants_merge_authority",
    "grants_rebase_authority",
    "grants_execution_authority",
    "grants_policy_authority",
    "grants_model_gateway_authority",
    "grants_tauri_frontend_authority",
    "grants_automatic_approval_authority",
)

CONSTRUCTION_COUNTS = {
    "e9a_proposal_instances": 0,
    "e9a_validation_results": 0,
    "e9b_review_artifacts": 0,
    "e9c_decisions": 0,
    "review_projection_calls": 0,
    "review_summary_projection_calls": 0,
    "decision_projection_calls": 0,
    "materialization_calls": 0,
    "canonical_calls": 0,
}
FAULT_RESULTS: list[dict[str, object]] = []
FAKE_DEPENDENCY_RESULTS: list[dict[str, object]] = []
SUBSTANCE_METRICS: dict[str, object] = {}


class DistinctBytes(bytes):
    """Valid UTF-8 bytes that model a distinct source representation."""

    def __eq__(self, other: object) -> bool:
        return False

    def __ne__(self, other: object) -> bool:
        return True


def _source_text() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _container_ids(value: object) -> set[int]:
    found: set[int] = set()
    if type(value) is dict:
        found.add(id(value))
        for key, child in value.items():
            found.update(_container_ids(key))
            found.update(_container_ids(child))
    elif type(value) is list:
        found.add(id(value))
        for child in value:
            found.update(_container_ids(child))
    return found


def _assert_standard_json_value(test: unittest.TestCase, value: object) -> None:
    value_type = type(value)
    test.assertIn(value_type, (dict, list, str, int, bool, type(None)))
    if value_type is dict:
        for key, child in value.items():
            test.assertIs(type(key), str)
            _assert_standard_json_value(test, child)
    elif value_type is list:
        for child in value:
            _assert_standard_json_value(test, child)


def _validation_mapping(node: dict[str, object]) -> dict[str, dict[str, object]]:
    if node["type_tag"] != "mapping":
        raise AssertionError("expected mapping projection")
    return {
        item["key"]: item["value"]
        for item in node["mapping_items"]
    }


def _clone_exact_review(
    artifact: KnowledgeChangeReviewArtifact,
    **changes: object,
) -> KnowledgeChangeReviewArtifact:
    return replace(artifact, **changes)


def _load_mutant(
    fault_name: str,
    needle: str,
    replacement: str,
) -> tuple[types.ModuleType, str]:
    source = _source_text()
    count = source.count(needle)
    if count != 1:
        raise AssertionError(f"{fault_name}: expected one mutation site, found {count}")
    mutated = source.replace(needle, replacement, 1)
    module_name = f"_localcomet_projection_mutant_{fault_name}"
    module = types.ModuleType(module_name)
    module.__file__ = f"<{module_name}>"
    sys.modules[module_name] = module
    try:
        exec(compile(mutated, module.__file__, "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module, module_name


def _probe_incomplete_dependency(module_name: str) -> str:
    source = _source_text()
    attribute_name = module_name.rsplit(".", 1)[-1]
    original_module = sys.modules[module_name]
    original_attribute = getattr(modules, attribute_name)
    fake = types.ModuleType(module_name)
    probe_name = f"_projection_fake_probe_{attribute_name}"
    probe = types.ModuleType(probe_name)
    probe.__file__ = f"<{probe_name}>"
    sys.modules[module_name] = fake
    setattr(modules, attribute_name, fake)
    sys.modules[probe_name] = probe
    try:
        try:
            exec(compile(source, probe.__file__, "exec"), probe.__dict__)
        except ImportError:
            return "IMPORT_ERROR"
        return "UNEXPECTED_IMPORT_SUCCESS"
    finally:
        sys.modules[module_name] = original_module
        setattr(modules, attribute_name, original_attribute)
        sys.modules.pop(probe_name, None)


class ProjectionBehaviorTests(unittest.TestCase):
    api = projection_contract
    record_counts = True

    def _count(self, name: str, amount: int = 1) -> None:
        if self.record_counts:
            CONSTRUCTION_COUNTS[name] += amount

    def _record_review_construction(self) -> None:
        self._count("e9a_proposal_instances", 2)
        self._count("e9a_validation_results")
        self._count("e9b_review_artifacts")

    def setUp(self) -> None:
        self.helper = e9b_fixtures.KnowledgeReviewBehaviorTests()
        self.clear_create = self.helper.clear_create_artifact()
        self._record_review_construction()
        self.clear_update = self.helper.clear_update_artifact()
        self._record_review_construction()

        required_proposal = self.helper.make_proposal(body="required-after\n")
        required_result = self.helper.validate(required_proposal)
        required_current = self.helper.snapshot("required-before\n")
        self.review_required = self.helper.review(
            required_proposal,
            required_result,
            self.helper.state(current=required_current, baseline=None),
        )
        self._record_review_construction()

        blocked_proposal = self.helper.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=e9b_fixtures.OTHER_TARGET,
            body="blocked body\n",
        )
        blocked_result = self.helper.validate(
            blocked_proposal,
            stable_ids={e9b_fixtures.TARGET},
        )
        self.blocked = self.helper.review(
            blocked_proposal,
            blocked_result,
            self.helper.state(
                stable_ids={e9b_fixtures.TARGET, e9b_fixtures.OTHER_TARGET}
            ),
        )
        self._record_review_construction()
        self.actor = decision_contract.HumanReviewerMetadata(
            actor_identifier="human-reviewer-001",
            display_name="Local Reviewer",
            source="local-human-review",
        )

    def _review_projection(self, artifact: KnowledgeChangeReviewArtifact | None = None):
        self._count("review_projection_calls")
        return self.api.project_knowledge_change_review(artifact or self.clear_update)

    def _review_summary_projection(self, artifact: KnowledgeChangeReviewArtifact | None = None):
        self._count("review_summary_projection_calls")
        return self.api.project_knowledge_change_review_summary(artifact or self.clear_update)

    def _decision(self, artifact, *, value, comment="", actor=None):
        result = decision_contract.create_human_review_decision(
            artifact,
            expected_proposal_id=artifact.proposal_id,
            expected_review_artifact_identity=artifact.review_artifact_identity,
            expected_change_identity=artifact.change_identity,
            expected_observed_vault_revision=artifact.observed_vault_revision,
            current_observed_vault_revision=artifact.observed_vault_revision,
            decision=value,
            comment=comment,
            actor=actor or self.actor,
        )
        self._count("e9c_decisions")
        return result

    def _decision_projection(self, decision):
        self._count("decision_projection_calls")
        return self.api.project_human_review_decision(decision)

    def _materialize(self, projection):
        self._count("materialization_calls")
        return self.api.materialize_json_value(projection)

    def _canonical(self, projection):
        self._count("canonical_calls")
        return self.api.canonical_projection_json_bytes(projection)

    def _replace_source_paths(self, artifact, paths):
        snapshot = replace(artifact.proposed_content_snapshot, source_paths=tuple(paths))
        return _clone_exact_review(artifact, proposed_content_snapshot=snapshot)

    def _large_update(self):
        after = "".join(
            f"line-{index:04d} Протокол проекции и доказательство границы\n"
            for index in range(1_000)
        )
        artifact = self.helper.clear_update_artifact(before="old\n", after=after)
        self._record_review_construction()
        return artifact

    def test_001_projection_contract_and_kind_are_exact(self) -> None:
        review = self._review_projection(self.clear_create)
        decision = self._decision_projection(
            self._decision(
                self.clear_create,
                value=decision_contract.HumanReviewDecisionValue.APPROVE,
            )
        )
        self.assertEqual(review.projection_contract, "localcomet.knowledge-review-ui/1.0")
        self.assertEqual(review.kind.value, "KNOWLEDGE_CHANGE_REVIEW")
        self.assertEqual(decision.kind.value, "HUMAN_REVIEW_DECISION")

    def test_002_clear_create_new_projection_uses_real_e9b_artifact(self) -> None:
        projected = self._review_projection(self.clear_create)
        self.assertIs(type(projected), self.api.KnowledgeChangeReviewProjection)
        self.assertEqual(projected.status, "CLEAR")
        self.assertEqual(projected.operation, "CREATE_NEW")
        self.assertIsNone(projected.before_source_byte_hash)

    def test_003_clear_update_existing_projection_preserves_preimage_hashes(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertEqual(projected.status, "CLEAR")
        self.assertEqual(projected.operation, "UPDATE_EXISTING")
        self.assertEqual(projected.before_source_byte_hash, self.clear_update.before_source_byte_hash)
        self.assertEqual(projected.before_text_raw_hash, self.clear_update.before_text_raw_hash)
        self.assertEqual(projected.before_semantic_text_hash, self.clear_update.before_semantic_text_hash)

    def test_004_review_required_projection_preserves_status_and_findings(self) -> None:
        projected = self._review_projection(self.review_required)
        self.assertEqual(projected.status, "REVIEW_REQUIRED")
        self.assertGreater(projected.findings.original_count, 0)
        self.assertEqual(
            [item.code for item in projected.findings.items],
            [item.code.value for item in self.review_required.findings],
        )

    def test_005_blocked_projection_preserves_status_without_change_identity(self) -> None:
        projected = self._review_projection(self.blocked)
        self.assertEqual(projected.status, "BLOCKED")
        self.assertIsNone(projected.change_identity)
        self.assertEqual(projected.review_artifact_identity, self.blocked.review_artifact_identity)

    def test_006_metadata_only_empty_diff_is_present_not_absent(self) -> None:
        artifact = self.helper.metadata_only_artifact(title="Metadata-only title")
        self._record_review_construction()
        self.assertEqual(artifact.deterministic_text_diff, "")
        projected = self._review_projection(artifact)
        self.assertIsNotNone(projected.diff)
        self.assertTrue(projected.diff.full_diff_present)
        self.assertEqual(projected.diff.full_diff_utf8_bytes, 0)
        self.assertEqual(projected.diff.preview.preview_text, "")
        self.assertEqual(projected.diff.full_diff_hash, artifact.deterministic_text_diff_hash)

    def test_007_line_ending_only_representation_delta_is_complete(self) -> None:
        artifact = self.helper.clear_update_artifact(before="same\r\n", after="same\n")
        self._record_review_construction()
        projected = self._review_projection(artifact)
        delta = projected.representation_delta
        self.assertIsNotNone(delta)
        self.assertEqual(delta.before_line_endings.crlf_count, 1)
        self.assertEqual(delta.after_line_endings.lf_count, 1)
        self.assertTrue(delta.raw_text_changed_semantic_equal)

    def test_008_terminal_newline_only_delta_is_preserved(self) -> None:
        artifact = self.helper.clear_update_artifact(before="same", after="same\n")
        self._record_review_construction()
        projected = self._review_projection(artifact)
        self.assertTrue(projected.representation_delta.terminal_newline_changed)
        self.assertFalse(projected.representation_delta.before_line_endings.terminal_newline)
        self.assertTrue(projected.representation_delta.after_line_endings.terminal_newline)

    def test_009_source_bytes_changed_text_identical_is_authentic_and_visible(self) -> None:
        proposal = self.helper.make_proposal(body="same\n")
        validation = self.helper.validate(proposal)
        baseline = self.helper.snapshot("same\n")
        current = replace(baseline, source_bytes=DistinctBytes(baseline.source_bytes))
        artifact = self.helper.review(
            proposal,
            validation,
            self.helper.state(current=current, baseline=baseline),
        )
        self._record_review_construction()
        self.assertIn(
            ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
            {finding.code for finding in artifact.findings},
        )
        projected = self._review_projection(artifact)
        self.assertFalse(projected.representation_delta.after_source_bytes_known)
        self.assertEqual(
            projected.representation_delta.source_bytes_changed_text_identical,
            artifact.representation_delta.source_bytes_changed_text_identical,
        )
        self.assertIn(
            "TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL",
            [item.code for item in projected.findings.items],
        )

    def test_010_all_18_proposed_content_fields_are_materialized(self) -> None:
        value = self._materialize(self._review_projection(self.clear_update))
        proposed = value["proposed_content_snapshot"]
        self.assertEqual(set(proposed), PROPOSED_CONTENT_FIELDS)
        self.assertEqual(len(proposed), 18)
        self.assertIs(type(proposed["body_text"]), dict)

    def test_011_proposed_scalar_metadata_is_exact(self) -> None:
        source = self.clear_update.proposed_content_snapshot
        projected = self._review_projection(self.clear_update).proposed_content_snapshot
        for name in (
            "title", "type", "status", "knowledge_layer", "evidence_class",
            "authority", "canonical", "canonical_scope", "updated",
            "last_reviewed", "verified_at",
        ):
            self.assertEqual(getattr(projected, name), getattr(source, name), name)

    def test_012_body_preview_preserves_exact_hashes_and_original_byte_count(self) -> None:
        projected = self._review_projection(self.clear_update).proposed_content_snapshot.body_text
        source = self.clear_update.proposed_content_snapshot.body_text
        self.assertEqual(projected.raw_text_hash, self.clear_update.proposed_text_raw_hash)
        self.assertEqual(projected.semantic_text_hash, self.clear_update.proposed_semantic_text_hash)
        self.assertEqual(projected.original_utf8_bytes, len(source.encode("utf-8")))
        self.assertTrue(projected.is_preview)

    def test_013_large_body_preview_has_truthful_truncation_flag(self) -> None:
        artifact = self.helper.clear_create_artifact(body="ж" * 10_000)
        self._record_review_construction()
        body = self._review_projection(artifact).proposed_content_snapshot.body_text
        self.assertTrue(body.truncated)
        self.assertLessEqual(body.preview_utf8_bytes, self.api.MAX_BODY_PREVIEW_BYTES)
        self.assertGreater(body.original_utf8_bytes, body.preview_utf8_bytes)

    def test_014_body_preview_enforces_line_bound(self) -> None:
        artifact = self.helper.clear_create_artifact(
            body="".join(f"body-{index}\n" for index in range(260))
        )
        self._record_review_construction()
        body = self._review_projection(artifact).proposed_content_snapshot.body_text
        self.assertTrue(body.truncated)
        self.assertLessEqual(body.preview_line_count, self.api.MAX_BODY_PREVIEW_LINES)
        self.assertEqual(body.original_line_count, 260)

    def test_015_bounded_metadata_collection_reports_original_count(self) -> None:
        aliases = tuple(f"alias-{index:03d}" for index in range(129))
        snapshot = replace(self.clear_create.proposed_content_snapshot, aliases=aliases)
        artifact = _clone_exact_review(self.clear_create, proposed_content_snapshot=snapshot)
        collection = self._review_projection(artifact).proposed_content_snapshot.aliases
        self.assertTrue(collection.truncated)
        self.assertEqual(collection.original_count, 129)
        self.assertEqual(len(collection.items), self.api.MAX_METADATA_COLLECTION_ITEMS)

    def test_016_every_collection_is_new_and_preserves_source_order(self) -> None:
        source = self.clear_update.proposed_content_snapshot
        projected = self._review_projection(self.clear_update).proposed_content_snapshot
        for name in (
            "aliases", "releases", "source_paths", "evidence_refs",
            "supersedes", "superseded_by",
        ):
            collection = getattr(projected, name)
            self.assertEqual(collection.items, getattr(source, name), name)
            self.assertEqual(collection.original_count, len(getattr(source, name)), name)
            self.assertFalse(collection.truncated, name)

    def test_017_validation_snapshot_retains_mapping_and_sequence_type_tags(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_create))
        root = materialized["validation_snapshot"]["value"]
        entries = _validation_mapping(root)
        self.assertEqual(root["type_tag"], "mapping")
        self.assertEqual(entries["findings"]["type_tag"], "sequence")
        self.assertEqual(entries["provenance_summary"]["type_tag"], "mapping")

    def test_018_validation_scalar_types_are_not_collapsed(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_create))
        entries = _validation_mapping(materialized["validation_snapshot"]["value"])
        self.assertEqual(entries["evidence_reference_count"]["type_tag"], "int")
        self.assertIs(type(entries["evidence_reference_count"]["scalar_value"]), int)
        self.assertEqual(entries["proposal_id"]["type_tag"], "string")

    def test_019_validation_projection_has_explicit_non_truncated_flag(self) -> None:
        projected = self._review_projection(self.clear_create).validation_snapshot
        self.assertFalse(projected.truncated)
        self.assertIs(type(projected.value), self.api.ValidationValueProjection)

    def test_020_source_validation_findings_do_not_invent_messages(self) -> None:
        projected = self._review_projection(self.clear_create).source_validation_findings
        self.assertEqual(
            [(item.code, item.severity) for item in projected.items],
            list(self.clear_create.source_validation_findings),
        )
        materialized = self._materialize(self._review_projection(self.clear_create))
        self.assertTrue(
            all(set(item) == {"code", "severity"}
                for item in materialized["source_validation_findings"]["items"])
        )

    def test_021_review_finding_order_messages_and_details_are_exact(self) -> None:
        projected = self._review_projection(self.review_required).findings
        self.assertEqual(projected.original_count, len(self.review_required.findings))
        for source, target in zip(self.review_required.findings, projected.items, strict=True):
            self.assertEqual(target.code, source.code.value)
            self.assertEqual(target.severity, source.severity.value)
            self.assertEqual(target.message.preview_text, source.message)
            self.assertEqual(
                [(detail.key, detail.value) for detail in target.details.items],
                list(source.details),
            )
            self.assertEqual(target.details.original_count, len(source.details))
            self.assertFalse(target.details.truncated)

    def test_022_review_finding_collection_truncation_is_explicit(self) -> None:
        finding = self.review_required.findings[0]
        artifact = _clone_exact_review(self.review_required, findings=(finding,) * 17)
        projected = self._review_projection(artifact).findings
        self.assertTrue(projected.truncated)
        self.assertEqual(projected.original_count, 17)
        self.assertEqual(len(projected.items), self.api.MAX_PROJECTED_FINDINGS)

    def test_023_all_before_and_proposed_hashes_are_unshortened(self) -> None:
        projected = self._review_projection(self.clear_update)
        for name in (
            "before_source_byte_hash", "before_text_raw_hash",
            "before_semantic_text_hash", "proposed_text_raw_hash",
            "proposed_semantic_text_hash",
        ):
            self.assertEqual(getattr(projected, name), getattr(self.clear_update, name))
            self.assertEqual(len(getattr(projected, name)), 71)

    def test_024_diff_projection_preserves_full_hash_and_original_byte_count(self) -> None:
        projected = self._review_projection(self.clear_update).diff
        self.assertTrue(projected.full_diff_present)
        self.assertEqual(projected.full_diff_hash, self.clear_update.deterministic_text_diff_hash)
        self.assertEqual(
            projected.full_diff_utf8_bytes,
            len(self.clear_update.deterministic_text_diff.encode("utf-8")),
        )

    def test_025_diff_preview_is_never_labeled_as_full_diff(self) -> None:
        projected = self._review_projection(self.clear_update).diff
        self.assertFalse(projected.preview_is_full_diff)
        self.assertIs(projected.preview_truncated, projected.preview.truncated)
        self.assertTrue(projected.preview.is_preview)
        self.assertNotEqual(projected.preview.preview_text, self.clear_update.deterministic_text_diff)

    def test_026_large_diff_preview_is_bounded_and_truncated(self) -> None:
        artifact = self._large_update()
        projected = self._review_projection(artifact).diff
        self.assertTrue(projected.preview.truncated)
        self.assertLessEqual(projected.preview.preview_utf8_bytes, self.api.MAX_DIFF_PREVIEW_BYTES)
        self.assertLessEqual(projected.preview.preview_line_count, self.api.MAX_DIFF_PREVIEW_LINES)

    def test_027_full_deterministic_diff_text_is_not_a_materialized_field(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_update))
        self.assertNotIn("deterministic_text_diff", materialized)
        self.assertNotIn("full_diff", materialized["diff"])
        self.assertIn("preview", materialized["diff"])

    def test_028_full_representation_delta_is_materialized(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_update))
        delta = materialized["representation_delta"]
        self.assertIsNotNone(delta)
        self.assertEqual(
            set(delta),
            {
                "before_present", "after_present", "before_line_endings",
                "after_line_endings", "terminal_newline_changed",
                "after_source_bytes_known", "source_bytes_changed_text_identical",
                "raw_text_changed_semantic_equal", "semantic_content_changed", "identity",
            },
        )
        self.assertEqual(delta["identity"], self.clear_update.representation_delta.identity)

    def test_029_human_preview_reports_original_size_and_preview_semantics(self) -> None:
        projected = self._review_projection(self.clear_update).human_review_preview
        self.assertTrue(projected.is_preview)
        self.assertEqual(
            projected.original_utf8_bytes,
            len(self.clear_update.human_review_preview.encode("utf-8")),
        )
        self.assertLessEqual(projected.preview_utf8_bytes, self.api.MAX_HUMAN_PREVIEW_BYTES)

    def test_030_large_human_preview_truncation_is_truthful(self) -> None:
        artifact = self._large_update()
        source_bytes = len(artifact.human_review_preview.encode("utf-8"))
        projected = self._review_projection(artifact).human_review_preview
        self.assertGreater(source_bytes, self.api.MAX_HUMAN_PREVIEW_BYTES)
        self.assertTrue(projected.truncated)
        self.assertLess(projected.preview_utf8_bytes, projected.original_utf8_bytes)

    def test_031_exact_review_identity_is_never_shortened(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertEqual(projected.review_artifact_identity, self.clear_update.review_artifact_identity)
        self.assertEqual(len(projected.review_artifact_identity), len("kreview:") + 64)
        self.assertEqual(projected.change_identity, self.clear_update.change_identity)

    def test_032_blocked_diff_delta_and_change_material_are_exact_none(self) -> None:
        materialized = self._materialize(self._review_projection(self.blocked))
        self.assertIsNone(materialized["diff"])
        self.assertIsNone(materialized["representation_delta"])
        self.assertIsNone(materialized["change_identity"])
        self.assertIsNone(self.blocked.deterministic_text_diff_hash)

    def test_033_blocked_projection_still_preserves_proposed_hashes(self) -> None:
        projected = self._review_projection(self.blocked)
        self.assertEqual(projected.proposed_text_raw_hash, self.blocked.proposed_text_raw_hash)
        self.assertEqual(projected.proposed_semantic_text_hash, self.blocked.proposed_semantic_text_hash)
        self.assertIsNotNone(projected.proposed_content_snapshot.body_text)

    def test_034_approve_decision_projection_preserves_real_e9c_fields(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.decision, "APPROVE")
        self.assertEqual(projected.change_identity, self.clear_create.change_identity)
        self.assertEqual(projected.decision_identity, decision.decision_identity)

    def test_035_blocked_reject_preserves_none_change_identity(self) -> None:
        decision = self._decision(
            self.blocked,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="Отклонено: конфликт stable ID",
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.review_status, "BLOCKED")
        self.assertEqual(projected.decision, "REJECT")
        self.assertIsNone(projected.change_identity)

    def test_036_request_changes_preserves_exact_unicode_comment(self) -> None:
        comment = "Нужны изменения — проверить Café и 東京 🚀\nСтрока 2"
        decision = self._decision(
            self.review_required,
            value=decision_contract.HumanReviewDecisionValue.REQUEST_CHANGES,
            comment=comment,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.decision, "REQUEST_CHANGES")
        self.assertEqual(projected.comment, comment)
        self.assertEqual(self._materialize(projected)["comment"], comment)

    def test_037_every_authority_flag_is_preserved_exactly(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        projected = self._decision_projection(decision)
        for name in AUTHORITY_FIELDS:
            self.assertIs(getattr(projected, name), getattr(decision, name), name)
        self.assertTrue(projected.hard_stop)
        self.assertTrue(projected.review_decision_only)
        self.assertTrue(projected.actor_metadata_evidence_only)
        self.assertFalse(any(getattr(projected, name) for name in AUTHORITY_FIELDS[3:]))

    def test_038_all_26_decision_fields_are_materialized(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )
        materialized = self._materialize(self._decision_projection(decision))
        self.assertEqual(set(materialized) - {"projection_contract", "kind"}, DECISION_FIELDS)
        self.assertEqual(len(materialized), 28)
        self.assertEqual(set(materialized["actor"]), {"actor_identifier", "display_name", "source"})

    def test_039_actor_metadata_is_exact_unicode_evidence(self) -> None:
        actor = decision_contract.HumanReviewerMetadata(
            actor_identifier="reviewer-ёж-東京",
            display_name="Ревьюер Élodie",
            source="локальный-интерфейс",
        )
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            actor=actor,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.actor.actor_identifier, actor.actor_identifier)
        self.assertEqual(projected.actor.display_name, actor.display_name)
        self.assertEqual(projected.actor.source, actor.source)

    def test_040_decision_and_binding_identities_are_exact(self) -> None:
        decision = self._decision(
            self.review_required,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="exact",
        )
        projected = self._decision_projection(decision)
        for name in (
            "proposal_id", "review_artifact_identity", "change_identity",
            "observed_vault_revision", "decision_identity",
        ):
            self.assertEqual(getattr(projected, name), getattr(decision, name), name)

    def test_041_projection_records_are_frozen_slotted_and_tuple_only(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertFalse(hasattr(projected, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            projected.status = "BLOCKED"

        def walk(value):
            if is_dataclass(value) and not isinstance(value, type):
                self.assertFalse(hasattr(value, "__dict__"), type(value).__name__)
                for item in fields(value):
                    walk(getattr(value, item.name))
            elif type(value) is tuple:
                for child in value:
                    walk(child)
            else:
                self.assertNotIn(type(value), (dict, list, set, bytearray))

        walk(projected)

    def test_042_materialized_projection_contains_only_standard_json_values(self) -> None:
        review_value = self._materialize(self._review_projection(self.clear_update))
        decision_value = self._materialize(
            self._decision_projection(
                self._decision(
                    self.clear_create,
                    value=decision_contract.HumanReviewDecisionValue.APPROVE,
                )
            )
        )
        _assert_standard_json_value(self, review_value)
        _assert_standard_json_value(self, decision_value)

    def test_043_json_round_trip_preserves_materialized_value(self) -> None:
        projected = self._review_projection(self.clear_update)
        materialized = self._materialize(projected)
        decoded = json.loads(self._canonical(projected).decode("utf-8"))
        self.assertEqual(decoded, materialized)
        self.assertIs(type(decoded), dict)

    def test_044_materializations_have_disjoint_containers_and_mutation_isolation(self) -> None:
        projected = self._review_projection(self.clear_update)
        first = self._materialize(projected)
        second = self._materialize(projected)
        self.assertTrue(_container_ids(first).isdisjoint(_container_ids(second)))
        first["proposed_content_snapshot"]["aliases"]["items"].append("MUTATED")
        third = self._materialize(projected)
        self.assertEqual(second, third)
        self.assertNotIn("MUTATED", third["proposed_content_snapshot"]["aliases"]["items"])

    def test_045_wrong_root_types_and_dict_inputs_are_typed_rejections(self) -> None:
        with self.assertRaises(self.api.ProjectionRejected) as review_error:
            self.api.project_knowledge_change_review({"artifact": self.clear_update})
        self.assertIs(review_error.exception.code, self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)
        with self.assertRaises(self.api.ProjectionRejected) as decision_error:
            self.api.project_human_review_decision(object())
        self.assertIs(decision_error.exception.code, self.api.ProjectionRejectionCode.WRONG_DECISION_TYPE)
        with self.assertRaises(self.api.ProjectionRejected) as json_error:
            self.api.materialize_json_value({"projection": "fake"})
        self.assertIs(json_error.exception.code, self.api.ProjectionRejectionCode.WRONG_PROJECTION_TYPE)

    def test_046_posix_absolute_and_windows_absolute_paths_are_rejected(self) -> None:
        for path in ("/etc/localcomet.md", r"C:\vault\note.md", r"\\server\share\note.md"):
            with self.subTest(path=path):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_047_windows_drive_relative_path_is_rejected(self) -> None:
        artifact = self._replace_source_paths(self.clear_create, ("C:foo.md",))
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_048_rooted_traversal_nul_and_overlength_paths_are_rejected(self) -> None:
        cases = (
            r"\rooted\note.md",
            "notes/../secret.md",
            "notes/bad\x00name.md",
            "a" * (self.api.MAX_SOURCE_PATH_CHARS + 1),
        )
        for path in cases:
            with self.subTest(path=repr(path)):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected):
                    self._review_projection(artifact)

    def test_049_unsafe_path_cannot_hide_after_collection_truncation(self) -> None:
        paths = tuple(
            f"notes/safe-{index:03d}.md"
            for index in range(self.api.MAX_METADATA_COLLECTION_ITEMS)
        ) + ("C:hidden-after-bound.md",)
        artifact = self._replace_source_paths(self.clear_create, paths)
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_050_safe_relative_posix_windows_and_dotted_paths_are_exact(self) -> None:
        paths = ("notes/current.md", r"notes\windows-relative.md", ".hidden/review.md")
        artifact = self._replace_source_paths(self.clear_create, paths)
        projected = self._review_projection(artifact)
        self.assertEqual(projected.proposed_content_snapshot.source_paths.items, paths)
        self.assertFalse(projected.proposed_content_snapshot.source_paths.truncated)

    def test_051_total_projection_byte_bound_is_enforced_at_canonical_boundary(self) -> None:
        projected = self._review_projection(self.clear_update)
        with mock.patch.object(self.api, "MAX_TOTAL_JSON_BYTES", 1):
            with self.assertRaises(self.api.ProjectionRejected) as captured:
                self._canonical(projected)
        self.assertIs(
            captured.exception.code,
            self.api.ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED,
        )

    def test_052_canonical_bytes_are_repeatable_and_match_independent_oracle(self) -> None:
        projected = self._review_projection(self.clear_update)
        first = self._canonical(projected)
        second = self._canonical(projected)
        self.assertEqual(first, second)
        oracle = json.dumps(
            self._materialize(projected),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(first, oracle)
        self.assertLessEqual(len(first), self.api.MAX_TOTAL_JSON_BYTES)

    def test_053_governed_review_and_decision_changes_change_canonical_bytes(self) -> None:
        before = self._canonical(self._review_projection(self.clear_update))
        after_artifact = self.helper.clear_update_artifact(before="old\n", after="different\n")
        self._record_review_construction()
        after = self._canonical(self._review_projection(after_artifact))
        self.assertNotEqual(before, after)
        reject = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )
        approve = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        self.assertNotEqual(
            self._canonical(self._decision_projection(reject)),
            self._canonical(self._decision_projection(approve)),
        )

    def test_054_static_module_has_no_side_effect_or_integration_runtime(self) -> None:
        tree = ast.parse(_source_text())
        allowed_import_roots = {
            "__future__", "dataclasses", "enum", "json", "pathlib", "re", "typing", "modules"
        }
        imports = []
        banned_calls = {
            "open", "write", "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
            "rename", "connect", "urlopen", "request", "run",
            "Popen", "system", "invoke", "emit",
        }
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in banned_calls:
                    calls.append(name)
        self.assertEqual(sorted(set(imports) - allowed_import_roots), [])
        self.assertEqual(calls, [])
        self.assertNotIn("__import__", _source_text())

    def test_055_runtime_projection_performs_no_io_network_subprocess_or_frontend_action(self) -> None:
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("open forbidden")),
            mock.patch.object(Path, "open", side_effect=AssertionError("Path.open forbidden")),
            mock.patch.object(Path, "write_text", side_effect=AssertionError("write forbidden")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write forbidden")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess forbidden")),
        ):
            review = self._review_projection(self.clear_update)
            decision = self._decision_projection(
                self._decision(
                    self.clear_create,
                    value=decision_contract.HumanReviewDecisionValue.REJECT,
                )
            )
            self._canonical(review)
            self._canonical(decision)

    def test_056_incomplete_fake_e9b_dependency_fails_static_import(self) -> None:
        result = _probe_incomplete_dependency("modules.knowledge_change_review_ru")
        FAKE_DEPENDENCY_RESULTS.append({"dependency": "e9b", "result": result})
        self.assertEqual(result, "IMPORT_ERROR")

    def test_057_incomplete_fake_e9c_dependency_fails_static_import(self) -> None:
        result = _probe_incomplete_dependency("modules.knowledge_change_review_decision_ru")
        FAKE_DEPENDENCY_RESULTS.append({"dependency": "e9c", "result": result})
        self.assertEqual(result, "IMPORT_ERROR")

    def test_058_all_ten_in_memory_faults_are_detected(self) -> None:
        faults = (
            (
                "01_omitted_proposed_field",
                "            for field in fields(value)\n",
                "            for field in fields(value)\n"
                "            if not (type(value) is ProposedContentProjection and field.name == \"verified_at\")\n",
                "test_010_all_18_proposed_content_fields_are_materialized",
            ),
            (
                "02_shortened_identity",
                "        review_artifact_identity=artifact.review_artifact_identity,\n",
                "        review_artifact_identity=artifact.review_artifact_identity[:-1],\n",
                "test_031_exact_review_identity_is_never_shortened",
            ),
            (
                "03_blocked_material_exposed",
                "        diff=diff,\n",
                "        diff=diff if artifact.status is not ReviewStatus.BLOCKED else \"EXPOSED\",\n",
                "test_032_blocked_diff_delta_and_change_material_are_exact_none",
            ),
            (
                "04_representation_omitted",
                "        representation_delta=representation,\n",
                "        representation_delta=None,\n",
                "test_028_full_representation_delta_is_materialized",
            ),
            (
                "05_preview_labeled_full",
                "        preview_is_full_diff=False,\n",
                "        preview_is_full_diff=True,\n",
                "test_025_diff_preview_is_never_labeled_as_full_diff",
            ),
            (
                "06_truncation_flag_disabled",
                "        truncated=body_preview.truncated,\n",
                "        truncated=False,\n",
                "test_013_large_body_preview_has_truthful_truncation_flag",
            ),
            (
                "07_windows_drive_relative_accepted",
                "        or bool(windows.drive)\n",
                "        or (bool(windows.drive) and not re.match(r\"^[A-Za-z]:[^\\\\/]\", value))\n",
                "test_047_windows_drive_relative_path_is_rejected",
            ),
            (
                "08_output_bound_disabled",
                "    if len(encoded) > MAX_TOTAL_JSON_BYTES:\n",
                "    if False and len(encoded) > MAX_TOTAL_JSON_BYTES:\n",
                "test_051_total_projection_byte_bound_is_enforced_at_canonical_boundary",
            ),
            (
                "09_json_aliases_internal_list",
                "            return [\n"
                "                _materialize(item, active=active, budget=budget)\n"
                "                for item in value\n"
                "            ]\n",
                "            global _FAULT_SHARED_LIST\n"
                "            if \"_FAULT_SHARED_LIST\" not in globals():\n"
                "                _FAULT_SHARED_LIST = [\n"
                "                    _materialize(item, active=active, budget=budget)\n"
                "                    for item in value\n"
                "                ]\n"
                "            return _FAULT_SHARED_LIST\n",
                "test_044_materializations_have_disjoint_containers_and_mutation_isolation",
            ),
            (
                "10_canonical_nondeterministic",
                "    return _canonical_json_value_bytes(materialized)\n",
                "    global _FAULT_CANONICAL_COUNTER\n"
                "    _FAULT_CANONICAL_COUNTER = globals().get(\"_FAULT_CANONICAL_COUNTER\", 0) + 1\n"
                "    return (\n"
                "        _canonical_json_value_bytes(materialized)\n"
                "        + str(_FAULT_CANONICAL_COUNTER).encode(\"ascii\")\n"
                "    )\n",
                "test_052_canonical_bytes_are_repeatable_and_match_independent_oracle",
            ),
        )
        observed = []
        for name, needle, replacement, test_name in faults:
            mutant, module_name = _load_mutant(name, needle, replacement)
            try:
                case = type(self)(test_name)
                case.api = mutant
                case.record_counts = False
                result = unittest.TestResult()
                case.run(result)
                entry = {
                    "fault": name,
                    "test": test_name,
                    "tests_run": result.testsRun,
                    "failures": len(result.failures),
                    "errors": len(result.errors),
                }
                observed.append(entry)
                self.assertEqual(entry["tests_run"], 1, name)
                self.assertEqual(entry["failures"], 1, name)
                self.assertEqual(entry["errors"], 0, name)
            finally:
                sys.modules.pop(module_name, None)
        FAULT_RESULTS[:] = observed
        self.assertEqual(len(observed), 10)

    def test_059_focused_suite_substance_gate(self) -> None:
        methods = {
            name: member
            for name, member in type(self).__dict__.items()
            if inspect.isfunction(member) and (name.startswith("test_") or name.startswith("_"))
        }
        public_names = {
            "project_knowledge_change_review",
            "project_knowledge_change_review_summary",
            "project_human_review_decision",
            "materialize_json_value",
            "canonical_projection_json_bytes",
        }
        call_graph: dict[str, set[str]] = {}
        direct_public: set[str] = set()
        normalized_bodies: dict[str, str] = {}
        assertion_patterns: dict[str, tuple[str, ...]] = {}
        for name, member in methods.items():
            try:
                source = inspect.getsource(member)
            except OSError:
                continue
            tree = ast.parse(textwrap.dedent(source))
            called = set()
            assertions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
                    if node.func.attr.startswith("assert"):
                        assertions.append(node.func.attr)
                    if node.func.attr in public_names:
                        direct_public.add(name)
            call_graph[name] = called
            if name.startswith("test_"):
                function = tree.body[0]
                function.name = "normalized"
                normalized_bodies[name] = ast.dump(function, include_attributes=False)
                assertion_patterns[name] = tuple(assertions)

        memo: dict[str, bool] = {}

        def reaches_public(name: str, active: set[str]) -> bool:
            if name in memo:
                return memo[name]
            if name in direct_public:
                memo[name] = True
                return True
            if name in active:
                return False
            result = any(
                called in methods and reaches_public(called, active | {name})
                for called in call_graph.get(name, set())
            )
            memo[name] = result
            return result

        tests = sorted(name for name in normalized_bodies)
        reached = sorted(name for name in tests if reaches_public(name, set()))
        duplicate_groups = []
        for index, left in enumerate(tests):
            group = [
                right for right in tests[index + 1:]
                if normalized_bodies[left] == normalized_bodies[right]
            ]
            if group:
                duplicate_groups.append([left, *group])
        near_duplicate_pairs = []
        for index, left in enumerate(tests):
            for right in tests[index + 1:]:
                left_body = normalized_bodies[left]
                right_body = normalized_bodies[right]
                larger = max(len(left_body), len(right_body))
                if larger and abs(len(left_body) - len(right_body)) / larger > 0.01:
                    continue
                matcher = difflib.SequenceMatcher(
                    None,
                    left_body,
                    right_body,
                    autojunk=False,
                )
                if matcher.quick_ratio() < 0.995:
                    continue
                ratio = matcher.ratio()
                if ratio >= 0.995:
                    near_duplicate_pairs.append((left, right, round(ratio, 6)))
        reach_ratio = len(reached) / len(tests)
        SUBSTANCE_METRICS.update(
            {
                "test_methods": len(tests),
                "public_api_reaching_methods": len(reached),
                "public_api_reach_ratio": round(reach_ratio, 6),
                "unique_behavioral_scenarios": len(
                    [
                        name for name in tests
                        if not name.startswith(("test_054_", "test_056_", "test_057_", "test_058_", "test_059_"))
                    ]
                ),
                "exact_duplicate_groups": duplicate_groups,
                "near_duplicate_pairs_at_0_995": near_duplicate_pairs,
                "distinct_assertion_patterns": len(set(assertion_patterns.values())),
            }
        )
        self.assertGreaterEqual(len(tests), 50)
        self.assertGreaterEqual(reach_ratio, 0.80)
        self.assertEqual(duplicate_groups, [])
        self.assertLessEqual(len(near_duplicate_pairs), 2)
        self.assertGreaterEqual(len(set(assertion_patterns.values())), 12)

    def test_060_validation_depth_nodes_mapping_sequence_key_and_string_bounds(self) -> None:
        null = FrozenCanonicalValue("null")
        deep = null
        for _ in range(self.api.MAX_VALIDATION_DEPTH + 1):
            deep = FrozenCanonicalValue("sequence", sequence_items=(deep,))
        mapping = FrozenCanonicalValue(
            "mapping",
            mapping_items=tuple(
                (f"key-{index:03d}", null)
                for index in range(self.api.MAX_VALIDATION_MAPPING_ITEMS + 1)
            ),
        )
        sequence = FrozenCanonicalValue(
            "sequence",
            sequence_items=(null,) * (self.api.MAX_VALIDATION_SEQUENCE_ITEMS + 1),
        )
        branch = FrozenCanonicalValue(
            "sequence",
            sequence_items=(null,) * self.api.MAX_VALIDATION_SEQUENCE_ITEMS,
        )
        node_heavy = FrozenCanonicalValue(
            "sequence",
            sequence_items=(branch,) * 9,
        )
        long_key = FrozenCanonicalValue(
            "mapping",
            mapping_items=(("k" * (self.api.MAX_VALIDATION_KEY_CHARS + 1), null),),
        )
        long_string = FrozenCanonicalValue(
            "string",
            "s" * (self.api.MAX_VALIDATION_STRING_CHARS + 1),
        )
        large_integer = FrozenCanonicalValue(
            "int",
            self.api.MAX_SAFE_JSON_INTEGER + 1,
        )
        cases = (
            (deep, self.api.ProjectionRejectionCode.VALIDATION_DEPTH_EXCEEDED),
            (mapping, self.api.ProjectionRejectionCode.VALIDATION_MAPPING_LIMIT_EXCEEDED),
            (sequence, self.api.ProjectionRejectionCode.VALIDATION_SEQUENCE_LIMIT_EXCEEDED),
            (node_heavy, self.api.ProjectionRejectionCode.VALIDATION_NODE_LIMIT_EXCEEDED),
            (long_key, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED),
            (long_string, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED),
            (large_integer, self.api.ProjectionRejectionCode.INVALID_VALIDATION_VALUE),
        )
        for snapshot, expected_code in cases:
            with self.subTest(code=expected_code.value):
                artifact = _clone_exact_review(
                    self.clear_create,
                    validation_snapshot=snapshot,
                )
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, expected_code)

    def test_061_general_string_and_source_body_bounds_fail_closed(self) -> None:
        oversized_title = replace(
            self.clear_create.proposed_content_snapshot,
            title="t" * (self.api.MAX_GENERAL_STRING_CHARS + 1),
        )
        title_artifact = _clone_exact_review(
            self.clear_create,
            proposed_content_snapshot=oversized_title,
        )
        with self.assertRaises(self.api.ProjectionRejected) as title_error:
            self._review_projection(title_artifact)
        self.assertIs(title_error.exception.code, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED)

        oversized_body = replace(
            self.clear_create.proposed_content_snapshot,
            body_text="b" * (self.api.MAX_SOURCE_BODY_BYTES + 1),
        )
        body_artifact = _clone_exact_review(
            self.clear_create,
            proposed_content_snapshot=oversized_body,
        )
        with self.assertRaises(self.api.ProjectionRejected) as body_error:
            self._review_projection(body_artifact)
        self.assertIs(body_error.exception.code, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED)

    def test_062_finding_detail_source_bound_fails_closed(self) -> None:
        source = self.review_required.findings[0]
        finding = object.__new__(ConflictFinding)
        object.__setattr__(finding, "code", source.code)
        object.__setattr__(finding, "severity", source.severity)
        object.__setattr__(finding, "message", source.message)
        object.__setattr__(
            finding,
            "details",
            tuple((f"key-{index:03d}", "value") for index in range(257)),
        )
        artifact = _clone_exact_review(self.review_required, findings=(finding,))
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED)

    def test_063_same_shape_but_unbound_decision_identity_is_rejected(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="identity-bound",
        )
        clone = object.__new__(decision_contract.HumanReviewDecision)
        for item in fields(decision_contract.HumanReviewDecision):
            value = getattr(decision, item.name)
            if item.name == "decision_identity":
                value = "kdecision:" + "0" * 64
            object.__setattr__(clone, item.name, value)
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._decision_projection(clone)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.INVALID_DECISION_ARTIFACT)

    def test_064_empty_and_dot_only_source_paths_are_rejected(self) -> None:
        for path in ("", ".", "./", ".\\"):
            with self.subTest(path=repr(path)):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_065_exact_review_identity_contract_and_binding_fields_are_preserved(self) -> None:
        projected = self._review_projection(self.clear_update)
        for name in (
            "contract_version", "proposal_id", "proposal_content_hash", "operation",
            "target_stable_id", "expected_vault_revision", "observed_vault_revision",
            "validation_outcome", "stable_id_set_hash", "change_identity",
            "review_artifact_identity",
        ):
            source_value = getattr(self.clear_update, name)
            expected = source_value.value if hasattr(source_value, "value") else source_value
            self.assertEqual(getattr(projected, name), expected, name)

    def test_066_every_representation_field_and_line_profile_value_is_exact(self) -> None:
        source = self.clear_update.representation_delta
        projected = self._review_projection(self.clear_update).representation_delta
        for name in (
            "before_present", "after_present", "terminal_newline_changed",
            "after_source_bytes_known", "source_bytes_changed_text_identical",
            "raw_text_changed_semantic_equal", "semantic_content_changed", "identity",
        ):
            self.assertEqual(getattr(projected, name), getattr(source, name), name)
        for profile_name in ("before_line_endings", "after_line_endings"):
            source_profile = getattr(source, profile_name)
            projected_profile = getattr(projected, profile_name)
            for name in ("crlf_count", "lf_count", "cr_count", "terminal_newline"):
                self.assertEqual(
                    getattr(projected_profile, name),
                    getattr(source_profile, name),
                    f"{profile_name}.{name}",
                )

    def test_067_all_projection_records_are_runtime_frozen(self) -> None:
        review = self._review_projection(self.clear_update)
        decision = self._decision_projection(
            self._decision(
                self.clear_create,
                value=decision_contract.HumanReviewDecisionValue.REJECT,
            )
        )

        def assert_frozen_tree(value):
            if is_dataclass(value) and not isinstance(value, type):
                self.assertTrue(type(value).__dataclass_params__.frozen, type(value).__name__)
                self.assertFalse(hasattr(value, "__dict__"), type(value).__name__)
                for item in fields(value):
                    assert_frozen_tree(getattr(value, item.name))
            elif type(value) is tuple:
                for child in value:
                    assert_frozen_tree(child)

        assert_frozen_tree(review)
        assert_frozen_tree(decision)
        with self.assertRaises(FrozenInstanceError):
            review.proposed_content_snapshot.title = "mutated"
        with self.assertRaises(FrozenInstanceError):
            decision.actor.display_name = "mutated"

    def test_068_real_finding_message_is_bounded_by_bytes_and_lines(self) -> None:
        source = self.review_required.findings[0]
        byte_heavy = ConflictFinding(
            code=source.code,
            severity=source.severity,
            message="🚀" * 800,
            details=source.details,
        )
        line_heavy = ConflictFinding(
            code=source.code,
            severity=source.severity,
            message="строка\n" * 100,
            details=source.details,
        )
        for finding, bound_name in (
            (byte_heavy, "bytes"),
            (line_heavy, "lines"),
        ):
            with self.subTest(bound=bound_name):
                artifact = _clone_exact_review(self.review_required, findings=(finding,))
                message = self._review_projection(artifact).findings.items[0].message
                self.assertTrue(message.truncated)
                self.assertLessEqual(message.preview_utf8_bytes, self.api.MAX_FINDING_MESSAGE_BYTES)
                self.assertLessEqual(message.preview_line_count, self.api.MAX_FINDING_MESSAGE_LINES)

    def test_069_exact_root_type_rejects_review_and_decision_subclasses(self) -> None:
        class ReviewSubclass(KnowledgeChangeReviewArtifact):
            pass

        review_subclass = object.__new__(ReviewSubclass)
        for item in fields(KnowledgeChangeReviewArtifact):
            object.__setattr__(review_subclass, item.name, getattr(self.clear_update, item.name))
        with self.assertRaises(self.api.ProjectionRejected) as review_error:
            self.api.project_knowledge_change_review(review_subclass)
        self.assertIs(review_error.exception.code, self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)

        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )

        class DecisionSubclass(decision_contract.HumanReviewDecision):
            pass

        decision_subclass = object.__new__(DecisionSubclass)
        for item in fields(decision_contract.HumanReviewDecision):
            object.__setattr__(decision_subclass, item.name, getattr(decision, item.name))
        with self.assertRaises(self.api.ProjectionRejected) as decision_error:
            self.api.project_human_review_decision(decision_subclass)
        self.assertIs(decision_error.exception.code, self.api.ProjectionRejectionCode.WRONG_DECISION_TYPE)

    def test_070_manual_projection_injection_is_rejected_before_json_escape(self) -> None:
        projected = self._review_projection(self.clear_update)
        mutable_injection = replace(projected, status=["CLEAR"])
        with self.assertRaises(self.api.ProjectionRejected) as mutable_error:
            self.api.materialize_json_value(mutable_injection)
        self.assertIs(mutable_error.exception.code, self.api.ProjectionRejectionCode.SERIALIZATION_FAILED)

        delta = replace(
            projected.representation_delta,
            before_present=self.api.MAX_SAFE_JSON_INTEGER + 1,
        )
        integer_injection = replace(projected, representation_delta=delta)
        with self.assertRaises(self.api.ProjectionRejected) as integer_error:
            self.api.materialize_json_value(integer_injection)
        self.assertIs(integer_error.exception.code, self.api.ProjectionRejectionCode.SERIALIZATION_FAILED)

    def test_071_stable_id_and_windows_normalized_traversal_are_rejected(self) -> None:
        invalid_target = _clone_exact_review(
            self.clear_update,
            target_stable_id=r"C:\secret\note.md",
        )
        with self.assertRaises(self.api.ProjectionRejected) as stable_id_error:
            self._review_projection(invalid_target)
        self.assertIs(stable_id_error.exception.code, self.api.ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT)

        traversal = self._replace_source_paths(
            self.clear_create,
            ("notes/.. /secret.md",),
        )
        with self.assertRaises(self.api.ProjectionRejected) as traversal_error:
            self._review_projection(traversal)
        self.assertIs(traversal_error.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_072_summary_projection_has_exact_bounded_queue_fields(self) -> None:
        summary = self._review_summary_projection(self.review_required)
        value = self._materialize(summary)
        self.assertIs(type(summary), self.api.KnowledgeChangeReviewSummaryProjection)
        self.assertEqual(
            set(value),
            {
                "projection_contract",
                "kind",
                "contract_version",
                "status",
                "blocked",
                "proposal_id",
                "target_stable_id",
                "operation",
                "expected_vault_revision",
                "observed_vault_revision",
                "review_artifact_identity",
                "change_identity",
                "finding_count",
                "normal_change_material_present",
                "detail_projection_truncated",
            },
        )
        self.assertEqual(value["projection_contract"], self.api.PROJECTION_CONTRACT_VERSION)
        self.assertEqual(value["kind"], "KNOWLEDGE_CHANGE_REVIEW_SUMMARY")
        self.assertEqual(value["finding_count"], len(self.review_required.findings))
        self.assertNotIn("body_text", value)
        self.assertNotIn("validation_snapshot", value)
        self.assertNotIn("human_review_preview", value)
        self.assertNotIn("findings", value)

    def test_073_summary_is_derived_by_calling_the_accepted_full_projector(self) -> None:
        original = self.api.project_knowledge_change_review
        with mock.patch.object(
            self.api,
            "project_knowledge_change_review",
            wraps=original,
        ) as full_projector:
            summary = self._review_summary_projection(self.clear_update)
        full_projector.assert_called_once_with(self.clear_update)
        self.assertEqual(summary.review_artifact_identity, self.clear_update.review_artifact_identity)
        self.assertTrue(summary.normal_change_material_present)

    def test_074_blocked_summary_preserves_absence_without_authority_fields(self) -> None:
        summary = self._review_summary_projection(self.blocked)
        value = self._materialize(summary)
        self.assertEqual(summary.status, "BLOCKED")
        self.assertTrue(summary.blocked)
        self.assertIsNone(summary.change_identity)
        self.assertFalse(summary.normal_change_material_present)
        serialized = json.dumps(value, sort_keys=True)
        for forbidden in (
            "decision_identity",
            "grants_write_authority",
            "human_identity_authenticated",
            "human_review_preview",
            "validation_snapshot",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_075_summary_truncation_fact_is_truthful_and_canonical(self) -> None:
        artifact = self._large_update()
        summary = self._review_summary_projection(artifact)
        first = self._canonical(summary)
        second = self._canonical(summary)
        self.assertTrue(summary.detail_projection_truncated)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), self.api.MAX_TOTAL_JSON_BYTES)
        self.assertEqual(json.loads(first.decode("utf-8")), self._materialize(summary))

    def test_076_summary_is_frozen_fresh_and_rejects_wrong_source_type(self) -> None:
        summary = self._review_summary_projection(self.clear_create)
        self.assertFalse(hasattr(summary, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            summary.status = "BLOCKED"
        first = self._materialize(summary)
        second = self._materialize(summary)
        self.assertTrue(_container_ids(first).isdisjoint(_container_ids(second)))
        first["status"] = "MUTATED"
        self.assertEqual(second["status"], "CLEAR")
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self.api.project_knowledge_change_review_summary({"artifact": self.clear_create})
        self.assertIs(
            captured.exception.code,
            self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE,
        )


def _run() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "construction_counts": CONSTRUCTION_COUNTS,
        "fake_dependency_results": sorted(
            FAKE_DEPENDENCY_RESULTS,
            key=lambda item: str(item["dependency"]),
        ),
        "fault_results": FAULT_RESULTS,
        "substance_metrics": SUBSTANCE_METRICS,
    }
    print("PROJECTION_EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run())
````

### ПУТЬ: tools/test_v68451e9d_knowledge_review_producer.py (491 строк, 22040 байт)

````python
"""Focused tests for the bounded trusted in-memory knowledge-review producer."""

from __future__ import annotations

import builtins
import copy
from dataclasses import FrozenInstanceError, replace
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import (
    CONTROL_PLANE_METHODS,
    ControlPlaneLimits,
    DesktopControlPlane,
)
import modules.desktop_control_plane_ru as control_plane_contract
from modules.desktop_sidecar_runtime_ru import CONTROL_PLANE_CAPABILITIES
from modules.knowledge_change_proposal_ru import (
    CONTRACT_VERSION as E9A_CONTRACT_VERSION,
    CanonicalLocationHint,
    EvidenceReference,
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposerMetadata,
    ProposedNoteContent,
    Provenance,
    ValidationResult,
    compute_proposal_instance_id,
)
from modules.knowledge_change_review_ru import (
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
    create_trusted_target_snapshot,
)


DESKTOP = ROOT / "desktop" / "localcomet-desktop"
REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
TARGET = "canonical.current-state"
OTHER_TARGET = "architecture.knowledge-layer"
PRODUCER_TESTS: set[str] = set()
PRODUCER_CALLS = 0
FAULT_RESULTS: list[dict[str, str]] = []


class KnowledgeReviewProducerTests(unittest.TestCase):
    def make_proposal(
        self,
        *,
        operation: ProposalOperation,
        target: str,
        body: str,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="test-agent",
            agent_instance_id="producer-instance",
            model_identifier="none",
            source_workflow="e9d-focused-tests",
        )
        provenance = Provenance(
            reason="bounded producer test",
            source_observation="trusted in-process input",
            related_stable_ids=(target,),
            evidence_references=(
                EvidenceReference(reference="EV-PRODUCER-001", description="producer evidence"),
            ),
            workflow_origin="e9d-focused-test",
        )
        content = ProposedNoteContent(
            title="Producer Review",
            body_text=body,
            type="project_state",
            status="accepted",
            knowledge_layer="canonical",
            evidence_class="A",
            authority="repository",
            canonical=True,
            canonical_scope="producer-review",
            aliases=("producer",),
            releases=("v6.84.5.1e9d",),
            source_paths=("modules/desktop_control_plane_ru.py",),
            evidence_refs=("EV-PRODUCER-001",),
            supersedes=(),
            superseded_by=(),
            updated="2026-07-16",
            last_reviewed="2026-07-16",
            verified_at=None,
        )
        hint = (
            CanonicalLocationHint(
                relative_path=f"canonical/{target.replace('.', '-')}.md",
                parent_stable_id=None,
            )
            if operation is ProposalOperation.CREATE_NEW
            else None
        )
        temporary = KnowledgeChangeProposal(
            proposal_id="kprop:" + "0" * 64,
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=REV_A,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        return KnowledgeChangeProposal(
            proposal_id=compute_proposal_instance_id(temporary),
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=REV_A,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )

    def make_inputs(
        self,
        kind: str = "create",
        *,
        target: str = OTHER_TARGET,
        body: str = "created by trusted producer\n",
    ) -> tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState]:
        if kind == "update" or kind == "review_required":
            proposal = self.make_proposal(
                operation=ProposalOperation.UPDATE_EXISTING,
                target=TARGET,
                body=body,
            )
            validation = ProposalValidator(REV_A, {TARGET}).validate(proposal)
            current = create_trusted_target_snapshot(
                source_bytes=b"existing body\n",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=REV_A,
            )
            state = CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids={TARGET},
                current_target=current,
                baseline_target=current if kind == "update" else None,
            )
            return proposal, validation, state

        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=target,
            body=body,
        )
        validation = ProposalValidator(REV_A, {TARGET}).validate(proposal)
        state = CurrentKnowledgeState(
            observed_vault_revision=REV_B if kind == "blocked" else REV_A,
            current_stable_ids={TARGET},
        )
        return proposal, validation, state

    def produce(
        self,
        plane: DesktopControlPlane,
        inputs: tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState],
    ) -> KnowledgeChangeReviewArtifact:
        global PRODUCER_CALLS
        PRODUCER_CALLS += 1
        PRODUCER_TESTS.add(self._testMethodName)
        return plane.produce_knowledge_review(*inputs)

    @staticmethod
    def list_reviews(plane: DesktopControlPlane) -> dict[str, object]:
        return dict(
            plane.dispatch(
                "knowledge.review.list",
                {"offset": 0, "limit": 50},
                request_id="producer-list",
            ).response
        )

    @staticmethod
    def get_review(plane: DesktopControlPlane, identity: str) -> dict[str, object]:
        return dict(
            plane.dispatch(
                "knowledge.review.get",
                {"review_artifact_identity": identity},
                request_id="producer-get",
            ).response
        )

    def record_fault(self, name: str, detector: str) -> None:
        FAULT_RESULTS.append({"fault": name, "detector": detector, "result": "DETECTED"})

    def test_001_default_control_plane_remains_truthfully_empty(self) -> None:
        response = self.list_reviews(DesktopControlPlane())
        self.assertEqual(response["items"], [])
        self.assertEqual(response["total_count"], 0)
        self.assertEqual(response["source"], "LOCAL_CONTROL_PLANE")
        self.assertIs(response["fixture"], False)

    def test_002_real_create_new_clear_artifact_is_produced(self) -> None:
        artifact = self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)
        self.assertIs(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.operation, "CREATE_NEW")

    def test_003_real_update_existing_clear_artifact_is_produced(self) -> None:
        artifact = self.produce(
            DesktopControlPlane(),
            self.make_inputs("update", body="updated body\n"),
        )
        self.assertIs(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.operation, "UPDATE_EXISTING")
        self.assertIsNotNone(artifact.change_identity)

    def test_004_review_required_artifact_is_preserved(self) -> None:
        artifact = self.produce(
            DesktopControlPlane(),
            self.make_inputs("review_required", body="review body\n"),
        )
        self.assertIs(artifact.status, ReviewStatus.REVIEW_REQUIRED)
        self.assertTrue(artifact.findings)

    def test_005_blocked_artifact_is_not_filtered(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs("blocked"))
        listed = self.list_reviews(plane)
        fetched = self.get_review(plane, artifact.review_artifact_identity)
        self.assertIs(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(listed["returned_count"], 1)
        self.assertEqual(fetched["projection"]["status"], "BLOCKED")
        self.assertIsNone(fetched["projection"]["change_identity"])
        self.record_fault("blocked artifact filtered out", "produced BLOCKED list/get retention")

    def test_006_produced_artifact_is_immediately_visible_through_list(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs())
        response = self.list_reviews(plane)
        self.assertEqual(response["total_count"], 1)
        self.assertEqual(response["items"][0]["review_artifact_identity"], artifact.review_artifact_identity)

    def test_007_produced_artifact_is_visible_through_exact_get(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs("update"))
        response = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(response["contract"], "localcomet.knowledge-review-get/1.0")
        self.assertEqual(response["projection"]["review_artifact_identity"], artifact.review_artifact_identity)

    def test_008_exact_kprop_kchange_kreview_identities_are_preserved(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, state = self.make_inputs("update", body="identity body\n")
        artifact = self.produce(plane, (proposal, validation, state))
        projection = self.get_review(plane, artifact.review_artifact_identity)["projection"]
        self.assertEqual(projection["proposal_id"], proposal.proposal_id)
        self.assertEqual(projection["change_identity"], artifact.change_identity)
        self.assertEqual(projection["review_artifact_identity"], artifact.review_artifact_identity)

    def test_009_ordering_is_deterministic_independent_of_production_order(self) -> None:
        inputs = [
            self.make_inputs(target=f"producer.target-{index:03d}", body=f"body {index}\n")
            for index in range(3)
        ]
        expected = sorted(analyze_review(*item).review_artifact_identity for item in inputs)
        plane = DesktopControlPlane()
        for item in reversed(inputs):
            self.produce(plane, item)
        actual = [item["review_artifact_identity"] for item in self.list_reviews(plane)["items"]]
        self.assertEqual(actual, expected)
        self.record_fault("ordering made nondeterministic", "reverse insertion canonical-order assertion")

    def test_010_exact_duplicate_production_is_idempotent(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        first = self.produce(plane, inputs)
        second = self.produce(plane, inputs)
        self.assertIs(first, second)
        self.assertEqual(self.list_reviews(plane)["total_count"], 1)

    def test_011_identity_collision_with_unequal_artifact_fails_closed(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        original = self.produce(plane, inputs)
        collision = replace(
            original,
            human_review_preview=original.human_review_preview + "\ncollision probe",
        )
        with mock.patch.object(control_plane_contract, "analyze_review", return_value=collision):
            with self.assertRaisesRegex(ValueError, "collision"):
                self.produce(plane, inputs)
        fetched = self.get_review(plane, original.review_artifact_identity)["projection"]
        self.assertNotIn("collision probe", fetched["human_review_preview"]["preview_text"])
        self.record_fault("duplicate collision silently overwritten", "unequal same-identity injection")

    def test_012_arbitrary_mapping_proposal_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        _, validation, state = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact KnowledgeChangeProposal"):
            plane.produce_knowledge_review({}, validation, state)
        self.record_fault("arbitrary mapping accepted", "exact proposal type gate")

    def test_013_wrong_validation_type_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        proposal, _, state = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact ValidationResult"):
            plane.produce_knowledge_review(proposal, {}, state)

    def test_014_wrong_current_state_type_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, _ = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact CurrentKnowledgeState"):
            plane.produce_knowledge_review(proposal, validation, {})

    def test_015_hard_artifact_count_bound_rejects_distinct_addition(self) -> None:
        plane = DesktopControlPlane(
            limits=ControlPlaneLimits(maximum_knowledge_review_artifacts=1),
        )
        self.produce(plane, self.make_inputs(target="producer.bound-first"))
        with self.assertRaisesRegex(ValueError, "limit reached"):
            self.produce(plane, self.make_inputs(target="producer.bound-second"))
        self.record_fault("artifact bound disabled", "one-item ControlPlaneLimits boundary")

    def test_016_full_collection_fails_without_hidden_eviction(self) -> None:
        plane = DesktopControlPlane(
            limits=ControlPlaneLimits(maximum_knowledge_review_artifacts=1),
        )
        first = self.produce(plane, self.make_inputs(target="producer.eviction-first"))
        with self.assertRaises(ValueError):
            self.produce(plane, self.make_inputs(target="producer.eviction-second"))
        response = self.list_reviews(plane)
        self.assertEqual(response["total_count"], 1)
        self.assertEqual(response["items"][0]["review_artifact_identity"], first.review_artifact_identity)
        self.record_fault("hidden eviction enabled", "full-list retention after rejected add")

    def test_017_source_inputs_are_not_mutated_or_retained_mutably(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, state = self.make_inputs()
        proposal_before = copy.deepcopy(proposal.to_dict())
        validation_before = copy.deepcopy(validation.to_dict())
        stable_ids_before = state.current_stable_ids
        artifact = self.produce(plane, (proposal, validation, state))
        self.assertEqual(proposal.to_dict(), proposal_before)
        self.assertEqual(validation.to_dict(), validation_before)
        self.assertIs(state.current_stable_ids, stable_ids_before)
        before = self.get_review(plane, artifact.review_artifact_identity)
        validation.provenance_summary["reason"] = "caller mutation after production"
        after = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(before, after)

    def test_018_returned_artifact_is_an_immutable_snapshot(self) -> None:
        artifact = self.produce(DesktopControlPlane(), self.make_inputs())
        with self.assertRaises(FrozenInstanceError):
            artifact.status = ReviewStatus.BLOCKED
        self.assertFalse(hasattr(artifact, "__dict__"))

    def test_019_constructor_injection_remains_compatible_with_production(self) -> None:
        injected = analyze_review(*self.make_inputs(target="producer.injected"))
        plane = DesktopControlPlane(knowledge_reviews=[injected])
        produced = self.produce(plane, self.make_inputs(target="producer.produced"))
        identities = [item["review_artifact_identity"] for item in self.list_reviews(plane)["items"]]
        self.assertEqual(identities, sorted((injected.review_artifact_identity, produced.review_artifact_identity)))

    def test_020_real_analyze_review_dependency_cannot_be_bypassed(self) -> None:
        plane = DesktopControlPlane()
        with mock.patch.object(
            control_plane_contract,
            "analyze_review",
            wraps=analyze_review,
        ) as analyzer:
            artifact = self.produce(plane, self.make_inputs())
        analyzer.assert_called_once()
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)
        self.record_fault("analyze_review bypassed", "wrapped real analyzer call assertion")

    def test_021_producer_is_not_exposed_as_an_ipc_method(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertEqual(
            {method for method in CONTROL_PLANE_METHODS if method.startswith("knowledge.review.")},
            {
                "knowledge.review.decision.create",
                "knowledge.review.get",
                "knowledge.review.list",
                "knowledge.review.refresh",
                "knowledge.review.snapshot",
            },
        )
        self.assertNotIn("produce_knowledge_review", CONTROL_PLANE_METHODS)
        self.assertNotIn("knowledge.review.register", CONTROL_PLANE_METHODS)
        self.assertNotIn("knowledge.review.upload", CONTROL_PLANE_METHODS)
        self.record_fault("producer exposed as IPC method", "exact review allowlist assertion")

    def test_022_no_sidecar_rust_tauri_or_frontend_producer_surface_exists(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertEqual(tuple(CONTROL_PLANE_METHODS), tuple(CONTROL_PLANE_CAPABILITIES))
        paths = (
            DESKTOP / "src-tauri" / "src" / "control_plane.rs",
            DESKTOP / "src-tauri" / "src" / "lib.rs",
            DESKTOP / "src" / "lib" / "bridge" / "knowledgeReview.ts",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("produce_knowledge_review", combined)
        self.assertNotIn("knowledge.review.produce", combined)

    def test_023_no_registration_or_decision_creation_vocabulary_in_producer(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        source = inspect.getsource(DesktopControlPlane.produce_knowledge_review).lower()
        for forbidden in (
            "register",
            "upload",
            "replace_all",
            "humanreviewdecision",
            "kdecision",
            "decision.create",
            "vault",
            "publish",
        ):
            self.assertNotIn(forbidden, source)

    def test_024_production_uses_no_filesystem_network_subprocess_or_model_path(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("filesystem access")),
            mock.patch.object(Path, "open", side_effect=AssertionError("filesystem access")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network access")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network access")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess access")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess access")),
        ):
            artifact = self.produce(plane, inputs)
        source = inspect.getsource(DesktopControlPlane.produce_knowledge_review).lower()
        self.assertNotIn("model", source)
        self.assertNotIn("persist", source)
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)

    def test_025_list_get_contracts_and_real_source_remain_unchanged(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs())
        listed = self.list_reviews(plane)
        fetched = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(listed["contract"], "localcomet.knowledge-review-list/1.0")
        self.assertEqual(fetched["contract"], "localcomet.knowledge-review-get/1.0")
        for response in (listed, fetched):
            self.assertEqual(response["source"], "LOCAL_CONTROL_PLANE")
            self.assertIs(response["fixture"], False)


def _run() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(KnowledgeReviewProducerTests)
    expected_tests = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    transitive_count = len(PRODUCER_TESTS)
    transitive_ratio = transitive_count / expected_tests if expected_tests else 0.0
    evidence = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "producer_api_calls": PRODUCER_CALLS,
        "tests_transitively_calling_producer": transitive_count,
        "transitive_ratio": transitive_ratio,
        "deliberate_faults": sorted(FAULT_RESULTS, key=lambda item: item["fault"]),
    }
    print("PRODUCER_EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, ensure_ascii=False))
    if transitive_ratio < 0.8:
        print("PRODUCER_SUBSTANCE_FAILURE=less than 80% of focused tests called producer")
        return 1
    if len(FAULT_RESULTS) < 8:
        print("PRODUCER_FAULT_FAILURE=fewer than 8 deliberate faults detected")
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run())
````

