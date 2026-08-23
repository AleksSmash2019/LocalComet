from __future__ import annotations

import win32gui


def main() -> int:
    hwnd = win32gui.FindWindow(None, "LocalComet")
    if not hwnd:
        raise RuntimeError("LocalComet window not found")
    win32gui.ShowWindow(hwnd, 0)
    print({"hwnd": hwnd, "visible": bool(win32gui.IsWindowVisible(hwnd))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
