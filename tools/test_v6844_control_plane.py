from __future__ import annotations

import builtins
import hashlib
import json
import socket
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "desktop" / "localcomet-desktop"
TAURI_SRC = DESKTOP / "src-tauri" / "src"
RUNNER = ROOT / "tools" / "run_localcomet_desktop_sidecar.py"
CHECK_COUNT = 0


def check(condition: bool, message: str) -> None:
    global CHECK_COUNT
    CHECK_COUNT += 1
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def decode_from_stream(stream) -> dict[str, Any]:
    prefix = stream.read(4)
    check(len(prefix) == 4, "frame prefix missing")
    length = struct.unpack(">I", prefix)[0]
    check(0 < length <= 4_194_304, "frame length invalid")
    body = stream.read(length)
    check(len(body) == length, "frame body truncated")
    from modules.desktop_ipc_contract_ru import decode_frame

    return decode_frame(prefix + body)


def request(message_id: str, method: str, payload: dict[str, Any]) -> bytes:
    from modules.desktop_ipc_contract_ru import encode_frame, make_request

    return encode_frame(make_request(message_id, method, payload))


def run_control_plane_unit_checks() -> None:
    import importlib

    before = {path.relative_to(ROOT).as_posix(): sha256(path) for path in [ROOT / "modules" / "desktop_control_plane_ru.py"]}
    module = importlib.import_module("modules.desktop_control_plane_ru")
    after = {path.relative_to(ROOT).as_posix(): sha256(path) for path in [ROOT / "modules" / "desktop_control_plane_ru.py"]}
    check(before == after, "control-plane import mutated files")

    limits = module.default_control_plane_limits()
    check(limits.maximum_sessions == 16, "session limit default wrong")
    check(limits.maximum_threads_per_session == 32, "thread limit default wrong")
    check(limits.maximum_turns_per_thread == 64, "turn limit default wrong")
    check(limits.maximum_items_per_turn == 128, "item limit default wrong")
    check(limits.maximum_prompt_characters == 8192, "prompt limit default wrong")
    check(limits.maximum_events_per_request == 64, "event limit default wrong")
    check(limits.maximum_knowledge_review_artifacts == 128, "review artifact limit wrong")
    check(limits.maximum_knowledge_review_page_size == 50, "review page limit wrong")
    for bad in [0, -1, True, 1.5, 65]:
        try:
            module.ControlPlaneLimits(maximum_sessions=bad)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"bad limit accepted: {bad!r}")

    ids = (f"{index:024x}" for index in range(1, 500))
    plane = module.DesktopControlPlane(id_factory=lambda: next(ids))
    boot = plane.dispatch("app.bootstrap", {}, request_id="req-bootstrap")
    payload = boot.response
    check(payload["control_plane_version"] == "v6.84.5.1", "bootstrap version wrong")
    check(
        set(payload)
        == {
            "control_plane_version",
            "protocol",
            "protocol_version",
            "sidecar_runtime_version",
            "capabilities",
            "limits",
            "counts",
            "sidecar_ready",
            "persistence",
            "models_connected",
            "provider_registry_available",
            "harness_registry_available",
        },
        "bootstrap payload shape changed",
    )
    check(payload["protocol"] == "localcomet.ipc", "bootstrap protocol wrong")
    check(payload["protocol_version"] == "1.0", "bootstrap protocol version wrong")
    check(payload["sidecar_runtime_version"] == "v6.84.3", "sidecar runtime version wrong")
    check(payload["capabilities"] == sorted(payload["capabilities"]), "capabilities not sorted")
    check("turn.start_mock" in payload["capabilities"], "mock turn capability missing")
    check("knowledge.review.list" in payload["capabilities"], "review list capability missing")
    check("knowledge.review.get" in payload["capabilities"], "review get capability missing")
    check("knowledge.review.snapshot" in payload["capabilities"], "review snapshot capability missing")
    check("knowledge.review.refresh" in payload["capabilities"], "review refresh capability missing")
    check(
        "knowledge.review.decision.create" in payload["capabilities"],
        "review decision capability missing",
    )
    check(
        payload["counts"]
        == {
            "sessions": 0,
            "threads": 0,
            "turns": 0,
            "active_turns": 0,
            "knowledge_reviews": 0,
            "human_review_decisions": 0,
        },
        "initial counts not zero",
    )
    check(payload["persistence"] is False, "persistence not false")
    check(payload["models_connected"] is False, "models connected invented")
    check(payload["provider_registry_available"] is False, "provider registry invented")
    check(payload["harness_registry_available"] is False, "harness registry invented")
    check("session_nonce" not in json.dumps(payload), "session nonce leaked")

    import tools.test_v68451e9b_knowledge_review as e9b_fixtures
    from modules.knowledge_change_proposal_ru import ProposalOperation

    empty_reviews = plane.dispatch(
        "knowledge.review.list",
        {"offset": 0, "limit": 50},
        request_id="req-review-empty",
    )
    check(empty_reviews.events == (), "empty review list emitted events")
    check(
        set(empty_reviews.response)
        == {
            "contract",
            "source",
            "fixture",
            "offset",
            "limit",
            "total_count",
            "returned_count",
            "truncated",
            "next_offset",
            "items",
        },
        "review list envelope shape wrong",
    )
    check(empty_reviews.response["contract"] == "localcomet.knowledge-review-list/1.0", "review list contract wrong")
    check(empty_reviews.response["source"] == "LOCAL_CONTROL_PLANE", "review list source wrong")
    check(empty_reviews.response["fixture"] is False, "review list claimed fixture")
    check(empty_reviews.response["items"] == [], "production review queue not empty")
    check(empty_reviews.response["total_count"] == 0, "empty review total wrong")
    check(empty_reviews.response["returned_count"] == 0, "empty review returned count wrong")
    check(empty_reviews.response["truncated"] is False, "empty review list truncated")
    check(empty_reviews.response["next_offset"] is None, "empty review continuation invented")

    helper = e9b_fixtures.KnowledgeReviewBehaviorTests()
    clear_create = helper.clear_create_artifact()
    clear_update = helper.clear_update_artifact()
    blocked_proposal = helper.make_proposal(
        operation=ProposalOperation.CREATE_NEW,
        target=e9b_fixtures.OTHER_TARGET,
        body="blocked review\n",
    )
    blocked_validation = helper.validate(
        blocked_proposal,
        stable_ids={e9b_fixtures.TARGET},
    )
    blocked = helper.review(
        blocked_proposal,
        blocked_validation,
        helper.state(stable_ids={e9b_fixtures.TARGET, e9b_fixtures.OTHER_TARGET}),
    )
    caller_reviews = [clear_update, clear_create]
    caller_before = tuple(caller_reviews)

    class FailKnowledgeAdapter:
        def __getattr__(self, name: str):
            raise AssertionError(f"review read touched knowledge adapter: {name}")

    review_plane = module.DesktopControlPlane(
        knowledge_adapter=FailKnowledgeAdapter(),
        knowledge_reviews=caller_reviews,
    )
    check(tuple(caller_reviews) == caller_before, "review constructor mutated caller list")
    caller_reviews.append(blocked)
    first_page = review_plane.dispatch(
        "knowledge.review.list",
        {"offset": 0, "limit": 1},
        request_id="req-review-page-1",
    )
    second_page = review_plane.dispatch(
        "knowledge.review.list",
        {"offset": 1, "limit": 1},
        request_id="req-review-page-2",
    )
    end_page = review_plane.dispatch(
        "knowledge.review.list",
        {"offset": 2, "limit": 1},
        request_id="req-review-page-end",
    )
    listed_ids = [
        first_page.response["items"][0]["review_artifact_identity"],
        second_page.response["items"][0]["review_artifact_identity"],
    ]
    check(listed_ids == sorted(listed_ids), "review list ordering is not deterministic")
    check(first_page.response["total_count"] == 2, "caller mutation changed owned reviews")
    check(first_page.response["returned_count"] == 1, "first review page count wrong")
    check(first_page.response["truncated"] is True, "first review page not truncated")
    check(first_page.response["next_offset"] == 1, "first review continuation wrong")
    check(first_page.response["items"][0]["kind"] == "KNOWLEDGE_CHANGE_REVIEW_SUMMARY", "review summary kind wrong")
    check(second_page.response["truncated"] is False, "final review page truncated")
    check(second_page.response["next_offset"] is None, "final review continuation invented")
    check(end_page.response["items"] == [], "offset-at-end review page not empty")
    check(end_page.response["returned_count"] == 0, "offset-at-end count wrong")

    selected_identity = listed_ids[0]
    selected_artifact = next(
        artifact
        for artifact in caller_before
        if artifact.review_artifact_identity == selected_identity
    )
    exact_get = review_plane.dispatch(
        "knowledge.review.get",
        {"review_artifact_identity": selected_identity},
        request_id="req-review-get",
    )
    check(exact_get.events == (), "review get emitted events")
    check(
        set(exact_get.response) == {"contract", "source", "fixture", "projection"},
        "review get envelope shape wrong",
    )
    check(exact_get.response["contract"] == "localcomet.knowledge-review-get/1.0", "review get contract wrong")
    check(exact_get.response["source"] == "LOCAL_CONTROL_PLANE", "review get source wrong")
    check(exact_get.response["fixture"] is False, "review get claimed fixture")
    check(exact_get.response["projection"]["kind"] == "KNOWLEDGE_CHANGE_REVIEW", "review get projection kind wrong")
    check(exact_get.response["projection"]["proposal_id"] == selected_artifact.proposal_id, "review get proposal changed")
    check(exact_get.response["projection"]["review_artifact_identity"] == selected_identity, "review get identity changed")

    blocked_plane = module.DesktopControlPlane(knowledge_reviews=[blocked])
    blocked_get = blocked_plane.dispatch(
        "knowledge.review.get",
        {"review_artifact_identity": blocked.review_artifact_identity},
        request_id="req-review-blocked",
    ).response["projection"]
    check(blocked_get["status"] == "BLOCKED", "blocked review status lost")
    check(blocked_get["change_identity"] is None, "blocked review change identity invented")
    check(blocked_get["diff"] is None, "blocked review diff invented")
    check(blocked_get["representation_delta"] is None, "blocked review delta invented")

    try:
        review_plane.dispatch(
            "knowledge.review.get",
            {"review_artifact_identity": "kreview:" + "f" * 64},
            request_id="req-review-missing",
        )
    except module.ControlPlaneError as exc:
        check(exc.code == "request_not_found", "unknown review identity wrong code")
    else:
        raise AssertionError("unknown review identity accepted")

    invalid_review_requests = (
        ("knowledge.review.list", {}),
        ("knowledge.review.list", {"offset": 0, "limit": 1, "extra": True}),
        ("knowledge.review.list", {"offset": True, "limit": 1}),
        ("knowledge.review.list", {"offset": -1, "limit": 1}),
        ("knowledge.review.list", {"offset": 129, "limit": 1}),
        ("knowledge.review.list", {"offset": 0, "limit": 0}),
        ("knowledge.review.list", {"offset": 0, "limit": 51}),
        ("knowledge.review.get", {}),
        ("knowledge.review.get", {"review_artifact_identity": "kreview:bad"}),
        (
            "knowledge.review.get",
            {"review_artifact_identity": selected_identity, "extra": True},
        ),
    )
    for index, (method, invalid_payload) in enumerate(invalid_review_requests):
        try:
            review_plane.dispatch(method, invalid_payload, request_id=f"req-review-invalid-{index}")
        except module.ControlPlaneError as exc:
            check(exc.code == "invalid_payload", f"invalid review request {index} wrong code")
        else:
            raise AssertionError(f"invalid review request {index} accepted")

    for bad_reviews in (
        {"artifact": clear_create},
        [object()],
    ):
        try:
            module.DesktopControlPlane(knowledge_reviews=bad_reviews)
        except TypeError:
            pass
        else:
            raise AssertionError("invalid review dependency accepted")
    try:
        module.DesktopControlPlane(knowledge_reviews=[clear_create, clear_create])
    except ValueError as exc:
        check("duplicate" in str(exc), "duplicate review rejection not explicit")
    else:
        raise AssertionError("duplicate review identity accepted")
    try:
        module.DesktopControlPlane(knowledge_reviews=[clear_create] * 129)
    except ValueError as exc:
        check("limit" in str(exc), "review count rejection not explicit")
    else:
        raise AssertionError("review artifact count overflow accepted")

    with (
        mock.patch.object(builtins, "open", side_effect=AssertionError("filesystem")),
        mock.patch.object(Path, "open", side_effect=AssertionError("filesystem")),
        mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
        mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
    ):
        safe_list = review_plane.dispatch(
            "knowledge.review.list",
            {"offset": 0, "limit": 1},
            request_id="req-review-no-io-list",
        )
        safe_get = review_plane.dispatch(
            "knowledge.review.get",
            {"review_artifact_identity": selected_identity},
            request_id="req-review-no-io-get",
        )
    check(safe_list.response["returned_count"] == 1, "no-I/O review list failed")
    check(safe_get.response["projection"]["review_artifact_identity"] == selected_identity, "no-I/O review get failed")

    original_summary_projector = module.project_knowledge_change_review_summary
    original_full_projector = module.project_knowledge_change_review
    try:
        def reject_summary(_artifact):
            raise module.ProjectionRejected(module.ProjectionRejectionCode.SERIALIZATION_FAILED)

        module.project_knowledge_change_review_summary = reject_summary
        try:
            review_plane.dispatch(
                "knowledge.review.list",
                {"offset": 0, "limit": 1},
                request_id="req-review-projection-error",
            )
        except module.ControlPlaneError as exc:
            check(exc.code == "internal_error", "summary projection failure wrong code")
            check(exc.message == "knowledge review projection failed", "summary projection failure leaked detail")
        else:
            raise AssertionError("summary projection failure escaped mapping")

        def reject_full(_artifact):
            raise module.ProjectionRejected(
                module.ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED
            )

        module.project_knowledge_change_review = reject_full
        try:
            review_plane.dispatch(
                "knowledge.review.get",
                {"review_artifact_identity": selected_identity},
                request_id="req-review-projection-large",
            )
        except module.ControlPlaneError as exc:
            check(exc.code == "payload_too_large", "large projection failure wrong code")
            check("Traceback" not in exc.message, "projection error leaked traceback")
        else:
            raise AssertionError("large projection failure escaped mapping")
    finally:
        module.project_knowledge_change_review_summary = original_summary_projector
        module.project_knowledge_change_review = original_full_projector

    for forbidden_method in (
        "knowledge.review.register",
        "knowledge.review.create",
        "knowledge.review.update",
        "knowledge.review.delete",
        "knowledge.review.publish",
        "knowledge.review.write",
        "knowledge.review.register",
        "knowledge.review.upload",
    ):
        check(forbidden_method not in module.CONTROL_PLANE_METHODS, f"forbidden review method present: {forbidden_method}")

    session = plane.dispatch("session.create", {"title": "  demo   title  "}, request_id="req-session")
    check(session.response["state"] == "OPEN", "session create did not open")
    check(session.response["title"] == "demo title", "session title not normalized")
    check(session.events[0].method == "session.created", "session created event missing")
    check(
        set(session.events[0].payload)
        == {
            "control_plane_version",
            "session_id",
            "thread_id",
            "turn_id",
            "item_id",
            "state",
            "kind",
            "text",
            "metadata",
        },
        "event payload shape changed",
    )
    session_id = session.response["session_id"]
    check(len(session_id) == 24 and all(ch in "0123456789abcdef" for ch in session_id), "session id invalid")
    check(plane.dispatch("session.get", {"session_id": session_id}, request_id="req-session-get").response["session_id"] == session_id, "session get failed")
    try:
        plane.dispatch("session.get", {"session_id": "0" * 24}, request_id="req-bad-session")
    except module.ControlPlaneError as exc:
        check(exc.code == "request_not_found", "unknown session wrong code")
    else:
        raise AssertionError("unknown session accepted")

    thread = plane.dispatch("thread.create", {"session_id": session_id, "title": "Thread"}, request_id="req-thread")
    thread_id = thread.response["thread_id"]
    check(thread.events[0].method == "thread.created", "thread created event missing")
    check(thread.response["session_id"] == session_id, "thread session mismatch")
    check(plane.dispatch("thread.get", {"thread_id": thread_id}, request_id="req-thread-get").response["thread_id"] == thread_id, "thread get failed")

    leaky_path = "C:" + "\\Users\\DNS\\x"
    leaky_path_prefix = "C:" + "\\Users\\DNS"
    complete = plane.dispatch(
        "turn.start_mock",
        {"thread_id": thread_id, "prompt": f"Tell me a secret sk-1234567890 at {leaky_path}", "behavior": "complete"},
        request_id="req-complete",
    )
    check(complete.response["state"] == "COMPLETED", "complete turn state wrong")
    check(complete.response["model_called"] is False, "model was called")
    check(complete.response["tools_executed"] == 0, "tool execution invented")
    check(complete.response["events_emitted"] == 10, "complete event count wrong")
    check([event.sequence for event in complete.events] == list(range(10)), "complete event sequence wrong")
    check(complete.events[0].method == "turn.started", "turn started not first")
    check(complete.events[-1].method == "turn.completed", "turn completed not last")
    text = "\n".join(str(event.payload.get("text") or "") for event in complete.events)
    check("No language model was called" in text, "demo text does not deny model call")
    check("no tool execution occurred" in text, "demo text does not deny tool execution")
    serialized = json.dumps([event.payload for event in complete.events])
    check("sk-1234567890" not in serialized, "secret prompt leaked")
    check(leaky_path_prefix not in serialized, "machine path leaked")
    status = plane.dispatch("turn.status", {"turn_id": complete.response["turn_id"]}, request_id="req-status").response
    check("prompt_sha256" in status, "prompt hash missing")
    status_blob = json.dumps(status)
    check("sk-1234567890" not in status_blob and leaky_path_prefix not in status_blob, "raw prompt retained")

    wait = plane.dispatch("turn.start_mock", {"thread_id": thread_id, "prompt": "cancel this", "behavior": "wait_for_cancel"}, request_id="req-wait")
    turn_id = wait.response["turn_id"]
    check(wait.response["state"] == "RUNNING", "wait turn not running")
    check(wait.response["events_emitted"] == 5, "wait event count wrong")
    try:
        plane.dispatch("session.close", {"session_id": session_id}, request_id="req-close-running")
    except module.ControlPlaneError as exc:
        check(exc.code == "busy", "running close wrong code")
    else:
        raise AssertionError("session closed while running")
    cancel = plane.dispatch("turn.cancel", {"turn_id": turn_id, "reason": "user_requested"}, request_id="req-cancel")
    check(cancel.response["state"] == "CANCELLED", "cancel did not terminally cancel")
    check(cancel.events[0].method == "turn.cancelled", "cancel event missing")
    check(plane.dispatch("turn.cancel", {"turn_id": turn_id, "reason": "user_requested"}, request_id="req-cancel-2").response["already_cancelled"], "duplicate cancel not idempotent")
    closed = plane.dispatch("session.close", {"session_id": session_id}, request_id="req-close")
    check(closed.response["state"] == "CLOSED", "session did not close")
    check(plane.dispatch("session.close", {"session_id": session_id}, request_id="req-close-2").response["state"] == "CLOSED", "session close not idempotent")
    try:
        plane.dispatch("thread.create", {"session_id": session_id, "title": "late"}, request_id="req-late-thread")
    except module.ControlPlaneError as exc:
        check(exc.code == "invalid_payload", "closed session thread wrong code")
    else:
        raise AssertionError("closed session accepted thread")

    check(module.validate_control_plane_payload("model.run", {}) == ("unsupported_method",), "unsupported method not rejected")
    check("approval.required" not in json.dumps(module.serialize_control_plane_metadata()).lower(), "approval runtime leaked into metadata")
    control_text = read(TAURI_SRC / "control_plane.rs")
    check(
        control_text.count("state.emit_sidecar_status();") == 1,
        "bootstrap does not emit exactly one subscribed sidecar status event",
    )


