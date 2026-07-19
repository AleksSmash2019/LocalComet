import ctypes
import ctypes.wintypes
import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value


ROOT_DIR = get_project_root()
BRIDGE_DIR = ROOT_DIR / "Projects" / "ChatGPTDesktopBridge"
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "chatgpt_desktop_bridge"
PROMPT_PATH = BRIDGE_DIR / "chatgpt_desktop_prompt.md"
RESPONSE_PATH = BRIDGE_DIR / "chatgpt_desktop_response.md"
LOOP_STATE_PATH = BRIDGE_DIR / "loop_state.json"
DEFAULT_LOOP_INTERVAL_SECONDS = 20


VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_loop_state():
    return {
        "enabled": False,
        "started_at": "",
        "stopped_at": "",
        "goal": "",
        "mode": "grimoire",
        "send": True,
        "prompt_sent": False,
        "last_action": "",
        "last_message": "",
        "last_step_at": "",
        "interval_seconds": DEFAULT_LOOP_INTERVAL_SECONDS,
        "rate_limited": False,
        "rate_limited_at": "",
        "cooldown_until": "",
        "last_send_blocked_reason": "",
    }


def _load_loop_state():
    _ensure_dirs()
    state = _default_loop_state()

    if LOOP_STATE_PATH.exists():
        try:
            loaded = json.loads(LOOP_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass

    return state


def _save_loop_state(state):
    _ensure_dirs()
    LOOP_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _now():
    return datetime.now()


def _now_iso():
    return _now().isoformat(timespec="seconds")


def _parse_iso_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _format_send_blocked_message(state):
    reason = str(state.get("last_send_blocked_reason") or "ChatGPT Desktop rate limit cooldown is active.").strip()
    cooldown_until = str(state.get("cooldown_until") or "").strip()

    if cooldown_until:
        return f"STOP: ChatGPT Desktop send blocked: {reason} Cooldown until: {cooldown_until}."

    return f"STOP: ChatGPT Desktop send blocked: {reason}"


def mark_chatgpt_desktop_rate_limited(reason="", cooldown_minutes=30):
    state = _load_loop_state()
    now = _now()

    try:
        minutes = int(cooldown_minutes)
    except Exception:
        minutes = 30

    if minutes < 1:
        minutes = 30

    reason = str(reason or "Manual ChatGPT Desktop rate-limit guard.").strip()
    cooldown_until = now + timedelta(minutes=minutes)
    state.update({
        "rate_limited": True,
        "rate_limited_at": now.isoformat(timespec="seconds"),
        "cooldown_until": cooldown_until.isoformat(timespec="seconds"),
        "last_send_blocked_reason": reason,
        "last_action": "rate_limit_marked",
        "last_message": f"GPT Desktop send paused for {minutes} minutes: {reason}",
        "last_step_at": now.isoformat(timespec="seconds"),
    })
    _save_loop_state(state)
    report = _write_report("rate_limit_mark", state)

    try:
        set_value("chatgpt_desktop_rate_limited", True)
        set_value("chatgpt_desktop_cooldown_until", state["cooldown_until"])
    except Exception:
        pass

    return {
        "ok": True,
        "message": state["last_message"],
        "cooldown_minutes": minutes,
        "report_path": report,
        **state,
    }


def clear_chatgpt_desktop_rate_limit():
    state = _load_loop_state()
    now = _now_iso()
    state.update({
        "rate_limited": False,
        "rate_limited_at": "",
        "cooldown_until": "",
        "last_send_blocked_reason": "",
        "last_action": "rate_limit_cleared",
        "last_message": "GPT Desktop rate-limit guard cleared.",
        "last_step_at": now,
    })
    _save_loop_state(state)
    report = _write_report("rate_limit_clear", state)

    try:
        set_value("chatgpt_desktop_rate_limited", False)
        set_value("chatgpt_desktop_cooldown_until", "")
    except Exception:
        pass

    return {"ok": True, "message": state["last_message"], "report_path": report, **state}


def is_chatgpt_desktop_send_allowed():
    state = _load_loop_state()

    if not state.get("rate_limited"):
        return {"ok": True, "allowed": True, "message": "ChatGPT Desktop send allowed.", **state}

    cooldown_until = _parse_iso_datetime(state.get("cooldown_until"))

    if cooldown_until and cooldown_until <= _now():
        state.update({
            "rate_limited": False,
            "rate_limited_at": "",
            "cooldown_until": "",
            "last_send_blocked_reason": "",
            "last_action": "rate_limit_auto_cleared",
            "last_message": "GPT Desktop rate-limit cooldown expired; send allowed.",
            "last_step_at": _now_iso(),
        })
        _save_loop_state(state)
        return {"ok": True, "allowed": True, "message": state["last_message"], **state}

    message = _format_send_blocked_message(state)
    state.update({
        "last_action": "send_blocked_rate_limit",
        "last_message": message,
        "last_step_at": _now_iso(),
    })
    _save_loop_state(state)

    return {"ok": False, "allowed": False, "message": message, **state}


def _window_text(hwnd):
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_class(hwnd):
    try:
        buffer = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_rect(hwnd):
    try:
        rect = ctypes.wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return {}

        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
        }
    except Exception:
        return {}


