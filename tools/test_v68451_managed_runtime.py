#!/usr/bin/env python
from __future__ import annotations

import http.client
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tools" / "test_fixtures" / "fake_managed_llama_server.py"
RUST_MANAGED = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "managed_runtime.rs"
RUST_JOB = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "windows_job.rs"


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


def run_source_guards() -> None:
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    managed_text = RUST_MANAGED.read_text(encoding="utf-8")
    job_text = RUST_JOB.read_text(encoding="utf-8")
    check("subprocess" not in fixture_text, "fixture imports subprocess")
    check("urllib" not in fixture_text and "requests" not in fixture_text, "fixture has outbound network client")
    check('EXECUTABLE_NAME: &str = "llama-server.exe"' in managed_text, "production executable rule missing")
    check("const APPROVED_RUNTIME_REGISTRY: &[ApprovedRuntime] = &[];" in managed_text, "production registry is not empty")
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
    run_source_guards()
    print("ALL v6.84.5.1 MANAGED RUNTIME TESTS PASSED")


if __name__ == "__main__":
    main()
