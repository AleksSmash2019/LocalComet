from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REAL_ACTIONS_VERSION = "v6.54"
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
    "chrome": {"command": "chrome.exe", "aliases": ["chrome", "google chrome", "хром", "браузер", "browser"]},
    "msedge": {"command": "msedge.exe", "aliases": ["edge", "msedge", "microsoft edge", "еdge"]},
    "firefox": {"command": "firefox.exe", "aliases": ["firefox", "фаерфокс", "мозилла", "mozilla"]},
    "vscode": {"command": "Code.exe", "aliases": ["vscode", "code", "visual studio code", "вс код", "код"]},
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


def _canonical_app_id(value: Any) -> str:
    normalized = _norm(value)
    if normalized in ALLOWED_APPS:
        return normalized
    for app_id, info in ALLOWED_APPS.items():
        if normalized in {_norm(app_id), *(_norm(alias) for alias in info.get("aliases", []))}:
            return app_id
    return normalized


def _canonical_folder_id(value: Any) -> str:
    normalized = _norm(value)
    if normalized in FOLDER_ALIASES:
        return normalized
    for folder_id, aliases in FOLDER_ALIASES.items():
        if normalized in {_norm(folder_id), *(_norm(alias) for alias in aliases)}:
            return folder_id
    return normalized


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


def resolve_folder_path(folder_id: str) -> Optional[Path]:
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
    return None


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


def _extract_search_query(goal: str) -> str:
    """Extract a web-search query from a find/search intent, or empty string.

    Natural phrasings ("найди X", "поищи X", "погугли X", "search for X") are
    mapped to a real browser-search flow, so they must not fall through to the
    non-executing delegate_multistep fallback.
    """
    raw = str(goal or "").strip()
    lowered = _norm(raw)
    # Longest-first so compound markers ("найди в интернете") win over "найди".
    markers = [
        "найди в интернете",
        "поищи в интернете",
        "найди в браузере",
        "поищи в браузере",
        "найди в гугле",
        "поищи в гугле",
        "погугли",
        "найди",
        "поищи",
        "ищи",
        "search for",
        "find",
        "google",
    ]
    best_index = -1
    best_len = -1
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0 and len(marker) > best_len:
            best_index = index
            best_len = len(marker)
    if best_index < 0:
        return ""
    payload = raw[best_index + best_len:].strip(" :,-")
    cut_markers = [
        " после этого ",
        " затем ",
        " потом ",
        " и нажми ",
        " and press ",
        " and hit ",
        " and ",
    ]
    for marker in cut_markers:
        pos = _norm(payload).find(marker.strip())
        if pos > 0:
            payload = payload[:pos].strip(" :,-")
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
        "ctrl+f": ["ctrl", "f"],
        "ctrl f": ["ctrl", "f"],
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

    search_query = _extract_search_query(goal)
    if search_query:
        if not app_id:
            actions.insert(0, {
                "kind": "open_app",
                "target": "chrome",
                "confidence": 0.92,
                "reason": "browser required for web search goal",
                "real_action": True,
            })
            actions.insert(1, {
                "kind": "wait_for_window",
                "target": "chrome",
                "seconds": 0.8,
                "confidence": 0.86,
                "reason": "wait for browser before search",
                "real_action": True,
            })
        actions.append({
            "kind": "type_element",
            "target": "Поиск",
            "text": search_query,
            "confidence": 0.9,
            "reason": "web search query typed into browser search bar",
            "real_action": True,
        })
        actions.append({
            "kind": "press_key",
            "target": "enter",
            "key": "enter",
            "confidence": 0.9,
            "reason": "submit the web search query",
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
    # The hotkey allowlist is enforced at this execution primitive so every
    # caller (sidecar tool channel, mission planners, console bridges) shares
    # one policy; previously only the auto-action path consulted it.
    combo = "+".join(normalized)
    try:
        from modules.computer_use_auto_action_ru import load_policy
        allowed_hotkeys = [str(item).lower() for item in load_policy().get("allowed_hotkeys", [])]
    except Exception:
        allowed_hotkeys = []
    if allowed_hotkeys and combo not in allowed_hotkeys:
        return {"ok": False, "status": "blocked", "reason": f"hotkey '{combo}' is not in the allowlist", "keys": normalized}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_hotkey", "keys": normalized}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real hotkey supports Windows in this build", "keys": normalized}
    pressed_codes: List[int] = []
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
            pressed_codes.append(code)
            time.sleep(0.025)
        return {"ok": True, "status": "executed", "mode": "computer_use_real_hotkey", "keys": normalized}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "keys": normalized}
    finally:
        # Never leave a modifier pressed when an input sequence is interrupted.
        if pressed_codes:
            try:
                for code in reversed(pressed_codes):
                    ctypes.windll.user32.keybd_event(code, 0, 0x0002, 0)
                    time.sleep(0.025)
            except Exception:
                pass


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


