from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REAL_ACTIONS_VERSION = "v6.53"
REAL_ACTIONS_NAME = "Computer Use Real Actions Upgrade RU"

try:
    from modules.project_paths import get_project_root
    ROOT_DIR = get_project_root()
except Exception:
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if not ROOT_DIR.exists():
        ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "computer_use_real_actions"
COMPUTER_USE_DIR = PROJECTS_DIR / "ComputerUse"


ALLOWED_APPS = {
    "notepad": {"command": "notepad.exe", "aliases": ["notepad", "блокнот", "заметки", "note", "notes"]},
    "calc": {"command": "calc.exe", "aliases": ["calc", "calculator", "калькулятор"]},
    "mspaint": {"command": "mspaint.exe", "aliases": ["paint", "mspaint", "рисование", "пейнт"]},
    "explorer": {"command": "explorer.exe", "aliases": ["explorer", "проводник", "файлы"]},
}

FOLDER_ALIASES = {
    "project": ["проект", "localagent", "workspace", "рабочая папка"],
    "projects": ["projects", "проекты"],
    "reports": ["reports", "отчеты", "отчёты"],
    "relay": ["relay", "chatgptrelay", "response"],
    "downloads": ["downloads", "загрузки"],
}

KEY_ALIASES = {
    "enter": "enter",
    "энтэр": "enter",
    "ввод": "enter",
    "tab": "tab",
    "таб": "tab",
    "escape": "esc",
    "esc": "esc",
    "backspace": "backspace",
    "space": "space",
    "пробел": "space",
    "delete": "delete",
    "del": "delete",
    "home": "home",
    "end": "end",
}

VK = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "a": 0x41,
    "c": 0x43,
    "s": 0x53,
    "v": 0x56,
    "x": 0x58,
    "z": 0x5A,
    "y": 0x59,
    "n": 0x4E,
    "o": 0x4F,
    "p": 0x50,
    "f": 0x46,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _safe_preview(value: Any, limit: int = 700) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[trimmed]"


def _ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    COMPUTER_USE_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")
    return str(path)


def _contains_secret_text(text: str) -> bool:
    lowered = _norm(text)
    secret_markers = [
        "password",
        "passwd",
        "api key",
        "api-key",
        "apikey",
        "private key",
        "ssh key",
        "token",
        "secret",
        "cookie",
        "cookies",
        "browser profile",
        "seed phrase",
        "парол",
        "токен",
        "секрет",
        "приватный ключ",
        "куки",
        "профиль браузера",
    ]
    return any(marker in lowered for marker in secret_markers)


def _blocked_goal(goal: str) -> Tuple[bool, str]:
    lowered = _norm(goal)
    blocks = [
        ("destructive_delete", r"\b(rm\s+-rf|rmdir|del\s+|format|wipe|erase)\b|удали|удалить|сотри|стереть"),
        ("terminal_admin", r"\b(powershell|cmd\.exe|cmd|bash|zsh|sudo|terminal|administrator|admin)\b|терминал|командн|админ"),
        ("secrets", r"\b(password|passwd|token|api\s*key|api-key|private\s*key|ssh\s*key|cookie|cookies|browser\s*profile)\b|парол|токен|секрет|куки|профил"),
        ("payment", r"\b(bank|payment|credit\s*card|paypal|wallet|casino|gambling|betting)\b|банк|платеж|платеж|карта|казино|ставк"),
    ]
    for reason, pattern in blocks:
        if re.search(pattern, lowered):
            return True, reason
    return False, ""


def _resolve_app(goal: str) -> str:
    lowered = _norm(goal)
    if not any(marker in lowered for marker in ["открой", "запусти", "open", "launch", "start"]):
        return ""
    for app_id, info in ALLOWED_APPS.items():
        aliases = info.get("aliases", [])
        if any(alias in lowered for alias in aliases):
            return app_id
    return ""


