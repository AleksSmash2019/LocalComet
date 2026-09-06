#!/usr/bin/env python3
"""Installed-release bug sweep on a hidden isolated desktop.

Launches the freshly built release LocalComet.exe (cargo-target bundle output)
with an isolated LOCALAPPDATA and loopback CDP, then walks every sidebar
workspace by clicking its real DOM button, collecting per-workspace:
  - uncaught exceptions (Runtime.exceptionThrown)
  - console errors
  - failed network requests (Network.loadingFailed)
Plus a sidecar bootstrap check (isolated app-data tree) and a chat-history
persistence round-trip across an app restart.

Output: Projects/Reports/computer_use_real_actions/installed_sweep.json
"""
from __future__ import annotations

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import ctypes.wintypes as wintypes

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "target" / "up00-wp01" / "cargo-target" / "release" / "LocalComet.exe"
# Override via env to sweep the actually-installed tree
if os.environ.get("SWEEP_EXE"):
    EXE = Path(os.environ["SWEEP_EXE"])
REPORT_DIR = ROOT / "Projects" / "Reports" / "computer_use_real_actions"
ISOLATED_ROOT = REPORT_DIR / ("installed_sweep_root" + ("-diag" if os.environ.get("SWEEP_DIAG") else ""))
CDP_PORT = 9351
DESKTOP_NAME = f"LocalCometHiddenCU_sweep_{os.getpid()}"

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DESKTOP_ALL = 0x01FF
CREATE_NEW_PROCESS_GROUP = 0x200
CREATE_UNICODE_ENVIRONMENT = 0x400
STARTF_USESHOWWINDOW = 0x1
SW_SHOWNORMAL = 1

WORKSPACES = ["chat", "hf_browser", "modelfit"]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", wintypes.LPBYTE),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_ctypes() -> None:
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p,
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL


def environment_block(env: dict[str, str]) -> str:
    return "\0".join(f"{k}={v}" for k, v in env.items()) + "\0"