def _fresh_uia_readback_contains(
    auto: Any,
    expected_text: str,
    *,
    target_native_hwnd: int = 0,
    target_runtime_id: Optional[Tuple[int, ...]] = None,
    target_control_type: str = "",
    target_window_native_hwnd: int = 0,
) -> bool:
    """Read text again through a fresh UIA traversal after a mutation.

    Reading the same ValuePattern object immediately after SetValue can only
    prove that the client-side object accepted the write. A second root scan
    asks the provider for a new control/pattern and is therefore required for
    a truthful ``verification=verified`` result. When the control exposes a
    native HWND or RuntimeId, the fresh scan must resolve that same control.
    """
    expected = str(expected_text or "")
    if not expected:
        return False
    queue: list[tuple[Any, bool]]
    if target_window_native_hwnd:
        try:
            from_handle = getattr(auto, "ControlFromHandle", None)
            fresh_window = from_handle(target_window_native_hwnd) if callable(from_handle) else None
            fresh_title = _norm(getattr(fresh_window, "Name", "")) if fresh_window else ""
            if fresh_window is not None and ("notepad" in fresh_title or "блокнот" in fresh_title):
                queue = [(fresh_window, True)]
            else:
                queue = []
        except Exception:
            queue = []
        if not queue:
            return False
    else:
        try:
            root = auto.GetRootControl()
            queue = [(child, False) for child in root.GetChildren()]
        except Exception:
            return False
    visited = 0
    while queue and visited < 640:
        node, in_notepad = queue.pop(0)
        visited += 1
        try:
            title = _norm(getattr(node, "Name", ""))
        except Exception:
            title = ""
        in_notepad = in_notepad or "notepad" in title or "блокнот" in title
        if not in_notepad:
            try:
                queue.extend((child, False) for child in node.GetChildren())
            except Exception:
                pass
            continue
        try:
            node_hwnd = int(getattr(node, "NativeWindowHandle", 0) or 0)
            node_control_type = str(getattr(node, "ControlTypeName", "") or "")
        except Exception:
            node_hwnd = 0
            node_control_type = ""
        node_runtime_id: Optional[Tuple[int, ...]] = None
        try:
            getter = getattr(node, "GetRuntimeId", None)
            if callable(getter):
                raw_id = getter()
                if raw_id:
                    node_runtime_id = tuple(int(item) for item in raw_id)
        except Exception:
            pass
        # NativeWindowHandle is the stronger grounded identity when exposed.
        # RuntimeId can be regenerated by some UIA providers between two root
        # traversals, so do not require both identifiers simultaneously.
        if target_native_hwnd:
            matched = node_hwnd == target_native_hwnd
        elif target_runtime_id is not None:
            matched = node_runtime_id == target_runtime_id
            # Modern Notepad can regenerate RuntimeId after SetValue. If the
            # ID changed, keep the independent check bounded to the same
            # Notepad editor control type rather than trusting an arbitrary
            # desktop text node.
            if not matched and target_control_type:
                matched = node_control_type == target_control_type
        else:
            matched = True
        if matched:
            for getter_name, pattern_name in (
                ("GetValuePattern", "Value"),
                ("GetTextPattern", "DocumentRange"),
            ):
                try:
                    pattern = getattr(node, getter_name)()
                    if pattern is None:
                        continue
                    if pattern_name == "Value":
                        current = str(getattr(pattern, "Value", "") or "")
                    else:
                        document_range = getattr(pattern, "DocumentRange", None)
                        current = str(document_range.GetText(-1) or "") if document_range else ""
                    if expected in current:
                        return True
                except Exception:
                    continue
        try:
            queue.extend((child, in_notepad) for child in node.GetChildren())
        except Exception:
            pass
    return False


def _uia_runtime_id(node: Any) -> Optional[Tuple[int, ...]]:
    try:
        getter = getattr(node, "GetRuntimeId", None)
        raw_id = getter() if callable(getter) else None
        return tuple(int(item) for item in raw_id) if raw_id else None
    except Exception:
        return None


