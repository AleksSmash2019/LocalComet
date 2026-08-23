import ctypes
import base64
import ctypes.wintypes
import hashlib
import json
import os
import struct

from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "desktop_observer"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


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
        user32 = ctypes.windll.user32
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_rect(hwnd):
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
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


def _active_window():
    if os.name != "nt":
        return {"title": "", "class": "", "rect": {}, "error": "desktop observer currently supports Windows"}

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return {
            "title": _window_text(hwnd),
            "class": _window_class(hwnd),
            "rect": _window_rect(hwnd),
            "hwnd": int(hwnd),
        }
    except Exception as exc:
        return {"title": "", "class": "", "rect": {}, "error": str(exc)}


def _visible_windows(limit=30):
    if os.name != "nt":
        return []

    user32 = ctypes.windll.user32
    windows = []

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            title = _window_text(hwnd)
            if not title:
                return True

            rect = _window_rect(hwnd)
            if rect and (rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0):
                return True

            windows.append({
                "title": title,
                "class": _window_class(hwnd),
                "rect": rect,
                "hwnd": int(hwnd),
            })

            return len(windows) < limit
        except Exception:
            return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(callback)
    user32.EnumWindows(enum_proc, 0)
    return windows


def _capture_screenshot():
    """Capture through the shared real-action backend and return path/error/meta.

    The old local fallback used desktop-wide BitBlt only. That API has no display
    surface on a hidden desktop and produced the misleading ``BitBlt failed``
    result. The shared backend first tries ImageGrab and then per-window
    PrintWindow, preserving a truthful backend name and bounded PNG bytes.
    """
    _ensure_dirs()
    png_path = SCREENSHOTS_DIR / f"desktop_{_stamp()}.png"
    try:
        from modules.computer_use_real_actions_ru import capture_screenshot

        payload = capture_screenshot(simulate=False)
        metadata = {
            "capture_backend": payload.get("capture_backend", "imagegrab"),
            "capture_scope": payload.get("capture_scope", "desktop"),
            "capture_window_title": payload.get("capture_window_title", ""),
            "capture_hwnd": payload.get("capture_hwnd"),
            "width": payload.get("width", 0),
            "height": payload.get("height", 0),
            "scale": payload.get("scale", 1.0),
        }
        encoded = payload.get("screenshot")
        if payload.get("ok") and isinstance(encoded, str) and encoded:
            raw = base64.b64decode(encoded, validate=True)
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("real screenshot backend returned non-PNG bytes")
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("real screenshot backend returned oversized PNG")
            png_path.write_bytes(raw)
            metadata["bytes"] = len(raw)
            metadata["sha256"] = hashlib.sha256(raw).hexdigest()
            return str(png_path), "", metadata

        reason = str(payload.get("reason") or payload.get("error") or "real screenshot backend returned no frame")
        metadata["backend_error"] = reason
        return "", reason, metadata
    except Exception as exc:
        return "", f"real screenshot backend failed: {exc}", {
            "capture_backend": "real_action_backend",
            "backend_error": str(exc),
        }


def _capture_screenshot_bmp():
    if os.name != "nt":
        return "", "BMP fallback currently supports Windows only"

    path = SCREENSHOTS_DIR / f"desktop_{_stamp()}.bmp"
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hdc_screen = None
    hdc_mem = None
    hbmp = None
    old_obj = None

    try:
        x = user32.GetSystemMetrics(76)
        y = user32.GetSystemMetrics(77)
        width = user32.GetSystemMetrics(78)
        height = user32.GetSystemMetrics(79)

        if width <= 0 or height <= 0:
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            x = 0
            y = 0

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        old_obj = gdi32.SelectObject(hdc_mem, hbmp)

        srccopy = 0x00CC0020
        captureblt = 0x40000000
        if not gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x, y, srccopy | captureblt):
            return "", "BitBlt failed"

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.wintypes.DWORD),
                ("biWidth", ctypes.wintypes.LONG),
                ("biHeight", ctypes.wintypes.LONG),
                ("biPlanes", ctypes.wintypes.WORD),
                ("biBitCount", ctypes.wintypes.WORD),
                ("biCompression", ctypes.wintypes.DWORD),
                ("biSizeImage", ctypes.wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.wintypes.LONG),
                ("biYPelsPerMeter", ctypes.wintypes.LONG),
                ("biClrUsed", ctypes.wintypes.DWORD),
                ("biClrImportant", ctypes.wintypes.DWORD),
            ]

        class BitmapInfo(ctypes.Structure):
            _fields_ = [
                ("bmiHeader", BitmapInfoHeader),
                ("bmiColors", ctypes.wintypes.DWORD * 3),
            ]

        bitmap_info = BitmapInfo()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BitmapInfoHeader)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = 0
        bitmap_info.bmiHeader.biSizeImage = width * height * 4

        buffer = ctypes.create_string_buffer(bitmap_info.bmiHeader.biSizeImage)
        lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bitmap_info), 0)
        if lines == 0:
            return "", "GetDIBits failed"

        pixel_data = buffer.raw
        file_header_size = 14
        info_header_size = 40
        offset = file_header_size + info_header_size
        file_size = offset + len(pixel_data)

        with path.open("wb") as handle:
            handle.write(struct.pack("<2sIHHI", b"BM", file_size, 0, 0, offset))
            handle.write(struct.pack(
                "<IiiHHIIiiII",
                info_header_size,
                width,
                height,
                1,
                32,
                0,
                len(pixel_data),
                0,
                0,
                0,
                0,
            ))
            handle.write(pixel_data)

        return str(path), ""
    except Exception as exc:
        return "", str(exc)
    finally:
        try:
            if old_obj and hdc_mem:
                gdi32.SelectObject(hdc_mem, old_obj)
            if hbmp:
                gdi32.DeleteObject(hbmp)
            if hdc_mem:
                gdi32.DeleteDC(hdc_mem)
            if hdc_screen:
                user32.ReleaseDC(0, hdc_screen)
        except Exception:
            pass


