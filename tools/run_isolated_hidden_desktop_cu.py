from __future__ import annotations

import argparse
import base64
import asyncio
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import socket
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "modules" / "_vendor"
# The harness itself may run with PYTHONNOUSERSITE=1, just like the confined
# sidecar. Resolve UIA dependencies from the shipped vendor tree, never from
# an ambient user-site installation.
for path in (VENDOR_ROOT, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
PYTHON = Path(sys.executable).resolve()
LAUNCHER = ROOT / "tools" / "launch_localcomet_dev.py"
CURRENT_APP_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "LocalCometDev" / "app-data"
DEFAULT_ISOLATED_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "LocalCometHiddenCU" / "default"
)
REPORT_DIR = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "isolated_hidden_desktop"
ISOLATED_VITE_PORT = int(os.environ.get("LC_ISOLATED_VITE_PORT", "1423"))
ISOLATED_CDP_PORT = int(os.environ.get("LC_ISOLATED_CDP_PORT", "9223"))
ISOLATED_BROWSER_CDP_PORT = int(os.environ.get("LC_ISOLATED_BROWSER_CDP_PORT", str(ISOLATED_CDP_PORT + 1)))
ISOLATED_WEBVIEW2_UDF_NAME = "webview2-user-data"
ISOLATED_BROWSER_PROFILE_NAME = "browser-user-data"
NO_NEW_TOOL_GRACE_SECONDS = 45.0
HIDDEN_BROWSER_ROOT_NAME = "LocalCometHiddenCU"
PROVENANCE_SUFFIX = ".provenance.json"
HIDDEN_CARGO_TARGET_SUBKEY = "hidden-isolated"


def resolve_hidden_cargo_target(source_root: Path, parent_local_appdata: str) -> Path:
    """Resolve the stable hidden target from the real parent AppData only."""
    from tools import launch_localcomet_dev as legacy

    parent = str(parent_local_appdata or "").strip()
    if not parent:
        raise RuntimeError("parent LOCALAPPDATA is required for canonical hidden Cargo target routing")
    return legacy.resolve_canonical_cargo_target_dir(
        Path(source_root),
        env={"LOCALAPPDATA": parent},
        subkey=HIDDEN_CARGO_TARGET_SUBKEY,
    )


def expected_isolated_dev_url(vite_port: int = ISOLATED_VITE_PORT) -> str:
    """The devUrl the isolated workspace config is patched to."""
    return f"http://127.0.0.1:{vite_port}"


def hidden_browser_profile_path(isolated_root: Path) -> Path:
    """Return the profile path matching the worker's effective LOCALAPPDATA.

    The worker intentionally remaps LOCALAPPDATA to its isolated root. The
    broker validates the profile against ``%LOCALAPPDATA%\\LocalCometHiddenCU``;
    keeping this derivation in one helper prevents a root-level profile from
    being rejected while still keeping all browser state manifest-owned.
    """
    return Path(isolated_root) / HIDDEN_BROWSER_ROOT_NAME / ISOLATED_BROWSER_PROFILE_NAME


class IsolatedStartupError(RuntimeError):
    """Explicit infrastructure failure classification.

    Never a tool PASS/FAIL: this marks the RUN as blocked before any
    interaction happens, with a machine-readable error_type.
    """

    def __init__(self, error_type: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}

MODEL_ID = "custom-hf-72962196cbe48a1dc6b432301cb3666a0aad360a53a43139094d52aa62b0f4f6"
MODEL_NAME = "Qwen3-1.7B.Q4_K_M.gguf"
MODEL_SHA256 = "ea2aa5f1cce3c8df81ae5fd292a6ed265b8393cc89534dc21fc5327cc974116a"
MODEL_SOURCE = CURRENT_APP_DATA / "models" / "custom" / MODEL_ID / MODEL_NAME

SCENARIOS = (
    {"id": "notepad_open_type", "prompt": "Открой Блокнот и напечатай в нём: LocalComet isolated smoke test."},
    {"id": "notepad_open_paste", "prompt": "Открой Блокнот и вставь в нём: LocalComet paste smoke."},
    {"id": "calculator_basic", "prompt": "Открой Калькулятор и вычисли 17 плюс 25. Покажи результат."},
    {"id": "desktop_screenshot", "prompt": "Открой Блокнот, дождись его окна, затем выполни Computer Use screenshot текущего изолированного рабочего стола и сообщи, что наблюдаешь."},
    {"id": "browser_youtube", "prompt": "Открой YouTube в браузере."},
    {"id": "browser_readonly_search", "prompt": "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."},
    {"id": "file_explorer_open", "prompt": "Открой Проводник и покажи папку Документы. Не удаляй и не изменяй файлы."},
    {"id": "notepad_recovery", "prompt": "Если Блокнот открыт, переключись на него и добавь строку: recovery-check."},
    {"id": "active_window_observe", "prompt": "Определи активное окно на рабочем столе и сообщи его название."},
    {"id": "screenshot_after_actions", "prompt": "Сделай ещё один снимок экрана после предыдущих действий и сообщи, изменилось ли состояние."},
    {"id": "browser_second_readonly_search", "prompt": "В браузере найди справочную страницу о Windows Notepad. Только чтение, без публикаций и отправок."},
    {"id": "computer_use_click", "prompt": "Кликни по кнопке Пуск и сообщи, что произошло."},
    {"id": "computer_use_double_click", "prompt": "Двойной клик по кнопке Чат и сообщи результат."},
    {"id": "computer_use_drag", "prompt": "Перетащи курсор из точки 100,100 в точку 200,200 и сообщи результат."},
    {"id": "computer_use_type", "prompt": "Введи текст: LocalComet action type smoke."},
    {"id": "computer_use_key", "prompt": "Нажми Enter и сообщи результат."},
    {"id": "computer_use_hotkey", "prompt": "Нажми Ctrl+F и сообщи результат."},
    {"id": "computer_use_scroll", "prompt": "Прокрути страницу вниз и сообщи результат."},
    {"id": "computer_use_wait", "prompt": "Подожди 1 секунду и сообщи, что ожидание завершено."},
    {"id": "calculator_repeat", "prompt": "Открой Калькулятор и вычисли 144 разделить на 12. Сообщи результат."},
    {"id": "notepad_final_text", "prompt": "Открой Блокнот и напечатай финальную строку isolated-final-check."},
    {"id": "safe_recovery", "prompt": "Если предыдущее действие не завершилось, сообщи честное состояние и не повторяй опасные действия автоматически."},
)

# Calculator coverage remains documented for historical audit purposes, but it
# is disabled for all automatic/hidden harness execution until explicitly
# re-enabled in a separately reviewed change. This prevents the default cyclic
# campaign from opening Calculator in front of the user.
DISABLED_AUTO_SCENARIO_IDS = frozenset({"calculator_basic", "calculator_repeat"})
AUTO_SCENARIOS = tuple(item for item in SCENARIOS if item["id"] not in DISABLED_AUTO_SCENARIO_IDS)

# These scenarios contain a mutating, launch, navigation, or input action.
# Their PASS verdict is invalid unless the UI exposes a real approval event and
# the event is correlated to the model request/action and canonical input.
APPROVAL_REQUIRED_SCENARIO_IDS = {
    "browser_youtube",
    "browser_readonly_search",
    "browser_second_readonly_search",
}


GUARDED_SCENARIO_IDS = frozenset({
    "notepad_open_type",
    "notepad_open_paste",
    "browser_youtube",
    "browser_readonly_search",
    "file_explorer_open",
    "notepad_recovery",
    "computer_use_click",
    "computer_use_double_click",
    "computer_use_drag",
    "computer_use_type",
    "computer_use_key",
    "computer_use_hotkey",
    "computer_use_scroll",
    "notepad_final_text",
})


# Win32 desktop constants. The worker is born on this desktop and never calls
# SwitchDesktop/SetForegroundWindow against the user's interactive desktop.
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
DESKTOP_READOBJECTS = 0x0001
DESKTOP_CREATEWINDOW = 0x0002
DESKTOP_ENUMERATE = 0x0040
DESKTOP_WRITEOBJECTS = 0x0080
DESKTOP_SWITCHDESKTOP = 0x0100
DESKTOP_ACCESS = DESKTOP_READOBJECTS | DESKTOP_CREATEWINDOW | DESKTOP_ENUMERATE | DESKTOP_WRITEOBJECTS | DESKTOP_SWITCHDESKTOP
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_UNICODE_ENVIRONMENT = 0x00000400
STARTF_USESHOWWINDOW = 0x00000001
SW_SHOWNORMAL = 1
INFINITE = 0xFFFFFFFF
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
user32.GetThreadDesktop.restype = wintypes.HANDLE
user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
user32.GetUserObjectInformationW.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


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
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
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


kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.BOOL,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFO),
    ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL

# Owner-scoped child lifecycle (plan P0.1 item 5): every process THIS worker
# spawns is assigned to a private job object. Closing the last job handle вЂ”
# including on worker crash or TerminateProcess вЂ” makes the kernel terminate
# exactly that tree. Foreign/user processes are unreachable by construction:
# nothing we did not spawn is ever assigned, and breakaway is allowed so a
# Chromium-style child spawner can never be broken by job membership.
JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
PROCESS_TERMINATE_RIGHT = 0x0001
PROCESS_SET_QUOTA_RIGHT = 0x0100


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE


def create_cleanup_job() -> wintypes.HANDLE:
    """Create the kill-on-close lease for this worker's own process tree."""
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
    )
    if not kernel32.SetInformationJobObject(
        job, JobObjectExtendedLimitInformation,
        ctypes.byref(limits), ctypes.sizeof(limits),
    ):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(error)
    return job


def assign_to_cleanup_job(job: wintypes.HANDLE, pid: int) -> bool:
    """Assign one of OUR direct children (and its whole future tree)."""
    handle = kernel32.OpenProcess(PROCESS_SET_QUOTA_RIGHT | PROCESS_TERMINATE_RIGHT, False, int(pid))
    if not handle:
        return False
    try:
        return bool(kernel32.AssignProcessToJobObject(job, handle))
    finally:
        kernel32.CloseHandle(handle)


def _cargo_identity() -> dict[str, str]:
    """Exact cargo executable identity for build parity evidence (В§3.3)."""
    exe = shutil.which("cargo") or ""
    version = ""
    if exe:
        try:
            completed = subprocess.run(
                [exe, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20
            )
            if completed.returncode == 0:
                version = (completed.stdout or "").strip().splitlines()[0]
        except Exception:
            version = ""
    return {"path": exe, "version": version}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact_secret_refs(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_screenshot_owner_context(
    path: Path,
    *,
    pid: int | str | None,
    desktop: str,
    request_id: str,
    action_id: str,
) -> bool:
    """Publish only broker-card identity for a later owner-scoped screenshot."""
    try:
        owner_pid = int(pid) if not isinstance(pid, bool) else 0
    except (TypeError, ValueError):
        owner_pid = 0
    desktop = str(desktop or "").strip()
    if owner_pid <= 0 or not desktop:
        return False
    write_json(path, {
        "schema_version": "localcomet.screenshot-owner-context.v1",
        "source": "rust_broker_card",
        "pid": owner_pid,
        "desktop": desktop,
        "request_id": str(request_id or ""),
        "action_id": str(action_id or ""),
    })
    return True


# ---------------------------------------------------------------------------
# Continuation-secret redaction (F-03). Raw broker continuation tokens
# (`cgr_...`) are one-time capability material: they may travel exactly once
# over the typed Tauri response to the authorized caller, but they must never
# be persisted. Every evidence artifact written by this harness goes through
# write_json, so the scrub lives there as the single enforcement point.
# ---------------------------------------------------------------------------

SECRET_REF_RE = re.compile(r"\bcgr_[0-9a-fA-F]{8,}\b")
SECRET_REF_MASK = "<redacted:cgr>"


def redact_secret_refs(value: Any) -> Any:
    """Deep-walk payload and mask raw continuation tokens in place."""
    if isinstance(value, str):
        return SECRET_REF_RE.sub(SECRET_REF_MASK, value)
    if isinstance(value, dict):
        return {key: redact_secret_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret_refs(item) for item in value]
    return value


def seed_isolated_app_data(isolated_root: Path) -> dict[str, Any]:
    if not MODEL_SOURCE.is_file():
        raise RuntimeError(f"Qwen3 source artifact is missing: {MODEL_SOURCE}")
    observed = sha256(MODEL_SOURCE)
    if observed != MODEL_SHA256:
        raise RuntimeError(f"Qwen3 SHA-256 mismatch: {observed}")
    source_runtime = CURRENT_APP_DATA / "runtimes"
    source_runtime_state = CURRENT_APP_DATA / "runtime-state"
    source_manifest = source_runtime_state / "custom-models.v1.json"
    target_app_data = isolated_root / "LocalCometDev" / "app-data"
    target_app_data.mkdir(parents=True, exist_ok=True)
    target_runtime = target_app_data / "runtimes"
    if source_runtime.is_dir() and not target_runtime.exists():
        shutil.copytree(source_runtime, target_runtime)
    target_runtime_state = target_app_data / "runtime-state"
    target_runtime_state.mkdir(parents=True, exist_ok=True)
    # Repair pass: the app can leave runtime-state emptied (observed after
    # repeated runs), which hides the custom model from the backend catalog
    # even though the GGUF is on disk. Re-seed the manifest whenever absent.
    manifest_repaired = False
    target_manifest = target_runtime_state / "custom-models.v1.json"
    if source_manifest.is_file() and not target_manifest.is_file():
        shutil.copy2(source_manifest, target_manifest)
        manifest_repaired = True
    target_model_dir = target_app_data / "models" / "custom" / MODEL_ID
    target_model_dir.mkdir(parents=True, exist_ok=True)
    target_model = target_model_dir / MODEL_NAME
    if not target_model.exists():
        shutil.copy2(MODEL_SOURCE, target_model)
    return {
        "source": str(MODEL_SOURCE),
        "target": str(target_model),
        "sha256": observed,
        "qwen25_copied": False,
        "runtime_seeded": target_runtime.is_dir(),
        "runtime_state_seeded": target_manifest.is_file(),
        "manifest_repaired": manifest_repaired,
    }


def environment_block(env: dict[str, str]) -> ctypes.Array[ctypes.c_wchar]:
    raw = "\0".join(f"{key}={value}" for key, value in sorted(env.items(), key=lambda item: item[0].upper())) + "\0\0"
    return ctypes.create_unicode_buffer(raw)


def choose_isolated_browser_cdp_port() -> int:
    """Return a currently free loopback port for the broker-owned browser.

    The historical fixed 9224 port can be occupied by a foreign or stale
    Chromium process. A fresh per-run port prevents Chrome from silently
    ignoring the remote-debugging argument and makes the later CDP probe
    evidence-correlated to this run.
    """
    requested_raw = os.environ.get("LC_ISOLATED_BROWSER_CDP_PORT", "").strip()
    candidates: list[int] = []
    if requested_raw.isdigit():
        candidates.append(int(requested_raw))
    candidates.append(0)
    for candidate in candidates:
        if candidate and not (1024 <= candidate <= 65535):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            port = int(probe.getsockname()[1])
            if 1024 <= port <= 65535:
                return port
    raise RuntimeError("unable to allocate a free loopback browser CDP port")


def create_worker_process(
    desktop_name: str,
    isolated_root: Path,
    report_dir: Path,
    cases: int,
    probe_only: bool = False,
    enable_computer_use: bool = False,
    scenario_id: str | None = None,
    use_intent: bool = False,
    cancel_after_ms: int | None = None,
    cancel_after_continuation: bool = False,
    restart_phase: int = 0,
) -> tuple[int, wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE]:
    desktop = user32.CreateDesktopW(desktop_name, None, None, 0, DESKTOP_ACCESS, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    env = os.environ.copy()
    parent_local_appdata = str(os.environ.get("LOCALAPPDATA", "")).strip()
    if not parent_local_appdata:
        raise RuntimeError("parent LOCALAPPDATA is required for canonical hidden Cargo target routing")
    env["LC_HIDDEN_CANONICAL_LOCALAPPDATA"] = parent_local_appdata
    env["LOCALAPPDATA"] = str(isolated_root)
    env["LC_HIDDEN_DESKTOP_NAME"] = desktop_name
    env["LC_HIDDEN_REPORT_DIR"] = str(report_dir)
    env["LC_ISOLATED_BROWSER_CDP_PORT"] = str(choose_isolated_browser_cdp_port())
    env["LC_HIDDEN_ISOLATED_ROOT"] = str(isolated_root)
    if use_intent:
        env["LC_USE_INTENT"] = "1"
        # Explicit, auditable opt-in: arm session capabilities in the isolated
        # app instance so the deterministic intent path can pass the
        # deny-by-default gate. Every dangerous action still consumes its own
        # scoped one-time approval token afterwards.
        env["LOCALCOMET_ISOLATED_CU_CAPABILITIES"] = (
            "localcomet.isolated-hidden-test.v1"
        )
    if cancel_after_continuation:
        env["LOCALCOMET_ISOLATED_CU_CAPABILITIES"] = "localcomet.isolated-hidden-test.v1"
        # This marker is meaningful only in the Cargo feature-gated harness
        # build; it is not exported by ordinary LocalComet launch paths.
        env["LC_FORCE_BROKER_CONTINUATION_PENDING"] = "1"
    if restart_phase in (1, 2):
        env["LC_RESTART_PHASE"] = str(restart_phase)
        env["LC_USE_CODING"] = "1"
    if os.environ.get("LC_USE_CODING", "") == "1" or restart_phase in (1, 2):
        # Coding E2E needs the same auditable opt-in: files.write is a
        # guarded capability and coding_start_approval refuses without it.
        env["LOCALCOMET_ISOLATED_CU_CAPABILITIES"] = (
            "localcomet.isolated-hidden-test.v1"
        )
    env_block = environment_block(env)
    command = subprocess.list2cmdline([
        str(PYTHON), "-B", str(Path(__file__).resolve()), "--worker",
        *(["--probe-only"] if probe_only else []),
        "--desktop-name", desktop_name,
        "--isolated-root", str(isolated_root),
        "--report-dir", str(report_dir),
        "--cases", str(cases),
        *( ["--enable-computer-use"] if enable_computer_use else []),
        *( ["--use-intent"] if use_intent else []),
        *( ["--scenario", scenario_id] if scenario_id else []),
        *( ["--cancel-after-ms", str(cancel_after_ms)] if cancel_after_ms is not None else []),
        *( ["--cancel-after-continuation"] if cancel_after_continuation else []),
        *( ["--restart-phase", str(restart_phase)] if restart_phase in (1, 2) else []),
    ])
    command_buffer = ctypes.create_unicode_buffer(command)
    startup = STARTUPINFO()
    startup.cb = ctypes.sizeof(STARTUPINFO)
    startup.lpDesktop = f"winsta0\\{desktop_name}"
    startup.dwFlags = STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNORMAL
    info = PROCESS_INFORMATION()
    ok = kernel32.CreateProcessW(
        None, command_buffer, None, None, False,
        CREATE_NEW_PROCESS_GROUP | CREATE_UNICODE_ENVIRONMENT,
        env_block, str(ROOT), ctypes.byref(startup), ctypes.byref(info),
    )
    if not ok:
        user32.CloseDesktop(desktop)
        raise ctypes.WinError(ctypes.get_last_error())
    kernel32.CloseHandle(info.hThread)
    return int(info.dwProcessId), desktop, info.hProcess, info.hProcess


def run_restart_parent(args: argparse.Namespace) -> int:
    """Run phase-1 and phase-2 app processes against one owned LOCALAPPDATA root."""
    isolated_root = Path(args.isolated_root).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    seed = seed_isolated_app_data(isolated_root)
    write_json(report_dir / "restart_isolation_seed.json", {"created_utc": utc_now(), **seed})
    desktop_base = str(getattr(args, "desktop_name", "") or "").strip() or f"LocalCometHiddenCU_{os.getpid()}"
    phase_reports = [report_dir / "restart_phase1", report_dir / "restart_phase2"]
    phase_results: list[dict[str, Any]] = []
    for phase, phase_report in ((1, phase_reports[0]), (2, phase_reports[1])):
        phase_report.mkdir(parents=True, exist_ok=True)
        desktop_name = f"{desktop_base}_P{phase}"
        pid, desktop, process_handle, _ = create_worker_process(
            desktop_name,
            isolated_root,
            phase_report,
            1,
            probe_only=False,
            enable_computer_use=args.enable_computer_use,
            scenario_id=None,
            use_intent=False,
            cancel_after_ms=None,
            cancel_after_continuation=False,
            restart_phase=phase,
        )
        print(json.dumps({"restart_phase": phase, "desktop": desktop_name, "worker_pid": pid, "report_dir": str(phase_report)}, ensure_ascii=False), flush=True)
        try:
            wait_result = kernel32.WaitForSingleObject(process_handle, INFINITE)
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code))
            # Phase 1 intentionally retains the exact isolated root so phase 2
            # can observe the persisted ledger. Phase 2 is the final owner run.
            if phase == 2:
                cleanup_after_worker_exit(phase_report)
            phase_results.append({"phase": phase, "worker_pid": pid, "wait_result": int(wait_result), "worker_exit_code": int(exit_code.value), "report_dir": str(phase_report)})
        finally:
            kernel32.CloseHandle(process_handle)
            user32.CloseDesktop(desktop)
        if phase == 1:
            phase1_payload = phase_report / "restart_phase1.json"
            if phase1_payload.is_file():
                phase1_data = json.loads(phase1_payload.read_text(encoding="utf-8"))
                task_id = str(phase1_data.get("task_id") or "")
                pre_sha = str(phase1_data.get("post_boundary_sha256") or "")
                if task_id:
                    os.environ["LC_RESTART_TASK_ID"] = task_id
                    os.environ["LC_RESTART_PRE_SHA256"] = pre_sha
        if phase_results[-1]["worker_exit_code"] != 0:
            break
    evidence = {
        "schema_version": "localcomet.application-restart.v1",
        "created_utc": utc_now(),
        "isolated_root": str(isolated_root),
        "phase_results": phase_results,
    }
    phase1 = phase_reports[0] / "restart_phase1.json"
    phase2 = phase_reports[1] / "restart_phase2.json"
    if phase1.is_file():
        evidence["phase1"] = json.loads(phase1.read_text(encoding="utf-8"))
    if phase2.is_file():
        evidence["phase2"] = json.loads(phase2.read_text(encoding="utf-8"))
    phase2_payload = evidence.get("phase2") if isinstance(evidence.get("phase2"), dict) else {}
    evidence["classification"] = phase2_payload.get("classification", "NOT_INDEPENDENTLY_VERIFIED")
    write_json(report_dir / "restart_application_evidence.json", evidence)
    print(json.dumps({"restart_probe": "done", "classification": evidence["classification"], "phase_results": phase_results}, ensure_ascii=False), flush=True)
    return 0 if evidence["classification"] == "VERIFIED_SUCCESS" and all(item["worker_exit_code"] == 0 for item in phase_results) else 1


def run_parent(args: argparse.Namespace) -> int:
    if getattr(args, "restart_probe", False):
        return run_restart_parent(args)
    isolated_root = Path(args.isolated_root).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    seed = seed_isolated_app_data(isolated_root)
    write_json(report_dir / "isolation_seed.json", {"created_utc": utc_now(), **seed})
    desktop_name = str(getattr(args, "desktop_name", "") or "").strip() or f"LocalCometHiddenCU_{os.getpid()}"
    pid, desktop, process_handle, _ = create_worker_process(
        desktop_name,
        isolated_root,
        report_dir,
        args.cases,
        probe_only=args.probe_only,
        enable_computer_use=args.enable_computer_use,
        scenario_id=args.scenario,
        use_intent=getattr(args, "use_intent", False),
        cancel_after_ms=getattr(args, "cancel_after_ms", None),
        cancel_after_continuation=getattr(args, "cancel_after_continuation", False),
    )
    print(json.dumps({"desktop": desktop_name, "worker_pid": pid, "isolated_root": str(isolated_root), "report_dir": str(report_dir)}, ensure_ascii=False))
    try:
        result = kernel32.WaitForSingleObject(process_handle, INFINITE)
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code))
        cleanup_after_worker_exit(report_dir)
        print(json.dumps({"wait_result": int(result), "worker_exit_code": int(exit_code.value)}, ensure_ascii=False))
        return int(exit_code.value)
    finally:
        kernel32.CloseHandle(process_handle)
        user32.CloseDesktop(desktop)


def cleanup_after_worker_exit(report_dir: Path) -> None:
    """Delete only completed manifest-owned paths after the worker is dead."""
    from tools import owned_run_cleanup as owned_cleanup

    candidates_path = Path(report_dir) / "owned_cleanup_candidates.json"
    try:
        manifest_path = Path(report_dir) / owned_cleanup.MANIFEST_NAME
        manifest = owned_cleanup.load_manifest(manifest_path)
        if not manifest.get("completed_utc"):
            return
        plan = owned_cleanup.plan_cleanup(
            manifest,
            mode=owned_cleanup.MODE_OWNED_CURRENT_RUN,
        )
        result = owned_cleanup.execute_plan(
            plan,
            mode=owned_cleanup.MODE_OWNED_CURRENT_RUN,
        )
        write_json(candidates_path, {
            "mode": owned_cleanup.MODE_OWNED_CURRENT_RUN,
            "deleted_count": result.get("deleted_count", 0),
            "note": "parent-side cleanup after worker exit; only manifest-listed paths",
            "candidates": plan,
            "results": result.get("results", []),
        })
    except Exception as exc:
        write_json(candidates_path, {
            "mode": owned_cleanup.MODE_OWNED_CURRENT_RUN,
            "deleted_count": 0,
            "error": str(exc)[:300],
        })


def load_uia():
    import uiautomation as auto
    return auto


def uia_walk(root: Any, max_nodes: int = 20_000) -> list[Any]:
    items: list[Any] = []
    queue = [root]
    while queue and len(items) < max_nodes:
        current = queue.pop(0)
        items.append(current)
        try:
            queue.extend(current.GetChildren())
        except Exception:
            pass
    return items


def uia_window(auto: Any) -> Any | None:
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, "LocalComet")
        if hwnd:
            return auto.ControlFromHandle(hwnd)
    except Exception:
        pass
    return None


def controls_named(root: Any, name: str) -> list[Any]:
    out: list[Any] = []
    for control in uia_walk(root):
        try:
            if str(control.Name or "").strip() == name:
                out.append(control)
        except Exception:
            pass
    return out


def named_status(root: Any) -> list[str]:
    values: list[str] = []
    for control in uia_walk(root):
        try:
            name = str(control.Name or "").strip()
            if name and name not in values:
                values.append(name)
        except Exception:
            pass
    return values