def _set_hidden_notepad_text_via_uia(text: str) -> Optional[Dict[str, Any]]:
    """Set text through UIA only for an explicitly isolated hidden desktop.

    This is deliberately gated by the harness-provided desktop name.  Normal
    sessions never use UIA to mutate a control, and this helper never calls
    SetFocus, click, or keyboard input.  It returns ``None`` outside hidden
    mode so the regular user-facing input path remains unchanged.
    """
    hidden_desktop = os.environ.get("LC_HIDDEN_DESKTOP_NAME", "").strip()
    if os.name != "nt" or not hidden_desktop:
        return None
    # UIA resolves the caller's desktop. Attach this worker thread explicitly
    # to the named harness desktop before asking for the UIA root; otherwise a
    # sidecar can accidentally inspect the user's interactive desktop or miss
    # the hidden Notepad entirely. This path is never enabled without the
    # harness-only environment marker above.
    try:
        import ctypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        desktop_access = 0x0001 | 0x0002 | 0x0040 | 0x0080  # read/create/enumerate/write
        user32.OpenDesktopW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        user32.OpenDesktopW.restype = ctypes.c_void_p
        user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]
        user32.SetThreadDesktop.restype = ctypes.c_bool
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
        user32.CloseDesktop.restype = ctypes.c_bool
        desktop_handle = user32.OpenDesktopW(hidden_desktop, 0, False, desktop_access)
        if not desktop_handle:
            return {"ok": False, "executed": False, "status": "error", "reason": "hidden_uia_desktop_open_failed"}
        try:
            if not user32.SetThreadDesktop(desktop_handle):
                return {"ok": False, "executed": False, "status": "error", "reason": "hidden_uia_desktop_attach_failed"}
        finally:
            user32.CloseDesktop(desktop_handle)
    except Exception as exc:
        return {"ok": False, "executed": False, "status": "error", "reason": f"hidden_uia_desktop_attach_unavailable: {exc}"}
    try:
        import uiautomation as auto
        root = auto.GetRootControl()
        top_windows = list(root.GetChildren())[:12]
    except Exception as exc:
        return {"ok": False, "executed": False, "status": "error", "reason": f"hidden_uia_unavailable: {exc}"}

    def norm_name(value: Any) -> str:
        return str(value or "").lower().replace("ё", "е").strip()

    visited = 0
    uia_diagnostics: List[Dict[str, Any]] = []
    for window in top_windows:
        try:
            title = str(window.Name or "")[:160]
            title_norm = norm_name(title)
        except Exception:
            continue
        if "notepad" not in title_norm and "блокнот" not in title_norm:
            continue
        queue: List[Tuple[Any, int]] = [(window, 0)]
        while queue and visited < 320:
            node, depth = queue.pop(0)
            visited += 1
            try:
                control_type = str(node.ControlTypeName or "")
                enabled = bool(node.IsEnabled)
                offscreen = bool(node.IsOffscreen)
                native_hwnd = int(getattr(node, "NativeWindowHandle", 0) or 0)
                runtime_id = _uia_runtime_id(node)
                children = list(node.GetChildren()) if depth < 8 else []
            except Exception:
                continue
            # A hidden desktop can truthfully report UIA IsOffscreen even for
            # the owned Notepad document. The function is already hard-gated by
            # LC_HIDDEN_DESKTOP_NAME, so do not discard the only grounded editor
            # solely because the test desktop is intentionally not user-visible.
            if control_type in {"EditControl", "DocumentControl"} and enabled:
                try:
                    pattern = node.GetValuePattern()
                    if pattern is not None and not bool(pattern.IsReadOnly):
                        if pattern.SetValue(text):
                            if _fresh_uia_readback_contains(
                                auto, text, target_native_hwnd=native_hwnd, target_runtime_id=runtime_id, target_control_type=control_type, target_window_native_hwnd=int(getattr(window, "NativeWindowHandle", 0) or 0)
                            ):
                                return {
                                    "ok": True,
                                    "executed": True,
                                    "status": "verified",
                                    "verification": "verified",
                                    "primitive": "uia_value_pattern",
                                    "window_title": title,
                                    "control_type": control_type,
                                    "char_count": len(text),
                                }
                except Exception:
                    pass
                # Some classic/compatibility Notepad edit controls expose a real
                # child HWND while ValuePattern is unavailable or read-only. The
                # HWND is obtained only from the UIA-grounded Notepad control;
                # never accept one from model input. SetWindowTextW avoids the
                # hidden-desktop SendInput limitation, then the same UIA readback
                # remains mandatory before claiming success.
                try:
                    native_hwnd = int(getattr(node, "NativeWindowHandle", 0) or 0)
                    set_window_text = getattr(node, "SetWindowText", None)
                    if native_hwnd and callable(set_window_text) and set_window_text(text):
                        time.sleep(0.25)
                        if _fresh_uia_readback_contains(
                            auto, text, target_native_hwnd=native_hwnd, target_runtime_id=runtime_id, target_control_type=control_type, target_window_native_hwnd=int(getattr(window, "NativeWindowHandle", 0) or 0)
                        ):
                            return {
                                "ok": True,
                                "executed": True,
                                "status": "verified",
                                "verification": "verified",
                                "primitive": "uia_native_window_settext",
                                "window_title": title,
                                "control_type": control_type,
                                "native_window_handle": native_hwnd,
                                "char_count": len(text),
                            }
                except Exception:
                    pass
                # Modern Notepad may expose a read-only TextPattern instead of
                # ValuePattern.  In the explicitly isolated harness only, use
                # UIA focus plus Unicode SendInput, then read the document back
                # through TextPattern.  This never runs in normal sessions.
                try:
                    if not node.SetFocus():
                        continue
                    from modules.computer_use_auto_action_ru import _send_unicode_text
                    typed = _send_unicode_text(text)
                    if not typed.get("ok"):
                        continue
                    time.sleep(0.25)
                    if _fresh_uia_readback_contains(
                        auto, text, target_native_hwnd=native_hwnd, target_runtime_id=runtime_id, target_control_type=control_type, target_window_native_hwnd=int(getattr(window, "NativeWindowHandle", 0) or 0)
                    ):
                        return {
                            **typed,
                            "status": "verified",
                            "verification": "verified",
                            "primitive": "uia_focus_unicode_sendinput",
                            "window_title": title,
                            "control_type": control_type,
                            "char_count": len(text),
                        }
                except Exception:
                    pass
            try:
                native_hwnd = int(getattr(node, "NativeWindowHandle", 0) or 0)
            except Exception:
                native_hwnd = 0
            try:
                value_pattern = node.GetValuePattern()
                value_available = value_pattern is not None
                value_read_only = bool(value_pattern.IsReadOnly) if value_pattern is not None else None
            except Exception:
                value_available = False
                value_read_only = None
            uia_diagnostics.append({
                "title": title,
                "control_type": control_type,
                "offscreen": offscreen,
                "native_window_handle": native_hwnd,
                "value_pattern": value_available,
                "value_read_only": value_read_only,
            })
            queue.extend((child, depth + 1) for child in children)
    trace_path = os.environ.get("LOCALCOMET_TOOLCALL_TRACE", "").strip()
    if trace_path and uia_diagnostics:
        try:
            with open(trace_path, "a", encoding="utf-8") as trace:
                for diagnostic in uia_diagnostics[:32]:
                    trace.write("uia_diag\t" + json.dumps(diagnostic, ensure_ascii=True, separators=(",", ":")) + "\n")
        except OSError:
            pass
    return {"ok": False, "executed": False, "status": "error", "reason": "hidden_notepad_edit_control_not_verified"}


def paste_text(text: str, simulate: bool = False) -> Dict[str, Any]:
    text = str(text or "")
    if _contains_secret_text(text):
        return {"ok": False, "status": "requires_confirmation", "requires_confirmation": True, "reason": "text appears to contain secret markers"}
    # The sidecar type/paste path must respect the same limit as the auto
    # policy, so no input route can bypass max_type_chars.
    try:
        from modules.computer_use_auto_action_ru import load_policy
        max_type_chars = int(load_policy().get("max_type_chars", 500))
    except Exception:
        max_type_chars = 500
    if len(text) > max_type_chars:
        return {
            "ok": False,
            "status": "requires_confirmation",
            "requires_confirmation": True,
            "reason": f"text exceeds max_type_chars ({max_type_chars})",
        }
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_paste_text", "text_preview": _safe_preview(text, 300)}
    hidden_uia_result = _set_hidden_notepad_text_via_uia(text)
    if hidden_uia_result is not None:
        if hidden_uia_result.get("ok"):
            return {
                **hidden_uia_result,
                "mode": "computer_use_real_paste_text_hidden_uia",
                "clipboard_preserved": True,
            }
        # Explicit hidden mode must remain fail-closed. Never fall through to
        # process-global SendInput after UIA failed, because that would lose
        # the grounded Notepad target and could type into an unintended window.
        return {
            **hidden_uia_result,
            "mode": "computer_use_real_paste_text_hidden_uia_failed",
            "clipboard_preserved": True,
        }
    try:
        from modules.computer_use_auto_action_ru import _send_unicode_text
        typed = _send_unicode_text(text)
        return {
            **typed,
            "status": "executed" if typed.get("ok") else "error",
            "mode": "computer_use_real_paste_text",
            "clipboard_preserved": bool(typed.get("clipboard_preserved")),
        }
    except Exception:
        return {"ok": False, "status": "error", "reason": "unicode_input_unavailable", "mode": "computer_use_real_paste_text"}


