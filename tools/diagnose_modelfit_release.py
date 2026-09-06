#!/usr/bin/env python3
"""One-shot ModelFit release diagnostic (hidden isolated desktop).

Launches the INSTALLED release LocalComet.exe on a hidden Win32 desktop with a
fresh isolated LOCALAPPDATA and a loopback CDP port, opens the ModelFit
workspace via UIA, then reads over CDP what actually happened to the
/modelfit.html iframe (target list + failed request text). Everything is torn
down afterwards; the user's running instance is never touched.

Run: python tools/diagnose_modelfit_release.py
Output: Projects/Reports/computer_use_real_actions/modelfit_release_diag.json
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
EXE = Path(r"C:\Users\DNS\AppData\Local\Programs\LocalComet\LocalComet.exe")
REPORT_DIR = ROOT / "Projects" / "Reports" / "computer_use_real_actions"
CDP_PORT = 9341
DESKTOP_NAME = f"LocalCometHiddenCU_mfdiag_{os.getpid()}"
ISOLATED_ROOT = REPORT_DIR / "modelfit_release_diag_root"

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DESKTOP_ALL = 0x01FF
CREATE_NEW_PROCESS_GROUP = 0x200
CREATE_UNICODE_ENVIRONMENT = 0x400
STARTF_USESHOWWINDOW = 0x1
SW_SHOWNORMAL = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", wintypes.LPBYTE),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


SW_SHOWNORMAL = 1


def setup_ctypes() -> None:
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        ctypes.c_void_p, ctypes.c_void_p,
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL


def environment_block(env: dict[str, str]) -> str:
    return "\0".join(f"{key}={value}" for key, value in env.items()) + "\0"


def cdp_ready(timeout: float = 60.0) -> bool:
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
    """Minimal RFC6455 client for loopback CDP: text frames only, no TLS."""

    def __init__(self, host: str, port: int, path: str) -> None:
        import base64
        import struct

        self.sock = socket.create_connection((host, port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
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
            if opcode in (0x9, 0xA):  # ping/pong control frames
                continue
            return payload.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def cdp_command(ws: MiniWs, call_id: int, method: str, params: dict | None = None, timeout: float = 15.0) -> dict:
    ws.send_text(json.dumps({"id": call_id, "method": method, "params": params or {}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        message = json.loads(ws.recv_text(timeout=timeout))
        if message.get("id") == call_id:
            return message
    raise TimeoutError(f"cdp {method} timed out")


def main() -> int:
    setup_ctypes()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
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
    pid = int(info.dwProcessId)
    result: dict = {"utc": utc_now(), "desktop": DESKTOP_NAME, "pid": pid, "exe": str(EXE)}
    try:
        result["cdp_ready"] = cdp_ready()
        if result["cdp_ready"]:
            # Wait for the SvelteKit page target to appear.
            targets: list = []
            for _ in range(40):
                raw = cdp_json("/json/list")
                targets = raw if isinstance(raw, list) else []
                if any("index.html" in str(t.get("url", "")) or "tauri" in str(t.get("url", "")) for t in targets):
                    break
                time.sleep(0.5)
            result["targets"] = [
                {"type": t.get("type"), "url": t.get("url"), "title": t.get("title")}
                for t in targets
            ]
            # Give the UI time to settle, then re-list: a FAILED iframe shows as
            # its own target only while alive; the main page target keeps the
            # frame tree, so re-listing late catches transient frame targets.
            time.sleep(3)
            late = cdp_json("/json/list")
            result["targets_late"] = [
                {"type": t.get("type"), "url": t.get("url"), "title": t.get("title")}
                for t in (late if isinstance(late, list) else [])
            ]
            # Decisive probe: navigate the app page itself to /modelfit.html and
            # read back what was served. Same custom-protocol path an iframe
            # request takes (GET http://tauri.localhost/modelfit.html).
            page = next((t for t in (late if isinstance(late, list) else []) if t.get("type") == "page"), None)
            if page and page.get("webSocketDebuggerUrl"):
                ws_path = page["webSocketDebuggerUrl"].split(f"127.0.0.1:{CDP_PORT}", 1)[1]
                ws = MiniWs("127.0.0.1", CDP_PORT, ws_path)
                try:
                    cdp_command(ws, 1, "Page.enable")
                    nav = cdp_command(ws, 2, "Page.navigate", {"url": "http://tauri.localhost/modelfit.html"})
                    result["nav_result"] = nav.get("result")
                    time.sleep(2.5)
                    evalr = cdp_command(ws, 3, "Runtime.evaluate", {
                        "expression": "JSON.stringify({title: document.title, ready: document.readyState, bytes: document.documentElement.outerHTML.length, head: document.head ? document.head.innerHTML.length : -1, bodyStart: document.body ? document.body.innerHTML.slice(0, 200) : ''})",
                        "returnByValue": True,
                    })
                    value = evalr.get("result", {}).get("result", {}).get("value")
                    result["modelfit_probe"] = json.loads(value) if isinstance(value, str) else value
                finally:
                    ws.close()
            # Back to the app page: test an IN-PAGE iframe (exactly what AppShell
            # does) and capture load/error timing.
            page2 = next((t for t in cdp_json("/json/list") if t.get("type") == "page"), None)
            if page2 and page2.get("webSocketDebuggerUrl"):
                ws_path2 = page2["webSocketDebuggerUrl"].split(f"127.0.0.1:{CDP_PORT}", 1)[1]
                ws2 = MiniWs("127.0.0.1", CDP_PORT, ws_path2)
                try:
                    cdp_command(ws2, 10, "Page.enable")
                    cdp_command(ws2, 11, "Page.navigate", {"url": "http://tauri.localhost/"})
                    time.sleep(2.5)
                    probe_expr = """
new Promise((resolve) => {
  const f = document.createElement('iframe');
  f.src = '/modelfit.html';
  let done = false;
  const finish = (outcome) => { if (!done) { done = true; resolve(JSON.stringify(outcome)); } };
  f.onload = () => {
    let nested = null;
    try { nested = f.contentDocument ? {title: f.contentDocument.title, bytes: f.contentDocument.documentElement.outerHTML.length} : null; }
    catch (e) { nested = {error: String(e)}; }
    finish({loaded: true, nested, origin: f.contentWindow ? String(f.contentWindow.location.origin) : null});
  };
  f.onerror = () => finish({loaded: false, errorEvent: true});
  document.body.appendChild(f);
  setTimeout(() => finish({timeout: true, removed: !f.isConnected, readyState: f.contentDocument ? f.contentDocument.readyState : null}), 6000);
})
"""
                    evalr2 = cdp_command(ws2, 12, "Runtime.evaluate", {
                        "expression": probe_expr, "returnByValue": True, "awaitPromise": True, "timeout": 9000,
                    })
                    value2 = evalr2.get("result", {}).get("result", {}).get("value")
                    result["iframe_probe"] = json.loads(value2) if isinstance(value2, str) else evalr2.get("result")
                finally:
                    ws2.close()
    finally:
        # Tear down OUR isolated tree only.
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, text=True, check=False,
        )
        user32.CloseDesktop(desktop)

    out = REPORT_DIR / "modelfit_release_diag.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=1, ensure_ascii=False)[:2000])
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