def _window_info(hwnd):
    return {
        "hwnd": int(hwnd or 0),
        "title": _window_text(hwnd),
        "class": _window_class(hwnd),
        "rect": _window_rect(hwnd),
    }


def _is_chatgpt_window_info(info):
    title_lower = str(info.get("title") or "").lower()
    return "chatgpt" in title_lower or title_lower.startswith("grimoire")


def _find_chatgpt_windows():
    user32 = ctypes.windll.user32
    matches = []

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            info = _window_info(hwnd)

            if _is_chatgpt_window_info(info):
                matches.append(info)
        except Exception:
            pass

        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(callback)
    user32.EnumWindows(enum_proc, 0)
    return matches


def _open_clipboard(user32):
    for _ in range(8):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def _clipboard_get_windows():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = ctypes.wintypes.BOOL
    user32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

    if not _open_clipboard(user32):
        raise RuntimeError("OpenClipboard failed")

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""

        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            raise RuntimeError("GetClipboardData failed")

        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("GlobalLock failed")

        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _clipboard_set_windows(text):
    text = str(text or "")
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
    user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.wintypes.BOOL
    user32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.wintypes.HANDLE]
    user32.SetClipboardData.restype = ctypes.wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL
    kernel32.GlobalFree.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = ctypes.wintypes.HGLOBAL

    data = ctypes.create_unicode_buffer(text)
    byte_count = ctypes.sizeof(data)
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, byte_count)

    if not handle:
        raise RuntimeError("GlobalAlloc failed")

    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        raise RuntimeError("GlobalLock failed")

    try:
        ctypes.memmove(locked, data, byte_count)
    finally:
        kernel32.GlobalUnlock(handle)

    if not _open_clipboard(user32):
        kernel32.GlobalFree(handle)
        raise RuntimeError("OpenClipboard failed")

    try:
        if not user32.EmptyClipboard():
            raise RuntimeError("EmptyClipboard failed")

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData failed")

        handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)


def _clipboard_set_tkinter(text):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(str(text or ""))
    root.update()
    root.destroy()


def _clipboard_get_tkinter():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        return root.clipboard_get()
    finally:
        root.destroy()


def _clipboard_set_powershell(text):
    command = (
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$text = [Console]::In.ReadToEnd(); "
        "Set-Clipboard -Value $text"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        input=str(text or ""),
        text=True,
        encoding="utf-8",
        check=True,
        capture_output=True,
        timeout=10,
    )


def get_clipboard_text():
    errors = []

    for method_name, getter in [
        ("windows_api", _clipboard_get_windows),
        ("tkinter", _clipboard_get_tkinter),
    ]:
        try:
            return getter()
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")

    command = "Get-Clipboard -Raw"
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            encoding="utf-8",
            check=True,
            capture_output=True,
            timeout=10,
        )
        return completed.stdout
    except Exception as exc:
        errors.append(f"powershell: {exc}")
        raise RuntimeError("; ".join(errors))