def open_app(app_id: str, simulate: bool = False) -> Dict[str, Any]:
    app_id = _canonical_app_id(app_id)
    if app_id not in ALLOWED_APPS:
        return {"ok": False, "status": "blocked", "reason": "app is not allowlisted", "app": app_id}
    command = str(ALLOWED_APPS[app_id].get("command") or "")
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
    try:
        try:
            from modules.pc_agent_actions import open_app as pc_open_app
            result = pc_open_app(app_id, dry_run=False)
            if isinstance(result, dict):
                result["mode"] = "computer_use_real_open_app"
                result["app"] = app_id
                if result.get("ok"):
                    return result
                # A GUI shell broker can launch outside the sidecar's process
                # quota even when CreateProcess is rejected with WinError 1816.
                # The broker accepting the request is not readiness: report
                # launch_pending until a window is verified (master prompt
                # section 4.2: ShellExecute is not proof of a ready window).
                if hasattr(os, "startfile"):
                    try:
                        os.startfile(command)
                        return {
                            "ok": True,
                            "status": "launch_pending",
                            "verification": "pending",
                            "mode": "computer_use_real_open_app_shell_broker",
                            "app": app_id,
                            "command": command,
                            "backend_error": result.get("error", ""),
                        }
                    except OSError as fallback_error:
                        result["fallback_error"] = str(fallback_error)
                return result
        except ImportError:
            # Keep the narrow OS fallback only for deployments without the
            # allowlisted launcher module. Runtime launch failures are returned
            # as structured results by pc_agent_actions and are not retried.
            pass
        if hasattr(os, "startfile"):
            os.startfile(command)
            return {"ok": True, "status": "launch_pending", "verification": "pending", "mode": "computer_use_real_open_app", "app": app_id, "command": command}
        return {"ok": False, "status": "unsupported", "reason": "app launch fallback requires Windows os.startfile", "app": app_id}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "app": app_id}


def open_folder(folder_id: str, simulate: bool = False) -> Dict[str, Any]:
    folder_id = _canonical_folder_id(folder_id)
    path = resolve_folder_path(folder_id)
    if path is None:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "folder is not allowlisted",
            "folder": str(folder_id),
        }
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
    try:
        try:
            from modules.pc_agent_actions import open_folder as pc_open_folder
            result = pc_open_folder(folder_id, dry_run=False)
            if isinstance(result, dict):
                result["mode"] = "computer_use_real_open_folder"
                result["folder"] = str(folder_id)
                return result
        except ImportError:
            pass
        if hasattr(os, "startfile"):
            os.startfile(str(path))
            return {"ok": True, "status": "launch_pending", "verification": "pending", "mode": "computer_use_real_open_folder", "folder": str(folder_id), "path": str(path)}
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
    # Canonical bounded wait (0.1..=30.0), shared with the Rust schema and the
    # sidecar dispatcher.
    seconds = max(0.1, min(float(seconds or 0.6), 30.0))
    if not simulate:
        time.sleep(seconds)
    return {"ok": True, "status": "simulated" if simulate else "executed", "mode": "computer_use_real_wait", "seconds": seconds}


def drag(
    from_x: int | None = None,
    from_y: int | None = None,
    to_x: int | None = None,
    to_y: int | None = None,
    *,
    simulate: bool = False,
    coordinate: list | None = None,
) -> Dict[str, Any]:
    """Drag from (x,y) to (x2,y2) — coordinates 0-1000 normalized or pixels.

    If coordinate=[x0,y0,x1,y1] (4 numbers) use that; else use from_* / to_*.
    Falls back gracefully if coordinates missing — returns error, no shell.
    """
    coords: list[int] | None = None
    if isinstance(coordinate, list) and len(coordinate) == 4:
        try:
            coords = [int(c) for c in coordinate]
        except Exception:
            coords = None
    elif from_x is not None and to_x is not None:
        try:
            coords = [int(from_x), int(from_y or 0), int(to_x), int(to_y or 0)]
        except Exception:
            coords = None
    if coords is None:
        return {"ok": False, "status": "error", "reason": "drag requires coordinate=[x0,y0,x1,y1] or from/to", "mode": "computer_use_real_drag"}
    if simulate:
        return {"ok": True, "status": "simulated", "mode": "computer_use_real_drag", "coordinate": coords}
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "reason": "real drag supports Windows in this build", "mode": "computer_use_real_drag"}
    left_button_down = False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        # Normalize 0-1000 to pixels if values look normalized (all <= 1000)
        def _px(v: int, total: int) -> int:
            if 0 <= v <= 1000 and max(coords or []) <= 1000:
                return int(round(v / 1000.0 * total))
            return int(v)

        sx = int(user32.GetSystemMetrics(0))
        sy = int(user32.GetSystemMetrics(1))
        x0, y0, x1, y1 = coords
        px0, py0 = _px(x0, sx), _px(y0, sy)
        px1, py1 = _px(x1, sx), _px(y1, sy)
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        user32.SetCursorPos(px0, py0)
        time.sleep(0.04)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        left_button_down = True
        time.sleep(0.04)
        # Interpolate 6 steps for smooth drag
        for step in range(1, 7):
            t = step / 6.0
            ix = int(round(px0 + (px1 - px0) * t))
            iy = int(round(py0 + (py1 - py0) * t))
            user32.SetCursorPos(ix, iy)
            time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        left_button_down = False
        return {"ok": True, "status": "executed", "mode": "computer_use_real_drag", "from": [px0, py0], "to": [px1, py1]}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "mode": "computer_use_real_drag"}
    finally:
        # A failed move must not leave the user with the primary mouse button held.
        if left_button_down:
            try:
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                pass