def _write_report(result):
    _ensure_dirs()
    path = REPORTS_DIR / f"desktop_observe_{_stamp()}.md"
    active = result.get("active_window") or {}
    windows = result.get("windows") or []

    lines = [
        "# Desktop Observe Report",
        "",
        f"- created_at: {result.get('created_at')}",
        f"- screenshot_path: {result.get('screenshot_path') or 'нет'}",
                f"- screenshot_error: {result.get('screenshot_error') or 'нет'}",
        f"- screenshot_backend: {result.get('screenshot_backend') or 'нет'}",
        f"- screenshot_scope: {(result.get('screenshot_meta') or {}).get('capture_scope') or 'нет'}",
        f"- screenshot_sha256: {(result.get('screenshot_meta') or {}).get('sha256') or 'нет'}",
        f"- uia_status: {result.get('uia_status') or 'нет'}",
        f"- ui_elements: {len(result.get('ui_elements') or [])}",
        f"- observation_state: {result.get('observation_state') or 'unknown'}",
        "",
        "## Active Window",

        "",
        f"- title: {active.get('title') or 'нет'}",
        f"- class: {active.get('class') or 'нет'}",
        f"- rect: `{json.dumps(active.get('rect') or {}, ensure_ascii=False)}`",
        "",
        "## Visible Windows",
        "",
    ]

    if windows:
        for index, window in enumerate(windows, start=1):
            title = window.get("title") or "нет"
            cls = window.get("class") or "нет"
            rect = json.dumps(window.get("rect") or {}, ensure_ascii=False)
            lines.append(f"{index}. `{title}` | class: `{cls}` | rect: `{rect}`")
    else:
        lines.append("- нет")

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def observe_desktop(write_report=True):
    _ensure_dirs()
    screenshot_path, screenshot_error, screenshot_meta = _capture_screenshot()
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "active_window": _active_window(),
        "windows": _visible_windows(),
        "screenshot_path": screenshot_path,
        "screenshot_error": screenshot_error,
        "screenshot_backend": screenshot_meta.get("capture_backend", ""),
        "screenshot_meta": screenshot_meta,
        "ui_elements": [],
        "uia_status": "not_attempted",
        "observation_state": "failed",
        "ok": False,
        "report_path": "",
    }
    try:
        from modules.pc_ui_parser_adapter import _uia_elements_for_desktop

        elements, uia_status = _uia_elements_for_desktop()
        result["ui_elements"] = elements[:200]
        result["uia_status"] = uia_status
    except Exception as exc:
        result["uia_status"] = f"uia unavailable: {exc}"

    has_screenshot = bool(screenshot_path)
    has_window = bool(result.get("active_window", {}).get("title") or result.get("windows"))
    has_uia = bool(result.get("ui_elements"))
    if has_screenshot and (has_window or has_uia):
        result["observation_state"] = "available"
    elif has_screenshot or has_window or has_uia:
        result["observation_state"] = "partial"
    else:
        result["observation_state"] = "failed"
    result["ok"] = result["observation_state"] != "failed"

    if write_report:

        result["report_path"] = _write_report(result)

    try:
        set_value("desktop_observer: да", "да")
        set_value("last_desktop_observation_report", result.get("report_path") or "")
        set_value("last_desktop_screenshot", result.get("screenshot_path") or "")
        set_value("last_desktop_active_window", (result.get("active_window") or {}).get("title") or "")
        set_value("last_desktop_observation", json.dumps(result, ensure_ascii=False)[:5000])
    except Exception:
        pass

    return result


def format_desktop_observation(result):
    active = result.get("active_window") or {}
    windows = result.get("windows") or []
    lines = [
        "Desktop Observe:",
        f"- created_at: {result.get('created_at')}",
        f"- active_window: {active.get('title') or 'нет'}",
        f"- active_class: {active.get('class') or 'нет'}",
        f"- visible_windows: {len(windows)}",
        f"- screenshot: {result.get('screenshot_path') or 'нет'}",
        f"- screenshot_error: {result.get('screenshot_error') or 'нет'}",
        f"- report: {result.get('report_path') or 'нет'}",
        "",
        "Visible windows:",
    ]

    if windows:
        for index, window in enumerate(windows[:12], start=1):
            lines.append(f"{index}. {window.get('title') or 'нет'}")
    else:
        lines.append("- нет")

    return "\n".join(lines)


def latest_desktop_observation_report():
    if not REPORTS_DIR.exists():
        return ""

    reports = sorted(REPORTS_DIR.glob("desktop_observe_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else ""
