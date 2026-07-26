# Полный исходный код (продолжение)

### ПУТЬ: tools/test_v6845_model_gateway.py (386 строк, 16471 байт)

````python
#!/usr/bin/env python
from __future__ import annotations

import json
import os
import subprocess
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
    _assert(payload["control_plane_version"] == DESKTOP_CONTROL_PLANE_VERSION == "v6.84.6", "Control Plane version not aligned")
    _assert(payload["control_plane_version"] != "v6.84.4", "stale Control Plane version still emitted")
    _assert(payload["model_gateway_version"] == LOCAL_MODEL_GATEWAY_VERSION == "v6.84.5", "Model Gateway release changed")
    _assert(IPC_PROTOCOL == "localcomet.ipc" and IPC_PROTOCOL_VERSION == "1.0", "IPC protocol changed")
    _assert(DESKTOP_SIDECAR_RUNTIME_VERSION == "v6.84.3", "Sidecar runtime version changed")

    bridge_text = (ROOT / "desktop" / "localcomet-desktop" / "src" / "lib" / "bridge" / "controlPlane.ts").read_text(encoding="utf-8")
    bridge_test_text = (ROOT / "desktop" / "localcomet-desktop" / "tests" / "control-plane.test.ts").read_text(encoding="utf-8")
    _assert("object.control_plane_version !== 'v6.84.6'" in bridge_text, "exact Control Plane validation changed")
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
    tracked = subprocess.run(
        ["git", "ls-files", "--", "desktop/localcomet-desktop/node_modules", "desktop/localcomet-desktop/src-tauri/target"],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    _assert(tracked.returncode == 0 and tracked.stdout.strip() == "", "build artifacts tracked by git")
    if os.environ.get("LOCALCOMET_PACKAGING_CHECK") == "1":
        _assert(not (desktop / "node_modules").exists(), "source node_modules present (packaging check)")
        _assert(not (desktop / "src-tauri" / "target").exists(), "source src-tauri/target present (packaging check)")


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
````

### ПУТЬ: tools/test_v6846_knowledge_operations_command_center.py (573 строк, 24183 байт)

````python
"""Focused v6.84.6 Human-Governed Knowledge Operations Command Center tests."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import (
    CONTROL_PLANE_METHODS,
    ControlPlaneError,
    ControlPlaneLimits,
    DesktopControlPlane,
    validate_control_plane_payload,
)
from modules.knowledge_contract_ru import KnowledgeAdapterError, KnowledgeErrorCode
from modules.knowledge_change_review_decision_ru import CONTRACT_VERSION as DECISION_CONTRACT
from modules.knowledge_change_review_ru import CONTRACT_VERSION as REVIEW_CONTRACT, ReviewStatus
import tools.test_v68451e9d_knowledge_review_producer as producer_fixtures

REV_A = producer_fixtures.REV_A
REV_B = producer_fixtures.REV_B


class _ReadOnlyAdapter:
    """Model the real adapter distinction between cached and filesystem revisions."""

    def __init__(
        self,
        cached_revision: str | None = REV_A,
        filesystem_revision: str | None | object = ...,
        *,
        refresh_failure: bool = False,
    ) -> None:
        self.cached_revision = cached_revision
        self.filesystem_revision = (
            cached_revision if filesystem_revision is ... else filesystem_revision
        )
        self.refresh_failure = refresh_failure
        self.refresh_calls = 0

    def status(self) -> dict[str, object]:
        return {
            "state": "READY" if self.cached_revision else "NOT_CONFIGURED",
            "vault_revision": self.cached_revision,
            "last_error_code": (
                None if self.cached_revision else "KNOWLEDGE_NOT_CONFIGURED"
            ),
        }

    def refresh(self) -> dict[str, object]:
        self.refresh_calls += 1
        if self.refresh_failure:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                "test refresh failure",
            )
        self.cached_revision = self.filesystem_revision
        return {
            "state": "READY" if self.cached_revision else "NOT_CONFIGURED",
            "previous_revision": None,
            "current_revision": self.cached_revision,
            "changed": True,
        }


class KnowledgeOperationsCommandCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = producer_fixtures.KnowledgeReviewProducerTests()

    def make_plane(
        self,
        *,
        cached_revision: str | None = REV_A,
        filesystem_revision: str | None | object = ...,
        refresh_failure: bool = False,
        refresh_available: bool = True,
        maximum_decisions: int = 128,
    ) -> tuple[DesktopControlPlane, _ReadOnlyAdapter]:
        adapter = _ReadOnlyAdapter(
            cached_revision,
            filesystem_revision,
            refresh_failure=refresh_failure,
        )
        if not refresh_available:
            adapter.refresh = None  # type: ignore[method-assign]
        limits = ControlPlaneLimits(maximum_knowledge_review_decisions=maximum_decisions)
        return DesktopControlPlane(limits=limits, knowledge_adapter=adapter), adapter

    def produce(self, plane: DesktopControlPlane, kind: str = "create"):
        inputs = self.builder.make_inputs(kind)
        return plane.produce_knowledge_review(*inputs)

    def dispatch(self, plane: DesktopControlPlane, method: str, payload: dict[str, object]):
        return plane.dispatch(method, payload, request_id=f"test-{method}").response

    def decision_payload(
        self,
        artifact,
        *,
        decision: str = "APPROVE",
        comment: str = "",
        proposal_id: str | None = None,
        review_identity: str | None = None,
        change_identity: str | None | object = ...,
        revision: str | None = None,
    ) -> dict[str, object]:
        exact_change = artifact.change_identity if change_identity is ... else change_identity
        return {
            "review_contract_version": REVIEW_CONTRACT,
            "proposal_id": proposal_id or artifact.proposal_id,
            "review_artifact_identity": review_identity or artifact.review_artifact_identity,
            "change_identity": exact_change,
            "observed_vault_revision": revision or artifact.observed_vault_revision,
            "decision": decision,
            "comment": comment,
            "actor_identifier": "local-reviewer",
            "actor_display_name": "Local Reviewer",
            "actor_source": "LOCALCOMET_REVIEW_CENTER",
        }

    def test_001_exact_command_surface(self) -> None:
        review_methods = {
            method for method in CONTROL_PLANE_METHODS if method.startswith("knowledge.review.")
        }
        self.assertEqual(
            {
                "knowledge.review.decision.create",
                "knowledge.review.get",
                "knowledge.review.list",
                "knowledge.review.refresh",
                "knowledge.review.snapshot",
            },
            review_methods,
        )
        for forbidden in ("register", "upload", "write", "publish", "delete", "clear"):
            self.assertFalse(any(forbidden in method for method in review_methods))

    def test_002_snapshot_default_empty_and_hard_stop(self) -> None:
        plane, _ = self.make_plane()
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual("localcomet.knowledge-review-snapshot/1.0", value["contract"])
        self.assertEqual(0, value["inbox_count"])
        self.assertEqual([], value["review_states"])
        self.assertTrue(value["hard_stop"])
        self.assertFalse(value["persistence"])
        self.assertFalse(value["vault_write_authority"])
        self.assertFalse(value["publication_authority"])

    def test_003_snapshot_marks_fresh_clear_review(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, value["inbox_count"])
        self.assertEqual(0, value["stale_count"])
        self.assertEqual(artifact.review_artifact_identity, value["review_states"][0]["review_artifact_identity"])
        self.assertIs(value["review_states"][0]["stale"], False)

    def test_004_snapshot_marks_stale_review(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        adapter.cached_revision = REV_B
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, value["stale_count"])
        self.assertEqual(artifact.review_artifact_identity, value["review_states"][0]["review_artifact_identity"])
        self.assertIs(value["review_states"][0]["stale"], True)

    def test_005_unknown_freshness_is_explicit_null(self) -> None:
        plane, _ = self.make_plane(cached_revision=None, filesystem_revision=None)
        self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertFalse(value["freshness_known"])
        self.assertIsNone(value["current_vault_revision"])
        self.assertIsNone(value["review_states"][0]["stale"])

    def test_006_refresh_calls_read_only_adapter(self) -> None:
        plane, adapter = self.make_plane()
        self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.refresh", {})
        self.assertEqual(1, adapter.refresh_calls)
        self.assertTrue(value["refresh_requested"])
        self.assertTrue(value["refresh_succeeded"])
        self.assertEqual("localcomet.knowledge-review-refresh/1.0", value["contract"])

    def test_007_real_approve_creates_exact_e9c_decision(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        value = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact),
        )
        decision = value["decision"]
        self.assertEqual(DECISION_CONTRACT, decision["contract_version"])
        self.assertEqual(artifact.proposal_id, decision["proposal_id"])
        self.assertEqual(artifact.review_artifact_identity, decision["review_artifact_identity"])
        self.assertEqual(artifact.change_identity, decision["change_identity"])
        self.assertEqual("APPROVE", decision["decision"])
        self.assertTrue(decision["hard_stop"])
        self.assertFalse(value["vault_modified"])
        self.assertFalse(value["persistence"])
        self.assertFalse(value["publication"])
        self.assertEqual(1, adapter.refresh_calls)
        self.assertEqual(artifact.observed_vault_revision, adapter.cached_revision)

    def test_008_duplicate_decision_is_idempotent(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact, decision="REJECT", comment="exact")
        first = self.dispatch(plane, "knowledge.review.decision.create", payload)
        second = self.dispatch(plane, "knowledge.review.decision.create", payload)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["decision"]["decision_identity"], second["decision"]["decision_identity"])
        self.assertEqual(2, adapter.refresh_calls)
        self.assertEqual(
            1,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_009_stale_revision_blocks_every_decision(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_A, filesystem_revision=REV_B)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("policy_blocked", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_025_refresh_failure_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(refresh_failure=True)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_026_refresh_unavailable_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(refresh_available=False)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(0, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_027_unknown_fresh_revision_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(
            cached_revision=REV_A,
            filesystem_revision=None,
        )
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_028_decision_path_never_uses_cached_status_as_freshness_authority(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_A, filesystem_revision=REV_B)
        artifact = self.produce(plane)
        status_before = adapter.status()
        self.assertEqual(REV_A, status_before["vault_revision"])
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="REJECT"),
            )
        self.assertEqual("policy_blocked", context.exception.code)
        self.assertEqual(1, adapter.refresh_calls)
        self.assertEqual(REV_B, adapter.cached_revision)

    def test_010_blocked_approve_is_forbidden(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_B, filesystem_revision=REV_B)
        artifact = self.produce(plane, "blocked")
        adapter.filesystem_revision = artifact.observed_vault_revision
        self.assertIs(artifact.status, ReviewStatus.BLOCKED)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="APPROVE"),
            )
        self.assertEqual("policy_blocked", context.exception.code)

    def test_011_blocked_reject_and_request_changes_remain_available(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_B, filesystem_revision=REV_B)
        artifact = self.produce(plane, "blocked")
        adapter.filesystem_revision = artifact.observed_vault_revision
        reject = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        request = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(
                artifact,
                decision="REQUEST_CHANGES",
                comment="Resolve the blocking finding.",
            ),
        )
        self.assertIsNone(reject["decision"]["change_identity"])
        self.assertIsNone(request["decision"]["change_identity"])

    def test_012_request_changes_requires_meaningful_comment(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(
                    artifact,
                    decision="REQUEST_CHANGES",
                    comment=" \t ",
                ),
            )
        self.assertEqual("invalid_payload", context.exception.code)

    def test_013_proposal_identity_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, proposal_id="kprop:" + "f" * 64),
            )

    def test_014_review_identity_mismatch_cannot_select_another_artifact(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, review_identity="kreview:" + "f" * 64),
            )
        self.assertEqual("request_not_found", context.exception.code)

    def test_015_change_identity_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, change_identity="kchange:" + "f" * 64),
            )

    def test_016_observed_revision_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, revision=REV_B),
            )

    def test_017_payload_extra_field_rejected(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact)
        payload["unexpected"] = True
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(plane, "knowledge.review.decision.create", payload)
        self.assertEqual("invalid_payload", context.exception.code)

    def test_018_decision_capacity_fails_without_eviction(self) -> None:
        plane, _ = self.make_plane(maximum_decisions=1)
        artifact = self.produce(plane)
        first = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT", comment="first"),
        )
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="REJECT", comment="second"),
            )
        self.assertEqual("busy", context.exception.code)
        snapshot = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, snapshot["session_decision_count"])
        self.assertTrue(first["decision"]["decision_identity"].startswith("kdecision:"))

    def test_019_status_exposes_only_bounded_session_counts(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        status = self.dispatch(plane, "app.status", {})
        self.assertEqual(1, status["counts"]["knowledge_reviews"])
        self.assertEqual(1, status["counts"]["human_review_decisions"])
        serialized = json.dumps(status).lower()
        self.assertNotIn("kdecision:", serialized)
        self.assertNotIn("actor_identifier", serialized)
        self.assertNotIn("comment", serialized)

    def test_020_production_owner_has_no_write_or_persistence_call(self) -> None:
        source = inspect.getsource(DesktopControlPlane._create_knowledge_review_decision)
        for forbidden in (
            "open(",
            "write_text",
            "write_bytes",
            "sqlite",
            "requests.",
            "subprocess",
            "publish",
            "merge(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"vault_modified": False', source)
        self.assertIn('"persistence": False', source)
        self.assertIn('"publication": False', source)


    def test_021_payload_validation_enforces_utf8_and_fixed_actor_source(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact, decision="REJECT")

        oversized_comment = dict(payload, comment="😀" * 1_025)
        self.assertIn(
            "invalid_comment",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                oversized_comment,
            ),
        )

        oversized_actor = dict(payload, actor_identifier="😀" * 129)
        self.assertIn(
            "invalid_actor_identifier",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                oversized_actor,
            ),
        )

        wrong_source = dict(payload, actor_source="UNTRUSTED_FRONTEND")
        self.assertIn(
            "invalid_actor_source",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                wrong_source,
            ),
        )

    def test_022_payload_validation_enforces_decision_comment_and_change_policy(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)

        request_changes = self.decision_payload(
            artifact,
            decision="REQUEST_CHANGES",
            comment="   ",
        )
        self.assertIn(
            "request_changes_comment_required",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                request_changes,
            ),
        )


    def test_023_session_reset_is_a_new_empty_control_plane_instance(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        self.assertEqual(
            self.dispatch(plane, "knowledge.review.snapshot", {})[
                "session_decision_count"
            ],
            1,
        )

        replacement, _ = self.make_plane()
        snapshot = self.dispatch(replacement, "knowledge.review.snapshot", {})
        self.assertEqual(snapshot["inbox_count"], 0)
        self.assertEqual(snapshot["session_decision_count"], 0)

    def test_024_decision_response_contains_only_bounded_evidence_and_hard_stop(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        result = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertLess(len(serialized.encode("utf-8")), 262_144)
        self.assertTrue(result["hard_stop"])
        self.assertFalse(result["vault_modified"])
        self.assertFalse(result["persistence"])
        self.assertFalse(result["publication"])
        for forbidden in (
            "vault_root",
            "absolute_path",
            "write_file",
            "publish",
            "execute",
            "environment",
        ):
            self.assertNotIn(forbidden, serialized.lower())



if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
````

### ПУТЬ: tools/test_v684_action_executor.py (437 строк, 30155 байт)

````python
#!/usr/bin/env python
from __future__ import annotations

import ast
import importlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _raises(fn, message: str) -> None:
    try:
        fn()
    except Exception:
        return
    raise AssertionError(message)


def _paths_under(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _import_executor():
    sys.modules.pop("modules.autonomous_action_executor_ru", None)
    return importlib.import_module("modules.autonomous_action_executor_ru")


def _policy(level: str = "LEVEL_2_SAFE_AUTOMATION", root: Path | None = None, actions: tuple[str, ...] = ("analyze", "inspect", "verify")):
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    root = root or ROOT
    return replace(policy_mod.default_autonomy_policy(root), level=getattr(policy_mod.AutonomyLevel, level), allowed_actions=actions)


def _proposal(action_type: str, target: str, **updates: Any):
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    data = {
        "action_id": "action_01",
        "action_type": action_type,
        "target": target,
        "arguments": {},
        "read_only": action_type in {"inspect", "analyze", "verify", "test"},
        "reversible": True,
        "expected_original_sha256": None,
        "estimated_changed_files": 0,
        "estimated_changed_lines": 0,
        "estimated_subprocesses": 0,
        "estimated_output_bytes": 0,
        "requires_network": False,
        "requires_elevation": False,
    }
    data.update(updates)
    return policy_mod.ActionProposal(**data)


def _action(action_type: str, operation: str, target: str, params: dict[str, Any] | None = None, **updates: Any):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    return executor.ExecutableAction(_proposal(action_type, target, **updates), operation, params or {})


def _grant(action: Any, config: Any):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    return executor.ApprovalGrant(action.proposal.action_id, executor.compute_action_fingerprint(action, config), True)


def _result(policy: Any, action: Any, config: Any, approval: Any | None = None, usage: Any | None = None, kill: Any | None = None):
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    res = executor.execute_action(policy, action, config=config, approval=approval, usage=usage, kill_switch=kill, now=lambda: "2026-07-13T12:00:00Z", monotonic=lambda: 10.0)
    return executor.serialize_action_result(res)


def _fixture_root() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="lc_v684_exec_")


def _write_manifest(root: Path, tests: list[str] | None = None) -> None:
    payload = {
        "release": "fixture",
        "project": "fixture",
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": [],
        "tests": sorted(tests or []),
        "tools": [],
    }
    (root / "localcomet_runtime_manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_import_side_effects() -> None:
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
        executor = _import_executor()
    finally:
        subprocess.Popen, socket.socket, urllib.request.urlopen = originals
    after = _paths_under(ROOT)
    _assert(executor.AUTONOMOUS_ACTION_EXECUTOR_VERSION == "v6.84", "Executor version changed.")
    _assert(before == after, "Executor import created or modified files.")
    _assert(calls == [], "Executor import used subprocess or network.")
    _assert(env_before == dict(os.environ), "Executor import mutated environment.")
    _assert({t.ident for t in threading.enumerate()} == threads_before, "Executor import started a thread.")


def test_configuration_and_validation() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "tools").mkdir()
        cfg = executor.default_executor_config(root)
        payload = executor.serialize_executor_config(cfg)
        _assert(payload["root"] == "<PROJECT_ROOT>", "Root was not redacted.")
        _assert(str(root) not in json.dumps(payload), "Full root leaked.")
        _assert(cfg.allow_test_execution is False and cfg.allow_project_writes is False and cfg.allow_temp_writes is False, "Default config is not read-only.")
        cfg2 = executor.ExecutorConfig(root=root, write_allowlist=("b.py", "a.py", "a.py"), test_allowlist=("tools/test_b.py", "tools/test_a.py"))
        _assert(cfg2.write_allowlist == ("a.py", "b.py"), "Write allowlist not sorted unique.")
        _assert(cfg2.test_allowlist == ("tools/test_a.py", "tools/test_b.py"), "Test allowlist not sorted unique.")
        absolute_allowlist = "C:" + "\\x.py"
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=(absolute_allowlist,)), "Absolute allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=("../x.py",)), "Traversal allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=(".git/config",)), "Protected allowlist accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_read_bytes=True), "Boolean limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_write_bytes=-1), "Negative limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_timeout_seconds=math.inf), "Non-finite limit accepted.")
        _raises(lambda: executor.ExecutorConfig(root=root, max_write_bytes=11 * 1024 * 1024), "Hard limit not enforced.")
        _raises(lambda: executor.executor_config_from_dict({"root": root, "extra": 1}), "Unknown configuration key accepted.")


def test_action_mapping_fingerprint_and_approval() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "a.txt").write_text("hello", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        supported = {
            "read_file": ("inspect", "a.txt", {}),
            "list_directory": ("inspect", ".", {"include_hidden": True}),
            "search_text": ("analyze", ".", {"query": "hello"}),
            "syntax_check": ("verify", "a.py", {}),
            "run_allowlisted_test": ("test", "tools/test_ok.py", {"timeout_seconds": 1}),
            "create_temp_file": ("create_temp", "tmp/new.txt", {"content": "x"}),
            "write_allowlisted_file": ("edit_file", "a.txt", {"content": "x"}),
            "apply_exact_patch": ("apply_patch", "a.txt", {"old_text": "hello", "new_text": "hi"}),
        }
        for op, (kind, target, params) in supported.items():
            action = _action(kind, op, target, params)
            if op == "syntax_check":
                (root / "a.py").write_text("x=1\n", encoding="utf-8")
            denied = _result(_policy("LEVEL_1_PLAN_ONLY", root=root), action, cfg)
            _assert(denied["status"] == "DENIED", "LEVEL_1 executed an operation.")
        unknown = _result(policy, _action("inspect", "shell", "a.txt"), cfg)
        _assert(unknown["error_category"] == "unsupported_operation" and unknown["executed"] is False, "Unknown operation was not denied.")
        mismatch = _result(policy, _action("inspect", "search_text", "a.txt", {"query": "hello"}), cfg)
        _assert(mismatch["error_category"] == "invalid_action", "Mapping mismatch was not denied.")
        for params in ({"extra": 1}, {"query": [[[[[[1]]]]]]}, {"query": "x" * 5000}, {"query": float("nan")}, {"query": Path("x")}, {"query": lambda: None}):
            data = _result(policy, _action("analyze", "search_text", ".", params), cfg)
            _assert(data["error_category"] == "unsupported_parameters", "Unsafe parameters were not denied.")
        net = _result(policy, _action("inspect", "read_file", "a.txt", requires_network=True), cfg)
        elev = _result(policy, _action("inspect", "read_file", "a.txt", requires_elevation=True), cfg)
        _assert(net["error_category"] == "invalid_action" and elev["error_category"] == "invalid_action", "Network/elevation proposal accepted.")
        a1 = _action("inspect", "read_file", "a.txt", {"z": 1, "a": 2})
        a2 = _action("inspect", "read_file", "a.txt", {"a": 2, "z": 1})
        fp = executor.compute_action_fingerprint(a1, cfg)
        _assert(fp == executor.compute_action_fingerprint(a2, cfg) and len(fp) == 64, "Fingerprint is not canonical.")
        _assert(fp != executor.compute_action_fingerprint(_action("inspect", "read_file", "b.txt"), cfg), "Target change did not affect fingerprint.")
        _assert(fp != executor.compute_action_fingerprint(_action("inspect", "list_directory", "."), cfg), "Operation change did not affect fingerprint.")
        changed_id = replace(a1, proposal=replace(a1.proposal, action_id="action_02"))
        _assert(fp != executor.compute_action_fingerprint(changed_id, cfg), "Action ID change did not affect fingerprint.")
        grant = _grant(a1, cfg)
        _assert(executor.validate_approval_grant(a1, cfg, grant)["valid"] is True, "Exact approval did not validate.")
        _assert(executor.validate_approval_grant(a1, cfg, None)["valid"] is False, "Missing approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, action_id="other"))["valid"] is False, "Wrong action approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, action_fingerprint="f" * 64))["valid"] is False, "Wrong fingerprint validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, granted=False))["valid"] is False, "Revoked approval validated.")
        _assert(executor.validate_approval_grant(a1, cfg, replace(grant, scope="GLOBAL"))["valid"] is False, "Invalid approval scope validated.")


def test_path_policy_and_kill_switches() -> None:
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text, _fixture_root() as external_text:
        root = Path(temp_text)
        external = Path(external_text)
        (root / "safe.txt").write_text("ok", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        good = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg)
        _assert(good["status"] == "SUCCESS" and good["target"] == "<PROJECT_ROOT>/safe.txt", "Safe read failed.")
        bads = ("../x", "..\\x", "C:" + "\\Windows\\x", "C:" + "Windows\\x", "\\\\server\\share", "/etc/passwd", "bad\x00path", "CON")
        for bad in bads:
            data = _result(policy, _action("inspect", "read_file", bad), cfg)
            _assert(data["status"] == "DENIED" and data["executed"] is False, "Unsafe path was not denied.")
        for protected in (".git/config", ".incident_backup/x", ".localcomet/reviewer/x", ".localcomet/policies/x", ".localcomet/autonomy/STOP"):
            data = _result(policy, _action("inspect", "read_file", protected), cfg)
            _assert(data["error_category"] in {"protected_path", "unsafe_path"}, "Protected path was not denied.")
        link = root / "link_out"
        try:
            link.symlink_to(external, target_is_directory=True)
            data = _result(policy, _action("inspect", "read_file", "link_out/file.txt"), cfg)
            _assert(data["status"] == "DENIED", "Symlink escape was not denied.")
            parent = root / "parent_link"
            parent.symlink_to(external, target_is_directory=True)
            _raises(lambda: executor.ExecutorConfig(root=root, write_allowlist=("parent_link/new.txt",), allow_project_writes=True), "Symlink parent allowlist accepted.")
        except OSError:
            print("SKIP symlink path tests: platform refused test symlink")
        kill = policy_mod.KillSwitchStatus(True, policy_mod.KillSwitchMode.DISABLE, "disabled")
        data = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg, kill=kill)
        _assert(data["error_category"] == "kill_switch_active" and data["executed"] is False, "Kill switch did not deny read.")
        for mode in (policy_mod.KillSwitchMode.STOP_FILE, policy_mod.KillSwitchMode.PAUSE):
            data = _result(policy, _action("inspect", "read_file", "safe.txt"), cfg, kill=policy_mod.KillSwitchStatus(True, mode, "active"))
            _assert(data["error_category"] == "kill_switch_active", "Kill switch mode did not deny.")


def test_read_list_search_and_syntax() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "dir").mkdir()
        secret = "sk" + "-" + "A" * 16
        (root / "dir" / "a.txt").write_text("Alpha\nneedle " + secret + "\n", encoding="utf-8")
        (root / "dir" / ".hidden").write_text("hide", encoding="utf-8")
        (root / "dir" / "b.bin").write_bytes(b"a\x00b")
        (root / "ok.py").write_text("x = 1\n", encoding="utf-8")
        (root / "bad.py").write_text("x =\n", encoding="utf-8")
        cfg = executor.ExecutorConfig(root=root, max_directory_entries=10, max_search_matches=10)
        policy = _policy(root=root)
        read = _result(policy, _action("inspect", "read_file", "dir/a.txt"), cfg)
        _assert(read["status"] == "SUCCESS" and read["original_sha256"], "Read did not succeed.")
        _assert(secret not in json.dumps(read) and "<REDACTED_SECRET>" in json.dumps(read), "Read secret was not redacted.")
        missing = _result(policy, _action("inspect", "read_file", "missing.txt"), cfg)
        oversized = _result(policy, _action("inspect", "read_file", "dir/a.txt"), executor.ExecutorConfig(root=root, max_read_bytes=2))
        binary = _result(policy, _action("inspect", "read_file", "dir/b.bin"), cfg)
        protected = _result(policy, _action("inspect", "read_file", ".git/config"), cfg)
        _assert(missing["error_category"] == "target_missing" and oversized["error_category"] == "size_limit" and binary["error_category"] == "binary_file" and protected["status"] == "DENIED", "Read failure categories changed.")
        listing = _result(policy, _action("inspect", "list_directory", "dir", {"include_hidden": False}), cfg)
        names = [entry["name"] for entry in listing["details"]["entries"]]
        _assert(names == sorted(names, key=str.lower) and ".hidden" not in names, "Directory listing not sorted or hidden filtering failed.")
        limit_listing = _result(policy, _action("inspect", "list_directory", "dir"), executor.ExecutorConfig(root=root, max_directory_entries=1))
        _assert(limit_listing["error_category"] == "size_limit", "Directory entry limit not enforced.")
        search = _result(policy, _action("analyze", "search_text", "dir", {"query": "NEEDLE", "case_sensitive": False}), cfg)
        _assert(search["details"]["matches"] and secret not in json.dumps(search), "Search did not redact match.")
        case = _result(policy, _action("analyze", "search_text", "dir", {"query": "NEEDLE", "case_sensitive": True}), cfg)
        literal = _result(policy, _action("analyze", "search_text", "dir", {"query": "needle.*"}), cfg)
        empty = _result(policy, _action("analyze", "search_text", "dir", {"query": ""}), cfg)
        _assert(case["details"]["matches"] == [] and literal["details"]["matches"] == [] and empty["status"] == "DENIED", "Search literal/case/empty behavior changed.")
        syntax_ok = _result(policy, _action("verify", "syntax_check", "ok.py"), cfg)
        syntax_bad = _result(policy, _action("verify", "syntax_check", "bad.py"), cfg)
        non_py = _result(policy, _action("verify", "syntax_check", "dir/a.txt"), cfg)
        _assert(syntax_ok["details"]["syntax_ok"] is True, "Valid syntax failed.")
        _assert(syntax_bad["details"]["syntax_ok"] is False and syntax_bad["details"]["filename"] == "<PROJECT_ROOT>/bad.py", "Invalid syntax details changed.")
        _assert(non_py["status"] == "DENIED" and not (root / "__pycache__").exists(), "Syntax check accepted non-Python or created pycache.")


def test_allowlisted_test_execution() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        tools = root / "tools"
        tools.mkdir()
        (tools / "test_ok.py").write_text("print('ok')\n", encoding="utf-8")
        (tools / "test_fail.py").write_text("import sys\nprint('bad')\nsys.exit(3)\n", encoding="utf-8")
        (tools / "test_timeout.py").write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
        (tools / "test_output.py").write_text("print('X' * 5000)\n", encoding="utf-8")
        secret = "ghp" + "_" + "B" * 16
        (tools / "test_secret.py").write_text("print('" + secret + "')\n", encoding="utf-8")
        _write_manifest(root, ["tools/test_ok.py", "tools/test_fail.py", "tools/test_timeout.py", "tools/test_output.py", "tools/test_secret.py"])
        policy = _policy("LEVEL_2_SAFE_AUTOMATION", root=root, actions=("analyze", "inspect", "test", "verify"))
        default = executor.default_executor_config(root)
        action = _action("test", "run_allowlisted_test", "tools/test_ok.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        _assert(_result(policy, action, default)["status"] == "DENIED", "Default config launched test.")
        cfg = executor.ExecutorConfig(root=root, test_allowlist=("tools/test_ok.py", "tools/test_fail.py", "tools/test_timeout.py", "tools/test_output.py", "tools/test_secret.py"), allow_test_execution=True, max_subprocess_output_bytes=1000)
        _assert(_result(policy, action, cfg, approval=_grant(action, cfg))["status"] == "SUCCESS", "Allowlisted test failed.")
        fail = _action("test", "run_allowlisted_test", "tools/test_fail.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        timeout = _action("test", "run_allowlisted_test", "tools/test_timeout.py", {"timeout_seconds": 0.1}, estimated_subprocesses=1, estimated_output_bytes=20)
        output = _action("test", "run_allowlisted_test", "tools/test_output.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        secret_action = _action("test", "run_allowlisted_test", "tools/test_secret.py", {"timeout_seconds": 1}, estimated_subprocesses=1, estimated_output_bytes=20)
        _assert(_result(policy, fail, cfg, approval=_grant(fail, cfg))["error_category"] == "subprocess_failed", "Failing test category changed.")
        _assert(_result(policy, timeout, cfg, approval=_grant(timeout, cfg))["status"] == "TIMEOUT", "Timeout did not terminate.")
        tiny = replace(cfg, max_subprocess_output_bytes=50)
        _assert(_result(policy, output, tiny, approval=_grant(output, tiny))["error_category"] == "output_limit", "Output limit not enforced.")
        redacted = _result(policy, secret_action, cfg, approval=_grant(secret_action, cfg))
        _assert(secret not in json.dumps(redacted), "Subprocess output leaked a secret fixture.")
        denied_action = _action("test", "run_allowlisted_test", "tools/not_manifest.py", {"timeout_seconds": 1}, estimated_subprocesses=1)
        denied = _result(policy, denied_action, cfg, approval=_grant(denied_action, cfg))
        _assert(denied["executed"] is False and denied["error_category"] == "test_not_allowlisted", "Non-manifest test was not denied.")


def test_writes_patches_hashes_and_rollback() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "tmp").mkdir()
        (root / "src").mkdir()
        existing = root / "src" / "file.txt"
        existing.write_text("old text\n", encoding="utf-8")
        before_hash = executor._sha256_file(existing)
        cfg = executor.ExecutorConfig(root=root, temporary_roots=(root / "tmp",), write_allowlist=("src/file.txt", "src/new.txt"), allow_project_writes=True, allow_temp_writes=True)
        policy = _policy("LEVEL_3_CONTROLLED_EDIT", root=root, actions=("analyze", "apply_patch", "create_file", "create_temp", "edit_file", "inspect", "test", "verify"))
        temp_action = _action("create_temp", "create_temp_file", "tmp/t.txt", {"content": "temp"}, read_only=False, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, temp_action, cfg, approval=_grant(temp_action, cfg))["status"] == "SUCCESS", "Temp creation failed.")
        blocked_secret = _action("create_temp", "create_temp_file", "tmp/s.txt", {"content": "token=" + "C" * 16}, read_only=False, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, blocked_secret, cfg, approval=_grant(blocked_secret, cfg))["error_category"] == "secret_content", "Secret temp content was not blocked.")
        new_action = _action("create_file", "write_allowlisted_file", "src/new.txt", {"content": "new\n"}, read_only=False, expected_original_sha256="0" * 64, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, new_action, cfg, approval=_grant(new_action, cfg))["status"] == "SUCCESS", "New allowlisted file failed.")
        wrong = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "bad\n"}, read_only=False, expected_original_sha256="b" * 64, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, wrong, cfg, approval=_grant(wrong, cfg))["error_category"] == "hash_mismatch", "Wrong hash did not block.")
        _assert(existing.read_text(encoding="utf-8") == "old text\n", "Wrong-hash write changed bytes.")
        edit = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "new text\n"}, read_only=False, expected_original_sha256=before_hash, estimated_changed_files=1, estimated_changed_lines=1)
        edited = _result(policy, edit, cfg, approval=_grant(edit, cfg))
        _assert(edited["status"] == "SUCCESS" and edited["result_sha256"] == executor._sha256_file(existing), "Correct-hash edit failed.")
        _assert(not list((root / "src").glob("*.localcomet-v684-*.tmp")), "Staging artifact remained.")
        patch_hash = executor._sha256_file(existing)
        patch = _action("apply_patch", "apply_exact_patch", "src/file.txt", {"old_text": "new", "new_text": "patched"}, read_only=False, expected_original_sha256=patch_hash, estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, patch, cfg, approval=_grant(patch, cfg))["status"] == "SUCCESS", "Exact patch failed.")
        missing = _action("apply_patch", "apply_exact_patch", "src/file.txt", {"old_text": "absent", "new_text": "x"}, read_only=False, expected_original_sha256=executor._sha256_file(existing), estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, missing, cfg, approval=_grant(missing, cfg))["error_category"] == "patch_not_found", "Missing patch text category changed.")
        dup_file = root / "src" / "dup.txt"
        dup_file.write_text("x x", encoding="utf-8")
        dup_cfg = replace(cfg, write_allowlist=("src/dup.txt",))
        dup = _action("apply_patch", "apply_exact_patch", "src/dup.txt", {"old_text": "x", "new_text": "y"}, read_only=False, expected_original_sha256=executor._sha256_file(dup_file), estimated_changed_files=1, estimated_changed_lines=1)
        _assert(_result(policy, dup, dup_cfg, approval=_grant(dup, dup_cfg))["error_category"] == "patch_not_unique", "Duplicate patch text category changed.")
        original_sha_func = executor._sha256_file
        rollback_target = root / "src" / "file.txt"
        rollback_hash = original_sha_func(rollback_target)
        rollback_action = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "rollback probe\n"}, read_only=False, expected_original_sha256=rollback_hash, estimated_changed_files=1, estimated_changed_lines=1)
        try:
            def fake_sha(path: Path) -> str:
                return "f" * 64

            executor._sha256_file = fake_sha
            rolled = _result(policy, rollback_action, cfg, approval=_grant(rollback_action, cfg))
        finally:
            executor._sha256_file = original_sha_func
        _assert(rolled["status"] == "ROLLED_BACK" and rollback_target.read_text(encoding="utf-8") != "rollback probe\n", "Rollback did not restore pre-state.")
        kill = importlib.import_module("modules.autonomy_policy_ru").KillSwitchStatus(True, "DISABLE", "disabled")
        blocked = _action("edit_file", "write_allowlisted_file", "src/file.txt", {"content": "blocked\n"}, read_only=False, expected_original_sha256=original_sha_func(existing), estimated_changed_files=1, estimated_changed_lines=1)
        before = existing.read_bytes()
        _assert(_result(policy, blocked, cfg, approval=_grant(blocked, cfg), kill=kill)["executed"] is False and existing.read_bytes() == before, "Kill switch allowed a write.")


def test_result_budget_manifest_and_regression_invariants() -> None:
    executor = importlib.import_module("modules.autonomous_action_executor_ru")
    policy_mod = importlib.import_module("modules.autonomy_policy_ru")
    with _fixture_root() as temp_text:
        root = Path(temp_text)
        (root / "a.txt").write_text("x", encoding="utf-8")
        cfg = executor.default_executor_config(root)
        policy = _policy(root=root)
        action = _action("inspect", "read_file", "a.txt")
        data = _result(policy, action, cfg, usage=policy_mod.BudgetUsage(actions_used=policy.budgets.max_actions))
        _assert(data["status"] == "DENIED" and data["executed"] is False and data["error_category"] == "budget_exceeded", "Budget overflow did not deny before execution.")
        schema = list(_result(policy, action, cfg).keys())
        expected = ["mode", "version", "action_id", "action_type", "operation", "status", "ok", "executed", "target", "action_fingerprint", "approval", "policy", "timing", "bytes_read", "bytes_written", "original_sha256", "result_sha256", "stdout", "stderr", "output_truncated", "rollback_performed", "error_category", "details", "warnings"]
        _assert(schema == expected, "Action result schema changed.")
        _assert(_result(policy, action, cfg)["ok"] is True, "SUCCESS did not set ok=true.")
    manifest = json.loads((ROOT / "localcomet_runtime_manifest.json").read_text(encoding="utf-8"))
    if "modules/autonomous_action_executor_ru.py" in manifest.get("lazy_runtime", []) or "tools/test_v684_action_executor.py" in manifest.get("tests", []):
        _assert("modules/autonomous_action_executor_ru.py" in manifest.get("lazy_runtime", []), "Executor module missing from manifest.")
        _assert("tools/test_v684_action_executor.py" in manifest.get("tests", []), "v6.84 test missing from manifest.")
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
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _assert(staged.returncode == 0 and staged.stdout.strip() == "", "Staged files present.")


def main() -> None:
    tests = [
        test_import_side_effects,
        test_configuration_and_validation,
        test_action_mapping_fingerprint_and_approval,
        test_path_policy_and_kill_switches,
        test_read_list_search_and_syntax,
        test_allowlisted_test_execution,
        test_writes_patches_hashes_and_rollback,
        test_result_budget_manifest_and_regression_invariants,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        print(f"PASS {test.__name__} {time.perf_counter() - start:.3f}s")
    print("ALL v6.84 ACTION EXECUTOR TESTS PASSED")


if __name__ == "__main__":
    main()
````

### ПУТЬ: tools/validate_localcomet_vault.py (1359 строк, 58943 байт)

````python
"""Deterministic, dependency-free, read-only validator for LocalComet Vault v2."""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


sys.dont_write_bytecode = True

MAX_NOTES = 2000
MAX_NOTE_BYTES = 1_048_576
MAX_TOTAL_SCAN_BYTES = 67_108_864
MAX_AUXILIARY_BYTES = 1_048_576
MAX_CANVAS_NODES = 512
MAX_CANVAS_EDGES = 1024
MAX_CANVAS_TEXT_CHARS = 65_536

DECLARED_CANVAS_ASSETS = frozenset(
    {"00 Канон/LocalComet — Архитектурная карта.canvas"}
)
HUB_PATH_PREFIXES = ("00 Канон/", "01 Архитектура/", "03 Решения/")
COMPONENT_PATH_PREFIXES = ("01 Архитектура/",)
DRAFT_PATH_PREFIXES = ("01 Архитектура/",)

REQUIRED_FIELDS = (
    "id",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "updated",
    "last_reviewed",
)
LIST_FIELDS = {
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "aliases",
    "tags",
}
ENUMS = {
    "type": {
        "canonical", "architecture", "release", "adr", "runbook", "incident",
        "roadmap", "security", "research", "prompt", "session", "evidence", "meta",
        "hub", "component",
    },
    "status": {
        "current", "active", "accepted", "planned", "research", "resolved",
        "historical", "superseded", "evidence-limited", "draft",
    },
    "knowledge_layer": {
        "current_source_truth", "verified_history", "founder_intent", "operational",
        "research", "roadmap", "forensic_evidence", "session_snapshot",
    },
    "evidence_class": {"A", "B", "C", "D", "E", "G"},
    "authority": {
        "source", "runtime", "test", "forensic_evidence", "founder",
        "architecture_decision", "research", "roadmap", "session",
    },
}
REQUIRED_CANONICAL_SCOPES = {
    "current-state",
    "version-matrix",
    "product-vision",
    "system-architecture",
    "source-map",
    "knowledge-schema",
    "security",
    "roadmap",
    "evidence",
    "incidents",
}
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".com", ".scr", ".msi",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".db", ".sqlite", ".sqlite3",
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".zsh",
    ".vbs", ".jar",
}
FORBIDDEN_AUXILIARY_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"PK\x03\x04",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07",
    b"\x1f\x8b",
    b"SQLite format 3\x00",
    b"#!",
)
LINK_BENEFIT_TYPES = {
    "canonical", "architecture", "adr", "runbook", "incident", "roadmap",
    "security", "research", "evidence", "hub",
}

ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
EVIDENCE_ID_RE = re.compile(r"^EV-[0-9]{3,}$")
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:[ ](.*))?$")
LIST_ITEM_RE = re.compile(r"^  -[ ](.+)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
WIKI_LINK_RE = re.compile(r"!?\[\[([^\[\]\r\n]+)\]\]")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ValidatorRuntimeError(RuntimeError):
    """The validator could not safely establish or read its configured roots."""


class FrontmatterError(ValueError):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.line = line


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    file: str = ""
    line: int = 0
    finding_type: str = ""
    redacted: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", 0)}


@dataclass
class Note:
    path: Path
    relative_path: str
    raw_bytes: bytes
    text: str
    metadata: dict[str, Any]
    body_lines: list[tuple[int, str]]
    headings: set[str] = field(default_factory=set)
    title: str = ""
    note_id: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    status: str
    vault_root: str
    project_root: str
    vault_revision: str
    markdown_note_count: int
    markdown_total_bytes: int
    obsidian_json_count: int
    obsidian_auxiliary_count: int
    obsidian_auxiliary_total_bytes: int
    obsidian_auxiliary_files: list[dict[str, Any]]
    stable_id_count: int
    canonical_scope_count: int
    wiki_link_count: int
    resolved_wiki_link_count: int
    broken_link_count: int
    ambiguous_link_count: int
    alias_collision_count: int
    evidence_record_count: int
    unresolved_evidence_ref_count: int
    canonical_ownership_conflict_count: int
    supersession_cycle_count: int
    missing_source_path_count: int
    unexpected_file_count: int
    binary_or_forbidden_file_count: int
    secret_finding_count: int
    error_count: int
    warning_count: int
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normal(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _lookup_key(value: str) -> str:
    return _normal(value).casefold()


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_path_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((os.fspath(path), os.fspath(root))) == os.fspath(root)
    except (ValueError, OSError):
        return False


def _stat_is_reparse(info: os.stat_result) -> bool:
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & marker)


def is_reparse_point(path: os.PathLike[str] | str) -> bool:
    """Return True for a symlink or Windows reparse point without following it."""
    info = os.lstat(path)
    return stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _path_components(path: Path) -> Iterable[Path]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    current = anchor
    if absolute == anchor:
        yield anchor
        return
    for part in absolute.parts[1:]:
        current = current / part
        yield current


def _safe_root(configured: os.PathLike[str] | str, label: str) -> Path:
    path = Path(os.path.abspath(os.fspath(configured)))
    try:
        for component in _path_components(path):
            if is_reparse_point(component):
                raise ValidatorRuntimeError(f"{label} contains a symlink or reparse point: {component}")
        if not path.exists() or not path.is_dir():
            raise ValidatorRuntimeError(f"{label} does not exist or is not a directory: {path}")
        resolved = path.resolve(strict=True)
    except ValidatorRuntimeError:
        raise
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot inspect {label}: {path}: {exc}") from exc
    return resolved


def _entry_is_link_or_reparse(entry: os.DirEntry[str], info: os.stat_result) -> bool:
    return entry.is_symlink() or stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _inspect_auxiliary_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_auxiliary",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_SIZE_LIMIT",
                f"Obsidian auxiliary file size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}",
                relative,
            )
        )
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Obsidian auxiliary file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Obsidian auxiliary file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(
            Issue(
                "error",
                "AUXILIARY_FORBIDDEN_CONTENT",
                "Obsidian auxiliary file contains executable, archive, or database content",
                relative,
            )
        )
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_BINARY_CONTENT",
                "Obsidian auxiliary file must be bounded UTF-8 text",
                relative,
            )
        )
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    return record, issues, False


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _bounded_canvas_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value) or abs(value) > 10_000_000:
        return False
    return not positive or value > 0


def _canvas_file_reference_problem(path_value: Any, vault_root: Path) -> str | None:
    if not isinstance(path_value, str) or not 1 <= len(path_value) <= 512:
        return "file node reference must be a bounded string"
    if URL_RE.match(path_value):
        return "URL file references are forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return "absolute, drive-qualified, or UNC file references are forbidden"
    if "\\" in path_value:
        return "Canvas file references must use forward slashes"
    parts = path_value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "Canvas file reference traversal is forbidden"
    if Path(path_value).suffix.casefold() != ".md":
        return "Canvas file nodes may reference Markdown notes only"
    candidate = vault_root.joinpath(*parts)
    current = vault_root
    try:
        for part in parts:
            current = current / part
            if current.exists() and is_reparse_point(current):
                return "Canvas file reference crosses a symlink or reparse point"
        if not candidate.exists() or not candidate.is_file():
            return "Canvas file reference does not resolve to a Vault note"
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return f"Canvas file reference inspection failed: {exc}"
    if not _is_path_within(resolved, vault_root):
        return "Canvas file reference resolves outside the Vault"
    return None


def _canvas_node_problem(node: Any, vault_root: Path) -> str | None:
    if not isinstance(node, dict):
        return "Canvas node must be an object"
    node_type = node.get("type")
    common = {"id", "type", "x", "y", "width", "height", "color"}
    allowed_by_type = {
        "group": common | {"label"},
        "file": common | {"file"},
        "text": common | {"text"},
    }
    required_by_type = {
        "group": {"id", "type", "x", "y", "width", "height", "label"},
        "file": {"id", "type", "x", "y", "width", "height", "file"},
        "text": {"id", "type", "x", "y", "width", "height", "text"},
    }
    if node_type not in allowed_by_type:
        return "Canvas node type must be group, file, or text"
    if not required_by_type[node_type].issubset(node) or not set(node).issubset(allowed_by_type[node_type]):
        return f"Canvas {node_type} node has missing or unknown fields"
    node_id = node.get("id")
    if not isinstance(node_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", node_id):
        return "Canvas node id is invalid"
    if not _bounded_canvas_number(node.get("x")) or not _bounded_canvas_number(node.get("y")):
        return "Canvas node coordinates are invalid"
    if not _bounded_canvas_number(node.get("width"), positive=True) or not _bounded_canvas_number(node.get("height"), positive=True):
        return "Canvas node dimensions are invalid"
    color = node.get("color")
    if color is not None and (not isinstance(color, str) or not 1 <= len(color) <= 64):
        return "Canvas node color is invalid"
    if node_type == "group":
        label = node.get("label")
        if not isinstance(label, str) or not 1 <= len(label) <= 512:
            return "Canvas group label is invalid"
    elif node_type == "file":
        return _canvas_file_reference_problem(node.get("file"), vault_root)
    else:
        text = node.get("text")
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_CANVAS_TEXT_CHARS:
            return "Canvas text node content is invalid"
        if re.search(r"(?i)\b(?:https?|file)://", text):
            return "Canvas text nodes may not declare external URL references"
    return None


def _canvas_edge_problem(edge: Any, node_ids: set[str]) -> str | None:
    if not isinstance(edge, dict):
        return "Canvas edge must be an object"
    allowed = {
        "id", "fromNode", "fromSide", "fromEnd", "toNode", "toSide",
        "toEnd", "color", "label",
    }
    if not {"id", "fromNode", "toNode"}.issubset(edge) or not set(edge).issubset(allowed):
        return "Canvas edge has missing or unknown fields"
    for field_name in ("id", "fromNode", "toNode"):
        value = edge.get(field_name)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            return f"Canvas edge {field_name} is invalid"
    if edge["fromNode"] not in node_ids or edge["toNode"] not in node_ids:
        return "Canvas edge references an unknown node"
    if edge["fromNode"] == edge["toNode"]:
        return "Canvas self-edges are forbidden"
    for field_name in ("fromSide", "toSide"):
        if field_name in edge and edge[field_name] not in {"top", "right", "bottom", "left"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name in ("fromEnd", "toEnd"):
        if field_name in edge and edge[field_name] not in {"none", "arrow"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name, limit in (("color", 64), ("label", 512)):
        if field_name in edge and (
            not isinstance(edge[field_name], str) or not 1 <= len(edge[field_name]) <= limit
        ):
            return f"Canvas edge {field_name} is invalid"
    return None


def _inspect_canvas_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
    vault_root: Path,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_canvas",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(Issue("error", "AUXILIARY_SIZE_LIMIT", f"Canvas size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}", relative))
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Canvas file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Canvas file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(Issue("error", "AUXILIARY_FORBIDDEN_CONTENT", "Canvas contains executable, archive, or database content", relative))
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(Issue("error", "AUXILIARY_BINARY_CONTENT", "Canvas must be bounded UTF-8 JSON", relative))
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON number: {value}")),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        issues.append(Issue("error", "CANVAS_JSON_INVALID", f"Canvas JSON is invalid: {exc}", relative))
        return record, issues, False
    if not isinstance(payload, dict) or set(payload) != {"nodes", "edges"}:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas root must contain exactly nodes and edges arrays", relative))
        return record, issues, False
    nodes = payload["nodes"]
    edges = payload["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas nodes must be a non-empty array and edges must be an array", relative))
        return record, issues, False
    if len(nodes) > MAX_CANVAS_NODES or len(edges) > MAX_CANVAS_EDGES:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas node or edge count exceeds the bounded policy", relative))
        return record, issues, False
    node_ids: set[str] = set()
    hard_stop_present = False
    for index, node in enumerate(nodes):
        problem = _canvas_node_problem(node, vault_root)
        if problem:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: {problem}", relative))
            continue
        node_id = node["id"]
        if node_id in node_ids:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: duplicate node id", relative))
        node_ids.add(node_id)
        if node.get("type") == "text" and "HARD STOP" in node.get("text", "") and "NO AUTOMATIC VAULT WRITE" in node.get("text", ""):
            hard_stop_present = True
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        problem = _canvas_edge_problem(edge, node_ids)
        if problem:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: {problem}", relative))
            continue
        edge_id = edge["id"]
        if edge_id in edge_ids:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: duplicate edge id", relative))
        edge_ids.add(edge_id)
    if not hard_stop_present:
        issues.append(Issue("error", "CANVAS_BOUNDARY_MISSING", "Declared architecture Canvas must retain the no-write HARD STOP boundary", relative))
    return record, issues, False


def _discover_files_detailed(
    vault_root: Path,
) -> tuple[
    list[tuple[Path, os.stat_result]],
    int,
    list[dict[str, Any]],
    list[Issue],
    int,
    int,
]:
    notes: list[tuple[Path, os.stat_result]] = []
    obsidian_json_count = 0
    auxiliary_files: list[dict[str, Any]] = []
    issues: list[Issue] = []
    unexpected_count = 0
    forbidden_count = 0

    def walk(directory: Path) -> None:
        nonlocal obsidian_json_count, unexpected_count, forbidden_count
        try:
            entries = sorted(os.scandir(directory), key=lambda item: _lookup_key(item.name))
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot enumerate Vault directory {directory}: {exc}") from exc
        try:
            for entry in entries:
                candidate = Path(entry.path)
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise ValidatorRuntimeError(f"cannot inspect Vault entry {candidate}: {exc}") from exc
                relative = _relative_posix(candidate, vault_root)
                if _entry_is_link_or_reparse(entry, info):
                    issues.append(Issue("error", "REPARSE_POINT", "symlink or reparse point is forbidden", relative))
                    continue
                if stat.S_ISDIR(info.st_mode):
                    walk(candidate)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    issues.append(Issue("error", "NON_REGULAR_FILE", "non-regular Vault entry is forbidden", relative))
                    continue
                resolved = candidate.resolve(strict=True)
                if not _is_path_within(resolved, vault_root):
                    issues.append(Issue("error", "PATH_ESCAPE", "Vault file resolves outside the configured root", relative))
                    continue
                in_obsidian = bool(Path(relative).parts and Path(relative).parts[0] == ".obsidian")
                suffix = candidate.suffix.casefold()
                if in_obsidian and suffix == ".json":
                    obsidian_json_count += 1
                elif not in_obsidian and suffix == ".md":
                    notes.append((candidate, info))
                elif suffix == ".base":
                    record, auxiliary_issues, forbidden_content = _inspect_auxiliary_file(
                        candidate,
                        info,
                        relative,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                elif suffix == ".canvas" and _normal(relative) in DECLARED_CANVAS_ASSETS:
                    record, auxiliary_issues, forbidden_content = _inspect_canvas_file(
                        candidate,
                        info,
                        relative,
                        vault_root,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                else:
                    unexpected_count += 1
                    if suffix in FORBIDDEN_EXTENSIONS:
                        forbidden_count += 1
                        issues.append(Issue("error", "FORBIDDEN_FILE", f"forbidden Vault file extension: {suffix}", relative))
                    else:
                        issues.append(Issue("error", "UNEXPECTED_FILE", "unexpected regular file outside the Vault file policy", relative))
        finally:
            for entry in entries:
                del entry

    walk(vault_root)
    notes.sort(key=lambda item: _lookup_key(_relative_posix(item[0], vault_root)))
    auxiliary_files.sort(key=lambda item: _normal(item["relative_path"]))
    return (
        notes,
        obsidian_json_count,
        auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    )


def _discover_files(
    vault_root: Path,
) -> tuple[list[tuple[Path, os.stat_result]], int, list[Issue], int, int]:
    """Compatibility wrapper used by the read-only KnowledgeAdapter."""
    notes, json_count, _auxiliary, issues, unexpected, forbidden = (
        _discover_files_detailed(vault_root)
    )
    return notes, json_count, issues, unexpected, forbidden


def _parse_scalar(value: str, line_number: int) -> Any:
    if value == "[]":
        return []
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if not value:
        raise FrontmatterError("empty scalar is unsupported; use [] for an empty list", line_number)
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise FrontmatterError(f"invalid quoted string: {exc.msg}", line_number) from exc
        if not isinstance(parsed, str):
            raise FrontmatterError("quoted frontmatter values must be strings", line_number)
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise FrontmatterError("invalid single-quoted string", line_number)
        return value[1:-1].replace("''", "'")
    if value[0] in "[{&*!>|%@`" or value.endswith(":") or " #" in value or "\t" in value:
        raise FrontmatterError("unsupported YAML-like scalar syntax", line_number)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], list[tuple[int, str]]]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterError("missing opening frontmatter delimiter", 1)
    closing = next((index for index in range(1, len(lines)) if lines[index] == "---"), None)
    if closing is None:
        raise FrontmatterError("missing closing frontmatter delimiter", 1)
    metadata: dict[str, Any] = {}
    index = 1
    while index < closing:
        line = lines[index]
        line_number = index + 1
        if not line.strip():
            index += 1
            continue
        if "\t" in line:
            raise FrontmatterError("tabs are unsupported in frontmatter", line_number)
        match = KEY_RE.fullmatch(line)
        if not match:
            raise FrontmatterError("unsupported frontmatter syntax", line_number)
        key, raw_value = match.group(1), match.group(2)
        if key in metadata:
            raise FrontmatterError(f"duplicate frontmatter key: {key}", line_number)
        if raw_value is None or raw_value == "":
            values: list[str] = []
            index += 1
            while index < closing:
                item_match = LIST_ITEM_RE.fullmatch(lines[index])
                if not item_match:
                    break
                item = _parse_scalar(item_match.group(1), index + 1)
                if not isinstance(item, str):
                    raise FrontmatterError("block list items must be scalar strings", index + 1)
                values.append(item)
                index += 1
            if not values:
                raise FrontmatterError(f"empty block list for {key}; use []", line_number)
            metadata[key] = values
            continue
        metadata[key] = _parse_scalar(raw_value, line_number)
        index += 1
    body = [(line_number + 1, line) for line_number, line in enumerate(lines[closing + 1 :], closing + 1)]
    return metadata, body


def _outside_fences(lines: list[tuple[int, str]]) -> Iterable[tuple[int, str]]:
    fence: str | None = None
    for line_number, line in lines:
        marker_match = re.match(r"^[ ]{0,3}(`{3,}|~{3,})", line)
        if marker_match:
            marker = marker_match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None:
            yield line_number, line


def _extract_headings(note: Note) -> None:
    headings: set[str] = set()
    first_h1 = ""
    for _line_number, line in _outside_fences(note.body_lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
        if heading:
            headings.add(_lookup_key(heading))
            if len(match.group(1)) == 1 and not first_h1:
                first_h1 = heading
    note.headings = headings
    configured_title = note.metadata.get("title")
    note.title = configured_title if isinstance(configured_title, str) else first_h1


def _issue(issues: list[Issue], severity: str, code: str, message: str, note: Note | None = None, line: int = 0) -> None:
    issues.append(Issue(severity, code, message, note.relative_path if note else "", line))


def _validate_date(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        _datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_timestamp(value: Any) -> bool:
    if _validate_date(value):
        return True
    if not isinstance(value, str):
        return False
    try:
        _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def _validate_note_schema(note: Note, issues: list[Issue]) -> None:
    metadata = note.metadata
    for field_name in REQUIRED_FIELDS:
        if field_name not in metadata:
            _issue(issues, "error", "MISSING_REQUIRED_FIELD", f"missing required field: {field_name}", note)
    for field_name, allowed in ENUMS.items():
        value = metadata.get(field_name)
        if field_name in metadata and (not isinstance(value, str) or value not in allowed):
            _issue(issues, "error", "INVALID_ENUM", f"invalid {field_name}: {value!r}", note)
    for field_name in LIST_FIELDS:
        if field_name not in metadata:
            continue
        value = metadata[field_name]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _issue(issues, "error", "INVALID_FIELD_TYPE", f"{field_name} must be a list of strings", note)
    canonical = metadata.get("canonical", False)
    if not isinstance(canonical, bool):
        _issue(issues, "error", "INVALID_CANONICAL_TYPE", "canonical must be a boolean", note)
    for field_name in ("updated", "last_reviewed"):
        if field_name in metadata and not _validate_date(metadata[field_name]):
            _issue(issues, "error", "INVALID_DATE", f"{field_name} must be a valid YYYY-MM-DD date", note)
    if "verified_at" in metadata and not _validate_timestamp(metadata["verified_at"]):
        _issue(issues, "error", "INVALID_TIMESTAMP", "verified_at must be an ISO date or ISO-8601 timestamp", note)
    note_id = metadata.get("id")
    if isinstance(note_id, str):
        note.note_id = note_id
        if not ID_RE.fullmatch(note_id):
            _issue(issues, "error", "INVALID_STABLE_ID", f"invalid stable ID: {note_id!r}", note)
    elif "id" in metadata:
        _issue(issues, "error", "INVALID_STABLE_ID", "stable ID must be a string", note)
    aliases = metadata.get("aliases", [])
    if isinstance(aliases, list) and all(isinstance(value, str) for value in aliases):
        note.aliases = aliases

    status = metadata.get("status")
    layer = metadata.get("knowledge_layer")
    note_type = metadata.get("type")
    if layer == "current_source_truth" and status in {"planned", "superseded"}:
        _issue(issues, "error", "CURRENT_TRUTH_STATUS", f"current source truth cannot be {status}", note)
    if canonical is True and status == "superseded":
        _issue(issues, "error", "SUPERSEDED_CANONICAL", "canonical note cannot be superseded", note)
    if status == "superseded" and not metadata.get("superseded_by"):
        _issue(issues, "error", "SUPERSEDED_WITHOUT_SUCCESSOR", "superseded note requires superseded_by", note)
    if layer == "founder_intent" and metadata.get("authority") != "founder":
        _issue(issues, "warning", "FOUNDER_INTENT_AUTHORITY", "founder_intent normally uses authority: founder", note)
    if note_type == "release" and not metadata.get("releases"):
        if not (isinstance(note_id, str) and re.fullmatch(r"release[._-]v?[0-9]+(?:[._-][0-9]+)*(?:[a-z][0-9]*)?", note_id)):
            _issue(issues, "error", "RELEASE_IDENTIFIER_MISSING", "release note requires releases or a release-compatible stable ID", note)
    if note_type == "hub":
        tags = metadata.get("tags", [])
        if not note.relative_path.startswith(HUB_PATH_PREFIXES) or not isinstance(tags, list) or "hub" not in tags:
            _issue(
                issues,
                "error",
                "HUB_ROLE_BOUNDARY",
                "hub is reserved for tagged navigation entry points under Canon, Architecture, or Decisions",
                note,
            )
    if note_type == "component":
        component_contract = (
            note.relative_path.startswith(COMPONENT_PATH_PREFIXES)
            and canonical is False
            and layer == "current_source_truth"
            and metadata.get("evidence_class") == "A"
            and metadata.get("authority") == "source"
            and bool(metadata.get("source_paths"))
        )
        if not component_contract:
            _issue(
                issues,
                "error",
                "COMPONENT_ROLE_BOUNDARY",
                "component is reserved for source-grounded, non-canonical software component notes under Architecture",
                note,
            )
    if status == "draft":
        draft_contract = (
            note.relative_path.startswith(DRAFT_PATH_PREFIXES)
            and canonical is False
            and layer == "founder_intent"
            and metadata.get("evidence_class") == "C"
            and metadata.get("authority") in {"founder", "architecture_decision"}
        )
        if not draft_contract:
            _issue(
                issues,
                "error",
                "DRAFT_AUTHORITY_BOUNDARY",
                "draft is non-canonical founder intent under Architecture and grants no current-source authority",
                note,
            )


def _validate_source_path(path_value: str, project_root: Path) -> tuple[Path | None, str | None]:
    if URL_RE.match(path_value):
        return None, "URL source path is forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return None, "absolute, drive-qualified, or UNC source path is forbidden"
    components = [part for part in re.split(r"[\\/]", path_value) if part not in ("", ".")]
    if not components or any(part == ".." for part in components):
        return None, "source path traversal is forbidden"
    candidate = project_root.joinpath(*components)
    current = project_root
    try:
        for component in components:
            current = current / component
            if current.exists() and is_reparse_point(current):
                return None, "source path traverses a symlink or reparse point"
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, f"source path inspection failed: {exc}"
    if not _is_path_within(resolved, project_root):
        return None, "source path resolves outside project root"
    return candidate, None


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}…{value[-4:]}"


def _looks_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in ("placeholder", "redacted", "example", "changeme", "your_", "your-", "xxxx", "<", ">", "..."))


def _scan_secret_text(text: str, relative_path: str) -> list[Issue]:
    findings: list[Issue] = []
    prefix_re = re.compile(
        r"\b(sk-(?:live-)?[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
        r"xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"
    )
    assignment_re = re.compile(
        r"(?i)\b(api[ _-]?key|access[ _-]?token|token|secret|password|passwd|client_secret)"
        r"\s*[:=]\s*[\"']?([A-Za-z0-9_./+\-=]{20,})"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        if "-----BEGIN " in line and "PRIVATE KEY-----" in line:
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "PEM_PRIVATE_KEY", "-----BEGIN … PRIVATE KEY-----"))
        for match in prefix_re.finditer(line):
            value = match.group(1)
            if not _looks_placeholder(value):
                findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "LIVE_TOKEN_PREFIX", _redact(value)))
        for match in assignment_re.finditer(line):
            value = match.group(2)
            if re.fullmatch(r"[0-9a-fA-F]{64}", value) or _looks_placeholder(value):
                continue
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence credential assignment", relative_path, line_number, "CREDENTIAL_ASSIGNMENT", _redact(value)))
    unique: dict[tuple[Any, ...], Issue] = {}
    for finding in findings:
        unique[(finding.file, finding.line, finding.finding_type, finding.redacted)] = finding
    return list(unique.values())


def _scan_secrets(note: Note) -> list[Issue]:
    return _scan_secret_text(note.text, note.relative_path)


def _compute_revision(notes: list[Note]) -> str:
    canonical = hashlib.sha256()
    for note in sorted(notes, key=lambda item: _normal(item.relative_path)):
        canonical.update(_normal(note.relative_path).encode("utf-8"))
        canonical.update(b"\0")
        canonical.update(hashlib.sha256(note.raw_bytes).hexdigest().encode("ascii"))
        canonical.update(b"\0")
    return f"sha256:{canonical.hexdigest()}"


def _cycle_count(edges: dict[str, set[str]]) -> int:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycle_keys: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, set())):
            if state.get(target, 0) == 0:
                visit(target)
            elif state.get(target) == 1:
                start = stack.index(target)
                cycle = stack[start:]
                rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
                cycle_keys.add(min(rotations))
        stack.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            visit(node)
    return len(cycle_keys)


def _result(
    *, vault_root: Path, project_root: Path, notes: list[Note], markdown_note_count: int,
    markdown_total_bytes: int, obsidian_json_count: int,
    obsidian_auxiliary_files: list[dict[str, Any]], issues: list[Issue],
    canonical_scope_count: int, wiki_count: int, resolved_count: int, broken_count: int,
    ambiguous_count: int, alias_collision_count: int, evidence_count: int,
    unresolved_evidence_count: int, ownership_conflicts: int, cycle_count: int,
    missing_source_count: int, unexpected_count: int, forbidden_count: int,
    secret_count: int,
) -> ValidationResult:
    issues.sort(key=lambda item: (_lookup_key(item.file), item.line, item.severity, item.code, item.message))
    errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
    warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    stable_ids = {note.note_id for note in notes if note.note_id and ID_RE.fullmatch(note.note_id)}
    return ValidationResult(
        status=status,
        vault_root=os.fspath(vault_root),
        project_root=os.fspath(project_root),
        vault_revision=_compute_revision(notes),
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_count=len(obsidian_auxiliary_files),
        obsidian_auxiliary_total_bytes=sum(
            int(item["size"]) for item in obsidian_auxiliary_files
        ),
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        stable_id_count=len(stable_ids),
        canonical_scope_count=canonical_scope_count,
        wiki_link_count=wiki_count,
        resolved_wiki_link_count=resolved_count,
        broken_link_count=broken_count,
        ambiguous_link_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_record_count=evidence_count,
        unresolved_evidence_ref_count=unresolved_evidence_count,
        canonical_ownership_conflict_count=ownership_conflicts,
        supersession_cycle_count=cycle_count,
        missing_source_path_count=missing_source_count,
        unexpected_file_count=unexpected_count,
        binary_or_forbidden_file_count=forbidden_count,
        secret_finding_count=secret_count,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
    )


def validate_vault(
    vault: os.PathLike[str] | str,
    project: os.PathLike[str] | str,
    *,
    require_canonical_scopes: bool = True,
    max_notes: int = MAX_NOTES,
    max_note_bytes: int = MAX_NOTE_BYTES,
    max_total_scan_bytes: int = MAX_TOTAL_SCAN_BYTES,
) -> ValidationResult:
    """Validate without writing to the Vault or project tree."""
    vault_root = _safe_root(vault, "Vault root")
    project_root = _safe_root(project, "project root")
    (
        discovered,
        obsidian_json_count,
        obsidian_auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    ) = _discover_files_detailed(vault_root)
    markdown_note_count = len(discovered)
    markdown_total_bytes = sum(info.st_size for _path, info in discovered)
    if markdown_note_count > max_notes:
        issues.append(Issue("error", "NOTE_COUNT_LIMIT", f"Markdown note count {markdown_note_count} exceeds limit {max_notes}"))
    if markdown_total_bytes > max_total_scan_bytes:
        issues.append(Issue("error", "TOTAL_SCAN_LIMIT", f"Markdown bytes {markdown_total_bytes} exceed limit {max_total_scan_bytes}"))

    notes: list[Note] = []
    for path, info in discovered:
        relative = _relative_posix(path, vault_root)
        if info.st_size > max_note_bytes:
            issues.append(Issue("error", "NOTE_SIZE_LIMIT", f"note size {info.st_size} exceeds limit {max_note_bytes}", relative))
            continue
        try:
            raw_bytes = path.read_bytes()
            if len(raw_bytes) != info.st_size:
                raise ValidatorRuntimeError(f"Vault note changed during validation: {relative}")
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(Issue("error", "INVALID_UTF8", f"note is not valid UTF-8: {exc}", relative))
            continue
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot read Vault note {relative}: {exc}") from exc
        try:
            metadata, body_lines = parse_frontmatter(text)
        except FrontmatterError as exc:
            issues.append(Issue("error", "FRONTMATTER_ERROR", str(exc), relative, exc.line))
            continue
        note = Note(path, relative, raw_bytes, text, metadata, body_lines)
        _extract_headings(note)
        _validate_note_schema(note, issues)
        issues.extend(_scan_secrets(note))
        notes.append(note)

    by_id: dict[str, list[Note]] = {}
    normalized_ids: dict[str, list[Note]] = {}
    for note in notes:
        if not note.note_id:
            continue
        by_id.setdefault(note.note_id, []).append(note)
        normalized_ids.setdefault(_lookup_key(note.note_id), []).append(note)
    for note_id, owners in sorted(by_id.items()):
        if len(owners) > 1:
            for note in owners:
                _issue(issues, "error", "DUPLICATE_STABLE_ID", f"duplicate stable ID: {note_id}", note)
    for normalized_id, owners in sorted(normalized_ids.items()):
        raw_values = {note.note_id for note in owners}
        if len(owners) > 1 and (len(raw_values) > 1 or len(by_id.get(next(iter(raw_values)), [])) > 1):
            for note in owners:
                _issue(issues, "error", "NORMALIZED_DUPLICATE_ID", f"normalized/case duplicate stable ID: {normalized_id}", note)

    canonical_owners: dict[str, list[Note]] = {}
    for note in notes:
        canonical = note.metadata.get("canonical", False)
        scope = note.metadata.get("canonical_scope")
        if canonical is True:
            if not isinstance(scope, str) or not scope:
                _issue(issues, "error", "CANONICAL_SCOPE_MISSING", "canonical note requires canonical_scope", note)
            else:
                canonical_owners.setdefault(scope, []).append(note)
    ownership_conflicts = 0
    for scope, owners in sorted(canonical_owners.items()):
        if len(owners) > 1:
            ownership_conflicts += 1
            for note in owners:
                _issue(issues, "error", "CANONICAL_SCOPE_CONFLICT", f"multiple canonical owners for scope: {scope}", note)
    if require_canonical_scopes:
        for scope in sorted(REQUIRED_CANONICAL_SCOPES - set(canonical_owners)):
            issues.append(Issue("error", "MISSING_CANONICAL_SCOPE", f"missing canonical scope: {scope}"))

    missing_source_count = 0
    for note in notes:
        paths = note.metadata.get("source_paths", [])
        if not isinstance(paths, list):
            continue
        for source_path in paths:
            if not isinstance(source_path, str):
                continue
            candidate, problem = _validate_source_path(source_path, project_root)
            if problem:
                _issue(issues, "error", "INVALID_SOURCE_PATH", f"{source_path!r}: {problem}", note)
                continue
            assert candidate is not None
            if not candidate.exists():
                if note.metadata.get("knowledge_layer") == "current_source_truth":
                    missing_source_count += 1
                    _issue(issues, "error", "MISSING_CURRENT_SOURCE", f"current source path does not exist: {source_path}", note)
                elif not note.metadata.get("evidence_refs"):
                    _issue(issues, "error", "MISSING_HISTORICAL_SOURCE", f"missing historical source path lacks evidence_refs: {source_path}", note)

    evidence_records: dict[str, list[tuple[Note, int]]] = {}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            heading = HEADING_RE.match(line)
            if not heading:
                continue
            heading_text = heading.group(2).strip()
            match = re.match(r"^(EV-[0-9]{3,})(?:\b|\s|—|-)", heading_text)
            if match:
                evidence_records.setdefault(match.group(1), []).append((note, line_number))
            elif heading_text.startswith("EV-"):
                _issue(issues, "error", "MALFORMED_EVIDENCE_ID", "malformed evidence record ID", note, line_number)
    for evidence_id, records in sorted(evidence_records.items()):
        if len(records) > 1:
            for note, line_number in records:
                _issue(issues, "error", "DUPLICATE_EVIDENCE_ID", f"duplicate evidence record ID: {evidence_id}", note, line_number)
    unresolved_evidence_count = 0
    for note in notes:
        references = note.metadata.get("evidence_refs", [])
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, str) or not EVIDENCE_ID_RE.fullmatch(reference):
                unresolved_evidence_count += 1
                _issue(issues, "error", "MALFORMED_EVIDENCE_REF", f"malformed evidence reference: {reference!r}", note)
            elif reference not in evidence_records:
                unresolved_evidence_count += 1
                _issue(issues, "error", "UNRESOLVED_EVIDENCE_REF", f"unresolved evidence reference: {reference}", note)

    id_to_note = {note.note_id: note for note in notes if note.note_id and len(by_id.get(note.note_id, [])) == 1}
    edges: dict[str, set[str]] = {note_id: set() for note_id in id_to_note}
    for note_id, note in id_to_note.items():
        supersedes = note.metadata.get("supersedes", [])
        superseded_by = note.metadata.get("superseded_by", [])
        for relation_name, references in (("supersedes", supersedes), ("superseded_by", superseded_by)):
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, str) or not ID_RE.fullmatch(reference):
                    _issue(issues, "error", "MALFORMED_SUPERSESSION_REF", f"malformed {relation_name} reference: {reference!r}", note)
                    continue
                if reference == note_id:
                    _issue(issues, "error", "SELF_SUPERSESSION", "self-supersession is forbidden", note)
                    continue
                if reference not in id_to_note:
                    _issue(issues, "error", "UNRESOLVED_SUPERSESSION_REF", f"unresolved {relation_name} reference: {reference}", note)
                    continue
                if relation_name == "supersedes":
                    edges[note_id].add(reference)
                    reciprocal = id_to_note[reference].metadata.get("superseded_by", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different superseded_by relation", note)
                else:
                    edges[reference].add(note_id)
                    reciprocal = id_to_note[reference].metadata.get("supersedes", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different supersedes relation", note)
    cycle_count = _cycle_count(edges)
    if cycle_count:
        issues.append(Issue("error", "SUPERSESSION_CYCLE", f"supersession graph contains {cycle_count} cycle(s)"))

    path_index: dict[str, list[Note]] = {}
    label_index: dict[str, list[Note]] = {}
    label_raw: dict[str, set[str]] = {}
    for note in notes:
        without_suffix = note.relative_path[:-3] if note.relative_path.casefold().endswith(".md") else note.relative_path
        path_index.setdefault(_lookup_key(without_suffix), []).append(note)
        labels = [Path(note.relative_path).stem]
        if note.title:
            labels.append(note.title)
        labels.extend(note.aliases)
        seen_in_note: set[str] = set()
        for label in labels:
            key = _lookup_key(label.strip())
            if not key or key in seen_in_note:
                continue
            seen_in_note.add(key)
            label_index.setdefault(key, []).append(note)
            label_raw.setdefault(key, set()).add(label)
    alias_collision_count = 0
    for key, owners in sorted(label_index.items()):
        unique_owners = {note.relative_path: note for note in owners}
        if len(unique_owners) > 1:
            alias_collision_count += 1
            raw = ", ".join(sorted(label_raw[key], key=_lookup_key))
            for note in unique_owners.values():
                _issue(issues, "error", "ALIAS_TITLE_COLLISION", f"ambiguous title/basename/alias after NFC and case normalization: {raw}", note)

    wiki_count = 0
    resolved_count = 0
    broken_count = 0
    ambiguous_count = 0
    incoming: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    outgoing: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            for match in WIKI_LINK_RE.finditer(line):
                wiki_count += 1
                content = match.group(1)
                target_part = content.split("|", 1)[0].strip()
                target_text, separator, heading_text = target_part.partition("#")
                target_text = target_text.strip().replace("\\", "/")
                heading_text = heading_text.strip() if separator else ""
                if not target_text:
                    candidates = [note] if separator else []
                else:
                    parts = target_text.split("/")
                    unsafe = URL_RE.match(target_text) or target_text.startswith("/") or PureWindowsPath(target_text).drive or any(part in ("", ".", "..") for part in parts)
                    if unsafe:
                        candidates = []
                    elif "/" in target_text:
                        normalized_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = path_index.get(_lookup_key(normalized_target), [])
                    else:
                        plain_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = label_index.get(_lookup_key(plain_target), [])
                unique_candidates = {candidate.relative_path: candidate for candidate in candidates}
                if not unique_candidates:
                    broken_count += 1
                    _issue(issues, "error", "BROKEN_WIKI_LINK", f"unresolved wiki link target: {target_text or target_part}", note, line_number)
                elif len(unique_candidates) > 1:
                    ambiguous_count += 1
                    _issue(issues, "error", "AMBIGUOUS_WIKI_LINK", f"ambiguous wiki link target: {target_text}", note, line_number)
                else:
                    target_note = next(iter(unique_candidates.values()))
                    resolved_count += 1
                    outgoing[note.relative_path].add(target_note.relative_path)
                    incoming[target_note.relative_path].add(note.relative_path)
                    if heading_text and _lookup_key(heading_text) not in target_note.headings:
                        _issue(issues, "warning", "MISSING_HEADING_FRAGMENT", f"wiki link heading not found: {heading_text}", note, line_number)

    for note in notes:
        if not incoming[note.relative_path]:
            code = "CANONICAL_NO_INCOMING" if note.metadata.get("canonical") is True else "NO_INCOMING_LINKS"
            _issue(issues, "warning", code, "note has no incoming wiki links", note)
        if note.metadata.get("type") in LINK_BENEFIT_TYPES and not outgoing[note.relative_path]:
            _issue(issues, "warning", "NO_OUTGOING_LINKS", "note type normally benefits from outgoing wiki links", note)
    hub_threshold = max(50, int(len(notes) * 0.60))
    for relative, targets in outgoing.items():
        if len(targets) > hub_threshold:
            note = next(item for item in notes if item.relative_path == relative)
            _issue(issues, "warning", "EXTREME_NAVIGATION_HUB", f"navigation note links to {len(targets)} distinct notes", note)

    secret_count = sum(1 for issue in issues if issue.code == "SECRET_FINDING")
    return _result(
        vault_root=vault_root,
        project_root=project_root,
        notes=notes,
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        issues=issues,
        canonical_scope_count=len(canonical_owners),
        wiki_count=wiki_count,
        resolved_count=resolved_count,
        broken_count=broken_count,
        ambiguous_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_count=len(evidence_records),
        unresolved_evidence_count=unresolved_evidence_count,
        ownership_conflicts=ownership_conflicts,
        cycle_count=cycle_count,
        missing_source_count=missing_source_count,
        unexpected_count=unexpected_count,
        forbidden_count=forbidden_count,
        secret_count=secret_count,
    )


def _human_report(result: ValidationResult) -> str:
    evidence_status = "PASS" if result.unresolved_evidence_ref_count == 0 else "FAIL"
    supersession_status = "PASS" if result.supersession_cycle_count == 0 else "FAIL"
    source_status = "PASS" if result.missing_source_path_count == 0 else "FAIL"
    return "\n".join(
        (
            "LocalComet Vault Validation",
            "",
            f"Status:\n{result.status}",
            "",
            f"Vault:\n{result.vault_root}",
            "",
            f"Vault revision:\n{result.vault_revision}",
            "",
            f"Markdown notes:\n{result.markdown_note_count}",
            "",
            f"Stable IDs:\n{result.stable_id_count}",
            "",
            f"Canonical scopes:\n{result.canonical_scope_count}",
            "",
            f"Obsidian auxiliary files:\n{result.obsidian_auxiliary_count}",
            "",
            f"Wiki links:\n{result.resolved_wiki_link_count} resolved\n{result.broken_link_count} broken\n{result.ambiguous_link_count} ambiguous",
            "",
            f"Evidence references:\n{evidence_status}",
            "",
            f"Supersession graph:\n{supersession_status}",
            "",
            f"Source paths:\n{source_status}",
            "",
            f"Unexpected files:\n{result.unexpected_file_count}",
            "",
            f"Secret findings:\n{result.secret_finding_count}",
            "",
            f"Errors:\n{result.error_count}",
            "",
            f"Warnings:\n{result.warning_count}",
            "",
            "Read only:\nYES",
        )
    )


def _runtime_payload(vault: str, project: str, exc: BaseException) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "vault_root": os.path.abspath(vault),
        "project_root": os.path.abspath(project),
        "error_count": 1,
        "warning_count": 0,
        "errors": [{"severity": "error", "code": "RUNTIME_FAILURE", "message": str(exc)}],
        "warnings": [],
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_vault(args.vault, args.project)
    except Exception as exc:  # Boundary: runtime failures use the exact CLI code 2.
        if args.json_output:
            print(json.dumps(_runtime_payload(args.vault, args.project, exc), ensure_ascii=False, sort_keys=True))
        else:
            print(f"LocalComet Vault Validation\n\nStatus:\nRUNTIME FAILURE\n\nError:\n{exc}\n\nRead only:\nYES")
        return 2
    if args.json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(_human_report(result))
    if result.status == "FAIL" or (args.fail_on_warnings and result.warning_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

### ПУТЬ: tools/verify_project_audit_bundle.py (402 строк, 18100 байт)

````python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.project_audit_bundle_ru import (
    EXCLUDE_GLOBS,
    EXCLUDE_PREFIXES,
    RELEASE,
    VERIFIER_SCHEMA_VERSION,
    _json_bytes,
    _matches_any,
    redact_text,
    scan_text_for_secret_markers,
)


REQUIRED_METADATA = {
    "bundle_manifest.json",
    "file_hashes_sha256.json",
    "tracked_files.txt",
    "included_untracked_sources.txt",
    "excluded_paths.json",
    "git_status.txt",
    "git_diff.patch",
    "git_diff_stat.txt",
    "git_diff_name_status.txt",
    "import_graph.json",
    "versions.json",
    "test_results.json",
    "secret_findings.json",
    "localcomet_runtime_manifest.json",
}
TEXT_SUFFIXES = (".txt", ".json", ".md", ".patch", ".py", ".csv", ".yml", ".yaml", ".toml", ".html", ".css", ".js")


class VerificationFailure(Exception):
    pass


def _ok_result() -> dict[str, Any]:
    return {
        "mode": "audit_bundle_verification",
        "version": VERIFIER_SCHEMA_VERSION,
        "ok": False,
        "legacy_schema": False,
        "bundle_id": "",
        "integrity": {},
        "security": {},
        "missing": [],
        "unexpected": [],
        "hash_mismatches": [],
        "secret_findings": [],
        "warnings": [],
        "summary": {},
    }


def _safe_zip_name(name: str) -> None:
    if not name or "\\" in name:
        raise VerificationFailure("archive path contains empty text or backslash")
    if unicodedata.normalize("NFKC", name) != name:
        raise VerificationFailure("archive path changes under Unicode NFKC normalization")
    if name.startswith("/") or name.startswith("\\"):
        raise VerificationFailure("archive path is absolute")
    pure = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise VerificationFailure("archive path contains traversal or empty segment")


def _source_rel_from_entry(bundle_root: str, name: str) -> str | None:
    prefix = f"{bundle_root}/source/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :]


def _metadata_rel_from_entry(bundle_root: str, name: str) -> str | None:
    prefix = f"{bundle_root}/metadata/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :]


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _json_from_zip(zipf: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(zipf.read(name).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationFailure(f"malformed JSON: {name}: {exc}") from exc


def _recompute_bundle_id(manifest: dict[str, Any]) -> str:
    base = dict(manifest)
    base["bundle_id"] = None
    base.pop("bundle_name", None)
    base.pop("created_at_utc", None)
    return hashlib.sha256(_json_bytes(base)).hexdigest()[:16]


def _excluded_source_present(rel: str) -> bool:
    if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return True
    if _matches_any(rel, EXCLUDE_GLOBS):
        return True
    return False


def verify_bundle(
    bundle_zip: Path,
    max_entries: int = 10000,
    max_uncompressed_mb: float = 500,
    max_single_file_mb: float = 10,
    max_compression_ratio: float = 100.0,
) -> dict[str, Any]:
    result = _ok_result()
    bundle_zip = bundle_zip.expanduser()
    try:
        with zipfile.ZipFile(bundle_zip, "r") as zipf:
            infos = zipf.infolist()
            names = [info.filename for info in infos]
            if len(names) > max_entries:
                raise VerificationFailure("archive exceeds max entry count")
            if len(names) != len(set(names)):
                raise VerificationFailure("duplicate ZIP entries detected")
            if not names:
                raise VerificationFailure("empty archive")
            for info in infos:
                _safe_zip_name(info.filename)
                if _is_symlink(info):
                    raise VerificationFailure("symlink ZIP entry rejected")
            bundle_roots = {PurePosixPath(name).parts[0] for name in names}
            if len(bundle_roots) != 1:
                raise VerificationFailure("archive must contain exactly one bundle root")
            bundle_root = next(iter(bundle_roots))
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > int(max_uncompressed_mb * 1024 * 1024):
                raise VerificationFailure("archive exceeds max uncompressed size")
            for info in infos:
                if info.file_size > int(max_single_file_mb * 1024 * 1024):
                    raise VerificationFailure(f"entry exceeds max file size: {info.filename}")
                if info.compress_size == 0 and info.file_size > 0:
                    raise VerificationFailure(f"entry has suspicious compression metadata: {info.filename}")
                if info.compress_size and info.file_size / max(info.compress_size, 1) > max_compression_ratio:
                    raise VerificationFailure(f"entry compression ratio is suspicious: {info.filename}")

            metadata_names = {
                rel
                for name in names
                for rel in [_metadata_rel_from_entry(bundle_root, name)]
                if rel is not None
            }
            missing_metadata = sorted(REQUIRED_METADATA - metadata_names)
            if missing_metadata:
                result["missing"].extend(f"metadata/{name}" for name in missing_metadata)
                raise VerificationFailure("required metadata missing")
            manifest_name = f"{bundle_root}/metadata/bundle_manifest.json"
            manifest = _json_from_zip(zipf, manifest_name)
            if not isinstance(manifest, dict):
                raise VerificationFailure("bundle manifest must be an object")
            if manifest.get("release") not in {RELEASE, "v6.80.1"}:
                raise VerificationFailure("unsupported bundle release")
            legacy_schema = manifest.get("release") == "v6.80.1" or "bundle_integrity.json" not in metadata_names
            result["legacy_schema"] = bool(legacy_schema)
            if manifest.get("hash_algorithm") != "sha256":
                raise VerificationFailure("unsupported hash algorithm")
            files = manifest.get("files")
            if not isinstance(files, list):
                raise VerificationFailure("manifest files must be a list")
            listed_paths: list[str] = []
            source_hashes: dict[str, str] = {}
            for item in files:
                if not isinstance(item, dict):
                    raise VerificationFailure("manifest file item must be an object")
                rel = item.get("path")
                digest = item.get("sha256")
                if not isinstance(rel, str) or not isinstance(digest, str):
                    raise VerificationFailure("manifest file item missing path or sha256")
                _safe_zip_name(rel)
                if rel != PurePosixPath(rel).as_posix() or rel in listed_paths:
                    raise VerificationFailure("manifest paths must be sorted unique normalized paths")
                if _excluded_source_present(rel):
                    raise VerificationFailure(f"excluded path present in source manifest: {rel}")
                listed_paths.append(rel)
                source_hashes[rel] = digest
            if listed_paths != sorted(listed_paths, key=str.lower):
                raise VerificationFailure("manifest paths are not sorted")
            source_entries = sorted(
                rel
                for name in names
                for rel in [_source_rel_from_entry(bundle_root, name)]
                if rel is not None
            )
            listed_sorted = sorted(listed_paths, key=str.lower)
            missing_sources = sorted(set(listed_sorted) - set(source_entries), key=str.lower)
            unexpected_sources = sorted(set(source_entries) - set(listed_sorted), key=str.lower)
            result["missing"].extend(missing_sources)
            result["unexpected"].extend(unexpected_sources)
            if missing_sources or unexpected_sources:
                raise VerificationFailure("source entries do not match manifest")
            for rel in listed_sorted:
                data = zipf.read(f"{bundle_root}/source/{rel}")
                digest = hashlib.sha256(data).hexdigest()
                if digest != source_hashes[rel]:
                    result["hash_mismatches"].append({"path": rel, "expected": source_hashes[rel], "actual": digest})
            if result["hash_mismatches"]:
                raise VerificationFailure("source hash mismatch")
            file_hashes_name = f"{bundle_root}/metadata/file_hashes_sha256.json"
            file_hashes = _json_from_zip(zipf, file_hashes_name)
            if file_hashes != source_hashes:
                raise VerificationFailure("file_hashes_sha256.json does not match manifest")
            expected_bundle_id = _recompute_bundle_id(manifest)
            if manifest.get("bundle_id") != expected_bundle_id:
                raise VerificationFailure("bundle_id does not match deterministic manifest content")
            for name in names:
                logical_name = name[len(bundle_root) + 1 :] if name.startswith(bundle_root + "/") else name
                if logical_name in {"metadata/secret_findings.json", "metadata/metadata_secret_findings.json"}:
                    continue
                suffix = PurePosixPath(name).suffix.lower()
                if suffix in TEXT_SUFFIXES or "/metadata/" in name or name.endswith("README_AUDIT.md"):
                    text = zipf.read(name).decode("utf-8", errors="ignore")
                    for finding in scan_text_for_secret_markers(text):
                        result["secret_findings"].append(
                            {"file": name, "line": finding["line"], "category": finding["category"]}
                        )
            integrity_name = f"{bundle_root}/metadata/bundle_integrity.json"
            if "bundle_integrity.json" in metadata_names:
                integrity = _json_from_zip(zipf, integrity_name)
                if integrity.get("bundle_id") != manifest.get("bundle_id"):
                    raise VerificationFailure("bundle_integrity bundle_id mismatch")
                expected_count = len(names)
                if integrity.get("entry_count") != expected_count:
                    raise VerificationFailure("bundle_integrity entry count mismatch")
                entry_hashes = integrity.get("entry_sha256")
                if not isinstance(entry_hashes, dict):
                    raise VerificationFailure("bundle_integrity entry_sha256 missing")
                logical_names = sorted(
                    name[len(bundle_root) + 1 :]
                    for name in names
                    if name != integrity_name
                )
                if sorted(entry_hashes, key=str.lower) != sorted(logical_names, key=str.lower):
                    raise VerificationFailure("bundle_integrity entry list mismatch")
                for logical_name in logical_names:
                    actual = hashlib.sha256(zipf.read(f"{bundle_root}/{logical_name}")).hexdigest()
                    if entry_hashes.get(logical_name) != actual:
                        raise VerificationFailure(f"bundle_integrity hash mismatch: {logical_name}")
                result["integrity"] = {
                    "bundle_id_recomputed": expected_bundle_id,
                    "hashes_verified": len(listed_sorted),
                    "entry_count": expected_count,
                    "uncompressed_size": total_uncompressed,
                }
            else:
                result["warnings"].append("metadata/bundle_integrity.json missing in legacy bundle")
                result["integrity"] = {
                    "bundle_id_recomputed": expected_bundle_id,
                    "hashes_verified": len(listed_sorted),
                    "entry_count": len(names),
                    "uncompressed_size": total_uncompressed,
                }
            result["ok"] = True
            result["bundle_id"] = str(manifest.get("bundle_id"))
            result["security"] = {
                "path_checks": "PASS",
                "duplicate_entries": "PASS",
                "symlink_entries": "PASS",
                "limits": "PASS",
                "secret_marker_count": len(result["secret_findings"]),
            }
            result["summary"] = {
                "source_files": len(listed_sorted),
                "metadata_files": len(metadata_names),
                "entries": len(names),
                "warnings": len(result["warnings"]),
                "legacy_schema": bool(result["legacy_schema"]),
            }
            result["_source_hashes"] = source_hashes
            result["_git_status_sha256"] = hashlib.sha256(zipf.read(f"{bundle_root}/metadata/git_status.txt")).hexdigest()
            result["_versions_sha256"] = hashlib.sha256(zipf.read(f"{bundle_root}/metadata/versions.json")).hexdigest()
            result["_categories"] = manifest.get("categories", {})
            return result
    except VerificationFailure as exc:
        result["ok"] = False
        result["warnings"].append(redact_text(str(exc)))
        return result
    except Exception as exc:
        raise RuntimeError(redact_text(f"{type(exc).__name__}: {exc}")) from exc


def compare_bundles(new_zip: Path, old_zip: Path, **limits: Any) -> dict[str, Any]:
    old = verify_bundle(old_zip, **limits)
    new = verify_bundle(new_zip, **limits)
    if not old.get("ok") or not new.get("ok"):
        raise VerificationFailure("cannot compare invalid bundle")
    old_hashes = old["_source_hashes"]
    new_hashes = new["_source_hashes"]
    old_paths = set(old_hashes)
    new_paths = set(new_hashes)
    metadata_changes: list[str] = []
    if old.get("_git_status_sha256") != new.get("_git_status_sha256"):
        metadata_changes.append("git_status")
    if old.get("_versions_sha256") != new.get("_versions_sha256"):
        metadata_changes.append("versions")
    if old.get("_categories") != new.get("_categories"):
        metadata_changes.append("manifest_categories")
    return {
        "mode": "audit_bundle_comparison",
        "version": VERIFIER_SCHEMA_VERSION,
        "old_bundle_id": old["bundle_id"],
        "new_bundle_id": new["bundle_id"],
        "added": sorted(new_paths - old_paths, key=str.lower),
        "modified": sorted((p for p in old_paths & new_paths if old_hashes[p] != new_hashes[p]), key=str.lower),
        "removed": sorted(old_paths - new_paths, key=str.lower),
        "unchanged": sorted((p for p in old_paths & new_paths if old_hashes[p] == new_hashes[p]), key=str.lower),
        "metadata_changes": sorted(metadata_changes),
        "summary": {
            "old_source_files": len(old_hashes),
            "new_source_files": len(new_hashes),
            "source_changes": len(new_paths - old_paths)
            + len(old_paths - new_paths)
            + sum(1 for p in old_paths & new_paths if old_hashes[p] != new_hashes[p]),
            "metadata_only": bool(metadata_changes)
            and old_hashes == new_hashes,
        },
    }


def _public(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify LocalComet audit bundle integrity.")
    parser.add_argument("bundle")
    parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    parser.add_argument("--compare", default=None, help="Previous bundle zip to compare against.")
    parser.add_argument("--max-entries", type=int, default=10000)
    parser.add_argument("--max-uncompressed-mb", type=float, default=500.0)
    parser.add_argument("--max-single-file-mb", type=float, default=10.0)
    parser.add_argument("--max-compression-ratio", type=float, default=100.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    limits = {
        "max_entries": args.max_entries,
        "max_uncompressed_mb": args.max_uncompressed_mb,
        "max_single_file_mb": args.max_single_file_mb,
        "max_compression_ratio": args.max_compression_ratio,
    }
    try:
        if args.compare:
            payload = compare_bundles(Path(args.bundle), Path(args.compare), **limits)
        else:
            payload = verify_bundle(Path(args.bundle), **limits)
        public = _public(payload)
        if args.json:
            print(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            if public.get("ok", True):
                print(f"OK {public.get('bundle_id', public.get('new_bundle_id', 'comparison'))}")
            else:
                print("FAIL " + "; ".join(public.get("warnings", [])))
        return 0 if public.get("ok", True) else 1
    except VerificationFailure as exc:
        payload = {"mode": "audit_bundle_comparison", "version": VERIFIER_SCHEMA_VERSION, "ok": False, "warnings": [redact_text(str(exc))]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("FAIL " + payload["warnings"][0])
        return 1
    except Exception as exc:
        message = redact_text(f"{type(exc).__name__}: {exc}")
        if args.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("ERROR " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
````

