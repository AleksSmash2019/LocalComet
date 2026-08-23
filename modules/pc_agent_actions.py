from modules.json_io import format_payload as format_action_result, write_json as _safe_write_json
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import ctypes
import json
import os
import queue
import subprocess
import threading
import time

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
ACTIONS_REPORTS_DIR = REPORTS_DIR / "pc_agent_actions"
NOTES_DIR = PROJECTS_DIR / "PCAgent" / "Notes"


def _user_home_directory() -> Path:
    for variable in ("USERPROFILE", "HOME", "HOMEDRIVE"):
        value = str(os.environ.get(variable) or "").strip()
        if value:
            candidate = Path(value)
            if variable != "HOMEDRIVE" or os.environ.get("HOMEPATH"):
                if variable == "HOMEDRIVE":
                    candidate = Path(value + str(os.environ.get("HOMEPATH") or ""))
                return candidate
    local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_appdata:
        return Path(local_appdata).parent
    return ROOT_DIR


USER_HOME_DIR = _user_home_directory()


APP_ALLOWLIST = {
    "notepad": ["notepad.exe"],
    "блокнот": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calculator": ["calc.exe"],
    "калькулятор": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "проводник": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "paint.exe": ["mspaint.exe"],
}

FOLDER_ALLOWLIST = {
    "root": ROOT_DIR,
    "проект": ROOT_DIR,
    "projects": PROJECTS_DIR,
    "проекты": PROJECTS_DIR,
    "reports": REPORTS_DIR,
    "отчеты": REPORTS_DIR,
    "selfedit": PROJECTS_DIR / "SelfEdit",
    "relay": PROJECTS_DIR / "ChatGPTRelay",
    "downloads": USER_HOME_DIR / "Downloads",
    "загрузки": USER_HOME_DIR / "Downloads",
    "pcagent": PROJECTS_DIR / "PCAgent",
    "pc agent": PROJECTS_DIR / "PCAgent",
    "actions": ACTIONS_REPORTS_DIR,
}

