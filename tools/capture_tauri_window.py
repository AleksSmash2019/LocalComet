from __future__ import annotations

from pathlib import Path
import ctypes

import win32gui
import win32ui

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run" / "tauri_window_current.bmp"


def main() -> int:
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet window not found")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source_dc, width, height)
    memory_dc.SelectObject(bitmap)
    result = ctypes.windll.user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bitmap.SaveBitmapFile(memory_dc, str(OUT))
    memory_dc.DeleteDC()
    source_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, window_dc)
    print({"hwnd": hwnd, "rect": [left, top, right, bottom], "width": width, "height": height, "print_window": result, "path": str(OUT)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