def _configure_capture_apis(user32: Any, gdi32: Any, wintypes: Any) -> None:
    """Declare pointer-sized Win32 capture signatures for 64-bit Python."""
    import ctypes

    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.ReleaseDC.restype = wintypes.INT
    user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [wintypes.INT]
    user32.GetSystemMetrics.restype = wintypes.INT
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, wintypes.INT, wintypes.INT]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.GetDIBits.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = wintypes.INT
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.BitBlt.argtypes = [
        ctypes.c_void_p,
        wintypes.INT,
        wintypes.INT,
        wintypes.INT,
        wintypes.INT,
        ctypes.c_void_p,
        wintypes.INT,
        wintypes.INT,
        wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL


def _visible_windows() -> List[Dict[str, Any]]:
    """Top-level visible windows with non-empty titles, largest area first.

    Used by the hidden-desktop capture backend: on a non-interactive desktop
    GDI desktop-BitBlt has no display surface, but per-window PrintWindow
    capture works for real windows that live on that desktop.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    _configure_capture_apis(user32, gdi32, wintypes)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = wintypes.INT
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]
    user32.GetWindowTextW.restype = wintypes.INT
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenDesktopW.restype = ctypes.c_void_p
    user32.EnumDesktopWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    user32.EnumDesktopWindows.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    user32.CloseDesktop.restype = wintypes.BOOL
    results: List[Dict[str, Any]] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, ctypes.c_void_p)
    hidden_desktop_name = os.environ.get("LC_HIDDEN_DESKTOP_NAME", "").strip()
    hidden_desktop_handle = None
    if hidden_desktop_name:
        DESKTOP_READOBJECTS = 0x0001
        DESKTOP_ENUMERATE = 0x0040
        _trace_capture_stage("before_open_hidden_desktop")
        hidden_desktop_handle = user32.OpenDesktopW(
            hidden_desktop_name,
            0,
            False,
            DESKTOP_READOBJECTS | DESKTOP_ENUMERATE,
        )
        _trace_capture_stage("after_open_hidden_desktop")
        if not hidden_desktop_handle:
            _trace_capture_stage("hidden_desktop_open_failed")
            return []

    def _callback(hwnd: Any, _lparam: Any) -> bool:
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = int(rect.right) - int(rect.left)
        height = int(rect.bottom) - int(rect.top)
        if width < 120 or height < 80:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append(
            {
                "hwnd": int(hwnd),
                "title": buf.value,
                "width": width,
                "height": height,
                "pid": int(pid.value),
            }
        )
        return True

    callback = enum_proc(_callback)
    try:
        if hidden_desktop_handle:
            _trace_capture_stage("before_enum_hidden_desktop_windows")
            user32.EnumDesktopWindows(hidden_desktop_handle, callback, 0)
            _trace_capture_stage("after_enum_hidden_desktop_windows")
        else:
            _trace_capture_stage("before_enum_current_windows")
            user32.EnumWindows(callback, 0)
            _trace_capture_stage("after_enum_current_windows")
    finally:
        if hidden_desktop_handle:
            _trace_capture_stage("before_close_hidden_desktop")
            user32.CloseDesktop(hidden_desktop_handle)
            _trace_capture_stage("after_close_hidden_desktop")
    results.sort(key=lambda item: item["width"] * item["height"], reverse=True)
    return results


def _print_window_bgra(hwnd: int, width: int, height: int) -> Optional[bytes]:
    """Capture one hidden-desktop window via its window DC as BGRA.

    PrintWindow is synchronous and can hang WebView2 windows on a noninteractive
    desktop. A bounded BitBlt from the window DC avoids sending WM_PRINT into
    the target process while retaining the same per-window scope.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    _configure_capture_apis(user32, gdi32, wintypes)
    _trace_capture_stage("before_get_window_dc")
    hdc_window = user32.GetDC(hwnd)
    _trace_capture_stage("after_get_window_dc")
    if not hdc_window:
        return None
    try:
        _trace_capture_stage("before_create_compatible_dc")
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        _trace_capture_stage("after_create_compatible_dc")
        _trace_capture_stage("before_create_compatible_bitmap")
        hbmp = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
        _trace_capture_stage("after_create_compatible_bitmap")
        if not hbmp:
            return None
        _trace_capture_stage("before_select_bitmap")
        prev = gdi32.SelectObject(hdc_mem, hbmp)
        _trace_capture_stage("after_select_bitmap")
        try:
            SRCCOPY = 0x00CC0020
            _trace_capture_stage("before_window_bitblt_api")
            ok = gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_window, 0, 0, SRCCOPY)
            _trace_capture_stage("after_window_bitblt_api")
            if not ok:
                return None
            bmi_header_size = 40

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            class BITMAPINFO(ctypes.Structure):
                _fields_ = [
                    ("bmiHeader", BITMAPINFOHEADER),
                    ("bmiColors", wintypes.DWORD * 3),
                ]

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = bmi_header_size
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0
            buffer_len = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_len)
            _trace_capture_stage("before_get_dibits")
            copied = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bmi), 0)
            _trace_capture_stage("after_get_dibits")
            if not copied:
                return None
            return bytes(buffer)
        finally:
            gdi32.SelectObject(hdc_mem, prev)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
    finally:
        user32.ReleaseDC(hwnd, hdc_window)