BLOCKED_TERMS = [
    "cmd",
    "powershell",
    "shell",
    "terminal",
    "regedit",
    "registry",
    "format",
    "delete",
    "remove",
    "rmdir",
    "del ",
    "rm -rf",
    "удали",
    "стереть",
    "формат",
    "реестр",
    "пароль",
    "password",
    "token",
    "secret",
    "private key",
    "приватный ключ",
    "оплати",
    "payment",
    "банк",
    "bank",
    "casino",
    "ставка",
    "login",
    "логин",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()



def _safe_write_text(path: Path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")
    return str(path)


def classify_action_request(text):
    lower = _norm(text)
    matched = [term for term in BLOCKED_TERMS if term in lower]
    return {
        "safe": not matched,
        "blocked_reason": "Опасные термины: " + ", ".join(matched) if matched else "",
        "matched_terms": matched,
    }


def pc_actions_status():
    payload = {
        "ok": True,
        "mode": "pc_agent_actions",
        "generated_at": _now(),
        "apps": sorted(APP_ALLOWLIST.keys()),
        "folders": sorted(FOLDER_ALLOWLIST.keys()),
        "commands": [
            "pc actions статус",
            "pc actions список",
            "pc actions dry open app <name>",
            "pc actions open app <name>",
            "pc actions dry open folder <name>",
            "pc actions open folder <name>",
            "pc actions note <text>",
            "pc actions report",
        ],
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }
    set_value("pc_agent_actions_status", payload)
    return payload


def format_pc_actions_status(payload=None):
    payload = payload or pc_actions_status()
    lines = [
        "PC Agent Actions Pack:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "Доступные приложения:",
        "- " + ", ".join(payload.get("apps", [])),
        "",
        "Доступные папки:",
        "- " + ", ".join(payload.get("folders", [])),
        "",
        "Команды:",
    ]
    lines.extend("- " + command for command in payload.get("commands", []))
    return "\n".join(lines)


def list_actions():
    return {
        "ok": True,
        "apps": APP_ALLOWLIST,
        "folders": {key: str(value) for key, value in FOLDER_ALLOWLIST.items()},
        "blocked_terms": BLOCKED_TERMS,
        "examples": [
            "pc actions dry open app notepad",
            "pc actions open app notepad",
            "pc actions open folder projects",
            "pc actions note План: проверить агент",
            "pc codex план открыть блокнот и написать заметку",
        ],
    }


def _resolve_app(name):
    key = _norm(name)
    if key not in APP_ALLOWLIST:
        return None
    return APP_ALLOWLIST[key]


def _resolve_folder(name):
    key = _norm(name)
    if key not in FOLDER_ALLOWLIST:
        return None
    path = FOLDER_ALLOWLIST[key]
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def _shell_execute_open(command_str: str) -> bool:
    """Launch an allowlisted GUI app through the Windows Shell broker."""
    if os.name != "nt":
        return False
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "open",
            str(command_str),
            None,
            None,
            1,
        )
        return int(result) > 32
    except Exception:
        return False


def _shell_execute_open_bounded(command_str: str, timeout: float = 2.0):
    """Keep a shell broker hang from blocking the sidecar IPC loop."""
    result_queue = queue.Queue(maxsize=1)

    def worker():
        result_queue.put(_shell_execute_open(command_str))

    thread = threading.Thread(target=worker, name="computer-use-shell-execute", daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return None
    return result_queue.get_nowait()


def _process_has_visible_window(pid: int) -> bool:
    """Return whether a Windows process currently owns a visible top-level window."""
    if os.name != "nt" or pid <= 0:
        return False
    try:
        user32 = ctypes.windll.user32
        found = False
        enum_windows = user32.EnumWindows
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            process_id = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if int(process_id.value) == pid:
                found = True
                return False
            return True

        enum_windows(callback_type(callback), 0)
        return found
    except Exception:
        return False


def _find_visible_process_for_image(image_name: str) -> bool:
    """Find a visible top-level window for an allowlisted executable image."""
    if os.name != "nt":
        return False
    expected = Path(str(image_name)).name.lower()
    if not expected:
        return False
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        found = False
        enum_windows = user32.EnumWindows
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            process_id = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if not process_id.value:
                return True
            handle = kernel32.OpenProcess(0x1000, False, process_id.value)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return True
            try:
                buffer = ctypes.create_unicode_buffer(512)
                size = ctypes.c_ulong(len(buffer))
                if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    found = Path(buffer.value).name.lower() == expected
            finally:
                kernel32.CloseHandle(handle)
            return not found

        enum_windows(callback_type(callback), 0)
        return found
    except Exception:
        return False


# The shell's own always-visible windows (taskbar, tray) satisfy any
# image-name scan for explorer.exe, so an image match can never verify an
# Explorer launch: only the exact spawned pid or a folder-window title
# check is accepted as readiness evidence.
_SHELL_IMAGE_NAMES = {"explorer.exe"}


def _wait_for_app_readiness(*, image_name: str, pid: int | None = None, timeout: float = 1.5) -> bool:
    """Bounded post-launch verification; never turns ShellExecute acceptance into success."""
    deadline = time.monotonic() + max(0.1, min(float(timeout), 3.0))
    accept_by_image = Path(str(image_name)).name.lower() not in _SHELL_IMAGE_NAMES
    while time.monotonic() < deadline:
        if (pid is not None and _process_has_visible_window(pid)) or (
            pid is None and accept_by_image and _find_visible_process_for_image(image_name)
        ):
            return True
        time.sleep(0.1)
    return False


def _folder_window_visible(folder_name: str) -> bool:
    """Return whether a visible Explorer window currently shows the folder.

    Explorer reuses a single broker process, so process spawn proves nothing;
    readiness must be a visible CabinetWClass/ExploreWClass window whose title
    contains the folder name (Explorer titles windows by folder name).
    """
    if os.name != "nt":
        return False
    needle = str(folder_name or "").strip().lower()
    if not needle:
        return False
    try:
        user32 = ctypes.windll.user32
        found = False
        enum_windows = user32.EnumWindows
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            class_buffer = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
            if class_buffer.value not in ("CabinetWClass", "ExploreWClass"):
                return True
            title_buffer = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            if needle in title_buffer.value.lower():
                found = True
                return False
            return True

        enum_windows(callback_type(callback), 0)
        return found
    except Exception:
        return False


def _wait_for_folder_readiness(*, folder_name: str, timeout: float = 1.5) -> bool:
    """Bounded post-launch verification for Explorer folder windows."""
    deadline = time.monotonic() + max(0.1, min(float(timeout), 3.0))
    while time.monotonic() < deadline:
        if _folder_window_visible(folder_name):
            return True
        time.sleep(0.1)
    return False


def open_app(name, dry_run=True):
    safety = classify_action_request(name)
    command = _resolve_app(name)
    payload = {
        "ok": False,
        "action": "open_app",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "command": command,
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not command:
        payload["result"] = "App is not allowlisted."
        payload["allowed"] = sorted(APP_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: приложение не запущено."
        return _remember(payload)

    if os.name == "nt":
        command_str = command[0] if isinstance(command, (list, tuple)) else str(command)
        shell_result = _shell_execute_open_bounded(command_str)
        if shell_result:
            ready = _wait_for_app_readiness(image_name=command_str)
            payload.update({
                "ok": ready,
                "status": "completed" if ready else "launch_pending",
                "launch_mode": "shell_execute_w",
                "verification": "verified" if ready else "pending",
                "result": "Приложение запущено и окно подтверждено." if ready else "Команда запуска передана; окно ещё не подтверждено.",
            })
            return _remember(payload)
        if shell_result is None:
            payload.update({
                "ok": True,
                "status": "launch_pending",
                "verification": "pending",
                "launch_mode": "shell_execute_w_pending",
                "result": "Команда запуска передана приложению.",
            })
            return _remember(payload)

    launch_kwargs = {
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    launch_attempts = [launch_kwargs]
    if os.name == "nt":
        # Do not inherit the sidecar's length-prefixed IPC handles. Prefer a
        # detached breakaway process, then fall back when the host job forbids
        # breakaway (ERROR_ACCESS_DENIED) or imposes a process quota (1816).
        breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
        detached = dict(launch_kwargs)
        detached["creationflags"] = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | breakaway
        )
        grouped = dict(launch_kwargs)
        grouped["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        plain = dict(launch_kwargs)
        plain["creationflags"] = 0
        minimal = {
            "shell": False,
            "creationflags": 0,
        }
        launch_attempts = [detached, grouped, plain, minimal]
    result_queue = queue.Queue(maxsize=1)

    def launch_worker():
        process = None
        last_error = None
        launch_mode = "allowlisted_process"
        for attempt in launch_attempts:
            try:
                process = subprocess.Popen(command, **attempt)
                break
            except OSError as exc:
                last_error = exc
        if process is None and os.name == "nt" and str(command).lower() != "explorer.exe":
            # Explorer is the user-session shell broker. When the sidecar is
            # hosted in a constrained job, ask the existing shell to activate
            # the allowlisted executable as a final bounded fallback.
            try:
                command_args = list(command) if isinstance(command, (list, tuple)) else [str(command)]
                process = subprocess.Popen(
                    ["explorer.exe", *command_args],
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=0,
                )
                launch_mode = "explorer_shell_broker"
            except OSError as broker_error:
                last_error = broker_error
        result_queue.put((process, last_error, launch_mode))

    worker = threading.Thread(target=launch_worker, name="computer-use-open-app", daemon=True)
    worker.start()
    worker.join(timeout=2.0)
    if worker.is_alive():
        payload.update({
            "ok": True,
            "status": "launch_pending",
            "verification": "pending",
            "launch_mode": "background_allowlisted_launcher",
            "result": "Команда запуска передана приложению.",
        })
        return _remember(payload)

    process, last_error, launch_mode = result_queue.get_nowait()
    if process is None:
        payload["result"] = "Не удалось запустить приложение."
        payload["error"] = str(last_error or "launcher failed")
        return _remember(payload)
    ready = _wait_for_app_readiness(image_name=str(command[0] if isinstance(command, (list, tuple)) else command), pid=process.pid)
    payload["ok"] = ready
    payload["pid"] = process.pid
    payload["status"] = "completed" if ready else "launch_pending"
    payload["launch_mode"] = launch_mode
    payload["verification"] = "verified" if ready else "pending"
    payload["result"] = "Приложение запущено и окно подтверждено." if ready else "Процесс запущен; окно ещё не подтверждено."
    return _remember(payload)


def open_folder(name, dry_run=True):
    safety = classify_action_request(name)
    path = _resolve_folder(name)
    payload = {
        "ok": False,
        "action": "open_folder",
        "name": name,
        "dry_run": bool(dry_run),
        "safety": safety,
        "path": str(path) if path else "",
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if not path:
        payload["result"] = "Folder is not allowlisted."
        payload["allowed"] = sorted(FOLDER_ALLOWLIST.keys())
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: папка не открыта."
        return _remember(payload)

    try:
        subprocess.Popen(["explorer.exe", str(path)], shell=False)
    except OSError as exc:
        payload["result"] = "Не удалось открыть папку."
        payload["error"] = str(exc)
        return _remember(payload)
    # Explorer reuses a broker process, so spawn acceptance alone is not
    # readiness: verify a visible folder window within a bounded wait.
    ready = _wait_for_folder_readiness(folder_name=Path(path).name)
    payload["ok"] = ready
    payload["status"] = "completed" if ready else "launch_pending"
    payload["verification"] = "verified" if ready else "pending"
    payload["result"] = "Папка открыта, окно подтверждено." if ready else "Команда открытия передана; окно папки ещё не подтверждено."
    return _remember(payload)


def create_note(text, dry_run=False):
    safety = classify_action_request(text)
    payload = {
        "ok": False,
        "action": "create_note",
        "dry_run": bool(dry_run),
        "safety": safety,
        "text_preview": str(text or "")[:500],
    }

    if not safety.get("safe"):
        payload["result"] = "BLOCKED."
        return _remember(payload)

    if dry_run:
        payload["ok"] = True
        payload["result"] = "DRY_RUN: заметка не создана."
        return _remember(payload)

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"note_{_stamp()}.md"
    body = "\n".join([
        "# PC Agent Note",
        "",
        f"- generated_at: {_now()}",
        "",
        str(text or "").strip(),
        "",
    ])
    _safe_write_text(path, body)
    payload["ok"] = True
    payload["path"] = str(path)
    payload["result"] = "Заметка создана."
    return _remember(payload)


def create_actions_report(note=""):
    ACTIONS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": pc_actions_status(),
        "last_action": get_value("pc_agent_actions_last_action", ""),
        "last_result": get_value("pc_agent_actions_last_result", ""),
    }

    json_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.json"
    md_path = ACTIONS_REPORTS_DIR / f"pc_agent_actions_report_{_stamp()}.md"

    _safe_write_json(json_path, payload)
    md = [
        "# PC Agent Actions Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_pc_actions_status(payload["status"]),
        "```",
        "",
        "## Last Result",
        "",
        "```json",
        json.dumps(payload["last_result"], ensure_ascii=False, indent=2),
        "```",
    ]
    _safe_write_text(md_path, "\n".join(md))

    result = {"ok": True, "report": str(md_path), "json": str(json_path)}
    set_value("pc_agent_actions_last_report", result)
    return result


def _remember(payload):
    set_value("pc_agent_actions_last_action", payload.get("action", "unknown"))
    set_value("pc_agent_actions_last_result", payload)
    return payload


def dispatch_action(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc actions", "pc actions status", "pc actions статус", "pc action status", "actions status"}:
        return pc_actions_status()

    if lower in {"pc actions список", "pc actions list", "pc action list", "список действий"}:
        return list_actions()

    if lower in {"pc actions report", "pc actions отчет", "actions report"}:
        return create_actions_report("manual report from panel chat")

    prefixes = [
        ("pc actions dry open app ", "dry_open_app"),
        ("pc action dry open app ", "dry_open_app"),
        ("pc actions open app ", "open_app"),
        ("pc action open app ", "open_app"),
        ("pc actions dry open folder ", "dry_open_folder"),
        ("pc action dry open folder ", "dry_open_folder"),
        ("pc actions open folder ", "open_folder"),
        ("pc action open folder ", "open_folder"),
        ("pc actions note ", "note"),
        ("pc action note ", "note"),
        ("создай заметку ", "note"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "dry_open_app":
                return open_app(value, dry_run=True)
            if action == "open_app":
                return open_app(value, dry_run=False)
            if action == "dry_open_folder":
                return open_folder(value, dry_run=True)
            if action == "open_folder":
                return open_folder(value, dry_run=False)
            if action == "note":
                return create_note(value, dry_run=False)

    return {
        "ok": False,
        "action": "unknown",
        "result": "Не понял PC Actions команду.",
        "help": list_actions(),
    }


