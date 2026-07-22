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
