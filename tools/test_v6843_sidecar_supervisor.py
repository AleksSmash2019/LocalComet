from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop" / "localcomet-desktop"
TAURI_SRC = DESKTOP / "src-tauri" / "src"
RUNNER = ROOT / "tools" / "run_localcomet_desktop_sidecar.py"
RUNTIME = ROOT / "modules" / "desktop_sidecar_runtime_ru.py"
MANIFEST = ROOT / "localcomet_runtime_manifest.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORBIDDEN_HASHES = {
    "modules/desktop_ipc_contract_ru.py": "C96538C5DAF210AFFC3AA1796FA6A7D23B29E14F71BEA772ECA32037A580CCF3",
    "tools/test_v6841_desktop_ipc.py": "49F827EC214BB4C2C8A59E1AC0EE9C294DC180B87A6E61467AD2D7D8CE6507CC",
    "docs/desktop_architecture_v6841.md": "A718EB7D53A72097359DABAE76702008D9CF0F87B6697C67444578B1603BCE47",
    "desktop/contracts/localcomet_ipc_v1.schema.json": "A6F5009788DD55246040029E2BAA1D15CE4E365DC4B339EBB7C991AC88D5333A",
}

CHECK_COUNT = 0


def check(condition: bool, message: str) -> None:
    global CHECK_COUNT
    CHECK_COUNT += 1
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rust_tokens(source: str) -> tuple[str, ...]:
    tokens: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if source.startswith("/*", index):
            depth = 1
            index += 2
            while index < length and depth:
                if source.startswith("/*", index):
                    depth += 1
                    index += 2
                elif source.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            continue
        if character == '"':
            start = index
            index += 1
            while index < length:
                if source[index] == "\\":
                    index += 2
                elif source[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            tokens.append(source[start:index])
            continue
        if character == "r" and index + 1 < length and source[index + 1] in {'"', "#"}:
            start = index
            marker = index + 1
            while marker < length and source[marker] == "#":
                marker += 1
            if marker < length and source[marker] == '"':
                hashes = marker - index - 1
                terminator = '"' + ("#" * hashes)
                end = source.find(terminator, marker + 1)
                index = length if end < 0 else end + len(terminator)
                tokens.append(source[start:index])
                continue
        if character.isalpha() or character == "_":
            start = index
            index += 1
            while index < length and (source[index].isalnum() or source[index] == "_"):
                index += 1
            tokens.append(source[start:index])
            continue
        tokens.append(character)
        index += 1
    return tuple(tokens)


def contains_token_sequence(tokens: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return width > 0 and any(tokens[index : index + width] == sequence for index in range(len(tokens) - width + 1))


def rust_function_parts(source: str, name: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    tokens = rust_tokens(source)
    candidates: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for index in range(len(tokens) - 2):
        if tokens[index : index + 3] != ("fn", name, "("):
            continue
        cursor = index + 2
        depth = 0
        close = None
        while cursor < len(tokens):
            if tokens[cursor] == "(":
                depth += 1
            elif tokens[cursor] == ")":
                depth -= 1
                if depth == 0:
                    close = cursor
                    break
            cursor += 1
        if close is None:
            continue
        opening = close + 1
        while opening < len(tokens) and tokens[opening] != "{":
            opening += 1
        if opening == len(tokens):
            continue
        cursor = opening
        depth = 0
        closing = None
        while cursor < len(tokens):
            if tokens[cursor] == "{":
                depth += 1
            elif tokens[cursor] == "}":
                depth -= 1
                if depth == 0:
                    closing = cursor
                    break
            cursor += 1
        if closing is not None:
            candidates.append((tokens[index + 3 : close], tokens[opening + 1 : closing]))
    return candidates[0] if len(candidates) == 1 else None


def startup_log_contract_errors(
    startup_source: str,
    app_data_root_source: str,
    lib_source: str,
    artifact_trust_source: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    startup_parts = rust_function_parts(startup_source, "startup_log_path")
    if startup_parts is None:
        errors.append("startup_log_path must have exactly one implementation")
    else:
        arguments, body = startup_parts
        if arguments:
            errors.append("startup_log_path must accept no caller-supplied path")
        if not contains_token_sequence(
            body,
            ("app_data_root", ":", ":", "resolve_startup_application_data_root", "(", ")"),
        ):
            errors.append("startup log must use the shared startup application-data-root resolver")
        if not contains_token_sequence(
            body,
            ("root", ".", "join", "(", '"logs"', ")", ".", "join", "(", '"startup.log"', ")"),
        ):
            errors.append("startup log must append exactly logs/startup.log to the resolved root")
        startup_strings = tuple(token for token in body if token.count('"') > 0)
        if body.count("join") != 2 or startup_strings != ('"logs"', '"startup.log"'):
            errors.append("startup log derivation must contain no additional path components")
        if '"LOCALAPPDATA"' in body or '"LocalComet"' in body:
            errors.append("startup log must not independently reconstruct the normal profile")

    application_parts = rust_function_parts(app_data_root_source, "resolve_application_data_root")
    startup_root_parts = rust_function_parts(app_data_root_source, "resolve_startup_application_data_root")
    explicit_parts = rust_function_parts(app_data_root_source, "explicit_application_data_root")
    if application_parts is None or startup_root_parts is None or explicit_parts is None:
        errors.append("application-data-root resolver functions are incomplete or ambiguous")
    else:
        _, application_body = application_parts
        _, startup_root_body = startup_root_parts
        _, explicit_body = explicit_parts
        shared_resolution = ("explicit_application_data_root", "(", ")", "?")
        if not contains_token_sequence(application_body, shared_resolution) or not contains_token_sequence(
            startup_root_body, shared_resolution
        ):
            errors.append("product and startup roots must share explicit override validation")
        if not contains_token_sequence(
            application_body,
            ("Some", "(", "root", ")", "=", ">", "Ok", "(", "root", ")"),
        ) or not contains_token_sequence(
            application_body,
            ("None", "=", ">", "Ok", "(", "default_local_data_dir", ".", "join", "(", '"LocalComet"', ")", ")"),
        ):
            errors.append("product root must select the override or default local data plus LocalComet")
        if not contains_token_sequence(
            startup_root_body,
            ("Some", "(", "root", ")", "=", ">", "Ok", "(", "Some", "(", "root", ")", ")"),
        ) or not contains_token_sequence(
            startup_root_body,
            ("None", "=", ">", "Ok", "(", "env", ":", ":", "var_os", "(", '"LOCALAPPDATA"', ")"),
        ) or not contains_token_sequence(
            startup_root_body,
            ("base", ".", "join", "(", '"LocalComet"', ")"),
        ):
            errors.append("default startup root must remain LOCALAPPDATA plus LocalComet")
        required_override_sequences = (
            ("env", ":", ":", "var_os", "(", "APPLICATION_DATA_ROOT_OVERRIDE", ")"),
            ("if", "value", ".", "is_empty", "(", ")"),
            ("ApplicationDataRootError", ":", ":", "Empty"),
            ("if", "!", "root", ".", "is_absolute", "(", ")"),
            ("ApplicationDataRootError", ":", ":", "Relative"),
            ("if", "!", "is_local_filesystem_path", "(", "&", "root", ")"),
            ("ApplicationDataRootError", ":", ":", "NonLocal"),
        )
        if not all(contains_token_sequence(explicit_body, sequence) for sequence in required_override_sequences):
            errors.append("empty, relative, and nonlocal overrides must fail without fallback")

    lib_tokens = rust_tokens(lib_source)
    artifact_tokens = rust_tokens(artifact_trust_source)
    required_alignment = (
        (
            lib_tokens,
            ("app_data_root", ":", ":", "resolve_application_data_root", "(", "&", "local_data_dir", ")"),
        ),
        (
            lib_tokens,
            (
                "Err", "(", "error", ")", "=", ">", "{",
                "startup", ":", ":", "report_application_data_root_failure", "(", "error", ")", ";",
                "app", ".", "handle", "(", ")", ".", "exit", "(", "1", ")", ";",
                "return", "Ok", "(", "(", ")", ")", ";", "}",
            ),
        ),
        (
            lib_tokens,
            ("ArtifactTrustService", ":", ":", "production", "(", "&", "application_data_root", ")"),
        ),
        (
            lib_tokens,
            ("ArtifactAcquisitionManager", ":", ":", "new", "(", "Arc", ":", ":", "clone", "(", "&", "artifact_trust"),
        ),
        (
            lib_tokens,
            ("ManagedRuntimeSupervisor", ":", ":", "new", "(", "artifact_trust", ")"),
        ),
        (
            artifact_tokens,
            ("ManagedArtifactRoots", ":", ":", "from_application_data_root", "(", "application_data_root", ")"),
        ),
        (
            artifact_tokens,
            ("runtime_root", ":", "application_data_root", ".", "join", "(", '"runtimes"', ")"),
        ),
        (
            artifact_tokens,
            ("model_root", ":", "application_data_root", ".", "join", "(", '"models"', ")"),
        ),
        (
            artifact_tokens,
            ("resolve_contained", "(", "&", "self", ".", "roots", ".", "app_data_root", ",", '"acquisition"', ")"),
        ),
    )
    if not all(contains_token_sequence(tokens, sequence) for tokens, sequence in required_alignment):
        errors.append("model, runtime, acquisition, and startup roots must share application-data authority")
    return tuple(errors)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_manifest() -> dict[str, object]:
    return json.loads(read(MANIFEST))


def decode_from_stream(stream) -> dict[str, object]:
    prefix = stream.read(4)
    check(len(prefix) == 4, "runner stdout frame prefix missing")
    length = struct.unpack(">I", prefix)[0]
    check(0 < length <= 4_194_304, f"runner stdout frame length invalid: {length}")
    body = stream.read(length)
    check(len(body) == length, "runner stdout frame body truncated")
    from modules.desktop_ipc_contract_ru import decode_frame

    return decode_frame(prefix + body)


def run_runtime_transcript() -> None:
    from modules.desktop_ipc_contract_ru import FrameDecoder, IPCProtocolError, encode_frame, make_hello, make_request
    from modules.desktop_sidecar_runtime_ru import (
        ALLOWED_REQUEST_METHODS,
        DESKTOP_SIDECAR_RUNTIME_VERSION,
        MAX_SEEN_MESSAGE_IDS,
        DesktopSidecarRuntime,
    )

    now = [100.0]

    def monotonic() -> float:
        return now[0]

    runtime = DesktopSidecarRuntime(session_nonce="0" * 24, monotonic=monotonic)
    startup = runtime.startup_messages()
    check(len(startup) == 1, "runtime does not emit one startup hello")
    check(startup[0]["type"] == "hello", "startup message is not hello")
    check(startup[0]["payload"]["role"] == "python_core", "startup role is not python_core")
    check(startup[0]["payload"]["runtime_version"] == DESKTOP_SIDECAR_RUNTIME_VERSION, "runtime version missing in hello")
    check("lifecycle" in startup[0]["payload"]["capabilities"], "hello lifecycle capability missing")
    check("app.bootstrap" in startup[0]["payload"]["capabilities"], "hello control-plane capability missing")
    check("knowledge.review.list" in startup[0]["payload"]["capabilities"], "hello review list capability missing")
    check("knowledge.review.get" in startup[0]["payload"]["capabilities"], "hello review get capability missing")
    check(
        {
            "app.health",
            "app.shutdown",
            "app.bootstrap",
            "knowledge.review.list",
            "knowledge.review.get",
        }.issubset(ALLOWED_REQUEST_METHODS),
        "allowed methods missing lifecycle/control-plane entries",
    )

    desktop_hello = make_hello("desk-hello-1", session_nonce="1" * 24, capabilities=("lifecycle",))
    hello_reply = runtime.handle_message(desktop_hello)
    check(len(hello_reply) == 1 and hello_reply[0]["type"] == "hello", "desktop hello was not acknowledged")
    check(hello_reply[0]["payload"]["role"] == "python_core", "desktop hello reply role invalid")

    now[0] += 1.25
    health = runtime.handle_message(make_request("desk-health-1", "app.health", {}))
    check(len(health) == 1, "health should return one response")
    check(health[0]["type"] == "response", "health did not return response")
    check(health[0]["reply_to"] == "desk-health-1", "health reply_to mismatch")
    check(health[0]["payload"]["status"] == "ok", "health status not ok")
    check(health[0]["payload"]["uptime_ms"] >= 1250, "health uptime missing")
    check("protocol_version" in health[0]["payload"], "health protocol version missing")
    check("seen_message_ids" in health[0]["payload"], "health duplicate cache metric missing")
    check("knowledge.review.list" in health[0]["payload"]["capabilities"], "health review list capability missing")
    check("knowledge.review.get" in health[0]["payload"]["capabilities"], "health review get capability missing")

    empty_reviews = runtime.handle_message(
        make_request(
            "desk-review-empty",
            "knowledge.review.list",
            {"offset": 0, "limit": 50},
        )
    )
    check(len(empty_reviews) == 1, "empty review list returned multiple terminal messages")
    check(empty_reviews[0]["type"] == "response", "empty review list did not return response")
    check(empty_reviews[0]["payload"]["items"] == [], "default sidecar review queue not empty")
    check(empty_reviews[0]["payload"]["total_count"] == 0, "default sidecar review count wrong")
    check(empty_reviews[0]["payload"]["source"] == "LOCAL_CONTROL_PLANE", "default sidecar review source wrong")
    check(empty_reviews[0]["payload"]["fixture"] is False, "default sidecar review queue claimed fixture")

    import tools.test_v68451e9b_knowledge_review as e9b_fixtures

    helper = e9b_fixtures.KnowledgeReviewBehaviorTests()
    artifact = helper.clear_update_artifact()
    injected = DesktopSidecarRuntime(
        session_nonce="6" * 24,
        monotonic=monotonic,
        knowledge_reviews=[artifact],
    )
    injected.handle_message(
        make_hello(
            "desk-review-hello",
            session_nonce="7" * 24,
            capabilities=("lifecycle",),
        )
    )
    review_list = injected.handle_message(
        make_request(
            "desk-review-list",
            "knowledge.review.list",
            {"offset": 0, "limit": 1},
        )
    )
    check(len(review_list) == 1, "review list emitted event or duplicate terminal")
    check(review_list[0]["type"] == "response", "injected review list did not respond")
    check(review_list[0]["sequence"] == 0, "review list response sequence wrong")
    check(review_list[0]["payload"]["returned_count"] == 1, "injected review missing")
    check(
        review_list[0]["payload"]["items"][0]["review_artifact_identity"]
        == artifact.review_artifact_identity,
        "injected review identity changed",
    )
    review_get = injected.handle_message(
        make_request(
            "desk-review-get",
            "knowledge.review.get",
            {"review_artifact_identity": artifact.review_artifact_identity},
        )
    )
    check(len(review_get) == 1, "review get emitted event or duplicate terminal")
    check(review_get[0]["type"] == "response", "review get did not respond")
    check(review_get[0]["sequence"] == 0, "review get response sequence wrong")
    check(
        review_get[0]["payload"]["projection"]["review_artifact_identity"]
        == artifact.review_artifact_identity,
        "review get identity changed",
    )
    invalid_list = injected.handle_message(
        make_request(
            "desk-review-list-extra",
            "knowledge.review.list",
            {"offset": 0, "limit": 1, "extra": True},
        )
    )
    check(len(invalid_list) == 1, "invalid review list returned multiple errors")
    check(invalid_list[0]["type"] == "error", "invalid review list was accepted")
    check(invalid_list[0]["payload"]["code"] == "invalid_payload", "invalid review list error wrong")
    invalid_get = injected.handle_message(
        make_request(
            "desk-review-get-invalid",
            "knowledge.review.get",
            {"review_artifact_identity": "kreview:bad"},
        )
    )
    check(len(invalid_get) == 1, "invalid review get returned multiple errors")
    check(invalid_get[0]["payload"]["code"] == "invalid_payload", "invalid review get error wrong")
    missing_get = injected.handle_message(
        make_request(
            "desk-review-get-missing",
            "knowledge.review.get",
            {"review_artifact_identity": "kreview:" + "f" * 64},
        )
    )
    check(len(missing_get) == 1, "missing review get returned multiple errors")
    check(missing_get[0]["payload"]["code"] == "request_not_found", "missing review get error wrong")
    check("Traceback" not in json.dumps(missing_get[0]), "review error leaked traceback")

    blocked_methods = [
        "chat.send",
        "model.invoke",
        "planner.plan",
        "actions.execute",
        "files.read",
        "network.connect",
        "localhost.open",
        "frontend.dispatch",
    ]
    for index, method in enumerate(blocked_methods):
        replies = runtime.handle_message(make_request(f"desk-block-{index}", method, {}))
        check(len(replies) == 1, f"{method} did not return one error")
        check(replies[0]["type"] == "error", f"{method} was not rejected")
        check(replies[0]["payload"]["code"] == "unsupported_method", f"{method} wrong error code")
        check(replies[0]["reply_to"] == f"desk-block-{index}", f"{method} reply_to mismatch")

    first = runtime.handle_message(make_request("desk-dup-1", "app.health", {}))
    duplicate = runtime.handle_message(make_request("desk-dup-1", "app.health", {}))
    check(first[0]["payload"]["status"] == "ok", "first duplicate probe should succeed")
    check(duplicate[0]["payload"]["code"] == "duplicate_message_id", "duplicate id was not rejected")

    bounded = DesktopSidecarRuntime(session_nonce="2" * 24, monotonic=monotonic)
    bounded.handle_message(make_hello("desk-bounded-hello", session_nonce="4" * 24, capabilities=("lifecycle",)))
    for index in range(MAX_SEEN_MESSAGE_IDS + 44):
        bounded.handle_message(make_request(f"id-{index:03d}", "app.health", {}))
    check(bounded.seen_id_count == MAX_SEEN_MESSAGE_IDS, "duplicate cache exceeded bound")
    evicted = bounded.handle_message(make_request("id-000", "app.health", {}))
    check(evicted[0]["payload"]["status"] == "ok", "old duplicate id was not evicted")

    shutdown = runtime.handle_message(make_request("desk-shutdown-1", "app.shutdown", {}))
    check(len(shutdown) == 2, "shutdown should return response and goodbye")
    check(shutdown[0]["type"] == "response", "shutdown first message is not response")
    check(shutdown[0]["payload"]["status"] == "shutting_down", "shutdown status wrong")
    check(shutdown[1]["type"] == "goodbye", "shutdown did not emit goodbye")
    check(runtime.shutdown_requested, "runtime shutdown flag not set")

    unsupported_event = DesktopSidecarRuntime(session_nonce="3" * 24)
    event = {
        "protocol": "localcomet.ipc",
        "version": "1.0",
        "type": "event",
        "id": "desk-event-1",
        "method": "app.health",
        "run_id": None,
        "sequence": 0,
        "reply_to": None,
        "payload": {},
    }
    event_error = unsupported_event.handle_message(event)
    check(event_error[0]["payload"]["code"] == "unsupported_type", "non-request lifecycle message was not rejected")

    decoder = FrameDecoder()
    bad_version_body = b'{"id":"bad-version","method":"app.health","payload":{},"protocol":"localcomet.ipc","reply_to":null,"run_id":null,"sequence":0,"type":"request","version":"9.9"}'
    try:
        decoder.feed(struct.pack(">I", len(bad_version_body)) + bad_version_body)
    except IPCProtocolError as exc:
        error = runtime.protocol_error_messages(exc)[0]
        check(error["payload"]["code"] == "invalid_envelope", "bad version did not become invalid_envelope")
        check("unsupported_version" in error["payload"]["message"], "bad version message not preserved")
    else:
        raise AssertionError("bad version frame was accepted")

    too_large = FrameDecoder()
    try:
        too_large.feed(struct.pack(">I", 4_194_305))
    except IPCProtocolError as exc:
        error = runtime.protocol_error_messages(exc)[0]
        check(error["payload"]["code"] == "frame_too_large", "oversized frame did not become frame_too_large")
    else:
        raise AssertionError("oversized frame was accepted")

    encoded = runtime.encode_messages([make_request("desk-roundtrip-1", "app.health", {})])
    roundtrip = FrameDecoder().feed(encoded)
    check(roundtrip[0]["method"] == "app.health", "runtime encode roundtrip failed")


def run_runner_transcript() -> None:
    from modules.desktop_ipc_contract_ru import encode_frame, make_hello, make_request

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
        check(hello["type"] == "hello", "runner did not emit hello first")
        check(hello["payload"]["role"] == "python_core", "runner hello role invalid")
        check("lifecycle" in hello["payload"]["capabilities"], "runner lifecycle capability missing")
        check("app.bootstrap" in hello["payload"]["capabilities"], "runner control-plane capability missing")
        check("knowledge.review.list" in hello["payload"]["capabilities"], "runner review list capability missing")
        check("knowledge.review.get" in hello["payload"]["capabilities"], "runner review get capability missing")

        process.stdin.write(encode_frame(make_hello("desk-runner-hello", session_nonce="5" * 24, capabilities=("lifecycle",))))
        process.stdin.flush()
        hello_reply = decode_from_stream(process.stdout)
        check(hello_reply["type"] == "hello", "runner desktop hello reply missing")

        process.stdin.write(encode_frame(make_request("desk-health-runner", "app.health", {})))
        process.stdin.flush()
        health = decode_from_stream(process.stdout)
        check(health["type"] == "response", "runner health did not return response")
        check(health["reply_to"] == "desk-health-runner", "runner health reply_to mismatch")
        check(health["payload"]["status"] == "ok", "runner health status wrong")

        process.stdin.write(
            encode_frame(
                make_request(
                    "desk-review-runner",
                    "knowledge.review.list",
                    {"offset": 0, "limit": 50},
                )
            )
        )
        process.stdin.flush()
        reviews = decode_from_stream(process.stdout)
        check(reviews["type"] == "response", "runner review list did not return response")
        check(reviews["reply_to"] == "desk-review-runner", "runner review list reply_to mismatch")
        check(reviews["payload"]["items"] == [], "runner default review queue not empty")
        check(reviews["payload"]["total_count"] == 0, "runner default review count wrong")

        process.stdin.write(encode_frame(make_request("desk-chat-runner", "chat.send", {})))
        process.stdin.flush()
        rejected = decode_from_stream(process.stdout)
        check(rejected["type"] == "error", "runner unsupported method did not return error")
        check(rejected["payload"]["code"] == "unsupported_method", "runner unsupported method code wrong")

        process.stdin.write(encode_frame(make_request("desk-stop-runner", "app.shutdown", {})))
        process.stdin.flush()
        shutdown = decode_from_stream(process.stdout)
        goodbye = decode_from_stream(process.stdout)
        check(shutdown["type"] == "response", "runner shutdown response missing")
        check(shutdown["payload"]["status"] == "shutting_down", "runner shutdown status wrong")
        check(goodbye["type"] == "goodbye", "runner goodbye missing")
    finally:
        if process.stdin:
            process.stdin.close()
    exit_code = process.wait(timeout=10)
    stderr = process.stderr.read().decode("utf-8", "replace")
    check(exit_code == 0, f"runner exit code wrong: {exit_code}")
    check(stderr == "", f"runner wrote stderr: {stderr!r}")


def run_source_scans() -> None:
    runtime_text = read(RUNTIME)
    runner_text = read(RUNNER)
    app_data_root_text = read(TAURI_SRC / "app_data_root.rs")
    artifact_trust_text = read(TAURI_SRC / "artifact_trust.rs")
    lib_text = read(TAURI_SRC / "lib.rs")
    ipc_text = read(TAURI_SRC / "ipc.rs")
    single_instance_text = read(TAURI_SRC / "single_instance.rs")
    startup_text = read(TAURI_SRC / "startup.rs")
    supervisor_text = read(TAURI_SRC / "supervisor.rs")
    windows_job_text = read(TAURI_SRC / "windows_job.rs")
    tauri_config_text = read(DESKTOP / "src-tauri" / "tauri.conf.json")
    nsis_hook_text = read(DESKTOP / "src-tauri" / "nsis" / "installer-hooks.nsh")
    rust_text = "\n".join(
        [lib_text, ipc_text, single_instance_text, startup_text, supervisor_text, windows_job_text]
    )

    for path in [
        RUNTIME,
        RUNNER,
        TAURI_SRC / "ipc.rs",
        TAURI_SRC / "single_instance.rs",
        TAURI_SRC / "startup.rs",
        TAURI_SRC / "supervisor.rs",
        TAURI_SRC / "windows_job.rs",
    ]:
        check(path.exists(), f"missing {path}")
    check("DESKTOP_SIDECAR_RUNTIME_VERSION = \"v6.84.3\"" in runtime_text, "runtime version constant missing")
    check("ALLOWED_REQUEST_METHODS" in runtime_text and "app.health" in runtime_text and "app.shutdown" in runtime_text, "runtime lifecycle allowlist missing")
    check("knowledge_reviews" in runtime_text, "runtime review dependency pass-through missing")
    check("chat." not in runtime_text and "planner." not in runtime_text, "runtime contains forbidden non-lifecycle method literal")
    check("model.catalog.get" in runtime_text and "model.turn.cancel" in runtime_text, "v6.84.5 fixed model gateway methods missing")
    check("subprocess" not in runtime_text and "socket" not in runtime_text, "runtime imports process or socket module")
    check("sys.path.insert" in runner_text, "runner does not prepare import path under isolated Python")
    check("is_symlink()" in runner_text, "runner does not reject symlink runner")
    check("FrameDecoder" in runner_text, "runner does not use contract frame decoder")
    check("stdout.buffer.write" in runner_text and "stderr.write(\"localcomet sidecar fatal" in runner_text, "runner stdout/stderr handling changed")

    check(
        all(
            marker in lib_text
            for marker in [
                "mod ipc;",
                "mod single_instance;",
                "mod startup;",
                "mod supervisor;",
                "mod windows_job;",
            ]
        ),
        "lib.rs launch modules not wired",
    )
    check(
        ".setup(|app|" in lib_text
        and "supervisor.start_and_wait_ready(BACKEND_READINESS_TIMEOUT)" in lib_text,
        "Tauri setup does not wait for bounded supervisor readiness",
    )
    check('"visible": false' in tauri_config_text and 'window.show()' in lib_text, "window is not gated on readiness")
    check(
        'StrCpy $INSTDIR "$LOCALAPPDATA\\Programs\\${PRODUCTNAME}"' in nsis_hook_text,
        "installer payload path is not separated from user data",
    )
    check(
        "SetOutPath $INSTDIR" in nsis_hook_text
        and nsis_hook_text.index("StrCpy $INSTDIR") < nsis_hook_text.index("SetOutPath $INSTDIR"),
        "installer output path is not reset after changing INSTDIR",
    )
    check("CloseRequested" in lib_text and "supervisor.shutdown()" in lib_text, "Tauri close does not stop supervisor")
    check("invoke_handler" in rust_text and "control_plane_bootstrap" in rust_text, "static control-plane invoke handler missing")
    check("control_plane_request" not in rust_text and "generic_request" not in rust_text, "generic invoke command present")
    check("std::process" not in rust_text and "Command::" not in rust_text, "arbitrary Rust process API present")
    check("TcpListener" not in rust_text and "UdpSocket" not in rust_text, "Rust network socket present")
    check("cmd.exe" not in rust_text.lower() and "powershell.exe" not in rust_text.lower(), "Rust source contains shell executable")
    check("@tauri-apps/plugin-shell" not in rust_text and "plugin-fs" not in rust_text and "plugin-http" not in rust_text, "forbidden Tauri plugin reference present")

    check("CreateProcessW" in windows_job_text, "Windows launcher does not use CreateProcessW")
    check("CREATE_SUSPENDED" in windows_job_text, "Windows launcher does not create suspended process")
    check("CREATE_NO_WINDOW" in windows_job_text, "Windows launcher does not suppress console window")
    check("EXTENDED_STARTUPINFO_PRESENT" in windows_job_text, "Windows launcher does not use extended startup info")
    check("CreateJobObjectW" in windows_job_text, "Windows launcher does not create job object")
    check("JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in windows_job_text, "job object kill-on-close missing")
    check("JOB_OBJECT_LIMIT_ACTIVE_PROCESS" in windows_job_text, "job object active-process limit missing")
    check("ActiveProcessLimit = 1" in windows_job_text, "job object active-process limit not exactly one")
    check("SetInformationJobObject" in windows_job_text, "job object limit not configured")
    check("AssignProcessToJobObject" in windows_job_text, "process not assigned to job")
    check("ResumeThread" in windows_job_text, "suspended child not resumed after containment")
    check("TerminateProcess" in windows_job_text, "contained process termination missing")
    check("CreatePipe" in windows_job_text, "stdio pipes missing")
    check("SetHandleInformation" in windows_job_text and "HANDLE_FLAG_INHERIT" in windows_job_text, "parent pipe inheritance not disabled")
    check("PROC_THREAD_ATTRIBUTE_HANDLE_LIST" in windows_job_text, "explicit handle inheritance list missing")
    check("InitializeProcThreadAttributeList" in windows_job_text, "handle list initialization missing")
    check("UpdateProcThreadAttribute" in windows_job_text, "handle list update missing")
    check("CreateProcessW" not in lib_text + ipc_text + supervisor_text, "CreateProcessW leaked outside windows_job.rs")

    check("CreateMutexW" in single_instance_text, "single-instance mutex is missing")
    check("ERROR_ALREADY_EXISTS" in single_instance_text, "duplicate-instance detection is missing")
    check("MessageBoxW" in startup_text, "native startup failure dialog is missing")
    startup_log_errors = startup_log_contract_errors(
        startup_text,
        app_data_root_text,
        lib_text,
        artifact_trust_text,
    )
    check(not startup_log_errors, "; ".join(startup_log_errors))
    check("C:\\Users\\" not in startup_text, "startup handling contains a machine-specific path")

    check('PYTHON_ISOLATED_ARG: &str = "-I"' in supervisor_text, "isolated Python arg not fixed")
    check('PYTHON_NO_BYTECODE_ARG: &str = "-B"' in supervisor_text, "no-bytecode Python arg not fixed")
    check("tools/run_localcomet_desktop_sidecar.py" in supervisor_text, "runner path constant missing")
    check("localcomet-core.exe" in supervisor_text, "release sidecar executable name missing")
    check("LOCALCOMET_TEST_PROJECT_ROOT" in supervisor_text and "LOCALCOMET_TEST_PYTHON" in supervisor_text, "test-only debug overrides missing")
    check("SystemRoot" in supervisor_text and "PYTHONNOUSERSITE" in supervisor_text, "minimal environment missing")
    check("OPENAI_API_KEY" not in supervisor_text and "std::env::vars" not in supervisor_text, "broad environment forwarding present")
    check("HEALTH_METHOD" in supervisor_text and "SHUTDOWN_METHOD" in supervisor_text, "lifecycle method constants missing")
    check("send_health_probe" in supervisor_text, "health probe method missing")
    check("ReadinessTimeout" in supervisor_text, "bounded readiness timeout missing")
    check("saw_health_ok" in supervisor_text, "health response gate missing")
    check("wait_bounded" in supervisor_text and "wait_bounded" in windows_job_text, "bounded process wait missing")
    check("INFINITE" not in windows_job_text, "unbounded Windows process wait remains")
    check("snapshot" in supervisor_text, "supervisor snapshot missing")


def run_startup_log_scan_regressions() -> None:
    startup_text = read(TAURI_SRC / "startup.rs")
    app_data_root_text = read(TAURI_SRC / "app_data_root.rs")
    lib_text = read(TAURI_SRC / "lib.rs")
    artifact_trust_text = read(TAURI_SRC / "artifact_trust.rs")
    check(
        not startup_log_contract_errors(startup_text, app_data_root_text, lib_text, artifact_trust_text),
        "current shared-root startup implementation must pass",
    )
    startup_literals = set(rust_tokens(startup_text))
    obsolete_literals = {
        '"%LOCALAPPDATA%\\\\LocalComet\\\\logs\\\\startup.log"',
        'r"%LOCALAPPDATA%\\LocalComet\\logs\\startup.log"',
    }
    check(
        startup_literals.isdisjoint(obsolete_literals),
        "obsolete hard-coded startup path must not be required as implementation text",
    )

    hard_coded_startup = r'''
fn startup_log_path() -> Option<PathBuf> {
    Some(PathBuf::from(r"%LOCALAPPDATA%\LocalComet\logs\startup.log"))
}
'''
    check(
        bool(startup_log_contract_errors(hard_coded_startup, app_data_root_text, lib_text, artifact_trust_text)),
        "hard-coded normal-profile startup log must be rejected",
    )
    independent_localappdata = r'''
fn startup_log_path() -> Option<PathBuf> {
    env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|root| root.join("LocalComet").join("logs").join("startup.log"))
}
'''
    check(
        bool(
            startup_log_contract_errors(
                independent_localappdata,
                app_data_root_text,
                lib_text,
                artifact_trust_text,
            )
        ),
        "independent LOCALAPPDATA startup resolver must be rejected",
    )
    comment_only = r'''
fn startup_log_path() -> Option<PathBuf> {
    // app_data_root::resolve_startup_application_data_root()
    /* root.join("logs").join("startup.log") */
    None
}
'''
    check(
        bool(startup_log_contract_errors(comment_only, app_data_root_text, lib_text, artifact_trust_text)),
        "comment-only shared-root markers must be rejected",
    )
    check(
        bool(startup_log_contract_errors(startup_text, app_data_root_text, "", artifact_trust_text)),
        "root alignment evidence must remain mandatory",
    )
    broken_failure_path = lib_text.replace(
        "startup::report_application_data_root_failure(error);",
        "let _ = error;",
        1,
    )
    check(
        bool(
            startup_log_contract_errors(
                startup_text,
                app_data_root_text,
                broken_failure_path,
                artifact_trust_text,
            )
        ),
        "invalid overrides must fail explicitly without normal-profile fallback",
    )

    broken_default_root = app_data_root_text.replace(
        'env::var_os("LOCALAPPDATA")',
        'env::var_os("LOCALCOMET_UNRELATED_ROOT")',
        1,
    )
    check(
        bool(startup_log_contract_errors(startup_text, broken_default_root, lib_text, artifact_trust_text)),
        "default Windows LOCALAPPDATA behavior must remain required",
    )
    broken_override_validation = app_data_root_text.replace(
        "if value.is_empty() {",
        "if false {",
        1,
    ).replace(
        "if !root.is_absolute() {",
        "if false {",
        1,
    )
    check(
        bool(
            startup_log_contract_errors(
                startup_text,
                broken_override_validation,
                lib_text,
                artifact_trust_text,
            )
        ),
        "empty and relative overrides must remain rejected",
    )


def run_manifest_checks() -> None:
    manifest = load_manifest()
    check("modules/desktop_sidecar_runtime_ru.py" in manifest.get("lazy_runtime", []), "manifest missing sidecar runtime")
    check("tools/run_localcomet_desktop_sidecar.py" in manifest.get("tools", []), "manifest missing sidecar runner")
    check("tools/test_v6843_sidecar_supervisor.py" in manifest.get("tests", []), "manifest missing v6.84.3 test")
    all_paths: list[str] = []
    for category in ["entrypoints", "runtime", "lazy_runtime", "tests", "tools"]:
        values = manifest.get(category, [])
        check(values == sorted(values, key=str.lower), f"manifest category not sorted: {category}")
        check(len(values) == len(set(values)), f"manifest category duplicate: {category}")
        check(all(not value.startswith("desktop/localcomet-desktop/") for value in values), f"desktop Rust asset listed in Python manifest: {category}")
        all_paths.extend(values)
    check(len(all_paths) == len(set(all_paths)), "manifest contains cross-category duplicate")


def run_repo_guard_checks() -> None:
    for path_text, expected in FORBIDDEN_HASHES.items():
        check(sha256(ROOT / path_text) == expected, f"forbidden v6.84.1 file changed: {path_text}")
    check(not (DESKTOP / "node_modules").exists(), "source repo node_modules exists")
    check(not (DESKTOP / "src-tauri" / "target").exists(), "source repo Cargo target exists")
    check(not (ROOT / "Projects" / "BrowserProfile").exists() or (ROOT / "Projects" / "BrowserProfile").is_dir(), "BrowserProfile guard path invalid")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True, capture_output=True, check=True)
    check(staged.stdout.strip() == "", "staged files are not empty")


def main() -> None:
    start = time.monotonic()
    if sys.argv[1:]:
        if sys.argv[1:] != ["--startup-log-scan-only"]:
            raise SystemExit("usage: test_v6843_sidecar_supervisor.py [--startup-log-scan-only]")
        run_startup_log_scan_regressions()
        elapsed = time.monotonic() - start
        print(f"ALL STARTUP LOG PACKAGING-SCAN TESTS PASSED ({CHECK_COUNT} checks, {elapsed:.2f}s)")
        return
    run_runtime_transcript()
    run_runner_transcript()
    run_source_scans()
    run_startup_log_scan_regressions()
    run_manifest_checks()
    run_repo_guard_checks()
    elapsed = time.monotonic() - start
    check(CHECK_COUNT >= 82, f"focused assertion count too low: {CHECK_COUNT}")
    print(f"ALL v6.84.3 SIDECAR SUPERVISOR TESTS PASSED ({CHECK_COUNT} checks, {elapsed:.2f}s)")


if __name__ == "__main__":
    main()
