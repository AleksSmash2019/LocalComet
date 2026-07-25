"""LocalComet test harness for smoke testing.

Wraps the REAL DesktopSidecarRuntime (modules/desktop_sidecar_runtime_ru.py)
and drives it in-process over the same IPC message contract the desktop bridge
uses. This does NOT duplicate product logic and does NOT open a private IPC
channel: it calls the same handle_message() entry point the runner uses.

Scope note: the desktop sidecar is a model-gateway / knowledge / session
manager. It performs NO filesystem tool execution (files.* methods are
unsupported_method). Approval and workspace confinement are enforced in the
Rust control plane (src-tauri/src/approval.rs, workspace.rs) and are covered by
cargo tests, not by this Python smoke.
"""

from __future__ import annotations

import time
from typing import Any

from modules.desktop_ipc_contract_ru import make_hello, make_request
from modules.desktop_sidecar_runtime_ru import make_runtime


class ApprovalRequired(Exception):
    pass


class InputDigestMismatch(Exception):
    pass


class TokenNotFound(Exception):
    pass


class WorkspaceViolation(Exception):
    pass


class LocalCometHarness:
    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = project_root
        self.runtime = make_runtime()
        self._counter = 0
        self._hello_seen = False
        self._capabilities: list[str] = []
        self._runtime_version = "unknown"

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"smoke-{prefix}-{self._counter:06d}"

    def start_sidecar(self, workspace: str | None = None) -> tuple[int, str]:
        hello = make_hello(self._next_id("hello"), session_nonce="smoke-nonce-000000000000")
        replies = self.runtime.handle_message(hello)
        for reply in replies:
            if reply.get("type") == "hello":
                payload = reply["payload"]
                self._hello_seen = True
                self._capabilities = list(payload.get("capabilities", []))
                self._runtime_version = payload.get("runtime_version", "unknown")
                return (0, self._runtime_version)
        raise RuntimeError("sidecar did not answer the desktop hello")

    def readiness_probe(self, timeout_ms: int = 5000) -> tuple[str, int]:
        started = time.monotonic()
        replies = self.runtime.handle_message(
            make_request(self._next_id("health"), "app.health", {})
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        for reply in replies:
            if reply.get("type") == "response" and reply.get("payload", {}).get("status") == "ok":
                return ("ok", elapsed_ms)
        return ("error", elapsed_ms)

    def runtime_health(self) -> dict[str, Any]:
        replies = self.runtime.handle_message(
            make_request(self._next_id("health"), "app.health", {})
        )
        for reply in replies:
            if reply.get("type") == "response":
                return reply["payload"]
        raise RuntimeError("no health response")

    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request and return the first response/error envelope."""
        replies = self.runtime.handle_message(
            make_request(self._next_id("req"), method, payload)
        )
        for reply in replies:
            if reply.get("type") in ("response", "error"):
                return reply
        raise RuntimeError(f"no terminal reply for {method}")

    def sidecar_pid(self) -> int:
        return 0  # in-process harness; no OS process

    def shutdown(self) -> None:
        try:
            self.runtime.handle_message(
                make_request(self._next_id("shutdown"), "app.shutdown", {})
            )
        finally:
            self.runtime.close()