def _resolve_folder(goal: str) -> str:
    lowered = _norm(goal)
    if not any(marker in lowered for marker in ["открой", "покажи", "open", "folder", "папк"]):
        return ""
    for folder_id, aliases in FOLDER_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return folder_id
    return ""


def resolve_folder_path(folder_id: str) -> Path:
    folder = _norm(folder_id)
    if folder == "project":
        return ROOT_DIR
    if folder == "projects":
        return PROJECTS_DIR
    if folder == "reports":
        return PROJECTS_DIR / "Reports"
    if folder == "relay":
        return PROJECTS_DIR / "ChatGPTRelay"
    if folder == "downloads":
        return Path.home() / "Downloads"
    return ROOT_DIR


def _strip_quotes(text: str) -> str:
    cleaned = str(text or "").strip()
    pairs = [('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"), ("`", "`")]
    changed = True
    while changed and len(cleaned) >= 2:
        changed = False
        for left, right in pairs:
            if cleaned.startswith(left) and cleaned.endswith(right):
                cleaned = cleaned[len(left):-len(right)].strip()
                changed = True
                break
    return cleaned


def _extract_text_payload(goal: str) -> str:
    raw = str(goal or "").strip()
    if "::" in raw:
        return _strip_quotes(raw.split("::", 1)[1].strip())
    lowered = _norm(raw)
    markers = [
        "напиши ",
        "введи ",
        "напечатай ",
        "набери ",
        "type ",
        "write ",
        "print ",
        "paste ",
        "вставь ",
    ]
    best_index = -1
    best_marker = ""
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0 and (best_index < 0 or index < best_index):
            best_index = index
            best_marker = marker
    if best_index < 0:
        return ""
    payload = raw[best_index + len(best_marker):].strip()
    lowered_payload = _norm(payload)
    cut_markers = [
        " после этого ",
        " затем ",
        " потом ",
        " и нажми ",
        " and press ",
        " and hit ",
    ]
    for marker in cut_markers:
        pos = lowered_payload.find(marker.strip())
        if pos > 0:
            payload = payload[:pos].strip()
            break
    return _strip_quotes(payload)


def _extract_type_target(goal: str) -> str:
    lowered = _norm(goal)
    explicit_patterns = [
        r"(?:в поле|ввод в|введи в|напиши в)\s+([a-zа-я0-9 _.\-]{2,80})",
        r"(?:поле|input|field)\s+([a-zа-я0-9 _.\-]{2,80})",
    ]
    stop_words = [
        " напиши ",
        " введи ",
        " напечатай ",
        " набери ",
        " type ",
        " write ",
        " paste ",
        " вставь ",
        " ::",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, lowered)
        if match:
            target = match.group(1).strip(" :,-—")
            for marker in stop_words:
                pos = target.find(marker.strip())
                if pos > 0:
                    target = target[:pos].strip(" :,-—")
            if target:
                if "поиск" in target or "search" in target:
                    return "Поиск"
                if "чат" in target or "chat" in target:
                    return "чат"
                return target
    if "поиск" in lowered or "search" in lowered:
        return "Поиск"
    if "чат" in lowered or "chat" in lowered:
        return "чат"
    return "active_window"


def _extract_click_target(goal: str) -> str:
    raw = str(goal or "").strip()
    lowered = _norm(raw)
    markers = [
        "кликни по ",
        "нажми на ",
        "нажми кнопку ",
        "кнопку ",
        "click ",
        "press button ",
        "button ",
    ]
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            target = raw[index + len(marker):].strip(" :,-—")
            for cut in [" затем ", " потом ", " после этого ", " and "]:
                cut_pos = _norm(target).find(cut.strip())
                if cut_pos > 0:
                    target = target[:cut_pos].strip()
            return _strip_quotes(target)
    return ""


def _extract_key(goal: str) -> str:
    lowered = _norm(goal)
    for alias, key in KEY_ALIASES.items():
        if ("нажми " + alias) in lowered or ("press " + alias) in lowered or lowered.endswith(alias):
            return key
    return ""


def _extract_hotkey(goal: str) -> List[str]:
    lowered = _norm(goal)
    known = {
        "ctrl+s": ["ctrl", "s"],
        "ctrl s": ["ctrl", "s"],
        "ctrl+v": ["ctrl", "v"],
        "ctrl v": ["ctrl", "v"],
        "ctrl+a": ["ctrl", "a"],
        "ctrl a": ["ctrl", "a"],
        "ctrl+c": ["ctrl", "c"],
        "ctrl c": ["ctrl", "c"],
        "alt+tab": ["alt", "tab"],
        "alt tab": ["alt", "tab"],
        "shift+tab": ["shift", "tab"],
        "shift tab": ["shift", "tab"],
    }
    for marker, keys in known.items():
        if marker in lowered:
            return keys
    return []


def _scroll_direction(goal: str) -> int:
    lowered = _norm(goal)
    if "прокрути вниз" in lowered or "scroll down" in lowered:
        return -1
    if "прокрути вверх" in lowered or "scroll up" in lowered:
        return 1
    return 0


def build_real_action_plan(goal: str, max_steps: int = 16) -> Dict[str, Any]:
    goal = str(goal or "").strip()
    blocked, reason = _blocked_goal(goal)
    if blocked:
        return {
            "ok": False,
            "mode": "computer_use_real_action_plan",
            "version": REAL_ACTIONS_VERSION,
            "blocked": True,
            "reason": reason,
            "actions": [],
        }

    actions: List[Dict[str, Any]] = []
    lowered = _norm(goal)

    app_id = _resolve_app(goal)
    if app_id:
        actions.append({
            "kind": "open_app",
            "target": app_id,
            "confidence": 0.96,
            "reason": "allowlisted app resolved from user goal",
            "real_action": True,
        })
        actions.append({
            "kind": "wait_for_window",
            "target": app_id,
            "seconds": 0.8,
            "confidence": 0.88,
            "reason": "wait for launched app to become ready",
            "real_action": True,
        })

    folder_id = _resolve_folder(goal)
    if folder_id:
        actions.append({
            "kind": "open_folder",
            "target": folder_id,
            "confidence": 0.94,
            "reason": "allowlisted folder resolved from user goal",
            "real_action": True,
        })
        actions.append({
            "kind": "wait_for_window",
            "target": folder_id,
            "seconds": 0.5,
            "confidence": 0.84,
            "reason": "wait for folder window",
            "real_action": True,
        })

    click_target = _extract_click_target(goal)
    double_click = any(marker in lowered for marker in ["двойной клик", "double click", "double-click"])
    if click_target:
        actions.append({
            "kind": "double_click_element" if double_click else "click_element",
            "target": click_target,
            "confidence": 0.82,
            "reason": "click target extracted and delegated to grounded click planner",
            "real_action": True,
        })

    text_payload = _extract_text_payload(goal)
    if text_payload:
        target = _extract_type_target(goal)
        if target and target != "active_window":
            actions.append({
                "kind": "type_element",
                "target": target,
                "text": text_payload,
                "confidence": 0.86,
                "reason": "typed payload with target field detected",
                "real_action": True,
            })
        else:
            actions.append({
                "kind": "paste_text",
                "target": "active_window",
                "text": text_payload,
                "confidence": 0.88 if app_id else 0.74,
                "reason": "typed payload extracted for active window paste",
                "real_action": True,
            })

    hotkey = _extract_hotkey(goal)
    if hotkey:
        actions.append({
            "kind": "hotkey",
            "target": "+".join(hotkey),
            "keys": hotkey,
            "confidence": 0.88,
            "reason": "known hotkey extracted from user goal",
            "real_action": True,
        })

    key = _extract_key(goal)
    if key and not hotkey:
        actions.append({
            "kind": "press_key",
            "target": key,
            "key": key,
            "confidence": 0.86,
            "reason": "single key press extracted from user goal",
            "real_action": True,
        })

    scroll = _scroll_direction(goal)
    if scroll:
        actions.append({
            "kind": "scroll",
            "target": "active_window",
            "direction": "up" if scroll > 0 else "down",
            "clicks": 4,
            "confidence": 0.84,
            "reason": "scroll command extracted from user goal",
            "real_action": True,
        })

    if not actions:
        actions.append({
            "kind": "delegate_multistep",
            "target": "screen",
            "goal": goal,
            "confidence": 0.72,
            "reason": "fallback to existing grounded multistep loop",
            "real_action": False,
        })

    for index, action in enumerate(actions[:max_steps], start=1):
        action["index"] = index

    return {
        "ok": True,
        "mode": "computer_use_real_action_plan",
        "version": REAL_ACTIONS_VERSION,
        "goal": goal,
        "actions": actions[:max_steps],
        "summary": {
            "total": len(actions[:max_steps]),
            "real_actions": sum(1 for item in actions[:max_steps] if item.get("real_action")),
            "fallback_actions": sum(1 for item in actions[:max_steps] if not item.get("real_action")),
        },
    }


def _vk_code(key: str) -> Optional[int]:
    lowered = _norm(key)
    if lowered in VK:
        return VK[lowered]
    if len(lowered) == 1 and "a" <= lowered <= "z":
        return ord(lowered.upper())
    return None


def press_hotkey(keys: List[str], simulate: bool = False) -> Dict[str, Any]:
    normalized = [_norm(key) for key in keys if _norm(key)]
    if not normalized:
        return {"ok": False, "status": "error", "reason": "empty hotkey"}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_hotkey", "keys": normalized}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real hotkey supports Windows in this build", "keys": normalized}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        key_up = 0x0002
        codes = []
        for key in normalized:
            code = _vk_code(key)
            if code is None:
                return {"ok": False, "status": "error", "reason": "unsupported key: " + key, "keys": normalized}
            codes.append(code)
        for code in codes:
            user32.keybd_event(code, 0, 0, 0)
            time.sleep(0.025)
        for code in reversed(codes):
            user32.keybd_event(code, 0, key_up, 0)
            time.sleep(0.025)
        return {"ok": True, "status": "executed", "mode": "computer_use_real_hotkey", "keys": normalized}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "keys": normalized}


