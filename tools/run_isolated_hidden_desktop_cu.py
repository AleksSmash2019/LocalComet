from __future__ import annotations

import argparse
import asyncio
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
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
DEFAULT_ISOLATED_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "LocalCometHiddenCU20260821"
REPORT_DIR = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "isolated_hidden_desktop"
ISOLATED_VITE_PORT = int(os.environ.get("LC_ISOLATED_VITE_PORT", "1423"))
ISOLATED_CDP_PORT = int(os.environ.get("LC_ISOLATED_CDP_PORT", "9223"))
ISOLATED_WEBVIEW2_UDF_NAME = "webview2-user-data"
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
    {"id": "calculator_basic", "prompt": "Открой Калькулятор и вычисли 17 плюс 25. Покажи результат."},
    {"id": "desktop_screenshot", "prompt": "Сделай снимок экрана текущего изолированного рабочего стола и сообщи, что наблюдаешь."},
    {"id": "browser_readonly_search", "prompt": "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."},
    {"id": "file_explorer_open", "prompt": "Открой Проводник и покажи папку Документы. Не удаляй и не изменяй файлы."},
    {"id": "notepad_recovery", "prompt": "Если Блокнот открыт, переключись на него и добавь строку: recovery-check."},
    {"id": "active_window_observe", "prompt": "Определи активное окно на рабочем столе и сообщи его название."},
    {"id": "screenshot_after_actions", "prompt": "Сделай ещё один снимок экрана после предыдущих действий и сообщи, изменилось ли состояние."},
    {"id": "browser_second_readonly_search", "prompt": "В браузере найди справочную страницу о Windows Notepad. Только чтение, без публикаций и отправок."},
    {"id": "calculator_repeat", "prompt": "Открой Калькулятор и вычисли 144 разделить на 12. Сообщи результат."},
    {"id": "notepad_final_text", "prompt": "Открой Блокнот и напечатай финальную строку isolated-final-check."},
    {"id": "safe_recovery", "prompt": "Если предыдущее действие не завершилось, сообщи честное состояние и не повторяй опасные действия автоматически."},
)

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
# spawns is assigned to a private job object. Closing the last job handle —
# including on worker crash or TerminateProcess — makes the kernel terminate
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
    """Exact cargo executable identity for build parity evidence (§3.3)."""
    exe = shutil.which("cargo") or ""
    version = ""
    if exe:
        try:
            completed = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20)
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def create_worker_process(
    desktop_name: str,
    isolated_root: Path,
    report_dir: Path,
    cases: int,
    probe_only: bool = False,
    enable_computer_use: bool = False,
    scenario_id: str | None = None,
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
    env["LC_HIDDEN_ISOLATED_ROOT"] = str(isolated_root)
    env_block = environment_block(env)
    command = subprocess.list2cmdline([
        str(PYTHON), "-B", str(Path(__file__).resolve()), "--worker",
        *(["--probe-only"] if probe_only else []),
        "--desktop-name", desktop_name,
        "--isolated-root", str(isolated_root),
        "--report-dir", str(report_dir),
        "--cases", str(cases),
        *( ["--enable-computer-use"] if enable_computer_use else []),
        *( ["--scenario", scenario_id] if scenario_id else []),
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


def run_parent(args: argparse.Namespace) -> int:
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
    return click_named(root, ("Одобрить", "Разрешить", "Подтвердить", "Продолжить"))


def wait_for_window(auto: Any, timeout: float) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = uia_window(auto)
        if window is not None:
            return window
        time.sleep(0.5)
    raise TimeoutError("hidden LocalComet Tauri window did not appear")


def wait_for_composer(auto: Any, timeout: float) -> tuple[Any, Any | None]:
    deadline = time.monotonic() + timeout
    last_names: list[str] = []
    while time.monotonic() < deadline:
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
            tauri_config.write_text(tauri_text, encoding="utf-8")
            return True
        time.sleep(0.1)
    return False


def binary_provenance_path(binary: Path) -> Path:
    return Path(str(binary) + PROVENANCE_SUFFIX)


def evaluate_binary_provenance(binary: Path, expected_dev_url: str) -> dict[str, Any]:
    """Decide whether a cached isolated debug binary may be reused.

    Tauri bakes build.devUrl into the executable at compile time. A stale
    binary silently loads whatever ELSE is listening on its baked-in port —
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
    return {"usable": True, "reason": "verified", "sha256": observed, "dev_url": marked_url}


def write_binary_provenance(binary: Path, dev_url: str) -> dict[str, Any]:
    payload = {"dev_url": dev_url, "sha256": sha256(binary), "recorded_utc": utc_now()}
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
            capture_output=True, text=True, timeout=30,
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
    # duplicating 6–7 GB of Rust objects per root is not isolation and can
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
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={ISOLATED_CDP_PORT}"
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
    # One-line tool-failure tracing lands next to the other run artifacts.
    env["LOCALCOMET_TOOLCALL_TRACE"] = str(report_dir / "toolcall_trace.log")
    env["LOCALCOMET_CU_DEBUG_PATH"] = str(report_dir / "cu_debug.jsonl")
    # Owner-scoped lifecycle lease: both direct children are assigned at
    # birth; closing this handle in run_worker's finally terminates exactly
    # our tree (kernel-enforced even on crash), never a foreign process.
    cleanup_job = create_cleanup_job()
    app_log = (report_dir / "tauri_app.log").open("ab")
    expected_dev_url = expected_isolated_dev_url()
    provenance = evaluate_binary_provenance(binary, expected_dev_url)
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
        process = subprocess.Popen([npm, "run", "tauri", "dev"], cwd=runtime_app_dir, env=env, shell=False, stdout=app_log, stderr=subprocess.STDOUT)
        assign_to_cleanup_job(cleanup_job, process.pid)
        owned_root_pids.append(process.pid)
        vite_pid = None
    write_json(report_dir / "isolated_processes.json", {
        "timestamp_utc": utc_now(),
        "vite_pid": vite_pid,
        "vite_managed_by_tauri": vite_pid is None,
        "tauri_pid": process.pid,
        "binary": str(binary),
        "binary_preexisting": binary.is_file(),
        "binary_provenance": provenance,
        "expected_dev_url": expected_dev_url,
        "launch_mode": launch_mode,
        "cdp_port": ISOLATED_CDP_PORT,
        "cargo_target_dir": str(cargo_target_dir),
        "cargo_target_evidence": legacy.cargo_target_evidence(cargo_target_dir, "isolated", subkey=cargo_subkey),
        "legacy_source_local_target_used": False,
        "cargo_exe": _cargo_identity(),
        "webview_user_data_folder": str(webview_udf),
        "cleanup_job_owner_pid": os.getpid(),
    })
    return process, port_patched, cleanup_job, expected_dev_url, owned_root_pids


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
            out["cta"] = await _cdp_evaluate(ws, counter, events, "(() => { const els=[...document.querySelectorAll('button,[role=button],a')]; const m=els.filter(e=>((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).includes('Настроить локальный AI')); return m.map(e=>({tag:e.tagName, label:e.getAttribute('aria-label'), text:(e.textContent||'').trim().slice(0,60), disabled:e.disabled})); })()")
            await _cdp_evaluate(ws, counter, events, "window.__lcClicks=[]; window.addEventListener('click', e=>{ try { window.__lcClicks.push({t:Date.now(), tag:e.target.tagName, label:e.target.getAttribute('aria-label')||'', text:(e.target.textContent||'').trim().slice(0,40)}) } catch(_){} }, true); 'recorder-installed'")
            state_expr = "({clicks: (window.__lcClicks||[]).length, clickLog: (window.__lcClicks||[]).slice(-6), dialogNodes: document.querySelectorAll('[role=dialog],dialog').length, hasDrawerText: document.body.innerText.includes('Запустить выбранную'), bodySnippet: document.body.innerText.slice(0,200)})"
            # Phase 1: UIA Invoke on the CTA (same call path the smoke uses).
            root = root_getter()
            uia_clicked = click_named(root, ("Настроить локальный AI",)) if root is not None else None
            await asyncio.sleep(4)
            out["uia_click"] = {"clicked": uia_clicked}
            out["after_uia"] = await _cdp_evaluate(ws, counter, events, state_expr)
            # Phase 2: direct JS DOM click on the same CTA.
            out["js_click"] = await _cdp_evaluate(ws, counter, events, "(() => { const els=[...document.querySelectorAll('button,[role=button]')]; const m=els.find(e=>((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).includes('Настроить локальный AI')); if(!m) return 'cta-not-found'; m.click(); return 'js-clicked'; })()")
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
      as an infrastructure error — reconnect failure can never become
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

    # -- socket lifecycle -------------------------------------------------

    def _ensure_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
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
        conn = await websockets.connect(page["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024, open_timeout=10)
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
            "(() => { const d=document.querySelector('[role=dialog][data-approval-request-id]'); if(!d) return null;"
            " const wanted = " + found + ";"
            " const els=[...d.querySelectorAll('button,[role=button]')];"
            " for (const w of wanted) { const m = els.filter(e=>!e.disabled && (((e.getAttribute('aria-label')||'')+' '+(e.textContent||'')).trim().includes(w)));"
            " if (m.length) { m[0].click(); return w; } } return null; })()"
        )
        return result if isinstance(result, str) else None

    def tool_card_count(self) -> int:
        result = self.eval("document.querySelectorAll('.tool-card[aria-label]').length")
        return int(result) if isinstance(result, (int, float)) else 0

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
        # Readiness means the composer exists and accepts input. The send
        # control is disabled while the input is empty, so its EXISTENCE is
        # required here; submit_prompt waits for it to become enabled.
        result = self.eval(
            "(() => { const tas=[...document.querySelectorAll('textarea,input[type=text]')];"
            " const btns=[...document.querySelectorAll('button')].filter(b=>((b.textContent||'')+' '+(b.getAttribute('aria-label')||'')).includes('Отправить'));"
            " return {edit: tas.some(t=>!t.disabled), send: btns.length>0}; })()"
        )
        return isinstance(result, dict) and bool(result.get("edit")) and bool(result.get("send"))

    def model_status_ready(self) -> bool:
        """UI-level readiness signal: header shows the attached model state."""
        result = self.eval(
            "(() => { const t=document.body.innerText||'';"
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
        payload = json.dumps(text, ensure_ascii=False)
        # One token per LOGICAL submission, stable across transport-level
        # retries inside eval(): if a previous attempt clicked Send but its
        # response was lost with the socket, the retry must not click again.
        token = f"lc-submit-{uuid.uuid4().hex}"
        # The Svelte store enables the send control a tick AFTER the input
        # event, so insertion and the click cannot share one synchronous tick:
        # poll for the enabled aria-labelled control inside the page.
        result = self.eval(
            "(async () => { const tok=" + json.dumps(token) + ";"
            " window.__lcSubmitTokens=window.__lcSubmitTokens||{};"
            " if (window.__lcSubmitTokens[tok]) return 'already-submitted';"
            " const vis=t=>{const r=t.getBoundingClientRect();return r.width>0&&r.height>0};"
            " const tas=[...document.querySelectorAll('textarea,input[type=text]')].filter(t=>!t.disabled&&vis(t));"
            " if (!tas.length) return 'no-composer'; const ta=tas[tas.length-1];"
            " ta.focus();"
            " let inserted=false;"
            " try { inserted=document.execCommand('insertText',false," + payload + "); } catch (e) { inserted=false; }"
            " if (!inserted || !ta.value) {"
            "  const setter=Object.getOwnPropertyDescriptor(ta.constructor.prototype,'value').set;"
            "  setter.call(ta, " + payload + ");"
            " }"
            " ta.dispatchEvent(new Event('input',{bubbles:true}));"
            " const find=()=>[...document.querySelectorAll('button')].find(b=>!b.disabled && ((b.textContent||'')+' '+(b.getAttribute('aria-label')||'')).trim().includes('Отправить'));"
            " for (let i=0;i<30;i++){ const b=find(); if(b){ b.click(); window.__lcSubmitTokens[tok]=Date.now(); return 'submitted'; } await new Promise(r=>setTimeout(r,100)); }"
            " return 'no-send'; })()",
            timeout=15.0,
            await_promise=True,
        )
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
    "JSON.stringify((()=>{const cards=[...document.querySelectorAll('.tool-card')];"
    "const c=cards.length?cards[cards.length-1]:null;"
    "const p=c?.querySelector('.status-pill');"
    "const r=c?.querySelector('.cu-reason');"
    "const img=c?.querySelector('img.cu-img, img[src^=\\\"data:image\\\"]');"
    "const text=c?.textContent||'';"
    "const m=text.match(/\\{[^}]*\\}/);"
    "const d=c?.dataset||{};"
    "return {pill:p?(p.textContent||'').trim():null,"
    "reason:r?(r.textContent||'').trim().slice(0,200):'',"
    "action:m?m[0]:'',"
    "request_id:d.cuRequestId||'',action_id:d.cuActionId||'',"
    "approval_id:d.cuApprovalId||'',approval_call_id:d.cuApprovalCallId||'',"
    "input_digest:d.cuInputDigest||'',screenshot_sha256:d.cuScreenshotSha256||'',"
    "screenshot_backend:d.cuScreenshotBackend||'',screenshot_scope:d.cuScreenshotScope||'',"
    "screenshot_bytes:d.cuScreenshotBytes||'',status:d.cuStatus||'',verification:d.cuVerification||'',card_count:cards.length,"
    "screenshot_present:!!img,"
    "screenshot_src_length:img?.getAttribute('src')?.length||0};})())"
)


APPROVAL_EXPRESSION = (
    "JSON.stringify((()=>{"
    "const ds=[...document.querySelectorAll('[role=dialog][data-approval-request-id]')];"
    "const d=ds.length?ds[ds.length-1]:null;"
    "return d?{approval_request_id:d.dataset.approvalRequestId||'',"
    "model_request_id:d.dataset.modelRequestId||'',model_action_id:d.dataset.modelActionId||''}:null;})())"
)


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


def _pill_evidence(driver, min_tool_cards: int = 0) -> dict[str, Any]:
    """Read the last mounted tool-card status, never a stale prior card."""
    fallback = {"pill": None, "reason": "", "action": "", "request_id": "", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": "", "screenshot_sha256": "", "screenshot_backend": "", "screenshot_scope": "", "screenshot_bytes": "", "status": "", "verification": "", "card_count": 0, "screenshot_present": False, "screenshot_src_length": 0}
    for _ in range(3):
        parsed = _json_object(driver.eval(PILL_EXPRESSION))
        has_identity = bool(parsed and parsed.get("request_id") and parsed.get("action_id"))
        # Return a real terminal pill even if its dataset lost correlation; the
        # later evidence validator must report that identity failure explicitly.
        if parsed and parsed.get("pill") and int(parsed.get("card_count") or 0) >= min_tool_cards:
            return parsed
        time.sleep(0.4)
    return fallback


def cdp_wait_for_turn(driver: "CdpDriver", timeout: float, min_tool_cards: int = 0) -> dict:
    """Wait for a submitted turn to finish, approving the consent card.

    Dangerous computer_use actions require the decision card; the harness
    approves through the same DOM channel a user click would use. Only the
    internal approval labels are considered — never browser/payment controls.
    """
    deadline = time.monotonic() + timeout
    started = time.monotonic()
    approvals = 0
    approval_prompt: dict[str, Any] | None = None
    snippets: list[str] = []
    while time.monotonic() < deadline:
        prompt_evidence = driver.approval_evidence()
        if prompt_evidence:
            approval_prompt = prompt_evidence
        clicked = driver.click_approval(("Подтвердить", "Одобрить", "Разрешить"))
        if clicked:
            approvals += 1
            time.sleep(1)
            continue

        # Svelte enables the composer while the assistant's tool card is still
        # executing.  Treating composer_ready as terminal here loses the real
        # approval/result envelope and produces a false NOT_INDEPENDENTLY_VERIFIED
        # row (the observed v3 screenshot smoke showed exactly this defect).
        evidence = _pill_evidence(driver, min_tool_cards)
        pill = str(evidence.get("pill") or "").upper()
        if pill and pill != "WAITING":
            result = {
                "state": "terminal",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:],
            }
            result.update(evidence)
            return result

        body = driver.body_snippet(1200)
        # If the submitted turn produces no new tool card while the composer is
        # already usable, finish as an honest no-tool turn instead of waiting
        # the full model timeout. This is especially important after a prior
        # successful open_app turn: stale cards must never hold the harness for
        # five minutes or be mistaken for the follow-up type action.
        if driver.composer_ready() and time.monotonic() - started >= 20 and driver.tool_card_count() < min_tool_cards:
            result = {
                "state": "composer_ready_no_new_tool",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:] + [body],
            }
            result.update(evidence)
            return result
        # If no computer_use card appeared at all, allow a bounded honest
        # no-tool response rather than waiting the full timeout. Once the card
        # exists, only a non-WAITING pill can finish the observation.
        if driver.composer_ready() and time.monotonic() - started >= 20 and "computer_use" not in body.lower():
            result = {
                "state": "composer_ready_no_tool",
                "approvals": approvals,
                "approval_prompt": approval_prompt,
                "snippets": snippets[-3:] + [body],
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
    }
    result.update(_pill_evidence(driver, min_tool_cards))
    return result


SCENARIO_EXPECTED_TEXT = {
    "notepad_open_type": "LocalComet isolated smoke test.",
    "notepad_recovery": "recovery-check.",
    "notepad_final_text": "isolated-final-check.",
}


SCENARIO_EXPECTED_PROCESS = {
    "notepad_open_type": ["notepad.exe"],
    "calculator_basic": ["calculatorapp.exe"],
    "file_explorer_open": ["explorer.exe"],
    "browser_readonly_search": ["chrome.exe", "msedge.exe", "firefox.exe"],
    "notepad_recovery": ["notepad.exe"],
    "notepad_final_text": ["notepad.exe"],
}


def _process_present(image_names):
    """Host-side postcondition evidence: is any expected image running?"""
    if not image_names:
        return None  # scenario has no spawn expectation
    try:
        output = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.lower()
    except Exception:
        return None
    return any(name.lower() in output for name in image_names)


def _tool_card_evidence(driver, min_tool_cards: int = 0) -> dict[str, Any]:
    """UI-level truth from the last new tool card, with bounded CDP retries."""
    fallback = {"pill": None, "reason": "", "action": "", "request_id": "", "action_id": "", "approval_id": "", "approval_call_id": "", "input_digest": "", "screenshot_sha256": "", "screenshot_backend": "", "screenshot_scope": "", "screenshot_bytes": "", "status": "", "verification": "", "card_count": 0, "screenshot_present": False, "screenshot_src_length": 0}
    for _ in range(4):
        parsed = _json_object(driver.eval(PILL_EXPRESSION))
        has_identity = bool(parsed and parsed.get("request_id") and parsed.get("action_id"))
        if parsed and parsed.get("pill") and int(parsed.get("card_count") or 0) >= min_tool_cards and (min_tool_cards <= 0 or has_identity):
            return parsed
        time.sleep(0.6)
    return fallback


def _valid_id(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(pattern, value))


def validate_correlation(observation: dict[str, Any], evidence: dict[str, Any], approvals: int) -> dict[str, Any]:
    """Validate identities from mounted UI evidence; never synthesize missing IDs."""
    if approvals <= 0:
        return {"status": "not_required", "ok": True, "checks": {}}
    prompt = observation.get("approval_prompt") if isinstance(observation.get("approval_prompt"), dict) else {}
    checks = {
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


def validate_screenshot_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "present": bool(evidence.get("screenshot_present")),
        "sha256": _valid_id(evidence.get("screenshot_sha256"), r"[0-9a-f]{64}"),
        "backend": evidence.get("screenshot_backend") in {"imagegrab", "gdi_bitblt", "printwindow"},
        "scope": evidence.get("screenshot_scope") in {"desktop", "window"},
        "bytes": str(evidence.get("screenshot_bytes") or "").isdigit() and int(evidence.get("screenshot_bytes") or 0) > 0,
    }
    return {"ok": all(checks.values()), "checks": checks}


def classify_case(
    pill: str | None,
    approvals: int,
    process_present,
    *,
    correlation_ok: bool = True,
    text_ok: bool | None = None,
    screenshot_ok: bool | None = None,
) -> str:
    if pill == "PASS":
        if process_present is False or (approvals > 0 and not correlation_ok):
            return "NOT_INDEPENDENTLY_VERIFIED"
        if text_ok is False or screenshot_ok is False:
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
    # Ownership manifest BEFORE any child resource is created (§4.1). The
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
        isolated_root, report_dir, cargo_target_dir=cargo_target_dir, cargo_subkey=cargo_subkey,
    )
    # Manifest copies learn the recorded child roots after spawn (§4.4).
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
    startup = {"started_utc": utc_now(), "worker_pid": os.getpid(), "launcher_pid": launch.pid, "isolated_root": str(isolated_root), "desktop_name": os.environ.get("LC_HIDDEN_DESKTOP_NAME", ""), "reader_startup_attachment": reader_startup_attachment, "isolated_vite_port": ISOLATED_VITE_PORT, "expected_dev_url": expected_dev_url, "port_patched": port_patched, "enable_computer_use": args.enable_computer_use, "scenario": args.scenario}
    write_json(report_dir / "isolated_launch.json", startup)
    summary = {"requested_cases": args.cases, "attempted": 0, "submitted": 0, "completed_observations": 0, "blocked": 0, "errors": 0, "model_ready": False, "computer_use_permissions_enabled": False, "verified_success": 0, "verified_blocked": 0, "verified_failed": 0, "pending_terminal": 0, "not_independently_verified": 0, "infrastructure_error": 0, "malformed_result": 0}
    try:
        root = wait_for_window(auto, 600)
        if not isolation_selfcheck(report_dir, launch.pid):
            summary["blocked"] = args.cases
            summary["finished_utc"] = utc_now()
            write_json(report_dir / "isolated_hidden_summary.json", summary)
            print(json.dumps({"outcome": "BLOCKED_ISOLATION_VIOLATION"}, ensure_ascii=False))
            return 2
        # Plan P0.1: the CDP page target is verified BEFORE any interaction.
        # The environment variable being set is not evidence; only an
        # answering endpoint on OUR port serving OUR dev-server URL counts.
        try:
            verification = verify_isolated_cdp_startup(report_dir)
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
                write_binary_provenance(rebuilt_binary, expected_dev_url)
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
        # The early CTA click can land before the webview finishes hydration;
        # the retry loop below re-opens the drawer as needed.
        time.sleep(8)
        driver.click_texts(("Настроить локальный AI",))
        time.sleep(2)
        # Model loading can take several minutes for the managed runtime.
        model_ready = False
        progress_path = report_dir / "model_setup_progress.jsonl"
        deadline = time.monotonic() + 600
        last_progress = 0.0
        while time.monotonic() < deadline:
            # Primary signal is an enabled composer; the header status text is
            # the fallback for the auto-setup path where no drawer ever opens.
            if driver.composer_ready() or driver.model_status_ready():
                model_ready = True
                break
            if driver.dialog_open():
                # Primary drawer action; 'Запустить выбранную' covers the
                # alternate state with a preselected launchable model.
                driver.click_in_dialog(("Запустить выбранную", "Подключить модель"))
            else:
                driver.click_texts(("Настроить локальный AI",))
            if time.monotonic() - last_progress > 15:
                last_progress = time.monotonic()
                with progress_path.open("a", encoding="utf-8") as progress:
                    progress.write(json.dumps({
                        "ts": utc_now(),
                        "target": getattr(driver, "target_url", ""),
                        "drawer": driver.dialog_open(),
                        "snippet": driver.body_snippet(400),
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
                driver.click_in_dialog(("Запустить выбранную", "Подключить модель", "Готово", "Закрыть"))
                driver.click_texts(("Чат",))
                time.sleep(2)
        if not model_ready or not driver.composer_ready():
            write_json(report_dir / "model_setup_blocked.json", {
                "timestamp_utc": utc_now(),
                "error_type": "TimeoutError",
                "error": "composer did not become enabled (CDP check)",
                "body_snippet": driver.body_snippet(800),
                "status_names": named_status(uia_window(auto))[-120:] if uia_window(auto) else [],
            })
        if model_ready and args.enable_computer_use:
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
                    if driver.dialog_open():
                        driver.click_in_dialog(("Запустить выбранную", "Подключить модель", "Готово", "Закрыть"))
                    else:
                        driver.click_texts(("Настроить локальный AI", "Чат"))
                    time.sleep(3)
                for _ in range(8):
                    if driver.composer_ready():
                        break
                    driver.click_in_dialog(("Запустить выбранную", "Подключить модель", "Готово", "Закрыть"))
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
            for index in range(args.cases):
                if args.scenario:
                    scenario = next(item for item in SCENARIOS if item["id"] == args.scenario)
                else:
                    scenario = SCENARIOS[index % len(SCENARIOS)]
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
                        elif not driver.submit_prompt(scenario["prompt"]):
                            raise RuntimeError("composer submit failed")
                        else:
                            summary["submitted"] += 1
                            row["outcome"] = "SUBMITTED"
                            initial_tool_card_count = driver.tool_card_count()
                            observations: list[dict[str, Any]] = [cdp_wait_for_turn(driver, 300, initial_tool_card_count + 1)]
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
                                    "screenshot_sha256": observed_turn.get("screenshot_sha256", ""),
                                    "screenshot_backend": observed_turn.get("screenshot_backend", ""),
                                    "screenshot_scope": observed_turn.get("screenshot_scope", ""),
                                    "screenshot_bytes": observed_turn.get("screenshot_bytes", ""),
                                    "screenshot_present": bool(observed_turn.get("screenshot_present")),
                                    "screenshot_src_length": int(observed_turn.get("screenshot_src_length") or 0),
                                    "card_count": int(observed_turn.get("card_count") or 0),
                                    "status": observed_turn.get("status", ""),
                                    "verification": observed_turn.get("verification", ""),
                                }

                            expected = SCENARIO_EXPECTED_PROCESS.get(scenario["id"])
                            expected_text = SCENARIO_EXPECTED_TEXT.get(scenario["id"])
                            proc_present = _process_present(expected)
                            text_proof = (
                                read_hidden_window_text(auto, expected_text, timeout=3.0)
                                if expected_text
                                else {"ok": True, "status": "not_required"}
                            )
                            first_evidence = evidence_from_observation(observations[0])
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
                                follow_up_baseline = driver.tool_card_count()
                                if driver.submit_prompt(follow_up):
                                    summary["submitted"] += 1
                                    observations.append(cdp_wait_for_turn(driver, 300, follow_up_baseline + 1))
                                    if observations[-1].get("state") in {"terminal", "composer_ready", "composer_ready_no_tool", "composer_ready_no_new_tool"}:
                                        summary["completed_observations"] += 1
                                    text_proof = read_hidden_window_text(auto, expected_text, timeout=12.0)
                                else:
                                    text_proof["reason"] = "follow-up prompt submit failed"

                            indexed = [(turn, evidence_from_observation(turn)) for turn in observations]
                            evidence = next(
                                (item[1] for item in indexed if item[1].get("approval_id") and item[1].get("input_digest")),
                                indexed[-1][1],
                            )
                            # Prefer terminal evidence from the last turn for the
                            # displayed outcome, but retain first-turn broker IDs.
                            final_evidence = indexed[-1][1]
                            if not final_evidence.get("pill"):
                                late = _tool_card_evidence(driver, initial_tool_card_count + len(observations))
                                if late.get("pill"):
                                    final_evidence = late
                            approvals = sum(int(turn.get("approvals") or 0) for turn in observations)
                            correlation_turn = next(
                                (turn for turn, item in indexed if item.get("approval_id") and item.get("input_digest")),
                                observations[0],
                            )
                            correlation = validate_correlation(correlation_turn, evidence, approvals)
                            screenshot_required = scenario["id"] in {"desktop_screenshot", "screenshot_after_actions"}
                            screenshot_evidence = validate_screenshot_evidence(final_evidence) if screenshot_required else {"ok": True, "status": "not_required", "checks": {}}
                            row["observation"] = observations[-1]
                            row["observations"] = observations
                            row["body_snippet"] = driver.body_snippet(500)
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
                            row["process_evidence"] = {
                                "expected_any": expected,
                                "present": proc_present,
                            }
                            classification = classify_case(
                                str(final_evidence.get("pill") or "").upper() or None,
                                approvals,
                                proc_present,
                                correlation_ok=bool(correlation.get("ok")),
                                text_ok=text_proof.get("ok") if expected_text else None,
                                screenshot_ok=screenshot_evidence.get("ok") if screenshot_required else None,
                            )
                            row["final_classification"] = classification
                            summary_key = classification.lower()
                            summary[summary_key] = summary.get(summary_key, 0) + 1
                    except Exception as exc:
                        summary["errors"] += 1
                        row["outcome"] = "ERROR"
                        row["final_classification"] = "INFRASTRUCTURE_ERROR"
                        summary["infrastructure_error"] = summary.get("infrastructure_error", 0) + 1
                        row["error_type"] = type(exc).__name__
                        row["error"] = str(exc)[:600]
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
        # — even if this worker crashed. Foreign/user processes were never
        # assigned to the job and remain unreachable by construction.
        cleanup = cleanup_owned_process_tree(owned_root_pids)
        write_json(report_dir / "owned_cleanup.json", cleanup)
        try:
            kernel32.CloseHandle(cleanup_job)
        except Exception:
            pass
        # Owner-scoped cleanup (§4.5): final evidence is already written above.
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
    parser.add_argument("--scenario", choices=tuple(item["id"] for item in SCENARIOS), default=None)
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("This harness requires Windows")
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
