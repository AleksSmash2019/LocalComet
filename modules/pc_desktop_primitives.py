from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root
import json
import platform
import re
import traceback


from core.state import get_value, set_value


ROOT_DIR = get_project_root()
PROJECTS_DIR = ROOT_DIR / "Projects"
REPORTS_DIR = PROJECTS_DIR / "Reports" / "pc_desktop_primitives"
ACTIONS_DIR = PROJECTS_DIR / "PCAgent" / "DesktopActions"

SAFE_HOTKEY_ALLOWLIST = {
    "ctrl+c": {
        "risk": "low",
        "description": "Copy selected text.",
        "exec_allowed": False,
    },
    "ctrl+a": {
        "risk": "medium",
        "description": "Select all in active field/window.",
        "exec_allowed": False,
    },
    "esc": {
        "risk": "low",
        "description": "Close menu/dialog or cancel current transient UI.",
        "exec_allowed": False,
    },
    "f5": {
        "risk": "medium",
        "description": "Refresh active window/page.",
        "exec_allowed": False,
    },
    "ctrl+l": {
        "risk": "medium",
        "description": "Focus browser/file-explorer address bar.",
        "exec_allowed": False,
    },
}

DANGEROUS_TITLE_TERMS = [
    "password",
    "пароль",
    "token",
    "secret",
    "private key",
    "bank",
    "банк",
    "payment",
    "casino",
    "ставк",
    "registry",
    "regedit",
]

BLOCKED_HOTKEY_TERMS = [
    "delete",
    "del",
    "alt+f4",
    "ctrl+w",
    "ctrl+shift+esc",
    "win+r",
    "cmd",
    "powershell",
    "enter",
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(text):
    return str(text or "").lower().replace("ё", "е").strip()


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _is_windows():
    return platform.system().lower() == "windows"


def _rect_to_payload(rect):
    left, top, right, bottom = rect
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": int(right - left),
        "height": int(bottom - top),
    }


def _safe_title(title):
    lower = _norm(title)
    hits = [term for term in DANGEROUS_TITLE_TERMS if term in lower]
    return {
        "safe": not hits,
        "matched_terms": hits,
        "reason": "" if not hits else "sensitive window title terms: " + ", ".join(hits),
    }


def _enum_windows_ctypes():
    if not _is_windows():
        return []

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        windows = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title:
                return True

            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            payload = {
                "title": title,
                "class": class_buffer.value,
                "rect": _rect_to_payload((rect.left, rect.top, rect.right, rect.bottom)),
                "hwnd": int(hwnd),
                "safety": _safe_title(title),
            }
            windows.append(payload)
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return windows
    except Exception:
        return []


def _active_window_ctypes():
    if not _is_windows():
        return {}

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {}

        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buffer, 256)

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        title = buffer.value.strip()
        return {
            "title": title,
            "class": class_buffer.value,
            "rect": _rect_to_payload((rect.left, rect.top, rect.right, rect.bottom)),
            "hwnd": int(hwnd),
            "safety": _safe_title(title),
        }
    except Exception:
        return {}