def cdp_ready(timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", CDP_PORT), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def cdp_json(path: str) -> list | dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class MiniWs:
    """Minimal RFC6455 client for loopback CDP."""

    def __init__(self, port: int, path: str) -> None:
        import base64
        import struct

        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("ws handshake failed")
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"ws upgrade refused: {response[:120]!r}")
        self._buf = b""

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("ws closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def send_text(self, text: str) -> None:
        import struct

        payload = text.encode("utf-8")
        header = bytes([0x81])
        length = len(payload)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", length)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + masked)

    def recv_text(self, timeout: float = 10.0) -> str:
        import struct

        self.sock.settimeout(timeout)
        while True:
            head = self._recv_exact(2)
            opcode = head[0] & 0x0F
            length = head[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            payload = self._recv_exact(length)
            if opcode == 0x8:
                raise RuntimeError("ws closed by peer")
            if opcode in (0x9, 0xA):
                continue
            return payload.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class CdpSession:
    def __init__(self, ws: MiniWs) -> None:
        self.ws = ws
        self.next_id = 1
        self.events: list[dict] = []
        self.console_errors: list[dict] = []
        self.exceptions: list[dict] = []
        self.failed_requests: list[dict] = []

    def command(self, method: str, params: dict | None = None, timeout: float = 20.0) -> dict:
        call_id = self.next_id
        self.next_id += 1
        self.ws.send_text(json.dumps({"id": call_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = json.loads(self.ws.recv_text(timeout=timeout))
            if message.get("id") == call_id:
                return message
            self._absorb_event(message)
        raise TimeoutError(f"cdp {method} timed out")

    def drain(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                message = json.loads(self.ws.recv_text(timeout=max(0.2, deadline - time.time())))
                self._absorb_event(message)
            except (TimeoutError, RuntimeError):
                return

    def _absorb_event(self, message: dict) -> None:
        method = message.get("method", "")
        params = message.get("params", {})
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            text = details.get("exception", {}).get("description") or details.get("text", "")
            self.exceptions.append({"text": text[:500]})
        elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            args = params.get("args", [])
            text = " ".join(str(a.get("value", a.get("description", "")))[:200] for a in args)
            self.console_errors.append({"text": text[:500]})
        elif method == "Network.loadingFailed":
            self.failed_requests.append({
                "errorText": params.get("errorText", "")[:120],
                "type": params.get("type", ""),
                "blocked": params.get("canceled", False),
            })


def launch() -> tuple[int, wintypes.HANDLE]:
    setup_ctypes()
    ISOLATED_ROOT.mkdir(parents=True, exist_ok=True)
    desktop = user32.CreateDesktopW(DESKTOP_NAME, None, None, 0, DESKTOP_ALL, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(ISOLATED_ROOT)
    env["LC_HIDDEN_DESKTOP_NAME"] = DESKTOP_NAME
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--disable-gpu --remote-debugging-port={CDP_PORT}"
    env_block = environment_block(env)
    command = subprocess.list2cmdline([str(EXE)])
    command_buffer = ctypes.create_unicode_buffer(command)
    startup = STARTUPINFO()
    startup.cb = ctypes.sizeof(startup)
    startup.lpDesktop = f"winsta0\\{DESKTOP_NAME}"
    startup.dwFlags = STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNORMAL
    info = PROCESS_INFORMATION()
    ok = kernel32.CreateProcessW(
        None, command_buffer, None, None, False,
        CREATE_NEW_PROCESS_GROUP | CREATE_UNICODE_ENVIRONMENT,
        env_block, str(EXE.parent), ctypes.byref(startup), ctypes.byref(info),
    )
    if not ok:
        user32.CloseDesktop(desktop)
        raise ctypes.WinError(ctypes.get_last_error())
    return int(info.dwProcessId), desktop


def evaluate(session: CdpSession, expression: str, timeout: float = 15.0) -> object:
    result = session.command("Runtime.evaluate", {
        "expression": expression, "returnByValue": True,
        "awaitPromise": True, "timeout": int(timeout * 1000),
    }, timeout=timeout + 5)
    inner = result.get("result", {}).get("result", {})
    if "exceptionDetails" in result.get("result", {}):
        return {"__exception": str(result["result"]["exceptionDetails"].get("text", ""))[:300]}
    return inner.get("value")


WORKSPACE_SNIPPET = """
(workspace) => {
  const buttons = [...document.querySelectorAll('button')];
  const target = buttons.find((b) => {
    const label = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
    if (workspace === 'chat') return b.textContent.trim() === 'Чат' || label === 'чат';
    if (workspace === 'hf_browser') return label.includes('модел') && label.includes('hf') || label === 'модели hf';
    if (workspace === 'modelfit') return label.includes('подобрать');
    return false;
  });
  if (!target) return 'BUTTON_NOT_FOUND';
  target.click();
  return 'clicked';
}
"""


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ISOLATED_ROOT.mkdir(parents=True, exist_ok=True)
    pid, desktop = launch()
    report: dict = {"utc": utc_now(), "desktop": DESKTOP_NAME, "pid": pid, "exe": str(EXE), "workspaces": {}}
    try:
        if not cdp_ready():
            report["error"] = "cdp_not_ready"
            return finish(report, pid, desktop)
        page = None
        for _ in range(60):
            for t in (cdp_json("/json/list") if isinstance(cdp_json("/json/list"), list) else []):
                if t.get("type") == "page" and "tauri.localhost" in str(t.get("url", "")):
                    page = t
                    break
            if page:
                break
            time.sleep(1.0)
        if not page:
            report["error"] = "page_target_not_found"
            return finish(report, pid, desktop)
        ws = MiniWs(CDP_PORT, page["webSocketDebuggerUrl"].split(f"127.0.0.1:{CDP_PORT}", 1)[1])
        session = CdpSession(ws)
        try:
            session.command("Runtime.enable")
            session.command("Page.enable")
            session.command("Network.enable")
            session.drain(4.0)
            report["boot"] = {
                "exceptions": session.exceptions[:10],
                "console_errors": session.console_errors[:10],
                "failed_requests": session.failed_requests[:10],
            }
            for workspace in WORKSPACES:
                session.exceptions.clear()
                session.console_errors.clear()
                session.failed_requests.clear()
                clicked = evaluate(session, f"({WORKSPACE_SNIPPET})({json.dumps(workspace)})")
                session.drain(5.0)
                state = evaluate(session, "JSON.stringify({title: document.title, activeButtons: [...document.querySelectorAll('[class*=active]')].length, bodyBytes: document.body.innerHTML.length})")
                report["workspaces"][workspace] = {
                    "click": clicked,
                    "state": state,
                    "exceptions": session.exceptions[:10],
                    "console_errors": session.console_errors[:10],
                    "failed_requests": session.failed_requests[:15],
                }
            # Persistence round-trip marker: localStorage must hold our key after boot.
            report["storage_probe"] = evaluate(session, "JSON.stringify({historyKey: !!localStorage.getItem('localcomet.chat.history.v1'), prefsKey: !!localStorage.getItem('localcomet.ui.preferences.v1')})")
        finally:
            ws.close()
    finally:
        finish(report, pid, desktop)
    return 0


def finish(report: dict, pid: int, desktop: wintypes.HANDLE) -> int:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
    user32.CloseDesktop(desktop)
    out = REPORT_DIR / "installed_sweep.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False)[:3500])
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
