#!/usr/bin/env python
from __future__ import annotations

import http.client
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tools" / "test_fixtures" / "fake_managed_llama_server.py"
RUST_MANAGED = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "managed_runtime.rs"
RUST_TRUST = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "artifact_trust.rs"
RUST_LIB = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "lib.rs"
RUST_JOB = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "windows_job.rs"
PERMISSIONS = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "permissions"
CAPABILITY = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "capabilities" / "main.json"

TRUST_COMMAND_PERMISSIONS = {
    "managed_runtime_catalog": "allow-managed-runtime-catalog",
    "managed_model_catalog": "allow-managed-model-catalog",
    "managed_installed_artifacts": "allow-managed-installed-artifacts",
    "managed_artifact_validation_status": "allow-managed-artifact-validation-status",
    "managed_model_readiness": "allow-managed-model-readiness",
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def request(port: int, method: str, path: str, token: str, body: bytes | None = None) -> tuple[int, bytes, dict[str, str]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read(64 * 1024)
    response_headers = {key.lower(): value for key, value in response.getheaders()}
    connection.close()
    return int(response.status), data, response_headers


def run_fixture_protocol() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_managed_fixture_") as temp_text:
        temp = Path(temp_text)
        model = temp / "model.gguf"
        key_file = temp / "key.txt"
        model.write_bytes(b"GGUF" + b"\0" * 1024)
        token = "a" * 64
        key_file.write_text(token + "\n", encoding="utf-8")
        port = free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(FIXTURE),
                "--model",
                str(model),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--api-key-file",
                str(key_file),
                "--no-webui",
                "--no-agent",
                "--ctx-size",
                "4096",
                "--n-predict",
                "32",
                "--alias",
                "localcomet-test-model",
            ],
            cwd=temp,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    status, body, _ = request(port, "GET", "/health", token)
                    if status == 200 and json.loads(body)["status"] == "ok":
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError("fixture did not become ready")
            bad_status, _, _ = request(port, "GET", "/health", "b" * 64)
            check(bad_status == 401, "fixture accepted invalid authorization")
            status, body, _ = request(port, "GET", "/v1/models", token)
            check(status == 200 and b"localcomet-test-model" in body, "fixture model list failed")
            payload = json.dumps({"model": "localcomet-test-model", "messages": [{"role": "user", "content": "hi"}], "stream": True}).encode("utf-8")
            status, body, headers = request(port, "POST", "/v1/chat/completions", token, payload)
            check(status == 200, "fixture SSE status wrong")
            check("text/event-stream" in headers.get("content-type", ""), "fixture SSE content type wrong")
            check(b"data: [DONE]" in body and len(body) < 64 * 1024, "fixture SSE body invalid")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        check(not key_file.exists() or key_file.read_text(encoding="utf-8").strip() == token, "fixture mutated credential")


def rust_function_block(source: str, function_name: str) -> str:
    markers = (f"pub fn {function_name}(", f"pub async fn {function_name}(")
    starts = [source.find(marker) for marker in markers]
    start = min((value for value in starts if value >= 0), default=-1)
    check(start >= 0, f"Rust command definition missing: {function_name}")
    opening = source.find("{", start)
    check(opening >= 0, f"Rust command body missing: {function_name}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Rust command body is unterminated: {function_name}")


def load_permission_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(PERMISSIONS.glob("*.toml")):
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        permissions = document.get("permission", [])
        check(isinstance(permissions, list), f"permission array missing in {path.name}")
        entries.extend(permissions)
    return entries


def run_trust_command_guards() -> None:
    trust_text = RUST_TRUST.read_text(encoding="utf-8")
    lib_text = RUST_LIB.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    entries = load_permission_entries()

    handler_marker = ".invoke_handler(tauri::generate_handler!["
    handler_start = lib_text.find(handler_marker)
    check(handler_start >= 0, "Tauri invoke handler missing")
    handler_end = lib_text.find("])\n", handler_start)
    check(handler_end >= 0, "Tauri invoke handler is unterminated")
    handler = lib_text[handler_start:handler_end]

    expected_calls = {
        "managed_runtime_catalog": "state.runtime_catalog()",
        "managed_model_catalog": "state.model_catalog()",
        "managed_installed_artifacts": "state.installed_artifacts()",
        "managed_artifact_validation_status": ".artifact_validation_status(&artifact_id)",
        "managed_model_readiness": "state.model_readiness(&model_id)",
    }
    for command in TRUST_COMMAND_PERMISSIONS:
        definition = re.compile(rf"#\[tauri::command\]\s*pub fn {re.escape(command)}\s*\(")
        check(len(definition.findall(trust_text)) == 1, f"typed Tauri command is not defined exactly once: {command}")
        check(len(re.findall(rf"\b{re.escape(command)}\b", handler)) == 1, f"invoke handler exposure is not exact: {command}")
        block = rust_function_block(trust_text, command)
        signature = block[: block.find("{")]
        check("State<'_, Arc<ArtifactTrustService>>" in signature, f"trust service state missing: {command}")
        check(expected_calls[command] in block, f"read-only trust service projection missing: {command}")
        for forbidden in ("Path", "PathBuf", "serde_json::Value", "catalog_json", "raw_command", "arguments"):
            check(forbidden not in signature, f"unsafe command input {forbidden!r}: {command}")

    check("artifact_id: String" in rust_function_block(trust_text, "managed_artifact_validation_status"), "artifact status is not keyed by stable ID")
    check("model_id: String" in rust_function_block(trust_text, "managed_model_readiness"), "model readiness is not keyed by stable ID")
    for command in ("managed_runtime_catalog", "managed_model_catalog", "managed_installed_artifacts"):
        signature = rust_function_block(trust_text, command).split("{", 1)[0]
        check("String" not in signature, f"list command accepts frontend-controlled text: {command}")

    identifiers = [entry.get("identifier") for entry in entries]
    check(len(identifiers) == len(set(identifiers)), "duplicate Tauri permission identifier")
    for command, permission_id in TRUST_COMMAND_PERMISSIONS.items():
        matches = [entry for entry in entries if entry.get("identifier") == permission_id]
        check(len(matches) == 1, f"permission is not defined exactly once: {permission_id}")
        permission = matches[0]
        commands = permission.get("commands")
        check(isinstance(commands, dict), f"permission commands missing: {permission_id}")
        check(commands.get("allow") == [command], f"permission is not narrowly bound: {permission_id}")
        check("deny" not in commands, f"unexpected deny rule in narrow permission: {permission_id}")
        description = str(permission.get("description", "")).lower()
        check("reading" in description and "write" not in description and "mutat" not in description, f"permission is not documented read-only: {permission_id}")
        command_matches = [
            entry
            for entry in entries
            if command in entry.get("commands", {}).get("allow", [])
        ]
        check(len(command_matches) == 1, f"command is allowed by more than one permission: {command}")

    capability_permissions = capability.get("permissions")
    check(isinstance(capability_permissions, list), "main capability permissions missing")
    check(len(capability_permissions) == len(set(capability_permissions)), "duplicate main capability permission")
    for permission_id in TRUST_COMMAND_PERMISSIONS.values():
        check(capability_permissions.count(permission_id) == 1, f"main capability exposure is not exact: {permission_id}")
    check(capability.get("windows") == ["main"], "artifact trust commands escaped the main-window capability")

    allowed_commands = [
        command
        for entry in entries
        for command in entry.get("commands", {}).get("allow", [])
        if isinstance(command, str)
    ]
    for forbidden in (
        "managed_artifact_approve",
        "managed_artifact_write",
        "managed_catalog_load",
        "managed_catalog_replace",
        "managed_registry_write",
    ):
        check(forbidden not in allowed_commands, f"approval mutation permission exposed: {forbidden}")


def run_source_guards() -> None:
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    managed_text = RUST_MANAGED.read_text(encoding="utf-8")
    trust_text = RUST_TRUST.read_text(encoding="utf-8")
    job_text = RUST_JOB.read_text(encoding="utf-8")
    check("subprocess" not in fixture_text, "fixture imports subprocess")
    check("urllib" not in fixture_text and "requests" not in fixture_text, "fixture has outbound network client")
    check('include_bytes!("../resources/localcomet/approved-artifacts.v1.json")' in trust_text, "approved catalog is not source-embedded")
    check("resolve_launch(model_id)" in managed_text, "managed launch does not resolve a stable model ID")
    check("model_path: String" not in rust_function_block(managed_text, "managed_runtime_start"), "managed runtime start accepts a raw model path")
    check("ManagedRuntimeLaunchSpec" in job_text, "managed launch spec missing")
    check("CREATE_SUSPENDED" in job_text and "AssignProcessToJobObject" in job_text and "ResumeThread" in job_text, "suspended containment sequence missing")
    check("JOB_OBJECT_LIMIT_ACTIVE_PROCESS" in job_text, "active process job limit missing")
    check("ActiveProcessLimit = 1" in job_text, "active process limit is not exactly 1")
    check("fake_managed_llama_server.py" not in managed_text, "fixture referenced by production Rust source")
    forbidden_created = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.is_dir():
            continue
        if path.suffix.lower() in {".exe", ".bat", ".ps1"}:
            forbidden_created.append(path.relative_to(ROOT).as_posix())
    check("tools/test_fixtures/fake_managed_llama_server.py" not in forbidden_created, "fixture has forbidden suffix")
    print("FORBIDDEN_SUFFIX_MATCHES " + json.dumps(sorted(forbidden_created), ensure_ascii=False))


def main() -> None:
    check(FIXTURE.is_file(), "fixture missing")
    check(subprocess.run([sys.executable, str(FIXTURE), "--version"], text=True, capture_output=True).returncode == 0, "fixture --version failed")
    help_result = subprocess.run([sys.executable, str(FIXTURE), "--help"], text=True, capture_output=True)
    check(help_result.returncode == 0 and "--api-key-file" in help_result.stdout and "--no-agent" in help_result.stdout, "fixture --help incomplete")
    bad_result = subprocess.run([sys.executable, str(FIXTURE), "--bad"], text=True, capture_output=True)
    check(bad_result.returncode != 0, "fixture accepted unknown flag")
    run_fixture_protocol()
    run_trust_command_guards()
    run_source_guards()
    print("ALL v6.84.5.1 MANAGED RUNTIME TESTS PASSED")


if __name__ == "__main__":
    main()