def _mouse_position_ctypes():
    if not _is_windows():
        return {"ok": False, "error": "mouse position is currently implemented for Windows only"}

    try:
        import ctypes
        from ctypes import wintypes

        point = wintypes.POINT()
        ok = ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        if not ok:
            return {"ok": False, "error": "GetCursorPos failed"}
        return {"ok": True, "x": int(point.x), "y": int(point.y)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _window_at_point(windows, x, y):
    for window in windows:
        rect = window.get("rect", {})
        left = int(rect.get("left", 0))
        top = int(rect.get("top", 0))
        right = int(rect.get("right", 0))
        bottom = int(rect.get("bottom", 0))
        if left <= x <= right and top <= y <= bottom:
            return window
    return {}


def _parse_two_ints(text):
    numbers = re.findall(r"-?\d+", str(text or ""))
    if len(numbers) < 2:
        raise ValueError("Need two coordinates: x y")
    return int(numbers[0]), int(numbers[1])


def _normalize_hotkey(combo):
    combo = _norm(combo)
    combo = combo.replace(" ", "")
    combo = combo.replace("control", "ctrl")
    combo = combo.replace("контрол", "ctrl")
    combo = combo.replace("контроль", "ctrl")
    combo = combo.replace("альт", "alt")
    combo = combo.replace("дел", "del")
    combo = combo.replace("эск", "esc")
    combo = combo.replace("escape", "esc")
    combo = combo.replace("plus", "+")
    combo = combo.replace("++", "+")
    return combo.strip("+")


def list_windows():
    windows = _enum_windows_ctypes()

    if not windows:
        try:
            from modules.desktop_observer import observe_desktop

            observed = observe_desktop()
            windows = observed.get("windows", [])
            for item in windows:
                item["safety"] = _safe_title(item.get("title", ""))
        except Exception:
            windows = []

    active = _active_window_ctypes()

    payload = {
        "ok": True,
        "mode": "desktop_windows",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window": active,
        "windows": windows,
        "count": len(windows),
    }
    set_value("pc_desktop_primitives_windows", payload)
    return payload


def mouse_position():
    payload = {
        "ok": True,
        "mode": "desktop_mouse",
        "generated_at": _now(),
        "position": _mouse_position_ctypes(),
        "active_window": _active_window_ctypes(),
    }
    set_value("pc_desktop_primitives_mouse", payload)
    return payload


def screenshot_metadata():
    _ensure_dirs()
    try:
        from modules.desktop_observer import observe_desktop

        observed = observe_desktop()
        payload = {
            "ok": True,
            "mode": "desktop_screenshot_metadata",
            "generated_at": _now(),
            "screenshot_path": observed.get("screenshot_path", ""),
            "screenshot_error": observed.get("screenshot_error", ""),
            "report_path": observed.get("report_path", ""),
            "active_window": observed.get("active_window", {}),
            "windows_count": len(observed.get("windows", []) or []),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "desktop_screenshot_metadata",
            "generated_at": _now(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    set_value("pc_desktop_primitives_screenshot", payload)
    return payload


def dry_click(x, y):
    x = int(x)
    y = int(y)
    windows_payload = list_windows()
    window = _window_at_point(windows_payload.get("windows", []), x, y)
    action = {
        "id": f"dry_click_{_stamp()}",
        "type": "click",
        "point": {"x": x, "y": y},
        "target_window": window,
        "dry_run_required": True,
        "confirmation_required": True,
        "executed": False,
        "result": "DRY_RUN: click not executed.",
        "safety": {
            "allowlisted": bool(window) and window.get("safety", {}).get("safe", True),
            "blocked_terms": window.get("safety", {}).get("matched_terms", []) if window else [],
            "reason": window.get("safety", {}).get("reason", "") if window else "No window found at point.",
        },
    }

    payload = {
        "ok": True,
        "mode": "desktop_dry_click",
        "generated_at": _now(),
        "action": action,
    }

    _ensure_dirs()
    path = ACTIONS_DIR / f"dry_click_{_stamp()}.json"
    payload["path"] = _write_json(path, payload)
    set_value("pc_desktop_primitives_last_dry_click", payload)
    return payload


def validate_hotkey(combo):
    normalized = _normalize_hotkey(combo)
    blocked_hits = [term for term in BLOCKED_HOTKEY_TERMS if term in normalized]
    allow_info = SAFE_HOTKEY_ALLOWLIST.get(normalized)

    if blocked_hits:
        return {
            "ok": False,
            "mode": "desktop_hotkey_validation",
            "generated_at": _now(),
            "combo": combo,
            "normalized": normalized,
            "allowed": False,
            "executed": False,
            "reason": "Blocked hotkey terms: " + ", ".join(blocked_hits),
        }

    if not allow_info:
        return {
            "ok": False,
            "mode": "desktop_hotkey_validation",
            "generated_at": _now(),
            "combo": combo,
            "normalized": normalized,
            "allowed": False,
            "executed": False,
            "reason": "Hotkey is not in safe allowlist.",
            "allowlist": sorted(SAFE_HOTKEY_ALLOWLIST.keys()),
        }

    return {
        "ok": True,
        "mode": "desktop_hotkey_validation",
        "generated_at": _now(),
        "combo": combo,
        "normalized": normalized,
        "allowed": True,
        "exec_allowed": bool(allow_info.get("exec_allowed")),
        "executed": False,
        "risk": allow_info.get("risk", "unknown"),
        "description": allow_info.get("description", ""),
        "reason": "DRY_RUN: hotkey validated but not executed.",
    }


def dry_hotkey(combo):
    payload = validate_hotkey(combo)
    payload["dry_run"] = True
    payload["result"] = "DRY_RUN: hotkey not executed."
    set_value("pc_desktop_primitives_last_dry_hotkey", payload)
    return payload


def _find_window_by_title(query):
    query_norm = _norm(query)
    windows_payload = list_windows()
    matches = []
    for window in windows_payload.get("windows", []):
        title = window.get("title", "")
        if query_norm and query_norm in _norm(title):
            matches.append(window)
    return matches


def dry_focus_window(query):
    matches = _find_window_by_title(query)
    selected = matches[0] if matches else {}
    payload = {
        "ok": bool(selected),
        "mode": "desktop_dry_focus_window",
        "generated_at": _now(),
        "query": str(query or "").strip(),
        "matches": matches[:10],
        "selected": selected,
        "executed": False,
        "result": "DRY_RUN: focus not changed." if selected else "No matching window found.",
        "next": f"pc desktop focus подтверждаю: {query}" if selected else "",
    }
    set_value("pc_desktop_primitives_last_dry_focus", payload)
    return payload


def focus_window(raw_query):
    raw_query = str(raw_query or "").strip()
    lower = _norm(raw_query)
    if "подтверждаю:" not in lower:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "executed": False,
            "reason": "Нужна явная фраза подтверждения.",
            "example": "pc desktop focus подтверждаю: LocalComet",
        }

    query = re.sub(r"(?i)подтверждаю\s*:", "", raw_query, count=1).strip()
    matches = _find_window_by_title(query)
    selected = matches[0] if matches else {}

    if not selected:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "executed": False,
            "reason": "No matching window found.",
        }

    safety = selected.get("safety", {})
    if not safety.get("safe", True):
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "reason": safety.get("reason", "Unsafe window title."),
        }

    if not _is_windows():
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "reason": "Focus execution is currently implemented for Windows only.",
        }

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = int(selected.get("hwnd", 0))
        if not hwnd:
            raise RuntimeError("No hwnd for selected window.")

        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd))

        payload = {
            "ok": ok,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": ok,
            "result": "Window focused." if ok else "SetForegroundWindow returned false.",
            "active_after": _active_window_ctypes(),
        }
        set_value("pc_desktop_primitives_last_focus", payload)
        return payload
    except Exception as exc:
        return {
            "ok": False,
            "mode": "desktop_focus_window",
            "generated_at": _now(),
            "query": query,
            "selected": selected,
            "executed": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def status():
    payload = {
        "ok": True,
        "mode": "pc_desktop_primitives",
        "generated_at": _now(),
        "platform": platform.platform(),
        "active_window": _active_window_ctypes(),
        "mouse": _mouse_position_ctypes(),
        "commands": [
            "pc desktop status",
            "pc desktop windows",
            "pc desktop mouse",
            "pc desktop screenshot",
            "pc desktop dry click <x> <y>",
            "pc desktop dry hotkey <combo>",
            "pc desktop dry focus <title>",
            "pc desktop focus подтверждаю: <title>",
            "pc desktop report",
        ],
        "safety": [
            "No blind click execution.",
            "Dry click only previews target window.",
            "Hotkeys are validation-only in v6.22.",
            "Focus window requires explicit confirmation.",
            "Sensitive window titles are blocked.",
            "No shell/cmd/powershell/delete actions.",
        ],
    }
    set_value("pc_desktop_primitives_status", payload)
    return payload


def format_status(payload=None):
    payload = payload or status()
    lines = [
        "PC Desktop Interaction Primitives:",
        f"- ok: {payload.get('ok')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- platform: {payload.get('platform')}",
        f"- active_window: {(payload.get('active_window') or {}).get('title', '')}",
        f"- mouse: {payload.get('mouse')}",
        "",
        "Commands:",
    ]
    lines.extend("- " + item for item in payload.get("commands", []))
    lines.append("")
    lines.append("Safety:")
    lines.extend("- " + item for item in payload.get("safety", []))
    return "\n".join(lines)


def report(note=""):
    _ensure_dirs()
    payload = {
        "ok": True,
        "generated_at": _now(),
        "note": str(note or "").strip(),
        "status": status(),
        "windows": list_windows(),
        "mouse": mouse_position(),
        "screenshot": screenshot_metadata(),
        "last_dry_click": get_value("pc_desktop_primitives_last_dry_click", ""),
        "last_dry_hotkey": get_value("pc_desktop_primitives_last_dry_hotkey", ""),
        "last_dry_focus": get_value("pc_desktop_primitives_last_dry_focus", ""),
        "last_focus": get_value("pc_desktop_primitives_last_focus", ""),
    }

    json_path = REPORTS_DIR / f"pc_desktop_primitives_report_{_stamp()}.json"
    md_path = REPORTS_DIR / f"pc_desktop_primitives_report_{_stamp()}.md"
    _write_json(json_path, payload)

    md = [
        "# PC Desktop Interaction Primitives Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- note: {payload['note'] or 'none'}",
        "",
        "## Status",
        "",
        "```text",
        format_status(payload["status"]),
        "```",
        "",
        "## Windows count",
        "",
        str(payload["windows"].get("count", 0)),
        "",
        "## Screenshot",
        "",
        "```json",
        json.dumps(payload["screenshot"], ensure_ascii=False, indent=2),
        "```",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"ok": True, "report": str(md_path), "json": str(json_path)}


def format_payload(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2)


def dispatch(command):
    text = str(command or "").strip()
    lower = _norm(text)

    if lower in {"pc desktop", "pc desktop status", "pc desktop статус", "desktop status"}:
        return format_status(status())

    if lower in {"pc desktop windows", "pc desktop окна", "desktop windows"}:
        return format_payload(list_windows())

    if lower in {"pc desktop mouse", "pc desktop мышь", "desktop mouse"}:
        return format_payload(mouse_position())

    if lower in {"pc desktop screenshot", "pc desktop скрин", "desktop screenshot"}:
        return format_payload(screenshot_metadata())

    if lower in {"pc desktop report", "pc desktop отчет", "pc desktop отчёт", "desktop report"}:
        return format_payload(report("manual report"))

    prefixes = [
        ("pc desktop dry click ", "dry_click"),
        ("pc desktop dry клик ", "dry_click"),
        ("desktop dry click ", "dry_click"),
        ("pc desktop dry hotkey ", "dry_hotkey"),
        ("pc desktop dry хоткей ", "dry_hotkey"),
        ("desktop dry hotkey ", "dry_hotkey"),
        ("pc desktop dry focus ", "dry_focus"),
        ("pc desktop dry фокус ", "dry_focus"),
        ("desktop dry focus ", "dry_focus"),
        ("pc desktop focus ", "focus"),
        ("pc desktop фокус ", "focus"),
        ("desktop focus ", "focus"),
    ]

    for prefix, action in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix):].strip(" :,-—")
            if action == "dry_click":
                try:
                    x, y = _parse_two_ints(value)
                    return format_payload(dry_click(x, y))
                except Exception as exc:
                    return format_payload({"ok": False, "error": str(exc), "example": "pc desktop dry click 100 200"})
            if action == "dry_hotkey":
                return format_payload(dry_hotkey(value))
            if action == "dry_focus":
                return format_payload(dry_focus_window(value))
            if action == "focus":
                return format_payload(focus_window(value))

    return format_payload({
        "ok": False,
        "error": "Unknown PC Desktop command.",
        "help": status().get("commands", []),
    })


def is_desktop_command(command):
    lower = _norm(command)
    exact = {
        "pc desktop",
        "pc desktop status",
        "pc desktop статус",
        "desktop status",
        "pc desktop windows",
        "pc desktop окна",
        "desktop windows",
        "pc desktop mouse",
        "pc desktop мышь",
        "desktop mouse",
        "pc desktop screenshot",
        "pc desktop скрин",
        "desktop screenshot",
        "pc desktop report",
        "pc desktop отчет",
        "pc desktop отчёт",
        "desktop report",
    }
    if lower in exact:
        return True

    prefixes = (
        "pc desktop dry click ",
        "pc desktop dry клик ",
        "desktop dry click ",
        "pc desktop dry hotkey ",
        "pc desktop dry хоткей ",
        "desktop dry hotkey ",
        "pc desktop dry focus ",
        "pc desktop dry фокус ",
        "desktop dry focus ",
        "pc desktop focus ",
        "pc desktop фокус ",
        "desktop focus ",
    )
    return lower.startswith(prefixes)