def _clipboard_set(text):
    expected = str(text or "")
    attempts = []

    for method_name, setter in [
        ("windows_api", _clipboard_set_windows),
        ("tkinter", _clipboard_set_tkinter),
        ("powershell", _clipboard_set_powershell),
    ]:
        try:
            setter(expected)
            actual = get_clipboard_text()

            if actual == expected:
                return {
                    "ok": True,
                    "method": method_name,
                    "chars": len(expected),
                    "verified": True,
                }

            attempts.append({
                "method": method_name,
                "ok": False,
                "error": f"verification mismatch: expected {len(expected)} chars, got {len(actual or '')}",
            })
        except Exception as exc:
            attempts.append({"method": method_name, "ok": False, "error": str(exc)})

    return {
        "ok": False,
        "message": "Clipboard write verification failed.",
        "chars": len(expected),
        "attempts": attempts,
    }


def clipboard_self_test():
    _ensure_dirs()
    test_text = f"LocalComet clipboard self-test {_stamp()}"
    result = _clipboard_set(test_text)
    actual = ""

    try:
        actual = get_clipboard_text()
    except Exception as exc:
        result.setdefault("attempts", []).append({"method": "get_clipboard_text", "ok": False, "error": str(exc)})

    ok = bool(result.get("ok")) and actual == test_text
    payload = {
        "ok": ok,
        "message": "Clipboard self-test OK." if ok else "Clipboard self-test failed.",
        "test_text": test_text,
        "clipboard_chars": len(actual or ""),
        "method": result.get("method", ""),
        "verified": actual == test_text,
        "write_result": result,
    }
    payload["report_path"] = _write_report("clipboard_self_test", payload)
    return payload


def _key_down(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _key_up(vk):
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _press_ctrl_v():
    _key_down(VK_CONTROL)
    time.sleep(0.05)
    _key_down(VK_V)
    time.sleep(0.05)
    _key_up(VK_V)
    time.sleep(0.05)
    _key_up(VK_CONTROL)


def _press_enter():
    _key_down(VK_RETURN)
    time.sleep(0.05)
    _key_up(VK_RETURN)


def _click_screen_point(x, y):
    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _looks_sensitive(prompt):
    text = str(prompt or "")
    patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"sk-proj-[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_ -]?key|password|passwd|token|secret)\s*[:=]\s*\S+",
        r"(?i)(пароль|токен|секретный ключ)\s*[:=]\s*\S+",
    ]
    return [pattern for pattern in patterns if re.search(pattern, text)]


def _write_report(action, payload):
    _ensure_dirs()
    path = REPORTS_DIR / f"chatgpt_desktop_bridge_{_stamp()}.md"
    lines = [
        "# ChatGPT Desktop Bridge Report",
        "",
        f"- action: {action}",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
    ]

    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f"- {key}: {value}")

    path.write_text("\n".join(lines), encoding="utf-8")

    try:
        set_value("last_chatgpt_desktop_bridge_report", str(path))
    except Exception:
        pass

    return str(path)


def chatgpt_desktop_status():
    _ensure_dirs()
    windows = _find_chatgpt_windows()
    result = {
        "available": bool(windows),
        "window_count": len(windows),
        "windows": windows,
        "prompt_path": str(PROMPT_PATH),
        "response_path": str(RESPONSE_PATH),
    }
    report = _write_report("status", result)
    result["report_path"] = report

    try:
        set_value("chatgpt_desktop_bridge: да", "да")
        set_value("last_chatgpt_desktop_available", bool(windows))
        set_value("last_chatgpt_desktop_window", windows[0]["title"] if windows else "")
    except Exception:
        pass

    return result