def press_key(key: str, simulate: bool = False) -> Dict[str, Any]:
    normalized = _norm(key)
    if not normalized:
        return {"ok": False, "status": "error", "reason": "empty key"}
    return press_hotkey([normalized], simulate=simulate)


def set_clipboard_text(text: str) -> Dict[str, Any]:
    if _contains_secret_text(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "clipboard payload appears to contain secret markers"}
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return {"ok": True, "status": "clipboard_set", "text_preview": _safe_preview(text, 160)}
    except Exception as exc:
        return {"ok": False, "status": "clipboard_error", "reason": str(exc)}


def paste_text(text: str, simulate: bool = False) -> Dict[str, Any]:
    text = str(text or "")
    if _contains_secret_text(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "text appears to contain secret markers"}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_paste_text", "text_preview": _safe_preview(text, 300)}
    clip = set_clipboard_text(text)
    if not clip.get("ok"):
        return clip
    hotkey = press_hotkey(["ctrl", "v"], simulate=False)
    hotkey["clipboard"] = clip
    hotkey["mode"] = "computer_use_real_paste_text"
    return hotkey


def open_app(app_id: str, simulate: bool = False) -> Dict[str, Any]:
    app_id = _norm(app_id)
    if app_id not in ALLOWED_APPS:
        return {"ok": False, "status": "blocked", "reason": "app is not allowlisted", "app": app_id}
    command = str(ALLOWED_APPS[app_id].get("command") or "")
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
    try:
        try:
            from modules.pc_agent_actions import open_app as pc_open_app
            result = pc_open_app(app_id, dry_run=False)
            if isinstance(result, dict) and result.get("ok"):
                result["mode"] = "computer_use_real_open_app"
                result["app"] = app_id
                return result
        except Exception:
            pass
        if hasattr(os, "startfile"):
            os.startfile(command)
            return {"ok": True, "status": "executed", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
        return {"ok": False, "status": "unsupported", "reason": "app launch fallback requires Windows os.startfile", "app": app_id}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "app": app_id}