def _bgra_is_nonblank(buffer: bytes, samples: int = 512) -> bool:
    """A real frame has pixel variety; a failed/empty capture does not."""
    if len(buffer) < samples * 4:
        return False
    step = max(4, (len(buffer) // 4) // samples * 4)
    distinct = set()
    for offset in range(0, min(len(buffer), step * samples), step):
        distinct.add(buffer[offset : offset + 3])
        if len(distinct) >= 6:
            return True
    return len(distinct) >= 2


def _capture_via_printwindow() -> Dict[str, Any]:
    """Window-level GDI capture fallback for non-interactive desktops.

    Tries visible top-level windows, largest first; skips blank frames. The
    result is an honest window observation — never presented as a full
    desktop frame (capture_backend records this).
    """
    if os.name != "nt":
        return {"ok": False, "status": "error", "reason": "window capture requires Windows", "mode": "computer_use_real_screenshot"}
    _trace_capture_stage("before_visible_windows")
    candidates = _visible_windows()
    _trace_capture_stage(f"after_visible_windows_count_{len(candidates)}")
    attempted: List[Dict[str, Any]] = []
    for candidate in candidates[:6]:
        _trace_capture_stage("before_window_capture")
        buffer = _print_window_bgra(candidate["hwnd"], candidate["width"], candidate["height"])
        _trace_capture_stage("after_window_capture")
        if not buffer or not _bgra_is_nonblank(buffer):
            attempted.append({"title": candidate["title"], "blank": True})
            continue
        b64, out_w, out_h, scale = _encode_bgra_png(buffer, candidate["width"], candidate["height"])
        return _with_png_evidence({
            "ok": True,
            "status": "executed",
            "mode": "computer_use_real_screenshot",
            "screenshot": b64,
            "width": int(out_w),
            "height": int(out_h),
            "scale": float(scale),
            "capture_backend": "gdi_bitblt",
            "capture_scope": "window",
            "capture_desktop": os.environ.get("LC_HIDDEN_DESKTOP_NAME", "").strip() or "current",
            "capture_hwnd": candidate["hwnd"],
            "capture_window_title": candidate["title"],
        })
    return {
        "ok": False,
        "status": "error",
        "reason": "no capturable window on this desktop",
        "mode": "computer_use_real_screenshot",
        "capture_backend": "gdi_bitblt",
        "capture_scope": "window",
        "capture_desktop": os.environ.get("LC_HIDDEN_DESKTOP_NAME", "").strip() or "current",
        "attempted": attempted[:6],
    }


def _encode_bgra_png(buffer: Any, orig_w: int, orig_h: int) -> tuple[str, int, int, float]:
    """Encode a Windows top-down BGRA buffer as a bounded RGB PNG without Pillow."""
    import base64
    import struct
    import zlib

    scale = 1.0
    long_edge = max(orig_w, orig_h)
    if long_edge > 1568:
        scale = min(scale, 1568.0 / float(long_edge))
    pixels = float(orig_w) * float(orig_h)
    if pixels > 1_150_000:
        scale = min(scale, (1_150_000 / pixels) ** 0.5)
    if orig_w > 1024 or orig_h > 768:
        scale = min(scale, min(1024.0 / float(orig_w), 768.0 / float(orig_h)))
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))
    actual_scale = float(new_w) / float(orig_w) if orig_w else 1.0
    source = memoryview(bytes(buffer))
    scanlines = bytearray()
    for y in range(new_h):
        scanlines.append(0)
        source_y = min(orig_h - 1, int(y / scale))
        for x in range(new_w):
            source_x = min(orig_w - 1, int(x / scale))
            offset = (source_y * orig_w + source_x) * 4
            scanlines.extend((source[offset + 2], source[offset + 1], source[offset]))

    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", new_w, new_h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii"), new_w, new_h, actual_scale