def prepare_chatgpt_desktop_prompt(goal, mode="patch"):
    _ensure_dirs()
    goal = str(goal or "").strip()
    mode = str(mode or "patch").strip() or "patch"

    prompt = (
        "# LocalComet -> ChatGPT Desktop Request\n\n"
        "You are Grimoire helping improve the local LocalComet / LocalAgent project.\n"
        "Give a focused, safe answer. Prefer one small implementable step.\n\n"
        "## Mode\n"
        f"{mode}\n\n"
        "## User Goal\n"
        f"{goal or 'нет'}\n\n"
        "## Required Response Contract\n"
        "- Decision\n"
        "- Risk level\n"
        "- Files allowed to touch\n"
        "- Files forbidden\n"
        "- Exact operations\n"
        "- Tests/checks\n"
        "- Stop conditions\n\n"
        "Do not request changes to config/router/planner/executor/apply/validate/browser bridge unless explicitly required.\n"
    )

    PROMPT_PATH.write_text(prompt, encoding="utf-8")

    try:
        set_value("last_chatgpt_desktop_prompt", str(PROMPT_PATH))
        set_value("last_chatgpt_desktop_goal", goal)
    except Exception:
        pass

    return prompt


def copy_prompt_to_clipboard(prompt):
    prompt = str(prompt or "")
    sensitive = _looks_sensitive(prompt)

    if sensitive:
        return {
            "ok": False,
            "message": "STOP: prompt похож на содержащий секреты. Clipboard не изменен.",
            "sensitive_markers": sensitive,
        }

    clipboard_result = _clipboard_set(prompt)

    if not clipboard_result.get("ok"):
        report = _write_report("copy_prompt", {"prompt_chars": len(prompt), **clipboard_result})
        return {
            "ok": False,
            "message": "STOP: prompt не скопирован в clipboard: проверка записи не прошла.",
            "prompt_chars": len(prompt),
            "clipboard_result": clipboard_result,
            "report_path": report,
        }

    report = _write_report("copy_prompt", {"prompt_chars": len(prompt), **clipboard_result})
    return {
        "ok": True,
        "message": "Prompt скопирован в clipboard.",
        "prompt_chars": len(prompt),
        "clipboard_method": clipboard_result.get("method", ""),
        "verified": True,
        "report_path": report,
    }


def focus_chatgpt_desktop_window():
    windows = _find_chatgpt_windows()

    if not windows:
        report = _write_report("focus", {"ok": False, "message": "ChatGPT Desktop window not found"})
        return {"ok": False, "message": "Окно ChatGPT Desktop не найдено.", "windows": [], "report_path": report}

    window = windows[0]
    hwnd = int(window["hwnd"])
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    payload = {
        "ok": bool(foreground.get("ok")),
        "window": window,
        "foreground": foreground,
    }

    if foreground.get("ok"):
        payload["message"] = "Окно ChatGPT Desktop сфокусировано."
    else:
        payload["message"] = "Окно ChatGPT Desktop найдено, но foreground-проверка не подтвердила фокус."

    report = _write_report("focus", payload)
    payload["report_path"] = report
    return payload


def get_foreground_window_info():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "", "class": "", "rect": {}}
        return _window_info(hwnd)
    except Exception:
        return {"hwnd": 0, "title": "", "class": "", "rect": {}}


def verify_chatgpt_desktop_foreground(write_report=True):
    info = get_foreground_window_info()
    ok = _is_chatgpt_window_info(info)
    payload = {
        "ok": ok,
        "message": "ChatGPT Desktop is foreground." if ok else "Foreground window is not ChatGPT Desktop.",
        "foreground": info,
    }

    if write_report:
        payload["report_path"] = _write_report("verify_foreground", payload)

    return payload


def _safe_input_click_point(rect):
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    left = int(rect.get("left") or 0)
    top = int(rect.get("top") or 0)
    right = int(rect.get("right") or 0)
    bottom = int(rect.get("bottom") or 0)

    if width <= 200 or height <= 200:
        return None

    x = left + int(width * 0.50)
    y = top + int(height * 0.89)
    x = min(max(x, left + 80), right - 80)
    y = min(max(y, top + 160), bottom - 45)
    return {"x": int(x), "y": int(y)}