def open_folder(folder_id: str, simulate: bool = False) -> Dict[str, Any]:
    path = resolve_folder_path(folder_id)
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(path))
            return {"ok": True, "status": "executed", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
        return {"ok": False, "status": "unsupported", "reason": "folder open requires Windows os.startfile", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "path": str(path)}


def click_element(target: str, simulate: bool = False, double: bool = False) -> Dict[str, Any]:
    target = str(target or "").strip()
    if not target:
        return {"ok": False, "status": "error", "reason": "empty click target"}
    try:
        from modules.computer_use_click_planner_ru import click_element as guarded_click
        first = guarded_click(target, simulate=simulate)
        if not double:
            first["mode"] = "computer_use_real_click_element"
            return first
        if not first.get("ok") and not first.get("simulated"):
            first["mode"] = "computer_use_real_double_click_element"
            return first
        second = guarded_click(target, simulate=simulate)
        return {
            "ok": bool(first.get("ok")) and bool(second.get("ok")),
            "status": "simulated" if simulate else "executed",
            "mode": "computer_use_real_double_click_element",
            "target": target,
            "first": first,
            "second": second,
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "target": target}


def type_element(target: str, text: str, simulate: bool = False) -> Dict[str, Any]:
    target = str(target or "").strip() or "active_window"
    if target == "active_window":
        return paste_text(text, simulate=simulate)
    try:
        from modules.computer_use_type_guard_ru import guarded_type
        result = guarded_type(target, str(text or ""), simulate=simulate)
        result["mode"] = "computer_use_real_type_element"
        return result
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "target": target, "text_preview": _safe_preview(text, 120)}


