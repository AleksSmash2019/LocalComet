import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from modules.chatgpt_desktop_bridge import (
    focus_chatgpt_desktop_window,
    get_foreground_window_info,
    paste_prompt_after_input_focus,
)
from modules.desktop_observer import observe_desktop


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports"
PC_AGENT_REPORTS_DIR = REPORTS_DIR / "pc_agent"

ALLOWED_COMMANDS = {
    "git status --short": ["git", "status", "--short"],
    "git log -5 --oneline": ["git", "log", "-5", "--oneline"],
    "git diff --stat": ["git", "diff", "--stat"],
    "python -m py_compile modules\\pc_agent_core.py": ["python", "-m", "py_compile", "modules\\pc_agent_core.py"],
    "python -m py_compile modules\\pc_control_core.py": ["python", "-m", "py_compile", "modules\\pc_control_core.py"],
    "python -m py_compile modules\\chatgpt_desktop_bridge.py": ["python", "-m", "py_compile", "modules\\chatgpt_desktop_bridge.py"],
    "python -m py_compile modules\\desktop_action_planner.py": ["python", "-m", "py_compile", "modules\\desktop_action_planner.py"],
    "python -m py_compile LocalComet_Control_Panel.py": ["python", "-m", "py_compile", "LocalComet_Control_Panel.py"],
}

HARD_BLOCK_MARKERS = [
    "delete",
    "remove",
    "rmdir",
    "del ",
    "format",
    "payment",
    "buy",
    "checkout",
    "password",
    "login",
    "bank",
    "crypto",
    "submit",
    "powershell",
    ".exe",
    "install",
    "system settings",
    "browserprofile",
    ".env",
    "private key",
    "secret",
    "token",
    "api key",
    "удали",
    "удалить",
    "пароль",
    "логин",
    "банк",
    "оплат",
]

SENSITIVE_FILE_MARKERS = [
    ".env",
    "secret",
    "token",
    "private",
    "key",
    "browserprofile",
    "projects/browserprofile",
    "config.py",
    "core/router.py",
    "core/planner.py",
    "core/executor.py",
    "modules/self_edit.py",
    "modules/gpt_browser_bridge.py",
    "modules/browser_bridge.py",
]

SAFE_OPEN_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".py",
    ".log",
    ".csv",
    ".yaml",
    ".yml",
}


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    PC_AGENT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def hard_block_reasons(text):
    lower = str(text or "").lower()
    return [marker for marker in HARD_BLOCK_MARKERS if marker in lower]


def is_safe_project_path(path):
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        return False, None, "path could not be resolved"

    root = ROOT_DIR.resolve()

    if resolved != root and root not in resolved.parents:
        return False, resolved, "path is outside LocalAgent"

    normalized = str(resolved).replace("\\", "/").lower()

    if "projects/browserprofile" in normalized:
        return False, resolved, "browser profile is blocked"

    if any(marker in normalized for marker in SENSITIVE_FILE_MARKERS):
        return False, resolved, "path looks sensitive"

    return True, resolved, ""


def list_visible_windows():
    observation = observe_desktop(write_report=False)
    return observation.get("windows") or []


def observe_pc():
    observation = observe_desktop(write_report=True)
    return {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "foreground": get_foreground_window_info(),
        "observation": observation,
        "windows": observation.get("windows") or [],
        "report_path": observation.get("report_path") or "",
    }


def focus_chatgpt_desktop():
    return focus_chatgpt_desktop_window()


def paste_to_chatgpt_focused_input(prompt, send=False, dry_run=True):
    return paste_prompt_after_input_focus(prompt=prompt, send=send, dry_run=dry_run)


def set_clipboard_text(text, confirmed=False, dry_run=True):
    text = str(text or "")
    payload = {
        "ok": False,
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
        "text_chars": len(text),
    }

    if hard_block_reasons(text):
        payload["message"] = "STOP: clipboard text contains blocked markers."
        payload["blocked_reasons"] = hard_block_reasons(text)
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: clipboard write allowed but not executed."
        return payload

    if not confirmed:
        payload["message"] = "STOP: clipboard write requires confirmed=True."
        return payload

    from modules.chatgpt_desktop_bridge import copy_prompt_to_clipboard

    result = copy_prompt_to_clipboard(text)
    payload.update(result)
    return payload


def run_allowed_command(command, confirmed=False, dry_run=True):
    command = str(command or "").strip()
    payload = {
        "ok": False,
        "command": command,
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
        "allowed_commands": sorted(ALLOWED_COMMANDS),
    }

    blocked = hard_block_reasons(command)
    if blocked:
        payload["message"] = "STOP: command contains blocked markers."
        payload["blocked_reasons"] = blocked
        return payload

    argv = ALLOWED_COMMANDS.get(command)
    if not argv:
        payload["message"] = "STOP: command is not in the exact allowlist."
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: command is allowlisted but not executed."
        payload["argv"] = argv
        return payload

    if not confirmed:
        payload["message"] = "STOP: command execution requires confirmed=True."
        return payload

    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    payload.update({
        "ok": completed.returncode == 0,
        "message": "Command completed." if completed.returncode == 0 else "Command failed.",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    })
    return payload


def open_safe_path(path, confirmed=False, dry_run=True):
    ok, resolved, reason = is_safe_project_path(path)
    payload = {
        "ok": False,
        "path": str(path or ""),
        "resolved_path": str(resolved or ""),
        "dry_run": bool(dry_run),
        "confirmed": bool(confirmed),
    }

    if not ok:
        payload["message"] = f"STOP: unsafe path: {reason}"
        return payload

    if not resolved.exists():
        payload["message"] = "STOP: path does not exist."
        return payload

    if resolved.is_file() and resolved.suffix.lower() not in SAFE_OPEN_SUFFIXES:
        payload["message"] = "STOP: file type is not in the safe-open allowlist."
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: path is safe to open."
        return payload

    if not confirmed:
        payload["message"] = "STOP: opening a path requires confirmed=True."
        return payload

    os.startfile(str(resolved))
    payload["ok"] = True
    payload["message"] = "Path opened."
    return payload


def write_pc_report(title, payload):
    _ensure_dirs()
    path = PC_AGENT_REPORTS_DIR / f"pc_agent_{_stamp()}.md"
    lines = [
        f"# {title}",
        "",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def latest_pc_control_report():
    if not PC_AGENT_REPORTS_DIR.exists():
        return ""

    reports = sorted(PC_AGENT_REPORTS_DIR.glob("pc_agent_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
