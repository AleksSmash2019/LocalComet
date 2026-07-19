"""Focused tests for the internal Control Plane ↔ KnowledgeAdapter contract."""

from __future__ import annotations

from dataclasses import asdict, FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.fspath(ROOT))

from modules.desktop_control_plane_ru import (  # noqa: E402
    CONTROL_PLANE_METHODS,
    EVENT_METHODS,
    ControlPlaneError,
    DesktopControlPlane,
)
from modules.knowledge_contract_ru import (  # noqa: E402
    DEFAULT_CONTEXT_CHARS,
    DEFAULT_MAX_RESULTS,
    HARD_MAX_CONTEXT_CHARS,
    HARD_MAX_RESULTS,
    MAX_QUERY_CHARS,
    KnowledgeAdapterError,
    KnowledgeContextError,
    KnowledgeContextRequest,
    KnowledgeContextResult,
    KnowledgeContextState,
    KnowledgeErrorCode,
    QueryIntent,
)
from modules.local_model_gateway_ru import ModelBinding  # noqa: E402


REQUEST_IDS = (f"kreq:00000000-0000-4000-8000-{index:012d}" for index in range(1, 1000))


def next_request_id() -> str:
    return next(REQUEST_IDS)


def source(
    note_id: str = "architecture.control-plane",
    *,
    content: str = "Control Plane coordinates lifecycle state.",
    relative_path: str = "01 Архитектура/Контур управления.md",
    knowledge_layer: str = "current_source_truth",
    evidence_class: str = "A",
    authority: str = "source",
    status: str = "current",
    canonical: bool = False,
) -> dict[str, object]:
    return {
        "note_id": note_id,
        "title": "Контур управления",
        "relative_path": relative_path,
        "knowledge_layer": knowledge_layer,
        "evidence_class": evidence_class,
        "authority": authority,
        "status": status,
        "canonical": canonical,
        "selected_sections": [
            {
                "heading": "Граница",
                "line_start": 10,
                "line_end": 12,
                "content": content,
            }
        ],
        "note_sha256": hashlib.sha256(note_id.encode("utf-8")).hexdigest(),
    }


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.model_calls = 0
        self.tool_executions = 0
        self.mode = "ready"
        self.content = "Control Plane coordinates lifecycle state."
        self.callback = None
        self.custom_sources: list[dict[str, object]] | None = None

    def context_preview(
        self,
        query: str,
        intent: QueryIntent | str,
        *,
        max_context_chars: int,
        max_results: int,
        include_superseded: bool,
    ) -> dict[str, object]:
        resolved_intent = QueryIntent(intent).value
        self.calls.append(
            {
                "query": query,
                "intent": resolved_intent,
                "max_context_chars": max_context_chars,
                "max_results": max_results,
                "include_superseded": include_superseded,
            }
        )
        if self.callback is not None:
            self.callback()
        if self.mode == "unavailable":
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                "KnowledgeAdapter is not configured.",
            )
        if self.mode == "validation_failure":
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_VALIDATION_FAILED,
                "Knowledge Vault validation failed.",
            )
        if self.mode == "path_error":
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Unsafe path at C:\\Users\\DNS\\Vault.",
            )
        if self.mode == "invalid_contract":
            return {"sources": "anonymous"}
        if self.mode == "zero":
            sources: list[dict[str, object]] = []
        elif self.custom_sources is not None:
            sources = self.custom_sources
        else:
            sources = [source(content=self.content)]
        total_chars = sum(
            len(section["content"])
            for item in sources
            for section in item["selected_sections"]
        )
        bundle_material = json.dumps(
            {
                "query": query,
                "intent": resolved_intent,
                "sources": sources,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "bundle_id": "kb:" + hashlib.sha256(bundle_material.encode("utf-8")).hexdigest(),
            "vault_revision": "sha256:" + "a" * 64,
            "query": query,
            "resolved_intent": resolved_intent,
            "total_chars": total_chars,
            "truncated": False,
            "sources": sources,
            "context_relations": [],
            "warnings": ["VALIDATION_WARNINGS:13"],
        }


def entity_ids():
    for index in range(1, 1000):
        yield f"{index:024x}"


def plane_with_turn(adapter: FakeAdapter | None = None):
    ids = entity_ids()
    plane = DesktopControlPlane(
        id_factory=lambda: next(ids),
        knowledge_adapter=adapter,
        knowledge_request_id_factory=next_request_id,
    )
    session = plane.dispatch("session.create", {"title": "e5"}, request_id="session")
    thread = plane.dispatch(
        "thread.create",
        {"session_id": session.response["session_id"], "title": "e5"},
        request_id="thread",
    )
    turn = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread.response["thread_id"], "prompt": "existing", "behavior": "complete"},
        request_id="turn",
    )
    return plane, turn.response["turn_id"]


class KnowledgeControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = FakeAdapter()
        self.plane = DesktopControlPlane(
            knowledge_adapter=self.adapter,
            knowledge_request_id_factory=next_request_id,
        )

    def request(self, **overrides):
        values = {
            "query": "Как устроен Control Plane?",
            "intent": QueryIntent.ARCHITECTURE,
        }
        values.update(overrides)
        return self.plane.request_knowledge_context(**values)

    def assert_contract_error(self, **overrides) -> None:
        with self.assertRaises(ControlPlaneError) as caught:
            self.request(**overrides)
        self.assertEqual("CONTRACT_VALIDATION_ERROR", caught.exception.code)

    def test_01_valid_request_contract_accepted(self) -> None:
        request = KnowledgeContextRequest(next_request_id(), "query", QueryIntent.AUTO)
        self.assertEqual(QueryIntent.AUTO, request.intent)

    def test_02_empty_query_rejected(self) -> None:
        self.assert_contract_error(query="   ")

    def test_03_oversized_query_rejected(self) -> None:
        self.assert_contract_error(query="x" * (MAX_QUERY_CHARS + 1))

    def test_04_invalid_intent_rejected(self) -> None:
        self.assert_contract_error(intent="NOT_AN_INTENT")

    def test_05_context_limit_rejected(self) -> None:
        self.assert_contract_error(max_context_chars=HARD_MAX_CONTEXT_CHARS + 1)

    def test_06_result_limit_rejected(self) -> None:
        self.assert_contract_error(max_results=HARD_MAX_RESULTS + 1)

    def test_07_boolean_limits_rejected(self) -> None:
        self.assert_contract_error(max_results=True)

    def test_08_request_id_is_unique_lifecycle_identity(self) -> None:
        first = self.request().response["request_id"]
        second = self.request().response["request_id"]
        self.assertNotEqual(first, second)

    def test_09_request_id_differs_from_bundle_id(self) -> None:
        result = self.request().response
        self.assertNotEqual(result["request_id"], result["bundle_id"])

    def test_10_standalone_request_works(self) -> None:
        result = self.request().response
        self.assertEqual("READY", result["state"])
        self.assertIsNone(result["turn_id"])

    def test_11_existing_turn_association_works(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        result = plane.request_knowledge_context(query="query", intent="ARCHITECTURE", turn_id=turn_id)
        self.assertEqual(turn_id, result.response["turn_id"])
        self.assertEqual(result.response["request_id"], plane.turn_knowledge_context(turn_id)["request_id"])

    def test_12_nonexistent_turn_fails(self) -> None:
        with self.assertRaises(ControlPlaneError) as caught:
            self.request(turn_id="0" * 24)
        self.assertEqual("KNOWLEDGE_TURN_NOT_FOUND", caught.exception.code)

    def test_13_missing_turn_is_not_created(self) -> None:
        before = len(self.plane._turns)
        with self.assertRaises(ControlPlaneError):
            self.request(turn_id="0" * 24)
        self.assertEqual(before, len(self.plane._turns))

    def test_14_success_lifecycle_exact(self) -> None:
        self.assertEqual(["REQUESTED", "RETRIEVING", "READY"], self.request().response["lifecycle"])

    def test_15_failed_lifecycle_exact(self) -> None:
        self.adapter.mode = "unavailable"
        self.assertEqual(["REQUESTED", "RETRIEVING", "FAILED"], self.request().response["lifecycle"])

    def test_16_ready_not_emitted_before_adapter_result(self) -> None:
        begun = self.plane.begin_knowledge_context(query="query", intent="ARCHITECTURE")
        request_id = begun.response["request_id"]
        observed = []
        self.adapter.callback = lambda: observed.append(self.plane.knowledge_context_status(request_id)["state"])
        completed = self.plane.retrieve_knowledge_context(request_id)
        self.assertEqual(["RETRIEVING"], observed)
        self.assertEqual("knowledge.context.ready", completed.events[0].method)

    def test_17_zero_sources_is_ready(self) -> None:
        self.adapter.mode = "zero"
        result = self.request().response
        self.assertEqual("READY", result["state"])
        self.assertEqual(0, result["source_count"])

    def test_18_adapter_unavailable_is_failed(self) -> None:
        self.adapter.mode = "unavailable"
        result = self.request().response
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("KNOWLEDGE_NOT_CONFIGURED", result["error"]["code"])

    def test_19_adapter_validation_failure_is_failed(self) -> None:
        self.adapter.mode = "validation_failure"
        result = self.request().response
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("KNOWLEDGE_VALIDATION_FAILED", result["error"]["code"])

    def test_20_ready_source_has_complete_provenance(self) -> None:
        selected = self.request().response["sources"][0]
        required = {
            "note_id", "relative_path", "knowledge_layer", "evidence_class", "authority",
            "status", "canonical", "selected_sections", "note_sha256",
        }
        self.assertTrue(required.issubset(selected))

    def test_21_anonymous_source_is_impossible(self) -> None:
        bad = source()
        del bad["note_id"]
        self.adapter.custom_sources = [bad]
        result = self.request().response
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("CONTRACT_VALIDATION_ERROR", result["error"]["code"])

    def test_22_absolute_vault_path_is_rejected(self) -> None:
        self.adapter.custom_sources = [source(relative_path="C:\\Users\\DNS\\Documents\\LocalCometVault\\note.md")]
        result = self.request().response
        self.assertEqual("FAILED", result["state"])

    def test_23_vault_revision_matches_adapter(self) -> None:
        self.assertEqual("sha256:" + "a" * 64, self.request().response["vault_revision"])

    def test_24_adapter_bundle_id_is_preserved(self) -> None:
        result = self.request().response
        expected = self.adapter.context_preview(
            "Как устроен Control Plane?", QueryIntent.ARCHITECTURE,
            max_context_chars=DEFAULT_CONTEXT_CHARS,
            max_results=DEFAULT_MAX_RESULTS,
            include_superseded=False,
        )
        self.assertEqual(expected["bundle_id"], result["bundle_id"])

    def test_25_same_content_same_bundle_different_request_ids(self) -> None:
        first = self.request().response
        second = self.request().response
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertEqual(first["bundle_id"], second["bundle_id"])

    def test_26_different_selected_content_changes_bundle(self) -> None:
        first = self.request().response["bundle_id"]
        self.adapter.content = "Different selected content."
        second = self.request().response["bundle_id"]
        self.assertNotEqual(first, second)

    def test_27_request_does_not_create_session(self) -> None:
        self.request()
        self.assertEqual(0, len(self.plane._sessions))

    def test_28_request_does_not_create_thread(self) -> None:
        self.request()
        self.assertEqual(0, len(self.plane._threads))

    def test_29_request_does_not_create_turn(self) -> None:
        self.request()
        self.assertEqual(0, len(self.plane._turns))

    def test_30_request_does_not_execute_tools(self) -> None:
        self.request()
        self.assertEqual(0, self.adapter.tool_executions)

    def test_31_request_does_not_call_shell(self) -> None:
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("shell called")):
            self.request()

    def test_32_request_does_not_use_network(self) -> None:
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network called")):
            self.request()

    def test_33_request_does_not_call_model(self) -> None:
        self.request()
        self.assertEqual(0, self.adapter.model_calls)

    def test_34_model_binding_remains_unchanged(self) -> None:
        binding = ModelBinding("p", "h", 1234, "m", "f", "d")
        before = asdict(binding)
        self.request()
        self.assertEqual(before, asdict(binding))

    def test_35_model_gateway_receives_no_request(self) -> None:
        gateway_calls = []
        self.request()
        self.assertEqual([], gateway_calls)

    def test_36_requested_event_emitted(self) -> None:
        self.assertEqual("knowledge.context.requested", self.request().events[0].method)

    def test_37_ready_event_emitted(self) -> None:
        self.assertEqual("knowledge.context.ready", self.request().events[-1].method)

    def test_38_failed_event_emitted(self) -> None:
        self.adapter.mode = "unavailable"
        self.assertEqual("knowledge.context.failed", self.request().events[-1].method)

    def test_39_event_sequence_monotonic(self) -> None:
        self.assertEqual([0, 1], [event.sequence for event in self.request().events])

    def test_40_full_note_contents_not_emitted(self) -> None:
        self.adapter.content = "FULL NOTE SECRET BODY"
        events = self.request().events
        self.assertNotIn("FULL NOTE SECRET BODY", json.dumps([event.payload for event in events]))

    def test_41_stale_result_cannot_overwrite_newer_turn_context(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        older = plane.begin_knowledge_context(query="older", intent="ARCHITECTURE", turn_id=turn_id)
        newer = plane.begin_knowledge_context(query="newer", intent="ARCHITECTURE", turn_id=turn_id)
        new_result = plane.retrieve_knowledge_context(newer.response["request_id"])
        old_result = plane.retrieve_knowledge_context(older.response["request_id"])
        self.assertEqual("FAILED", old_result.response["state"])
        self.assertEqual("KNOWLEDGE_STALE_RESULT", old_result.response["error"]["code"])
        self.assertEqual(new_result.response["request_id"], plane.turn_knowledge_context(turn_id)["request_id"])

    def test_42_duplicate_request_id_rejected(self) -> None:
        request_id = next_request_id()
        self.request(request_id=request_id)
        with self.assertRaises(ControlPlaneError) as caught:
            self.request(request_id=request_id)
        self.assertEqual("KNOWLEDGE_REQUEST_DUPLICATE", caught.exception.code)

    def test_43_failed_new_request_preserves_prior_success(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        first = plane.request_knowledge_context(query="first", intent="ARCHITECTURE", turn_id=turn_id)
        self.adapter.mode = "unavailable"
        second = plane.request_knowledge_context(query="second", intent="ARCHITECTURE", turn_id=turn_id)
        self.assertEqual("FAILED", second.response["state"])
        self.assertEqual(first.response["request_id"], plane.turn_knowledge_context(turn_id)["request_id"])

    def test_44_superseded_default_delegated_to_adapter(self) -> None:
        self.request()
        self.assertIs(False, self.adapter.calls[-1]["include_superseded"])

    def test_45_include_superseded_explicitly_delegated(self) -> None:
        self.request(include_superseded=True)
        self.assertIs(True, self.adapter.calls[-1]["include_superseded"])

    def test_46_evidence_class_semantics_preserved(self) -> None:
        self.adapter.custom_sources = [source(evidence_class="D", knowledge_layer="forensic_evidence")]
        selected = self.request(intent="HISTORY").response["sources"][0]
        self.assertEqual(("D", "forensic_evidence"), (selected["evidence_class"], selected["knowledge_layer"]))

    def test_47_founder_intent_remains_distinct(self) -> None:
        self.adapter.custom_sources = [source(knowledge_layer="founder_intent", authority="founder", evidence_class="C")]
        selected = self.request(intent="FOUNDER_INTENT").response["sources"][0]
        self.assertEqual("founder_intent", selected["knowledge_layer"])
        self.assertNotEqual("current_source_truth", selected["knowledge_layer"])

    def test_48_missing_request_rejected(self) -> None:
        with self.assertRaises(ControlPlaneError) as caught:
            self.plane.retrieve_knowledge_context("kreq:00000000-0000-4000-8000-999999999999")
        self.assertEqual("KNOWLEDGE_REQUEST_NOT_FOUND", caught.exception.code)

    def test_49_terminal_retrieval_is_idempotent(self) -> None:
        first = self.request()
        again = self.plane.retrieve_knowledge_context(first.response["request_id"])
        self.assertEqual((), again.events)
        self.assertEqual(first.response["bundle_id"], again.response["bundle_id"])

    def test_50_failed_result_has_structured_error(self) -> None:
        self.adapter.mode = "unavailable"
        error = self.request().response["error"]
        self.assertEqual({"code", "safe_message"}, set(error))

    def test_51_error_message_hides_absolute_path(self) -> None:
        self.adapter.mode = "path_error"
        payload = self.request().response
        self.assertNotIn("C:\\Users\\DNS", json.dumps(payload))
        self.assertIn("<USER_PATH>", payload["error"]["safe_message"])

    def test_52_result_contract_is_frozen(self) -> None:
        result = KnowledgeContextResult(
            next_request_id(), KnowledgeContextState.READY,
            vault_revision="sha256:" + "a" * 64,
            bundle_id="kb:" + "b" * 64,
            resolved_intent=QueryIntent.AUTO,
        )
        with self.assertRaises(FrozenInstanceError):
            result.state = KnowledgeContextState.FAILED

    def test_53_turn_summary_is_bounded(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        plane.request_knowledge_context(query="query", intent="ARCHITECTURE", turn_id=turn_id)
        summary = plane.dispatch("turn.status", {"turn_id": turn_id}, request_id="status").response
        self.assertNotIn("sources", json.dumps(summary))
        self.assertIn("knowledge_context", summary)

    def test_54_events_do_not_emit_query(self) -> None:
        query = "UNIQUE FULL QUERY CONTENT"
        result = self.request(query=query)
        self.assertNotIn(query, json.dumps([event.payload for event in result.events]))

    def test_55_exact_knowledge_event_families_registered(self) -> None:
        knowledge_events = {event for event in EVENT_METHODS if event.startswith("knowledge.")}
        self.assertEqual(
            {"knowledge.context.requested", "knowledge.context.ready", "knowledge.context.failed"},
            knowledge_events,
        )

    def test_56_external_methods_are_only_authorized_read_only_reviews(self) -> None:
        knowledge_methods = {
            method for method in CONTROL_PLANE_METHODS if method.startswith("knowledge.")
        }
        self.assertEqual(
            {
                "knowledge.review.decision.create",
                "knowledge.review.get",
                "knowledge.review.list",
                "knowledge.review.refresh",
                "knowledge.review.snapshot",
            },
            knowledge_methods,
        )
        self.assertNotIn("knowledge.review.register", knowledge_methods)
        self.assertNotIn("knowledge.review.upload", knowledge_methods)
        self.assertNotIn("knowledge.review.write", knowledge_methods)

    def test_57_no_persistent_request_storage_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            before = list(Path(directory).iterdir())
            with mock.patch.object(Path, "cwd", return_value=Path(directory)):
                self.request()
            self.assertEqual(before, list(Path(directory).iterdir()))

    def test_58_tauri_only_adds_fixed_read_only_review_commands(self) -> None:
        rust = (ROOT / "desktop/localcomet-desktop/src-tauri/src/control_plane.rs").read_text(encoding="utf-8")
        production_rust = rust.split("#[cfg(test)]", 1)[0]
        self.assertEqual(18, rust.count("#[tauri::command]"))
        self.assertIn("knowledge_review_list", production_rust)
        self.assertIn("knowledge_review_get", production_rust)
        self.assertIn('"knowledge.review.list"', production_rust)
        self.assertIn('"knowledge.review.get"', production_rust)
        self.assertIn("knowledge_review_snapshot", production_rust)
        self.assertIn("knowledge_review_refresh", production_rust)
        self.assertIn("knowledge_review_decision_create", production_rust)
        self.assertIn('"knowledge.review.snapshot"', production_rust)
        self.assertIn('"knowledge.review.refresh"', production_rust)
        self.assertIn('"knowledge.review.decision.create"', production_rust)
        self.assertNotIn("knowledge_review_register", production_rust)
        self.assertNotIn("knowledge.review.register", production_rust)
        self.assertNotIn("knowledge_context", production_rust)

    def test_59_no_frontend_bridge_added(self) -> None:
        frontend = (ROOT / "desktop/localcomet-desktop/src/lib/bridge/controlPlane.ts").read_text(encoding="utf-8")
        self.assertNotIn("knowledgeContext", frontend)

    def test_60_adapter_result_contract_failure_is_failed(self) -> None:
        self.adapter.mode = "invalid_contract"
        result = self.request().response
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("CONTRACT_VALIDATION_ERROR", result["error"]["code"])

    def test_61_turn_state_unchanged_by_knowledge(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        before = plane.dispatch("turn.status", {"turn_id": turn_id}, request_id="before").response["state"]
        plane.request_knowledge_context(query="query", intent="ARCHITECTURE", turn_id=turn_id)
        after = plane.dispatch("turn.status", {"turn_id": turn_id}, request_id="after").response["state"]
        self.assertEqual(before, after)

    def test_62_ready_warnings_preserved(self) -> None:
        self.assertEqual(["VALIDATION_WARNINGS:13"], self.request().response["warnings"])

    def test_63_request_defaults_are_adapter_bounds(self) -> None:
        self.request()
        call = self.adapter.calls[-1]
        self.assertEqual(DEFAULT_CONTEXT_CHARS, call["max_context_chars"])
        self.assertEqual(DEFAULT_MAX_RESULTS, call["max_results"])

    def test_64_stale_request_retained_as_historical_failed_state(self) -> None:
        plane, turn_id = plane_with_turn(self.adapter)
        old = plane.begin_knowledge_context(query="old", intent="ARCHITECTURE", turn_id=turn_id)
        plane.begin_knowledge_context(query="new", intent="ARCHITECTURE", turn_id=turn_id)
        plane.retrieve_knowledge_context(old.response["request_id"])
        status = plane.knowledge_context_status(old.response["request_id"])
        self.assertEqual("FAILED", status["state"])

    def test_65_request_identity_factory_uses_kreq_uuid_form(self) -> None:
        generated = DesktopControlPlane(knowledge_adapter=self.adapter).begin_knowledge_context(
            query="query", intent="AUTO"
        ).response["request_id"]
        self.assertTrue(generated.startswith("kreq:"))
        self.assertEqual(41, len(generated))

    def test_66_raw_query_is_not_echoed_in_result_status(self) -> None:
        query = "C:\\Users\\DNS\\Documents\\LocalCometVault\\private.md"
        payload = self.request(query=query).response
        self.assertNotIn(query, json.dumps(payload, ensure_ascii=False))


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(KnowledgeControlPlaneTests)
    count = suite.countTestCases()
    if count < 45:
        raise AssertionError(f"focused e5 test count too low: {count}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"ALL v6.84.5.1e5 KNOWLEDGE CONTROL PLANE TESTS PASSED ({count} tests)")


if __name__ == "__main__":
    main()
