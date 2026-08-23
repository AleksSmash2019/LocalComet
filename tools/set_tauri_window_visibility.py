from __future__ import annotations

import sys
import win32gui


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "hide"
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet window not found")
    command = 5 if mode == "show" else 0
    win32gui.ShowWindow(hwnd, command)
    if mode == "show":
        win32gui.SetForegroundWindow(hwnd)
    print({"hwnd": hwnd, "mode": mode, "visible": bool(win32gui.IsWindowVisible(hwnd))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