def run_sidecar_transcripts() -> None:
    from modules.desktop_ipc_contract_ru import encode_frame, make_hello

    process = subprocess.Popen(
        [sys.executable, "-I", "-B", str(RUNNER)],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        hello = decode_from_stream(process.stdout)
        check(hello["type"] == "hello", "sidecar hello missing")
        expected_review_capabilities = {
            "knowledge.review.list",
            "knowledge.review.get",
            "knowledge.review.snapshot",
            "knowledge.review.refresh",
            "knowledge.review.decision.create",
        }
        check(
            expected_review_capabilities.issubset(set(hello["payload"]["capabilities"])),
            "sidecar Knowledge Operations capabilities missing",
        )
        process.stdin.write(request("pre-hello", "app.bootstrap", {}))
        process.stdin.flush()
        pre_hello = decode_from_stream(process.stdout)
        check(pre_hello["type"] == "error" and pre_hello["payload"]["code"] == "sidecar_unavailable", "request before hello not rejected")
        process.stdin.write(encode_frame(make_hello("desktop-hello", session_nonce="1" * 24, capabilities=("lifecycle",))))
        process.stdin.flush()
        check(decode_from_stream(process.stdout)["type"] == "hello", "desktop hello reply missing")
        process.stdin.write(request("bootstrap", "app.bootstrap", {}))
        process.stdin.flush()
        bootstrap = decode_from_stream(process.stdout)
        check(bootstrap["type"] == "response", "bootstrap did not respond")
        check(bootstrap["payload"]["control_plane_version"] == "v6.84.5.1", "bootstrap response version wrong")
        process.stdin.write(request("review-empty", "knowledge.review.list", {"offset": 0, "limit": 50}))
        process.stdin.flush()
        review_empty = decode_from_stream(process.stdout)
        check(review_empty["type"] == "response", "review list did not return one terminal response")
        check(review_empty["payload"]["items"] == [], "runner production review queue not empty")
        check(review_empty["payload"]["source"] == "LOCAL_CONTROL_PLANE", "runner review source wrong")
        check(review_empty["payload"]["fixture"] is False, "runner review queue claimed fixture")
        process.stdin.write(request("review-snapshot", "knowledge.review.snapshot", {}))
        process.stdin.flush()
        review_snapshot = decode_from_stream(process.stdout)
        check(review_snapshot["type"] == "response", "review snapshot did not return one terminal response")
        check(review_snapshot["payload"]["command_center_version"] == "v6.84.6", "command center version wrong")
        check(review_snapshot["payload"]["inbox_count"] == 0, "empty runtime snapshot inbox count wrong")
        check(review_snapshot["payload"]["hard_stop"] is True, "review snapshot lost HARD STOP")
        check(review_snapshot["payload"]["vault_write_authority"] is False, "review snapshot granted Vault write")
        check(review_snapshot["payload"]["publication_authority"] is False, "review snapshot granted publication")
        process.stdin.write(request("session", "session.create", {"title": "Demo"}))
        process.stdin.flush()
        session_event = decode_from_stream(process.stdout)
        session_response = decode_from_stream(process.stdout)
        check(session_event["type"] == "event" and session_event["method"] == "session.created", "session event missing")
        session_id = session_response["payload"]["session_id"]
        process.stdin.write(request("thread", "thread.create", {"session_id": session_id, "title": "Thread"}))
        process.stdin.flush()
        thread_event = decode_from_stream(process.stdout)
        thread_response = decode_from_stream(process.stdout)
        check(thread_event["method"] == "thread.created", "thread event missing")
        thread_id = thread_response["payload"]["thread_id"]
        process.stdin.write(request("complete", "turn.start_mock", {"thread_id": thread_id, "prompt": "hello", "behavior": "complete"}))
        process.stdin.flush()
        methods = [decode_from_stream(process.stdout)["method"] for _ in range(10)]
        terminal = decode_from_stream(process.stdout)
        check(methods == ["turn.started", "item.started", "item.completed", "item.started", "item.completed", "item.started", "item.delta", "item.delta", "item.completed", "turn.completed"], "complete transcript order wrong")
        check(terminal["type"] == "response" and terminal["payload"]["state"] == "COMPLETED", "complete terminal response wrong")
        process.stdin.write(request("shutdown", "app.shutdown", {}))
        process.stdin.flush()
        check(decode_from_stream(process.stdout)["type"] == "response", "shutdown response missing")
        check(decode_from_stream(process.stdout)["type"] == "goodbye", "shutdown goodbye missing")
    finally:
        if process.stdin:
            process.stdin.close()
    check(process.wait(timeout=10) == 0, "sidecar transcript exit code wrong")
    check(process.stderr.read().decode("utf-8", "replace") == "", "sidecar wrote stderr")

    process = subprocess.Popen(
        [sys.executable, "-I", "-B", str(RUNNER)],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    try:
        decode_from_stream(process.stdout)
        process.stdin.write(encode_frame(make_hello("desktop-hello-2", session_nonce="2" * 24, capabilities=("lifecycle",))))
        process.stdin.flush()
        decode_from_stream(process.stdout)
        process.stdin.write(request("s2", "session.create", {"title": "Cancel"}))
        process.stdin.flush()
        decode_from_stream(process.stdout)
        session_id = decode_from_stream(process.stdout)["payload"]["session_id"]
        process.stdin.write(request("t2", "thread.create", {"session_id": session_id, "title": "Cancel"}))
        process.stdin.flush()
        decode_from_stream(process.stdout)
        thread_id = decode_from_stream(process.stdout)["payload"]["thread_id"]
        process.stdin.write(request("wait", "turn.start_mock", {"thread_id": thread_id, "prompt": "wait", "behavior": "wait_for_cancel"}))
        process.stdin.flush()
        for _ in range(5):
            decode_from_stream(process.stdout)
        wait_response = decode_from_stream(process.stdout)
        turn_id = wait_response["payload"]["turn_id"]
        check(wait_response["payload"]["state"] == "RUNNING", "wait transcript not running")
        process.stdin.write(request("turn-status", "turn.status", {"turn_id": turn_id}))
        process.stdin.flush()
        check(decode_from_stream(process.stdout)["payload"]["state"] == "RUNNING", "turn status not running")
        process.stdin.write(request("cancel", "turn.cancel", {"turn_id": turn_id, "reason": "user_requested"}))
        process.stdin.flush()
        cancel_event = decode_from_stream(process.stdout)
        cancel_response = decode_from_stream(process.stdout)
        check(cancel_event["method"] == "turn.cancelled", "cancel event missing")
        check(cancel_response["payload"]["state"] == "CANCELLED", "cancel response wrong")
        process.stdin.write(request("shutdown2", "app.shutdown", {}))
        process.stdin.flush()
        decode_from_stream(process.stdout)
        decode_from_stream(process.stdout)
    finally:
        if process.stdin:
            process.stdin.close()
    check(process.wait(timeout=10) == 0, "cancel transcript exit code wrong")
    check(process.stderr.read().decode("utf-8", "replace") == "", "cancel transcript stderr")


def run_source_checks() -> None:
    control_text = read(TAURI_SRC / "control_plane.rs")
    supervisor_text = read(TAURI_SRC / "supervisor.rs")
    lib_text = read(TAURI_SRC / "lib.rs")
    frontend_text = "\n".join(
        read(path)
        for path in [
            DESKTOP / "src" / "lib" / "bridge" / "controlPlane.ts",
            DESKTOP / "src" / "lib" / "stores" / "controlPlane.ts",
            DESKTOP / "src" / "lib" / "components" / "shell" / "ChatHeader.svelte",
            DESKTOP / "src" / "lib" / "components" / "chat" / "MessageComposer.svelte",
            DESKTOP / "src" / "lib" / "components" / "shell" / "AgentInspector.svelte",
            DESKTOP / "src" / "lib" / "components" / "agent" / "Diagnostics.svelte",
            DESKTOP / "src" / "lib" / "data" / "mockData.ts",
            DESKTOP / "src" / "lib" / "i18n" / "en.ts",
            DESKTOP / "src" / "lib" / "i18n" / "ru.ts",
        ]
    )
    exact_commands = [
        "control_plane_bootstrap",
        "control_plane_create_session",
        "control_plane_close_session",
        "control_plane_create_thread",
        "control_plane_start_mock_turn",
        "control_plane_get_turn_status",
        "control_plane_cancel_turn",
        "model_gateway_catalog",
        "model_gateway_probe",
        "model_gateway_list_models",
        "model_binding_set",
        "model_turn_start",
        "model_turn_cancel",
        "knowledge_review_list",
        "knowledge_review_get",
        "knowledge_review_snapshot",
        "knowledge_review_refresh",
        "knowledge_review_decision_create",
    ]
    for command in exact_commands:
        check(command in control_text and command in lib_text, f"missing Tauri command {command}")
    check(control_text.count("#[tauri::command]") == 18, "wrong Tauri command count")
    check("control_plane_request" not in control_text and "generic_request" not in control_text, "generic Tauri request present")
    check("enum ControlPlaneMethod" in control_text, "closed Rust method enum missing")
    check("From<String>" not in control_text, "arbitrary method conversion present")
    check("MAX_IN_FLIGHT_REQUESTS: usize = 32" in control_text, "bounded registry constant missing")
    check("MAX_EVENTS_PER_REQUEST: usize = 64" in control_text, "event limit constant missing")
    check("MAX_EVENT_TEXT_PER_REQUEST" in control_text, "event text limit missing")
    check("duplicate terminal response" in control_text, "duplicate terminal protection missing")
    check("event after terminal response" in control_text, "event after terminal protection missing")
    check("sidecar.stdout" not in control_text.lower(), "raw stdout exposed")
    check("SidecarFrameRouter" in supervisor_text, "supervisor router missing")
    check("send_ipc_frame" in supervisor_text, "supervisor writer missing")
    check("spawn_stdout_reader" in supervisor_text and supervisor_text.count("spawn_stdout_reader") == 2, "stdout reader structure changed")
    check("automatic restart" not in supervisor_text.lower(), "automatic restart added")
    windows_job_text = read(TAURI_SRC / "windows_job.rs")
    check("JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in windows_job_text, "job kill-on-close missing")
    check("JOB_OBJECT_LIMIT_ACTIVE_PROCESS" in windows_job_text, "job active process limit missing")
    check("ActiveProcessLimit = 1" in windows_job_text, "job active process limit not exactly one")
    check("AssignProcessToJobObject" in windows_job_text and "ResumeThread" in windows_job_text, "assignment before resume proof missing")
    check("localcomet://control-plane-event" in control_text, "exact event channel missing")
    for forbidden in ["@tauri-apps/plugin-shell", "plugin-fs", "plugin-http", "Command::", "std::process", "TcpListener", "UdpSocket"]:
        check(forbidden not in control_text + supervisor_text + lib_text, f"forbidden Rust surface {forbidden}")
    check("bootstrapControlPlane" in frontend_text and "subscribeControlPlaneEvents" in frontend_text, "frontend bridge missing")
    for forbidden in ["fetch(", "WebSocket", "EventSource", "localStorage", "sessionStorage", "indexedDB", "IndexedDB"]:
        check(forbidden not in frontend_text, f"forbidden frontend API {forbidden}")
    check("Control Plane demo" in frontend_text, "composer demo notice missing")
    check("chat.connect_model" in frontend_text and "conn.model_connected" in frontend_text, "header model status missing")
    check("diag.model_called" in frontend_text and "diag.tools_executed" in frontend_text, "inspector facts missing")
    check("Reserved" in frontend_text and "Provider" in frontend_text and "Harness" in frontend_text, "deferred sections missing")
    capability = json.loads(read(DESKTOP / "src-tauri" / "capabilities" / "main.json"))
    permissions = capability["permissions"]
    check("*" not in json.dumps(permissions), "wildcard permission present")
    check("core:event:allow-listen" in permissions and "core:event:allow-unlisten" in permissions, "event listen permissions missing")
    for command in exact_commands:
        check(f"allow-{command.replace('_', '-')}" in permissions, f"permission missing {command}")
    manifest = json.loads(read(ROOT / "localcomet_runtime_manifest.json"))
    check("modules/desktop_control_plane_ru.py" in manifest.get("lazy_runtime", []), "manifest missing control-plane module")
    check("tools/test_v6844_control_plane.py" in manifest.get("tests", []), "manifest missing v6.84.4 test")
    all_paths: list[str] = []
    for category in ["entrypoints", "runtime", "lazy_runtime", "tests", "tools"]:
        values = manifest.get(category, [])
        check(values == sorted(values, key=str.lower), f"manifest not sorted: {category}")
        check(len(values) == len(set(values)), f"manifest duplicate: {category}")
        check(all(not value.startswith("desktop/localcomet-desktop/") for value in values), "desktop file in Python manifest")
        all_paths.extend(values)
    check(len(all_paths) == len(set(all_paths)), "manifest cross-category duplicate")
    check(not (DESKTOP / "node_modules").exists(), "node_modules exists")
    check(not (DESKTOP / "src-tauri" / "target").exists(), "src-tauri target exists")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True, capture_output=True, check=True)
    check(staged.stdout.strip() == "", "staged files are not empty")


def main() -> None:
    run_control_plane_unit_checks()
    run_sidecar_transcripts()
    run_source_checks()
    check(CHECK_COUNT >= 164, f"focused check count too low: {CHECK_COUNT}")
    print(f"ALL v6.84.4 CONTROL PLANE TESTS PASSED ({CHECK_COUNT} checks)")


if __name__ == "__main__":
    main()
