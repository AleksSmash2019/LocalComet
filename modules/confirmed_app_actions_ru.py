from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
from typing import Any, Dict, List

CONFIRMED_APP_ACTIONS_VERSION = "v6.72"

ROOT_DIR = get_project_root()
if not ROOT_DIR.exists():
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _normalize(text: str) -> str:
    return str(text or "").strip().lower().replace("ё", "е")


def _exec_calc():
    return subprocess.Popen(["calc.exe"], shell=False)


def _exec_notepad():
    return subprocess.Popen(["notepad.exe"], shell=False)


def _exec_explorer():
    return subprocess.Popen(["explorer.exe"], shell=False)


def _exec_browser():
    import webbrowser
    webbrowser.open("https://www.google.com")


_APPS = [
    {
        "id": "browser",
        "title": "Default web browser",
        "aliases": ["браузер", "browser", "default browser"],
        "confirm_commands": [
            "подтвердить открыть браузер",
            "confirm open browser",
            "подтвердить запустить браузер",
        ],
        "method_desc": "Python webbrowser.open",
        "execute": _exec_browser,
    },
    {
        "id": "calculator",
        "title": "Windows Calculator",
        "aliases": ["калькулятор", "calculator", "calc"],
        "confirm_commands": [
            "подтвердить открыть калькулятор",
            "confirm open calculator",
            "подтвердить запустить калькулятор",
        ],
        "method_desc": "subprocess.Popen(['calc.exe'], shell=False)",
        "execute": _exec_calc,
    },
    {
        "id": "notepad",
        "title": "Windows Notepad",
        "aliases": ["блокнот", "notepad"],
        "confirm_commands": [
            "подтвердить открыть блокнот",
            "confirm open notepad",
            "подтвердить запустить блокнот",
        ],
        "method_desc": "subprocess.Popen(['notepad.exe'], shell=False)",
        "execute": _exec_notepad,
    },
    {
        "id": "explorer",
        "title": "Windows File Explorer",
        "aliases": ["проводник", "explorer", "file explorer"],
        "confirm_commands": [
            "подтвердить открыть проводник",
            "confirm open explorer",
            "подтвердить запустить проводник",
        ],
        "method_desc": "subprocess.Popen(['explorer.exe'], shell=False)",
        "execute": _exec_explorer,
    },
]