_hidden_reader_desktop_name = ""
_hidden_reader_desktop_attached = False
UOI_NAME = 2


def _current_thread_desktop_name() -> str:
    """Read the current thread desktop name without switching or interacting."""
    handle = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    if not handle:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if not user32.GetUserObjectInformationW(
        handle, UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
    ):
        return ""
    return str(buffer.value or "").strip()


def attach_reader_to_hidden_desktop() -> dict[str, Any]:
    """Attach this reader thread to the named desktop without interaction.

    The reader requests only desktop read/enumeration access. It never calls
    SwitchDesktop, SetForegroundWindow, UIA Invoke/Click, or SendInput.
    """
    global _hidden_reader_desktop_name, _hidden_reader_desktop_attached
    desktop_name = str(os.environ.get("LC_HIDDEN_DESKTOP_NAME", "")).strip()
    if not desktop_name:
        return {"ok": False, "reason": "LC_HIDDEN_DESKTOP_NAME_missing", "desktop_name": ""}
    if _hidden_reader_desktop_attached and _hidden_reader_desktop_name == desktop_name:
        return {"ok": True, "desktop_name": desktop_name, "mode": "already_attached"}
    access = DESKTOP_READOBJECTS | DESKTOP_ENUMERATE
    handle = user32.OpenDesktopW(desktop_name, 0, False, access)
    if not handle:
        return {
            "ok": False,
            "reason": "OpenDesktopW_failed",
            "desktop_name": desktop_name,
            "winerror": int(ctypes.get_last_error()),
        }
    try:
        if not user32.SetThreadDesktop(handle):
            error = int(ctypes.get_last_error())
            current_name = _current_thread_desktop_name()
            # A worker created with STARTUPINFO.lpDesktop is already bound to
            # the target. Windows may reject a second bind with ERROR_BUSY=170
            # once that thread owns a desktop object. Accept only when the
            # current desktop name independently equals the requested one.
            if error == 170 and current_name.casefold() == desktop_name.casefold():
                _hidden_reader_desktop_name = desktop_name
                _hidden_reader_desktop_attached = True
                return {
                    "ok": True,
                    "desktop_name": desktop_name,
                    "mode": "already_on_named_desktop",
                    "current_desktop_name": current_name,
                    "set_thread_desktop_winerror": error,
                }
            return {
                "ok": False,
                "reason": "SetThreadDesktop_failed",
                "desktop_name": desktop_name,
                "current_desktop_name": current_name,
                "winerror": error,
            }
        _hidden_reader_desktop_name = desktop_name
        _hidden_reader_desktop_attached = True
        return {"ok": True, "desktop_name": desktop_name, "mode": "attached"}
    finally:
        user32.CloseDesktop(handle)


def _window_desktop_name(hwnd: int) -> str:
    """Return a top-level HWND's desktop name without switching desktops."""
    if not hwnd:
        return ""
    process_id = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(process_id))
    if not thread_id:
        return ""
    handle = user32.GetThreadDesktop(thread_id)
    if not handle:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if not user32.GetUserObjectInformationW(
        handle, UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
    ):
        return ""
    return str(buffer.value or "").strip()


def _uia_control_text(control: Any, auto: Any) -> list[tuple[str, str]]:
    """Read text/value patterns without invoking, focusing, or mutating a control."""
    values: list[tuple[str, str]] = []
    try:
        name = str(control.Name or "").strip()
        if name:
            values.append(("uia_name", name))
    except Exception:
        pass
    pattern_ids = getattr(auto, "PatternId", None)
    text_pattern = None
    try:
        direct_text_pattern = getattr(control, "GetTextPattern", None)
        if callable(direct_text_pattern):
            text_pattern = direct_text_pattern()
    except Exception:
        pass
    if text_pattern is None and pattern_ids is not None:
        try:
            text_pattern = control.GetPattern(pattern_ids.TextPattern)
        except Exception:
            pass
    try:
        if text_pattern and getattr(text_pattern, "DocumentRange", None):
            text = str(text_pattern.DocumentRange.GetText(-1) or "").strip()
            if text:
                values.append(("uia_text_pattern", text))
    except Exception:
        pass
    value_pattern = None
    try:
        direct_value_pattern = getattr(control, "GetValuePattern", None)
        if callable(direct_value_pattern):
            value_pattern = direct_value_pattern()
    except Exception:
        pass
    if value_pattern is None and pattern_ids is not None:
        try:
            value_pattern = control.GetPattern(pattern_ids.ValuePattern)
        except Exception:
            pass
    try:
        value = str(getattr(value_pattern, "Value", "") or "").strip() if value_pattern else ""
        if value:
            values.append(("uia_value_pattern", value))
    except Exception:
        pass
    # Some classic Notepad compatibility controls expose their document text
    # through the native child HWND while UIA Text/Value patterns are stale or
    # unavailable. The HWND is accepted only when it comes from this UIA
    # grounded control; this is read-only and never focuses or sends input.
    try:
        hwnd = int(getattr(control, "NativeWindowHandle", 0) or 0)
        if hwnd:
            length = max(0, int(user32.GetWindowTextLengthW(hwnd)))
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                copied = int(user32.GetWindowTextW(hwnd, buffer, length + 1))
                native_text = str(buffer.value[:copied] or "").strip()
                if native_text:
                    values.append(("uia_native_window_text", native_text))
    except Exception:
        pass
    return values


def read_hidden_window_text(auto: Any, expected_marker: str, timeout: float = 12.0) -> dict[str, Any]:
    """Independently prove text in a hidden Notepad window using UIA reads only."""
    marker = str(expected_marker or "").strip()
    result: dict[str, Any] = {
        "ok": False,
        "expected_marker": marker,
        "source": "uia_read_only",
        "window_title": "",
        "control_type": "",
        "text_length": 0,
        "text_sha256": "",
        "reason": "",
        "windows_scanned": 0,
        "notepad_windows": 0,
        "controls_scanned": 0,
        "pattern_hits": 0,
        "uia_errors": 0,
        "control_type_counts": {},
        "desktop_attachment": {},
        "expected_marker_sha256": hashlib.sha256(marker.encode("utf-8")).hexdigest(),
        "observed_text_digests": [],
        "desktop_scoped_windows": 0,
        "foreign_windows_skipped": 0,
        "unscoped_windows_skipped": 0,
    }
    if not marker:
        result["reason"] = "no expected marker configured"
        return result
    attachment = attach_reader_to_hidden_desktop()
    result["desktop_attachment"] = attachment
    if not attachment.get("ok"):
        result["reason"] = "hidden_uia_desktop_attach_failed"
        return result
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            root = auto.GetRootControl()
            for window in root.GetChildren():
                result["windows_scanned"] += 1
                title = str(window.Name or "").strip()
                title_lower = title.lower()
                if "notepad" not in title_lower and "блокнот" not in title_lower:
                    continue
                try:
                    window_hwnd = int(getattr(window, "NativeWindowHandle", 0) or 0)
                except Exception:
                    window_hwnd = 0
                requested_desktop = str(attachment.get("desktop_name") or "").strip()
                actual_desktop = _window_desktop_name(window_hwnd)
                if not window_hwnd or not actual_desktop:
                    result["unscoped_windows_skipped"] += 1
                    continue
                if actual_desktop.casefold() != requested_desktop.casefold():
                    result["foreign_windows_skipped"] += 1
                    continue
                result["desktop_scoped_windows"] += 1
                result["notepad_windows"] += 1
                for control in uia_walk(window):
                    result["controls_scanned"] += 1
                    control_type = str(getattr(control, "ControlTypeName", "") or "")[:80]
                    if control_type:
                        counts = result["control_type_counts"]
                        counts[control_type] = int(counts.get(control_type, 0)) + 1
                    values = _uia_control_text(control, auto)
                    result["pattern_hits"] += len(values)
                    for source, text in values:
                        if len(result["observed_text_digests"]) < 256 and text:
                            result["observed_text_digests"].append({
                                "source": source,
                                "text_length": len(text),
                                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                "control_type": control_type,
                            })
                        if marker not in text:
                            continue
                        result.update({
                            "ok": True,
                            "source": source,
                            "window_title": title[:160],
                            "control_type": str(getattr(control, "ControlTypeName", "") or "")[:80],
                            "text_length": len(text),
                            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        })
                        return result
        except Exception as exc:
            result["uia_errors"] += 1
            result["reason"] = f"uia read failed: {exc}"
        time.sleep(0.5)
    result["reason"] = result.get("reason") or "expected marker was not observed in hidden Notepad UIA text"
    return result


def click_control(control: Any) -> bool:
    try:
        if not control.IsEnabled:
            return False
    except Exception:
        return False
    try:
        control.Invoke()
        return True
    except Exception:
        try:
            control.Click()
            return True
        except Exception:
            return False


def click_named(root: Any, names: tuple[str, ...]) -> str | None:
    for name in names:
        matches = controls_named(root, name)
        for control in reversed(matches):
            try:
                if control.IsEnabled and click_control(control):
                    return name
            except Exception:
                continue
    return None


def approve_pending(root: Any) -> str | None:
    # Only internal approval labels are considered. No browser posting/payment
    # controls are auto-submitted by this harness.
    return click_named(root, ("РћРґРѕР±СЂРёС‚СЊ", "Р Р°Р·СЂРµС€РёС‚СЊ", "РџРѕРґС‚РІРµСЂРґРёС‚СЊ", "РџСЂРѕРґРѕР»Р¶РёС‚СЊ"))


def wait_for_window(auto: Any, timeout: float, process: subprocess.Popen[Any] | None = None) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None:
            require_native_process_alive(process, "window_wait")
        window = uia_window(auto)
        if window is not None:
            return window
        time.sleep(0.5)
    raise TimeoutError("hidden LocalComet Tauri window did not appear")


def wait_for_composer(auto: Any, timeout: float, process: subprocess.Popen[Any] | None = None) -> tuple[Any, Any | None]:
    deadline = time.monotonic() + timeout
    last_names: list[str] = []
    while time.monotonic() < deadline:
        if process is not None:
            require_native_process_alive(process, "composer_wait")
        root = uia_window(auto)
        if root is not None:
            last_names = named_status(root)
            edits = [c for c in uia_walk(root) if getattr(c, "ControlTypeName", "") == "EditControl"]
            sends = controls_named(root, "Отправить")
            enabled_edit = next((c for c in edits if getattr(c, "IsEnabled", False)), None)
            enabled_send = next((c for c in reversed(sends) if getattr(c, "IsEnabled", False)), None)
            if enabled_edit is not None and enabled_send is not None:
                return enabled_edit, enabled_send
        time.sleep(1.0)
    raise TimeoutError("composer did not become enabled; status=" + " | ".join(last_names[-40:]))


def set_edit_value(auto: Any, edit: Any, text: str) -> None:
    try:
        edit.SetValue(text)
        return
    except Exception:
        pass
    # This fallback executes on the isolated desktop worker, never on the
    # user's interactive desktop.
    edit.Click()
    auto.SendKeys(text, interval=0)