def scroll(direction: str = "down", clicks: int = 4, simulate: bool = False) -> Dict[str, Any]:
    direction = _norm(direction)
    clicks = max(1, min(int(clicks or 4), 15))
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_scroll", "direction": direction, "clicks": clicks}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real scroll supports Windows in this build"}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        wheel_delta = 120 * clicks
        if direction == "down":
            wheel_delta = -wheel_delta
        user32.mouse_event(0x0800, 0, 0, wheel_delta, 0)
        return {"ok": True, "status": "executed", "mode": "computer_use_real_scroll", "direction": direction, "clicks": clicks}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "direction": direction}


def wait_for_window(seconds: float = 0.6, simulate: bool = False) -> Dict[str, Any]:
    seconds = max(0.0, min(float(seconds or 0.6), 5.0))
    if not simulate:
        time.sleep(seconds)
    return {"ok": True, "status": "simulated" if simulate else "executed", "mode": "computer_use_real_wait", "seconds": seconds}


def execute_real_action(action: Dict[str, Any], simulate: bool = False, mission_goal: str = "") -> Dict[str, Any]:
    kind = str(action.get("kind") or "").strip()
    try:
        if kind == "open_app":
            return open_app(str(action.get("target") or ""), simulate=simulate)
        if kind == "open_folder":
            return open_folder(str(action.get("target") or ""), simulate=simulate)
        if kind == "wait_for_window" or kind == "wait":
            return wait_for_window(float(action.get("seconds") or 0.6), simulate=simulate)
        if kind == "paste_text":
            return paste_text(str(action.get("text") or ""), simulate=simulate)
        if kind == "type_element":
            return type_element(str(action.get("target") or ""), str(action.get("text") or ""), simulate=simulate)
        if kind == "click_element":
            return click_element(str(action.get("target") or ""), simulate=simulate, double=False)
        if kind == "double_click_element":
            return click_element(str(action.get("target") or ""), simulate=simulate, double=True)
        if kind == "hotkey":
            return press_hotkey(list(action.get("keys") or []), simulate=simulate)
        if kind == "press_key":
            return press_key(str(action.get("key") or action.get("target") or ""), simulate=simulate)
        if kind == "scroll":
            return scroll(str(action.get("direction") or "down"), int(action.get("clicks") or 4), simulate=simulate)
        if kind == "delegate_multistep":
            from modules.computer_use_multistep_loop_ru import run_loop
            result = run_loop(str(action.get("goal") or mission_goal), simulate=simulate, max_steps=1, max_failures=1)
            result.setdefault("status", result.get("outcome") or "returned")
            return result
        return {"ok": False, "status": "error", "reason": "unknown real action kind: " + kind}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "traceback": traceback.format_exc(), "action": action}