def focus_chatgpt_desktop_input_box(dry_run=True):
    windows = _find_chatgpt_windows()

    if not windows:
        payload = {
            "ok": False,
            "dry_run": bool(dry_run),
            "message": "Окно ChatGPT Desktop не найдено.",
            "windows": [],
        }
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    window = windows[0]
    rect = window.get("rect") or {}
    point = _safe_input_click_point(rect)

    payload = {
        "dry_run": bool(dry_run),
        "window": window,
        "click_point": point,
    }

    if not point:
        payload["ok"] = False
        payload["message"] = "Не удалось рассчитать безопасную точку клика внутри окна ChatGPT Desktop."
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    focus_result = focus_chatgpt_desktop_window()
    payload["focus_result"] = focus_result

    if not focus_result.get("ok"):
        payload["ok"] = False
        payload["message"] = focus_result.get("message", "Окно ChatGPT Desktop не сфокусировано.")
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    if dry_run:
        payload["ok"] = True
        payload["message"] = "DRY RUN: input focus point calculated; click not performed."
        payload["report_path"] = _write_report("focus_input", payload)
        return payload

    _click_screen_point(point["x"], point["y"])
    time.sleep(0.25)
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    payload["foreground"] = foreground
    payload["ok"] = bool(foreground.get("ok"))
    payload["message"] = (
        "Поле ввода ChatGPT Desktop должно быть сфокусировано."
        if payload["ok"]
        else "Клик выполнен, но foreground-проверка не подтвердила ChatGPT Desktop."
    )
    payload["report_path"] = _write_report("focus_input", payload)
    return payload


def paste_prompt_after_input_focus(prompt=None, send=False, dry_run=True):
    _ensure_dirs()
    prompt = PROMPT_PATH.read_text(encoding="utf-8") if prompt is None and PROMPT_PATH.exists() else str(prompt or "")
    sensitive = _looks_sensitive(prompt)

    payload = {
        "dry_run": bool(dry_run),
        "send": bool(send),
        "focused_path": True,
        "prompt_chars": len(prompt),
        "sensitive_markers": sensitive,
    }

    if sensitive:
        payload["ok"] = False
        payload["message"] = "STOP: prompt похож на содержащий секреты."
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    if send and not dry_run:
        send_allowed = is_chatgpt_desktop_send_allowed()
        payload["send_allowed"] = bool(send_allowed.get("allowed"))

        if not send_allowed.get("allowed"):
            payload["ok"] = False
            payload["message"] = send_allowed.get("message", "STOP: ChatGPT Desktop send blocked.")
            payload["rate_limited"] = bool(send_allowed.get("rate_limited"))
            payload["cooldown_until"] = send_allowed.get("cooldown_until", "")
            payload["last_send_blocked_reason"] = send_allowed.get("last_send_blocked_reason", "")
            payload["report_path"] = _write_report("paste_prompt_focused", payload)
            return payload

    status = chatgpt_desktop_status()
    payload["available"] = status.get("available")
    payload["window_count"] = status.get("window_count")

    if not status.get("available"):
        payload["ok"] = False
        payload["message"] = "Окно ChatGPT Desktop не найдено."
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    focus_preview = focus_chatgpt_desktop_input_box(dry_run=True)
    payload["focus_preview"] = focus_preview

    if dry_run:
        payload["ok"] = bool(focus_preview.get("ok"))
        payload["message"] = (
            "DRY RUN: prompt готов, окно найдено, input-point рассчитан; paste/send не выполнялись."
            if payload["ok"]
            else focus_preview.get("message", "DRY RUN: input focus check failed.")
        )
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    copy_result = copy_prompt_to_clipboard(prompt)
    payload["copy_result"] = copy_result

    if not copy_result.get("ok"):
        payload["ok"] = False
        payload["message"] = copy_result.get("message", "STOP: prompt не скопирован в clipboard.")
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    focus_input_result = focus_chatgpt_desktop_input_box(dry_run=False)
    payload["focus_input_result"] = focus_input_result

    if not focus_input_result.get("ok"):
        payload["ok"] = False
        payload["message"] = focus_input_result.get("message", "STOP: поле ввода ChatGPT Desktop не сфокусировано.")
        payload["report_path"] = _write_report("paste_prompt_focused", payload)
        return payload

    _press_ctrl_v()
    time.sleep(0.35)

    if send:
        time.sleep(0.65)
        _press_enter()

    payload["ok"] = True
    payload["message"] = "Prompt вставлен в ChatGPT Desktop через focused path." + (" Enter отправлен." if send else " Enter не отправлялся.")
    payload["report_path"] = _write_report("paste_prompt_focused", payload)

    try:
        set_value("last_chatgpt_desktop_paste_result", payload["message"])
    except Exception:
        pass

    return payload