def _with_png_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach bounded, content-derived PNG evidence to a successful capture."""
    encoded = payload.get("screenshot")
    if not isinstance(encoded, str) or not encoded:
        return payload
    raw = base64.b64decode(encoded, validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("screenshot encoder returned invalid PNG bytes")
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("screenshot encoder returned oversized PNG")
    payload["screenshot_bytes"] = len(raw)
    payload["screenshot_sha256"] = hashlib.sha256(raw).hexdigest()
    return payload


def _trace_capture_stage(stage: str) -> None:
    """Write a safe capture stage marker when hidden-run tracing is enabled."""
    trace_path = os.environ.get("LOCALCOMET_TOOLCALL_TRACE", "").strip()
    if not trace_path:
        return
    try:
        with open(trace_path, "a", encoding="utf-8") as trace:
            trace.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\tcapture_stage\t{stage}\n")
    except OSError:
        pass


def capture_screenshot(simulate: bool = False) -> Dict[str, Any]:
    """Capture desktop screenshot, downscale, return base64 PNG.

    Gated by simulate flag: when True no OS capture is performed.
    Primary path uses PIL ImageGrab; fallback uses ctypes BitBlt (Windows GDI).
    Downscale preserves aspect: max 1024x768 and Anthropic pattern
    long_edge 1568 / 1.15M pixels (whichever is stricter).
    No raw shell is invoked.
    """
    if simulate:
        return {
            "ok": True,
            "status": "simulated",
            "mode": "computer_use_real_screenshot",
            "screenshot": "",
            "width": 1024,
            "height": 768,
            "scale": 1.0,
        }
    # --- capture ---
    _trace_capture_stage("start")
    image = None
    raw_bgra = None
    orig_w = orig_h = 0
    try:
        try:
            from PIL import ImageGrab  # type: ignore

            image = ImageGrab.grab(all_screens=True)
        except Exception:
            _trace_capture_stage("imagegrab_failed")
            image = None
        if image is None:
            if os.name != "nt":
                return {"ok": False, "status": "unsupported", "reason": "screenshot requires Windows or PIL ImageGrab", "mode": "computer_use_real_screenshot"}
            # Fallback: ctypes BitBlt -> pure-Python PNG (Pillow is optional).
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            _configure_capture_apis(user32, gdi32, wintypes)
            # Ensure DPI awareness so GetSystemMetrics returns physical pixels
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
            width = int(user32.GetSystemMetrics(0))
            height = int(user32.GetSystemMetrics(1))
            if width <= 0 or height <= 0:
                return {"ok": False, "status": "error", "reason": "invalid screen dimensions", "mode": "computer_use_real_screenshot"}
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            if not hbmp:
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                return {"ok": False, "status": "error", "reason": "CreateCompatibleBitmap failed", "mode": "computer_use_real_screenshot"}
            prev = gdi32.SelectObject(hdc_mem, hbmp)
            SRCCOPY = 0x00CC0020
            ok_blt = gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, SRCCOPY)
            if not ok_blt:
                _trace_capture_stage("bitblt_failed_before_hidden_enum")
                gdi32.SelectObject(hdc_mem, prev)
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                # Non-interactive desktops have no display surface for a
                # desktop-wide BitBlt; fall back to per-window capture.
                _trace_capture_stage("before_printwindow_fallback")
                result = _capture_via_printwindow()
                _trace_capture_stage("after_printwindow_fallback")
                return result
            # Extract bitmap bits via GetDIBits.
            bmi_header_size = 40
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            class BITMAPINFO(ctypes.Structure):
                _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = bmi_header_size
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height  # top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0  # BI_RGB
            buffer_len = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_len)
            ret = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bmi), 0)
            gdi32.SelectObject(hdc_mem, prev)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            if not ret:
                return {"ok": False, "status": "error", "reason": "GetDIBits failed", "mode": "computer_use_real_screenshot"}
            raw_bgra = bytes(buffer)
            orig_w, orig_h = width, height
        if raw_bgra is not None:
            b64, new_w, new_h, actual_scale = _encode_bgra_png(raw_bgra, orig_w, orig_h)
            return _with_png_evidence({
                "ok": True,
                "status": "executed",
                "mode": "computer_use_real_screenshot",
                "screenshot": b64,
                "width": int(new_w),
                "height": int(new_h),
                "scale": float(actual_scale),
                "capture_backend": "gdi_bitblt",
                "capture_scope": "desktop",
            })
        # --- downscale preserving aspect ---
        import base64
        import io

        orig_w, orig_h = int(image.size[0]), int(image.size[1])
        if orig_w <= 0 or orig_h <= 0:
            return {"ok": False, "status": "error", "reason": "invalid image dimensions", "mode": "computer_use_real_screenshot"}
        scale = 1.0
        # Anthropic pattern constraints
        long_edge = max(orig_w, orig_h)
        if long_edge > 1568:
            scale = min(scale, 1568.0 / float(long_edge))
        pixels = float(orig_w) * float(orig_h)
        if pixels > 1_150_000:
            scale = min(scale, (1_150_000 / pixels) ** 0.5)
        # Target max 1024x768
        if orig_w > 1024 or orig_h > 768:
            scale = min(scale, min(1024.0 / float(orig_w), 768.0 / float(orig_h)))
        if scale < 1.0:
            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))
            try:
                # Pillow >= 9.1 uses Resampling
                resample = getattr(getattr(image, "Resampling", image), "LANCZOS", 1)
                image = image.resize((new_w, new_h), resample)
            except Exception:
                image = image.resize((new_w, new_h))
        else:
            new_w, new_h = orig_w, orig_h
            scale = 1.0
        # Recompute actual scale from realized dimensions (round-trip safe)
        actual_scale = float(new_w) / float(orig_w) if orig_w else 1.0
        # Encode PNG base64
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return _with_png_evidence({
            "ok": True,
            "status": "executed",
            "mode": "computer_use_real_screenshot",
            "screenshot": b64,
            "width": int(new_w),
            "height": int(new_h),
            "scale": float(actual_scale),
            "capture_backend": "imagegrab",
            "capture_scope": "desktop",
        })
    except Exception as exc:
        _trace_capture_stage("python_exception")
        return {
            "ok": False,
            "status": "error",
            "reason": "screenshot_capture_failed",
            "mode": "computer_use_real_screenshot",
        }


def _task_action_summary(action: Dict[str, Any]) -> Dict[str, Any]:
    summary = {key: value for key, value in action.items() if key not in {"text", "coordinate"}}
    if "text" in action:
        text = str(action.get("text") or "")
        summary["text_length"] = len(text)
        summary["text_preview"] = _safe_preview(text, 80)
    if "coordinate" in action:
        coordinate = action.get("coordinate")
        summary["coordinate"] = coordinate if isinstance(coordinate, list) and len(coordinate) == 4 else "redacted_invalid"
    return summary


def _task_result_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        key: result.get(key)
        for key in ("ok", "status", "verification", "mode", "reason", "requires_confirmation", "next_decision")
        if key in result
    }
    if isinstance(result.get("screenshot_evidence"), dict):
        summary["screenshot_evidence"] = result["screenshot_evidence"]
    if isinstance(result.get("capture_backend"), str):
        summary["capture_backend"] = result["capture_backend"]
    if isinstance(result.get("capture_scope"), str):
        summary["capture_scope"] = result["capture_scope"]
    if isinstance(result.get("screenshot_bytes"), int):
        summary["screenshot_bytes"] = result["screenshot_bytes"]
    return summary


def _task_observe(label: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        from modules.computer_use_visual_guard_ru import observe_with_ui_map
        full = observe_with_ui_map(label)
        compact = {
            "artifact": full.get("artifact", ""),
            "observation_summary": full.get("observation_summary", {}),
            "ui_map_path": full.get("ui_map", {}).get("ui_map_path", "") if isinstance(full.get("ui_map"), dict) else "",
            "ui_map_element_count": full.get("ui_map", {}).get("element_count", 0) if isinstance(full.get("ui_map"), dict) else 0,
            "ui_markers": full.get("ui_markers", {}),
        }
        return full, compact
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, {"ok": False, "error": str(exc)}


def run_bounded_interaction_task(goal: str, simulate: bool = False, max_steps: int = 6) -> Dict[str, Any]:
    """Execute a bounded sequence of grounded UI interactions.

    This is deliberately an interaction-only composite. App/folder/browser
    launches stay on the host broker path because the confined sidecar cannot
    safely spawn GUI processes. The caller must issue that broker step first;
    this function then handles a finite chain of click/type/key/scroll/wait and
    optional observation primitives with before/after visual evidence.
    """
    goal = str(goal or "").strip()
    max_steps = max(1, min(int(max_steps or 6), 8))
    blocked, reason = _blocked_goal(goal)
    if blocked:
        return {
            "ok": False,
            "status": "blocked",
            "terminal": True,
            "verification": "failed",
            "blocked": True,
            "mode": "computer_use_real_task",
            "reason": reason,
            "goal": goal,
            "steps": [],
        }

    plan = build_real_action_plan(goal, max_steps=max_steps)
    actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
    if not plan.get("ok"):
        return {
            "ok": False,
            "status": "blocked" if plan.get("blocked") else "unavailable",
            "terminal": True,
            "verification": "failed",
            "blocked": bool(plan.get("blocked")),
            "mode": "computer_use_real_task",
            "reason": plan.get("reason", "task planning failed"),
            "goal": goal,
            "steps": [],
        }

    host_kinds = {"open_app", "open_folder", "open_url"}
    host_step = next((action for action in actions if action.get("kind") in host_kinds), None)
    if host_step is not None:
        return {
            "ok": False,
            "status": "blocked",
            "terminal": True,
            "verification": "failed",
            "blocked": True,
            "requires_host_broker_step": True,
            "mode": "computer_use_real_task",
            "reason": "task contains a launch/navigation step; execute that allowlisted host-broker step separately before interaction task",
            "goal": goal,
            "next_host_action": _task_action_summary(host_step),
            "steps": [],
        }

    executable_kinds = {"wait_for_window", "wait", "paste_text", "type_element", "click_element", "double_click_element", "hotkey", "press_key", "scroll", "drag", "screenshot"}
    unsupported = next((action for action in actions if action.get("kind") not in executable_kinds), None)
    if not actions or unsupported is not None or any(not action.get("real_action", True) for action in actions):
        return {
            "ok": False,
            "status": "unavailable",
            "terminal": True,
            "verification": "failed",
            "mode": "computer_use_real_task",
            "reason": "task has no bounded executable interaction sequence",
            "goal": goal,
            "unsupported_action": _task_action_summary(unsupported) if unsupported else None,
            "steps": [],
        }

    steps: List[Dict[str, Any]] = []
    replan_count = 0
    for index, action in enumerate(actions[:max_steps], start=1):
        before_full: Dict[str, Any] = {}
        before_compact: Dict[str, Any] = {"mode": "simulation"}
        if not simulate:
            before_full, before_compact = _task_observe(f"task_step_{index}_before")

        result = execute_real_action(action, simulate=simulate, mission_goal=goal)
        after_full: Dict[str, Any] = {}
        after_compact: Dict[str, Any] = {"mode": "simulation"}
        comparison: Dict[str, Any] = {"decision": "continue", "reason": "simulation; no desktop observation performed"}
        if not simulate:
            after_full, after_compact = _task_observe(f"task_step_{index}_after")
            try:
                from modules.computer_use_visual_guard_ru import compare_observations
                comparison = compare_observations(
                    before_full.get("observation", before_full),
                    after_full.get("observation", after_full),
                    before_full.get("ui_map", {}),
                    after_full.get("ui_map", {}),
                )
            except Exception as exc:
                comparison = {"decision": "stop", "reason": f"visual comparison unavailable: {exc}"}

        step = {
            "step_index": index,
            "action": _task_action_summary(action),
            "result": _task_result_summary(result),
            "before": before_compact,
            "after": after_compact,
            "visual_guard": {
                "decision": comparison.get("decision", "stop"),
                "reason": comparison.get("reason", ""),
                "changed_signals": comparison.get("changed_signals", 0),
                "stable_signals": comparison.get("stable_signals", 0),
            },
        }
        steps.append(step)

        if result.get("requires_confirmation") or result.get("status") in {"blocked", "requires_confirmation"}:
            return {
                "ok": False,
                "status": "blocked",
                "terminal": True,
                "verification": "failed",
                "blocked": True,
                "mode": "computer_use_real_task",
                "reason": result.get("reason", "task step requires confirmation"),
                "goal": goal,
                "steps": steps,
                "completed_steps": index - 1,
                "total_steps": len(actions[:max_steps]),
            }
        if not result.get("ok"):
            return {
                "ok": False,
                "status": "failed",
                "terminal": True,
                "verification": "failed",
                "mode": "computer_use_real_task",
                "reason": result.get("reason", "task step failed"),
                "goal": goal,
                "steps": steps,
                "completed_steps": index - 1,
                "total_steps": len(actions[:max_steps]),
            }
        if str(result.get("status") or "").lower() in {"launch_pending", "pending", "awaiting_observation"}:
            return {
                "ok": False,
                "status": "awaiting_observation",
                "terminal": False,
                "verification": "pending",
                "mode": "computer_use_real_task",
                "reason": "task step completed without terminal observation",
                "goal": goal,
                "steps": steps,
                "completed_steps": index,
                "total_steps": len(actions[:max_steps]),
            }
        decision = str(comparison.get("decision") or "continue")
        if decision == "stop":
            return {
                "ok": False,
                "status": "failed",
                "terminal": True,
                "verification": "failed",
                "mode": "computer_use_real_task",
                "reason": comparison.get("reason", "visual guard stopped the task"),
                "goal": goal,
                "steps": steps,
                "completed_steps": index,
                "total_steps": len(actions[:max_steps]),
            }
        if decision == "ask_user":
            return {
                "ok": False,
                "status": "blocked",
                "terminal": True,
                "verification": "failed",
                "blocked": True,
                "requires_confirmation": True,
                "mode": "computer_use_real_task",
                "reason": comparison.get("reason", "visual guard requires user decision"),
                "goal": goal,
                "steps": steps,
                "completed_steps": index,
                "total_steps": len(actions[:max_steps]),
            }
        if decision == "replan":
            replan_count += 1

    return {
        "ok": True,
        "status": "completed",
        "terminal": True,
        "succeeded": True,
        "verification": "not_applicable",
        "mode": "computer_use_real_task",
        "goal": goal,
        "steps": steps,
        "completed_steps": len(steps),
        "total_steps": len(actions[:max_steps]),
        "replan_count": replan_count,
        "note": "all bounded interaction steps completed; no independent task-level postcondition was asserted",
    }


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
        if kind == "drag":
            coord = action.get("coordinate")
            if isinstance(coord, list) and len(coord) == 4:
                return drag(coordinate=coord, simulate=simulate)
            return drag(
                from_x=action.get("from_x"),
                from_y=action.get("from_y"),
                to_x=action.get("to_x"),
                to_y=action.get("to_y"),
                coordinate=coord if isinstance(coord, list) else None,
                simulate=simulate,
            )
        if kind == "screenshot":
            return capture_screenshot(simulate=simulate)
        if kind in {"task", "multi_step_task"}:
            return run_bounded_interaction_task(
                str(action.get("goal") or mission_goal),
                simulate=simulate,
                max_steps=int(action.get("max_steps") or 6),
            )
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
            "drag",
            "wait_for_window",
            "screenshot",
            "task",
            "multi_step_task",
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
