from __future__ import annotations

import ctypes
import os
import sys
import time

CTRL_BREAK_EVENT = 1
ATTACH_CONSOLE = ctypes.windll.kernel32.AttachConsole
FREE_CONSOLE = ctypes.windll.kernel32.FreeConsole
GENERATE_CONSOLE_CTRL_EVENT = ctypes.windll.kernel32.GenerateConsoleCtrlEvent

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: graceful_ctrl_break_detached.py PID")
    pid = int(sys.argv[1])
    before = ctypes.GetLastError() if hasattr(ctypes, "GetLastError") else 0
    freed = bool(FREE_CONSOLE())
    attached = bool(ATTACH_CONSOLE(pid))
    attach_error = ctypes.get_last_error()
    sent = bool(GENERATE_CONSOLE_CTRL_EVENT(CTRL_BREAK_EVENT, 0)) if attached else False
    send_error = ctypes.get_last_error()
    if attached:
        FREE_CONSOLE()
    print(
        f"pid={pid} freed={freed} attached={attached} attach_error={attach_error} "
        f"sent={sent} send_error={send_error} before={before}"
    )
    time.sleep(3)