def paste_prompt_to_chatgpt_desktop(prompt=None, send=False, dry_run=True):
    return paste_prompt_after_input_focus(prompt=prompt, send=send, dry_run=dry_run)


def verify_chatgpt_desktop_send_state(before_clipboard="", after_clipboard="", send_result=None):
    send_result = send_result if isinstance(send_result, dict) else {}
    foreground = verify_chatgpt_desktop_foreground(write_report=False)
    send_requested = bool(send_result.get("send"))
    dry_run = bool(send_result.get("dry_run"))
    paste_ok = bool(send_result.get("ok"))
    rate_limited = bool(send_result.get("rate_limited"))
    send_allowed = send_result.get("send_allowed", True)
    clipboard_still_prompt = bool(before_clipboard) and str(after_clipboard or "") == str(before_clipboard or "")

    evidence = {
        "foreground_ok": bool(foreground.get("ok")),
        "paste_path_ok": paste_ok,
        "send_requested": send_requested,
        "dry_run": dry_run,
        "rate_limit_not_active": not rate_limited and send_allowed is not False,
        "clipboard_still_equals_prompt": clipboard_still_prompt,
        "message": send_result.get("message", ""),
    }

    likely_sent = (
        send_requested
        and not dry_run
        and paste_ok
        and evidence["foreground_ok"]
        and evidence["rate_limit_not_active"]
        and not clipboard_still_prompt
    )
    needs_manual_check = send_requested and not likely_sent

    if likely_sent:
        message = "ChatGPT Desktop send likely succeeded."
    elif not send_requested:
        message = "Send was not requested; prompt may only be prepared or pasted."
    elif clipboard_still_prompt:
        message = "Not enough evidence: clipboard still equals the prompt; manual check needed."
    else:
        message = "Not enough evidence that ChatGPT Desktop sent the prompt; manual check needed."

    return {
        "ok": bool(paste_ok) and (likely_sent or not send_requested),
        "likely_sent": likely_sent,
        "message": message,
        "evidence": evidence,
        "needs_manual_check": needs_manual_check,
    }


def save_clipboard_response_from_chatgpt_desktop():
    _ensure_dirs()
    text = get_clipboard_text()

    if not str(text or "").strip():
        report = _write_report("capture_response", {"ok": False, "message": "Clipboard пустой"})
        return {"ok": False, "message": "Clipboard пустой.", "report_path": report}

    RESPONSE_PATH.write_text(text, encoding="utf-8")
    report = _write_report("capture_response", {"ok": True, "response_chars": len(text), "response_path": str(RESPONSE_PATH)})

    try:
        set_value("last_chatgpt_desktop_response", str(RESPONSE_PATH))
    except Exception:
        pass

    return {"ok": True, "message": "Ответ из clipboard сохранен.", "response_path": str(RESPONSE_PATH), "response_chars": len(text), "report_path": report}


def chatgpt_desktop_loop_status():
    send_allowed = is_chatgpt_desktop_send_allowed()
    state = _load_loop_state()
    state["send_allowed"] = bool(send_allowed.get("allowed"))
    state["send_blocked_message"] = "" if send_allowed.get("allowed") else send_allowed.get("message", "")
    state["state_path"] = str(LOOP_STATE_PATH)
    state["prompt_path"] = str(PROMPT_PATH)
    state["response_path"] = str(RESPONSE_PATH)
    return state