def wait_for_turn(root_getter: Any, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    snapshots: list[list[str]] = []
    while time.monotonic() < deadline:
        root = root_getter()
        if root is not None:
            approved = approve_pending(root)
            names = named_status(root)
            if approved:
                snapshots.append(names[-80:])
            # A new assistant/tool message is represented by a changed UIA
            # tree. We retain snapshots as observation evidence and stop when
            # no active approval and the composer is enabled again.
            edits = [c for c in uia_walk(root) if getattr(c, "ControlTypeName", "") == "EditControl"]
            sends = controls_named(root, "Отправить")
            if any(getattr(c, "IsEnabled", False) for c in edits) and any(getattr(c, "IsEnabled", False) for c in sends):
                return {"state": "composer_ready", "snapshots": snapshots[-4:], "names_tail": names[-80:]}
        time.sleep(1.0)
    return {"state": "observation_timeout", "snapshots": snapshots[-4:]}


def _wait_for_port(port: int, timeout: float) -> bool:
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def patch_isolated_workspace_port(isolated_root: Path, port: int, timeout: float = 180.0) -> bool:
    workspace = isolated_root / "LocalCometDev" / "workspace" / "desktop" / "localcomet-desktop"
    vite_config = workspace / "vite.config.ts"
    package_json = workspace / "package.json"
    tauri_config = workspace / "src-tauri" / "tauri.conf.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if vite_config.is_file() and tauri_config.is_file():
            # Idempotent: whatever port is currently written (fresh 1420 from
            # the sync or a leftover from a previous isolated run) is rewritten
            # to the requested one.
            vite_text = vite_config.read_text(encoding="utf-8")
            vite_text = re.sub(r"port:\s*\d+", f"port: {port}", vite_text, count=1)
            vite_config.write_text(vite_text, encoding="utf-8")
            if package_json.is_file():
                package_text = package_json.read_text(encoding="utf-8")
                package_text = re.sub(r"--port[= ]\d+", f"--port {port}", package_text)
                package_json.write_text(package_text, encoding="utf-8")
            tauri_text = tauri_config.read_text(encoding="utf-8")
            tauri_text = re.sub(r"http://(127\.0\.0\.1|localhost):\d+", f"http://127.0.0.1:{port}", tauri_text)
            tauri_text = patch_tauri_webview_browser_args(tauri_text)
            tauri_config.write_text(tauri_text, encoding="utf-8")
            return True
        time.sleep(0.1)
    return False


def patch_tauri_webview_browser_args(tauri_text: str) -> str:
    """Inject additionalBrowserArgs into the runtime config copy.

    Recent WebView2 runtime builds stopped honoring the
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS environment variable when the
    environment is created explicitly (observed 2026-08-28: the browser
    process started without the harness flags and the CDP endpoint never
    opened). The isolated runtime workspace copy is the authoritative
    harness-only transport config: the product repository config stays
    untouched, and the flags match the env contract exactly.
    """
    if "additionalBrowserArgs" in tauri_text:
        return tauri_text
    # Replicate wry defaults exactly (wry omits its own defaults whenever
    # additional_browser_args is set), matching the observed successful
    # command line; the CDP port is the only harness-specific addition.
    args = ("--autoplay-policy=no-user-gesture-required"
                    f" --disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection"
                    f" --remote-debugging-port={ISOLATED_CDP_PORT}")
    marker = '"visible": false'
    if marker in tauri_text:
        injection = marker + ',\n        "additionalBrowserArgs": "' + args + '"'
    else:
        marker = '"fullscreen": false'
        if marker not in tauri_text:
            raise RuntimeError("tauri.conf.json window block has no visible/fullscreen marker")
        injection = marker + ',\n        "additionalBrowserArgs": "' + args + '"'
    return tauri_text.replace(marker, injection, 1)


def binary_provenance_path(binary: Path) -> Path:
    return Path(str(binary) + PROVENANCE_SUFFIX)


def rust_build_input_fingerprint(source_root: Path) -> str:
    """Hash the source/config inputs that Tauri embeds into the debug binary.

    A dev URL marker alone cannot detect a cached executable built before a
    Rust control-plane or capability change. The hidden harness therefore
    fingerprints the relevant source/config bytes and requires the marker to
    match whenever it evaluates a binary for a live run.
    """
    rust_root = Path(source_root) / "desktop" / "localcomet-desktop" / "src-tauri"
    if not rust_root.is_dir():
        raise RuntimeError("Tauri source root is missing")
    included_suffixes = {".rs", ".toml", ".lock", ".json", ".json5"}
    digest = hashlib.sha256()
    files = sorted(
        path for path in rust_root.rglob("*")
        if path.is_file() and "target" not in path.parts and path.suffix.lower() in included_suffixes
    )
    if not files:
        raise RuntimeError("Tauri source inputs are missing")
    for path in files:
        relative = path.relative_to(rust_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def evaluate_binary_provenance(
    binary: Path,
    expected_dev_url: str,
    expected_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Decide whether a cached isolated debug binary may be reused.

    Tauri bakes build.devUrl into the executable at compile time. A stale
    binary silently loads whatever ELSE is listening on its baked-in port вЂ”
    observed evidence: the hidden window rendered the normal instance's
    :1420 page while the isolated Vite served :1423, so the run blocked on
    "no page target". Reuse therefore requires byte-level proof that THIS
    exact binary was built against THIS run's dev URL:
      - a provenance marker written by a previous verified isolated launch;
      - sha256(binary) equal to the marked digest (no byte drift);
      - the marked dev_url equal to the expected one.
    Anything else fails closed into a rebuild, never a blind reuse.
    """
    marker_path = binary_provenance_path(binary)
    if not binary.is_file():
        return {"usable": False, "reason": "binary_missing"}
    if not marker_path.is_file():
        return {"usable": False, "reason": "provenance_marker_missing"}
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"usable": False, "reason": "provenance_marker_unreadable"}
    if not isinstance(marker, dict):
        return {"usable": False, "reason": "provenance_marker_malformed"}
    observed = sha256(binary)
    if marker.get("sha256") != observed:
        return {"usable": False, "reason": "binary_sha256_mismatch", "expected_dev_url": expected_dev_url}
    marked_url = marker.get("dev_url")
    if marked_url != expected_dev_url:
        return {
            "usable": False,
            "reason": "dev_url_mismatch",
            "marked_dev_url": marked_url,
            "expected_dev_url": expected_dev_url,
        }
    if expected_source_fingerprint is not None:
        marked_source_fingerprint = marker.get("source_fingerprint")
        if not isinstance(marked_source_fingerprint, str):
            return {
                "usable": False,
                "reason": "source_fingerprint_missing",
                "expected_source_fingerprint": expected_source_fingerprint,
            }
        if marked_source_fingerprint != expected_source_fingerprint:
            return {
                "usable": False,
                "reason": "source_fingerprint_mismatch",
                "marked_source_fingerprint": marked_source_fingerprint,
                "expected_source_fingerprint": expected_source_fingerprint,
            }
    result = {"usable": True, "reason": "verified", "sha256": observed, "dev_url": marked_url}
    if expected_source_fingerprint is not None:
        result["source_fingerprint"] = expected_source_fingerprint
    return result


def write_binary_provenance(
    binary: Path,
    dev_url: str,
    source_fingerprint: str | None = None,
) -> dict[str, Any]:
    payload = {"dev_url": dev_url, "sha256": sha256(binary), "recorded_utc": utc_now()}
    if source_fingerprint is not None:
        payload["source_fingerprint"] = source_fingerprint
    write_json(binary_provenance_path(binary), payload)
    return payload


def fetch_cdp_targets(cdp_port: int, timeout: float = 2.0) -> list:
    """Live target list from the CDP HTTP endpoint. Raises on transport failure."""
    raw = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=timeout).read()
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def classify_cdp_page_state(targets: list, vite_port: int) -> dict[str, Any]:
    needle = f":{vite_port}"
    pages = [t for t in targets if t.get("type") == "page"]
    ours = [t.get("url") or "" for t in pages if needle in (t.get("url") or "")]
    foreign = sorted({t.get("url") or "<untitled>" for t in pages if needle not in (t.get("url") or "")})
    return {
        "ok": bool(ours),
        "page_url": ours[0] if ours else None,
        "foreign_urls": foreign,
    }


def wait_for_isolated_page(
    cdp_port: int,
    vite_port: int,
    timeout: float,
    fetch=fetch_cdp_targets,
    sleep=time.sleep,
) -> dict[str, Any]:
    """Health-probe authority for the isolated CDP startup (plan P0.1 item 1).

    The environment variable being set proves nothing; this probe requires an
    ANSWERING endpoint on our isolated port AND a page target whose URL names
    OUR isolated dev-server port. Two distinct failure classifications:
      - cdp_endpoint_not_listening: browser args never applied / webview dead;
      - cdp_foreign_page_target: webview alive but serving someone else's page.
    """
    deadline = time.monotonic() + timeout
    endpoint_ever_up = False
    last_state = classify_cdp_page_state([], vite_port)
    while True:
        try:
            targets = fetch(cdp_port)
        except Exception:
            targets = None
        if targets is not None:
            endpoint_ever_up = True
            state = classify_cdp_page_state(targets, vite_port)
            if state["ok"]:
                state["endpoint_up"] = True
                return state
            last_state = state
        if time.monotonic() >= deadline:
            break
        sleep(min(0.5, max(timeout / 10.0, 0.05)))
    if not endpoint_ever_up:
        raise IsolatedStartupError(
            "cdp_endpoint_not_listening",
            f"no CDP endpoint answered on 127.0.0.1:{cdp_port} within {timeout:.0f}s: "
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS were not applied or the WebView2 "
            "browser process failed to start",
            {"cdp_port": cdp_port, "vite_port": vite_port},
        )
    raise IsolatedStartupError(
        "cdp_foreign_page_target",
        f"CDP endpoint {cdp_port} up but no page serves the isolated dev server "
        f"port {vite_port}; observed page URLs: {last_state['foreign_urls']}",
        {"cdp_port": cdp_port, "vite_port": vite_port, **last_state},
    )


def webview_command_line_evidence(cdp_port: int, user_data_folder: Path) -> dict[str, Any]:
    """Independent command-line confirmation of the applied WebView2 flags.

    Complements the health probe with the actual msedgewebview2.exe command
    lines: the debugging flag must be present together with OUR isolated
    user-data-dir, which also proves the hidden webview did not join the
    normal instance's browser process.
    """
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" | "
        "ForEach-Object { $_.CommandLine }"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    except Exception as exc:
        return {"confirmed": None, "error": f"command-line probe unavailable: {exc}"}
    flag = f"--remote-debugging-port={cdp_port}"
    udf = str(user_data_folder)
    matched = [
        line for line in lines
        if flag.lower() in line.lower() and udf.lower() in line.lower()
    ]
    return {
        "confirmed": bool(matched),
        "matched_process_count": len(matched),
        "flag": flag,
        "user_data_folder": udf,
        "sample_command_line": matched[0][:400] if matched else None,
        "observed_webview_process_count": len(lines),
    }


def _windows_process_table() -> list[dict[str, Any]]:
    """Return a small read-only process table for native-child resolution."""
    if os.name != "nt":
        return []
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        payload = json.loads(completed.stdout)
        rows = payload if isinstance(payload, list) else [payload]
        return [row for row in rows if isinstance(row, dict)]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def resolve_native_child_pid(launcher_pid: int, timeout: float = 180.0) -> int | None:
    """Resolve the real Tauri child below an npm/cargo dev launcher.

    ``tauri dev`` is a wrapper process. Monitoring its PID is insufficient:
    npm/cargo can remain alive after ``localcomet-desktop.exe`` exits. This
    resolver walks only descendants of the owned launcher PID and returns the
    exact native image PID. It never searches by image name globally.
    """
    if os.name != "nt":
        return int(launcher_pid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = _windows_process_table()
        by_parent: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            try:
                parent = int(row.get("ParentProcessId"))
                pid = int(row.get("ProcessId"))
            except (TypeError, ValueError):
                continue
            by_parent.setdefault(parent, []).append({**row, "ProcessId": pid})
        queue = [int(launcher_pid)]
        seen: set[int] = set()
        while queue:
            parent = queue.pop(0)
            if parent in seen:
                continue
            seen.add(parent)
            for row in by_parent.get(parent, []):
                pid = int(row["ProcessId"])
                name = str(row.get("Name") or "").casefold()
                if name == "localcomet-desktop.exe":
                    return pid
                queue.append(pid)
        if not any(int(row.get("ProcessId", -1)) == int(launcher_pid) for row in rows):
            return None
        time.sleep(0.5)
    return None


class NativeProcessMonitor:
    """Popen-compatible liveness view over the real native Tauri process."""

    def __init__(self, launcher: subprocess.Popen[Any], native_pid: int | None):
        self.launcher = launcher
        self.native_pid = int(native_pid) if native_pid is not None else None
        self.native_pid_resolved = self.native_pid is not None
        self.pid = self.native_pid if self.native_pid is not None else int(launcher.pid)

    def poll(self) -> int | None:
        if self.native_pid is None or self.native_pid == int(self.launcher.pid):
            return self.launcher.poll()
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, self.native_pid)
        if not handle:
            # The process handle is no longer queryable: fail closed as exited.
            return 1
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return 1
            return None if int(code.value) == STILL_ACTIVE else int(code.value)
        finally:
            kernel32.CloseHandle(handle)


def require_native_process_alive(process: Any, stage: str) -> None:
    """Fail closed when the native Tauri child dies while WebView2 remains reachable.

    A CDP page or UIA window is not native product evidence by itself: after a
    Tauri crash, the dev server and an orphaned WebView2 can still answer. The
    real native child must be resolved and alive at every startup boundary
    before any model setup or Computer Use interaction is attempted.
    """
    if getattr(process, "native_pid_resolved", True) is False:
        raise IsolatedStartupError(
            "native_process_unresolved",
            f"native Tauri child could not be resolved during {stage}",
            {"launcher_pid": getattr(process, "launcher", process).pid, "stage": stage},
        )
    returncode = process.poll()
    if returncode is not None:
        raise IsolatedStartupError(
            "native_process_exited",
            f"native Tauri process exited during {stage} with return code {returncode}",
            {"pid": process.pid, "returncode": returncode, "stage": stage},
        )


def verify_isolated_cdp_startup(report_dir: Path, timeout: float = 120.0) -> dict[str, Any]:
    """Full startup verification artifact; raises IsolatedStartupError."""
    udf_env = os.environ.get("LC_ISOLATED_WEBVIEW2_UDF", "").strip()
    user_data_folder = (
        Path(udf_env) if udf_env
        else Path(os.environ["LC_HIDDEN_ISOLATED_ROOT"]) / ISOLATED_WEBVIEW2_UDF_NAME
    )
    payload: dict[str, Any] = {
        "timestamp_utc": utc_now(),
        "cdp_port": ISOLATED_CDP_PORT,
        "vite_port": ISOLATED_VITE_PORT,
        "expected_dev_url": expected_isolated_dev_url(),
    }
    page = wait_for_isolated_page(ISOLATED_CDP_PORT, ISOLATED_VITE_PORT, timeout)
    payload.update(page)
    payload["command_line_evidence"] = webview_command_line_evidence(ISOLATED_CDP_PORT, user_data_folder)
    write_json(report_dir / "cdp_verification.json", payload)
    return payload


def launch_isolated_tauri(
    isolated_root: Path,
    report_dir: Path,
    cargo_target_dir: Path | None = None,
    cargo_subkey: str | None = None,
    enable_pending_hook: bool = False,
) -> tuple[subprocess.Popen[Any], bool, wintypes.HANDLE, str, list[int]]:
    from tools import launch_localcomet_dev as legacy

    source_root = legacy.source_root_from_launcher()
    legacy.validate_source_layout(source_root)
    paths = legacy.resolve_runtime_paths()
    paths.root.mkdir(parents=True, exist_ok=True)
    state, malformed_state = legacy.read_state(paths.state)
    package_lock_hash = legacy.sha256_file(source_root / "desktop/localcomet-desktop/package-lock.json")
    sync_summary, synced_files = legacy.synchronize_runtime(source_root, paths, state)
    state["synced_files"] = synced_files
    legacy.save_state(paths.state, state)
    resource_summary, resource_fingerprint, resource_files = legacy.prepare_tauri_resources(source_root, paths, state)
    state["runtime_resource_fingerprint"] = resource_fingerprint
    state["runtime_resource_files"] = resource_files
    legacy.save_state(paths.state, state)
    legacy.validate_sidecar_layout(paths.workspace)
    runtime_app_dir = paths.workspace / "desktop" / "localcomet-desktop"
    legacy.patch_runtime_vite_config(runtime_app_dir / "vite.config.ts")
    node_modules = runtime_app_dir / "node_modules"
    dependency = legacy.dependency_action(state, package_lock_hash, node_modules)
    if dependency == "INSTALLED":
        legacy.run_npm_ci(runtime_app_dir, paths.state, state, package_lock_hash)
    env = legacy.build_launch_environment(source_root, paths)
    port_patched = patch_isolated_workspace_port(isolated_root, ISOLATED_VITE_PORT)
    if not port_patched:
        raise RuntimeError("isolated runtime workspace was not ready for port patch")
    write_json(report_dir / "isolated_prepare.json", {
        "timestamp_utc": utc_now(),
        "source_root": str(source_root),
        "runtime_root": str(paths.root),
        "sync_summary": sync_summary.as_dict(),
        "resource_summary": resource_summary.as_dict(),
        "malformed_state": malformed_state,
        "dependency": dependency,
        "port": ISOLATED_VITE_PORT,
        "port_patched": port_patched,
    })
    npm = legacy.resolve_npm_executable()
    # Fail fast on leftovers from a previous isolated run: silently reusing a
    # stale dev server or a stale CDP endpoint poisons the whole run.
    for port in (ISOLATED_VITE_PORT, ISOLATED_CDP_PORT):
        try:
            import socket as _socket

            with _socket.create_connection(("127.0.0.1", port), timeout=0.5):
                raise RuntimeError(
                    f"port {port} is already in use; stop leftovers from the previous isolated run first"
                )
        except OSError:
            pass
    # The compiled-binary path owns Vite directly. The Tauri-dev path must
    # not start Vite here because Tauri's beforeDevCommand owns that server;
    # starting both creates a strictPort collision before UIA/CDP can start.
    # Hidden runs are deliberately serialized by this workflow: use one
    # stable target under the ONE external BuildCache base. Isolation comes
    # from the copied workspace, LOCALAPPDATA, hidden desktop, ports and UDF;
    # duplicating 6вЂ“7 GB of Rust objects per root is not isolation and can
    # exhaust C:. Never use a root-specific target key here.
    if cargo_target_dir is None:
        cargo_subkey = cargo_subkey or HIDDEN_CARGO_TARGET_SUBKEY
        cargo_target_dir = resolve_hidden_cargo_target(
            ROOT, os.environ.get("LC_HIDDEN_CANONICAL_LOCALAPPDATA", "")
        )
    elif not cargo_subkey:
        cargo_subkey = HIDDEN_CARGO_TARGET_SUBKEY
    cargo_target_dir = Path(cargo_target_dir)
    cargo_target_dir.mkdir(parents=True, exist_ok=True)
    env["CARGO_TARGET_DIR"] = str(cargo_target_dir)
    binary = cargo_target_dir / "debug" / "localcomet-desktop.exe"
    # Expose the WebView2 DevTools protocol (CDP) for the isolated run so the
    # drawer diagnosis can read the page console and DOM directly. Loopback
    # only, test affordance for the isolated lifetime of the app.
    # Hidden/non-interactive desktops can crash WebView2's GPU compositor
    # after Rust setup has already succeeded. Keep this mitigation scoped to
    # the isolated evidence harness; production retains its normal GPU path.
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--disable-gpu --remote-debugging-port={ISOLATED_CDP_PORT}"
    # Pin an explicit user-data-dir INSIDE the isolated root. wry passes an
    # empty data directory to the WebView2 loader, so the loader resolves the
    # default from the environment; without this pin the hidden webview could
    # share (and therefore JOIN) the normal instance's browser process, which
    # silently ignores our debugging arguments. A distinct UDF guarantees a
    # fresh browser process that actually carries --remote-debugging-port.
    webview_udf = isolated_root / ISOLATED_WEBVIEW2_UDF_NAME
    webview_udf.mkdir(parents=True, exist_ok=True)
    os.environ["LC_ISOLATED_WEBVIEW2_UDF"] = str(webview_udf)
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(webview_udf)
    # Hidden-desktop binding for the CU broker: the app must spawn every GUI
    # child onto winsta0\<desktop>, never the interactive one.
    hidden_desktop = os.environ.get("LC_HIDDEN_DESKTOP_NAME", "").strip()
    if hidden_desktop:
        env["LC_HIDDEN_DESKTOP_NAME"] = hidden_desktop
        # Hidden evidence runs must not ask Tauri/WebView2 to show a top-level
        # native window on a noninteractive desktop. This is harness-only: the
        # normal production launch environment keeps its existing visibility
        # behavior, while CDP/UIA can still observe the isolated webview here.
        env["LOCALCOMET_INVISIBLE"] = "1"
        browser_profile = hidden_browser_profile_path(isolated_root)
        browser_profile.mkdir(parents=True, exist_ok=True)
        env["LC_HIDDEN_BROWSER_PROFILE_DIR"] = str(browser_profile)
        env["LC_HIDDEN_BROWSER_CDP_PORT"] = str(ISOLATED_BROWSER_CDP_PORT)
        env["LC_HIDDEN_SCREENSHOT_OWNER_CONTEXT"] = str(report_dir / "screenshot_owner_context.json")
    # One-line tool-failure tracing lands next to the other run artifacts.
    env["LOCALCOMET_TOOLCALL_TRACE"] = str(report_dir / "toolcall_trace.log")
    env["LOCALCOMET_APPROVAL_TRACE"] = "1"
    env["LOCALCOMET_CU_DEBUG_PATH"] = str(report_dir / "cu_debug.jsonl")
    # Owner-scoped lifecycle lease: both direct children are assigned at
    # birth; closing this handle in run_worker's finally terminates exactly
    # our tree (kernel-enforced even on crash), never a foreign process.
    cleanup_job = create_cleanup_job()
    app_log = (report_dir / "tauri_app.log").open("ab")
    expected_dev_url = expected_isolated_dev_url()
    rust_source_fingerprint = rust_build_input_fingerprint(source_root)
    provenance = evaluate_binary_provenance(binary, expected_dev_url, rust_source_fingerprint)
    if enable_pending_hook:
        # The diagnostic feature must never reuse a default-profile binary from
        # the shared target cache. Force the Tauri dev build below so the binary
        # actually contains the isolated hook, while normal runs retain reuse.
        provenance = {**provenance, "usable": False, "reason": "cancellation_probe_forces_feature_build"}
    if os.environ.get("LC_RESTART_PHASE", "") in {"1", "2"}:
        # Application-boundary recovery must execute the commands compiled from
        # THIS source tree. Never reuse a cached binary that predates recovery
        # command registration, even when its old provenance marker is valid.
        provenance = {**provenance, "usable": False, "reason": "restart_probe_forces_fresh_tauri_build"}
    owned_root_pids: list[int] = []
    if provenance["usable"]:
        # The prebuilt binary is byte-verified against THIS run's dev URL and
        # does not run beforeDevCommand: this branch owns Vite and waits for
        # the patched port before spawning the app.
        vite_log = (report_dir / "vite_dev.log").open("ab")
        vite = subprocess.Popen([npm, "run", "dev"], cwd=runtime_app_dir, env=env, shell=False, stdout=vite_log, stderr=subprocess.STDOUT)
        assign_to_cleanup_job(cleanup_job, vite.pid)
        if not _wait_for_port(ISOLATED_VITE_PORT, 180.0):
            raise RuntimeError("isolated vite dev server did not start listening")
        process = subprocess.Popen([str(binary)], cwd=runtime_app_dir, env=env, shell=False, stdout=app_log, stderr=subprocess.STDOUT)
        assign_to_cleanup_job(cleanup_job, process.pid)
        launch_mode = "compiled_binary_with_isolated_dev_server"
        vite_pid = vite.pid
        owned_root_pids.extend([vite.pid, process.pid])
    else:
        # Fail closed into a rebuild instead of blind reuse: Tauri's dev path
        # rebuilds against the PATCHED workspace config (devUrl 127.0.0.1:<port>),
        # owns the single Vite server via beforeDevCommand, and overwrites the
        # stale binary in our private cargo target dir.
        launch_mode = "tauri_dev_rebuild_after_stale_binary" if binary.is_file() else "tauri_dev_with_tauri_managed_vite"
        tauri_command = [npm, "run", "tauri", "--", "dev"]
        if enable_pending_hook:
            tauri_command.extend(["--features", "isolated-cu-test-hook"])
        process = subprocess.Popen(tauri_command, cwd=runtime_app_dir, env=env, shell=False, stdout=app_log, stderr=subprocess.STDOUT)
        assign_to_cleanup_job(cleanup_job, process.pid)
        owned_root_pids.append(process.pid)
        vite_pid = None
    launcher_pid = int(process.pid)
    native_pid = launcher_pid if launch_mode == "compiled_binary_with_isolated_dev_server" else resolve_native_child_pid(launcher_pid)
    native_process = NativeProcessMonitor(process, native_pid)
    write_json(report_dir / "isolated_processes.json", {
        "timestamp_utc": utc_now(),
        "vite_pid": vite_pid,
        "vite_managed_by_tauri": vite_pid is None,
        "tauri_pid": native_process.pid,
        "launcher_pid": launcher_pid,
        "native_pid": native_process.native_pid,
        "binary": str(binary),
        "binary_preexisting": binary.is_file(),
        "binary_provenance": provenance,
        "expected_dev_url": expected_dev_url,
        "rust_source_fingerprint": rust_source_fingerprint,
        "launch_mode": launch_mode,
        "pending_hook_feature": bool(enable_pending_hook),
        "cdp_port": ISOLATED_CDP_PORT,
        "cargo_target_dir": str(cargo_target_dir),
        "cargo_target_evidence": legacy.cargo_target_evidence(cargo_target_dir, "isolated", subkey=cargo_subkey),
        "legacy_source_local_target_used": False,
        "cargo_exe": _cargo_identity(),
        "webview_user_data_folder": str(webview_udf),
        "cleanup_job_owner_pid": os.getpid(),
    })
    return native_process, port_patched, cleanup_job, expected_dev_url, owned_root_pids


def cleanup_owned_process_tree(root_pids: list[int]) -> dict[str, Any]:
    """Terminate only the roots owned by this isolated run and their trees.

    WebView2/Chromium may silently break away from the worker job when
    ``JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`` is enabled. The job remains the
    primary crash-safety boundary, but it cannot clean up escaped descendants.
    ``taskkill /T`` is therefore the bounded normal-exit cleanup fallback; it
    receives only PIDs recorded from this run and never searches by image name
    or kills unrelated/user processes.
    """
    results: list[dict[str, Any]] = []
    if os.name != "nt":
        return {"root_pids": root_pids, "results": results, "skipped": "windows_only"}
    for pid in dict.fromkeys(int(value) for value in root_pids if int(value) > 0):
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            results.append({
                "pid": pid,
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[-400:],
                "stderr": (completed.stderr or "")[-400:],
            })
        except Exception as exc:
            results.append({"pid": pid, "error": f"{type(exc).__name__}: {exc}"})
    return {"root_pids": root_pids, "results": results}


def _descendant_pids(root_pids: set[int]) -> set[int]:
    """All pids whose parent chain reaches one of root_pids (plus roots)."""
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    entries: dict[int, int] = {}
    if snap and snap != wintypes.HANDLE(-1):
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    entries[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                    if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)
    allowed = set(root_pids)
    changed = True
    while changed:
        changed = False
        for pid, parent in entries.items():
            if pid not in allowed and parent in allowed:
                allowed.add(pid)
                changed = True
    allowed.add(0)
    allowed.add(4)
    return allowed


def isolation_selfcheck(report_dir: Path, launcher_pid: int) -> bool:
    """Prove the worker desktop is isolated before any interaction.

    EnumWindows on this thread enumerates ONLY windows of the desktop the
    thread was born on. If any top-level window on that desktop belongs to a
    process outside our launch tree, isolation is lost and the run must stop
    (master prompt: any isolation loss halts the campaign immediately).
    """
    windows: list[dict[str, Any]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        klass = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, klass, 256)
        windows.append({
            "hwnd": hwnd,
            "pid": int(pid.value),
            "title": title.value,
            "class": klass.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
        })
        return True

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(enum_proc(callback), 0)
    allowed = _descendant_pids({os.getpid(), launcher_pid})
    background_classes = {
        # Window-manager background classes present on any fresh desktop.
        "Desktop", "ToolbarWindow32", "SysListView32", "Progman", "Button",
    }
    benign_invisible_external_classes = {
        # Windows creates these invisible shared infrastructure windows on a
        # fresh desktop. They are not application UI and are safe only while
        # invisible; unknown or visible external windows remain violations.
        "GDI+ Hook Window Class", "IME", "Default IME",
    }
    benign_external = lambda window: (
        not window["visible"]
        and (
            window["class"] in benign_invisible_external_classes
            or window["class"].startswith(".NET-BroadcastEventWindow.")
        )
    )
    violations = [
        w for w in windows
        if w["pid"] not in allowed
        and w["class"] not in background_classes
        and not benign_external(w)
    ]
    payload = {
        "timestamp_utc": utc_now(),
        "worker_pid": os.getpid(),
        "launcher_pid": launcher_pid,
        "allowed_pid_count": len(allowed),
        "window_count": len(windows),
        "windows": windows[:80],
        "violations": violations,
        "benign_invisible_external_windows": [w for w in windows if w["pid"] not in allowed and benign_external(w)],
        "isolated": not violations,
    }
    write_json(report_dir / "isolation_selfcheck.json", payload)
    return payload["isolated"]


async def _cdp_call(ws, msg_id: int, method: str, params: dict | None, events: list, timeout: float = 10.0):
    import asyncio as _asyncio

    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = await _asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
        except _asyncio.TimeoutError:
            return None
        data = json.loads(raw)
        if data.get("id") == msg_id:
            return data
        events.append(data)
    return None


async def _cdp_evaluate(ws, counter: list, events: list, expression: str, timeout: float = 10.0):
    counter[0] += 1
    reply = await _cdp_call(ws, counter[0], "Runtime.evaluate", {"expression": expression, "returnByValue": True}, events, timeout)
    if not reply:
        return {"__error": "timeout"}
    body = reply.get("result", {})
    if body.get("exceptionDetails"):
        details = body["exceptionDetails"]
        return {"__error": str(details.get("exception", {}).get("description") or details.get("text", "evaluation error"))[:600]}
    return body.get("result", {}).get("value")


def cdp_drawer_probe(report_dir: Path, auto, root_getter) -> dict:
    """Decisive drawer diagnosis over the WebView2 DevTools protocol.

    With a DOM click recorder installed, one UIA Invoke and one JS click are
    delivered to the same CTA: if the recorder sees the JS click but not the
    UIA one, the app is fine and the UIA<->WebView2 bridge drops the event;
    if neither registers (or handlers throw), the page itself is broken.
    Console/exception events observed during the probe are captured.
    """
    import asyncio
    import urllib.request

    import websockets

    try:
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{ISOLATED_CDP_PORT}/json", timeout=5))
    except Exception as exc:
        payload = {"ok": False, "error": f"cdp http failed: {exc}"}
        write_json(report_dir / "webview_probe.json", payload)
        return payload

    page = next((t for t in targets if t.get("type") == "page"), None)
    if page is None:
        payload = {"ok": False, "error": "no page target", "target_urls": [t.get("url") for t in targets][:6]}
        write_json(report_dir / "webview_probe.json", payload)
        return payload

    async def run() -> dict:
        events: list[str] = []
        out: dict[str, Any] = {"ok": True, "page_url": page.get("url")}
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024) as ws:
            counter = [0]
            await _cdp_call(ws, counter[0] + 1, "Runtime.enable", None, events)
            counter[0] += 1
            await _cdp_call(ws, counter[0] + 1, "Log.enable", None, events)
            counter[0] += 1
            out["page"] = await _cdp_evaluate(ws, counter, events, "({url: location.href, readyState: document.readyState, tauri: !!window.__TAURI_INTERNALS__})")
            out["cta"] = await _cdp_evaluate(ws, counter, events, "(() => { const els=[...document.querySelectorAll('button,[role=button],a')]; const m=els.filter(e=>((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).includes('Подобрать модель')); return m.map(e=>({tag:e.tagName, label:e.getAttribute('aria-label'), text:(e.textContent||'').trim().slice(0,60), disabled:e.disabled})); })()")
            await _cdp_evaluate(ws, counter, events, "window.__lcClicks=[]; window.addEventListener('click', e=>{ try { window.__lcClicks.push({t:Date.now(), tag:e.target.tagName, label:e.target.getAttribute('aria-label')||'', text:(e.target.textContent||'').trim().slice(0,40)}) } catch(_){} }, true); 'recorder-installed'")
            state_expr = "({clicks: (window.__lcClicks||[]).length, clickLog: (window.__lcClicks||[]).slice(-6), dialogNodes: document.querySelectorAll('[role=dialog],dialog').length, hasDrawerText: document.body.innerText.includes('Загрузить и подключить'), bodySnippet: document.body.innerText.slice(0,200)})"
            # Phase 1: UIA Invoke on the CTA (same call path the smoke uses).
            root = root_getter()
            uia_clicked = click_named(root, ("Подобрать модель", "Настроить локальный AI", "Подключить модель")) if root is not None else None
            await asyncio.sleep(4)
            out["uia_click"] = {"clicked": uia_clicked}
            out["after_uia"] = await _cdp_evaluate(ws, counter, events, state_expr)
            # Phase 2: direct JS DOM click on the same CTA.
            out["js_click"] = await _cdp_evaluate(ws, counter, events, "(() => { const els=[...document.querySelectorAll('button,[role=button]')]; const m=els.find(e=>((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).includes('Подобрать модель')); if(!m) return 'cta-not-found'; m.click(); return 'js-clicked'; })()")
            await asyncio.sleep(4)
            out["after_js"] = await _cdp_evaluate(ws, counter, events, state_expr)
        interesting = []
        for event in events:
            method = event.get("method", "")
            if method in ("Runtime.consoleAPICalled", "Runtime.exceptionThrown", "Log.entryAdded"):
                interesting.append(event.get("params", {}))
        out["console_events"] = interesting[-40:]
        return out

    payload = {"timestamp_utc": utc_now(), "cdp_port": ISOLATED_CDP_PORT, **asyncio.run(run())}
    write_json(report_dir / "webview_probe.json", payload)
    return payload


class CdpDriver:
    """DOM-level driver over the WebView2 DevTools protocol.

    Diagnosis (webview_probe.json): the app is healthy and opens the drawer on
    a real DOM click, while UIA Invoke on a non-interactive desktop never
    reaches the WebView2 DOM. Driving clicks/typing through CDP keeps the run
    physical-input-free and confined to the isolated webview.

    Connection lifecycle contract (fixes campaign_1000_final stale-WebSocket
    root cause):
    - The socket lives on ONE dedicated event loop for the whole driver
      lifetime; it is never reused across loops.
    - timeout / disconnect / protocol error move the driver into an explicitly
      invalid socket state: the old connection is closed deterministically and
      no command is ever sent into a stale or half-open socket again.
    - Recovery re-resolves the page target from the live /json list, requires
      THIS run's isolated dev-server port in the page URL (fail-closed: no
      fallback to arbitrary page targets) and only then attaches a brand-new
      connection.
    - eval() retry budget is bounded by CDP_MAX_ATTEMPTS with a per-attempt
      timeout; exhaustion returns {"__error": ...} which callers MUST classify
      as an infrastructure error вЂ” reconnect failure can never become
      submitted/pass evidence.
    """

    CDP_MAX_ATTEMPTS = 2

    def __init__(self) -> None:
        self._loop = None
        self._conn = None
        self._counter = 0
        self._events: list = []
        self.target_url = ""
        self.last_error = ""
        self.last_submit_result = ""
        # Logical submit identity survives a transport-uncertain return so a
        # caller retry cannot create a second model turn. It is cleared only
        # after a definite click outcome or a definite pre-click failure.
        self._pending_submit: tuple[str, str] | None = None

    # -- socket lifecycle -------------------------------------------------

    def _ensure_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        return self._loop

    def _list_page_targets(self) -> list:
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{ISOLATED_CDP_PORT}/json", timeout=5))
        # Only the page served by THIS run's dev server is ours; stale tabs
        # from earlier app instances must never receive our commands.
        needle = f":{ISOLATED_VITE_PORT}"
        return [t for t in targets if t.get("type") == "page" and needle in (t.get("url") or "")]

    def _diagnose_targets(self) -> list[str]:
        """Best-effort observed page URLs for fail-closed error messages."""
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{ISOLATED_CDP_PORT}/json", timeout=3))
        except Exception:
            return []
        return sorted({t.get("url") or "<untitled>" for t in targets if t.get("type") == "page"})

    async def _aclose_conn(self, conn) -> None:
        try:
            await conn.close()
        except Exception:
            pass
        wait_closed = getattr(conn, "wait_closed", None)
        if callable(wait_closed):
            try:
                await wait_closed()
            except Exception:
                pass

    def _dispose_socket(self) -> None:
        """Deterministically close the current socket, if any.

        Safe outside the loop thread: exceptions are swallowed because the
        socket is being discarded anyway.
        """
        conn, self._conn = self._conn, None
        if conn is not None and self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.run_until_complete(self._aclose_conn(conn))
            except Exception:
                pass

    async def _establish(self):
        """Dispose any old socket, then attach to THIS run's isolated page.

        Page identity is re-verified against the live /json target list after
        every transport failure; a missing or non-isolated URL fails closed
        instead of silently attaching to some other page.
        """
        old_conn, self._conn = self._conn, None
        if old_conn is not None:
            await self._aclose_conn(old_conn)
        import websockets

        pages = self._list_page_targets()
        if not pages:
            observed = self._diagnose_targets()
            raise RuntimeError(
                f"cdp: no page target on isolated port {ISOLATED_VITE_PORT}; "
                f"observed page targets: {observed or '<endpoint unreachable or empty>'}"
            )
        page = pages[0]
        url = page.get("url") or ""
        if f":{ISOLATED_VITE_PORT}" not in url:
            raise RuntimeError(f"cdp: refusing non-isolated page {url!r} (expected :{ISOLATED_VITE_PORT})")
        conn = await websockets.connect(
            page["webSocketDebuggerUrl"],
            max_size=32 * 1024 * 1024,
            open_timeout=10,
            ping_interval=None,
        )
        self._conn = conn
        self.target_url = url
        return conn

    async def _evaluate(self, expression: str, timeout: float = 10.0, await_promise: bool = False):
        ws = self._conn
        if ws is None:
            ws = await self._establish()
        self._counter += 1
        message_id = self._counter
        await ws.send(json.dumps({"id": message_id, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True, "awaitPromise": await_promise}}))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Transport-level failure: raise so the caller disposes this
                # socket and reconnects instead of caching a dead one forever.
                raise TimeoutError("cdp recv timeout")
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            data = json.loads(raw)
            if data.get("id") == message_id:
                body = data.get("result", {})
                if body.get("exceptionDetails"):
                    details = body["exceptionDetails"]
                    return {"__error": "js: " + str(details.get("exception", {}).get("description") or details.get("text", "evaluation error"))[:500]}
                return body.get("result", {}).get("value")

    def eval(self, expression: str, timeout: float = 10.0, await_promise: bool = False):
        last_error = ""
        for _attempt in range(self.CDP_MAX_ATTEMPTS):
            try:
                return self._ensure_loop().run_until_complete(self._evaluate(expression, timeout, await_promise))
            except Exception as exc:
                last_error = f"cdp eval failed: {exc}"
                self.last_error = last_error
                # Terminal invalid state: close the possibly half-open socket
                # before any retry gets a brand-new connection.
                self._dispose_socket()
        return {"__error": last_error}

    def insert_text(self, text: str) -> bool:
        """Send text through the isolated page's CDP input domain.

        Runtime.evaluate property mutation is not a reliable input event for a
        controlled Svelte textarea in WebView2. CDP Input.insertText reaches the
        DOM as a browser input operation while remaining confined to this run's
        isolated page; the text is never persisted in harness diagnostics.
        """
        if self._conn is None:
            return False
        self._counter += 1
        reply = self._ensure_loop().run_until_complete(
            _cdp_call(
                self._conn,
                self._counter,
                "Input.insertText",
                {"text": text},
                self._events,
                timeout=10.0,
            )
        )
        insert_ok = bool(reply and "error" not in reply)
        current_length = self.eval(
            "(() => { const t=document.querySelector('#composer-draft'); return t ? (t.value||'').length : -1; })()"
        )
        if insert_ok and current_length == len(text):
            return True
        if current_length not in (0, -1):
            return False
        # WebView2 can ignore Input.insertText while a hidden page is between
        # reactive ticks. A bounded char-event fallback still uses the browser
        # input domain and is only attempted when no text reached the target.
        for char in text:
            self._counter += 1
            char_reply = self._ensure_loop().run_until_complete(
                _cdp_call(
                    self._conn,
                    self._counter,
                    "Input.dispatchKeyEvent",
                    {"type": "char", "text": char, "unmodifiedText": char, "key": char},
                    self._events,
                    timeout=10.0,
                )
            )
            if not char_reply or "error" in char_reply:
                return False
        final_length = self.eval(
            "(() => { const t=document.querySelector('#composer-draft'); return t ? (t.value||'').length : -1; })()"
        )
        return final_length == len(text)

    def click_texts(self, texts: tuple[str, ...]) -> str | None:
        found = json.dumps(texts, ensure_ascii=False)
        result = self.eval(
            "(() => { const wanted = " + found + ";"
            " const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);"
            " const els=[...document.querySelectorAll('button,[role=button],a')];"
            " for (const w of wanted) { const m = els.filter(e=>!e.disabled && visible(e) && (((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).trim().includes(w)));"
            # Hidden duplicates (closed drawers, alternate views) must not
            # steal the click: act on the FIRST visible match.
            " if (m.length) { m[0].click(); return w; } } return null; })()"
        )
        return result if isinstance(result, str) else None

    def dialog_open(self) -> bool:
        result = self.eval(
            "(() => { const d=document.querySelector('[role=dialog],dialog');"
            " return !!d && !!(d.offsetWidth || d.offsetHeight || d.getClientRects().length); })()"
        )
        return result is True

    def click_setup_action(self) -> str | None:
        """Click only the model setup action selected by stable product IDs.

        Text fallback intentionally excludes the navigation label ``Подобрать
        модель``: in the production shell that label can open the HF browser,
        which is not the managed-model setup transition. A missing or disabled
        stable action is returned as ``None`` and recorded by diagnostics.
        """
        result = self.eval(
            "(() => {"
            " const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);"
            " const primary=document.querySelector('[data-testid=\\\"managed-model-primary-action\\\"]');"
            " if(primary && !primary.disabled){ primary.click(); return 'managed-primary'; }"
            " const chat=document.querySelector('[data-testid=\\\"chat-setup-local-ai\\\"]');"
            " if(chat && !chat.disabled && visible(chat)){ chat.click(); return 'chat-setup'; }"
            " const wanted=['Настроить локальный AI','Подключить модель'];"
            " const els=[...document.querySelectorAll('button,[role=button]')];"
            " for(const w of wanted){ const match=els.find(e=>!e.disabled&&visible(e)&&(((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).trim().includes(w)));"
            " if(match){match.click();return 'text:'+w;} }"
            " return null; })()"
        )
        return result if isinstance(result, str) else None

    def setup_diagnostics(self) -> dict[str, Any]:
        result = self.eval(
            "(() => {"
            " const drawer=document.querySelector('[data-testid=\\\"model-setup-drawer\\\"]');"
            " const primary=[...document.querySelectorAll('[data-testid=\\\"managed-model-primary-action\\\"]')];"
            " const chat=document.querySelector('[data-testid=\\\"chat-setup-local-ai\\\"]');"
            " const region=document.querySelector('[data-testid=\\\"composer-region\\\"]');"
            " const ta=document.querySelector('[data-testid=\\\"composer-textarea\\\"],#composer-draft');"
            " return {url:location.href,readyState:document.readyState,chatWorkspace:!!document.querySelector('#chat-workspace'),"
            "drawer:!!drawer,drawerState:drawer?.getAttribute('data-managed-state')||'',"
            "primary:primary.map(e=>({disabled:!!e.disabled,text:(e.textContent||'').trim().slice(0,100)})),"
            "chatSetup:chat?{disabled:!!chat.disabled,text:(chat.textContent||'').trim().slice(0,100)}:null,"
            "region:region?.getAttribute('data-model-status')||null,textarea:ta?{disabled:!!ta.disabled,display:!!(ta.offsetWidth||ta.offsetHeight||ta.getClientRects().length)}:null,"
            "body:(document.body.innerText||'').slice(0,500)}; })()"
        )
        return result if isinstance(result, dict) else {"error": str(result)[:200]}

    def approval_evidence(self) -> dict[str, Any] | None:
        """Read the mounted consent modal before it is dismissed by a click."""
        return _json_object(self.eval(APPROVAL_EXPRESSION))

    def click_approval(self, texts: tuple[str, ...]) -> str | None:
        """Click only an enabled button inside the consent modal.

        The modal is already scoped by its generated approval-request attribute;
        do not require CSS layout visibility because a hidden desktop WebView can
        report zero client rects while still accepting the DOM click.
        """
        found = json.dumps(texts, ensure_ascii=False)
        result = self.eval(
            "(() => { const d=document.querySelector('[role=dialog][data-approval-request-id],[role=alertdialog][data-approval-request-id]'); if(!d) return null;"
            " const stable=d.querySelector('[data-testid=\\\"approval-confirm\\\"],[data-lc=\\\"approval-confirm\\\"]');"
            " if (stable && !stable.disabled) { stable.click(); return 'approval-confirm'; }"
            " const wanted = " + found + ";"
            " const els=[...d.querySelectorAll('button,[role=button]')];"
            " for (const w of wanted) { const m = els.filter(e=>!e.disabled && (((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).trim().includes(w)));"
            " if (m.length) { m[0].click(); return w; } } return null; })()"
        )
        return result if isinstance(result, str) else None

    def tool_card_count(self) -> int:
        result = self.eval("document.querySelectorAll('.tool-card[aria-label]').length")
        return int(result) if isinstance(result, (int, float)) else 0

    def install_cancel_trace(self) -> dict[str, Any]:
        """Install the page-local cancel watcher without touching Tauri invoke.

        The diagnostic continuation trace is written by the application itself
        (``recordContinuationTrace`` in modelGateway.ts) into
        ``window.__LOCALCOMET_CONTINUATION_TRACE``; the harness only reads that
        trace and clicks the real composer Stop control at the first successful
        continuation lease. The replay proof therefore belongs to the app, not
        to a harness-injected invoke wrapper. Monkey-patching ``T.invoke`` is
        impossible on Tauri 2.11.5 (the property is non-configurable), so the
        rewriting probe reports ``internals_invoke_writable`` from the internals
        object itself instead of attempting the dead assignment.
        ``__lcCancelTrace`` is kept as an always-empty array so ``cancel_trace()``
        and the existing flow observe a bounded, honest trace (the harness no
        longer records or scrubs anything itself).
        """
        result = self.eval(
            "(() => {"
            " const T=window.__TAURI_INTERNALS__; if(!T||typeof T.invoke!=='function') return {installed:false,reason:'tauri_internals_missing'};"
            " const internalsInvokeWritable=(()=>{try{const k='__lcRewriteProbe'+Date.now(); T[k]=1; const writable=delete T[k]; return writable;}catch(e){return false;}})();"
            " if(T.__lcCancelTraceInstalled) return {installed:true,already:true,internals_invoke_writable:internalsInvokeWritable};"
            " window.__lcCancelTrace=[]; window.__lcContinuationStopAttempt=null; window.__lcContinuationStopWatcher=null;"
            " const clickStopAfterLease=(requestId)=>{"
            "  if(window.__lcContinuationStopAttempt) return;"
            "  const button=[...document.querySelectorAll('[data-testid=\\\"send-button\\\"][data-send=\\\"submit\\\"]')].find(item=>item.getAttribute('data-composer-action')==='stop' || ((item.getAttribute('aria-label')||'')==='Остановить'));"
            "  if(!button || button.disabled){return;}"
            "  button.click(); if(window.__lcContinuationStopWatcher) clearInterval(window.__lcContinuationStopWatcher); window.__lcContinuationStopWatcher=null; window.__lcContinuationStopAttempt={clicked:true,trigger:'continuation_consume_leased'};"
            " };"
            " window.__lcContinuationStopWatcher=setInterval(()=>{"
            "  if(window.__lcContinuationStopAttempt) return;"
            "  const leased=(window.__LOCALCOMET_CONTINUATION_TRACE||[]).find(e=>e&&e.event==='continuation_consume_leased');"
            "  if(leased&&typeof leased.request_id==='string') clickStopAfterLease(leased.request_id);"
            " },25);"
            " T.__lcCancelTraceInstalled=true; return {installed:true,internals_invoke_writable:internalsInvokeWritable}; })()"
        )
        return result if isinstance(result, dict) else {"installed": False, "reason": "trace_install_invalid"}

    def cancel_trace(self) -> list[dict[str, Any]]:
        result = self.eval("window.__lcCancelTrace || []")
        return result if isinstance(result, list) else []

    def continuation_trace(self) -> list[dict[str, Any]]:
        result = self.eval("window.__LOCALCOMET_CONTINUATION_TRACE || []")
        return result if isinstance(result, list) else []

    def cancel_backend_probe(self, turn_id: str) -> dict[str, Any]:
        """Call the same Rust cancel command with a validated turn id."""
        if not re.fullmatch(r"[0-9a-f]{24}", str(turn_id or "")):
            return {"ok": False, "reason": "invalid_turn_id"}
        encoded = json.dumps(str(turn_id))
        return self.eval(
            "(async()=>{const T=window.__TAURI_INTERNALS__;if(!T||!T.invoke)return {ok:false,reason:'tauri_internals_missing'};"
            "try{const response=await T.invoke('model_turn_cancel',{requestId:" + encoded + "});return {ok:true,response};}"
            "catch(e){return {ok:false,error:(e&&typeof e==='object')?JSON.stringify(e):String(e)};}})()",
            timeout=8.0,
            await_promise=True,
        )

    def turn_status_probe(self, turn_id: str) -> dict[str, Any]:
        """Read authoritative Rust turn.status without changing state."""
        if not re.fullmatch(r"[0-9a-f]{24}", str(turn_id or "")):
            return {"ok": False, "reason": "invalid_turn_id"}
        encoded = json.dumps(str(turn_id))
        return self.eval(
            "(async()=>{const T=window.__TAURI_INTERNALS__;if(!T||!T.invoke)return {ok:false,reason:'tauri_internals_missing'};"
            "try{const response=await T.invoke('control_plane_get_turn_status',{turnId:" + encoded + "});return {ok:true,response};}"
            "catch(e){return {ok:false,error:(e&&typeof e==='object')?JSON.stringify(e):String(e)};}})()",
            timeout=8.0,
            await_promise=True,
        )

    def click_stop(self) -> dict[str, Any]:
        """Click only the mounted composer Stop control for this isolated page."""
        prior = self.eval("window.__lcContinuationStopAttempt || null")
        if isinstance(prior, dict) and prior.get("clicked") is True:
            return prior
        result = self.eval(
            "(() => {"
            " const region=document.querySelector('[data-testid=\\\"composer-region\\\"]');"
            " if(!region) return {clicked:false,reason:'composer_missing'};"
            " const all=[...region.querySelectorAll('[data-testid=\\\"send-button\\\"][data-send=\\\"submit\\\"]')];"
            " const button=all.find(item=>item.getAttribute('data-composer-action')==='stop' || ((item.getAttribute('aria-label')||'')==='Остановить'));"
            " if(!button) return {clicked:false,reason:'stop_not_mounted',buttons:all.map(item=>({action:item.getAttribute('data-composer-action'),aria:item.getAttribute('aria-label')||'',disabled:!!item.disabled}))};"
            " if(button.disabled) return {clicked:false,reason:'stop_disabled',buttons:all.map(item=>({action:item.getAttribute('data-composer-action'),aria:item.getAttribute('aria-label')||'',disabled:!!item.disabled}))};"
            " button.click(); return {clicked:true,action:button.getAttribute('data-composer-action'),aria:button.getAttribute('aria-label')||''};"
            "})()"
        )
        return result if isinstance(result, dict) else {"clicked": False, "reason": "stop_probe_invalid"}

    def click_in_dialog(self, texts: tuple[str, ...]) -> str | None:
        """Click a button inside the open drawer only (scoped, no page-wide
        text matches like the chat header's identically-named button)."""
        found = json.dumps(texts, ensure_ascii=False)
        result = self.eval(
            "(() => { const d=document.querySelector('[role=dialog],dialog'); if(!d) return null;"
            " const wanted = " + found + ";"
            " const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);"
            " const els=[...d.querySelectorAll('button,[role=button]')];"
            " for (const w of wanted) { const m = els.filter(e=>!e.disabled && visible(e) && (((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).trim().includes(w)));"
            " if (m.length) { m[0].click(); return w; } } return null; })()"
        )
        return result if isinstance(result, str) else None

    def composer_ready(self) -> bool:
        # Readiness means the composer exists and accepts input. Prefer stable
        # data attributes (P0-D.1) before falling back to locale text (AC-006).
        result = self.eval(
            "(() => {"
            " const byStable = document.querySelector('[data-testid=\"composer-textarea\"][data-composer=\"message\"]') || document.querySelector('#composer-draft');"
            " const tas = byStable ? [byStable] : [...document.querySelectorAll('textarea,input[type=text]')];"
            " const stableBtns=[...document.querySelectorAll('[data-testid=\"send-button\"][data-send=\"submit\"], [data-lc=\"composer-send\"]')].filter(b=>!b.closest('[aria-hidden=\"true\"]'));"
            " const textBtns=[...document.querySelectorAll('button')].filter(b=>((b.textContent||'')+' '+(b.getAttribute('aria-label')||'')).includes('Отправить'));"
            " const btns = stableBtns.length ? stableBtns : textBtns;"
            " const editReady = tas.some(t=>t && !t.disabled && t.offsetParent!==null);"
            " const stableRegion=document.querySelector('[data-testid=\"composer-region\"]');"
            " const regionReady = !stableRegion || stableRegion.getAttribute('data-model-status')==='ready';"
            " return {edit: editReady, send: btns.length>0, regionReady}; })()"
        )
        if not isinstance(result, dict):
            return False
        # A visible/enabled textarea and send button are insufficient when the
        # production composer explicitly reports model-not-ready. The stable
        # region marker is authoritative whenever it exists; legacy pages have
        # no marker and retain the compatibility default of ready.
        return bool(result.get("edit")) and bool(result.get("send")) and bool(result.get("regionReady"))

    def model_status_ready(self) -> bool:
        """UI-level readiness signal: prefer stable data attribute, fallback to locale text."""
        result = self.eval(
            "(() => {"
            " const stable=document.querySelector('[data-testid=\"composer-region\"]');"
            " if (stable && stable.getAttribute('data-model-status')==='ready') {"
            "   const taStable=[...document.querySelectorAll('textarea')].some(x=>!x.disabled);"
            "   if (taStable) return true;"
            " }"
            " const t=document.body.innerText||'';"
            " const ta=[...document.querySelectorAll('textarea')].some(x=>!x.disabled);"
            " return t.includes('\\u041c\\u043e\\u0434\\u0435\\u043b\\u044c: \\u0433\\u043e\\u0442\\u043e\\u0432\\u0430') && ta; })()"
        )
        return result is True

    def enable_computer_use_permissions(self) -> bool:
        """Opt-in isolated setup for a user-authorized CU smoke.

        The production default remains computerUse=false. This helper updates
        only this run's WebView localStorage and reloads the isolated page so
        shellStore reads the enabled permission before the prompt is submitted.
        """
        preferences = json.dumps({
            "theme": "system",
            "locale": "ru",
            "diagnosticsPanel": "closed",
            "agentPermissions": {
                "files": True,
                "shell": True,
                "tools": True,
                "computerUse": True,
                "internet": False,
            },
            "voiceMode": False,
            "ctxSizeOverride": None,
            "gpuLayersOverride": None,
            "computeMode": "gpu",
            "effort": "off",
        }, ensure_ascii=False)
        result = self.eval(
            "(() => { localStorage.setItem('localcomet.ui.preferences.v1', "
            + json.dumps(preferences, ensure_ascii=False)
            + "); location.reload(); return true; })()",
            timeout=10.0,
        )
        if result is not True:
            return False
        time.sleep(5)
        return self.eval(
            "(() => { try { const p=JSON.parse(localStorage.getItem('localcomet.ui.preferences.v1')||'{}');"
            " return !!(p.agentPermissions && p.agentPermissions.computerUse === true && p.agentPermissions.shell === true);"
            " } catch (_) { return false; } })()"
        ) is True

    def submit_prompt(self, text: str) -> bool:
        # Focus the production composer first; the actual text is delivered via
        # CDP Input.insertText so Svelte receives a browser-level input event.
        # P0-D.3/5: stable DOM identity and post-input send-enabled verification.
        # Reuse the token only for the same logical prompt after an uncertain
        # protocol return; a different prompt always receives a new identity.
        if self._pending_submit is not None and self._pending_submit[0] == text:
            token = self._pending_submit[1]
        else:
            token = f"lc-submit-{uuid.uuid4().hex}"
            self._pending_submit = (text, token)
        focus_result = self.eval(
            "(() => { const vis=t=>{const r=t.getBoundingClientRect();return r.width>0&&r.height>0};"
            " const stable=document.querySelector('[data-testid=\"composer-textarea\"][data-composer=\"message\"]');"
            " if (stable && !stable.disabled && vis(stable)) { stable.focus(); return document.activeElement===stable ? 'focused' : 'focus-failed'; }"
            " const tas=[...document.querySelectorAll('#composer-draft,textarea,input[type=text]')].filter(t=>!t.disabled&&vis(t));"
            " if (!tas.length) return 'no-composer'; const ta=tas.find(t=>t.id==='composer-draft')||tas[0]||tas[tas.length-1];"
            " ta.focus(); return document.activeElement===ta ? 'focused' : 'focus-failed'; })()",
            timeout=15.0,
        )
        if focus_result != "focused":
            self.last_submit_result = str(focus_result)[:200]
            self._pending_submit = None
            return False
        if not self.insert_text(text):
            self.last_submit_result = "input-failed"
            self._pending_submit = None
            return False
        # Svelte enables Send on the next reactive tick. Prefer stable data-send
        # attribute (P0-D.1) before locale fallback; verify same DOM target.
        result = self.eval(
            "(async () => { const tok=" + json.dumps(token) + ";"
            " window.__lcSubmitTokens=window.__lcSubmitTokens||{};"
            " const storageKey='localcomet.submit.'+tok;"
            " const stored=()=>{try{return sessionStorage.getItem(storageKey)}catch(_){return null}};"
            " if (window.__lcSubmitTokens[tok] || stored()) return 'already-submitted';"
            " const stableFind=()=>{ const els=[...document.querySelectorAll('[data-testid=\"send-button\"][data-send=\"submit\"], [data-lc=\"composer-send\"]')].filter(b=>!b.disabled); if(els.length) return els[0]; return null; };"
            " const textFind=()=>[...document.querySelectorAll('button')].find(b=>!b.disabled && ((b.textContent||'')+' '+(b.getAttribute('aria-label')||'')).trim().includes('Отправить'));"
            " const find=()=>stableFind() || textFind();"
            " const status=()=>JSON.stringify({stable: [...document.querySelectorAll('[data-testid=\"send-button\"]')].map(b=>({disabled:b.disabled,testid:b.getAttribute('data-testid'),send:b.getAttribute('data-send')})).slice(-3), buttons:[...document.querySelectorAll('button')].filter(b=>((b.textContent||'')+' '+(b.getAttribute('aria-label')||'')).includes('Отправить')).map(b=>({disabled:b.disabled,aria:b.getAttribute('aria-label')||'',title:b.getAttribute('title')||''})).slice(-5), taLen:(document.querySelector('[data-testid=\"composer-textarea\"]')||document.querySelector('#composer-draft')||{}).value?.length||-1});"
            " for (let i=0;i<30;i++){ const b=find(); if(b){ b.click(); window.__lcSubmitTokens[tok]=Date.now(); try{sessionStorage.setItem(storageKey,String(Date.now()))}catch(_){} return 'submitted'; } await new Promise(r=>setTimeout(r,100)); }"
            " return 'no-send:'+status(); })()",
            timeout=15.0,
            await_promise=True,
        )
        self.last_submit_result = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)[:500]
        if result in ("submitted", "already-submitted") or (isinstance(result, str) and result.startswith("no-send:")):
            self._pending_submit = None
        # A non-string result is normally the bounded CDP error object. Keep the
        # token so the next retry of the same prompt can prove/avoid a duplicate.
        return result in ("submitted", "already-submitted")

    def body_has(self, needle: str) -> bool:
        result = self.eval("document.body.innerText.includes(" + json.dumps(needle, ensure_ascii=False) + ")")
        return result is True

    def body_snippet(self, limit: int = 600) -> str:
        result = self.eval(f"document.body.innerText.slice(0,{limit})")
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)[:limit]

    def close(self) -> None:
        self._dispose_socket()
        if self._loop is not None:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None


PILL_EXPRESSION = (
    "JSON.stringify((()=>{const allCards=[...document.querySelectorAll('.tool-card')];"
    "const cards=allCards;const c=cards.length?cards[cards.length-1]:null;"
    "const p=c?.querySelector('.status-pill');"
    "const r=c?.querySelector('.cu-reason');"
    "const img=c?.querySelector('img.cu-img, img[src^=\\\"data:image\\\"]');"
    "const text=c?.textContent||'';"
    "const m=text.match(/\\{[^}]*\\}/);"
    "const d=c?.dataset||{};"
    "const findDataset=(key)=>{for(let i=cards.length-1;i>=0;i-=1){const value=cards[i]?.dataset?.[key]||'';if(value)return value;}return '';};"
    "const processCard=[...cards].reverse().find(card=>card?.dataset?.cuProcessPid);"
    "const browserCard=[...cards].reverse().find(card=>card?.dataset?.cuBrowserUrl||card?.dataset?.cuBrowserCdpPort);"
    "const screenshotCard=[...cards].reverse().find(card=>card?.dataset?.cuScreenshotSha256||card?.dataset?.cuScreenshotBytes);"
    "return {pill:p?(p.textContent||'').trim():null,"
    "reason:r?(r.textContent||'').trim().slice(0,200):'',"
    "action:m?m[0]:'',"
    "request_id:d.cuRequestId||'',action_id:d.cuActionId||'',"
    "approval_id:d.cuApprovalId||'',approval_call_id:d.cuApprovalCallId||'',"
    "input_digest:d.cuInputDigest||'',"
    "process_pid:processCard?.dataset?.cuProcessPid||'',"
    "process_request_id:processCard?.dataset?.cuRequestId||'',"
    "process_action_id:processCard?.dataset?.cuActionId||'',"
    "browser_url:browserCard?.dataset?.cuBrowserUrl||'',"
    "browser_cdp_port:browserCard?.dataset?.cuBrowserCdpPort||'',"
    "browser_request_id:browserCard?.dataset?.cuRequestId||'',"
    "browser_action_id:browserCard?.dataset?.cuActionId||'',"
    "screenshot_sha256:screenshotCard?.dataset?.cuScreenshotSha256||'',"
    "screenshot_backend:screenshotCard?.dataset?.cuScreenshotBackend||'',"
    "screenshot_scope:screenshotCard?.dataset?.cuScreenshotScope||'',"
    "screenshot_bytes:screenshotCard?.dataset?.cuScreenshotBytes||'',"
    "screenshot_capture_pid:screenshotCard?.dataset?.cuScreenshotCapturePid||'',"
    "status:d.cuStatus||'',verification:d.cuVerification||'',card_count:allCards.length,"
    "screenshot_present:!!(screenshotCard?.querySelector('img.cu-img, img[src^=\\\"data:image\\\"]')),"
    "screenshot_src_length:screenshotCard?.querySelector('img.cu-img, img[src^=\\\"data:image\\\"]')?.getAttribute('src')?.length||0,"
    "dataset_fallback_request_id:findDataset('cuRequestId'),"
    "dataset_fallback_action_id:findDataset('cuActionId')};})())"
)


def scoped_pill_expression(min_tool_cards: int = 0, lookback_cards: int = 1) -> str:
    """Scope evidence to cards mounted during the current turn.

    ``min_tool_cards`` is the minimum total card count required by the caller.
    ``lookback_cards`` retains the preceding cards that belong to a compound
    turn, so the terminal interaction card can be correlated with its exact
    host-launch PID/browser metadata. The default keeps the historical
    one-card behavior unchanged.
    """
    lookback = max(1, int(lookback_cards))
    start = max(0, int(min_tool_cards) - lookback)
    return PILL_EXPRESSION.replace(
        "const cards=allCards;",
        f"const cards=allCards.slice({start});",
        1,
    )


# ---------------------------------------------------------------------------
# Deterministic intent worker dispatch (--use-intent).
#
# The worker drives the REAL production command path through the app's own
# Tauri IPC bridge (window.__TAURI_INTERNALS__), never a parallel executor:
#   intent_compile -> request_approval (+ typed consent auto-resolve)
#   -> run_tool_call -> cu_broker hidden spawn -> truthful envelope.
# No Qwen tool emission is required; no Python host spawn exists here.
# ---------------------------------------------------------------------------

INTENT_DISPATCH_PROMPT = "Открой https://example.com в браузере"


def build_intent_dispatch_expression(prompt: str) -> str:
    """Deterministic JS evaluated inside the isolated WebView.

    Authority stays in Rust: every capability decision is a real Tauri
    command. The consent card emitted for the dangerous open_url action is
    resolved through the same public resolve_tool_approval command the user's
    Approve button uses вЂ” equivalent authority, deterministic driver.
    """
    payload = json.dumps(prompt, ensure_ascii=False)
    errfmt = (
        "(e && typeof e === 'object')"
        " ? ((e.code || e.message) ? String(e.code || '') + ':' + String(e.message || '') : JSON.stringify(e))"
        " : String(e)"
    )
    return (
        "(async () => {"
        " const T = window.__TAURI_INTERNALS__; if (!T || !T.invoke) return JSON.stringify({error:'no-tauri-internals'});"
        " const invoke = T.invoke;"
        " const rawText=" + payload + ";"
        " let plan;"
        " try { plan = await invoke('intent_compile', { rawText }); }"
        " catch (e) { return JSON.stringify({error:'intent_compile_rejected', detail:" + errfmt + "}); }"
        " const input = { action:'open_url', target: plan.target || 'chrome', url: plan.url };"
        " let unlisten = null;"
        " try {"
        "  const handler = T.transformCallback((evt) => {"
        "   try { const p = typeof evt === 'string' ? JSON.parse(evt) : (evt && evt.payload) || evt;"
        "    const rid = p && (p.request_id || p.requestId);"
        "    if (rid) invoke('resolve_tool_approval', { requestId: rid, decision: 'approve' });"
        "   } catch (_) {}"
        "  });"
        "  const eventId = await invoke('plugin:event|listen', { event: 'request_tool_approval', target: { kind: 'Any' }, handler });"
        "  unlisten = () => invoke('plugin:event|unlisten', { event: 'request_tool_approval', eventId }).catch(()=>{});"
        " } catch (_) {}"
        " let envelope;"
        " try { envelope = await invoke('request_approval', { tool: 'computer_use', input }); }"
        " catch (e) { if (unlisten) unlisten(); return JSON.stringify({error:'approval_denied', detail:" + errfmt + "}); }"
        " if (unlisten) unlisten();"
        " const bytes = new Uint8Array(12); crypto.getRandomValues(bytes);"
        " const requestId = Array.from(bytes, b => b.toString(16).padStart(2,'0')).join('');"
        " const b2 = new Uint8Array(16); crypto.getRandomValues(b2);"
        " const actionId = 'call_' + Array.from(b2, x => x.toString(16).padStart(2,'0')).join('');"
        " let result;"
        " try { result = await invoke('run_tool_call', { tool:'computer_use', input, token: envelope.token,"
        "  approvalId: envelope.approvalId, callId: envelope.callId, requestId, actionId }); }"
        " catch (e) { return JSON.stringify({error:'dispatch_failed', detail:" + errfmt + ", requestId}); }"
        " return JSON.stringify({ requestId, actionId,"
        "  intent_id: plan.intentId || plan.intent_id, plan_digest: plan.planDigest || plan.plan_digest,"
        "  source_text_hash: plan.sourceTextHash || plan.source_text_hash,"
        "  envelope: { approval_id: envelope.approvalId }, result });"
        "})()"
    )


def classify_intent_dispatch_result(parsed: dict[str, Any]) -> tuple[str, str]:
    """Map the dispatch payload onto honest outcome/classification pairs."""
    if not isinstance(parsed, dict):
        return ("MALFORMED_RESULT", "MALFORMED_RESULT")
    if parsed.get("error"):
        return ("BLOCKED_INTENT_ERROR", "VERIFIED_BLOCKED")
    result = parsed.get("result") or {}
    status = str(result.get("status") or "")
    continuation = ((result.get("execution") or {}).get("continuation") or {})
    has_grant_hash = bool(continuation.get("grant_ref")) or bool(parsed.get("envelope", {}).get("approval_id"))
    if status == "completed" and result.get("verification") == "verified":
        return ("COMPLETED_VERIFIED", "VERIFIED_SUCCESS")
    if status == "launch_pending":
        return ("LAUNCH_PENDING_OBSERVED", "PENDING_TERMINAL")
    if status in {"blocked", "failed"}:
        return (f"BROKER_{status.upper()}", "VERIFIED_FAILED" if status == "failed" else "VERIFIED_BLOCKED")
    if has_grant_hash:
        return ("UNKNOWN_ENVELOPE", "NOT_INDEPENDENTLY_VERIFIED")
    return ("NO_EVIDENCE", "NOT_INDEPENDENTLY_VERIFIED")


def _windows_process_ids(process_name: str) -> list[int]:
    """List current PIDs for one image for a bounded negative proof only."""
    if os.name != "nt" or not process_name or any(ch in process_name for ch in "'\";&|<>`"):
        return []
    script = (
        "@(Get-Process -Name " + json.dumps(process_name.removesuffix(".exe"))
        + " -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        raw = json.loads(result.stdout.strip() or "[]")
        values = raw if isinstance(raw, list) else ([raw] if isinstance(raw, int) else [])
        return sorted({int(value) for value in values if int(value) > 0})
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
        return []


def _windows_process_state(pid: int) -> dict[str, Any]:
    """Query one exact PID without image-name enumeration or termination."""
    if os.name != "nt" or pid <= 0:
        return {"pid": pid, "alive": False, "process_name": "", "window_title": ""}
    script = (
        "$p=Get-Process -Id "
        + str(int(pid))
        + " -ErrorAction SilentlyContinue;"
        "if($null -eq $p){ @{alive=$false;pid="
        + str(int(pid))
        + ";process_name='';window_title=''} | ConvertTo-Json -Compress }"
        "else { @{alive=$true;pid=$p.Id;process_name=$p.ProcessName;window_title=$p.MainWindowTitle} | ConvertTo-Json -Compress }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        parsed = json.loads(result.stdout.strip() or "{}")
        return parsed if isinstance(parsed, dict) else {"pid": pid, "alive": False}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"pid": pid, "alive": None, "process_name": "", "window_title": ""}


def _approval_dispatch_helpers() -> tuple[str, str]:
    errfmt = (
        "(e && typeof e === 'object')"
        " ? ((e.code || e.message) ? String(e.code || '') + ':' + String(e.message || '') : JSON.stringify(e))"
        " : String(e)"
    )
    setup = (
        " const T=window.__TAURI_INTERNALS__; if(!T||!T.invoke) return JSON.stringify({error:'no-tauri-internals'});"
        " const invoke=T.invoke; let unlisten=null;"
        " try {"
        "  const handler=T.transformCallback((evt)=>{try{const p=typeof evt==='string'?JSON.parse(evt):(evt&&evt.payload)||evt;const rid=p&&(p.request_id||p.requestId);if(rid)invoke('resolve_tool_approval',{requestId:rid,decision:'approve'});}catch(_) {}});"
        "  const eventId=await invoke('plugin:event|listen',{event:'request_tool_approval',target:{kind:'Any'},handler});"
        "  unlisten=()=>invoke('plugin:event|unlisten',{event:'request_tool_approval',eventId}).catch(()=>{});"
        " } catch(_) {}"
    )
    dispatch = (
        " const rid=()=>{const b=new Uint8Array(12);crypto.getRandomValues(b);return Array.from(b,x=>x.toString(16).padStart(2,'0')).join('')};"
        " const aid=()=>{const b=new Uint8Array(16);crypto.getRandomValues(b);return 'call_'+Array.from(b,x=>x.toString(16).padStart(2,'0')).join('')};"
        " async function dispatch(input){ const requestId=rid(),actionId=aid(); let env;"
        "  try{env=await invoke('request_approval',{tool:'computer_use',input});}catch(e){return {requestId,actionId,error:'approval_denied',detail:"+errfmt+"};}"
        "  try{const result=await invoke('run_tool_call',{tool:'computer_use',input,token:env.token,approvalId:env.approvalId,callId:env.callId,requestId,actionId});return {requestId,actionId,result};}"
        "  catch(e){return {requestId,actionId,error:'dispatch_failed',detail:"+errfmt+"};}"
        " }"
    )
    return setup, dispatch


def build_foreign_ownership_expression() -> str:
    """Open the broker-owned process and return before any close is attempted."""
    setup, dispatch = _approval_dispatch_helpers()
    return "(async () => {" + setup + dispatch + " const open=await dispatch({action:'open_app',target:'notepad'}); if(unlisten) unlisten(); return JSON.stringify({open}); })()"


def build_foreign_close_expression(parent_request_id: str) -> str:
    """Attempt wrong-parent close, then close only the recorded broker PID."""
    setup, dispatch = _approval_dispatch_helpers()
    parent = json.dumps(parent_request_id)
    return (
        "(async () => {" + setup + dispatch
        + " const foreignAttempt=await dispatch({action:'close_owned',target:'notepad',ownership_request_id:rid()});"
        + " const close=await dispatch({action:'close_owned',target:'notepad',ownership_request_id:" + parent + "});"
        + " if(unlisten) unlisten(); return JSON.stringify({foreignAttempt,close}); })()"
    )


def build_foreign_negative_close_expression() -> str:
    """Attempt only a random-parent close; never terminate the broker owner."""
    setup, dispatch = _approval_dispatch_helpers()
    return (
        "(async () => {" + setup + dispatch
        + " const foreignAttempt=await dispatch({action:'close_owned',target:'notepad',ownership_request_id:rid()});"
        + " if(unlisten) unlisten(); return JSON.stringify({foreignAttempt}); })()"
    )


def build_fake_approval_expression() -> str:
    """Show why a fake DOM approval cannot authorize a Tauri tool call."""
    return (
        "(async () => {"
        " const T=window.__TAURI_INTERNALS__; if(!T||!T.invoke) return JSON.stringify({error:'no-tauri-internals'});"
        " const invoke=T.invoke; const requestId='abcdef0123456789abcdef01'; const actionId='call_fake_dom_approval_01';"
        " const dialog=document.createElement('div'); dialog.setAttribute('role','dialog'); dialog.dataset.approvalRequestId='fake_dom_request';"
        " dialog.dataset.modelRequestId=requestId; dialog.dataset.modelActionId=actionId; dialog.innerHTML='<button data-testid=\"approval-confirm\">Подтвердить</button>';"
        " document.body.appendChild(dialog); const button=dialog.querySelector('button'); button.click();"
        " const input={action:'open_app',target:'notepad'}; let rejected=false; let detail='';"
        " try { await invoke('run_tool_call',{tool:'computer_use',input,token:'fake_dom_token',approvalId:'appr_fake_dom_00000000000000000000000000000000',callId:'call_fake_dom_00000000000000000000000000000000',requestId,actionId}); }"
        " catch(e) { rejected=true; detail=(e&&typeof e==='object')?JSON.stringify(e):String(e); }"
        " dialog.remove(); return JSON.stringify({fake_dom_present:true,fake_dom_button_clicked:true,rejected,detail,requestId,actionId});"
        "})()"
    )


APPROVAL_EXPRESSION = (
    "JSON.stringify((()=>{"
    "const ds=[...document.querySelectorAll('[role=dialog][data-approval-request-id],[role=alertdialog][data-approval-request-id]')];"
    "const d=ds.length?ds[ds.length-1]:null;"
    "return d?{approval_request_id:d.dataset.approvalRequestId||'',"
    "model_request_id:d.dataset.modelRequestId||'',model_action_id:d.dataset.modelActionId||''}:null;})())"
)


# ---------------------------------------------------------------------------
# Deterministic coding E2E dispatch (LC_USE_CODING=1).
#
# Drives the REAL production coding path through the app's own Tauri IPC:
#   set_workspace -> coding_start_approval -> coding_start
#   -> replay rejection -> tamper rejection -> compile-failure rollback
# No model, no scripted approvals beyond the typed one-time grant the same
# production command mints. Postconditions are verified independently by the
# Python worker reading fixture bytes and ledger files from disk.
# ---------------------------------------------------------------------------

CODING_FIXTURE_DIRNAME = "coding_fixture"
CODING_REL_PATH = "src/main.rs"
CODING_ORIGINAL_CONTENT = 'pub fn localcomet_e2e_marker() -> u32 {\n    42\n}\n'
CODING_NEW_CONTENT = (
    'pub fn localcomet_e2e_marker() -> u32 {\n'
    '    43\n'
    '}\n'
)
CODING_BROKEN_CONTENT = 'pub fn broken() -> u32 { undefined_ident_never_defined }\n'
def prepare_coding_fixture(isolated_root: Path) -> dict[str, Any]:
    """Create the isolated Rust fixture workspace on disk before dispatch."""
    fixture = Path(isolated_root) / CODING_FIXTURE_DIRNAME
    src_dir = fixture / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "main.rs"
    if not target.exists():
        target.write_text(CODING_ORIGINAL_CONTENT, encoding="utf-8", newline="\n")
    return {
        "workspace": str(fixture),
        "rel_path": CODING_REL_PATH,
        "original_sha256": __import__("hashlib").sha256(
            target.read_bytes()
        ).hexdigest(),
    }


def build_coding_dispatch_expression(workspace: str) -> str:
    """Deterministic JS: happy path + replay + tamper + compile-failure.

    All four stages run inside the isolated WebView against real Tauri
    commands; the one-time grant comes from the same production
    coding_start_approval command the UI uses.
    """
    payload = json.dumps(workspace)
    errfmt = (
        "(e && typeof e === 'object')"
        " ? ((e.code || e.message) ? String(e.code || '') + ':' + String(e.message || '') : JSON.stringify(e))"
        " : String(e)"
    )
    prologue = (
        "(async () => {"
        " const T = window.__TAURI_INTERNALS__; if (!T || !T.invoke) return JSON.stringify({error:'no-tauri-internals'});"
        " const invoke = T.invoke;"
        " const wsPath=" + payload + ";"
        " const relPath='src/main.rs';"
        " const stamp = Date.now().toString(36);"
        " async function sha256Hex(text){const b=new TextEncoder().encode(text);"
        "  const d=await crypto.subtle.digest('SHA-256',b);"
        "  return Array.from(new Uint8Array(d)).map(x=>x.toString(16).padStart(2,'0')).join('');}"
        # 1. Confirm the fixture workspace through the production command.
        " try { await invoke('set_workspace', { path: wsPath }); }"
        " catch (e) { return JSON.stringify({error:'set_workspace_rejected', detail:" + errfmt + "}); }"
        " const taskId='lcoding_'+stamp, patchId='patch_'+taskId, stepId='step_1';"
        " const newContent=" + json.dumps(CODING_NEW_CONTENT) + ";"
        " const contentSha = await sha256Hex(newContent);"
    )
    let_envelope = (
        " let envelope;"
        " try { envelope = await invoke('coding_start_approval', { descriptor:"
        "  { relPath, contentSha256: contentSha, taskId, patchId, stepId } }); }"
        " catch (e) { return JSON.stringify({error:'approval_denied', detail:" + errfmt + ", taskId}); }"
    )
    start_request = (
        " { sessionId:'', workspacePath: wsPath, relPath, newContent,"
        " taskId, patchId, stepId,"
        " token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId }"
    )
    happy = (
        let_envelope
        + " let result;"
        + " try { result = await invoke('coding_start', { request: " + start_request + " }); }"
        + " catch (e) { return JSON.stringify({error:'dispatch_failed', detail:" + errfmt + ", requestId: taskId}); }"
        + " let events=null;"
        + " try { events = await invoke('coding_events', { taskId }); } catch (_) {}"
        + " const out = { taskId, result, events };"
    )
    # 2. Replay of the consumed one-time token must be a typed rejection.
    replay = (
        " try { await invoke('coding_start', { request: " + start_request + " });"
        "  out.replay = { rejected:false }; }"
        " catch (e) { out.replay = { rejected:true, code:" + errfmt + " }; }"
    )
    # 3. Tampered body under an approval minted for the ORIGINAL digest.
    tamper = (
        " try {"
        "  const t2='ltamper_'+stamp, p2='patch_'+t2;"
        "  const env2 = await invoke('coding_start_approval', { descriptor:"
        "   { relPath, contentSha256: contentSha, taskId:t2, patchId:p2, stepId } });"
        "  const tampered='pub fn tampered() -> u32 { 7 }\\n';"
        "  await invoke('coding_start', { request: { sessionId:'', workspacePath: wsPath,"
        "   relPath, newContent: tampered, taskId:t2, patchId:p2, stepId,"
        "   token: env2.token, approvalId: env2.approvalId, callId: env2.callId } });"
        "  out.tamper = { rejected:false }; }"
        " catch (e) { out.tamper = { rejected:true, code:" + errfmt + " }; }"
    )
    # 4. Compile failure must FAIL and roll the file back to its preimage.
    rollback = (
        " try {"
        "  const t3='lbroken_'+stamp, p3='patch_'+t3;"
        "  const broken=" + json.dumps(CODING_BROKEN_CONTENT) + ";"
        "  const env3 = await invoke('coding_start_approval', { descriptor:"
        "   { relPath, contentSha256: await sha256Hex(broken), taskId:t3, patchId:p3, stepId } });"
        "  const res3 = await invoke('coding_start', { request: { sessionId:'', workspacePath: wsPath,"
        "   relPath, newContent: broken, taskId:t3, patchId:p3, stepId,"
        "   token: env3.token, approvalId: env3.approvalId, callId: env3.callId } });"
        "  out.compile_failure = { status: res3.status, reason: res3.reason,"
        "   error_diagnostics: res3.error_diagnostics }; }"
        " catch (e) { out.compile_failure = { status:'rejected', code:" + errfmt + " }; }"
    )
    return prologue + happy + replay + tamper + rollback + " return JSON.stringify(out); })()"


def build_restart_phase1_expression(workspace: str) -> str:
    """Persist a real approval boundary, then return before the guarded start.

    The parent terminates only this worker's recorded app tree after the
    nonterminal `awaiting_approval` ledger is observed; phase 2 relaunches
    against the same isolated LOCALAPPDATA. No ledger/state is synthesized by
    the harness and no approval token is written to evidence.
    """
    payload = json.dumps(workspace)
    content = json.dumps(CODING_NEW_CONTENT)
    return (
        "(async()=>{"
        "const T=window.__TAURI_INTERNALS__;if(!T||!T.invoke)return JSON.stringify({error:'no-tauri-internals'});"
        f"const wsPath={payload},relPath='src/main.rs',taskId='lrestart_'+Date.now().toString(36),patchId='patch_'+taskId,stepId='step_1',newContent={content};"
        "const err=e=>(e&&typeof e==='object')?JSON.stringify(e):String(e);"
        "const sha=async text=>{const d=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return Array.from(new Uint8Array(d)).map(x=>x.toString(16).padStart(2,'0')).join('')};"
        "try{await T.invoke('set_workspace',{path:wsPath});}catch(e){return JSON.stringify({error:'set_workspace_rejected',detail:err(e),taskId});}"
        "let envelope;try{envelope=await T.invoke('coding_start_approval',{descriptor:{relPath,contentSha256:await sha(newContent),taskId,patchId,stepId}});}catch(e){return JSON.stringify({taskId,phase_error:'approval_denied',detail:err(e)});}"
        "let lastEvents=null;try{lastEvents=await T.invoke('coding_events',{taskId});}catch(e){return JSON.stringify({taskId,phase_error:'events_unavailable',detail:err(e)});}"
        "const es=Array.isArray(lastEvents?.events)?lastEvents.events:[];"
        "return JSON.stringify({taskId,patchId,approvalIssued:Boolean(envelope&&envelope.token),startCalled:false,lastEvents,eventCount:es.length});})()"
    )


def build_restart_phase2_expression(task_id: str, workspace: str) -> str:
    """Confirm workspace, then read/recover one task after a real app relaunch."""
    encoded = json.dumps(task_id)
    workspace_encoded = json.dumps(workspace)
    return (
        "(async()=>{"
        "const T=window.__TAURI_INTERNALS__;if(!T||!T.invoke)return JSON.stringify({error:'no-tauri-internals'});"
        "const original=T.invoke.bind(T);let codingStarts=0;"
        "T.invoke=async(command,args)=>{if(command==='coding_start')codingStarts+=1;return original(command,args)};"
        f"const taskId={encoded},workspacePath={workspace_encoded},relPath='src/main.rs',patchId='patch_'+taskId,stepId='step_1',newContent={json.dumps(CODING_NEW_CONTENT)};let listed=null,recovered=null,replayApproval=null,error='';"
        "const sha=async text=>{const d=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return Array.from(new Uint8Array(d)).map(x=>x.toString(16).padStart(2,'0')).join('')};"
        "try{await original('set_workspace',{path:workspacePath});listed=await original('coding_list_tasks');recovered=await original('coding_recover_task',{taskId});}catch(e){error=(e&&typeof e==='object')?JSON.stringify(e):String(e)}"
        "try{await original('coding_start_approval',{descriptor:{relPath,contentSha256:await sha(newContent),taskId,patchId,stepId}});replayApproval={rejected:false};}catch(e){replayApproval={rejected:true,code:(e&&typeof e==='object')?JSON.stringify(e):String(e)}}"
        "await new Promise(r=>setTimeout(r,2500));"
        "return JSON.stringify({taskId,listed,recovered,replayApproval,codingStarts,error});})()"
    )


def classify_coding_result(
    parsed: dict[str, Any] | None, fixture_check: dict[str, Any]
) -> tuple[str, str]:
    """Map dispatch payload + independent Python postconditions onto verdicts.

    Rollback semantics: each task rolls back to ITS OWN preimage. The broken
    patch started from the happy-path content, so after its rollback the disk
    must hold that last-known-good content again — never the broken bytes.
    """
    if not isinstance(parsed, dict):
        return ("MALFORMED_RESULT", "MALFORMED_RESULT")
    if parsed.get("error"):
        return ("BLOCKED_CODING_ERROR", "VERIFIED_BLOCKED")
    result = parsed.get("result") or {}
    status = str(result.get("status") or "")
    negatives_ok = bool((parsed.get("replay") or {}).get("rejected")) and bool(
        (parsed.get("tamper") or {}).get("rejected")
    )
    rollback_ok = (
        str((parsed.get("compile_failure") or {}).get("status") or "") == "failed"
        and fixture_check.get("exists") is True
        and fixture_check.get("rollback_restored_own_preimage") is True
        and fixture_check.get("left_broken") is False
    )
    if status in {"completed", "compile_verified_only"} and fixture_check.get("content_matches_new"):
        if not negatives_ok:
            return ("SECURITY_NEGATIVE_REGRESSION", "VERIFIED_FAILED")
        if rollback_ok:
            return ("CODING_FLOW_VERIFIED", "VERIFIED_SUCCESS")
        return ("ROLLBACK_UNPROVEN", "NOT_INDEPENDENTLY_VERIFIED")
    if status == "failed":
        if rollback_ok:
            return ("COMPILE_FAILURE_ROLLED_BACK", "VERIFIED_SUCCESS")
        return ("BROKEN_CODING_FAILED", "VERIFIED_FAILED")
    if status == "blocked":
        return ("BROKER_BLOCKED", "VERIFIED_BLOCKED")
    return ("UNKNOWN_ENVELOPE", "NOT_INDEPENDENTLY_VERIFIED")


def verify_coding_fixture_on_disk(
    isolated_root: Path,
    original_sha256: str,
    new_content: str,
) -> dict[str, Any]:
    """Independent postcondition: read the REAL bytes back from the fixture.

    After the full flow the file must equal the ORIGINAL preimage again вЂ” the
    happy-path patch was applied then superseded by the broken-patch rollback;
    either way no silently-broken workspace may remain.
    """
    import hashlib

    target = Path(isolated_root) / CODING_FIXTURE_DIRNAME / "src" / "main.rs"
    if not target.is_file():
        return {"exists": False}
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    expected_new_sha256 = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
    return {
        "exists": True,
        "original_sha256": original_sha256,
        "expected_new_sha256": expected_new_sha256,
        "final_sha256": digest,
        "content_matches_new": text == new_content,
        # The broken patch has its own preimage: the happy-path new content.
        # Restoring the file to the original pre-happy bytes would be an
        # incorrect rollback assertion for this sequential fixture.
        "rollback_restored_own_preimage": text == new_content,
        "rollback_restored_original": digest == original_sha256,
        "left_broken": text == CODING_BROKEN_CONTENT,
    }


def _json_object(raw: Any) -> dict[str, Any] | None:
    """Decode Runtime.evaluate values, including JSON.stringify strings."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None
    return None


def _pill_evidence(driver, min_tool_cards: int = 0, lookback_cards: int = 1) -> dict[str, Any]:
    """Read the last mounted tool-card status, never a stale prior card."""
    fallback = {"pill": None, "reason": "", "action": "", "request_id": "", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": "", "process_pid": "", "process_request_id": "", "process_action_id": "", "browser_url": "", "browser_cdp_port": "", "browser_request_id": "", "browser_action_id": "", "screenshot_sha256": "", "screenshot_backend": "", "screenshot_scope": "", "screenshot_bytes": "", "screenshot_capture_pid": "", "status": "", "verification": "", "card_count": 0, "screenshot_present": False, "screenshot_src_length": 0}
    for _ in range(3):
        parsed = _json_object(driver.eval(scoped_pill_expression(min_tool_cards, lookback_cards)))
        has_identity = bool(parsed and parsed.get("request_id") and parsed.get("action_id"))
        # Return a real terminal pill even if its dataset lost correlation; the
        # later evidence validator must report that identity failure explicitly.
        if parsed and parsed.get("pill") and int(parsed.get("card_count") or 0) >= min_tool_cards:
            return parsed
        time.sleep(0.4)
    return fallback


def submit_prompt_with_card_baseline(driver: "CdpDriver", prompt: str) -> tuple[bool, int]:
    """Capture the current-turn card baseline before a fast UI submission.

    A direct read-only ``open_url`` turn can mount its ToolCallCard before the
    submit call returns. Capturing the baseline afterward would make the
    current turn disappear from scoped-card correlation.
    """
    baseline = driver.tool_card_count()
    return driver.submit_prompt(prompt), baseline


def cdp_wait_for_turn(
    driver: "CdpDriver",
    timeout: float,
    min_tool_cards: int = 0,
    native_process: subprocess.Popen[Any] | None = None,
    lookback_cards: int = 1,
    cancel_after_ms: int | None = None,
    cancel_after_continuation: bool = False,
) -> dict:
    """Wait for a submitted turn to finish, approving the consent card.

    Dangerous computer_use actions require the decision card; the harness
    approves through the same DOM channel a user click would use. Only the
    internal approval labels are considered вЂ” never browser/payment controls.
    """
    deadline = time.monotonic() + timeout
    started = time.monotonic()
    approvals = 0
    approval_prompt: dict[str, Any] | None = None
    snippets: list[str] = []
    cancel_probe: dict[str, Any] | None = None
    cancel_probe_until: float | None = None
    continuation_ready_since: float | None = None
    cancel_trace_installed: dict[str, Any] | None = None
    cancel_card_count_before: int | None = None
    if cancel_after_continuation:
        cancel_trace_installed = driver.install_cancel_trace()
    while time.monotonic() < deadline:
        if native_process is not None:
            try:
                require_native_process_alive(native_process, "turn_observation")
            except IsolatedStartupError as exc:
                return {
                    "state": "native_process_exited",
                    "approvals": approvals,
                    "approval_prompt": approval_prompt,
                    "snippets": snippets[-3:],
                    "cancel_probe": cancel_probe,
                    "native_process_error": exc.error_type,
                    "native_process_details": exc.details,
                }
        now = time.monotonic()
        cancel_eligible = False
        if cancel_after_continuation:
            turn_id = str((approval_prompt or {}).get("model_request_id") or "")
            continuation_facts = continuation_cancel_trace_verified(driver.continuation_trace(), turn_id)
            if continuation_facts.get("host_continuation_correlated") is True:
                continuation_ready_since = continuation_ready_since or now
            cancel_eligible = (
                continuation_ready_since is not None
                and cancel_after_ms is not None
                and (now - continuation_ready_since) * 1000 >= max(0, cancel_after_ms)
            )
        else:
            cancel_eligible = cancel_after_ms is not None and (now - started) * 1000 >= max(0, cancel_after_ms)
        if cancel_eligible and cancel_probe_until is None:
            cancel_probe_until = now + 8.0
            cancel_card_count_before = driver.tool_card_count()
            if cancel_trace_installed is None:
                cancel_trace_installed = driver.install_cancel_trace()
            prompt_before_stop = driver.approval_evidence()
            if prompt_before_stop:
                approval_prompt = prompt_before_stop
        if cancel_probe_until is not None and now <= cancel_probe_until and not (cancel_probe and cancel_probe.get("clicked") is True):
            cancel_probe = driver.click_stop()
            if cancel_probe.get("clicked") is True:
                cancel_probe["trace_install"] = cancel_trace_installed
                cancel_probe["card_count_before"] = cancel_card_count_before
                cancel_probe["turn_id"] = (approval_prompt or {}).get("model_request_id", "")
                cancel_probe["continuation_trace_before_cancel"] = driver.continuation_trace()
                cancel_probe.update(continuation_cancel_trace_verified(
                    cancel_probe["continuation_trace_before_cancel"],
                    str(cancel_probe.get("turn_id") or ""),
                ))
        if cancel_probe and cancel_probe.get("clicked") is True:
            trace = driver.cancel_trace()
            cancel_events = [event for event in trace if isinstance(event, dict) and event.get("command") == "model_turn_cancel"]
            turn_id = str(cancel_probe.get("turn_id") or (approval_prompt or {}).get("model_request_id") or "")
            if not cancel_events and turn_id and not cancel_probe.get("backend_probe"):
                cancel_probe["backend_probe"] = driver.cancel_backend_probe(turn_id)
            if turn_id and cancel_probe.get("backend_probe") and not cancel_probe.get("backend_status_probe"):
                backend_probe = cancel_probe.get("backend_probe") or {}
                backend_response = backend_probe.get("response") if isinstance(backend_probe, dict) else None
                if isinstance(backend_response, dict):
                    cancel_probe["backend_ack"] = backend_response.get("turn_id") == turn_id
                    cancel_probe["backend_state"] = backend_response.get("state")
                    cancel_probe["backend_acknowledged"] = cancel_probe.get("backend_ack") is True and backend_response.get("state") in {"Cancelling", "Cancelled"}
                cancel_probe["backend_status_probe"] = {"skipped": True, "reason": "model_turn_cancel acknowledgement is the authoritative status response"}
                cancel_probe["terminal_cancelled"] = isinstance(backend_response, dict) and backend_response.get("turn_id") == turn_id and backend_response.get("state") == "Cancelled" and backend_response.get("worker_alive") is False
            if cancel_events:
                cancel_event = cancel_events[-1]
                cancel_probe["backend_trace"] = cancel_event
                response = cancel_event.get("response") if isinstance(cancel_event, dict) else None
                cancel_probe["backend_ack"] = isinstance(response, dict) and bool(response.get("turn_id"))
                cancel_probe["backend_state"] = response.get("state") if isinstance(response, dict) else None
                cancel_probe["backend_acknowledged"] = isinstance(response, dict) and bool(response.get("turn_id")) and response.get("state") in {"Cancelling", "Cancelled"}
                cancel_probe["terminal_cancelled"] = isinstance(response, dict) and bool(response.get("turn_id")) and response.get("state") == "Cancelled" and response.get("worker_alive") is False
                cancel_probe["backend_cancel_error"] = cancel_event.get("error") if isinstance(cancel_event, dict) else None
            if now > cancel_probe_until:
                cancel_probe["continuation_trace_after_cancel"] = driver.continuation_trace()
                cancel_probe["invoke_trace_after_cancel"] = driver.cancel_trace()
                cancel_probe.update(continuation_cancel_trace_verified(
                    cancel_probe["continuation_trace_after_cancel"],
                    str(cancel_probe.get("turn_id") or ""),
                ))
                cancel_probe["card_count_after"] = driver.tool_card_count()
                cancel_probe["no_new_tool_cards"] = cancel_probe.get("card_count_after") == cancel_probe.get("card_count_before")
                cancel_probe["composer_ready_after"] = driver.composer_ready()
                cancel_probe["stop_control_gone"] = driver.eval("!document.querySelector('[data-testid=\\\"send-button\\\"][data-composer-action=\\\"stop\\\"], [aria-label=\\\"Остановить\\\"]')") is True
                if cancel_safe_state_verified(cancel_probe):
                    result = {"state": "terminal_cancelled", "approvals": approvals, "approval_prompt": approval_prompt, "snippets": snippets[-3:], "cancel_probe": cancel_probe}
                    result.update(_pill_evidence(driver, min_tool_cards, lookback_cards))
                    return result
                result = {"state": "cancel_terminal_timeout", "approvals": approvals, "approval_prompt": approval_prompt, "snippets": snippets[-3:], "cancel_probe": cancel_probe}
                result.update(_pill_evidence(driver, min_tool_cards, lookback_cards))
                return result

        prompt_evidence = driver.approval_evidence()
        if prompt_evidence:
            approval_prompt = prompt_evidence
        clicked = driver.click_approval(("РџРѕРґС‚РІРµСЂРґРёС‚СЊ", "РћРґРѕР±СЂРёС‚СЊ", "Р Р°Р·СЂРµС€РёС‚СЊ"))
        if clicked:
            approvals += 1
            time.sleep(1)
            continue

        # Svelte enables the composer while the assistant's tool card is still
        # executing.  Treating composer_ready as terminal here loses the real
        # approval/result envelope and produces a false NOT_INDEPENDENTLY_VERIFIED
        # row (the observed v3 screenshot smoke showed exactly this defect).
        evidence = _pill_evidence(driver, min_tool_cards, lookback_cards)
        pill = str(evidence.get("pill") or "").upper()
        if pill and pill != "WAITING":
            if cancel_probe and cancel_probe.get("clicked") is True and now <= (cancel_probe_until or now):
                time.sleep(0.5)
                continue
            result = {
                "state": "terminal",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:],
                "cancel_probe": cancel_probe,
                "continuation_trace": driver.continuation_trace(),
            }
            result.update(evidence)
            return result

        body = driver.body_snippet(1200)
        # If the submitted turn produces no new tool card while the composer is
        # already usable, finish as an honest no-tool turn instead of waiting
        # the full model timeout. This is especially important after a prior
        # successful open_app turn: stale cards must never hold the harness for
        # five minutes or be mistaken for the follow-up type action.
        if driver.composer_ready() and time.monotonic() - started >= NO_NEW_TOOL_GRACE_SECONDS and driver.tool_card_count() < min_tool_cards:
            if cancel_probe and cancel_probe.get("clicked") is True and now <= (cancel_probe_until or now):
                time.sleep(0.5)
                continue
            result = {
                "state": "composer_ready_no_new_tool",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:] + [body],
                "cancel_probe": cancel_probe,
            }
            result.update(evidence)
            return result
        # If no computer_use card appeared at all, allow a bounded honest
        # no-tool response rather than waiting the full timeout. Once the card
        # exists, only a non-WAITING pill can finish the observation.
        if driver.composer_ready() and time.monotonic() - started >= NO_NEW_TOOL_GRACE_SECONDS and "computer_use" not in body.lower():
            if cancel_probe and cancel_probe.get("clicked") is True and now <= (cancel_probe_until or now):
                time.sleep(0.5)
                continue
            result = {
                "state": "composer_ready_no_tool",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:] + [body],
                "cancel_probe": cancel_probe,
            }
            result.update(evidence)
            return result

        snippets.append(body[:300])
        time.sleep(2)
    result = {
        "state": "observation_timeout",
        "approvals": approvals,
        "approval_prompt": approval_prompt,
        "snippets": snippets[-3:],
        "cancel_probe": cancel_probe,
        "continuation_trace": driver.continuation_trace(),
    }
    result.update(_pill_evidence(driver, min_tool_cards, lookback_cards))
    return result


SCENARIO_EXPECTED_TEXT = {
    "notepad_open_type": "LocalComet isolated smoke test.",
    "notepad_recovery": "recovery-check.",
    "notepad_final_text": "isolated-final-check.",
}


SCENARIO_EXPECTED_PROCESS = {
    "notepad_open_type": ["notepad.exe"],
    "desktop_screenshot": ["notepad.exe"],
    "calculator_basic": ["calculatorapp.exe"],
    "file_explorer_open": ["explorer.exe"],
    "browser_youtube": ["chrome.exe", "msedge.exe", "firefox.exe"],
    "browser_readonly_search": ["chrome.exe", "msedge.exe", "firefox.exe"],
    "notepad_recovery": ["notepad.exe"],
    "notepad_final_text": ["notepad.exe"],
}


def _broker_process_present(
    image_names: list[str] | tuple[str, ...] | None,
    evidence: dict[str, Any] | None,
    observations: list[dict[str, Any]],
) -> bool:
    """Prove a process reported by the Rust broker is alive and correlated.

    Broker-spawned host processes are intentionally not descendants of the
    WebView/launcher tree. The Rust result card is the ownership authority for
    this path; the independent probe still checks exact PID liveness/image and
    that the process-specific request/action IDs occurred in this turn.
    """
    if not image_names or not isinstance(evidence, dict):
        return False
    try:
        pid = int(evidence.get("process_pid") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0 or evidence.get("status") not in {"verified", "completed"} or evidence.get("verification") != "verified":
        return False
    process_request_id = str(evidence.get("process_request_id") or "")
    process_action_id = str(evidence.get("process_action_id") or "")
    request_ids = {str(item.get("request_id") or "") for item in observations if isinstance(item, dict)}
    if not process_request_id or process_request_id not in request_ids:
        return False
    # The broker may allocate a nested continuation call id for the host
    # operation; it need not equal the outer model card action id. Keep the
    # schema/correlation check, but do not reject valid nested calls.
    if not process_action_id.startswith("call_") or len(process_action_id) < 12:
        return False
    state = _windows_process_state(pid)
    if state.get("alive") is not True:
        return False
    actual = str(state.get("process_name") or "").casefold()
    expected = {str(name).removesuffix(".exe").casefold() for name in image_names}
    return actual in expected


def _process_present(
    image_names: list[str] | tuple[str, ...] | None,
    owner_pids: list[int] | tuple[int, ...] | None = None,
    *,
    observed_pid: int | str | None = None,
) -> bool | None:
    """Prove an observed process belongs to this isolated run.

    A process image name is not an identity. The caller must provide the
    broker-reported PID and launcher roots; the PID must be a descendant of an
    owned root and ``tasklist`` must report one of the expected exact images for
    that PID. Missing ownership or PID evidence fails closed rather than
    accepting a similarly named user process.
    """
    if not image_names:
        return None  # scenario has no spawn expectation
    if os.name != "nt" or not owner_pids:
        return None
    try:
        pid = int(observed_pid) if observed_pid is not None else 0
        roots = {int(value) for value in owner_pids if int(value) > 0}
    except (TypeError, ValueError):
        return False
    if pid <= 0 or not roots:
        return False
    try:
        owned_pids = _descendant_pids(roots)
    except Exception:
        return None
    if pid not in owned_pids:
        return False
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception:
        return None
    expected = {str(name).casefold() for name in image_names}
    try:
        rows = csv.reader((completed.stdout or "").splitlines())
        for row in rows:
            if len(row) < 2:
                continue
            image = row[0].strip().casefold()
            reported_pid = row[1].strip()
            if reported_pid == str(pid) and image in expected:
                return True
    except (csv.Error, TypeError):
        return None
    return False


def _hidden_visible_window_pids() -> set[int]:
    """Enumerate visible top-level windows on the worker's current desktop only."""
    pids: set[int] = set()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                pids.add(int(pid.value))
        return True

    user32.EnumWindows(callback, 0)
    return pids


def _browser_expected_hosts(scenario_id: str) -> set[str]:
    if scenario_id == "browser_youtube":
        return {"youtube.com", "www.youtube.com"}
    if scenario_id == "browser_readonly_search":
        return {"python.org", "www.python.org", "docs.python.org", "peps.python.org"}
    if scenario_id == "browser_second_readonly_search":
        return {"learn.microsoft.com", "support.microsoft.com"}
    return set()


def _browser_target_matches(url: str, title: str, scenario_id: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port:
        return False
    if host not in _browser_expected_hosts(scenario_id):
        return False
    if not title.strip():
        return False
    if scenario_id == "browser_second_readonly_search":
        haystack = f"{url} {title}".casefold()
        if "notepad" not in haystack:
            return False
    return True


def browser_listener_identity(
    cdp_port: int,
    expected_pid: int,
    expected_profile_dir: Path | None,
) -> dict[str, Any]:
    """Bind a browser CDP endpoint to its exact owner PID and profile."""
    if os.name != "nt" or not (1024 <= cdp_port <= 65535) or expected_pid <= 0 or expected_profile_dir is None:
        return {"ok": False, "reason": "missing browser listener identity inputs"}
    profile = str(expected_profile_dir).casefold()
    if not profile:
        return {"ok": False, "reason": "missing isolated browser profile"}
    script = (
        "$port=" + str(int(cdp_port)) + "; $expectedPid=" + str(int(expected_pid)) + "; "
        "$listeners=@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | "
        "ForEach-Object {[int]$_.OwningProcess}); "
        "$process=@(Get-CimInstance Win32_Process -Filter ('ProcessId=' + $expectedPid) | "
        "ForEach-Object {[pscustomobject]@{ProcessId=[int]$_.ProcessId;Name=$_.Name;CommandLine=$_.CommandLine}}); "
        "[pscustomobject]@{listeners=$listeners;process=$process} | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return {"ok": False, "reason": "browser listener identity probe unavailable"}
        payload = json.loads(completed.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"ok": False, "reason": "browser listener identity probe failed"}
    listeners = payload.get("listeners") if isinstance(payload, dict) else []
    listeners = [int(value) for value in (listeners if isinstance(listeners, list) else [listeners]) if str(value).isdigit()]
    processes = payload.get("process") if isinstance(payload, dict) else []
    if isinstance(processes, dict):
        process = processes
    elif isinstance(processes, list) and processes and isinstance(processes[0], dict):
        process = processes[0]
    else:
        process = None
    command_line = str((process or {}).get("CommandLine") or "")
    image_name = str((process or {}).get("Name") or "").casefold()
    expected_flag = f"--remote-debugging-port={cdp_port}".casefold()
    checks = {
        "listener_owner_pid": listeners == [expected_pid],
        "process_pid": int((process or {}).get("ProcessId") or 0) == expected_pid,
        "browser_image": image_name in {"chrome.exe", "msedge.exe", "firefox.exe"},
        "debug_port_flag": expected_flag in command_line.casefold(),
        "isolated_profile": profile in command_line.casefold(),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "listener_pids": listeners,
        "pid": expected_pid,
        "profile": str(expected_profile_dir),
        "image": image_name,
        "command_line_present": bool(command_line),
        "reason": "" if all(checks.values()) else "browser CDP listener/process/profile identity mismatch",
    }


def browser_url_evidence(
    cdp_port: int,
    expected_pid: int,
    *,
    scenario_id: str,
    expected_profile_dir: Path | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Independently prove the scenario URL, title and owned hidden window.

    This reads the broker-owned browser CDP endpoint, never the WebView2
    endpoint. A browser process alone is insufficient: a matching HTTPS page,
    non-empty title and visible expected PID on the worker desktop are all
    required before returning ``ok=True``.
    """
    if not (1024 <= cdp_port <= 65535) or expected_pid <= 0:
        return {
            "ok": False,
            "reason": "missing broker browser pid or cdp port",
            "cdp_port": cdp_port,
            "pid": expected_pid,
            "scenario_id": scenario_id,
        }
    expected_hosts = _browser_expected_hosts(scenario_id)
    if not expected_hosts:
        return {"ok": False, "reason": "browser scenario has no approved host set", "scenario_id": scenario_id}
    endpoint = f"http://127.0.0.1:{cdp_port}/json/list"
    deadline = time.monotonic() + timeout
    last_error = "browser CDP page not ready"
    last_listener: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            listener = browser_listener_identity(cdp_port, expected_pid, expected_profile_dir)
            last_listener = dict(listener)
            if not listener.get("ok"):
                last_error = str(listener.get("reason") or "browser listener identity mismatch")
                time.sleep(0.5)
                continue
            with urllib.request.urlopen(endpoint, timeout=2.0) as response:
                targets = json.loads(response.read().decode("utf-8"))
            if not isinstance(targets, list):
                last_error = "browser CDP returned a non-list target payload"
            else:
                for target in targets:
                    if not isinstance(target, dict) or target.get("type") != "page":
                        continue
                    url = str(target.get("url") or "")
                    title = str(target.get("title") or "")
                    if not _browser_target_matches(url, title, scenario_id):
                        continue
                    parsed = urlparse(url)
                    host = (parsed.hostname or "").lower().rstrip(".")
                    hidden_window_pid = expected_pid in _hidden_visible_window_pids()
                    return {
                        "ok": hidden_window_pid,
                        "scenario_id": scenario_id,
                        "url": url,
                        "host": host,
                        "title": title,
                        "cdp_port": cdp_port,
                        "pid": expected_pid,
                                                    "hidden_window_pid": hidden_window_pid,
                            "listener_identity": listener,
                            "reason": "" if hidden_window_pid else "broker pid has no visible window on worker hidden desktop",

                    }
        except Exception as exc:
            last_error = f"browser CDP unavailable: {type(exc).__name__}"
        time.sleep(0.5)
    return {
        "ok": False,
        "reason": last_error,
        "cdp_port": cdp_port,
        "pid": expected_pid,
        "scenario_id": scenario_id,
        "listener_identity": last_listener,
    }


def browser_youtube_evidence(cdp_port: int, expected_pid: int, timeout: float = 20.0) -> dict[str, Any]:
    """Compatibility wrapper for the historical YouTube-only probe."""
    return browser_url_evidence(cdp_port, expected_pid, scenario_id="browser_youtube", timeout=timeout)


def _tool_card_evidence(driver, min_tool_cards: int = 0, lookback_cards: int = 1) -> dict[str, Any]:
    """UI-level truth from the last new tool card, with bounded CDP retries."""
    fallback = {"pill": None, "reason": "", "action": "", "request_id": "", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": "", "process_pid": "", "process_request_id": "", "process_action_id": "", "browser_url": "", "browser_cdp_port": "", "browser_request_id": "", "browser_action_id": "", "screenshot_sha256": "", "screenshot_backend": "", "screenshot_scope": "", "screenshot_bytes": "", "screenshot_capture_pid": "", "status": "", "verification": "", "card_count": 0, "screenshot_present": False, "screenshot_src_length": 0}
    for _ in range(4):
        parsed = _json_object(driver.eval(scoped_pill_expression(min_tool_cards, lookback_cards)))
        has_identity = bool(parsed and parsed.get("request_id") and parsed.get("action_id"))
        if parsed and parsed.get("pill") and int(parsed.get("card_count") or 0) >= min_tool_cards and (min_tool_cards <= 0 or has_identity):
            return parsed
        time.sleep(0.6)
    return fallback


def _valid_id(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(pattern, value))


def validate_correlation(
    observation: dict[str, Any],
    evidence: dict[str, Any],
    approvals: int,
    *,
    approval_required: bool = False,
    session_capability_required: bool = False,
    session_capability_ok: bool = False,
) -> dict[str, Any]:
    """Validate identities from mounted UI evidence; never synthesize missing IDs."""
    if approvals <= 0:
        if approval_required:
            return {
                "status": "required_but_absent",
                "ok": False,
                "checks": {"approval_observed": False},
            }
        if session_capability_required:
            checks = {
                "session_capability_granted": session_capability_ok,
                "model_request_id": _valid_id(evidence.get("request_id"), r"[0-9a-f]{24}"),
                "model_action_id": _valid_id(evidence.get("action_id"), r"[A-Za-z0-9_.:-]{1,128}"),
                "input_digest": _valid_id(evidence.get("input_digest"), r"[0-9a-f]{64}"),
            }
            return {
                "status": "session_capability_validated" if all(checks.values()) else "incomplete",
                "ok": all(checks.values()),
                "checks": checks,
            }
        return {"status": "not_required", "ok": True, "checks": {}}
    prompt = observation.get("approval_prompt") if isinstance(observation.get("approval_prompt"), dict) else {}
    checks = {
        "approval_observed": approvals > 0,
        "approval_prompt_request_id": _valid_id(prompt.get("approval_request_id"), r"appr_[0-9a-f]{32}"),
        "model_request_id": _valid_id(evidence.get("request_id"), r"[0-9a-f]{24}"),
        "model_action_id": _valid_id(evidence.get("action_id"), r"[A-Za-z0-9_.:-]{1,128}"),
        "approval_id": _valid_id(evidence.get("approval_id"), r"appr_[0-9a-f]{32}"),
        "approval_call_id": _valid_id(evidence.get("approval_call_id"), r"call_[0-9a-f]{32}"),
        "input_digest": _valid_id(evidence.get("input_digest"), r"[0-9a-f]{64}"),
    }
    checks["prompt_matches_model_request"] = bool(prompt.get("model_request_id")) and prompt.get("model_request_id") == evidence.get("request_id")
    checks["prompt_matches_model_action"] = bool(prompt.get("model_action_id")) and prompt.get("model_action_id") == evidence.get("action_id")
    return {"status": "validated" if all(checks.values()) else "incomplete", "ok": all(checks.values()), "checks": checks}


def materialize_rendered_screenshot(
    driver: Any,
    output_path: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    """Persist the rendered PNG from the current ToolCallCard and verify its hash."""
    expression = (
        "(()=>{const cards=[...document.querySelectorAll('.tool-card')];"
        "const card=[...cards].reverse().find(c=>c?.dataset?.cuScreenshotSha256);"
        "return card?.querySelector('img.cu-img, img[src^=\\\"data:image/png;base64,\\\"]')?.src||'';})()"
    )
    try:
        data_url = driver.eval(expression, timeout=15.0)
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": "rendered screenshot DOM read failed: " + type(exc).__name__}
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        return {"ok": False, "status": "error", "reason": "rendered screenshot PNG data URL missing"}
    encoded = data_url.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return {"ok": False, "status": "error", "reason": "rendered screenshot PNG base64 invalid"}
    digest = hashlib.sha256(raw).hexdigest()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or not raw or len(raw) > 8 * 1024 * 1024:
        return {"ok": False, "status": "error", "reason": "rendered screenshot PNG bytes invalid or oversized", "bytes": len(raw)}
    if not _valid_id(expected_sha256, r"[0-9a-f]{64}") or digest != expected_sha256:
        return {"ok": False, "status": "error", "reason": "rendered screenshot hash mismatch", "bytes": len(raw), "sha256": digest}
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw)
    except OSError:
        return {"ok": False, "status": "error", "reason": "rendered screenshot artifact write failed"}
    return {
        "ok": True,
        "status": "persisted",
        "path": str(output_path),
        "bytes": len(raw),
        "sha256": digest,
        "source": "rendered_tool_card_png",
    }


def validate_screenshot_evidence(
    evidence: dict[str, Any],
    *,
    expected_pid: int | str | None = None,
) -> dict[str, Any]:
    scope = evidence.get("screenshot_scope")
    checks = {
        "present": bool(evidence.get("screenshot_present")),
        "sha256": _valid_id(evidence.get("screenshot_sha256"), r"[0-9a-f]{64}"),
        "backend": evidence.get("screenshot_backend") in {"imagegrab", "gdi_bitblt", "printwindow"},
        "scope": scope in {"desktop", "window"},
        "bytes": str(evidence.get("screenshot_bytes") or "").isdigit() and int(evidence.get("screenshot_bytes") or 0) > 0,
    }
    if scope == "window":
        capture_pid = str(evidence.get("screenshot_capture_pid") or "")
        checks["capture_pid"] = capture_pid.isdigit() and int(capture_pid) > 0
        if expected_pid is not None:
            try:
                checks["capture_pid_matches_owner"] = checks["capture_pid"] and int(capture_pid) == int(expected_pid)
            except (TypeError, ValueError):
                checks["capture_pid_matches_owner"] = False
    return {"ok": all(checks.values()), "checks": checks}


def continuation_cancel_trace_verified(trace: Any, turn_id: str) -> dict[str, Any]:
    """Extract a bounded, secret-free proof that a leased continuation was revoked.

    The trace is produced inside the real WebView Tauri invoke wrapper. It is
    accepted only when the same model request leased a continuation, Rust
    returned a positive revoke count, and no observe/consume command followed
    that revoke. Raw grant/lease material is never accepted as evidence.
    """
    events = trace if isinstance(trace, list) else []
    normalized = [event for event in events if isinstance(event, dict)]
    consume_indexes: list[int] = []
    observe_indexes: list[int] = []
    revoke_indexes: list[int] = []
    replay_indexes: list[int] = []
    leased_consume = False
    revoked_positive = False
    replay_rejected = False
    replay_unexpected_success = False
    for index, event in enumerate(normalized):
        command = event.get("command")
        event_name = event.get("event")
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        response = event.get("response") if isinstance(event.get("response"), dict) else {}
        request_match = event.get("request_id") == turn_id or args.get("requestId") == turn_id
        if command == "cu_broker_continuation_consume" or event_name in {"continuation_consume_requested", "continuation_consume_leased", "continuation_consume_rejected", "continuation_consume_failed"}:
            consume_indexes.append(index)
            leased_consume = leased_consume or (
                event_name == "continuation_consume_leased"
                or (
                    request_match
                    and args.get("actionKind") == "observe"
                    and args.get("grantRef") == "<redacted:cgr>"
                    and response.get("status") == "leased"
                )
            )
        elif command == "cu_broker_observe" or event_name in {"continuation_observe_requested", "continuation_observe_result"}:
            observe_indexes.append(index)
        elif command == "cu_broker_continuation_revoke" or event_name in {"continuation_revoke_requested", "continuation_revoke_succeeded", "continuation_revoke_failed"}:
            revoke_indexes.append(index)
            if event_name == "continuation_revoke_succeeded":
                revoked_positive = isinstance(event.get("revoked"), int) and event.get("revoked", 0) > 0
            elif isinstance(response.get("revoked"), int) and response.get("revoked", 0) > 0:
                revoked_positive = True
        elif event_name in {"continuation_replay_rejected", "continuation_replay_unexpected_success"}:
            replay_indexes.append(index)
            replay_rejected = replay_rejected or (
                event_name == "continuation_replay_rejected"
                and event.get("status") == "continuation_replayed"
                and request_match
            )
            replay_unexpected_success = replay_unexpected_success or event_name == "continuation_replay_unexpected_success"
    revoke_after_consume = bool(revoke_indexes) and bool(consume_indexes) and max(consume_indexes) < max(revoke_indexes)
    revoke_event = normalized[max(revoke_indexes)] if revoke_indexes else {}
    revoke_response = revoke_event.get("response") if isinstance(revoke_event.get("response"), dict) else {}
    revoked_positive = revoked_positive or (isinstance(revoke_response.get("revoked"), int) and revoke_response.get("revoked", 0) > 0)
    last_revoke = max(revoke_indexes) if revoke_indexes else -1
    no_post_revoke_dispatch = (
        last_revoke >= 0
        and not any(index > last_revoke for index in consume_indexes + observe_indexes)
        and replay_rejected
        and not replay_unexpected_success
    )
    return {
        "host_continuation_correlated": leased_consume and bool(turn_id),
        "post_grant_revocation_verified": revoke_after_consume and revoked_positive,
        "no_stale_host_replay": no_post_revoke_dispatch,
        "replay_rejected": replay_rejected,
        "replay_unexpected_success": replay_unexpected_success,
        "continuation_consume_count": len(consume_indexes),
        "continuation_observe_count": len(observe_indexes),
        "continuation_revoke_count": len(revoke_indexes),
        "revoked_positive": revoked_positive,
        "trace_secret_free": not any("cgr_" in json.dumps(event, ensure_ascii=False) or "lease_" in json.dumps(event, ensure_ascii=False) for event in normalized),
    }


def cancel_terminal_only_verified(probe: dict[str, Any] | None) -> bool:
    """Verify only the model-turn terminal cancellation observation.

    This is deliberately weaker than the P0 cancellation acceptance: it does
    not prove that a consumed host grant/continuation was revoked.
    """
    if not isinstance(probe, dict):
        return False
    return all(
        probe.get(key) is True
        for key in (
            "backend_acknowledged",
            "terminal_cancelled",
            "no_new_tool_cards",
            "composer_ready_after",
            "stop_control_gone",
        )
    )


def cancel_safe_state_verified(probe: dict[str, Any] | None) -> bool:
    """Accept full cancellation only after post-grant revocation is proven."""
    if not cancel_terminal_only_verified(probe):
        return False
    return all(
        probe.get(key) is True
        for key in (
            "host_continuation_correlated",
            "post_grant_revocation_verified",
            "no_stale_host_replay",
            "replay_rejected",
            "trace_secret_free",
        )
    )


def classify_case(
    pill: str | None,
    approvals: int,
    process_present,
    *,
    correlation_ok: bool | None = None,
    text_ok: bool | None = None,
    screenshot_ok: bool | None = None,
    browser_ok: bool | None = None,
    process_required: bool = False,
    text_required: bool = False,
    screenshot_required: bool = False,
    browser_required: bool = False,
    approval_required: bool = False,
    session_capability_required: bool = False,
    session_capability_ok: bool = False,
) -> str:
    if pill == "PASS":
        # A PASS pill is model/UI output, never independent acceptance evidence.
        # Every requirement selected by the scenario must be explicitly present
        # and true; None is deliberately different from False and fails closed.
        if approval_required and approvals <= 0:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if session_capability_required and not session_capability_ok:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if correlation_ok is not True:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if process_required and process_present is not True:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if text_required and text_ok is not True:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if screenshot_required and screenshot_ok is not True:
            return "NOT_INDEPENDENTLY_VERIFIED"
        if browser_required and browser_ok is not True:
            return "NOT_INDEPENDENTLY_VERIFIED"
        return "VERIFIED_SUCCESS"
    if pill == "BLOCKED":
        return "VERIFIED_BLOCKED"
    if pill == "FAIL":
        return "VERIFIED_FAILED"
    if pill == "WAITING":
        return "PENDING_TERMINAL"
    if approvals and approvals > 0:
        return "NOT_INDEPENDENTLY_VERIFIED"
    return "NOT_INDEPENDENTLY_VERIFIED"


def _sha256_path(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def run_restart_phase_worker(
    phase: int,
    driver: CdpDriver,
    isolated_root: Path,
    report_dir: Path,
) -> tuple[dict[str, Any], bool]:
    """Execute one half of a real app process-boundary restart proof."""
    fixture = prepare_coding_fixture(isolated_root)
    target = Path(fixture["workspace"]) / CODING_REL_PATH
    if phase == 1:
        raw = driver.eval(
            build_restart_phase1_expression(fixture["workspace"]),
            timeout=30.0,
            await_promise=True,
        )
        parsed = _json_object(raw) or {}
        raw_error = raw.get("__error") if isinstance(raw, dict) else None
        task_id = str(parsed.get("taskId") or "")
        events = parsed.get("lastEvents") if isinstance(parsed.get("lastEvents"), dict) else {}
        event_rows = events.get("events") if isinstance(events.get("events"), list) else []
        states = [str(item.get("state_after")) for item in event_rows if isinstance(item, dict)]
        evidence = {
            "schema_version": "localcomet.application-restart.phase1.v1",
            "phase": 1,
            "task_id": task_id,
            "approval_issued": parsed.get("approvalIssued") is True,
            "start_called": parsed.get("startCalled") is True,
            "ledger_event_count": parsed.get("eventCount"),
            "ledger_last_state": states[-1] if states else None,
            "start_error": str(parsed.get("startError") or parsed.get("phase_error") or raw_error or ""),
            "event_states_before_boundary": states,
            "workspace_path": fixture["workspace"],
            "pre_boundary_sha256": fixture["original_sha256"],
            "post_boundary_sha256": _sha256_path(target),
            "boundary": "worker/application process is terminated by exact owner cleanup after this evidence is written",
        }
        evidence["classification"] = (
            "VERIFIED_SUCCESS"
            if evidence["task_id"]
            and evidence["approval_issued"]
            and evidence["start_called"] is False
            and evidence["ledger_event_count"] == 2
            and evidence["ledger_last_state"] == "awaiting_approval"
            and not evidence["start_error"]
            else "NOT_INDEPENDENTLY_VERIFIED"
        )
        write_json(report_dir / "restart_phase1.json", evidence)
        return evidence, evidence["classification"] == "VERIFIED_SUCCESS"

    task_id = str(os.environ.get("LC_RESTART_TASK_ID", "")).strip()
    raw = driver.eval(build_restart_phase2_expression(task_id, fixture["workspace"]), timeout=20.0, await_promise=True) if task_id else {"error": "missing_restart_task_id"}
    parsed = _json_object(raw) or {}
    listed = parsed.get("listed") if isinstance(parsed.get("listed"), dict) else {}
    tasks = listed.get("tasks") if isinstance(listed.get("tasks"), list) else []
    listed_task = next((item for item in tasks if isinstance(item, dict) and item.get("task_id") == task_id), None)
    recovered = parsed.get("recovered") if isinstance(parsed.get("recovered"), dict) else {}
    pre_sha = str(os.environ.get("LC_RESTART_PRE_SHA256", ""))
    post_sha = _sha256_path(target)
    states = [str(item.get("state_after")) for item in (recovered.get("events") or []) if isinstance(item, dict)]
    replay_approval = parsed.get("replayApproval") if isinstance(parsed.get("replayApproval"), dict) else {}
    duplicate_approval_rejected = replay_approval.get("rejected") is True
    no_auto_resume = parsed.get("codingStarts") == 0
    paused = (
        isinstance(listed_task, dict)
        and listed_task.get("status") == "paused_for_review"
        and listed_task.get("requires_review") is True
        and listed_task.get("terminal") is False
        and recovered.get("status") == "paused_for_review"
        and recovered.get("requires_review") is True
        and recovered.get("terminal") is False
    )
    evidence = {
        "schema_version": "localcomet.application-restart.phase2.v1",
        "phase": 2,
        "task_id": task_id,
        "listed_task": listed_task,
        "recovered": recovered,
        "recovered_event_states": states,
        "coding_start_calls_after_relaunch": parsed.get("codingStarts"),
        "no_auto_resume": no_auto_resume,
        "duplicate_approval_rejected": duplicate_approval_rejected,
        "duplicate_approval_code": str(replay_approval.get("code") or ""),
        "pre_restart_sha256": pre_sha,
        "post_restart_sha256": post_sha,
        "workspace_unchanged_after_relaunch": bool(pre_sha) and pre_sha == post_sha,
        "error": str(parsed.get("error") or ""),
        "boundary": "phase 2 is a separate LocalComet process with a fresh WebView session and fresh PID",
    }
    evidence["classification"] = (
        "VERIFIED_SUCCESS"
        if paused
        and no_auto_resume
        and duplicate_approval_rejected
        and evidence["workspace_unchanged_after_relaunch"]
        and not evidence["error"]
        else "NOT_INDEPENDENTLY_VERIFIED"
    )
    write_json(report_dir / "restart_phase2.json", evidence)
    return evidence, evidence["classification"] == "VERIFIED_SUCCESS"


def run_worker(args: argparse.Namespace) -> int:
    from tools import launch_localcomet_dev as _legacy_launcher
    from tools import owned_run_cleanup as owned_cleanup

    # Import UIA/COM before attempting a desktop rebind; on this Windows
    # build, SetThreadDesktop before CoInitializeEx can make COM initialization
    # fail with access denied. No root/window query occurs here. We then attach
    # (or verify the worker is already on) the named hidden desktop before any
    # independent observation is attempted.
    auto = load_uia()
    reader_startup_attachment = attach_reader_to_hidden_desktop()
    isolated_root = Path(args.isolated_root).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    # Ownership manifest BEFORE any child resource is created (В§4.1). The
    # isolated root is the only destructive cleanup candidate; the canonical
    # Cargo target is a shared build cache and is intentionally never deleted
    # by a run cleanup operation.
    cargo_subkey = HIDDEN_CARGO_TARGET_SUBKEY
    parent_local_appdata = os.environ.get("LC_HIDDEN_CANONICAL_LOCALAPPDATA", "").strip()
    cargo_target_dir = resolve_hidden_cargo_target(ROOT, parent_local_appdata)
    manifest_path, manifest_payload = owned_cleanup.write_manifest(
        run_root=isolated_root,
        audit_copy_dir=report_dir,
        owner="localcomet-hidden-harness",
        repo_root=ROOT,
        isolated_root=isolated_root,
        cargo_target_dir=cargo_target_dir,
        vite_port=ISOLATED_VITE_PORT,
        cdp_port=ISOLATED_CDP_PORT,
        hidden_desktop=os.environ.get("LC_HIDDEN_DESKTOP_NAME", ""),
        root_pid=os.getpid(),
        owned_pids=[],
        owned_paths=[isolated_root],
    )
    launch, port_patched, cleanup_job, expected_dev_url, owned_root_pids = launch_isolated_tauri(
        isolated_root,
        report_dir,
        cargo_target_dir=cargo_target_dir,
        cargo_subkey=cargo_subkey,
        enable_pending_hook=bool(getattr(args, "cancel_after_continuation", False)),
    )
    # Manifest copies learn the recorded child roots after spawn (В§4.4).
    manifest_payload["owned_pids"] = sorted({int(pid) for pid in owned_root_pids})
    for manifest_copy in (
        manifest_path,
        isolated_root / owned_cleanup.MANIFEST_NAME,
        report_dir / owned_cleanup.MANIFEST_NAME,
    ):
        try:
            manifest_copy.write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except OSError:
            pass
    report_path = report_dir / "isolated_hidden_user_runs.jsonl"
    startup = {"started_utc": utc_now(), "worker_pid": os.getpid(), "launcher_pid": getattr(launch, "launcher", launch).pid, "native_pid": launch.pid, "isolated_root": str(isolated_root), "desktop_name": os.environ.get("LC_HIDDEN_DESKTOP_NAME", ""), "reader_startup_attachment": reader_startup_attachment, "isolated_vite_port": ISOLATED_VITE_PORT, "expected_dev_url": expected_dev_url, "port_patched": port_patched, "enable_computer_use": args.enable_computer_use, "scenario": args.scenario}
    write_json(report_dir / "isolated_launch.json", startup)
    summary = {"requested_cases": args.cases, "attempted": 0, "submitted": 0, "completed_observations": 0, "blocked": 0, "errors": 0, "model_ready": False, "computer_use_permissions_enabled": False, "verified_success": 0, "verified_blocked": 0, "verified_failed": 0, "pending_terminal": 0, "not_independently_verified": 0, "infrastructure_error": 0, "malformed_result": 0}
    try:
        try:
            require_native_process_alive(launch, "before_window_probe")
            root = wait_for_window(auto, 600, launch)
            require_native_process_alive(launch, "after_window_probe")
        except IsolatedStartupError as exc:
            summary["blocked"] = args.cases
            summary["infrastructure_error"] = summary.get("infrastructure_error", 0) + 1
            summary["startup_blocker"] = exc.error_type
            summary["startup_blocker_message"] = str(exc)[:600]
            summary["startup_blocker_details"] = exc.details
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "BLOCKED_NATIVE_STARTUP", "error_type": exc.error_type}, ensure_ascii=False))
            return 4
        if not isolation_selfcheck(report_dir, getattr(launch, "launcher", launch).pid):
            summary["blocked"] = args.cases
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "BLOCKED_ISOLATION_VIOLATION"}, ensure_ascii=False))
            return 2
        # Plan P0.1: the CDP page target is verified BEFORE any interaction.
        # The environment variable being set is not evidence; only an
        # answering endpoint on OUR port serving OUR dev-server URL counts.
        try:
            require_native_process_alive(launch, "before_cdp_startup")
            verification = verify_isolated_cdp_startup(report_dir)
            require_native_process_alive(launch, "after_cdp_startup")
        except IsolatedStartupError as exc:
            summary["blocked"] = args.cases
            summary["infrastructure_error"] = summary.get("infrastructure_error", 0) + 1
            summary["startup_blocker"] = exc.error_type
            summary["startup_blocker_message"] = str(exc)[:600]
            summary["startup_blocker_details"] = exc.details
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "BLOCKED_CDP_STARTUP", "error_type": exc.error_type}, ensure_ascii=False))
            return 3
        summary["cdp_verified_page_url"] = verification.get("page_url")
        # A tauri-dev rebuild just produced a binary against THIS run's dev
        # URL: record byte-level provenance so later runs may reuse it fast.
        try:
            meta = json.loads((report_dir / "isolated_processes.json").read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if str(meta.get("launch_mode", "")).startswith("tauri_dev"):
            rebuilt_binary = Path(str(meta.get("binary", "")))
            if rebuilt_binary.is_file():
                write_binary_provenance(
                    rebuilt_binary,
                    expected_dev_url,
                    rust_build_input_fingerprint(ROOT),
                )
                summary["binary_provenance_recorded"] = True
        if args.probe_only:
            time.sleep(15)  # let the webview finish hydration
            payload = cdp_drawer_probe(report_dir, auto, lambda: uia_window(auto))
            summary["probe_only"] = True
            summary["probe_ok"] = bool(payload.get("ok"))
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "PROBE_DONE", "ok": payload.get("ok")}, ensure_ascii=False))
            return 0
        # CDP-driven interaction: the app is healthy, but UIA Invoke never
        # reaches the WebView2 DOM on a non-interactive desktop (see
        # webview_probe.json), so all clicks/typing go through the DevTools
        # protocol while UIA remains available for read-only observation.
        driver = CdpDriver()
        restart_phase = int(os.environ.get("LC_RESTART_PHASE", "0") or 0)
        if restart_phase in (1, 2):
            # Restart proof is deterministic Tauri coding IPC and does not need
            # a model or a UI approval click. It returns before the normal model
            # setup loop so a fresh app process can be measured directly.
            evidence, ok = run_restart_phase_worker(restart_phase, driver, isolated_root, report_dir)
            summary["model_ready"] = True
            summary["attempted"] = 1
            summary["completed_observations"] = 1
            summary["verified_success"] = 1 if ok else 0
            summary["not_independently_verified"] = 0 if ok else 1
            summary["restart_phase"] = restart_phase
            summary["restart_classification"] = evidence.get("classification")
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "RESTART_PHASE_DONE", "phase": restart_phase, "classification": evidence.get("classification")}, ensure_ascii=False), flush=True)
            return 0 if ok else 1
        # The early CTA click can land before the webview finishes hydration;
        # the retry loop below re-opens the drawer as needed.
        time.sleep(8)
        use_coding = os.environ.get("LC_USE_CODING", "") == "1"
        if not use_coding:
            driver.click_setup_action()
            time.sleep(2)
        # Model loading can take several minutes for the managed runtime.
        # The deterministic coding E2E is pure Tauri IPC and needs no model,
        # so it only waits out a short webview-hydration window.
        model_ready = False
        progress_path = report_dir / "model_setup_progress.jsonl"
        deadline = time.monotonic() + (20 if use_coding else 600)
        last_progress = 0.0
        while time.monotonic() < deadline:
            # Primary signal is an enabled composer; the header status text is
            # the fallback for the auto-setup path where no drawer ever opens.
            if driver.composer_ready() or driver.model_status_ready():
                model_ready = True
                break
            # Stable selector-first action handles both the chat setup CTA and
            # the managed drawer primary install/connect CTA. Never use the HF
            # navigation label as a setup fallback.
            driver.click_setup_action()
            if time.monotonic() - last_progress > 15:
                last_progress = time.monotonic()
                with progress_path.open("a", encoding="utf-8") as progress:
                    progress.write(json.dumps({
                        "ts": utc_now(),
                        "target": getattr(driver, "target_url", ""),
                        "drawer": driver.dialog_open(),
                        "snippet": driver.body_snippet(400),
                        "diagnostics": driver.setup_diagnostics(),
                    }, ensure_ascii=False) + "\n")
            time.sleep(3)
        summary["model_ready"] = model_ready
        if model_ready:
            # Auto-attach can flip the header status while the setup drawer is
            # still open and the chat view is not mounted yet: navigate there
            # explicitly before running scenarios.
            for _ in range(8):
                if driver.composer_ready():
                    break
                driver.click_in_dialog(("Загрузить и подключить", "Подключить модель", "Подключить", "Готово", "Закрыть"))
                driver.click_texts(("Чат",))
                time.sleep(2)
        if not model_ready or not driver.composer_ready():
            write_json(report_dir / "model_setup_blocked.json", {
                "timestamp_utc": utc_now(),
                "error_type": "TimeoutError",
                "error": "composer did not become enabled (CDP check)",
                "body_snippet": driver.body_snippet(800),
                "setup_diagnostics": driver.setup_diagnostics(),
                "status_names": named_status(uia_window(auto))[-120:] if uia_window(auto) else [],
            })
        # Deterministic intent dispatch needs the same explicit, opt-in
        # computerUse capability as the model path (deny-by-default holds).
        needs_permissions = args.enable_computer_use or os.environ.get("LC_USE_INTENT", "") == "1"
        if model_ready and needs_permissions:
            permissions_enabled = driver.enable_computer_use_permissions()
            summary["computer_use_permissions_enabled"] = permissions_enabled
            if permissions_enabled:
                # Reloaded page must rehydrate the managed model session before
                # submitting. A localStorage permission change intentionally
                # resets the WebView stores, so reuse the same truthful readiness
                # loop rather than treating the temporary loading state as a
                # permanent block.
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    if driver.composer_ready() or driver.model_status_ready():
                        break
                    driver.click_setup_action()
                    time.sleep(3)
                for _ in range(8):
                    if driver.composer_ready():
                        break
                    driver.click_setup_action()
                    driver.click_texts(("Чат",))
                    time.sleep(2)
            if not permissions_enabled or not driver.composer_ready():
                summary["blocked"] = args.cases
                summary["finished_utc"] = utc_now()
                write_json(report_dir / "isolated_hidden_summary.json", summary)
                print(json.dumps({"outcome": "BLOCKED_COMPUTER_USE_PERMISSION_SETUP"}, ensure_ascii=False))
                return 2
        with report_path.open("w", encoding="utf-8") as report:
            campaign_id = f"campaign-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            consecutive_blocked = 0
            driver = CdpDriver()
            if getattr(args, "cancel_after_continuation", False):
                continuation_workspace = Path(args.isolated_root).resolve() / "continuation_fixture"
                continuation_workspace.mkdir(parents=True, exist_ok=True)
                workspace_path_json = json.dumps(str(continuation_workspace), ensure_ascii=False)
                workspace_raw = driver.eval(
                    "(async()=>{const T=window.__TAURI_INTERNALS__;if(!T||!T.invoke)return {error:'tauri_internals_missing'};"
                    "try{return await T.invoke('set_workspace',{path:" + workspace_path_json + "});}"
                    "catch(e){return {error:(e&&typeof e==='object')?JSON.stringify(e):String(e)};}})()",
                    timeout=30.0,
                    await_promise=True,
                )
                workspace_result = _json_object(workspace_raw)
                write_json(report_dir / "cancellation_workspace.json", {
                    "schema_version": "localcomet.cancellation-workspace.v1",
                    "workspace": str(continuation_workspace),
                    "result": workspace_result,
                    "ok": workspace_result.get("status") == "ok" and bool(workspace_result.get("workspace_digest")),
                })
                if workspace_result.get("status") != "ok" or not workspace_result.get("workspace_digest"):
                    summary["blocked"] = args.cases
                    summary["finished_utc"] = utc_now()
                    write_json(report_dir / "isolated_hidden_summary.json", summary)
                    print(json.dumps({"outcome": "BLOCKED_CANCELLATION_WORKSPACE_SETUP"}, ensure_ascii=False))
                    return 2
            scenario_pool = SCENARIOS if args.scenario else AUTO_SCENARIOS
            for index in range(args.cases):
                if args.scenario:
                    scenario = next(item for item in scenario_pool if item["id"] == args.scenario)
                else:
                    scenario = scenario_pool[index % len(scenario_pool)]
                row: dict[str, Any] = {
                    "campaign_id": campaign_id,
                    "case_id": f"ISO-CU-{index + 1:04d}",
                    "scenario_family": scenario["id"],
                    "prompt": scenario["prompt"],
                    "started_utc": utc_now(),
                }
                summary["attempted"] += 1
                # A fresh socket per case removes half-dead connection states
                # that previously degraded all late-campaign evidence.
                try:
                    driver.close()
                except Exception:
                    pass
                driver = CdpDriver()
                use_coding = os.environ.get("LC_USE_CODING", "") == "1"
                if use_coding:
                    # Deterministic coding E2E: real Tauri IPC, no model.
                    # Independent postconditions come from fixture bytes on
                    # disk, not from the app's own claims.
                    fixture = prepare_coding_fixture(isolated_root)
                    dispatch_expr = build_coding_dispatch_expression(fixture["workspace"])
                    raw = driver.eval(dispatch_expr, timeout=300.0, await_promise=True)
                    parsed = _json_object(raw)
                    disk = verify_coding_fixture_on_disk(
                        isolated_root,
                        fixture["original_sha256"],
                        CODING_NEW_CONTENT,
                    )
                    outcome, classification = classify_coding_result(parsed, disk)
                    write_json(report_dir / "coding_dispatch.json", {
                        "schema_version": "localcomet.coding-dispatch.v1",
                        "timestamp_utc": utc_now(),
                        "branch_head": subprocess.run(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
                        ).stdout.strip() if shutil.which("git") else "",
                        "fixture": {
                            "workspace": fixture["workspace"],
                            "original_sha256": fixture["original_sha256"],
                        },
                        "payload": parsed,
                        "disk_postcondition": disk,
                        "outcome": outcome,
                        "classification": classification,
                    })
                    row["outcome"] = outcome
                    row["final_classification"] = classification
                    row["observation"] = {
                        "task_id": (parsed or {}).get("taskId", ""),
                        "status": ((parsed or {}).get("result") or {}).get("status", ""),
                        "reason": ((parsed or {}).get("result") or {}).get("reason", ""),
                        "generation_hash": ((parsed or {}).get("result") or {}).get("generation_hash", ""),
                        "replay_rejected": bool(((parsed or {}).get("replay") or {}).get("rejected")),
                        "tamper_rejected": bool(((parsed or {}).get("tamper") or {}).get("rejected")),
                        "compile_failure_status": ((parsed or {}).get("compile_failure") or {}).get("status", ""),
                        "disk_final_sha256": disk.get("final_sha256", ""),
                        "rollback_restored_original": disk.get("rollback_restored_original"),
                        "events_count": len(((parsed or {}).get("events") or {}).get("events") or []),
                    }
                    summary["completed_observations"] += 1
                    if classification == "VERIFIED_SUCCESS":
                        summary["verified_success"] += 1
                    elif classification == "VERIFIED_BLOCKED":
                        summary["verified_blocked"] += 1
                    elif classification == "VERIFIED_FAILED":
                        summary["verified_failed"] += 1
                    else:
                        summary["not_independently_verified"] += 1
                    report.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                use_fake_approval = os.environ.get("LC_USE_FAKE_APPROVAL", "") == "1"
                if use_fake_approval:
                    before_notepad = _windows_process_ids("notepad.exe")
                    raw = driver.eval(build_fake_approval_expression(), timeout=60.0, await_promise=True)
                    parsed = _json_object(raw) or {}
                    after_notepad = _windows_process_ids("notepad.exe")
                    detail = str(parsed.get("detail") or parsed.get("error") or "")
                    proof = {
                        "fake_dom_present": parsed.get("fake_dom_present") is True,
                        "fake_dom_button_clicked": parsed.get("fake_dom_button_clicked") is True,
                        "run_rejected": parsed.get("rejected") is True,
                        "rejection_mentions_approval": "approval" in detail.lower() or "grant" in detail.lower() or "token" in detail.lower(),
                        "notepad_pids_before": before_notepad,
                        "notepad_pids_after": after_notepad,
                        "new_notepad_pids": sorted(set(after_notepad) - set(before_notepad)),
                        "no_host_mutation": after_notepad == before_notepad,
                    }
                    proof_ok = all(
                        proof.get(key) is True
                        for key in (
                            "fake_dom_present",
                            "fake_dom_button_clicked",
                            "run_rejected",
                            "rejection_mentions_approval",
                            "no_host_mutation",
                        )
                    )
                    evidence = {
                        "schema_version": "localcomet.fake-approval.v1",
                        "timestamp_utc": utc_now(),
                        "branch_head": subprocess.run(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
                        ).stdout.strip() if shutil.which("git") else "",
                        "payload": parsed,
                        "proof": proof,
                        "outcome": "FAKE_DOM_APPROVAL_REJECTED" if proof_ok else "FAKE_DOM_APPROVAL_PROOF_FAILED",
                        "classification": "VERIFIED_BLOCKED" if proof_ok else "NOT_INDEPENDENTLY_VERIFIED",
                    }
                    write_json(report_dir / "fake_approval_dispatch.json", evidence)
                    row["outcome"] = evidence["outcome"]
                    row["final_classification"] = evidence["classification"]
                    row["observation"] = proof
                    summary["completed_observations"] += 1
                    if evidence["classification"] == "VERIFIED_BLOCKED":
                        summary["verified_blocked"] += 1
                    else:
                        summary["not_independently_verified"] += 1
                    report.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                use_foreign = os.environ.get("LC_USE_FOREIGN", "") == "1"
                if use_foreign:
                    # A real foreign process is created by this harness on the
                    # already-bound hidden desktop. It is harness-owned for
                    # cleanup, but deliberately absent from the Rust broker's
                    # SPAWN_REGISTRY. Both windows must share the same image and
                    # title; close_owned may terminate only the broker record.
                    foreign_process = subprocess.Popen(
                        ["notepad.exe"],
                        creationflags=CREATE_NEW_PROCESS_GROUP,
                    )
                    foreign_pid = int(foreign_process.pid)
                    time.sleep(1.5)
                    foreign_before = _windows_process_state(foreign_pid)
                    dispatch_expr = build_foreign_ownership_expression()
                    raw = driver.eval(dispatch_expr, timeout=180.0, await_promise=True)
                    parsed = _json_object(raw) or {}
                    open_payload = parsed.get("open") or {}
                    open_result = open_payload.get("result") or {}
                    owner_execution = open_result.get("execution") or {}
                    owner_pid = int(owner_execution.get("pid") or owner_execution.get("spawn_pid") or 0)
                    owner_before = _windows_process_state(owner_pid)
                    time.sleep(0.8)
                    foreign_after_open = _windows_process_state(foreign_pid)
                    negative_raw = driver.eval(
                        build_foreign_negative_close_expression(),
                        timeout=180.0,
                        await_promise=True,
                    )
                    negative_payload = _json_object(negative_raw) or {}
                    parsed["foreignAttempt"] = negative_payload.get("foreignAttempt")
                    time.sleep(0.8)
                    foreign_after = _windows_process_state(foreign_pid)
                    owner_after = _windows_process_state(owner_pid)
                    close_result = {}
                    foreign_attempt = parsed.get("foreignAttempt") or {}
                    foreign_attempt_result = foreign_attempt.get("result") or {}
                    proof = {
                        "foreign_pid": foreign_pid,
                        "foreign_before": foreign_before,
                        "foreign_after": foreign_after,
                        "owner_pid": owner_pid,
                        "owner_before": owner_before,
                        "owner_after": owner_after,
                        "same_process_image": str(foreign_before.get("process_name", "")).lower() == str(owner_before.get("process_name", "")).lower() == "notepad",
                        "same_window_title": bool(foreign_before.get("window_title")) and foreign_before.get("window_title") == owner_before.get("window_title"),
                        "foreign_preserved": foreign_after.get("alive") is True,
                        "owner_still_present_before_owner_cleanup": owner_after.get("alive") is True,
                        "foreign_parent_attempt_blocked": foreign_attempt_result.get("status") == "blocked",
                        "close_status": close_result.get("status", "not_attempted"),
                        "close_terminated": False,
                    }
                    # This is intentionally a negative protected-postcondition
                    # proof. The random ownership request must be blocked while
                    # a same-title foreign PID remains alive. The broker owner
                    # is left to the canonical harness job cleanup, not killed
                    # from inside the CDP expression.
                    proof_ok = all(
                        proof.get(key) is True
                        for key in (
                            "same_process_image",
                            "same_window_title",
                            "foreign_preserved",
                            "owner_still_present_before_owner_cleanup",
                            "foreign_parent_attempt_blocked",
                        )
                    )
                    try:
                        evidence = {
                            "schema_version": "localcomet.foreign-ownership.v1",
                            "timestamp_utc": utc_now(),
                            "branch_head": subprocess.run(
                                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
                            ).stdout.strip() if shutil.which("git") else "",
                            "payload": parsed,
                            "proof": proof,
                            "outcome": "FOREIGN_OWNER_REJECTION_VERIFIED" if proof_ok else "FOREIGN_OWNER_PROOF_FAILED",
                            "classification": "VERIFIED_BLOCKED" if proof_ok else "NOT_INDEPENDENTLY_VERIFIED",
                        }
                        write_json(report_dir / "foreign_ownership_dispatch.json", evidence)
                        row["outcome"] = evidence["outcome"]
                        row["final_classification"] = evidence["classification"]
                        row["observation"] = proof
                        summary["completed_observations"] += 1
                        if evidence["classification"] == "VERIFIED_SUCCESS":
                            summary["verified_success"] += 1
                        elif evidence["classification"] == "VERIFIED_BLOCKED":
                            summary["verified_blocked"] += 1
                        else:
                            summary["not_independently_verified"] += 1
                        report.write(json.dumps(row, ensure_ascii=False) + "\n")
                    finally:
                        # Exact handle/PID cleanup for the process this branch
                        # created; never terminate by image name.
                        if foreign_process.poll() is None:
                            foreign_process.terminate()
                            try:
                                foreign_process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                foreign_process.kill()
                                foreign_process.wait(timeout=3)
                    continue
                use_intent = os.environ.get("LC_USE_INTENT", "") == "1"
                if use_intent:
                    # Deterministic intent path: no Qwen tool emission, no
                    # model fallback. Every authority decision is a real
                    # Tauri command executed inside the isolated app.
                    dispatch_expr = build_intent_dispatch_expression(INTENT_DISPATCH_PROMPT)
                    raw = driver.eval(dispatch_expr, timeout=150.0, await_promise=True)
                    parsed = _json_object(raw)
                    outcome, classification = classify_intent_dispatch_result(parsed)
                    write_json(report_dir / "intent_dispatch.json", {
                        "schema_version": "localcomet.intent-dispatch.v1",
                        "timestamp_utc": utc_now(),
                        "prompt": INTENT_DISPATCH_PROMPT,
                        "branch_head": subprocess.run(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
                        ).stdout.strip() if shutil.which("git") else "",
                        "payload": parsed,
                        "outcome": outcome,
                        "classification": classification,
                    })
                    row["outcome"] = outcome
                    row["final_classification"] = classification
                    if isinstance(parsed, dict):
                        result_env = (parsed.get("result") or {})
                        execution = result_env.get("execution") or {}
                        row["observation"] = {
                            "status": result_env.get("status", ""),
                            "verification": result_env.get("verification", ""),
                            "request_id": parsed.get("requestId", ""),
                            "action_id": parsed.get("actionId", ""),
                            "intent_id": parsed.get("intent_id", ""),
                            "plan_digest": parsed.get("plan_digest", ""),
                            "approval_id": (parsed.get("envelope") or {}).get("approval_id", ""),
                            "desktop": execution.get("desktop", ""),
                            "spawn_pid": execution.get("spawn_pid"),
                            "observed_pid": execution.get("pid"),
                            "url": execution.get("url", ""),
                            "cdp_port": execution.get("cdp_port"),
                            "input_digest": execution.get("input_digest", ""),
                            "continuation_grant_present": bool((execution.get("continuation") or {}).get("grant_ref")),
                            "on_user_desktop": ((execution.get("window_evidence") or {}).get("on_user_desktop")),
                            "foreground_unchanged": execution.get("foreground_unchanged"),
                        }
                    summary["completed_observations"] += 1
                    if classification == "VERIFIED_SUCCESS":
                        summary["verified_success"] += 1
                    elif classification == "VERIFIED_BLOCKED":
                        summary["verified_blocked"] += 1
                    elif classification == "VERIFIED_FAILED":
                        summary["verified_failed"] += 1
                    elif classification == "PENDING_TERMINAL":
                        summary["pending_terminal"] += 1
                    else:
                        summary["not_independently_verified"] += 1
                    report.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                if not model_ready:
                    row["outcome"] = "BLOCKED_MODEL_NOT_READY"
                    row["final_classification"] = "NOT_INDEPENDENTLY_VERIFIED"
                    summary["blocked"] += 1
                else:
                    try:
                        if not driver.composer_ready():
                            consecutive_blocked += 1
                            row["outcome"] = "BLOCKED_COMPOSER_NOT_READY"
                            row["final_classification"] = "INFRASTRUCTURE_ERROR"
                            summary["blocked"] += 1
                            summary["infrastructure_error"] = summary.get("infrastructure_error", 0) + 1
                            if consecutive_blocked >= 3:
                                # App is gone/unresponsive: stop honestly now
                                # instead of emitting hundreds of junk rows.
                                row["abort_note"] = "stopping campaign: app unresponsive"
                                summary["aborted_reason"] = "app unresponsive (composer not ready x3)"
                                report.write(json.dumps(row, ensure_ascii=False) + "\n")
                                break
                        else:
                            consecutive_blocked = 0
                        if row.get("outcome"):
                            pass
                        else:
                            submitted, initial_tool_card_count = submit_prompt_with_card_baseline(
                                driver, scenario["prompt"]
                            )
                            if not submitted:
                                raise RuntimeError("composer submit failed")
                            summary["submitted"] += 1
                            row["outcome"] = "SUBMITTED"
                            # The current narrow browser fallback is one direct
                            # open_url card. Keep same-turn correlation strict;
                            # never compensate for a late baseline with body text.
                            required_tool_cards = 1
                            observations: list[dict[str, Any]] = [cdp_wait_for_turn(
                                driver,
                                300,
                                initial_tool_card_count + required_tool_cards,
                                native_process=launch,
                                lookback_cards=required_tool_cards,
                                cancel_after_ms=args.cancel_after_ms,
                                cancel_after_continuation=getattr(args, "cancel_after_continuation", False),
                            )]
                            for observed_turn in observations:
                                if observed_turn.get("state") in {"terminal", "composer_ready", "composer_ready_no_tool", "composer_ready_no_new_tool"}:
                                    summary["completed_observations"] += 1

                            def evidence_from_observation(observed_turn: dict[str, Any]) -> dict[str, Any]:
                                return {
                                    "pill": observed_turn.get("pill"),
                                    "reason": observed_turn.get("reason", ""),
                                    "action": observed_turn.get("action", ""),
                                    "request_id": observed_turn.get("request_id", ""),
                                    "action_id": observed_turn.get("action_id", ""),
                                    "approval_id": observed_turn.get("approval_id", ""),
                                    "approval_call_id": observed_turn.get("approval_call_id", ""),
                                    "input_digest": observed_turn.get("input_digest", ""),
                                    "process_pid": observed_turn.get("process_pid", ""),
                                    "browser_url": observed_turn.get("browser_url", ""),
                                    "browser_cdp_port": observed_turn.get("browser_cdp_port", ""),
                                    "screenshot_sha256": observed_turn.get("screenshot_sha256", ""),
                                    "screenshot_backend": observed_turn.get("screenshot_backend", ""),
                                    "screenshot_scope": observed_turn.get("screenshot_scope", ""),
                                    "screenshot_bytes": observed_turn.get("screenshot_bytes", ""),
                                    "screenshot_capture_pid": observed_turn.get("screenshot_capture_pid", ""),
                                    "screenshot_present": bool(observed_turn.get("screenshot_present")),
                                    "screenshot_src_length": int(observed_turn.get("screenshot_src_length") or 0),
                                    "card_count": int(observed_turn.get("card_count") or 0),
                                    "status": observed_turn.get("status", ""),
                                    "verification": observed_turn.get("verification", ""),
                                }

                            expected = SCENARIO_EXPECTED_PROCESS.get(scenario["id"])
                            expected_text = SCENARIO_EXPECTED_TEXT.get(scenario["id"])
                            first_evidence = evidence_from_observation(observations[0])
                            observed_process_pid = first_evidence.get("process_pid")
                            proc_present = _process_present(
                                expected,
                                owned_root_pids,
                                observed_pid=observed_process_pid,
                            )
                            if proc_present is not True:
                                proc_present = _broker_process_present(expected, first_evidence, observations)
                            text_proof = (
                                read_hidden_window_text(auto, expected_text, timeout=3.0)
                                if expected_text
                                else {"ok": True, "status": "not_required"}
                            )
                            # Some models satisfy the first compound request only
                            # with open_app. One bounded, explicit follow-up makes
                            # the requested typing a real user-style second turn;
                            # it is still independently checked through UIA.
                            if (
                                expected_text
                                and text_proof.get("ok") is False
                                and proc_present is True
                                and str(first_evidence.get("pill") or "").upper() == "PASS"
                                and int(first_evidence.get("card_count") or 0) < initial_tool_card_count + 2
                            ):
                                follow_up = (
                                    "В уже открытом Блокноте выполни именно действие Computer Use "
                                    f"type с текстом только этого маркера: {expected_text}. "
                                    "Не отвечай объяснением и не пропускай вызов инструмента."
                                )
                                row["follow_up_prompt"] = follow_up
                                follow_up_submitted, follow_up_baseline = submit_prompt_with_card_baseline(
                                    driver, follow_up
                                )
                                if follow_up_submitted:
                                    summary["submitted"] += 1
                                    observations.append(cdp_wait_for_turn(
                                        driver,
                                        300,
                                        follow_up_baseline + 1,
                                        native_process=launch,
                                    ))
                                    if observations[-1].get("state") in {"terminal", "composer_ready", "composer_ready_no_tool", "composer_ready_no_new_tool"}:
                                        summary["completed_observations"] += 1
                                    text_proof = read_hidden_window_text(auto, expected_text, timeout=12.0)
                                else:
                                    text_proof["reason"] = "follow-up prompt submit failed"

                            screenshot_scenario = scenario["id"] in {"desktop_screenshot", "screenshot_after_actions"}
                            broker_card_identity_ready = (
                                str(first_evidence.get("status") or "") in {"verified", "completed"}
                                and first_evidence.get("verification") == "verified"
                                and str(first_evidence.get("process_pid") or "").isdigit()
                                and bool(first_evidence.get("request_id"))
                                and bool(first_evidence.get("action_id"))
                            )
                            if screenshot_scenario and scenario["id"] == "desktop_screenshot" and broker_card_identity_ready:
                                row["screenshot_owner_context_written"] = write_screenshot_owner_context(
                                    report_dir / "screenshot_owner_context.json",
                                    pid=first_evidence.get("process_pid"),
                                    desktop=os.environ.get("LC_HIDDEN_DESKTOP_NAME", ""),
                                    request_id=str(first_evidence.get("request_id") or ""),
                                    action_id=str(first_evidence.get("action_id") or ""),
                                )
                            latest_before_screenshot_follow_up = evidence_from_observation(observations[-1])
                            if (
                                screenshot_scenario
                                and not latest_before_screenshot_follow_up.get("screenshot_sha256")
                                and str(latest_before_screenshot_follow_up.get("pill") or "").upper() == "PASS"
                                and int(latest_before_screenshot_follow_up.get("card_count") or 0) < initial_tool_card_count + 2
                            ):
                                screenshot_follow_up = (
                                    "Сделай screenshot сейчас в текущем изолированном окне. Это обязательный read-only шаг "
                                    "текущего сценария; "
                                    "не отвечай объяснением и не пропускай вызов инструмента."
                                )
                                row["screenshot_follow_up_prompt"] = screenshot_follow_up
                                screenshot_submitted, screenshot_baseline = submit_prompt_with_card_baseline(
                                    driver, screenshot_follow_up
                                )
                                if screenshot_submitted:
                                    summary["submitted"] += 1
                                    observations.append(cdp_wait_for_turn(
                                        driver,
                                        300,
                                        screenshot_baseline + 1,
                                        native_process=launch,
                                    ))
                                    if observations[-1].get("state") in {"terminal", "composer_ready", "composer_ready_no_tool", "composer_ready_no_new_tool"}:
                                        summary["completed_observations"] += 1

                            indexed = [(turn, evidence_from_observation(turn)) for turn in observations]
                            evidence = next(
                                (item[1] for item in indexed if item[1].get("approval_id") and item[1].get("input_digest")),
                                indexed[-1][1],
                            )
                            # Prefer terminal evidence from the last turn for the
                            # displayed outcome, but retain correlated host and
                            # observation fields from earlier cards in this same
                            # turn (for example open_app PID -> task PASS).
                            final_evidence = dict(indexed[-1][1])
                            for field in (
                                "process_pid",
                                "browser_url",
                                "browser_cdp_port",
                                "screenshot_sha256",
                                "screenshot_backend",
                                "screenshot_scope",
                                "screenshot_bytes",
                                "screenshot_capture_pid",
                            ):
                                if not final_evidence.get(field):
                                    final_evidence[field] = next(
                                        (item[1].get(field) for item in indexed if item[1].get(field)),
                                        "",
                                    )
                            observed_process_pid = final_evidence.get("process_pid")
                            proc_present = _process_present(
                                expected,
                                owned_root_pids,
                                observed_pid=observed_process_pid,
                            )
                            if proc_present is not True:
                                proc_present = _broker_process_present(expected, final_evidence, observations)
                            if (
                                not final_evidence.get("pill")
                                or not (evidence.get("approval_id") and evidence.get("input_digest"))
                            ):
                                late = _tool_card_evidence(driver, initial_tool_card_count + len(observations))
                                if late.get("pill"):
                                    if not final_evidence.get("pill"):
                                        final_evidence = late
                                    else:
                                        for field, value in late.items():
                                            if value and not final_evidence.get(field):
                                                final_evidence[field] = value
                                    if late.get("approval_id") and late.get("input_digest"):
                                        # The late card is still the same current
                                        # turn; use its authenticated envelope
                                        # for correlation instead of the earlier
                                        # composer-ready snapshot.
                                        evidence = late
                            observed_process_pid = final_evidence.get("process_pid")
                            proc_present = _process_present(
                                expected,
                                owned_root_pids,
                                observed_pid=observed_process_pid,
                            )
                            if proc_present is not True:
                                proc_present = _broker_process_present(expected, final_evidence, observations)
                            approvals = sum(int(turn.get("approvals") or 0) for turn in observations)
                            correlation_turn = next(
                                (turn for turn, item in indexed if item.get("approval_id") and item.get("input_digest")),
                                observations[0],
                            )
                            session_capability_required = scenario["id"] in GUARDED_SCENARIO_IDS
                            # Browser navigation is Rust-dangerous and must be
                            # accepted through the observed frontend approval
                            # prompt. Guarded app actions may use the explicit
                            # hidden session capability, but this branch must not
                            # downgrade browser approval to that capability.
                            approval_required = scenario["id"] in APPROVAL_REQUIRED_SCENARIO_IDS
                            session_capability_ok = bool(args.enable_computer_use)
                            correlation = validate_correlation(
                                correlation_turn,
                                evidence,
                                approvals,
                                approval_required=approval_required,
                                session_capability_required=session_capability_required,
                                session_capability_ok=session_capability_ok,
                            )
                            screenshot_required = scenario["id"] in {"desktop_screenshot", "screenshot_after_actions"}
                            rendered_screenshot = (
                                materialize_rendered_screenshot(
                                    driver,
                                    report_dir / "captured_window.png",
                                    str(final_evidence.get("screenshot_sha256") or ""),
                                )
                                if screenshot_required
                                else {"ok": True, "status": "not_required"}
                            )
                            screenshot_evidence = (
                                validate_screenshot_evidence(
                                    final_evidence,
                                    expected_pid=observed_process_pid if scenario["id"] == "desktop_screenshot" else None,
                                )
                                if screenshot_required
                                else {"ok": True, "status": "not_required", "checks": {}}
                            )
                            if screenshot_required:
                                screenshot_evidence["rendered_png"] = rendered_screenshot
                                screenshot_evidence.setdefault("checks", {})["rendered_png"] = bool(rendered_screenshot.get("ok"))
                                screenshot_evidence["ok"] = bool(screenshot_evidence.get("ok")) and bool(rendered_screenshot.get("ok"))
                                if screenshot_evidence.get("ok") is True:
                                    try:
                                        capture_pid = int(final_evidence.get("screenshot_capture_pid") or 0)
                                        observed_pid = int(final_evidence.get("process_pid") or 0)
                                    except (TypeError, ValueError):
                                        capture_pid = observed_pid = 0
                                    if capture_pid > 0 and capture_pid == observed_pid:
                                        proc_present = True
                            browser_required = scenario["id"] in {
                                "browser_youtube",
                                "browser_readonly_search",
                                "browser_second_readonly_search",
                            }
                            browser_pid_raw = str(final_evidence.get("process_pid") or "")
                            browser_port_raw = str(final_evidence.get("browser_cdp_port") or "")
                            browser_evidence = (
                                browser_url_evidence(
                                    int(browser_port_raw) if browser_port_raw.isdigit() else 0,
                                    int(browser_pid_raw) if browser_pid_raw.isdigit() else 0,
                                    scenario_id=scenario["id"],
                                    expected_profile_dir=hidden_browser_profile_path(isolated_root),
                                )
                                if browser_required
                                else {"ok": True, "status": "not_required"}
                            )
                            if browser_required and browser_evidence.get("ok") is True:
                                proc_present = True
                            row["observation"] = observations[-1]
                            row["observations"] = observations
                            row["cancellation_requested"] = args.cancel_after_ms is not None
                            row["cancellation_evidence"] = [
                                turn.get("cancel_probe") for turn in observations if turn.get("cancel_probe") is not None
                            ]
                            row["body_snippet"] = driver.body_snippet(500)
                            row["approval_required"] = approval_required
                            row["session_capability_required"] = session_capability_required
                            row["session_capability_enabled"] = session_capability_ok
                            row["authorization_mode"] = "approval" if approval_required else ("session_capability" if session_capability_required else "none")
                            row["approval_decision"] = "approved" if approvals else "none"
                            prompt_evidence = correlation_turn.get("approval_prompt") or {}
                            row["approval_request_id"] = prompt_evidence.get("approval_request_id", "")
                            row["approval_id"] = evidence.get("approval_id", "")
                            row["approval_call_id"] = evidence.get("approval_call_id", "")
                            row["grant_id"] = "not_returned_by_contract"
                            row["grant_id_note"] = "Grant token is intentionally never exposed to UI or harness."
                            row["request_id"] = evidence.get("request_id", "")
                            row["action_id"] = evidence.get("action_id", "")
                            row["correlation_evidence"] = correlation
                            row["screenshot_evidence"] = screenshot_evidence
                            row["text_evidence"] = text_proof
                            row["browser_evidence"] = browser_evidence
                            row["process_evidence"] = {
                                "expected_any": expected,
                                "observed_pid": observed_process_pid,
                                "owned_root_pids": sorted({int(pid) for pid in owned_root_pids}),
                                "present": proc_present,
                            }
                            classification = classify_case(
                                str(final_evidence.get("pill") or "").upper() or None,
                                approvals,
                                proc_present,
                                correlation_ok=bool(correlation.get("ok")),
                                text_ok=text_proof.get("ok") if expected_text else None,
                                screenshot_ok=screenshot_evidence.get("ok") if screenshot_required else None,
                                browser_ok=browser_evidence.get("ok") if browser_required else None,
                                process_required=bool(expected),
                                text_required=bool(expected_text),
                                screenshot_required=screenshot_required,
                                browser_required=browser_required,
                                approval_required=approval_required,
                                session_capability_required=session_capability_required,
                                session_capability_ok=session_capability_ok,
                            )
                            cancellation_clicks = [
                                item for item in row["cancellation_evidence"]
                                if isinstance(item, dict) and item.get("clicked") is True
                            ]
                            if cancellation_clicks:
                                cancel_terminal_only = any(cancel_terminal_only_verified(item) for item in cancellation_clicks)
                                cancel_safe_state = any(cancel_safe_state_verified(item) for item in cancellation_clicks)
                                # A DOM Stop click alone is never acceptance. The
                                # current native probe proves only model-turn terminal
                                # cancellation; full P0 acceptance additionally needs
                                # a correlated consumed host continuation, proven grant
                                # revocation, and no stale replay.
                                classification = "VERIFIED_SUCCESS" if cancel_safe_state else "PENDING_TERMINAL"
                                row["cancellation_terminal_only_verified"] = cancel_terminal_only
                                row["cancellation_full_safe_state_verified"] = cancel_safe_state
                            row["final_classification"] = classification
                            row["cancellation_clicks"] = cancellation_clicks
                            summary_key = classification.lower()
                            summary[summary_key] = summary.get(summary_key, 0) + 1
                    except Exception as exc:
                        summary["errors"] += 1
                        row["outcome"] = "ERROR"
                        row["final_classification"] = "INFRASTRUCTURE_ERROR"
                        summary["infrastructure_error"] = summary.get("infrastructure_error", 0) + 1
                        row["error_type"] = type(exc).__name__
                        row["error"] = str(exc)[:600]
                        row["cdp_last_error"] = driver.last_error[:300]
                        row["submit_result"] = driver.last_submit_result[:200]
                row["finished_utc"] = utc_now()
                report.write(json.dumps(row, ensure_ascii=False) + "\n")
                report.flush()
                if (index + 1) % 5 == 0:
                    print(json.dumps({"progress": index + 1, **summary}, ensure_ascii=False), flush=True)
    finally:
        summary["finished_utc"] = utc_now()
        write_json(report_dir / "isolated_hidden_summary.json", summary)
        # Owner-scoped lifecycle (plan P0.1 item 5): the job object holds every
        # process THIS worker spawned (npm/node/vite/cargo/app/msedgewebview2).
        # Closing the last handle makes the kernel terminate exactly that tree
        # вЂ” even if this worker crashed. Foreign/user processes were never
        # assigned to the job and remain unreachable by construction.
        cleanup = cleanup_owned_process_tree(owned_root_pids)
        write_json(report_dir / "owned_cleanup.json", cleanup)
        try:
            kernel32.CloseHandle(cleanup_job)
        except Exception:
            pass
        # Owner-scoped cleanup (В§4.5): final evidence is already written above.
        # Mark completion here, but the parent performs destructive cleanup only
        # after this worker exits, so root_pid cannot make its own root ineligible
        # or race the evidence write. The report and shared BuildCache base remain
        # untouched; only exact manifest-listed paths are candidates.
        try:
            for manifest_copy in (
                manifest_path,
                isolated_root / owned_cleanup.MANIFEST_NAME,
                report_dir / owned_cleanup.MANIFEST_NAME,
            ):
                owned_cleanup.mark_completed(manifest_copy)
            cleanup_manifest = owned_cleanup.load_manifest(report_dir / owned_cleanup.MANIFEST_NAME)
            plan = owned_cleanup.plan_cleanup(
                cleanup_manifest,
                mode=owned_cleanup.MODE_DRY_RUN,
            )
            write_json(report_dir / "owned_cleanup_candidates.json", {
                "mode": owned_cleanup.MODE_DRY_RUN,
                "deleted_count": 0,
                "note": "worker dry-run; parent executes after worker exit",
                "candidates": plan,
            })
        except Exception as exc:
            write_json(report_dir / "owned_cleanup_candidates.json", {
                "mode": owned_cleanup.MODE_DRY_RUN,
                "deleted_count": 0,
                "error": str(exc)[:300],
            })
    return 0 if summary["errors"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--desktop-name", default=os.environ.get("LC_HIDDEN_DESKTOP_NAME", ""))
    parser.add_argument("--isolated-root", default=str(DEFAULT_ISOLATED_ROOT))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--cases", type=int, default=12)
    parser.add_argument("--enable-computer-use", action="store_true")
    parser.add_argument("--cancel-after-ms", type=int, default=None, help="bounded native Stop-button probe delay; evidence remains non-authoritative")
    parser.add_argument("--cancel-after-continuation", action="store_true", help="arm Stop only after a real continuation lease is observed; requires --cancel-after-ms")
    parser.add_argument("--restart-phase", type=int, choices=(1, 2), default=0, help="run one half of the owner-scoped application restart proof")
    parser.add_argument("--restart-probe", action="store_true", help="run both owner-scoped application restart phases against one isolated root")
    parser.add_argument("--use-intent", action="store_true", help="Deterministic intent compiler path: compile raw text via intent_compile Tauri command before approval/broker")
    parser.add_argument("--scenario", choices=tuple(item["id"] for item in SCENARIOS), default=None)
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("This harness requires Windows")
    if args.scenario in DISABLED_AUTO_SCENARIO_IDS:
        print(json.dumps({
            "outcome": "BLOCKED_SCENARIO_DISABLED",
            "scenario": args.scenario,
            "reason": "Calculator scenarios are disabled for hidden/automatic execution",
        }, ensure_ascii=False))
        return 2
    # The worker calls the same resource packager as the trusted launcher.
    # Re-exec before any worker is created so packaging and sidecar ABI remain
    # on the manifest-declared CPython 3.14, even when the shell's `python`
    # alias resolves to another installed interpreter.
    from tools import launch_localcomet_dev as _legacy_launcher
    _legacy_launcher.ensure_runtime_python(ROOT, script_path=Path(__file__))
    if args.worker:
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