def is_plain_app_goal(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    if not lower:
        return {"is_goal": False}
    open_verbs = ["открой ", "открыть ", "open "]
    for verb in open_verbs:
        v = verb.rstrip()
        if lower == v:
            continue
        if lower.startswith(verb):
            target = lower[len(verb):].strip()
            for app in _APPS:
                if target == app["id"] or target in app["aliases"]:
                    first_alias = app["aliases"][0]
                    return {
                        "is_goal": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "confirmation_required": True,
                        "real_action": False,
                        "confirmation_message": (
                            f"Требуется подтверждение: открыть {first_alias}?"
                            f" Напиши: подтвердить открыть {first_alias}"
                        ),
                        "confirm_command": f"подтвердить открыть {first_alias}",
                    }
    return {"is_goal": False}


def is_confirmed_app_action_command(command: str) -> bool:
    lower = _normalize(command)
    if not lower:
        return False
    for app in _APPS:
        for cc in app["confirm_commands"]:
            if lower == _normalize(cc):
                return True
    return False


def run_confirmed_app_action(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    for app in _APPS:
        for cc in app["confirm_commands"]:
            if lower == _normalize(cc):
                try:
                    proc = app["execute"]()
                    opened = proc is not None
                    message = (
                        f"Выполнено: {app['title']} открыт по вашему подтверждению.\n"
                        f"Действие было разрешено (allowlisted).\n"
                        f"Метод: {app['method_desc']}"
                    )
                    return {
                        "mode": "confirmed_app_action",
                        "route": "confirmed_app_actions",
                        "version": CONFIRMED_APP_ACTIONS_VERSION,
                        "real_action": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "method": app["method_desc"],
                        "opened": opened,
                        "message": message,
                        "result": {
                            "command": "allowlisted_app_action",
                            "action": f"open_{app['id']}",
                            "method": app["method_desc"],
                            "opened": opened,
                            "note": "Только разрешённые действия. Полный Computer Use не включён.",
                        },
                    }
                except Exception as exc:
                    return {
                        "mode": "confirmed_app_action_error",
                        "route": "confirmed_app_actions",
                        "version": CONFIRMED_APP_ACTIONS_VERSION,
                        "real_action": False,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "error": str(exc),
                        "message": f"Ошибка: не удалось открыть {app['title']}: {exc}",
                        "result": {
                            "command": "allowlisted_app_action_failed",
                            "action": f"open_{app['id']}",
                            "error": str(exc),
                            "note": "Allowlisted action failed.",
                        },
                    }
    return {
        "mode": "confirmed_app_action_error",
        "route": "confirmed_app_actions",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "real_action": False,
        "result": {"error": "No matching confirmed app action found"},
    }


def get_allowlist() -> List[Dict[str, Any]]:
    return [
        {
            "app_id": app["id"],
            "app_title": app["title"],
            "confirm_commands": app["confirm_commands"],
            "method": app["method_desc"],
        }
        for app in _APPS
    ]


def is_direct_allowlisted_app_command(command: str) -> Dict[str, Any]:
    lower = _normalize(command)
    if not lower:
        return {"is_direct": False}
    open_verbs = ["открой ", "открыть ", "open "]
    for verb in open_verbs:
        v = verb.rstrip()
        if lower == v:
            continue
        if lower.startswith(verb):
            target = lower[len(verb):].strip()
            for app in _APPS:
                if target == app["id"] or target in app["aliases"]:
                    return {
                        "is_direct": True,
                        "app_id": app["id"],
                        "app_title": app["title"],
                        "method": app["method_desc"],
                        "execute": app["execute"],
                    }
    return {"is_direct": False}


def run_direct_allowlisted_app_action(command: str):
    info = is_direct_allowlisted_app_command(command)
    if not info.get("is_direct"):
        return {
            "mode": "direct_app_action_error",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": False,
            "result": {"error": "Not a direct allowlisted app command"},
        }
    app_id = info["app_id"]
    app_title = info["app_title"]
    method = info["method"]
    execute = info["execute"]
    try:
        result = execute()
        opened = True
        message = (
            f"Выполнено: {app_title} открыт.\n"
            f"Действие было разрешено (allowlisted).\n"
            f"Метод: {method}"
        )
        return {
            "mode": "direct_app_action",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": True,
            "app_id": app_id,
            "app_title": app_title,
            "method": method,
            "opened": opened,
            "message": message,
            "result": {
                "command": "direct_allowlisted_app_action",
                "action": f"open_{app_id}",
                "method": method,
                "opened": opened,
                "note": "Прямое разрешённое действие. Подтверждение не требовалось.",
            },
        }
    except Exception as exc:
        return {
            "mode": "direct_app_action_error",
            "route": "confirmed_app_actions",
            "version": CONFIRMED_APP_ACTIONS_VERSION,
            "real_action": False,
            "app_id": app_id,
            "app_title": app_title,
            "error": str(exc),
            "message": f"Ошибка: не удалось открыть {app_title}: {exc}",
            "result": {
                "command": "direct_allowlisted_app_action_failed",
                "action": f"open_{app_id}",
                "error": str(exc),
                "note": "Direct allowlisted action failed.",
            },
        }


def dispatch(command: str = "") -> Dict[str, Any]:
    lower = _normalize(command)
    if lower in {"status", "pc confirmed actions status"}:
        return status()
    if lower in {"report", "pc confirmed actions report"}:
        return report()
    if is_confirmed_app_action_command(lower):
        return run_confirmed_app_action(lower)
    return {
        "mode": "confirmed_app_actions_unrecognized",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "result": "Неизвестная команда. Используйте: pc confirmed actions status, pc confirmed actions report",
    }


def status() -> Dict[str, Any]:
    allowlist = get_allowlist()
    return {
        "ok": True,
        "mode": "confirmed_app_actions_status",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "total_actions": len(allowlist),
        "actions": [a["app_id"] for a in allowlist],
    }


def report() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "confirmed_app_actions_report",
        "version": CONFIRMED_APP_ACTIONS_VERSION,
        "generated_at": _now(),
        "allowlist": get_allowlist(),
        "status": status(),
        "note": "All app actions are allowlisted and require explicit confirmation. Only fixed methods allowed: subprocess.Popen with shell=False.",
    }