def start_chatgpt_desktop_loop(goal="", mode="grimoire", send=True):
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")
    state.update({
        "enabled": True,
        "started_at": now,
        "stopped_at": "",
        "goal": str(goal or state.get("goal") or "Предложи следующий безопасный шаг для LocalComet.").strip(),
        "mode": str(mode or "grimoire").strip() or "grimoire",
        "send": bool(send),
        "prompt_sent": False,
        "last_action": "start",
        "last_message": "GPT Desktop loop включен.",
        "last_step_at": now,
        "interval_seconds": int(state.get("interval_seconds") or DEFAULT_LOOP_INTERVAL_SECONDS),
    })
    _save_loop_state(state)
    report = _write_report("loop_start", state)
    state["report_path"] = report

    try:
        set_value("chatgpt_desktop_loop_enabled", True)
        set_value("chatgpt_desktop_loop_goal", state["goal"])
    except Exception:
        pass

    return {"ok": True, "message": "GPT Desktop loop включен.", **state}


def stop_chatgpt_desktop_loop():
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")
    state.update({
        "enabled": False,
        "stopped_at": now,
        "last_action": "stop",
        "last_message": "GPT Desktop loop выключен.",
        "last_step_at": now,
    })
    _save_loop_state(state)
    report = _write_report("loop_stop", state)
    state["report_path"] = report

    try:
        set_value("chatgpt_desktop_loop_enabled", False)
    except Exception:
        pass

    return {"ok": True, "message": "GPT Desktop loop выключен.", **state}


def chatgpt_desktop_loop_step():
    state = _load_loop_state()
    now = datetime.now().isoformat(timespec="seconds")

    if not state.get("enabled"):
        return {"ok": False, "message": "GPT Desktop loop выключен.", **state}

    send_allowed = is_chatgpt_desktop_send_allowed()
    state = _load_loop_state()

    if not send_allowed.get("allowed"):
        message = send_allowed.get("message", "STOP: GPT Desktop loop ждет окончания rate-limit cooldown.")
        state.update({
            "last_action": "wait_rate_limit",
            "last_message": message,
            "last_step_at": now,
        })
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_rate_limit", "send_allowed": False, **state}

    if not state.get("prompt_sent"):
        prompt = prepare_chatgpt_desktop_prompt(state.get("goal"), mode=state.get("mode") or "grimoire")
        result = paste_prompt_to_chatgpt_desktop(prompt, send=bool(state.get("send")), dry_run=False)
        state.update({
            "prompt_sent": bool(result.get("ok")),
            "last_action": "send_prompt",
            "last_message": result.get("message", ""),
            "last_step_at": now,
        })
        _save_loop_state(state)
        return {"ok": bool(result.get("ok")), "message": result.get("message", ""), "step": "send_prompt", "result": result, **state}

    clipboard_text = get_clipboard_text()
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""

    if not str(clipboard_text or "").strip():
        message = "Ответ еще не найден: clipboard пустой."
        state.update({"last_action": "wait_response", "last_message": message, "last_step_at": now})
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_response", **state}

    if clipboard_text == prompt_text or str(clipboard_text).lstrip().startswith("# LocalComet -> ChatGPT Desktop Request"):
        message = "Ответ еще не найден: в clipboard пока находится отправленный prompt."
        state.update({"last_action": "wait_response", "last_message": message, "last_step_at": now})
        _save_loop_state(state)
        return {"ok": True, "message": message, "step": "wait_response", **state}

    result = save_clipboard_response_from_chatgpt_desktop()
    state.update({
        "last_action": "capture_response",
        "last_message": result.get("message", ""),
        "last_step_at": now,
    })
    _save_loop_state(state)
    return {"ok": bool(result.get("ok")), "message": result.get("message", ""), "step": "capture_response", "result": result, **state}


def latest_chatgpt_desktop_bridge_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("chatgpt_desktop_bridge_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