def get_real_action_capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "computer_use_real_action_capabilities",
        "version": REAL_ACTIONS_VERSION,
        "actions": [
            "open_app",
            "open_folder",
            "click_element",
            "double_click_element",
            "type_element",
            "paste_text",
            "hotkey",
            "press_key",
            "scroll",
            "wait_for_window",
            "delegate_multistep",
        ],
        "app_allowlist": sorted(ALLOWED_APPS.keys()),
        "folder_allowlist": sorted(FOLDER_ALIASES.keys()),
        "notes": [
            "Real GUI actions are functionality-first for normal GUI tasks.",
            "Hard gates still block destructive, terminal/admin, secret, payment, and browser-profile flows.",
        ],
    }


def run_self_check(write_report: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details if details is not None else {}})

    blocked, reason = _blocked_goal("удали все файлы через powershell")
    add("hard gate blocks destructive terminal goal", blocked and reason in {"destructive_delete", "terminal_admin"}, {"blocked": blocked, "reason": reason})

    plan = build_real_action_plan("открой блокнот и напиши hello и нажми enter", max_steps=8)
    kinds = [item.get("kind") for item in plan.get("actions", [])]
    add("plan includes open app paste and key", plan.get("ok") and "open_app" in kinds and "paste_text" in kinds and "press_key" in kinds, {"kinds": kinds})

    click_plan = build_real_action_plan("кликни по Сохранить", max_steps=4)
    add("plan supports grounded click element", click_plan.get("ok") and any(item.get("kind") == "click_element" for item in click_plan.get("actions", [])), click_plan)

    type_plan = build_real_action_plan("в поле Поиск напиши hello", max_steps=4)
    add("plan supports targeted type element", type_plan.get("ok") and any(item.get("kind") == "type_element" for item in type_plan.get("actions", [])), type_plan)

    scroll_plan = build_real_action_plan("прокрути вниз", max_steps=4)
    add("plan supports scroll", scroll_plan.get("ok") and any(item.get("kind") == "scroll" for item in scroll_plan.get("actions", [])), scroll_plan)

    open_sim = execute_real_action({"kind": "open_app", "target": "notepad"}, simulate=True)
    add("simulate open app executes", open_sim.get("ok") and open_sim.get("status") == "simulated", open_sim)

    paste_sim = execute_real_action({"kind": "paste_text", "text": "hello"}, simulate=True)
    add("simulate paste executes", paste_sim.get("ok") and paste_sim.get("status") == "simulated", paste_sim)

    caps = get_real_action_capabilities()
    add("capabilities expose real actions", caps.get("ok") and "open_app" in caps.get("actions", []) and "scroll" in caps.get("actions", []), caps)

    summary = {
        "passed": sum(1 for item in checks if item.get("ok")),
        "total": len(checks),
        "failed": sum(1 for item in checks if not item.get("ok")),
    }
    payload = {
        "ok": summary["failed"] == 0,
        "mode": "computer_use_real_actions_self_check",
        "version": REAL_ACTIONS_VERSION,
        "summary": summary,
        "checks": checks,
    }
    if write_report:
        _ensure_dirs()
        path = REPORTS_DIR / ("real_actions_self_check_" + _stamp() + ".json")
        _write_json(path, payload)
        payload["report"] = str(path)
    return payload


def format_result(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
